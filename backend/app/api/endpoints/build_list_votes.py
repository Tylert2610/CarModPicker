"""
Refactored build list votes endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseVoteRouter to provide common voting operations
while maintaining build list-specific functionality.
"""

import logging
from typing import List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_vote import BuildListVote as DBBuildListVote
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_vote import (
    BuildListVoteCreate,
    BuildListVoteRead,
    BuildListVoteSummary,
    FlaggedBuildListSummary,
)
from app.api.services.build_list_vote_service import BuildListVoteService
from app.api.utils.base_vote_router import BaseVoteRouter
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.common_patterns import get_standard_public_endpoint_dependencies
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
build_list_vote_service = BuildListVoteService()

# Create base vote router
base_vote_router = BaseVoteRouter(
    service=build_list_vote_service,
    router=router,
    entity_name="build list",
    vote_entity_id_param="build_list_id",
)


# Add custom build list-specific endpoints
@router.get(
    "/{build_list_id}/vote-summary",
    response_model=BuildListVoteSummary,
    responses=standard_responses(
        success_description="Vote summary for build list retrieved successfully",
        not_found=True,
    ),
)
async def get_build_list_vote_summary(
    build_list_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> BuildListVoteSummary:
    """Get vote summary for a build list."""
    db = deps["db"]
    logger = deps["logger"]

    return build_list_vote_service.get_vote_summary(
        db=db,
        build_list_id=build_list_id,
        logger=logger,
    )


@router.get(
    "/{build_list_id}/my-vote",
    response_model=BuildListVoteRead,
    responses=standard_responses(
        success_description="User vote on build list retrieved successfully",
        not_found=True,
    ),
)
async def get_my_vote_on_build_list(
    build_list_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListVoteRead:
    """Get the current user's vote on a specific build list."""
    db = deps["db"]
    logger = deps["logger"]

    vote = build_list_vote_service.get_user_vote(
        db=db,
        build_list_id=build_list_id,
        user_id=current_user.id,
    )
    if not vote:
        from app.api.utils.response_patterns import ResponsePatterns

        ResponsePatterns.raise_not_found("Vote")
    return vote


@router.get(
    "/admin/flagged",
    response_model=List[FlaggedBuildListSummary],
    responses=standard_responses(
        success_description="Flagged build lists retrieved successfully", forbidden=True
    ),
)
async def get_flagged_build_lists(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    min_downvotes: int = Query(
        5, ge=1, le=100, description="Minimum downvotes to consider flagged"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[FlaggedBuildListSummary]:
    """Get build lists flagged for review based on downvotes and reports (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    return build_list_vote_service.get_flagged_build_lists(
        db=db,
        days=days,
        min_downvotes=min_downvotes,
        logger=logger,
    )


@router.get(
    "/admin/flagged/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of flagged build lists", forbidden=True
    ),
)
async def get_flagged_build_lists_count(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    min_downvotes: int = Query(
        5, ge=1, le=100, description="Minimum downvotes to consider flagged"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, int]:
    """Get count of flagged build lists (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    flagged_build_lists = build_list_vote_service.get_flagged_build_lists(
        db=db,
        days=days,
        min_downvotes=min_downvotes,
        logger=logger,
    )
    return {"count": len(flagged_build_lists)}


@router.get(
    "/top/upvoted",
    response_model=List[BuildListVoteRead],
    responses=standard_responses(
        success_description="Top upvoted build lists retrieved successfully"
    ),
)
async def get_top_upvoted_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of build lists to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[BuildListVoteRead]:
    """Get top upvoted build lists."""
    db = deps["db"]
    logger = deps["logger"]

    build_lists = build_list_vote_service.get_build_lists_by_vote_type(
        db=db,
        vote_type="upvote",
        skip=skip,
        limit=limit,
        logger=logger,
    )
    return [BuildListVoteRead.model_validate(build_list) for build_list in build_lists]


@router.get(
    "/top/downvoted",
    response_model=List[BuildListVoteRead],
    responses=standard_responses(
        success_description="Top downvoted build lists retrieved successfully"
    ),
)
async def get_top_downvoted_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of build lists to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[BuildListVoteRead]:
    """Get top downvoted build lists."""
    db = deps["db"]
    logger = deps["logger"]

    build_lists = build_list_vote_service.get_build_lists_by_vote_type(
        db=db,
        vote_type="downvote",
        skip=skip,
        limit=limit,
        logger=logger,
    )
    return [BuildListVoteRead.model_validate(build_list) for build_list in build_lists]
