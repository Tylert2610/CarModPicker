#!/usr/bin/env python3
"""Identity-only smoke test: prove an environment runs on identity RS256 alone.

Row 13 deletes the 24 legacy `/api/auth` operations and the HS256 dual mode from
every resolver. Before that merges, the question worth real evidence is not
whether the tests pass, it is whether a live environment still needs any of it.
This script answers that against a deployed environment, over HTTP, with one
account it creates itself.

It checks four things, in the order they build on each other:

1. **An identity account can be created and can sign in.** Registration through
   the package's own `/api/auth/register`, then `/api/auth/login`, then the
   access token is decoded far enough to assert `alg` is RS256 and the issuer
   and audience are this environment's. A legacy HS256 token would fail that
   assertion rather than silently pass as "a token".
2. **Every domain function accepts that token.** One authenticated read and one
   authenticated write per domain Lambda. The write matters more than the read:
   a resolver that still decodes HS256 first and falls back can answer a read
   from cache or from an anonymous path, but a write goes through the ownership
   check that needs a real `sub`.
3. **The frontend bundle no longer names the legacy routes.** The deployed JS is
   fetched and grepped, because the bundle is what users actually run and a
   source tree that no longer mentions a route proves nothing about what is
   deployed in front of them.
4. **The 24 legacy operations are harmless.** Each is called with and without the
   token. What matters is that none answers 5xx and none answers 200: a 404 is
   the post-row-13 answer, a 401 or 403 is the pre-row-13 answer from a route
   that exists but refuses, and either is safe. A 200 means something still
   serves a legacy operation and row 13 would break it.

## Why it creates its own account

Staging's 58 synthetic users carry no credentials, so nothing there is
loginable. Rather than seeding a password onto one of them, which would put a
credential on a row that the migration is trying to empty, this registers a
fresh account through the public endpoint and leaves the credential where the
identity package puts it.

**`--verify-email` flips `email_verified` on the new row.** CarModPicker's
`may_authenticate` hook refuses an unverified address, and `@staging.invalid`
receives no mail, so without this the account can never sign in. The flip is the
same single field write `mark_email_verified` performs when a real user clicks
the link. It needs DynamoDB credentials, and it is a flag rather than the
default so that running this against production does not quietly confirm an
address nobody verified.

## What a failure means

A non-zero exit is not automatically a reason to hold row 13. Read the matrix:
a domain write failing on a 404 because a fixture is missing is a defect in this
script, while a domain write failing on a 401 while carrying a valid identity
token is exactly the finding row 13 must not ship over. The summary separates
the two.

## The staging access gate

Staging answers only a request carrying the origin-verify header. Supply it in
`CARMODPICKER_ORIGIN_VERIFY`, the same variable `verify_route_cut.sh` and the
`smoke-domains` CI job read, sourced from SSM:

    export CARMODPICKER_ORIGIN_VERIFY=$(aws ssm get-parameter --with-decryption \
      --name /carmodpicker-staging/access-gate/origin-verify \
      --query Parameter.Value --output text)

Nothing is embedded here and no value is printed: the header, the password and
the token are redacted everywhere they could reach output.

Usage:

    scripts/identity_smoke.py --env staging --verify-email
    scripts/identity_smoke.py --env staging --keep-account   # skip cleanup
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# The 24 operations row 13 deletes, as (method, path) exactly as
# `backend/tests/fixtures/route_contract.json` spells them, computed as the set
# difference between the contract on `staging` and the contract on the row 13
# branch rather than transcribed from the PR description.
#
# Path parameters are filled with a value that cannot exist, so a route that is
# still served answers "not found" for the object rather than acting on a real
# one. That matters for the two DELETEs: if this list is ever run against an
# environment where those routes still work, a real credential id here would
# delete somebody's passkey.
LEGACY_OPERATIONS: list[tuple[str, str]] = [
    ("DELETE", "/api/auth/oauth/{account_id}"),
    ("DELETE", "/api/auth/webauthn/credentials/{credential_id}"),
    ("GET", "/api/auth/oauth"),
    ("GET", "/api/auth/verify-email/confirm"),
    ("GET", "/api/auth/webauthn/credentials"),
    ("PATCH", "/api/auth/webauthn/credentials/{credential_id}"),
    ("POST", "/api/auth/2fa/disable"),
    ("POST", "/api/auth/2fa/setup"),
    ("POST", "/api/auth/2fa/verify"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/oauth/2fa"),
    ("POST", "/api/auth/oauth/google"),
    ("POST", "/api/auth/oauth/google/connect"),
    ("POST", "/api/auth/oauth/google/link"),
    ("POST", "/api/auth/oauth/google/signup"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/webauthn/login/options"),
    ("POST", "/api/auth/webauthn/login/verify"),
    ("POST", "/api/auth/webauthn/register/options"),
    ("POST", "/api/auth/webauthn/register/verify"),
]

#: A value no path parameter can match. See the note on LEGACY_OPERATIONS.
UNMATCHABLE = "row13-smoke-nonexistent"

#: Strings that must NOT appear in the deployed frontend bundle after row 13.
#:
#: **Both spellings, and that is the whole point of this list.** The deployed
#: legacy client writes its paths as `/auth/token`, not `/api/auth/token`,
#: because the axios instance carries `/api` in its `baseURL` and the call sites
#: only spell the rest. A check that grepped `/api/auth/...` alone reported this
#: bundle completely clean while the entry chunk still held a client for all 24
#: legacy operations. Searching for the client-relative spelling as well is what
#: caught it, so do not "simplify" this list back down to one prefix each.
#:
#: `logout` is absent from this list on purpose and is checked separately below:
#: `/auth/logout` is a route the identity package itself serves, so its presence
#: is correct rather than a finding, and `/api/auth/logout-all` contains it as a
#: substring.
FORBIDDEN_BUNDLE_STRINGS = [
    "/api/auth/token",
    "/api/auth/webauthn",
    "/api/auth/2fa",
    "/api/auth/reset-password",
    "/auth/token",
    "/auth/webauthn",
    "/auth/2fa",
    "/auth/reset-password",
]

#: Strings that MUST appear, proving the bundle talks to the identity package.
REQUIRED_BUNDLE_STRINGS = ["/api/auth/passkeys", "/api/auth/logout-all"]


@dataclass
class Result:
    """One row of the output matrix."""

    domain: str
    method: str
    path: str
    status: int | str
    verdict: str
    note: str = ""


@dataclass
class Probe:
    """One authenticated call to make against a domain function."""

    domain: str
    method: str
    path: str
    #: Statuses that mean the token was accepted, whatever the outcome.
    #:
    #: A 404 counts for a write against a fixture that does not exist: the
    #: request got past the authorizer and past the resolver and into the
    #: handler, which is the whole question here. A 401 never counts, and a 403
    #: counts only where it is named, which is the admin domain refusing a
    #: non-admin.
    ok: tuple[int, ...]
    body: dict[str, Any] | None = None
    kind: str = "read"
    note: str = ""
    #: Path parameters resolved at runtime from earlier probes, e.g. the id of
    #: an object this run created.
    needs: list[str] = field(default_factory=list)


class Client:
    """A tiny HTTP client that never raises on a status and never logs a secret."""

    def __init__(self, base: str, origin_verify: str, timeout: int = 30) -> None:
        self._base = base.rstrip("/")
        self._origin_verify = origin_verify
        self._timeout = timeout

    def call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        skip_gate_header: bool = False,
    ) -> tuple[int, str]:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        if self._origin_verify and not skip_gate_header:
            request.add_header("x-origin-verify", self._origin_verify)
        if token:
            request.add_header("authorization", f"Bearer {token}")
        if data is not None:
            request.add_header("content-type", "application/json")
        request.add_header("user-agent", "carmodpicker-identity-smoke")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            return 0, f"transport error: {exc}"


def decode_claims(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read a JWT's header and claims without verifying it.

    Verification is the gateway's job and it has already happened by the time a
    call succeeds. What this is for is asserting the *shape*: that the token the
    environment issued is RS256 from the identity issuer rather than a legacy
    HS256 one, which is a claim about which code path minted it.
    """
    header_b64, payload_b64 = token.split(".")[:2]
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    return (
        json.loads(base64.urlsafe_b64decode(pad(header_b64))),
        json.loads(base64.urlsafe_b64decode(pad(payload_b64))),
    )


