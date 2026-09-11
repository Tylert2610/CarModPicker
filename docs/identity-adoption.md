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

## Row 8: the token enforced at the gateway

Row 8 is done, and it turned out to be a different shape from the one row 4
sketched above. The sketch assumed the authorizer was the whole of it and that
the existing `ANY /api/auth` pair needed nothing added. Both halves changed.

**`var.identity_jwt_mode`, with values `native`, `gate` and `off`.** Enforcement
needs two different mechanisms because an HTTP API route takes exactly one
authorizer and which one is free differs by environment. `gate` puts the check
in the staging access gate's own Lambda authorizer, which already holds every
route's slot: the signed cookie first, exactly as before, then a Bearer access
token on the marked routes. `native` creates API Gateway's own JWT authorizer,
which is the ungated shape production will use. `off`, the default, enforces
nothing. A variable validation refuses `native` in staging, because there is no
slot for it there.

**Staging is `gate`, set as a workspace variable rather than in this
repository. Production stays `off` until the identity stack is promoted.**
`CreateAuthorizer` synchronously fetches
`<issuer>/.well-known/openid-configuration` from outside AWS with none of our
credentials, so turning `native` on before the promotion fails the apply rather
than leaving anything open. That is the safe direction but it is still a failed
apply; set it in the apply that follows the promotion.

**Fifteen explicit route keys, which row 4 did not anticipate.** Enforcement
granularity is the route key and nothing finer, and row 27 cut this whole domain
onto `ANY /api/auth` and `ANY /api/auth/{proxy+}`, so the token bearing routes
and the anonymous ones share a key. Marking that key would require a token on
`login`, `register` and `refresh`, which is an API nobody can sign in to. So
`password`, `logout-all`, the five TOTP and step-up routes, the five passkey
management routes and the three OAuth link routes each get a key of their own,
pointed at the same `identity` integration, and are marked there. API Gateway
picks the most specific match, so every other method and path under `/api/auth`
still falls to the proxy key untouched. `terraform/apigateway.tf` carries the
per-route reasoning, including why `login/totp`, `logout`, the passkey login
legs and `oauth/{provider}/start` stay open.

**The two `.well-known` documents needed no key.** In production `authorizer_id`
is null, so the module's default authorization type is already `NONE` on the
proxy key that serves them, and the anonymous discovery fetch succeeds. In
staging no native authorizer is created at all, so nothing fetches discovery,
and giving them `NONE` there would punch a hole past the gate on two paths that
currently sit behind it.

**No backend change.** Nothing in `backend/app` reads authorizer claims today;
the only `requestContext` consumer is the shared rate limiter, which reads the
source IP. Row 11 is where the domains start reading claims, and that is where
the two context shapes, `authorizer.jwt.claims` in production and
`authorizer.lambda["jwt.claims"]` in staging, get their one-line reader.

## Row 11: the domains read the claims

Row 11 is done. It is the row where an identity access token starts resolving to
a CarModPicker user, and it is deliberately additive: the legacy HS256 session
resolves exactly as it did before, and nothing about the shipped sign in flow
changes. Row 12 is the cutover and row 13 is what retires the legacy path, so
until then every authenticated route accepts either credential.

### `sub` is the user id

The mapping is the one row 9's hooks already established, and it is the identity
rather than a link table. `CarModPickerIdentityHooks.load_user_by_id` takes the
`sub` claim, parses it with `UUID(...)` and does one `GetItem` against the users
table, so an identity user is the legacy user row under the id it always had.
There is no second id space and no join, and row 9 created no new user rows for
existing accounts.

That is also what makes the two token kinds impossible to confuse. The legacy
session's `sub` is a **username**; the identity token's `sub` is a **uuid7 user
id**. `get_current_user` tries the legacy decode first, and only a token that
fails it is offered to the identity resolver, so neither path can accidentally
satisfy the other even though both arrive in the same `Authorization` header.

### One reader, three shapes

`backend/app/api/dependencies/identity_claims.py` is the reader, and it answers
one question: which subject is this request for, if any. It handles the three
ways the same token reaches this application.

1. **Production, after the promotion.** API Gateway's own JWT authorizer verifies
   the token and puts the claims at `requestContext.authorizer.jwt.claims` as a
   flat string map.
