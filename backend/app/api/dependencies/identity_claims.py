"""Reading the identity access token's claims, in whichever shape this environment delivers them.

Row 11 of `docs/identity-adoption.md`. Row 8 put the identity access token in
front of fifteen `/api/auth` route keys at the gateway; this is the module that
turns a verified token into a CarModPicker user, and since row 13 it is the
only thing `app/api/dependencies/auth.py` calls: the legacy HS256 session that
used to resolve ahead of it no longer exists.

Nothing here mints, and nothing here decides policy. It answers one question,
"which subject is this request for, if any", and answers it with `None` rather
than an exception for every way the answer can be "nobody".

## Three shapes, one reader

The same access token reaches this application through three different paths,
and which one applies is a deployment fact rather than a request fact:

1. **Production, after the promotion.** API Gateway's own JWT authorizer
   verifies the token and puts the claims at
   `requestContext.authorizer.jwt.claims`, as a flat string map. Every value is
   a string there, `exp` included.
2. **Staging today.** Every route carries the staging access gate's REQUEST
   authorizer, and an HTTP API route takes exactly one authorizer, so the gate's
   own Lambda does the verification on the flagged route keys. A Lambda
   authorizer's context always lands under `requestContext.authorizer.lambda`
   and API Gateway refuses a nested object there, so the gate publishes one
   string key literally named `jwt.claims` holding the claims as JSON. The
   values inside it are stringified too, deliberately, so that `exp` reads the
   same way in both environments and no caller needs a branch on which
   environment it is in.
3. **Neither.** Every `/api/v1` route key is an `ANY` over a whole prefix mixing
   public reads with authenticated writes, so none of them is flagged and no
   authorizer claim ever arrives on one. That is the common case today and it is
   why `identity_subject` answers `None` rather than raising: a request with no
   authorizer section is not a failed authorization, it is a route that was
   never configured to carry one.

`webbpulse.identity.claims.read_authorizer_claims` is the package's reader and
it handles shape 1 only: it raises `NoClaimsSection` for a context whose
`authorizer` has `lambda` rather than `jwt`, and its own message says so. So
this module calls it first and falls back to the gate's shape, rather than
parsing the header twice or reimplementing the part the package already owns.
`coerce_claims` is the package's too, and running the gate's JSON through it is
what makes the two shapes produce identical Python values rather than merely
similar ones.

## Why this does not verify a signature, and where verification actually happens

On a flagged route key, the token was verified before this process was invoked,
by the gateway's authorizer in production or by the gate's Lambda in staging.
Verifying it a second time here would be a `kms:GetPublicKey` and a signature
check per request to reach an answer that is already in the event.

On an unflagged route key there is nothing in the event, and the only way to
accept a token there is to verify it in process, which is what
`verify_bearer_subject` does. That path needs `IDENTITY_SIGNING_KEY_ARNS` and a
`kms:GetPublicKey` grant, and **only the identity function has either**:
`terraform/lambda_domains.tf` sets the `IDENTITY_*` block on `identity` and on
no other domain, and `terraform/identity.tf` attaches the signing policy to the
identity role alone. So `verify_bearer_subject` returns `None` on any function
that is not `identity`, and it does that by looking at whether the settings can
be built at all rather than by naming the domain, because the domain a process
serves is not something this module should have to know.

That asymmetry is the honest state of row 11 rather than a gap being papered
over, and `docs/identity-adoption.md`'s row 11 entry says so in the same words:
the `/api/v1` domains accept an identity token when the gateway hands them one,
and until a domain's route keys are flagged or its function is given the signing
key, the gateway hands them none. Row 12 is where that is decided, because
flagging a domain key is what turns an anonymous read into a 401 and that is a
cutover decision rather than a dual-mode one.

## Why a failed verification is indistinguishable from no token

Every path below answers `None`, and the caller turns `None` into a 401. An
expired token, a token for another
audience, a `sub` that resolves to no row and no token at all are one answer to
a caller, because distinguishing them is a signal handed to somebody probing.
The reason is logged; it is not returned.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import Request

__all__ = [
    "GATE_CLAIMS_KEY",
    "identity_claims",
    "identity_subject",
    "verify_bearer_subject",
]

logger = logging.getLogger(__name__)

#: The single context key the staging access gate's Lambda authorizer publishes,
#: holding every claim as JSON. Named `jwt.claims` with a literal dot so that the
#: value sits at `authorizer.lambda["jwt.claims"]` and mirrors the native
#: authorizer's `authorizer.jwt.claims` as closely as a Lambda authorizer can.
#: The gate also lifts `jwt.claims.sub`, `jwt.claims.iss` and `jwt.claims.exp`
#: out as their own keys; this module reads the JSON rather than the lifted
#: subject, so that one code path produces the whole claim set in both
#: environments and a caller that later wants `roles` does not have to add a
#: second reader.
GATE_CLAIMS_KEY = "jwt.claims"


def _gate_claims(request: "Request") -> Optional[dict[str, Any]]:
    """The gate authorizer's claims for this request, or `None`.

    Reached only when the package's reader found no `authorizer.jwt.claims`,
    which in staging is every flagged request. The header is parsed a second
    time rather than threaded out of the package's reader because the package
    raises before it returns anything on this shape, and a parse of a header this
    process already has in memory is cheaper than the alternative of vendoring
    the package's parse to get at its intermediate value.

    Answers `None` for every failure and logs the ones worth seeing. An
    unparseable `jwt.claims` is worth seeing because the gate writes it with
    `JSON.stringify` and nothing else writes it at all, so a value that does not
    parse means the two sides disagree about the encoding, which is the exact
    failure `webbpulse.identity.claims` was written to stop being silent.
    """
    from webbpulse.http import REQUEST_CONTEXT_HEADER

    raw = request.headers.get(REQUEST_CONTEXT_HEADER)
    if raw is None or not raw.strip():
        return None
    try:
        context = json.loads(raw)
    except ValueError:
        # The package's reader has already logged and raised on this, so it is
        # debug here rather than a second warning for one header.
        logger.debug("The %s header is not JSON.", REQUEST_CONTEXT_HEADER)
        return None
    if not isinstance(context, Mapping):
        return None

    authorizer = context.get("authorizer")
    if not isinstance(authorizer, Mapping):
        return None
    lambda_context = authorizer.get("lambda")
    if not isinstance(lambda_context, Mapping):
        return None
    encoded = lambda_context.get(GATE_CLAIMS_KEY)
    if not isinstance(encoded, str) or not encoded.strip():
        # A gate authorizer that ran and allowed the request on a route key that
        # is not flagged publishes no claims at all, which is the ordinary state
        # of every `/api/v1` request in staging today and not worth a log line.
        return None
    try:
        claims = json.loads(encoded)
    except ValueError:
        logger.warning(
            "The staging access gate published a %r context value that is not JSON. "
            "The gate writes it with JSON.stringify, so this means the two sides "
            "disagree about the encoding rather than that the token was bad.",
            GATE_CLAIMS_KEY,
        )
        return None
    if not isinstance(claims, Mapping):
        return None
    return dict(claims)


def identity_claims(request: "Request") -> Optional[Mapping[str, Any]]:
    """The verified identity claims for this request, or `None` for none.

    Tries the native authorizer's shape through the package's own reader first,
    then the staging gate's. Both results go through `coerce_claims`, the
    package's own coercion, so `exp` is an `int` and `roles` is a `list[str]`
    whichever environment produced them: the gate stringifies every value on
    purpose so that exactly this is possible.

    `None` means no authorizer ran for this route, which is not the same thing as
    a refused request. See the module docstring.
    """
    from webbpulse.identity.claims import (
        AuthorizerClaims,
        ClaimsUnavailable,
        coerce_claims,
    )

    try:
        return AuthorizerClaims(dict(_read_native(request)))
    except ClaimsUnavailable:
        pass
    gate = _gate_claims(request)
    if gate is None:
        return None
    return coerce_claims(gate)


def _read_native(request: "Request") -> Mapping[str, Any]:
    """The package's reader, isolated so `identity_claims` reads as two attempts."""
    from webbpulse.identity.claims import read_authorizer_claims

    return read_authorizer_claims(request)


