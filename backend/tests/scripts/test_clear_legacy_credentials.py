"""`scripts/clear_legacy_credentials.py` against moto and the real stores.

The stores under test are the package's own `DynamoCredentialStore` and
`DynamoTotpFactorStore` over moto-backed tables, not fakes, on the same argument
`test_credential_migration.py` makes: the claim this script rests on is that the
replacement it checks for is the row the running service reads, and a stub store
would prove only that the script can call `get`.

The refusals are what most of these cases are about. This script is the one step
of the identity migration that cannot be undone by reverting a deploy, so the
tests that matter are the ones proving it writes nothing when it cannot account
for a column.
"""

from __future__ import annotations

from typing import Any

import pytest
from uuid6 import uuid7
from webbpulse.identity import PASSWORD_CREDENTIAL_TYPE, CredentialRecord
from webbpulse.security import hash_password

from app.db.dynamo import client as dynamo_client
from app.db.dynamo.serialization import unique_lookup_key
from app.db.dynamo.tables import USERS
from scripts import clear_legacy_credentials as script
from tests.scripts.conftest import PREFIX


@pytest.fixture
def identity_tables(credentials_table: Any, totp_factors_table: Any) -> Any:
    """Both identity tables, since this script reads both."""
    return credentials_table


@pytest.fixture
def credentials(identity_tables: Any) -> Any:
    return script.build_credential_store(PREFIX)


@pytest.fixture
def totp_factors(identity_tables: Any) -> Any:
    return script.build_totp_store(PREFIX)


@pytest.fixture
def users(identity_tables: Any) -> Any:
    """The raw moto `users` table.

    Directly rather than through `UserRepository`, because every row here carries
    at least one attribute the model no longer declares, which is the whole
    subject of the script.
    """
    return dynamo_client.get_resource().Table(f"{PREFIX}-{USERS.suffix}")


@pytest.fixture
def factors_table(identity_tables: Any) -> Any:
    return dynamo_client.get_resource().Table(f"{PREFIX}-totp-factors")


def make_user(users: Any, **overrides: Any) -> str:
    """A users row shaped like the one signup writes. Returns the id."""
    user_id = str(uuid7())
    item: dict[str, Any] = {
        "id": user_id,
        "username": f"user-{user_id[:8]}",
        "email": f"{user_id[:8]}@example.com",
        "email_verified": True,
        "disabled": False,
    }
    item.update(overrides)
    users.put_item(Item=item)
    return user_id


def give_credential(credentials: Any, user_id: str, secret: str) -> None:
    credentials.put(
        CredentialRecord(
            user_id=user_id,
            credential_type=PASSWORD_CREDENTIAL_TYPE,
            secret=secret,
        )
    )


def give_sealed_factor(factors_table: Any, user_id: str) -> None:
    """A sealed factor row, written directly.

    Presence is all the script reads, and building a real `TotpFactorRecord`
    would need a KMS key this test has no business creating. See
    `build_totp_store` for why the script never opens the seed.
    """
    factors_table.put_item(
        Item={
            "user_id": user_id,
            "sealed_seed": "not-read-by-this-script",
            "activated_at": "2026-09-01T00:00:00Z",
        }
    )


def item(users: Any, user_id: str) -> dict[str, Any]:
    return dict(users.get_item(Key={"id": user_id})["Item"])


def run(users: Any, credentials: Any, totp_factors: Any, apply: bool = False) -> Any:
    return script.clear(
        script.iter_user_rows(PREFIX),
        credentials,
        totp_factors,
        prefix=PREFIX,
        apply=apply,
    )


# ---- the happy paths ---------------------------------------------------------------


def test_a_dry_run_writes_nothing(users: Any, credentials: Any, totp_factors: Any) -> None:
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)
    give_credential(credentials, user_id, hashed)

    summary, decisions = run(users, credentials, totp_factors)

    assert summary["cleared"] == 1
    assert [d.action for d in decisions] == ["cleared"]
    assert item(users, user_id)["hashed_password"] == hashed


def test_applying_removes_the_password_column(users: Any, credentials: Any, totp_factors: Any) -> None:
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)
    give_credential(credentials, user_id, hashed)

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["cleared"] == 1
    # Removed, not blanked. See the module docstring on why that distinction
    # matters beyond tidiness.
    assert "hashed_password" not in item(users, user_id)


def test_applying_removes_the_totp_seed(users: Any, credentials: Any, totp_factors: Any, factors_table: Any) -> None:
    user_id = make_user(users, totp_secret="JBSWY3DPEHPK3PXP", totp_enabled=True)
    give_sealed_factor(factors_table, user_id)

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["cleared"] == 1
    row = item(users, user_id)
    assert "totp_secret" not in row
    # The flag stays. It is what the profile UI renders, and the sealed factor it
    # refers to is still there.
    assert row["totp_enabled"] is True


def test_both_columns_go_in_one_pass(users: Any, credentials: Any, totp_factors: Any, factors_table: Any) -> None:
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed, totp_secret="JBSWY3DPEHPK3PXP")
    give_credential(credentials, user_id, hashed)
    give_sealed_factor(factors_table, user_id)

    summary, decisions = run(users, credentials, totp_factors, apply=True)

    assert summary["cleared"] == 1
    assert set(decisions[0].fields) == {"hashed_password", "totp_secret"}
    row = item(users, user_id)
    assert "hashed_password" not in row
    assert "totp_secret" not in row


