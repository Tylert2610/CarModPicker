"""
Refactored car votes endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseVoteRouter and CarVoteService to provide
all common voting operations while maintaining car-specific functionality.
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.car import Car as DBCar
from app.api.models.car_vote import CarVote as DBCarVote
from app.api.models.user import User as DBUser
from app.api.schemas.car_vote import (
    CarVoteCreate,
    CarVoteRead,
    CarVoteSummary,
    FlaggedCarSummary,
)
from app.api.services.car_vote_service import CarVoteService
from app.api.utils.base_vote_router import BaseVoteRouter
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.common_patterns import get_standard_public_endpoint_dependencies
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
car_vote_service = CarVoteService()

# Create base vote router
base_vote_router = BaseVoteRouter(
    service=car_vote_service,
    router=router,
    entity_name="car",
    vote_entity_id_param="car_id",
)


# Add custom car-specific endpoints
@router.get(
    "/{car_id}/vote-summary-detailed",
    response_model=CarVoteSummary,
    responses=standard_responses(
        success_description="Detailed vote summary for car retrieved successfully",
        not_found=True,
    ),
)
async def get_car_vote_summary_detailed(
    car_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> CarVoteSummary:
    """Get detailed vote summary for a car with percentages."""
    db = deps["db"]
    logger = deps["logger"]

    return car_vote_service.get_car_vote_summary(
        db=db,
        car_id=car_id,
        logger=logger,
    )


@router.get(
    "/admin/flagged",
    response_model=List[FlaggedCarSummary],
    responses=standard_responses(
        success_description="Flagged cars retrieved successfully", forbidden=True
    ),
)
async def get_flagged_cars(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    min_downvotes: int = Query(
        5, ge=1, le=100, description="Minimum downvotes to consider flagged"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[FlaggedCarSummary]:
    """Get cars flagged for review based on downvotes and reports (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    return car_vote_service.get_flagged_cars(
        db=db,
        days=days,
        min_downvotes=min_downvotes,
        logger=logger,
    )


@router.get(
    "/admin/flagged/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of flagged cars", forbidden=True
    ),
)
async def get_flagged_cars_count(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    min_downvotes: int = Query(
        5, ge=1, le=100, description="Minimum downvotes to consider flagged"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, int]:
    """Get count of flagged cars (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    flagged_cars = car_vote_service.get_flagged_cars(
        db=db,
        days=days,
        min_downvotes=min_downvotes,
        logger=logger,
    )
    return {"count": len(flagged_cars)}


@router.get(
    "/top/upvoted",
    response_model=List[CarVoteRead],
    responses=standard_responses(
        success_description="Top upvoted cars retrieved successfully"
    ),
)
async def get_top_upvoted_cars(
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarVoteRead]:
    """Get top upvoted cars."""
    db = deps["db"]
    logger = deps["logger"]

    cars = car_vote_service.get_cars_by_vote_type(
        db=db,
        vote_type="upvote",
        skip=skip,
        limit=limit,
        logger=logger,
    )
    return [CarVoteRead.model_validate(car) for car in cars]


@router.get(
    "/top/downvoted",
    response_model=List[CarVoteRead],
    responses=standard_responses(
        success_description="Top downvoted cars retrieved successfully"
    ),
)
async def get_top_downvoted_cars(
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarVoteRead]:
    """Get top downvoted cars."""
    db = deps["db"]
    logger = deps["logger"]

    cars = car_vote_service.get_cars_by_vote_type(
        db=db,
        vote_type="downvote",
        skip=skip,
        limit=limit,
        logger=logger,
    )
    return [CarVoteRead.model_validate(car) for car in cars]
