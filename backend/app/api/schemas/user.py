from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.api.schemas.auth import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, OAuthAccountRead
from app.api.schemas.part import apply_image_url_presigning

# Max length for social profile URLs (RFC 7230 recommends 8000; we use 500 for profile links)
SOCIAL_URL_MAX_LENGTH = 500

# Allowed host substrings per platform (URL host must contain one of these)
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


# Schema for request body when creating a user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


# Schema for request body when updating a user
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    image_urls: Optional[List[str]] = None
    current_password: Optional[str] = None
    otp: Optional[str] = None  # Required if 2FA is enabled and changing password
    # Social profile links (optional; validated per platform)
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    session_expire_minutes: Optional[int] = (
        None  # User preference; None = server default. Valid range enforced in backend config.
    )

    @field_validator("instagram_url", mode="before")
    @classmethod
    def validate_instagram_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Instagram", SOCIAL_PLATFORM_HOSTS["instagram"])

    @field_validator("facebook_url", mode="before")
    @classmethod
    def validate_facebook_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Facebook", SOCIAL_PLATFORM_HOSTS["facebook"])

    @field_validator("reddit_url", mode="before")
    @classmethod
    def validate_reddit_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Reddit", SOCIAL_PLATFORM_HOSTS["reddit"])

    @field_validator("youtube_url", mode="before")
    @classmethod
    def validate_youtube_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "YouTube", SOCIAL_PLATFORM_HOSTS["youtube"])

    @field_validator("tiktok_url", mode="before")
    @classmethod
    def validate_tiktok_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "TikTok", SOCIAL_PLATFORM_HOSTS["tiktok"])


# Schema for admin operations when updating a user
class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    image_urls: Optional[List[str]] = None
    is_superuser: Optional[bool] = None
    is_admin: Optional[bool] = None
    email_verified: Optional[bool] = None
    subscription_tier: Optional[str] = None  # 'free' or 'premium'
    subscription_status: Optional[str] = None  # 'active', 'cancelled', or 'expired'
    subscription_expires_at: Optional[datetime] = None

    @field_validator("subscription_tier", mode="before")
    @classmethod
    def validate_subscription_tier(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("free", "premium"):
            raise ValueError("subscription_tier must be 'free' or 'premium'")
        return s

    @field_validator("subscription_status", mode="before")
    @classmethod
    def validate_subscription_status(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("active", "cancelled", "expired"):
            raise ValueError("subscription_status must be 'active', 'cancelled', or 'expired'")
        return s


# `UserRead` takes `email` as a plain `str`, deliberately, while the write
# models above keep `EmailStr`. `PublicUserRead` does not carry `email` at all.
#
# A response model has to be able to serialise anything the write path
# legitimately accepted, plus anything already sitting in the table. It cannot,
# when it revalidates a stored value with a rule stricter than the one that let
# the value in. `email` is a plain `str` on the DynamoDB row
# (`app/db/dynamo/users.py`), so the stored value is whatever the writer put
# there, and `EmailStr` re-runs full `email-validator` checks on the way out.
#
# That is not hypothetical. Staging users are seeded with addresses under
# `staging.invalid`, and `.invalid` is an IANA special-use reserved TLD that
# `email-validator` rejects. Reading one of those rows raised a `ValidationError`
# inside response serialisation, which surfaces as an unhandled HTTP 500 rather
# than as a 422, because by then the request has already succeeded and there is
# no request body left to blame. It fired the
# `carmodpicker-staging-application-errors` alarm.
#
# Returning the stored value is strictly better than 500ing on it: the caller
# can see and correct a bad address, and an operator can read the row. Input
# validation stays where it belongs, on `UserCreate`, `UserUpdate` and
# `AdminUserUpdate`, so no new bad address can be written through the API.
#
# `PublicUserRead` drops `email` outright rather than relaxing it. The public
# shape is what `/api/search` and an unauthenticated `GET /api/users/{id}`
# return, so every address it carried was readable by anyone who could guess a
# username fragment; the search page rendered them verbatim on each result card.
# Nothing needs the field: the only reader was that card, and a signed-in user's
# own address still comes from `UserRead` via `/api/users/me`. Removing it ends
# the exposure and removes the last read path that could 500 on a stored
# address, which relaxing the type alone would not have done.


# Schema for public user data (excludes sensitive fields like email_verified and totp_enabled)
class PublicUserRead(BaseModel):
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


# Schema for response body when reading a user (DO NOT include hashed password)
# Includes sensitive fields that should only be visible to the user themselves, admins, or superusers
class UserRead(BaseModel):
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
    # Linked third-party sign-in providers. Empty list when none. Eagerly loaded
    # in admin list endpoint via selectinload to avoid N+1; safely lazy elsewhere
    # (each UserRead serialization triggers at most one extra query for one user).
    oauth_accounts: List[OAuthAccountRead] = []

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)
