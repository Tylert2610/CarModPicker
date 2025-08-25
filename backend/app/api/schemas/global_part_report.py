from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


class ReportReason(str, Enum):
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SPAM = "spam"
    INACCURATE = "inaccurate"
    DUPLICATE = "duplicate"
    OTHER = "other"


class ReportStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class GlobalPartReportCreate(BaseModel):
    reason: ReportReason
    description: Optional[str] = None


class GlobalPartReportUpdate(BaseModel):
    status: ReportStatus
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
