"""Row 9: the package's M5 passkeys and M6 OAuth, and the switches that gate them.

Row 5 mounted M1 to M4 and `tests/test_identity_row5.py` pins what an identity
function serves with none of this row's switches on: twenty routes, including
`GET /api/auth/oauth/providers`, which 0.16.0 mounts unconditionally. This file
owns the twelve that the switches control, and the switches themselves.

## What is actually being tested, which is a configuration contract

Almost nothing here is a test of the package. The package's own suite covers
whether a passkey verifies and whether a token exchange works, and repeating
that here would be asserting that somebody else's code does what their tests
already say it does.

What this file tests is the seam: that the six environment variables
`terraform/lambda_domains.tf` renders are the six the package reads, that each
one turns on exactly what it claims to, and that the two client secrets travel
from the `carmodpicker-<env>/app` secret into the argument the package takes
rather than into a settings field. Every one of those is a thing that can be
broken by a Terraform edit with no Python change at all, which is precisely the
class of failure a backend test suite normally cannot see.

So the environment is written as environment variables rather than passed as
arguments, exactly as row 5's file does and for the same reason:
`IdentitySettings` is a `BaseSettings` with `env_prefix="IDENTITY_"` and
`app/composition/identity.py` constructs it with no arguments at all. A test
that built the settings object directly would not notice a Terraform variable
renamed, or never set.

## Why the fixtures are imported from row 5's file rather than rewritten

`identity_env`, `identity_app`, `private_key` and `FakeKms` are the deployed
identity function's environment and a local RSA signer, and there is one correct
version of each. Copying them would mean two inventories of `IDENTITY_*` names
drifting apart, and the drift would show up as this file passing while the
deployed function is misconfigured. The fixtures below layer on top by setting
more variables before `identity_app` builds, which works because `identity_env`
is an ordinary fixture dependency and `monkeypatch.setenv` from a fixture that
depends on it runs after it.

## The two flags default ON in the package and OFF here

`IdentitySettings.passkeys_enabled` and `passkeys_passwordless` both default to
`True`, because the standard's baseline is mandatory and the flags exist to
stage a rollout rather than to opt out. `terraform/variables.tf` defaults both to
`false` and the staging workspace sets both `true`, which is a deliberate
departure and the one thing in this row that is a judgement rather than a
mechanical adoption: a default that turns a sign-in method on in whichever
environment applies next fails in the wrong direction. Production receives the
same variables at promotion.

`terraform/lambda_domains.tf` renders both on every identity function in every
environment, so an unset flag is not a state a deployed function is ever in, and
`test_the_passkey_routes_are_absent_with_the_flag_off` is what says the off
state is really off rather than the package's default leaking through.

## What is deliberately not here

**No test of the legacy WebAuthn or legacy Google routes.** They are untouched by
this row, they still serve, and `tests/entrypoints/test_route_split.py` already
pins them. Row 13 retires them.

**No migration of their contents.** `docs/identity-migration-runbook.md` records
what a future migration of `oauth_accounts` and `webauthn_credentials` would map;
this row writes no such script and no test asserts one exists.
"""

from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

import pytest

from app.composition.identity_hooks import CarModPickerIdentityHooks
from app.db.dynamo.users import User

from .entrypoints.test_route_split import _pairs

# Row 5's fixtures and constants, imported rather than rewritten. See the module
# docstring for why this file leans on row 5 instead of standing up its own
# issuer, key and environment.
#
# The two fixtures are imported under private aliases and re-exported below.
# Importing them under their public names would make every test signature that
# takes one look, to a linter, like a redefinition of the imported name: pytest
# resolves fixtures by parameter name, but ruff only sees a module-level name
# being shadowed twelve times over. The alias plus an explicit re-export says
# the same thing to pytest and nothing confusing to the linter.
from .test_identity_row5 import ISSUER, FakeKms
from .test_identity_row5 import identity_env as _identity_env
from .test_identity_row5 import private_key as _private_key

