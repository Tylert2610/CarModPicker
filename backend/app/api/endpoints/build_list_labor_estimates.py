"""
Build list labor estimates endpoint on DynamoDB.

Estimates are created and listed under /build-lists/{id}/labor-estimates;
this router owns the per-estimate update and delete routes.
"""

from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list_labor_estimate import (
    BuildListLaborEstimateRead,
    BuildListLaborEstimateUpdate,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.build_lists import BuildList, BuildListLaborEstimate
from app.db.dynamo.users import User as DBUser

router = APIRouter()


def _require_estimate(repos: Repositories, labor_estimate_id: UUID) -> BuildListLaborEstimate:
    """Return the labor estimate or raise 404."""
    estimate = repos.build_list_labor_estimates.get(labor_estimate_id)
    if estimate is None:
        ResponsePatterns.raise_not_found("build list labor estimate", labor_estimate_id)
    assert estimate is not None
    return estimate


def _require_build_list(repos: Repositories, build_list_id: UUID) -> BuildList:
    """Return the build list or raise 404."""
    build_list = repos.build_lists.get(build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_list_id)
    assert build_list is not None
    return build_list


def _validate_phase_belongs_to_build_list(repos: Repositories, phase_id: Optional[UUID], build_list_id: UUID) -> None:
    """Reject a phase id that does not belong to the given build list."""
    if phase_id is None:
        return
    phase = repos.build_list_phases.get(phase_id)
    if phase is None or phase.build_list_id != build_list_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phase does not belong to this build list",
        )


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build list labor estimates"),
)
async def count_build_list_labor_estimates(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    """Get total count of build list labor estimates."""
    return {"count": len(repos.build_list_labor_estimates.scan_all())}


@router.put(
    "/{labor_estimate_id}",
    response_model=BuildListLaborEstimateRead,
    responses=standard_responses(
        success_description="Build list labor estimate updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_labor_estimate(
    labor_estimate_id: UUID,
    body: BuildListLaborEstimateUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListLaborEstimateRead:
    """Update a labor estimate. Only build list owner or admin."""
    logger = deps["logger"]

    estimate = _require_estimate(repos, labor_estimate_id)
    build_list = _require_build_list(repos, estimate.build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    update_data = body.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(repos, update_data["build_list_phase_id"], estimate.build_list_id)
    updated = repos.build_list_labor_estimates.update(estimate.id, **update_data) if update_data else estimate

    logger.info(f"User {current_user.id} updated labor estimate {labor_estimate_id}")
    return BuildListLaborEstimateRead.model_validate(updated)


@router.delete(
    "/{labor_estimate_id}",
    response_model=BuildListLaborEstimateRead,
    responses=standard_responses(
        success_description="Build list labor estimate deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_labor_estimate(
    labor_estimate_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListLaborEstimateRead:
    """Delete a labor estimate. Only build list owner or admin."""
    logger = deps["logger"]

    estimate = _require_estimate(repos, labor_estimate_id)
    build_list = _require_build_list(repos, estimate.build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    deleted_data = BuildListLaborEstimateRead.model_validate(estimate)
    repos.build_list_labor_estimates.delete(estimate.id)

    logger.info(f"User {current_user.id} deleted labor estimate {labor_estimate_id}")
    return deleted_data
