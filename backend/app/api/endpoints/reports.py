"""
Unified reports endpoint for all entity types.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.report import (
    EntityType,
    ReportCreate,
    ReportRead,
    ReportUpdate,
    ReportWithDetails,
)
from app.api.services.report_service import ReportService
from app.api.utils.common_patterns import create_paginated_response
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()

report_service = ReportService()


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of reports",
    ),
)
async def count_reports(
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Get total count of reports."""
    try:
        count = repos.reports.count()
        logger.info(f"Retrieved reports count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting reports: {str(e)}")
        raise


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=ReportRead,
    responses=standard_responses(
        success_description="Report created successfully",
        validation_error=True,
        not_found=True,
        conflict=True,
    ),
)
async def report_entity(
    entity_type: EntityType,
    entity_id: UUID,
    report_data: ReportCreate,
    current_user: DBUser = Depends(get_current_user),
) -> ReportRead:
    """Report an entity (build list or global part) for admin review."""
    report = report_service.create_report(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
        report_data=report_data,
        logger=logger,
    )
    return ReportRead.model_validate(report)


@router.get(
    "/admin/list",
    response_model=List[ReportRead],
    responses=standard_responses(
        success_description="Reports retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_reports(
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reports to return"),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[ReportRead]:
    """List reports with optional filtering. Admin only."""
    return report_service.get_reports(
        entity_type=entity_type,
        status=status,
        skip=skip,
        limit=limit,
        logger=logger,
    )


@router.get(
    "/my-reports",
    response_model=List[ReportRead],
    responses=standard_responses(
        success_description="User's reports retrieved successfully",
    ),
)
async def get_my_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reports to return"),
    current_user: DBUser = Depends(get_current_user),
) -> List[ReportRead]:
    """Get all reports created by the current user."""
    return report_service.get_user_reports(
        user_id=current_user.id,
        status=status,
        skip=skip,
        limit=limit,
        logger=logger,
    )


@router.get(
    "/admin/list-with-details",
    responses=standard_responses(
        success_description="Reports with details retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_reports_with_details(
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reports to return"),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """List reports with detailed information. Admin only."""
    reports, total_count = report_service.get_reports_with_details(
        entity_type=entity_type,
        status=status,
        skip=skip,
        limit=limit,
        logger=logger,
    )

    return create_paginated_response(
        data=reports,
        total=total_count,
        skip=skip,
        limit=limit,
    )


@router.put(
    "/{report_id}",
    response_model=ReportRead,
    responses=standard_responses(
        success_description="Report updated successfully",
        validation_error=True,
        not_found=True,
        unauthorized=True,
        forbidden=True,
    ),
)
async def update_report(
    report_id: UUID,
    report_update: ReportUpdate,
    current_user: DBUser = Depends(get_current_admin_user),
) -> ReportRead:
    """Update a report (typically for admin review). Admin only."""
    report = report_service.update_report(
        report_id=report_id,
        status=report_update.status.value,
        admin_notes=report_update.admin_notes,
        reviewer_id=current_user.id,
        logger=logger,
    )
    return ReportRead.model_validate(report)


@router.delete(
    "/{report_id}",
    responses=standard_responses(
        success_description="Report deleted successfully",
        not_found=True,
        unauthorized=True,
        forbidden=True,
    ),
)
async def delete_report(
    report_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    """Delete a report (admin only)."""
    report_service.delete_report(
        report_id=report_id,
        logger=logger,
    )
    return {"message": "Report deleted successfully"}


@router.get(
    "/{report_id}",
    response_model=ReportWithDetails,
    responses=standard_responses(
        success_description="Report retrieved successfully",
        not_found=True,
    ),
)
async def get_report(
    report_id: UUID,
    current_user: DBUser = Depends(get_current_user),
) -> ReportWithDetails:
    """Get a specific report with details. Users can access their own reports, admins can access any report."""
    report = report_service.get_report_by_id(
        report_id=report_id,
        current_user_id=current_user.id,
        is_admin=current_user.is_admin,
        logger=logger,
    )

    if not report:
        ResponsePatterns.raise_not_found("Report", report_id)

    return report
