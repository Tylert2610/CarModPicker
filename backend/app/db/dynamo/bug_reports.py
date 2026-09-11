"""Bug reports on DynamoDB, submitted by any user and triaged by admins.

The status GSI serves the admin queue; the user GSI serves "my reports"
and account purges.
"""

from datetime import datetime
from uuid import UUID

from boto3.dynamodb.conditions import Attr
from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository
from app.db.dynamo.tables import BUG_REPORTS

USER_INDEX = "user_id-created_at-index"
STATUS_INDEX = "status-created_at-index"


class BugReport(TimestampedDynamoModel):
    """A bug report submitted through the app (``user_id`` is None when anonymous)."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID | None = None
    title: str
    description: str
    steps_to_reproduce: str | None = None
    expected_behavior: str | None = None
    actual_behavior: str | None = None
    browser_info: str | None = None
    device_info: str | None = None
    screenshot_url: str | None = None
    status: str = "pending"
    priority: str = "medium"
    admin_notes: str | None = None
    assigned_to: UUID | None = None
    resolved_at: datetime | None = None


def _newest_first(reports: list[BugReport]) -> list[BugReport]:
    """Sort reports newest first, breaking ties on id so the order is stable."""
    return sorted(reports, key=lambda report: (report.created_at, str(report.id)), reverse=True)


class BugReportRepository(DynamoRepository[BugReport]):
    """Bug reports, queryable by submitting user and by triage status."""

    def __init__(self) -> None:
        """Bind to the bug reports table."""
        super().__init__(BugReport, BUG_REPORTS)

    def list_by_user(self, user_id: UUID) -> list[BugReport]:
        """This user's reports, newest first."""
        return self.query_all(USER_INDEX, user_id, scan_forward=False)

    def list_filtered(self, *, status: str | None = None, priority: str | None = None) -> list[BugReport]:
        """Every bug report matching the filters, newest first."""
        if status is not None:
            reports = self.query_all(STATUS_INDEX, status, scan_forward=False)
        elif priority is not None:
            reports = self.scan_all(filter_expression=Attr("priority").eq(priority))
        else:
            reports = self.scan_all()
        if priority is not None:
            reports = [report for report in reports if report.priority == priority]
        return _newest_first(reports)

    def count(self) -> int:
        """How many bug reports exist."""
        return len(self.scan_all())

    def delete_for_user(self, user_id: UUID) -> int:
        """Delete every report this user submitted, returning how many were removed."""
        keys = [str(report.id) for report in self.list_by_user(user_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)
