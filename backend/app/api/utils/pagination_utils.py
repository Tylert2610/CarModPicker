"""
Standardized pagination utilities to reduce redundancy.

This module provides common pagination patterns and utilities for
consistent pagination implementation across endpoints.
"""

from typing import List, TypeVar, Generic, Type, Optional, Tuple, Any
from fastapi import Query, Depends
from sqlalchemy.orm import Session, Query as SQLAlchemyQuery
from sqlalchemy import func

from app.api.utils.endpoint_decorators import validate_pagination_params
from app.core.logging import get_logger

# Generic types
ModelType = TypeVar("ModelType")


class PaginationParams:
    """Standardized pagination parameters."""

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return"
        ),
    ):
        self.skip = skip
        self.limit = limit


def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
) -> Tuple[int, int]:
    """
    Get validated pagination parameters.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return

    Returns:
        Tuple of validated (skip, limit) parameters
    """
    return validate_pagination_params(skip=skip, limit=limit)


def paginate_query(
    query: SQLAlchemyQuery[ModelType],
    skip: int,
    limit: int,
    logger: Any = None,
    entity_name: str = "items",
) -> List[ModelType]:
    """
    Apply pagination to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query to paginate
        skip: Number of items to skip
        limit: Maximum number of items to return
        logger: Logger instance for logging
        entity_name: Name of the entity for logging

    Returns:
        List of paginated results
    """
    paginated_query = query.offset(skip).limit(limit)
    results = paginated_query.all()

    if logger:
        logger.info(
            f"Retrieved {len(results)} {entity_name} (skip: {skip}, limit: {limit})"
        )

    return results


def get_total_count(query: SQLAlchemyQuery[ModelType]) -> int:
    """
    Get total count of items in a query.

    Args:
        query: SQLAlchemy query to count

    Returns:
        Total count of items
    """
    return query.count()


def create_paginated_response(
    data: List[ModelType],
    total: int,
    skip: int,
    limit: int,
    entity_name: str = "items",
) -> dict:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items
        skip: Number of items skipped
        limit: Items per page
        entity_name: Name of the entity type

    Returns:
        Dictionary with pagination metadata and data
    """
    current_page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit

    return {
        "data": data,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "total_items": total,
            "items_per_page": limit,
            "has_next": current_page < total_pages,
            "has_previous": current_page > 1,
        },
    }


def apply_search_filter(
    query: SQLAlchemyQuery[ModelType],
    search: Optional[str],
    search_fields: List[str],
    case_sensitive: bool = False,
) -> SQLAlchemyQuery[ModelType]:
    """
    Apply search filter to a query.

    Args:
        query: SQLAlchemy query to filter
        search: Search term
        search_fields: List of field names to search in
        case_sensitive: Whether search should be case sensitive

    Returns:
        Filtered query
    """
    if not search:
        return query

    search_terms = []
    for field in search_fields:
        if hasattr(query.column_descriptions[0]["entity"], field):
            if case_sensitive:
                search_terms.append(
                    getattr(query.column_descriptions[0]["entity"], field).ilike(
                        f"%{search}%"
                    )
                )
            else:
                search_terms.append(
                    getattr(query.column_descriptions[0]["entity"], field).ilike(
                        f"%{search}%"
                    )
                )

    if search_terms:
        from sqlalchemy import or_

        query = query.filter(or_(*search_terms))

    return query


def apply_sorting(
    query: SQLAlchemyQuery[ModelType],
    sort_by: Optional[str],
    sort_order: str = "asc",
    allowed_sort_fields: Optional[List[str]] = None,
) -> SQLAlchemyQuery[ModelType]:
    """
    Apply sorting to a query.

    Args:
        query: SQLAlchemy query to sort
        sort_by: Field name to sort by
        sort_order: Sort order ('asc' or 'desc')
        allowed_sort_fields: List of allowed field names for sorting

    Returns:
        Sorted query
    """
    if not sort_by:
        return query

    # Validate sort field
    if allowed_sort_fields and sort_by not in allowed_sort_fields:
        return query

    # Get the model class from the query
    model_class = query.column_descriptions[0]["entity"]

    if hasattr(model_class, sort_by):
        sort_field = getattr(model_class, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

    return query