#: Re-exported so pytest finds them by name in this module. The assignment is
#: the whole mechanism: a fixture is discovered by the name it is bound to in
#: the collected module, not by the name it was defined under.
identity_env = _identity_env
private_key = _private_key

#: The five M6 flow routes, spelled out rather than derived from the package. A
#: list computed from the thing it checks cannot notice that the thing moved,
#: and these paths are API Gateway route keys as well as Python routes.
#:
#: `GET /api/auth/oauth/providers` is deliberately NOT here. It mounts in every
#: deployment including one with no OAuth at all, so it belongs to row 5's
#: inventory of what an unswitched function serves, and that is where it is.
OAUTH_FLOW_PATHS = (
    ("GET", "/api/auth/oauth/{provider}/start"),
    ("GET", "/api/auth/oauth/callback"),
    ("POST", "/api/auth/oauth/{provider}/link"),
    ("GET", "/api/auth/oauth/links"),
    ("DELETE", "/api/auth/oauth/{provider}/link"),
)

#: The five passkey management routes: what `passkeys_enabled` alone mounts.
PASSKEY_MANAGEMENT_PATHS = (
    ("POST", "/api/auth/passkeys/register/options"),
    ("POST", "/api/auth/passkeys/register/verify"),
    ("GET", "/api/auth/passkeys"),
    ("PATCH", "/api/auth/passkeys/{credential_id}"),
    ("DELETE", "/api/auth/passkeys/{credential_id}"),
)

#: The two passkey login routes. They are declared by `passkeys_enabled` and
#: **refused** by `passkeys_passwordless`, which is a distinction this file
#: checks rather than assumes: the package declares all seven on the first flag
#: and the second decides whether a passkey is an entry point or only something
#: a signed-in user may add.
PASSKEY_LOGIN_PATHS = (
    ("POST", "/api/auth/login/passkey/options"),
    ("POST", "/api/auth/login/passkey/verify"),
)

#: What the staging workspace sets, and the values this file's `on` fixtures use.
GOOGLE_CLIENT_ID = "111111111111-carmodpicker.apps.googleusercontent.com"
GITHUB_CLIENT_ID = "Iv1.carmodpicker00000"
GOOGLE_CLIENT_SECRET = "google-client-secret-not-a-real-one"
GITHUB_CLIENT_SECRET = "github-client-secret-not-a-real-one"

#: The frontend origin, which is what `IDENTITY_WEBAUTHN_ORIGINS` carries. The
#: API origin would be wrong and the wrongness would be invisible until a real
#: authenticator refused an assertion, so it is written out here as the thing
#: `terraform/identity.tf` renders rather than derived from `ISSUER`.
FRONTEND_ORIGIN = "https://staging.carmodpicker.com"


# ---------------------------------------------------------------------------
# Fixtures. Each layers more `IDENTITY_*` onto row 5's environment.
# ---------------------------------------------------------------------------


@pytest.fixture
def passkeys_on(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`IDENTITY_PASSKEYS_ENABLED` and `..._PASSWORDLESS` both true.

    What the staging workspace sets, and what production receives at promotion.
    The origins list is a JSON array because `webauthn_origins` is a list field
    and `IdentitySettings` refuses bare comma separated values for its lists, so
    the format is load bearing rather than incidental.
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "true")
    monkeypatch.setenv("IDENTITY_WEBAUTHN_ORIGINS", json.dumps([FRONTEND_ORIGIN]))


