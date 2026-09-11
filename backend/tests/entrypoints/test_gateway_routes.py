"""Row 12: the domain route keys that require an authenticated caller.

`terraform/apigateway.tf` names 80 route keys in
`local.domain_identity_jwt_route_paths`, one per `/api` route outside
`/api/auth` whose FastAPI dependency tree reaches a resolver that refuses an
anonymous caller. That list is a second spelling of something the application
already knows, and the two can drift in the direction that matters: a route
added to a router with `get_current_user` on it and not added to the Terraform
is a route the gateway never checks, and nothing about it looks wrong from
either side on its own.

So this file recomputes the set from the application and asserts it is exactly
the set the Terraform names. **The set is derived, never listed here.** There is
no constant in this file enumerating the 80 keys, because a constant is a third
copy that drifts from both. Portfolio's `test_gateway_routes.py` is the
cautionary case: it subtracted one hand written constant per identity milestone,
so a milestone nobody remembered to add was asserted in neither direction, and
two of them shipped to staging with no route keys at all and answered the
gateway's own 404. The assertion that does not have that shape is the one that
builds the real application and compares against it, which is what every test
below does.

## What counts as requiring a caller

Three resolvers in `app/api/dependencies/auth.py`, and the distinction is the
whole subject of this row:

- `get_current_user`, `get_current_admin_user` and `get_current_superuser` raise
  401 when they cannot resolve a caller. A route behind one of them is already
  closed inside the function, and a flagged route key states the same thing one
  hop earlier at the gateway.
- `get_optional_current_user` and `get_current_active_user_optional` return
  `None` instead. A route behind one of those serves anonymous callers, usually
  personalising its answer when a caller is signed in, so flagging its key would
  turn a public page into a 401 for every signed out visitor. These are the trap
  in this row: the two resolvers are one word apart in a router and a route key
  cannot tell them apart.
- `require_api_key_or_admin` accepts a shared `X-API-Key` with no bearer token
  at all. Its one route is the Chrome extension's price history ingest, and
  flagging it would lock out the only callers it has.

## Why the Terraform is parsed rather than planned

The same reason `test_route_split.py` reads it: the keys are static text, and a
regex over them compares two sets of strings with no credentials, no workspace
and no network. A plan would assert the same thing and could not run in CI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, Set, Tuple

BACKEND = Path(__file__).resolve().parents[2]
APIGATEWAY_TF = BACKEND.parent / "terraform" / "apigateway.tf"

#: The resolvers that refuse an anonymous caller. A route whose dependency tree
#: reaches one of these needs a flagged route key.
REQUIRES_CALLER = {
    "get_current_user",
    "get_current_admin_user",
    "get_current_superuser",
}

#: The resolvers that tolerate one. Named so the test can assert the separation
#: explicitly rather than only by absence, because "not in the required set" and
#: "known to be optional" are different claims and only the second one catches a
#: resolver that was renamed.
TOLERATES_ANONYMOUS = {
    "get_optional_current_user",
    "get_current_active_user_optional",
    "require_api_key_or_admin",
}

#: `/api/auth` is the `identity` domain, and row 8 owns every key under it.
#: CarModPicker's own 12 legacy auth routes live there too and row 13 retires
#: them with the legacy session; neither set is this row's business.
IDENTITY_PREFIX = "/api/auth"

#: Routes that belong to no domain, served locally by every function.
ROOT_PATHS = {
    "/",
    "/health",
    "/ready",
    "/sitemap.xml",
    "/sitemap-{name}.xml",
}

#: `"<METHOD> <path>" = {` inside a `domain = [ ... ]` list, which is how
#: `local.domain_identity_jwt_route_paths` is written: a map of domain name to a
#: list of route keys.
DOMAIN_LIST = re.compile(
    r'^\s*"?(?P<domain>[a-z][a-z-]*)"?\s*=\s*\[(?P<body>[^\]]*)\]',
    re.MULTILINE,
)

#: `"<METHOD> <path>" = { integration = "<name>" }`, the shape the two anonymous
#: guard keys are written in.
GUARD_ENTRY = re.compile(
    r'"(?P<key>(?:ANY|GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /[^"]*)"\s*='
    r'\s*\{\s*integration\s*=\s*"(?P<integration>[^"]+)"\s*\}'
)


def _terraform_source() -> str:
    return APIGATEWAY_TF.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """The file with whole-line `#` comments removed.

    `apigateway.tf` carries a great deal of narrative, and this row's own
    comment block quotes route keys in prose to explain why some of them are
    written the way they are. A regex over the raw file would read those quoted
    keys as configuration. Only whole-line comments are stripped, which is every
    comment in that file.
    """
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))


def _block(source: str, name: str) -> str:
    """The text of the `name = { ... }` local, by brace balance.

    Taken by counting braces rather than by regex, because the value contains
    nested braces in both directions: `{proxy+}` and `{user_id}` inside route
    keys, and the `{ integration = ... }` objects themselves.
    """
    start = source.index(f"{name} = {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"local.{name} is not brace balanced in {APIGATEWAY_TF}")


def terraform_domain_route_keys() -> Dict[str, str]:
    """Every route key in `local.domain_identity_jwt_route_paths`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "domain_identity_jwt_route_paths")
    out: Dict[str, str] = {}
    for match in DOMAIN_LIST.finditer(block):
        domain = match.group("domain")
        for key in re.findall(r'"([^"]+)"', match.group("body")):
            assert key not in out, f"{key} is written twice in local.domain_identity_jwt_route_paths"
            out[key] = domain
    return out


