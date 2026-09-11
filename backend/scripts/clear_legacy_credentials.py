"""Remove the legacy `hashed_password` and `totp_secret` columns from user rows.

The far end of the identity migration, and the one step in it that cannot be
undone by reverting a deploy. `migrate_credentials_to_identity.py` copies each
bcrypt hash into the package's `credentials` table and
`migrate_totp_seeds_to_identity.py` seals each TOTP seed into `totp-factors`;
both leave the legacy columns exactly where they were. This script removes them,
and only for a user whose replacement is provably present.

Mirrors Portfolio's `backend/scripts/clear_legacy_credentials.py`, which cleared
one column. This one clears two, because CarModPicker carries a plaintext base32
TOTP seed on the user row as well as the password hash, and
`docs/security/totp-seed-encryption.md` records that plaintext as a known
finding. Clearing them in one pass means one read of the users table, one
refusal rule, and one entry in the runbook rather than two that can be run in
the wrong order.

`docs/identity-migration-runbook.md` is the runbook and gives the order of
operations for row 13.

## READ THIS BEFORE RUNNING IT

**Row 13 did not finish retiring `hashed_password`, and running this script
before the row that does will lock every password account out.**

Three routes still write that column, and none of them is an `/api/auth` route,
so row 13 did not delete them:

  - `POST /api/users/` (public registration)
  - the password change on `PUT /api/users/{user_id}`
  - the admin password set on `PUT /api/users/admin/users/{user_id}`

They write through `UserRepository.set_legacy_password_hash`, which is the only
code left in the backend that knows the column exists, and the long note on that
method says why they could not be ported in this row: the package's
`credentials` table and its IAM grant belong to `module.identity`, which takes
exactly one role, and the users Lambda holds no grant on it.

So today a password set through any of those three routes exists **only** in the
legacy column. Clearing it would take away the only copy. The follow up row that
points the SPA at the package's own `POST /api/auth/register` and
`POST /api/auth/password`, or that grants the users function the `credentials`
table, is what makes this script safe to run.

The refusal rules below catch this in practice rather than relying on somebody
having read this paragraph: a password set through those routes after the
migration ran classifies as `mismatch`, and a `mismatch` refuses the whole run.

## What it will not do

**It never clears a column it cannot account for.** Each user is classified
before anything is written, and the two columns are classified independently:

  - `cleared`             at least one legacy column was removed, and every
                          column removed had a confirmed replacement,
  - `already_clear`       neither legacy column is on the row,
  - `mismatch`            a replacement exists but holds a different secret
                          from the legacy column,
  - `missing_credential`  a legacy column is present and its replacement is
                          absent,
  - `errors`              the write itself failed.

`mismatch` and `missing_credential` are refusals rather than warnings, and the
process exits non-zero on either, because both mean removing the column would
take away a way into the account without having confirmed there is another one.

A `mismatch` on the password is usually a password changed after the migration
ran, through one of the three routes named above. The right answer is still a
human: re-run `migrate_credentials_to_identity.py --replace` so the identity
store carries the newer secret, then run this again. This script will not make
that judgement on its own.

An account with **neither** column and no credential is `already_clear` rather
than a refusal. That is an OAuth only or passkey only account, which is an
ordinary state and not a migration that failed.

## Removal, not an empty string

Both attributes are REMOVEd, through a DynamoDB `REMOVE` expression, so the
attribute stops existing rather than holding `""`.

That matters for more than tidiness. `verify_password` answers `False` for an
empty string, so an empty column and a missing one behave identically. But an
empty column reads as "deliberately blanked" rather than "never there", and a
row created through the package's registration flow has no such attribute at
all, so removal is what makes a migrated row and a natively created row
identical.

**Nothing in the backend requires either attribute to be present.** Checked
before writing this:

  - `app/db/dynamo/users.py`'s `User` model declares neither field as of row 13,
    and its `model_config` is `extra="ignore"`, so a row that still carries one
    loads with the attribute dropped rather than refused.
  - `app/api/schemas/user.py`'s `UserRead` never mentioned either, so no
    response model can fail on a missing column.
  - `UserRepository.get_legacy_password_hash` reads the attribute off the raw
    item and answers `None` when it is absent, which `verify_password` turns
    into a refusal rather than an exception.
  - `totp_enabled` stays on the model and is untouched here. It is the flag the
    profile UI renders; the seed it refers to lives sealed in `totp-factors`.

## Dry run by default

Nothing is written unless `--apply` is passed, on the same rule both migration
scripts follow: the first run against an environment is always a read.

## No secret is ever printed

Not in the summary, not in a detail line, not in an error. Every comparison is
made in memory and reported as a verdict. A script that printed the secret it
was about to delete would put the thing it is retiring into a terminal
scrollback and a CI log.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# `app.core.config` builds a `Settings` at import and refuses to construct
# without these. This script reads users, reads credentials and authenticates
# nobody, so the values are placeholders that never reach a hash or a token.
# `setdefault` so a real environment carrying them is left alone.
for _name, _placeholder in (
    ("SECRET_KEY", "migration"),
    ("EMAIL_FROM", "migration@example.com"),
):
    os.environ.setdefault(_name, _placeholder)

# Imported from the package rather than spelled out here, so this script and the
# flows that read the rows cannot disagree about a table name or a range key.
from webbpulse.identity import (  # noqa: E402
    CREDENTIALS_TABLE,
    PASSWORD_CREDENTIAL_TYPE,
    TOTP_FACTORS_TABLE,
)

from app.db.dynamo.serialization import UNIQUE_KEY_PREFIX  # noqa: E402
from app.db.dynamo.tables import USERS  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - typing only
    from webbpulse.identity import CredentialStore, TotpFactorStore

#: The two legacy attributes on a CarModPicker user row. Spelled here rather
#: than imported from the migration scripts: the three run independently, and
#: one importing another would make a rename of any of them a runtime dependency
#: between scripts that are meant to be separable.
LEGACY_HASH_FIELD = "hashed_password"
LEGACY_SEED_FIELD = "totp_secret"

#: The actions that mean the run failed. Both are a user whose column would have
#: been removed without a confirmed replacement, which is the one outcome this
#: script exists to prevent.
FAILING_ACTIONS = ("mismatch", "missing_credential", "errors")

#: Every action, in the order the summary prints them.
ACTIONS = ("cleared", "already_clear", "mismatch", "missing_credential", "errors")


class Decision(NamedTuple):
    """What one user needs, decided without writing anything.

    Carries no secret of any kind. `detail` is a sentence for a human and is
    built from verdicts rather than from values, which is what keeps the
    no secrets rule true by construction rather than by remembering it at each
    print site.

    `fields` names the attributes to REMOVE, and is empty for every action other
    than `cleared`.
    """

    user_id: str
    action: str
    detail: str
    fields: tuple[str, ...] = ()


def build_credential_store(
    prefix: str, endpoint_url: str | None = None, region_name: str | None = None
) -> "CredentialStore":
    """The package's `DynamoCredentialStore` over the `credentials` table.

    The same construction `app/composition/identity.py` uses for the running
    service and the same one `migrate_credentials_to_identity.py` uses, so the
    rows this reads are the rows that flow reads.
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


