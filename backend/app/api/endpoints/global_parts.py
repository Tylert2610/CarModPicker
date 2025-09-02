"""
Refactored global parts endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseEndpointRouter to provide common CRUD operations
while maintaining global part-specific functionality.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.global_part import (
    GlobalPartCreate,
    GlobalPartRead,
    GlobalPartUpdate,
    GlobalPartReadWithVotes,
)
from app.api.services.base_crud_service import BaseCRUDService
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
    standard_responses,
)
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()


# Create base CRUD service
class GlobalPartService(
    BaseCRUDService[DBGlobalPart, GlobalPartCreate, GlobalPartRead, GlobalPartUpdate]
):
    """Global part service that extends the base CRUD service."""

    def __init__(self):
        super().__init__(
            model=DBGlobalPart,
            entity_name="global part",
            subscription_check_method="can_create_global_part",
        )


global_part_service = GlobalPartService()

# Create base endpoint router
base_router = BaseEndpointRouter(
    service=global_part_service,
    router=router,
    entity_name="global part",
    allow_public_read=True,  # Global parts can be viewed publicly
    additional_create_data={},  # No additional data needed for global parts
)

# Override search fields for global parts
base_router._get_search_fields = lambda: ["name", "description", "category"]


# Add custom endpoints specific to global parts
@router.get(
    "/with-votes",
    response_model=List[GlobalPartReadWithVotes],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def read_global_parts_with_votes(
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of global parts to return"
    ),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(
        None, description="Search in global part names and descriptions"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartReadWithVotes]:
    """Get all global parts with vote data and optional filtering and search."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    query = db.query(DBGlobalPart)

    # Apply standard filters
    query = apply_standard_filters(
        query=query,
        search=search,
        category_id=category_id,
        search_fields=["name", "description"],
    )

    parts = get_paginated_response(
        query=query, skip=skip, limit=limit, logger=logger, entity_name="global parts"
    )
    return [GlobalPartReadWithVotes.model_validate(part) for part in parts]


@router.get(
    "/category/{category_id}",
    response_model=List[GlobalPartRead],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def get_global_parts_by_category(
    category_id: int,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of parts to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartRead]:
    """Get global parts by category with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    parts = (
        db.query(DBGlobalPart)
        .filter(DBGlobalPart.category_id == category_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    logger.info(f"Retrieved {len(parts)} parts for category {category_id}")
    return [GlobalPartRead.model_validate(part) for part in parts]


@router.get(
    "/user/{user_id}/count",
    response_model=dict,
    responses=standard_responses(
        success_description="Count of global parts for user", not_found=True
    ),
)
async def count_global_parts_by_user(
    user_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Count global parts created by a specific user."""
    count = (
        deps["db"].query(DBGlobalPart).filter(DBGlobalPart.user_id == user_id).count()
    )
    return {"count": count}


# Add filter endpoint for category
base_router.add_filter_endpoint("category", "category_id")

# Add count endpoint
base_router.add_count_endpoint()
