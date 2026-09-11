"""Google OAuth endpoints: sign-in, signup, link, connect, 2FA, account list/delete."""

from __future__ import annotations

import binascii
import logging
import uuid
from datetime import timedelta
from typing import Any

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from webbpulse.security import TokenError

from app.api.dependencies.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    verify_password,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.endpoints.auth._helpers import issue_login_response, maybe_2fa_challenge
from app.api.schemas.auth import (
    GoogleConnectRequest,
    GoogleLinkRequest,
    GoogleSignInLinkRequired,
    GoogleSignInRequest,
    GoogleSignInSignupRequired,
    GoogleSignupRequest,
    OAuthAccountRead,
    OAuthTwoFactorRequest,
)
from app.api.schemas.user import UserRead
from app.api.utils.google_oauth import GoogleIdentity, GoogleTokenError, verify_google_id_token
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.dynamo.users import (
    EMAIL,
    PROVIDER_ACCOUNT,
    USERNAME,
    OAuthAccount,
    UniqueAttributeTaken,
)
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import (
    run_unique_transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter()


GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


def _ensure_google_enabled() -> None:
    """Raise 503 when Google sign-in is not configured."""
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )


def _verify_google_or_400(id_token_str: str, nonce: str, logger: logging.Logger) -> GoogleIdentity:
    """Verify a Google ID token, rejecting bad tokens and unverified emails."""
    try:
        identity = verify_google_id_token(id_token_str, nonce, settings.GOOGLE_CLIENT_ID)
    except GoogleTokenError as e:
        logger.warning(f"Google id_token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    if not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified",
        )
    return identity


def _suggest_username(email: str, repos: Repositories) -> str:
    """Build a username suggestion from the email local-part. Caller still validates uniqueness."""
    local = email.split("@", 1)[0].lower()
    base = "".join(ch for ch in local if ch.isalnum() or ch in ("_", "-", ".")) or "user"
    candidate = base
    suffix = 1
    while repos.users.get_by_username(candidate) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
        if suffix > 100:
            return base
    return candidate


def _decode_purpose_token(token: str, expected_purpose: str) -> dict[str, Any]:
    """Decode a single purpose token, rejecting anything issued for another purpose."""
    try:
        payload = decode_access_token(token)
    except TokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from e
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return payload


