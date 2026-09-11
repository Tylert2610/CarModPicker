"""
Standardized pagination utilities to reduce redundancy.

This module provides common pagination parameter handling and the
pagination response envelope used across endpoints.
"""

from typing import Any, List, Tuple, TypeVar

from fastapi import Query

from app.api.utils.endpoint_decorators import validate_pagination_params

ModelType = TypeVar("ModelType")


class PaginationParams:
    """Standardized pagination parameters."""

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of items to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    ):
        """Capture the validated skip and limit query parameters."""
        self.skip = skip
        self.limit = limit


def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
) -> Tuple[int, int]:
    """Get validated pagination parameters."""
    return validate_pagination_params(skip=skip, limit=limit)


def create_paginated_response(
    data: List[ModelType],
    total: int,
    skip: int,
    limit: int,
    entity_name: str = "items",
) -> dict[str, Any]:
    """Create a standardized paginated response."""
    current_page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit

    return {
        "data": data,
        "total": total,
        "skip": skip,
        "limit": limit,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "total_items": total,
            "items_per_page": limit,
            "has_next": current_page < total_pages,
            "has_previous": current_page > 1,
        },
    }
