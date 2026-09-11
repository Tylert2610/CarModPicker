"""
Part manufacturers endpoint.

There is a single global manufacturer namespace, unique by case-insensitive
name. Manufacturers are created by the Chrome extension, the seed script,
admins, or regular users while making a Part; ``get_or_create`` dedupes by
name (and canonical key) so the same brand isn't minted twice.

Edit/delete authorization is admin/superuser only. A manufacturer cannot be
deleted while any Part still references it.
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.pagination import CursorPage
from app.api.schemas.part import PartRead
from app.api.schemas.part_manufacturer import (
    PartManufacturerAdminUpdate,
    PartManufacturerCreate,
    PartManufacturerResponse,
)
from app.api.services.part_listing_service import (
    get_or_create_part_manufacturer_by_name,
)
from app.api.utils.authorization import (
    require_part_manufacturer_delete_permission,
    require_part_manufacturer_edit_permission,
)
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params, page_from_repository
from app.api.utils.endpoint_decorators import (
    crud_responses,
    pagination_responses,
    search_responses,
    standard_responses,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo import search
from app.db.dynamo.catalog import PartManufacturer
from app.db.dynamo.users import UniqueAttributeTaken
from app.db.dynamo.users import User as DBUser

router = APIRouter()


def _get_part_manufacturer_or_404(repos: Repositories, part_manufacturer_id: UUID) -> PartManufacturer:
    pm = repos.part_manufacturers.get(str(part_manufacturer_id))
    if pm is None:
        ResponsePatterns.raise_not_found("Part Manufacturer")
    assert pm is not None
    return pm


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={200: {"description": "Part manufacturer count retrieved successfully"}},
)
async def count_part_manufacturers(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    return {"count": repos.part_manufacturers.count()}


@router.get("", response_model=List[PartManufacturerResponse])
async def get_part_manufacturers(
    active_only: bool = Query(True, description="Only return active part manufacturers"),
    repos: Repositories = Depends(get_repositories),
) -> List[PartManufacturerResponse]:
    """List part manufacturers."""
    manufacturers = repos.part_manufacturers.list_sorted(active_only=active_only)
    return [PartManufacturerResponse.model_validate(pm) for pm in manufacturers]


@router.get(
    "/search",
    response_model=CursorPage[PartManufacturerResponse],
    responses=search_responses("part manufacturer", allow_public_read=True),
)
async def search_part_manufacturers(
    q: str = Query(..., description="Search term for part manufacturer name or description"),
    params: CursorParams = Depends(get_cursor_params),
    repos: Repositories = Depends(get_repositories),
) -> CursorPage[PartManufacturerResponse]:
    """Search part manufacturers by name or description."""
    term = search.normalize_term(q)
    matches = search.scan_matching(repos.part_manufacturers, lambda pm: search.contains(term, pm.name, pm.description))
    return search.paginate(
        matches,
        limit=params.limit,
        cursor=params.cursor,
        sort_key=lambda pm: search.text_key(pm.name),
        transform=PartManufacturerResponse.model_validate,
    )


@router.get("/{part_manufacturer_id}", response_model=PartManufacturerResponse)
async def get_part_manufacturer(
    part_manufacturer_id: UUID,
    repos: Repositories = Depends(get_repositories),
) -> PartManufacturerResponse:
    """Get a manufacturer by id."""
    return PartManufacturerResponse.model_validate(_get_part_manufacturer_or_404(repos, part_manufacturer_id))


@router.get(
    "/{part_manufacturer_id}/parts",
    response_model=CursorPage[PartRead],
    responses=pagination_responses("part", allow_public_read=True),
)
async def get_parts_by_part_manufacturer(
    part_manufacturer_id: UUID,
    params: CursorParams = Depends(get_cursor_params),
    repos: Repositories = Depends(get_repositories),
) -> CursorPage[PartRead]:
    """All parts that reference this manufacturer."""
    _get_part_manufacturer_or_404(repos, part_manufacturer_id)
    page = repos.parts.page_by_manufacturer(part_manufacturer_id, limit=params.limit, cursor=params.cursor)
    return page_from_repository(page, PartRead.model_validate)


@router.post(
    "",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "create"),
)
async def create_part_manufacturer(
    part_manufacturer: PartManufacturerCreate,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartManufacturerResponse:
    """Create a manufacturer.

    Dedupes by case-insensitive name (and canonical key) so the same brand
    isn't minted twice — an existing match is returned instead.
    """
    name = part_manufacturer.name.strip() if part_manufacturer.name else ""
    if not name:
        ResponsePatterns.raise_bad_request("Part manufacturer name is required", "PART_MANUFACTURER_NAME_REQUIRED")

    pm = get_or_create_part_manufacturer_by_name(name)

    if pm is None:
        ResponsePatterns.raise_bad_request("Part manufacturer name is required", "PART_MANUFACTURER_NAME_REQUIRED")
    assert pm is not None

    if part_manufacturer.description and not pm.description:
        pm = repos.part_manufacturers.update_unique(pm, description=part_manufacturer.description)
    return PartManufacturerResponse.model_validate(pm)


@router.put(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "update"),
)
async def update_part_manufacturer(
    part_manufacturer_id: UUID,
    part_manufacturer: PartManufacturerAdminUpdate,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartManufacturerResponse:
    """Update a manufacturer (admin/superuser only)."""
    db_pm = _get_part_manufacturer_or_404(repos, part_manufacturer_id)
    require_part_manufacturer_edit_permission(current_user, db_pm)

    update_data = part_manufacturer.model_dump(exclude_unset=True)

    new_name = update_data.get("name")
    if new_name and new_name != db_pm.name:
        conflict = repos.part_manufacturers.get_by_name(new_name)
        if conflict is not None and conflict.id != db_pm.id:
            ResponsePatterns.raise_conflict(
                "Part manufacturer with this name already exists", "PART_MANUFACTURER_EXISTS"
            )

    try:
        updated = repos.part_manufacturers.update_unique(db_pm, **update_data)
    except UniqueAttributeTaken:
        ResponsePatterns.raise_conflict("Part manufacturer with this name already exists", "PART_MANUFACTURER_EXISTS")
        raise
    return PartManufacturerResponse.model_validate(updated)


@router.delete(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "delete"),
)
async def delete_part_manufacturer(
    part_manufacturer_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> PartManufacturerResponse:
    """Delete a manufacturer (admin/superuser only).

    Cannot delete if any Part still references it.
    """
    db_pm = _get_part_manufacturer_or_404(repos, part_manufacturer_id)
    require_part_manufacturer_delete_permission(current_user, db_pm)

    parts_count = repos.parts.count_by_manufacturer(part_manufacturer_id)
    if parts_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete part manufacturer that has {parts_count} associated parts",
            "PART_MANUFACTURER_IN_USE",
        )

    pm_response = PartManufacturerResponse.model_validate(db_pm)
    repos.part_manufacturers.delete_unique(db_pm)
    return pm_response


@router.get(
    "/{part_manufacturer_id}/parts-count",
    responses=standard_responses(
        success_description="Part manufacturer parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_part_manufacturer_parts_count(
    part_manufacturer_id: UUID,
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Count of parts referencing this manufacturer (no UGC/curated filter)."""
    _get_part_manufacturer_or_404(repos, part_manufacturer_id)
    return {"parts_count": repos.parts.count_by_manufacturer(part_manufacturer_id)}


@router.get(
    "/counts/by-source",
    responses=standard_responses(success_description="Total part manufacturer count"),
)
async def get_part_manufacturer_counts_by_source(
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Total manufacturer count for the admin dashboard."""
    return {"total": repos.part_manufacturers.count()}
