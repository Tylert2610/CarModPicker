import hmac
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from webbpulse.log_context import user_id_var
from webbpulse.security import (
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
# `scheme_name` pins the OpenAPI security scheme to the name the parent class
# would have given it. FastAPI names the scheme after the class by default, and
# the class is an implementation detail: the published contract, and the
# snapshot test that pins it, must not change because of it.
oauth2_scheme = IdentityAwareOAuth2(tokenUrl=f"{settings.API_STR}/auth/token", scheme_name="OAuth2PasswordBearer")
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


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Sign a short lived HS256 token with `SECRET_KEY`.

    **This is no longer a session token and row 13 left it deliberately.** The
    legacy sign in flow that used to mint one here is gone; what still calls
    this is the one-click unsubscribe link in a price drop alert email, which
    `app/core/email.py` signs with `purpose="price_alert_unsubscribe"` and
    `GET /api/part-price-alerts/unsubscribe` verifies through
    `decode_access_token`. That token authenticates nobody: it names an alert id
    and deactivates one alert, it is the only credential a mail client can carry
    in a URL, and it has no identity access token equivalent because the
    recipient is by construction not signed in.

    So `SECRET_KEY` outlives the legacy session, and the PR that retires the
    rest of it says so rather than removing a setting three live callers read.
    See `docs/identity-adoption.md` row 13 for the inventory.
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
    are `TokenError`.

    The algorithm list is always explicit and never read from the token header,
    which is what refuses `alg: none` and the RS256-verified-as-HMAC confusion.
    Since row 13 the only caller is the price alert unsubscribe route; no
    resolver in this module decodes anything, because the only credential that
    resolves to a user is an identity access token.
    """
    return decode_token(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


# --- The identity access token, which is now the only credential ---
#
# Row 13 of `docs/identity-adoption.md`. Rows 11 and 12 ran these resolvers in
# dual mode: a legacy HS256 session decoded first, and an identity RS256 access
# token resolved to the same row when it did not. Row 12's cutover moved every
# client onto the identity token and the soak confirmed it, so this row deletes
# the legacy half.
#
# What that removes is a whole branch rather than a flag. There is no
# `decode_access_token` call on any resolver path any more, no `sub`-as-username
# lookup, and no `get_by_username` read behind a bearer token. A request either
# carries claims an authorizer verified, or a Bearer token this process can
# verify on the identity function, or it is refused. `resolve_identity_user` is
# the single answer to "who is this request for", and every resolver below is a
# policy on top of it rather than a second way of asking.


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
    """The user this request is for, or 401.

    Identity only since row 13. The credential is an identity access token, and
    it reaches this process in one of two ways: as claims an authorizer already
    verified and put in the request context, or as a Bearer token that
    `verify_bearer_subject` verifies here. `resolve_identity_user` tries them in
    that order and applies the three account checks, so a disabled or unverified
    account is refused on either.

    `token` stays in the signature although nothing here reads it. It is what
    keeps `oauth2_scheme` in the dependency tree, and that has two effects worth
    keeping: the published OpenAPI document still declares the
    `OAuth2PasswordBearer` security scheme on every route that depends on this,
    and a request carrying neither a header nor authorizer claims is still
    refused by the scheme itself with the same `Not authenticated` body it
    always produced. Removing it would change the API's published contract as a
    side effect of deleting the legacy decode, which is a different change from
    the one this row is making.
    """
    user = resolve_identity_user(request, repos)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """The user this request is for, or `None` for an anonymous caller.

    For the routes that serve everybody and personalise for a signed in caller.
    Identity only since row 13, and `None` rather than a raise for every way the
    answer can be "nobody", which is what keeps a public page public.

    `token` is unread, for the same reason `get_current_user`'s is: it holds the
    optional security scheme in the dependency tree so the OpenAPI document is
    unchanged by this row.
    """
    return resolve_identity_user(request, repos)


async def get_current_active_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """The current active user if one is authenticated, otherwise `None`.

    Identity only since row 13, and now identical in behaviour to
    `get_optional_current_user`. The two are kept as separate names because
    their call sites mean different things by them and the dual-mode rows had a
    real difference between them: this one did not require a verified address on
    the legacy path where the other did. On the identity path that difference
    never existed, because `resolve_identity_user` checks `email_verified` for
    both, so deleting the legacy branch is what collapsed them.

    Kept rather than aliased so a later divergence is a change to one function
    rather than an unpicking of an alias, and because the accounts the looser
    check would have admitted are exactly the ones `may_authenticate` refuses at
    the package's door, so no identity token is ever minted for one.
    """
    return resolve_identity_user(request, repos)


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
    """Allow a valid `X-API-Key`, or an admin identity token, and nothing else.

    Returns the authenticated admin user, or `None` when the caller got in on
    the API key (there is no user behind a machine credential). Raises through
    the app's normal `HTTPException` path:

      - no credential at all, or a bad/unknown key with no token -> 401
      - a valid token belonging to a non-admin user -> 403

    The API key is checked first and is a complete credential on its own, which
    is why `POST /api/parts/price-history` is not a flagged route key at the
    gateway: its callers are the Chrome extension and the ingestion jobs, and
    neither carries a bearer token at all. See the row 12a inventory in
    `docs/identity-adoption.md`.

    `token` is unread since row 13. The bearer branch used to decode a legacy
    session here; now both the header and the authorizer context are read by
    `resolve_identity_user`, so there is one path rather than two.
    """
    if verify_api_key(api_key):
        return None

    identity_user = resolve_identity_user(request, repos)
    if identity_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_current_admin_user(current_user=identity_user)
