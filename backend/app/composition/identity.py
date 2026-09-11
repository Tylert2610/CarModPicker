"""The identity function's composition: `IdentitySettings` and the package router.

Row 5 of `docs/migration/cmp-identity-plan.md`. This is what mounts
`webbpulse.identity` M1 through M4 onto the `identity` domain application, and
it is additive: the 24 legacy routes under `/api/auth` keep working, unchanged,
until row 13 retires them.

## Why this lives in `app/composition/` rather than beside the endpoint modules

It is composition, not endpoint code. This module declares no route of its own,
it reads the product's `Settings`, and the router it returns is the package's.
It is the layer above the endpoint modules, which is the layer that already
knows the process runs on Lambda with a role attached.

That separation is what made row 13 of `docs/identity-adoption.md` a deletion
rather than a rewrite. The legacy flow's own four routers lived under
`app/api/endpoints/auth/`, and row 13 removed that package outright along with
the 24 routes it declared. Nothing here moved, because nothing here was ever
part of it: `/api/auth` is now served entirely by the package's router that this
module builds.

## Where the router mounts, which is the issuer's path and not the origin

`build_identity_router` places every route it declares under
`identity_prefix(settings)`, which is the issuer's path with any trailing slash
stripped. `terraform/identity.tf` renders that issuer as
`https://<api host>/api/auth`, so every package route lands under `/api/auth`
and `app/composition/wiring.py` mounts the router **with no prefix of its own**.
A prefix there would double every path to `/api/auth/api/auth/...`.

That derivation is the package's rather than this product's on purpose. API
Gateway builds the discovery URL as
`issuer + "/.well-known/openid-configuration"` at `CreateAuthorizer` time, and
the `jwks_uri` the served document advertises is built from the issuer too, which
the gateway then follows literally. Those two URLs are not ours to choose once
the issuer is set, so a second setting for the mount path would be a second
source of truth for one fact, and the failure it invites is silent: the documents
serve 200 at a path nothing fetches while the gateway gets a 404 and every
authorized route fails closed.

**No new API Gateway route keys are needed.** The existing pair
`ANY /api/auth` and `ANY /api/auth/{proxy+}` already covers every path below,
because every one of them is under `/api/auth`. Row 8 is what adds the two
`.well-known` keys, and it adds them to carve those documents out at
`authorization_type = "NONE"` rather than because they are unreachable today.

## What mounts, and what does not

`build_identity_router` in 0.14.0 serves the three M1 documents:

    GET /.well-known/openid-configuration
    GET /.well-known/jwks.json
    GET /health

and, because this module passes `hooks` and a `stores` carrying a credential
store, the six M2 flow routes:

    POST /register
    POST /login
    POST /password
    POST /refresh
    POST /logout
    POST /logout-all

and, because it also passes an `email_sender` and a `stores` carrying an
`identity-tokens` store, the four M3 email routes:

    POST /verify-email
    POST /verify-email/confirm
    POST /reset
    POST /reset/confirm

and, because it also passes a TOTP factor store and a recovery code store on top
of that identity-tokens store, the six M4 MFA routes:

    POST /login/totp
    POST /totp/enrol
    POST /totp/activate
    POST /totp/disable
    POST /recovery-codes
    POST /step-up

all of them under `/api/auth`, so `/api/auth/login` and the rest. Each group's
mounting is conditional inside the package on exactly its own collaborators being
present, which is why supplying them is the whole of what turns M2, M3 and M4 on
here.

## What row 9 adds, which is M5 and M6

The pin moves to 0.16.0 and this module now supplies four more stores, so
`build_identity_router` also declares M6's five OAuth routes:

    GET    /oauth/{provider}/start
    GET    /oauth/callback
    POST   /oauth/{provider}/link
    GET    /oauth/links
    DELETE /oauth/{provider}/link

and M5's seven passkey routes:

    POST   /passkeys/register/options
    POST   /passkeys/register/verify
    POST   /login/passkey/options
    POST   /login/passkey/verify
    GET    /passkeys
    PATCH  /passkeys/{credential_id}
    DELETE /passkeys/{credential_id}

and, new in 0.16.0 and unconditionally in every deployment, one more:

    GET    /oauth/providers

**The four stores are supplied unconditionally, and that is deliberately not
what decides whether the routes exist.** The package's condition for the five
OAuth routes is both stores AND at least one provider carrying a client id; for
the seven passkey routes it is both stores AND `passkeys_enabled`. So the switch
for each lives in exactly one place, which is `terraform/lambda_domains.tf`.
Adding a second condition here could only ever disagree with the settings
object, and disagreeing would present as a Terraform variable flipped with
nothing changing and no error anywhere to say why.

The four tables all exist already. CMP does not pass `tables` to
`module "identity"`, so it takes the module's default map, and the 2.8.0 release
the `~> 2.7` pin resolved to carries all ten: `passkeys`,
`webauthn-challenges`, `oauth-states` and `oauth-links` were created by row 4's
apply along with the six M1 to M4 ones, and the module's IAM grant already
covers them. This row is therefore a backend change against infrastructure that
exists, with only environment variables in front of it.

A `Repository` resolves its table lazily per call, so the four stores cost one
construction each and touch DynamoDB not at all until a route that needs them is
both mounted and called.

`GET /oauth/providers` is the exception to all of the above conditionality: it
mounts in every deployment, including this test suite's, and answers with only
the providers that carry **both** a client id and a client secret. It exists so
the sign-in page can ask rather than infer the answer by probing `start` and
reading the status code, which spends the start route's rate limit budget on
page loads and cannot tell "not configured" from "briefly broken". A provider
with an id and no secret is not advertised and `start` refuses it with a 503
`OAUTH_PROVIDER_UNAVAILABLE`, rather than sending a user to consent at the
provider and meeting the failure on the way back.

**The legacy routes are untouched, and both families still serve.** CarModPicker's
own Google flow under `/api/auth/oauth/*` and its seven WebAuthn routes under
`/api/auth/webauthn/*` collide with none of the twelve paths above, so this row
is additive in exactly the way row 5 was. Row 13 retires them, and this row
migrates none of their contents: `docs/identity-migration-runbook.md` records
what a future migration of `oauth_accounts` and `webauthn_credentials` would
map.

## Why the client secrets are an argument and not a setting

`build_identity_router` takes `oauth_client_secrets` as a keyword argument
rather than reading it off `IdentitySettings`, and the package's own docstring
gives the reason: a secret that is a settings field is a secret that appears in
a `repr`, in a pydantic validation error, and in whatever log line prints the
settings object. So the two client ids travel as ordinary `IDENTITY_*`
environment variables and the two secrets travel through
`build_oauth_client_secrets` below and are on no object that anything renders.

They are also deliberately not Lambda environment variables. This estate's rule
is one JSON secret per service per environment, reached through
`APP_SECRETS_ARN`, and a client secret in a function's environment is a secret
visible in the console, in `get-function-configuration` and in every Terraform
plan that touches the function.

## What this changes about a legacy login, which is nothing

Not one legacy route changes shape. Most of the package's paths are new: `/login`,
`/register`, `/password`, `/refresh`, `/logout-all`, `/reset`, `/reset/confirm`
and the six MFA paths collide with nothing the legacy routers declare, whose own
paths are `/token`, `/token/2fa`, `/reset-password`, `/reset-password/confirm`
and the `/oauth/*`, `/2fa/*` and `/webauthn/*` families.

**Two `(method, path)` pairs exist on both sides**, and in both cases the legacy
one wins, because `composition/domains.py` loads the four legacy routers before
`app/composition/wiring.py` mounts this one and FastAPI keeps the first match:

    POST /api/auth/logout        legacy advisory no-op, vs the package's M2 logout
    POST /api/auth/verify-email  legacy verification request, vs the package's M3

That is the correct outcome for this row, and it is what makes the row additive
rather than a cutover. The legacy flow must keep working, and neither package
route is reachable from the frontend until row 6 wires `@webbpulse/auth`. It is
also harmless in both directions: the legacy `logout` is advisory and clears
nothing the package would have cleared, and the legacy `verify-email` mails the
legacy link, which is the only link today's frontend can confirm.

A third pair looks like a collision and is not.
`GET /api/auth/verify-email/confirm` is the legacy link target, which 302s to the
SPA; the package declares `POST /api/auth/verify-email/confirm`. Different
methods, so both serve, and the two coexist on one path.

Row 13 is what resolves all of this, by deleting the legacy routers rather than
by reordering an include. A mount order is not a thing a reader should have to
know to predict which handler answers, and `tests/test_identity_row5.py` asserts
the current order explicitly so that a reordering is a test failure rather than a
silent change of behaviour on two live paths.

## Where the envelope cipher comes from, which is one environment variable

A TOTP seed is the one identity secret that cannot be hashed: the server has to
reproduce the code to check it. `EnvelopeCipher` therefore seals it under a data
key that KMS mints, and the key it mints from is `IDENTITY_DATA_KEY_ARN`, which
`module.identity` sets on this function. Nothing here reads that variable by
hand: `IdentitySettings` picks it up under the `IDENTITY_` prefix as
`data_key_arn`, and `MfaService` builds the cipher from it and from the same KMS
client this module already passes for signing, on the first enrolment rather than
at construction. That is why there is no new argument below, and when the
variable is absent enrolment fails loudly naming it rather than storing a seed in
the clear.

The legacy plaintext `users.totp_secret` is untouched. Row 7's second migration
script is what seals the existing seeds into `totp-factors`.

## Why the KMS and SES clients are constructed here

The package takes a KMS client rather than building one, and `SesV2EmailSender`
takes an SES client on the same terms, which is what keeps `boto3` out of the
`identity` extra and keeps the package importable with no AWS at all. Somebody
has to construct them, and the composition root is the place.

Both are constructed lazily, inside a function, rather than at import. Nothing in
this package calls AWS at import time, and a `boto3.client` at module scope would
be a credential resolution on every import of every module that transitively
reaches this one, including in a test suite that has no credentials.

The client is built once per router and shared, because `TokenService` caches
each key's public JWK for the life of the execution environment and a client per
request would not change that but would pay a fresh session setup each time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import APIRouter

    from app.core.config import Settings


def build_identity_settings(settings: "Settings") -> Any:
    """`IdentitySettings` for this product, from the environment.

    Every field comes from an `IDENTITY_*` environment variable that
    `terraform/lambda_domains.tf` sets on the identity function, because
    `IdentitySettings` is a `BaseSettings` with `env_prefix="IDENTITY_"`. So this
    is a bare constructor call rather than a long keyword list: adding a setting
    is one line of Terraform and none of Python, which is the point of the
    prefix.

    That includes `IDENTITY_SIGNING_KEY_ARNS`, which Terraform renders as a JSON
    array. `IdentitySettings` deliberately refuses bare comma separated values
    for its list fields, so a stray comma in an ARN is an error here rather than
    a silently split entry.

    `settings` is taken as an argument rather than read from the module-level
    singleton so a test can build this against a settings object it controls. It
    is currently unused, and that is deliberate rather than an oversight: every
    value reaches `IdentitySettings` through the environment directly, and
    reading one here to pass it again would create a second path for the same
    string to travel and a second place for it to be wrong.

    Raises `pydantic.ValidationError` when the environment is incomplete or
    inconsistent, which is what a fail-fast startup wants: a plaintext issuer
    outside local, a `SameSite=None` cookie without `Secure`, or an access token
    TTL over an hour all fail here, at startup, rather than on the first request
    that would have been affected.
    """
    from webbpulse.identity import IdentitySettings

    del settings  # See the docstring: every field travels through the environment.
    return IdentitySettings()  # pyright: ignore[reportCallIssue]


def build_router(settings: "Settings") -> "APIRouter":
    """The identity router, mounted by the caller with no prefix of its own.

    `build_identity_router` places every route under the issuer's path itself.
    See the module docstring: a prefix here would double it.

    Passing `hooks` and a `stores` whose `credentials` is set is what mounts the
    six M2 flow routes. Passing an `email_sender` **and** a `stores` whose
    `identity_tokens` is set is what mounts the four M3 routes on top. M4's six
    are the same rule with a longer condition: `totp_enabled` on the settings,
    which is the package's default, plus all three of `totp_factors`,
    `recovery_codes` and `identity_tokens` on the stores.

    Row 9 adds four more stores on the same rule. Supplying `oauth_states` and
    `oauth_links` is necessary and not sufficient for M6's five routes: the
    package also needs at least one provider carrying a client id, which comes
    from `IDENTITY_GOOGLE_CLIENT_ID` or `IDENTITY_GITHUB_CLIENT_ID`. Supplying
    `passkeys` and `webauthn_challenges` is necessary and not sufficient for
    M5's seven: the package also needs `passkeys_enabled`, from
    `IDENTITY_PASSKEYS_ENABLED`. See the module docstring for why the switch
    lives there and not here.

    `GET /oauth/providers` mounts regardless, in 0.16.0 and later.
    """
    import boto3
    from webbpulse.dynamodb import Repository
    from webbpulse.identity import (
        CREDENTIALS_TABLE,
        IDENTITY_TOKENS_TABLE,
        LOGIN_ATTEMPTS_TABLE,
        OAUTH_LINKS_TABLE,
        OAUTH_STATES_TABLE,
        PASSKEYS_TABLE,
        RECOVERY_CODES_TABLE,
        REFRESH_TOKENS_TABLE,
        TOTP_FACTORS_TABLE,
        WEBAUTHN_CHALLENGES_TABLE,
        DynamoCredentialStore,
        DynamoIdentityTokenStore,
        DynamoLoginAttemptStore,
        DynamoOAuthLinkStore,
        DynamoOAuthStateStore,
        DynamoPasskeyStore,
        DynamoRecoveryCodeStore,
        DynamoRefreshTokenStore,
        DynamoTotpFactorStore,
        DynamoWebAuthnChallengeStore,
        IdentityStores,
        build_identity_router,
    )

    from app.composition.identity_hooks import CarModPickerIdentityHooks

    def repository(logical_name: str) -> Repository:
        """A package repository for one of the six identity tables.

        Prefix and endpoint are passed explicitly rather than left to the
        package's own environment lookup, so this reads the same `Settings` the
        rest of the backend does. `settings.dynamodb_table_prefix` is the same
        `<prefix>-<name>` scheme `app/db/dynamo/client.py` builds every other
        table name from, so the six identity tables resolve exactly as the
        module creates them. The endpoint matters more: `DYNAMODB_ENDPOINT_URL`
        is how a local run and the test suite point at something other than AWS,
        and the package reads no such variable.

        The table names are the package's own constants rather than strings
        spelled here. A name copied into this file is a name that can drift from
        the one the store queries, and a drifted name is a
        `ResourceNotFoundException` on the first login rather than anything a
        type checker sees.
        """
        return Repository(
            logical_name,
            prefix=settings.dynamodb_table_prefix,
            endpoint_url=settings.DYNAMODB_ENDPOINT_URL or None,
        )

    identity_settings = build_identity_settings(settings)

    stores = IdentityStores(
        credentials=DynamoCredentialStore(repository(CREDENTIALS_TABLE)),
        refresh_tokens=DynamoRefreshTokenStore(repository(REFRESH_TOKENS_TABLE)),
        identity_tokens=DynamoIdentityTokenStore(repository(IDENTITY_TOKENS_TABLE)),
        # M4. Supplying these two, with `identity_tokens` already above and
        # `totp_enabled` left at the package's default, is the whole of what
        # mounts the six MFA routes. The MFA ticket that carries a login between
        # its two legs is an `identity-tokens` row with `purpose = "mfa_ticket"`,
        # so it needs no store of its own.
        totp_factors=DynamoTotpFactorStore(repository(TOTP_FACTORS_TABLE)),
        recovery_codes=DynamoRecoveryCodeStore(repository(RECOVERY_CODES_TABLE)),
        # M6, row 9. Supplied unconditionally; the client ids are what decide
        # whether the five OAuth routes are declared. See the module docstring.
        oauth_states=DynamoOAuthStateStore(repository(OAUTH_STATES_TABLE)),
        oauth_links=DynamoOAuthLinkStore(repository(OAUTH_LINKS_TABLE)),
        # M5, row 9. Supplied unconditionally; `passkeys_enabled` is what
        # decides whether the seven passkey routes are declared.
        passkeys=DynamoPasskeyStore(repository(PASSKEYS_TABLE)),
        webauthn_challenges=DynamoWebAuthnChallengeStore(repository(WEBAUTHN_CHALLENGES_TABLE)),
    )

    return build_identity_router(
        identity_settings,
        # The two package stores are handed to the hooks as well as to the
        # package, and they are the same two objects rather than a second
        # construction. `has_other_sign_in_method` has to count a package
        # passkey and a package OAuth link from row 9 on, because a user may
        # hold only those after migration, and the hook cannot reach them any
        # other way: it is the product's class and the package's tables.
        # Passing the objects `stores` already carries means the table names are
        # spelled once, above, rather than once here and once in the hooks.
        CarModPickerIdentityHooks(
            package_passkeys=stores.passkeys,
            package_oauth_links=stores.oauth_links,
        ),
        stores,
        kms_client=boto3.client("kms"),
        service="carmodpicker-identity",
        version=IDENTITY_ROUTER_VERSION,
        # Progressive lockout. The package treats this as optional and runs the
        # flows with lockout disabled when it is absent, which is the right
        # default for a product that has not created the table. This one has, in
        # the same apply that creates the other five, so there is no window where
        # passing it would fail. CarModPicker has no account lockout at all
        # today, so this is a control the legacy flow never had rather than a
        # replacement for one.
        attempts=DynamoLoginAttemptStore(repository(LOGIN_ATTEMPTS_TABLE)),
        email_sender=build_email_sender(identity_settings),
        # M6's client secrets, as an argument rather than a settings field. See
        # `build_oauth_client_secrets` for why the package draws that line and
        # why an empty mapping is the honest thing to pass when nothing is
        # configured.
        oauth_client_secrets=build_oauth_client_secrets(settings),
    )


#: The keys of the `carmodpicker-<env>/app` secret that carry the OAuth client
#: secrets, mapped to the provider names the package knows.
#:
#: The provider names on the left are the package's:
#: `IdentitySettings.oauth_providers` is a `Literal["google", "github"]`, and
#: `oauth_client_secrets` is keyed by exactly those strings. The names on the
#: right are this product's, and they are SCREAMING_SNAKE because every other
#: key of that secret is: `SECRET_KEY`, `SENTRY_DSN` and `EXTENSION_API_KEY`
#: are the three `app/core/config.py` already reads, and `terraform/secretsmanager.tf`
#: renders the JSON with those spellings. Matching the existing casing is what
#: keeps one secret readable by one convention rather than two.
#:
#: Deliberately NOT added to `SECRET_FIELDS` in `app/core/config.py`. That tuple
#: is the set of secrets resolved lazily as `Settings` properties, and putting
#: these two there would make them settings fields, which is precisely what the
#: package's design avoids. See `build_oauth_client_secrets`.
OAUTH_SECRET_KEYS = {
    "google": "OAUTH_GOOGLE_CLIENT_SECRET",
    "github": "OAUTH_GITHUB_CLIENT_SECRET",
}


def build_oauth_client_secrets(settings: "Settings") -> dict[str, str]:
    """The M6 OAuth client secrets, from the single app secret. Possibly empty.

    ## Why every key is optional and an empty result is a success

    **Returning `{}` is a correct state, not a failure.** With no client id set,
    the package's `enabled_providers()` is empty and `build_identity_router`
    declares no OAuth flow route at all, so there is no route that could want a
    secret. Raising here for a missing key would turn a deployment that is
    correctly serving no OAuth into a cold start failure, which is a much worse
    outcome than the one it would be guarding against.

    That stays true one provider at a time. Registering Google alone puts
    `OAUTH_GOOGLE_CLIENT_SECRET` in the secret and leaves `github` out of this
    mapping, and the package mounts the routes with only Google enabled.

    A client id set with no matching secret is the one bad combination this
    cannot prevent, and it does not try to. As of 0.16.0 the package handles it
    itself and handles it well: `GET /oauth/providers` does not advertise such a
    provider, and `start` refuses it with a 503 `OAUTH_PROVIDER_UNAVAILABLE`
    rather than sending the user to consent and failing on the way back. So a
    half-configured provider is a button that does not appear, not a service
    that will not start.

    ## Why it does not go through `Settings`

    `Settings` resolves exactly the three `SECRET_FIELDS` names lazily as
    properties, and adding these two there would make them settings fields. The
    package's whole reason for taking the secrets as an argument is to keep them
    off any object that a `repr`, a pydantic validation error or a settings log
    line would render, and routing them through `Settings` would give that back.

    `fetch_app_secrets` returns the whole flat map and caches it for the life of
    the execution environment, so reading both keys off it costs one Secrets
    Manager call at composition time and none afterwards.

    That call used to be free, because the identity domain named `SECRET_KEY` in
    `requires_secrets` and had already fetched the blob to sign the legacy HS256
    session. Row 13 of `docs/identity-adoption.md` deleted that session, so this
    function is now the **only** reason the identity Lambda holds a
    `secretsmanager:GetSecretValue` grant at all. The domain descriptor's
    `requires_secrets` is empty and stays empty, because nothing here is a
    settings field and `check_signing_key` would turn a name there into a hard
    startup requirement for a value that is optional. The Terraform side
    therefore cannot read the grant off `requires_secrets` for this domain;
    `terraform/lambda_domains.tf` keeps `secrets = true` on `identity` and says
    why.

    The environment is consulted first for each key, ahead of the secret, which
    is the same precedence `Settings._resolve_secret` gives every other secret
    in this application. It is what lets a local run or a test supply one
    without a Secrets Manager stub.

    Called once at composition time rather than per request, so a rotated secret
    is picked up on the next cold start, which is the same contract every other
    value from this secret has.
    """
    import os

    from app.core.secrets import fetch_app_secrets

    arn = os.environ.get("APP_SECRETS_ARN", "") or settings.APP_SECRETS_ARN

    from_env = {provider: os.environ[key] for provider, key in OAUTH_SECRET_KEYS.items() if os.environ.get(key)}
    if len(from_env) == len(OAUTH_SECRET_KEYS) or not arn:
        # Either the environment carried both, so there is nothing left to
        # fetch, or there is no secret to fetch from. A local run and the test
        # suite are the second case, and neither declares an OAuth client id, so
        # no OAuth flow route is declared there anyway.
        return from_env

    loaded = fetch_app_secrets(arn)
    return {
        provider: from_env.get(provider) or loaded[key]
        for provider, key in OAUTH_SECRET_KEYS.items()
        if from_env.get(provider) or loaded.get(key)
    }


#: What the package router's own `/health` reports. A constant rather than a read
#: of the application version because `app/composition/wiring.py` reports the
#: same literal on the five root routes, and the two should agree; when this
#: product grows a real version module both move to it together.
IDENTITY_ROUTER_VERSION = "1.0.0"


def build_email_sender(identity_settings: Any) -> Any:
    """The `EmailSender` for the four M3 routes, or `None` when SES is absent.

    Returning `None` is a supported state rather than a failure, and it is the
    reason this is a function rather than two lines above. The package mounts the
    four email routes only when a sender is supplied, so a deployment without one
    serves the M1 documents and the M2 flows and declares no route it cannot
    honour, rather than declaring four that answer 503.

    `terraform/lambda_domains.tf` sets `IDENTITY_EMAIL_FROM` in every profile,
    because this product has a verified SES identity in every environment it
    deploys to, so in a deployed function this returns a sender. It returns
    `None` in a local run and in a test, which is exactly where the four routes
    should not exist.

    Constructing the client here rather than at import, for the reason the module
    docstring gives about the KMS client: a `boto3.client` at module scope is a
    credential resolution in every test that transitively imports this.

    `from_settings` rather than a keyword list, so the from address and the
    configuration set travel from the environment through `IdentitySettings` on
    one path. `ses_configuration_set` unset means the key is omitted from the
    `SendEmail` call rather than sent empty, which matters: a configuration set
    that does not exist is a hard failure on every send, and an empty string is a
    name that does not exist rather than an absence.
    """
    if not identity_settings.email_from:
        return None

    import boto3
    from webbpulse.identity.email import SesV2EmailSender

    return SesV2EmailSender.from_settings(identity_settings, boto3.client("sesv2"))
