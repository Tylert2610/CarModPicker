"""Row 5: the identity hooks, and the package router mounted on the identity app.

This row adds two files and one mount. `app/composition/identity_hooks.py` is
the product policy half of the seam and `app/composition/identity.py` is the
composition half, and `build_domain_app` includes the second one on the identity
domain application only, guarded on `IDENTITY_ISSUER` being set.

What this file does not test is the package's own behaviour. That a TOTP code
verifies inside its window, that a refresh token rotates, that a reset link is
single use: the package's suite covers all of it, and asserting it again here
would pin the same behaviour twice and say nothing about CarModPicker.

What it tests is the four things only this repository can be wrong about.

**The hooks answer this product's questions.** `may_authenticate` has to refuse
a disabled account, a service account and an unverified address, because those
three flags are CarModPicker's own and the package has never heard of them.
`claims_for` has to put this product's two roles and its username into the
token, because every other domain reads them from there. The protocol is
asserted structurally with `isinstance`, which is what turns a package release
that grows a hook into a failure here rather than an `AttributeError` mid-login
in staging.

**The mount is conditional and the condition is the issuer.** With
`IDENTITY_ISSUER` unset the identity application is byte for byte the one row 4
left behind, which is what keeps `tests/fixtures/route_contract.json`, the
per-domain counts in `tests/entrypoints/test_route_split.py` and the OpenAPI
snapshot valid without regenerating any of them. Set it, and nineteen routes
appear. Both halves are asserted, because a mount that fired unconditionally
would break three pinned fixtures and a mount that never fired would look
exactly like success from the outside.

**The public paths are `/api/auth/...` with no prefix of this repository's
own.** `build_identity_router` places every route under `identity_prefix`, which
is the path component of the issuer, so the caller mounts with no prefix and the
issuer is the single thing that decides where the routes land. Passing a prefix
here would double it to `/api/api/auth`. The test asserts the paths rather than
the absence of an argument, because the path is what API Gateway routes on.

**The legacy routes still win the two collisions.** `POST /api/auth/logout` and
`POST /api/auth/verify-email` exist on both sides. The package router is
included after the legacy routers and FastAPI keeps the first match, so the
legacy handler answers both, which is what makes this row additive rather than a
cutover. The assertion is on the winning endpoint's module, so a reordering of
the include is a failure here rather than a silent change of behaviour on two
paths the frontend uses today.
"""

from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils

from app.composition.identity_hooks import CarModPickerIdentityHooks
from app.db.dynamo.users import User

# The route walker the split tests already use. Starlette 1.x stores one lazy
# wrapper per included router rather than flattening, so `app.routes` is not a
# flat list and counting it directly would find nine routes and miss every one
# this row cares about. Importing the helper rather than copying it means this
# file cannot disagree with the file that pins the counts.
from .entrypoints.test_route_split import _effective_routes, _pairs

# ---------------------------------------------------------------------------
# The environment terraform/lambda_domains.tf sets on the identity function.
#
# Written as environment variables rather than passed as arguments because that
# is the real interface: `IdentitySettings` is a `BaseSettings` with
# `env_prefix="IDENTITY_"` and `app/composition/identity.py` constructs it with
# no arguments at all. A test that built the settings object directly would not
# notice a Terraform variable renamed or never set.
# ---------------------------------------------------------------------------

#: The path component of this is what every route is mounted under, so
#: `/api/auth` here is what makes the public paths `/api/auth/...`.
ISSUER = "https://api.staging.carmodpicker.com/api/auth"
AUDIENCE = "carmodpicker-staging-api"
KEY_ARN = "arn:aws:kms:us-west-2:748861776298:key/11111111-2222-3333-4444-555555555555"
DATA_KEY_ARN = "arn:aws:kms:us-west-2:748861776298:key/99999999-8888-7777-6666-555555555555"

