from datetime import datetime
from pydantic import BaseModel, ConfigDict


class GlobalPartVoteCreate(BaseModel):
    vote_type: str  # 'upvote' or 'downvote'


class GlobalPartVoteUpdate(BaseModel):
    vote_type: str  # 'upvote' or 'downvote'


class GlobalPartVoteRead(BaseModel):
    id: int
    user_id: int
    global_part_id: int
    vote_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GlobalPartVoteSummary(BaseModel):
    part_id: int
    upvotes: int
    downvotes: int
    total_votes: int
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedGlobalPartSummary(BaseModel):
    part_id: int
    part_name: str
    part_brand: str | None
    category_id: int
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    downvote_ratio: float  # downvotes / total_votes
    recent_downvotes: int  # downvotes in last 7 days
    has_reports: bool  # whether part has pending reports
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
