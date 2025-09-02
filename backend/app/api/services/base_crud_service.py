"""
Base service class for CRUD operations to eliminate code duplication.
"""

import logging
from typing import List, Optional, TypeVar, Generic, Dict, Any, Type
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.api.models.user import User as DBUser
from app.api.utils.common_operations import (
    verify_entity_exists,
    verify_entity_ownership,
    verify_entity_access,
    create_entity,
    update_entity,
    delete_entity,
    get_entities_with_pagination,
    check_subscription_limits,
    validate_pagination_params,
)

# Generic types for different models and schemas
ModelType = TypeVar("ModelType")
CreateSchema = TypeVar("CreateSchema")
ReadSchema = TypeVar("ReadSchema")
UpdateSchema = TypeVar("UpdateSchema")


class BaseCRUDService(Generic[ModelType, CreateSchema, ReadSchema, UpdateSchema]):
    """
    Base service class for CRUD operations.

    This class provides common CRUD functionality for all entity types
    to eliminate code duplication across different endpoints.
    """

    def __init__(
        self,
        model: Type[ModelType],
        entity_name: str = "entity",
        subscription_check_method: Optional[str] = None,
    ):
        """
        Initialize the base CRUD service.

        Args:
            model: The SQLAlchemy model class
            entity_name: Human-readable name of the entity type
            subscription_check_method: Method name to call on SubscriptionService for limits
        """
        self.model = model
        self.entity_name = entity_name
        self.subscription_check_method = subscription_check_method

    def create(
        self,
        db: Session,
        data: CreateSchema,
        current_user: DBUser,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Create a new entity.

        Args:
            db: Database session
            data: Entity creation data
            current_user: Current authenticated user
            logger: Logger instance
            additional_data: Additional data to include (e.g., user_id)

        Returns:
            The created entity

        Raises:
            HTTPException: If creation fails or subscription limit reached
        """
        # Check subscription limits if method is specified
        if self.subscription_check_method:
            check_subscription_limits(
                db,
                current_user,
                self.subscription_check_method,
                self.entity_name,
                logger,
            )

        # Prepare data for creation
        entity_data = data.model_dump()
        if additional_data:
            entity_data.update(additional_data)

        return create_entity(
            db=db,
            model=self.model,
            data=entity_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def get_by_id(
        self,
        db: Session,
        entity_id: int,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> ModelType:
        """
        Get an entity by ID.

        Args:
            db: Database session
            entity_id: ID of the entity
            current_user: Current authenticated user (optional)
            allow_public: Whether to allow public access
            logger: Logger instance (optional)

        Returns:
            The found entity

        Raises:
            HTTPException: If entity not found or access denied
        """
        if current_user and not allow_public:
            entity = verify_entity_access(
                db, self.model, entity_id, current_user, self.entity_name, allow_public
            )
        else:
            entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)

        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id}")

        return entity

    def get_by_user(
        self,
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ModelType]:
        """
        Get entities owned by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of entities
        """
        validate_pagination_params(skip, limit)

        filters = {"user_id": user_id}
        entities = get_entities_with_pagination(
            db=db,
            model=self.model,
            skip=skip,
            limit=limit,
            filters=filters,
            logger=logger,
        )

        return entities

    def list_all(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        order_by: str = "created_at",
        order_direction: str = "desc",
        logger: Optional[logging.Logger] = None,
    ) -> List[ModelType]:
        """
        List all entities with pagination, filtering, and search.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field names and values to filter by
            search: Search term to look for
            search_fields: List of field names to search in
            order_by: Field to order by
            order_direction: Order direction ('asc' or 'desc')
            logger: Logger instance (optional)

        Returns:
            List of entities
        """
        validate_pagination_params(skip, limit)

        entities = get_entities_with_pagination(
            db=db,
            model=self.model,
            skip=skip,
            limit=limit,
            filters=filters,
            search=search,
            search_fields=search_fields,
            order_by=order_by,
            order_direction=order_direction,
            logger=logger,
        )

        return entities

    def update(
        self,
        db: Session,
        entity_id: int,
        data: UpdateSchema,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> ModelType:
        """
        Update an existing entity.

        Args:
            db: Database session
            entity_id: ID of the entity to update
            data: Entity update data
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            The updated entity

        Raises:
            HTTPException: If entity not found, access denied, or update fails
        """
        # Verify ownership
        entity = verify_entity_ownership(
            db, self.model, entity_id, current_user, self.entity_name
        )

        # Update the entity
        update_data = data.model_dump(exclude_unset=True)
        return update_entity(
            db=db,
            entity=entity,
            update_data=update_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def delete(
        self,
        db: Session,
        entity_id: int,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> Dict[str, str]:
        """
        Delete an entity.

        Args:
            db: Database session
            entity_id: ID of the entity to delete
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            Success message

        Raises:
            HTTPException: If entity not found, access denied, or deletion fails
        """
        # Verify ownership
        entity = verify_entity_ownership(
            db, self.model, entity_id, current_user, self.entity_name
        )

        # Delete the entity
        return delete_entity(
            db=db,
            entity=entity,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def count_by_user(
        self, db: Session, user_id: int, logger: Optional[logging.Logger] = None
    ) -> int:
        """
        Count entities owned by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            logger: Logger instance (optional)

        Returns:
            Count of entities
        """
        count = db.query(self.model).filter(self.model.user_id == user_id).count()

        if logger:
            logger.info(f"Counted {count} {self.entity_name}s for user {user_id}")

        return count

    def exists(
        self, db: Session, entity_id: int, logger: Optional[logging.Logger] = None
    ) -> bool:
        """
        Check if an entity exists.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance (optional)

        Returns:
            True if entity exists, False otherwise
        """
        exists = (
            db.query(self.model).filter(self.model.id == entity_id).first() is not None
        )

        if logger:
            logger.info(f"Entity {self.entity_name} {entity_id} exists: {exists}")

        return exists

    def get_with_relations(
        self,
        db: Session,
        entity_id: int,
        relations: List[str],
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> ModelType:
        """
        Get an entity with related data loaded.

        Args:
            db: Database session
            entity_id: ID of the entity
            relations: List of relation names to load
            current_user: Current authenticated user (optional)
            allow_public: Whether to allow public access
            logger: Logger instance (optional)

        Returns:
            The found entity with relations loaded

        Raises:
            HTTPException: If entity not found or access denied
        """
        # Build query with relations
        query = db.query(self.model)
        for relation in relations:
            if hasattr(self.model, relation):
                query = query.options(db.joinedload(getattr(self.model, relation)))

        # Get entity
        entity = query.filter(self.model.id == entity_id).first()
        if not entity:
            raise HTTPException(
                status_code=404, detail=f"{self.entity_name.title()} not found"
            )

        # Check access if user is provided
        if current_user and not allow_public:
            if hasattr(entity, "user_id") and entity.user_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail=f"Not authorized to access this {self.entity_name}",
                )

        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id} with relations")

        return entity
