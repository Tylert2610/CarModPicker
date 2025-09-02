"""
Base report router with common patterns to reduce redundancy.
"""

from typing import TypeVar, Generic, Type, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.user import User as DBUser
from app.api.services.base_report_service import BaseReportService
from app.core.logging import get_logger
from app.db.session import get_db

# Generic types
ReportModelType = TypeVar("ReportModelType")
ReportCreateSchema = TypeVar("ReportCreateSchema")
ReportReadSchema = TypeVar("ReportReadSchema")
EntityModelType = TypeVar("EntityModelType")


class BaseReportRouter(
    Generic[ReportModelType, ReportCreateSchema, ReportReadSchema, EntityModelType]
):
    """
    Base report router that provides common reporting endpoint patterns.

    This class eliminates redundancy by providing standardized implementations
    for common reporting operations like create report, get reports, and update status.
    """

    def __init__(
        self,
        service: BaseReportService[
            ReportModelType, ReportCreateSchema, ReportReadSchema, EntityModelType
        ],
        router: APIRouter,
        entity_name: str = "entity",
        report_entity_id_param: str = "entity_id",
    ):
        """
        Initialize the base report router.

        Args:
            service: Report service instance
            router: FastAPI router instance
            entity_name: Human-readable name of the entity type
            report_entity_id_param: URL parameter name for the entity ID
        """
        self.service = service
        self.router = router
        self.entity_name = entity_name
        self.report_entity_id_param = report_entity_id_param

        # Register common report endpoints
        self._register_common_report_endpoints()

    def _register_common_report_endpoints(self):
        """Register common reporting endpoints."""

        # Create report endpoint
        @self.router.post(
            f"/{{{self.report_entity_id_param}}}/report",
            response_model=ReportReadSchema,
            responses={
                400: {"description": f"Invalid report data"},
                404: {"description": f"{self.entity_name.title()} not found"},
                409: {
                    "description": f"You have already reported this {self.entity_name}"
                },
            },
        )
        async def create_report(
            entity_id: int,
            report: ReportCreateSchema,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> ReportModelType:
            """Create a report for an entity."""
            return self.service.create_report(
                db=db,
                entity_id=entity_id,
                user_id=current_user.id,
                report_data=report,
                logger=logger,
            )

        # Get reports for entity endpoint
        @self.router.get(
            f"/{{{self.report_entity_id_param}}}/reports",
            response_model=List[ReportReadSchema],
            responses={
                200: {
                    "description": f"Reports for {self.entity_name} retrieved successfully"
                },
                404: {"description": f"{self.entity_name.title()} not found"},
            },
        )
        async def get_reports_by_entity(
            entity_id: int,
            status: str = Query(None, description="Filter by report status"),
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
        ) -> List[ReportModelType]:
            """Get all reports for a specific entity."""
            return self.service.get_reports_by_entity(
                db=db,
                entity_id=entity_id,
                logger=logger,
                status=status,
            )

        # Get report summary endpoint
        @self.router.get(
            f"/{{{self.report_entity_id_param}}}/report-summary",
            responses={
                200: {
                    "description": f"Report summary for {self.entity_name} retrieved successfully"
                },
                404: {"description": f"{self.entity_name.title()} not found"},
            },
        )
        async def get_report_summary(
            entity_id: int,
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
        ) -> Dict[str, Any]:
            """Get report summary for an entity."""
            return self.service.get_report_summary(
                db=db,
                entity_id=entity_id,
                logger=logger,
            )

        # Get user's reports endpoint
        @self.router.get(
            "/my-reports",
            response_model=List[ReportReadSchema],
            responses={
                200: {"description": "User's reports retrieved successfully"},
            },
        )
        async def get_my_reports(
            status: str = Query(None, description="Filter by report status"),
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_user),
        ) -> List[ReportModelType]:
            """Get all reports created by the current user."""
            return self.service.get_user_reports(
                db=db,
                user_id=current_user.id,
                logger=logger,
                status=status,
            )

        # Admin endpoints
        # Get pending reports endpoint (admin only)
        @self.router.get(
            "/admin/pending",
            response_model=List[ReportReadSchema],
            responses={
                200: {"description": "Pending reports retrieved successfully"},
                403: {"description": "Admin access required"},
            },
        )
        async def get_pending_reports(
            skip: int = Query(0, ge=0, description="Number of reports to skip"),
            limit: int = Query(
                100, ge=1, le=1000, description="Maximum number of reports to return"
            ),
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_admin_user),
        ) -> List[ReportModelType]:
            """Get all pending reports (admin only)."""
            return self.service.get_pending_reports(
                db=db,
                logger=logger,
                skip=skip,
                limit=limit,
            )

        # Update report status endpoint (admin only)
        @self.router.put(
            "/admin/{report_id}/status",
            response_model=ReportReadSchema,
            responses={
                200: {"description": "Report status updated successfully"},
                403: {"description": "Admin access required"},
                404: {"description": "Report not found"},
            },
        )
        async def update_report_status(
            report_id: int,
            status_update: Dict[str, Any],
            db: Session = Depends(get_db),
            logger=Depends(get_logger),
            current_user: DBUser = Depends(get_current_admin_user),
        ) -> ReportModelType:
            """Update the status of a report (admin only)."""
            new_status = status_update.get("status")
            resolution_notes = status_update.get("resolution_notes")

            if not new_status:
                raise HTTPException(
                    status_code=400,
                    detail="Status is required",
                )

            return self.service.update_report_status(
                db=db,
                report_id=report_id,
                new_status=new_status,
                admin_user_id=current_user.id,
                logger=logger,
                resolution_notes=resolution_notes,
            )

    def add_custom_report_endpoint(
        self,
        path: str,
        response_model: Type[ReportReadSchema],
        method: str = "get",
        **kwargs,
    ):
        """
        Add a custom report endpoint to the router.

        Args:
            path: URL path for the endpoint
            response_model: Response model for the endpoint
            method: HTTP method (get, post, put, delete)
            **kwargs: Additional FastAPI endpoint parameters
        """

        def decorator(func):
            if method.lower() == "get":
                self.router.get(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "post":
                self.router.post(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "put":
                self.router.put(path, response_model=response_model, **kwargs)(func)
            elif method.lower() == "delete":
                self.router.delete(path, **kwargs)(func)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            return func

        return decorator
