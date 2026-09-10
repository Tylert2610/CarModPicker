"""Seam 4: the price drop alert email, fired off the `part_listings` stream.

Split plan row 25, section 1.3's seam 4. `part_listing_service`'s price capture
used to call `evaluate_alerts_for_listing` inline, on the request thread, after
the transactional write returned. That is `catalog` reading `part_price_alerts`
and calling SES, and both of those belong to `admin`. This module is the
inversion: a Lambda consuming the `part_listings` DynamoDB stream, owned by
`admin`, which evaluates the alerts and sends the mail. `catalog` keeps neither
the alert read nor the SES grant.

**Why this is worth doing on its own merits.** Section 1.3 makes the point and
it is not a split argument: a price write used to block on a fan-out read of
four tables plus a synchronous SES call inside a 29 second Lambda, and a user
waiting on the listing write was waiting on someone else's email. Off the
stream the write returns as soon as the transaction commits.

**What a record gives us.** The stream carries `NEW_AND_OLD_IMAGES`, so a
listing INSERT has the new item, a MODIFY has both and a REMOVE has only the
old. The item is a `PartListing`, which carries `part_id`, `retailer_id`,
`last_known_price_cents` and `last_price_updated_at`: exactly the four
arguments the old inline call passed. Nothing is read out of `part_price_history`
and nothing else is needed, which is what keeps the event to the record's own
data.

**A price has to have actually dropped.** Every write in the capture path
touches the listing, including the ones that only re-stamp `updated_at` on an
unchanged price, so a naive handler would re-evaluate every alert on every
crawler revisit. The handler compares the new image's price against the old
one's and does nothing unless the price moved down. An INSERT with a price is a
drop by definition, because there was no previous price to be below. A REMOVE
is never a drop.

**Idempotency, which the stream requires rather than merely rewards.** A
DynamoDB stream is at-least-once, so the same record can arrive twice, and this
handler's side effect is an email, which cannot be taken back. Three things
stand between a redelivery and a duplicate email, and they are listed in the
order they take effect:

1. The drop test above. A redelivered record carries the same two images, so it
   computes the same verdict, and a record that was not a drop stays not a drop.
2. `last_fired_at` on the alert row, which is the marker. A send writes it, and
   an alert that fired within `ALERT_COOLDOWN` of the observation is suppressed.
   A redelivery of a record that did fire an email therefore finds the marker
   already written and sends nothing. This is the check that carries the weight,
   and it is the reason the write of the marker is not optional.
3. The window between the send and the marker write, which is the one hole none
   of this closes: a function that dies between SES accepting the message and
   the `last_fired_at` update will send twice on the retry. It is left open
   deliberately. Closing it means a marker written before the send, which turns
   the failure mode from a duplicate email into a silently missing one, and a
   missed price alert is worse than a repeated one.

**Per-alert isolation, per-listing failure reporting.** One alert that cannot be
evaluated must not stop the others on the same listing, which the evaluation
already guarantees by catching per alert. A listing that cannot be evaluated at
all, which is a throttle or a timeout on the reads before the loop, is reported
as a batch item failure so the mapping retries only that listing's records.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

#: The DynamoDB stream record field the mapping identifies a record by. It is
#: what `batchItemFailures` entries must carry, spelled once so the handler and
#: its tests cannot disagree about the key.
SEQUENCE_NUMBER = "sequenceNumber"


class PriceDrop:
    """One evaluated listing record: what to evaluate alerts against.

    A small object rather than a tuple because four positional values of which
    two are UUIDs and one is an int is exactly the shape that gets passed in the
    wrong order eventually.
    """

    __slots__ = ("part_id", "retailer_id", "price_cents", "observed_at")

    def __init__(
        self,
        part_id: UUID,
        retailer_id: UUID,
        price_cents: int,
        observed_at: datetime,
    ) -> None:
        self.part_id = part_id
        self.retailer_id = retailer_id
        self.price_cents = price_cents
        self.observed_at = observed_at

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PriceDrop):
            return NotImplemented
        return (
            self.part_id == other.part_id
            and self.retailer_id == other.retailer_id
            and self.price_cents == other.price_cents
            and self.observed_at == other.observed_at
        )

    def __repr__(self) -> str:
        return (
            f"PriceDrop(part_id={self.part_id}, retailer_id={self.retailer_id}, "
            f"price_cents={self.price_cents}, observed_at={self.observed_at!r})"
        )


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image.

    Stream images are in the low level wire format, `{"S": "..."}` rather than
    `"..."`, because an event source mapping delivers what the stream holds and
    not what `boto3.resource` would deserialise. The four types this module
    reads are handled: a string for the ids and the timestamp, a number for the
    price, a null for a listing that has never carried one, and a boolean for
    completeness. Anything else is returned untouched, which the caller treats
    as a value it cannot read rather than guessing.
    """
    if not isinstance(value, Mapping):
        return value
    if "S" in value:
        return value["S"]
    if "N" in value:
        return value["N"]
    if "NULL" in value:
        return None
    if "BOOL" in value:
        return value["BOOL"]
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


