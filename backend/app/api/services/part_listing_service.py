"""
Service for part listing deduplication and retailer/listing/price operations.

Used by global part create, create-and-add-part, and scrapers to:
- Get-or-create retailers and part_manufacturers
- Find existing parts by URL, part_manufacturer+part_number, or GTIN (UPC/EAN)
- Create/update PartListing and append PartPriceHistory
"""

import re
from datetime import UTC, datetime
from typing import Any, Iterable, Optional
from urllib.parse import urlparse
from uuid import UUID

from app.api.dependencies.repositories import get_repositories
from app.api.schemas.part_listing import PartListingRead, PartListingReadWithRetailer
from app.api.schemas.retailer import RetailerRead
from app.db.dynamo.catalog import Part, PartListing, PartManufacturer, PartPriceHistory, Retailer
from app.db.dynamo.repository import transact_write
from app.db.dynamo.users import UniqueAttributeTaken

# Tokens stripped from the tail of a manufacturer name during canonical comparison.
# Sub-divisions ("Performance", "Racing", "Electronics", ...) and corporate suffixes
# ("Inc", "LLC", ...) all collapse to the parent brand so an adapter submitting
# "AEM Electronics" or "APR Performance" resolves to the existing "AEM" / "APR" row
# rather than creating a duplicate.
_MANUFACTURER_TRAILING_TOKENS = frozenset(
    {
        # Corporate suffixes
        "inc",
        "llc",
        "ltd",
        "co",
        "corp",
        "company",
        "llp",
        "limited",
        # Brand sub-divisions / generic descriptors
        "performance",
        "racing",
        "motorsport",
        "motorsports",
        "tuning",
        "engineering",
        "electronics",
        "induction",
        "industries",
        "usa",
        "america",
        "automotive",
    }
)


def manufacturer_name_canonical(raw: str) -> str:
    """Reduce a manufacturer name to a canonical comparison key.

    Steps:
      1. Lowercase.
      2. Strip non-alphanumerics (collapses ``A'PEX-i`` -> ``apexi``,
         ``Borg Warner`` -> ``borgwarner``, ``K&N`` -> ``kn``, ``Stop Tech``
         -> ``stoptech``, ``Studio RSR`` -> ``studiorsr``).
      3. After tokenizing on whitespace, drop trailing tokens listed in
         ``_MANUFACTURER_TRAILING_TOKENS`` (corporate suffixes + brand
         sub-division words). Iteratively — ``Titan 7 LLC USA`` collapses
         all the way to ``titan7``.

    Returns an empty string if nothing remains. Used for case-insensitive,
    whitespace-insensitive, suffix-insensitive lookups; never written back
    to the DB.
    """
    if not raw:
        return ""
    lowered = raw.lower()
    # Tokenize first (whitespace + punctuation), then apply the trailing-token
    # filter, then strip remaining non-alphanumerics on each surviving token.
    # This way ``AEM Electronics`` -> tokens ["aem", "electronics"] -> drop
    # trailing "electronics" -> "aem", instead of mashing into "aemelectronics"
    # and never matching the trailing-token list.
    tokens = [t for t in re.split(r"[^a-z0-9]+", lowered) if t]
    while tokens and tokens[-1] in _MANUFACTURER_TRAILING_TOKENS:
        tokens.pop()
    return "".join(tokens)


def _domain_variants(domain: str) -> list[str]:
    normalized = domain.strip().lower()
    if normalized.startswith("www."):
        return [normalized, normalized[4:]]
    return [normalized, "www." + normalized]


