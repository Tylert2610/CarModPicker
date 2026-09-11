"""The Chrome extension's sign in handoff: two routes under `/api/auth`.

The web page trades a signed in session for a single use sixty second code, which
the extension exchanges for a token. The code is a KMS signed JWT, not a row.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from fastapi import Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

    from app.core.config import Settings

_log = logging.getLogger(__name__)

HANDOFF_TOKEN_TYPE = "extension_handoff"

HANDOFF_TTL_SECONDS = 60

EXTENSION_IDS_ENV = "CHROME_EXTENSION_IDS"

DEFAULT_EXTENSION_ID = "dbglgmnnfandmnacdpibkfggkadjikkg"


def allowed_extension_ids(env: dict[str, str] | None = None) -> list[str]:
    """The extension ids this deployment will issue a handoff code for.

    An unset variable means the shipped store extension; an explicitly empty one
    means none, which turns handoff off. The `chrome-extension://` scheme is tolerated.
    """
    source = os.environ if env is None else env
    raw = source.get(EXTENSION_IDS_ENV)
    if raw is None:
        raw = DEFAULT_EXTENSION_ID
    ids: list[str] = []
    for candidate in raw.split(","):
        cleaned = candidate.strip()
        if not cleaned:
            continue
        if cleaned.startswith("chrome-extension://"):
            cleaned = cleaned[len("chrome-extension://") :].strip("/")
        if cleaned:
            ids.append(cleaned)
    return ids


def extension_id_for(redirect_uri: str, allowed: list[str]) -> str | None:
    """The extension id `redirect_uri` names, or `None` if it names none we trust.

    Scheme, non-empty host and allowlist membership are all checked, because a
    `chrome-extension://` URL is by itself evidence of nothing.
    """
    parts = urlsplit(redirect_uri)
    if parts.scheme != "chrome-extension":
        return None
    host = parts.hostname or ""
    if host == "" or host not in allowed:
        return None
    return host


class HandoffRequest(BaseModel):
    """What the handoff page posts. `state` is the extension's nonce, echoed back.

    Defined at module scope because `from __future__ import annotations` makes
    FastAPI resolve the body annotation against module globals, not local scope.
    """

    redirect_uri: str = Field(min_length=1, max_length=2048)
    state: str = Field(default="", max_length=512)


class TokenRequest(BaseModel):
    """What the extension posts to spend a code. See `HandoffRequest` on scope."""

    code: str = Field(min_length=1, max_length=4096)


def build_router(settings: "Settings") -> "APIRouter":
    """The two extension routes, mounted by the caller with no prefix of its own.

    Paths come from `identity_prefix(settings)`, the one source of truth for where
    these live. The KMS client and `TokenService` are built once per router.
    """
    import boto3
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
    from webbpulse.identity import KmsSigner, TokenService, identity_prefix

    from app.composition.identity import build_identity_settings

    identity_settings = build_identity_settings(settings)
    kms_client = boto3.client("kms")
    tokens = TokenService(identity_settings, kms_client)
    signer = KmsSigner(kms_client, identity_settings.signing_key_arns[0])
    prefix = identity_prefix(identity_settings)

    handoff_audience = f"{identity_settings.issuer.rstrip('/')}/extension"

    router = APIRouter()

    def caller_subject(request: Request) -> str:
        """The verified `sub` of whoever is asking, or `""` for nobody.

        Prefers the gateway authorizer's already-checked claims, falling back to
        verifying the header locally. Never raises: every failure is "not signed in".
        """
        from webbpulse.identity.claims import ClaimsUnavailable, read_authorizer_claims

        try:
            claims = read_authorizer_claims(request)
        except ClaimsUnavailable:
            claims = None
        if claims is not None:
            subject = str(claims.get("sub", ""))
            if subject:
                return subject

        authorization = request.headers.get("authorization", "")
        scheme, _, presented = authorization.partition(" ")
        if scheme.lower() != "bearer" or not presented:
            return ""
        try:
            verified = tokens.verify_access_token(presented)
        except Exception:
            return ""
        return str(verified.get("sub", ""))

    @router.post(f"{prefix}/extension/handoff")
    async def issue_handoff_code(body: HandoffRequest, request: Request) -> JSONResponse:
        """Mint a sixty second code for a signed in user and a trusted extension.

        Answers `{"code": "..."}`, the shape the handoff page already reads.
        """
        subject = caller_subject(request)
        if not subject:
            return JSONResponse(
                {"detail": {"error_code": "NOT_AUTHENTICATED", "message": "Sign in first."}},
                status_code=401,
            )

        extension_id = extension_id_for(body.redirect_uri, allowed_extension_ids())
        if extension_id is None:
            _log.warning("extension handoff refused for redirect_uri %r", body.redirect_uri)
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "EXTENSION_NOT_ALLOWED",
                        "message": "That extension is not recognised.",
                    }
                },
                status_code=400,
            )

        issued_at = int(time.time())
        code = signer.encode(
            {
                "iss": identity_settings.issuer,
                "sub": subject,
                "aud": handoff_audience,
                "iat": issued_at,
                "exp": issued_at + HANDOFF_TTL_SECONDS,
                "typ": HANDOFF_TOKEN_TYPE,
                "ext": extension_id,
            }
        )
        _log.info("extension.handoff issued for %s to %s", subject, extension_id)
        return JSONResponse({"code": code})

    @router.post(f"{prefix}/extension/token")
    async def exchange_handoff_code(body: TokenRequest) -> JSONResponse:
        """Exchange a handoff code for an access token, unauthenticated by design.

        `typ` is asserted only after the signature and audience check, so an access
        token cannot be presented here and traded for one with a reset expiry.
        """
        from webbpulse.identity.service import InvalidToken

        try:
            claims = tokens.verify_access_token(body.code, audience=handoff_audience)
        except InvalidToken as exc:
            _log.info("extension handoff code rejected: %s", exc.reason)
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "HANDOFF_CODE_INVALID",
                        "message": "That sign in has expired. Start again from the extension.",
                    }
                },
                status_code=401,
            )

        if claims.get("typ") != HANDOFF_TOKEN_TYPE:
            _log.warning("extension token exchange refused typ %r", claims.get("typ"))
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "HANDOFF_CODE_INVALID",
                        "message": "That sign in has expired. Start again from the extension.",
                    }
                },
                status_code=401,
            )

        subject = str(claims.get("sub", ""))
        access_token = tokens.mint_access_token(subject)
        _log.info("extension.token issued for %s", subject)
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": int(identity_settings.access_token_ttl.total_seconds()),
            }
        )

    return router