def _uuid(image: Mapping[str, Any], key: str) -> Optional[UUID]:
    value = _plain(image.get(key))
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _price_cents(image: Mapping[str, Any]) -> Optional[int]:
    """`last_known_price_cents` off an image, or `None` when it has no price.

    A negative price is treated as no price, matching the capture path, which
    only records an observation when `price_cents >= 0`.
    """
    value = _plain(image.get("last_known_price_cents"))
    if value is None or isinstance(value, bool):
        return None
    try:
        price = int(value)
    except (TypeError, ValueError):
        return None
    return price if price >= 0 else None


def _observed_at(image: Mapping[str, Any]) -> Optional[datetime]:
    """`last_price_updated_at` off an image, as an aware datetime.

    The repositories serialise datetimes as ISO 8601 strings, so this is a
    string on the wire. A naive value is read as UTC, the same treatment
    `part_price_alert_service._ensure_aware` gives one, because the observation
    timestamps from the crawler path have historically arrived both ways.
    """
    value = _plain(image.get("last_price_updated_at"))
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def price_drop_from_record(record: Mapping[str, Any]) -> Optional[PriceDrop]:
    """The drop this record represents, or `None` when it is not one.

    `None` covers every reason a record is not this function's business, and
    they are deliberately not distinguished because none of them is retryable:
    a REMOVE, a write that did not touch the price, a write that raised the
    price or left it equal, a listing that has never had a price, and an image
    whose ids or timestamp cannot be read. Failing on any of them would put a
    record on the dead letter queue that a redelivery could never fix.

    An INSERT with a price counts as a drop. There is no earlier price for it
    to be below, and a user who subscribed to a threshold before any retailer
    listed the part should hear about the first listing that meets it.
    """
    new_image, old_image = _images(record)
    if not new_image:
        # A REMOVE, or a record with no image at all. Deleting a listing is not
        # a price drop, and there is nothing to evaluate against.
        return None

    price_cents = _price_cents(new_image)
    if price_cents is None:
        return None

    previous = _price_cents(old_image)
    if previous is not None and price_cents >= previous:
        # The write touched the listing without lowering the price. Every
        # re-stamp of `updated_at` on an unchanged price lands here, which is
        # the common case on a crawler that revisits a stable listing.
        return None

    part_id = _uuid(new_image, "part_id")
    retailer_id = _uuid(new_image, "retailer_id")
    observed_at = _observed_at(new_image)
    if part_id is None or retailer_id is None or observed_at is None:
        logger.warning(
            "Price alert stream: a record carries a price but not the fields to evaluate it; skipping it.",
            extra={
                "event_name": record.get("eventName"),
                "has_part_id": part_id is not None,
                "has_retailer_id": retailer_id is not None,
                "has_observed_at": observed_at is not None,
            },
        )
        return None

    return PriceDrop(
        part_id=part_id,
        retailer_id=retailer_id,
        price_cents=price_cents,
        observed_at=observed_at,
    )


