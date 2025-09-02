"""
Common endpoint patterns to reduce redundancy across API endpoints.

This module provides reusable patterns for common operations like pagination,
ownership verification, admin checks, and standard query parameters.
"""

from typing import Any, Dict, List, Optional, Tuple, Type
from functools import wraps
from fastapi import Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.user import User as DBUser
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db


# Standard pagination parameters
def get_standard_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
) -> Tuple[int, int]:
    """
    Standard pagination parameters for endpoints.

    Returns:
        Tuple of (skip, limit) values
    """
    return skip, limit


def validate_pagination_params(skip: int, limit: int) -> Tuple[int, int]:
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


# Standard endpoint dependencies
def get_standard_endpoint_dependencies():
    """
    Standard dependencies for endpoints that need database, logger, and current user.

    Returns:
        Dictionary of standard dependencies
    """
    return {
        "db": Depends(get_db),
        "logger": Depends(get_logger),
        "current_user": Depends(get_current_user),
    }


def get_standard_public_endpoint_dependencies():
    """
    Standard dependencies for public endpoints that need database and logger.

    Returns:
        Dictionary of standard dependencies
    """
    return {
        "db": Depends(get_db),
        "logger": Depends(get_logger),
    }


# Standard authorization patterns
def verify_user_access_or_admin(
    current_user: DBUser,
    target_user_id: int,
    action_description: str = "access this resource",
    logger: Optional[Any] = None,
) -> None:
    """
    Verify that the current user can access a resource or is an admin.

    Args:
        current_user: The authenticated user making the request
        target_user_id: The user ID of the resource owner
        action_description: Description of the action for error messages
        logger: Optional logger for warning messages
    """
    if (
        current_user.id != target_user_id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        if logger:
            logger.warning(
                f"Access denied: User {current_user.id} attempted to {action_description} "
                f"for user {target_user_id}"
            )
        ResponsePatterns.raise_forbidden(f"Not authorized to {action_description}")


def verify_entity_ownership_or_admin(
    entity,
    current_user: DBUser,
    entity_name: str = "entity",
    action_description: str = "access this resource",
    logger: Optional[Any] = None,
) -> None:
    """
    Verify that the current user owns an entity or is an admin.

    Args:
        entity: The entity to check ownership of
        current_user: The authenticated user making the request
        entity_name: Name of the entity for error messages
        action_description: Description of the action for error messages
        logger: Optional logger for warning messages
    """
    if not entity:
        ResponsePatterns.raise_not_found(entity_name.title())

    if hasattr(entity, "user_id") and entity.user_id != current_user.id:
        if not current_user.is_admin and not current_user.is_superuser:
            if logger:
                logger.warning(
                    f"Access denied: User {current_user.id} attempted to {action_description} "
                    f"for {entity_name} {getattr(entity, 'id', 'unknown')} owned by user {entity.user_id}"
                )
            ResponsePatterns.raise_forbidden(f"Not authorized to {action_description}")


# Standard pagination response patterns
def get_paginated_response(
    query,
    skip: int,
    limit: int,
    logger: Any,
    entity_name: str = "items",
    user_id: Optional[int] = None,
) -> List[Any]:
    """
    Get paginated response with consistent logging.

    Args:
        query: SQLAlchemy query object
        skip: Number of items to skip
        limit: Maximum number of items to return
        logger: Logger instance
        entity_name: Name of the entity for logging
        user_id: Optional user ID for user-specific queries

    Returns:
        List of paginated items
    """
    items = query.offset(skip).limit(limit).all()

    if not items:
        if user_id:
            logger.info(f"No {entity_name} found for user {user_id}")
        else:
            logger.info(f"No {entity_name} found")
    else:
        if user_id:
            logger.info(
                f"{entity_name.title()} retrieved for user {user_id}: {len(items)} items"
            )
        else:
            logger.info(f"{entity_name.title()} retrieved: {len(items)} items")

    return items


# Standard search and filter patterns
def apply_standard_filters(
    query,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    search_fields: Optional[List[str]] = None,
) -> Any:
    """
    Apply standard search and filter patterns to a query.

    Args:
        query: SQLAlchemy query object
        search: Optional search term
        category_id: Optional category ID filter
        search_fields: List of fields to search in

    Returns:
        Modified query object
    """
    if category_id:
        query = query.filter(query.model.category_id == category_id)

    if search and search_fields:
        search_term = f"%{search}%"
        search_filters = []
        for field in search_fields:
            if hasattr(query.model, field):
                search_filters.append(getattr(query.model, field).ilike(search_term))

        if search_filters:
            from sqlalchemy import or_

            query = query.filter(or_(*search_filters))

    return query


# Ownership verification decorator
def verify_ownership(
    entity_name: str,
    entity_id_param: str = "entity_id",
    user_id_field: str = "user_id",
    not_found_detail: Optional[str] = None,
    forbidden_detail: Optional[str] = None,
):
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

    def decorator(func):
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


# Admin-only decorator
def admin_only(func):
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


# Common database operations
def get_entity_or_404(
    db: Session,
    model: Any,
    entity_id: int,
    entity_name: str,
    logger: Optional[Any] = None,
) -> Any:
    """
    Get an entity by ID or raise 404 if not found.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: Entity ID to find
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings

    Returns:
        Entity instance

    Raises:
        HTTPException: 404 if entity not found
    """
    entity = db.query(model).filter(model.id == entity_id).first()
    if not entity:
        if logger:
            logger.warning(f"Attempt to access non-existent {entity_name} {entity_id}")
        ResponsePatterns.raise_not_found(entity_name, entity_id)
    return entity


def verify_entity_ownership(
    entity: Any,
    current_user: DBUser,
    entity_name: str,
    logger: Optional[Any] = None,
    custom_forbidden_detail: Optional[str] = None,
) -> None:
    """
    Verify that the current user owns the entity.

    Args:
        entity: Entity instance to check ownership
        current_user: Current authenticated user
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings
        custom_forbidden_detail: Custom forbidden error detail

    Raises:
        HTTPException: 403 if user doesn't own the entity
    """
    if entity.user_id != current_user.id:
        detail = (
            custom_forbidden_detail or f"Not authorized to access this {entity_name}"
        )
        if logger:
            logger.warning(
                f"User {current_user.id} attempted to access {entity_name} {entity.id} "
                f"owned by user {entity.user_id}"
            )
        ResponsePatterns.raise_forbidden(detail)


# Common query building
def build_search_query(
    query: Any,
    search_term: Optional[str],
    search_fields: List[str],
) -> Any:
    """
    Build a search query with LIKE filters.

    Args:
        query: Base SQLAlchemy query
        search_term: Search term to filter by
        search_fields: List of field names to search in

    Returns:
        Modified query with search filters
    """
    if not search_term:
        return query

    search_filters = []
    for field in search_fields:
        search_filters.append(
            getattr(query.column_descriptions[0]["entity"], field).ilike(
                f"%{search_term}%"
            )
        )

    if search_filters:
        from sqlalchemy import or_

        query = query.filter(or_(*search_filters))

    return query


def build_filtered_query(
    query: Any,
    filters: Dict[str, Any],
) -> Any:
    """
    Build a filtered query based on filter parameters.

    Args:
        query: Base SQLAlchemy query
        filters: Dictionary of field names and values to filter by

    Returns:
        Modified query with filters
    """
    for field_name, value in filters.items():
        if value is not None:
            if hasattr(query.column_descriptions[0]["entity"], field_name):
                field = getattr(query.column_descriptions[0]["entity"], field_name)
                query = query.filter(field == value)

    return query


def build_sorted_query(
    query: Any,
    sort_by: Optional[str],
    sort_order: str,
    allowed_sort_fields: List[str],
    default_sort: str = "id",
) -> Any:
    """
    Build a sorted query.

    Args:
        query: Base SQLAlchemy query
        sort_by: Field name to sort by
        sort_order: Sort order (asc/desc)
        allowed_sort_fields: List of allowed field names for sorting
        default_sort: Default field to sort by

    Returns:
        Modified query with sorting
    """
    if sort_by and sort_by in allowed_sort_fields:
        sort_field = getattr(query.column_descriptions[0]["entity"], sort_by)
    else:
        sort_field = getattr(query.column_descriptions[0]["entity"], default_sort)

    if sort_order.lower() == "desc":
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    return query


# Common response patterns
def create_paginated_response(
    data: List[Any],
    total: int,
    skip: int,
    limit: int,
    message: str = "Data retrieved successfully",
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items
        skip: Number of items skipped
        limit: Items per page
        message: Success message

    Returns:
        Dictionary with paginated response structure
    """
    total_pages = (total + limit - 1) // limit
    current_page = (skip // limit) + 1

    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "total": total,
            "total_pages": total_pages,
            "current_page": current_page,
            "skip": skip,
            "limit": limit,
            "has_next": current_page < total_pages,
            "has_previous": current_page > 1,
        },
    }


# Common error handling
def handle_integrity_error(
    error: Exception,
    entity_name: str,
    logger: Optional[Any] = None,
) -> None:
    """
    Handle database integrity errors with standardized responses.

    Args:
        error: IntegrityError instance
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings

    Raises:
        HTTPException: Appropriate error response
    """
    if logger:
        logger.warning(f"IntegrityError during {entity_name} operation: {error}")

    error_detail_str = str(error).lower()

    # Check for common constraint violations
    if "unique constraint" in error_detail_str or "duplicate key" in error_detail_str:
        if "username" in error_detail_str:
            ResponsePatterns.raise_conflict(
                "Username already exists", "USERNAME_EXISTS"
            )
        elif "email" in error_detail_str:
            ResponsePatterns.raise_conflict("Email already exists", "EMAIL_EXISTS")
        else:
            ResponsePatterns.raise_conflict(
                f"{entity_name.title()} already exists", "DUPLICATE_ENTITY"
            )
    else:
        ResponsePatterns.raise_bad_request(f"Data validation failed for {entity_name}")


# Common dependency injection
def get_common_dependencies():
    """
    Common dependencies for endpoints.

    Returns:
        Dictionary of common dependencies
    """
    return {
        "db": Depends(get_db),
        "logger": Depends(get_logger),
        "current_user": Depends(get_current_user),
    }


def get_admin_dependencies():
    """
    Admin-only dependencies for endpoints.

    Returns:
        Dictionary of admin dependencies
    """
    return {
        "db": Depends(get_db),
        "logger": Depends(get_logger),
        "current_user": Depends(get_current_admin_user),
    }


# Vote-related patterns
def handle_vote_operation(
    db: Session,
    user_id: int,
    entity_id: int,
    vote_type: str,
    entity_model: Type,
    vote_model: Type,
    entity_name: str,
    logger: Any,
    existing_vote: Optional[Any] = None,
) -> Any:
    """
    Handle vote operations (create/update) with consistent patterns.

    Args:
        db: Database session
        user_id: ID of the user voting
        entity_id: ID of the entity being voted on
        vote_type: Type of vote (upvote/downvote)
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        logger: Logger instance
        existing_vote: Existing vote if updating

    Returns:
        The vote object (created or updated)
    """
    # Verify entity exists
    entity = db.query(entity_model).filter(entity_model.id == entity_id).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        if existing_vote:
            # Update existing vote
            existing_vote.vote_type = vote_type
            db.commit()
            db.refresh(existing_vote)
            logger.info(
                f"Vote updated: {existing_vote.id} by user {user_id} on {entity_name} {entity_id}"
            )
            return existing_vote
        else:
            # Create new vote
            new_vote = vote_model(
                user_id=user_id,
                **{f"{entity_name.lower().replace(' ', '_')}_id": entity_id},
                vote_type=vote_type,
            )
            db.add(new_vote)
            db.commit()
            db.refresh(new_vote)
            logger.info(
                f"Vote created: {new_vote.id} by user {user_id} on {entity_name} {entity_id}"
            )
            return new_vote
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle vote operation: {e}")
        ResponsePatterns.raise_internal_server_error(f"Failed to process vote")


def remove_vote_operation(
    db: Session,
    user_id: int,
    entity_id: int,
    entity_model: Type,
    vote_model: Type,
    entity_name: str,
    logger: Any,
) -> dict[str, str]:
    """
    Handle vote removal with consistent patterns.

    Args:
        db: Database session
        user_id: ID of the user removing vote
        entity_id: ID of the entity vote is being removed from
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        logger: Logger instance

    Returns:
        Success message
    """
    # Verify entity exists
    entity = db.query(entity_model).filter(entity_model.id == entity_id).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    # Find and remove vote
    vote = (
        db.query(vote_model)
        .filter(
            vote_model.user_id == user_id,
            **{f"{entity_name.lower().replace(' ', '_')}_id": entity_id},
        )
        .first()
    )

    if not vote:
        ResponsePatterns.raise_not_found(f"Vote on {entity_name}")

    try:
        db.delete(vote)
        db.commit()
        logger.info(
            f"Vote removed: {vote.id} by user {user_id} on {entity_name} {entity_id}"
        )
        return {"message": f"Vote on {entity_name} removed successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to remove vote: {e}")
        ResponsePatterns.raise_internal_server_error(f"Failed to remove vote")


def get_vote_summary(
    db: Session,
    entity_id: int,
    entity_model: Type,
    vote_model: Type,
    entity_name: str,
    logger: Any,
) -> dict[str, Any]:
    """
    Get vote summary statistics for an entity.

    Args:
        db: Database session
        entity_id: ID of the entity
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        logger: Logger instance

    Returns:
        Dictionary with vote statistics
    """
    # Verify entity exists
    entity = db.query(entity_model).filter(entity_model.id == entity_id).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        from sqlalchemy import func

        # Get vote counts
        vote_counts = (
            db.query(vote_model.vote_type, func.count(vote_model.id).label("count"))
            .filter(**{f"{entity_name.lower().replace(' ', '_')}_id": entity_id})
            .group_by(vote_model.vote_type)
            .all()
        )

        # Calculate totals
        upvotes = 0
        downvotes = 0
        for vote_type, count in vote_counts:
            if vote_type == "upvote":
                upvotes = count
            elif vote_type == "downvote":
                downvotes = count

        total_votes = upvotes + downvotes
        score = upvotes - downvotes

        logger.info(f"Retrieved vote summary for {entity_name} {entity_id}")
        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "total_votes": total_votes,
            "score": score,
        }
    except Exception as e:
        logger.error(f"Failed to get vote summary: {e}")
        ResponsePatterns.raise_internal_server_error(f"Failed to get vote summary")


# Report-related patterns
def handle_report_creation(
    db: Session,
    user_id: int,
    entity_id: int,
    report_data: dict,
    entity_model: Type,
    report_model: Type,
    entity_name: str,
    logger: Any,
    additional_filters: Optional[dict] = None,
) -> Any:
    """
    Handle report creation with consistent patterns.

    Args:
        db: Database session
        user_id: ID of the user creating the report
        entity_id: ID of the entity being reported
        report_data: Report data dictionary
        entity_model: Model class for the entity
        report_model: Model class for the report
        entity_name: Human-readable name of the entity
        logger: Logger instance
        additional_filters: Additional filters for entity lookup

    Returns:
        The created report object
    """
    # Verify entity exists
    query = db.query(entity_model).filter(entity_model.id == entity_id)
    if additional_filters:
        for key, value in additional_filters.items():
            query = query.filter(getattr(entity_model, key) == value)

    entity = query.first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    # Check if user has already reported this entity
    existing_report = (
        db.query(report_model)
        .filter(
            report_model.user_id == user_id,
            **{f"{entity_name.lower().replace(' ', '_')}_id": entity_id},
        )
        .first()
    )

    if existing_report:
        ResponsePatterns.raise_conflict(f"User has already reported this {entity_name}")

    try:
        # Create new report
        new_report = report_model(
            user_id=user_id,
            **{f"{entity_name.lower().replace(' ', '_')}_id": entity_id},
            **report_data,
        )
        db.add(new_report)
        db.commit()
        db.refresh(new_report)

        logger.info(
            f"Report created: {new_report.id} by user {user_id} on {entity_name} {entity_id}"
        )
        return new_report
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create report: {e}")
        ResponsePatterns.raise_internal_server_error(f"Failed to create report")


def get_reports_by_entity(
    db: Session,
    entity_id: int,
    entity_model: Type,
    report_model: Type,
    entity_name: str,
    logger: Any,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
) -> List[Any]:
    """
    Get reports for a specific entity with pagination and filtering.

    Args:
        db: Database session
        entity_id: ID of the entity
        entity_model: Model class for the entity
        report_model: Model class for the report
        entity_name: Human-readable name of the entity
        logger: Logger instance
        skip: Number of reports to skip
        limit: Maximum number of reports to return
        status_filter: Optional status filter

    Returns:
        List of reports
    """
    # Verify entity exists
    entity = db.query(entity_model).filter(entity_model.id == entity_id).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        query = db.query(report_model).filter(
            **{f"{entity_name.lower().replace(' ', '_')}_id": entity_id}
        )

        if status_filter:
            query = query.filter(report_model.status == status_filter)

        reports = query.offset(skip).limit(limit).all()

        logger.info(f"Retrieved {len(reports)} reports for {entity_name} {entity_id}")
        return reports
    except Exception as e:
        logger.error(f"Failed to get reports: {e}")
        ResponsePatterns.raise_internal_server_error(f"Failed to get reports")


def update_report_status(
    db: Session,
    report_id: int,
    new_status: str,
    report_model: Type,
    logger: Any,
    admin_user_id: int,
    resolution_notes: Optional[str] = None,
) -> dict[str, str]:
    """
    Update report status with consistent patterns.

    Args:
        db: Database session
        report_id: ID of the report to update
        new_status: New status for the report
        report_model: Model class for the report
        logger: Logger instance
        admin_user_id: ID of the admin updating the report
        resolution_notes: Optional notes about the resolution

    Returns:
        Success message
    """
    report = db.query(report_model).filter(report_model.id == report_id).first()
    if not report:
        ResponsePatterns.raise_not_found("Report", report_id)

    try:
        report.status = new_status
        report.resolved_at = datetime.utcnow()
        report.resolved_by = admin_user_id

        if resolution_notes:
            report.resolution_notes = resolution_notes

        db.commit()

        logger.info(
            f"Report {report_id} status updated to {new_status} by admin {admin_user_id}"
        )
        return {"message": f"Report status updated to {new_status}"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update report status: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to update report status")
