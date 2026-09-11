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

---

# Row 11: the domains read the authorizer's claims

Row 11 is not a data migration either. Nothing here moves a row, and the two
scripts at the top of this file are still the only scripts that write. What
changes is which credentials an authenticated route accepts: as of this row it
accepts both the legacy HS256 session and an identity RS256 access token, and
`sub` on the identity token is the CarModPicker user id.

There is nothing to run and nothing to schedule. This section is the verification
that the row did what it claims, and it is worth doing in staging before row 12
flips `VITE_AUTH_MODE`, because row 12 assumes this row works.

## Before you start

Row 11 needs rows 8 and 9 applied, which they are in staging. Confirm the gate is
in the mode that verifies rather than merely passing traffic through:

`var.identity_jwt_mode` is not an output, so read it from the workspace rather
than from `terraform output`. In the HCP Terraform UI it is a workspace variable
on `CarModPicker-staging`; expect `gate`. The fifteen route keys it applies to
are `local.identity_jwt_route_keys` in `terraform/apigateway.tf`.

`off` means no route key verifies anything and every check below will read as a
row 11 failure when it is really a row 8 configuration. Check this first.

## 1. The legacy session still works

This is the check that matters most, because row 11 is additive and a regression
here is worse than the feature not landing. Nothing about this should have
changed, which is the point.

```bash
API=https://api.staging.carmodpicker.com

# A legacy sign in, exactly as the shipped frontend does it.
LEGACY=$(curl -s -X POST "$API/api/auth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$USERNAME&password=$PASSWORD" | jq -r .access_token)

curl -s -o /dev/null -w '%{http_code}\n' "$API/api/users/me" \
  -H "Authorization: Bearer $LEGACY"     # expect: 200
```

A 401 here means the dual mode change swallowed the legacy path and the row
should be reverted rather than debugged in place. The legacy flow is what every
signed in user is on until row 12.

## 2. An identity access token resolves to the same user

```bash
# An identity sign in. Same user, different credential. Note that the package's
# login takes `email` where the legacy `/api/auth/token` takes `username`.
IDENTITY=$(curl -s -X POST "$API/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r .access_token)

curl -s "$API/api/users/me" -H "Authorization: Bearer $IDENTITY" | jq '{id, username}'
```

Compare the `id` against the one step 1 returned. They must be the same string.
If they differ, the mapping assumption in this row is wrong and row 12 must not
proceed: `sub` is supposed to be the user id itself.

Decode the token to see the mapping directly, without verifying it, since all you
want is the payload:

```bash
echo "$IDENTITY" | cut -d. -f2 | base64 -d 2>/dev/null | jq '{sub, iss, aud}'
```

`sub` is the uuid7 user id, `iss` is `https://api.staging.carmodpicker.com/api/auth`
and `aud` is `carmodpicker-staging-api`.

## 3. The claims actually come from the gateway on a flagged route

Steps 1 and 2 both send an `Authorization` header, so they do not distinguish
between the application reading the gateway's claims and the application
verifying the token itself. On the identity function both work, which is exactly
why the two need separating.

The cheap way to tell them apart is to look at what the authorizer put in the
context. On a flagged `/api/auth` route key in staging the gate's Lambda
authorizer publishes `jwt.claims`, and the request reaching the function carries
it in `x-amzn-request-context`:

```bash
aws logs tail /aws/lambda/carmodpicker-staging-identity --since 5m --follow
```

Then make one request from step 2 and watch. A request whose token failed
verification never reaches the function at all: the gate returns 401 at the
gateway, so no log line appears. That absence is the check. A 401 with a log line
is the application refusing the claims, which is a different failure and points
at the account checks rather than at the token.

## 4. A refused token is refused the same way as no token

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/users/me"                      # expect: 401
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/users/me" \
  -H "Authorization: Bearer not.a.token"                                          # expect: 401