def group_records_by_listing(
    records: Iterable[Mapping[str, Any]],
) -> Dict[UUID, tuple[PriceDrop, List[str]]]:
    """`listing_id -> (the lowest drop seen for it, the records that asked)`.

    One evaluation per listing per batch rather than one per record. Ordering on
    a DynamoDB stream is per partition key, which for `part_listings` is the
    listing id, so records for one listing arrive in order within a shard and a
    batch can hold several writes to the same listing. Evaluating each of them
    would send the same user several emails for the same listing in one batch,
    and the cooldown marker would only suppress the second and later ones after
    the first had already written it, which is a race rather than a guarantee.

    The lowest price in the batch is the one kept, because that is the one the
    user's threshold is most likely to meet and the one whose email is worth
    sending. Ties keep the earlier record, which is the earlier observation.

    A listing with no readable sequence number is still evaluated. A missing
    identifier is a reason not to be able to retry the record, not a reason to
    leave a subscriber unemailed.
    """
    grouped: Dict[UUID, tuple[PriceDrop, List[str]]] = {}
    for record in records:
        drop = price_drop_from_record(record)
        if drop is None:
            continue
        listing_id = _listing_id(record)
        if listing_id is None:
            continue

        sequence_number = record.get(SEQUENCE_NUMBER)
        if sequence_number is None:
            dynamodb = record.get("dynamodb")
            if isinstance(dynamodb, Mapping):
                sequence_number = dynamodb.get("SequenceNumber")

        existing = grouped.get(listing_id)
        if existing is None:
            grouped[listing_id] = (drop, [])
        elif drop.price_cents < existing[0].price_cents:
            grouped[listing_id] = (drop, existing[1])

        if sequence_number is not None:
            grouped[listing_id][1].append(str(sequence_number))
    return grouped


def _listing_id(record: Mapping[str, Any]) -> Optional[UUID]:
    """The listing the record is about, off the keys or off whichever image.

    `Keys` is preferred because it is present on every record regardless of the
    view type, and it is the partition key the grouping above is keyed on.
    """
    dynamodb = record.get("dynamodb")
    if isinstance(dynamodb, Mapping):
        keys = dynamodb.get("Keys")
        if isinstance(keys, Mapping):
            listing_id = _uuid(keys, "id")
            if listing_id is not None:
                return listing_id
    new_image, old_image = _images(record)
    return _uuid(new_image, "id") or _uuid(old_image, "id")


def evaluate(repos: Any, drop: PriceDrop) -> None:
    """Evaluate one listing's drop against every alert on its part.

    A thin call into `part_price_alert_service.evaluate_alerts_for_listing`,
    which is unchanged by this row and stays the single implementation of the
    alert semantics: the threshold test, the 24 hour cooldown, the per-alert
    exception isolation, and the rule that an SES failure leaves `last_fired_at`
    alone so the next observation retries.

    Keeping that function rather than reimplementing it in the consumer is what
    makes this row a move rather than a rewrite: the eleven service level tests
    that pinned its behaviour on the monolith still pin it here, and there is
    one place where a rule about when a user gets mail can be read.

    The repositories are passed rather than resolved, because a consumer builds
    its bundle once per execution environment while the service resolves
    `get_repositories()` per call.
    """
    from app.api.services.part_price_alert_service import evaluate_alerts_for_listing

    evaluate_alerts_for_listing(
        part_id=drop.part_id,
        retailer_id=drop.retailer_id,
        price_cents=drop.price_cents,
        observed_at=drop.observed_at,
        repos=repos,
    )


def process_records(repos: Any, records: Iterable[Mapping[str, Any]]) -> List[str]:
    """Evaluate every listing the batch dropped; return the failed sequence numbers.

    One evaluation per listing, and a failure on one listing does not stop the
    others: the listings in a batch are independent, and abandoning the rest of
    the batch on the first error would leave subscribers on healthy listings
    unemailed.
    """
    failures: List[str] = []
    for listing_id, (drop, sequence_numbers) in group_records_by_listing(records).items():
        try:
            evaluate(repos, drop)
        except Exception:
            # Broad on purpose, and narrower in practice than it reads. The
            # evaluation already catches per alert, so what reaches here is a
            # failure of the reads before the loop: a throttle, a timeout, or a
            # transient DynamoDB error, every one of which is worth the
            # mapping's retry. Letting it propagate instead would fail the whole
            # batch, which is what `ReportBatchItemFailures` exists to avoid.
            #
            # A retry can duplicate an email for an alert that already fired
            # inside a partially completed evaluation. The cooldown marker is
            # what bounds that, and it is why the marker is written per alert
            # rather than per listing.
            logger.exception(
                "Price alert stream: failed to evaluate alerts for a listing; reporting its records for retry.",
                extra={"listing_id": str(listing_id), "records": len(sequence_numbers)},
            )
            failures.extend(sequence_numbers)
    return failures


def handle(event: Mapping[str, Any], repos: Any) -> Dict[str, List[Dict[str, str]]]:
    """The handler body, with the repository bundle passed in.

    Separate from the entrypoint's route so a test can drive it with a bundle of
    fakes and no AWS at all, which is the same split every entrypoint makes
    between `build_app` and `main`.

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
            "Price alert stream: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": sequence} for sequence in failures]}