def get_or_create_retailer(
    name: str,
    *,
    domain: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Retailer:
    """Get existing retailer by domain (if provided) or name; otherwise create."""
    repos = get_repositories()
    if domain:
        for candidate in _domain_variants(domain):
            retailer = repos.retailers.get_by_domain(candidate)
            if retailer:
                return retailer
    retailer = repos.retailers.get_by_name(name)
    if retailer:
        if domain and not retailer.domain:
            retailer = repos.retailers.update_unique(
                retailer, domain=domain.strip().lower(), base_url=base_url or retailer.base_url
            )
        return retailer
    candidate = Retailer(
        name=name.strip(),
        domain=domain.strip().lower() if domain else None,
        base_url=base_url,
        is_active=True,
    )
    try:
        return repos.retailers.create_unique(candidate)
    except UniqueAttributeTaken:
        existing = repos.retailers.get_by_name(name)
        if existing is None and domain:
            existing = repos.retailers.get_by_domain(domain.strip().lower())
        if existing is not None:
            return existing
        raise


def _find_pm_by_name(name_normalized: str) -> Optional[PartManufacturer]:
    """Look up a manufacturer by name.

    Two-pass match:
      1. Exact case-insensitive name match.
      2. Canonical-key match: compute ``manufacturer_name_canonical`` for the
         input, then for each row, and return the first row whose canonical
         key matches. This lets ``"APR Performance"`` resolve to the existing
         ``"APR"`` row, or ``"AEM Electronics"`` to ``"AEM"``, without minting
         a duplicate. Pulls all rows in memory; the catalog is small
         (~hundreds), so the cost is negligible compared to the dedup win. If
         two rows share a canonical key, return the first sorted by name for
         determinism.
    """
    repos = get_repositories()
    exact = repos.part_manufacturers.get_by_name(name_normalized)
    if exact is not None:
        return exact

    canonical_key = manufacturer_name_canonical(name_normalized)
    if not canonical_key:
        return None
    for pm in repos.part_manufacturers.list_sorted():
        if manufacturer_name_canonical(pm.name) == canonical_key:
            return pm
    return None


def get_or_create_part_manufacturer_by_name(name: str) -> Optional[PartManufacturer]:
    """Get-or-create a manufacturer by name (case-insensitive).

    Used by the Chrome extension, the seed script, admin-driven creates, and
    user part creates. There is a single global manufacturer namespace.

    Returns ``None`` if the name is empty.
    """
    if not name or not name.strip():
        return None
    name_normalized = name.strip()
    existing = _find_pm_by_name(name_normalized)
    if existing:
        return existing
    try:
        return get_repositories().part_manufacturers.create_unique(
            PartManufacturer(name=name_normalized, is_active=True)
        )
    except UniqueAttributeTaken:
        existing = _find_pm_by_name(name_normalized)
        if existing is not None:
            return existing
        raise


def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url or not url.strip():
        return None
    return url.strip()


def normalize_part_number(part_number: Optional[str]) -> Optional[str]:
    """
    Normalize part number by stripping common prefixes (SKU:, Part #:, etc.)
    so lookups and storage use the actual code for deduplication.
    """
    if not part_number or not part_number.strip():
        return None
    s = part_number.strip()
    prefixes = [
        r"^SKU\s*:\s*",
        r"^Part\s*#\s*:\s*",
        r"^Part\s*Number\s*:\s*",
        r"^Item\s*#\s*:\s*",
        r"^Product\s*Code\s*:\s*",
        r"^Model\s*#?\s*:\s*",
        r"^Code\s*:\s*",
    ]
    for pattern in prefixes:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = s.strip()
    return s if s else None


def _owned_by(part: Part, creator_id: Optional[UUID]) -> bool:
    return creator_id is None or part.user_id == creator_id


def find_part_by_product_url(
    product_url: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[Part]:
    """
    Find a part that owns a PartListing with this product URL.

    ``creator_id`` scopes the search to parts owned by that user — used by the
    create dup check to ask "does *this* user already have a part for this
    URL?" without being fooled by another user's part sorting first.

    Returns any matching Part (canonical or duplicate). Callers doing canonical
    dedup should resolve the result to its canonical.
    """
    normalized = _normalize_url(product_url)
    if not normalized:
        return None
    repos = get_repositories()
    listings = repos.part_listings.list_by_product_url(normalized)
    parts = repos.parts.get_many(listing.part_id for listing in listings)
    for listing in sorted(listings, key=lambda item: str(item.id)):
        part = parts.get(listing.part_id)
        if part is not None and _owned_by(part, creator_id):
            return part
    return None


def _first_canonical(parts: Iterable[Part], creator_id: Optional[UUID]) -> Optional[Part]:
    for part in sorted(parts, key=lambda item: str(item.id)):
        if part.canonical_part_id is None and _owned_by(part, creator_id):
            return part
    return None


def find_part_by_part_manufacturer_and_part_number(
    part_manufacturer_id: UUID,
    part_number: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[Part]:
    """
    Find a canonical part by part_manufacturer_id and part_number.

    Uses ``part_number_normalized`` (the canonical alphanumeric-uppercase
    form) for matching so styling drift between ``"AEM-30-2400"`` and
    ``"AEM 30/2400"`` collapses into one dedup key. Only returns canonicals.

    ``creator_id`` optionally scopes to parts owned by that user.
    """
    from app.api.services.page_parser import part_number_canonical

    canonical = part_number_canonical(part_number)
    if not canonical:
        return None
    matches = get_repositories().parts.list_by_manufacturer_part_number(part_manufacturer_id, canonical)
    return _first_canonical(matches, creator_id)


def normalize_gtin(gtin: Optional[str]) -> Optional[str]:
    """
    Normalize GTIN (UPC/EAN) to digits only for storage and dedup lookup.
    Handles formats like 0-12345-67890-1 or 012345678901.
    """
    if not gtin or not gtin.strip():
        return None
    digits = "".join(c for c in gtin.strip() if c.isdigit())
    return digits if digits else None


def find_part_by_gtin(
    gtin: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[Part]:
    """
    Find a canonical part by GTIN (UPC/EAN).

    Uses normalized digits-only for matching. Only returns canonicals so the
    linker never recommends a duplicate as a merge target.

    ``creator_id`` optionally scopes to parts owned by that user.
    """
    normalized = normalize_gtin(gtin)
    if not normalized:
        return None
    repos = get_repositories()
    exact = _first_canonical(repos.parts.list_by_gtin(normalized), creator_id)
    if exact is not None:
        return exact
    fuzzy = [part for part in repos.parts.list_canonical() if part.gtin and normalize_gtin(part.gtin) == normalized]
    return _first_canonical(fuzzy, creator_id)


def find_existing_part_for_create(
    *,
    creator_id: UUID,
    product_url: Optional[str] = None,
) -> Optional[tuple[Part, str]]:
    """
    Decide whether a part-create attempt should be denied in favor of an
    existing part the same user already owns.

    Policy — URL-only, per-user matching: if the creator already has a part
    with a listing for this exact ``product_url``, deny and point them at
    their own prior entry (no accidental self-duplicates). Different users may
    each contribute their own row for the same URL.

    Returns ``(existing_part, "own_part_exists")`` or ``None`` if nothing
    blocks the create.
    """
    if not product_url or not product_url.strip():
        return None

    own = find_part_by_product_url(product_url, creator_id=creator_id)
    if own is not None:
        return own, "own_part_exists"

    return None


def link_group_ids(part: Part) -> list[UUID]:
    canonical_id = part.canonical_part_id or part.id
    ids = [canonical_id]
    ids.extend(linked.id for linked in get_repositories().parts.list_link_group(canonical_id))
    if part.id not in ids:
        ids.append(part.id)
    return list(dict.fromkeys(ids))


def best_price_for_group(part_ids: Iterable[UUID]) -> Optional[int]:
    listings = get_repositories().part_listings.list_by_parts(part_ids)
    prices = [
        listing.last_known_price_cents
        for listing in listings
        if listing.last_known_price_cents is not None and listing.last_known_price_cents >= 0
    ]
    return min(prices) if prices else None


def best_price_actions(part: Part, group_ids: list[UUID], best_price: Optional[int]) -> list[dict[str, Any]]:
    repos = get_repositories()
    canonical_id = part.canonical_part_id or part.id
    actions: list[dict[str, Any]] = []
    parts = repos.parts.get_many(group_ids)
    for target_id in dict.fromkeys([canonical_id, part.id]):
        target = parts.get(target_id)
        if target is not None and target.best_price_cents != best_price:
            actions.append(repos.parts.update_action(str(target_id), best_price_cents=best_price))
    return actions


def refresh_best_price(part_id: UUID) -> None:
    repos = get_repositories()
    part = repos.parts.get(str(part_id))
    if part is None:
        return
    group_ids = link_group_ids(part)
    actions = best_price_actions(part, group_ids, best_price_for_group(group_ids))
    if actions:
        transact_write(actions)


def _same_day_bounds(ts: datetime) -> tuple[datetime, datetime]:
    start = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def create_or_update_listing_and_price(
    part_id: UUID,
    retailer_id: UUID,
    *,
    product_url: Optional[str] = None,
    price_cents: Optional[int] = None,
    observed_at: Optional[datetime] = None,
) -> PartListing:
    """
    Create or update PartListing for (part_id, retailer_id).
    If price_cents is provided, append PartPriceHistory and update listing's last_known_price_cents/last_price_updated_at.
    Returns the PartListing.
    """
    repos = get_repositories()
    normalized_url = _normalize_url(product_url)
    listing = repos.part_listings.get_by_part_and_retailer(part_id, retailer_id)
    if not listing and normalized_url:
        listing = next(
            (item for item in repos.part_listings.list_by_part(part_id) if item.product_url == normalized_url),
            None,
        )
    actions: list[dict[str, Any]] = []
    if not listing:
        listing = PartListing(part_id=part_id, retailer_id=retailer_id, product_url=normalized_url)
        actions.append(repos.part_listings.create_action(listing))
    else:
        if normalized_url:
            listing = listing.model_copy(update={"product_url": normalized_url})
        listing.touch()
        actions.append(repos.part_listings.put_action(listing))

    ts: Optional[datetime] = None
    if price_cents is not None and price_cents >= 0:
        ts = observed_at or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        day_start, day_end = _same_day_bounds(ts)
        existing = repos.part_price_history.find_between(listing.id, day_start, day_end)
        if existing:
            history = existing.model_copy(update={"price_cents": price_cents, "observed_at": ts})
        else:
            history = PartPriceHistory(part_listing_id=listing.id, price_cents=price_cents, observed_at=ts)
        actions.append(repos.part_price_history.put_action(history))
        listing.last_known_price_cents = price_cents
        listing.last_price_updated_at = ts
        actions[0] = repos.part_listings.put_action(listing)

        part = repos.parts.get(str(part_id))
        if part is not None:
            group_ids = link_group_ids(part)
            other_prices = [
                item.last_known_price_cents
                for item in repos.part_listings.list_by_parts(group_ids)
                if item.id != listing.id
                and item.last_known_price_cents is not None
                and item.last_known_price_cents >= 0
            ]
            best_price = min([price_cents, *other_prices])
            actions.extend(best_price_actions(part, group_ids, best_price))

    transact_write(actions)

    # Split plan row 25, seam 4. The price drop alert used to be evaluated here,
    # synchronously, right after this transaction committed: a fan-out read of
    # `part_price_alerts`, `parts`, `retailers` and `users` plus an SES call,
    # all on the request thread and all inside a 29 second Lambda. Three of
    # those tables and the SES grant belong to `admin` rather than to `catalog`,
    # which made it the seam. It now runs off the `part_listings` stream in
    # `app/consumers/price_alerts.py`, so this write returns as soon as the
    # transaction commits and `catalog` holds no SES grant at all.
    #
    # The stream carries everything the evaluation needs, because the item this
    # transaction just wrote is where the old call read its four arguments from:
    # `part_id`, `retailer_id`, `last_known_price_cents` and
    # `last_price_updated_at` are all attributes of the listing.

    return listing


def get_best_listing_for_part(part_id: UUID) -> Optional[PartListing]:
    """Return the PartListing with the lowest current price for this part."""
    priced = [
        listing
        for listing in get_repositories().part_listings.list_by_part(part_id)
        if listing.last_known_price_cents is not None and listing.last_known_price_cents >= 0
    ]
    if not priced:
        return None
    return min(priced, key=lambda listing: (listing.last_known_price_cents or 0, str(listing.id)))


def listing_with_retailer(listing: PartListing, retailer: Retailer) -> PartListingReadWithRetailer:
    return PartListingReadWithRetailer(
        **PartListingRead.model_validate(listing).model_dump(),
        retailer=RetailerRead.model_validate(retailer),
    )


def listings_with_retailers(listings: Iterable[PartListing]) -> list[PartListingReadWithRetailer]:
    listings = list(listings)
    retailers = get_repositories().retailers.get_many(listing.retailer_id for listing in listings)
    result: list[PartListingReadWithRetailer] = []
    for listing in listings:
        retailer = retailers.get(listing.retailer_id)
        if retailer is not None:
            result.append(listing_with_retailer(listing, retailer))
    return result


def delete_part_cascade_actions(part: Part) -> list[dict[str, Any]]:
    repos = get_repositories()
    actions: list[dict[str, Any]] = []
    for car_id in part.car_ids:
        actions.append(repos.part_cars.unlink_action(part.id, car_id))
    return actions


def delete_listing_with_history(listing: PartListing) -> None:
    repos = get_repositories()
    repos.part_price_history.delete_for_listing(listing.id)
    repos.part_listings.delete(str(listing.id))


def delete_part_listings(part_id: UUID) -> None:
    repos = get_repositories()
    for listing in repos.part_listings.delete_for_part(part_id):
        repos.part_price_history.delete_for_listing(listing.id)


def domain_from_url(url: str) -> Optional[str]:
    """Extract domain (hostname) from a URL for retailer lookup."""
    if not url or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
        if parsed.netloc:
            return parsed.netloc.lower()
        return None
    except Exception:
        return None
