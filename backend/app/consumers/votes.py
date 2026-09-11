"""Recompute `parts.net_votes` off the `votes` stream, so `catalog` owns its write.

Each affected part is recounted from the table rather than incremented, which makes
redelivery harmless. Tombstoned entities are skipped and failures reported per record.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

from app.db.dynamo.repository import ItemNotFound
from app.db.dynamo.tombstones import is_tombstoned

logger = logging.getLogger(__name__)

PART_ENTITY_TYPE = "part"

SEQUENCE_NUMBER = "sequenceNumber"


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image's low level wire format.

    Only the string, number and null forms this module reads are unwrapped;
    anything else is returned untouched for the caller to reject.
    """
    if not isinstance(value, Mapping):
        return value
    if "S" in value:
        return value["S"]
    if "N" in value:
        return value["N"]
    if "NULL" in value:
        return None
    return value


def _image(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """The image to read the entity off, new preferred over old.

    INSERT and MODIFY carry `NewImage`, REMOVE only `OldImage`.
    """
    dynamodb = record.get("dynamodb")
    if not isinstance(dynamodb, Mapping):
        return {}
    for key in ("NewImage", "OldImage"):
        image = dynamodb.get(key)
        if isinstance(image, Mapping) and image:
            return image
    return {}


def part_id_from_record(record: Mapping[str, Any]) -> Optional[UUID]:
    """The part this record's vote is on, or `None` if it is not a part vote.

    `None` also covers a missing image and a malformed id, because none of those
    is retryable and failing would send a record to the dead letter queue.
    """
    image = _image(record)
    if _plain(image.get("entity_type")) != PART_ENTITY_TYPE:
        return None
    entity_id = _plain(image.get("entity_id"))
    if not isinstance(entity_id, str):
        return None
    try:
        return UUID(entity_id)
    except ValueError:
        logger.warning(
            "Vote stream record carries an entity_id that is not a UUID; skipping it.",
            extra={"entity_id": entity_id, "event_name": record.get("eventName")},
        )
        return None


def group_records_by_part(records: Iterable[Mapping[str, Any]]) -> Dict[UUID, List[str]]:
    """Map each affected part to the sequence numbers of the records that touched it.

    One recompute per part per batch, and every contributing record is reported
    when that recompute fails.
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


def recompute_net_votes(repos: Any, part_id: UUID) -> Optional[int]:
    """Recount the votes on one part and write the total, returning what it wrote.

    `None` means nothing was written because the part is gone or tombstoned, both
    terminal states rather than retryable ones.
    """
    part = repos.parts.get(str(part_id))
    if part is None:
        logger.info(
            "Vote stream: the part this vote is on no longer exists; nothing to recompute.",
            extra={"part_id": str(part_id)},
        )
        return None
    if is_tombstoned(part):
        logger.info(
            "Vote stream: the part this vote is on is tombstoned; leaving its aggregate alone.",
            extra={"part_id": str(part_id)},
        )
        return None

    upvotes, downvotes = repos.votes.counts(PART_ENTITY_TYPE, part_id)
    net_votes = upvotes - downvotes
    if part.net_votes == net_votes:
        return net_votes
    try:
        repos.parts.update(str(part_id), net_votes=net_votes)
    except ItemNotFound:
        logger.info(
            "Vote stream: the part was deleted while its aggregate was being recomputed.",
            extra={"part_id": str(part_id)},
        )
        return None
    return net_votes


def process_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Recompute every part the batch touched and return the failed sequence numbers.

    Parts are independent, so one failure does not abandon the rest of the batch.
    """
    failures: List[str] = []
    for part_id, sequence_numbers in group_records_by_part(records).items():
        try:
            recompute_net_votes(repos, part_id)
        except Exception:
            logger.exception(
                "Vote stream: failed to recompute net_votes for a part; reporting its records for retry.",
                extra={"part_id": str(part_id), "records": len(sequence_numbers)},
            )
            failures.extend(sequence_numbers)
    return failures


def handle(event: Mapping[str, Any], repos: Any) -> Dict[str, List[Dict[str, str]]]:
    """The handler body, with the repository bundle passed in so tests need no AWS.

    Returns the `batchItemFailures` shape the event source mapping expects; an
    empty list is returned explicitly, since an unparseable result retries all.
    """
    records = event.get("Records") or []
    failures = process_records(repos, records)
    if failures:
        logger.warning(
            "Vote stream: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": sequence} for sequence in failures]}