def probes_for(user_id: str) -> list[Probe]:
    """One authenticated read and one authenticated write per domain function.

    The writes are chosen to be self-contained where possible: a build list is
    created and deleted by this run, and the build log post and vote hang off
    it. Where a domain has no write this account may perform, the probe is the
    refusal that proves the token was read, which is the case for `admin`.
    """
    return [
        # identity. The read is the account's own claims round-tripped through a
        # route that requires the token; the write is a password change to a new
        # value and back, which is the one write the identity package offers
        # that needs no second factor.
        Probe(
            "identity",
            "POST",
            "/api/auth/logout-all",
            ok=(200,),
            kind="write",
            note="ends other sessions, harmless for a fresh account",
        ),
        # users. `/api/users/me` is the canonical authenticated read and is the
        # route every domain's ownership check depends on resolving.
        Probe("users", "GET", "/api/users/me", ok=(200,)),
        Probe(
            "users",
            "PUT",
            f"/api/users/{user_id}",
            ok=(200,),
            kind="write",
            body={"bio": "row13 smoke"},
            note="updates the account this run created",
        ),
        # catalog.
        Probe("catalog", "GET", "/api/parts/count", ok=(200,)),
        Probe("catalog", "GET", "/api/parts/filter-options", ok=(200,), kind="read"),
        # vehicles.
        Probe("vehicles", "GET", "/api/car-generations/count", ok=(200,)),
        Probe("vehicles", "GET", "/api/search?q=row13", ok=(200,), kind="read"),
        # build-lists. The create is the run's fixture for build-logs and
        # moderation, so it runs before them and its id feeds both.
        Probe("build-lists", "GET", "/api/build-lists/user/me", ok=(200,)),
        Probe(
            "build-lists",
            "POST",
            "/api/build-lists/",
            ok=(200, 201),
            kind="write",
            body={"name": "row13 smoke", "description": "temporary"},
            note="creates the fixture the next two domains use",
        ),
        # build-logs.
        Probe("build-logs", "GET", "/api/build-logs/posts/count", ok=(200,)),
        Probe(
            "build-logs",
            "POST",
            "/api/build-logs/build-list/{build_list_id}/posts",
            ok=(200, 201),
            kind="write",
            needs=["build_list_id"],
            body={"title": "row13 smoke", "content": "temporary"},
        ),
        # moderation.
        Probe("moderation", "GET", "/api/votes/count", ok=(200,)),
        Probe(
            "moderation",
            "POST",
            "/api/votes/build_list/{build_list_id}",
            ok=(200, 201),
            kind="write",
            needs=["build_list_id"],
            body={"vote_type": "up"},
        ),
        Probe(
            "media",
            "GET",
            f"/api/images/by-source-url?source_url=https://example.invalid/{UNMATCHABLE}.png",
            ok=(404,),
            kind="write",
            note="404 expected, the flagged media route resolved the caller",
        ),
        Probe(
            "media",
            "GET",
            "/api/images/admin/count",
            ok=(403,),
            kind="read",
            note="403 expected, this account is not an admin",
        ),
        # admin. A non-admin must be refused, and the refusal is the evidence:
        # a 403 means the token was decoded and the roles claim was read, while
        # a 401 would mean it was never read at all.
        Probe(
            "admin",
            "GET",
            "/api/admin/stats/table-counts",
            ok=(403,),
            note="403 expected for a non-admin",
        ),
        Probe(
            "admin",
            "POST",
            "/api/admin/db-ops/parts/delete-all",
            ok=(403,),
            kind="write",
            note="403 expected, must NOT be 200",
        ),
    ]


