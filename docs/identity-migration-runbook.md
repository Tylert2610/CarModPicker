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

---

# Row 9: passkeys and OAuth

Row 9 turns on the package's M5 (passkeys, WebAuthn) and M6 (OAuth) surfaces by
bumping `webbpulse` to 0.16.0 and adding the two extras those milestones need.
It is not a data migration. Nothing in this section moves a row; the two scripts
above are still the only scripts that write, and neither of them is involved.

## What actually changed

The four stores M5 and M6 need are supplied to `IdentityStores` unconditionally
in `backend/app/composition/identity.py`, alongside the ones row 5 already
passed. Supplying a store is not turning a feature on: the package mounts a
route only when the store **and** the matching setting are both present, so the
settings are the single switch and Terraform is the single place that sets them.
A second condition in Python could only ever disagree with the first, which is
why there is not one.

| Surface | Mounts when |
|---|---|
| Five passkey management routes | `IDENTITY_PASSKEYS_ENABLED` is true |
| Two passkey login routes | `IDENTITY_PASSKEYS_ENABLED` and `IDENTITY_PASSKEYS_PASSWORDLESS` both true |
| Five OAuth flow routes | at least one of `IDENTITY_GOOGLE_CLIENT_ID` / `IDENTITY_GITHUB_CLIENT_ID` is set |
| `GET /api/auth/oauth/providers` | always, including with no OAuth configured at all |

`/oauth/providers` mounting unconditionally is new in 0.16.0 and is why row 5's
route inventory went from nineteen paths to twenty. A deployment with no OAuth
serves it and it answers with an empty list, which is what lets the frontend ask
rather than be told at build time.

**The package defaults both passkey flags to true.** `IdentitySettings` ships
`passkeys_enabled = True` and `passkeys_passwordless = True`, so a function that
sets neither variable mounts all seven passkey routes. That is the opposite of
this repository's Terraform defaults, and it is the reason
`terraform/lambda_domains.tf` renders both variables explicitly in every
environment rather than only when they are on. Leaving a variable unset does not
mean off. Row 5's test fixture sets both to `false` for the same reason.

## Terraform

Six new variables in `terraform/variables.tf`, all defaulting to off or empty so
that an environment that sets nothing keeps exactly the behaviour it had:

| Variable | Type | Default | Set in staging |
|---|---|---|---|
| `passkeys_enabled` | bool | `false` | `true` |
| `passkeys_passwordless` | bool | `false` | `true` |
| `oauth_google_client_id` | string | `""` | workspace variable |
| `oauth_google_client_secret` | string, sensitive | `""` | workspace variable |
| `oauth_github_client_id` | string | `""` | workspace variable |
| `oauth_github_client_secret` | string, sensitive | `""` | workspace variable |

The four OAuth values come from HCP workspace variables, not from a `.tfvars`
file, and the two secrets are marked sensitive there as well as in the variable
block. The client ids reach the function as plain environment variables because
a client id is public by construction: it travels in the authorization URL the
browser follows. The two secrets do not. They go into the `<prefix>/app` JSON
secret that `APP_SECRETS_ARN` already points at, under
`OAUTH_GOOGLE_CLIENT_SECRET` and `OAUTH_GITHUB_CLIENT_SECRET`, matching the
SCREAMING_SNAKE casing of the `SECRET_KEY`, `SENTRY_DSN` and `EXTENSION_API_KEY`
keys already in that object. The backend reads them in
`build_oauth_client_secrets` and hands them to `build_identity_router` as an
argument.

**The secrets are an argument and not a setting on purpose.** A settings field
ends up in a `repr`, in a pydantic validation error and in anything that logs a
settings object. An argument consumed by the router constructor does not. This
is also why they are deliberately absent from `SECRET_FIELDS` in
`app/core/config.py`: adding them there would make them settings fields and undo
the whole point.

A provider whose secret is missing or empty is omitted from the mapping entirely
rather than passed as an empty string. The package treats an empty-string secret
as a present one and would advertise a provider on `/oauth/providers` that
cannot complete a token exchange, which fails at the last step of a sign-in
instead of never offering it.

## Redirect URI and WebAuthn origin

These two are different hosts and mixing them up is the failure that looks like
a working deploy until someone tries to sign in.

