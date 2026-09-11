"""
Build list phases endpoint on DynamoDB.

Phases are created and listed under /build-lists/{id}/phases; this router
owns the per-phase update and delete routes.
"""

from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list_phase import BuildListPhaseRead, BuildListPhaseUpdate
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.build_lists import BuildList, BuildListPhase
from app.db.dynamo.repository import transact_write
from app.db.dynamo.users import User as DBUser

router = APIRouter()


def _require_phase(repos: Repositories, phase_id: UUID) -> BuildListPhase:
    """Return the build list phase or raise 404."""
    phase = repos.build_list_phases.get(phase_id)
    if phase is None:
        ResponsePatterns.raise_not_found("build list phase", phase_id)
    assert phase is not None
    return phase


def _require_build_list(repos: Repositories, build_list_id: UUID) -> BuildList:
    """Return the build list or raise 404."""
    build_list = repos.build_lists.get(build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_list_id)
    assert build_list is not None
    return build_list


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build list phases"),
)
async def count_build_list_phases(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    """Get total count of build list phases."""
    return {"count": len(repos.build_list_phases.scan_all())}


@router.put(
    "/{phase_id}",
    response_model=BuildListPhaseRead,
    responses=standard_responses(
        success_description="Build list phase updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_phase(
    phase_id: UUID,
    body: BuildListPhaseUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPhaseRead:
    """Update a phase. Only build list owner or admin."""
    logger = deps["logger"]

    phase = _require_phase(repos, phase_id)
    build_list = _require_build_list(repos, phase.build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    update_data = body.model_dump(exclude_unset=True)
    updated = repos.build_list_phases.update(phase.id, **update_data) if update_data else phase

    logger.info(f"User {current_user.id} updated phase {phase_id}")
    return BuildListPhaseRead.model_validate(updated)


@router.delete(
    "/{phase_id}",
    response_model=BuildListPhaseRead,
    responses=standard_responses(
        success_description="Build list phase deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_phase(
    phase_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPhaseRead:
    """Delete a phase. Parts and labor estimates in it become ungrouped. Only build list owner or admin."""
    logger = deps["logger"]

    phase = _require_phase(repos, phase_id)
    build_list = _require_build_list(repos, phase.build_list_id)
    verify_user_access_or_admin(current_user, build_list.user_id, "modify this build list", logger)

    deleted_data = BuildListPhaseRead.model_validate(phase)

    detach_actions = [
        *repos.build_list_parts.clear_phase(phase.id, phase.build_list_id),
        *repos.build_list_labor_estimates.clear_phase(phase.id, phase.build_list_id),
    ]
    for start in range(0, len(detach_actions), 100):
        transact_write(detach_actions[start : start + 100])
    repos.build_list_phases.delete(phase.id)

    logger.info(f"User {current_user.id} deleted phase {phase_id}")
    return deleted_data
