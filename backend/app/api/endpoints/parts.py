"""
Parts endpoint using base classes to eliminate redundancy.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.auth import (
    get_current_user,
    get_optional_current_user,
    require_api_key_or_admin,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.pagination import CursorPage
from app.api.schemas.part import (
    MAX_IMAGES_PER_PART,
    PartAppendImages,
    PartCreate,
    PartRead,
    PartReadWithListings,
    PartReadWithVotes,
    PartUpdate,
    SetPrimaryImageRequest,
)
from app.api.schemas.part_listing import PartListingCreate, PartListingReadWithRetailer
from app.api.schemas.part_price_history import (
    PriceHistoryBatchRequest,
    PriceHistoryBatchResponse,
    PriceHistorySinglePartResponse,
)
from app.api.services.part_listing_service import (
    create_or_update_listing_and_price,
    find_part_by_part_manufacturer_and_part_number,
    listing_with_retailer,
    listings_with_retailers,
)
from app.api.services.part_price_aggregation_service import (
    ALLOWED_WINDOWS,
    aggregate_batch,
    aggregate_single_part,
    apply_retailer_filter,
    parse_window,
)
from app.api.services.part_service import PartListFilters, PartService, purge_related_rows_for_parts
from app.api.utils.authorization import require_part_edit_permission
from app.api.utils.base_dynamo_endpoint_router import BaseDynamoEndpointRouter
from app.api.utils.common_patterns import PublicEndpointDeps, get_standard_public_endpoint_dependencies
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params
from app.api.utils.endpoint_decorators import pagination_responses, standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.catalog import Part
from app.db.dynamo.users import User as DBUser

router = APIRouter()
part_service = PartService()


def _get_part_or_404(repos: Repositories, part_id: UUID) -> Part:
    part = repos.parts.get(str(part_id))
    if part is None:
        ResponsePatterns.raise_not_found("Part")
    assert part is not None
    return part


def _invalid_window(window: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error_code": "INVALID_WINDOW",
            "message": f"Invalid window {window!r}; expected one of {ALLOWED_WINDOWS}",
            "details": {"allowed": ALLOWED_WINDOWS},
        },
    )


@router.get(
    "/with-votes",
    response_model=CursorPage[PartReadWithVotes],
    responses=pagination_responses("part", allow_public_read=True),
)
async def read_parts_with_votes(
    params: CursorParams = Depends(get_cursor_params),
    category_id: Optional[UUID] = Query(None, description="Filter by category ID (single; use category_ids for multi)"),
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs (parts matching any)"),
    car_id: Optional[UUID] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[UUID]] = Query(
        None, description="Filter by car IDs (e.g. all generations for a make or model)"
    ),
    part_manufacturer_id: Optional[UUID] = Query(
        None, description="Filter by part_manufacturer ID (single; use part_manufacturer_ids for multi)"
    ),
    part_manufacturer_ids: Optional[List[UUID]] = Query(
        None, description="Filter by part_manufacturer IDs (parts matching any)"
    ),
    retailer_id: Optional[UUID] = Query(None, description="Filter to parts that have a listing from this retailer"),
    user_id: Optional[UUID] = Query(None, description="Filter to parts created by this user (for 'My Parts' view)"),
    sort: Optional[str] = Query(
        None,
        description="Sort: votes_desc (default), votes_asc, lowest_price, highest_price, name_asc, name_desc, part_number_asc, part_number_desc, part_manufacturer_asc, part_manufacturer_desc, category_asc, category_desc",
    ),
    search: Optional[str] = Query(None, description="Search in part names and descriptions"),
    min_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price >= this (cents)"),
    max_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price <= this (cents)"),
    universal: Optional[bool] = Query(
        None, description="When true, return only parts that fit all cars (is_universal)"
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> CursorPage[PartReadWithVotes]:
    """Get all parts with vote data and optional filtering and search."""
    filters = PartListFilters(
        category_ids=category_ids or ([category_id] if category_id is not None else None),
        part_manufacturer_ids=part_manufacturer_ids
        or ([part_manufacturer_id] if part_manufacturer_id is not None else None),
        car_ids=car_ids or ([car_id] if car_id is not None else None),
        search=search,
        user_id=user_id,
        retailer_id=retailer_id,
        universal=universal,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
    page = part_service.list_with_votes(
        filters, sort=sort, limit=params.limit, cursor=params.cursor, current_user=current_user
    )
    deps["logger"].info(f"Retrieved {len(page.items)} parts (limit: {params.limit})")
    return page


@router.get(
    "/filter-options",
    response_model=Dict[str, Any],
)
async def get_parts_filter_options(
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs (parts matching any)"),
    part_manufacturer_ids: Optional[List[UUID]] = Query(
        None, description="Filter by part_manufacturer IDs (parts matching any)"
    ),
    car_id: Optional[UUID] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[UUID]] = Query(
        None, description="Filter by car IDs (e.g. all generations for a make or model)"
    ),
    search: Optional[str] = Query(None, description="Search in names and descriptions"),
    user_id: Optional[UUID] = Query(None, description="Filter to parts created by this user (e.g. for My Parts)"),
    universal: Optional[bool] = Query(None, description="When true, scope to parts that fit all cars (is_universal)"),
) -> Dict[str, Any]:
    """
    Return category_ids and part_manufacturer_ids that have at least one part matching the current filters.
    """
    filters = PartListFilters(
        category_ids=category_ids,
        part_manufacturer_ids=part_manufacturer_ids,
        car_ids=car_ids or ([car_id] if car_id is not None else None),
        search=search,
        user_id=user_id,
        universal=universal,
    )
    return part_service.filter_options(filters)


@router.get(
    "/category/{category_id}",
    response_model=CursorPage[PartRead],
    responses=pagination_responses("part", allow_public_read=True),
)
async def get_parts_by_category(
    category_id: UUID,
    params: CursorParams = Depends(get_cursor_params),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> CursorPage[PartRead]:
    """Get parts by category with pagination."""
    page = part_service.page_by_category(category_id, limit=params.limit, cursor=params.cursor)
    deps["logger"].info(f"Retrieved {len(page.items)} parts for category {category_id}")
    return page


@router.get(
    "/check-url",
    response_model=Dict[str, Optional[UUID]],
    responses=standard_responses(success_description="URL check completed"),
)
async def check_product_url_exists(
    product_url: Optional[str] = Query(None, description="Product URL to check"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Optional[UUID]]:
    """Check if a product URL already exists in the parts catalog."""
    logger = deps["logger"]

    try:
        if not product_url or not product_url.strip():
            return {"existing_part_id": None}

        normalized_url = product_url.strip()
        listing = repos.part_listings.get_by_product_url(normalized_url)
        existing_part = repos.parts.get(str(listing.part_id)) if listing else None

        if existing_part:
            logger.info(f"URL check: Found existing part {existing_part.id} for URL: {normalized_url[:50]}...")
            return {"existing_part_id": existing_part.id}
        logger.debug(f"URL check: No existing part found for URL: {normalized_url[:50]}...")
        return {"existing_part_id": None}
    except Exception as e:
        logger.error(f"Error checking product URL: {str(e)}", exc_info=True)
        return {"existing_part_id": None}


@router.get(
    "/find-by-part-manufacturer-and-part-number",
    response_model=PartRead,
    responses=standard_responses(success_description="Existing part found", not_found=True),
)
async def find_part_by_part_manufacturer_and_part_number_endpoint(
    part_manufacturer_id: UUID = Query(..., description="PartManufacturer ID"),
    part_number: str = Query(..., min_length=1, description="Part number or SKU"),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Find an existing part by part manufacturer and part number (normalized). Returns 404 if not found."""
    part = find_part_by_part_manufacturer_and_part_number(part_manufacturer_id, part_number)
    if not part:
        raise HTTPException(status_code=404, detail="No part found for this part manufacturer and part number")
    return PartRead.model_validate(part)


