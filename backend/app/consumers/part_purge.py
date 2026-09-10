"""Seam 2: the part purge cascade, drained off the `parts` stream.

Split plan row 28, section 1.3's seam 2. `purge_related_rows_for_parts` used to
run inline at the end of every part delete, on the request thread, deleting rows
in `build_list_parts`, `votes`, `reports` and `part_price_alerts`. Those four
tables belong to `build-lists`, `moderation` twice and `admin`, so that one
function call is `catalog` writing three other domains' tables. This module is
the inversion: the delete writes a tombstone and returns, the `parts` stream
carries the tombstone to this consumer, and the consumer performs the cascade.

**The purge semantics are unchanged.** Exactly the same four tables lose exactly
the same rows, and the catalogue side of the purge (`part_listings`,
`part_price_history`, `part_cars`, the duplicate unlink and the part row itself)
still runs synchronously in `PartService.purge`, because every one of those
tables is `catalog`'s own. What changed is who performs the cross-domain half of
the cascade and when, and nothing else. `backend/tests/api/endpoints/test_delete_cascades.py`
is the record of the synchronous behaviour and it still passes against the end
state this consumer reaches.

**The tombstone is the contract.** `PartService.purge` writes `deleted` and
`deleted_at` in a single update and returns. Between that write and this
consumer draining, the part is in a half-deleted state: the row still exists and
its related rows still exist, and every read path treats it as absent because
row 23 made `is_tombstoned` the predicate on every join that reaches a part. The
build-list join is the visible one, and section 1.3 names it: a build list
containing a purged part must drop the row rather than render a hole, which
`app/api/endpoints/build_list_parts.py` already does.

**Why the work queue and not the four deletes inline here.** The `part-purge`
SQS queue row 22 created is the durable retry buffer between the stream and the
deletes. A DynamoDB stream retains a record for 24 hours and an event source
mapping's retries are spent in minutes, so a cascade unit that keeps failing
against a throttled table would be lost with nothing but failure metadata on the
stream dead letter queue to say which part it was. Enqueued, the same unit
carries the part id itself, survives four days in the queue, is retried five
times by the redrive policy, and lands in `part-purge-dlq` with enough
information to replay by hand. The visible symptom this protects against is the
one section 7 names: a purged part that is still in someone's build list.

So the shape is a producer and a drainer, and this module is both, because the
two halves are one function's worth of work:

  `handle_stream` reads the tombstones off the stream and enqueues one message
  per part. It writes nothing to any table.

  `handle_queue` takes those messages back off the queue and performs the four
  deletes. It writes nothing that is not a delete.

**Idempotency, which is the property the whole design rests on.** Every delivery
guarantee in the path is at-least-once: the DynamoDB stream is, and so is SQS.
On top of that the mapping bisects a failing batch, which means a batch that
half-succeeded is re-run with its successful half included. So every step has to
be safe to run again, and every step is, for the same structural reason rather
than by four separate arguments:

1. Each of the four deletes is a query for the rows that reference the part
   followed by a `batch_delete` of exactly those keys. A replay queries again,
   finds nothing, and issues no write at all. There is no counter to decrement,
   no aggregate to adjust and no flag to flip, so a second run is not merely
   harmless, it is a no-op that costs one query.
2. `DynamoRepository.delete` is called with `must_exist` left false throughout,
   and DynamoDB's `DeleteItem` on a key that is not there succeeds. So even the
   race where two deliveries interleave mid-cascade cannot fail one of them.
3. The tombstone itself is idempotent. A part that is already tombstoned when a
   redelivered MODIFY arrives is still tombstoned, and this consumer reads the
   flag rather than the transition, so it enqueues the same message and the
   drain does the same nothing.
4. Enqueueing twice is safe because draining twice is safe. That is what lets
   the producer send without deduplication and lets the queue be a standard
   queue rather than FIFO with a content-based dedup id, which section 7 already
   chose for exactly this reason.

The consequence worth stating plainly: the cascade is safe to replay in whole or
in part, from the stream, from the queue, or by hand from the dead letter queue,
and running it twice reaches the same state as running it once.

**Failures are loud and land in the existing dead letter queue path.** Nothing
here catches an error and reports success. A stream record that cannot be
enqueued is reported as a batch item failure so the mapping retries only that
record, and a batch that keeps failing goes to `parts-stream-dlq` through the
mapping's `on_failure` destination. A queue message whose cascade fails is
reported as a batch item failure so SQS retries only that message, and after
five receives the redrive policy moves it to `part-purge-dlq`. Both queues are
covered by the one `<prefix>-dlq-depth` alarm row 22 created, so either failure
pages without a new alarm.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from uuid import UUID

from app.db.dynamo.tombstones import DELETED_ATTRIBUTE

logger = logging.getLogger(__name__)

#: The DynamoDB stream record field the mapping identifies a record by, and the
#: SQS field that does the same job for a queue message. Both are what
#: `batchItemFailures` entries carry, spelled once each so a handler and its
#: tests cannot disagree about the key.
SEQUENCE_NUMBER = "sequenceNumber"
MESSAGE_ID = "messageId"

#: The environment variable Terraform sets to the `part-purge` queue URL. A
#: producer sends with the URL rather than the ARN, which is why
#: `terraform/outputs.tf` publishes both.
QUEUE_URL_VARIABLE = "PART_PURGE_QUEUE_URL"

#: The message body's shape, versioned from the first message. The cascade is
#: going to grow a second producer in row 30, when the user delete fans parts
#: onto a queue of its own, and a body that says what it is costs one key now
#: and saves guessing later.
MESSAGE_VERSION = 1
MESSAGE_KIND = "part-purge"


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image.

    Stream images are in the low level wire format, `{"S": "..."}` rather than
    `"..."`, because an event source mapping delivers what the stream holds and
    not what `boto3.resource` would deserialise. The three types this module
    reads are handled: a string for the id, a boolean for the tombstone flag,
    and a null. Anything else is returned untouched, which the caller treats as
    a value it cannot read rather than guessing.
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
    """Whether an image carries the tombstone flag.

    Reads `deleted` through `DELETED_ATTRIBUTE` rather than a literal, which is
    what `app/db/dynamo/tombstones.py` asks of anything writing or reading the
    pair. `deleted_at` is deliberately not consulted here, for the same reason
    `is_tombstoned` does not consult it: the flag is the state and the timestamp
    is the audit trail.
    """
    return bool(_plain(image.get(DELETED_ATTRIBUTE)))


def part_id_from_record(record: Mapping[str, Any]) -> Optional[UUID]:
    """The part this record tombstones, or `None` when it does not tombstone one.

    `None` covers every reason a record is not this consumer's business, and
    none of them is retryable, so they are deliberately not distinguished:

    - A part write that is not a tombstone. Every ordinary edit to a part lands
      here, which is the overwhelming majority of what this stream carries, and
      it costs one dictionary lookup and no AWS call.
    - A record that was already a tombstone before this write. `deleted` is on
      the old image as well as the new, so the write changed something else on
      an already-purged row and the cascade has already been enqueued for it.
      Enqueueing again would be safe, per the module docstring, but it is still
      work nothing asked for.
    - A REMOVE. The row is gone rather than tombstoned. The hard delete that
      follows a drained cascade lands here and must not re-enqueue the cascade
      it just completed.
    - An id that is missing or is not a UUID, which no redelivery can repair.
    """
    new_image, old_image = _images(record)
    if not new_image:
        # A REMOVE, or a record with no image at all.
        return None
    if not _tombstoned(new_image):
        return None
    if _tombstoned(old_image):
        # Already tombstoned before this write, so the cascade is already in
        # flight or already done.
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
    """`part_id -> the sequence numbers of the records that tombstoned it`.

    Ordering on a DynamoDB stream is per partition key, which for `parts` is the
    part id, so every record for one part arrives on one shard in order and a
    batch can hold more than one. Grouping collapses them to one message rather
    than one per record, and keeping the sequence numbers alongside is what lets
    a failed enqueue report every record that asked for it rather than only the
    last one.
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
            # Nothing to report a failure against. Enqueue it anyway, because a
            # missing identifier is a reason not to be able to retry the record,
            # not a reason to leave a part's related rows behind.
            grouped.setdefault(part_id, [])
            continue
        grouped.setdefault(part_id, []).append(str(sequence_number))
    return grouped


