"""
Base vote router with common patterns to reduce redundancy.
"""

from typing import TypeVar, Generic, Type, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.user import User as DBUser
from app.api.services.base_vote_service import BaseVoteService
from app.core.logging import get_logger
from app.db.session import get_db

# Generic types
VoteModelType = TypeVar("VoteModelType")
VoteCreateSchema = TypeVar("VoteCreateSchema")
VoteReadSchema = TypeVar("VoteReadSchema")
EntityModelType = TypeVar("EntityModelType")


class BaseVoteRouter(
    Generic[VoteModelType, VoteCreateSchema, VoteReadSchema, EntityModelType]
):
    """
    Base vote router that provides common voting endpoint patterns.

    This class eliminates redundancy by providing standardized implementations
    for common voting operations like vote, remove vote, and get vote summary.
    """

    def __init__(
        self,
        service: BaseVoteService[
            VoteModelType, VoteCreateSchema, VoteReadSchema, EntityModelType
        ],
        router: APIRouter,
        entity_name: str = "entity",
        vote_entity_id_param: str = "entity_id",
    ):
        """
        Initialize the base vote router.

        Args:
            service: Vote service instance
            router: FastAPI router instance
            entity_name: Human-readable name of the entity type
            vote_entity_id_param: URL parameter name for the entity ID
        """
        self.service = service
        self.router = router
        self.entity_name = entity_name
        self.vote_entity_id_param = vote_entity_id_param

        # Register common vote endpoints
        self._register_common_vote_endpoints()

    def _register_common_vote_endpoints(self):
        """Register common voting endpoints."""

        # Vote on entity endpoint
        @self.router.post(
            f"/{{{self.vote_entity_id_param}}}/vote",
            response_model=VoteReadSchema,
            responses={
                400: {"description": f"Invalid vote data"},
                404: {"description": f"{self.entity_name.title()} not found"},
                409: {"description": "User has already voted on this entity"},
            },
        )
        async def vote_on_entity(
            entity_id: int,
            vote: VoteCreateSchema,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> VoteModelType:
            """Vote on an entity (upvote or downvote)."""
            return self.service.vote_on_entity(
                db=db,
                entity_id=entity_id,
                user_id=current_user.id,
                vote_data=vote,
                logger=logger,
            )

        # Remove vote endpoint
        @self.router.delete(
            f"/{{{self.vote_entity_id_param}}}/vote",
            responses={
                404: {
                    "description": f"{self.entity_name.title()} not found or no vote exists"
                },
            },
        )
        async def remove_vote(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> Dict[str, str]:
            """Remove user's vote on an entity."""
            removed = self.service.remove_vote(
                db=db,
                entity_id=entity_id,
                user_id=current_user.id,
                logger=logger,
            )

            if removed:
                return {"message": f"Vote removed successfully from {self.entity_name}"}
            else:
                return {"message": f"No vote found to remove from {self.entity_name}"}

        # Get vote summary endpoint
        @self.router.get(
            f"/{{{self.vote_entity_id_param}}}/vote-summary",
            responses={
                200: {
                    "description": f"Vote summary for {self.entity_name} retrieved successfully"
                },
                404: {"description": f"{self.entity_name.title()} not found"},
            },
        )
        async def get_vote_summary(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
        ) -> Dict[str, Any]:
            """Get vote summary for an entity."""
            return self.service.get_vote_summary(
                db=db,
                entity_id=entity_id,
                logger=logger,
            )

        # Get user's vote on entity endpoint
        @self.router.get(
            f"/{{{self.vote_entity_id_param}}}/my-vote",
            response_model=VoteReadSchema,
            responses={
                200: {
                    "description": f"User's vote on {self.entity_name} retrieved successfully"
                },
                404: {
                    "description": f"{self.entity_name.title()} not found or no vote exists"
                },
            },
        )
        async def get_my_vote(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> VoteModelType:
            """Get the current user's vote on a specific entity."""
            vote = self.service.get_user_vote(
                db=db,
                entity_id=entity_id,
                user_id=current_user.id,
                logger=logger,
            )

            if not vote:
                raise HTTPException(
                    status_code=404,
                    detail=f"You have not voted on this {self.entity_name}",
                )

            return vote

    def add_custom_vote_endpoint(
        self,
        path: str,
        response_model: Type[VoteReadSchema],
        method: str = "get",
        **kwargs,
    ):
        """
        Add a custom vote endpoint to the router.

        Args:
            path: URL path for the endpoint
            response_model: Response model for the endpoint
            method: HTTP method (get, post, put, delete)
            **kwargs: Additional FastAPI endpoint parameters
        """

        def decorator(func):
            if method.lower() == "get":
                self.router.get(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "post":
                self.router.post(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "put":
                self.router.put(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "delete":
                self.router.delete(path, **kwargs)(func)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            return func

        return decorator
