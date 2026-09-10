"""`scripts/migrate_totp_seeds_to_identity.py` against moto's DynamoDB and KMS.

The stores and the cipher under test are the package's own, over moto-backed
tables and a moto KMS key. Nothing here is a fake, and that is the whole point:
what this script has to get right is a **row shape and an encryption context**
that another piece of code, `MfaService`, reads back after the cutover. A test
against a stub store would prove the script can call `put` and nothing about
whether MFA still works.

`test_a_sealed_seed_verifies_through_the_packages_mfa_service` is the load
bearing one. It seals a `pyotp`-compatible seed with the script, then satisfies a
challenge through `MfaService.verify_challenge` with a code generated from the
plaintext seed the way the legacy path does. If the row shape, the encryption
context, the `activated_at` derivation or the base32 handling ever diverge, that
test fails here rather than every enrolled user failing to sign in at cutover.

`crypto.py`'s own docstring records that moto 5.2.3 is faithful for the symmetric
KMS path: `GenerateDataKey` and `Decrypt` round trip, the encryption context is
enforced as AAD, and a tampered ciphertext is rejected. That is what makes these
tests meaningful rather than a rehearsal against a permissive fake.
"""

from __future__ import annotations

import base64
from typing import Any, Generator

import boto3
import pytest
from uuid6 import uuid7
from webbpulse.identity import TotpFactorRecord

from app.db.dynamo import client as dynamo_client
from app.db.dynamo.serialization import unique_lookup_key
from app.db.dynamo.tables import USERS
from scripts import migrate_totp_seeds_to_identity as script
from tests.scripts.conftest import PREFIX, REGION

#: A base32 seed in exactly the form `two_factor.py` stores: what
#: `pyotp.random_base32()` produces, unpadded and uppercase.
SEED = base64.b32encode(b"0123456789abcdefghij").decode("ascii").rstrip("=")
OTHER_SEED = base64.b32encode(b"jihgfedcba9876543210").decode("ascii").rstrip("=")


@pytest.fixture
def kms(totp_factors_table: Any) -> Generator[Any, None, None]:
    """A moto KMS client and a symmetric key, as `module.identity` creates one."""
    yield boto3.client("kms", region_name=REGION)


@pytest.fixture
def data_key_arn(kms: Any) -> str:
    """The identity-data key. Distinct from any signing key, as the standard requires."""
    return kms.create_key(Description="carmodpicker-test-identity-data")["KeyMetadata"]["Arn"]


@pytest.fixture
def cipher(data_key_arn: str, kms: Any) -> Any:
    return script.build_cipher(data_key_arn, kms)


@pytest.fixture
def store(totp_factors_table: Any) -> Any:
    """The real `DynamoTotpFactorStore` over the moto table."""
    return script.build_store(PREFIX)


@pytest.fixture
def users(totp_factors_table: Any) -> Any:
    """The raw moto `users` table, written to directly."""
    return dynamo_client.get_resource().Table(f"{PREFIX}-{USERS.suffix}")


def make_user(
    users: Any,
    *,
    seed: str | None = SEED,
    enabled: bool = True,
    **overrides: Any,
) -> str:
    """A users row carrying a legacy TOTP seed. Returns the id."""
    user_id = str(uuid7())
    item: dict[str, Any] = {
        "id": user_id,
        "username": f"user-{user_id[:8]}",
        "email": f"{user_id[:8]}@example.com",
        "email_verified": True,
        "totp_enabled": enabled,
    }
    if seed is not None:
        item["totp_secret"] = seed
    item.update(overrides)
    users.put_item(Item=item)
    return user_id


def rows() -> list[dict[str, Any]]:
    return list(script.iter_user_rows(PREFIX))


# ---------------------------------------------------------------------------
# Sealing
# ---------------------------------------------------------------------------


def test_a_dry_run_writes_nothing(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)

    summary, decisions = script.migrate(rows(), store, cipher)

    assert summary["seal"] == 1
    assert [d.action for d in decisions] == ["seal"]
    assert store.get(user_id) is None


