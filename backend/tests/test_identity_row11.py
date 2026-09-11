"""Row 11: the domains read the authorizer's claims, and `sub` is the user id.

Row 11 of `docs/identity-adoption.md`. Rows 8 and 9 put the identity access
token in front of fifteen `/api/auth` route keys at the gateway; this row is
where `app/api/dependencies/auth.py` turns a verified token into a `DBUser`.
Row 11 did that alongside the legacy HS256 session rather than instead of it;
row 13 deleted the legacy branch, so the identity claims are the only path a
resolver takes now.

## What is worth testing here

Three properties, and each one fails loudly if the code it covers is deleted.

1. **The legacy session is gone.** Row 12 was the cutover and row 13 retired the
   legacy flow. Through row 12 this file asserted the opposite, that a dual-mode
   change had not quietly regressed the shipped path, and those assertions were
   deliberate restatements of behaviour that was already true. Row 13 inverted
   the one that named the HS256 session: what it protects now is that no
   resolver takes an `Authorization: Bearer` HS256 token as proof of a session,
   which is the property that makes deleting `SECRET_KEY` from the identity
   domain safe.
2. **Both authorizer shapes resolve, and to the same user.** Production's native
   JWT authorizer puts claims at `authorizer.jwt.claims`; the staging access gate
   publishes one JSON string at `authorizer.lambda["jwt.claims"]`. The whole
   point of row 11's reader is that a caller sees one answer either way, so the
   two shapes are driven through the same request and compared.
3. **`sub` is the user id and not the username.** This is the mapping the row
   turns on and it is the one thing that would be silently wrong if it were
   guessed: the legacy session's `sub` is a **username**, the identity token's
   `sub` is a **uuid7 user id**, and a reader that tried the wrong lookup would
   still find a user on a system where someone's username happens to parse.

## What is deliberately not tested

**Not the signature.** Whether an RS256 token verifies is `webbpulse.identity`'s
own test, and on a flagged route key the gateway has already checked it before
this application runs. What is tested here is that a claim set reaches the
resolver and that a user id comes out.

**Not the gateway.** Which route keys are flagged is `terraform/apigateway.tf`
and the staging access gate module's own tests. This file starts from the event
those produce.

**Not in-process verification on a domain function.** `verify_bearer_subject`
answers `""` without `IDENTITY_SIGNING_KEY_ARNS` and a `kms:GetPublicKey` grant,
which no domain but `identity` has. That is asserted as the deployment fact it
is, rather than mocked into passing, because mocking it would test a
configuration this estate does not have.
"""

from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from webbpulse.http import REQUEST_CONTEXT_HEADER

from app.api.dependencies.auth import (
    create_access_token,
    get_current_user,
    get_optional_current_user,
    resolve_identity_user,
)
from app.api.dependencies.identity_claims import (
    GATE_CLAIMS_KEY,
    identity_claims,
    identity_subject,
    reset_token_service,
    verify_bearer_subject,
)
from app.api.dependencies.repositories import get_repositories
from app.db.dynamo.users import User, UserRepository

#: The issuer and audience `terraform/identity.tf` renders for staging. Spelled
#: out rather than imported from row 5's fixture because this file never builds
#: an `IdentitySettings`: what it needs is a claim set of the right shape, and
#: the two strings are part of that shape.
ISSUER = "https://api.staging.carmodpicker.com/api/auth"
AUDIENCE = "carmodpicker-staging-api"


def access_claims(subject: str, **overrides: Any) -> dict[str, str]:
    """A claim set shaped exactly as an authorizer delivers one.

    **Every value is a string, `exp` included, and that is the point rather than
    laziness in the fixture.** API Gateway's native JWT authorizer flattens the
    verified claims into a string map before putting them in the request
    context, and the staging access gate stringifies every value for exactly
    that reason, so that one reader works in both environments. A fixture using
    real integers would test a shape neither environment produces and would hide
    a coercion bug in the code under test.
    """
    claims = {
        "sub": subject,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": "access",
        "iat": "1788938046",
        "exp": "1788938646",
        "jti": "976037a1ea4847da8a633b3338d61f65",
        "username": "whoever",
        "roles": "[]",
    }
    claims.update({key: str(value) for key, value in overrides.items()})
    return claims


def native_context(subject: str, **overrides: Any) -> str:
    """The `x-amzn-request-context` header production's JWT authorizer produces.

    Plain JSON and never base64. The Lambda Web Adapter forwards the request
    context as a JSON string, which is the fact `webbpulse.identity.claims`
    exists to have exactly one implementation of.
    """
    return json.dumps({"authorizer": {"jwt": {"claims": access_claims(subject, **overrides)}}})


