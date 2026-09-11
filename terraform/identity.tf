# ---------------------------------------------------------------------------
# The shared identity layer, from the org's platform module.
#
# Row 4 of the identity adoption plan, and the first row of it that touches
# infrastructure. What it creates is the estate the `webbpulse.identity`
# package needs before a single one of its routes can be mounted: two KMS
# keys, their aliases, the six tables the M1 to M4 flows read and write, and
# the three IAM role policies that let the identity Lambda use all of it.
#
# Nothing here changes how anybody signs in today. The legacy HS256 flow in
# `backend/app/api/endpoints/auth/` is untouched by this file and stays the
# only thing serving `/api/auth` until row 12 flips the cutover. This row is
# the tables and the keys sitting there unread, which is deliberate: the
# backend adoption in row 5 is a code change against infrastructure that
# already exists, rather than one apply that has to land both at once.
#
# WHAT IS DELIBERATELY NOT HERE.
#
#  - No `aws_apigatewayv2_authorizer`, because `http_api_id` is not passed.
#    That is row 8, and it is not merely the next line of Terraform: an HTTP
#    API route takes exactly one authorizer and `local.staging_gate_enabled`
#    already occupies that slot on every route in staging. Section 2b of the
#    plan records that production's slot is free and staging's is not, which
#    is the whole of why the authorizer is its own row with its own decision.
#    Leaving `http_api_id` null also leaves `terraform_data.discovery_document_ready`
#    uncreated, so this apply neither polls nor waits on a URL that no code
#    answers yet.
#
#  - No route changes. The existing pair `ANY /api/auth` and
#    `ANY /api/auth/{proxy+}` in apigateway.tf already covers every package
#    route, because the package mounts everything under the issuer path
#    `/api/auth`. Row 8 adds exactly two more, the two `.well-known`
#    documents at `authorization_type = "NONE"`.
#
#  - No M5 or M6 tables. `passkeys`, `webauthn-challenges`, `oauth-states`
#    and `oauth-links` are in flight in the package (plan section 2a) and do
#    not exist in the module's 2.7 default map. They arrive with the module
#    release that carries them, as ordinary creates, on the same argument
#    this file makes for the six below: a table with no store behind it is an
#    empty table with a backup policy.
#
#  - No `moved` blocks, and this is the one place CarModPicker is simpler
#    than Portfolio. Portfolio's adoption (PR 164) was eleven state moves,
#    because an M0 spike had hand-written the signing key and four of the
#    tables into `module.dynamodb` first. CarModPicker ran no spike and
#    `terraform/dynamodb_tables.json` holds none of these six names, so every
#    address below is a create. A destroy anywhere in this plan would mean an
#    address did not line up and must be investigated rather than applied.
# ---------------------------------------------------------------------------