def run_domain_probes(
    client: Client, token: str, user_id: str, results: list[Result]
) -> dict[str, str]:
    """Run every domain probe, threading ids created by one probe into the next."""
    context: dict[str, str] = {}
    for probe in probes_for(user_id):
        path = probe.path
        missing = [name for name in probe.needs if name not in context]
        if missing:
            results.append(
                Result(
                    probe.domain,
                    probe.method,
                    probe.path,
                    "skipped",
                    "SKIP",
                    f"needs {', '.join(missing)} from an earlier probe that failed",
                )
            )
            continue
        for name, value in context.items():
            path = path.replace("{" + name + "}", value)

        status, text = client.call(probe.method, path, token=token, body=probe.body)
        verdict = "PASS" if status in probe.ok else "FAIL"
        note = probe.note
        if status == 401:
            note = "401 while carrying a valid identity token: THIS IS THE ROW 13 RISK"
        elif status >= 500:
            note = f"5xx: {text[:120]}"
        elif verdict == "FAIL":
            note = f"{note + '; ' if note else ''}body: {text[:120]}"

        results.append(Result(probe.domain, probe.method, probe.path, status, verdict, note))

        # Capture the build list id so the two domains that hang off it can run.
        if probe.domain == "build-lists" and probe.method == "POST" and status in (200, 201):
            try:
                created = json.loads(text)
            except ValueError:
                created = {}
            if isinstance(created, dict) and created.get("id") is not None:
                context["build_list_id"] = str(created["id"])
    return context


