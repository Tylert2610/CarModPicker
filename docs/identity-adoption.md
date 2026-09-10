# Adopting the shared identity standard

CarModPicker is moving its authentication onto the org's shared identity layer:
the `webbpulse.identity` package for the flows, and the
`platform-modules/aws//modules/identity` Terraform module for the keys and
tables underneath them. This document tracks where that has got to.

Nothing about signing in has changed yet. The legacy HS256 flow in
`backend/app/api/endpoints/auth/` is still the only thing serving `/api/auth`,
and it stays that way until the cutover row lands.

## What the standard replaces

| Today | After |
| --- | --- |
| HS256, one `SECRET_KEY` shared by nine functions | RS256, signed in KMS, private half never leaves it |
| `sub` is the **username** | `sub` is the user id |
| No `iss`, `aud`, `jti`, `kid`, roles or scopes | All of them, `typ` asserted positively on every token |
| No refresh tokens, no revocation, no denylist | Refresh rotation with reuse detection |
| One key signs seven purpose-scoped tokens | Purpose is a claim that is checked, not a convention |
| TOTP seeds in **plaintext base32** on the user item | Sealed under a KMS envelope key, per-user encryption context |
| No recovery codes | A generated set, shown once |
| No account lockout | Progressive lockout on `login-attempts` |
| Each function re-reads `users` on every authenticated request | Claims carry it; an API Gateway JWT authorizer verifies once |

## The six tables

Created by `module.identity` in `terraform/identity.tf`, physically named
`carmodpicker-<env>-<key>`. The key schemas are the package's contract, copied
from `webbpulse.identity.storage` and `webbpulse.identity.lockout`: a table whose
hash key does not match what the store writes fails at request time, not at
apply time.

| Logical name | Hash key | Range key | Index | TTL | PITR |
| --- | --- | --- | --- | --- | --- |
| `credentials` | `user_id` | `credential_type` | — | none | yes |
| `refresh-tokens` | `token_hash` | — | `family_id-generation-index` (hash `family_id`, range `generation`, projection ALL) | `expires_at` | yes |
| `identity-tokens` | `token_hash` | — | — | `expires_at` | yes |
| `login-attempts` | `identity_key` | `attempted_at` | — | `expires_at` | **no** |
| `totp-factors` | `user_id` | — | — | **none, ever** | yes |
| `recovery-codes` | `user_id` | `code_hash` | — | **none, ever** | yes |

`tables` is deliberately **not passed** to the module, so all six come from its
2.7 default map. Passing `tables` replaces that map wholesale rather than
merging with it, so restating the six here would be six chances to mistype a
contract this repository does not own — and it is what forced Portfolio to add
its two M4 entries by hand in a later PR. CarModPicker has none of these tables
in `terraform/dynamodb_tables.json`, so there is nothing to restate and nothing
to move.

**Why `totp-factors` and `recovery-codes` have no TTL.** An expiring refresh
token costs a user one extra sign in. A TOTP factor or a recovery code reclaimed
on DynamoDB's own schedule is a lockout of an account somebody still controls,
silently, with the paper codes in their hand still looking valid. Both rows are
deleted explicitly, by a user disabling TOTP or by a regeneration replacing a
set, and never on a clock.

**Why continuous backups are on regardless of environment.** Unlike
`module.dynamodb`, which takes `var.environment == "production"`, these six are
on in both. Losing a staging product table costs a reseed; losing staging's
`credentials` table locks every synthetic test account out with no way back.
`login-attempts` keeps the module's own `false`, because every row there is a
failure counter inside a lookback window and there is nothing worth restoring.

## The rest of what row 4 creates

Two KMS keys and their aliases, and three IAM role policies attached to the
**existing** `carmodpicker-<env>-lambda-identity` role that row 27's split
created.

