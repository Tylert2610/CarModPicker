from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter()


@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get current subscription status and limits for the authenticated user.
    """
    return SubscriptionService.get_subscription_status(db, current_user)


@router.post("/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    upgrade_data: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Upgrade user to premium subscription.
    """
    if upgrade_data.tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only premium tier upgrades are supported",
        )

    if (
        current_user.subscription_tier == "premium"
        and current_user.subscription_status == "active"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active premium subscription",
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

    return subscription


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Cancel premium subscription.
    """
    if current_user.subscription_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a premium subscription to cancel",
        )

    if current_user.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not active",
        )

    updated_user = SubscriptionService.cancel_subscription(db, current_user)

    # Get the latest subscription record
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == updated_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    return subscription


@router.get("/limits/check")
async def check_creation_limits(
    resource_type: str,  # 'car' or 'build_list'
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check if user can create a specific resource type.
    """
    if resource_type == "car":
        can_create = SubscriptionService.can_create_car(db, current_user)
    elif resource_type == "build_list":
        can_create = SubscriptionService.can_create_build_list(db, current_user)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type. Must be 'car' or 'build_list'",
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
