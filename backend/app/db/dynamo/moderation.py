"""Votes and reports on DynamoDB, polymorphic over ``entity_type`` / ``entity_id``.

``entity_key`` is derived from that pair at write time, so one GSI answers
"everything about this entity" with ``user_id`` as its range key.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from boto3.dynamodb.conditions import Attr
from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository, RangeCondition
from app.db.dynamo.serialization import composite_key
from app.db.dynamo.tables import REPORTS, VOTES

ENTITY_INDEX = "entity_key-user_id-index"
USER_INDEX = "user_id-created_at-index"
STATUS_INDEX = "status-created_at-index"

UPVOTE = "upvote"
DOWNVOTE = "downvote"


class Vote(TimestampedDynamoModel):
    """One user's vote on one entity (car generation, build list or part)."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    entity_type: str
    entity_id: UUID
    vote_type: str


class Report(TimestampedDynamoModel):
    """A user's report of a build list or part for admin review."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    entity_type: str
    entity_id: UUID
    reason: str
    description: str | None = None
    status: str = "pending"
    admin_notes: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None


def _entity_key(entity_type: str, entity_id: UUID) -> str:
    """The composite key identifying one entity across the polymorphic tables."""
    return composite_key(entity_type, entity_id)


class VoteRepository(DynamoRepository[Vote]):
    """Votes on any entity type, with one vote per user and entity."""

    def __init__(self) -> None:
        """Bind to the votes table."""
        super().__init__(Vote, VOTES)

    def for_entity(self, entity_type: str, entity_id: UUID) -> list[Vote]:
        """Every vote on one entity."""
        return self.query_all(ENTITY_INDEX, _entity_key(entity_type, entity_id))

    def get_user_vote(self, entity_type: str, entity_id: UUID, user_id: UUID) -> Vote | None:
        """This user's vote on this entity, or None."""
        page = self.query(
            ENTITY_INDEX, _entity_key(entity_type, entity_id), range_condition=RangeCondition.eq(user_id), limit=1
        )
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[Vote]:
        """Every vote this user has cast."""
        return self.query_all(USER_INDEX, user_id)

    def for_entities(self, entity_type: str, entity_ids: Iterable[UUID]) -> dict[UUID, list[Vote]]:
        """The votes on each of these entities, keyed by entity id."""
        votes: dict[UUID, list[Vote]] = defaultdict(list)
        for entity_id in set(entity_ids):
            votes[entity_id] = self.for_entity(entity_type, entity_id)
        return dict(votes)

    def counts(self, entity_type: str, entity_id: UUID) -> tuple[int, int]:
        """``(upvotes, downvotes)`` for one entity."""
        votes = self.for_entity(entity_type, entity_id)
        return _tally(votes)

    def tallies(self, entity_type: str, entity_ids: Iterable[UUID]) -> tuple[dict[UUID, int], dict[UUID, int]]:
        """Per-entity ``(upvotes, downvotes)`` maps; entities without votes are absent."""
        upvotes: dict[UUID, int] = {}
        downvotes: dict[UUID, int] = {}
        for entity_id, votes in self.for_entities(entity_type, entity_ids).items():
            up, down = _tally(votes)
            if up:
                upvotes[entity_id] = up
            if down:
                downvotes[entity_id] = down
        return upvotes, downvotes

    def user_votes(self, entity_type: str, entity_ids: Iterable[UUID], user_id: UUID) -> dict[UUID, str]:
        """``entity_id -> vote_type`` for the entities this user has voted on."""
        ids = set(entity_ids)
        return {
            vote.entity_id: vote.vote_type
            for vote in self.list_by_user(user_id)
            if vote.entity_type == entity_type and vote.entity_id in ids
        }

    def all_of_type(self, entity_type: str) -> list[Vote]:
        """Every vote on entities of this type."""
        return self.scan_all(filter_expression=Attr("entity_type").eq(entity_type))

    def count(self) -> int:
        """How many votes exist."""
        return len(self.scan_all())

    def count_by_entity_type(self) -> dict[str, int]:
        """How many votes exist per entity type."""
        counts: dict[str, int] = defaultdict(int)
        for vote in self.scan_all():
            counts[vote.entity_type] += 1
        return dict(counts)

    def delete_for_entities(self, entity_type: str, entity_ids: Iterable[UUID]) -> int:
        """Delete every vote on these entities, returning how many were removed."""
        keys = [str(vote.id) for votes in self.for_entities(entity_type, entity_ids).values() for vote in votes]
        if keys:
            self.batch_delete(keys)
        return len(keys)

    def delete_for_entity_type(self, entity_type: str) -> int:
        """Delete every vote on entities of this type, returning how many were removed."""
        keys = [str(vote.id) for vote in self.all_of_type(entity_type)]
        if keys:
            self.batch_delete(keys)
        return len(keys)

    def delete_for_user(self, user_id: UUID) -> int:
        """Delete every vote this user cast, returning how many were removed."""
        keys = [str(vote.id) for vote in self.list_by_user(user_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)


class ReportRepository(DynamoRepository[Report]):
    """Reports on any entity type, queryable by entity, user and triage status."""

    def __init__(self) -> None:
        """Bind to the reports table."""
        super().__init__(Report, REPORTS)

    def for_entity(self, entity_type: str, entity_id: UUID) -> list[Report]:
        """Every report on one entity."""
        return self.query_all(ENTITY_INDEX, _entity_key(entity_type, entity_id))

    def pending_by_user(self, entity_type: str, entity_id: UUID, user_id: UUID) -> Report | None:
        """This user's open report on this entity, or None."""
        reports = self.query_all(
            ENTITY_INDEX, _entity_key(entity_type, entity_id), range_condition=RangeCondition.eq(user_id)
        )
        pending = [report for report in reports if report.status == "pending"]
        return pending[0] if pending else None

    def list_by_user(self, user_id: UUID, *, status: str | None = None) -> list[Report]:
        """This user's reports, newest first, optionally filtered by status."""
        reports = self.query_all(USER_INDEX, user_id, scan_forward=False)
        if status is not None:
            reports = [report for report in reports if report.status == status]
        return _newest_first(reports)

    def list_filtered(self, *, entity_type: str | None = None, status: str | None = None) -> list[Report]:
        """Every report matching the filters, newest first."""
        if status is not None:
            reports = self.query_all(STATUS_INDEX, status, scan_forward=False)
        elif entity_type is not None:
            reports = self.scan_all(filter_expression=Attr("entity_type").eq(entity_type))
        else:
            reports = self.scan_all()
        if entity_type is not None:
            reports = [report for report in reports if report.entity_type == entity_type]
        return _newest_first(reports)

    def entities_with_reports(self, entity_type: str, entity_ids: Iterable[UUID]) -> set[UUID]:
        """Which of these entities have at least one report."""
        return {entity_id for entity_id in set(entity_ids) if self.for_entity(entity_type, entity_id)}

    def count(self) -> int:
        """How many reports exist."""
        return len(self.scan_all())

    def count_by_entity_type(self) -> dict[str, int]:
        """How many reports exist per entity type."""
        counts: dict[str, int] = defaultdict(int)
        for report in self.scan_all():
            counts[report.entity_type] += 1
        return dict(counts)

    def delete_for_entities(self, entity_type: str, entity_ids: Iterable[UUID]) -> int:
        """Delete every report on these entities, returning how many were removed."""
        keys = [str(report.id) for entity_id in set(entity_ids) for report in self.for_entity(entity_type, entity_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)

    def delete_for_user(self, user_id: UUID) -> int:
        """Delete every report this user filed, returning how many were removed."""
        keys = [str(report.id) for report in self.query_all(USER_INDEX, user_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)


def _tally(votes: Iterable[Vote]) -> tuple[int, int]:
    """Count upvotes and downvotes, ignoring any other vote type."""
    up = down = 0
    for vote in votes:
        if vote.vote_type == UPVOTE:
            up += 1
        elif vote.vote_type == DOWNVOTE:
            down += 1
    return up, down


def _newest_first(reports: list[Report]) -> list[Report]:
    """Sort reports newest first, breaking ties on id so the order is stable."""
    return sorted(reports, key=lambda report: (report.created_at, str(report.id)), reverse=True)


def moderation_delete_actions(
    entity_type: str,
    entity_id: UUID,
    *,
    votes: VoteRepository,
    reports: ReportRepository,
) -> list[dict[str, Any]]:
    """Transaction actions removing every vote and report on one entity."""
    actions: list[dict[str, Any]] = []
    actions.extend(votes.delete_action(str(vote.id)) for vote in votes.for_entity(entity_type, entity_id))
    actions.extend(reports.delete_action(str(report.id)) for report in reports.for_entity(entity_type, entity_id))
    return actions
