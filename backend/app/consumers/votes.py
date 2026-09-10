"""Seam 3: the `net_votes` aggregate, recomputed off the `votes` stream.

Split plan row 24, section 1.3's seam 3. `vote_service._sync_part_net_votes`
used to write `parts.net_votes` inline on every vote create, update and remove,
which is `moderation` writing a table `catalog` owns. This module is the
inversion: a Lambda consuming the `votes` DynamoDB stream, owned by `catalog`,
recomputing the aggregate and writing it to the part.

**What a record gives us and what it does not.** The stream carries
`NEW_AND_OLD_IMAGES`, so an INSERT has the new vote, a MODIFY has both images
and a REMOVE has only the old one. None of them carries the part's total. The
handler therefore does not add or subtract: it takes the `(entity_type,
entity_id)` pair off whichever image is present and recounts every vote on that
entity. Recounting is what makes the handler idempotent, which is the property
the delivery guarantee actually requires. DynamoDB streams guarantee order per
partition key and at-least-once delivery, so the same record can arrive twice,
and a handler that decremented a counter per event would drift permanently on
the first redelivery. A recount converges no matter how many times it runs or in
what order two entities' batches interleave.

**One recompute per entity per batch, not one per record.** Ordering is per
partition key, which for `votes` is the vote id, so a batch can hold several
votes on the same part in any order. Deduplicating to the set of affected
entities before recounting means a batch of fifty votes on one part is one
query and one write rather than fifty of each, and the answer is the same
either way because the recount reads the current state of the table.

**Only parts.** Votes are polymorphic over `entity_type`: a vote can be on a
car generation, a build list or a part, and only parts carry a denormalised
`net_votes`. Records for the other two entity types are dropped before any
DynamoDB call, so the common case of a build list vote costs this function one
dictionary lookup.

**Tombstoned parts are skipped.** Row 23 put the `deleted` pair on `Part` and
`app/db/dynamo/tombstones.py` holds the predicate. A part that is tombstoned is
one row 28's purge is in the middle of removing, and writing an aggregate onto
it would resurrect an attribute on a row that is being deleted and would race
the purge's own writes. It is skipped rather than failed: a tombstone is a
terminal state, so retrying the record could never succeed and would only send
a healthy batch to the dead letter queue.

**Partial batch failures.** The event source mapping is created with
`function_response_types = ["ReportBatchItemFailures"]`, so this handler returns
the identifiers of the records it could not process and the mapping retries only
those. The alternative, raising, retries the whole batch including the records
that already succeeded; those are idempotent so it would be correct, but it
turns one bad part into repeated writes on every other part in the batch and
eventually sends them all to the dead letter queue together.

The sequence number reported is the one from the record that failed. Where a
recompute fails for an entity several records in the batch touched, every one of
those records is reported, because the mapping retries by record and reporting
only one of them would drop the others.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

from app.db.dynamo.repository import ItemNotFound
from app.db.dynamo.tombstones import is_tombstoned

logger = logging.getLogger(__name__)

#: The one `entity_type` that carries a denormalised aggregate. Votes on car
#: generations and build lists are counted live by `VoteService.get_vote_summary`
#: and have no column to keep in step.
PART_ENTITY_TYPE = "part"

#: The DynamoDB stream record field the mapping identifies a record by. It is
#: what `batchItemFailures` entries must carry, spelled once so the handler and
#: its tests cannot disagree about the key.
SEQUENCE_NUMBER = "sequenceNumber"


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image.

    Stream images are in the low level wire format, `{"S": "..."}` rather than
    `"..."`, because an event source mapping delivers what the stream holds and
    not what `boto3.resource` would deserialise. Only the three types this
    module reads are handled: a string for the ids and the entity type, a number
    for nothing here but present so a schema change does not silently return the
    wrapper dict, and a null. Anything else is returned untouched, which the
    caller treats as a record it cannot read rather than guessing.
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

    INSERT and MODIFY carry `NewImage` and REMOVE carries only `OldImage`. The
    new image is preferred because a MODIFY that moved a vote between entities
    would need the new one, even though nothing in the application does that
    today: `vote_service` only ever updates `vote_type`.
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

    `None` covers every reason a record is not this function's business and they
    are deliberately not distinguished: a vote on a build list or a car
    generation, a record with no image at all, and an `entity_id` that is not a
    UUID. All three mean "nothing to recompute", and none of them is retryable,
    so failing on the malformed case would put a record on the dead letter queue
    that a redelivery could never fix.
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
    """`part_id -> the sequence numbers of the records that touched it`.

    The grouping is what turns a batch into one recompute per part, and keeping
    the sequence numbers alongside is what lets a failed recompute report every
    record that asked for it rather than only the last one.
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
            # Nothing to report a failure against. Recompute it anyway, because
            # a missing identifier is a reason not to be able to retry the
            # record, not a reason to leave the aggregate stale.
            grouped.setdefault(part_id, [])
            continue
        grouped.setdefault(part_id, []).append(str(sequence_number))
    return grouped