@router.post(
    "/",
    response_model=PartRead,
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Not authorized"},
        409: {"description": "Part already exists"},
    },
)
async def create_part(
    data: PartCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Create a user-contributed part, optionally with a retailer listing and price."""
    part = part_service.create_part(data, current_user, deps["logger"])
    return PartRead.model_validate(part)


@router.get(
    "/{part_id}/listings",
    response_model=List[PartListingReadWithRetailer],
    responses=standard_responses(success_description="Part listings retrieved", not_found=True),
)
async def get_part_listings(
    part_id: UUID,
    repos: Repositories = Depends(get_repositories),
) -> List[PartListingReadWithRetailer]:
    """List all retailer listings for a part (with current price)."""
    _get_part_or_404(repos, part_id)
    return listings_with_retailers(repos.part_listings.list_by_part(part_id))


@router.post(
    "/{part_id}/listings",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(success_description="Part listing created or updated", not_found=True),
)
async def create_or_update_part_listing(
    part_id: UUID,
    data: PartListingCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_user),
) -> PartListingReadWithRetailer:
    """Create or update a retailer listing for a part (and optionally add a price)."""
    _get_part_or_404(repos, part_id)
    retailer = repos.retailers.get(str(data.retailer_id))
    if retailer is None:
        ResponsePatterns.raise_not_found("Retailer")
    assert retailer is not None
    if data.part_id != part_id:
        ResponsePatterns.raise_conflict(
            message="Body part_id must match path part_id.",
            error_code="PART_ID_MISMATCH",
        )
    listing = create_or_update_listing_and_price(
        part_id,
        data.retailer_id,
        product_url=data.product_url,
        price_cents=data.price_cents,
    )
    return listing_with_retailer(listing, retailer)


@router.post(
    "/{part_id}/append-images",
    response_model=PartRead,
    responses=standard_responses(success_description="Images appended to part", not_found=True),
)
async def append_images_to_part(
    part_id: UUID,
    data: PartAppendImages,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartRead:
    """Append image file keys to a part's gallery."""
    part = _get_part_or_404(repos, part_id)
    require_part_edit_permission(current_user, part)

    existing = list(part.image_urls or [])
    if len(existing) >= MAX_IMAGES_PER_PART:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Part already has the maximum number of images ({MAX_IMAGES_PER_PART}).",
        )

    seen = set(existing)
    for fk in data.file_keys:
        if fk and fk not in seen and len(existing) < MAX_IMAGES_PER_PART:
            existing.append(fk)
            seen.add(fk)

    part = part_service.apply_changes(part, image_urls=existing[:MAX_IMAGES_PER_PART])
    return PartRead.model_validate(part)


