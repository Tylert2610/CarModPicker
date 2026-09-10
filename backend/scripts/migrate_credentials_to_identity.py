"""Copy each user's bcrypt password hash into the identity `credentials` table.

Row 7 of the identity adoption plan, and the data half of the cutover. Row 5
puts the identity Lambda, its hooks and the package flows in place; row 4 puts
the six identity tables there. Neither moves a single existing password, so
until this script runs the `credentials` table is empty and every account signs
in through the legacy `/api/auth/token` route and through nothing else. Running
it is what makes flipping `VITE_AUTH_MODE` to `identity` a variable change
rather than a lockout.

`docs/identity-migration-runbook.md` gives the order of operations, and
`migrate_totp_seeds_to_identity.py` is the other half, for second factors.

## The hash copies verbatim, and here is why that is safe

The legacy attribute and the identity credential hold **the same bytes produced
by the same function**, so this is a copy and not a rehash. No account resets a
password.

- The legacy hash is written through `app/api/dependencies/auth.py`'s
  `get_password_hash`, a one line adapter over
  `webbpulse.security.hash_password`.
- The identity registration flow writes its credential in
  `webbpulse/identity/flows.py`, calling `hash_password` from that same
  `webbpulse.security`.
- Verification matches too: the legacy path reaches `verify_password` in the
  same adapter module, and the identity login flow calls the same function.

One bcrypt implementation, one cost of 12, one 72 byte truncation applied
identically on hash and on verify. `tests/test_long_password_regression.py` and
`tests/test_token_hash_compatibility.py` already pin that from the other side.

The script still **validates** rather than assuming. `is_supported_hash`
rejects anything that is not a bcrypt modular crypt string of the right length,
and a row carrying one is reported and skipped rather than written as a
credential that could never verify.

## OAuth only accounts are a `skip`, not a failure

CarModPicker signs users in with Google as well as with a password, and a
Google-only account has `hashed_password = None` on the user row. There is
nothing to copy and nothing wrong: the account keeps working through the OAuth
path, which needs no credential row.

They are counted separately from the other skips, under `skip_oauth_only`, and
the reason is the summary. On a production run these are a large fraction of
the rows, and a single `skip` total that mixed them with genuinely unreadable
hashes would look like data loss and would hide the handful of rows that really
do need a human.

## Idempotence, and what a rerun does

Safe to run repeatedly, which matters because the runbook runs it once per
environment and a half finished run has to be resumable.

A user whose credential is already present with the same secret is left exactly
as it is, `created_at` included, and counted as `unchanged`. One whose stored
secret differs is only rewritten under `--replace`; without it the row is
reported as a conflict and the script exits non-zero, because a credential that
disagrees with the legacy attribute is either a password changed through the
identity flow after the cutover began or a run pointed at the wrong
environment's tables, and both want a human rather than an overwrite.

`created_at` is preserved on an unchanged row rather than refreshed. The value
is the moment the credential came into existence, and a rerun of a migration is
not a new credential.

## Dry run by default

Nothing is written unless `--apply` is passed. The default prints the plan and
exits, so the runbook's first step against any environment is always a read.

## Table names come from the environment, not from a constant

`--prefix` defaults to `DYNAMODB_TABLE_PREFIX`, the variable every function
already carries and the one `app/db/dynamo/client.py` builds every table name
from. The logical names are the package's own `CREDENTIALS_TABLE` and this
repository's `USERS.suffix`, so a rename in either place travels here without an
edit.

## The store is the package's, not a hand rolled PutItem

Writes go through `webbpulse.identity.DynamoCredentialStore` over a
`webbpulse.dynamodb.Repository`, the same pair the running identity function
builds. That is deliberate: the item shape, the `created_at`/`updated_at`
defaulting and the key names are the package's problem, and a script writing its
own item dict would be a second implementation of a shape the package is free to
change.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# `app.core.config` builds a `Settings` at import and refuses to construct
# without these. This migration reads users and writes credentials and
# authenticates nobody, so the values are placeholders that never reach a hash
# or a token. `setdefault` so a real environment carrying them is left alone.
for _name, _placeholder in (
    ("SECRET_KEY", "migration"),
    ("EMAIL_FROM", "migration@example.com"),
):
    os.environ.setdefault(_name, _placeholder)

# `PASSWORD_CREDENTIAL_TYPE` is the `credential_type` range key for a bcrypt
# password. Imported from the package rather than spelled `"password"` here, so
# this and the flow that reads the row cannot disagree about the key.
from webbpulse.identity import (  # noqa: E402
    CREDENTIALS_TABLE,
    PASSWORD_CREDENTIAL_TYPE,
)

from app.db.dynamo.serialization import UNIQUE_KEY_PREFIX  # noqa: E402
from app.db.dynamo.tables import USERS  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - typing only
    from webbpulse.identity import CredentialStore

#: The legacy attribute holding the bcrypt hash on a CarModPicker user row.
LEGACY_HASH_FIELD = "hashed_password"

#: The bcrypt modular crypt prefixes. `$2b$` is what `bcrypt.hashpw` produces
#: today and what every CarModPicker row carries; `$2a$` and `$2y$` are older
#: variants that the same `bcrypt.checkpw` still verifies, so a row carrying one
#: migrates rather than being refused. Anything else is not a bcrypt hash and is
#: not copied: writing it would produce a credential that can never verify.
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

#: A bcrypt modular crypt string is exactly this long, always.
BCRYPT_LENGTH = 60

#: The actions `plan` may return, and the keys of the summary. Ordered so the
#: printed totals read from "did something" to "did nothing".
ACTIONS = ("write", "unchanged", "conflict", "skip_oauth_only", "skip")


class CredentialConflict(Exception):
    """A user already holds a credential whose secret is not the legacy hash.

    Raised rather than resolved, because the two ways to get here want opposite
    answers. A password changed through the identity flow after the cutover
    began must not be reverted to the legacy hash, and a run pointed at the
    wrong environment's tables must not write anything at all. `--replace` is
    the explicit way to say the legacy attribute is the truth.
    """

    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = conflicts
        detail = ", ".join(str(user_id) for user_id in conflicts)
        super().__init__(
            f"{len(conflicts)} user(s) already hold a different credential "
            f"({detail}); rerun with --replace to overwrite from the users table"
        )


class Decision(NamedTuple):
    """What one user needs, decided without writing anything.

    Carries the `secret` and `created_at` the write would use, so `migrate`
    applies the plan it printed rather than re-reading the users table and
    deciding a second time. A second read could see a row edited between the two
    passes, which would apply something the dry run never showed.
    """

    user_id: str
    action: str
    detail: str
    secret: str = ""
    created_at: str = ""


def is_supported_hash(value: Any) -> bool:
    """Whether `value` is a bcrypt hash this migration may copy verbatim.

    A length check as well as a prefix check: a bcrypt string is 60 characters,
    and a truncated one would be copied happily by a prefix test alone and then
    fail every verification with no indication of why.
    """
    if not isinstance(value, str):
        return False
    return value.startswith(BCRYPT_PREFIXES) and len(value) == BCRYPT_LENGTH


def build_store(prefix: str, endpoint_url: str | None = None, region_name: str | None = None) -> "CredentialStore":
    """The package's `DynamoCredentialStore` over the `credentials` table.

    The same construction the running identity function uses, so the items this
    writes are the items that flow reads.
    """
    from webbpulse.dynamodb import Repository
    from webbpulse.identity import DynamoCredentialStore

    return DynamoCredentialStore(
        Repository(
            CREDENTIALS_TABLE,
            prefix=prefix,
            endpoint_url=endpoint_url or None,
            region_name=region_name or None,
        )
    )


def iter_user_rows(
    prefix: str, endpoint_url: str | None = None, region_name: str | None = None
) -> Iterable[dict[str, Any]]:
    """Every user row, as the raw item rather than as a `User` model.

    Raw on purpose. The model is free to stop declaring `hashed_password` once
    row 13 retires it, and this script has to keep working against rows written
    before that happens: it reads an attribute the model may no longer carry, and
    a Pydantic round trip would drop it. Scanning through the same
    `webbpulse.dynamodb.Repository` the credential store is built on keeps this
    to one table client rather than two.

    `#unique#` sentinel rows are excluded, mirroring `DynamoRepository.scan`.
    They live in the same table as the users, carry no `hashed_password`, and
    would otherwise be counted as OAuth only accounts and inflate that total by
    two per user.

    Tombstoned and disabled rows are **included**. Deciding who may sign in is
    `may_authenticate`'s job in the hooks, not this script's, and dropping a
    disabled user's credential here would make reactivating them a password
    reset. A hard deleted row is simply not there to scan.
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


