"""Access token schemas for the auth endpoints."""

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """An issued access token and its type."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Claims decoded from an access token."""

    username: Optional[str] = None
