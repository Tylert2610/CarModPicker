from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class CarVoteCreate(BaseModel):
    vote_type: VoteType


class CarVoteUpdate(BaseModel):
    vote_type: VoteType


class CarVoteRead(BaseModel):
    id: int
    user_id: int
    car_id: int
    vote_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CarVoteSummary(BaseModel):
    car_id: int
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedCarSummary(BaseModel):
    car_id: int
    car_make: str
    car_model: str
    car_year: int
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    downvote_ratio: float  # downvotes / total_votes
    recent_downvotes: int  # downvotes in last 7 days
    has_reports: bool  # whether car has pending reports
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
