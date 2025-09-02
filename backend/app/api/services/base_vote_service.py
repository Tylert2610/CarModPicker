"""
Base service class for voting operations to eliminate code duplication.
"""

import logging
from typing import TypeVar, Generic, Type, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from fastapi import HTTPException

from app.api.models.user import User as DBUser
from app.api.utils.common_operations import verify_entity_exists

# Generic types for different vote models and schemas
VoteModelType = TypeVar("VoteModelType")
VoteCreateSchema = TypeVar("VoteCreateSchema")
VoteReadSchema = TypeVar("VoteReadSchema")
EntityModelType = TypeVar("EntityModelType")


class BaseVoteService(
    Generic[VoteModelType, VoteCreateSchema, VoteReadSchema, EntityModelType]
):
    """
    Base service class for voting operations.

    This class provides common voting functionality for all entity types
    to eliminate code duplication across different vote endpoints.
    """

    def __init__(
        self,
        vote_model: Type[VoteModelType],
        entity_model: Type[EntityModelType],
        entity_name: str = "entity",
        vote_entity_id_field: str = "entity_id",
    ):
        """
        Initialize the base vote service.

        Args:
            vote_model: The SQLAlchemy vote model class
            entity_model: The SQLAlchemy entity model class being voted on
            entity_name: Human-readable name of the entity type
            vote_entity_id_field: Field name in vote model that references the entity
        """
        self.vote_model = vote_model
        self.entity_model = entity_model
        self.entity_name = entity_name
        self.vote_entity_id_field = vote_entity_id_field

    def vote_on_entity(
        self,
        db: Session,
        entity_id: int,
        user_id: int,
        vote_data: VoteCreateSchema,
        logger: logging.Logger,
    ) -> VoteModelType:
        """
        Vote on an entity (upvote or downvote).

        Args:
            db: Database session
            entity_id: ID of the entity being voted on
            user_id: ID of the user voting
            vote_data: Vote data (typically contains vote_type)
            logger: Logger instance

        Returns:
            The created or updated vote

        Raises:
            HTTPException: If entity not found or voting fails
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        # Check if user has already voted on this entity
        existing_vote = (
            db.query(self.vote_model)
            .filter(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
            .first()
        )

        if existing_vote:
            # Update existing vote
            existing_vote.vote_type = vote_data.vote_type.value
            db.commit()
            db.refresh(existing_vote)
            logger.info(
                f"Vote updated: {existing_vote.id} by user {user_id} on {self.entity_name} {entity_id}"
            )
            return existing_vote
        else:
            # Create new vote
            vote_data_dict = vote_data.model_dump()
            vote_data_dict["user_id"] = user_id
            vote_data_dict[self.vote_entity_id_field] = entity_id

            db_vote = self.vote_model(**vote_data_dict)
            db.add(db_vote)
            db.commit()
            db.refresh(db_vote)
            logger.info(
                f"Vote created: {db_vote.id} by user {user_id} on {self.entity_name} {entity_id}"
            )
            return db_vote

    def remove_vote(
        self,
        db: Session,
        entity_id: int,
        user_id: int,
        logger: logging.Logger,
    ) -> bool:
        """
        Remove user's vote on an entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            user_id: ID of the user
            logger: Logger instance

        Returns:
            True if vote was removed, False if no vote existed

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        # Find and delete the vote
        existing_vote = (
            db.query(self.vote_model)
            .filter(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
            .first()
        )

        if existing_vote:
            db.delete(existing_vote)
            db.commit()
            logger.info(
                f"Vote removed: {existing_vote.id} by user {user_id} on {self.entity_name} {entity_id}"
            )
            return True
        else:
            logger.info(
                f"No vote found for user {user_id} on {self.entity_name} {entity_id}"
            )
            return False

    def get_vote_summary(
        self,
        db: Session,
        entity_id: int,
        logger: logging.Logger,
    ) -> Dict[str, Any]:
        """
        Get vote summary for an entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance

        Returns:
            Dictionary with vote counts and summary

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        # Get vote counts
        upvotes = (
            db.query(func.count(self.vote_model.id))
            .filter(
                and_(
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                    self.vote_model.vote_type == "upvote",
                )
            )
            .scalar()
        )

        downvotes = (
            db.query(func.count(self.vote_model.id))
            .filter(
                and_(
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                    self.vote_model.vote_type == "downvote",
                )
            )
            .scalar()
        )

        total_votes = upvotes + downvotes
        score = upvotes - downvotes

        logger.info(
            f"Vote summary for {self.entity_name} {entity_id}: upvotes={upvotes}, downvotes={downvotes}, score={score}"
        )

        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "total_votes": total_votes,
            "score": score,
        }

    def get_user_vote(
        self,
        db: Session,
        entity_id: int,
        user_id: int,
        logger: logging.Logger,
    ) -> Optional[VoteModelType]:
        """
        Get a user's vote on a specific entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            user_id: ID of the user
            logger: Logger instance

        Returns:
            The user's vote or None if no vote exists
        """
        vote = (
            db.query(self.vote_model)
            .filter(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
            .first()
        )

        if vote:
            logger.debug(
                f"User {user_id} vote on {self.entity_name} {entity_id}: {vote.vote_type}"
            )
        else:
            logger.debug(
                f"No vote found for user {user_id} on {self.entity_name} {entity_id}"
            )

        return vote