- **The signing key**, `RSA_2048` `SIGN_VERIFY`, aliased
  `alias/carmodpicker-<env>-identity-signing`. RSA rather than EC because the
  HTTP API JWT authorizer verifies RSA-based algorithms only, which is what
  fixes RS256. The `identity-signing` policy grants the role `kms:Sign` and
  `kms:GetPublicKey`.
- **The MFA envelope key**, symmetric, aliased
  `alias/carmodpicker-<env>-identity-mfa`. TOTP seeds are sealed under a
  per-seed data key minted from it, with an encryption context of
  `{"user_id": "<id>", "purpose": "totp"}`; the key policy pins `purpose`. The
  `identity-mfa` policy grants `kms:GenerateDataKey` and `kms:Decrypt`. This is
  what closes the plaintext-seed finding in
  `docs/security/totp-seed-encryption.md`.
- **The `identity-tables` policy**, granting `local.dynamodb_domain_write_actions`
  on the six tables and their indexes. The action list is matched to what every
  other domain function already holds on its own tables rather than left at the
  module's shorter default, so "what may a domain function do to its own tables"
  has one answer in this repository rather than two.

The environment variables the module owns — `IDENTITY_ISSUER`,
`IDENTITY_AUDIENCE`, `IDENTITY_SIGNING_KEY_ARNS`, `IDENTITY_COOKIE_DOMAIN`,
`IDENTITY_RP_ID` and `IDENTITY_DATA_KEY_ARN` — are merged **last** over the
product strings in `terraform/lambda_domains.tf`, so a product override of one
of them is impossible rather than merely unlikely. An overridden
`IDENTITY_ISSUER` would be a mismatch between the gateway and the signer that
denies every request while logging no reason.

`IDENTITY_REGISTRATION_ENABLED` is `"true"`, which is one of the two places
CarModPicker diverges from Portfolio. Portfolio is a single administrator
product whose one account is seeded; CarModPicker allows public sign up through
`POST /api/users/` today, and turning registration off would remove a shipped
feature at cutover.

## The issuer

`https://api.<domain>/api/auth`, so `https://api.carmodpicker.com/api/auth` in
production and `https://api.staging.carmodpicker.com/api/auth` in staging.

That one string is three things at once: the `iss` claim the token service
signs, the `issuer` member of the discovery document, and the `issuer`
configured on the JWT authorizer. A mismatch between any two of them presents as
every request being denied with nothing in any log to say why, and a trailing
slash is the classic way to produce one, so it is derived once in
`local.identity_issuer` and read from there everywhere else.

The path is not cosmetic. API Gateway appends
`/.well-known/openid-configuration` to whatever issuer it is given, so both
documents answer under `/api/auth` rather than at the origin root, and the
`jwks_uri` the discovery document advertises is built from the same string.

The audience is `carmodpicker-<env>-api`, carrying the environment so a staging
token is not accepted by production.

## What is not here yet

### Deliberately not in row 4

- **The JWT authorizer and the two `.well-known` route keys.** `http_api_id` is
  not passed to the module, so no `aws_apigatewayv2_authorizer` and no
  `terraform_data.discovery_document_ready` are created. This is not merely the
  next line of Terraform: an HTTP API route takes exactly one authorizer, and
  the staging access gate already occupies that slot on every route in staging.
  Production's slot is free and staging's is not, which is why it is a separate
  row with its own decision. The two documents will need
  `authorization_type = "NONE"`, because API Gateway fetches discovery at
  `CreateAuthorizer` time carrying no gate cookie. A route key may not end in a
  slash.
- **New route keys for the flows.** The existing pair `ANY /api/auth` and
  `ANY /api/auth/{proxy+}` already covers every package route, because the
  package mounts everything under the issuer path.

### Waiting on the package

**M5 (passkeys) and M6 (OAuth) are in flight**, and their tables are not in the
module's 2.7 default map. CarModPicker ships both features today against its own
`webauthn_credentials` and `oauth_accounts` tables, so adopting the package as
it stands would remove working features — which is why the cutover is gated on
M5 and M6 existing rather than run now.

