"""Build lists endpoint on DynamoDB.

Build lists and their children are DynamoDB tables. Votes and build logs are
still SQL rows, which is why the vote-aware listing and the create/copy paths
"""

import logging
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list import (
    MAX_IMAGES_PER_BUILDLIST,
    BuildListAppendImages,
    BuildListCreate,
    BuildListRead,
    BuildListReadWithVotes,
    BuildListSetPrimaryImageRequest,
    BuildListUpdate,
)
from app.api.schemas.build_list_labor_estimate import (
    BuildListLaborEstimateCreate,
    BuildListLaborEstimateRead,
)
from app.api.schemas.build_list_phase import BuildListPhaseCreate, BuildListPhaseRead
from app.api.services.build_list_service import BuildListService
from app.api.utils.base_dynamo_endpoint_router import BaseDynamoEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    standard_responses,
)
from app.api.utils.pagination_utils import create_paginated_response
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo import search
from app.db.dynamo.build_lists import BuildList, BuildListLaborEstimate, BuildListPhase
from app.db.dynamo.tombstones import drop_tombstoned_values
from app.db.dynamo.users import User as DBUser

router = APIRouter()

build_list_service = BuildListService()


def _require_build_list(repos: Repositories, build_list_id: UUID) -> BuildList:
    """Return the build list or raise 404."""
    build_list = repos.build_lists.get(build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_list_id)
    assert build_list is not None
    return build_list


def _matches_search(term: str, build_list: BuildList) -> bool:
    """Report whether the term appears in the build list name or description."""
    return search.contains(term, build_list.name, build_list.description)


def _next_sort_order(existing: List[Any]) -> int:
    """Next sort_order: max + 1, or 0 for the first child."""
    if not existing:
        return 0
    return max(item.sort_order for item in existing) + 1