def test_a_row_with_neither_column_is_already_clear(users: Any, credentials: Any, totp_factors: Any) -> None:
    """An OAuth only or passkey only account, or a second run of this script."""
    make_user(users)

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary == {
        "cleared": 0,
        "already_clear": 1,
        "mismatch": 0,
        "missing_credential": 0,
        "errors": 0,
    }


def test_running_twice_is_a_no_op(users: Any, credentials: Any, totp_factors: Any) -> None:
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)
    give_credential(credentials, user_id, hashed)

    run(users, credentials, totp_factors, apply=True)
    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["already_clear"] == 1
    assert summary["cleared"] == 0
    assert "hashed_password" not in item(users, user_id)


# ---- the refusals ------------------------------------------------------------------


def test_a_password_with_no_credential_refuses(users: Any, credentials: Any, totp_factors: Any) -> None:
    """The migration has not run, or did not cover this user."""
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["missing_credential"] == 1
    assert item(users, user_id)["hashed_password"] == hashed


def test_a_changed_password_refuses(users: Any, credentials: Any, totp_factors: Any) -> None:
    """The case the three surviving users domain routes produce.

    A password set through `PUT /api/users/{user_id}` after the migration ran
    lands in the legacy column and nowhere else, so the credential is stale. This
    is the refusal that stops the script being run before the follow up row.
    """
    user_id = make_user(users, hashed_password=hash_password("the-new-password"))
    give_credential(credentials, user_id, hash_password("the-old-password"))

    summary, decisions = run(users, credentials, totp_factors, apply=True)

    assert summary["mismatch"] == 1
    assert "different secret" in decisions[0].detail
    assert "hashed_password" in item(users, user_id)


def test_a_plaintext_seed_with_no_sealed_factor_refuses(users: Any, credentials: Any, totp_factors: Any) -> None:
    user_id = make_user(users, totp_secret="JBSWY3DPEHPK3PXP")

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["missing_credential"] == 1
    assert item(users, user_id)["totp_secret"] == "JBSWY3DPEHPK3PXP"


def test_one_refusal_stops_the_whole_run(users: Any, credentials: Any, totp_factors: Any) -> None:
    """The load bearing one.

    A partial run would leave the environment in a state neither this script nor
    either migration describes, so a single unaccountable row has to stop every
    write and not just its own.
    """
    good_hash = hash_password("legacy-password")
    good = make_user(users, hashed_password=good_hash)
    give_credential(credentials, good, good_hash)
    bad = make_user(users, hashed_password=hash_password("orphaned"))

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["missing_credential"] == 1
    assert summary["cleared"] == 1  # classified as clearable, and still not written
    assert item(users, good)["hashed_password"] == good_hash
    assert item(users, bad)["hashed_password"]


def test_a_refusal_exits_non_zero(users: Any, credentials: Any, totp_factors: Any) -> None:
    make_user(users, hashed_password=hash_password("orphaned"))

    assert script.main(["--prefix", PREFIX, "--apply"]) == 1


def test_a_clean_run_exits_zero(users: Any, credentials: Any, totp_factors: Any) -> None:
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)
    give_credential(credentials, user_id, hashed)

    assert script.main(["--prefix", PREFIX, "--apply"]) == 0
    assert "hashed_password" not in item(users, user_id)


# ---- the scan ----------------------------------------------------------------------


def test_unique_sentinel_rows_are_not_users(users: Any, credentials: Any, totp_factors: Any) -> None:
    """`#unique#` rows share the users table and are not accounts.

    Counting them would inflate `already_clear` by two per user and make the
    summary unreadable against a real environment.
    """
    hashed = hash_password("legacy-password")
    user_id = make_user(users, hashed_password=hashed)
    give_credential(credentials, user_id, hashed)
    users.put_item(Item={"id": unique_lookup_key("username", "someone"), "owner_id": user_id})

    summary, decisions = run(users, credentials, totp_factors)

    assert len(decisions) == 1
    assert summary["already_clear"] == 0


def test_a_disabled_user_is_still_swept(users: Any, credentials: Any, totp_factors: Any, factors_table: Any) -> None:
    """Leaving a disabled account's plaintext seed behind would defeat the sweep."""
    user_id = make_user(users, disabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    give_sealed_factor(factors_table, user_id)

    summary, _ = run(users, credentials, totp_factors, apply=True)

    assert summary["cleared"] == 1
    assert "totp_secret" not in item(users, user_id)


# ---- the no secrets rule -----------------------------------------------------------


def test_no_secret_reaches_the_report(
    users: Any, credentials: Any, totp_factors: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """A script that printed what it was deleting would put it in a CI log."""
    password_hash = hash_password("legacy-password")
    seed = "JBSWY3DPEHPK3PXP"
    user_id = make_user(users, hashed_password=password_hash, totp_secret=seed)
    give_credential(credentials, user_id, password_hash)

    summary, decisions = run(users, credentials, totp_factors)
    script.report(summary, decisions, apply=False)

    output = capsys.readouterr()
    assert password_hash not in output.out + output.err
    assert seed not in output.out + output.err
