from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class BuildListVoteCreate(BaseModel):
    vote_type: VoteType


class BuildListVoteUpdate(BaseModel):
    vote_type: VoteType


class BuildListVoteRead(BaseModel):
    id: int
    user_id: int
    build_list_id: int
    vote_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BuildListVoteSummary(BaseModel):
    build_list_id: int
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedBuildListSummary(BaseModel):
    build_list_id: int
    build_list_name: str
    build_list_description: str | None
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    downvote_ratio: float  # downvotes / total_votes
    recent_downvotes: int  # downvotes in last 7 days
    has_reports: bool  # whether build list has pending reports
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