```

Both are 401 and neither body says which of the several possible reasons applied.
An expired token, a token for another audience, a `sub` naming a deleted user and
no token at all are one answer to a caller by design.

## What this row deliberately does not verify

**That a `/api/v1` route accepts an identity token.** It does not, and that is
expected. No `/api/v1` route key is flagged, so the gateway hands those functions
no claims, and in process verification needs `IDENTITY_SIGNING_KEY_ARNS` plus a
`kms:GetPublicKey` grant that only the identity function has. The adoption doc's
row 11 section sets out the two ways row 12 can close that, and the choice
between them is an owner decision rather than a defect in this row.

## Rolling back row 11

Revert the pull request. There is no state to unwind: no table changed, no
variable changed, no Terraform changed. Every user signed in through the legacy
session stays signed in, because that path is untouched by this row and by its
revert. A user signed in through an identity token would need to sign in again,
which is only possible for someone testing the new flow deliberately, since row
12 has not flipped the frontend yet.

# Row 12 preparation: the domain route keys

The owner decided on 2026-09-11 that the gateway verifies the identity access
token on the domain routes, not the domain functions. This row is the Terraform
that makes that possible, and it deliberately does not switch it on.

## What lands

`local.domain_identity_jwt_route_paths` in `terraform/apigateway.tf` names 80
route keys, one per `/api` route outside `/api/auth` that needs an authenticated
caller, plus `local.domain_anonymous_guard_route_keys` with two literal `count`
keys that keep an anonymous route from being captured by a flagged `{id}` key on
the same method. Both are merged into `local.lambda_domain_route_keys` alongside
the generated `ANY` pairs and row 8's fifteen identity keys.

`var.domain_jwt_enforced` decides whether the 80 carry `require_identity_jwt`. It
defaults to `false` and this row applies with it false.

## Why it must not be enforced on the same apply

In staging `identity_jwt_mode` is `gate`. A flagged route key puts the key in
`module.api.identity_jwt_route_keys`, which `terraform/staging_access_gate.tf`
passes to the gate authorizer, and from that moment the gate requires a valid
RS256 identity access token on those routes. **The CarModPicker frontend still
sends the legacy HS256 session token, which the gate rejects with a 401.** So
enforcing on this apply would break every authenticated write path in staging for
every user, including the owner.

The keys are inert until the frontend cutover. Do not set
`domain_jwt_enforced = true` before that is ready.

## The expected plan, with the variable false

Run against the staging workspace. The change is 82 new routes and nothing else:

```
Plan: 82 to add, 0 to change, 0 to destroy.
```

All 82 are `module.api.aws_apigatewayv2_route.this["<key>"]`, each with
`authorization_type = "CUSTOM"` and the staging gate's `authorizer_id`, which is
what every existing route on this API already carries. 80 are the authenticated
routes and 2 are the guard keys.

**Nothing else may appear in that plan.** In particular no existing route is
changed or replaced, because the new keys are additional map entries rather than
edits to the generated `ANY` pairs, and the gate authorizer Lambda is untouched
because `module.api.identity_jwt_route_keys` is still empty with the variable
false. A plan showing a change to `module.staging_access_gate` means the variable
is true; stop and check the workspace variable before applying.

## The expected plan, with the variable true

This is the later enforcement apply, after the frontend cutover:

```
Plan: 0 to add, 1 to change, 0 to destroy.
```

The one change is the gate's authorizer Lambda, whose environment gains the 80
route keys. **No route resource moves, changes or is replaced.** That is a
property of the platform module in gate mode rather than a coincidence: it only
moves a marked route into its own JWT resource when `module.api.identity_jwt` is
non-null, and in gate mode it is null, so a marked route stays at the same
resource address with the same `authorization_type` and the same authorizer as an
unmarked one. Only the module's `identity_jwt_route_keys` output changes, and the
gate consumes it.

A plan at this step that proposes to destroy and recreate routes means the
workspace is in `native` mode rather than `gate`, which is production's shape and
not staging's. Do not apply it in staging.

## Rollback

Set `domain_jwt_enforced` back to `false` and apply. The gate authorizer's
environment loses the 80 keys, every route keeps its address, and the keys go back
to being inert explicit routes. There is no state to unwind and no user is signed
out, because the legacy session path is untouched throughout.

To roll back the keys themselves as well, revert the pull request and apply: the
82 routes are destroyed and every request falls back to the generated `ANY` pair
that served it before, which is where it was routed all along.

## What keeps the two in step

`backend/tests/entrypoints/test_gateway_routes.py` rebuilds the application,
walks every route's dependency tree, and asserts the set of routes that refuse an
anonymous caller is exactly the set `apigateway.tf` names. It fails in both
directions: a route added behind `get_current_user` with no key, and a key naming
a route the application serves anonymously. It also asserts each key names the
domain that serves its prefix, that no key ends in a slash, and that no anonymous
route is capturable by a flagged path parameter key. Run it after any route
change:

```
cd backend
TESTING=true SECRET_KEY=test-secret-key python -m pytest tests/entrypoints/test_gateway_routes.py
```

## Creating a staging test user

The behavioural checks in this runbook need an account whose password is known.
Staging holds no such account: every user in it is synthetic, copied from
production content with credentials deliberately left behind, so no staging row
has a `hashed_password` at all. Create one, per check, with this procedure.

Staging SES is in the sandbox, so the verification mail never delivers. That is
the only reason this procedure ends by setting a flag by hand rather than
clicking a link. Do not change the SES account configuration to work around it.

**1. Generate a password into the scratchpad and nowhere else.** It must not
reach a commit, a pull request, a report, or the terminal scrollback.

```bash
umask 077
printf 'TEST_PASSWORD=%s\n' "$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" \
  > "$SCRATCH/staging_testuser.env"