2. **Staging today.** The staging access gate's Lambda authorizer does the
   verification on the flagged route keys and publishes one string key named
   `jwt.claims` under `requestContext.authorizer.lambda`, because API Gateway
   refuses a nested object there.
3. **Neither.** A route key that is not flagged carries no claims at all, which
   is not a failed authorization but a route that was never configured to carry
   one.

`webbpulse.identity.claims.read_authorizer_claims` is the package's reader and it
handles shape 1 only: it raises `NoClaimsSection` on a context whose `authorizer`
carries `lambda` rather than `jwt`, and says so in the message. So this module
calls it first and falls back to the gate's shape, and runs both through the
package's own `coerce_claims` so the two produce identical Python values rather
than merely similar ones. The gate stringifies every claim value on purpose so
that this is possible.

Row 10's `app/composition/identity_extension.py` had a local version of this
reader with a note that it might want generalising. This is that generalisation.

### The scheme had to learn about claims

`get_current_user` depends on `oauth2_scheme`, which was an
`OAuth2PasswordBearer` with `auto_error=True`. That raises 401 from inside the
dependency, before the route's resolver runs, whenever there is no
`Authorization` header. On a flagged route key the credential is in the request
context rather than in that header, so the one shape row 11 exists to serve was
the one shape refused before it could reach the code serving it.

`IdentityAwareOAuth2` is a three line subclass that declines to raise only when
`identity_subject` has already found a verified subject on the request. A request
carrying neither a header nor an authorizer still falls through to the parent
class and gets the same `Not authenticated` body it always did. The widening is
not something a caller can reach for: it needs an authorizer to have run and
verified a token, and the `x-amzn-request-context` header is written by the
Lambda Web Adapter from the invoke event, never from an inbound header.

### The verification asymmetry, which is an owner decision for row 12

On a flagged route key the token was already verified before this process was
invoked, so the reader trusts the claims in the event. On an unflagged route key
there is nothing in the event, and the only way to accept a token is to verify it
in process. `verify_bearer_subject` does that, and **it can only work on the
identity function.**

`TokenService.verify_access_token` resolves a signing key's public JWK with
`kms:GetPublicKey` against the ARNs in `IDENTITY_SIGNING_KEY_ARNS`.
`terraform/lambda_domains.tf` sets the `IDENTITY_*` block on the `identity`
function and on no other domain, and `terraform/identity.tf` attaches the signing
policy to the identity role alone. So a `catalog` or `build-lists` function
returns no subject from that path, and since every `/api/v1` route key is an `ANY`
over a whole prefix and none of them is flagged, those domains accept an identity
token only where the gateway hands them claims, which today is nowhere.

This is stated rather than fixed because fixing it is a row 12 decision with two
possible shapes, and they are not equivalent:

- **Flag the domain route keys.** Then the gateway verifies, and nothing needs a
  KMS grant. But every `/api/v1` key is an `ANY` over a prefix mixing public
  reads with authenticated writes, so flagging one turns an anonymous read into a
  401. That is a cutover, not a dual-mode step, and it needs the route keys split
  before it is safe.
- **Give every domain the signing key ARNs and a `kms:GetPublicKey` grant.** Then
  in process verification works everywhere and the route keys stay as they are.
  The cost is that nine functions get a KMS grant to serve a path that a flagged
  route key would make unnecessary, and each pays a `kms:GetPublicKey` on a cold
  start.

Neither is needed for row 11 to be correct, and no Terraform changed in this row.

**The owner decided this on 2026-09-11: the gateway verifies, not the domain
functions.** That is the first of the two shapes, and it is the one that keeps
`kms:GetPublicKey` on the one function that signs rather than spreading it across
all nine. The section below is what that decision costs and how it lands.

## Row 12 preparation: explicit route keys for the authenticated routes

The decision above cannot be applied to the route keys as they stand, for the
reason the first bullet gives: every domain prefix is served by a generated pair,
`ANY /api/<prefix>` and `ANY /api/<prefix>/{proxy+}`, and one key carries both the
anonymous reads and the authenticated writes of that prefix. Marking either would
demand a token on a public catalogue page. So the preparation is to give every
route that needs an authenticated caller a key of its own, which is the same move
row 8 made for `/api/auth` and for the same reason: enforcement granularity at an
HTTP API is the route key and nothing finer.

