"""
Refactored build list reports endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseEndpointRouter to provide common CRUD operations
while maintaining build list report-specific functionality.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_report import BuildListReport as DBBuildListReport
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_report import (
    BuildListReportCreate,
    BuildListReportRead,
    BuildListReportUpdate,
    BuildListReportWithDetails,
)
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    get_standard_pagination_params,
    validate_pagination_params,
    get_standard_endpoint_dependencies,
    get_entity_or_404,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    crud_responses,
    standard_responses,
)
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()


# Create base CRUD service
class BuildListReportService(
    BaseCRUDService[
        DBBuildListReport,
        BuildListReportCreate,
        BuildListReportRead,
        BuildListReportUpdate,
    ]
):
    """Build list report service that extends the base CRUD service."""

    def __init__(self):
        super().__init__(
            model=DBBuildListReport,
            entity_name="build list report",
            subscription_check_method=None,  # Reports don't count against subscription
        )


build_list_report_service = BuildListReportService()

# Create base endpoint router
base_router = BaseEndpointRouter(
    service=build_list_report_service,
    router=router,
    entity_name="build list report",
    allow_public_read=False,  # Reports are private
    additional_create_data={},  # No additional data needed
    disable_endpoints=["list", "update", "delete"],  # Custom implementations for these
)


@router.post(
    "/{build_list_id}/report",
    response_model=BuildListReportRead,
    responses=standard_responses(
        success_description="Build list reported successfully",
        validation_error=True,
        not_found=True,
        conflict=True,
    ),
)
async def report_build_list(
    build_list_id: int,
    report: BuildListReportCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListReportRead:
    """Report a build list for admin review."""
    # Check if build list exists
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Check if user is trying to report their own build list
    if db_build_list.user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You cannot report your own build list"
        )

    # Check if user has already reported this build list
    existing_report = (
        db.query(DBBuildListReport)
        .filter(
            DBBuildListReport.user_id == current_user.id,
            DBBuildListReport.build_list_id == build_list_id,
            DBBuildListReport.status == "pending",
        )
        .first()
    )

    if existing_report:
        raise HTTPException(status_code=400, detail="Already reported")

    # Create new report
    db_report = DBBuildListReport(
        user_id=current_user.id,
        build_list_id=build_list_id,
        reason=report.reason.value,
        description=report.description,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    logger.info(
        f"Build list reported: {db_report.id} by user {current_user.id} on build list {build_list_id}"
    )
    return BuildListReportRead.model_validate(db_report)


@router.get(
    "/admin/list",
    response_model=List[BuildListReportRead],
    responses=standard_responses(
        success_description="Build list reports retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_reports_admin(
    status: Optional[str] = Query(None, description="Filter by status"),
    reason: Optional[str] = Query(None, description="Filter by reason"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of reports to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListReportRead]:
    """List all reports with optional filtering (admin only)."""
    # Check if user is admin
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    skip, limit = validate_pagination_params(skip, limit)

    # Build query
    query = db.query(DBBuildListReport)

    # Apply filters
    if status:
        query = query.filter(DBBuildListReport.status == status)
    if reason:
        query = query.filter(DBBuildListReport.reason == reason)

    # Apply pagination
    reports = (
        query.order_by(DBBuildListReport.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    logger.info(f"Retrieved {len(reports)} reports for admin user {current_user.id}")
    return [BuildListReportRead.model_validate(report) for report in reports]


@router.get(
    "/my-reports",
    response_model=List[BuildListReportRead],
    responses=standard_responses(
        success_description="User reports retrieved successfully", unauthorized=True
    ),
)
async def get_my_reports(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListReportRead]:
    """Get reports created by the current user."""
    db_reports = (
        db.query(DBBuildListReport)
        .filter(DBBuildListReport.user_id == current_user.id)
        .order_by(DBBuildListReport.created_at.desc())
        .all()
    )

    reports = [BuildListReportRead.model_validate(report) for report in db_reports]

    logger.info(f"Retrieved {len(reports)} reports for user {current_user.id}")
    return reports


@router.get(
    "/{report_id}",
    response_model=BuildListReportRead,
    responses=standard_responses(
        success_description="Report retrieved successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListReportRead:
    """Get a specific report by ID (user can only see their own reports)."""
    report = (
        db.query(DBBuildListReport).filter(DBBuildListReport.id == report_id).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Users can only see their own reports unless they're admin
    if not current_user.is_admin and report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Report not found")

    logger.info(f"Report retrieved: {report_id} by user {current_user.id}")
    return BuildListReportRead.model_validate(report)


@router.get(
    "/admin/{report_id}",
    response_model=BuildListReportWithDetails,
    responses=standard_responses(
        success_description="Report details retrieved successfully",
        forbidden=True,
        not_found=True,
    ),
)
async def get_report_admin(
    report_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> BuildListReportWithDetails:
    """Get a specific report with details (admin only)."""
    report = get_entity_or_404(db, DBBuildListReport, report_id, "report")

    # Get reporter username
    reporter = db.query(DBUser).filter(DBUser.id == report.user_id).first()
    reporter_username = reporter.username if reporter else "Unknown"

    # Get build list details
    build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == report.build_list_id).first()
    )
    build_list_name = build_list.name if build_list else "Unknown"
    build_list_description = build_list.description if build_list else None

    # Get reviewer username
    reviewer_username = None
    if report.reviewed_by:
        reviewer = db.query(DBUser).filter(DBUser.id == report.reviewed_by).first()
        reviewer_username = reviewer.username if reviewer else "Unknown"

    report_detail = BuildListReportWithDetails(
        **report.__dict__,
        reporter_username=reporter_username,
        build_list_name=build_list_name,
        build_list_description=build_list_description,
        reviewer_username=reviewer_username,
    )

    logger.info(
        f"Report with details retrieved: {report_id} by admin {current_admin.id}"
    )
    return report_detail


@router.put(
    "/{report_id}",
    response_model=BuildListReportRead,
    responses=standard_responses(
        success_description="Report status updated successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def update_report_status(
    report_id: int,
    report_update: BuildListReportUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListReportRead:
    """Update a report status (admin only)."""
    # Check if user is admin
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get the report
    db_report = get_entity_or_404(db, DBBuildListReport, report_id, "report")

    # Update the report
    db_report.status = report_update.status.value
    if report_update.admin_notes is not None:
        db_report.admin_notes = report_update.admin_notes
    db_report.reviewed_by = current_user.id
    db_report.reviewed_at = datetime.now(UTC)

    db.commit()
    db.refresh(db_report)

    logger.info(
        f"Report {report_id} status updated to {report_update.status.value} by admin {current_user.id}"
    )
    return BuildListReportRead.model_validate(db_report)


@router.delete(
    "/{report_id}",
    response_model=Dict[str, str],
    responses=standard_responses(
        success_description="Report deleted successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> Dict[str, str]:
    """Delete a report (admin only)."""
    # Check if user is admin
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get the report
    db_report = get_entity_or_404(db, DBBuildListReport, report_id, "report")

    # Delete the report
    db.delete(db_report)
    db.commit()

    logger.info(f"Report {report_id} deleted by admin {current_user.id}")
    return {"message": "Report deleted successfully"}


@router.get(
    "/admin/pending/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Pending reports count retrieved successfully",
        forbidden=True,
    ),
)
async def get_pending_reports_count(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> Dict[str, int]:
    """Get count of pending reports (admin only)."""
    count = (
        db.query(DBBuildListReport)
        .filter(DBBuildListReport.status == "pending")
        .count()
    )
    logger.info(f"Pending reports count: {count}")
    return {"pending_count": count}
