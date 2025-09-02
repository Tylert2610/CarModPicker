"""
Refactored subscriptions endpoint using consistent patterns to eliminate redundancy.

This endpoint now uses standardized error handling, response decorators, and
service layer usage consistent with other endpoints.
"""

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.api.models.user import User
from app.api.schemas.subscription import (
    SubscriptionStatus,
    UpgradeRequest,
    SubscriptionResponse,
)
from app.api.services.subscription_service import SubscriptionService
from app.api.models.subscription import Subscription
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.api.utils.common_patterns import get_standard_public_endpoint_dependencies
from fastapi import HTTPException, status

router = APIRouter()


@router.get(
    "/status",
    response_model=SubscriptionStatus,
    responses=standard_responses(
        success_description="Subscription status retrieved successfully"
    ),
)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
    logger=Depends(get_logger),
) -> Any:
    """Get current subscription status and limits for the authenticated user."""
    status = SubscriptionService.get_subscription_status(db, current_user)
    logger.info(f"User {current_user.id} retrieved subscription status")
    return status


@router.post(
    "/upgrade",
    response_model=SubscriptionResponse,
    responses=standard_responses(
        success_description="Subscription upgraded successfully",
        conflict=True,
    ),
)
async def upgrade_subscription(
    upgrade_data: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> Any:
    """Upgrade user to premium subscription."""
    db = deps["db"]
    logger = deps["logger"]

    if upgrade_data.tier != "premium":
        ResponsePatterns.raise_bad_request(
            "Only premium tier upgrades are supported", "INVALID_TIER"
        )

    if (
        current_user.subscription_tier == "premium"
        and current_user.subscription_status == "active"
    ):
        ResponsePatterns.raise_conflict(
            "User already has an active premium subscription", "ALREADY_PREMIUM"
        )

    # In a real implementation, you would integrate with a payment processor here
    # For now, we'll just upgrade the user directly
    updated_user = SubscriptionService.upgrade_to_premium(db, current_user)

    # Get the latest subscription record
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == updated_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    logger.info(f"User {current_user.id} upgraded to premium subscription")
    return subscription


@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    responses=standard_responses(
        success_description="Subscription cancelled successfully",
        conflict=True,
    ),
)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> Any:
    """Cancel premium subscription."""
    db = deps["db"]
    logger = deps["logger"]

    if current_user.subscription_tier != "premium":
        ResponsePatterns.raise_bad_request(
            "User does not have a premium subscription to cancel",
            "NO_PREMIUM_SUBSCRIPTION",
        )

    if current_user.subscription_status != "active":
        ResponsePatterns.raise_conflict(
            "Subscription is not active", "INACTIVE_SUBSCRIPTION"
        )

    updated_user = SubscriptionService.cancel_subscription(db, current_user)

    # Get the latest subscription record
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == updated_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    logger.info(f"User {current_user.id} cancelled premium subscription")
    return subscription


@router.get("/limits/check")
async def check_creation_limits(
    resource_type: str,  # 'car' or 'build_list'
    current_user: User = Depends(get_current_user),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
) -> Any:
    """
    Check if user can create a specific resource type.
    """
    db = deps["db"]

    if resource_type == "car":
        can_create = SubscriptionService.can_create_car(db, current_user)
    elif resource_type == "build_list":
        can_create = SubscriptionService.can_create_build_list(db, current_user)
    else:
        ResponsePatterns.raise_bad_request(
            "Invalid resource type. Must be 'car' or 'build_list'"
        )

    return {"can_create": can_create}


@router.get("/limits/check/global-part")
async def check_global_part_creation_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check if user can create a global part.
    """
    can_create = SubscriptionService.can_create_global_part(db, current_user)
    return {"can_create": can_create}