def plan(user_rows: Iterable[dict[str, Any]], store: "CredentialStore") -> list[Decision]:
    """Decide what each user needs, touching nothing.

    Returns a list of `Decision`, whose `action` is one of `write`, `unchanged`,
    `conflict`, `skip_oauth_only` or `skip`. Separating the decision from the
    write is what lets `--apply` and the dry run share one code path and report
    the same thing.
    """
    decisions: list[Decision] = []
    for user in user_rows:
        user_id = str(user["id"])
        legacy = user.get(LEGACY_HASH_FIELD)

        if not legacy:
            # An account that signs in with Google only, or one created through
            # the identity registration flow, whose credential already exists.
            # Either way there is nothing here to copy, and this is the ordinary
            # case rather than a fault. Counted apart from the other skips: see
            # the module docstring on why the summary needs the distinction.
            decisions.append(
                Decision(
                    user_id,
                    "skip_oauth_only",
                    "no legacy hash on the user row (OAuth only or already migrated)",
                )
            )
            continue

        if not is_supported_hash(legacy):
            decisions.append(
                Decision(
                    user_id,
                    "skip",
                    "legacy hash is not a bcrypt modular crypt string",
                )
            )
            continue

        existing = store.get(user_id, PASSWORD_CREDENTIAL_TYPE)
        if existing is None:
            decisions.append(Decision(user_id, "write", "no credential yet", legacy))
        elif existing.secret == legacy:
            decisions.append(Decision(user_id, "unchanged", "credential already matches", legacy))
        else:
            decisions.append(
                Decision(
                    user_id,
                    "conflict",
                    "credential differs from legacy hash",
                    legacy,
                    existing.created_at,
                )
            )
    return decisions