Four tables arrive with them, as ordinary creates, by bumping the module pin
rather than by editing `terraform/identity.tf`:

| Table | For |
| --- | --- |
| `passkeys` | Credential records; signature counters must migrate **as stored**, never as zero |
| `webauthn-challenges` | 5 minute TTL, deleted on use. Closes today's replay window, since challenges are stateless 5 minute JWTs |
| `oauth-states` | 10 minute TTL |
| `oauth-links` | Provider account links |

Renaming the two existing tables into those names is optional and not worth a
data move: the key schemas already match the standard's shapes and the RP ID is
unchanged per environment, so no passkey is re-enrolled and no link is re-made.

## The sequence

| Row | What | Depends on | State |
| --- | --- | --- | --- |
| 1 | Package M5: passkeys, stores, challenge table, ceremonies | — | in flight |
| 2 | Package M6: OAuth, `oauth-states`, linking rules | — | in flight |
| 3 | Package: per-user refresh TTL hook or settings field | owner decision | open |
| **4** | **Terraform: `module.identity` 2.7, six tables, two KMS keys, env merge** | — | **this change** |
| 5 | Backend M1 to M4: hooks, `composition/identity.py`, mount | 4 | next |
| 6 | Frontend: `AuthClient`, delete `tokenStore`, verify and reset pages, behind `VITE_AUTH_MODE` | — | |
| 7 | Credential migration script plus TOTP seed sealing script | 5 | |
| 8 | Terraform: JWT authorizer, `.well-known` at `NONE` | 4, 5 | |
| 9 | Backend M5 and M6 adoption | 1, 2, 5 | |
| 10 | Chrome extension: auth option, handoff page, publish | 6 | |
| 11 | Domains read authorizer claims; `sub` becomes the user id | 8, 9 | |
| 12 | Cutover: flip `VITE_AUTH_MODE`, run migrations, verify | 7, 9, 10, 11 | |
| 13 | Retire legacy: 24 routes, `hashed_password`, `totp_secret`, `SECRET_KEY` | 12, soak | |

Row 6 ships dark behind a flag, which makes row 12 a variable flip rather than a
deploy. Until row 13 lands, the whole sequence rolls back by setting that flag
back and redeploying.

## Migration notes carried forward

**Password hashes copy verbatim.** Both products write the hash through
`webbpulse.security.hash_password` — one bcrypt implementation, cost 12, 72 byte
truncation applied identically on hash and verify. No user resets a password and
no re-hash is needed. OAuth-only accounts have `hashed_password = None` and are
a skip rather than a failure; the migration summary must count them separately
or it looks like data loss.

**TOTP seeds are unchanged by the sweep.** The seed is sealed, not rotated, so
no authenticator is re-enrolled. The plaintext is not cleared until the sweep is
verified. A seed must never reach a log.

**Recovery codes do not exist today**, so every enrolled TOTP user should be
prompted to generate a set at first login after cutover. The codes are shown
once, in the activation response, and never again.

## Open questions for the owner

1. **`session_expire_minutes`.** A shipped user-facing setting spanning 15
   minutes to 7 days, against a package that fixes the access token at 10
   minutes with a one hour cap. Reinterpret it as a per-user refresh lifetime
   (row 3), or drop the setting and its UI at cutover?
2. **Chrome extension authentication.** The handoff gives the worker a raw
   bearer token, and the refresh half is an httpOnly cookie an extension cannot
   read. Its own refresh family (new package surface), or `host_permissions`
   plus the `cookies` permission (one manifest change, wider grant)?
3. **The authorizer and the gated staging.** Authorizer in production only with
   in-app verification in gated staging, accepting that the authorizer path is
   first exercised in production?
4. **OAuth auto-link.** The standard permits auto-linking when both emails are
   verified; CarModPicker today always demands the account password.
