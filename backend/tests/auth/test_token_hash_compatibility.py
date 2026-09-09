"""Adopting `webbpulse.security` must not log anybody out or invalidate a stored hash.

This deploys to a running service holding live sessions and a table of bcrypt
hashes written by the code being replaced. Neither can be migrated: there is no
way to re-hash a password nobody has typed yet, and no way to re-mint a token
sitting in somebody's browser. So the swap is only safe if the new code reads
what the old code wrote, and these tests pin both halves of that.

The old primitives are reproduced here literally, as `_legacy_*`, rather than
imported. Importing them would defeat the point once they are deleted; written
out, they keep asserting against what production actually wrote even though that
code no longer exists in the tree.

The two facts that make this work:

  - **Hashes.** The local `get_password_hash` passed `rounds=12` explicitly and
    the package's `DEFAULT_ROUNDS` is also 12, so the stored value has the same
    algorithm, cost and format. bcrypt hashes carry their own salt and cost, so
    verification is a property of the string, not of who wrote it.
  - **Tokens.** Both sign HS256 with `settings.SECRET_KEY` over the same claims.
    The package additionally stamps `iat`, which is additive: nothing here
    requires it to be absent, and a token minted without it still decodes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings

PASSWORD = "a-perfectly-ordinary-password"


def _legacy_get_password_hash(password: str) -> str:
    """The implementation this change deleted, kept to generate a pre-swap hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _legacy_create_access_token(data: dict[str, object], expires_delta: timedelta) -> str:
    """The implementation this change deleted, kept to mint a pre-swap token.

    Note what it does *not* set: no `iat`. A token in a browser right now looks
    like this, so this is the shape the new decode has to accept.
    """
    to_encode = dict(data)
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


# ---- hashes ----------------------------------------------------------------------


def test_a_hash_written_before_the_swap_still_verifies() -> None:
    """Every stored password in the table is this case."""
    legacy_hash = _legacy_get_password_hash(PASSWORD)

    assert verify_password(PASSWORD, legacy_hash) is True
    assert verify_password("the wrong password", legacy_hash) is False


def test_a_hash_written_after_the_swap_verifies_under_the_old_code() -> None:
    """The reverse direction, which is what makes a rollback safe."""
    new_hash = get_password_hash(PASSWORD)

    assert bcrypt.checkpw(PASSWORD.encode("utf-8"), new_hash.encode("utf-8")) is True


def test_the_cost_is_unchanged_at_twelve() -> None:
    """Same cost either side, so no account is silently weakened or re-hashed."""
    assert _legacy_get_password_hash(PASSWORD).split("$")[2] == "12"
    assert get_password_hash(PASSWORD).split("$")[2] == "12"


def test_an_account_with_no_password_at_all_verifies_false() -> None:
    """OAuth-only accounts have a null hash. This must be False, never an exception."""
    assert verify_password(PASSWORD, None) is False
    assert verify_password(PASSWORD, "") is False


# ---- tokens ----------------------------------------------------------------------


def test_a_token_minted_before_the_swap_still_decodes() -> None:
    """The live-session case: issued by the old code, verified by the new."""
    legacy_token = _legacy_create_access_token({"sub": "alice"}, timedelta(minutes=60))

    claims = decode_access_token(legacy_token)

    assert claims["sub"] == "alice"
    assert "exp" in claims
    # The old code never wrote `iat`, and decoding must not start requiring it.
    assert "iat" not in claims


def test_a_token_minted_after_the_swap_decodes_under_the_old_code() -> None:
    """The reverse direction, which is what makes a rollback safe."""
    token = create_access_token({"sub": "alice"}, expires_delta=timedelta(minutes=60))

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "alice"


def test_the_new_token_adds_iat_and_nothing_else() -> None:
    """`iat` is the one claim that changed. Pinned so a third does not appear unnoticed."""
    token = create_access_token({"sub": "alice", "purpose": "verify_email"})

    claims = decode_access_token(token)

    assert set(claims) == {"sub", "purpose", "exp", "iat"}


def test_the_default_expiry_still_comes_from_settings() -> None:
    """Expiry semantics are the app's, not the package's default."""
    token = create_access_token({"sub": "alice"})

    claims = decode_access_token(token)
    expected = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    actual = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)

    assert abs((expected - actual).total_seconds()) < 5


def test_a_token_signed_with_another_secret_is_refused() -> None:
    from webbpulse.security import TokenError

    forged = jwt.encode(
        {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=60)},
        "not-the-real-secret",
        algorithm=ALGORITHM,
    )

    try:
        decode_access_token(forged)
    except TokenError:
        pass
    else:  # pragma: no cover - the assert below is the failure path
        raise AssertionError("a token signed with the wrong secret was accepted")


def test_an_expired_token_is_refused() -> None:
    from webbpulse.security import ExpiredToken

    expired = create_access_token({"sub": "alice"}, expires_delta=timedelta(minutes=-5))

    try:
        decode_access_token(expired)
    except ExpiredToken:
        pass
    else:  # pragma: no cover - the assert below is the failure path
        raise AssertionError("an expired token was accepted")