def test_apply_writes_the_factor_in_the_packages_shape(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)

    summary, _ = script.migrate(rows(), store, cipher, apply=True)

    assert summary["seal"] == 1
    factor = store.get(user_id)
    assert factor is not None
    assert factor.user_id == user_id
    # The three envelope fields, all present and all base64.
    assert factor.secret_ciphertext and factor.secret_nonce and factor.wrapped_data_key
    for value in (factor.secret_ciphertext, factor.secret_nonce, factor.wrapped_data_key):
        base64.b64decode(value.encode("ascii"), validate=True)
    assert factor.created_at
    # No watermark to carry: the legacy implementation keeps none.
    assert factor.last_used_step == 0


def test_the_sealed_seed_opens_back_to_the_plaintext(store: Any, cipher: Any, users: Any) -> None:
    """The bytes are unchanged, so no authenticator is re-enrolled."""
    user_id = make_user(users)

    script.migrate(rows(), store, cipher, apply=True)

    factor = store.get(user_id)
    assert script._open(factor, user_id, cipher) == SEED


def test_the_encryption_context_binds_the_ciphertext_to_the_user(store: Any, cipher: Any, users: Any) -> None:
    """A ciphertext moved onto another user's row must not decrypt.

    This is the property `encryption_context` exists for: without it an attacker
    with a single write to `totp-factors` promotes their own seed onto a victim's
    account and every code they generate is accepted.
    """
    victim = make_user(users)
    attacker = make_user(users)

    script.migrate(rows(), store, cipher, apply=True)

    stolen = store.get(attacker)
    assert script._open(stolen, victim, cipher) is None


# ---------------------------------------------------------------------------
# The shape must be one `MfaService` can read
# ---------------------------------------------------------------------------


def test_a_sealed_seed_verifies_through_the_packages_mfa_service(
    store: Any, cipher: Any, users: Any, data_key_arn: str, kms: Any
) -> None:
    """The whole claim of the migration, end to end and through the real reader.

    Sealed by this script, then satisfied through `MfaService.verify_challenge`
    with a code generated from the plaintext the legacy path would have used. If
    the row shape or the encryption context diverged, this is where it shows.
    """
    import pyotp
    from webbpulse.identity import IdentityStores
    from webbpulse.identity.mfa import AMR_OTP, MfaService
    from webbpulse.identity.settings import IdentitySettings

    user_id = make_user(users, enabled=True)
    script.migrate(rows(), store, cipher, apply=True)

    settings = IdentitySettings(
        issuer="https://api.example.com/api/auth",
        audience="carmodpicker-api",
        # A signing key is required to construct the settings and is not used
        # here: nothing in this test mints a token, only verifies a factor.
        signing_key_arns=["arn:aws:kms:us-east-1:1:key/signing-not-used-here"],
        data_key_arn=data_key_arn,
        product_name="CarModPicker",
    )
    service = MfaService(
        settings,
        IdentityStores(totp_factors=store),
        tokens=None,  # type: ignore[arg-type]
        kms_client=kms,
    )

    # The factor is active, so the login challenge would ask for it.
    assert service.factors_for(user_id) == ["totp"]

    # A code from the plaintext seed, generated exactly as `two_factor.py` does.
    code = pyotp.TOTP(SEED).now()
    assert service.verify_challenge(user_id, code) == AMR_OTP


def test_a_pending_enrolment_is_not_a_factor_the_service_challenges(
    store: Any, cipher: Any, users: Any, data_key_arn: str, kms: Any
) -> None:
    """`totp_enabled = False` with a seed present must not gate login.

    Activating it would challenge a user whose authenticator never received the
    seed, which is a lockout with no way through.
    """
    from webbpulse.identity import IdentityStores
    from webbpulse.identity.mfa import MfaService
    from webbpulse.identity.settings import IdentitySettings

    user_id = make_user(users, enabled=False)
    script.migrate(rows(), store, cipher, apply=True)

    factor = store.get(user_id)
    assert factor.activated_at == ""
    assert factor.is_active is False

    settings = IdentitySettings(
        issuer="https://api.example.com/api/auth",
        audience="carmodpicker-api",
        signing_key_arns=["arn:aws:kms:us-east-1:1:key/signing-not-used-here"],
        data_key_arn=data_key_arn,
    )
    service = MfaService(
        settings, IdentityStores(totp_factors=store), tokens=None, kms_client=kms  # type: ignore[arg-type]
    )
    assert service.factors_for(user_id) == []


