"""
Refactored categories endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining category-specific functionality.
"""

from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.category import Category as DBCategory
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.api.schemas.global_part import GlobalPartRead
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    get_standard_pagination_params,
    validate_pagination_params,
    get_entity_or_404,
    handle_integrity_error,
    get_standard_public_endpoint_dependencies,
)
from app.api.utils.endpoint_decorators import (
    crud_responses,
    pagination_responses,
    admin_only,
    standard_responses,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db


# Create base CRUD service
class CategoryService(
    BaseCRUDService[DBCategory, CategoryCreate, CategoryResponse, CategoryUpdate]
):
    """Category service that extends the base CRUD service."""

    def __init__(self):
        super().__init__(
            model=DBCategory,
            entity_name="category",
            subscription_check_method=None,  # Categories don't require subscription
        )

    def get_active_categories(self, db: Session) -> List[DBCategory]:
        """Get all active categories ordered by sort order."""
        return (
            db.query(DBCategory)
            .filter(DBCategory.is_active == True)
            .order_by(DBCategory.sort_order)
            .all()
        )


# Create router
router = APIRouter()

# Create service
category_service = CategoryService()

# Create base endpoint router
base_router = BaseEndpointRouter(
    service=category_service,
    router=router,
    entity_name="category",
    allow_public_read=True,  # Categories can be viewed publicly
    additional_create_data={},  # No additional data needed
    disable_endpoints=["list"],  # Disable automatic list endpoint to use custom one
)

# Override search fields for categories
base_router._get_search_fields = lambda: ["name", "description"]


# Custom endpoints specific to categories
@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> List[CategoryResponse]:
    """
    Get all active categories.
    """
    db = deps["db"]
    categories = category_service.get_active_categories(db)
    # Convert to Pydantic models for proper serialization
    return [CategoryResponse.model_validate(category) for category in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> CategoryResponse:
    """
    Get specific category details.
    """
    db = deps["db"]
    category = get_entity_or_404(db, DBCategory, category_id, "category")
    return CategoryResponse.model_validate(category)


@router.get(
    "/{category_id}/global-parts",
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
    """
    Get global parts by category with pagination.
    """
    db = deps["db"]

    # First verify the category exists
    category = get_entity_or_404(db, DBCategory, category_id, "category")

    # Validate pagination parameters
    skip, limit = validate_pagination_params(skip, limit)

    parts = (
        db.query(DBGlobalPart)
        .filter(DBGlobalPart.category_id == category_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    # Convert to Pydantic models for proper serialization
    return [GlobalPartRead.model_validate(part) for part in parts]


@router.post(
    "/",
    response_model=CategoryResponse,
    responses=crud_responses("category", "create"),
)
async def create_category(
    category: CategoryCreate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CategoryResponse:
    """
    Create a new category (admin only).
    """
    db = deps["db"]
    logger = deps["logger"]

    # Check if category with same name already exists
    existing_category = (
        db.query(DBCategory).filter(DBCategory.name == category.name).first()
    )
    if existing_category:
        ResponsePatterns.raise_conflict(
            "Category with this name already exists", "CATEGORY_EXISTS"
        )

    db_category = DBCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return CategoryResponse.model_validate(db_category)


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    responses=crud_responses("category", "update"),
)
async def update_category(
    category_id: int,
    category: CategoryUpdate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CategoryResponse:
    """
    Update a category (admin only).
    """
    db_category = get_entity_or_404(deps["db"], DBCategory, category_id, "category")

    # Check if name is being changed and if it conflicts with existing
    if category.name and category.name != db_category.name:
        existing_category = (
            deps["db"]
            .query(DBCategory)
            .filter(DBCategory.name == category.name)
            .first()
        )
        if existing_category:
            ResponsePatterns.raise_conflict(
                "Category with this name already exists", "CATEGORY_EXISTS"
            )

    # Update fields
    update_data = category.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_category, field, value)

    try:
        deps["db"].add(db_category)
        deps["db"].commit()
        deps["db"].refresh(db_category)
        return CategoryResponse.model_validate(db_category)
    except Exception as e:
        deps["db"].rollback()
        handle_integrity_error(e, "category")


@router.delete(
    "/{category_id}",
    response_model=CategoryResponse,
    responses=crud_responses("category", "delete"),
)
async def delete_category(
    category_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CategoryResponse:
    """
    Delete a category (admin only).
    """
    db_category = get_entity_or_404(deps["db"], DBCategory, category_id, "category")

    # Check if category is being used by any parts
    parts_count = (
        deps["db"]
        .query(DBGlobalPart)
        .filter(DBGlobalPart.category_id == category_id)
        .count()
    )
    if parts_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete category that has {parts_count} associated parts",
            "CATEGORY_IN_USE",
        )

    # Convert to response model before deleting
    category_response = CategoryResponse.model_validate(db_category)

    deps["db"].delete(db_category)
    deps["db"].commit()
    return category_response


@router.get(
    "/{category_id}/parts-count",
    responses=standard_responses(
        success_description="Category parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_category_parts_count(
    category_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """
    Get the count of parts in a specific category.
    """
    # Verify category exists
    get_entity_or_404(deps["db"], DBCategory, category_id, "category")

    parts_count = (
        deps["db"]
        .query(DBGlobalPart)
        .filter(DBGlobalPart.category_id == category_id)
        .count()
    )
    return {"parts_count": parts_count}


# Add count endpoint
base_router.add_count_endpoint()
