from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.models.user import User
from app.api.models.subscription import Subscription
from app.api.models.car import Car
from app.api.models.build_list import BuildList
from app.api.schemas.subscription import SubscriptionCreate, SubscriptionStatus


class SubscriptionService:
    """Service for handling subscription-related business logic"""

    # Subscription limits
    FREE_TIER_LIMITS = {
        "cars": 3,
        "build_lists": 5,
    }

    PREMIUM_TIER_LIMITS = {
        "cars": None,  # Unlimited
        "build_lists": None,  # Unlimited
    }

    @staticmethod
    def get_user_limits(user: User) -> Dict[str, Optional[int]]:
        """Get the current limits for a user based on their subscription tier"""
        if user.subscription_tier == "premium" and user.subscription_status == "active":
            return SubscriptionService.PREMIUM_TIER_LIMITS
        return SubscriptionService.FREE_TIER_LIMITS

    @staticmethod
    def get_user_usage(db: Session, user_id: int) -> Dict[str, int]:
        """Get current usage statistics for a user"""
        cars_count = db.query(Car).filter(Car.user_id == user_id).count()
        build_lists_count = (
            db.query(BuildList).filter(BuildList.user_id == user_id).count()
        )

        return {
            "cars": cars_count,
            "build_lists": build_lists_count,
        }

    @staticmethod
    def can_create_car(db: Session, user: User) -> bool:
        """Check if user can create a new car"""
        limits = SubscriptionService.get_user_limits(user)
        if limits["cars"] is None:  # Unlimited
            return True

        current_usage = SubscriptionService.get_user_usage(db, user.id)
        return current_usage["cars"] < limits["cars"]

    @staticmethod
    def can_create_build_list(db: Session, user: User) -> bool:
        """Check if user can create a new build list"""
        limits = SubscriptionService.get_user_limits(user)
        if limits["build_lists"] is None:  # Unlimited
            return True

        current_usage = SubscriptionService.get_user_usage(db, user.id)
        return current_usage["build_lists"] < limits["build_lists"]

    @staticmethod
    def get_subscription_status(db: Session, user: User) -> SubscriptionStatus:
        """Get comprehensive subscription status for a user"""
        limits = SubscriptionService.get_user_limits(user)
        usage = SubscriptionService.get_user_usage(db, user.id)

        return SubscriptionStatus(
            tier=user.subscription_tier,
            status=user.subscription_status,
            expires_at=user.subscription_expires_at,
            limits=limits,
            usage=usage,
        )

    @staticmethod
    def upgrade_to_premium(
        db: Session, user: User, expires_at: Optional[datetime] = None
    ) -> User:
        """Upgrade user to premium subscription"""
        # Set expiration to 30 days from now if not provided
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(days=30)

        user.subscription_tier = "premium"
        user.subscription_status = "active"
        user.subscription_expires_at = expires_at

        # Create subscription record
        subscription = Subscription(
            user_id=user.id,
            tier="premium",
            status="active",
            expires_at=expires_at,
        )

        db.add(subscription)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def cancel_subscription(db: Session, user: User) -> User:
        """Cancel user's premium subscription"""
        user.subscription_status = "cancelled"

        # Update subscription record
        subscription = (
            db.query(Subscription)
            .filter(
                and_(Subscription.user_id == user.id, Subscription.status == "active")
            )
            .first()
        )

        if subscription:
            subscription.status = "cancelled"

        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def check_expired_subscriptions(db: Session) -> None:
        """Check and update expired subscriptions"""
        expired_users = (
            db.query(User)
            .filter(
                and_(
                    User.subscription_tier == "premium",
                    User.subscription_status == "active",
                    User.subscription_expires_at < datetime.utcnow(),
                )
            )
            .all()
        )

        for user in expired_users:
            user.subscription_status = "expired"
            user.subscription_tier = "free"

        db.commit()
