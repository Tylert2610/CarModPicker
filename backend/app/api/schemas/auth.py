"""What survives the legacy auth routers.

Row 13 of `docs/identity-adoption.md` deleted the four routers under
`/api/auth`, and with them every request and response model that only those
routes declared: the TOTP setup, verify, login and disable pairs, the four
Google sign in shapes, and the three "this sign in needs another step" replies.
The package owns all of those flows now and declares its own models for them.

Three names are left, and none of them is about the legacy session:

- `PASSWORD_MIN_LENGTH` and `PASSWORD_MAX_LENGTH` bound the password field on
  `UserCreate` and `UserUpdate`, which are the users domain's own schemas for
  `POST /api/users/` and the password change on `PUT /api/users/{user_id}`.
  Those routes are not legacy auth routes and row 13 does not touch them.
- `OAuthAccountRead` is read by `app/api/services/user_service.py` to render the
  linked provider accounts on a user, which `GET /api/users/me` still returns.

The 72 byte cap is bcrypt's and is expressed in characters here deliberately;
`webbpulse.security.hash_password` truncates on the byte boundary, so a value
that passes this validator always hashes. See the note in
`app/api/dependencies/auth.py`.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# bcrypt silently truncates anything past 72 bytes. Capping here so users can't
# set a password whose tail is ignored on verification.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


class OAuthAccountRead(BaseModel):
    id: UUID
    provider: str
    email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
