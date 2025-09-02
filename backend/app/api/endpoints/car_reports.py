"""
Refactored car reports endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseReportRouter to provide common reporting operations
while maintaining car-specific functionality.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.car import Car as DBCar
from app.api.models.car_report import CarReport as DBCarReport
from app.api.models.user import User as DBUser
from app.api.schemas.car_report import (
    CarReportCreate,
    CarReportRead,
    CarReportUpdate,
    CarReportWithDetails,
)
from app.api.services.car_report_service import CarReportService
from app.api.utils.base_report_router import BaseReportRouter
from app.api.utils.endpoint_decorators import standard_responses
from app.core.logging import get_logger
from app.db.session import get_db
from app.api.utils.common_patterns import get_standard_public_endpoint_dependencies

# Create router
router = APIRouter()

# Initialize the car report service
car_report_service = CarReportService()

# Create base report router
base_report_router = BaseReportRouter(
    service=car_report_service,
    router=router,
    entity_name="car",
    report_entity_id_param="car_id",
)


# Add custom car-specific endpoints
@router.get(
    "/",
    response_model=List[CarReportWithDetails],
    responses=standard_responses(
        success_description="Car reports retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def list_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    reason: Optional[str] = Query(None, description="Filter by reason"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of reports to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[CarReportWithDetails]:
    """List all reports with optional filtering (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    return car_report_service.get_reports_with_details(
        db=db, current_user=current_user, status=status, skip=skip, limit=limit
    )


@router.get(
    "/{report_id}",
    response_model=CarReportWithDetails,
    responses=standard_responses(
        success_description="Car report retrieved successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def get_report(
    report_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> CarReportWithDetails:
    """Get a specific report by ID. Admins can see all reports, users can only see their own."""
    db = deps["db"]
    logger = deps["logger"]

    return car_report_service.get_report_with_details(db, report_id, current_user)


@router.put(
    "/{report_id}",
    response_model=CarReportRead,
    responses=standard_responses(
        success_description="Car report updated successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def update_report_status(
    report_id: int,
    report_update: CarReportUpdate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> CarReportRead:
    """Update a report status (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    updated_report = car_report_service.update_report_status(
        db, report_id, report_update, current_user, logger
    )
    return CarReportRead.model_validate(updated_report)


@router.delete(
    "/{report_id}",
    response_model=Dict[str, str],
    responses=standard_responses(
        success_description="Car report deleted successfully",
        unauthorized=True,
        forbidden=True,
        not_found=True,
    ),
)
async def delete_report(
    report_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> Dict[str, str]:
    """Delete a report (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    return car_report_service.delete_report(db, report_id, current_user, logger)


@router.get(
    "/pending/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Pending reports count retrieved successfully",
        forbidden=True,
    ),
)
async def get_pending_reports_count(
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> Dict[str, int]:
    """Get count of pending reports (admin only)."""
    db = deps["db"]
    logger = deps["logger"]

    return car_report_service.get_pending_count(db, current_admin, logger)
