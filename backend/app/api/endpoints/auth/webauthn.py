"""WebAuthn passkey endpoints: register/login ceremonies + credentials management."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from webbpulse.security import TokenError

from app.api.dependencies.auth import (
    create_access_token,
    decode_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.user import UserRead
from app.api.schemas.webauthn import (
    WebAuthnCredentialRename,
    WebAuthnCredentialSummary,
    WebAuthnLoginOptionsRequest,
    WebAuthnLoginOptionsResponse,
    WebAuthnLoginVerifyRequest,
    WebAuthnRegisterOptionsRequest,
    WebAuthnRegisterOptionsResponse,
    WebAuthnRegisterVerifyRequest,
)
from app.api.services.user_service import user_read
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.dynamo.users import UniqueAttributeTaken
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import WebAuthnCredential

logger = logging.getLogger(__name__)
router = APIRouter()


# --- WebAuthn-local helpers (D-19 — stay in this module) ---

WEBAUTHN_REGISTER_PURPOSE = "webauthn_register"
WEBAUTHN_LOGIN_PURPOSE = "webauthn_login"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _build_challenge_token(purpose: str, challenge: bytes, user_id: str | None = None) -> str:
    payload: dict[str, str] = {"purpose": purpose, "challenge": _b64url_encode(challenge)}
    if user_id is not None:
        payload["user_id"] = user_id
    return create_access_token(data=payload, expires_delta=timedelta(minutes=5))


def _decode_challenge_token(token: str, expected_purpose: str) -> tuple[bytes, str | None]:
    try:
        payload = decode_access_token(token)
    except TokenError:
        ResponsePatterns.raise_bad_request("Invalid or expired challenge")
    if payload.get("purpose") != expected_purpose:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    challenge_b64 = payload.get("challenge")
    if not challenge_b64:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    return _b64url_decode(challenge_b64), payload.get("user_id")


@router.post("/register/options", response_model=WebAuthnRegisterOptionsResponse)
async def webauthn_register_options(
    request: WebAuthnRegisterOptionsRequest,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> WebAuthnRegisterOptionsResponse:
    """Start passkey registration: generate a challenge + options object for the browser."""
    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")

    challenge = secrets.token_bytes(32)
    existing = repos.webauthn_credentials.list_by_user(current_user.id)
    exclude = [PublicKeyCredentialDescriptor(id=cred.credential_id) for cred in existing]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=current_user.id.bytes,
        user_name=current_user.username,
        user_display_name=current_user.username,
        challenge=challenge,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    options_json = options_to_json(options)

    logger.info(f"WebAuthn registration options generated for user: {current_user.username}")
    return WebAuthnRegisterOptionsResponse(
        options=json.loads(options_json),
        challenge_token=_build_challenge_token(WEBAUTHN_REGISTER_PURPOSE, challenge, user_id=str(current_user.id)),
    )


@router.post("/register/verify", response_model=WebAuthnCredentialSummary)
async def webauthn_register_verify(
    request: WebAuthnRegisterVerifyRequest,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> WebAuthnCredentialSummary:
    """Verify the browser's attestation and persist the new credential."""
    challenge, challenge_user_id = _decode_challenge_token(request.challenge_token, WEBAUTHN_REGISTER_PURPOSE)
    if challenge_user_id != str(current_user.id):
        ResponsePatterns.raise_bad_request("Challenge does not match current user")

    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")

    try:
        verified = verify_registration_response(
            credential=request.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins_list,
        )
    except InvalidRegistrationResponse as e:
        logger.warning(f"WebAuthn registration verify failed for {current_user.username}: {e}")
        ResponsePatterns.raise_bad_request(f"Registration failed: {e}")

    if repos.webauthn_credentials.get_by_credential_id(verified.credential_id) is not None:
        ResponsePatterns.raise_conflict("This credential is already registered", "CREDENTIAL_EXISTS")

    transports = None
    raw_response = request.credential.get("response", {}) if isinstance(request.credential, dict) else {}
    raw_transports = raw_response.get("transports") if isinstance(raw_response, dict) else None
    if isinstance(raw_transports, list):
        transports = [str(t) for t in raw_transports]

    cred = WebAuthnCredential(
        user_id=current_user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=transports,
        aaguid=verified.aaguid,
        nickname=nickname,
        backup_eligible=bool(getattr(verified, "credential_backed_up", False)),
        backup_state=bool(getattr(verified, "credential_backed_up", False)),
    )
    try:
        repos.webauthn_credentials.create_credential(cred)
    except UniqueAttributeTaken:
        ResponsePatterns.raise_conflict("This credential is already registered", "CREDENTIAL_EXISTS")

    logger.info(f"WebAuthn credential registered for user: {current_user.username}")
    return WebAuthnCredentialSummary.model_validate(cred)