def gate_context(subject: str, **overrides: Any) -> str:
    """The header the staging access gate's Lambda authorizer produces.

    A Lambda authorizer's context always lands under `authorizer.lambda` and API
    Gateway refuses a nested object there, so the gate publishes one string key
    literally named `jwt.claims` holding the claims as JSON, plus the three it
    lifts out. The lifted keys are included because the real event carries them
    and a reader that accidentally depended on one would pass without them.
    """
    claims = access_claims(subject, **overrides)
    return json.dumps(
        {
            "authorizer": {
                "lambda": {
                    GATE_CLAIMS_KEY: json.dumps(claims),
                    "jwt.claims.sub": claims["sub"],
                    "jwt.claims.iss": claims["iss"],
                    "jwt.claims.exp": claims["exp"],
                }
            }
        }
    )


@pytest.fixture(autouse=True)
def _clean_token_service() -> Iterator[None]:
    """Drop the memoised `TokenService` around every test in this file.

    It caches a failure as well as a success, so a test that ran with no
    `IDENTITY_*` environment would otherwise poison one that sets it.
    """
    reset_token_service()
    yield
    reset_token_service()


@pytest.fixture
def identity_user(db_session: Any, dynamo_tables: Any) -> User:
    """A verified, enabled user, which is what `may_authenticate` admits."""
    suffix = str(id(db_session))
    return UserRepository().create_user(
        User(
            username=f"row11_{suffix}",
            email=f"row11_{suffix}@example.com",
            email_verified=True,
            disabled=False,
        )
    )


def _request(header_value: str | None = None, authorization: str | None = None) -> Request:
    """A bare ASGI `Request` carrying the headers this row reads.

    Built by hand rather than through a `TestClient` so that a unit test of the
    reader is a unit test. The routes are exercised through the application in
    the last section of this file.
    """
    headers: list[tuple[bytes, bytes]] = []
    if header_value is not None:
        headers.append((REQUEST_CONTEXT_HEADER.encode(), header_value.encode()))
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


# ---------------------------------------------------------------------------
# The reader: two shapes, one answer.
# ---------------------------------------------------------------------------


def test_the_native_authorizer_shape_is_read() -> None:
    """Production's `authorizer.jwt.claims` resolves through the package's reader."""
    subject = str(uuid4())
    assert identity_subject(_request(native_context(subject))) == subject


def test_the_staging_gate_shape_is_read() -> None:
    """Staging's `authorizer.lambda["jwt.claims"]` resolves too.

    This is the half the package's own `read_authorizer_claims` does not do: it
    raises `NoClaimsSection` on a context whose authorizer carries `lambda`
    rather than `jwt`, and its message says so. Deleting the fallback in
    `identity_claims.py` fails here and nowhere else, which is the whole reason
    this test exists.
    """
    subject = str(uuid4())
    assert identity_subject(_request(gate_context(subject))) == subject


def test_both_shapes_coerce_to_the_same_claims() -> None:
    """The two environments produce equal Python values and not merely equal subjects.

    The gate stringifies every claim value on purpose so that this is possible,
    and both paths run through the package's `coerce_claims`, so `exp` is an
    `int` on both sides rather than an `int` on one and a string on the other. A
    caller reading `exp` would otherwise work in production and raise a
    `TypeError` in staging, which is the failure mode the gate's own comment
    warns about.
    """
    subject = str(uuid4())
    native = identity_claims(_request(native_context(subject)))
    gate = identity_claims(_request(gate_context(subject)))
    assert native is not None and gate is not None
    assert native["exp"] == gate["exp"] == 1788938646
    assert isinstance(native["exp"], int) and isinstance(gate["exp"], int)
    assert native["sub"] == gate["sub"] == subject


def test_a_request_with_no_authorizer_is_nobody_rather_than_an_error() -> None:
    """An unflagged route key carries no claims, and that is not a failure.

    Every `/api/v1` route key today is an `ANY` over a whole prefix, so no
    authorizer claim ever arrives on one. Answering `""` rather than raising is
    what lets those routes stay anonymous-readable.
    """
    assert identity_subject(_request()) == ""
    assert identity_subject(_request(json.dumps({"http": {"sourceIp": "203.0.113.1"}}))) == ""


