"""
Build list parts endpoint on DynamoDB.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list_part import (
    BuildListPartCreate,
    BuildListPartRead,
    BuildListPartReadWithPart,
    BuildListPartUpdate,
    CreatePartAndAddToBuildListRequest,
)
from app.api.schemas.part import PartCreate, PartRead
from app.api.services.part_listing_service import (
    best_price_for_group,
    create_or_update_listing_and_price,
    find_part_by_gtin,
    find_part_by_part_manufacturer_and_part_number,
    find_part_by_product_url,
    get_best_listing_for_part,
    link_group_ids,
    normalize_gtin,
)
from app.api.services.part_service import PartService
from app.api.utils.authorization import (
    require_build_list_part_delete_permission,
    require_build_list_part_edit_permission,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.build_lists import BuildList, BuildListPart
from app.db.dynamo.catalog import Part
from app.db.dynamo.tombstones import drop_tombstoned_values, is_tombstoned
from app.db.dynamo.users import User as DBUser

router = APIRouter()
part_service = PartService()


def _require_part(repos: Repositories, part_id: UUID) -> Part:
    """Return the live part or raise 404."""
    part = repos.parts.get(str(part_id))
    if part is None or is_tombstoned(part):
        ResponsePatterns.raise_not_found("part", part_id)
    assert part is not None
    return part


def _require_build_list(repos: Repositories, build_list_id: UUID) -> BuildList:
    """Return the build list or raise 404."""
    build_list = repos.build_lists.get(build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_list_id)
    assert build_list is not None
    return build_list


def _require_build_list_part(repos: Repositories, build_list_part_id: UUID) -> BuildListPart:
    """Return the build list part or raise 404."""
    build_list_part = repos.build_list_parts.get(build_list_part_id)
    if build_list_part is None:
        ResponsePatterns.raise_not_found("build list part", build_list_part_id)
    assert build_list_part is not None
    return build_list_part


def _find_part_in_build_list(repos: Repositories, build_list_id: UUID, part_id: UUID) -> Optional[BuildListPart]:
    """Return the build list row holding that part, or None."""
    return next(
        (blp for blp in repos.build_list_parts.all_for_build_list(build_list_id) if blp.part_id == part_id),
        None,
    )


def _require_part_in_build_list(repos: Repositories, build_list_id: UUID, part_id: UUID) -> BuildListPart:
    """Return the build list row holding that part or raise 404."""
    build_list_part = _find_part_in_build_list(repos, build_list_id, part_id)
    if build_list_part is None:
        ResponsePatterns.raise_not_found("Build list part not found in build list")
    assert build_list_part is not None
    return build_list_part


def _part_read_with_best_price(part: Part) -> PartRead:
    """Read a part with its cheapest known listing price attached."""
    best = get_best_listing_for_part(part.id)
    part_dict = PartRead.model_validate(part).model_dump()
    part_dict["best_price_cents"] = best.last_known_price_cents if best else None
    return PartRead(**part_dict)


def _build_list_part_with_part(
    repos: Repositories, build_list_part: BuildListPart, part_read: PartRead
) -> BuildListPartReadWithPart:
    """Combine a build list row with its part and phase name."""
    phase_name = None
    if build_list_part.build_list_phase_id:
        phase = repos.build_list_phases.get(build_list_part.build_list_phase_id)
        phase_name = phase.name if phase else None
    return BuildListPartReadWithPart(
        id=build_list_part.id,
        build_list_id=build_list_part.build_list_id,
        part_id=build_list_part.part_id,
        added_by=build_list_part.added_by,
        quantity=build_list_part.quantity,
        notes=build_list_part.notes,
        purchased=build_list_part.purchased,
        added_at=build_list_part.added_at,
        build_list_phase_id=build_list_part.build_list_phase_id,
        phase_name=phase_name,
        part=part_read,
    )


def _validate_phase_belongs_to_build_list(repos: Repositories, phase_id: Optional[UUID], build_list_id: UUID) -> None:
    """If phase_id is set, verify the phase exists and belongs to the build list."""
    if phase_id is None:
        return
    phase = repos.build_list_phases.get(phase_id)
    if phase is None:
        ResponsePatterns.raise_not_found("build list phase", phase_id)
    assert phase is not None
    if phase.build_list_id != build_list_id:
        ResponsePatterns.raise_not_found("Build list phase does not belong to this build list")


def _add_part_to_build_list(
    repos: Repositories,
    build_list_id: UUID,
    part_id: UUID,
    current_user: DBUser,
    *,
    quantity: int,
    notes: Optional[str],
    build_list_phase_id: Optional[UUID],
) -> BuildListPart:
    """Attach a part to a build list, or bump the quantity if it is already there."""
    return repos.build_list_parts.create(
        BuildListPart(
            build_list_id=build_list_id,
            part_id=part_id,
            added_by=current_user.id,
            quantity=quantity,
            notes=notes,
            build_list_phase_id=build_list_phase_id,
        )
    )


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build list parts"),
)
async def count_build_list_parts(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Get total count of build list parts."""
    logger = deps["logger"]
    count = len(repos.build_list_parts.scan_all())
    logger.info(f"Retrieved build list parts count: {count}")
    return {"count": count}


