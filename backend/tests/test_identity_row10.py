"""Row 10: the Chrome extension's sign in handoff, and what it refuses.

Row 10 of `docs/identity-adoption.md`. `app/composition/identity_extension.py`
declares two routes, and unlike rows 5 and 9 this is product code rather than a
package mount, so this file tests behaviour and not only a configuration seam.

## What is worth testing here

The handoff is a credential-issuing path with three checks holding it up, and
each one is the only thing standing between a caller and somebody else's
session:

1. **Who is asking.** `POST /extension/handoff` needs a verified access token.
   Without that, knowing a redirect URI would be enough to mint a code for an
   arbitrary `sub`.
2. **Which extension.** The redirect target must name an id on
   `CHROME_EXTENSION_IDS`, the same variable the CORS allow list reads. Without
   that, a page could send a code to an extension the user never installed.
3. **What a code is.** `POST /extension/token` must accept a handoff code and
   refuse an access token. Without the `typ` and `aud` checks, an access token
   could be exchanged for a fresh access token with a reset expiry, which turns
   a ten minute credential into an unbounded one.

Each has a test that fails if the check is deleted, which is the property that
makes them worth having rather than restatements of the code.

## Why the tokens are minted through the router's own signer

The tests sign with `FakeKms` from row 5's file, which is a real RSA key with
KMS's interface. So a code this file builds by hand verifies exactly as one the
route minted, and one with a wrong `aud` or `typ` fails for the reason the route
says rather than because the signature is fake. A stubbed verifier would let
every one of the three checks above be deleted without a failure here.

## What is deliberately not tested

**Not the package's token machinery.** Whether an RS256 signature verifies and
whether `aud` is enforced are `webbpulse.identity`'s own tests. What this file
tests is that this product passes the right audience and asserts the right
`typ`.

**Not the frontend page.** `frontend/src/pages/authentication/ExtensionHandoff.
test.tsx` owns the redirect target validation on that side. The duplication of
the check is the point, so both sides have their own test.

**Not the extension.** `chrome-extension/` has no test runner: its CI is
type-check, `npm audit` and build. The manual steps are in the pull request.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import pytest

from .entrypoints.test_route_split import _pairs

# Row 5's fixtures, imported rather than rewritten, for the reason row 9's file
# gives: there is one correct version of the identity function's environment and
# a local RSA signer, and a second copy would drift.
#
# Aliased on import and re-exported below so that a linter does not read twelve
# test signatures as twelve redefinitions of a module-level name. See the note in
# `test_identity_row9.py`.
from .test_identity_row5 import AUDIENCE, ISSUER, KEY_ARN, FakeKms
from .test_identity_row5 import identity_env as _identity_env
from .test_identity_row5 import private_key as _private_key

identity_env = _identity_env
private_key = _private_key

#: The staging extension id, which is `vars.CWS_EXTENSION_ID` on that
#: Environment and the same value `VITE_ALLOWED_EXTENSION_IDS` carries into the
#: frontend bundle. Spelled out rather than invented so that this file exercises
#: the real shape of the value: 32 lowercase letters, which is what Chrome
#: generates and what `new URL(...).hostname` lowercases to on the page.
STAGING_EXTENSION_ID = "dbglgmnnfandmnacdpibkfggkadjikkg"

#: A well-formed id that is not on the allowlist. Same shape as a real one, so a
#: test that refuses it is testing the allowlist rather than the parser.
OTHER_EXTENSION_ID = "aaaabbbbccccddddeeeeffffgggghhhh"

#: Row 10's two routes, spelled out rather than derived. `test_identity_row5.py`
#: imports this tuple for its exact-delta assertion, so this is the one
#: inventory of what row 10 adds, and both files read it from here.
#:
#: Both are under `/api/auth`, which is why row 10 adds no API Gateway route
#: key: `ANY /api/auth/{proxy+}` already covers them.
EXTENSION_PATHS = (
    ("POST", "/api/auth/extension/handoff"),
    ("POST", "/api/auth/extension/token"),
)


@pytest.fixture
def extension_env(identity_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Row 5's environment plus the one variable row 10 adds.

    Layered on top of `identity_env` rather than replacing it, which works
    because `monkeypatch.setenv` from a fixture depending on another runs after
    it. The same composition `test_identity_row9.py` uses for its switches.
    """
    monkeypatch.setenv("CHROME_EXTENSION_IDS", STAGING_EXTENSION_ID)


