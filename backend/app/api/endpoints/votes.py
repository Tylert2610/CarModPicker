"""
Unified votes endpoint for all entity types.
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import (
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.vote import (
    EntityType,
    FlaggedEntitySummary,
    VoteCreate,
    VoteMutationResult,
    VoteSummary,
)
from app.api.services.vote_service import VoteService
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Create service
vote_service = VoteService()


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of votes",
    ),
)
async def count_votes(
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Get total count of votes."""
    try:
        count = repos.votes.count()
        logger.info(f"Retrieved votes count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting votes: {str(e)}")
        raise


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=VoteMutationResult,
    responses=standard_responses(
        success_description="Vote created/updated successfully, with the entity's tallies as of this write",
        validation_error=True,
        not_found=True,
        conflict=True,
    ),
)
async def vote_on_entity(
    entity_type: EntityType,
    entity_id: UUID,
    vote_data: VoteCreate,
    current_user: DBUser = Depends(get_current_user),
) -> VoteMutationResult:
    """Vote on an entity (car, build list, or global part).

    The response carries the entity's recomputed tallies alongside the vote.
    Split plan row 24 moved the `parts.net_votes` aggregate onto the `votes`
    stream, so that column now lags the vote; these counts are read from the
    `votes` table in this request and do not, which is what lets a client render
    the new total without a follow-up read.
    """
    return vote_service.vote_on_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
        vote_data=vote_data,
        logger=logger,
    )


@router.delete(
    "/{entity_type}/{entity_id}",
    response_model=VoteMutationResult,
    responses=standard_responses(
        success_description="Vote removed successfully, with the entity's tallies after the removal",
        not_found=True,
    ),
)
async def remove_vote(
    entity_type: EntityType,
    entity_id: UUID,
    current_user: DBUser = Depends(get_current_user),
) -> VoteMutationResult:
    """Remove a vote from an entity.

    Returns the same shape the vote route does, with `vote` set to null because
    there is no vote left. A client removing a vote needs the new total for
    exactly the same reason a client casting one does.
    """
    result = vote_service.remove_vote(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
        logger=logger,
    )

    if result is None:
        # IN-06: use the centralized error-shape helper instead of raw
        # ``HTTPException`` so the response follows the same {message,
        # error_code, details} contract as the rest of the module.
        ResponsePatterns.raise_not_found("Vote")
    return result


@router.get(
    "/{entity_type}/{entity_id}/summary",
    response_model=VoteSummary,
    responses=standard_responses(
        success_description="Vote summary retrieved successfully",
        not_found=True,
    ),
)
async def get_vote_summary(
    entity_type: EntityType,
    entity_id: UUID,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> VoteSummary:
    """Get vote summary for an entity (public endpoint, authentication optional)."""
    user_id = current_user.id if current_user else None
    return vote_service.get_vote_summary(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        logger=logger,
    )


@router.get(
    "/admin/flagged/{entity_type}",
    response_model=List[FlaggedEntitySummary],
    responses=standard_responses(
        success_description="Flagged entities retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def get_flagged_entities(
    entity_type: EntityType,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of flagged entities to return"),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[FlaggedEntitySummary]:
    """Get flagged entities (those with high downvote ratios or reports). Admin only."""
    return vote_service.get_flagged_entities(
        entity_type=entity_type,
        limit=limit,
        logger=logger,
    )
