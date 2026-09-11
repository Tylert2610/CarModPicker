import hmac
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from webbpulse.log_context import user_id_var
from webbpulse.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
)
from webbpulse.security import verify_password as _verify_password

from app.api.dependencies.identity_claims import (
    identity_subject,
    verify_bearer_subject,
)
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
    "resolve_identity_user",
    "verify_api_key",
    "verify_password",
]


class IdentityAwareOAuth2(OAuth2PasswordBearer):
    """`OAuth2PasswordBearer` that does not refuse a request an authorizer vouched for.

    Row 11 of `docs/identity-adoption.md`. The parent class with `auto_error=True`
    raises 401 from the dependency itself, before the route's own resolver runs,
    whenever there is no `Authorization` header. That is the right default and it
    stays the default here: a request with nothing on it still gets the same 401
    with the same `Not authenticated` body it always did, produced by the same
    line of the same parent class.

    What it cannot see is the case row 11 exists for. On a route key listed in
    `IDENTITY_JWT_ROUTE_KEYS` the gateway verified the access token before this
    process was invoked and put the claims in the request context, so the
    credential for that request is in `x-amzn-request-context` rather than in
    `Authorization`. A caller in that position has no reason to send the token
    twice, and with the parent's behaviour unmodified the resolver that knows how
    to read those claims could never be reached: the one shape row 11 serves was
    the one shape refused before reaching the code serving it.

    So the refusal is conditional on there being nothing to fall through to.
    Returning `""` rather than raising says "no bearer token here, ask the
    request context", and `get_current_user` still raises its own 401 if the
    claims turn out to name no usable account. **This widens nothing:** the extra
    path is entered only when `identity_subject` finds a subject, which requires
    an authorizer to have run and verified a token, which is something no caller
    can fabricate. The `x-amzn-request-context` header is set by the Lambda Web
    Adapter from the invoke event and an inbound header of that name never
    reaches it.
    """

    async def __call__(self, request: Request) -> Optional[str]:
        if request.headers.get("authorization"):
            return await super().__call__(request)
        if identity_subject(request):
            return ""
        return await super().__call__(request)


# OAuth2 scheme for Bearer token extraction (FastAPI standard)
oauth2_scheme = IdentityAwareOAuth2(tokenUrl=f"{settings.API_STR}/auth/token")
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


# --- The identity access token, alongside the legacy session ---
#
# Row 11 of `docs/identity-adoption.md`. Every resolver below is dual mode: the
# legacy HS256 session resolves exactly as it did, and an identity RS256 access
# token additionally resolves to the same `DBUser`. Neither path can shadow the
# other, because the two tokens are told apart by what they carry rather than by
# a flag: a legacy session's `sub` is the **username** and is signed with
# `SECRET_KEY`, an identity token's `sub` is the **user id** and is signed in
# KMS. Row 12 is the cutover and row 13 is what deletes the legacy half.
#
# The legacy path is tried first and deliberately so. It is the path every
# request takes today, it costs one HMAC verification with no network call, and
# putting it first means the shipped flow's latency and its failure modes are
# untouched by this row. An identity token simply fails `decode_access_token`,
# because it is RS256 and the decoder names HS256 explicitly, and falls through.


def _subject_from_request(request: Optional[Request]) -> str:
    """The identity `sub` for this request, from the authorizer or from the header.

    Two sources in order, which is the order `app/composition/identity_extension.
    py` already reads one in. The authorizer's context is preferred where the
    gateway put it there, because the signature is already checked and checking
    it again is a `kms:GetPublicKey` and a verification per request to reach an
    answer that is in the event. In-process verification is the fallback, and on
    every domain but `identity` it answers `""` because that function holds
    neither the signing key ARNs nor the grant to read them. See
    `app/api/dependencies/identity_claims.py` for why that asymmetry is the
    honest state of this row rather than a gap.

    `request` is `Optional` because `require_api_key_or_admin` calls
    `get_current_user` directly rather than through `Depends`, and a machine
    caller on the API key path has no identity token to find.
    """
    if request is None:
        return ""
    subject = identity_subject(request)
    if subject:
        return subject
    return verify_bearer_subject(request)