```

**2. Register through the identity function.** The API sits behind the staging
access gate, which refuses an unauthenticated HTTP request with a 403 before the
application sees it, so invoke the function directly rather than going through
the gateway. Name the user so nobody mistakes it for a real one, and give it an
address under `staging.invalid`, which is a reserved TLD that can never receive
mail.

```bash
. "$SCRATCH/staging_testuser.env"
jq -n --arg pw "$TEST_PASSWORD" '{
  version: "2.0", routeKey: "POST /api/auth/register",
  rawPath: "/api/auth/register", requestContext: {http: {method: "POST", path: "/api/auth/register"}},
  headers: {"content-type": "application/json"},
  body: ({username: "row12-cutover-check",
          email: "row12-cutover-check@staging.invalid",
          password: $pw} | tostring),
  isBase64Encoded: false
}' > "$SCRATCH/register.json"

aws lambda invoke --function-name carmodpicker-staging-identity \
  --payload "fileb://$SCRATCH/register.json" "$SCRATCH/register-out.json" >/dev/null
jq -r '.statusCode' "$SCRATCH/register-out.json"
```

A 403 carrying `EMAIL_VERIFICATION_REQUIRED` is the success case here, not a
failure. The user row and its `credentials` row are both written before that
refusal; what the refusal denies is the sign in, which is exactly what step 3
unblocks.

**3. Mark the address verified.** There is no admin or test hook for this in
either the identity package or the application, so the flag is set directly on
the one row. Scope the write with a condition on the username so a mistyped id
cannot touch a different user.

```bash
USER_ID=$(aws dynamodb query --table-name carmodpicker-staging-users \
  --index-name username-index \
  --key-condition-expression 'username = :u' \
  --expression-attribute-values '{":u":{"S":"row12-cutover-check"}}' \
  --query 'Items[0].id.S' --output text)

aws dynamodb update-item --table-name carmodpicker-staging-users \
  --key "{\"id\":{\"S\":\"$USER_ID\"}}" \
  --update-expression 'SET email_verified = :t' \
  --condition-expression 'attribute_exists(id) AND username = :u' \
  --expression-attribute-values '{":t":{"BOOL":true},":u":{"S":"row12-cutover-check"}}'
```

`may_authenticate` in `backend/app/composition/identity_hooks.py` gates on
`disabled`, `is_service_account` and `email_verified`, so with the flag set the
account signs in and nothing else about it is special.

**4. Sign in and keep the token out of the report.** Invoke the identity function
with `POST /api/auth/login` the same way, and assert on the shape rather than the
value:

```bash
jq -r 'if (.body | fromjson | has("access_token")) then "has_access: true" else "has_access: false" end' \
  "$SCRATCH/login-out.json"
```

**A `@staging.invalid` address makes some routes return 500, and it is not an
auth failure.** `UserRead.email` is an `EmailStr`, and Pydantic refuses a
reserved TLD on the way *out*, so any route that serialises a user object
(`GET /api/users/me` among them) raises a `ValidationError` in
`app/api/services/user_service.py` after authentication has already succeeded.
Every one of the 58 pre-existing synthetic users has the same problem. Verify
against a flagged route that returns no user object, such as
`GET /api/build-lists/user/me`, and read a 500 here as a serialisation bug rather
than evidence that the token was refused.

Leave the account in place between rows. It is cheap, it is obviously synthetic,
and recreating it is the only other way to run these checks.

## Executed 2026-09-11, staging

What actually ran for row 12 in the staging account (748861776298), workspace
`CarModPicker-staging` / `ws-dNLoiEHVxr2o81XM`, against `origin/staging` at
`aa91960d`.

### Preflight

Rows 7, 9, 10, 11 and 12a were confirmed on `origin/staging` and deployed. The
users table was snapshotted first, with a projection that names the attributes to
read rather than scanning whole items, so no hash and no seed entered the output:

```bash
aws dynamodb scan --table-name carmodpicker-staging-users \
  --projection-expression 'id,#u,email,email_verified,is_active,is_admin,is_superuser,is_service_account,totp_enabled' \
  --expression-attribute-names '{"#u":"username"}'