def test_an_unparseable_gate_payload_is_refused_rather_than_guessed() -> None:
    """A `jwt.claims` value that is not JSON resolves to nobody.

    The gate writes it with `JSON.stringify` and nothing else writes it at all,
    so a value that does not parse means the two sides disagree about the
    encoding. Refusing is the only safe direction: inventing a subject from a
    value this process could not read would be an authorization decision made on
    a guess.
    """
    broken = json.dumps({"authorizer": {"lambda": {GATE_CLAIMS_KEY: "not json at all"}}})
    assert identity_subject(_request(broken)) == ""


def test_in_process_verification_is_off_without_the_identity_environment() -> None:
    """`verify_bearer_subject` answers `""` on a function with no signing key.

    `terraform/lambda_domains.tf` sets the `IDENTITY_*` block on the identity
    function alone and `terraform/identity.tf` attaches the signing policy to the
    identity role alone, so a `catalog` or `build-lists` function can verify
    nothing in process. That is a deployment fact rather than a code path being
    skipped, and it is asserted here so that the report in the row 11 docs is
    checked rather than merely written down.
    """
    assert verify_bearer_subject(_request(authorization="Bearer whatever")) == ""


# ---------------------------------------------------------------------------
# The mapping: `sub` is the user id.
# ---------------------------------------------------------------------------


def test_sub_resolves_to_the_user_row_by_id(identity_user: User) -> None:
    """The identity `sub` is the CarModPicker `users.id`, with no link table.

    `CarModPickerIdentityHooks.load_user_by_id` parses the `sub` to a `UUID` and
    does one `GetItem`, so an identity user is the legacy user row under the id
    it always had. This is the assertion that would fail if the mapping were a
    stored link or a second id space.
    """
    repos = get_repositories()
    resolved = resolve_identity_user(_request(native_context(str(identity_user.id))), repos)
    assert resolved is not None
    assert resolved.id == identity_user.id
    assert resolved.username == identity_user.username


def test_a_username_in_sub_does_not_resolve(identity_user: User) -> None:
    """A `sub` holding a username finds nobody, which is what keeps the two flows apart.

    The legacy session's `sub` is the username and the identity token's is the
    id. A resolver that tried a username lookup as a fallback would let a legacy
    token minted for one flow satisfy the other, which is precisely the
    confusion row 13 has to be able to rely on not existing.
    """
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(identity_user.username)), repos) is None


def test_a_sub_that_is_not_a_uuid_resolves_to_nobody() -> None:
    """A token this product did not mint is "no such user" rather than a 500."""
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context("not-a-uuid")), repos) is None


def test_a_disabled_account_is_refused_on_the_identity_path(identity_user: User) -> None:
    """A token minted before an account was disabled stops working immediately.

    The three account checks are the same three `may_authenticate` applies at the
    package's door, and they are applied again here because an access token lives
    for ten minutes and an account can be disabled inside one.
    """
    UserRepository().update_user(identity_user.id, disabled=True)
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(str(identity_user.id))), repos) is None


def test_an_unverified_address_is_refused_on_the_identity_path(identity_user: User) -> None:
    """An unverified account is refused, matching what `get_current_user` already does."""
    UserRepository().update_user(identity_user.id, email_verified=False)
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(str(identity_user.id))), repos) is None


# ---------------------------------------------------------------------------
# Dual mode, through a real application.
# ---------------------------------------------------------------------------


def _dual_mode_app() -> FastAPI:
    """A minimal application carrying the two resolvers this row changed.

    Two routes rather than the whole application, because what is under test is
    the dependency and not any product endpoint. Building it here keeps the test
    independent of which domain happens to own an authenticated route today.
    """
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: User = Depends(get_current_user)) -> dict[str, str]:
        return {"id": str(user.id), "username": user.username}

    @app.get("/maybe")
    async def maybe(user: User | None = Depends(get_optional_current_user)) -> dict[str, str]:
        return {"id": str(user.id)} if user is not None else {"id": ""}

    return app


