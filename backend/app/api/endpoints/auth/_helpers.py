"""Shared pieces the auth endpoints use to finish a sign in."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from app.api.dependencies.auth import (
    create_access_token,
    get_access_token_expires_delta_for_user,
)
from app.api.dependencies.repositories import Repositories
from app.api.schemas.user import UserRead
from app.api.services.user_service import user_read
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


def issue_login_response(user: DBUser, repos: Optional[Repositories] = None) -> dict[str, str | UserRead]:
    """Mint an access token for the user and return it with their profile."""
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=expires_delta)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_read(user, repos),
    }


def maybe_2fa_challenge(user: DBUser) -> Optional[dict[str, str | bool]]:
    """Return a short lived 2FA challenge when the user has TOTP enabled, else None."""
    if not user.totp_enabled:
        return None
    otp_token = create_access_token(
        data={"purpose": OAUTH_2FA_PURPOSE, "user_id": str(user.id), "source": GOOGLE_PROVIDER},
        expires_delta=timedelta(minutes=5),
    )
    return {"requires_2fa": True, "otp_token": otp_token}
