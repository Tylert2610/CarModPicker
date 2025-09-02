"""
Refactored cars endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining car-specific functionality.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import get_current_user
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.car_service import CarService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    get_standard_pagination_params,
    validate_pagination_params,
    get_standard_public_endpoint_dependencies,
    get_paginated_response,
    apply_standard_filters,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    search_responses,
    crud_responses,
    standard_responses,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
car_service = CarService()

# Create base endpoint router
base_router = BaseEndpointRouter(
    service=car_service,
    router=router,
    entity_name="car",
    allow_public_read=True,  # Cars can be viewed publicly
    additional_create_data={},  # No additional data needed for cars
)

# Override search fields for cars
base_router._get_search_fields = lambda: ["make", "model"]


# Add custom endpoints specific to cars
@router.get(
    "/make/{make}",
    response_model=List[CarRead],
    responses=pagination_responses("car", allow_public_read=True),
)
async def get_cars_by_make(
    make: str,
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Get cars by make with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.get_cars_by_make_and_year(
        db=db, make=make, skip=skip, limit=limit, logger=logger
    )
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/year/{year}",
    response_model=List[CarRead],
    responses=pagination_responses("car", allow_public_read=True),
)
async def get_cars_by_year(
    year: int,
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Get cars by year with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.get_cars_by_make_and_year(
        db=db, year=year, skip=skip, limit=limit, logger=logger
    )
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/search",
    response_model=List[CarRead],
    responses=search_responses("car", allow_public_read=True),
)
async def search_cars(
    q: str = Query(..., description="Search term for car make or model"),
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Search cars by make or model with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.search_cars(
        db=db, search_term=q, skip=skip, limit=limit, logger=logger
    )
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/user/{user_id}",
    response_model=List[CarRead],
    responses=pagination_responses("car", allow_public_read=False),
)
async def get_cars_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of cars to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[CarRead]:
    """Get cars by user ID with pagination."""
    # Users can only see their own cars
    if current_user.id != user_id:
        ResponsePatterns.raise_forbidden("Not authorized to view other users' cars")

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.get_cars_by_user(
        db=deps["db"], user_id=user_id, skip=skip, limit=limit, logger=deps["logger"]
    )
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/stats/makes",
    response_model=dict[str, int],
    responses=standard_responses(
        success_description="Car make statistics retrieved successfully"
    ),
)
async def get_car_make_stats(
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of cars by make."""
    from sqlalchemy import func

    db = deps["db"]
    logger = deps["logger"]

    stats = (
        db.query(DBCar.make, func.count(DBCar.id).label("count"))
        .group_by(DBCar.make)
        .order_by(func.count(DBCar.id).desc())
        .all()
    )

    result = {make: count for make, count in stats}
    logger.info(f"Retrieved car make statistics: {len(result)} makes")
    return result


@router.get(
    "/stats/years",
    response_model=dict[str, int],
    responses=standard_responses(
        success_description="Car year statistics retrieved successfully"
    ),
)
async def get_car_year_stats(
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of cars by year."""
    from sqlalchemy import func

    db = deps["db"]
    logger = deps["logger"]

    stats = (
        db.query(DBCar.year, func.count(DBCar.id).label("count"))
        .group_by(DBCar.year)
        .order_by(DBCar.year.desc())
        .all()
    )

    result = {str(year): count for year, count in stats}
    logger.info(f"Retrieved car year statistics: {len(result)} years")
    return result


# Add count endpoint
base_router.add_count_endpoint()
