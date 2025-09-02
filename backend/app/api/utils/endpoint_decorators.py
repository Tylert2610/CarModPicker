"""
Common endpoint decorators for standardizing API responses and reducing redundancy.

This module provides decorators that automatically add consistent response documentation
and error handling patterns to FastAPI endpoints.
"""

from typing import Any, Dict, List, Optional, Type, Union, Callable
from functools import wraps
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse

from .response_patterns import ResponsePatterns


def standard_responses(
    success_description: str = "Operation completed successfully",
    not_found: bool = False,
    unauthorized: bool = False,
    forbidden: bool = False,
    validation_error: bool = False,
    conflict: bool = False,
    custom_responses: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Generate standardized response documentation for endpoints.

    Args:
        success_description: Description for successful responses
        not_found: Whether to include 404 response
        unauthorized: Whether to include 401 response
        forbidden: Whether to include 403 response
        validation_error: Whether to include 422 response
        conflict: Whether to include 409 response
        custom_responses: Additional custom response codes and descriptions

    Returns:
        Dictionary of response codes and their documentation
    """
    responses = {
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
        responses.update(custom_responses)

    return responses


def crud_responses(
    entity_name: str,
    operation: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Generate standardized CRUD operation response documentation.

    Args:
        entity_name: Name of the entity being operated on
        operation: Type of operation (create, read, update, delete, list)
        allow_public_read: Whether the operation allows public access
        custom_responses: Additional custom response codes and descriptions

    Returns:
        Dictionary of response codes and their documentation
    """
    base_responses = {}

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
        base_responses.update(custom_responses)

    return base_responses


def pagination_responses(
    entity_name: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Generate standardized pagination response documentation.

    Args:
        entity_name: Name of the entity being listed
        allow_public_read: Whether the operation allows public access
        custom_responses: Additional custom response codes and descriptions

    Returns:
        Dictionary of response codes and their documentation
    """
    base_responses = {
        200: {"description": f"List of {entity_name}s retrieved successfully"},
    }

    if not allow_public_read:
        base_responses[401] = {"description": "Authentication required"}
        base_responses[403] = {"description": f"Not authorized to list {entity_name}s"}

    if custom_responses:
        base_responses.update(custom_responses)

    return base_responses


def search_responses(
    entity_name: str,
    allow_public_read: bool = False,
    custom_responses: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Generate standardized search response documentation.

    Args:
        entity_name: Name of the entity being searched
        allow_public_read: Whether the operation allows public access
        custom_responses: Additional custom response codes and descriptions

    Returns:
        Dictionary of response codes and their documentation
    """
    base_responses = {
        200: {
            "description": f"Search results for {entity_name}s retrieved successfully"
        },
        400: {"description": "Invalid search parameters"},
    }

    if not allow_public_read:
        base_responses[401] = {"description": "Authentication required"}
        base_responses[403] = {
            "description": f"Not authorized to search {entity_name}s"
        }

    if custom_responses:
        base_responses.update(custom_responses)

    return base_responses


def standard_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
) -> tuple[int, int]:
    """
    Standard pagination parameters for endpoints.

    Returns:
        Tuple of (skip, limit) values
    """
    return skip, limit


def validate_pagination_params(skip: int, limit: int) -> tuple[int, int]:
    """
    Validate and normalize pagination parameters.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return

    Returns:
        Tuple of validated (skip, limit) values
    """
    if skip < 0:
        skip = 0
    if limit < 1:
        limit = 1
    elif limit > 1000:
        limit = 1000

    return skip, limit


def ownership_verification(
    entity_name: str,
    entity_id_param: str = "entity_id",
    user_id_field: str = "user_id",
    not_found_detail: Optional[str] = None,
    forbidden_detail: Optional[str] = None,
) -> Callable:
    """
    Decorator for verifying entity ownership.

    Args:
        entity_name: Name of the entity for error messages
        entity_id_param: Name of the entity ID parameter
        user_id_field: Name of the user ID field in the entity model
        not_found_detail: Custom not found error detail
        forbidden_detail: Custom forbidden error detail

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract parameters from kwargs
            entity_id = kwargs.get(entity_id_param)
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")
            logger = kwargs.get("logger")

            if not all([entity_id, db, current_user]):
                raise ValueError(
                    f"Missing required parameters for ownership verification: {entity_name}"
                )

            # Get entity and verify ownership
            entity = (
                db.query(func.__annotations__["return"])
                .filter(getattr(func.__annotations__["return"], "id") == entity_id)
                .first()
            )

            if not entity:
                detail = not_found_detail or f"{entity_name.title()} not found"
                ResponsePatterns.raise_not_found(entity_name, entity_id)

            if getattr(entity, user_id_field) != current_user.id:
                detail = (
                    forbidden_detail or f"Not authorized to access this {entity_name}"
                )
                ResponsePatterns.raise_forbidden(detail)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def admin_only(func: Callable) -> Callable:
    """
    Decorator to ensure only admin users can access an endpoint.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get("current_user")
        if not current_user or not current_user.is_admin:
            ResponsePatterns.raise_forbidden("Admin access required")
        return await func(*args, **kwargs)

    return wrapper


def public_read_optional(func: Callable) -> Callable:
    """
    Decorator to make an endpoint optionally public readable.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # This decorator can be used to modify response models or add public access
        # Implementation depends on specific use case
        return await func(*args, **kwargs)

    return wrapper
