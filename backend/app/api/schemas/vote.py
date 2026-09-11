"""Request and response schemas for votes on cars, build lists and parts."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    """Direction of a vote."""

    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class VoteEntityType(str, Enum):
    """Kind of entity a vote targets."""

    CAR_GENERATION = "car_generation"
    BUILD_LIST = "build_list"
    PART = "part"


EntityType = VoteEntityType


class VoteCreate(BaseModel):
    """Request body for casting a vote."""

    vote_type: VoteType


class VoteUpdate(BaseModel):
    """Request body for changing an existing vote."""

    vote_type: VoteType


class VoteRead(BaseModel):
    """A vote as returned to clients."""

    id: UUID
    user_id: UUID
    vote_type: str
    entity_type: str
    entity_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoteMutationResult(BaseModel):
    """A vote write, plus the entity's tallies as of that write.

    The tallies are returned with the write so clients need not re-read an
    aggregate that lags behind the stream.
    """

    vote: VoteRead | None = None
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int

    model_config = ConfigDict(from_attributes=True)


class VoteSummary(BaseModel):
    """Vote tallies for one entity, including the caller's own vote."""

    entity_id: UUID
    entity_type: str
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int
    user_vote: str | None

    model_config = ConfigDict(from_attributes=True)


class FlaggedEntitySummary(BaseModel):
    """An entity surfaced to moderators by its downvote pattern."""

    entity_id: UUID
    entity_type: str
    entity_name: str
    entity_description: Optional[str] = None
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int
    downvote_ratio: float
    recent_downvotes: int
    has_reports: bool
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