def resolve_identity_user(request: Optional[Request], repos: Repositories) -> Optional[DBUser]:
    """The CarModPicker user an identity access token names, or `None`.

    **The mapping is the id and nothing else.** `CarModPickerIdentityHooks.
    claims_for` puts `roles` and `username` in the token and leaves `sub` to the
    package, which sets it from the user record's `id`; `load_user_by_id` parses
    that `sub` straight back to a `UUID` and does one `GetItem` on `users`. So an
    identity user *is* the legacy user row, under the same uuid7 id it always
    had, and there is no link table and no second id space. That is what makes
    row 11 a dual-mode read rather than a data migration: row 9's hooks created
    no new user rows for existing accounts, they mounted the package's flows on
    top of the rows that were already there.

    A `sub` that is not a UUID is a token this product did not mint, so it is
    `None` for the same reason `load_user_by_id` answers `None`: "no such user"
    is the honest answer and a `ValueError` here would be a 500 on a request that
    deserves a 401.

    The three account checks are the same three `may_authenticate` applies at the
    package's door, restated here for the reason the hooks module gives about
    writing them twice: that hook guards the package's login and this guards
    every domain read, and the two are independent until row 13. A token minted
    before an account was disabled must not keep working for its remaining ten
    minutes.
    """
    subject = _subject_from_request(request)
    if not subject:
        return None
    try:
        user_id = UUID(subject)
    except (AttributeError, TypeError, ValueError):
        return None

    user = repos.users.get(user_id)
    if user is None or user.disabled or not user.email_verified:
        return None
    # Set here rather than at each of the three call sites, so the log context
    # carries the user on the identity path exactly as it does on the legacy one
    # and a resolver added later cannot forget it.
    user_id_var.set(str(user.id))
    return user


# --- Dependency to Get Current User ---


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),  # Bearer token from Authorization header (FastAPI standard)
    repos: Repositories = Depends(get_repositories),
) -> DBUser:
    """
    Decodes JWT Bearer token from Authorization header, validates credentials, and returns the user.
    Uses standard OAuth2 Bearer token authentication.

    Dual mode since row 11: a legacy HS256 session resolves first and unchanged,
    and an identity RS256 access token resolves to the same row when it does not.
    See the section comment above for why that order and why the two cannot be
    confused for one another.

    The scheme this depends on is `oauth2_scheme`, which admits a request
    carrying no `Authorization` header only when an authorizer already put
    verified claims on it. See `IdentityAwareOAuth2` for why.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    username: Optional[str] = None
    if token:
        try:
            payload = decode_access_token(token)
            username = payload.get("sub")
        except TokenError:
            username = None

    if username is None:
        # Not a legacy session. An identity access token is the other thing this
        # header carries, and the account checks below are applied to it through
        # `resolve_identity_user` rather than repeated here, so that a disabled
        # or unverified account is refused identically on both paths.
        identity_user = resolve_identity_user(request, repos)
        if identity_user is None:
            raise credentials_exception
        return identity_user

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
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """
    Decodes JWT Bearer token and returns the user, or None if not authenticated.
    This is for endpoints that can work with or without authentication.
    Uses standard OAuth2 Bearer token authentication.

    Dual mode since row 11. The identity path is tried even when there is no
    `Authorization` header at all, because on a flagged route key the claims
    arrive in the request context and the header the gateway verified is not
    necessarily forwarded to the application.
    """
    username: Optional[str] = None
    if token is not None:
        try:
            username = decode_access_token(token).get("sub")
        except TokenError:
            username = None

    if username is None:
        return resolve_identity_user(request, repos)

    user = repos.users.get_by_username(username)
    if user is None or user.disabled or not user.email_verified:
        return None

    user_id_var.set(str(user.id))
    return user


async def get_current_active_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """
    Optionally returns the current active user if a valid Bearer token is present.
    Returns None if no token, token is invalid/expired, user not found, or user is inactive.
    Uses standard OAuth2 Bearer token authentication.

    Dual mode since row 11. This resolver does not require a verified address
    where the other two do, and that difference is preserved rather than
    flattened: `resolve_identity_user` does check it, so the identity path here
    is the stricter of the two. Widening it would mean a second resolver whose
    only difference is a check this row has no reason to relax, and the accounts
    it would admit are exactly the ones `may_authenticate` refuses at the
    package's own door, so no identity token is ever minted for one.
    """
    username: Optional[str] = None
    if token is not None:
        try:
            username = decode_access_token(token).get("sub")
        except TokenError:  # Covers expired, invalid signature, etc.
            username = None

    if username is None:
        return resolve_identity_user(request, repos)

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
    request: Request,
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
        # No key and no bearer token still leaves the identity path, because on a
        # flagged route key the claims arrive in the request context rather than
        # in a header this application sees.
        identity_user = resolve_identity_user(request, repos)
        if identity_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await get_current_admin_user(current_user=identity_user)

    user = await get_current_user(request=request, token=token, repos=repos)
    return await get_current_admin_user(current_user=user)
