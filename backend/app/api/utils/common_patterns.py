"""
Common endpoint patterns to reduce redundancy across API endpoints.

This module provides reusable patterns for shared endpoint dependencies,
ownership/admin checks, and paginated response envelopes.
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict, TypeVar
from uuid import UUID

from app.api.protocols import HasId
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=HasId)


class PublicEndpointDeps(TypedDict):
    """Dependencies for public endpoints (no authentication required)."""

    logger: logging.Logger


from app.api.utils.endpoint_decorators import validate_pagination_params as validate_pagination_params  # noqa: E402


def get_standard_public_endpoint_dependencies() -> PublicEndpointDeps:
    """Standard dependencies for public endpoints."""
    return {"logger": logger}


def verify_user_access_or_admin(
    current_user: DBUser,
    target_user_id: UUID,
    action_description: str = "access this resource",
    logger: Optional[logging.Logger] = None,
) -> None:
    """Verify that the current user can access a resource or is an admin."""
    if current_user.id != target_user_id and not current_user.is_admin and not current_user.is_superuser:
        if logger:
            logger.warning(
                f"Access denied: User {current_user.id} " f"attempted to {action_description} for user {target_user_id}"
            )
        ResponsePatterns.raise_forbidden(f"Not authorized to {action_description}")


def create_paginated_response(
    data: List[ModelT],
    total: int,
    skip: int,
    limit: int,
    message: str = "Data retrieved successfully",
) -> Dict[str, Any]:
    """Create a standardized paginated response."""
    total_pages = (total + limit - 1) // limit
    current_page = (skip // limit) + 1

    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "total": total,
            "total_items": total,
            "total_pages": total_pages,
            "current_page": current_page,
            "skip": skip,
            "limit": limit,
            "items_per_page": limit,
            "has_next": current_page < total_pages,
            "has_previous": current_page > 1,
        },
    }
