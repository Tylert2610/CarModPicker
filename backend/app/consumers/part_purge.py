"""Drain the part purge cascade off the `parts` stream through the `part-purge` queue.

`handle_stream` enqueues one message per tombstoned part and `handle_queue` performs
the four cross-domain deletes. Every step is query-then-delete, so replays are no-ops.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from uuid import UUID

from app.db.dynamo.tombstones import DELETED_ATTRIBUTE

logger = logging.getLogger(__name__)

SEQUENCE_NUMBER = "sequenceNumber"
MESSAGE_ID = "messageId"

QUEUE_URL_VARIABLE = "PART_PURGE_QUEUE_URL"

MESSAGE_VERSION = 1
MESSAGE_KIND = "part-purge"


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image's low level wire format.

    The string, boolean, number and null forms are unwrapped; anything else is
    returned untouched for the caller to reject.
    """
    if not isinstance(value, Mapping):
        return value
    if "S" in value:
        return value["S"]
    if "BOOL" in value:
        return value["BOOL"]
    if "N" in value:
        return value["N"]
    if "NULL" in value:
        return None
    return value


def _images(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """`(new, old)` for one record, each `{}` when the record does not carry it."""
    dynamodb = record.get("dynamodb")
    if not isinstance(dynamodb, Mapping):
        return {}, {}
    new_image = dynamodb.get("NewImage")
    old_image = dynamodb.get("OldImage")
    return (
        new_image if isinstance(new_image, Mapping) else {},
        old_image if isinstance(old_image, Mapping) else {},
    )


def _tombstoned(image: Mapping[str, Any]) -> bool:
    """Whether an image carries the `deleted` flag.

    The flag is the state and `deleted_at` is only the audit trail, so the
    timestamp is deliberately not consulted.
    """
    return bool(_plain(image.get(DELETED_ATTRIBUTE)))


def part_id_from_record(record: Mapping[str, Any]) -> Optional[UUID]:
    """The part this record tombstones, or `None` when it does not tombstone one.

    An ordinary edit, an already-tombstoned row, a REMOVE and an unreadable id
    all answer `None`, because none of them is retryable.
    """
    new_image, old_image = _images(record)
    if not new_image:
        return None
    if not _tombstoned(new_image):
        return None
    if _tombstoned(old_image):
        return None

    part_id = _plain(new_image.get("id"))
    if not isinstance(part_id, str):
        return None
    try:
        return UUID(part_id)
    except ValueError:
        logger.warning(
            "Part purge stream: a tombstoned record carries an id that is not a UUID; skipping it.",
            extra={"part_id": part_id, "event_name": record.get("eventName")},
        )
        return None


def group_records_by_part(records: Iterable[Mapping[str, Any]]) -> Dict[UUID, List[str]]:
    """Map each tombstoned part to the sequence numbers of the records that asked.

    Collapses a batch to one message per part, and lets a failed enqueue report
    every contributing record rather than only the last.
    """
    grouped: Dict[UUID, List[str]] = {}
    for record in records:
        part_id = part_id_from_record(record)
        if part_id is None:
            continue
        sequence_number = record.get(SEQUENCE_NUMBER)
        if sequence_number is None:
            dynamodb = record.get("dynamodb")
            if isinstance(dynamodb, Mapping):
                sequence_number = dynamodb.get("SequenceNumber")
        if sequence_number is None:
            grouped.setdefault(part_id, [])
            continue
        grouped.setdefault(part_id, []).append(str(sequence_number))
    return grouped


def message_body(part_id: UUID) -> str:
    """The queue message for one part's cascade: the part id and nothing else.

    Carrying the related row ids would be a snapshot a retry could act on after
    the rows had changed, which is the one way this could delete too much.
    """
    return json.dumps({"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "part_id": str(part_id)})


def part_id_from_message(body: str) -> Optional[UUID]:
    """The part id out of a queue message body, or `None` when it is unreadable.

    `None` is terminal, not retryable: the message is dropped with a warning
    rather than spending five receives to reach the dead letter queue.
    """
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        logger.warning("Part purge queue: a message body is not JSON; dropping it.")
        return None
    if not isinstance(payload, Mapping):
        logger.warning("Part purge queue: a message body is not an object; dropping it.")
        return None
    part_id = payload.get("part_id")
    if not isinstance(part_id, str):
        logger.warning("Part purge queue: a message body carries no part_id; dropping it.")
        return None
    try:
        return UUID(part_id)
    except ValueError:
        logger.warning(
            "Part purge queue: a message body carries a part_id that is not a UUID; dropping it.",
            extra={"part_id": part_id},
        )
        return None


def enqueue_part_purges(client: Any, queue_url: str, part_ids: Sequence[UUID]) -> None:
    """Send one message per part, one `send_message` each.

    Not `send_message_batch`, whose per-entry failures come back in the body and
    would have to be mapped back to the records that asked for each part.
    """
    for part_id in part_ids:
        client.send_message(QueueUrl=queue_url, MessageBody=message_body(part_id))


def process_stream_records(
    client: Any,
    queue_url: str,
    records: Iterable[Mapping[str, Any]],
) -> List[str]:
    """Enqueue a cascade for every part this batch tombstoned; return the failures.

    Parts are independent, so one failed enqueue does not abandon the rest.
    """
    failures: List[str] = []
    for part_id, sequence_numbers in group_records_by_part(records).items():
        try:
            enqueue_part_purges(client, queue_url, [part_id])
        except Exception:
            logger.exception(
                "Part purge stream: failed to enqueue the cascade for a part; reporting its records for retry.",
                extra={"part_id": str(part_id), "records": len(sequence_numbers)},
            )
            failures.extend(sequence_numbers)
        else:
            logger.info(
                "Part purge stream: enqueued the cascade for a tombstoned part.",
                extra={"part_id": str(part_id), "records": len(sequence_numbers)},
            )
    return failures


def purge_related_rows(repos: Any, part_id: UUID) -> Dict[str, int]:
    """Delete every row in the four cross-domain tables that references the part.

    Each is a query followed by a delete of exactly those keys, which is the
    whole idempotency argument: a replay finds nothing and writes nothing.
    """
    votes = repos.votes.delete_for_entities("part", [part_id])
    reports = repos.reports.delete_for_entities("part", [part_id])

    build_list_parts = repos.build_list_parts
    usage_ids = [str(usage.id) for usage in build_list_parts.query_all("part_id-index", part_id)]
    if usage_ids:
        build_list_parts.batch_delete(usage_ids)

    alerts = repos.part_price_alerts.delete_for_parts([part_id])

    return {
        "votes": votes,
        "reports": reports,
        "build_list_parts": len(usage_ids),
        "part_price_alerts": alerts,
    }


def process_queue_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Drain a batch of queue messages and return the ids of the ones that failed.

    One cascade per message, isolated, so a throttle on one part does not re-run
    the cascade for every other part in the batch.
    """
    failures: List[str] = []
    for record in records:
        message_id = record.get(MESSAGE_ID)
        body = record.get("body")
        if not isinstance(body, str):
            logger.warning(
                "Part purge queue: a message carries no body; dropping it.",
                extra={"message_id": message_id},
            )
            continue
        part_id = part_id_from_message(body)
        if part_id is None:
            continue
        try:
            removed = purge_related_rows(repos, part_id)
        except Exception:
            logger.exception(
                "Part purge queue: the cascade failed for a part; reporting the message for retry.",
                extra={"part_id": str(part_id), "message_id": message_id},
            )
            if message_id is not None:
                failures.append(str(message_id))
        else:
            logger.info(
                "Part purge queue: cascade complete.",
                extra={"part_id": str(part_id), "message_id": message_id, **removed},
            )
    return failures


def queue_url() -> str:
    """The `part-purge` queue URL from the environment, raising when it is unset.

    Defaulting would ack a stream batch with nothing enqueued, which is exactly
    the silent data loss this consumer exists to prevent.
    """
    url = os.environ.get(QUEUE_URL_VARIABLE)
    if not url:
        raise RuntimeError(
            f"{QUEUE_URL_VARIABLE} is not set; the part purge consumer cannot enqueue a cascade without it."
        )
    return url


def handle_stream(event: Mapping[str, Any], client: Any) -> Dict[str, List[Dict[str, str]]]:
    """The stream half, with the SQS client passed in.

    Separate from the entrypoint so a test can drive it with a fake client and
    no AWS at all, which is the same split every other consumer makes.
    """
    records = event.get("Records") or []
    failures = process_stream_records(client, queue_url(), records)
    if failures:
        logger.warning(
            "Part purge stream: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": sequence} for sequence in failures]}


def handle_queue(event: Mapping[str, Any], repos: Any) -> Dict[str, List[Dict[str, str]]]:
    """The queue half, with the repository bundle passed in so tests need no AWS.

    Returns the `batchItemFailures` shape keyed by `messageId`; an empty list is
    returned explicitly, since an unparseable result retries the whole batch.
    """
    records = event.get("Records") or []
    failures = process_queue_records(repos, records)
    if failures:
        logger.warning(
            "Part purge queue: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": message_id} for message_id in failures]}


def is_queue_event(event: Mapping[str, Any]) -> bool:
    """Whether this event came from SQS rather than from the DynamoDB stream.

    One function serves both mappings and tells them apart by `eventSource`. An
    empty batch reads as a stream event, which either half handles identically.
    """
    records = event.get("Records") or []
    for record in records:
        if isinstance(record, Mapping) and record.get("eventSource") == "aws:sqs":
            return True
    return False
