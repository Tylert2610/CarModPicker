import hmac
from datetime import timedelta
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from webbpulse.log_context import user_id_var
from webbpulse.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
)
from webbpulse.security import verify_password as _verify_password

from app.api.dependencies.repositories import Repositories, get_repositories
from app.core.config import settings
from app.db.dynamo.users import User as DBUser

ALGORITHM = settings.JWT_ALGORITHM

__all__ = [
    "ALGORITHM",
    "create_access_token",
    "decode_access_token",
    "get_access_token_expires_delta_for_user",
    "get_current_active_user_optional",
    "get_current_admin_user",
    "get_current_superuser",
    "get_current_user",
    "get_optional_current_user",
    "get_password_hash",
    "require_api_key_or_admin",
    "verify_api_key",
    "verify_password",
]


# OAuth2 scheme for Bearer token extraction (FastAPI standard)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token")
# auto_error=False for optional endpoints that can work without auth
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token", auto_error=False)

# --- Password Utilities ---
#
# Both of these are `webbpulse.security` under this app's existing names, kept as
# thin functions rather than bare import aliases so the names the rest of the
# codebase already calls stay stable and adopting the package is not also a
# rename touching a hundred call sites.
#
# The package writes bcrypt at cost 12, which is exactly what the local
# implementation passed explicitly, so every stored hash keeps verifying and
# nothing needs re-hashing.
#
# What changes is the 72 byte boundary. bcrypt reads at most 72 bytes, and 5.0.0,
# which this app pins, raises ValueError on anything longer instead of
# truncating. The schemas cap a password at 72 *characters*, and a character is
# not a byte: 72 accented or CJK characters are well over 72 bytes, passed
# validation, and then took the hash call into a 500. The package truncates to
# 72 bytes itself, on a byte boundary, so those passwords now hash and verify
# instead. See tests/auth/test_long_password_regression.py.


def get_password_hash(password: str) -> str:
    """Hashes a plain password with bcrypt at cost 12."""
    return hash_password(password)


def verify_password(plain_password: str, hashed_password_str: Optional[str]) -> bool:
    """Verifies a plain password against a hashed password.

    Returns False if the user has no password set (OAuth-only account), which is
    a real state here rather than an error, and False rather than raising on a
    stored value that is not a parseable bcrypt hash.
    """
    return _verify_password(plain_password, hashed_password_str)


# --- JWT Utilities ---


def get_access_token_expires_delta_for_user(user: DBUser) -> timedelta:
    """Returns the access token expiry duration for a user (their preference clamped to server bounds)."""
    minutes = getattr(user, "session_expire_minutes", None)
    if minutes is None:
        minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    minutes = max(
        settings.ACCESS_TOKEN_EXPIRE_MINUTES_MIN,
        min(settings.ACCESS_TOKEN_EXPIRE_MINUTES_MAX, minutes),
    )
    return timedelta(minutes=minutes)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token.

    A thin wrapper over `webbpulse.security.create_token` that keeps this app's
    two local decisions: the default expiry comes from settings when the caller
    passes none, and the algorithm is `settings.JWT_ALGORITHM` rather than the
    package default, so an operator overriding the setting still signs and
    verifies with the same one.

    The package additionally stamps `iat`, which the local implementation did
    not. That is additive: nothing in this app requires `iat` to be absent, and
    a token minted before this change still decodes, so existing sessions are
    unaffected.
    """
    return create_token(
        data,
        settings.SECRET_KEY,
        expires_in=(
            expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a token minted by `create_access_token` and return its claims.

    Raises `webbpulse.security.ExpiredToken` or `InvalidToken`, both of which
    are `TokenError`. Callers that treated every decode failure the same way
    catch `TokenError`; that is the same set of failures PyJWT's
    `InvalidTokenError` covered here before, including expiry.

    The algorithm list is always explicit and never read from the token header,
    which is what refuses `alg: none` and the RS256-verified-as-HMAC confusion.
    """
    return decode_token(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


# --- Dependency to Get Current User ---


async def get_current_user(
    token: str = Depends(oauth2_scheme),  # Bearer token from Authorization header (FastAPI standard)
    repos: Repositories = Depends(get_repositories),
) -> DBUser:
    """
    Decodes JWT Bearer token from Authorization header, validates credentials, and returns the user.
    Uses standard OAuth2 Bearer token authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except TokenError:
        raise credentials_exception

    user = repos.users.get_by_username(username)
    if user is None:
        raise credentials_exception
    if user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email not verified")
    user_id_var.set(str(user.id))
    return user


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """
    Decodes JWT Bearer token and returns the user, or None if not authenticated.
    This is for endpoints that can work with or without authentication.
    Uses standard OAuth2 Bearer token authentication.
    """
    if token is None:
        return None

    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None
    except TokenError:
        return None

    user = repos.users.get_by_username(username)
    if user is None or user.disabled or not user.email_verified:
        return None

    user_id_var.set(str(user.id))
    return user


async def get_current_active_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """
    Optionally returns the current active user if a valid Bearer token is present.
    Returns None if no token, token is invalid/expired, user not found, or user is inactive.
    Uses standard OAuth2 Bearer token authentication.
    """
    if token is None:
        return None
    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None  # Invalid token payload
    except TokenError:  # Covers expired, invalid signature, etc.
        return None  # Token is invalid or expired

    user = repos.users.get_by_username(username)
    if user is None:
        return None  # User from token not found in DB

    if user.disabled:
        return None  # User is inactive, so not considered an "active user"

    user_id_var.set(str(user.id))
    return user


# --- Admin/Superuser Dependencies ---


async def get_current_admin_user(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be an admin.
    """
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_superuser(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


# --- API key or admin dependencies -------------------------------------------
#
# The batch price-history route is written to by two kinds of caller that are
# not interactive users: the Chrome extension and ingestion/admin jobs. Neither
# should need a per-user account, so they present the shared `X-API-Key` secret
# instead; an admin bearer token is the human path to the same route.

API_KEY_HEADER = "X-API-Key"

api_key_header_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def verify_api_key(presented: Optional[str]) -> bool:
    """True when `presented` matches the configured `EXTENSION_API_KEY`.

    Compared with `hmac.compare_digest` so the check does not leak the key
    through its own timing. An unconfigured (empty) key never matches, so a
    deployment that forgets to set it fails closed rather than accepting the
    empty string.
    """
    if not presented:
        return False
    configured = settings.EXTENSION_API_KEY
    if not configured:
        return False
    return hmac.compare_digest(presented, configured)


async def require_api_key_or_admin(
    api_key: Optional[str] = Depends(api_key_header_scheme),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """Allow a valid `X-API-Key`, or an admin bearer token, and nothing else.

    Returns the authenticated admin user, or `None` when the caller got in on
    the API key (there is no user behind a machine credential). Raises through
    the app's normal `HTTPException` path:

      - no credential at all, or a bad/unknown key with no token -> 401
      - a valid token belonging to a non-admin user -> 403
    """
    if verify_api_key(api_key):
        return None

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_current_user(token=token, repos=repos)
    return await get_current_admin_user(current_user=user)