@pytest.fixture
def oauth_on(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both providers' client ids and secrets, as a configured workspace has them.

    The ids are `IDENTITY_*` environment variables, which is where they belong:
    a client id is not a secret. The secrets are **not** `IDENTITY_*` and never
    are; they are read by `build_oauth_client_secrets`, which consults the
    process environment before the app secret exactly as every other secret in
    this application does, so setting them here is the same path a local run
    takes rather than a path invented for the test.
    """
    monkeypatch.setenv("IDENTITY_GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_GITHUB_CLIENT_ID", GITHUB_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_OAUTH_REDIRECT_URIS", json.dumps([f"{ISSUER}/oauth/callback"]))
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", GITHUB_CLIENT_SECRET)


def _build_identity_app(private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Row 5's `identity_app` body, reusable after a fixture has set more env.

    Hermetic in the two ways that matter: `boto3.client` is replaced so building
    the router constructs no real client and reaches no network, and nothing
    here touches DynamoDB, because constructing a store is a table name and a
    lazy resource handle and no route is called.
    """
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"the identity router asked for an unexpected client: {service}")

    # Patched on `boto3` itself, because `app/composition/identity.py` imports
    # it inside `build_router` rather than at module scope.
    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


@pytest.fixture
def passkey_app(passkeys_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with both passkey flags on and no OAuth."""
    yield from _build_identity_app(private_key, monkeypatch)


@pytest.fixture
def oauth_app(oauth_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with both providers configured and no passkeys."""
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    yield from _build_identity_app(private_key, monkeypatch)


@pytest.fixture
def everything_app(
    passkeys_on: None, oauth_on: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """Both switches on, which is what the staging workspace applies."""
    yield from _build_identity_app(private_key, monkeypatch)


# ---------------------------------------------------------------------------
# M5: the seven passkey routes and their two switches
# ---------------------------------------------------------------------------


def test_the_passkey_routes_mount_with_both_flags_on(passkey_app: Any) -> None:
    """All seven, at their public paths under the issuer's path.

    Seven rather than five because `passkeys_passwordless` is on as well, which
    is what the staging workspace sets. The paths are `/api/auth/...` because
    the package mounts everything under the issuer's path and this environment's
    issuer ends in `/api/auth`.
    """
    pairs = _pairs(passkey_app)

    for method, path in PASSKEY_MANAGEMENT_PATHS + PASSKEY_LOGIN_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"


def test_the_passkey_routes_are_absent_with_the_flag_off(oauth_app: Any) -> None:
    """None of the seven, and the absence is real rather than the package default.

    This is the test that matters most of the three, because the package's own
    default for `passkeys_enabled` is `True`. A Terraform edit that stopped
    rendering `IDENTITY_PASSKEYS_ENABLED` would silently turn seven routes on in
    production, and the only thing that would catch it is an assertion that the
    off state is really off.

    Absent rather than 403: a route that does not exist is not in the OpenAPI
    document, so a frontend cannot offer a button for a capability this
    deployment does not have.
    """
    pairs = _pairs(oauth_app)

    for method, path in PASSKEY_MANAGEMENT_PATHS + PASSKEY_LOGIN_PATHS:
        assert (method, path) not in pairs, f"{method} {path} mounted with the flag off"


def test_passwordless_off_keeps_the_five_management_routes(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`passkeys_enabled` true and `passkeys_passwordless` false declares all seven.

    The distinction this pins is the package's, and it is worth pinning because
    it is not the obvious one: `passkeys_passwordless` does **not** remove the
    two `/login/passkey/*` routes, it makes them refuse. So the shape of a
    second-factor-only deployment is seven routes of which two answer an error,
    not five routes.

    A reader who assumed otherwise would write a Terraform variable description
    claiming the routes disappear, and the frontend would hide a button on the
    strength of a 404 that never comes.
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    monkeypatch.setenv("IDENTITY_WEBAUTHN_ORIGINS", json.dumps([FRONTEND_ORIGIN]))

    app = next(_build_identity_app(private_key, monkeypatch))
    pairs = _pairs(app)

    for method, path in PASSKEY_MANAGEMENT_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"
    for method, path in PASSKEY_LOGIN_PATHS:
        assert (method, path) in pairs, (
            f"{method} {path} is declared by passkeys_enabled and refused by " "passwordless, not removed by it"
        )


def test_the_webauthn_origin_is_the_frontend_and_not_the_api(passkeys_on: None) -> None:
    """`IDENTITY_WEBAUTHN_ORIGINS` carries the SPA's origin, not the API host.

    WebAuthn binds an assertion to the origin of the page that created it, and
    the page is the SPA. Checking it server side is what makes a passkey
    phishing resistant: a look-alike site can copy every pixel and cannot
    produce an assertion carrying this origin. Pointing it at the API host would
    be a configuration that never verifies a single real assertion, and nothing
    short of a browser would notice.

    `rp_id` is the registrable domain and a different field with a different
    job: it is hashed into every credential and immutable for that credential's
    life, so it is the module's to set and not this block's.
    """
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.webauthn_origins == [FRONTEND_ORIGIN]
    assert identity_settings.rp_id == "staging.carmodpicker.com"
    assert identity_settings.rp_name == "CarModPicker"


# ---------------------------------------------------------------------------
# M6: the five OAuth flow routes, and the one that is always there
# ---------------------------------------------------------------------------


def test_the_oauth_routes_mount_when_a_provider_has_a_client_id(
    oauth_app: Any,
) -> None:
    """All five flow routes, with both providers configured."""
    pairs = _pairs(oauth_app)

    for method, path in OAUTH_FLOW_PATHS:
        assert (method, path) in pairs, f"{method} {path} did not mount"


def test_the_oauth_flow_routes_are_absent_with_no_client_id(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No client id means no flow route, which is how this ships until an app exists.

    The stores are supplied unconditionally by the composition root, so this is
    the assertion that says the client id is genuinely the switch and the stores
    are genuinely not. If a future edit made the composition root gate on the
    ids as well, this test would still pass and the second condition would be
    dead weight that could later disagree; what it catches is the opposite
    mistake, a store made into a switch.
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    app = next(_build_identity_app(private_key, monkeypatch))
    pairs = _pairs(app)

    for method, path in OAUTH_FLOW_PATHS:
        assert (method, path) not in pairs, f"{method} {path} mounted with no client id"


def test_the_providers_route_mounts_with_no_oauth_configured(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`GET /oauth/providers` is unconditional, and that is the point of it.

    A route that vanished when OAuth was off would mean a 404 the client has to
    interpret, and a 404 cannot be told apart from a routing mistake or an older
    version of the package. An empty list says "no providers, and I am sure".
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    app = next(_build_identity_app(private_key, monkeypatch))

    assert ("GET", "/api/auth/oauth/providers") in _pairs(app)


def test_the_providers_route_lists_both_configured_providers(
    everything_app: Any,
) -> None:
    """Both providers appear, because both carry an id **and** a secret.

    This is the end to end assertion for the whole secret path: the two values
    reach the package only through `oauth_client_secrets`, and a provider is
    advertised only when its secret arrived. So a provider listed here is proof
    that `OAUTH_GOOGLE_CLIENT_SECRET` travelled from where Terraform puts it to
    the argument the package takes.
    """
    from fastapi.testclient import TestClient

    with TestClient(everything_app) as client:
        response = client.get("/api/auth/oauth/providers")

    assert response.status_code == 200
    listed = {entry["id"] for entry in response.json()["providers"]}
    assert listed == {"google", "github"}


def test_a_provider_with_no_secret_is_not_advertised(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An id with no secret is a button that does not appear, not a failed start.

    This is the half-configured state that a two-agent rollout can genuinely be
    in for a few minutes: the client id is set on the workspace and the secret
    has not landed in the app secret yet. Before 0.16.0 the symptom was a user
    consenting at Google and meeting a 503 on the way back; now the provider is
    simply not offered.

    The deployment still starts, which is the other half of the contract and the
    reason `build_oauth_client_secrets` returns a partial mapping rather than
    raising on a missing key.
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")
    monkeypatch.setenv("IDENTITY_GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    monkeypatch.setenv("IDENTITY_GITHUB_CLIENT_ID", GITHUB_CLIENT_ID)
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
    # GitHub's secret is deliberately absent.

    from fastapi.testclient import TestClient

    app = next(_build_identity_app(private_key, monkeypatch))
    with TestClient(app) as client:
        response = client.get("/api/auth/oauth/providers")

    assert response.status_code == 200
    listed = {entry["id"] for entry in response.json()["providers"]}
    assert listed == {"google"}


# ---------------------------------------------------------------------------
# The client secrets, and the path they travel
# ---------------------------------------------------------------------------


def test_the_secret_keys_are_the_ones_terraform_writes() -> None:
    """`OAUTH_SECRET_KEYS` maps the package's provider names to this app's keys.

    Spelled out rather than derived, because the right hand side is a contract
    with `terraform/secretsmanager.tf` and the left hand side is a contract with
    the package. A rename on either side that is not made on the other is a
    provider that silently stops being advertised, and this is the assertion
    that turns that into a failing test.

    SCREAMING_SNAKE because the three keys already in that secret are
    `SECRET_KEY`, `SENTRY_DSN` and `EXTENSION_API_KEY`. Portfolio's are
    lowercase; matching this product's existing casing rather than Portfolio's
    is what keeps one secret readable by one convention.
    """
    from app.composition.identity import OAUTH_SECRET_KEYS

    assert OAUTH_SECRET_KEYS == {
        "google": "OAUTH_GOOGLE_CLIENT_SECRET",
        "github": "OAUTH_GITHUB_CLIENT_SECRET",
    }


def test_the_client_secrets_are_read_from_the_app_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both secrets come out of the `APP_SECRETS_ARN` blob, keyed as above.

    The environment is cleared for both names first, so this exercises the
    Secrets Manager path rather than the environment shortcut. That is the path
    a deployed function actually takes: `terraform/lambda_domains.tf` sets no
    `OAUTH_*_CLIENT_SECRET` variable on the function at all, deliberately, so
    the blob is the only source there is.
    """
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:1:secret:app")
    monkeypatch.setattr(
        "app.core.secrets.fetch_app_secrets",
        lambda *args, **kwargs: {
            "SECRET_KEY": "unused-here",
            "OAUTH_GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
            "OAUTH_GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
        },
    )

    assert build_oauth_client_secrets(app_settings) == {
        "google": GOOGLE_CLIENT_SECRET,
        "github": GITHUB_CLIENT_SECRET,
    }


def test_a_missing_key_is_omitted_rather_than_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One provider registered is a one-entry mapping, not a two-entry one with a blank.

    The distinction is load bearing. The package decides whether to advertise a
    provider by whether its secret is present, and an empty string is present,
    so returning `{"github": ""}` would advertise GitHub and then fail the token
    exchange, which is exactly the state 0.16.0's discovery route exists to
    prevent.
    """
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:1:secret:app")
    monkeypatch.setattr(
        "app.core.secrets.fetch_app_secrets",
        lambda *args, **kwargs: {
            "OAUTH_GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
            "OAUTH_GITHUB_CLIENT_SECRET": "",
        },
    )

    assert build_oauth_client_secrets(app_settings) == {"google": GOOGLE_CLIENT_SECRET}


def test_no_app_secret_is_an_empty_mapping_and_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local run with no `APP_SECRETS_ARN` gets `{}` and starts.

    Raising here would turn a deployment that is correctly serving no OAuth into
    a cold start failure, which is a far worse outcome than the one it would be
    guarding against. With no client id either, no OAuth flow route is declared,
    so there is no route that could have wanted the secret.
    """
    from app.composition.identity import build_oauth_client_secrets
    from app.core.config import settings as app_settings

    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("APP_SECRETS_ARN", raising=False)
    monkeypatch.setattr(app_settings, "APP_SECRETS_ARN", "")

    assert build_oauth_client_secrets(app_settings) == {}


def test_the_client_secrets_are_not_settings_fields(oauth_on: None) -> None:
    """Neither secret is a field of `IdentitySettings`, which is the whole design.

    A secret that is a settings field is a secret that appears in a `repr`, in a
    pydantic validation error, and in whatever log line prints the settings
    object. The package takes them as an argument for exactly that reason, and
    this is the assertion that says the argument was not quietly turned back
    into a field.

    `repr` is checked as well as the field list, because `extra="ignore"` on
    that class means an unknown `IDENTITY_*` name is dropped rather than
    rejected: a secret set under the prefix by mistake would not fail, it would
    simply not be there, and asserting on the rendered object is what catches a
    future change that makes it there.
    """
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert not hasattr(identity_settings, "google_client_secret")
    assert not hasattr(identity_settings, "github_client_secret")
    assert GOOGLE_CLIENT_SECRET not in repr(identity_settings)
    assert GITHUB_CLIENT_SECRET not in repr(identity_settings)

    # The ids, by contrast, are ordinary fields and are meant to be.
    assert identity_settings.google_client_id == GOOGLE_CLIENT_ID
    assert identity_settings.github_client_id == GITHUB_CLIENT_ID


def test_the_redirect_uri_is_the_issuer_callback(oauth_on: None) -> None:
    """The one allowed redirect URI is `<issuer>/oauth/callback`.

    Checked by exact string equality inside the package and never by prefix: a
    prefix check on `https://api.staging.carmodpicker.com` would also admit
    `https://api.staging.carmodpicker.com.attacker.test`, which is a registrable
    domain an attacker can buy today. An unchecked redirect URI is a code
    exfiltration primitive rather than an ordinary open redirect, because the
    provider sends a live authorization code to whatever it is told.
    """
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.oauth_redirect_uris == ["https://api.staging.carmodpicker.com/api/auth/oauth/callback"]


# ---------------------------------------------------------------------------
# Lifetimes: the refresh window this product runs
# ---------------------------------------------------------------------------


def test_the_refresh_window_is_thirty_days_rolling(identity_env: None) -> None:
    """Thirty days, reset on every rotation, with a ninety day hard cap.

    The owner's decision for this product, and it is the package's default
    rather than something Terraform sets, which is why this test asserts on the
    value rather than on an environment variable: a settings default that
    changed under a version bump would be a silent change to how long a session
    survives, and nothing else in this repository would notice.

    Rolling is the package's own behaviour and not something implemented here.
    `refresh_token_ttl` is the window and the package resets it on each
    rotation, so a user who visits inside thirty days keeps their session
    indefinitely, up to `refresh_absolute_ttl`, at which point a full sign-in is
    required regardless of activity.
    """
    from datetime import timedelta

    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.refresh_token_ttl == timedelta(days=30)
    assert identity_settings.refresh_absolute_ttl == timedelta(days=90)
    assert identity_settings.refresh_absolute_ttl >= identity_settings.refresh_token_ttl


# ---------------------------------------------------------------------------
# The hook: what now counts as another way in
# ---------------------------------------------------------------------------


def _user(**overrides: Any) -> User:
    """A user with no sign-in method at all, so each test adds exactly one."""
    base: dict[str, Any] = {
        "username": f"user{uuid4().hex[:8]}",
        "email": f"{uuid4().hex[:8]}@example.com",
        "email_verified": True,
        "hashed_password": None,
        "disabled": False,
        "is_superuser": False,
        "is_admin": False,
        "is_service_account": False,
    }
    base.update(overrides)
    return User(**base)


@pytest.fixture
def package_stores() -> tuple[Any, Any]:
    """The package's own in-memory passkey and OAuth link stores.

    In-memory rather than the Dynamo ones over moto, because what is under test
    is the hook's counting and not the package's storage. The in-memory classes
    are the package's own and implement the same ABCs the Dynamo ones do, so a
    signature change in `list_for_user` fails here too.
    """
    from webbpulse.identity.oauth import InMemoryOAuthLinkStore
    from webbpulse.identity.storage import InMemoryPasskeyStore

    return InMemoryPasskeyStore(), InMemoryOAuthLinkStore()


@pytest.fixture
def hooks_with_package_stores(dynamo_tables: Any, package_stores: tuple[Any, Any]) -> CarModPickerIdentityHooks:
    """Hooks over the real legacy repositories plus the two package stores.

    Real repositories for the legacy side, because the legacy half of this hook
    is almost entirely calls into them and a fake would assert that this file's
    stub behaves like this file's stub.
    """
    passkeys, links = package_stores
    return CarModPickerIdentityHooks(
        package_passkeys=passkeys,
        package_oauth_links=links,
    )


def test_a_package_passkey_counts(
    hooks_with_package_stores: CarModPickerIdentityHooks,
    package_stores: tuple[Any, Any],
    dynamo_tables: Any,
) -> None:
    """A user whose only credential is a package passkey has another way in.

    This is the case row 9 exists to cover in this hook. After migration a user
    may hold a passkey enrolled through the package's M5 routes and no package
    password, and `OAuthService.unlink` cannot see it: it counts the package's
    `credentials` row and its own `oauth-links` rows and nothing else. Without
    this, unlinking their last OAuth provider would delete the last thing
    `unlink` can see and leave an account reachable only by a credential the
    caller was just told did not exist.
    """
    from webbpulse.identity.storage import PasskeyRecord

    passkeys, _ = package_stores
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is False

    passkeys.put(
        PasskeyRecord(
            user_id=str(created.id),
            credential_id="Y3JlZGVudGlhbA",
            public_key="cHVibGlja2V5",
            name="Phone",
        )
    )

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is True


def test_a_package_oauth_link_counts(
    hooks_with_package_stores: CarModPickerIdentityHooks,
    package_stores: tuple[Any, Any],
    dynamo_tables: Any,
) -> None:
    """A package OAuth link counts, and counting it twice is the safe direction.

    `unlink` counts the package's links itself, so this is a deliberate double
    count. The two answers are taken at different moments: `unlink` counts the
    links it is about to reduce by one and this counts what exists now, so if
    they ever disagree the disagreement makes this hook answer `True` where
    `unlink` would have answered `False`. That refuses an unlink that might have
    been allowed, which costs a support ticket, rather than permitting one that
    loses an account.
    """
    from webbpulse.identity.oauth import OAuthLinkRecord

    _, links = package_stores
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    links.put(
        OAuthLinkRecord(
            provider_subject="google:12345",
            provider="google",
            subject="12345",
            user_id=str(created.id),
            linked_at="2026-09-10T00:00:00Z",
        )
    )

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is True


def test_a_package_totp_factor_still_does_not_count(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """Neither store is consulted for a second factor, and neither should be.

    A user holding only a TOTP factor and no first factor cannot sign in at all,
    so counting it would let `unlink` remove the last real credential and lock
    the account permanently. The hooks are not given a TOTP store at all, which
    makes this structural rather than a matter of remembering not to look.
    """
    user = _user()
    created = hooks_with_package_stores._users.create_user(user)

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is False
    assert not hasattr(hooks_with_package_stores, "_package_totp_factors")


def test_absent_package_stores_read_as_no_rows(dynamo_tables: Any) -> None:
    """Hooks built without the two package stores still answer, and answer `False`.

    A `None` store is a store this deployment does not have, and a deployment
    without the package's passkeys table has no package passkeys in it. This
    keeps every existing call site that builds these hooks with three arguments
    working unchanged, rather than making them stub two stores to count the
    legacy tables.
    """
    hooks = CarModPickerIdentityHooks()
    user = _user()
    created = hooks._users.create_user(user)

    assert hooks.has_other_sign_in_method(str(created.id)) is False


def test_a_legacy_password_still_counts_with_the_package_stores_present(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """Row 5's three legacy sources are unchanged by row 9's two additions.

    Adding to the end of a short-circuiting chain cannot break what came before
    it, but the chain is the whole method and a rewrite that reordered it could,
    so the cheapest of the three is checked here to say the legacy half still
    answers.
    """
    user = _user(hashed_password="$2b$12$" + "x" * 53)
    created = hooks_with_package_stores._users.create_user(user)

    assert hooks_with_package_stores.has_other_sign_in_method(str(created.id)) is True


def test_an_unparseable_subject_still_answers_false(
    hooks_with_package_stores: CarModPickerIdentityHooks, dynamo_tables: Any
) -> None:
    """An id this product cannot resolve gets `False`, and neither store is queried.

    The refusing side, as row 5 established: an `unlink` for a subject this
    product cannot resolve should not be told the account has other ways in.
    Row 9 adds two reads after the parse and the parse still guards both.
    """
    assert hooks_with_package_stores.has_other_sign_in_method("not-a-uuid") is False


# ---------------------------------------------------------------------------
# The composition seam
# ---------------------------------------------------------------------------


def test_the_hooks_receive_the_same_store_objects_the_package_does(
    everything_app: Any,
) -> None:
    """One construction of each store, shared between the hooks and the package.

    Two constructions would mean the package's table names spelled in two
    places, kept in step by hand, and a drifted name is a
    `ResourceNotFoundException` on the first unlink rather than anything a type
    checker sees. Asserting identity rather than equality is what says they are
    the same object and not merely two stores over the same table.
    """
    from app.composition.identity import build_router
    from app.core.config import settings as app_settings

    captured: dict[str, Any] = {}

    import webbpulse.identity as package

    original = package.build_identity_router

    def capture(settings: Any, hooks: Any, stores: Any, **kwargs: Any) -> Any:
        captured["hooks"] = hooks
        captured["stores"] = stores
        return original(settings, hooks, stores, **kwargs)

    # Patched on the package module because `build_router` imports the name
    # inside the function, so the lookup happens at call time.
    package.build_identity_router = capture  # type: ignore[assignment]
    try:
        build_router(app_settings)
    finally:
        package.build_identity_router = original  # type: ignore[assignment]

    hooks = captured["hooks"]
    stores = captured["stores"]

    assert hooks._package_passkeys is stores.passkeys
    assert hooks._package_oauth_links is stores.oauth_links


def test_the_four_new_stores_are_supplied_unconditionally(
    identity_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All four stores are present even with every switch off.

    This is the assertion that says the switch lives in the settings and not in
    the composition root. A second condition here could only ever disagree with
    the settings object, and disagreeing would present as a Terraform variable
    flipped with nothing changing and no error anywhere to say why.
    """
    monkeypatch.setenv("IDENTITY_PASSKEYS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_PASSKEYS_PASSWORDLESS", "false")

    from app.composition.identity import build_router
    from app.core.config import settings as app_settings

    captured: dict[str, Any] = {}

    import boto3

    monkeypatch.setattr(
        boto3,
        "client",
        lambda service, *a, **k: FakeKms(private_key) if service == "kms" else object(),
    )

    import webbpulse.identity as package

    original = package.build_identity_router

    def capture(settings: Any, hooks: Any, stores: Any, **kwargs: Any) -> Any:
        captured["stores"] = stores
        return original(settings, hooks, stores, **kwargs)

    package.build_identity_router = capture  # type: ignore[assignment]
    try:
        build_router(app_settings)
    finally:
        package.build_identity_router = original  # type: ignore[assignment]

    stores = captured["stores"]
    assert stores.passkeys is not None
    assert stores.webauthn_challenges is not None
    assert stores.oauth_states is not None
    assert stores.oauth_links is not None
