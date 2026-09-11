"""
Common endpoint decorators for standardizing API responses and reducing redundancy.

This module provides decorators that automatically add consistent response documentation
and error handling patterns to FastAPI endpoints.
"""

from collections.abc import Awaitable
from functools import wraps
from typing import Annotated, Any, Callable, Dict, Optional, ParamSpec, TypeVar, cast

from fastapi import Query

from .response_patterns import ResponsePatterns

P = ParamSpec("P")
T = TypeVar("T")


def standard_responses(
    success_description: str = "Operation completed successfully",
    not_found: bool = False,
    unauthorized: bool = False,
    forbidden: bool = False,
    validation_error: bool = False,
    conflict: bool = False,
    custom_responses: Optional[Dict[int | str, Dict[str, Any]]] = None,
) -> Dict[int | str, Dict[str, Any]]:
    """Generate standardized response documentation for endpoints."""
    responses: Dict[int | str, Dict[str, Any]] = {
        200: {"description": success_description},
    }

    if not_found:
        responses[404] = {"description": "Resource not found"}

    if unauthorized:
        responses[401] = {"description": "Authentication required"}

    if forbidden:
        responses[403] = {"description": "Access denied"}

    if validation_error:
        responses[422] = {"description": "Validation error"}

    if conflict:
        responses[409] = {"description": "Resource conflict"}

    if custom_responses:
        for key, value in custom_responses.items():
            responses[key] = value

    return responses


def crud_responses(
    entity_name: str,
    operation: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int | str, Dict[str, Any]]] = None,
) -> Dict[int | str, Dict[str, Any]]:
    """Generate standardized CRUD operation response documentation."""
    base_responses: Dict[int | str, Dict[str, Any]] = {}

    if operation == "create":
        base_responses = {
            201: {"description": f"{entity_name.title()} created successfully"},
            400: {"description": f"Invalid {entity_name} data"},
            403: {"description": f"Not authorized to create {entity_name}"},
            422: {"description": "Validation error"},
        }
    elif operation == "read":
        if allow_public_read:
            base_responses = {
                200: {"description": f"{entity_name.title()} retrieved successfully"},
                404: {"description": f"{entity_name.title()} not found"},
            }
        else:
            base_responses = {
                200: {"description": f"{entity_name.title()} retrieved successfully"},
                401: {"description": "Authentication required"},
                403: {"description": f"Not authorized to access {entity_name}"},
                404: {"description": f"{entity_name.title()} not found"},
            }
    elif operation == "update":
        base_responses = {
            200: {"description": f"{entity_name.title()} updated successfully"},
            400: {"description": f"Invalid {entity_name} data"},
            401: {"description": "Authentication required"},
            403: {"description": f"Not authorized to update {entity_name}"},
            404: {"description": f"{entity_name.title()} not found"},
            409: {"description": f"{entity_name.title()} conflict"},
            422: {"description": "Validation error"},
        }
    elif operation == "delete":
        base_responses = {
            200: {"description": f"{entity_name.title()} deleted successfully"},
            401: {"description": "Authentication required"},
            403: {"description": f"Not authorized to delete {entity_name}"},
            404: {"description": f"{entity_name.title()} not found"},
        }
    elif operation == "list":
        if allow_public_read:
            base_responses = {
                200: {"description": f"List of {entity_name}s retrieved successfully"},
            }
        else:
            base_responses = {
                200: {"description": f"List of {entity_name}s retrieved successfully"},
                401: {"description": "Authentication required"},
                403: {"description": f"Not authorized to list {entity_name}s"},
            }

    if custom_responses:
        for key, value in custom_responses.items():
            base_responses[key] = value

    return base_responses


def pagination_responses(
    entity_name: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int | str, Dict[str, Any]]] = None,
) -> Dict[int | str, Dict[str, Any]]:
    """Generate standardized pagination response documentation."""
    base_responses: Dict[int | str, Dict[str, Any]] = {
        200: {"description": f"List of {entity_name}s retrieved successfully"},
    }

    if not allow_public_read:
        base_responses[401] = {"description": "Authentication required"}
        base_responses[403] = {"description": f"Not authorized to list {entity_name}s"}

    if custom_responses:
        for key, value in custom_responses.items():
            base_responses[key] = value

    return base_responses


def search_responses(
    entity_name: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int | str, Dict[str, Any]]] = None,
) -> Dict[int | str, Dict[str, Any]]:
    """Generate standardized search response documentation."""
    base_responses: Dict[int | str, Dict[str, Any]] = {
        200: {"description": f"Search results for {entity_name}s retrieved successfully"},
        400: {"description": "Invalid search parameters"},
    }

    if not allow_public_read:
        base_responses[401] = {"description": "Authentication required"}
        base_responses[403] = {"description": f"Not authorized to search {entity_name}s"}

    if custom_responses:
        for key, value in custom_responses.items():
            base_responses[key] = value

    return base_responses


def standard_pagination_params(
    skip: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of items to return")] = 100,
) -> tuple[int, int]:
    """Standard pagination parameters for endpoints."""
    return skip, limit


def validate_pagination_params(skip: int, limit: int) -> tuple[int, int]:
    """Validate and normalize pagination parameters (clamping variant).

    Silently clamps out-of-range inputs to the nearest legal value
    (``skip<0`` → 0, ``limit<1`` → 1, ``limit>1000`` → 1000) and
    """
    if skip < 0:
        skip = 0
    if limit < 1:
        limit = 1
    elif limit > 1000:
        limit = 1000

    return skip, limit


def admin_only(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """
    Decorator to ensure only admin users can access an endpoint.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        """Reject a non admin caller before running the endpoint."""
        from app.db.dynamo.users import User as DBUser

        user_value = kwargs.get("current_user")
        if not user_value:
            ResponsePatterns.raise_forbidden("Admin access required")
        current_user = cast(DBUser, user_value)
        if not current_user.is_admin:
            ResponsePatterns.raise_forbidden("Admin access required")
        return await func(*args, **kwargs)

    return wrapper


def public_read_optional(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """
    Decorator to make an endpoint optionally public readable.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        """Run the endpoint without requiring authentication."""
        return await func(*args, **kwargs)

    return wrapper