def message_body(part_id: UUID) -> str:
    """The queue message for one part's cascade.

    The part id and nothing else, because the drain reads the current state of
    the four tables rather than anything the producer observed. Carrying the
    related row ids in the message instead would be a snapshot that a retry
    could act on after the rows had changed, which is the one way this cascade
    could delete something it should not.
    """
    return json.dumps({"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "part_id": str(part_id)})


def part_id_from_message(body: str) -> Optional[UUID]:
    """The part id out of a queue message body, or `None` when it is unreadable.

    `None` is terminal rather than retryable: a body that is not JSON, or whose
    part id is not a UUID, will not parse on the next receive either, so
    reporting it as a failure would spend five receives to reach the dead letter
    queue on a message no retry could fix. It is dropped with a warning instead
    and the alarm that matters, the one on the dead letter queue, is left for
    failures that are real.
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

    Not `send_message_batch`, and that is a deliberate trade rather than an
    oversight. A batch send reports per-entry failures in the response body
    rather than raising, so using it correctly means reading `Failed` and
    mapping each entry back to the part it came from and then to the stream
    records that asked for that part. One send per part gets the same isolation
    from the exception itself, and a tombstoned part is a human deleting one
    part rather than a stream of them: a batch of a hundred stream records
    collapses to a handful of parts in practice, and the batching that matters
    for cost happens on the mapping's side with `maximum_batching_window_in_seconds`.
    """
    for part_id in part_ids:
        client.send_message(QueueUrl=queue_url, MessageBody=message_body(part_id))


def process_stream_records(
    client: Any,
    queue_url: str,
    records: Iterable[Mapping[str, Any]],
) -> List[str]:
    """Enqueue a cascade for every part this batch tombstoned; return the failures.

    One message per part, and a failure on one part does not stop the others:
    the parts in a batch are independent, and abandoning the rest of the batch on
    the first error would leave related rows behind for parts that had nothing
    wrong with them.
    """
    failures: List[str] = []
    for part_id, sequence_numbers in group_records_by_part(records).items():
        try:
            enqueue_part_purges(client, queue_url, [part_id])
        except Exception:
            # Broad on purpose. A failed send is a throttle, a timeout or a
            # transient SQS error, and every one of those is worth the mapping's
            # retry. Letting it propagate instead would fail the whole batch,
            # which is what `ReportBatchItemFailures` exists to avoid.
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
    """Delete every row in the four tables that references the part.

    This is `purge_related_rows_for_parts` moved, one part at a time, and the
    four calls are the same four in the same order. Each returns the number of
    rows it removed, which is what the log line reports and what the tests
    assert against.

    Every one of the four is a query followed by a `batch_delete` of exactly the
    keys the query returned, which is the whole idempotency argument in one
    sentence: a replay queries, finds nothing, and writes nothing. See the
    module docstring for why that property has to hold at every step rather than
    only at the end.
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
    """Drain a batch of queue messages; return the ids of the ones that failed.

    One cascade per message, and a failure on one message does not stop the
    others, for the same reason the stream side isolates per part: the parts are
    independent and one throttled table should not re-run the cascade for every
    other part in the batch.
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
            # Unreadable and unretryable; already logged where it was found.
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
    """The `part-purge` queue URL from the environment.

    Raises rather than defaulting. A consumer that cannot find its queue must
    fail the invoke, because the alternative is a stream batch acked with
    nothing enqueued, which is the exact shape of silent data loss this row
    exists to avoid.
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
    """The queue half, with the repository bundle passed in.

    The return shape is the one an SQS event source mapping with
    `ReportBatchItemFailures` expects, which is the same shape the DynamoDB
    stream mapping expects, keyed by `messageId` rather than by sequence number.
    An empty list means the whole batch succeeded, and it is returned explicitly
    rather than as an empty response, because a handler that returns something
    the mapping cannot parse has the whole batch retried.
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

    One function serves both mappings, so it has to tell the two events apart,
    and the discriminator is the record's own `eventSource`. Both shapes carry
    `Records`, and both carry an `eventSource` on every record: `aws:sqs` for a
    queue message and `aws:dynamodb` for a stream record. An empty batch is
    treated as a stream event, which is the arbitrary half of an arbitrary
    choice with no consequence: both halves answer an empty batch with an empty
    failure list and touch nothing.
    """
    records = event.get("Records") or []
    for record in records:
        if isinstance(record, Mapping) and record.get("eventSource") == "aws:sqs":
            return True
    return False
