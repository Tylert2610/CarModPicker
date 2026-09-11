"""Pure read service that aggregates `PartPriceHistory` over a time window.

Two public functions:
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from app.api.dependencies.repositories import get_repositories
from app.api.schemas.part_price_history import (
    PartPriceHistoryReadWithRetailer,
    PriceHistoryBatchSummaryItem,
    PriceHistorySinglePartResponse,
    PriceHistorySummary,
    PriceTrend,
    RetailerPriceBreakdown,
)
from app.db.dynamo.catalog import PartPriceHistory, Retailer

_VALID_WINDOWS = {"7d", "30d", "90d", "180d", "1y", "all"}
ALLOWED_WINDOWS: list[str] = sorted(_VALID_WINDOWS)


def parse_window(window: str) -> Optional[datetime]:
    """Translate a window literal to the lower-bound `since` timestamp.

    Returns None for `all` (no lower bound). Raises ValueError on anything
    outside the whitelist — the endpoint layer turns this into HTTP 422.
    """
    if window not in _VALID_WINDOWS:
        raise ValueError(f"Invalid window {window!r}; expected one of {sorted(_VALID_WINDOWS)}")
    if window == "all":
        return None
    now = datetime.now(UTC)
    if window == "7d":
        return now - timedelta(days=7)
    if window == "30d":
        return now - timedelta(days=30)
    if window == "90d":
        return now - timedelta(days=90)
    if window == "180d":
        return now - timedelta(days=180)
    return now - timedelta(days=365)


def _empty_summary() -> PriceHistorySummary:
    """Return a zeroed summary for a part with no observations."""
    return PriceHistorySummary(
        min_cents=None,
        max_cents=None,
        last_cents=None,
        last_observed_at=None,
        trend="flat",
        observation_count=0,
    )


def _empty_batch_item() -> PriceHistoryBatchSummaryItem:
    """Return a zeroed batch summary item for a part with no observations."""
    return PriceHistoryBatchSummaryItem(
        min_cents=None,
        max_cents=None,
        last_cents=None,
        last_observed_at=None,
        trend="flat",
        observation_count=0,
    )


def _compute_trend(prices_chronological: list[int]) -> PriceTrend:
    """Linear-regression slope sign on a chronologically ordered price series.

    Threshold: |slope * n| (i.e. total expected drift across the window) compared
    to ±1% of the mean. With <2 observations or zero mean, trend is flat.
    """
    n = len(prices_chronological)
    if n < 2:
        return "flat"
    mean = statistics.fmean(prices_chronological)
    if mean == 0:
        return "flat"
    x_mean = (n - 1) / 2.0
    num = 0.0
    den = 0.0
    for i, y in enumerate(prices_chronological):
        dx = i - x_mean
        num += dx * (y - mean)
        den += dx * dx
    if den == 0:
        return "flat"
    slope = num / den
    drift = slope * (n - 1)
    threshold = abs(mean) * 0.01
    if drift > threshold:
        return "up"
    if drift < -threshold:
        return "down"
    return "flat"


def _history_rows(
    part_ids: Iterable[UUID],
    *,
    since: Optional[datetime],
) -> tuple[list[tuple[PartPriceHistory, UUID]], dict[UUID, Retailer]]:
    """Load price observations for these parts with their retailers, newest first."""
    repos = get_repositories()
    listings = repos.part_listings.list_by_parts(part_ids)
    retailers = repos.retailers.get_many(listing.retailer_id for listing in listings)
    rows: list[tuple[PartPriceHistory, UUID]] = []
    for listing in listings:
        for entry in repos.part_price_history.list_by_listing(listing.id, since=since):
            rows.append((entry, listing.retailer_id))
    rows.sort(key=lambda row: (row[0].observed_at, str(row[0].id)), reverse=True)
    return rows, retailers


def _with_retailer(entry: PartPriceHistory, retailer: Retailer) -> PartPriceHistoryReadWithRetailer:
    """Build a price history read schema with its retailer named."""
    return PartPriceHistoryReadWithRetailer(
        id=entry.id,
        part_listing_id=entry.part_listing_id,
        price_cents=entry.price_cents,
        observed_at=entry.observed_at,
        retailer_id=retailer.id,
        retailer_name=retailer.name,
    )


def aggregate_single_part(
    part_id: UUID,
    window: str,
) -> PriceHistorySinglePartResponse:
    """Aggregate price history for one part over the given window.

    Empty-history cases return a well-formed empty payload (status 200 from the
    endpoint layer); 404 is the endpoint's call when the part itself is missing.
    """
    since = parse_window(window)
    group_ids = [part_id]

    all_rows, retailers = _history_rows(group_ids, since=None)
    rows = [(h, rid) for h, rid in all_rows if rid in retailers and (since is None or h.observed_at >= since)]

    history: list[PartPriceHistoryReadWithRetailer] = [_with_retailer(h, retailers[rid]) for h, rid in rows]

    pre_window_anchors: list[PartPriceHistoryReadWithRetailer] = []
    if since is not None:
        seen_retailers: set[UUID] = set()
        for h, rid in all_rows:
            if rid not in retailers or h.observed_at >= since or rid in seen_retailers:
                continue
            seen_retailers.add(rid)
            pre_window_anchors.append(_with_retailer(h, retailers[rid]))

    if not rows:
        return PriceHistorySinglePartResponse(
            summary=_empty_summary(),
            retailers=[],
            history=[],
            pre_window_anchors=pre_window_anchors,
            window=window,
        )

    all_prices = [h.price_cents for h, _rid in rows]
    chrono = list(reversed(all_prices))
    most_recent_h = rows[0][0]
    summary = PriceHistorySummary(
        min_cents=min(all_prices),
        max_cents=max(all_prices),
        last_cents=most_recent_h.price_cents,
        last_observed_at=most_recent_h.observed_at,
        trend=_compute_trend(chrono),
        observation_count=len(all_prices),
    )

    by_retailer: dict[UUID, list[PartPriceHistory]] = {}
    for h, rid in rows:
        by_retailer.setdefault(rid, []).append(h)

    retailer_breakdowns: list[RetailerPriceBreakdown] = []
    for retailer_id, entries in by_retailer.items():
        prices = [h.price_cents for h in entries]
        most_recent = entries[0]
        retailer_breakdowns.append(
            RetailerPriceBreakdown(
                retailer_id=retailer_id,
                retailer_name=retailers[retailer_id].name,
                min_cents=min(prices),
                max_cents=max(prices),
                last_cents=most_recent.price_cents,
                last_observed_at=most_recent.observed_at,
                observation_count=len(prices),
            )
        )

    retailer_breakdowns.sort(key=lambda b: b.retailer_name)

    return PriceHistorySinglePartResponse(
        summary=summary,
        retailers=retailer_breakdowns,
        history=history,
        pre_window_anchors=pre_window_anchors,
        window=window,
    )


def apply_retailer_filter(
    result: PriceHistorySinglePartResponse,
    retailer_id: UUID,
) -> PriceHistorySinglePartResponse:
    """Narrow a single-part aggregation to one retailer slice.

    Filters `history` to entries from the given retailer, keeps at most one
    matching `RetailerPriceBreakdown` in `retailers`, and recomputes `summary`
    """
    filtered_history = [h for h in result.history if h.retailer_id == retailer_id]
    filtered_retailers = [r for r in result.retailers if r.retailer_id == retailer_id]
    filtered_anchors = [a for a in result.pre_window_anchors if a.retailer_id == retailer_id]

    if not filtered_history:
        return PriceHistorySinglePartResponse(
            summary=_empty_summary(),
            retailers=filtered_retailers,
            history=[],
            pre_window_anchors=filtered_anchors,
            window=result.window,
        )

    prices_desc = [h.price_cents for h in filtered_history]
    chrono = list(reversed(prices_desc))
    most_recent = filtered_history[0]
    summary = PriceHistorySummary(
        min_cents=min(prices_desc),
        max_cents=max(prices_desc),
        last_cents=most_recent.price_cents,
        last_observed_at=most_recent.observed_at,
        trend=_compute_trend(chrono),
        observation_count=len(prices_desc),
    )
    return PriceHistorySinglePartResponse(
        summary=summary,
        retailers=filtered_retailers,
        history=filtered_history,
        pre_window_anchors=filtered_anchors,
        window=result.window,
    )


def aggregate_batch(
    part_ids: list[UUID],
    window: str,
) -> dict[UUID, PriceHistoryBatchSummaryItem]:
    """Aggregate min/max/last/trend per part over the window.

    Always returns one entry per requested part_id — empty parts get the
    well-formed empty shape so the frontend can iterate without holes. Resolves
    """
    since = parse_window(window)

    if not part_ids:
        return {}

    repos = get_repositories()
    requested = repos.parts.get_many(part_ids)
    canonical_for_requested: dict[UUID, UUID] = {
        pid: (part.canonical_part_id or pid) for pid, part in requested.items()
    }
    canonical_ids = set(canonical_for_requested.values())

    group_members: dict[UUID, list[UUID]] = {}
    for canon in canonical_ids:
        members = [canon]
        members.extend(sibling.id for sibling in repos.parts.list_link_group(canon))
        group_members[canon] = list(dict.fromkeys(members))

    obs_by_canonical: dict[UUID, list[tuple[int, datetime]]] = {}
    for canon, members in group_members.items():
        rows, _retailers = _history_rows(members, since=since)
        obs_by_canonical[canon] = [(h.price_cents, h.observed_at) for h, _rid in reversed(rows)]

    result: dict[UUID, PriceHistoryBatchSummaryItem] = {}
    for pid in part_ids:
        if pid not in requested:
            result[pid] = _empty_batch_item()
            continue
        observations = obs_by_canonical.get(canonical_for_requested[pid], [])
        if not observations:
            result[pid] = _empty_batch_item()
            continue
        prices_chrono = [p for p, _ts in observations]
        last_price, last_ts = observations[-1]
        result[pid] = PriceHistoryBatchSummaryItem(
            min_cents=min(prices_chrono),
            max_cents=max(prices_chrono),
            last_cents=last_price,
            last_observed_at=last_ts,
            trend=_compute_trend(prices_chrono),
            observation_count=len(prices_chrono),
        )
    return result
