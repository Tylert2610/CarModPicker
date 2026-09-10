"""`scripts/migrate_credentials_to_identity.py` against moto and the real store.

The store under test is the package's `DynamoCredentialStore` over a moto-backed
`credentials` table, not a fake. That is the point: the claim this migration
rests on is that a hash written by the legacy path verifies through the identity
flow, and a test against a stub store would prove only that the script can call
`put`.

`test_the_migrated_hash_verifies_through_the_package` is the load bearing one.
It hashes a password the way `app/api/dependencies/auth.py` does, migrates it,
and then verifies the plaintext against the migrated credential with
`webbpulse.security.verify_password`, which is the function the identity login
flow calls. If the two ever stop being the same bcrypt, that fails here rather
than every account failing to sign in after a cutover.

The `credentials` table is created by the fixture rather than by
`app/db/dynamo/tables.py`, because it is not a product table: row 4's
`module.identity` creates it in Terraform, and `TABLES` deliberately does not
carry it.
"""

from __future__ import annotations

from typing import Any

import pytest
from uuid6 import uuid7
from webbpulse.identity import PASSWORD_CREDENTIAL_TYPE, CredentialRecord
from webbpulse.security import hash_password, verify_password

from app.db.dynamo import client as dynamo_client
from app.db.dynamo.serialization import unique_lookup_key
from app.db.dynamo.tables import USERS
from scripts import migrate_credentials_to_identity as script
from tests.scripts.conftest import PREFIX


@pytest.fixture
def store(credentials_table: Any) -> Any:
    """The real `DynamoCredentialStore` over the moto table."""
    return script.build_store(PREFIX)


@pytest.fixture
def users(credentials_table: Any) -> Any:
    """The raw moto `users` table, written to directly.

    Directly rather than through `UserRepository` because several of these cases
    are rows the model refuses to build: a non bcrypt hash in a field the model
    types as a hash, and a `#unique#` sentinel that is not a user at all.
    """
    return dynamo_client.get_resource().Table(f"{PREFIX}-{USERS.suffix}")


def make_user(users: Any, password: str | None = "legacy-password", **overrides: Any) -> str:
    """A users row shaped like the one signup writes. Returns the id."""
    user_id = str(uuid7())
    item: dict[str, Any] = {
        "id": user_id,
        "username": f"user-{user_id[:8]}",
        "email": f"{user_id[:8]}@example.com",
        "email_verified": True,
        "disabled": False,
    }
    if password is not None:
        item["hashed_password"] = hash_password(password)
    item.update(overrides)
    users.put_item(Item=item)
    return user_id


def rows(prefix: str = PREFIX) -> list[dict[str, Any]]:
    return list(script.iter_user_rows(prefix))


def test_a_dry_run_writes_nothing(store: Any, users: Any) -> None:
    user_id = make_user(users)

    summary, decisions = script.migrate(rows(), store)

    assert summary["write"] == 1
    assert [d.action for d in decisions] == ["write"]
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is None


def test_apply_writes_the_credential_in_the_packages_shape(store: Any, users: Any) -> None:
    user_id = make_user(users)
    legacy = users.get_item(Key={"id": user_id})["Item"]["hashed_password"]

    summary, _ = script.migrate(rows(), store, apply=True)

    assert summary["write"] == 1
    credential = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)
    assert credential is not None
    assert credential.user_id == user_id
    assert credential.credential_type == PASSWORD_CREDENTIAL_TYPE
    assert credential.secret == legacy
    # The store fills both timestamps in when the record leaves them empty.
    assert credential.created_at
    assert credential.updated_at


def test_the_migrated_hash_verifies_through_the_package(store: Any, users: Any) -> None:
    """The whole claim of the migration, end to end.

    The legacy attribute is written by `webbpulse.security.hash_password` and
    the identity login flow verifies with `webbpulse.security.verify_password`,
    so the copied secret must accept the original plaintext and reject anything
    else.
    """
    user_id = make_user(users, password="correct-horse-battery")

    script.migrate(rows(), store, apply=True)

    credential = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)
    assert verify_password("correct-horse-battery", credential.secret) is True
    assert verify_password("wrong-password", credential.secret) is False


def test_a_rerun_is_idempotent_and_preserves_created_at(store: Any, users: Any) -> None:
    user_id = make_user(users)

    script.migrate(rows(), store, apply=True)
    first = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)

    summary, decisions = script.migrate(rows(), store, apply=True)

    assert summary == {
        "write": 0,
        "unchanged": 1,
        "conflict": 0,
        "skip_oauth_only": 0,
        "skip": 0,
    }
    assert [d.action for d in decisions] == ["unchanged"]
    second = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)
    assert second.secret == first.secret
    assert second.created_at == first.created_at
    assert second.updated_at == first.updated_at


def test_a_differing_credential_is_a_conflict_and_nothing_is_written(store: Any, users: Any) -> None:
    """A password changed through the identity flow must not be reverted."""
    user_id = make_user(users)
    changed = hash_password("changed-through-identity")
    store.put(
        CredentialRecord(
            user_id=user_id,
            credential_type=PASSWORD_CREDENTIAL_TYPE,
            secret=changed,
        )
    )

    with pytest.raises(script.CredentialConflict) as error:
        script.migrate(rows(), store, apply=True)

    assert user_id in error.value.conflicts
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE).secret == changed


def test_a_conflict_blocks_the_whole_run_before_any_write(store: Any, users: Any) -> None:
    """Refusing first, not partway through: a half applied run is worse."""
    clean = make_user(users)
    conflicted = make_user(users)
    store.put(
        CredentialRecord(
            user_id=conflicted,
            credential_type=PASSWORD_CREDENTIAL_TYPE,
            secret=hash_password("changed-through-identity"),
        )
    )

    with pytest.raises(script.CredentialConflict):
        script.migrate(rows(), store, apply=True)

    assert store.get(clean, PASSWORD_CREDENTIAL_TYPE) is None


