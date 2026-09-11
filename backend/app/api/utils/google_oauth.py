"""Google OAuth ID token verification.

The frontend uses Google Identity Services (GIS) to obtain an ID token. We verify
the token's signature against Google's JWKS, check the audience matches our client
"""

import base64
import hashlib
from dataclasses import dataclass
from typing import Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


class GoogleTokenError(ValueError):
    """Raised when an ID token fails verification (bad signature, audience, nonce, etc.)."""


def _hashed_nonce(value: str) -> str:
    """Compute the hashed nonce form Google emits under FedCM:
    base64url(sha256(nonce)) without padding."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class GoogleIdentity:
    """Parsed identity claims from a verified Google ID token."""

    sub: str
    email: str
    email_verified: bool
    name: Optional[str]
    picture: Optional[str]


_request = google_requests.Request()


def verify_google_id_token(token: str, expected_nonce: str, client_id: str) -> GoogleIdentity:
    """Verify a Google ID token and return the identity claims.

    Raises GoogleTokenError on any verification failure. The caller decides the HTTP
    response — usually 401 for bad token, 400 for missing email_verified.
    """
    if not client_id:
        raise GoogleTokenError("Google sign-in is not configured")
    if not token:
        raise GoogleTokenError("Missing id_token")
    if not expected_nonce:
        raise GoogleTokenError("Missing nonce")

    try:
        claims = google_id_token.verify_oauth2_token(token, _request, client_id)
    except ValueError as e:
        raise GoogleTokenError(f"Invalid id_token: {e}") from e

    claim_nonce = claims.get("nonce")
    if claim_nonce not in (expected_nonce, _hashed_nonce(expected_nonce)):
        raise GoogleTokenError("Nonce mismatch")

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleTokenError("id_token missing required claims")

    return GoogleIdentity(
        sub=str(sub),
        email=str(email),
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )
