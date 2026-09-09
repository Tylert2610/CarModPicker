"""
Unified vote service for all entity types.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.vote import (
    EntityType,
    FlaggedEntitySummary,
    VoteCreate,
    VoteSummary,
)
from app.db.dynamo.build_lists import BuildList as DBBuildList
from app.db.dynamo.catalog import CarGeneration, Part
from app.db.dynamo.moderation import DOWNVOTE, Vote
from app.db.dynamo.repository import ItemNotFound
from app.db.dynamo.tombstones import drop_tombstoned_values

VotableEntity = Union[CarGeneration, DBBuildList, Part]

FLAG_MIN_VOTES = 5
FLAG_DOWNVOTE_RATIO = 0.3
FLAG_RECENT_DOWNVOTES = 3
FLAG_RECENT_WINDOW = timedelta(days=7)


class VoteService:
    """
    Unified vote service for all entity types.

    This service handles voting operations for cars, build lists, and global parts
    using the unified Vote model in DynamoDB.
    """

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Initialize the unified vote service."""
        self.repos = repos or get_repositories()

    def vote_on_entity(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
        vote_data: VoteCreate,
        logger: logging.Logger,
    ) -> Vote:
        """
        Vote on an entity (car, build list, or global part).

        Returns the created or updated vote; raises 404 if the entity doesn't exist.
        """
        self._get_entity_or_404(entity_type, entity_id)

        existing_vote = self.repos.votes.get_user_vote(entity_type.value, entity_id, user_id)
        if existing_vote:
            vote = self.repos.votes.update(existing_vote.id, vote_type=vote_data.vote_type.value)
            self._sync_part_net_votes(entity_type, entity_id)
            logger.info(f"Vote updated: {vote.id} by user {user_id} on {entity_type.value} {entity_id}")
            return vote

        vote = self.repos.votes.create(
            Vote(
                user_id=user_id,
                entity_type=entity_type.value,
                entity_id=entity_id,
                vote_type=vote_data.vote_type.value,
            )
        )
        self._sync_part_net_votes(entity_type, entity_id)
        logger.info(f"Vote created: {vote.id} by user {user_id} on {entity_type.value} {entity_id}")
        return vote

    def remove_vote(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
        logger: logging.Logger,
    ) -> bool:
        """Remove a vote from an entity. Returns True if a vote was removed."""
        vote = self.repos.votes.get_user_vote(entity_type.value, entity_id, user_id)
        if vote is None:
            return False
        self.repos.votes.delete(vote.id)
        self._sync_part_net_votes(entity_type, entity_id)
        logger.info(f"Vote removed: {vote.id} by user {user_id} on {entity_type.value} {entity_id}")
        return True

    def get_user_vote(self, entity_type: EntityType, entity_id: UUID, user_id: UUID) -> Vote | None:
        return self.repos.votes.get_user_vote(entity_type.value, entity_id, user_id)

    def get_vote_summary(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: Optional[UUID] = None,
        logger: Optional[logging.Logger] = None,
    ) -> VoteSummary:
        """Vote summary for an entity; raises 404 if the entity doesn't exist."""
        self._get_entity_or_404(entity_type, entity_id)

        upvotes, downvotes = self.repos.votes.counts(entity_type.value, entity_id)
        user_vote = None
        if user_id:
            user_vote_obj = self.repos.votes.get_user_vote(entity_type.value, entity_id, user_id)
            user_vote = user_vote_obj.vote_type if user_vote_obj else None

        return VoteSummary(
            entity_id=entity_id,
            entity_type=entity_type.value,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=upvotes + downvotes,
            vote_score=upvotes - downvotes,
            user_vote=user_vote,
        )

    def get_flagged_entities(
        self,
        entity_type: EntityType,
        limit: int = 50,
        logger: Optional[logging.Logger] = None,
    ) -> List[FlaggedEntitySummary]:
        """
        Entities of one type with at least five votes whose downvote ratio is 0.3 or
        more, or which received three or more downvotes in the last seven days.
        Sorted by downvote ratio then recent downvotes, both descending.
        """
        now = datetime.now(UTC)
        recent_cutoff = now - FLAG_RECENT_WINDOW

        votes_by_entity: dict[UUID, list[Vote]] = {}
        for vote in self.repos.votes.all_of_type(entity_type.value):
            votes_by_entity.setdefault(vote.entity_id, []).append(vote)

        stats: list[tuple[UUID, int, int, int, float]] = []
        for entity_id, votes in votes_by_entity.items():
            total = len(votes)
            if total < FLAG_MIN_VOTES:
                continue
            downvotes = sum(1 for vote in votes if vote.vote_type == DOWNVOTE)
            upvotes = total - downvotes
            recent_downvotes = sum(
                1 for vote in votes if vote.vote_type == DOWNVOTE and _aware(vote.created_at) >= recent_cutoff
            )
            ratio = downvotes / total if total else 0.0
            if ratio >= FLAG_DOWNVOTE_RATIO or recent_downvotes >= FLAG_RECENT_DOWNVOTES:
                stats.append((entity_id, upvotes, downvotes, recent_downvotes, ratio))

        stats.sort(key=lambda row: (row[4], row[3]), reverse=True)
        stats = stats[:limit]

        ids = [row[0] for row in stats]
        entities = self._get_entities(entity_type, ids)
        reported = self.repos.reports.entities_with_reports(entity_type.value, ids)

        flagged: List[FlaggedEntitySummary] = []
        for entity_id, upvotes, downvotes, recent_downvotes, ratio in stats:
            entity = entities.get(entity_id)
            if entity is None:
                continue
            flagged.append(
                FlaggedEntitySummary(
                    entity_id=entity.id,
                    entity_type=entity_type.value,
                    entity_name=self._get_entity_name(entity, entity_type),
                    entity_description=getattr(entity, "description", None),
                    upvotes=upvotes,
                    downvotes=downvotes,
                    total_votes=upvotes + downvotes,
                    vote_score=upvotes - downvotes,
                    downvote_ratio=ratio,
                    recent_downvotes=recent_downvotes,
                    has_reports=entity_id in reported,
                    created_at=entity.created_at,
                    flagged_at=now,
                )
            )
        return flagged

    def _sync_part_net_votes(self, entity_type: EntityType, entity_id: UUID) -> None:
        if entity_type != EntityType.PART:
            return
        upvotes, downvotes = self.repos.votes.counts(entity_type.value, entity_id)
        try:
            self.repos.parts.update(str(entity_id), net_votes=upvotes - downvotes)
        except ItemNotFound:
            return

    def _get_entities(self, entity_type: EntityType, ids: List[Any]) -> dict[UUID, VotableEntity]:
        if not ids:
            return {}
        if entity_type == EntityType.BUILD_LIST:
            return dict(self.repos.build_lists.get_many(ids))
        if entity_type == EntityType.CAR_GENERATION:
            return dict(self.repos.car_generations.get_many(ids))
        if entity_type == EntityType.PART:
            # Both vote paths funnel through here: `_get_entity_or_404` (which
            # turns a dropped part into its existing 404) and the flagged-entity
            # listing (which already skips ids that resolve to nothing). Filtering
            # once covers both. `get_many` is a `batch_get`, so this is a Python
            # filter rather than a filter expression.
            return dict(drop_tombstoned_values(self.repos.parts.get_many(ids)))
        raise ValueError(f"Unknown entity type: {entity_type}")

    def _get_entity_or_404(self, entity_type: EntityType, entity_id: UUID) -> VotableEntity:
        entity = self._get_entities(entity_type, [entity_id]).get(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{entity_type.value.title()} not found")
        return entity

    def _get_entity_name(self, entity: VotableEntity, entity_type: EntityType) -> str:
        """Get the display name for an entity."""
        if isinstance(entity, CarGeneration):
            from app.api.services.car_generation_service import CarGenerationService

            read = CarGenerationService(self.repos).hydrate_one(entity)
            return (
                f"{read.car_make_name} {read.car_model_name} {read.generation_name} ({read.start_year}-{read.end_year})"
            )
        return str(entity.name)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