@router.post(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def add_part_to_build_list(
    build_list_id: UUID,
    part_id: UUID,
    build_list_part: BuildListPartCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Add an existing part to a build list as a build list part."""
    logger = deps["logger"]

    build_list = _require_build_list(repos, build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    _require_part(repos, part_id)

    if _find_part_in_build_list(repos, build_list_id, part_id) is not None:
        ResponsePatterns.raise_conflict("Part already exists in build list")

    phase_id = getattr(build_list_part, "build_list_phase_id", None)
    _validate_phase_belongs_to_build_list(repos, phase_id, build_list_id)

    created = _add_part_to_build_list(
        repos,
        build_list_id,
        part_id,
        current_user,
        quantity=build_list_part.quantity,
        notes=build_list_part.notes,
        build_list_phase_id=phase_id,
    )

    logger.info(
        f"Part {part_id} added to build list {build_list_id} "
        f"as build list part {created.id} by user {current_user.id}"
    )
    return BuildListPartRead.model_validate(created)


@router.get(
    "/{build_list_id}",
    response_model=List[BuildListPartRead],
    responses=standard_responses(success_description="Build list parts retrieved successfully", not_found=True),
)
async def get_build_list_parts(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> List[BuildListPartRead]:
    """Get all build list parts in a build list. Public read access."""
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)
    build_list_parts = [
        BuildListPartRead.model_validate(part) for part in repos.build_list_parts.all_for_build_list(build_list_id)
    ]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part updated successfully", not_found=True, forbidden=True
    ),
)
async def update_build_list_part(
    build_list_part_id: UUID,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Update a build list part."""
    logger = deps["logger"]

    existing = _require_build_list_part(repos, build_list_part_id)
    build_list = _require_build_list(repos, existing.build_list_id)

    require_build_list_part_edit_permission(current_user, existing, build_list)

    update_data = build_list_part.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(repos, update_data["build_list_phase_id"], existing.build_list_id)
    updated = repos.build_list_parts.update(existing.id, **update_data) if update_data else existing

    logger.info(f"Build list part {updated.id} updated by user {current_user.id}")
    return BuildListPartRead.model_validate(updated)


@router.delete(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part deleted successfully", not_found=True, forbidden=True
    ),
)
async def delete_build_list_part(
    build_list_part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Delete a build list part."""
    logger = deps["logger"]

    existing = _require_build_list_part(repos, build_list_part_id)
    require_build_list_part_delete_permission(current_user, existing)

    deleted_data = BuildListPartRead.model_validate(existing)
    repos.build_list_parts.delete(existing.id)

    logger.info(f"Build list part {existing.id} deleted by user {current_user.id}")
    return deleted_data


@router.post(
    "/{build_list_id}/create-and-add-part",
    response_model=BuildListPartReadWithPart,
    responses=standard_responses(
        success_description="Part created and added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def create_part_and_add_to_build_list(
    build_list_id: UUID,
    request: CreatePartAndAddToBuildListRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartReadWithPart:
    """Create a new part and automatically add it to the specified build list."""
    logger = deps["logger"]

    build_list = _require_build_list(repos, build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    if repos.categories.get(str(request.category_id)) is None:
        ResponsePatterns.raise_not_found("category", request.category_id)

    phase_id = getattr(request, "build_list_phase_id", None)
    _validate_phase_belongs_to_build_list(repos, phase_id, build_list_id)

    part_by_url: Optional[Part] = None
    part_by_part_manufacturer: Optional[Part] = None
    part_by_gtin: Optional[Part] = None
    if request.product_url and request.product_url.strip():
        part_by_url = find_part_by_product_url(request.product_url)
    if request.part_manufacturer_id and request.part_number and request.part_number.strip():
        part_by_part_manufacturer = find_part_by_part_manufacturer_and_part_number(
            request.part_manufacturer_id, request.part_number
        )
    if request.gtin and normalize_gtin(request.gtin):
        part_by_gtin = find_part_by_gtin(request.gtin)

    parts = [p for p in (part_by_gtin, part_by_url, part_by_part_manufacturer) if p is not None]
    ids = {p.id for p in parts}
    if len(ids) > 1:
        ResponsePatterns.raise_conflict(
            message="Product URL, part manufacturer + part number, or GTIN point to different existing parts.",
            error_code="PART_DEDUP_CONFLICT",
            details={
                "gtin_part_id": part_by_gtin.id if part_by_gtin else None,
                "url_part_id": part_by_url.id if part_by_url else None,
                "part_manufacturer_part_id": part_by_part_manufacturer.id if part_by_part_manufacturer else None,
            },
        )

    wants_listing = bool(request.retailer_id and (request.product_url or request.price_cents is not None))
    if wants_listing and repos.retailers.get(str(request.retailer_id)) is None:
        ResponsePatterns.raise_not_found("retailer", request.retailer_id)

    existing_part = part_by_gtin or part_by_url or part_by_part_manufacturer
    if existing_part:
        if wants_listing:
            assert request.retailer_id is not None
            create_or_update_listing_and_price(
                existing_part.id,
                request.retailer_id,
                product_url=request.product_url,
                price_cents=request.price_cents,
            )
        created = _add_part_to_build_list(
            repos,
            build_list_id,
            existing_part.id,
            current_user,
            quantity=request.quantity,
            notes=request.notes,
            build_list_phase_id=phase_id,
        )
        existing_part = repos.parts.get(str(existing_part.id)) or existing_part
        logger.info(
            f"User {current_user.id} added existing part {existing_part.id} to build list "
            f"{build_list_id} as build list part {created.id} (dedup)"
        )
        return _build_list_part_with_part(repos, created, _part_read_with_best_price(existing_part))

    part_create = PartCreate(
        name=request.name,
        description=request.description,
        image_urls=request.image_urls,
        product_url=request.product_url,
        category_id=request.category_id,
        car_ids=request.car_ids,
        is_universal=request.is_universal,
        part_manufacturer_id=request.part_manufacturer_id,
        part_number=request.part_number,
        gtin=request.gtin,
        retailer_id=request.retailer_id,
        price_cents=request.price_cents,
    )
    db_part = part_service.create_part(part_create, current_user, logger)

    created = _add_part_to_build_list(
        repos,
        build_list_id,
        db_part.id,
        current_user,
        quantity=request.quantity,
        notes=request.notes,
        build_list_phase_id=phase_id,
    )

    logger.info(
        f"Part {db_part.id} created and added to build list "
        f"{build_list_id} as build list part {created.id} by user {current_user.id}"
    )
    return _build_list_part_with_part(repos, created, _part_read_with_best_price(db_part))


@router.get(
    "/{build_list_id}/parts",
    response_model=List[BuildListPartReadWithPart],
    responses=standard_responses(success_description="Parts in build list retrieved successfully", not_found=True),
)
async def get_parts_in_build_list(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> List[BuildListPartReadWithPart]:
    """Get all build list parts in a build list. Public read access."""
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)

    build_list_parts_raw = repos.build_list_parts.all_for_build_list(build_list_id)
    phases = {phase.id: phase for phase in repos.build_list_phases.all_for_build_list(build_list_id)}

    stored_parts = drop_tombstoned_values(repos.parts.get_many({p.part_id for p in build_list_parts_raw}))
    canonical_ids_to_load = {
        part.canonical_part_id for part in stored_parts.values() if part.canonical_part_id is not None
    }
    canonicals: Dict[UUID, Part] = (
        drop_tombstoned_values(repos.parts.get_many(canonical_ids_to_load)) if canonical_ids_to_load else {}
    )

    def effective_part(stored: Part) -> Part:
        """Return the canonical part a stored row points at, or the row itself."""
        if stored.canonical_part_id and stored.canonical_part_id in canonicals:
            return canonicals[stored.canonical_part_id]
        return stored

    best_price_cents_dict: Dict[UUID, Optional[int]] = {}

    def part_read_with_best_price(part: Part) -> PartRead:
        """Read a part with the cheapest price across its link group attached."""
        if part.id not in best_price_cents_dict:
            best_price_cents_dict[part.id] = best_price_for_group(link_group_ids(part))
        part_dict = PartRead.model_validate(part).model_dump()
        part_dict["best_price_cents"] = best_price_cents_dict[part.id]
        return PartRead(**part_dict)

    def phase_name(part: BuildListPart) -> Optional[str]:
        """Return the name of the phase a build list part sits in, if any."""
        phase = phases.get(part.build_list_phase_id) if part.build_list_phase_id else None
        return phase.name if phase else None

    build_list_parts = [
        BuildListPartReadWithPart(
            id=part.id,
            build_list_id=part.build_list_id,
            part_id=part.part_id,
            added_by=part.added_by,
            quantity=part.quantity,
            notes=part.notes,
            purchased=part.purchased,
            added_at=part.added_at,
            build_list_phase_id=part.build_list_phase_id,
            phase_name=phase_name(part),
            part=part_read_with_best_price(effective_part(stored_parts[part.part_id])),
        )
        for part in build_list_parts_raw
        if part.part_id in stored_parts
    ]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part in build list updated successfully", not_found=True, forbidden=True
    ),
)
async def update_part_in_build_list(
    build_list_id: UUID,
    part_id: UUID,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Update a build list part's notes in a build list."""
    logger = deps["logger"]

    build_list = _require_build_list(repos, build_list_id)
    existing = _require_part_in_build_list(repos, build_list_id, part_id)

    require_build_list_part_edit_permission(current_user, existing, build_list)

    update_data = build_list_part.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(repos, update_data["build_list_phase_id"], build_list_id)
    updated = repos.build_list_parts.update(existing.id, **update_data) if update_data else existing

    logger.info(f"Build list part {updated.id} updated in build list {build_list_id} by user {current_user.id}")
    return BuildListPartRead.model_validate(updated)


@router.delete(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part removed from build list successfully", not_found=True, forbidden=True
    ),
)
async def remove_part_from_build_list(
    build_list_id: UUID,
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Remove a build list part from a build list."""
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)
    existing = _require_part_in_build_list(repos, build_list_id, part_id)

    require_build_list_part_delete_permission(current_user, existing)

    deleted_data = BuildListPartRead.model_validate(existing)
    repos.build_list_parts.delete(existing.id)

    logger.info(f"Build list part {existing.id} removed from build list {build_list_id} by user {current_user.id}")
    return deleted_data


@router.get(
    "/parts/{part_id}/build-lists/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build lists containing the part", not_found=True),
)
async def count_build_lists_containing_part(
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Count the number of build lists that contain a specific part."""
    logger = deps["logger"]

    _require_part(repos, part_id)

    usages: List[Any] = repos.build_list_parts.query_all("part_id-index", part_id)
    count = len({usage.build_list_id for usage in usages})

    logger.info(f"Part {part_id} is contained in {count} build list(s)")
    return {"count": count}
