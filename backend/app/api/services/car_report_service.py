"""
Car report service that extends the base report service.
"""

from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.services.base_report_service import BaseReportService
from app.api.models.car import Car as DBCar
from app.api.models.car_report import CarReport as DBCarReport
from app.api.models.user import User as DBUser
from app.api.schemas.car_report import (
    CarReportCreate,
    CarReportRead,
    CarReportUpdate,
    CarReportWithDetails,
)


class CarReportService(
    BaseReportService[DBCarReport, CarReportCreate, CarReportRead, CarReportWithDetails]
):
    """
    Car report service that extends the base report service.

    This service provides car-specific reporting functionality while inheriting
    common operations from the base report service.
    """

    def __init__(self):
        """Initialize the car report service with car-specific models."""
        super().__init__(
            report_model=DBCarReport,
            entity_model=DBCar,
            entity_name="car",
            report_entity_id_field="car_id",
        )

    def get_reports_with_details(
        self,
        db: Session,
        current_user: DBUser,
        status: str = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CarReportWithDetails]:
        """
        Get car reports with detailed information (admin only).

        Args:
            db: Database session
            current_user: Current authenticated user
            status: Filter by status
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of car reports with details

        Raises:
            HTTPException: If user is not admin
        """
        # Check if user is admin
        if not current_user.is_admin and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Build query
        query = db.query(DBCarReport)

        if status:
            query = query.filter(DBCarReport.status == status)

        reports = query.offset(skip).limit(limit).all()

        # Add additional details
        report_details = []
        for report in reports:
            # Get reporter username
            reporter = db.query(DBUser).filter(DBUser.id == report.user_id).first()
            reporter_username = reporter.username if reporter else "Unknown"

            # Get car details
            car = db.query(DBCar).filter(DBCar.id == report.car_id).first()
            car_make = car.make if car else "Unknown"
            car_model = car.model if car else "Unknown"
            car_year = car.year if car else 0

            # Get reviewer username
            reviewer_username = None
            if report.reviewed_by:
                reviewer = (
                    db.query(DBUser).filter(DBUser.id == report.reviewed_by).first()
                )
                reviewer_username = reviewer.username if reviewer else "Unknown"

            report_detail = CarReportWithDetails(
                **report.__dict__,
                reporter_username=reporter_username,
                car_make=car_make,
                car_model=car_model,
                car_year=car_year,
                reviewer_username=reviewer_username,
            )
            report_details.append(report_detail)

        return report_details

    def get_report_with_details(
        self, db: Session, report_id: int, current_user: DBUser
    ) -> CarReportWithDetails:
        """
        Get a specific car report with detailed information.

        Args:
            db: Database session
            report_id: ID of the report
            current_user: Current authenticated user

        Returns:
            Car report with details

        Raises:
            HTTPException: If report not found or user not authorized
        """
        report = self.get_report_by_id(db, report_id, current_user, None)

        # Get reporter username
        reporter = db.query(DBUser).filter(DBUser.id == report.user_id).first()
        reporter_username = reporter.username if reporter else "Unknown"

        # Get car details
        car = db.query(DBCar).filter(DBCar.id == report.car_id).first()
        car_make = car.make if car else "Unknown"
        car_model = car.model if car else "Unknown"
        car_year = car.year if car else 0

        # Get reviewer username
        reviewer_username = None
        if report.reviewed_by:
            reviewer = db.query(DBUser).filter(DBUser.id == report.reviewed_by).first()
            reviewer_username = reviewer.username if reviewer else "Unknown"

        return CarReportWithDetails(
            **report.__dict__,
            reporter_username=reporter_username,
            car_make=car_make,
            car_model=car_model,
            car_year=car_year,
            reviewer_username=reviewer_username,
        )