@pytest.fixture
def extension_app(extension_env: None, private_key: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The identity application with the extension allowlist set.

    Hermetic in the same two ways row 5's `identity_app` is: `boto3.client` is
    replaced so building the routers reaches no network, and the KMS client is a
    local signer. No DynamoDB table is touched, because neither route reads or
    writes one: the handoff code carries its own state. See the module docstring
    of `app/composition/identity_extension.py` for why it is a signed token
    rather than a row.
    """
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"an unexpected client was requested: {service}")

    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


@pytest.fixture
def client(extension_app: Any) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    with TestClient(extension_app) as test_client:
        yield test_client


def _sign(private_key: Any, claims: dict[str, Any]) -> str:
    """Encode `claims` with the same key and algorithm the router signs with.

    Goes through the package's own `KmsSigner` over `FakeKms` rather than
    calling PyJWT directly, so the header, the `kid` and the signature are built
    by the code the route's verifier is paired with. A token this produces is
    indistinguishable from one the route minted, which is what lets the refusal
    tests below isolate exactly the claim they change.
    """
    from webbpulse.identity import KmsSigner

    return KmsSigner(FakeKms(private_key), KEY_ARN).encode(claims)


def _access_token(private_key: Any, subject: str = "user-1") -> str:
    """A valid access token for `subject`, with this deployment's audience."""
    issued_at = int(time.time())
    return _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": subject,
            "aud": AUDIENCE,
            "iat": issued_at,
            "exp": issued_at + 600,
            "typ": "access",
        },
    )


def _redirect_uri(extension_id: str = STAGING_EXTENSION_ID) -> str:
    return f"chrome-extension://{extension_id}/handoff.html"


# ---------------------------------------------------------------------------
# The routes exist, where the gateway already covers them
# ---------------------------------------------------------------------------


def test_both_routes_mount_on_the_identity_function(extension_app: Any) -> None:
    served = _pairs(extension_app)
    missing = [pair for pair in EXTENSION_PATHS if pair not in served]
    assert missing == []


def test_every_route_is_under_the_existing_proxy_route_key(extension_app: Any) -> None:
    """Both paths sit under `/api/auth`, so row 10 adds no API Gateway route key.

    `ANY /api/auth/{proxy+}` already covers everything below `/api/auth`. A path
    that escaped that prefix would need a Terraform change, which row 10 is
    explicitly not, and would fail closed in a deployed environment while
    passing every test here.
    """
    served = {path for method, path in _pairs(extension_app) if (method, path) in EXTENSION_PATHS}
    assert served
    assert all(path.startswith("/api/auth/") for path in served)