def test_an_enabled_seed_activates(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users, enabled=True)

    script.migrate(rows(), store, cipher, apply=True)

    factor = store.get(user_id)
    assert factor.activated_at
    assert factor.is_active is True


# ---------------------------------------------------------------------------
# Idempotence and conflicts
# ---------------------------------------------------------------------------


def test_a_rerun_is_idempotent(store: Any, cipher: Any, users: Any) -> None:
    make_user(users)

    script.migrate(rows(), store, cipher, apply=True)
    summary, decisions = script.migrate(rows(), store, cipher, apply=True)

    assert summary == {"seal": 0, "unchanged": 1, "conflict": 0, "skip": 0}
    assert [d.action for d in decisions] == ["unchanged"]


def test_a_rerun_does_not_reseal_and_so_does_not_move_created_at(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)

    script.migrate(rows(), store, cipher, apply=True)
    first = store.get(user_id)
    script.migrate(rows(), store, cipher, apply=True)
    second = store.get(user_id)

    assert second.created_at == first.created_at
    assert second.secret_ciphertext == first.secret_ciphertext


def test_a_different_sealed_seed_is_a_conflict_and_nothing_is_written(store: Any, cipher: Any, users: Any) -> None:
    """A factor enrolled through the identity flow holds a seed a phone has."""
    user_id = make_user(users)
    sealed = cipher.seal(OTHER_SEED.encode("ascii"), user_id=user_id)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
            activated_at="2020-01-01T00:00:00Z",
        )
    )

    with pytest.raises(script.SeedConflict) as error:
        script.migrate(rows(), store, cipher, apply=True)

    assert user_id in error.value.conflicts
    assert script._open(store.get(user_id), user_id, cipher) == OTHER_SEED


def test_a_conflict_blocks_the_whole_run_before_any_write(store: Any, cipher: Any, users: Any) -> None:
    clean = make_user(users)
    conflicted = make_user(users)
    sealed = cipher.seal(OTHER_SEED.encode("ascii"), user_id=conflicted)
    store.put(
        TotpFactorRecord(
            user_id=conflicted,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
        )
    )

    with pytest.raises(script.SeedConflict):
        script.migrate(rows(), store, cipher, apply=True)

    assert store.get(clean) is None


def test_replace_overwrites_a_conflict_but_keeps_created_at(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)
    sealed = cipher.seal(OTHER_SEED.encode("ascii"), user_id=user_id)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
        )
    )

    summary, _ = script.migrate(rows(), store, cipher, apply=True, replace=True)

    assert summary["conflict"] == 1
    factor = store.get(user_id)
    assert script._open(factor, user_id, cipher) == SEED
    assert factor.created_at == "2020-01-01T00:00:00Z"


def test_a_factor_that_will_not_decrypt_is_a_conflict_not_an_overwrite(store: Any, cipher: Any, users: Any) -> None:
    """It might hold a seed a phone actually has; a human decides."""
    user_id = make_user(users)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext="bm90IGEgY2lwaGVydGV4dA==",
            secret_nonce="AAAAAAAAAAAAAAAA",
            wrapped_data_key="AAAAAAAAAAAAAAAA",
            created_at="2020-01-01T00:00:00Z",
        )
    )

    with pytest.raises(script.SeedConflict):
        script.migrate(rows(), store, cipher, apply=True)


def test_the_same_seed_with_the_wrong_state_is_reset_not_a_conflict(store: Any, cipher: Any, users: Any) -> None:
    """The phone holds this seed either way, so `activated_at` is a correction."""
    user_id = make_user(users, enabled=True)
    sealed = cipher.seal(SEED.encode("ascii"), user_id=user_id)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
            activated_at="",
        )
    )

    summary, decisions = script.migrate(rows(), store, cipher, apply=True)

    assert summary["seal"] == 1
    assert summary["conflict"] == 0
    assert "wrong active state" in decisions[0].detail
    assert store.get(user_id).is_active is True


# ---------------------------------------------------------------------------
# Skips
# ---------------------------------------------------------------------------


def test_a_user_with_no_seed_is_skipped(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users, seed=None, enabled=False)

    summary, decisions = script.migrate(rows(), store, cipher, apply=True)

    assert summary["skip"] == 1
    assert decisions[0].action == "skip"
    assert store.get(user_id) is None


