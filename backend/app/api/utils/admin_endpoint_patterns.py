"""
Standardized admin endpoint patterns to reduce redundancy.

This module provides common patterns for admin-only endpoints including
authentication, authorization, and response handling.
"""

from typing import List, TypeVar, Generic, Type, Optional, Any
from functools import wraps
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.user import User as DBUser
from app.api.utils.endpoint_decorators import crud_responses, validate_pagination_params
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db

# Generic types
ModelType = TypeVar("ModelType")
ReadSchema = TypeVar("ReadSchema")
UpdateSchema = TypeVar("UpdateSchema")


def admin_list_endpoint(
    router: APIRouter,
    entity_name: str,
    model: Type[ModelType],
    response_model: Type[List[ReadSchema]],
    allow_public_read: bool = False,
) -> Any:
    """
    Create a standardized admin list endpoint.

    Args:
        router: FastAPI router instance
        entity_name: Human-readable name of the entity
        model: SQLAlchemy model class
        response_model: Pydantic response model for list
        allow_public_read: Whether to allow public read access

    Returns:
        Decorated endpoint function
    """

    def decorator(func):
        @router.get(
            f"/admin/{entity_name.replace(' ', '-')}s",
            response_model=response_model,
            responses=crud_responses(
                entity_name, "list", allow_public_read=allow_public_read
            ),
        )
        @wraps(func)
        async def wrapper(
            skip: int = Query(0, ge=0, description=f"Number of {entity_name}s to skip"),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description=f"Maximum number of {entity_name}s to return",
            ),
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_admin_user),
        ) -> List[ModelType]:
            """Get all entities (admin only)."""
            skip, limit = validate_pagination_params(skip=skip, limit=limit)
            entities = db.query(model).offset(skip).limit(limit).all()
            logger.info(
                f"Admin {current_user.id} retrieved {len(entities)} {entity_name}s"
            )
            return (
                func(entities, db, logger, current_user)
                if func != admin_list_endpoint
                else entities
            )

        return wrapper

    return decorator


def admin_update_endpoint(
    router: APIRouter,
    entity_name: str,
    model: Type[ModelType],
    response_model: Type[ReadSchema],
    update_schema: Type[UpdateSchema],
) -> Any:
    """
    Create a standardized admin update endpoint.

    Args:
        router: FastAPI router instance
        entity_name: Human-readable name of the entity
        model: SQLAlchemy model class
        response_model: Pydantic response model
        update_schema: Pydantic update schema

    Returns:
        Decorated endpoint function
    """

    def decorator(func):
        @router.put(
            f"/admin/{entity_name.replace(' ', '-')}s/{{entity_id}}",
            response_model=response_model,
            responses=crud_responses(entity_name, "update"),
        )
        @wraps(func)
        async def wrapper(
            entity_id: int,
            update_data: update_schema,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_admin_user),
        ) -> ModelType:
            """Update an entity with admin privileges (admin only)."""
            db_entity = db.query(model).filter(model.id == entity_id).first()
            if db_entity is None:
                ResponsePatterns.raise_not_found(entity_name.title(), entity_id)

            return func(db_entity, update_data, db, logger, current_user)

        return wrapper

    return decorator


def admin_delete_endpoint(
    router: APIRouter,
    entity_name: str,
    model: Type[ModelType],
    response_model: Type[ReadSchema],
) -> Any:
    """
    Create a standardized admin delete endpoint.

    Args:
        router: FastAPI router instance
        entity_name: Human-readable name of the entity
        model: SQLAlchemy model class
        response_model: Pydantic response model

    Returns:
        Decorated endpoint function
    """

    def decorator(func):
        @router.delete(
            f"/admin/{entity_name.replace(' ', '-')}s/{{entity_id}}",
            response_model=response_model,
            responses=crud_responses(entity_name, "delete"),
        )
        @wraps(func)
        async def wrapper(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_admin_user),
        ) -> ModelType:
            """Delete an entity with admin privileges (admin only)."""
            db_entity = db.query(model).filter(model.id == entity_id).first()
            if db_entity is None:
                ResponsePatterns.raise_not_found(entity_name.title(), entity_id)

            return func(db_entity, db, logger, current_user)

        return wrapper

    return decorator


def prevent_self_modification(
    entity_id: int,
    current_user: DBUser,
    operation: str = "modify",
    entity_name: str = "entity",
) -> None:
    """
    Prevent users from modifying their own admin privileges.

    Args:
        entity_id: ID of the entity being modified
        current_user: Current authenticated user
        operation: Description of the operation being prevented
        entity_name: Name of the entity type
    """
    if entity_id == current_user.id:
        ResponsePatterns.raise_bad_request(f"Cannot {operation} your own {entity_name}")