def test_the_routes_are_absent_without_an_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `IDENTITY_ISSUER` means no mount, exactly as row 5's package mount.

    The monolith's environment carries none, so this is what keeps row 10 off
    `tests/fixtures/route_contract.json` and out of the published OpenAPI
    snapshot.
    """
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", "")
    from app.entrypoints.identity import build_app

    served = {path for _, path in _pairs(build_app())}
    assert "/api/auth/extension/handoff" not in served
    assert "/api/auth/extension/token" not in served


# ---------------------------------------------------------------------------
# Check 1: who is asking
# ---------------------------------------------------------------------------


def test_a_code_needs_a_signed_in_caller(client: Any) -> None:
    response = client.post(
        "/api/auth/extension/handoff",
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "NOT_AUTHENTICATED"


def test_an_unverifiable_bearer_token_is_simply_not_signed_in(client: Any) -> None:
    """A garbage token is the same 401 as no token, with no hint about why.

    Distinguishing "expired" from "wrong issuer" from "not a token at all" tells
    somebody probing which of their guesses was closer.
    """
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": "Bearer not-a-token"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "NOT_AUTHENTICATED"


def test_a_signed_in_caller_gets_a_code(client: Any, private_key: Any) -> None:
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("code"), str)
    assert body["code"]
    # Exactly the shape `ExtensionHandoff.tsx` reads: it takes `code` off the
    # body and puts it in the redirect fragment. A second field would be
    # harmless, but the page would not carry it, so there is nothing to add.
    assert set(body) == {"code"}


# ---------------------------------------------------------------------------
# Check 2: which extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "redirect_uri",
    [
        pytest.param(f"https://{STAGING_EXTENSION_ID}/handoff.html", id="https-scheme"),
        pytest.param(f"chrome-extension://{OTHER_EXTENSION_ID}/x.html", id="unlisted-id"),
        pytest.param("chrome-extension:///handoff.html", id="no-host"),
        pytest.param("not a url at all", id="unparseable"),
        pytest.param(f"moz-extension://{STAGING_EXTENSION_ID}/x", id="other-extension-scheme"),
    ],
)
def test_a_redirect_target_we_do_not_trust_is_refused(client: Any, private_key: Any, redirect_uri: str) -> None:
    """Every way of naming an extension we will not hand a code to.

    The scheme cases matter as much as the id one: a `https://` target with an
    allowlisted id would be a redirect off the extension entirely, carrying a
    credential in its fragment to an origin that can read it.
    """
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": redirect_uri},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "EXTENSION_NOT_ALLOWED"


def test_an_unset_allowlist_still_serves_the_store_build(
    client: Any, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unset means the store id, the same default `Settings` carries.

    The allowlist reads `CHROME_EXTENSION_IDS`, which the CORS allow list also
    reads and which is defaulted in `app/core/config.py` precisely so a shipped
    extension works without a Terraform or Lambda environment change. An unset
    variable therefore means the published build rather than nothing, and the
    handoff has to agree with CORS about that or the extension would pass the
    preflight and then fail to sign in.
    """
    monkeypatch.delenv("CHROME_EXTENSION_IDS", raising=False)
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 200


