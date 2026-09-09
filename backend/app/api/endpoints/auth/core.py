"""Authentication core endpoints: token issuance, email verification, password reset, logout."""

from __future__ import annotations

import logging
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from webbpulse.security import TokenError

from app.api.dependencies.auth import (
    create_access_token,
    decode_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.auth import (
    NewPassword,
    TOTPLoginRequest,
)
from app.api.schemas.user import UserRead
from app.api.services.user_service import user_read
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.core.email import send_reset_password_email, send_verify_email
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead | bool]:
    """
    Authenticate user and return access token and user details.
    Takes form data: username and password.
    If 2FA is enabled, returns requires_2fa: true and user must call /token/2fa to complete login.
    Returns Bearer token in response body for standard OAuth2 flow.
    """
    user = repos.users.get_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        ResponsePatterns.raise_unauthorized("Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    if user.disabled:
        logger.warning(f"Login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")
    if user.is_service_account:
        logger.warning(f"Login attempt for service account: {user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})

    # Check if 2FA is enabled
    if user.totp_enabled:
        logger.info(f"2FA enabled for user: {user.username}, requiring OTP verification")
        return {
            "requires_2fa": True,
            "message": "2FA is enabled. Please provide OTP code.",
        }

    access_token_data = {"sub": user.username}
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data=access_token_data, expires_delta=expires_delta)

    logger.info(f"User logged in successfully: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_read(user, repos),
    }


@router.post("/token/2fa")
async def login_with_2fa(
    request: TOTPLoginRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead]:
    """
    Complete login with 2FA OTP code.
    User must have called /token first to verify username/password.
    """
    user = repos.users.get_by_username(request.username)
    if not user:
        logger.warning(f"2FA login attempt for non-existent user: {request.username}")
        ResponsePatterns.raise_unauthorized("Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

    if user.disabled:
        logger.warning(f"2FA login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")

    if not user.totp_enabled:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    if not user.totp_secret:
        logger.error(f"2FA enabled but no secret found for user: {user.username}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Verify password again for security
    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Invalid password in 2FA login for user: {user.username}")
        ResponsePatterns.raise_unauthorized("Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

    # Verify OTP
    try:
        totp = pyotp.TOTP(user.totp_secret)
    except Exception as e:
        logger.error(f"Invalid TOTP secret format for user: {user.username}, error: {str(e)}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    if not totp.verify(request.otp, valid_window=1):  # Allow 1 time step window for clock skew
        logger.warning(f"Invalid OTP provided for user: {user.username}")
        ResponsePatterns.raise_unauthorized("Invalid OTP code", headers={"WWW-Authenticate": "Bearer"})

    access_token_data = {"sub": user.username}
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data=access_token_data, expires_delta=expires_delta)

    logger.info(f"User logged in successfully with 2FA: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_read(user, repos),
    }


@router.post("/verify-email")
async def verify_email(
    email: str = Body(..., embed=True),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Send verification email to user."""
    user = repos.users.get_by_email(email)
    if not user:
        logger.warning(f"Email verification requested for non-existent email: {email}")
        ResponsePatterns.raise_not_found("User")
    if user.email_verified:
        logger.info(f"Email verification requested for already verified email: {email}")
        ResponsePatterns.raise_conflict("Email already verified", "EMAIL_ALREADY_VERIFIED")

    token = create_access_token(
        data={"sub": user.email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        verify_url = f"http://localhost:8000/api/auth/verify-email/confirm?token={token}"
    else:
        verify_url = f"https://api.carmodpicker.com/api/auth/verify-email/confirm?token={token}"

    if not send_verify_email(user.email, verify_url):
        ResponsePatterns.raise_internal_server_error("Failed to send verification email")
    logger.info(f"Verification email sent to: {email}")
    return {"message": "Verification email sent"}


@router.get("/verify-email/confirm")
async def verify_email_confirm(
    token: str = Query(...),
    repos: Repositories = Depends(get_repositories),
) -> RedirectResponse:
    """Confirm email verification with token."""
    frontend_base_url = f"{settings.frontend_base_url}/verify-email/confirm"

    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "verify_email":
            logger.warning("Invalid email verification token")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=error&message=Invalid+or+expired+verification+link",
                status_code=302,
            )

        user = repos.users.get_by_email(email)
        if not user:
            logger.warning(f"Email verification attempted for non-existent user: {email}")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=error&message=User+not+found",
                status_code=302,
            )

        if user.email_verified:
            logger.info(f"Email verification attempted for already verified user: {email}")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=info&message=Email+already+verified",
                status_code=302,
            )

        repos.users.update(user.id, email_verified=True)
        logger.info(f"Email verified successfully for user: {email}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=success&message=Email+verified+successfully",
            status_code=302,
        )

    except TokenError as e:
        logger.warning(f"JWT error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=error&message=Invalid+or+expired+verification+link",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=error&message=Something+went+wrong.+Please+try+again.",
            status_code=302,
        )


@router.post("/reset-password")
async def reset_password(
    email: str = Body(..., embed=True),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Send password reset email to user."""
    user = repos.users.get_by_email(email)
    if not user:
        logger.warning(f"Password reset requested for non-existent email: {email}")
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, a password reset link has been sent"}

    token = create_access_token(
        data={"sub": user.email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    reset_url = f"{settings.frontend_base_url}/forgot-password/confirm?token={token}"

    if not send_reset_password_email(user.email, reset_url):
        ResponsePatterns.raise_internal_server_error("Failed to send password reset email")
    logger.info(f"Password reset email sent to: {email}")
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password/confirm")
async def reset_password_confirm(
    token: str = Body(..., embed=True),
    new_password: NewPassword = Body(...),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Confirm password reset with token and new password."""
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "reset_password":
            logger.warning("Invalid password reset token")
            ResponsePatterns.raise_bad_request("Invalid or expired reset token")

        user = repos.users.get_by_email(email)
        if not user:
            logger.warning(f"Password reset attempted for non-existent user: {email}")
            ResponsePatterns.raise_not_found("User")

        # Hash the new password
        hashed_password = get_password_hash(new_password.password)
        repos.users.update(user.id, hashed_password=hashed_password)

        logger.info(f"Password reset successfully for user: {email}")
        return {"message": "Password reset successfully"}

    except TokenError as e:
        logger.warning(f"JWT error during password reset: {e}")
        ResponsePatterns.raise_bad_request("Invalid or expired reset token")
    except HTTPException:
        # Re-raise HTTPException so it's not caught by the generic handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to reset password")


@router.post("/logout")
async def logout(
    current_user: DBUser = Depends(get_current_user),
) -> dict[str, str]:
    """
    Logout endpoint for client-side token removal.
    Note: With Bearer tokens, the client is responsible for removing the token from storage.
    Auth-gated so unauthenticated callers get a clean 401 (AUTH-03 / D-31 post-split truth).
    """
    logger.info(f"User logged out successfully: {current_user.username}")
    return {"message": "Logged out successfully"}
