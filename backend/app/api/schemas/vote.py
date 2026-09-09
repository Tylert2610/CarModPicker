from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class VoteEntityType(str, Enum):
    CAR_GENERATION = "car_generation"
    BUILD_LIST = "build_list"
    PART = "part"


EntityType = VoteEntityType


class VoteCreate(BaseModel):
    vote_type: VoteType


class VoteUpdate(BaseModel):
    vote_type: VoteType


class VoteRead(BaseModel):
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

    Split plan row 24 and its open question 2. Once the `net_votes` aggregate is
    recomputed off the `votes` stream it lags the vote by the stream latency, so
    a client that votes and then re-reads can see the old number. Carrying the
    counts on the write response removes the re-read entirely: the vote itself
    is synchronous and strongly consistent, so the tallies computed in the same
    request are the authoritative ones and the client has no reason to ask
    again.

    `vote` is `None` on a removal, where there is no vote left to return. The
    counts are always present, which is what lets one response shape serve both
    routes and keeps the frontend from branching on which call it made.

    The counts are read from the `votes` table, not from `parts.net_votes`.
    Reading the denormalised column would hand back exactly the stale number
    this schema exists to avoid.
    """

    vote: VoteRead | None = None
    upvotes: int
    downvotes: int
    total_votes: int
    #: `upvotes - downvotes`, the same number the stream consumer writes to
    #: `parts.net_votes`. Named to match `VoteSummary.vote_score` so a client
    #: reads the same field off both responses.
    vote_score: int

    model_config = ConfigDict(from_attributes=True)


class VoteSummary(BaseModel):
    entity_id: UUID
    entity_type: str
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedEntitySummary(BaseModel):
    entity_id: UUID
    entity_type: str
    entity_name: str
    entity_description: Optional[str] = None
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    downvote_ratio: float  # downvotes / total_votes
    recent_downvotes: int  # downvotes in last 7 days
    has_reports: bool  # whether entity has pending reports
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