```

174 items: 58 user rows plus 116 `#unique#` sentinels. One admin and superuser
(`Tylert2610`), one service account (`crawler`), every address under
`staging.invalid`, `totp_enabled` on none.

### Credential and TOTP migration: nothing to migrate

Both scripts were dry run and both reported zero work, because **staging holds no
credentials at all.** Counted without reading any value:

| Attribute or table | Count |
| --- | --- |
| users with `hashed_password` | 0 |
| users with `totp_secret` | 0 |
| `oauth_accounts` rows | 0 |
| `webauthn_credentials` rows | 0 |
| every identity table | empty |

```
migrate_credentials_to_identity.py --prefix carmodpicker-staging
  write=0 unchanged=0 conflict=0 skip_oauth_only=58 skip=0

migrate_totp_seeds_to_identity.py --prefix carmodpicker-staging --verify
  seal=0 unchanged=0 conflict=0 skip=58
```

Zero unsupported hashes and zero conflicts, which is the gate the runbook asks
for. **`--apply` was deliberately not run on either script.** With `write=0` and
`seal=0` an apply is a guaranteed no-op, and not running it keeps the record
honest about what touched the account.

This is expected rather than surprising: staging was seeded from production
*content* on 2026-09-06 and real credentials were never copied. It does mean the
migration scripts themselves are still unexercised against real data, and
production is where they first do work.

`migrate_totp_seeds_to_identity.py` builds its KMS client without threading
`--region` through, so it raises `NoRegionError` unless `AWS_DEFAULT_REGION` is
exported alongside `AWS_REGION`. Export both.

### Frontend flip

```bash
gh variable set AUTH_MODE --env staging --body identity --repo WebbPulse/CarModPicker
gh workflow run "Frontend Deploy" --ref staging
```

Run `34569931625`, success. Confirmed on the deployed artefact rather than on the
variable: the bundles in `s3://carmodpicker-staging-frontend/assets/` carry
`VITE_AUTH_MODE:"identity"` as a build time literal, which is what Vite leaves
behind when it substitutes `import.meta.env`.

### Behavioural verification, before enforcement

Against the synthetic account from "Creating a staging test user"
(`row12-cutover-check`, id `01a08f23-2ffa-79ea-9144-1806e48bba7f`):

1. `POST /api/auth/login` on `carmodpicker-staging-identity`: 200, `has_access:
   true`. Claims `sub=01a08f23-2ffa-79ea-9144-1806e48bba7f`,
   `iss=https://api.staging.carmodpicker.com/api/auth`,
   `aud=carmodpicker-staging-api`, `typ=access`, `roles=[]`. The `sub` equals the
   DynamoDB row id, which is row 11's contract.
2. `GET /api/build-lists/user/me` on `carmodpicker-staging-build-lists` with gate
   shaped claims: **200**.
3. The same call with no claims and no header: **401**, `UNAUTHORIZED`. The
   negative control matters, because a route that answered 200 either way would
   prove nothing.

### Enforcement apply

`bootstrap_image_tag` was refreshed from the stale `sha-2ad19cb0…` to
`sha-aa91960d1876ba6a17d5d7873a9de0d5c789e9c9` first, and all nine
`carmodpicker-staging/<domain>` ECR repositories were confirmed to carry that tag
before queueing. A stale bootstrap tag plans green and fails at apply, because
keep-last-10 lifecycle rules remove old tags.

`domain_jwt_enforced` did not exist on the workspace (it was running on the
`false` default) and was created as `true`.

Run `run-wsHvCgFrQexSrc14` planned exactly as this runbook predicts:

```
Plan: 0 to add, 1 to change, 0 to destroy.
  update  module.staging_access_gate[0].aws_lambda_function.authorizer
```

`IDENTITY_JWT_ROUTE_KEYS` was to go from **15 keys to 95** (15 identity plus 80
domain). No route resource moved, which is the gate mode property this runbook
predicts.

**The apply then failed, and enforcement is not on.** See the next section.

### The apply failed: the 95 keys do not fit in a Lambda environment