def build_totp_store(prefix: str, endpoint_url: str | None = None, region_name: str | None = None) -> "TotpFactorStore":
    """The package's `DynamoTotpFactorStore` over the `totp-factors` table.

    Only ever asked whether a row exists. Opening the sealed seed to compare it
    with the plaintext would cost one `kms:Decrypt` per user and would put the
    seed in this process's memory, and `migrate_totp_seeds_to_identity.py
    --verify` is the step that already makes that comparison. Presence is what
    this script needs and presence is all it reads.
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


def iter_user_rows(
    prefix: str, endpoint_url: str | None = None, region_name: str | None = None
) -> Iterable[dict[str, Any]]:
    """Every user row, as the raw item rather than as a `User` model.

    Raw on purpose, and more so here than in the migration scripts. `User` no
    longer declares either legacy attribute as of row 13 and its `model_config`
    is `extra="ignore"`, so a Pydantic round trip would drop exactly the two
    values this script exists to look at, and every row would classify as
    `already_clear`.

    `#unique#` sentinel rows are excluded, mirroring `DynamoRepository.scan`.
    They live in the same table as the users, carry neither legacy attribute,
    and would otherwise be counted as already clear accounts and inflate that
    total by two per user.

    Tombstoned and disabled rows are **included**. Leaving a disabled user's
    plaintext seed behind because they cannot currently sign in would defeat the
    point of the sweep, and a hard deleted row is simply not there to scan.
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


def _classify(
    user: dict[str, Any],
    credentials: "CredentialStore",
    totp_factors: "TotpFactorStore",
) -> Decision:
    """One user's verdict, reading both columns and both replacements."""
    user_id = str(user["id"])
    legacy_hash = user.get(LEGACY_HASH_FIELD)
    legacy_seed = user.get(LEGACY_SEED_FIELD)

    if not legacy_hash and not legacy_seed:
        # Neither column on the row. Either a previous run cleared it, or the
        # account was created through the package's registration flow, or it
        # signs in with Google or a passkey and never had a password. All three
        # are ordinary states, and none of them is something to write to.
        return Decision(user_id, "already_clear", "neither legacy column is on the row")

    fields: list[str] = []

    if legacy_hash:
        credential = credentials.get(user_id, PASSWORD_CREDENTIAL_TYPE)
        if credential is None:
            return Decision(
                user_id,
                "missing_credential",
                "a legacy password column is present and no password credential exists",
            )
        if credential.secret != legacy_hash:
            return Decision(
                user_id,
                "mismatch",
                "the password credential holds a different secret from the legacy column",
            )
        fields.append(LEGACY_HASH_FIELD)

    if legacy_seed:
        # Presence only. See `build_totp_store` for why the sealed seed is not
        # opened here, and `migrate_totp_seeds_to_identity.py --verify` for the
        # step that does compare them.
        if totp_factors.get(user_id) is None:
            return Decision(
                user_id,
                "missing_credential",
                "a plaintext TOTP seed is present and no sealed factor exists",
            )
        fields.append(LEGACY_SEED_FIELD)

    return Decision(
        user_id,
        "cleared",
        "every legacy column on the row has a confirmed replacement, removing it",
        tuple(fields),
    )


