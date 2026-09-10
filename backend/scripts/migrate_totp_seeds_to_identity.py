"""Seal each user's plaintext TOTP seed into the identity `totp-factors` table.

The other half of row 7. `migrate_credentials_to_identity.py` moves first
factors; this moves second ones, and it is the script that decides whether a
user with an authenticator app can still sign in after the cutover.

`docs/identity-migration-runbook.md` gives the order of operations.

## The seed is unchanged, so no authenticator is re-enrolled

CarModPicker stores `users.totp_secret` as an unpadded uppercase base32 string
and feeds it to `pyotp.TOTP`, which is RFC 6238 with the universal defaults:
HMAC-SHA1, 30 second steps, six digits. `webbpulse.identity.totp` is the same
arithmetic with the same defaults over the same base32 seed, and it accepts the
padding and case a stored seed might carry.

So the migration moves the **same bytes** into a new place, and every phone
already holding the account keeps producing codes that verify. Nobody rescans a
QR code. `tests/scripts/test_totp_seed_migration.py` proves that by sealing with
this script and then verifying a `pyotp`-generated code through the package's
own `MfaService`, which is the code path that runs after the cutover.

## What sealing means, and why it is not a copy

The plaintext seed is the one identity secret that cannot be hashed: the server
recomputes the code, so the value has to come back. `docs/security/totp-seed-encryption.md`
is the finding that CarModPicker stores it in the clear on the user row, and
this is the fix.

`EnvelopeCipher` generates a fresh AES-256 data key from KMS under
`IDENTITY_DATA_KEY_ARN`, encrypts the seed locally with AES-256-GCM, and stores
the ciphertext, the nonce and the KMS wrapped data key. Reading a usable seed
then needs `dynamodb:GetItem` **and** `kms:Decrypt`, and every decrypt is a
CloudTrail event.

The **encryption context** is `{"user_id": <id>, "purpose": "totp"}`, built by
the package's own `encryption_context` and never spelled here. KMS binds it into
the wrapped key as authenticated data, so a ciphertext copied into another
user's row fails to decrypt rather than silently authenticating the wrong
person. This script must produce exactly the context `MfaService._open_seed`
rebuilds on the verify path, which is why it calls `EnvelopeCipher.seal` with
the `user_id` rather than assembling an item itself.

## `activated_at` is derived from `totp_enabled`, and that is the whole state

`TotpFactorRecord.is_active` is `bool(activated_at)`, and only an **active**
factor appears in `MfaService.factors_for` and therefore in the login challenge.

- `totp_enabled = True` migrates with `activated_at` set, so the user is
  challenged for a code exactly as they are today.
- `totp_enabled = False` with a seed present is a **pending enrolment**: the user
  started setup and never confirmed it. It migrates with `activated_at` empty,
  so it does not gate login, matching what the legacy code does with such a row.

Getting this backwards in either direction is the failure mode worth guarding.
Activating a pending enrolment would challenge a user whose authenticator never
received the seed and lock them out; leaving an enabled factor inactive would
silently drop a working second factor to none.

`last_used_step` starts at 0. The legacy implementation keeps no replay
watermark, so there is nothing to carry, and 0 means "nothing accepted yet",
which accepts the user's next code and refuses every replay after it.

## No seed is ever logged, and this is enforced

`report` prints user ids, actions and reasons. It never prints a seed, a
ciphertext, a nonce or a wrapped key, and there is no verbose flag that would.
The `Decision` this script carries deliberately holds **no** seed field: the
plaintext is read inside `migrate`, sealed, and dropped, so a decision list that
escapes into a log or a traceback cannot carry one.
`tests/scripts/test_totp_seed_migration.py` asserts that on the real output.

## Clearing the plaintext is a separate, later pass

Three modes, and they are meant to be run as three separate commands:

1. `--apply` seals every seed into `totp-factors` and **leaves
   `users.totp_secret` exactly where it is**. Both copies exist, and the legacy
   2FA path keeps working, so this is reversible by deleting the new rows.
2. `--verify` opens every sealed row back through `EnvelopeCipher` and checks it
   equals the plaintext still on the user row. This is what makes step 3 safe,
   and it is why step 1 does not clear.
3. `--clear-plaintext` sets `users.totp_secret` to `None` on rows whose sealed
   copy verifies. It refuses any row it could not verify, so a seed is never
   destroyed while the only other copy is unreadable.

`docs/security/totp-seed-encryption.md` prefers a lazy migrate-on-use, and its
reversibility concern is exactly what the split above answers: until step 3
runs, rollback is doing nothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# See the sibling credential script: `app.core.config` refuses to construct
# without these, and this migration authenticates nobody.
for _name, _placeholder in (
    ("SECRET_KEY", "migration"),
    ("EMAIL_FROM", "migration@example.com"),
):
    os.environ.setdefault(_name, _placeholder)

from webbpulse.dynamodb import now_iso  # noqa: E402
from webbpulse.identity import TOTP_FACTORS_TABLE  # noqa: E402
from webbpulse.identity.crypto import (  # noqa: E402
    EnvelopeCipher,
    EnvelopeDecryptionFailed,
    SealedSecret,
)

from app.db.dynamo.serialization import UNIQUE_KEY_PREFIX  # noqa: E402
from app.db.dynamo.tables import USERS  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - typing only
    from webbpulse.identity import TotpFactorStore

#: The legacy attributes on a CarModPicker user row.
LEGACY_SEED_FIELD = "totp_secret"
LEGACY_ENABLED_FIELD = "totp_enabled"

#: The actions `plan` may return, and the keys of the summary.
ACTIONS = ("seal", "unchanged", "conflict", "skip")

#: The actions `verify` and `clear` report.
VERIFY_ACTIONS = ("verified", "mismatch", "unreadable", "missing", "skip")
CLEAR_ACTIONS = ("cleared", "already_clear", "refused", "skip")


class SeedConflict(Exception):
    """A user already holds a sealed factor that is not this plaintext seed.

    Raised rather than resolved. A factor written through the identity enrolment
    flow after the cutover began holds a seed the user's phone actually has, and
    overwriting it with the legacy one would break their authenticator. A run
    pointed at the wrong environment's tables must write nothing at all.
    `--replace` is the explicit way to say the user row is the truth.
    """

    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = conflicts
        detail = ", ".join(str(user_id) for user_id in conflicts)
        super().__init__(
            f"{len(conflicts)} user(s) already hold a different TOTP factor "
            f"({detail}); rerun with --replace to overwrite from the users table"
        )


class Decision(NamedTuple):
    """What one user needs, decided without writing anything.

    **Carries no seed, deliberately.** The credential script's `Decision` holds
    the bcrypt hash it will write, which is a verifier and not a secret; a TOTP
    seed is the secret itself, and a decision list is a thing that ends up in a
    log line, a traceback or a debugger. `migrate` reads the plaintext from the
    row a second time inside the write, which costs nothing because the row is
    already in memory, and buys the guarantee that no structure this module
    returns can leak one.
    """

    user_id: str
    action: str
    detail: str
    #: Whether the factor should be active, from `totp_enabled`. Reported so a
    #: dry run shows the state it would write.
    activate: bool = False
    #: Preserved across a `--replace`, as in the credential script.
    created_at: str = ""


def build_store(prefix: str, endpoint_url: str | None = None, region_name: str | None = None) -> "TotpFactorStore":
    """The package's `DynamoTotpFactorStore` over the `totp-factors` table.

    The same construction the running identity function builds, so the rows this
    writes are the rows `MfaService` reads.
    """
    from webbpulse.dynamodb import Repository
    from webbpulse.identity import DynamoTotpFactorStore

    return DynamoTotpFactorStore(
        Repository(
            TOTP_FACTORS_TABLE,
            prefix=prefix,
            endpoint_url=endpoint_url or None,
            region_name=region_name or None,
        )
    )


def build_cipher(data_key_arn: str, kms_client: Any = None) -> EnvelopeCipher:
    """The package's `EnvelopeCipher` under the identity data key.

    Built from the same `IDENTITY_DATA_KEY_ARN` the identity function carries, so
    the wrapped data keys this writes are ones that function can unwrap. A
    different key produces rows that decrypt nowhere, and the symptom is a user
    whose second factor stopped working with nothing in the logs to say why.
    """
    if kms_client is None:
        import boto3

        kms_client = boto3.client("kms")
    return EnvelopeCipher(data_key_arn, kms_client)


def iter_user_rows(
    prefix: str, endpoint_url: str | None = None, region_name: str | None = None
) -> Iterable[dict[str, Any]]:
    """Every user row, raw, with the `#unique#` sentinel rows excluded.

    Raw for the same reason the credential script scans raw: row 13 retires
    `totp_secret` from the model, and this script has to keep reading rows
    written before that.
    """
    from boto3.dynamodb.conditions import Attr
    from webbpulse.dynamodb import Repository

    repository = Repository(
        USERS.suffix,
        prefix=prefix,
        endpoint_url=endpoint_url or None,
        region_name=region_name or None,
    )
    not_a_sentinel = ~Attr(USERS.partition_key.name).begins_with(UNIQUE_KEY_PREFIX)

    start_key: dict[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {"FilterExpression": not_a_sentinel}
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        response = repository.table.scan(**kwargs)
        for item in response.get("Items", []):
            yield dict(item)
        start_key = response.get("LastEvaluatedKey")
        if not start_key:
            return


def _seed_of(user: dict[str, Any]) -> str:
    """The plaintext seed on a user row, normalised to a string, or empty."""
    seed = user.get(LEGACY_SEED_FIELD)
    return str(seed) if seed else ""


def plan(
    user_rows: Iterable[dict[str, Any]],
    store: "TotpFactorStore",
    cipher: EnvelopeCipher,
) -> list[tuple[Decision, dict[str, Any]]]:
    """Decide what each user needs, writing nothing.

    Returns `(decision, user_row)` pairs rather than decisions alone, so
    `migrate` writes from the row this pass read instead of scanning a second
    time and possibly applying something the dry run never showed. The seed
    stays inside the row dict and never inside the `Decision`.

    Deciding `unchanged` costs one `kms:Decrypt` per already sealed user,
    because the only way to tell whether a sealed row holds this seed is to open
    it. That is the price of idempotence here and it is paid once per rerun.
    """
    decisions: list[tuple[Decision, dict[str, Any]]] = []
    for user in user_rows:
        user_id = str(user["id"])
        seed = _seed_of(user)

        if not seed:
            # No second factor, which is most accounts. Nothing to seal.
            decisions.append((Decision(user_id, "skip", "no TOTP seed on the user row"), user))
            continue

        activate = bool(user.get(LEGACY_ENABLED_FIELD))
        existing = store.get(user_id)
        if existing is None:
            detail = "no factor yet, enabled" if activate else "no factor yet, pending enrolment"
            decisions.append((Decision(user_id, "seal", detail, activate), user))
            continue

        opened = _open(existing, user_id, cipher)
        if opened == seed and bool(existing.activated_at) == activate:
            decisions.append((Decision(user_id, "unchanged", "factor already matches", activate), user))
        elif opened == seed:
            # Same seed, wrong state. Resealing rewrites `activated_at` to match
            # `totp_enabled`, which is a correction rather than a conflict: the
            # user's phone holds this seed either way.
            detail = "factor holds this seed but the wrong active state"
            decisions.append(
                (
                    Decision(user_id, "seal", detail, activate, existing.created_at),
                    user,
                )
            )
        else:
            decisions.append(
                (
                    Decision(
                        user_id,
                        "conflict",
                        "factor holds a different seed" if opened is not None else "factor could not be decrypted",
                        activate,
                        existing.created_at,
                    ),
                    user,
                )
            )
    return decisions


def _open(factor: Any, user_id: str, cipher: EnvelopeCipher) -> str | None:
    """Decrypt a stored factor's seed, or `None` when it will not open.

    `None` for every failure, as `EnvelopeCipher` gives one exception for every
    cause. A row that will not open is a conflict rather than something to
    overwrite silently: the seed inside it might be one a phone actually holds.
    """
    sealed = SealedSecret(
        ciphertext=factor.secret_ciphertext,
        nonce=factor.secret_nonce,
        wrapped_key=factor.wrapped_data_key,
    )
    try:
        return cipher.open(sealed, user_id=user_id).decode("ascii")
    except (EnvelopeDecryptionFailed, ValueError, UnicodeDecodeError):
        return None


def migrate(
    user_rows: Iterable[dict[str, Any]],
    store: "TotpFactorStore",
    cipher: EnvelopeCipher,
    *,
    apply: bool = False,
    replace: bool = False,
) -> tuple[dict[str, int], list[Decision]]:
    """Seal every migratable seed. Dry run unless `apply` is true.

    Raises `SeedConflict` when a user holds a different factor and `replace` was
    not passed, **before writing anything at all**.

    Returns only the decisions, never the `(decision, row)` pairs, so the caller
    and anything it logs cannot reach a plaintext seed.
    """
    from webbpulse.identity import TotpFactorRecord

    pairs = plan(user_rows, store, cipher)
    decisions = [decision for decision, _ in pairs]

    conflicts = [d.user_id for d in decisions if d.action == "conflict"]
    if conflicts and not replace:
        raise SeedConflict(conflicts)

    summary = {action: 0 for action in ACTIONS}
    for decision, user in pairs:
        summary[decision.action] += 1
        if decision.action in ("unchanged", "skip"):
            continue
        if not apply:
            continue

        sealed = cipher.seal(_seed_of(user).encode("ascii"), user_id=decision.user_id)
        store.put(
            TotpFactorRecord(
                user_id=decision.user_id,
                secret_ciphertext=sealed.ciphertext,
                secret_nonce=sealed.nonce,
                wrapped_data_key=sealed.wrapped_key,
                created_at=decision.created_at or now_iso(),
                # The whole of the factor's state. Empty means enrolled but
                # never confirmed, which is what `totp_enabled = False` with a
                # seed present means today.
                activated_at=(now_iso() if decision.activate else ""),
                # No watermark to carry: the legacy implementation keeps none.
                last_used_step=0,
            )
        )
    return summary, decisions


def verify(
    user_rows: Iterable[dict[str, Any]],
    store: "TotpFactorStore",
    cipher: EnvelopeCipher,
) -> tuple[dict[str, int], list[Decision]]:
    """Open every sealed factor and check it against the plaintext still stored.

    Read only, always, with no `--apply` of its own. This is the gate on
    `--clear-plaintext`: the plaintext is the only other copy of the seed, so
    destroying it without having read the sealed one back is how a user loses a
    second factor to a key policy nobody noticed.
    """
    summary = {action: 0 for action in VERIFY_ACTIONS}
    decisions: list[Decision] = []
    for user in user_rows:
        user_id = str(user["id"])
        seed = _seed_of(user)
        if not seed:
            decisions.append(Decision(user_id, "skip", "no TOTP seed on the user row"))
            summary["skip"] += 1
            continue

        factor = store.get(user_id)
        if factor is None:
            decisions.append(Decision(user_id, "missing", "no sealed factor for this user"))
            summary["missing"] += 1
            continue

        opened = _open(factor, user_id, cipher)
        if opened is None:
            decisions.append(Decision(user_id, "unreadable", "the sealed factor would not decrypt"))
            summary["unreadable"] += 1
        elif opened != seed:
            decisions.append(Decision(user_id, "mismatch", "the sealed factor holds a different seed"))
            summary["mismatch"] += 1
        else:
            active = bool(factor.activated_at)
            detail = "sealed seed matches, active" if active else "sealed seed matches, pending"
            decisions.append(Decision(user_id, "verified", detail, active))
            summary["verified"] += 1
    return summary, decisions


def clear_plaintext(
    user_rows: Iterable[dict[str, Any]],
    store: "TotpFactorStore",
    cipher: EnvelopeCipher,
    *,
    prefix: str,
    endpoint_url: str | None = None,
    region_name: str | None = None,
    apply: bool = False,
) -> tuple[dict[str, int], list[Decision]]:
    """Remove `users.totp_secret` on rows whose sealed copy verifies.

    Each row is verified again here rather than trusting an earlier `--verify`
    run, because the two are separate commands and something could have changed
    between them. A row that does not verify is `refused` and its plaintext
    stays: this pass never destroys the only readable copy of a seed.

    Dry run unless `apply` is true, like every other mode.
    """
    from webbpulse.dynamodb import Repository

    repository = Repository(
        USERS.suffix,
        prefix=prefix,
        endpoint_url=endpoint_url or None,
        region_name=region_name or None,
    )

    summary = {action: 0 for action in CLEAR_ACTIONS}
    decisions: list[Decision] = []
    for user in user_rows:
        user_id = str(user["id"])
        seed = _seed_of(user)
        if not seed:
            decisions.append(Decision(user_id, "already_clear", "no plaintext seed stored"))
            summary["already_clear"] += 1
            continue

        factor = store.get(user_id)
        if factor is None or _open(factor, user_id, cipher) != seed:
            decisions.append(
                Decision(
                    user_id,
                    "refused",
                    "the sealed factor is missing or does not match; plaintext kept",
                )
            )
            summary["refused"] += 1
            continue

        decisions.append(Decision(user_id, "cleared", "sealed copy verified"))
        summary["cleared"] += 1
        if apply:
            # REMOVE rather than SET to null: the attribute simply goes away,
            # which is what `totp_secret: str | None = None` reads back as, and
            # it leaves nothing on the row for a later reader to mistake for a
            # seed.
            repository.update(
                {USERS.partition_key.name: user_id},
                update_expression=f"REMOVE {LEGACY_SEED_FIELD}",
            )
    return summary, decisions


def report(summary: dict[str, int], decisions: list[Decision], mode: str) -> None:
    """Print the plan and the totals.

    Ids, actions and reasons only. No seed, no ciphertext, no nonce and no
    wrapped key ever reaches this function, because `Decision` carries none of
    them. See the module docstring.
    """
    print(f"totp seed migration ({mode})")
    for decision in decisions:
        print(f"  user {decision.user_id}: {decision.action} ({decision.detail})")
    print("  totals: " + ", ".join(f"{action}={count}" for action, count in summary.items()))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seal each user's plaintext TOTP seed into the identity totp-factors "
            "table. Dry run unless --apply is passed. Clearing the plaintext is a "
            "separate --clear-plaintext pass, run only after --verify."
        )
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("DYNAMODB_TABLE_PREFIX"),
        help="DynamoDB table prefix (default: $DYNAMODB_TABLE_PREFIX)",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("DYNAMODB_ENDPOINT_URL"),
        help="DynamoDB endpoint (default: $DYNAMODB_ENDPOINT_URL, else AWS)",
    )
    parser.add_argument(
        "--data-key-arn",
        default=os.environ.get("IDENTITY_DATA_KEY_ARN"),
        help="KMS identity-data key (default: $IDENTITY_DATA_KEY_ARN)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        help="AWS region (default: $AWS_REGION, then $AWS_DEFAULT_REGION, else boto3's)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write; without it the script only prints the plan",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="overwrite a factor holding a different seed",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify",
        action="store_true",
        help="read every sealed factor back and compare it to the plaintext; writes nothing",
    )
    mode.add_argument(
        "--clear-plaintext",
        action="store_true",
        help=(
            "remove users.totp_secret on rows whose sealed copy verifies. Run only "
            "after a clean --verify, and only with --apply to actually write."
        ),
    )
    args = parser.parse_args(argv)
    if not args.prefix:
        parser.error("--prefix is required when DYNAMODB_TABLE_PREFIX is not set")
    if not args.data_key_arn:
        parser.error("--data-key-arn is required when IDENTITY_DATA_KEY_ARN is not set")
    return args


def main(argv: list[str] | None = None, *, kms_client: Any = None) -> int:
    args = parse_args(argv)

    store = build_store(args.prefix, args.endpoint_url, args.region)
    cipher = build_cipher(args.data_key_arn, kms_client)

    if args.verify:
        summary, decisions = verify(iter_user_rows(args.prefix, args.endpoint_url, args.region), store, cipher)
        report(summary, decisions, "verify, read only")
        # Non-zero on anything that would block a clear, so the runbook's
        # "verify came back clean" step is a exit code rather than a reading.
        blocked = summary["mismatch"] + summary["unreadable"] + summary["missing"]
        return 1 if blocked else 0

    if args.clear_plaintext:
        summary, decisions = clear_plaintext(
            iter_user_rows(args.prefix, args.endpoint_url, args.region),
            store,
            cipher,
            prefix=args.prefix,
            endpoint_url=args.endpoint_url,
            region_name=args.region,
            apply=args.apply,
        )
        mode = "cleared" if args.apply else "dry run, nothing written"
        report(summary, decisions, f"clear plaintext, {mode}")
        return 1 if summary["refused"] else 0

    try:
        summary, decisions = migrate(
            iter_user_rows(args.prefix, args.endpoint_url, args.region),
            store,
            cipher,
            apply=args.apply,
            replace=args.replace,
        )
    except SeedConflict as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    report(summary, decisions, "applied" if args.apply else "dry run, nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