def terraform_guard_route_keys() -> Dict[str, str]:
    """Every route key in `local.domain_anonymous_guard_route_keys`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "domain_anonymous_guard_route_keys")
    return {match.group("key"): match.group("integration") for match in GUARD_ENTRY.finditer(block)}


def terraform_domain_prefixes() -> Dict[str, str]:
    """Each `/api` prefix in `local.lambda_domain_path_prefixes`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "lambda_domain_path_prefixes")
    out: Dict[str, str] = {}
    for match in DOMAIN_LIST.finditer(block):
        for prefix in re.findall(r'"([^"]+)"', match.group("body")):
            out[prefix] = match.group("domain")
    return out


def _effective_routes(app: object) -> Iterator[Any]:
    """Every route an application serves, flattened.

    The same walk `test_route_split.py` documents at length: Starlette 1.x
    stores one lazy `_IncludedRouter` per included router rather than copying
    the sub-router's routes into the parent, so a naive walk of `app.routes`
    finds 9 of this application's 180 routes. Both shapes are handled because
    the suite has to pass on whichever version is installed.
    """
    for route in getattr(app, "routes", []):
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
        else:
            yield route


def _dependency_names(route: object) -> Set[str]:
    """Every dependency callable's name in a route's flattened dependant tree.

    Walked rather than read one level deep, because the resolvers this row cares
    about are usually reached indirectly: `get_current_admin_user` itself
    depends on `get_current_user`, and a router's own `dependencies=[...]` are
    another level again.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return set()
    names: Set[str] = set()
    stack = [dependant]
    seen: Set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        call = getattr(current, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", ""))
        stack.extend(getattr(current, "dependencies", []) or [])
    return names


def _route_key(method: str, path: str) -> str:
    """`<METHOD> <path>`, with the trailing slash removed.

    A route key may not end in a slash: API Gateway normalises the trailing
    slash onto the bare key and rejects the other spelling at apply time on a
    plan that was green. `POST /api/build-lists/` in FastAPI is therefore
    `POST /api/build-lists` here.
    """
    return f"{method} {path.rstrip('/') or path}"


def _application_routes() -> Iterator[Tuple[str, str, Set[str]]]:
    """`(method, path, dependency names)` for every route the monolith serves."""
    from app.main import app

    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        if path is None:
            continue
        names = _dependency_names(route)
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                yield method, path, names


def _in_scope(path: str) -> bool:
    """Whether a path is this row's business.

    `/api/auth` is row 8's, the root and documentation routes belong to no
    domain, and everything else under `/api` is a domain route.
    """
    if path in ROOT_PATHS or not path.startswith("/api"):
        return False
    return not (path == IDENTITY_PREFIX or path.startswith(IDENTITY_PREFIX + "/"))


def application_authenticated_route_keys() -> Set[str]:
    """Every in scope route key whose resolver refuses an anonymous caller."""
    return {
        _route_key(method, path)
        for method, path, names in _application_routes()
        if _in_scope(path) and (names & REQUIRES_CALLER)
    }


def application_anonymous_route_keys() -> Set[str]:
    """Every in scope route key that serves an anonymous caller."""
    return {
        _route_key(method, path)
        for method, path, names in _application_routes()
        if _in_scope(path) and not (names & REQUIRES_CALLER)
    }


def test_terraform_names_exactly_the_routes_that_require_a_caller() -> None:
    """The set in `apigateway.tf` equals the set the application enforces.

    This is the assertion the row exists for, and it fails in both directions.
    A route added behind `get_current_user` with no key is a route the gateway
    will not check; a key naming a route the application serves anonymously is
    a 401 for every signed out caller the moment the flag is turned on.
    """
    expected = application_authenticated_route_keys()
    actual = set(terraform_domain_route_keys())

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert not missing, (
        "These routes require an authenticated caller but have no explicit route key in "
        "local.domain_identity_jwt_route_paths, so the gateway would never check them: "
        f"{missing}"
    )
    assert not extra, (
        "These route keys are named in local.domain_identity_jwt_route_paths but the application "
        "does not require an authenticated caller on them, so flagging them would 401 anonymous "
        f"callers: {extra}"
    )


def test_no_named_key_is_served_by_an_optional_resolver() -> None:
    """No flagged key sits on a route that personalises for anonymous callers.

    The complement of the test above, asserted against the optional resolvers by
    name rather than by absence from the required set. A resolver that was
    renamed would fall out of `REQUIRES_CALLER` and quietly stop being checked;
    this fails instead, because the route would then be in neither set.
    """
    named = set(terraform_domain_route_keys())
    for method, path, names in _application_routes():
        if not _in_scope(path):
            continue
        key = _route_key(method, path)
        if key not in named:
            continue
        overlap = names & TOLERATES_ANONYMOUS
        assert not overlap, (
            f"{key} is named in local.domain_identity_jwt_route_paths but resolves through "
            f"{sorted(overlap)}, which serves anonymous callers. Flagging it would turn a public "
            "route into a 401."
        )
        assert names & REQUIRES_CALLER, (
            f"{key} is named in local.domain_identity_jwt_route_paths but its dependency tree "
            "reaches none of the resolvers that refuse an anonymous caller. Either the route "
            "changed or a resolver was renamed and REQUIRES_CALLER is now stale."
        )


def test_every_named_key_points_at_the_domain_that_serves_its_prefix() -> None:
    """A key's integration is the domain whose prefix its path falls under.

    A key naming the wrong domain still plans and still applies: it routes the
    request to a healthy function that does not serve that path, so it answers
    that function's own 404 rather than anything that looks like a routing bug.
    """
    prefixes = terraform_domain_prefixes()
    for key, domain in sorted(terraform_domain_route_keys().items()):
        path = key.split(" ", 1)[1]
        matches = [p for p in prefixes if path == p or path.startswith(p + "/")]
        assert matches, f"{key} falls under no prefix in local.lambda_domain_path_prefixes"
        longest = max(matches, key=len)
        assert prefixes[longest] == domain, (
            f"{key} is listed under {domain!r} but its path falls under {longest!r}, "
            f"which local.lambda_domain_path_prefixes gives to {prefixes[longest]!r}."
        )


def test_no_route_key_ends_in_a_slash() -> None:
    """Route keys cannot end in a slash.

    API Gateway normalises a trailing slash onto the bare key and refuses the
    other spelling with a `BadRequestException` at apply time, on a plan that
    was green. Several of these routes are declared as `"/"` in their routers,
    so this is the mistake the generator would make if `_route_key` stopped
    stripping.
    """
    for key in sorted(set(terraform_domain_route_keys()) | set(terraform_guard_route_keys())):
        path = key.split(" ", 1)[1]
        assert path == "/" or not path.endswith("/"), f"{key} ends in a slash and would fail at apply time"


def test_anonymous_routes_are_not_captured_by_a_named_path_parameter_key() -> None:
    """No anonymous route is shadowed by a flagged key on the same method.

    The hazard this row introduces, and the reason the two guard keys exist.
    `GET /api/reports/{report_id}` and `GET /api/reports/count` are the same
    shape to a gateway: `count` matches `{report_id}` as readily as a uuid does.
    FastAPI resolves it by registration order, which does not exist at the
    gateway; API Gateway resolves it by specificity, and a static segment beats
    a path variable at the same depth. So an anonymous route colliding this way
    is safe only when it has a literal key of its own.

    Asserted over the whole application rather than over the two known cases, so
    a `/count` style route added under any flagged `{id}` key in future fails
    here instead of quietly becoming a 401 at the next flip.
    """
    named = set(terraform_domain_route_keys())
    guards = set(terraform_guard_route_keys())

    def captures(key_path: str, request_path: str) -> bool:
        left = key_path.strip("/").split("/")
        right = request_path.strip("/").split("/")
        if len(left) != len(right):
            return False
        return all(a == b or (a.startswith("{") and a.endswith("}")) for a, b in zip(left, right))

    for anonymous in sorted(application_anonymous_route_keys()):
        method, path = anonymous.split(" ", 1)
        path = path.rstrip("/") or path
        for key in named:
            key_method, key_path = key.split(" ", 1)
            if key_method != method or key_path == path:
                continue
            if captures(key_path, path):
                assert anonymous in guards, (
                    f"{anonymous} is anonymous but would be captured by the flagged key {key}, "
                    "so it needs a literal key of its own in "
                    "local.domain_anonymous_guard_route_keys to hold the more specific match."
                )


def test_guard_keys_are_anonymous_routes_the_application_serves() -> None:
    """Every guard key is a real anonymous route, and none of them is flagged.

    A guard key that named nothing would be harmless but dead, and a guard key
    that drifted onto an authenticated route would be a hole rather than a
    guard, so both directions are checked.
    """
    guards = terraform_guard_route_keys()
    assert guards, "local.domain_anonymous_guard_route_keys is empty; the two count keys are missing"

    anonymous = application_anonymous_route_keys()
    named = set(terraform_domain_route_keys())
    for key in sorted(guards):
        assert key in anonymous, f"{key} is a guard key but the application does not serve it anonymously"
        assert key not in named, f"{key} is both a guard key and a flagged key"


def test_the_flag_is_gated_on_the_variable_rather_than_hardcoded() -> None:
    """The keys land unflagged until `var.domain_jwt_enforced` says otherwise.

    The operational half of this row. In staging `identity_jwt_mode` is "gate",
    so a flagged key demands a valid identity access token at the gateway the
    moment it applies, while the frontend still sends the legacy session token.
    Landing the keys already flagged would sign every staging user out of every
    write path, so the flag reads the variable and the variable defaults to
    false.
    """
    source = _strip_comments(_terraform_source())
    assert "require_identity_jwt = var.domain_jwt_enforced" in source, (
        "local.domain_identity_jwt_route_keys must take require_identity_jwt from "
        "var.domain_jwt_enforced, so that the keys can land before enforcement begins."
    )

    variables = (BACKEND.parent / "terraform" / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "domain_jwt_enforced"') :]
    block = block[: block.index("\n}\n") + 3]
    assert re.search(r"^\s*default\s*=\s*false\s*$", block, re.MULTILINE), (
        "var.domain_jwt_enforced must default to false: the frontend still sends the legacy "
        "session token and a flagged route rejects it."
    )
