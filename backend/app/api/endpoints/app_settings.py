"""Global app settings endpoints.

Stores a single DynamoDB item with runtime-mutable toggles that apply to
every user (e.g. the premium-system kill switch that disables ads, gates,
"""

import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_admin_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.app_settings import AppSettingsRead, AppSettingsUpdate
from app.api.utils.endpoint_decorators import standard_responses
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=AppSettingsRead,
    responses=standard_responses(success_description="Current global app settings"),
)
async def get_app_settings(repos: Repositories = Depends(get_repositories)) -> AppSettingsRead:
    """Public: current global app settings (used by the frontend to honor toggles)."""
    return AppSettingsRead.model_validate(repos.app_settings.get_or_create())


@router.put(
    "",
    response_model=AppSettingsRead,
    responses=standard_responses(
        success_description="App settings updated",
        forbidden=True,
    ),
)
async def update_app_settings(
    update: AppSettingsUpdate,
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> AppSettingsRead:
    """Admin-only: update global app settings. Only provided fields change."""
    data = update.model_dump(exclude_unset=True)
    current = repos.app_settings.update_settings(**data)
    logger.info("Admin %s updated app settings: %s", current_user.id, data)
    return AppSettingsRead.model_validate(current)
