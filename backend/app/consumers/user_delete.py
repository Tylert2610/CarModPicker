"""Drain the account delete cascade off the `users` stream through the `user-delete` queue.

The delete tombstones the user and frees the `username` and `email` reservations; this
removes the rows they owned. Every step is query-then-delete, so replays are no-ops.
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

QUEUE_URL_VARIABLE = "USER_DELETE_QUEUE_URL"

MESSAGE_VERSION = 1
MESSAGE_KIND = "user-delete"


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


def user_id_from_record(record: Mapping[str, Any]) -> Optional[UUID]:
    """The user this record tombstones, or `None` when it does not tombstone one.

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

    user_id = _plain(new_image.get("id"))
    if not isinstance(user_id, str):
        return None
    try:
        return UUID(user_id)
    except ValueError:
        logger.warning(
            "User delete stream: a tombstoned record carries an id that is not a UUID; skipping it.",
            extra={"user_id": user_id, "event_name": record.get("eventName")},
        )
        return None


def group_records_by_user(records: Iterable[Mapping[str, Any]]) -> Dict[UUID, List[str]]:
    """Map each tombstoned user to the sequence numbers of the records that asked.

    Collapses a batch to one message per user, and lets a failed enqueue report
    every contributing record rather than only the last.
    """
    grouped: Dict[UUID, List[str]] = {}
    for record in records:
        user_id = user_id_from_record(record)
        if user_id is None:
            continue
        sequence_number = record.get(SEQUENCE_NUMBER)
        if sequence_number is None:
            dynamodb = record.get("dynamodb")
            if isinstance(dynamodb, Mapping):
                sequence_number = dynamodb.get("SequenceNumber")
        if sequence_number is None:
            grouped.setdefault(user_id, [])
            continue
        grouped.setdefault(user_id, []).append(str(sequence_number))
    return grouped