def _get_part_image_file_keys(part: Part) -> List[str]:
    """Return ordered list of image file keys. First entry is the primary/display image."""
    return list(part.image_urls or [])


@router.delete(
    "/{part_id}/images/{image_index}",
    response_model=PartRead,
    responses=standard_responses(success_description="Image removed from part", not_found=True),
)
async def remove_image_from_part(
    part_id: UUID,
    image_index: int,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartRead:
    """Remove the image at the given index from the part's gallery."""
    from app.api.services.storage_service import storage_service
    from app.api.utils.image_utils import is_file_key

    part = _get_part_or_404(repos, part_id)
    require_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if image_index < 0 or image_index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {image_index}. Part has {len(file_keys)} image(s).",
        )

    removed_key = file_keys[image_index]
    new_keys = [fk for i, fk in enumerate(file_keys) if i != image_index]

    if removed_key and is_file_key(removed_key):
        try:
            storage_service.delete_image(removed_key)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to delete image from storage for part %s: %s",
                part_id,
                e,
            )

    part = part_service.apply_changes(part, image_urls=new_keys if new_keys else None)
    return PartRead.model_validate(part)


@router.patch(
    "/{part_id}/primary-image",
    response_model=PartRead,
    responses=standard_responses(success_description="Primary image updated", not_found=True),
)
async def set_primary_image_for_part(
    part_id: UUID,
    data: SetPrimaryImageRequest,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartRead:
    """Set the image at the given index as the primary (display) image."""
    part = _get_part_or_404(repos, part_id)
    require_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if data.index < 0 or data.index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {data.index}. Part has {len(file_keys)} image(s).",
        )

    primary_key = file_keys[data.index]
    new_order = [primary_key] + [fk for i, fk in enumerate(file_keys) if i != data.index]
    part = part_service.apply_changes(part, image_urls=new_order)
    return PartRead.model_validate(part)