@router.post("/login/options", response_model=WebAuthnLoginOptionsResponse)
async def webauthn_login_options(
    request: WebAuthnLoginOptionsRequest,
    repos: Repositories = Depends(get_repositories),
) -> WebAuthnLoginOptionsResponse:
    """Start passkey login: generate a challenge. Username is optional (discoverable flow)."""
    challenge = secrets.token_bytes(32)

    allow_credentials: list[PublicKeyCredentialDescriptor] = []
    if request.username:
        user = repos.users.get_by_username(request.username)
        if user:
            creds = repos.webauthn_credentials.list_by_user(user.id)
            allow_credentials = [PublicKeyCredentialDescriptor(id=c.credential_id) for c in creds]

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge,
        allow_credentials=allow_credentials or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    options_json = options_to_json(options)

    logger.info(f"WebAuthn login options generated (username={request.username or 'discoverable'})")
    return WebAuthnLoginOptionsResponse(
        options=json.loads(options_json),
        challenge_token=_build_challenge_token(WEBAUTHN_LOGIN_PURPOSE, challenge),
    )


@router.post("/login/verify")
async def webauthn_login_verify(
    request: WebAuthnLoginVerifyRequest,
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str | UserRead]:
    """Verify a passkey assertion, bump sign_count, and mint an access token.

    Passkeys are phishing-resistant multi-factor by design, so this path bypasses TOTP.
    """
    challenge, _ = _decode_challenge_token(request.challenge_token, WEBAUTHN_LOGIN_PURPOSE)

    raw_credential_id = request.credential.get("id") if isinstance(request.credential, dict) else None
    if not raw_credential_id:
        ResponsePatterns.raise_bad_request("Invalid credential payload")
    try:
        credential_id_bytes = _b64url_decode(raw_credential_id)
    except (ValueError, binascii.Error):
        ResponsePatterns.raise_bad_request("Invalid credential id")

    cred = repos.webauthn_credentials.get_by_credential_id(credential_id_bytes)
    if not cred:
        logger.warning("WebAuthn login: credential not recognized")
        ResponsePatterns.raise_unauthorized("Unknown credential")

    user = repos.users.get(cred.user_id)
    if not user:
        logger.error(f"WebAuthn credential {cred.id} has no matching user")
        ResponsePatterns.raise_unauthorized("Unknown credential")
    if user.disabled:
        ResponsePatterns.raise_bad_request("Inactive user")
    if user.is_service_account:
        ResponsePatterns.raise_unauthorized("Unknown credential")
    # Mirrors get_current_user: unverified users must not be able to acquire a
    # session, even via a previously-registered passkey.
    if not user.email_verified:
        ResponsePatterns.raise_unauthorized("Email not verified")

    try:
        verified = verify_authentication_response(
            credential=request.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins_list,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        logger.warning(f"WebAuthn login verify failed: {e}")
        ResponsePatterns.raise_unauthorized(f"Authentication failed: {e}")

    repos.webauthn_credentials.update(cred.id, sign_count=verified.new_sign_count, last_used_at=datetime.now(UTC))

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=get_access_token_expires_delta_for_user(user),
    )
    logger.info(f"User logged in via passkey: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_read(user, repos),
    }


@router.get("/credentials", response_model=list[WebAuthnCredentialSummary])
async def list_webauthn_credentials(
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> list[WebAuthnCredentialSummary]:
    creds = repos.webauthn_credentials.list_by_user(current_user.id)
    return [WebAuthnCredentialSummary.model_validate(c) for c in creds]


@router.patch("/credentials/{credential_id}", response_model=WebAuthnCredentialSummary)
async def rename_webauthn_credential(
    credential_id: uuid.UUID,
    request: WebAuthnCredentialRename,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> WebAuthnCredentialSummary:
    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")
    cred = repos.webauthn_credentials.get(credential_id)
    if not cred or cred.user_id != current_user.id:
        ResponsePatterns.raise_not_found("Passkey")
    cred = repos.webauthn_credentials.update(cred.id, nickname=nickname)
    return WebAuthnCredentialSummary.model_validate(cred)


@router.delete("/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    cred = repos.webauthn_credentials.get(credential_id)
    if not cred or cred.user_id != current_user.id:
        ResponsePatterns.raise_not_found("Passkey")
    repos.webauthn_credentials.delete_credential(cred)
    logger.info(f"WebAuthn credential deleted: {credential_id} (user {current_user.username})")
    return {"message": "Passkey removed"}