#: The nineteen routes this row mounts, spelled out rather than derived from the
#: package. A list computed from the thing it checks cannot notice that the
#: thing moved, and these paths are also API Gateway route keys in row 8.
PACKAGE_PATHS = (
    # M1: discovery, JWKS and the package's own health document.
    ("GET", "/api/auth/.well-known/openid-configuration"),
    ("GET", "/api/auth/.well-known/jwks.json"),
    ("GET", "/api/auth/health"),
    # M2: the password flows.
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/password"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/logout-all"),
    # M3: the two email ceremonies, which mount only because an email sender is
    # passed, which happens only because IDENTITY_EMAIL_FROM is set.
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/verify-email/confirm"),
    ("POST", "/api/auth/reset"),
    ("POST", "/api/auth/reset/confirm"),
    # M4: TOTP, recovery codes and step-up.
    ("POST", "/api/auth/login/totp"),
    ("POST", "/api/auth/totp/enrol"),
    ("POST", "/api/auth/totp/activate"),
    ("POST", "/api/auth/totp/disable"),
    ("POST", "/api/auth/recovery-codes"),
    ("POST", "/api/auth/step-up"),
)

#: The two `(method, path)` pairs that exist on both sides. The legacy handler
#: answers both, and `test_the_legacy_handlers_win_both_collisions` is what says
#: so. Row 13 resolves them by deleting the legacy routers.
COLLISIONS = (
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/verify-email"),
)


