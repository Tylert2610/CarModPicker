"""Regression: a password over bcrypt's 72 byte limit must not 500.

bcrypt reads at most 72 bytes of a password and ignores the rest. What differs
between library versions is what happens when it is handed more: bcrypt 4.x
truncates silently, and bcrypt 5.0.0, which this app pins, raises

    ValueError: password cannot be longer than 72 bytes

The schemas cap a password at `PASSWORD_MAX_LENGTH` characters, and the comment
there says the cap exists because of that bcrypt limit. But a character is not a
byte. The cap is enforced by pydantic's `max_length`, which counts characters, so
72 accented, CJK or emoji characters are 144 bytes or more, pass validation
cleanly, and then reached `bcrypt.hashpw` and became a 500. Signup, password
reset and password change were all affected, and login against such an account
was unreachable because the account could never be created in the first place.

`webbpulse.security` truncates to 72 **bytes** before bcrypt sees the value, on a
byte boundary rather than a character boundary, so these now hash and verify like
any other password. Byte truncation is what keeps the hash identical to what any
other implementation writes for the same input; trimming back to the last whole
character would feed bcrypt different bytes.

These tests use a multi-byte password rather than a long ASCII one on purpose.
An ASCII password of 73 characters is rejected by the schema with a 422, which is
correct behaviour and not the bug. The multi-byte case is the one that got past
validation, and it is the case that regressed.

Row 13 of `docs/identity-adoption.md` deleted the four routers under `/api/auth`,
and with them the login and password reset halves of this regression. What is
left is the half that still has live callers: the hashing primitives, and
`POST /api/users/` which is the users domain's own route and still takes a
password. Login against an over limit account is now the package's business and
is covered by the package's own tests.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash, verify_password
from app.api.schemas.auth import PASSWORD_MAX_LENGTH

# `PASSWORD_MAX_LENGTH` characters of a two byte character: exactly at the schema's
# limit, and exactly twice bcrypt's. Built from the constant rather than hardcoded so
# this keeps testing the boundary if the cap is ever changed.
OVER_LIMIT_PASSWORD = "é" * PASSWORD_MAX_LENGTH


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_the_test_password_is_the_shape_this_regression_is_about() -> None:
    """Guard the fixture itself: within the char cap, over bcrypt's byte limit."""
    assert len(OVER_LIMIT_PASSWORD) <= PASSWORD_MAX_LENGTH
    assert len(OVER_LIMIT_PASSWORD.encode("utf-8")) > 72


def test_hashing_a_password_over_72_bytes_does_not_raise() -> None:
    """The primitive itself. bcrypt 5 raised ValueError here before the swap."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert hashed.startswith("$2")
    # Cost 12, unchanged from the local implementation, so stored hashes stay valid.
    assert hashed.split("$")[2] == "12"
    assert verify_password(OVER_LIMIT_PASSWORD, hashed) is True


def test_a_wrong_password_still_fails_against_an_over_limit_hash() -> None:
    """Truncation must not turn verification into a rubber stamp."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert verify_password("something else entirely", hashed) is False


def test_signup_with_a_password_over_72_bytes(client: TestClient, db_session: Any) -> None:
    """Signup 500'd on this password before the swap. Now it creates the account."""
    username = _uniq("longpw_signup")

    signup = client.post(
        "/api/users/",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": OVER_LIMIT_PASSWORD,
        },
    )
    assert signup.status_code == 200, signup.text
    assert signup.json()["username"] == username


def test_an_ascii_password_past_the_char_cap_is_still_a_422(client: TestClient, db_session: Any) -> None:
    """The schema cap is unchanged. Over-long ASCII is a validation error, not a 500.

    Pinned so that adopting a module which truncates internally is not mistaken
    for permission to drop the app's own maximum length.
    """
    username = _uniq("longpw_ascii")

    signup = client.post(
        "/api/users/",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "a" * (PASSWORD_MAX_LENGTH + 1),
        },
    )
    assert signup.status_code == 422