def _log_user(current_user: Optional[DBUser]) -> str:
    """Render the caller for a log line, naming anonymous callers as such."""
    return f"User {current_user.id}" if current_user else "Anonymous user"


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={200: {"description": "Build list count retrieved successfully"}},
)
async def count_build_lists(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    """Get total count of build lists."""
    return {"count": repos.build_lists.count()}


@router.get(
    "/with-votes",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_with_votes(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    search_term: Optional[str] = Query(None, alias="search", description="Search in build list names and descriptions"),
    car_id: Optional[UUID] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[UUID]] = Query(
        None, description="Filter by car IDs (e.g. all generations for a make or model)"
    ),
    owner_id: Optional[UUID] = Query(None, description="Filter by owner (user) ID"),
    min_cost_cents: Optional[int] = Query(None, ge=0, description="Minimum total build list cost (cents)"),
    max_cost_cents: Optional[int] = Query(None, ge=0, description="Maximum total build list cost (cents)"),
    sort: Optional[str] = Query(
        None,
        description="Sort order: votes (default), votes_asc, price_asc, price_desc",
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """Get all build lists with vote data and optional filtering and search."""
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    term = search.normalize_term(search_term)
    car_filter = set(car_ids) if car_ids else ({car_id} if car_id is not None else None)
    candidates = [
        bl
        for bl in repos.build_lists.scan_all()
        if (not term or _matches_search(term, bl))
        and (car_filter is None or bl.car_id in car_filter)
        and (owner_id is None or bl.user_id == owner_id)
    ]

    candidate_ids = {bl.id for bl in candidates}
    parts_by_list: Dict[UUID, List[Any]] = {}
    for part in repos.build_list_parts.scan_all():
        if part.build_list_id in candidate_ids:
            parts_by_list.setdefault(part.build_list_id, []).append(part)
    prices = {
        part_id: part.best_price_cents
        for part_id, part in drop_tombstoned_values(
            repos.parts.get_many({p.part_id for ps in parts_by_list.values() for p in ps})
        ).items()
    }
    parts_cost: Dict[UUID, Optional[int]] = {
        list_id: sum(part.quantity * (prices.get(part.part_id) or 0) for part in parts)
        for list_id, parts in parts_by_list.items()
    }
    labor_cost: Dict[UUID, Optional[int]] = {}
    for estimate in repos.build_list_labor_estimates.scan_all():
        if estimate.build_list_id in candidate_ids:
            labor_cost[estimate.build_list_id] = (labor_cost.get(estimate.build_list_id) or 0) + estimate.cost_cents

    def total_cost(bl: BuildList) -> int:
        """Return the base price plus parts and labor cost for a build list."""
        return (bl.base_price_cents or 0) + (parts_cost.get(bl.id) or 0) + (labor_cost.get(bl.id) or 0)

    if min_cost_cents is not None:
        candidates = [bl for bl in candidates if total_cost(bl) >= min_cost_cents]
    if max_cost_cents is not None:
        candidates = [bl for bl in candidates if total_cost(bl) <= max_cost_cents]
    total = len(candidates)

    upvotes: Dict[UUID, int] = {}
    downvotes: Dict[UUID, int] = {}
    if candidates:
        upvotes, downvotes = repos.votes.tallies("build_list", [bl.id for bl in candidates])

    def net_votes(bl: BuildList) -> int:
        """Return upvotes minus downvotes for a build list."""
        return upvotes.get(bl.id, 0) - downvotes.get(bl.id, 0)

    if sort == "price_asc":
        candidates.sort(key=lambda bl: (total_cost(bl), str(bl.id)))
    elif sort == "price_desc":
        candidates.sort(key=lambda bl: (total_cost(bl), str(bl.id)), reverse=True)
    elif sort == "votes_asc":
        candidates.sort(key=lambda bl: (net_votes(bl), str(bl.id)))
    else:
        candidates.sort(key=lambda bl: (net_votes(bl), str(bl.id)), reverse=True)

    build_lists = candidates[skip : skip + limit]
    logger.info(f"Retrieved {len(build_lists)} build lists (skip: {skip}, limit: {limit})")

    if not build_lists:
        return create_paginated_response(data=[], total=total, skip=skip, limit=limit, entity_name="build lists")

    user_votes: Dict[UUID, str] = {}
    if current_user:
        user_votes = repos.votes.user_votes("build_list", [bl.id for bl in build_lists], current_user.id)

    build_lists_data: List[BuildListReadWithVotes] = []
    for build_list in build_lists:
        build_list_dict = BuildListRead.model_validate(build_list).model_dump()
        build_list_dict["upvotes"] = upvotes.get(build_list.id, 0)
        build_list_dict["downvotes"] = downvotes.get(build_list.id, 0)
        build_list_dict["total_votes"] = build_list_dict["upvotes"] + build_list_dict["downvotes"]
        build_list_dict["user_vote"] = user_votes.get(build_list.id)
        build_list_dict["total_cost_cents"] = total_cost(build_list)
        build_list_dict["total_parts_cost_cents"] = parts_cost.get(build_list.id)
        build_list_dict["total_labor_cost_cents"] = labor_cost.get(build_list.id)
        build_lists_data.append(BuildListReadWithVotes(**build_list_dict))

    return create_paginated_response(
        data=cast(List[Any], build_lists_data), total=total, skip=skip, limit=limit, entity_name="build lists"
    )


@router.post(
    "",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Build list created successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def create_build_list(
    data: BuildListCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListRead:
    """Create a build list. Free accounts are capped at one."""
    build_list = build_list_service.create(data, current_user, logger=deps["logger"])
    return BuildListRead.model_validate(build_list)


@router.get(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        200: {"description": "Build list retrieved successfully"},
        404: {"description": "Build list not found"},
    },
)
async def read_build_list(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListRead:
    """
    Retrieve a build list by ID.
    Public read access - anyone can view build lists.
    Only owners can edit or delete.
    """
    logger = deps["logger"]
    build_list = _require_build_list(repos, build_list_id)
    logger.info(f"{_log_user(current_user)} retrieved build list {build_list_id}")
    return BuildListRead.model_validate(build_list)


@router.get(
    "/{build_list_id}/phases",
    response_model=List[BuildListPhaseRead],
    responses=standard_responses(
        success_description="Build list phases retrieved successfully",
        not_found=True,
    ),
)
async def list_build_list_phases(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> List[BuildListPhaseRead]:
    """List phases for a build list. Public read access."""
    logger = deps["logger"]
    _require_build_list(repos, build_list_id)
    phases = repos.build_list_phases.ordered_for_build_list(build_list_id)
    logger.info(f"{_log_user(current_user)}: Retrieved {len(phases)} phases for build list {build_list_id}")
    return [BuildListPhaseRead.model_validate(p) for p in phases]


@router.post(
    "/{build_list_id}/phases",
    response_model=BuildListPhaseRead,
    responses=standard_responses(
        success_description="Build list phase created successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def create_build_list_phase(
    build_list_id: UUID,
    body: BuildListPhaseCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPhaseRead:
    """Create a phase for a build list. Only build list owner or admin."""
    logger = deps["logger"]

    build_list = _require_build_list(repos, build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    existing = repos.build_list_phases.all_for_build_list(build_list_id)
    phase = repos.build_list_phases.create(
        BuildListPhase(
            build_list_id=build_list_id,
            name=body.name,
            sort_order=body.sort_order if body.sort_order != 0 else _next_sort_order(existing),
        )
    )

    logger.info(f"User {current_user.id} created phase {phase.id} for build list {build_list_id}")
    return BuildListPhaseRead.model_validate(phase)


@router.get(
    "/{build_list_id}/labor-estimates",
    response_model=List[BuildListLaborEstimateRead],
    responses=standard_responses(
        success_description="Build list labor estimates retrieved successfully",
        not_found=True,
    ),
)
async def list_build_list_labor_estimates(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> List[BuildListLaborEstimateRead]:
    """List labor estimates for a build list. Public read access."""
    logger = deps["logger"]
    _require_build_list(repos, build_list_id)
    estimates = repos.build_list_labor_estimates.ordered_for_build_list(build_list_id)
    logger.info(f"{_log_user(current_user)}: Retrieved {len(estimates)} labor estimates for build list {build_list_id}")
    return [BuildListLaborEstimateRead.model_validate(e) for e in estimates]


@router.post(
    "/{build_list_id}/labor-estimates",
    response_model=BuildListLaborEstimateRead,
    responses=standard_responses(
        success_description="Build list labor estimate created successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def create_build_list_labor_estimate(
    build_list_id: UUID,
    body: BuildListLaborEstimateCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListLaborEstimateRead:
    """Create a labor estimate for a build list. Only build list owner or admin."""
    logger = deps["logger"]

    build_list = _require_build_list(repos, build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    if body.build_list_phase_id is not None:
        phase = repos.build_list_phases.get(body.build_list_phase_id)
        if phase is None or phase.build_list_id != build_list_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phase does not belong to this build list",
            )

    existing = repos.build_list_labor_estimates.all_for_build_list(build_list_id)
    estimate = repos.build_list_labor_estimates.create(
        BuildListLaborEstimate(
            build_list_id=build_list_id,
            build_list_phase_id=body.build_list_phase_id,
            name=body.name,
            description=body.description,
            cost_cents=body.cost_cents,
            sort_order=body.sort_order if body.sort_order != 0 else _next_sort_order(existing),
        )
    )

    logger.info(f"User {current_user.id} created labor estimate {estimate.id} for build list {build_list_id}")
    return BuildListLaborEstimateRead.model_validate(estimate)


@router.get(
    "/car/{car_id}",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_by_car(
    car_id: UUID,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    search_term: Optional[str] = Query(None, alias="search", description="Search in build list names and descriptions"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """
    Retrieve all build lists associated with a specific car with pagination.
    Public read access - anyone can view build lists for any car.
    """
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    if repos.car_generations.get(str(car_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")

    term = search.normalize_term(search_term)
    matching = [
        bl
        for bl in repos.build_lists.query_all("car_id-created_at-index", car_id)
        if not term or _matches_search(term, bl)
    ]
    build_lists = matching[skip : skip + limit]

    user_info = _log_user(current_user)
    if not build_lists:
        logger.info(f"{user_info}: No Build Lists found for car with id {car_id}")
    else:
        logger.info(msg=f"{user_info}: Build Lists retrieved for car {car_id}: {[bl.id for bl in build_lists]}")

    build_lists_data = [BuildListRead.model_validate(build_list) for build_list in build_lists]
    return create_paginated_response(
        data=build_lists_data, total=len(matching), skip=skip, limit=limit, entity_name="build lists"
    )


@router.get(
    "/user/me",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=False),
)
async def read_my_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """
    Retrieve all build lists owned by the current user with pagination.
    """
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    owned = repos.build_lists.query_all("user_id-created_at-index", current_user.id)
    build_lists = owned[skip : skip + limit]
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {current_user.id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {current_user.id}: {[bl.id for bl in build_lists]}")

    build_lists_data = [BuildListRead.model_validate(build_list) for build_list in build_lists]
    return create_paginated_response(
        data=build_lists_data, total=len(owned), skip=skip, limit=limit, entity_name="build lists"
    )


@router.get(
    "/user/{user_id}",
    response_model=List[BuildListRead],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_by_user(
    user_id: UUID,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[BuildListRead]:
    """
    Retrieve all build lists owned by a specific user.
    Public endpoint - build lists are discoverable via search and catalog, so listing by user is allowed for profile pages.
    """
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    build_lists = build_list_service.get_build_lists_by_user(user_id, skip=skip, limit=limit)
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {user_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {user_id}: {[bl.id for bl in build_lists]}")
    return [BuildListRead.model_validate(build_list) for build_list in build_lists]


class CopyBuildListRequest(BaseModel):
    """Request model for copying a build list."""

    new_name: Optional[str] = None


@router.post(
    "/{build_list_id}/copy",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Build list copied successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def copy_build_list(
    build_list_id: UUID,
    request: CopyBuildListRequest = Body(default=CopyBuildListRequest()),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListRead:
    """
    Copy a build list and all its parts.
    Creates a new build list owned by the current user with all parts from the original.
    All authenticated users can copy any build list.
    """
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)

    new_build_list = build_list_service.copy_build_list(
        build_list_id=build_list_id,
        current_user=current_user,
        logger=logger,
        new_name=request.new_name,
    )

    logger.info(f"User {current_user.id} copied build list {build_list_id} to {new_build_list.id}")
    return BuildListRead.model_validate(new_build_list)


def _get_build_list_image_file_keys(build_list: BuildList) -> List[str]:
    """Return ordered list of image file keys. First entry is the primary/display image."""
    return list(build_list.image_urls or [])


def _require_owned_build_list(
    repos: Repositories, build_list_id: UUID, current_user: DBUser, logger: logging.Logger
) -> BuildList:
    """Return the build list once the caller is allowed to modify it."""
    build_list = _require_build_list(repos, build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)
    return build_list


@router.post(
    "/{build_list_id}/append-images",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Images appended to build list",
        not_found=True,
        forbidden=True,
    ),
)
async def append_images_to_build_list(
    build_list_id: UUID,
    data: BuildListAppendImages,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListRead:
    """Append image file keys to a build list's gallery."""
    build_list = _require_owned_build_list(repos, build_list_id, current_user, deps["logger"])

    existing = list(build_list.image_urls or [])
    if len(existing) >= MAX_IMAGES_PER_BUILDLIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Build list already has the maximum number of images ({MAX_IMAGES_PER_BUILDLIST}).",
        )

    seen = set(existing)
    for fk in data.file_keys:
        if fk and fk not in seen and len(existing) < MAX_IMAGES_PER_BUILDLIST:
            existing.append(fk)
            seen.add(fk)

    updated = repos.build_lists.update(build_list.id, image_urls=existing[:MAX_IMAGES_PER_BUILDLIST])
    return BuildListRead.model_validate(updated)


@router.delete(
    "/{build_list_id}/images/{image_index}",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Image removed from build list",
        not_found=True,
        forbidden=True,
    ),
)
async def remove_image_from_build_list(
    build_list_id: UUID,
    image_index: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListRead:
    """Remove the image at the given index from the build list's gallery."""
    from app.api.services.storage_service import storage_service
    from app.api.utils.image_utils import is_file_key

    build_list = _require_owned_build_list(repos, build_list_id, current_user, deps["logger"])

    file_keys = _get_build_list_image_file_keys(build_list)
    if image_index < 0 or image_index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {image_index}. Build list has {len(file_keys)} image(s).",
        )

    removed_key = file_keys[image_index]
    new_keys = [fk for i, fk in enumerate(file_keys) if i != image_index]

    updated = repos.build_lists.update(build_list.id, image_urls=new_keys if new_keys else None)

    if removed_key and is_file_key(removed_key):
        try:
            storage_service.delete_image(removed_key)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to delete image from storage for build list %s: %s",
                build_list_id,
                e,
            )

    return BuildListRead.model_validate(updated)


@router.patch(
    "/{build_list_id}/primary-image",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Primary image updated",
        not_found=True,
        forbidden=True,
    ),
)
async def set_primary_image_for_build_list(
    build_list_id: UUID,
    data: BuildListSetPrimaryImageRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListRead:
    """Set the image at the given index as the primary (display) image."""
    build_list = _require_owned_build_list(repos, build_list_id, current_user, deps["logger"])

    file_keys = _get_build_list_image_file_keys(build_list)
    if data.index < 0 or data.index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {data.index}. Build list has {len(file_keys)} image(s).",
        )

    primary_key = file_keys[data.index]
    new_order = [primary_key] + [fk for i, fk in enumerate(file_keys) if i != data.index]
    updated = repos.build_lists.update(build_list.id, image_urls=new_order)
    return BuildListRead.model_validate(updated)


base_router = BaseDynamoEndpointRouter(
    build_list_service,
    router,
    entity_name="build list",
    read_schema=BuildListRead,
    update_schema=BuildListUpdate,
    allow_public_read=False,
    disable_endpoints=["count", "create", "get"],
)
