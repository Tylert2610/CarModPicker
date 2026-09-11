"""
Bug reports endpoint for handling bug reports.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import get_current_admin_user, get_optional_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.bug_report import (
    BugReportCreate,
    BugReportRead,
    BugReportUpdate,
    BugReportWithDetails,
)
from app.api.services.bug_report_service import BugReportService
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    create_paginated_response,
    get_standard_public_endpoint_dependencies,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()

bug_report_service = BugReportService()


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of bug reports",
    ),
)
async def count_bug_reports(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    """Get total count of bug reports."""
    try:
        count = repos.bug_reports.count()
        logger.info(f"Retrieved bug reports count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting bug reports: {str(e)}")
        raise


@router.post(
    "/",
    response_model=BugReportRead,
    responses=standard_responses(
        success_description="Bug report created successfully",
        validation_error=True,
    ),
)
async def create_bug_report(
    bug_report_data: BugReportCreate,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> BugReportRead:
    """Create a new bug report. Can be created by authenticated or anonymous users."""
    user_id = current_user.id if current_user else None
    bug_report = bug_report_service.create_bug_report(
        bug_report_data=bug_report_data,
        user_id=user_id,
        logger=logger,
    )
    return BugReportRead.model_validate(bug_report)


@router.get(
    "/admin/list",
    response_model=List[BugReportRead],
    responses=standard_responses(
        success_description="Bug reports retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_bug_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    skip: int = Query(0, ge=0, description="Number of bug reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of bug reports to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[BugReportRead]:
    """List bug reports with optional filtering. Admin only."""
    logger = deps["logger"]

    return bug_report_service.get_bug_reports(
        status=status,
        priority=priority,
        skip=skip,
        limit=limit,
        logger=logger,
    )


@router.get(
    "/admin/list-with-details",
    responses=standard_responses(
        success_description="Bug reports with details retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_bug_reports_with_details(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    skip: int = Query(0, ge=0, description="Number of bug reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of bug reports to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """List bug reports with detailed information. Admin only."""
    logger = deps["logger"]

    bug_reports, total_count = bug_report_service.get_bug_reports_with_details(
        status=status,
        priority=priority,
        skip=skip,
        limit=limit,
        logger=logger,
    )

    return create_paginated_response(
        data=bug_reports,
        total=total_count,
        skip=skip,
        limit=limit,
    )


@router.put(
    "/{bug_report_id}",
    response_model=BugReportRead,
    responses=standard_responses(
        success_description="Bug report updated successfully",
        validation_error=True,
        not_found=True,
        unauthorized=True,
        forbidden=True,
    ),
)
async def update_bug_report(
    bug_report_id: UUID,
    bug_report_update: BugReportUpdate,
    current_user: DBUser = Depends(get_current_admin_user),
) -> BugReportRead:
    """Update a bug report (typically for admin review). Admin only."""
    bug_report = bug_report_service.update_bug_report(
        bug_report_id=bug_report_id,
        bug_report_update=bug_report_update,
        logger=logger,
    )
    return BugReportRead.model_validate(bug_report)


@router.delete(
    "/{bug_report_id}",
    responses=standard_responses(
        success_description="Bug report deleted successfully",
        not_found=True,
        unauthorized=True,
        forbidden=True,
    ),
)
async def delete_bug_report(
    bug_report_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    """Delete a bug report (admin only)."""
    bug_report_service.delete_bug_report(
        bug_report_id=bug_report_id,
        logger=logger,
    )
    return {"message": "Bug report deleted successfully"}


@router.get(
    "/{bug_report_id}",
    response_model=BugReportWithDetails,
    responses=standard_responses(
        success_description="Bug report retrieved successfully",
        not_found=True,
        unauthorized=True,
        forbidden=True,
    ),
)
async def get_bug_report(
    bug_report_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
) -> BugReportWithDetails:
    """Get a specific bug report with details. Admin only."""
    bug_report = bug_report_service.get_bug_report_by_id(
        bug_report_id=bug_report_id,
        logger=logger,
    )

    if not bug_report:
        ResponsePatterns.raise_not_found("Bug report", bug_report_id)

    return bug_report
