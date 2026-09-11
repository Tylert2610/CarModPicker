"""Row 10's two routes: the Chrome extension's sign in handoff.

Row 10 of `docs/identity-adoption.md`. The extension stops holding credentials
of its own. It opens the web app's `/extension-handoff` page, the user signs in
there with whatever the deployment offers, and what crosses back to the
extension is a single use, sixty second code that the extension exchanges here
for an access token.

Two routes, both under `/api/auth`, so the existing `ANY /api/auth/{proxy+}`
gateway route already covers both and row 10 adds no route key:

    POST /api/auth/extension/handoff    the web page asks for a code
    POST /api/auth/extension/token      the extension spends it

## Why this is a product module rather than a package one

`webbpulse.identity` 0.16.0 has no extension surface at all, and this is not a
gap in the package so much as a product-shaped problem: the redirect target is a
`chrome-extension://` URL whose id belongs to this product's Chrome Web Store
listing, and the allowlist that names it is a CarModPicker deployment variable.
A package route would have to take all of that as configuration to serve one
consumer.

It is built entirely out of the package's public surface, though. `TokenService`
mints and verifies both tokens, and the `aud`/`typ`/`exp` shape below is the
same one `mint_mfa_ticket` uses for exactly the same reason. Nothing here
reimplements a signature, a key lookup or a claim check.

## The code is a signed token and not a database row

The obvious design is a random string in a table with a TTL, which is what
`identity-tokens` holds for the three purposes M3 and M4 use. This does not use
it, for two reasons, and the second is the decisive one.

`IdentityTokenPurpose` is a closed `Literal["verify_email", "reset_password",
"mfa_ticket"]`. A fourth purpose is a package change, and writing a row with a
purpose outside the type would be a type error here and a row nothing else in
the estate knows how to read.

And a CarModPicker-owned table for this would be a Terraform change, which row
10 is explicitly not. So the code carries its own state: it is an RS256 JWT
signed by the same KMS key the access tokens use, with

    aud = <issuer>/extension    an audience nothing else accepts
    typ = extension_handoff     asserted positively after the signature
    exp = iat + 60              sixty seconds, not the access token's ten minutes

which is the three-part separation `mint_mfa_ticket` documents: a handoff code
presented as a bearer token is refused by the gateway's authorizer, which is
configured with the product's own audience, before any code here sees it.

## What single use means here, which is weaker than a consumed row and is enough

A signed code with no row cannot be marked spent, so a code replayed inside its
sixty seconds mints a second access token. That is a real difference from the
MFA ticket and it is worth being plain about rather than implying a guarantee
this does not provide.

It is acceptable because of what the replay would have to be. The code only ever
exists in two places: the fragment of a `chrome-extension://` redirect, which the
browser gives to the extension that owns that id and to nothing else, and the
body of one HTTPS request. A fragment is never sent to a server and never
reaches an access log. An attacker holding the code already holds the extension's
own channel, and the second access token it could mint is one the first already
gave them.

The sixty seconds is what bounds it. The code is spent by an extension that is
already running and already waiting for it, so the window between mint and
exchange is a round trip, and sixty seconds is generous for that rather than a
budget anything needs.

## What the extension gets, which is an access token and no refresh token

`AuthResult` carries a refresh token too, and this deliberately does not issue
one. The package's `POST /api/auth/refresh` reads the refresh token from the
httpOnly cookie and from nowhere else, and applies a `Sec-Fetch-Site` check on
top. An extension service worker can hold neither: it has no cookie jar for the
API origin unless the manifest grows `host_permissions` plus the `cookies`
permission, which is the wider of the two grants open question 2 in
`docs/identity-adoption.md` puts to the owner and is not row 10's to decide.

So the extension holds an access token for its lifetime and signs in again when
it expires, which is exactly the shape its current bearer token has: the legacy
`/extension-auth` handoff gives it a token that lives until it expires with
nothing to renew it. Row 10 changes where the token comes from, not how long the
extension keeps one. When the owner answers question 2, an extension refresh
family is an additive change to this module and to `src/background.ts`, and
nothing built here has to be taken back out first.

## Who may ask for a code

`POST /extension/handoff` requires a verified access token, read the same two
ways every other authenticated route in this estate reads one: the API Gateway
JWT authorizer's context when the gateway put it there, and the `Authorization`
header verified locally otherwise. That is what proves the asker is the signed in
user rather than a page that merely knows a redirect URI.

`redirect_uri` is validated against `CHROME_EXTENSION_IDS` on top of that,
because the signed in user is not evidence about which extension the code should
go to. The frontend validates the same value before it ever calls this, and both
checks are wanted: the frontend's is what stops the page redirecting to an
attacker's extension, and this one is what stops a caller skipping the page
entirely.

That is the same variable the CORS allow list reads, so an id is trusted by both
or by neither. Unset means the Chrome Web Store build, matching the default on
`Settings.CHROME_EXTENSION_IDS`; explicitly empty means nothing is trusted and
every handoff answers 400.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from fastapi import Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import APIRouter

    from app.core.config import Settings

_log = logging.getLogger(__name__)

#: The `typ` a handoff code carries, asserted positively after the signature.
#: Section 3.2 of the identity standard requires every token to say what it is,
#: and requires the reader to check rather than assume.
HANDOFF_TOKEN_TYPE = "extension_handoff"

#: How long a code is good for. Sixty seconds, because the extension that will
#: spend it is already running and already waiting: the whole window is one
#: redirect and one request. See the module docstring on what single use does
#: and does not mean for a code with no row behind it.
HANDOFF_TTL_SECONDS = 60

#: The environment variable naming the extension ids a code may be issued for.
#:
#: This is `CHROME_EXTENSION_IDS`, the variable the CORS allow list already
#: reads (`Settings.chrome_extension_origins_list`), rather than a new one. The
#: two answer the same question - which builds of our extension is this
#: deployment willing to talk to - and splitting them would let an id be on one
#: list and off the other, which presents as an extension that passes CORS and
#: then cannot sign in, or the reverse. It also means row 10 needs no Terraform
#: and no Lambda environment change: the field already defaults to the Chrome
#: Web Store id, which is `dbglgmnnfandmnacdpibkfggkadjikkg` on staging, the
#: same value `vars.CWS_EXTENSION_ID` renders into the frontend's
#: `VITE_ALLOWED_EXTENSION_IDS`.
#:
#: Read per request from the environment rather than off the `Settings` object
#: captured at composition time, so a test can set it with `monkeypatch.setenv`
#: without rebuilding the router. Nothing here is secret: an extension id is
#: public, printed in the Chrome Web Store URL.
EXTENSION_IDS_ENV = "CHROME_EXTENSION_IDS"

#: What `Settings.CHROME_EXTENSION_IDS` falls back to when the environment does
#: not set it. Duplicated from `app.core.config` rather than imported, so that
#: reading this module does not drag the whole settings object in, and asserted
#: equal to it in `tests/test_identity_row10.py` so the two cannot drift.
DEFAULT_EXTENSION_ID = "dbglgmnnfandmnacdpibkfggkadjikkg"


def allowed_extension_ids(env: dict[str, str] | None = None) -> list[str]:
    """The extension ids this deployment will issue a handoff code for.

    An unset variable means the shipped store extension, matching the default on
    `Settings.CHROME_EXTENSION_IDS`, because the store build is the one every
    deployment serves. An explicitly empty value means none: someone who sets
    the variable to the empty string has said so, and that turns handoff off
    rather than silently re-enabling the default.

    Ids are tolerated with the `chrome-extension://` scheme already on them, the
    same latitude `chrome_extension_origins_list` allows, so one variable can
    feed both readers without a caller having to know which form each wants.
    """
    source = os.environ if env is None else env
    raw = source.get(EXTENSION_IDS_ENV)
    if raw is None:
        raw = DEFAULT_EXTENSION_ID
    ids: list[str] = []
    for candidate in raw.split(","):
        cleaned = candidate.strip()
        if not cleaned:
            continue
        if cleaned.startswith("chrome-extension://"):
            cleaned = cleaned[len("chrome-extension://") :].strip("/")
        if cleaned:
            ids.append(cleaned)
    return ids


def extension_id_for(redirect_uri: str, allowed: list[str]) -> str | None:
    """The extension id `redirect_uri` names, or `None` if it names none we trust.

    Three checks, all of them load bearing. The scheme must be
    `chrome-extension:`, because any other scheme is a redirect off the
    extension entirely and this value ends up in a `Location`-shaped position on
    the page that called us. The host must be non-empty, because that is what
    names the extension. And it must be on the allowlist, because a
    `chrome-extension://` URL is not by itself evidence of anything: anyone can
    write one.

    Mirrors `validateRedirectUri` in `frontend/src/pages/authentication/
    ExtensionHandoff.tsx` deliberately, rather than trusting that the page
    already ran it. The page's check is what stops a redirect to an attacker's
    extension; this one is what stops a caller skipping the page.
    """
    parts = urlsplit(redirect_uri)
    if parts.scheme != "chrome-extension":
        return None
    host = parts.hostname or ""
    if host == "" or host not in allowed:
        return None
    return host


class HandoffRequest(BaseModel):
    """What `ExtensionHandoff.tsx` posts. Matches that page exactly.

    `state` is the extension's own nonce, echoed back to it unchanged in the
    redirect fragment so it can tell the answer to the request it made from an
    unsolicited one. Nothing here reads it or stores it: it round trips through
    the page, not through this route, and is accepted only so that the body the
    page already sends validates.

    At module scope rather than inside `build_router`, which is load bearing and
    not style. This module has `from __future__ import annotations`, so every
    annotation is a string that FastAPI resolves against the **module** globals
    when it builds the route signature. A model defined in a function's local
    scope is not there, so FastAPI cannot tell the parameter is a body, silently
    treats it as a query parameter, and every request answers 422 naming a
    missing query field. It fails identically for the `Request` parameter, which
    is how that presents: two "field required" entries for names that are
    plainly in the signature.
    """

    redirect_uri: str = Field(min_length=1, max_length=2048)
    state: str = Field(default="", max_length=512)


class TokenRequest(BaseModel):
    """What the extension posts to spend a code. See `HandoffRequest` on scope."""

    code: str = Field(min_length=1, max_length=4096)


def build_router(settings: "Settings") -> "APIRouter":
    """The two extension routes, mounted with no prefix of its own.

    Paths are built from `identity_prefix(settings)` exactly as the package's own
    router builds its paths, for the reason `app/composition/identity.py`'s
    module docstring gives at length: the issuer's path is the one source of
    truth for where these routes live, and a second derivation here would be a
    second thing to get wrong. `terraform/identity.tf` renders that issuer as
    `https://<api host>/api/auth`, so these land at `/api/auth/extension/...`.

    The KMS client and the `TokenService` are built once per router rather than
    per request. `TokenService` caches each key's public JWK for the life of the
    execution environment, so a client per request would re-pay session setup to
    arrive at the same cached answer.
    """
    import boto3
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
    from webbpulse.identity import KmsSigner, TokenService, identity_prefix

    from app.composition.identity import build_identity_settings

    identity_settings = build_identity_settings(settings)
    kms_client = boto3.client("kms")
    tokens = TokenService(identity_settings, kms_client)
    # The active signing key, which is the first of the configured ARNs and the
    # same one `TokenService` mints access tokens with. A `KmsSigner` of its own
    # rather than the service's private one: `TokenService` exposes no "sign
    # these arbitrary claims" method, correctly, because every token it knows
    # about has a shape it enforces. This module's code is a fourth shape, so it
    # builds the claims itself and uses the public signer to encode them.
    signer = KmsSigner(kms_client, identity_settings.signing_key_arns[0])
    prefix = identity_prefix(identity_settings)

    #: The audience a handoff code carries: `<issuer>/extension`. An audience
    #: nothing else accepts, which is what makes a code useless as a bearer
    #: token at the gateway, whose authorizer is configured with the product's
    #: own audience. Same construction as `TokenService.mfa_audience`.
    handoff_audience = f"{identity_settings.issuer.rstrip('/')}/extension"

    router = APIRouter()

    def caller_subject(request: Request) -> str:
        """The verified `sub` of whoever is asking, or `""` for nobody.

        Two sources in order, which is the same order and the same reasoning as
        the package's own authenticated routes. The API Gateway authorizer's
        context is preferred where the gateway put it there, because the
        signature is already checked and checking it again is duplicated work on
        a path that runs per request. The `Authorization` header verified locally
        is the fallback, and is the path in a local run, in this repository's
        tests, and in a deployment that has not yet put the authorizer in front
        of `/api/auth` (which row 8 is what changes).

        Returns `""` rather than raising for anything invalid. The caller turns
        that into one 401 whose body says nothing about which of the several
        possible reasons applied: an expired token, a token for another issuer
        and no token at all are all simply "not signed in" to the caller, and
        distinguishing them is a signal handed to somebody probing.
        """
        from webbpulse.identity.claims import ClaimsUnavailable, read_authorizer_claims

        try:
            claims = read_authorizer_claims(request)
        except ClaimsUnavailable:
            claims = None
        if claims is not None:
            subject = str(claims.get("sub", ""))
            if subject:
                return subject

        authorization = request.headers.get("authorization", "")
        scheme, _, presented = authorization.partition(" ")
        if scheme.lower() != "bearer" or not presented:
            return ""
        try:
            verified = tokens.verify_access_token(presented)
        except Exception:
            # Every verification failure is the same answer to the caller. The
            # reason is logged by the token service and is not something to
            # return.
            return ""
        return str(verified.get("sub", ""))

    @router.post(f"{prefix}/extension/handoff")
    async def issue_handoff_code(body: HandoffRequest, request: Request) -> JSONResponse:
        """Mint a sixty second code for a signed in user and a trusted extension.

        Answers exactly `{"code": "..."}` on success, which is the shape
        `ExtensionHandoff.tsx` already reads: it takes `code` off the JSON body
        and puts it in the redirect fragment. That page is the only caller and
        was written against this contract before this route existed, so the body
        is matched to the page rather than the other way round.
        """
        subject = caller_subject(request)
        if not subject:
            return JSONResponse(
                {"detail": {"error_code": "NOT_AUTHENTICATED", "message": "Sign in first."}},
                status_code=401,
            )

        extension_id = extension_id_for(body.redirect_uri, allowed_extension_ids())
        if extension_id is None:
            # Logged at warning with the target, because in a correctly
            # configured deployment this does not happen: the page validates the
            # same value against the same list before it calls. Reaching here
            # means either the two allowlists disagree or something called this
            # route directly, and both are worth seeing.
            _log.warning("extension handoff refused for redirect_uri %r", body.redirect_uri)
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "EXTENSION_NOT_ALLOWED",
                        "message": "That extension is not recognised.",
                    }
                },
                status_code=400,
            )

        issued_at = int(time.time())
        code = signer.encode(
            {
                "iss": identity_settings.issuer,
                "sub": subject,
                "aud": handoff_audience,
                "iat": issued_at,
                "exp": issued_at + HANDOFF_TTL_SECONDS,
                "typ": HANDOFF_TOKEN_TYPE,
                "ext": extension_id,
            }
        )
        _log.info("extension.handoff issued for %s to %s", subject, extension_id)
        return JSONResponse({"code": code})

    @router.post(f"{prefix}/extension/token")
    async def exchange_handoff_code(body: TokenRequest) -> JSONResponse:
        """Exchange a handoff code for an access token.

        Unauthenticated by design: the code **is** the credential, and requiring
        a bearer token to spend it would require the extension to already hold
        the thing it is asking for.

        `typ` is asserted after the signature and audience are checked, not
        before. A `typ` read from an unverified token is a value the attacker
        wrote, so checking it first would be checking their claim rather than
        ours. This is the order `TokenService.verify_mfa_ticket` documents and it
        is the whole reason the check is worth anything: it is what stops an
        access token being presented here and exchanged for a fresh one with a
        reset expiry, which would turn a ten minute token into an unbounded one.
        """
        from webbpulse.identity.service import InvalidToken

        try:
            claims = tokens.verify_access_token(body.code, audience=handoff_audience)
        except InvalidToken as exc:
            _log.info("extension handoff code rejected: %s", exc.reason)
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "HANDOFF_CODE_INVALID",
                        "message": "That sign in has expired. Start again from the extension.",
                    }
                },
                status_code=401,
            )

        if claims.get("typ") != HANDOFF_TOKEN_TYPE:
            _log.warning("extension token exchange refused typ %r", claims.get("typ"))
            return JSONResponse(
                {
                    "detail": {
                        "error_code": "HANDOFF_CODE_INVALID",
                        "message": "That sign in has expired. Start again from the extension.",
                    }
                },
                status_code=401,
            )

        subject = str(claims.get("sub", ""))
        access_token = tokens.mint_access_token(subject)
        _log.info("extension.token issued for %s", subject)
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": int(identity_settings.access_token_ttl.total_seconds()),
            }
        )

    return router