def plan(
    user_rows: Iterable[dict[str, Any]],
    credentials: "CredentialStore",
    totp_factors: "TotpFactorStore",
) -> list[Decision]:
    """Classify every user, touching nothing.

    Separating the decision from the write is what lets the dry run and
    `--apply` report the same thing, and it is what lets the refusal below
    happen before a single row is touched.
    """
    return [_classify(user, credentials, totp_factors) for user in user_rows]


def clear(
    user_rows: Iterable[dict[str, Any]],
    credentials: "CredentialStore",
    totp_factors: "TotpFactorStore",
    prefix: str,
    endpoint_url: str | None = None,
    region_name: str | None = None,
    apply: bool = False,
) -> tuple[dict[str, int], list[Decision]]:
    """Remove the columns for every user the plan cleared. Dry run unless `apply`.

    Refuses before writing anything when any user is a `mismatch` or a
    `missing_credential`. A run that cleared half the table and then refused
    would leave an environment in a state neither this script nor either
    migration describes, and the whole point of the classification is that it
    can be made without a write.
    """
    decisions = plan(user_rows, credentials, totp_factors)
    summary = {action: 0 for action in ACTIONS}
    for decision in decisions:
        summary[decision.action] += 1

    blocking = [d for d in decisions if d.action in ("mismatch", "missing_credential")]
    if blocking or not apply:
        return summary, decisions

    from webbpulse.dynamodb import Repository

    repository = Repository(
        USERS.suffix,
        prefix=prefix,
        endpoint_url=endpoint_url or None,
        region_name=region_name or None,
    )

    written: list[Decision] = []
    for decision in decisions:
        if decision.action != "cleared":
            written.append(decision)
            continue
        try:
            # A REMOVE expression rather than a SET of `None`. The package's
            # `Repository.update` takes the expression literally rather than
            # deriving it from a mapping the way this repository's own
            # `DynamoRepository.update` does, so the REMOVE is spelled out.
            # See the module docstring for why removal rather than `""`.
            names = {f"#c{index}": field for index, field in enumerate(decision.fields)}
            repository.update(
                {USERS.partition_key.name: decision.user_id},
                update_expression="REMOVE " + ", ".join(names),
                expression_names=names,
            )
            written.append(decision)
        except Exception as error:  # noqa: BLE001 - reported, not swallowed
            summary["cleared"] -= 1
            summary["errors"] += 1
            written.append(
                Decision(
                    decision.user_id,
                    "errors",
                    f"the write failed: {type(error).__name__}",
                )
            )
    return summary, written


def report(summary: dict[str, int], decisions: list[Decision], apply: bool) -> None:
    mode = "applied" if apply else "dry run, nothing written"
    print(f"legacy credential clearing ({mode})")
    for decision in decisions:
        columns = f" [{', '.join(decision.fields)}]" if decision.fields else ""
        print(f"  user {decision.user_id}: {decision.action}{columns} ({decision.detail})")
    print("  totals: " + ", ".join(f"{action}={summary[action]}" for action in ACTIONS))
    blocking = sum(summary[action] for action in FAILING_ACTIONS)
    if blocking:
        print(
            f"  refused: {blocking} user(s) are not safe to clear. Nothing was "
            "written. Confirm both migrations have run for this environment and "
            "that every user with a legacy column holds its replacement.",
            file=sys.stderr,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove the legacy hashed_password and totp_secret columns from "
            "every user whose identity replacement is confirmed present. Dry "
            "run unless --apply is passed."
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
    args = parser.parse_args(argv)
    if not args.prefix:
        parser.error("--prefix is required when DYNAMODB_TABLE_PREFIX is not set")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    credentials = build_credential_store(args.prefix, args.endpoint_url, args.region)
    totp_factors = build_totp_store(args.prefix, args.endpoint_url, args.region)
    summary, decisions = clear(
        iter_user_rows(args.prefix, args.endpoint_url, args.region),
        credentials,
        totp_factors,
        prefix=args.prefix,
        endpoint_url=args.endpoint_url,
        region_name=args.region,
        apply=args.apply,
    )
    report(summary, decisions, args.apply)
    if any(summary[action] for action in FAILING_ACTIONS):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
