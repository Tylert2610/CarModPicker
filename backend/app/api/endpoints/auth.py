"""
Authentication endpoints with consistent error handling patterns.

This endpoint uses standardized patterns for error handling and response formatting
while maintaining authentication-specific functionality.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.auth import NewPassword
from app.api.schemas.user import UserRead
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.core.email import send_email
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post("/token", response_model=UserRead)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
) -> DBUser:
    """
    Authenticate user, set JWT token in an HTTP-only cookie, and return user details.
    Takes form data: username and password.
    """
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        ResponsePatterns.raise_unauthorized(
            "Incorrect username or password", headers={"WWW-Authenticate": "Bearer"}
        )
    if user.disabled:
        logger.warning(f"Login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")

    access_token_data = {"sub": user.username}
    access_token = create_access_token(data=access_token_data)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Crucial for security
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Cookie expiry in seconds
        path="/",  # Cookie available for all paths
        samesite="lax",  # Recommended for CSRF protection balance
        secure=False,  # TODO: Set to True in production if using HTTPS
    )

    logger.info(f"User logged in successfully: {user.username}")
    return user  # Return user information


@router.post("/verify-email")
async def verify_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
) -> dict[str, str]:
    """Send verification email to user."""
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        logger.warning(f"Email verification requested for non-existent email: {email}")
        ResponsePatterns.raise_not_found("User")
    if user.email_verified:
        logger.info(f"Email verification requested for already verified email: {email}")
        ResponsePatterns.raise_conflict(
            "Email already verified", "EMAIL_ALREADY_VERIFIED"
        )

    token = create_access_token(
        data={"sub": user.email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        verify_url = (
            f"http://localhost:8000/api/auth/verify-email/confirm?token={token}"
        )
    else:
        verify_url = f"https://api.carmodpicker.webbpulse.com/api/auth/verify-email/confirm?token={token}"

    try:
        send_email(
            user.email,
            settings.SENDGRID_VERIFY_EMAIL_TEMPLATE_ID,
            {"verify_email_link": verify_url},
        )
        logger.info(f"Verification email sent to: {email}")
        return {"message": "Verification email sent"}
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        ResponsePatterns.raise_internal_server_error(
            "Failed to send verification email"
        )


@router.get("/verify-email/confirm")
async def verify_email_confirm(
    token: str = Query(...),
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
) -> RedirectResponse:
    """Confirm email verification with token."""
    if settings.DEBUG:
        frontend_base_url = "http://localhost:4000/verify-email/confirm"
    else:
        frontend_base_url = "https://carmodpicker.webbpulse.com/verify-email/confirm"

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "verify_email":
            logger.warning("Invalid email verification token")
            return RedirectResponse(
                url=f"{frontend_base_url}?error=invalid_token", status_code=302
            )

        user = db.query(DBUser).filter(DBUser.email == email).first()
        if not user:
            logger.warning(
                f"Email verification attempted for non-existent user: {email}"
            )
            return RedirectResponse(
                url=f"{frontend_base_url}?error=user_not_found", status_code=302
            )

        if user.email_verified:
            logger.info(
                f"Email verification attempted for already verified user: {email}"
            )
            return RedirectResponse(
                url=f"{frontend_base_url}?error=already_verified", status_code=302
            )

        user.email_verified = True
        db.commit()
        logger.info(f"Email verified successfully for user: {email}")
        return RedirectResponse(
            url=f"{frontend_base_url}?success=true", status_code=302
        )

    except JWTError as e:
        logger.warning(f"JWT error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?error=invalid_token", status_code=302
        )
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?error=server_error", status_code=302
        )


@router.post("/reset-password")
async def reset_password(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
) -> dict[str, str]:
    """Send password reset email to user."""
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        logger.warning(f"Password reset requested for non-existent email: {email}")
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, a password reset link has been sent"}

    token = create_access_token(
        data={"sub": user.email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        reset_url = f"http://localhost:4000/reset-password?token={token}"
    else:
        reset_url = f"https://carmodpicker.webbpulse.com/reset-password?token={token}"

    try:
        send_email(
            user.email,
            settings.SENDGRID_RESET_PASSWORD_TEMPLATE_ID,
            {"reset_password_link": reset_url},
        )
        logger.info(f"Password reset email sent to: {email}")
        return {"message": "If the email exists, a password reset link has been sent"}
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        ResponsePatterns.raise_internal_server_error(
            "Failed to send password reset email"
        )


@router.post("/reset-password/confirm")
async def reset_password_confirm(
    token: str = Body(..., embed=True),
    new_password: NewPassword = Body(...),
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
) -> dict[str, str]:
    """Confirm password reset with token and new password."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "reset_password":
            logger.warning("Invalid password reset token")
            ResponsePatterns.raise_bad_request("Invalid or expired reset token")

        user = db.query(DBUser).filter(DBUser.email == email).first()
        if not user:
            logger.warning(f"Password reset attempted for non-existent user: {email}")
            ResponsePatterns.raise_not_found("User")

        # Hash the new password
        hashed_password = get_password_hash(new_password.password)
        user.hashed_password = hashed_password
        db.commit()

        logger.info(f"Password reset successfully for user: {email}")
        return {"message": "Password reset successfully"}

    except JWTError as e:
        logger.warning(f"JWT error during password reset: {e}")
        ResponsePatterns.raise_bad_request("Invalid or expired reset token")
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to reset password")


@router.post("/logout")
async def logout(
    response: Response,
    logger=Depends(get_logger),
) -> dict[str, str]:
    """Logout user by clearing the access token cookie."""
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,  # TODO: Set to True in production if using HTTPS
    )

    logger.info("User logged out successfully")
    return {"message": "Logged out successfully"}