def _best_listing(repos: Repositories, part_id: UUID) -> Optional[PartListingReadWithRetailer]:
    listings = listings_with_retailers(repos.part_listings.list_by_part(part_id))
    priced = [l for l in listings if l.last_known_price_cents is not None and l.last_known_price_cents >= 0]
    return min(priced, key=lambda l: (l.last_known_price_cents or 0, str(l.id))) if priced else None


@router.get(
    "/{part_id}/best-listing",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(success_description="Best (lowest price) listing retrieved", not_found=True),
)
async def get_part_best_listing(
    part_id: UUID,
    repos: Repositories = Depends(get_repositories),
) -> PartListingReadWithRetailer:
    """Get the listing with the lowest current price for this part (across its link group)."""
    _get_part_or_404(repos, part_id)
    best = _best_listing(repos, part_id)
    if not best:
        ResponsePatterns.raise_http_exception(
            status.HTTP_404_NOT_FOUND,
            "No listing with price for this part",
            error_code="NOT_FOUND",
        )
    assert best is not None
    return best


@router.get(
    "/{part_id}/with-listings",
    response_model=PartReadWithListings,
    responses=standard_responses(success_description="Part with listings and best listing retrieved", not_found=True),
)
async def get_part_with_listings(
    part_id: UUID,
    repos: Repositories = Depends(get_repositories),
) -> PartReadWithListings:
    """Get a part with all retailer listings (aggregated across the link group) and best price."""
    part = _get_part_or_404(repos, part_id)
    listings = listings_with_retailers(repos.part_listings.list_by_part(part_id))
    priced = [l for l in listings if l.last_known_price_cents is not None and l.last_known_price_cents >= 0]
    best_listing = min(priced, key=lambda l: (l.last_known_price_cents or 0, str(l.id))) if priced else None
    part_dict = PartRead.model_validate(part).model_dump()
    part_dict["best_price_cents"] = best_listing.last_known_price_cents if best_listing else None
    return PartReadWithListings(**part_dict, listings=listings, best_listing=best_listing)


