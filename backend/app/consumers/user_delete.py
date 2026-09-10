"""Seam 1: the user delete cascade, drained off the `users` stream.

Split plan row 30, section 1.3's seam 1. `_delete_user_everywhere` in
`app/api/endpoints/users.py` used to run inline at the end of every account
deletion, on the request thread, deleting rows in roughly fifteen tables across
five other domains: `oauth_accounts` and `webauthn_credentials` (`identity`),
`parts`, `part_cars`, `part_listings` and `part_price_history` (`catalog`),
`build_lists`, `build_list_parts`, `build_list_phases` and
`build_list_labor_estimates` (`build-lists`), `build_logs` and `build_log_posts`
(`build-logs`), `votes` and `reports` (`moderation`), and `part_price_alerts`
(`admin`). That is the single widest coupling in the application, it is why
`users` carried twenty-three of twenty-five repositories, and it is why section
1.1 cuts `users` last. This module is the inversion: the delete writes a
tombstone and hard deletes the user row, the `users` stream carries the
tombstone to this consumer, and the consumer performs the cascade.

**The delete semantics are unchanged.** Exactly the same tables lose exactly the
same rows, in the same order, by the same repository calls.
`backend/tests/api/endpoints/test_delete_cascades.py` is the record of the
synchronous behaviour and it still describes the end state this consumer
reaches. What changed is who performs the cascade and when, and nothing else.

**The tombstone is the contract, and row 23 is why it is safe.**
`_delete_user_everywhere` writes `deleted` and `deleted_at` in a single update
and then hard deletes the row. Between that update and this consumer draining,
the application is in a half-deleted state: the user's build lists, parts and
posts still exist and still carry an author id that no longer resolves. Every
read path that joins to a user tolerates exactly that, because row 23 made
`is_tombstoned` the predicate on every such join and `live_or_none` the shape
most of them use, so a deleted author renders as an absent one. Section 1.3
required that filtering to land before `users` was cut and row 23 landed it.

**Why the work queue and not the cascade inline here.** The `user-delete` SQS
queue row 22 created is the durable retry buffer between the stream and the
deletes, and the argument for it is the same one row 28 made with more weight
behind it, because this cascade is fifteen tables rather than four. A DynamoDB
stream retains a record for 24 hours and an event source mapping's retries are
spent in minutes, so a cascade unit that keeps failing against a throttled table
would be lost with nothing but failure metadata on the stream dead letter queue
to say which user it was. Enqueued, the same unit carries the user id itself,
survives four days in the queue, is retried five times by the redrive policy,
and lands in `user-delete-dlq` with enough information to replay by hand. The
visible symptom this protects against is the one section 7 names: a user who
deleted their account and whose build lists are still public.

So the shape is a producer and a drainer, and this module is both, because the
two halves are one function's worth of work:

  `handle_stream` reads the tombstones off the stream and enqueues one message
  per user. It writes nothing to any table.

  `handle_queue` takes those messages back off the queue and performs the
  cascade. It writes nothing that is not a delete.

**The uniqueness reservations stay synchronous, and this row is where that is
decided.** `UserRepository.delete_user` removes the user row and releases the
`username` and `email` reservations in one transaction. Row 28 answered the same
question for `gtin` and `manufacturer + part_number` by keeping the release on
the request thread, and it explicitly declined to set a precedent for seam 1 on
the grounds that the blast radius here is different. It is different, and it is
worse rather than better, which is why the answer is the same and is now settled
for both seams.

A `username` or `email` reservation held past the tombstone is a person who
deleted their account and cannot register again with the address they just
freed, for however deep the `user-delete` queue happens to be. They get
`EMAIL_EXISTS` against a row no user and no administrator can see, because the
user row is gone and only the reservation item remains. Row 28's case blocked a
software engineer re-creating a catalogue part; this one blocks a member of the
public signing up, it fails closed, and the way out of it is a manual DynamoDB
edit. Deferring it would buy one transaction's latency on a request that is
already deleting an account.

So the user row and its two reservations are removed together, synchronously, in
the transaction that already did it, and this consumer never writes `users` and
never touches the reservation table. What it does write is
`oauth_accounts` and `webauthn_credentials`, which release reservations of their
own (`provider_account`, `user_provider` and `credential_id`), and those do move
here. The distinction is what the held reservation blocks: re-linking the same
social account or re-registering the same authenticator to a *new* account is
the only path that touches them, and nobody walks that path in the seconds after
deleting the account it was linked to. Nothing a person can do in that window is
blocked, so there is no reason to hold the request open for it.

**Idempotency, which is the property the whole design rests on.** Every delivery
guarantee in the path is at-least-once: the DynamoDB stream is, and so is SQS.
On top of that the mapping bisects a failing batch, which means a batch that
half-succeeded is re-run with its successful half included. So every step has to
be safe to run again, and every step is, for the same structural reason rather
than by fifteen separate arguments:

1. Every step of the cascade is a query for the rows that reference the user
   followed by a `batch_delete` or a transaction over exactly the keys the query
   returned. A replay queries again, finds nothing, and issues no write at all.
   There is no counter to decrement, no aggregate to adjust and no flag to flip,
   so a second run is not merely harmless, it is a no-op that costs one query.
2. `DynamoRepository.delete` is called with `must_exist` left false throughout,
   and DynamoDB's `DeleteItem` on a key that is not there succeeds. So even the
   interleaving where two deliveries run the same cascade concurrently cannot
   fail one of them.
3. The tombstone itself is idempotent. This module reads the flag on the new
   image rather than the transition, and a redelivered record carrying an
   already-tombstoned image enqueues the same message, whose drain does the same
   nothing.
4. Enqueueing twice is safe because draining twice is safe. That is what lets
   the producer send without deduplication and lets the queue be a standard
   queue rather than FIFO with a content-based dedup id, which is what section 7
   chose for exactly this reason.

The one step that is not a bare query-then-delete is the part purge, and it
deserves its own sentence rather than being folded into the argument above.
`PartService.purge` writes the part's tombstone with an `attribute_exists`
condition, so on a replay, where the part is already gone, it raises
`ItemNotFound`. That is caught per part here rather than failing the cascade,
because a part that is already purged is precisely what a correct replay is
supposed to find.

**Two cascades chained, which is deliberate.** Purging a user's parts through
`PartService.purge` writes a tombstone per part, and row 28's consumer picks
each of those up off the `parts` stream and performs seam 2's cross-domain half.
So this module never deletes a `build_list_parts`, `votes`, `reports` or
`part_price_alerts` row on a *part's* behalf; it deletes only the rows the
*user* owns. Reusing the service rather than reimplementing the catalogue half
is what keeps the two seams from drifting, and it is why `purge_owned_parts`
runs first: the sooner those part tombstones are on the `parts` stream, the more
the two cascades overlap.

**Failures are loud and land in the dead letter queues row 22 built.** Nothing
here catches an error and reports success. A stream record that cannot be
enqueued is reported as a batch item failure so the mapping retries only that
record, and a batch that keeps failing goes to `users-stream-dlq` through the
mapping's `on_failure` destination. A queue message whose cascade fails is
reported as a batch item failure so SQS retries only that message, and after
five receives the redrive policy moves it to `user-delete-dlq`. Both queues are
covered by the one aggregate `dlq-depth` alarm row 22 created, so either failure
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

#: The environment variable Terraform sets to the `user-delete` queue URL. A
#: producer sends with the URL rather than the ARN, which is why
#: `terraform/outputs.tf` publishes both.
QUEUE_URL_VARIABLE = "USER_DELETE_QUEUE_URL"

#: The message body's shape, versioned from the first message and carrying the
#: same two keys row 28's does. `kind` is what tells a person reading a dead
#: letter queue by hand which cascade a stranded message belongs to; the two
#: queues are separate, so nothing depends on it at runtime.
MESSAGE_VERSION = 1
MESSAGE_KIND = "user-delete"


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


def user_id_from_record(record: Mapping[str, Any]) -> Optional[UUID]:
    """The user this record tombstones, or `None` when it does not tombstone one.

    `None` covers every reason a record is not this consumer's business, and
    none of them is retryable, so they are deliberately not distinguished:

    - A user write that is not a tombstone. Every ordinary edit to a user lands
      here, and on this stream that majority is larger than on row 28's: profile
      updates, password changes, 2FA changes, and every `identity` write on an
      oauth link or a webauthn registration. It costs one dictionary lookup and
      no AWS call.
    - A record that was already a tombstone before this write. `deleted` is on
      the old image as well as the new, so the write changed something else on
      an already-deleted row and the cascade has already been enqueued for it.
      Enqueueing again would be safe, per the module docstring, but it is still
      work nothing asked for.
    - A REMOVE. The row is gone rather than tombstoned. The hard delete that
      immediately follows the tombstone write lands here on every single account
      deletion, and it must not re-enqueue the cascade the tombstone enqueued.
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
    """`user_id -> the sequence numbers of the records that tombstoned it`.

    Ordering on a DynamoDB stream is per partition key, which for `users` is the
    user id, so every record for one user arrives on one shard in order and a
    batch can hold more than one. Grouping collapses them to one message rather
    than one per record, and keeping the sequence numbers alongside is what lets
    a failed enqueue report every record that asked for it rather than only the
    last one.
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
            # Nothing to report a failure against. Enqueue it anyway: a missing
            # identifier is a reason not to be able to retry the record, not a
            # reason to leave a deleted user's rows behind.
            grouped.setdefault(user_id, [])
            continue
        grouped.setdefault(user_id, []).append(str(sequence_number))
    return grouped


def message_body(user_id: UUID) -> str:
    """The queue message for one user's cascade.

    The user id and nothing else, because the drain reads the current state of
    the tables rather than anything the producer observed. Carrying the related
    row ids in the message instead would be a snapshot that a retry could act on
    after the rows had changed, which is the one way this cascade could delete
    something it should not.
    """
    return json.dumps({"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "user_id": str(user_id)})


def user_id_from_message(body: str) -> Optional[UUID]:
    """The user id out of a queue message body, or `None` when it is unreadable.

    `None` is terminal rather than retryable: a body that is not JSON, or whose
    user id is not a UUID, will not parse on the next receive either, so
    reporting it as a failure would spend five receives to reach the dead letter
    queue on a message no retry could fix. It is dropped with a warning instead,
    which leaves the dead letter queue and its alarm for failures that are real.
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

    Not `send_message_batch`, for row 28's reason and with more room to spare. A
    batch send reports per-entry failures in the response body rather than
    raising, so using it correctly means reading `Failed` and mapping each entry
    back to the user it came from and then to the stream records that asked for
    it. One send per user gets the same isolation from the exception itself, and
    the volume does not argue otherwise: a batch of a hundred `users` stream
    records collapses to at most a handful of tombstones and usually to none,
    because account deletion is rare and ordinary profile and authentication
    writes are what this stream mostly carries.
    """
    for user_id in user_ids:
        client.send_message(QueueUrl=queue_url, MessageBody=message_body(user_id))


def process_stream_records(
    client: Any,
    queue_url: str,
    records: Iterable[Mapping[str, Any]],
) -> List[str]:
    """Enqueue a cascade for every user this batch tombstoned; return the failures.

    One message per user, and a failure on one user does not stop the others:
    the users in a batch are independent, and abandoning the rest of the batch
    on the first error would leave rows behind for accounts that had nothing
    wrong with them.
    """
    failures: List[str] = []
    for user_id, sequence_numbers in group_records_by_user(records).items():
        try:
            enqueue_user_deletes(client, queue_url, [user_id])
        except Exception:
            # Broad on purpose. A failed send is a throttle, a timeout or a
            # transient SQS error, and every one of those is worth the mapping's
            # retry. Letting it propagate instead would fail the whole batch,
            # which is what `ReportBatchItemFailures` exists to avoid.
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
    """The user's parts, and the price alerts the user subscribed to.

    `_purge_owned_parts` moved. Each part goes through `PartService.purge`,
    which is the same code path a part delete route takes: it writes the part's
    tombstone, deletes the catalogue rows `catalog` owns (`part_listings`,
    `part_price_history`, `part_cars` and the duplicate unlinks), and releases
    the part's GTIN and manufacturer part number reservations through
    `delete_unique`. Row 28's consumer then takes each of those tombstones off
    the `parts` stream and performs seam 2's cross-domain half, which is why
    nothing here touches `build_list_parts`, `votes` or `reports` on a part's
    behalf.

    The `purge_related_rows_for_parts` call the synchronous version made after
    this loop is gone rather than moved, because it has been a documented no-op
    since row 28: the tombstones this loop writes are what trigger that work.

    `part_price_alerts` is different and is deleted here. Those are alerts the
    *user* subscribed to, on parts that may belong to anyone, so no part
    tombstone will ever reach them.

    A part that is already purged raises `ItemNotFound` from the tombstone
    write's `attribute_exists` condition. That is caught per part: a part that
    is already gone is what a replay is supposed to find, so it is the success
    case rather than an error, and it is counted separately so the log line
    distinguishes a first run from a redelivery.
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
    """The user's build lists, their phases, parts, labor estimates and logs.

    `_purge_owned_build_lists` moved verbatim, including the second pass over
    `build_list_parts` for rows the user added to somebody else's list.
    `delete_build_list_cascade` is a transaction under the 100 action ceiling
    with a batched fallback above it, and both branches delete exactly the keys
    a query returned, so a replay of a list that is already gone finds no
    children and deletes a parent that is not there, which succeeds.
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
    """The user's votes and reports.

    `_purge_owned_moderation` moved verbatim. Both repositories query the user
    index and batch delete exactly what they found, so a replay finds nothing
    and writes nothing.
    """
    return {
        "votes": repos.votes.delete_for_user(user_id),
        "reports": repos.reports.delete_for_user(user_id),
    }


def purge_identity(repos: Any, user_id: UUID) -> Dict[str, int]:
    """The user's oauth links and webauthn credentials.

    The two `delete_all_for_user` calls moved verbatim. Neither is a batch
    delete, and that is deliberate rather than an oversight in the original:
    each row is removed in a transaction that also releases that row's own
    unique labels, `provider_account` and `user_provider` for an oauth link and
    `credential_id` for a credential. Every one of them has to be released or
    the same social account or authenticator can never be attached to any
    account again.

    Those releases move here, unlike the account's `username` and `email`. See
    the module docstring: what a held reservation blocks is the difference, and
    nothing a person can do in the seconds after deleting an account is blocked
    by these three.

    Both list by user before deleting, so a replay lists nothing.
    """
    accounts = len(repos.oauth_accounts.list_by_user(user_id))
    repos.oauth_accounts.delete_all_for_user(user_id)
    credentials = len(repos.webauthn_credentials.list_by_user(user_id))
    repos.webauthn_credentials.delete_all_for_user(user_id)
    return {"oauth_accounts": accounts, "webauthn_credentials": credentials}


def cascade_user_delete(repos: Any, user_id: UUID) -> Dict[str, int]:
    """Every row in the fifteen tables that belonged to the deleted user.

    This is `_delete_user_everywhere` moved, minus its last line. The four
    groups run in the order that function ran them, which is not arbitrary:
    parts first, because purging a part writes a tombstone that row 28's
    consumer drains, and starting that as early as possible gives the two
    cascades the most overlap.

    The line that did not move is `repos.users.delete_user(user)`. The user row
    and its `username` and `email` reservations are removed synchronously,
    before this consumer ever sees the tombstone, and the module docstring is
    where that decision is argued. This function must never write `users`.
    """
    counts: Dict[str, int] = {}
    counts.update(purge_owned_parts(repos, user_id))
    counts.update(purge_owned_build_lists(repos, user_id))
    counts.update(purge_owned_moderation(repos, user_id))
    counts.update(purge_identity(repos, user_id))
    return counts


def process_queue_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Drain a batch of queue messages; return the ids of the ones that failed.

    One cascade per message, and a failure on one message does not stop the
    others, for the same reason the stream side isolates per user: the accounts
    are independent and one throttled table should not re-run the cascade for
    every other account in the batch.
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
            # Unreadable and unretryable; already logged where it was found.
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
    """The `user-delete` queue URL from the environment.

    Raises rather than defaulting. A consumer that cannot find its queue must
    fail the invoke, because the alternative is a stream batch acked with
    nothing enqueued, which is the exact shape of silent data loss this row
    exists to avoid.
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
            "User delete queue: reporting partial batch failure.",
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