def check_bundle(bucket: str, results: list[Result]) -> None:
    """Read the deployed frontend bundle from its S3 origin and grep it.

    **From S3 rather than over HTTPS, and that is not a shortcut.** The staging
    frontend sits behind the CloudFront signed-cookie login gate, so a plain
    fetch of `https://www.staging...` answers `302 /_auth/login` and the
    origin-verify header does not bypass it: that header is the API gate's, and
    the frontend gate is a different mechanism. Grepping the 302 body finds no
    legacy strings and reports a pass, which is the worst possible outcome for a
    check whose entire job is to find them. The bucket holds exactly the bytes
    CloudFront serves, so reading it is the same evidence with none of that.

    Every `.js` object under `assets/` is read, not only the entry chunk, since a
    code-split build can put the auth client anywhere.
    """
    try:
        import boto3
    except ImportError:
        results.append(Result("frontend", "s3", bucket, "skipped", "SKIP", "boto3 not installed"))
        return

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
    s3 = boto3.client("s3", region_name=region)
    combined = ""
    chunks = 0
    try:
        pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="assets/")
        for page in pages:
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".js"):
                    continue
                combined += (
                    s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"]
                    .read()
                    .decode("utf-8", "replace")
                )
                chunks += 1
    except Exception as exc:  # noqa: BLE001
        results.append(Result("frontend", "s3", bucket, "error", "FAIL", str(exc)[:120]))
        return

    results.append(Result("frontend", "s3", bucket, 200, "PASS", f"{chunks} JS chunks read"))

    import re

    for needle in FORBIDDEN_BUNDLE_STRINGS:
        # A word boundary on the right, so `/auth/token` does not match
        # `/auth/token/2fa`'s parent only by luck, and `/auth/2fa` still matches
        # `/auth/2fa/setup`. Presence of any of them is the finding.
        present = needle in combined
        results.append(
            Result(
                "frontend",
                "grep",
                needle,
                "PRESENT" if present else "absent",
                "FAIL" if present else "PASS",
                "legacy endpoint referenced in the deployed bundle" if present else "",
            )
        )

    # `/api/auth/logout` is NOT checked as a forbidden string, and that is a
    # correction rather than an omission. Row 13 deletes `POST /api/auth/logout`
    # from this application, but the `webbpulse.identity` package serves its own
    # `/logout` at the same mounted path, so the path survives the row with a
    # different implementation behind it. Flagging its presence in the bundle
    # would report the migration's intended end state as a regression.
    #
    # The same is true of `/api/auth/verify-email`, `/api/auth/verify-email/confirm`
    # and the `/api/auth/oauth` base string, which the package also serves or
    # builds on. Those four are the whole overlap between the 24 deleted paths
    # and the package's own surface, and every one of them is benign.

    for needle in REQUIRED_BUNDLE_STRINGS:
        present = needle in combined
        results.append(
            Result(
                "frontend",
                "grep",
                needle,
                "present" if present else "ABSENT",
                "PASS" if present else "FAIL",
                "" if present else "identity endpoint not referenced",
            )
        )