def test_unique_sentinel_rows_are_not_users(store: Any, cipher: Any, users: Any) -> None:
    make_user(users)
    users.put_item(Item={"id": unique_lookup_key("username", "someone")})

    summary, decisions = script.migrate(rows(), store, cipher, apply=True)

    assert len(decisions) == 1
    assert summary["seal"] == 1


# ---------------------------------------------------------------------------
# The plaintext survives sealing, and only a later explicit pass removes it
# ---------------------------------------------------------------------------


def test_apply_leaves_the_plaintext_in_place(store: Any, cipher: Any, users: Any) -> None:
    """Rollback is doing nothing, which requires both copies to exist."""
    user_id = make_user(users)

    script.migrate(rows(), store, cipher, apply=True)

    assert users.get_item(Key={"id": user_id})["Item"]["totp_secret"] == SEED


def test_verify_passes_after_a_clean_apply(store: Any, cipher: Any, users: Any) -> None:
    make_user(users)
    script.migrate(rows(), store, cipher, apply=True)

    summary, decisions = script.verify(rows(), store, cipher)

    assert summary["verified"] == 1
    assert summary["mismatch"] == 0
    assert summary["unreadable"] == 0
    assert summary["missing"] == 0
    assert decisions[0].action == "verified"


def test_verify_reports_a_user_whose_factor_was_never_sealed(store: Any, cipher: Any, users: Any) -> None:
    make_user(users)

    summary, _ = script.verify(rows(), store, cipher)

    assert summary["missing"] == 1
    assert summary["verified"] == 0


def test_verify_writes_nothing(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)
    script.migrate(rows(), store, cipher, apply=True)
    before = store.get(user_id)

    script.verify(rows(), store, cipher)

    after = store.get(user_id)
    assert after.secret_ciphertext == before.secret_ciphertext
    assert users.get_item(Key={"id": user_id})["Item"]["totp_secret"] == SEED


def test_clear_plaintext_is_a_dry_run_by_default(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)
    script.migrate(rows(), store, cipher, apply=True)

    summary, _ = script.clear_plaintext(rows(), store, cipher, prefix=PREFIX)

    assert summary["cleared"] == 1
    assert users.get_item(Key={"id": user_id})["Item"]["totp_secret"] == SEED


def test_clear_plaintext_removes_the_attribute_once_applied(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)
    script.migrate(rows(), store, cipher, apply=True)

    summary, _ = script.clear_plaintext(rows(), store, cipher, prefix=PREFIX, apply=True)

    assert summary["cleared"] == 1
    # REMOVE rather than a null, so the attribute is simply gone.
    assert "totp_secret" not in users.get_item(Key={"id": user_id})["Item"]
    # And the sealed copy, the only one left, still opens.
    assert script._open(store.get(user_id), user_id, cipher) == SEED


def test_clear_plaintext_refuses_a_user_whose_factor_is_missing(store: Any, cipher: Any, users: Any) -> None:
    """The plaintext is the only readable copy; destroying it would end the factor."""
    user_id = make_user(users)

    summary, decisions = script.clear_plaintext(rows(), store, cipher, prefix=PREFIX, apply=True)

    assert summary["refused"] == 1
    assert summary["cleared"] == 0
    assert "plaintext kept" in decisions[0].detail
    assert users.get_item(Key={"id": user_id})["Item"]["totp_secret"] == SEED


def test_clear_plaintext_refuses_a_factor_holding_a_different_seed(store: Any, cipher: Any, users: Any) -> None:
    user_id = make_user(users)
    sealed = cipher.seal(OTHER_SEED.encode("ascii"), user_id=user_id)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
        )
    )

    summary, _ = script.clear_plaintext(rows(), store, cipher, prefix=PREFIX, apply=True)

    assert summary["refused"] == 1
    assert users.get_item(Key={"id": user_id})["Item"]["totp_secret"] == SEED


# ---------------------------------------------------------------------------
# Nothing prints a seed, and the decisions cannot carry one
# ---------------------------------------------------------------------------