def message_body(user_id: UUID) -> str:
    """The queue message for one user's cascade: the user id and nothing else.

    Carrying the owned row ids would be a snapshot a retry could act on after
    the rows had changed, which is the one way this could delete too much.
    """
    return json.dumps({"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "user_id": str(user_id)})


def user_id_from_message(body: str) -> Optional[UUID]:
    """The user id out of a queue message body, or `None` when it is unreadable.

    `None` is terminal, not retryable: the message is dropped with a warning
    rather than spending five receives to reach the dead letter queue.
    """
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        logger.warning("User delete queue: a message body is not JSON; dropping it.")
        return None
    if not isinstance(payload, Mapping):
        logger.warning("User delete queue: a message body is not an object; dropping it.")
        return None
    user_id = payload.get("user_id")
    if not isinstance(user_id, str):
        logger.warning("User delete queue: a message body carries no user_id; dropping it.")
        return None
    try:
        return UUID(user_id)
    except ValueError:
        logger.warning(
            "User delete queue: a message body carries a user_id that is not a UUID; dropping it.",
            extra={"user_id": user_id},
        )
        return None


def enqueue_user_deletes(client: Any, queue_url: str, user_ids: Sequence[UUID]) -> None:
    """Send one message per user, one `send_message` each.

    Not `send_message_batch`, whose per-entry failures come back in the body and
    would have to be mapped back to the records that asked for each user.
    """
    for user_id in user_ids:
        client.send_message(QueueUrl=queue_url, MessageBody=message_body(user_id))


def process_stream_records(
    client: Any,
    queue_url: str,
    records: Iterable[Mapping[str, Any]],
) -> List[str]:
    """Enqueue a cascade for every user this batch tombstoned; return the failures.

    Users are independent, so one failed enqueue does not abandon the rest.
    """
    failures: List[str] = []
    for user_id, sequence_numbers in group_records_by_user(records).items():
        try:
            enqueue_user_deletes(client, queue_url, [user_id])
        except Exception:
            logger.exception(
                "User delete stream: failed to enqueue the cascade for a user; reporting its records for retry.",
                extra={"user_id": str(user_id), "records": len(sequence_numbers)},
            )
            failures.extend(sequence_numbers)
        else:
            logger.info(
                "User delete stream: enqueued the cascade for a tombstoned user.",
                extra={"user_id": str(user_id), "records": len(sequence_numbers)},
            )
    return failures


def purge_owned_parts(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Purge the user's parts, and the price alerts the user subscribed to.

    Each part goes through `PartService.purge`, whose tombstone the part purge
    consumer drains. An already-purged part is the success case on a replay.
    """
    from app.api.services.part_service import PartService
    from app.db.dynamo.errors import ItemNotFound

    service = PartService(repos)
    purged = 0
    already_purged = 0
    for part in repos.parts.list_by_user(user_id):
        try:
            service.purge(part)
        except ItemNotFound:
            already_purged += 1
        else:
            purged += 1
    alerts = repos.part_price_alerts.delete_for_user(user_id)
    return {"parts": purged, "parts_already_purged": already_purged, "part_price_alerts": alerts}


def purge_owned_build_lists(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Delete the user's build lists with their children, and their build logs.

    Also the rows the user added to somebody else's list. Every branch deletes
    exactly the keys a query returned, so a replay writes nothing.
    """
    from app.db.dynamo.build_lists import delete_build_list_cascade
    from app.db.dynamo.build_logs import build_log_delete_actions

    owned = repos.build_lists.query_all("user_id-created_at-index", user_id)
    for build_list in owned:
        delete_build_list_cascade(
            build_list.id,
            build_lists=repos.build_lists,
            parts=repos.build_list_parts,
            phases=repos.build_list_phases,
            labor_estimates=repos.build_list_labor_estimates,
            extra_actions=build_log_delete_actions(
                build_list.id, build_logs=repos.build_logs, posts=repos.build_log_posts
            ),
        )
    added_elsewhere = [str(usage.id) for usage in repos.build_list_parts.scan_all() if usage.added_by == user_id]
    if added_elsewhere:
        repos.build_list_parts.batch_delete(added_elsewhere)
    return {
        "build_lists": len(owned),
        "build_list_parts_added_elsewhere": len(added_elsewhere),
    }


def purge_owned_moderation(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Delete the user's votes and reports."""
    return {
        "votes": repos.votes.delete_for_user(user_id),
        "reports": repos.reports.delete_for_user(user_id),
    }


def purge_identity(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Delete the user's OAuth links and WebAuthn credentials.

    Each row is removed in a transaction that also releases its own unique
    labels, without which the same account or authenticator could never re-link.
    """
    accounts = len(repos.oauth_accounts.list_by_user(user_id))
    repos.oauth_accounts.delete_all_for_user(user_id)
    credentials = len(repos.webauthn_credentials.list_by_user(user_id))
    repos.webauthn_credentials.delete_all_for_user(user_id)
    return {"oauth_accounts": accounts, "webauthn_credentials": credentials}


def cascade_user_delete(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Delete every row in the fifteen tables that belonged to the deleted user.

    Parts run first so the part purge consumer can start draining their
    tombstones. This must never write `users`, whose row is already gone.
    """
    counts: Dict[str, int] = {}
    counts.update(purge_owned_parts(repos, user_id))
    counts.update(purge_owned_build_lists(repos, user_id))
    counts.update(purge_owned_moderation(repos, user_id))
    counts.update(purge_identity(repos, user_id))
    return counts


def process_queue_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Drain a batch of queue messages and return the ids of the ones that failed.

    One cascade per message, isolated, so a throttle on one user does not re-run
    the cascade for every other user in the batch.
    """
    failures: List[str] = []
    for record in records:
        message_id = record.get(MESSAGE_ID)
        body = record.get("body")
        if not isinstance(body, str):
            logger.warning(
                "User delete queue: a message carries no body; dropping it.",
                extra={"message_id": message_id},
            )
            continue
        user_id = user_id_from_message(body)
        if user_id is None:
            continue
        try:
            removed = cascade_user_delete(repos, user_id)
        except Exception:
            logger.exception(
                "User delete queue: the cascade failed for a user; reporting the message for retry.",
                extra={"user_id": str(user_id), "message_id": message_id},
            )
            if message_id is not None:
                failures.append(str(message_id))
        else:
            logger.info(
                "User delete queue: cascade complete.",
                extra={"user_id": str(user_id), "message_id": message_id, **removed},
            )
    return failures


def queue_url() -> str:
    """The `user-delete` queue URL from the environment, raising when it is unset.

    Defaulting would ack a stream batch with nothing enqueued, which is exactly
    the silent data loss this consumer exists to prevent.
    """
    url = os.environ.get(QUEUE_URL_VARIABLE)
    if not url:
        raise RuntimeError(
            f"{QUEUE_URL_VARIABLE} is not set; the user delete consumer cannot enqueue a cascade without it."
        )
    return url


def handle_stream(event: Mapping[str, Any], client: Any) -> Dict[str, List[Dict[str, str]]]:
    """The stream half, with the SQS client passed in.

    Separate from the entrypoint so a test can drive it with a fake client and
    no AWS at all, which is the same split row 28's consumer makes.
    """
    records = event.get("Records") or []
    failures = process_stream_records(client, queue_url(), records)
    if failures:
        logger.warning(
            "User delete stream: reporting partial batch failure.",
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
            "User delete queue: reporting partial batch failure.",
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
