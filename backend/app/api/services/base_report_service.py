"""
Base service class for reporting operations to eliminate code duplication.
"""

import logging
from typing import TypeVar, Generic, Type, Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from fastapi import HTTPException

from app.api.models.user import User as DBUser
from app.api.utils.common_operations import verify_entity_exists

# Generic types for different report models and schemas
ReportModelType = TypeVar("ReportModelType")
ReportCreateSchema = TypeVar("ReportCreateSchema")
ReportReadSchema = TypeVar("ReportReadSchema")
EntityModelType = TypeVar("EntityModelType")


class BaseReportService(
    Generic[ReportModelType, ReportCreateSchema, ReportReadSchema, EntityModelType]
):
    """
    Base service class for reporting operations.

    This class provides common reporting functionality for all entity types
    to eliminate code duplication across different report endpoints.
    """

    def __init__(
        self,
        report_model: Type[ReportModelType],
        entity_model: Type[EntityModelType],
        entity_name: str = "entity",
        report_entity_id_field: str = "entity_id",
    ):
        """
        Initialize the base report service.

        Args:
            report_model: The SQLAlchemy report model class
            entity_model: The SQLAlchemy entity model class being reported
            entity_name: Human-readable name of the entity type
            report_entity_id_field: Field name in report model that references the entity
        """
        self.report_model = report_model
        self.entity_model = entity_model
        self.entity_name = entity_name
        self.report_entity_id_field = report_entity_id_field

    def create_report(
        self,
        db: Session,
        entity_id: int,
        user_id: int,
        report_data: ReportCreateSchema,
        logger: logging.Logger,
    ) -> ReportModelType:
        """
        Create a report for an entity.

        Args:
            db: Database session
            entity_id: ID of the entity being reported
            user_id: ID of the user reporting
            report_data: Report data (typically contains reason and description)
            logger: Logger instance

        Returns:
            The created report

        Raises:
            HTTPException: If entity not found or reporting fails
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        # Check if user has already reported this entity
        existing_report = (
            db.query(self.report_model)
            .filter(
                and_(
                    getattr(self.report_model, "user_id") == user_id,
                    getattr(self.report_model, self.report_entity_id_field)
                    == entity_id,
                    getattr(self.report_model, "status") == "pending",
                )
            )
            .first()
        )

        if existing_report:
            raise HTTPException(
                status_code=409,
                detail=f"You have already reported this {self.entity_name}",
            )

        # Create new report
        report_data_dict = report_data.model_dump()
        report_data_dict["user_id"] = user_id
        report_data_dict[self.report_entity_id_field] = entity_id
        report_data_dict["status"] = "pending"

        db_report = self.report_model(**report_data_dict)
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        logger.info(
            f"Report created: {db_report.id} by user {user_id} on {self.entity_name} {entity_id}"
        )
        return db_report

    def get_reports_by_entity(
        self,
        db: Session,
        entity_id: int,
        logger: logging.Logger,
        status: Optional[str] = None,
    ) -> List[ReportModelType]:
        """
        Get all reports for a specific entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance
            status: Optional status filter (pending, resolved, dismissed)

        Returns:
            List of reports for the entity

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        query = db.query(self.report_model).filter(
            getattr(self.report_model, self.report_entity_id_field) == entity_id
        )

        if status:
            query = query.filter(getattr(self.report_model, "status") == status)

        reports = query.order_by(desc(getattr(self.report_model, "created_at"))).all()

        logger.info(
            f"Retrieved {len(reports)} reports for {self.entity_name} {entity_id}"
        )
        return reports

    def update_report_status(
        self,
        db: Session,
        report_id: int,
        new_status: str,
        admin_user_id: int,
        logger: logging.Logger,
        resolution_notes: Optional[str] = None,
    ) -> ReportModelType:
        """
        Update the status of a report (admin only).

        Args:
            db: Database session
            report_id: ID of the report
            new_status: New status (resolved, dismissed, etc.)
            admin_user_id: ID of the admin user making the change
            logger: Logger instance
            resolution_notes: Optional notes about the resolution

        Returns:
            The updated report

        Raises:
            HTTPException: If report not found or status update fails
        """
        report = (
            db.query(self.report_model)
            .filter(getattr(self.report_model, "id") == report_id)
            .first()
        )

        if not report:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        # Update status
        report.status = new_status
        if resolution_notes:
            report.resolution_notes = resolution_notes

        db.commit()
        db.refresh(report)

        logger.info(
            f"Report {report_id} status updated to {new_status} by admin {admin_user_id}"
        )
        return report

    def get_pending_reports(
        self,
        db: Session,
        logger: logging.Logger,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ReportModelType]:
        """
        Get all pending reports (admin only).

        Args:
            db: Database session
            logger: Logger instance
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of pending reports
        """
        reports = (
            db.query(self.report_model)
            .filter(getattr(self.report_model, "status") == "pending")
            .order_by(desc(getattr(self.report_model, "created_at")))
            .offset(skip)
            .limit(limit)
            .all()
        )

        logger.info(f"Retrieved {len(reports)} pending reports")
        return reports

    def get_report_summary(
        self,
        db: Session,
        entity_id: int,
        logger: logging.Logger,
    ) -> Dict[str, Any]:
        """
        Get report summary for an entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance

        Returns:
            Dictionary with report counts and summary

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
            logger=logger,
        )

        # Get report counts by status
        pending_reports = (
            db.query(func.count(self.report_model.id))
            .filter(
                and_(
                    getattr(self.report_model, self.report_entity_id_field)
                    == entity_id,
                    getattr(self.report_model, "status") == "pending",
                )
            )
            .scalar()
        )

        resolved_reports = (
            db.query(func.count(self.report_model.id))
            .filter(
                and_(
                    getattr(self.report_model, self.report_entity_id_field)
                    == entity_id,
                    getattr(self.report_model, "status") == "resolved",
                )
            )
            .scalar()
        )

        dismissed_reports = (
            db.query(func.count(self.report_model.id))
            .filter(
                and_(
                    getattr(self.report_model, self.report_entity_id_field)
                    == entity_id,
                    getattr(self.report_model, "status") == "dismissed",
                )
            )
            .scalar()
        )

        total_reports = pending_reports + resolved_reports + dismissed_reports

        logger.info(
            f"Report summary for {self.entity_name} {entity_id}: pending={pending_reports}, resolved={resolved_reports}, dismissed={dismissed_reports}"
        )

        return {
            "pending_reports": pending_reports,
            "resolved_reports": resolved_reports,
            "dismissed_reports": dismissed_reports,
            "total_reports": total_reports,
        }

    def get_user_reports(
        self,
        db: Session,
        user_id: int,
        logger: logging.Logger,
        status: Optional[str] = None,
    ) -> List[ReportModelType]:
        """
        Get all reports created by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            logger: Logger instance
            status: Optional status filter

        Returns:
            List of reports created by the user
        """
        query = db.query(self.report_model).filter(
            getattr(self.report_model, "user_id") == user_id
        )

        if status:
            query = query.filter(getattr(self.report_model, "status") == status)

        reports = query.order_by(desc(getattr(self.report_model, "created_at"))).all()

        logger.info(f"Retrieved {len(reports)} reports by user {user_id}")
        return reports
