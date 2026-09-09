"""
Bug report service on DynamoDB.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.bug_report import (
    BugReportCreate,
    BugReportRead,
    BugReportUpdate,
    BugReportWithDetails,
)
from app.db.dynamo.bug_reports import BugReport
from app.db.dynamo.models import utc_now
from app.db.dynamo.tombstones import live_or_none


class BugReportService:
    """
    Service for handling bug reports.
    """

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        self.repos = repos or get_repositories()
        self.users = self.repos.users

    def create_bug_report(
        self,
        bug_report_data: BugReportCreate,
        user_id: Optional[UUID] = None,
        logger: Optional[logging.Logger] = None,
    ) -> BugReport:
        """Create a new bug report (``user_id`` is None for anonymous reports)."""
        bug_report = self.repos.bug_reports.create(BugReport(user_id=user_id, **bug_report_data.model_dump()))
        if logger:
            logger.info(f"Bug report created: {bug_report.id} by user {user_id or 'anonymous'}")
        return bug_report

    def _list(
        self, status: Optional[str], priority: Optional[str], skip: int, limit: int
    ) -> tuple[List[BugReport], int]:
        reports = self.repos.bug_reports.list_filtered(status=status or None, priority=priority or None)
        return reports[skip : skip + limit], len(reports)

    def get_bug_reports(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[BugReportRead]:
        """Bug reports matching the optional status/priority filters, newest first."""
        reports, _ = self._list(status, priority, skip, limit)
        return [BugReportRead.model_validate(report) for report in reports]

    def get_bug_reports_with_details(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> tuple[List[BugReportWithDetails], int]:
        """Bug reports with reporter/assignee usernames, plus the unpaginated total."""
        reports, total_count = self._list(status, priority, skip, limit)
        user_ids = [report.user_id for report in reports if report.user_id] + [
            report.assigned_to for report in reports if report.assigned_to
        ]
        users_by_id = self.users.get_many(user_ids)

        def username(user_id: UUID | None) -> str | None:
            # A tombstoned reporter or assignee reads as absent, which this
            # closure already renders as None.
            user = live_or_none(users_by_id.get(user_id)) if user_id else None
            return user.username if user else None

        return [
            self._with_details(
                report,
                reporter_username=username(report.user_id),
                assignee_username=username(report.assigned_to),
            )
            for report in reports
        ], total_count

    def update_bug_report(
        self,
        bug_report_id: UUID,
        bug_report_update: BugReportUpdate,
        logger: Optional[logging.Logger] = None,
    ) -> BugReport:
        """Update a bug report (typically for admin review). Raises 404 when missing."""
        self._require(bug_report_id)

        changes: dict[str, object] = {}
        if bug_report_update.status:
            changes["status"] = bug_report_update.status.value
            if bug_report_update.status.value == "resolved":
                changes["resolved_at"] = utc_now()
        if bug_report_update.priority:
            changes["priority"] = bug_report_update.priority.value
        if bug_report_update.admin_notes is not None:
            changes["admin_notes"] = bug_report_update.admin_notes
        if bug_report_update.assigned_to is not None:
            changes["assigned_to"] = bug_report_update.assigned_to

        bug_report = self.repos.bug_reports.update(bug_report_id, updated_at=utc_now(), **changes)
        if logger:
            logger.info(f"Bug report updated: {bug_report_id}")
        return bug_report

    def delete_bug_report(
        self,
        bug_report_id: UUID,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Delete a bug report (admin only). Raises 404 when missing."""
        self._require(bug_report_id)
        self.repos.bug_reports.delete(bug_report_id)
        if logger:
            logger.info(f"Bug report deleted: {bug_report_id}")

    def get_bug_report_by_id(
        self,
        bug_report_id: UUID,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[BugReportWithDetails]:
        """A single bug report with reporter/assignee usernames, or None."""
        bug_report = self.repos.bug_reports.get(bug_report_id)
        if bug_report is None:
            return None

        reporter = live_or_none(self.users.get(bug_report.user_id)) if bug_report.user_id else None
        assignee = live_or_none(self.users.get(bug_report.assigned_to)) if bug_report.assigned_to else None
        return self._with_details(
            bug_report,
            reporter_username=reporter.username if reporter else None,
            assignee_username=assignee.username if assignee else None,
        )

    # -- helpers -----------------------------------------------------------

    def _require(self, bug_report_id: UUID) -> BugReport:
        bug_report = self.repos.bug_reports.get(bug_report_id)
        if bug_report is None:
            raise HTTPException(status_code=404, detail="Bug report not found")
        return bug_report

    @staticmethod
    def _with_details(
        bug_report: BugReport, *, reporter_username: str | None, assignee_username: str | None
    ) -> BugReportWithDetails:
        return BugReportWithDetails(
            **BugReportRead.model_validate(bug_report).model_dump(),
            reporter_username=reporter_username,
            assignee_username=assignee_username,
        )