locals {
  # The issuer, byte for byte, and the single definition of it.
  #
  # This exact string is three things at once: the `iss` claim the token
  # service signs, the `issuer` member of the discovery document, and, from
  # row 8, the `issuer` configured on the JWT authorizer. A mismatch between
  # any two presents as every request being denied with nothing in any log to
  # say why, and a trailing slash is the classic way to produce one. So it is
  # derived once here and read from this local everywhere else.
  #
  # The host is written out rather than read from `module.api.api_url`,
  # deliberately and for two reasons. It has to be a stable public hostname
  # that resolves and serves TLS from outside AWS, because API Gateway
  # fetches the discovery document from its own infrastructure; and it has to
  # be known at plan time, which `aws_apigatewayv2_api.api_endpoint` is not.
  # `api.${local.domain_name}` is exactly the string apigateway.tf gives the
  # custom domain, so the two cannot drift.
  #
  # Without a custom domain there is no such hostname, and this falls back to
  # the API module's origin. That configuration (a minimal staging profile)
  # cannot serve an authorizer anyway, for the plan-time reason above, and
  # row 8 does not run there. The fallback exists so the module's own
  # validation of the issuer passes rather than because the value is useful.
  #
  # The `/api/auth` path is the standard's shape and is not cosmetic: API
  # Gateway appends `/.well-known/openid-configuration` to whatever it is
  # given, so the documents answer under `/api/auth` rather than at the
  # origin root, and the `jwks_uri` the discovery document advertises is
  # built from this same string. The route keys in apigateway.tf and the
  # router's mount point both follow from this local.
  identity_issuer = "https://${local.custom_domain ? "api.${local.domain_name}" : replace(local.api_url, "https://", "")}/api/auth"

  # The audience, matched by the row 8 authorizer and carried as `aud` on
  # every token from now.
  #
  # The standard's convention is `<product>-api`, carrying the environment so
  # that a staging token is not accepted by production. Once the issuer
  # differs by hostname the audience is the only other claim that separates
  # them, and having both differ is cheap.
  identity_audience = "carmodpicker-${var.environment}-api"

  # The cookie and WebAuthn scope: the registrable domain, not the API host.
  #
  # An RP ID is hashed into every credential by the authenticator and is
  # immutable for that credential's life, so choosing it is close to
  # irreversible. The registrable domain rather than a host is the right
  # default because it lets `www.` and the API host share credentials, and
  # `local.domain_name` is already exactly that: `carmodpicker.com` in
  # production and `staging.carmodpicker.com` in staging. A passkey
  # registered against staging will not work in production, which is correct
  # behaviour rather than a problem, and matches how the legacy WebAuthn
  # routes already behave (their RP ID is the `FRONTEND_URL` hostname).
  #
  # Nothing reads either value until row 5 mounts the package. They are set
  # now because the composition root reads the whole settings object at
  # startup, and a value that first appears at the milestone that reads it is
  # a value nobody reviews when it is still cheap to change.
  identity_registrable_domain = local.domain_name

  # Read from the module rather than rebuilt here. `signing_key_arns` is
  # ordered by the module's `active_signing_key` input and never sorted: the
  # head signs and every element is published in the JWKS. Key rotation is
  # two applies against `signing_key_count` and `active_signing_key` rather
  # than an edit to a list in this repository.
  identity_signing_key_arns = module.identity.signing_key_arns

  # M6's redirect URI allow list, as the JSON array IDENTITY_OAUTH_REDIRECT_URIS
  # expects. A JSON array rather than a bare string because
  # `IdentitySettings.oauth_redirect_uris` is a list field and the class
  # deliberately refuses bare comma separated values for its lists: a stray
  # comma in a URI must be an error rather than a silently split entry.
  #
  # Derived from `local.identity_issuer` rather than written out, so the one
  # definition of the host and the path serves here too. The path the package
  # mounts the callback on is `<prefix>/oauth/callback` and the prefix is the
  # issuer's path, so this string is the URL the provider will actually be
  # given, byte for byte.
  #
  # One entry, which is the ordinary case. The package treats an empty list as
  # meaning exactly this default, and it is written out anyway because the check
  # it feeds is exact string equality rather than a prefix match, and a reviewer
  # asking "which callback URLs may a start request name" should be able to read
  # the answer rather than infer it. A prefix check on
  # `https://api.staging.carmodpicker.com` would also admit
  # `https://api.staging.carmodpicker.com.attacker.test`, which is a domain an
  # attacker can register today, and an unchecked redirect URI is a
  # code exfiltration primitive rather than an ordinary open redirect.
  #
  # This exact string must also be registered with Google and with GitHub, which
  # is the second and independent check on the same thing.
  identity_oauth_redirect_uris = jsonencode(["${local.identity_issuer}/oauth/callback"])

  # M5's WebAuthn origin allow list, on the same JSON array rule.
  #
  # The FRONTEND origin, not the API origin, and that is the whole point of the
  # field rather than an accident of which local was nearest. WebAuthn binds an
  # assertion to the origin of the page that created it, and the page is the
  # SPA. Checking it server side is what makes a passkey phishing resistant: a
  # look-alike site can copy every pixel and cannot produce an assertion
  # carrying this origin.
  #
  # `local.frontend_url` is what the frontend is actually served from in each
  # profile, custom domain or not, so a staging profile without a custom domain
  # gets its CloudFront origin here rather than a domain that does not resolve.
  # The apex only: `www.` is a redirect to it in every profile, so an assertion
  # is never created on that host, and RP ID `carmodpicker.com` already covers
  # both for the credential's own scope.
  identity_webauthn_origins = jsonencode([local.frontend_url])
}