@router.get(
    "/{part_id}/price-history",
    response_model=PriceHistorySinglePartResponse,
    responses=standard_responses(
        success_description="Price history retrieved (object shape with summary, retailers, history, window)",
        not_found=True,
    ),
)
async def get_part_price_history(
    part_id: UUID,
    window: str = Query(
        "90d",
        description=f"Time window for aggregation. Allowed: {ALLOWED_WINDOWS}",
    ),
    retailer_id: Optional[UUID] = Query(None, description="Filter by retailer ID"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> PriceHistorySinglePartResponse:
    """Get price history for this part (aggregated across its link group).

    Returns the S05 object shape (`summary`, `retailers`, `history`, `window`).
    Optional `retailer_id` narrows the response to one retailer; `summary` is
    recomputed from that filtered slice (not the cross-retailer aggregate).
    Invalid `window` values produce a 422 with `error_code: INVALID_WINDOW`
    (see schema response).
    """
    logger = deps["logger"]
    _get_part_or_404(repos, part_id)

    try:
        parse_window(window)
    except ValueError:
        raise _invalid_window(window)

    started = time.perf_counter()
    result = aggregate_single_part(part_id, window)
    if retailer_id is not None:
        result = apply_retailer_filter(result, retailer_id)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "price_history_aggregation: endpoint=single part_count=1 "
        "window=%s link_groups_resolved=%d rows_scanned=%d elapsed_ms=%d",
        window,
        1,
        result.summary.observation_count,
        elapsed_ms,
    )
    return result


@router.post(
    "/price-history",
    response_model=PriceHistoryBatchResponse,
    responses=standard_responses(
        success_description="Batch price-history summaries (one entry per requested part_id)",
    ),
)
async def post_batch_price_history(
    body: PriceHistoryBatchRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    caller: Optional[DBUser] = Depends(require_api_key_or_admin),
) -> PriceHistoryBatchResponse:
    """Aggregate min/max/last/trend per part for a batch of part IDs (1–100).

    POST (not GET) so the body can carry up to 100 UUIDs without hitting proxy
    URL-length limits. The endpoint never 404s on a per-id basis — unknown IDs
    return well-formed empty-summary entries so the client can iterate without
    holes. Invalid `window` values 422 with `error_code: INVALID_WINDOW`.

    Writers are machines, not end users: an `X-API-Key` matching the configured
    `EXTENSION_API_KEY` gets in (the Chrome extension and ingestion jobs), and so
    does an admin bearer token. A non-admin user token is 403; no credential at
    all is 401. `caller` is the admin user, or None on the API-key path.
    """
    logger = deps["logger"]

    try:
        parse_window(body.window)
    except ValueError:
        raise _invalid_window(body.window)

    started = time.perf_counter()
    summaries = aggregate_batch(body.part_ids, body.window)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    found_count = sum(1 for item in summaries.values() if item.observation_count > 0)
    rows_scanned = sum(item.observation_count for item in summaries.values())
    link_groups_resolved = len(summaries)

    logger.info(
        "price_history_aggregation: endpoint=batch part_count=%d "
        "window=%s link_groups_resolved=%d rows_scanned=%d elapsed_ms=%d",
        len(body.part_ids),
        body.window,
        link_groups_resolved,
        rows_scanned,
        elapsed_ms,
    )

    return PriceHistoryBatchResponse(
        summaries=summaries,
        window=body.window,
        requested_count=len(body.part_ids),
        found_count=found_count,
    )


@router.get(
    "/",
    response_model=CursorPage[PartRead],
    responses={200: {"description": "Part page retrieved successfully"}},
)
async def list_parts(
    params: CursorParams = Depends(get_cursor_params),
    search: Optional[str] = Query(None, description="Search in part names and descriptions"),
) -> CursorPage[PartRead]:
    """List canonical parts newest-first, optionally filtered by a search term."""
    return part_service.list_page_read(limit=params.limit, cursor=params.cursor, term=search)


base_router = BaseDynamoEndpointRouter(
    service=part_service,
    router=router,
    entity_name="part",
    read_schema=PartRead,
    update_schema=PartUpdate,
    allow_public_read=True,
    disable_endpoints=["create", "list", "delete"],
)


@router.delete(
    "/{part_id}",
    response_model=PartRead,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Part not found"},
    },
)
async def delete_part(
    part_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartRead:
    """Delete a part. Only the creator or an admin can delete it."""
    part = part_service.delete(part_id, current_user)
    purge_related_rows_for_parts([part.id])
    return PartRead.model_validate(part)


@router.get(
    "/user/{user_id}/count",
    response_model=dict,
    responses=standard_responses(success_description="Count of parts for user", not_found=True),
)
async def count_parts_by_user(user_id: UUID) -> Dict[str, int]:
    """Count parts created by a specific user."""
    return {"count": part_service.count_by_user(user_id)}