- **OAuth redirect URI** is on the **API**:
  `https://api.staging.carmodpicker.com/api/auth/oauth/callback`, rendered from
  `local.identity_issuer`. It has to match what is registered in the Google
  Cloud console and the GitHub OAuth app byte for byte, including the scheme and
  the absence of a trailing slash.
- **WebAuthn origin** is on the **frontend**: `https://staging.carmodpicker.com`,
  rendered from `local.frontend_url`. A browser sends the origin of the page
  that called `navigator.credentials`, which is the SPA, never the API.
- **RP id** is the registrable domain, which the identity module already owned
  before row 9 and which is shared with the refresh cookie domain.

## Registering the OAuth applications

Both applications are created by hand, once per environment, in the provider's
own console. Neither is Terraform's.

- Google: an OAuth 2.0 Client ID of type Web application. Authorized redirect
  URI is the callback above. The client id and secret go into the two workspace
  variables.
- GitHub: an OAuth App. Authorization callback URL is the same callback. Same
  two workspace variables.

Use a separate application per environment. Pointing staging at the production
client id means a staging sign-in redirects to the production host.

## Refresh lifetime

Thirty days, rolling, reset on every rotation, with a ninety day absolute cap.
No code sets this: it is `IdentitySettings`' own default in 0.16.0
(`refresh_token_ttl = timedelta(days=30)`, `refresh_absolute_ttl = 90 days`).
`test_the_refresh_window_is_thirty_days_rolling` asserts the pair so that a
future package bump that changes the default fails here rather than silently
shortening or lengthening every session.

## The legacy tables stay

`oauth_accounts` and `webauthn_credentials` are **not** migrated by row 9 and
**not** dropped. Both keep serving the legacy endpoints, and both are still
counted by `has_other_sign_in_method`. Retiring them is row 13.

What changed in row 9 is that `has_other_sign_in_method` now counts five sources
rather than three: the legacy password, the legacy `webauthn_credentials` rows,
the legacy `oauth_accounts` rows, and now the package's own `passkeys` and
`oauth-links` rows. TOTP is deliberately still not counted, because a second
factor is not a sign-in method and counting it would let someone remove their
only way in.

Counting both the legacy OAuth rows and the package OAuth links double counts a
user who exists in both, and that is the intended direction. The question this
predicate answers is "will this user still be able to sign in if I remove this
one method", and over-counting refuses a removal that would have been safe,
while under-counting locks someone out.

### What a row 13 migration would map

Written down now while the shapes are in front of us. No script implements this
yet.

| Legacy row | Package row | Field mapping |
|---|---|---|
| `oauth_accounts` | `oauth-links` | `provider` to `provider`; the provider's account id to `subject`; `user_id` to `user_id`; the two compose the `provider_subject` key the package partitions on; `linked_at` from the legacy created timestamp |
| `webauthn_credentials` | `passkeys` | `credential_id` to `credential_id`; the stored public key to `public_key`; `sign_count` to `sign_count`; `user_id` to `user_id`; the legacy label, where there is one, to `name` |

Two things make this harder than the credentials migration in row 7 and are the
reason it is a separate row rather than a step here:

1. The package partitions OAuth links on `provider_subject`, a composite of
   provider and the provider's own subject claim. A legacy row that stored only
   an email, or stored the provider's id under a different name, has to be
   resolved against the provider before it can be keyed, and a row that cannot
   be resolved cannot be migrated at all.
2. A WebAuthn public key has a stored encoding, and the legacy rows and the
   package do not necessarily agree on it. Migrating a credential whose encoding
   does not match produces a passkey that exists, appears in the user's list and
   fails every assertion, which is worse than not migrating it.

Until row 13 runs, a user who wants a package passkey or a package OAuth link
enrolls a new one. Both surfaces are additive, so nothing is lost by waiting.

## Rolling back row 9

Set `passkeys_enabled` and `passkeys_passwordless` to `false` and clear the two
client id variables, then apply. The routes stop mounting on the next apply and
the function serves exactly the surface it served before. Any rows already
written to `passkeys` or `oauth-links` are inert, not harmful: nothing reads them
while the routes are gone, and they are still there if the flags go back on.

The one thing rollback does not undo is a user who enrolled a package passkey as
their only sign-in method while passwordless was on. Turning passkeys off takes
their way in with it. This is why the flags go on in staging first and why
`has_other_sign_in_method` counts the package rows: the predicate is what stops
that user from having deleted their password in the first place.
