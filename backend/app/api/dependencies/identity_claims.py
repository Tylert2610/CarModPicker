"""Read the identity access token's claims in whichever shape the environment delivers.

Accepts the gateway JWT authorizer's flat claim map and the staging access gate's
JSON `jwt.claims` string, normalising both to the same values. Answers None for
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import Request

__all__ = [
    "GATE_CLAIMS_KEY",
    "identity_claims",
    "identity_subject",
    "verify_bearer_subject",
]

logger = logging.getLogger(__name__)

GATE_CLAIMS_KEY = "jwt.claims"


def _gate_claims(request: "Request") -> Optional[dict[str, Any]]:
    """The gate authorizer's claims for this request, or `None`.

    Reached only when the package's reader found no `authorizer.jwt.claims`,
    which in staging is every flagged request. The header is parsed a second
    """
    from webbpulse.http import REQUEST_CONTEXT_HEADER

    raw = request.headers.get(REQUEST_CONTEXT_HEADER)
    if raw is None or not raw.strip():
        return None
    try:
        context = json.loads(raw)
    except ValueError:
        logger.debug("The %s header is not JSON.", REQUEST_CONTEXT_HEADER)
        return None
    if not isinstance(context, Mapping):
        return None

    authorizer = context.get("authorizer")
    if not isinstance(authorizer, Mapping):
        return None
    lambda_context = authorizer.get("lambda")
    if not isinstance(lambda_context, Mapping):
        return None
    encoded = lambda_context.get(GATE_CLAIMS_KEY)
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    try:
        claims = json.loads(encoded)
    except ValueError:
        logger.warning(
            "The staging access gate published a %r context value that is not JSON. "
            "The gate writes it with JSON.stringify, so this means the two sides "
            "disagree about the encoding rather than that the token was bad.",
            GATE_CLAIMS_KEY,
        )
        return None
    if not isinstance(claims, Mapping):
        return None
    return dict(claims)


def identity_claims(request: "Request") -> Optional[Mapping[str, Any]]:
    """The verified identity claims for this request, or `None` for none.

    Tries the native authorizer's shape through the package's own reader first,
    then the staging gate's. Both results go through `coerce_claims`, the
    """
    from webbpulse.identity.claims import (
        AuthorizerClaims,
        ClaimsUnavailable,
        coerce_claims,
    )

    try:
        return AuthorizerClaims(dict(_read_native(request)))
    except ClaimsUnavailable:
        pass
    gate = _gate_claims(request)
    if gate is None:
        return None
    return coerce_claims(gate)


def _read_native(request: "Request") -> Mapping[str, Any]:
    """The package's reader, isolated so `identity_claims` reads as two attempts."""
    from webbpulse.identity.claims import read_authorizer_claims

    return read_authorizer_claims(request)


def identity_subject(request: "Request") -> str:
    """The verified `sub` the authorizer put on this request, or `""`.

    `sub` is the CarModPicker user id, as a string. `CarModPickerIdentityHooks.
    claims_for` puts nothing else there and `load_user_by_id` parses it straight
    """
    claims = identity_claims(request)
    if claims is None:
        return ""
    return str(claims.get("sub", "") or "")


def verify_bearer_subject(request: "Request") -> str:
    """The `sub` of a Bearer identity token verified in this process, or `""`.

    The fallback for a route the gateway put no claims on. It is a real
    verification: signature, issuer, audience and expiry, through
    """
    from app.core.config import settings

    if not settings.IDENTITY_ISSUER.strip():
        return ""

    authorization = request.headers.get("authorization", "")
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented.strip():
        return ""

    service = _token_service()
    if service is None:
        return ""
    try:
        claims = service.verify_access_token(presented.strip())
    except Exception:
        logger.debug("An identity access token did not verify.", exc_info=True)
        return ""
    return str(claims.get("sub", "") or "")


_token_service_cache: Optional[Any] = None
_token_service_failed = False


def _token_service() -> Optional[Any]:
    """The shared `TokenService`, or `None` where one cannot be built.

    A failure is remembered. On a function with no `IDENTITY_*` block the
    settings raise, and retrying that per request would be a pydantic validation
    """
    global _token_service_cache, _token_service_failed

    if _token_service_cache is not None:
        return _token_service_cache
    if _token_service_failed:
        return None
    try:
        import boto3
        from webbpulse.identity import TokenService

        from app.composition.identity import build_identity_settings
        from app.core.config import settings as app_settings

        identity_settings = build_identity_settings(app_settings)
        _token_service_cache = TokenService(identity_settings, boto3.client("kms"))
    except Exception:
        _token_service_failed = True
        logger.debug(
            "No identity TokenService on this function, so a Bearer identity token cannot "
            "be verified in process here. Expected on every domain but `identity`.",
            exc_info=True,
        )
        return None
    return _token_service_cache


def reset_token_service() -> None:
    """Drop the memoised `TokenService`. For tests that change the environment."""
    global _token_service_cache, _token_service_failed

    _token_service_cache = None
    _token_service_failed = False
