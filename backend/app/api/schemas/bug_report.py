"""Request and response schemas for user submitted bug reports."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BugReportStatus(str, Enum):
    """Lifecycle state of a bug report."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class BugReportPriority(str, Enum):
    """Triage priority of a bug report."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BugReportCreate(BaseModel):
    """Request body for filing a bug report."""

    title: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_info: Optional[str] = None
    device_info: Optional[str] = None
    screenshot_url: Optional[str] = None


class BugReportUpdate(BaseModel):
    """Request body for an admin triaging a bug report."""

    status: Optional[BugReportStatus] = None
    priority: Optional[BugReportPriority] = None
    admin_notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


class BugReportRead(BaseModel):
    """A bug report as returned to clients."""

    id: UUID
    user_id: Optional[UUID] = None
    title: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_info: Optional[str] = None
    device_info: Optional[str] = None
    screenshot_url: Optional[str] = None
    status: str
    priority: str
    admin_notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BugReportWithDetails(BugReportRead):
    """A bug report with reporter and assignee usernames resolved."""

    reporter_username: Optional[str] = None
    assignee_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
