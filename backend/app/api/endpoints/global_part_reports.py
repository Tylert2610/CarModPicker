import logging
from typing import List, Optional, Dict
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.global_part_report import GlobalPartReport as DBGlobalPartReport
from app.api.models.user import User as DBUser
from app.api.schemas.global_part_report import (
    GlobalPartReportCreate,
    GlobalPartReportRead,
    GlobalPartReportUpdate,
    GlobalPartReportWithDetails,
)
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/{part_id}/report",
    response_model=GlobalPartReportRead,
    responses={
        400: {"description": "Invalid report data"},
        404: {"description": "Part not found"},
        409: {"description": "User has already reported this part"},
    },
)
async def report_part(
    part_id: int,
    report: GlobalPartReportCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBGlobalPartReport:
    """Report a part for admin review."""
    # Validate reason
    valid_reasons = ["inappropriate", "spam", "inaccurate", "duplicate", "other"]
    if report.reason not in valid_reasons:
        raise HTTPException(
            status_code=400, detail=f"Reason must be one of: {', '.join(valid_reasons)}"
        )

    # Check if part exists
    db_global_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if not db_global_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check if user is trying to report their own part
    if db_global_part.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot report your own part")

    # Check if user has already reported this part
    existing_report = (
        db.query(DBGlobalPartReport)
        .filter(
            DBGlobalPartReport.user_id == current_user.id,
            DBGlobalPartReport.global_part_id == part_id,
            DBGlobalPartReport.status == "pending",
        )
        .first()
    )

    if existing_report:
        raise HTTPException(status_code=400, detail="already reported")

    # Create new report
    db_report = DBGlobalPartReport(
        user_id=current_user.id,
        global_part_id=part_id,
        reason=report.reason,
        description=report.description,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    logger.info(
        f"Part reported: {db_report.id} by user {current_user.id} on part {part_id}"
    )
    return db_report


@router.get(
    "/my-reports",
    response_model=List[GlobalPartReportRead],
    responses={
        401: {"description": "Authentication required"},
    },
)
async def get_my_reports(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[GlobalPartReportRead]:
    """Get reports created by the current user."""
    db_reports = (
        db.query(DBGlobalPartReport)
        .filter(DBGlobalPartReport.user_id == current_user.id)
        .order_by(DBGlobalPartReport.created_at.desc())
        .all()
    )

    reports = [GlobalPartReportRead.model_validate(report) for report in db_reports]

    logger.info(f"Retrieved {len(reports)} reports for user {current_user.id}")
    return reports


@router.get(
    "/{report_id}",
    response_model=GlobalPartReportRead,
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Report not found"},
    },
)
async def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartReportRead:
    """Get a specific report by ID (user can only see their own reports)."""
    report = (
        db.query(DBGlobalPartReport)
        .filter(
            DBGlobalPartReport.id == report_id,
            DBGlobalPartReport.user_id == current_user.id,
        )
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    logger.info(f"Report retrieved: {report_id} by user {current_user.id}")
    return report


@router.get(
    "/",
    response_model=List[GlobalPartReportWithDetails],
    responses={
        403: {"description": "Admin access required"},
    },
)
async def get_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of reports to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> List[GlobalPartReportWithDetails]:
    """Get all reports (admin only)."""
    query = db.query(DBGlobalPartReport)

    if status:
        query = query.filter(DBGlobalPartReport.status == status)

    reports = query.offset(skip).limit(limit).all()

    # Add additional details
    report_details = []
    for report in reports:
        # Get reporter username
        reporter = db.query(DBUser).filter(DBUser.id == report.user_id).first()
        reporter_username = reporter.username if reporter else "Unknown"

        # Get part name
        part = (
            db.query(DBGlobalPart)
            .filter(DBGlobalPart.id == report.global_part_id)
            .first()
        )
        part_name = part.name if part else "Unknown Part"

        # Get reviewer username
        reviewer_username = None
        if report.reviewed_by:
            reviewer = db.query(DBUser).filter(DBUser.id == report.reviewed_by).first()
            reviewer_username = reviewer.username if reviewer else "Unknown"

        report_detail = GlobalPartReportWithDetails(
            **report.__dict__,
            reporter_username=reporter_username,
            part_name=part_name,
            reviewer_username=reviewer_username,
        )
        report_details.append(report_detail)

    logger.info(f"Retrieved {len(report_details)} reports")
    return report_details


@router.get(
    "/reports/{report_id}",
    response_model=GlobalPartReportWithDetails,
    responses={
        403: {"description": "Admin access required"},
        404: {"description": "Report not found"},
    },
)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> GlobalPartReportWithDetails:
    """Get a specific report (admin only)."""
    report = (
        db.query(DBGlobalPartReport).filter(DBGlobalPartReport.id == report_id).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get reporter username
    reporter = db.query(DBUser).filter(DBUser.id == report.user_id).first()
    reporter_username = reporter.username if reporter else "Unknown"

    # Get part name
    part = (
        db.query(DBGlobalPart).filter(DBGlobalPart.id == report.global_part_id).first()
    )
    part_name = part.name if part else "Unknown Part"

    # Get reviewer username
    reviewer_username = None
    if report.reviewed_by:
        reviewer = db.query(DBUser).filter(DBUser.id == report.reviewed_by).first()
        reviewer_username = reviewer.username if reviewer else "Unknown"

    report_detail = GlobalPartReportWithDetails(
        **report.__dict__,
        reporter_username=reporter_username,
        part_name=part_name,
        reviewer_username=reviewer_username,
    )

    logger.info(f"Report retrieved: {report_id}")
    return report_detail


@router.put(
    "/{report_id}/status",
    response_model=GlobalPartReportRead,
    responses={
        403: {"description": "Admin access required"},
        404: {"description": "Report not found"},
    },
)
async def update_report_status(
    report_id: int,
    report_update: GlobalPartReportUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> DBGlobalPartReport:
    """Update a report status (admin only)."""
    report = (
        db.query(DBGlobalPartReport).filter(DBGlobalPartReport.id == report_id).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Validate status
    valid_statuses = ["pending", "reviewed", "resolved", "dismissed"]
    if report_update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(valid_statuses)}",
        )

    # Update report
    report.status = report_update.status
    report.admin_notes = report_update.admin_notes
    report.reviewed_by = current_admin.id
    report.reviewed_at = datetime.now(UTC)

    db.commit()
    db.refresh(report)

    logger.info(f"Report updated: {report_id} by admin {current_admin.id}")
    return report


@router.put(
    "/reports/{report_id}",
    response_model=GlobalPartReportRead,
    responses={
        403: {"description": "Admin access required"},
        404: {"description": "Report not found"},
    },
)
async def update_report(
    report_id: int,
    report_update: GlobalPartReportUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> DBGlobalPartReport:
    """Update a report status (admin only)."""
    report = (
        db.query(DBGlobalPartReport).filter(DBGlobalPartReport.id == report_id).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Validate status
    valid_statuses = ["pending", "reviewed", "resolved", "dismissed"]
    if report_update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(valid_statuses)}",
        )

    # Update report
    report.status = report_update.status
    report.admin_notes = report_update.admin_notes
    report.reviewed_by = current_admin.id
    report.reviewed_at = datetime.now(UTC)

    db.commit()
    db.refresh(report)

    logger.info(f"Report updated: {report_id} by admin {current_admin.id}")
    return report


@router.get(
    "/reports/pending/count",
    responses={
        403: {"description": "Admin access required"},
    },
)
async def get_pending_reports_count(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> Dict[str, int]:
    """Get count of pending reports (admin only)."""
    count = (
        db.query(DBGlobalPartReport)
        .filter(DBGlobalPartReport.status == "pending")
        .count()
    )
    logger.info(f"Pending reports count: {count}")
    return {"pending_count": count}
