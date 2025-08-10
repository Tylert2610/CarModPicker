from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
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
from app.core.config import settings
from app.core.email import send_email
from app.db.session import get_db

router = APIRouter()


@router.post("/token", response_model=UserRead)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate user, set JWT token in an HTTP-only cookie, and return user details.
    Takes form data: username and password.
    """
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

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
    return user  # Return user information


@router.post("/verify-email")
async def verify_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    token = create_access_token(
        data={"sub": user.email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )
    verify_url = f"http://localhost:8000/api/auth/verify-email/confirm?token={token}"
    send_email(
        user.email,
        settings.SENDGRID_VERIFY_EMAIL_TEMPLATE_ID,
        {"verify_email_link": verify_url},
    )
    return {"message": "Verification email sent"}


@router.get("/verify-email/confirm")
async def verify_email_confirm(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    if settings.DEBUG:
        frontend_base_url = "http://localhost:4000/verify-email/confirm"
    else:
        frontend_base_url = "http://carmodpicker.webbpulse.com/verify-email/confirm"
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        email = payload.get("sub")
        purpose = payload.get("purpose")
        if not email or purpose != "verify_email":
            # Invalid token purpose or missing email
            redirect_url = (
                f"{frontend_base_url}?status=error&message=Invalid+verification+token"
            )
            return RedirectResponse(url=redirect_url)
    except JWTError:
        # Invalid or expired token
        redirect_url = (
            f"{frontend_base_url}?status=error&message=Invalid+or+expired+token"
        )
        return RedirectResponse(url=redirect_url)

    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        # User not found
        redirect_url = f"{frontend_base_url}?status=error&message=User+not+found"
        return RedirectResponse(url=redirect_url)

    if user.email_verified:
        # Email already verified
        redirect_url = f"{frontend_base_url}?status=info&message=Email+already+verified"
        return RedirectResponse(url=redirect_url)

    # Proceed with email verification
    user.email_verified = True
    db.commit()
    db.refresh(user)

    # Successful verification
    redirect_url = (
        f"{frontend_base_url}?status=success&message=Email+verified+successfully"
    )
    return RedirectResponse(url=redirect_url)


@router.post("/forgot-password")
async def reset_password(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_access_token(
        data={"sub": user.email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        frontend_reset_url_base = "http://localhost:4000/forgot-password/confirm"
    else:
        frontend_reset_url_base = (
            "https://carmodpicker.webbpulse.com/forgot-password/confirm"
        )

    new_password_frontend_url = f"{frontend_reset_url_base}?token={token}"
    send_email(
        user.email,
        settings.SENDGRID_RESET_PASSWORD_TEMPLATE_ID,
        {"reset_password_link": new_password_frontend_url},
    )
    return {"message": "Password reset email sent"}


@router.post("/forgot-password/confirm")
async def reset_password_confirm(
    token: str = Query(...),
    new_password_data: NewPassword = Body(...),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        email = payload.get("sub")
        purpose = payload.get("purpose")
        if email is None or purpose != "reset_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token purpose or missing email",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(new_password_data.password)
    db.commit()
    return {"message": "Password has been reset successfully"}


@router.post("/logout")
async def logout(response: Response):
    """
    Invalidate the user's session by clearing the access token cookie.
    """
    response.delete_cookie("access_token", path="/")
    return {"message": "Successfully logged out"}
