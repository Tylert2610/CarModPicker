"""
Unified report service for all entity types.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.report import (
    EntityType,
    ReportCreate,
    ReportRead,
    ReportWithDetails,
)
from app.db.dynamo.build_lists import BuildList as DBBuildList
from app.db.dynamo.catalog import Part
from app.db.dynamo.moderation import Report
from app.db.dynamo.tombstones import live_or_none


class ReportService:
    """
    Unified report service for all entity types.

    This service handles reporting operations for build lists and global parts
    using the unified Report model in DynamoDB.
    """

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Bind the service to a repository bundle."""
        self.repos = repos or get_repositories()

    def create_report(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
        report_data: ReportCreate,
        logger: logging.Logger,
    ) -> Report:
        """
        Create a report for an entity.

        Raises 404 if the entity doesn't exist and 400 if the user owns the entity
        or already has a pending report on it.
        """
        entity = self._get_entity_or_404(entity_type, entity_id)

        if entity.user_id == user_id:
            raise HTTPException(
                status_code=400,
                detail=f"You cannot report your own {entity_type.value}",
            )

        if self.repos.reports.pending_by_user(entity_type.value, entity_id, user_id) is not None:
            raise HTTPException(status_code=400, detail="You have already reported this entity")

        report = self.repos.reports.create(
            Report(
                user_id=user_id,
                entity_type=entity_type.value,
                entity_id=entity_id,
                reason=report_data.reason.value,
                description=report_data.description,
            )
        )
        logger.info(f"Report created: {report.id} by user {user_id} on {entity_type.value} {entity_id}")
        return report

    def get_reports(
        self,
        entity_type: Optional[EntityType] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ReportRead]:
        """Reports matching the optional filters, newest first."""
        reports = self._filtered(entity_type, status)[skip : skip + limit]
        return [ReportRead.model_validate(report) for report in reports]

    def get_reports_with_details(
        self,
        entity_type: Optional[EntityType] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> tuple[List[ReportWithDetails], int]:
        """Reports with reporter, reviewer and entity details plus the total count."""
        matching = self._filtered(entity_type, status)
        total_count = len(matching)
        reports = matching[skip : skip + limit]

        user_ids = [report.user_id for report in reports] + [
            report.reviewed_by for report in reports if report.reviewed_by
        ]
        users_by_id = self.repos.users.get_many(user_ids)

        details: List[ReportWithDetails] = []
        for report in reports:
            reporter = live_or_none(users_by_id.get(report.user_id))
            reviewer = live_or_none(users_by_id.get(report.reviewed_by)) if report.reviewed_by else None
            details.append(
                self._with_details(
                    report,
                    reporter_username=reporter.username if reporter else "",
                    reviewer_username=reviewer.username if reviewer else None,
                )
            )
        return details, total_count

    def update_report(
        self,
        report_id: UUID,
        status: str,
        admin_notes: Optional[str] = None,
        reviewer_id: Optional[UUID] = None,
        logger: Optional[logging.Logger] = None,
    ) -> Report:
        """Update a report (typically for admin review). Raises 404 if missing."""
        report = self.repos.reports.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        updated = self.repos.reports.update(
            report.id,
            status=status,
            admin_notes=admin_notes,
            reviewed_by=reviewer_id,
            reviewed_at=datetime.now(UTC),
        )
        if logger:
            logger.info(f"Report updated: {report_id} by reviewer {reviewer_id} to status {status}")
        return updated

    def delete_report(
        self,
        report_id: UUID,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Delete a report (admin only). Raises 404 if missing."""
        report = self.repos.reports.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        self.repos.reports.delete(report.id)
        if logger:
            logger.info(f"Report deleted: {report_id}")

    def get_user_reports(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ReportRead]:
        """Reports created by one user, newest first."""
        reports = self.repos.reports.list_by_user(user_id, status=status)[skip : skip + limit]
        if logger:
            logger.info(f"Retrieved {len(reports)} reports by user {user_id}")
        return [ReportRead.model_validate(report) for report in reports]

    def get_report_by_id(
        self,
        report_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[ReportWithDetails]:
        """One report with details, or None when missing or not visible to this user."""
        report = self.repos.reports.get(report_id)
        if not report:
            return None

        if not is_admin and report.user_id != current_user_id:
            return None

        reporter = live_or_none(self.repos.users.get(report.user_id))
        reviewer = live_or_none(self.repos.users.get(report.reviewed_by)) if report.reviewed_by else None
        return self._with_details(
            report,
            reporter_username=reporter.username if reporter else "",
            reviewer_username=reviewer.username if reviewer else None,
        )

    def _filtered(self, entity_type: Optional[EntityType], status: Optional[str]) -> list[Report]:
        """Return reports matching the optional entity type and status filters."""
        return self.repos.reports.list_filtered(
            entity_type=entity_type.value if entity_type else None,
            status=status,
        )

    def _with_details(
        self, report: Report, *, reporter_username: str, reviewer_username: str | None
    ) -> ReportWithDetails:
        """Attach reporter, reviewer and target details to a report."""
        entity = self._get_entity_details(report.entity_type, report.entity_id)
        return ReportWithDetails(
            **ReportRead.model_validate(report).model_dump(),
            reporter_username=reporter_username,
            entity_name=entity["name"],
            entity_description=entity.get("description"),
            reviewer_username=reviewer_username,
        )

    def _get_entity_or_404(self, entity_type: EntityType, entity_id: UUID) -> Union[DBBuildList, Part]:
        """Fetch the reported entity or raise 404."""
        entity: Union[DBBuildList, Part, None]
        if entity_type == EntityType.BUILD_LIST:
            entity = self.repos.build_lists.get(entity_id)
        elif entity_type == EntityType.PART:
            entity = live_or_none(self.repos.parts.get(str(entity_id)))
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{entity_type.value.title()} not found")
        return entity

    def _get_entity_details(self, entity_type: str, entity_id: UUID) -> Dict[str, Any]:
        """Get entity details for report display."""
        if entity_type == "build_list":
            bl = self.repos.build_lists.get(entity_id)
            if bl:
                return {"name": bl.name, "description": bl.description}
        elif entity_type == "part":
            part = live_or_none(self.repos.parts.get(str(entity_id)))
            if part:
                return {"name": part.name, "description": part.description}

        return {"name": f"Unknown {entity_type}", "description": None}
