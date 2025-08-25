from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class GlobalPartReportCreate(BaseModel):
    reason: str  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Optional[str] = None


class GlobalPartReportUpdate(BaseModel):
    status: str  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Optional[str] = None


class GlobalPartReportRead(BaseModel):
    id: int
    user_id: int
    global_part_id: int
    reason: str
    description: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GlobalPartReportWithDetails(GlobalPartReportRead):
    reporter_username: str
    part_name: str
    reviewer_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
