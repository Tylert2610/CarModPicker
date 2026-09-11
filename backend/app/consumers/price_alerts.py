"""Send price drop alert mail off the `part_listings` stream, so `admin` owns it.

A record counts only when the new price is below the old, and `last_fired_at` stops
a redelivery mailing twice. It is written after the send, never before.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

SEQUENCE_NUMBER = "sequenceNumber"


class PriceDrop:
    """One evaluated listing record: what to evaluate its part's alerts against.

    An object rather than a tuple, because two UUIDs and an int in a row is the
    shape that eventually gets passed in the wrong order.
    """

    __slots__ = ("part_id", "retailer_id", "price_cents", "observed_at")

    def __init__(
        self,
        part_id: UUID,
        retailer_id: UUID,
        price_cents: int,
        observed_at: datetime,
    ) -> None:
        """Hold the four values an alert evaluation needs."""
        self.part_id = part_id
        self.retailer_id = retailer_id
        self.price_cents = price_cents
        self.observed_at = observed_at

    def __eq__(self, other: object) -> bool:
        """Compare on all four fields, so tests can assert on a whole drop."""
        if not isinstance(other, PriceDrop):
            return NotImplemented
        return (
            self.part_id == other.part_id
            and self.retailer_id == other.retailer_id
            and self.price_cents == other.price_cents
            and self.observed_at == other.observed_at
        )

    def __repr__(self) -> str:
        """All four fields, for a readable assertion failure."""
        return (
            f"PriceDrop(part_id={self.part_id}, retailer_id={self.retailer_id}, "
            f"price_cents={self.price_cents}, observed_at={self.observed_at!r})"
        )


def _plain(value: Any) -> Any:
    """One attribute value out of a stream image's low level wire format.

    The string, number, null and boolean forms are unwrapped; anything else is
    returned untouched for the caller to reject.
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
    """One UUID-valued attribute off an image, or `None` when unreadable."""
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

    A naive value is read as UTC, matching the alert service, because crawler
    timestamps have historically arrived both ways.
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

    `None` covers a REMOVE, an unchanged or raised price, and an unreadable
    image alike, because none of those is retryable.
    """
    new_image, old_image = _images(record)
    if not new_image:
        return None

    price_cents = _price_cents(new_image)
    if price_cents is None:
        return None

    previous = _price_cents(old_image)
    if previous is not None and price_cents >= previous:
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
    """Map each listing to the lowest drop in the batch and the records that asked.

    One evaluation per listing per batch, so several writes to one listing cannot
    race the cooldown marker into several emails.
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

    A thin call into `evaluate_alerts_for_listing`, which stays the single
    implementation of the threshold, cooldown and per-alert isolation rules.
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
    """Evaluate every listing the batch dropped and return the failed sequence numbers.

    Listings are independent, so one failure does not leave the rest unemailed.
    """
    failures: List[str] = []
    for listing_id, (drop, sequence_numbers) in group_records_by_listing(records).items():
        try:
            evaluate(repos, drop)
        except Exception:
            logger.exception(
                "Price alert stream: failed to evaluate alerts for a listing; reporting its records for retry.",
                extra={"listing_id": str(listing_id), "records": len(sequence_numbers)},
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
            "Price alert stream: reporting partial batch failure.",
            extra={"failed": len(failures), "records": len(records)},
        )
    return {"batchItemFailures": [{"itemIdentifier": sequence} for sequence in failures]}
