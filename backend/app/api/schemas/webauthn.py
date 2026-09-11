"""Pydantic schemas for WebAuthn (passkey) endpoints.

Options and results cross the wire as JSON in the WebAuthn spec shape that
py_webauthn's options_to_json helper produces.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class WebAuthnRegisterOptionsRequest(BaseModel):
    """Request body for starting passkey registration."""

    nickname: str


class WebAuthnRegisterOptionsResponse(BaseModel):
    """Registration options plus the challenge token to echo back."""

    options: dict[str, Any]
    challenge_token: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    """Request body carrying the registration credential to verify."""

    challenge_token: str
    credential: dict[str, Any]
    nickname: str


class WebAuthnLoginOptionsRequest(BaseModel):
    """Request body for starting a passkey assertion."""

    username: Optional[str] = None


class WebAuthnLoginOptionsResponse(BaseModel):
    """Assertion options plus the challenge token to echo back."""

    options: dict[str, Any]
    challenge_token: str


class WebAuthnLoginVerifyRequest(BaseModel):
    """Request body carrying the assertion credential to verify."""

    challenge_token: str
    credential: dict[str, Any]


class WebAuthnCredentialSummary(BaseModel):
    """A registered passkey as shown in account settings."""

    id: UUID
    nickname: str
    aaguid: Optional[str] = None
    transports: Optional[list[str]] = None
    backup_eligible: bool
    backup_state: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebAuthnCredentialRename(BaseModel):
    """Request body for renaming a registered passkey."""

    nickname: str
