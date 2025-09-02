"""
Base endpoint router with common patterns to reduce redundancy.
"""

from typing import List, Optional, Type, TypeVar, Generic, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.user import User as DBUser
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger
from app.db.session import get_db

# Generic types
ModelType = TypeVar("ModelType")
CreateSchema = TypeVar("CreateSchema")
ReadSchema = TypeVar("ReadSchema")
UpdateSchema = TypeVar("UpdateSchema")


class BaseEndpointRouter(Generic[ModelType, CreateSchema, ReadSchema, UpdateSchema]):
    """
    Base endpoint router that provides common CRUD endpoint patterns.

    This class eliminates redundancy by providing standardized implementations
    for common operations like create, read, update, delete, and list.
    """

    def __init__(
        self,
        service: BaseCRUDService[ModelType, CreateSchema, ReadSchema, UpdateSchema],
        router: APIRouter,
        entity_name: str = "entity",
        allow_public_read: bool = False,
        additional_create_data: Optional[Dict[str, Any]] = None,
        disable_endpoints: Optional[List[str]] = None,
    ):
        """
        Initialize the base endpoint router.

        Args:
            service: CRUD service instance
            router: FastAPI router instance
            entity_name: Human-readable name of the entity type
            allow_public_read: Whether to allow public read access
            additional_create_data: Additional data to include when creating entities
            disable_endpoints: List of endpoint names to disable (e.g., ["list", "create"])
        """
        self.service = service
        self.router = router
        self.entity_name = entity_name
        self.allow_public_read = allow_public_read
        self.additional_create_data = additional_create_data or {}
        self.disable_endpoints = disable_endpoints or []

        # Register common endpoints
        self._register_common_endpoints()

    def _register_common_endpoints(self):
        """Register common CRUD endpoints."""

        # Create endpoint
        @self.router.post(
            "/",
            response_model=ReadSchema,
            responses={
                400: {"description": f"Invalid {self.entity_name} data"},
                403: {"description": f"Not authorized to create {self.entity_name}"},
                402: {"description": "Subscription limit reached"},
            },
        )
        async def create_entity(
            data: CreateSchema,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> ModelType:
            """Create a new entity."""
            return self.service.create(
                db=db,
                data=data,
                current_user=current_user,
                logger=logger,
                additional_data=self.additional_create_data,
            )

        # Get by ID endpoint
        if self.allow_public_read:

            @self.router.get(
                "/{entity_id}",
                response_model=ReadSchema,
                responses={
                    404: {"description": f"{self.entity_name.title()} not found"},
                },
            )
            async def get_entity_public(
                entity_id: int,
                db: Session = Depends(get_db),
                logger=Depends(get_logger),
            ) -> ModelType:
                """Get an entity by ID (public access)."""
                return self.service.get_by_id(
                    db=db,
                    entity_id=entity_id,
                    current_user=None,
                    allow_public=True,
                    logger=logger,
                )

        else:

            @self.router.get(
                "/{entity_id}",
                response_model=ReadSchema,
                responses={
                    404: {"description": f"{self.entity_name.title()} not found"},
                    403: {
                        "description": f"Not authorized to access this {self.entity_name}"
                    },
                },
            )
            async def get_entity_private(
                entity_id: int,
                db: Session = Depends(get_db),
                logger=Depends(get_logger),
                current_user: DBUser = Depends(get_current_user),
            ) -> ModelType:
                """Get an entity by ID (private access)."""
                return self.service.get_by_id(
                    db=db,
                    entity_id=entity_id,
                    current_user=current_user,
                    allow_public=False,
                    logger=logger,
                )

        # List all endpoint
        if "list" not in self.disable_endpoints:

            @self.router.get(
                "/",
                response_model=List[ReadSchema],
                responses={
                    200: {
                        "description": f"List of {self.entity_name}s retrieved successfully"
                    },
                },
            )
            async def list_entities(
                skip: int = Query(
                    0, ge=0, description=f"Number of {self.entity_name}s to skip"
                ),
                limit: int = Query(
                    100,
                    ge=1,
                    le=1000,
                    description=f"Maximum number of {self.entity_name}s to return",
                ),
                search: Optional[str] = Query(
                    None,
                    description=f"Search in {self.entity_name} names and descriptions",
                ),
                db: Session = Depends(get_db),
                logger=Depends(get_logger),
            ) -> List[ModelType]:
                """List all entities with pagination and search."""
                return self.service.list_all(
                    db=db,
                    skip=skip,
                    limit=limit,
                    search=search,
                    search_fields=self._get_search_fields(),
                    logger=logger,
                )

        # Update endpoint
        @self.router.put(
            "/{entity_id}",
            response_model=ReadSchema,
            responses={
                404: {"description": f"{self.entity_name.title()} not found"},
                403: {
                    "description": f"Not authorized to update this {self.entity_name}"
                },
            },
        )
        async def update_entity(
            entity_id: int,
            data: UpdateSchema,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> ModelType:
            """Update an existing entity."""
            return self.service.update(
                db=db,
                entity_id=entity_id,
                data=data,
                current_user=current_user,
                logger=logger,
            )

        # Delete endpoint
        @self.router.delete(
            "/{entity_id}",
            response_model=Dict[str, str],
            responses={
                404: {"description": f"{self.entity_name.title()} not found"},
                403: {
                    "description": f"Not authorized to delete this {self.entity_name}"
                },
            },
        )
        async def delete_entity(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> Dict[str, str]:
            """Delete an entity."""
            self.service.delete(
                db=db,
                entity_id=entity_id,
                current_user=current_user,
                logger=logger,
            )
            return {"message": f"{self.entity_name.title()} deleted successfully"}

    def _get_search_fields(self) -> List[str]:
        """Get search fields for the entity. Override in subclasses if needed."""
        return ["name", "description"]

    def add_filter_endpoint(self, filter_name: str, filter_field: str):
        """
        Add a filter endpoint for a specific field.

        Args:
            filter_name: Name of the filter (used in URL)
            filter_field: Database field name to filter on
        """

        @self.router.get(
            f"/{filter_name}/{{{filter_name}_id}}",
            response_model=List[ReadSchema],
            responses={
                200: {
                    "description": f"List of {self.entity_name}s filtered by {filter_name} retrieved successfully"
                },
            },
        )
        async def filter_entities(
            filter_id: int,
            skip: int = Query(
                0, ge=0, description=f"Number of {self.entity_name}s to skip"
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description=f"Maximum number of {self.entity_name}s to return",
            ),
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
        ) -> List[ModelType]:
            """Filter entities by a specific field."""
            return self.service.filter_by_field(
                db=db,
                field_name=filter_field,
                field_value=filter_id,
                skip=skip,
                limit=limit,
                logger=logger,
            )

    def add_count_endpoint(self):
        """Add a count endpoint for the entity."""

        @self.router.get(
            "/count",
            response_model=Dict[str, int],
            responses={
                200: {"description": f"Count of {self.entity_name}s"},
            },
        )
        async def count_entities(
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
        ) -> Dict[str, int]:
            """Get total count of entities."""
            count = self.service.count_all(db=db, logger=logger)
            return {"count": count}