def recompute_net_votes(repos: Any, part_id: UUID) -> Optional[int]:
    """Recount the votes on one part and write the total, returning what it wrote.

    `None` means nothing was written, and there are two reasons for it, both
    terminal rather than retryable. The part is gone, which is the race the
    synchronous version already handled by swallowing `ItemNotFound`: a vote and
    a part delete can interleave, and a vote on a part that no longer exists has
    no aggregate to keep. Or the part is tombstoned, which row 28's purge is in
    the middle of, and writing to it would both resurrect an attribute on a row
    being deleted and race the purge.

    The count is `upvotes - downvotes`, which is exactly what
    `_sync_part_net_votes` wrote, so the aggregate this produces is the same
    number the inline write produced and no backfill is needed at the cutover.
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
        # The write is skipped rather than made unconditionally. This is the
        # common case on a redelivery and on the second of two records for the
        # same part in different batches, and skipping it saves a write against
        # a table every read path in `catalog` shares. It is not what makes the
        # handler idempotent; the recount is.
        return net_votes
    try:
        repos.parts.update(str(part_id), net_votes=net_votes)
    except ItemNotFound:
        # Deleted between the read above and the write. Same terminal case as a
        # part that was already gone.
        logger.info(
            "Vote stream: the part was deleted while its aggregate was being recomputed.",
            extra={"part_id": str(part_id)},
        )
        return None
    return net_votes


def process_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Recompute every part the batch touched; return the failed sequence numbers.

    One recompute per part, and a failure on one part does not stop the others:
    the parts in a batch are independent, and abandoning the rest of the batch
    on the first error would leave aggregates stale that had nothing wrong with
    them.
    """
    failures: List[str] = []
    for part_id, sequence_numbers in group_records_by_part(records).items():
        try:
            recompute_net_votes(repos, part_id)
        except Exception:
            # Broad on purpose. Anything the recompute raises that is not the
            # `ItemNotFound` handled inside it is a throttle, a timeout or a
            # transient DynamoDB error, and every one of those is worth the
            # mapping's retry. Letting it propagate instead would fail the whole
            # batch, which is what `ReportBatchItemFailures` exists to avoid.
            logger.exception(
                "Vote stream: failed to recompute net_votes for a part; reporting its records for retry.",
                extra={"part_id": str(part_id), "records": len(sequence_numbers)},
            )
            failures.extend(sequence_numbers)
    return failures


def handle(event: Mapping[str, Any], repos: Any) -> Dict[str, List[Dict[str, str]]]:
    """The handler body, with the repository bundle passed in.

    Separate from `handler` below so a test can drive it with a bundle of fakes
    and no AWS at all, which is the same split `build_app` and `main` make in
    every entrypoint.

    The return shape is the one an event source mapping with
    `ReportBatchItemFailures` expects: `{"batchItemFailures": [{"itemIdentifier":
    "<sequence number>"}]}`. An empty list means the whole batch succeeded, and
    it is returned explicitly rather than as an empty response, because a
    handler that returns something the mapping cannot parse has the whole batch
    retried.
    """
    records = event.get("Records") or []
    failures = process_records(repos, records)
    if failures:
        logger.warning(
            "Vote stream: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": sequence} for sequence in failures]}