def identity_subject(request: "Request") -> str:
    """The verified `sub` the authorizer put on this request, or `""`.

    `sub` is the CarModPicker user id, as a string. `CarModPickerIdentityHooks.
    claims_for` puts nothing else there and `load_user_by_id` parses it straight
    back to a `UUID`, so the mapping from a token to a row is the id and there is
    no link table between them.
    """
    claims = identity_claims(request)
    if claims is None:
        return ""
    return str(claims.get("sub", "") or "")


def verify_bearer_subject(request: "Request") -> str:
    """The `sub` of a Bearer identity token verified in this process, or `""`.

    The fallback for a route the gateway put no claims on. It is a real
    verification: signature, issuer, audience and expiry, through
    `TokenService.verify_access_token`, which is the same call
    `app/composition/identity_extension.py` makes for the same reason.

    **It answers `""` on any function that is not `identity`, and that is a
    deployment fact rather than a code path being skipped.** `TokenService`
    resolves a signing key's public JWK with `kms:GetPublicKey` against the ARNs
    in `IDENTITY_SIGNING_KEY_ARNS`, and `terraform/lambda_domains.tf` sets that
    variable on the identity function alone while `terraform/identity.tf`
    attaches the `identity-signing` policy to the identity role alone. A
    `catalog` or `build-lists` function has neither, so building the settings
    raises and this returns `""` rather than a 500 on every request that carried
    a token it could never have checked.

    `settings.IDENTITY_ISSUER` is the cheap question asked first, exactly as
    `app/composition/wiring.py` asks it: it is required by `IdentitySettings`
    and set only where the rest of the block is, so its emptiness is the same
    answer as a `ValidationError` without paying for one.
    """
    from app.core.config import settings

    if not settings.IDENTITY_ISSUER.strip():
        return ""

    authorization = request.headers.get("authorization", "")
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented.strip():
        return ""

    service = _token_service()
    if service is None:
        return ""
    try:
        claims = service.verify_access_token(presented.strip())
    except Exception:
        # Every verification failure is one answer to the caller. Debug rather
        # than warning: a failure here is an expired, malformed or foreign token
        # on a request that is about to get the same 401 as a request carrying
        # nothing, and the caller is told no more than that. The reason is
        # logged; it is not returned.
        logger.debug("An identity access token did not verify.", exc_info=True)
        return ""
    return str(claims.get("sub", "") or "")