def test_replace_overwrites_a_conflict_but_keeps_created_at(store: Any, users: Any) -> None:
    user_id = make_user(users)
    legacy = users.get_item(Key={"id": user_id})["Item"]["hashed_password"]
    store.put(
        CredentialRecord(
            user_id=user_id,
            credential_type=PASSWORD_CREDENTIAL_TYPE,
            secret=hash_password("changed-through-identity"),
            created_at="2020-01-01T00:00:00Z",
        )
    )

    summary, _ = script.migrate(rows(), store, apply=True, replace=True)

    assert summary["conflict"] == 1
    credential = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)
    assert credential.secret == legacy
    assert credential.created_at == "2020-01-01T00:00:00Z"


def test_an_oauth_only_account_is_its_own_skip_count(store: Any, users: Any) -> None:
    """`hashed_password = None` is the ordinary Google-only account.

    Counted apart from the unreadable-hash skips, because on a production run
    these are most of the rows and a merged total would read as data loss.
    """
    user_id = make_user(users, password=None)

    summary, decisions = script.migrate(rows(), store, apply=True)

    assert summary["skip_oauth_only"] == 1
    assert summary["skip"] == 0
    assert decisions[0].action == "skip_oauth_only"
    assert "OAuth only" in decisions[0].detail
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is None


def test_a_non_bcrypt_hash_is_a_skip_not_an_oauth_skip(store: Any, users: Any) -> None:
    """Copying an unrecognised secret would write a credential that never verifies."""
    user_id = make_user(users, hashed_password="pbkdf2_sha256$390000$salt$hash")

    summary, decisions = script.migrate(rows(), store, apply=True)

    assert summary["skip"] == 1
    assert summary["skip_oauth_only"] == 0
    assert "not a bcrypt" in decisions[0].detail
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is None


def test_a_disabled_user_still_migrates(store: Any, users: Any) -> None:
    """`may_authenticate` is the gate, not this script.

    Deciding who may sign in belongs to the hooks, and a migration that silently
    dropped a disabled user's credential would make reactivating them a password
    reset.
    """
    user_id = make_user(users, disabled=True)

    summary, _ = script.migrate(rows(), store, apply=True)

    assert summary["write"] == 1
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is not None


def test_a_tombstoned_user_still_migrates(store: Any, users: Any) -> None:
    """Same reason as a disabled one: this script does not decide who signs in."""
    user_id = make_user(users, deleted=True, deleted_at="2026-01-01T00:00:00Z")

    summary, _ = script.migrate(rows(), store, apply=True)

    assert summary["write"] == 1
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is not None


def test_unique_sentinel_rows_are_not_users(store: Any, users: Any) -> None:
    """`#unique#` rows share the table and are not accounts.

    Counting them would inflate `skip_oauth_only` by two per user and make the
    summary meaningless on a real run.
    """
    make_user(users)
    users.put_item(Item={"id": unique_lookup_key("username", "someone")})
    users.put_item(Item={"id": unique_lookup_key("email", "someone@example.com")})

    summary, decisions = script.migrate(rows(), store, apply=True)

    assert len(decisions) == 1
    assert summary["write"] == 1
    assert summary["skip_oauth_only"] == 0


def test_the_report_never_prints_a_hash(store: Any, users: Any, capsys: Any) -> None:
    """A bcrypt hash is a verifier, and CloudWatch is not where it belongs."""
    user_id = make_user(users)
    legacy = users.get_item(Key={"id": user_id})["Item"]["hashed_password"]

    summary, decisions = script.migrate(rows(), store, apply=True)
    script.report(summary, decisions, apply=True)

    assert legacy not in capsys.readouterr().out


@pytest.mark.parametrize(
    "value,supported",
    [
        ("$2b$12$" + "a" * 53, True),
        ("$2a$12$" + "a" * 53, True),
        ("$2y$12$" + "a" * 53, True),
        ("$2b$12$tooshort", False),
        ("$2b$12$" + "a" * 54, False),
        ("pbkdf2_sha256$390000$salt$hash", False),
        ("", False),
        (None, False),
        (12345, False),
    ],
)
def test_is_supported_hash(value: Any, supported: bool) -> None:
    assert script.is_supported_hash(value) is supported


def test_parse_args_requires_a_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DYNAMODB_TABLE_PREFIX", raising=False)
    with pytest.raises(SystemExit):
        script.parse_args([])


def test_parse_args_defaults_the_prefix_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DYNAMODB_TABLE_PREFIX", "carmodpicker-staging")
    args = script.parse_args([])
    assert args.prefix == "carmodpicker-staging"
    assert args.apply is False
    assert args.replace is False


def test_main_dry_runs_by_default_and_reports(store: Any, users: Any, capsys: Any) -> None:
    user_id = make_user(users)

    exit_code = script.main(["--prefix", PREFIX])

    assert exit_code == 0
    assert "dry run, nothing written" in capsys.readouterr().out
    assert store.get(user_id, PASSWORD_CREDENTIAL_TYPE) is None


def test_main_returns_one_on_a_conflict(store: Any, users: Any, capsys: Any) -> None:
    user_id = make_user(users)
    store.put(
        CredentialRecord(
            user_id=user_id,
            credential_type=PASSWORD_CREDENTIAL_TYPE,
            secret=hash_password("changed-through-identity"),
        )
    )

    exit_code = script.main(["--prefix", PREFIX, "--apply"])

    assert exit_code == 1
    assert "--replace" in capsys.readouterr().err