@pytest.fixture
def legacy_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-empty `SECRET_KEY`, so an HS256 token can be minted at all.

    The test environment leaves it empty, which row 13 made the normal state:
    nothing in the identity domain signs with it any more. The two tests below
    have to mint a legacy token in order to assert it is refused, and `PyJWT`
    raises `InvalidKeyError` on an empty HMAC key before the resolver is ever
    reached. Set here rather than in `conftest.py` so that the emptiness stays
    the default everywhere else.

    `SECRET_KEY` is a read-only property that resolves `SECRET_KEY_SETTING`
    through the secrets loader, so the backing field is what is patched. Same
    approach as `tests/consumers/test_price_alerts_consumer.py`.
    """
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SECRET_KEY_SETTING", "test-signing-key-not-a-real-one")


def test_the_legacy_session_no_longer_resolves(identity_user: User, dynamo_tables: Any, legacy_secret: None) -> None:
    """An HS256 token with a username in `sub` is nobody, which is row 13's point.

    Through row 12 this asserted the opposite: `POST /api/auth/token` minted
    exactly this token and the resolver had to keep accepting it, and if the
    identity branch had swallowed that path this was the test that failed.

    Row 13 deleted the route that minted it and the branch that read it. The
    token still verifies as a signature, because `create_access_token` survives
    for the price alert unsubscribe link, so this is not a test that the secret
    is gone. It is a test that a validly signed HS256 token is no longer a
    session: the resolver reads identity claims and nothing else, so a caller
    presenting one resolves to nobody rather than to `identity_user`.

    The distinction matters because the unsubscribe token is minted with the
    same key and would otherwise be a bearer token for whichever user its `sub`
    happened to name.
    """
    client = TestClient(_dual_mode_app())
    token = create_access_token({"sub": identity_user.username})

    # The required resolver refuses outright rather than resolving to somebody.
    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

    # And the optional one is anonymous rather than falling back to the username
    # lookup, which is the half a 401 alone would not distinguish.
    optional = client.get("/maybe", headers={"Authorization": f"Bearer {token}"})
    assert optional.status_code == 200
    assert optional.json()["id"] == ""


def test_an_unsubscribe_token_is_not_a_session_for_the_user_it_names(
    identity_user: User, dynamo_tables: Any, legacy_secret: None
) -> None:
    """The concrete form of the risk above, with the real token this key still signs.

    `app/core/email.py` mints a 30 day token whose `sub` is a price alert id and
    whose purpose is `price_alert_unsubscribe`, and it is the one caller of
    `create_access_token` that outlived the legacy session. A resolver that
    still read HS256 would turn every unsubscribe link in every inbox into a
    bearer token. Pinned with the user's own id in `sub`, which is the worst
    case: a uuid that does resolve to a row.
    """
    client = TestClient(_dual_mode_app())
    token = create_access_token(
        {"sub": str(identity_user.id), "purpose": "price_alert_unsubscribe"},
    )

    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

    optional = client.get("/maybe", headers={"Authorization": f"Bearer {token}"})
    assert optional.status_code == 200
    assert optional.json()["id"] == ""


def test_an_identity_token_resolves_through_the_gate_context(identity_user: User, dynamo_tables: Any) -> None:
    """Staging's shape resolves end to end, with no `Authorization` header at all.

    The header is deliberately absent. On a flagged route key the gateway has
    already verified the token and the claims arrive in the request context, so a
    resolver that only ever looked at `Authorization` would answer 401 on exactly
    the requests row 8 arranged to be verified.
    """
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: gate_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_an_identity_token_resolves_through_the_native_context(identity_user: User, dynamo_tables: Any) -> None:
    """Production's shape resolves end to end too, so the promotion changes nothing here."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: native_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_an_unknown_subject_is_a_401_and_not_a_500(dynamo_tables: Any) -> None:
    """A well-formed id for a row that does not exist is refused, quietly.

    One 401 whose body says nothing about which of the several possible reasons
    applied. An expired token, a token for another issuer, a `sub` naming a
    deleted user and no token at all are all simply "not signed in".
    """
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: native_context(str(uuid4()))},
    )
    assert response.status_code == 401


def test_the_optional_resolver_is_anonymous_without_a_token(dynamo_tables: Any) -> None:
    """A public read stays public. This is what would break if the optional
    resolver had been made to raise on a missing claim section."""
    client = TestClient(_dual_mode_app())
    response = client.get("/maybe")
    assert response.status_code == 200
    assert response.json()["id"] == ""


def test_the_optional_resolver_reads_an_identity_token(identity_user: User, dynamo_tables: Any) -> None:
    """A public read that carries an identity token sees the user behind it."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/maybe",
        headers={REQUEST_CONTEXT_HEADER: gate_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_a_bare_request_still_gets_the_unchanged_401_body(dynamo_tables: Any) -> None:
    """`IdentityAwareOAuth2` changes nothing for a request carrying no credential.

    The scheme only declines to raise when `identity_subject` already found a
    verified subject, so a request with neither a header nor an authorizer falls
    through to the parent class and gets the same `Not authenticated` body,
    produced by the same line of `OAuth2PasswordBearer`, that it always did. This
    is the test that fails if the widening were ever made unconditional, which is
    the only way the new scheme could weaken anything.
    """
    client = TestClient(_dual_mode_app())
    response = client.get("/whoami")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