def test_an_explicitly_empty_allowlist_trusts_nothing(
    client: Any, private_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting the variable to empty is a deliberate statement, and is honoured.

    This is the switch that turns handoff off in a deployment, and it has to be
    distinguishable from "not configured": the empty string is someone saying
    no extension, where absence is someone not having said anything.
    """
    monkeypatch.setenv("CHROME_EXTENSION_IDS", "")
    response = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "EXTENSION_NOT_ALLOWED"


def test_the_allowlist_parses_the_comma_separated_form_terraform_renders() -> None:
    """Several ids, whitespace and empty entries, the way a variable arrives."""
    from app.composition.identity_extension import allowed_extension_ids

    parsed = allowed_extension_ids({"CHROME_EXTENSION_IDS": f" {STAGING_EXTENSION_ID} ,,{OTHER_EXTENSION_ID}"})
    assert parsed == [STAGING_EXTENSION_ID, OTHER_EXTENSION_ID]
    assert allowed_extension_ids({"CHROME_EXTENSION_IDS": ""}) == []

    # Absent means the store default, not nothing. See the route test above.
    assert allowed_extension_ids({}) == [STAGING_EXTENSION_ID]

    # `chrome_extension_origins_list` tolerates an id that already carries the
    # scheme, so one variable can feed both readers.
    assert allowed_extension_ids({"CHROME_EXTENSION_IDS": f"chrome-extension://{STAGING_EXTENSION_ID}"}) == [
        STAGING_EXTENSION_ID
    ]


def test_the_default_matches_the_settings_field_it_shadows() -> None:
    """The duplicated default cannot drift from the one `Settings` declares.

    `identity_extension` spells the store id itself rather than importing
    `Settings`, so that reading the module pulls in no configuration object.
    That is only safe while the two agree, which is what this asserts.
    """
    from app.composition.identity_extension import DEFAULT_EXTENSION_ID
    from app.core.config import Settings

    field = Settings.model_fields["CHROME_EXTENSION_IDS"]
    assert field.default == DEFAULT_EXTENSION_ID
    assert DEFAULT_EXTENSION_ID == STAGING_EXTENSION_ID


# ---------------------------------------------------------------------------
# Check 3: what a code is
# ---------------------------------------------------------------------------


def test_a_code_round_trips_to_an_access_token(client: Any, private_key: Any) -> None:
    """The whole path: sign in, ask for a code, spend it, hold a token.

    The subject survives the round trip, which is the property the extension
    depends on: the token it ends up holding is the user's who signed in on the
    page, and not anybody else's.
    """
    issued = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key, 'user-42')}"},
        json={"redirect_uri": _redirect_uri(), "state": "nonce"},
    )
    assert issued.status_code == 200

    exchanged = client.post(
        "/api/auth/extension/token",
        json={"code": issued.json()["code"]},
    )
    assert exchanged.status_code == 200
    body = exchanged.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0

    from webbpulse.identity import TokenService

    from app.composition.identity import build_identity_settings
    from app.core.config import settings as app_settings

    tokens = TokenService(build_identity_settings(app_settings), FakeKms(private_key))
    claims = tokens.verify_access_token(body["access_token"])
    assert claims["sub"] == "user-42"
    assert claims["typ"] == "access"


def test_an_access_token_cannot_be_exchanged_for_another(client: Any, private_key: Any) -> None:
    """The check that stops a ten minute credential becoming an unbounded one.

    Without the audience and `typ` assertions, an extension (or anything else
    holding a token) could spend it here every ten minutes forever and never
    sign in again. The token presented here is a perfectly valid access token,
    so this fails for the right reason.
    """
    response = client.post(
        "/api/auth/extension/token",
        json={"code": _access_token(private_key)},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_a_code_with_the_wrong_typ_is_refused(client: Any, private_key: Any) -> None:
    """Right audience, wrong `typ`. Isolates the `typ` assertion on its own.

    The audience alone is not enough, which is why both are checked: a future
    token minted for the extension audience for some other reason must not be
    spendable here.
    """
    issued_at = int(time.time())
    forged = _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "something_else",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": forged})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_an_expired_code_is_refused(client: Any, private_key: Any) -> None:
    """Sixty seconds is a real bound and not a comment.

    Minted in the past rather than by waiting, so the test is deterministic and
    costs nothing. The clock skew leeway is why this is well past the window
    rather than one second over it.
    """
    issued_at = int(time.time()) - 3600
    stale = _sign(
        private_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "extension_handoff",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": stale})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_a_code_signed_by_another_key_is_refused(client: Any) -> None:
    """A correctly shaped code from a key this deployment does not know.

    This is the check that makes the whole design safe to put in a URL
    fragment: the code's authority comes from the signature and not from
    knowing its shape, so an attacker who reads the format learns nothing they
    can use.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issued_at = int(time.time())
    forged = _sign(
        other_key,
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": f"{ISSUER}/extension",
            "iat": issued_at,
            "exp": issued_at + 60,
            "typ": "extension_handoff",
        },
    )
    response = client.post("/api/auth/extension/token", json={"code": forged})
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "HANDOFF_CODE_INVALID"


def test_the_exchange_needs_no_bearer_token(client: Any, private_key: Any) -> None:
    """The code is the credential, so requiring a token to spend it is circular.

    Stated as a test because it looks like a missing check rather than a
    decision, and somebody adding authentication here would break the extension
    with a change that reads like a fix.
    """
    issued = client.post(
        "/api/auth/extension/handoff",
        headers={"authorization": f"Bearer {_access_token(private_key)}"},
        json={"redirect_uri": _redirect_uri()},
    )
    response = client.post("/api/auth/extension/token", json={"code": issued.json()["code"]})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# The redirect target parser, on its own
# ---------------------------------------------------------------------------


def test_the_parser_agrees_with_the_frontends_validation() -> None:
    """`extension_id_for` mirrors `validateRedirectUri` in `ExtensionHandoff.tsx`.

    Both check scheme, host and membership, and both refuse rather than allowing
    an unlisted id through in development. The duplication is deliberate: the
    page's check stops a redirect to an attacker's extension, and the backend's
    stops a caller skipping the page.
    """
    from app.composition.identity_extension import extension_id_for

    allowed = [STAGING_EXTENSION_ID]
    assert extension_id_for(_redirect_uri(), allowed) == STAGING_EXTENSION_ID
    assert extension_id_for(f"chrome-extension://{OTHER_EXTENSION_ID}/x", allowed) is None
    assert extension_id_for(f"https://{STAGING_EXTENSION_ID}/x", allowed) is None
    assert extension_id_for("", allowed) is None
    assert extension_id_for(_redirect_uri(), []) is None