#: The process's `TokenService`, built once. `TokenService` caches each signing
#: key's public JWK for the life of the execution environment, so a service per
#: request would re-pay boto3 session setup and a `kms:GetPublicKey` to arrive at
#: the same cached answer. A module global rather than an `lru_cache` so that
#: `reset_token_service` can clear it for a test that changes the environment.
_token_service_cache: Optional[Any] = None
_token_service_failed = False


def _token_service() -> Optional[Any]:
    """The shared `TokenService`, or `None` where one cannot be built.

    A failure is remembered. On a function with no `IDENTITY_*` block the
    settings raise, and retrying that per request would be a pydantic validation
    on the hot path of every authenticated request forever.
    """
    global _token_service_cache, _token_service_failed

    if _token_service_cache is not None:
        return _token_service_cache
    if _token_service_failed:
        return None
    try:
        import boto3
        from webbpulse.identity import TokenService

        from app.composition.identity import build_identity_settings
        from app.core.config import settings as app_settings

        identity_settings = build_identity_settings(app_settings)
        _token_service_cache = TokenService(identity_settings, boto3.client("kms"))
    except Exception:
        _token_service_failed = True
        logger.debug(
            "No identity TokenService on this function, so a Bearer identity token cannot "
            "be verified in process here. Expected on every domain but `identity`.",
            exc_info=True,
        )
        return None
    return _token_service_cache


def reset_token_service() -> None:
    """Drop the memoised `TokenService`. For tests that change the environment."""
    global _token_service_cache, _token_service_failed

    _token_service_cache = None
    _token_service_failed = False