`local.domain_identity_jwt_route_paths` in `terraform/apigateway.tf` is that set.
Each key names one method and one concrete path, points at the same integration
the generated pair points at, and takes precedence over that pair only on the
exact method and path it names. Everything else keeps falling through to the
generated `ANY` keys exactly as before.

### The inventory

80 route keys across seven domains, derived from the application rather than
chosen: a route is in the set when its FastAPI dependency tree reaches
`get_current_user`, `get_current_admin_user` or `get_current_superuser`, all three
of which answer 401 without a caller.

| Domain | Flagged | Left anonymous on the `ANY` keys |
| --- | --- | --- |
| `admin` | 11 | 1 |
| `build-lists` | 20 | 14 |
| `build-logs` | 3 | 2 |
| `catalog` | 15 | 28 |
| `media` | 7 | 1 |
| `moderation` | 15 | 5 |
| `users` | 9 | 5 |
| `vehicles` | 0 | 11 |
| `identity` | 0 (row 8 owns `/api/auth`) | 24 |
| **Total** | **80** | **91** |

The 91 are the 171 domain routes less the 80. They divide into the catalogue and
lookup reads that are anonymous by construction, the 15 routes that resolve
through the optional resolvers, one route on a shared API key, and the 24 under
`/api/auth`.

### What is deliberately not flagged

- **The 15 optional-resolver routes.** `get_optional_current_user` returns `None`
  rather than raising, so these routes serve anonymous callers and personalise
  when a caller is signed in. `GET /api/build-lists/{build_list_id}` and
  `GET /api/users/{user_id}` are the shape. Flagging one turns a public page into
  a 401 for every signed out visitor, and a route key cannot tell the optional
  resolver from the required one: they are one word apart in a router.
- **`POST /api/parts/price-history`**, whose dependency is
  `require_api_key_or_admin`. A valid `X-API-Key` is a complete credential there
  and carries no bearer token at all, so flagging it locks out the Chrome
  extension and the ingestion jobs, which are its only callers.
- **The 12 legacy routes under `/api/auth` that do require a caller.** That prefix
  is row 8's, and these 12 are CarModPicker's own pre-package auth routes, disjoint
  from the 15 package paths row 8 marked. Row 13 retires them with the legacy
  session. Requiring an identity token on the endpoints that issue and manage the
  legacy session is the circularity row 8's comment describes.

### The two guard keys, which are an ordering hazard rather than a route

`GET /api/reports/{report_id}` and `GET /api/bug-reports/{bug_report_id}` are
flagged, and `GET /api/reports/count` and `GET /api/bug-reports/count` are
anonymous. To a gateway those are the same shape: `count` matches `{report_id}` as
readily as a uuid does. FastAPI gets this right today only because the router
registers `/count` first, and that ordering does not exist at the gateway. API
Gateway resolves it by specificity instead, and a static segment beats a path
variable at the same depth, so `local.domain_anonymous_guard_route_keys` names the
two literals explicitly to hold the more specific match. They carry no
`require_identity_jwt` and are inert in both settings of the variable.

This is section 1.4's ordering hazard reappearing, and it is worth naming because
the `catalog` and `users` prefix comments in `apigateway.tf` both predicted it:
splitting a subtree across route keys is what breaks it, and this is the first row
that splits any subtree. `test_gateway_routes.py` asserts the property over the
whole application rather than over these two cases, so a `/count` style route
added under any flagged `{id}` key in future fails a test instead of quietly
becoming a 401.

### The keys land before they are enforced

**This is the part that sequences the row, and getting it wrong signs every
staging user out.** In staging `identity_jwt_mode` is `gate`, so the moment a key
carries `require_identity_jwt` the gate Lambda demands a valid RS256 identity
access token on it. The CarModPicker frontend still sends the legacy HS256 session
token, which the gate rejects. A PR that landed the keys already flagged would
therefore break every write path in staging on apply.

So `var.domain_jwt_enforced` gates the flag and **defaults to `false`**. The 80
keys land as explicit but unflagged route keys, routing exactly as the generated
`ANY` pair already routed them, and enforcement is a later one line flip on the
workspace variable once the frontend sends identity tokens.

### The flip procedure

1. Land and apply this preparation PR with `domain_jwt_enforced = false`. Nothing
   about request handling changes.
2. Complete the frontend cutover, so the SPA sends an identity access token on
   every call. That is row 12's `VITE_AUTH_MODE` flip.