def test_no_output_contains_a_seed_or_any_envelope_field(store: Any, cipher: Any, users: Any, capsys: Any) -> None:
    """A TOTP seed is the secret itself, and CloudWatch is not where it belongs."""
    user_id = make_user(users)

    summary, decisions = script.migrate(rows(), store, cipher, apply=True)
    script.report(summary, decisions, "applied")
    summary, decisions = script.verify(rows(), store, cipher)
    script.report(summary, decisions, "verify, read only")

    printed = capsys.readouterr().out
    assert SEED not in printed
    factor = store.get(user_id)
    assert factor.secret_ciphertext not in printed
    assert factor.secret_nonce not in printed
    assert factor.wrapped_data_key not in printed


def test_a_decision_carries_no_seed_field(store: Any, cipher: Any, users: Any) -> None:
    """Structural, so a future field cannot reintroduce one by accident."""
    make_user(users)

    _, decisions = script.migrate(rows(), store, cipher, apply=True)

    assert set(script.Decision._fields) == {
        "user_id",
        "action",
        "detail",
        "activate",
        "created_at",
    }
    for decision in decisions:
        assert SEED not in "".join(str(value) for value in decision)


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------


def test_parse_args_requires_a_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DYNAMODB_TABLE_PREFIX", raising=False)
    monkeypatch.setenv("IDENTITY_DATA_KEY_ARN", "arn:aws:kms:us-west-2:1:key/abc")
    with pytest.raises(SystemExit):
        script.parse_args([])


def test_parse_args_requires_a_data_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IDENTITY_DATA_KEY_ARN", raising=False)
    with pytest.raises(SystemExit):
        script.parse_args(["--prefix", PREFIX])


def test_parse_args_defaults_both_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DYNAMODB_TABLE_PREFIX", "carmodpicker-staging")
    monkeypatch.setenv("IDENTITY_DATA_KEY_ARN", "arn:aws:kms:us-west-2:1:key/abc")
    args = script.parse_args([])
    assert args.prefix == "carmodpicker-staging"
    assert args.data_key_arn == "arn:aws:kms:us-west-2:1:key/abc"
    assert args.apply is False
    assert args.verify is False
    assert args.clear_plaintext is False


def test_verify_and_clear_plaintext_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        script.parse_args(["--prefix", PREFIX, "--data-key-arn", "k", "--verify", "--clear-plaintext"])


def test_main_dry_runs_by_default(
    store: Any, cipher: Any, users: Any, data_key_arn: str, kms: Any, capsys: Any
) -> None:
    user_id = make_user(users)

    exit_code = script.main(["--prefix", PREFIX, "--data-key-arn", data_key_arn], kms_client=kms)

    assert exit_code == 0
    assert "dry run, nothing written" in capsys.readouterr().out
    assert store.get(user_id) is None


def test_main_returns_one_on_a_conflict(
    store: Any, cipher: Any, users: Any, data_key_arn: str, kms: Any, capsys: Any
) -> None:
    user_id = make_user(users)
    sealed = cipher.seal(OTHER_SEED.encode("ascii"), user_id=user_id)
    store.put(
        TotpFactorRecord(
            user_id=user_id,
            secret_ciphertext=sealed.ciphertext,
            secret_nonce=sealed.nonce,
            wrapped_data_key=sealed.wrapped_key,
            created_at="2020-01-01T00:00:00Z",
        )
    )

    exit_code = script.main(["--prefix", PREFIX, "--data-key-arn", data_key_arn, "--apply"], kms_client=kms)

    assert exit_code == 1
    assert "--replace" in capsys.readouterr().err


def test_main_verify_returns_one_when_a_factor_is_missing(store: Any, users: Any, data_key_arn: str, kms: Any) -> None:
    """The runbook's gate on clearing is an exit code, not a reading."""
    make_user(users)

    exit_code = script.main(["--prefix", PREFIX, "--data-key-arn", data_key_arn, "--verify"], kms_client=kms)

    assert exit_code == 1


def test_main_verify_returns_zero_after_a_clean_apply(store: Any, users: Any, data_key_arn: str, kms: Any) -> None:
    make_user(users)
    script.main(["--prefix", PREFIX, "--data-key-arn", data_key_arn, "--apply"], kms_client=kms)

    exit_code = script.main(["--prefix", PREFIX, "--data-key-arn", data_key_arn, "--verify"], kms_client=kms)

    assert exit_code == 0
