"""Schemas for password, two factor and Google OAuth authentication flows."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


class NewPassword(BaseModel):
    """A new password constrained to the bcrypt safe length range."""

    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class TOTPSetupResponse(BaseModel):
    """Response when setting up 2FA - contains QR code data and secret."""

    secret: str
    qr_code_data: str
    manual_entry_key: str


class TOTPVerifyRequest(BaseModel):
    """Request to verify and enable 2FA."""

    otp: str


class TOTPVerifyResponse(BaseModel):
    """Response after verifying 2FA setup."""

    success: bool
    message: str


class TOTPLoginRequest(BaseModel):
    """Request for 2FA verification during login."""

    username: str
    password: str
    otp: str


class TOTPDisableRequest(BaseModel):
    """Request to disable 2FA - requires password and OTP."""

    password: str
    otp: str


class GoogleSignInRequest(BaseModel):
    """Initial Google sign-in: frontend sends the Google ID token + nonce it generated."""

    id_token: str
    nonce: str


class GoogleLinkRequest(BaseModel):
    """Merge Google identity into an existing password account. Requires the link_token from
    the initial Google sign-in plus the user's password (and OTP if 2FA enabled)."""

    link_token: str
    password: str
    otp: Optional[str] = None


class GoogleSignupRequest(BaseModel):
    """Finish account creation after Google sign-in when no matching email was found."""

    signup_token: str
    username: str


class OAuthTwoFactorRequest(BaseModel):
    """Complete 2FA after a Google sign-in for a user with TOTP enabled."""

    otp_token: str
    otp: str


class GoogleConnectRequest(BaseModel):
    """Authenticated request to link a Google account to the current user."""

    id_token: str
    nonce: str


class OAuthAccountRead(BaseModel):
    """A linked OAuth account as returned to clients."""

    id: UUID
    provider: str
    email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoogleSignInLinkRequired(BaseModel):
    """Returned by /auth/google when the email matches an existing password user.
    Frontend prompts for password and submits to /auth/google/link."""

    requires_link: bool = True
    link_token: str
    email: EmailStr
    display_name: Optional[str] = None
    has_totp: bool = False


class GoogleSignInSignupRequired(BaseModel):
    """Returned by /auth/google when no matching account exists.
    Frontend collects a username and submits to /auth/google/signup."""

    requires_signup: bool = True
    signup_token: str
    email: EmailStr
    suggested_username: str


class OAuthTwoFactorRequired(BaseModel):
    """Returned when a verified Google sign-in maps to a user with TOTP enabled."""

    requires_2fa: bool = True
    otp_token: str