module "identity" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/identity"
  version = "~> 2.7"

  name_prefix        = local.prefix
  issuer             = local.identity_issuer
  audience           = local.identity_audience
  registrable_domain = local.identity_registrable_domain

  # The EXISTING identity domain role, created by row 27's split and named in
  # lambda_domains.tf. The module attaches `identity-signing`,
  # `identity-tables` and `identity-mfa` to it; it creates no role of its own
  # and it does not touch the runtime policy that row 27 wrote.
  #
  # Two inputs rather than one because a KMS key policy names a principal ARN
  # while an `aws_iam_role_policy` takes a role name.
  identity_role_name = module.lambda_domain["identity"].role_id
  identity_role_arn  = module.lambda_domain["identity"].role_arn

  # `tables` IS DELIBERATELY NOT PASSED, WHICH IS THE OPPOSITE OF WHAT
  # PORTFOLIO DOES AND IS RIGHT HERE FOR A REASON WORTH WRITING DOWN.
  #
  # Passing `tables` REPLACES the module's default map wholesale rather than
  # merging with it. Portfolio passes it because its adoption had four tables
  # already in state that had to be restated to be moved, and its PR 166
  # then had to add the two M4 entries by hand for exactly that reason.
  #
  # CarModPicker has none of those six tables anywhere, so there is nothing
  # to restate and nothing to move. Taking the module's 2.7 default gets all
  # six with the key schemas, indexes and TTL attributes copied from
  # `webbpulse.identity.storage` and `webbpulse.identity.lockout`, which are
  # the package's contract rather than this module's preference: a table
  # whose hash key does not match what the store writes fails at request
  # time, not at apply time. Restating them here would be six chances to
  # mistype a contract we do not own.
  #
  # It also means the M5 and M6 tables arrive by bumping the pin rather than
  # by editing this file, once the package ships them.
  #
  # The six, and what each is for:
  #
  #   credentials      hash user_id, range credential_type. The bcrypt hash,
  #                    as credential_type = "password". No TTL.
  #   refresh-tokens   hash token_hash, GSI family_id-generation-index,
  #                    TTL expires_at. Rotation and reuse detection.
  #   identity-tokens  hash token_hash, TTL expires_at. Single-use email
  #                    verification and password reset links.
  #   login-attempts   hash identity_key, range attempted_at, TTL expires_at.
  #                    Progressive lockout, which this product has none of
  #                    today.
  #   totp-factors     hash user_id. The envelope-sealed TOTP seed, replacing
  #                    the plaintext base32 on the user item.
  #   recovery-codes   hash user_id, range code_hash. Which this product has
  #                    none of today.
  #
  # Neither M4 table takes a TTL and neither ever should. An expiring refresh
  # token costs a user one extra sign in; a TOTP factor or a recovery code
  # reclaimed on DynamoDB's own schedule is a lockout of an account somebody
  # still controls, with the paper codes in their hand still looking valid.

  # Continuous backups on by default, because these tables hold user state
  # that cannot be reconstructed: a restored TOTP seed is the authenticator
  # still in the user's pocket and a restored credential row is a password
  # they still know. The module's own default map turns it off on
  # `login-attempts`, whose every row is a failure counter inside a lookback
  # window, and that override is kept rather than overridden here.
  #
  # This is deliberately NOT the `var.environment == "production"` switch
  # that module.dynamodb takes in dynamodb.tf. Losing a staging product table
  # costs a reseed; losing staging's credentials table locks every synthetic
  # test account out with no way back, and continuous backup on six
  # low-volume tables is not a cost worth that.
  point_in_time_recovery = true

  # The same switch module.dynamodb takes, and the way this repository
  # already parameterises staging against production: one root, one
  # var.environment, two workspaces. Production refuses a DeleteTable call;
  # staging stays destroyable.
  deletion_protection = var.environment == "production"

  # Matched to what every other domain function already holds on its own
  # tables, rather than left at the module's shorter default.
  #
  # The module's default drops Scan, DescribeTable and ConditionCheckItem.
  # For an estate adopting the module over existing hand-written grants that
  # difference is a behaviour change; here it is a free choice, and the
  # choice is to keep the identity role's shape identical to the other eight
  # domain roles so that "what may a domain function do to its own tables"
  # has one answer in this repository rather than two. Narrowing to the
  # module's default is a separate decision with its own review.
  table_policy_actions = local.dynamodb_domain_write_actions

  # `name_tag` and the Name tag it renders, matching module.dynamodb's call
  # in dynamodb.tf so that all thirty two tables in this account carry the
  # same tag shape. `tags` is left empty: the provider's `default_tags` in
  # providers.tf already puts Project, Environment and ManagedBy on every
  # resource, and unlike Portfolio there is no pre-existing hand-written key
  # whose tags have to be reproduced to keep it byte identical.
  name_tag = true

  # The MFA envelope key is left at its default, which is on. TOTP seeds live
  # in plaintext base32 on the user item today, which
  # docs/security/totp-seed-encryption.md records as a known unfixed finding;
  # the key created here is what closes it, and row 7's sweep is what moves
  # the seeds under it.
  #
  # The rotation inputs are left at their defaults too: one signing key at
  # index zero, which is the single-key state a fresh estate is in.
}

# ---------------------------------------------------------------------------
# Outputs. What a reviewer checks after an apply, and what row 8 configures
# the authorizer from.
# ---------------------------------------------------------------------------

output "identity_issuer" {
  description = "The identity issuer. Byte identical to the iss claim, to the issuer member of the discovery document, and from row 8 to the JWT authorizer's configured issuer. Verify after row 5 with: curl https://<api host>/api/auth/.well-known/openid-configuration"
  value       = local.identity_issuer
}

output "identity_audience" {
  description = "The aud claim the identity function will stamp on every access token, and the audience the row 8 authorizer will require."
  value       = local.identity_audience
}

output "identity_signing_key_arns" {
  description = "The identity signing keys, active signer first. A single key today; a second entry is a rotation in progress."
  value       = local.identity_signing_key_arns
}

output "identity_signing_key_alias" {
  description = "Alias of the active identity signing key. Points at the same key as the first entry of identity_signing_key_arns."
  value       = module.identity.signing_key_alias
}

output "identity_table_names" {
  description = "Logical name to physical name for the six identity tables the module creates. The application derives the same strings from DYNAMODB_TABLE_PREFIX rather than reading this, so it is here for a reviewer checking an apply rather than for a consumer."
  value       = module.identity.table_names
}
