from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PartReportCreate(BaseModel):
    reason: str  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Optional[str] = None


class PartReportUpdate(BaseModel):
    status: str  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Optional[str] = None


class PartReportRead(BaseModel):
    id: int
    user_id: int
    part_id: int
    reason: str
    description: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartReportWithDetails(PartReportRead):
    reporter_username: str
    part_name: str
    reviewer_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