def migrate(
    user_rows: Iterable[dict[str, Any]],
    store: "CredentialStore",
    *,
    apply: bool = False,
    replace: bool = False,
) -> tuple[dict[str, int], list[Decision]]:
    """Copy every migratable hash. Dry run unless `apply` is true.

    Raises `CredentialConflict` when a user holds a different credential and
    `replace` was not passed, **before writing anything at all**: a run that
    partially applied and then refused is worse than one that refuses first.
    """
    from webbpulse.identity import CredentialRecord

    decisions = plan(user_rows, store)

    conflicts = [d.user_id for d in decisions if d.action == "conflict"]
    if conflicts and not replace:
        raise CredentialConflict(conflicts)

    summary = {action: 0 for action in ACTIONS}
    for decision in decisions:
        summary[decision.action] += 1
        if decision.action in ("unchanged", "skip", "skip_oauth_only"):
            continue
        if not apply:
            continue

        store.put(
            CredentialRecord(
                user_id=decision.user_id,
                credential_type=PASSWORD_CREDENTIAL_TYPE,
                secret=decision.secret,
                # Preserve the original creation moment when replacing, so a
                # rewrite records when the credential came into existence rather
                # than when the migration last touched it. The store fills both
                # timestamps in when they are empty.
                created_at=decision.created_at,
            )
        )
    return summary, decisions


def report(summary: dict[str, int], decisions: list[Decision], apply: bool) -> None:
    """Print the plan and the totals.

    User ids only. A bcrypt hash is not a plaintext but it is still a
    credential, and a migration log that carried one would put every account's
    verifier into CloudWatch.
    """
    mode = "applied" if apply else "dry run, nothing written"
    print(f"credential migration ({mode})")
    for decision in decisions:
        print(f"  user {decision.user_id}: {decision.action} ({decision.detail})")
    print("  totals: " + ", ".join(f"{action}={summary[action]}" for action in ACTIONS))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy each user's bcrypt password hash into the identity "
            "credentials table. Dry run unless --apply is passed."
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
        help="overwrite a credential that differs from the legacy hash",
    )
    args = parser.parse_args(argv)
    if not args.prefix:
        parser.error("--prefix is required when DYNAMODB_TABLE_PREFIX is not set")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    store = build_store(args.prefix, args.endpoint_url, args.region)
    try:
        summary, decisions = migrate(
            iter_user_rows(args.prefix, args.endpoint_url, args.region),
            store,
            apply=args.apply,
            replace=args.replace,
        )
    except CredentialConflict as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    report(summary, decisions, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