```
InvalidParameterValueException: Lambda was unable to configure your environment
variables because the environment variables you have provided exceeded the 4KB
limit. Measured size: 4545 bytes
```

Lambda caps the whole environment variable map at 4KB, and 95 comma joined route
keys do not fit next to the gate's other ten variables:

| Part | Bytes |
| --- | --- |
| the other ten variables, keys and values | 869 |
| `IDENTITY_JWT_ROUTE_KEYS` with 15 identity keys | 498 |
| `IDENTITY_JWT_ROUTE_KEYS` with all 95 keys | 3600 |
| total as measured by Lambda at 95 keys | **4545** |
| the limit | 4096 |

The overage is 449 bytes. The 80 domain keys average 37.8 characters, so roughly
a dozen of them would have to be dropped to squeeze under, which defeats the
point of the row: enforcement granularity is the route key, and a key that is not
in the list is a route that is not enforced.

**Nothing is half applied.** `UpdateFunctionConfiguration` is atomic, so the
function kept its previous configuration: 15 keys, `LastUpdateStatus:
Successful`. Staging was never in a broken state and no user was signed out. The
frontend is in identity mode and the domain routes are still unenforced, which is
precisely the state step 2 of the flip procedure describes, so it is a safe place
to stop.

**Why the plan could not catch this.** Terraform validates the environment map
shape, not its serialized size, and the size is only known to the Lambda API at
apply. A green plan is not evidence the environment fits. Any future change that
grows this map has the same failure mode.

**The fix is not in this repository.** `IDENTITY_JWT_ROUTE_KEYS` is written by
the `staging-access-gate` module in `terraform-aws-platform-modules`, so the
route key list has to stop being an environment variable there before row 12 can
finish. Options, in rough order of preference and all needing an owner decision:

1. **Move the list out of the environment.** Ship it in the authorizer's
   deployment package, or read it from SSM Parameter Store or S3 at cold start.
   This removes the ceiling rather than raising it, and it is the only option
   that still scales when production flags its own routes.
2. **Compress the representation.** The keys share long prefixes, so a per method
   prefix grouping or a compact encoding would fit today. It buys room rather
   than removing the limit, and it makes the value unreadable in the console.
3. **Enforce by prefix rather than by key.** Far smaller, but it changes the
   enforcement granularity that rows 11 and 12a were built around, and the two
   anonymous guard keys (`GET /api/reports/count`,
   `GET /api/bug-reports/count`) exist precisely because prefix matching is not
   safe here.

Option 3 is cheapest and is the one to resist: it would quietly enforce the two
guard routes and break anonymous reads.

Until that lands, leave `domain_jwt_enforced` set to `true` on the workspace only
if you intend to retry the apply immediately; otherwise set it back to `false` so
the next unrelated apply on this workspace does not fail on the same error. It
was set back to `false` on 2026-09-11.

### Rollback

Exact, in the order to undo it:

1. **Enforcement.** Set `domain_jwt_enforced` to `false` on
   `ws-dNLoiEHVxr2o81XM` and apply. The authorizer environment drops back to 15
   keys, every route keeps its address, nobody is signed out. This alone reverses
   the user visible effect.
2. **Frontend.** `gh variable set AUTH_MODE --env staging --body bearer --repo
   WebbPulse/CarModPicker`, then rerun the Frontend Deploy on `staging`. An empty
   value works too, since `resolveAuthMode` treats empty as unset and falls
   through to `bearer`.
3. **Credentials.** Nothing to unwind. No migration wrote anything, and the
   legacy `hashed_password` and `totp_secret` attributes are untouched until
   row 13 retires them. Rollback is not clearing the plaintext.

### Two things worth knowing before production

- **`scripts/verify_route_cut.sh` needed a fix.** Its `expected_key()` assumed
  every path under a domain prefix resolves to that prefix's `{proxy+}` key,
  which stopped being true when row 12a added explicit `GET /api/<domain>/{id}`
  keys: the gateway prefers the more specific key at the same depth. The
  assertion was stale, not the deployment, and the 401 the probe got back was
  proof the request had reached the authenticated handler. Fixed by reading the
  explicit keys out of `terraform/apigateway.tf` rather than listing them again
  in the script.
- **`deploy-backend.yml` is path filtered to `backend/**`.** A fix under
  `scripts/` merges without triggering a deploy. Dispatch one by hand with
  `gh workflow run "Deploy Backend" --ref staging`.
