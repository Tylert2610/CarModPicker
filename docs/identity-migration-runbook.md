# Identity migration runbook

The two scripts that move existing credentials and second factors into the
identity tables, and the order they run in. Row 7 of the adoption plan.

Neither script is part of a deploy. Both are run by hand, per environment,
staging first and in full, as part of the row 12 cutover.

## What each script does

| Script | Reads | Writes |
|---|---|---|
| `backend/scripts/migrate_credentials_to_identity.py` | `users.hashed_password` | `credentials` rows, one per password account |
| `backend/scripts/migrate_totp_seeds_to_identity.py` | `users.totp_secret`, `users.totp_enabled` | `totp-factors` rows, sealed under KMS |

Neither changes the `users` table, with one exception: the TOTP script's
separate `--clear-plaintext` pass, which is the last step and is never run in the
same command as the sealing pass.

## Prerequisites

- Row 4 applied, so the `credentials` and `totp-factors` tables exist and the
  `identity-data` KMS key exists.
- Row 5 merged, so the identity function reads what these scripts write.
- `DYNAMODB_TABLE_PREFIX` set to the environment's prefix, for example
  `carmodpicker-staging`. Every table name is built from it.
- `IDENTITY_DATA_KEY_ARN` set to that environment's `identity-data` key, for the
  TOTP script only. A different key produces rows that decrypt nowhere.
- Credentials with `dynamodb:Scan` on `users`, read and write on the two identity
  tables, and `kms:GenerateDataKey` plus `kms:Decrypt` on the data key.

Both scripts also take `--prefix`, `--endpoint-url`, `--region` and, for the TOTP
script, `--data-key-arn`, so nothing has to be set in the environment.

## Order of operations

Run every step as a dry run first. Neither script writes anything without
`--apply`, so step 1 of each pair is always a read.

```
# 1. Credentials, dry run. Read the summary before going further.
python backend/scripts/migrate_credentials_to_identity.py

# 2. Credentials, applied.
python backend/scripts/migrate_credentials_to_identity.py --apply

# 3. TOTP seeds, dry run.
python backend/scripts/migrate_totp_seeds_to_identity.py

# 4. TOTP seeds, sealed. The plaintext on the user row is left alone.
python backend/scripts/migrate_totp_seeds_to_identity.py --apply

# 5. Verify every sealed seed opens and matches. Writes nothing. Exits non-zero
#    if anything is missing, unreadable or mismatched.
python backend/scripts/migrate_totp_seeds_to_identity.py --verify

# ---- the cutover happens here: flip VITE_AUTH_MODE and soak ----

# 6. Only after the soak, and only after step 5 exited zero. Dry run first.
python backend/scripts/migrate_totp_seeds_to_identity.py --clear-plaintext
python backend/scripts/migrate_totp_seeds_to_identity.py --clear-plaintext --apply
```

Steps 1 to 5 are reversible. Step 6 is not, which is why it is on the far side of
the soak.

## Reading the summary counts

Both scripts print one line per user and a `totals:` line. Read the totals.

### Credentials

| Count | Means | Action |
|---|---|---|
| `write` | A bcrypt hash was copied into a new `credentials` row. | The expected case on a first run. |
| `unchanged` | A credential already holds exactly this hash. | The expected case on a rerun. Nothing was touched, `created_at` included. |
| `conflict` | A credential exists and holds a **different** secret. | Stop. See below. |
| `skip_oauth_only` | `hashed_password` is absent: a Google-only account, or one already created through the identity flow. | Normal, and usually a large number. Not data loss. |
| `skip` | A hash that is not a bcrypt modular crypt string of 60 characters. | Investigate. Copying it would write a credential that could never verify. |

`skip_oauth_only` is separate from `skip` on purpose. On a production run most
accounts may be OAuth only, and a merged total would look alarming and would hide
the handful of rows that genuinely need a human.

### TOTP seeds

| Count | Means | Action |
|---|---|---|
| `seal` | A seed was sealed into a new or corrected `totp-factors` row. | The expected case on a first run. |
| `unchanged` | A factor already holds this seed in this state. | The expected case on a rerun. |
| `conflict` | A factor exists holding a different seed, or one that will not decrypt. | Stop. See below. |
| `skip` | No `totp_secret` on the user row: the account has no second factor. | Normal, and usually most rows. |

`--verify` reports `verified`, `mismatch`, `unreadable`, `missing` and `skip`, and
exits non-zero if any of the middle three is non-zero. `--clear-plaintext`
reports `cleared`, `already_clear`, `refused` and `skip`, and refuses any row
whose sealed copy does not verify rather than destroying the last readable copy
of a seed.

### On a conflict

Both scripts refuse the **whole run before writing anything** if any conflict
exists, and exit 1. A partially applied run that then refused would be worse than
one that refuses first.

A conflict means one of two things and they want opposite answers:

- A password or an authenticator was changed through the identity flow after the
  cutover began. The identity row is the truth and must not be reverted.
- The run is pointed at the wrong environment's tables. Nothing should be
  written at all.

Work out which before doing anything. `--replace` says the `users` table is the
truth and overwrites, preserving the original `created_at`. It is not a way to
get past the message.

## Rollback

**Rollback is not clearing the plaintext.**

Until step 6 runs, every legacy value is exactly where it was. `hashed_password`
and `totp_secret` are untouched by steps 1 to 5, so the legacy sign-in and 2FA
paths keep working unchanged, and reverting the cutover is setting
`VITE_AUTH_MODE` back to `bearer` and redeploying. The identity rows can be left
in place; they are inert while the flag is off.

If the identity rows have to go, delete them from `credentials` and
`totp-factors`. There is nothing to restore, because nothing was moved.

Once step 6 has run, the sealed copy is the only copy of every TOTP seed. That is
why `--verify` gates it, why `--clear-plaintext` re-verifies each row rather than
trusting the earlier run, and why the step waits for a soak.

## What is deliberately not logged

Neither script prints a secret. The credential script prints user ids, actions
and reasons, never a bcrypt hash. The TOTP script prints the same and never a
seed, a ciphertext, a nonce or a wrapped data key: its `Decision` type carries no
seed field at all, so a decision list that reached a log or a traceback could not
hold one. `backend/tests/scripts/` asserts both on the real output.