@router.post("/google")
async def google_sign_in(
    request: GoogleSignInRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, Any]:
    """Verify a Google ID token and route to the right next step.

    Outcomes:
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = repos.oauth_accounts.get_by_provider_account(GOOGLE_PROVIDER, identity.sub)
    if existing_link is not None:
        user = repos.users.get(existing_link.user_id)
        if user is None:
            logger.error(f"OAuth link {existing_link.id} points to missing user {existing_link.user_id}")
            ResponsePatterns.raise_unauthorized("Account not available")
        if user.disabled:
            ResponsePatterns.raise_bad_request("Inactive user")
        if user.is_service_account:
            ResponsePatterns.raise_unauthorized("Account not available")
        challenge = maybe_2fa_challenge(user)
        if challenge is not None:
            logger.info(f"Google sign-in: 2FA required for user {user.username}")
            return challenge
        logger.info(f"Google sign-in: existing link, logging in user {user.username}")
        return issue_login_response(user, repos)

    email_match = repos.users.get_by_email(identity.email)
    if email_match is not None:
        if email_match.disabled or email_match.is_service_account:
            ResponsePatterns.raise_bad_request("Account not available")
        link_token = create_access_token(
            data={
                "purpose": GOOGLE_LINK_PURPOSE,
                "google_sub": identity.sub,
                "email": identity.email,
            },
            expires_delta=timedelta(minutes=10),
        )
        logger.info(f"Google sign-in: email match for {identity.email}, link required")
        return GoogleSignInLinkRequired(
            link_token=link_token,
            email=identity.email,
            display_name=identity.name,
            has_totp=email_match.totp_enabled,
        ).model_dump()

    signup_token = create_access_token(
        data={
            "purpose": GOOGLE_SIGNUP_PURPOSE,
            "google_sub": identity.sub,
            "email": identity.email,
        },
        expires_delta=timedelta(minutes=15),
    )
    suggested_username = _suggest_username(identity.email, repos)
    logger.info(f"Google sign-in: no match for {identity.email}, signup required")
    return GoogleSignInSignupRequired(
        signup_token=signup_token,
        email=identity.email,
        suggested_username=suggested_username,
    ).model_dump()


@router.post("/google/link")
async def google_link(
    request: GoogleLinkRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead]:
    """Merge a Google identity into an existing password account.

    Required after the initial /auth/google call returned `requires_link: true`.
    Verifies the user's password (and OTP if 2FA is enabled), creates the oauth_accounts row,
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.link_token, GOOGLE_LINK_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    user = repos.users.get_by_email(email)
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None

    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Google link: bad password for user {user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect password")

    if user.totp_enabled:
        if not request.otp:
            ResponsePatterns.raise_bad_request("OTP required")
        if not user.totp_secret:
            logger.error(f"2FA enabled but no secret for user {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")
        try:
            totp = pyotp.TOTP(user.totp_secret)
        except (ValueError, TypeError, binascii.Error):
            logger.error(f"Invalid TOTP secret format for user: {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")

        try:
            if not totp.verify(request.otp, valid_window=1):
                ResponsePatterns.raise_unauthorized("Invalid OTP code")
        except (ValueError, TypeError, binascii.Error):
            logger.error(f"TOTP verification failed for user: {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")

    if repos.oauth_accounts.get_by_provider_account(GOOGLE_PROVIDER, google_sub) is not None:
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")
    if repos.oauth_accounts.get_for_user_provider(user.id, GOOGLE_PROVIDER) is not None:
        ResponsePatterns.raise_conflict("Account already has Google linked", "OAUTH_ACCOUNT_EXISTS")

    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    try:
        repos.oauth_accounts.create_link(link)
    except UniqueAttributeTaken as e:
        if e.attribute == PROVIDER_ACCOUNT:
            ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")
        ResponsePatterns.raise_conflict("Account already has Google linked", "OAUTH_ACCOUNT_EXISTS")
    logger.info(f"Google linked to existing user {user.username}")
    return issue_login_response(user, repos)


@router.post("/google/signup")
async def google_signup(
    request: GoogleSignupRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead]:
    """Create a brand-new account from a Google identity. The email had no existing match
    when /auth/google was called; the client collected a username and submits it here.
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.signup_token, GOOGLE_SIGNUP_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    username = request.username.strip()
    if not username:
        ResponsePatterns.raise_bad_request("Username cannot be empty")

    if repos.users.get_by_username(username) is not None:
        ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")
    if repos.users.get_by_email(email) is not None:
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
    if repos.oauth_accounts.get_by_provider_account(GOOGLE_PROVIDER, google_sub) is not None:
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")

    user = DBUser(
        username=username,
        email=email,
        hashed_password=None,
        email_verified=True,
    )
    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    user_actions, user_labels = repos.users.create_actions(user)
    link_actions, link_labels = repos.oauth_accounts.create_actions(link)
    try:
        run_unique_transaction(user_actions + link_actions, user_labels + link_labels)
    except UniqueAttributeTaken as e:
        if e.attribute == USERNAME:
            ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")
        if e.attribute == EMAIL:
            ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")
    logger.info(f"Google signup: created user {user.username} (email {user.email})")
    return issue_login_response(user, repos)


@router.post("/2fa")
async def oauth_two_factor(
    request: OAuthTwoFactorRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead]:
    """Complete 2FA after an OAuth sign-in. Accepts the otp_token + OTP only — no password,
    since OAuth-only users may not have one.
    """
    payload = _decode_purpose_token(request.otp_token, OAUTH_2FA_PURPOSE)
    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from e

    user = repos.users.get(user_uuid)
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None
    if not user.totp_enabled or not user.totp_secret:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    try:
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(request.otp, valid_window=1):
            ResponsePatterns.raise_unauthorized("Invalid OTP code")
    except (ValueError, TypeError, binascii.Error):
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    logger.info(f"OAuth 2FA completed for user {user.username}")
    return issue_login_response(user, repos)


@router.post("/google/connect", response_model=OAuthAccountRead)
async def google_connect(
    request: GoogleConnectRequest,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> OAuthAccountRead:
    """Link a Google account to the *currently logged-in* user.

    Refuses if the Google email matches a *different* user — the user must instead sign out
    and use the merge flow from the login page. This preserves the invariant that no two
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = repos.oauth_accounts.get_by_provider_account(GOOGLE_PROVIDER, identity.sub)
    if existing_link is not None:
        if existing_link.user_id == current_user.id:
            ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")
        ResponsePatterns.raise_conflict(
            "This Google account is linked to a different user", "OAUTH_LINKED_TO_OTHER_USER"
        )

    if repos.oauth_accounts.get_for_user_provider(current_user.id, GOOGLE_PROVIDER) is not None:
        ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")

    email_match = repos.users.get_by_email(identity.email)
    if email_match is not None and email_match.id != current_user.id:
        ResponsePatterns.raise_conflict(
            "Another account already uses this Google email — sign out and use 'Sign in with Google' to merge.",
            "EMAIL_BELONGS_TO_OTHER_USER",
        )

    link = OAuthAccount(
        user_id=current_user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=identity.sub,
        email=identity.email,
    )
    try:
        repos.oauth_accounts.create_link(link)
    except UniqueAttributeTaken as e:
        if e.attribute == PROVIDER_ACCOUNT:
            ResponsePatterns.raise_conflict(
                "This Google account is linked to a different user", "OAUTH_LINKED_TO_OTHER_USER"
            )
        ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")
    logger.info(f"Google connected to user {current_user.username}")
    return OAuthAccountRead.model_validate(link)


@router.get("", response_model=list[OAuthAccountRead])
async def list_oauth_accounts(
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> list[OAuthAccountRead]:
    """Return the OAuth providers linked to the caller."""
    rows = repos.oauth_accounts.list_by_user(current_user.id)
    return [OAuthAccountRead.model_validate(r) for r in rows]


@router.delete("/{account_id}")
async def delete_oauth_account(
    account_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Remove a linked OAuth provider.

    Refuses if removing it would leave the user with no way to sign in: no password set,
    no other linked OAuth accounts, and no passkeys.
    """
    link = repos.oauth_accounts.get(account_id)
    if link is None or link.user_id != current_user.id:
        ResponsePatterns.raise_not_found("OAuth account")
    assert link is not None

    if not current_user.hashed_password:
        other_oauth = [a for a in repos.oauth_accounts.list_by_user(current_user.id) if a.id != link.id]
        passkeys = repos.webauthn_credentials.list_by_user(current_user.id)
        if not other_oauth and not passkeys:
            ResponsePatterns.raise_bad_request(
                "Set a password or register a passkey before removing your only sign-in method"
            )

    repos.oauth_accounts.delete_link(link)
    logger.info(f"OAuth account {account_id} removed (user {current_user.username})")
    return {"message": "Connected account removed"}
