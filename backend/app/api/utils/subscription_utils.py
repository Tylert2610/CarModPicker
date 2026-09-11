"""
Subscription helpers for premium tier and build list caps.
"""

from datetime import UTC, datetime

from app.db.dynamo.app_settings import AppSettingsRepository
from app.db.dynamo.users import User as DBUser


def is_premium_system_disabled() -> bool:
    """Return True when the admin kill switch has disconnected the premium system."""
    return AppSettingsRepository().premium_disabled()


def is_user_premium(user: DBUser, *, check_kill_switch: bool = False) -> bool:
    """Return True if the user has an active premium subscription, OR (when

    ``check_kill_switch`` is set) if the admin kill switch has disabled the
    premium system entirely, in which case every user is treated as premium
    """
    if check_kill_switch and is_premium_system_disabled():
        return True
    if user.subscription_tier != "premium":
        return False
    if user.subscription_status != "active":
        return False
    if user.subscription_expires_at is not None and user.subscription_expires_at <= datetime.now(UTC):
        return False
    return True