3. Verify in staging that a signed in browser session carries an RS256 token on a
   write path, and that an anonymous caller still reaches the public reads.
4. Set `domain_jwt_enforced = true` on the staging workspace and apply. No route
   resource changes; the gate authorizer Lambda gains the 80 keys in its
   environment.
5. Soak, then repeat on production once `identity_jwt_mode` there is `native`.

**Rollback at any point is setting `domain_jwt_enforced` back to `false` and
applying.** It is the same shape of change in reverse and equally cheap, because
in gate mode no route resource moves in either direction.

### Step 4 was blocked, then fixed: 95 route keys do not fit in a Lambda environment

Steps 1 to 3 were done in staging on 2026-09-11. Step 4 planned correctly, 0 to
add and 1 to change, and then **failed at apply**:

```
InvalidParameterValueException: ... environment variables exceeded the 4KB
limit. Measured size: 4545 bytes
```

Lambda caps a function's whole environment variable map at 4096 bytes. The gate
authorizer already carries ten other variables (869 bytes, including a 451 byte
public key PEM), and `IDENTITY_JWT_ROUTE_KEYS` holding all 95 keys is 3600 bytes
on its own. The overage is 449 bytes, which is about a dozen domain keys, and
dropping a key means not enforcing that route, so there is nothing to trim.

`UpdateFunctionConfiguration` is atomic, so the authorizer kept its previous
configuration and staging stayed healthy throughout. The estate rested at the end
of step 3, which is a designed, safe resting point: the frontend sends identity
tokens, the domain routes accept them, and nothing is enforced yet.

**The plan cannot catch this.** Terraform checks the shape of the environment
map, not its serialized size, which only the Lambda API measures at apply. Treat
a green plan on this resource as no evidence about size.

**The fix belonged in `terraform-aws-platform-modules`**, since the
`staging-access-gate` module is what writes the variable, and it shipped the same
day as **2.11.0**. The route key list and the signing public key PEM now travel
in the authorizer's deployment package, rendered as `identity_jwt_config.json`
and read by the handler at import time. Compressing the value would have bought
room without removing the ceiling, and enforcing by prefix instead of by key
would have broken the two anonymous guard routes that exist precisely because
prefix matching is unsafe here. The chosen fix removes the ceiling rather than
raising it, so production will not hit it when it flags its own routes.

The consumer change here was a version constraint bump, `~> 2.9` to `~> 2.11`
(PR 419), because the module's inputs did not change.

**Step 4 then applied, and enforcement has been on in staging since 2026-09-11.**
The authorizer environment measures **396 bytes with all 95 keys enforced**,
against 4545 bytes for the attempt that failed, because it no longer carries the
list at all. Verified through the staging gateway with the origin-verify header
and no bearer token: `GET /api/build-lists/user/me` is refused by the authorizer
with 403 `{"message":"Forbidden"}` before reaching application code, while the
two anonymous guard routes `GET /api/reports/count` and
`GET /api/bug-reports/count` still answer 200. `docs/identity-migration-runbook.md`
carries the full execution record.

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
| 4 | Terraform: `module.identity` 2.7, six tables, two KMS keys, env merge | — | landed |
| 5 | Backend M1 to M4: hooks, `composition/identity.py`, mount | 4 | landed |
| 6 | Frontend: `AuthClient`, delete `tokenStore`, verify and reset pages, behind `VITE_AUTH_MODE` | — | landed |
| 7 | Credential migration script plus TOTP seed sealing script | 5 | landed |
| 8 | Terraform: `identity_jwt_mode`, fifteen explicit `/api/auth` route keys, gate enforcement in staging | 4, 5 | landed |
| 9 | Backend M5 and M6 adoption | 1, 2, 5 | landed |
| 10 | Chrome extension: auth option, handoff page, publish | 6 | landed |
| 11 | Domains read authorizer claims; `sub` becomes the user id | 8, 9 | landed |
| 12a | Terraform: 80 explicit domain route keys behind `domain_jwt_enforced`, default off | 11 | landed |
| 12 | Cutover: flip `VITE_AUTH_MODE`, run migrations, verify, then `domain_jwt_enforced = true` | 7, 9, 10, 11, 12a | staging: landed. Frontend flipped and verified; enforcement on since 2026-09-11 and verified at the gateway. The 4KB environment blocker is fixed upstream in `staging-access-gate` 2.11.0 |
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
