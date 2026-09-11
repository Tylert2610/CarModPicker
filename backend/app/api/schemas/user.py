"""Request and response schemas for user accounts and profiles."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.api.schemas.auth import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, OAuthAccountRead
from app.api.schemas.part import apply_image_url_presigning

SOCIAL_URL_MAX_LENGTH = 500

SOCIAL_PLATFORM_HOSTS = {
    "instagram": ["instagram.com"],
    "facebook": ["facebook.com", "fb.com", "fb.me"],
    "reddit": ["reddit.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
}


def _validate_social_url(value: Any, platform: str, allowed_host_substrings: list[str]) -> Optional[str]:
    """Validate optional URL: allow None/empty; otherwise require HTTP(S) and platform domain."""
    if value is None or not (isinstance(value, str) and value.strip()):
        return None
    value = value.strip()
    from pydantic import AnyHttpUrl

    try:
        url = AnyHttpUrl(value)
    except Exception:
        raise ValueError("Must be a valid HTTP or HTTPS URL")
    if len(value) > SOCIAL_URL_MAX_LENGTH:
        raise ValueError(f"URL must be at most {SOCIAL_URL_MAX_LENGTH} characters")
    host_lower = (url.host or "").lower()
    if not any(h in host_lower for h in allowed_host_substrings):
        raise ValueError(f"URL must be a {platform} profile link (e.g. https://{allowed_host_substrings[0]}/...)")
    return str(url)


class UserCreate(BaseModel):
    """Request body for registering an account."""

    username: str
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class UserUpdate(BaseModel):
    """Request body for a user editing their own account."""

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    image_urls: Optional[List[str]] = None
    current_password: Optional[str] = None
    otp: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    session_expire_minutes: Optional[int] = None

    @field_validator("instagram_url", mode="before")
    @classmethod
    def validate_instagram_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise and require an Instagram profile URL."""
        return _validate_social_url(v, "Instagram", SOCIAL_PLATFORM_HOSTS["instagram"])

    @field_validator("facebook_url", mode="before")
    @classmethod
    def validate_facebook_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise and require a Facebook profile URL."""
        return _validate_social_url(v, "Facebook", SOCIAL_PLATFORM_HOSTS["facebook"])

    @field_validator("reddit_url", mode="before")
    @classmethod
    def validate_reddit_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise and require a Reddit profile URL."""
        return _validate_social_url(v, "Reddit", SOCIAL_PLATFORM_HOSTS["reddit"])

    @field_validator("youtube_url", mode="before")
    @classmethod
    def validate_youtube_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise and require a YouTube profile URL."""
        return _validate_social_url(v, "YouTube", SOCIAL_PLATFORM_HOSTS["youtube"])

    @field_validator("tiktok_url", mode="before")
    @classmethod
    def validate_tiktok_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalise and require a TikTok profile URL."""
        return _validate_social_url(v, "TikTok", SOCIAL_PLATFORM_HOSTS["tiktok"])


class AdminUserUpdate(BaseModel):
    """Request body for an admin editing any account."""

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    image_urls: Optional[List[str]] = None
    is_superuser: Optional[bool] = None
    is_admin: Optional[bool] = None
    email_verified: Optional[bool] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None

    @field_validator("subscription_tier", mode="before")
    @classmethod
    def validate_subscription_tier(cls, v: Any) -> Optional[str]:
        """Accept only a known subscription tier."""
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("free", "premium"):
            raise ValueError("subscription_tier must be 'free' or 'premium'")
        return s

    @field_validator("subscription_status", mode="before")
    @classmethod
    def validate_subscription_status(cls, v: Any) -> Optional[str]:
        """Accept only a known subscription status."""
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("active", "cancelled", "expired"):
            raise ValueError("subscription_status must be 'active', 'cancelled', or 'expired'")
        return s


class PublicUserRead(BaseModel):
    """A user profile as shown to other users."""

    id: UUID
    username: str
    disabled: bool
    image_urls: Optional[List[str]] = None
    is_superuser: bool
    is_admin: bool
    is_service_account: bool = False
    subscription_tier: str
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)


class UserRead(BaseModel):
    """A user account as returned to its owner."""

    id: UUID
    username: str
    email: str
    disabled: bool
    email_verified: bool
    image_urls: Optional[List[str]] = None
    is_superuser: bool
    is_admin: bool
    is_service_account: bool = False
    subscription_tier: str
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None
    totp_enabled: bool = False
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    session_expire_minutes: Optional[int] = None
    oauth_accounts: List[OAuthAccountRead] = []

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)