class FakeKms:
    """A KMS client for one key, signing for real with a local private key.

    Faithful in the two ways the rendered documents depend on: it signs the
    digest it is handed without re-hashing it, which is what `MessageType`
    `DIGEST` means, and it returns the DER SubjectPublicKeyInfo that the `kid`
    is the base64url SHA-256 of. It differs from KMS only in who holds the key.
    """

    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self._key = key

    def get_public_key(self, *, KeyId: str) -> dict[str, Any]:
        from webbpulse.identity import KMS_SIGNING_ALGORITHM

        return {
            "KeyId": KeyId,
            "PublicKey": self._key.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            "KeySpec": "RSA_2048",
            "KeyUsage": "SIGN_VERIFY",
            "SigningAlgorithms": [KMS_SIGNING_ALGORITHM],
        }

    def sign(self, *, KeyId: str, Message: bytes, MessageType: str, SigningAlgorithm: str) -> dict[str, Any]:
        return {
            "KeyId": KeyId,
            "Signature": self._key.sign(Message, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256())),
            "SigningAlgorithm": SigningAlgorithm,
        }


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    """One 2048-bit key for the module. Generation is slow enough to share."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def identity_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `IDENTITY_*` environment the deployed identity function receives.

    `IDENTITY_SIGNING_KEY_ARNS` is JSON because `jsonencode` is what renders it
    in `terraform/identity.tf`. The settings refuse a bare comma separated list,
    so the format is load bearing rather than incidental.

    `IDENTITY_EMAIL_FROM` is set because it is what decides whether the four M3
    routes exist: `build_email_sender` returns `None` without it and the package
    mounts no email ceremony when the sender is `None`.
    """
    from app.core.config import settings as app_settings

    monkeypatch.setenv("IDENTITY_ENVIRONMENT", "staging")
    monkeypatch.setenv("IDENTITY_ISSUER", ISSUER)
    monkeypatch.setenv("IDENTITY_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("IDENTITY_SIGNING_KEY_ARNS", json.dumps([KEY_ARN]))
    monkeypatch.setenv("IDENTITY_DATA_KEY_ARN", DATA_KEY_ARN)
    monkeypatch.setenv("IDENTITY_COOKIE_DOMAIN", "staging.carmodpicker.com")
    monkeypatch.setenv("IDENTITY_RP_ID", "staging.carmodpicker.com")
    monkeypatch.setenv("IDENTITY_RP_NAME", "CarModPicker")
    monkeypatch.setenv("IDENTITY_PRODUCT_NAME", "CarModPicker")
    monkeypatch.setenv("IDENTITY_SUPPORT_EMAIL", "support@carmodpicker.com")
    monkeypatch.setenv("IDENTITY_FRONTEND_BASE_URL", "https://staging.carmodpicker.com")
    monkeypatch.setenv("IDENTITY_EMAIL_FROM", "no-reply@staging.carmodpicker.com")

    # The one `IDENTITY_*` name `Settings` itself declares, and the only thing
    # `build_domain_app` consults before deciding to mount. Set on the settings
    # object rather than only in the environment because the object is a module
    # level singleton built at import, long before this fixture runs.
    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", ISSUER)


@pytest.fixture
def identity_app(identity_env: None, private_key: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity domain application, built in process with the mount on.

    Hermetic in the two ways that matter. `boto3.client` is replaced so that
    building the router constructs no real client and reaches no network, and
    the KMS client it would have built is the local signer above. Nothing here
    touches DynamoDB: the stores are constructed, which is a table name and a
    resource handle, and no route is called.
    """
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"the identity router asked for an unexpected client: {service}")

    # Patched on `boto3` itself rather than on `app.composition.identity`,
    # because that module imports `boto3` inside `build_router` rather than at
    # module scope. Importing it lazily is what keeps a monolith or a local run
    # from paying for botocore's import when the router never mounts, and it
    # means the name to patch is the one in `boto3`.
    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


@pytest.fixture
def hooks(dynamo_tables: Any) -> CarModPickerIdentityHooks:
    """Hooks over the real repositories, against moto's in-memory DynamoDB.

    Real repositories rather than fakes because the hooks are almost entirely
    calls into them, and a fake would be asserting that this file's own stub
    behaves the way this file's own stub behaves. `dynamo_tables` creates every
    table the repositories address.
    """
    return CarModPickerIdentityHooks()


def _user(**overrides: Any) -> User:
    """A user with the flags this product's policy reads, all permissive."""
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


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


def test_the_hooks_satisfy_the_protocol_structurally() -> None:
    """`isinstance` against the runtime checkable Protocol, with no inheritance.

    `CarModPickerIdentityHooks` subclasses nothing from the package, which is
    the point: the seam is structural, so a product's own class satisfies it
    without an import-time dependency on a package base class.

    This is also the release canary. `IdentityHooks` is `runtime_checkable`, so
    `isinstance` checks that every method name is present. A package release
    that adds a hook fails here, in a test that names the file to change, rather
    than at the first call in staging with an `AttributeError`.
    """
    from webbpulse.identity import IdentityHooks

    assert isinstance(CarModPickerIdentityHooks(), IdentityHooks)


def test_the_hooks_inherit_nothing_from_the_package() -> None:
    """Structural satisfaction, asserted as the absence of a base class.

    If a later edit makes this class extend `BaseIdentityHooks`, the `isinstance`
    above keeps passing while the failure mode changes completely: a forgotten
    hook starts raising `HookNotImplemented` at call time instead of failing the
    protocol check. Both are defensible; silently moving between them is not.
    """
    from webbpulse.identity import BaseIdentityHooks

    assert not issubclass(CarModPickerIdentityHooks, BaseIdentityHooks)


# ---------------------------------------------------------------------------
# may_authenticate: the three refusals and the one admission
# ---------------------------------------------------------------------------


def test_may_authenticate_admits_an_ordinary_verified_user(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """Not raising is the only way to permit, so this asserts a silent return."""
    assert hooks.may_authenticate({"email_verified": True}) is None


@pytest.mark.parametrize(
    ("user", "error_code"),
    [
        ({"email_verified": True, "disabled": True}, "ACCOUNT_DISABLED"),
        ({"email_verified": True, "is_service_account": True}, "SERVICE_ACCOUNT"),
        ({"email_verified": False}, "EMAIL_NOT_VERIFIED"),
    ],
    ids=["disabled", "service-account", "unverified"],
)
def test_may_authenticate_refuses_each_of_this_products_three_flags(
    hooks: CarModPickerIdentityHooks, user: dict[str, Any], error_code: str
) -> None:
    """Three flags the package has never heard of, each with its own code.

    The `error_code` is the half the frontend branches on, so it is asserted
    rather than only the fact of the refusal. The message deliberately does not
    distinguish them: telling a caller which of the three applies to an address
    they guessed is information about somebody else's account.
    """
    from webbpulse.identity import AuthenticationRefused

    with pytest.raises(AuthenticationRefused) as caught:
        hooks.may_authenticate(user)

    assert caught.value.error_code == error_code


def test_every_refusal_carries_the_same_message(hooks: CarModPickerIdentityHooks) -> None:
    """One message for all three, so a probe cannot tell them apart."""
    from webbpulse.identity import AuthenticationRefused

    messages = set()
    for user in (
        {"email_verified": True, "disabled": True},
        {"email_verified": True, "is_service_account": True},
        {"email_verified": False},
    ):
        with pytest.raises(AuthenticationRefused) as caught:
            hooks.may_authenticate(user)
        messages.add(caught.value.message)

    assert len(messages) == 1


def test_a_missing_flag_reads_as_unverified(hooks: CarModPickerIdentityHooks) -> None:
    """An empty mapping is refused, which is the failing-safe direction.

    `user.get("email_verified")` on a record that predates the attribute is
    `None`, and `not None` refuses. A record with no flags at all should not be
    a record that may sign in.
    """
    from webbpulse.identity import AuthenticationRefused

    with pytest.raises(AuthenticationRefused):
        hooks.may_authenticate({})


# ---------------------------------------------------------------------------
# claims_for: this product's two roles and its username
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "roles"),
    [
        ({}, []),
        ({"is_admin": True}, ["admin"]),
        ({"is_superuser": True}, ["superuser"]),
        ({"is_superuser": True, "is_admin": True}, ["superuser", "admin"]),
    ],
    ids=["none", "admin", "superuser", "both"],
)
def test_claims_for_maps_the_two_boolean_columns_onto_roles(
    hooks: CarModPickerIdentityHooks, flags: dict[str, Any], roles: list[str]
) -> None:
    """Two booleans in the users table, one `roles` array in the token.

    Every other domain authorises off this array, so the mapping is the contract
    between the identity function and the eight others. The order is asserted
    too, because an array is what lands in the token and a reordering would show
    up in a snapshot somewhere as a spurious diff.
    """
    claims = hooks.claims_for({"username": "someone", **flags})

    assert claims["roles"] == roles


def test_claims_for_carries_the_username(hooks: CarModPickerIdentityHooks) -> None:
    """The frontend renders it and the API Gateway authorizer passes it through.

    It is a required key rather than an optional one: `user["username"]` raises
    on a record without it, which is correct, because a CarModPicker user always
    has one and a record without one is a bug worth seeing.
    """
    assert hooks.claims_for({"username": "tyler"})["username"] == "tyler"


# ---------------------------------------------------------------------------
# The repository-backed hooks
# ---------------------------------------------------------------------------


def test_load_user_by_id_round_trips_a_created_user(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """And the id comes back as a string, not a UUID.

    That conversion is the whole reason `_as_mapping` calls `model_dump` in JSON
    mode. The package puts this value straight into `sub`, and a `UUID` object
    there is not JSON serialisable, so the failure without it is a 500 at the
    end of an otherwise successful login rather than anything a type checker
    sees.
    """
    created = hooks.create_user(email="round@example.com", attributes={"username": "round"})

    loaded = hooks.load_user_by_id(created["id"])

    assert loaded is not None
    assert loaded["id"] == created["id"]
    assert isinstance(loaded["id"], str)


def test_load_user_by_email_finds_the_same_record(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """The email index is how every login begins."""
    created = hooks.create_user(email="byemail@example.com", attributes={"username": "byemail"})

    loaded = hooks.load_user_by_email("byemail@example.com")

    assert loaded is not None
    assert loaded["id"] == created["id"]


def test_load_user_by_id_answers_none_for_an_unknown_id(
    hooks: CarModPickerIdentityHooks,
) -> None:
    assert hooks.load_user_by_id(str(uuid4())) is None


def test_load_user_by_id_answers_none_for_a_value_that_is_not_an_id(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """A `sub` claim is caller-supplied, so it may be anything at all.

    Answering `None` rather than raising is what makes an unparseable `sub`
    behave exactly like an id that names no user, which is a 401 rather than a
    500. Raising here would turn a malformed token into an error page.
    """
    assert hooks.load_user_by_id("not-a-uuid") is None


def test_load_user_by_email_answers_none_for_an_unknown_address(
    hooks: CarModPickerIdentityHooks,
) -> None:
    assert hooks.load_user_by_email("nobody@example.com") is None


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


def test_create_user_derives_a_username_from_the_address(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """The package's register flow supplies an email and no username.

    CarModPicker requires one and it is unique, so something has to invent it.
    The local part is the obvious choice and the one a user would have picked.
    """
    created = hooks.create_user(email="derived@example.com", attributes={})

    assert created["username"] == "derived"


def test_create_user_prefers_a_supplied_username(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """A caller that knows the username is not overridden by the derivation."""
    created = hooks.create_user(email="supplied@example.com", attributes={"username": "chosen"})

    assert created["username"] == "chosen"


def test_create_user_writes_the_address_it_was_given(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """The `email` argument wins over anything in `attributes`.

    The package verified the address in the argument, not one that arrived in a
    free-form attributes mapping, so letting the mapping win would let a
    registration claim an address it never proved.
    """
    created = hooks.create_user(
        email="actual@example.com",
        attributes={"email": "spoofed@example.com"},
    )

    assert created["email"] == "actual@example.com"


def test_create_user_refuses_to_carry_a_password_across_the_seam(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """`hashed_password` is dropped, whatever the attributes say.

    The package owns credentials now, in its own `credentials` table. A password
    written onto the legacy user row here would be a second copy that the
    package never rotates and `has_other_sign_in_method` would then read as a
    live sign-in method forever.
    """
    created = hooks.create_user(
        email="nopass@example.com",
        attributes={"username": "nopass", "hashed_password": "$2b$12$notreal"},
    )

    assert created["hashed_password"] is None


def test_create_user_ignores_a_supplied_id(hooks: CarModPickerIdentityHooks) -> None:
    """The repository mints a uuid7, and a caller does not get to choose it.

    uuid7 is time ordered, which is what makes the users table scan in creation
    order, and an id from outside would break that ordering silently.
    """
    chosen = str(uuid4())

    created = hooks.create_user(email="ownid@example.com", attributes={"username": "ownid", "id": chosen})

    assert created["id"] != chosen


def test_create_user_is_transactional_on_the_unique_attributes(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """A duplicate username fails the whole registration, atomically.

    `create_user` on the repository writes the row and its two `#unique#`
    sentinel rows inside one `TransactWriteItems`, so a collision on either
    attribute rolls the user row back with it. Without that, a taken username
    would leave a half-created account that can never log in and can never be
    registered again.
    """
    from app.db.dynamo.users import UniqueAttributeTaken

    hooks.create_user(email="first@example.com", attributes={"username": "taken"})

    with pytest.raises(UniqueAttributeTaken):
        hooks.create_user(email="second@example.com", attributes={"username": "taken"})

    # And the losing registration left nothing behind.
    assert hooks.load_user_by_email("second@example.com") is None


# ---------------------------------------------------------------------------
# mark_email_verified
# ---------------------------------------------------------------------------


def test_mark_email_verified_flips_the_flag_may_authenticate_reads(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """The two halves of the verification story, asserted as one sequence.

    This is the hook the package documents as having no safe default, and this
    is why: a product that confirmed a link without setting this flag would tell
    the user their address was verified and then go on refusing every login.
    """
    from webbpulse.identity import AuthenticationRefused

    created = hooks.create_user(email="verify@example.com", attributes={"username": "verify"})
    with pytest.raises(AuthenticationRefused):
        hooks.may_authenticate(created)

    hooks.mark_email_verified(created["id"])

    reloaded = hooks.load_user_by_id(created["id"])
    assert reloaded is not None
    assert hooks.may_authenticate(reloaded) is None


def test_mark_email_verified_raises_for_an_unknown_user(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """A consumed link that names no user is an error, not a silent success.

    CarModPicker's repository raises `ItemNotFound` where Portfolio's `update`
    returns `None`, so this hook translates it. Either way the caller has to
    learn that the address is not verified, because the token is spent and the
    user needs a new link.
    """
    with pytest.raises(ValueError):
        hooks.mark_email_verified(str(uuid4()))


def test_mark_email_verified_raises_for_a_value_that_is_not_an_id(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """Unlike the loaders, this one raises rather than answering quietly.

    A read that finds nothing is an ordinary outcome; a write that cannot even
    parse its target is a bug in the caller, and the id belongs in the message.
    """
    with pytest.raises(ValueError):
        hooks.mark_email_verified("not-a-uuid")


# ---------------------------------------------------------------------------
# has_other_sign_in_method
#
# New in 0.14.0, and the hook with the most product judgement in it. The package
# asks it before unlinking an OAuth account or removing a credential, to refuse
# the removal that would lock somebody out of their own account.
#
# CarModPicker counts three things as a sign-in method, and the tests below name
# each one:
#
#   1. a legacy password on the user row (`users.hashed_password`)
#   2. any passkey (`webauthn_credentials`)
#   3. any legacy Google link (`oauth_accounts`)
#
# It deliberately does not count the package's own `credentials` and
# `oauth-links` rows: `unlink` counts those itself, and counting them here would
# double count the very row being removed and refuse every legitimate unlink.
#
# It deliberately does not count TOTP. A second factor is not a sign-in method:
# a user with a TOTP factor and nothing else cannot sign in at all, so treating
# it as an alternative would permit removing the last real one.
# ---------------------------------------------------------------------------


def test_has_other_sign_in_method_is_false_for_a_user_with_nothing(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """A freshly created user has no password, no passkey and no link."""
    created = hooks.create_user(email="bare@example.com", attributes={"username": "bare"})

    assert hooks.has_other_sign_in_method(created["id"]) is False


def test_a_legacy_password_counts(hooks: CarModPickerIdentityHooks) -> None:
    """`users.hashed_password` is how every account created before this row signs in.

    It is still a live sign-in method until row 7's migration moves it into the
    package's `credentials` table, so unlinking an OAuth account for a user who
    has one must be permitted.
    """
    user = hooks.user_repository().create_user(_user(hashed_password="$2b$12$notreal"))

    assert hooks.has_other_sign_in_method(str(user.id)) is True


def test_a_passkey_counts(hooks: CarModPickerIdentityHooks, dynamo_tables: Any) -> None:
    """Any row in `webauthn_credentials` is a way in that does not need a password."""
    from app.db.dynamo.users import WebAuthnCredential, WebAuthnCredentialRepository

    user = hooks.user_repository().create_user(_user())
    WebAuthnCredentialRepository().create(
        WebAuthnCredential(
            user_id=user.id,
            credential_id=b"credential-id",
            public_key=b"public-key",
            nickname="a passkey",
        )
    )

    assert hooks.has_other_sign_in_method(str(user.id)) is True


def test_a_legacy_google_link_counts(hooks: CarModPickerIdentityHooks, dynamo_tables: Any) -> None:
    """CarModPicker's own Google flow is still mounted and still signs people in."""
    from app.db.dynamo.users import OAuthAccount, OAuthAccountRepository

    user = hooks.user_repository().create_user(_user())
    OAuthAccountRepository().create(OAuthAccount(user_id=user.id, provider="google", provider_account_id="12345"))

    assert hooks.has_other_sign_in_method(str(user.id)) is True


def test_a_totp_factor_does_not_count(hooks: CarModPickerIdentityHooks) -> None:
    """A second factor is not a sign-in method, and treating it as one locks people out.

    A user whose only remaining method is TOTP cannot sign in at all: there is
    no first factor to present it after. Counting it would let the package
    remove the last real method and report the account as still reachable.
    """
    user = hooks.user_repository().create_user(_user(totp_enabled=True, totp_secret="JBSWY3DPEHPK3PXP"))

    assert hooks.has_other_sign_in_method(str(user.id)) is False


def test_has_other_sign_in_method_is_false_for_an_unknown_user(
    hooks: CarModPickerIdentityHooks,
) -> None:
    assert hooks.has_other_sign_in_method(str(uuid4())) is False


def test_has_other_sign_in_method_is_false_for_a_value_that_is_not_an_id(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """The refusing side: an unparseable id reports no alternative method.

    That is the answer that makes the package refuse the removal, which is the
    safe direction when the caller has handed us something we cannot interpret.
    """
    assert hooks.has_other_sign_in_method("not-a-uuid") is False


# ---------------------------------------------------------------------------
# The two hooks with nothing to do
# ---------------------------------------------------------------------------


def test_on_user_created_does_nothing_and_says_so(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """CarModPicker runs no side effect on registration, so this returns None.

    It exists because the protocol has it, and it is asserted because a hook
    that grew a side effect without a test would be a side effect nobody knew
    ran on every registration.
    """
    assert hooks.on_user_created({"id": "whatever"}, "register") is None


def test_user_repository_hands_back_this_products_users_table(
    hooks: CarModPickerIdentityHooks,
) -> None:
    """Section 4.2's ownership convention, expressed as the returned object.

    The user record is owned by the `users` domain and `identity` is a writer of
    the authentication columns only. This is the seam where that is stated.
    """
    from app.db.dynamo.users import UserRepository

    assert isinstance(hooks.user_repository(), UserRepository)


# ---------------------------------------------------------------------------
# The mount
# ---------------------------------------------------------------------------


def test_without_an_issuer_the_identity_app_is_exactly_what_row_four_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard, asserted from the outside: no issuer, no package routes.

    This is the half that keeps `tests/fixtures/route_contract.json`, the
    per-domain counts in `tests/entrypoints/test_route_split.py` and the OpenAPI
    snapshot valid without regenerating any of them. The monolith and every
    local run leave `IDENTITY_ISSUER` empty, so they build the application they
    always built. A mount that fired unconditionally would break three pinned
    fixtures at once.
    """
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", "")

    from app.entrypoints.identity import build_app

    paths = {path for _, path in _pairs(build_app())}

    assert "/api/auth/.well-known/openid-configuration" not in paths
    assert "/api/auth/login" not in paths
    # And the legacy surface is untouched, which is the point of the guard.
    assert "/api/auth/token" in paths


def test_with_an_issuer_every_package_route_is_mounted(identity_app: Any) -> None:
    """All nineteen, at their public paths.

    Nineteen rather than fifteen because `IDENTITY_EMAIL_FROM` is set, which is
    what makes `build_email_sender` return a sender and the package mount M3's
    four email routes. The deployed function gets that variable from
    `terraform/lambda_domains.tf`, so nineteen is the deployed number.
    """
    served = _pairs(identity_app)

    missing = [pair for pair in PACKAGE_PATHS if pair not in served]

    assert missing == []


def test_the_router_is_mounted_with_no_prefix_of_this_repositorys_own(
    identity_app: Any,
) -> None:
    """`/api/auth/login`, not `/api/api/auth/login`.

    `build_identity_router` already places every route under
    `identity_prefix(settings)`, which is the path component of the issuer. The
    caller therefore mounts with no prefix, and the issuer is the single thing
    that decides where the routes land. Passing this domain's `router_prefix`
    as well, which is what `load_routers` does for every legacy router, would
    double it. The assertion is on the served paths rather than on the absence
    of an argument, because the path is what API Gateway routes on.
    """
    from webbpulse.identity import identity_prefix

    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    assert identity_prefix(build_identity_settings(app_settings)) == "/api/auth"

    doubled = [path for _, path in _pairs(identity_app) if path.startswith("/api/api")]
    assert doubled == []


def test_the_issuers_path_is_where_the_routes_land(identity_app: Any) -> None:
    """Every package route sits under the issuer's own path and nowhere else.

    This is the property that makes the mount correct rather than coincidentally
    right: change the issuer and the routes move with it, which is what keeps
    the discovery document's URLs and the served paths from ever disagreeing.
    """
    from urllib.parse import urlparse

    prefix = urlparse(ISSUER).path

    served = _pairs(identity_app)
    for method, path in PACKAGE_PATHS:
        assert (method, path) in served
        assert path.startswith(prefix)


def test_the_legacy_handlers_win_both_collisions(identity_app: Any) -> None:
    """Two paths exist on both sides, and the legacy handler answers both.

    `composition/domains.py` loads the legacy routers and `wiring.py` includes
    the package router after them, and FastAPI keeps the first match. That
    ordering is what makes this row additive: the legacy flow the frontend uses
    today is unchanged, and no package route is reachable from the SPA until
    row 6 wires `@webbpulse/auth`.

    Asserted on the winning endpoint's module rather than on the mount order, so
    that a reordering of the include is a failure here rather than a silent
    change of behaviour on two live paths.
    """
    winners: dict[tuple[str, str], Any] = {}
    for route in _effective_routes(identity_app):
        path = getattr(route, "path", None)
        for method in getattr(route, "methods", None) or []:
            winners.setdefault((method, path), getattr(route, "endpoint", None))

    for pair in COLLISIONS:
        endpoint = winners[pair]
        assert endpoint is not None
        assert endpoint.__module__.startswith(
            "app.api.endpoints.auth"
        ), f"{pair} is answered by {endpoint.__module__}, not the legacy router"


def test_the_legacy_auth_surface_is_unchanged_by_the_mount(identity_app: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every legacy `/api/auth` route still exists once the package is mounted.

    The collision test says the two shared paths still reach the legacy handler.
    This one says the other twenty-two are still there at all, which is the
    stronger form of "the legacy CMP auth routes must keep working in this row".
    """
    from app.core.config import settings as app_settings

    with_package = {pair for pair in _pairs(identity_app) if pair[1].startswith("/api/auth")}

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", "")
    from app.entrypoints.identity import build_app

    legacy_only = {pair for pair in _pairs(build_app()) if pair[1].startswith("/api/auth")}

    assert legacy_only <= with_package


def test_the_mount_adds_exactly_the_package_routes_and_nothing_else(
    identity_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The difference between the two applications is the seventeen new pairs.

    Seventeen rather than nineteen because two of the nineteen already existed
    on the legacy side. Pinning the difference rather than a total is what makes
    this test survive row 8 adding a route to some other part of the domain,
    while still failing if this row starts mounting something it did not before.
    """
    from app.core.config import settings as app_settings

    with_package = _pairs(identity_app)

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", "")
    from app.entrypoints.identity import build_app

    added = with_package - _pairs(build_app())

    assert added == set(PACKAGE_PATHS) - set(COLLISIONS)


# ---------------------------------------------------------------------------
# The composition seam itself
# ---------------------------------------------------------------------------


def test_the_settings_are_read_from_the_environment_and_not_passed_in(
    identity_env: None,
) -> None:
    """`IdentitySettings` reads `IDENTITY_*` itself, which is the whole wiring.

    `app/core/config.py` names exactly one of those variables, `IDENTITY_ISSUER`,
    and only because `build_domain_app` has to consult it before deciding to
    mount. Everything else reaches the package directly from the environment, so
    a Terraform rename shows up as a settings value that is wrong here rather
    than as a keyword argument that no longer exists.
    """
    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    identity_settings = build_identity_settings(app_settings)

    assert identity_settings.issuer == ISSUER
    assert identity_settings.audience == AUDIENCE
    assert identity_settings.signing_key_arns == [KEY_ARN]
    assert identity_settings.data_key_arn == DATA_KEY_ARN


def test_no_oauth_route_is_mounted(identity_app: Any) -> None:
    """M6 shipped in 0.14.0 and this row deliberately does not turn it on.

    The package mounts its five OAuth routes only when the stores carry both an
    `oauth_states` and an `oauth_links`, and `app/composition/identity.py`
    supplies neither, because `terraform/identity.tf` on PR 399 creates the six
    M1 to M4 tables and not the two OAuth ones. Supplying a store for a table
    that does not exist would turn a route that is absent from the OpenAPI
    document into one that 500s on the first click.

    CarModPicker's own Google flow under `/api/auth/oauth/*` is untouched and
    still serves, which is why this asserts on the package's own OAuth paths
    rather than on the absence of the word "oauth".
    """
    served = {path for _, path in _pairs(identity_app)}

    assert "/api/auth/oauth/authorize" not in served
    assert "/api/auth/oauth/callback" not in served
    # The legacy Google flow is still there.
    assert "/api/auth/oauth/google" in served


def test_building_the_router_opens_no_network_connection(identity_app: Any) -> None:
    """The fixture is the assertion: `boto3.client` raises for anything unexpected.

    `identity_app`'s fake refuses every service but `kms` and `sesv2`, so the
    application above was built without one real client, and this test exists to
    say that the hermetic property is deliberate rather than incidental. A
    future edit that reached for DynamoDB or SSM at build time would fail the
    fixture, not this assertion, which is the point.
    """
    assert identity_app is not None