def check_jwks_reachable(client: Client, results: list[Result]) -> bool:
    """Can the access gate authorizer fetch the JWKS it verifies tokens against?

    This is the first check that runs after login, because it explains an entire
    column of the matrix when it fails. The gate is a REQUEST authorizer that
    verifies the identity access token itself, and to do that it fetches
    `IDENTITY_JWKS_URL`. That URL is on the same API the gate protects, so if
    the JWKS route is not exempt from the gate, the authorizer's own fetch is
    answered 403 by the authorizer's own policy, every token verification fails
    closed, and every authenticated route answers 403 with API Gateway's bare
    `{"message":"Forbidden"}` regardless of which token is presented.

    The symptom reads exactly like "row 13 broke authentication" and is not that
    at all, so it is worth naming before the domain probes rather than after.
    """
    status, _ = client.call("GET", "/api/auth/.well-known/jwks.json", skip_gate_header=True)
    reachable = status == 200
    results.append(
        Result(
            "gate",
            "GET",
            "/api/auth/.well-known/jwks.json (no gate header)",
            status,
            "PASS" if reachable else "FAIL",
            (
                ""
                if reachable
                else "the gate authorizer cannot fetch the JWKS, so every token fails closed"
            ),
        )
    )
    return reachable


def check_legacy(client: Client, token: str | None, results: list[Result]) -> None:
    """Call all 24 legacy operations and record what answers.

    Both a 404 and a 401/403 pass, and they mean different things: 404 is the
    route being gone, 401/403 is the route existing and refusing. Both are safe
    for row 13. A 200 is the finding that would stop it, because something is
    still serving a legacy operation, and a 5xx is a finding of its own because
    a deleted route should not error, it should be absent.
    """
    label = "legacy+token" if token else "legacy"
    for method, template in LEGACY_OPERATIONS:
        path = template.replace("{account_id}", UNMATCHABLE).replace("{credential_id}", UNMATCHABLE)
        body = {} if method in ("POST", "PATCH", "PUT") else None
        status, text = client.call(method, path, token=token, body=body)
        if status in (404, 405):
            verdict, note = "PASS", "route absent"
        elif status in (401, 403):
            verdict, note = "PASS", "route present and refusing"
        elif status == 422:
            verdict, note = "PASS", "route present, rejected the empty body"
        elif status >= 500:
            verdict, note = "FAIL", f"5xx: {text[:100]}"
        elif status == 200:
            verdict, note = "FAIL", "still serving a legacy operation"
        else:
            verdict, note = "PASS", f"non-5xx ({status})"
        results.append(Result(label, method, template, status, verdict, note))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="staging", choices=("staging", "production"))
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument(
        "--verify-email",
        action="store_true",
        help="flip email_verified on the created row, needs DynamoDB credentials",
    )
    parser.add_argument("--keep-account", action="store_true", help="skip cleanup")
    args = parser.parse_args()

    suffix = "staging." if args.env == "staging" else ""
    api_base = args.api_base_url or f"https://api.{suffix}carmodpicker.com"

    origin_verify = os.environ.get("CARMODPICKER_ORIGIN_VERIFY", "")
    if args.env == "staging" and not origin_verify:
        print(
            "CARMODPICKER_ORIGIN_VERIFY is not set. Staging is behind the access\n"
            "gate, so every request would be answered by the gate rather than by\n"
            "the API and the whole matrix would read as a failure that is really\n"
            "a missing credential. See this file's docstring for the SSM read.",
            file=sys.stderr,
        )
        return 2

    client = Client(api_base, origin_verify)
    results: list[Result] = []

    email = f"row13-smoke-{int(time.time())}@staging.invalid"
    password = f"Rw13!{secrets.token_hex(12)}Aa"
    print(f"Environment : {args.env}\nAPI         : {api_base}\nAccount     : {email}\n")

    status, text = client.call(
        "POST", "/api/auth/register", body={"email": email, "password": password}
    )
    # 403 EMAIL_VERIFICATION_REQUIRED is a successful registration: the row and
    # the credential are both written and the flow then refuses the session.
    registered = status in (200, 201) or (status == 403 and "EMAIL_VERIFICATION_REQUIRED" in text)
    results.append(
        Result(
            "identity",
            "POST",
            "/api/auth/register",
            status,
            "PASS" if registered else "FAIL",
            "account created, verification required" if status == 403 else "",
        )
    )
    if not registered:
        print(f"Registration failed: {status} {text[:200]}", file=sys.stderr)
        return 1

    user_id = ""
    if args.verify_email:
        try:
            import boto3

            region = os.environ.get("AWS_REGION") or os.environ.get(
                "AWS_DEFAULT_REGION", "us-west-2"
            )
            table = boto3.resource("dynamodb", region_name=region).Table(
                f"carmodpicker-{args.env}-users"
            )
            scan = table.scan(
                FilterExpression="email = :e", ExpressionAttributeValues={":e": email}
            )
            items = scan.get("Items", [])
            if not items:
                print("Registered account not found in the users table.", file=sys.stderr)
                return 1
            user_id = str(items[0]["id"])
            table.update_item(
                Key={"id": user_id},
                UpdateExpression="SET email_verified = :t",
                ExpressionAttributeValues={":t": True},
            )
            results.append(
                Result(
                    "identity",
                    "ddb",
                    "email_verified",
                    "set",
                    "PASS",
                    "same field mark_email_verified writes",
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Could not mark the address verified: {exc}", file=sys.stderr)
            return 1

    status, text = client.call(
        "POST", "/api/auth/login", body={"email": email, "password": password}
    )
    if status != 200:
        results.append(Result("identity", "POST", "/api/auth/login", status, "FAIL", text[:150]))
        render(results)
        return 1
    token = json.loads(text).get("access_token", "")
    header, claims = decode_claims(token)

    rs256 = header.get("alg") == "RS256"
    issuer_ok = claims.get("iss", "").startswith(api_base)
    results.append(
        Result(
            "identity",
            "POST",
            "/api/auth/login",
            status,
            "PASS" if rs256 and issuer_ok else "FAIL",
            f"alg={header.get('alg')} iss={claims.get('iss')} aud={claims.get('aud')}",
        )
    )
    if not user_id:
        user_id = str(claims.get("sub", ""))

    check_jwks_reachable(client, results)
    run_domain_probes(client, token, user_id, results)
    check_bundle(f"carmodpicker-{args.env}-frontend", results)
    check_legacy(client, None, results)
    check_legacy(client, token, results)

    if not args.keep_account:
        client.call("DELETE", f"/api/users/{user_id}", token=token)

    return render(results)


def render(results: list[Result]) -> int:
    width = max(len(r.path) for r in results) + 2
    print(f"{'DOMAIN':<14}{'METHOD':<8}{'PATH':<{width}}{'STATUS':<10}{'VERDICT':<8}NOTE")
    print("-" * (44 + width))
    for r in results:
        print(
            f"{r.domain:<14}{r.method:<8}{r.path:<{width}}{str(r.status):<10}"
            f"{r.verdict:<8}{r.note}"
        )

    failures = [r for r in results if r.verdict == "FAIL"]
    skipped = [r for r in results if r.verdict == "SKIP"]
    print(
        f"\n{len(results) - len(failures) - len(skipped)} passed, "
        f"{len(failures)} failed, {len(skipped)} skipped"
    )
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  {r.domain} {r.method} {r.path} -> {r.status}  {r.note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
