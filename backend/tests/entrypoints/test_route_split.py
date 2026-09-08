"""The route contract, and the agreement between the two composition roots.

Three claims, in order of what they protect.

**Root A serves exactly the routes it served before the split.**
`tests/fixtures/route_contract.json` was captured from `app.main:app` on
`staging` before any of this existed, and is asserted here as a sorted list of
`(method, path)` pairs plus a count. It overlaps
`tests/test_openapi_snapshot.py`, deliberately: the snapshot pins the whole
published document and fails on a schema change as well as a routing one, while
this pins routing alone, so a failure here says "a route moved" rather than
"something in the document changed".

**Root B's routes are Root A's routes, partitioned.** The union of the nine
per-domain applications equals Root A exactly. This is the contract that lets a
cut be verified: when API Gateway starts sending `/api/images` to the `media`
function, the response has to be the one the monolith would have given, and it
can only be if `media`'s application declares the same routes.

**Each domain serves the number of routes the plan says it does.** Section 1.1
lists per-domain counts, and they are asserted individually rather than only in
aggregate, so a route moving between two domains fails loudly instead of
cancelling out in the total.

## 176 against 171

Section 2.7 of the plan speaks of 176 routes and section 1.1's per-domain table
sums to 171. Both are right and the difference is the five root routes.

- 171 are the domain routes under `/api`, and each of the nine per-domain counts
  in section 1.1 is exact.
- 5 more are `/`, `/health`, `/ready`, `/sitemap.xml` and `/sitemap-{name}.xml`,
  which belong to no domain and which every function serves locally, because the
  Lambda Web Adapter polls `/health` on every cold start and a function that did
  not answer it would never be marked ready.
- 176 is the sum, and it is what a deployed function's route table has to
  contain: its own domain's routes plus those five.

FastAPI adds four more of its own on top, which every count in the plan
excludes: `/docs`, `/docs/oauth2-redirect`, `/redoc` and `/api/openapi.json`.
So `len(app.routes)` reports 180 for Root A, and the constants below name all
three numbers so a future reader does not have to re-derive which is which.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import List, Set, Tuple

import pytest

from app.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "route_contract.json"

#: Routes that belong to no domain and that every function serves locally.
ROOT_ROUTES: Set[Tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/sitemap.xml"),
    ("GET", "/sitemap-{name}.xml"),
}

#: FastAPI's own, excluded from every count in the plan.
DOCS_ROUTES: Set[Tuple[str, str]] = {
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
    ("GET", "/api/openapi.json"),
}

DOMAIN_ROUTE_COUNT = 171
ROOT_ROUTE_COUNT = 5
DEPLOYED_ROUTE_COUNT = DOMAIN_ROUTE_COUNT + ROOT_ROUTE_COUNT  # 176, section 2.7
TOTAL_WITH_DOCS = DEPLOYED_ROUTE_COUNT + len(DOCS_ROUTES)  # 180, what len(app.routes) reports

#: Section 1.1, per domain.
EXPECTED_DOMAIN_ROUTES = {
    "identity": 24,
    "users": 14,
    "catalog": 43,
    "vehicles": 11,
    "build-lists": 34,
    "build-logs": 5,
    "moderation": 20,
    "media": 8,
    "ingestion": 12,
}


def _pairs(app: object) -> Set[Tuple[str, str]]:
    """Every `(method, path)` a application serves, HEAD excluded.

    Starlette adds HEAD alongside GET on every route it generates, so counting
    it would double the GET routes and make every number in the plan wrong.
    """
    out: Set[Tuple[str, str]] = set()
    for route in getattr(app, "routes", []):
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                out.add((method, getattr(route, "path")))
    return out


def _root_a() -> Set[Tuple[str, str]]:
    from app.main import app

    return _pairs(app)


def _root_b(domain: str) -> Set[Tuple[str, str]]:
    module = importlib.import_module(f"app.entrypoints.{ENTRYPOINT_MODULES[domain]}")
    return _pairs(module.build_app())


def test_root_a_matches_the_committed_route_contract() -> None:
    """The routing table, pinned.

    Regenerate only alongside a change that deliberately adds or removes a
    route, and the diff on the fixture is the review artifact:

        cd backend
        TESTING=true SECRET_KEY=test-secret-key python -c \\
          "import json; from app.main import app; \\
           print(json.dumps(sorted([m, r.path] for r in app.routes \\
             for m in (getattr(r, 'methods', None) or []) if m != 'HEAD'), indent=2))" \\
          > tests/fixtures/route_contract.json
    """
    expected: List[Tuple[str, str]] = [tuple(pair) for pair in json.loads(CONTRACT_PATH.read_text())]  # type: ignore[misc]
    actual = sorted(_root_a())
    assert actual == sorted(expected), (
        "Route drift detected. Review the diff on backend/tests/fixtures/route_contract.json; "
        "if it is intentional, regenerate the fixture and commit it with the change."
    )


def test_root_a_route_counts_reconcile() -> None:
    """171 domain routes, 5 root routes, 4 FastAPI routes, 180 in the table."""
    pairs = _root_a()
    assert len(pairs) == TOTAL_WITH_DOCS
    assert ROOT_ROUTES <= pairs
    assert DOCS_ROUTES <= pairs
    assert len(pairs - ROOT_ROUTES - DOCS_ROUTES) == DOMAIN_ROUTE_COUNT


def test_root_a_openapi_paths_match_the_contract() -> None:
    """The published document and the routing table describe the same surface.

    The contract is captured from `app.routes`, which is what actually resolves
    a request; this asserts the OpenAPI document agrees with it. The two can
    drift: a route declared with `include_in_schema=False` is in the table and
    not in the document, and the five that do that here are named, so a new one
    appearing is a deliberate decision rather than an accident.
    """
    from app.main import app

    documented = {
        (method.upper(), path)
        for path, operations in app.openapi().get("paths", {}).items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "TRACE"}
    }
    in_table = _root_a()
    # `/docs`, `/redoc`, `/docs/oauth2-redirect` and `/api/openapi.json` are
    # generated by FastAPI and never documented; the two sitemap routes set
    # `include_in_schema=False` because they serve XML to crawlers.
    undocumented = {
        ("GET", "/sitemap.xml"),
        ("GET", "/sitemap-{name}.xml"),
    } | DOCS_ROUTES
    assert documented == in_table - undocumented
    assert len(documented) == DOMAIN_ROUTE_COUNT + ROOT_ROUTE_COUNT - 2


def test_no_route_is_registered_twice() -> None:
    """A duplicate `(method, path)` means the first declaration wins silently."""
    from app.main import app

    seen: List[Tuple[str, str]] = []
    for route in app.routes:
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                seen.append((method, getattr(route, "path")))
    duplicates = sorted({pair for pair in seen if seen.count(pair) > 1})
    assert duplicates == [], f"routes registered more than once: {duplicates}"


def test_the_union_of_root_b_equals_root_a() -> None:
    """The contract that lets a cut be verified.

    When a prefix is flipped to a domain function, the response has to be the
    one the monolith would have given. It can only be if that function's
    application declares the same routes, and no others.
    """
    union: Set[Tuple[str, str]] = set()
    for domain in DOMAIN_NAMES:
        union |= _root_b(domain)
    root_a = _root_a()
    assert sorted(union - root_a) == [], "a domain serves a route the composed application does not"
    assert sorted(root_a - union) == [], "the composed application serves a route no domain owns"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_serves_the_routes_section_one_one_gives_it(domain: str) -> None:
    """Per domain, not only in aggregate, so a route moving fails loudly."""
    pairs = _root_b(domain)
    own = pairs - ROOT_ROUTES - DOCS_ROUTES
    assert len(own) == EXPECTED_DOMAIN_ROUTES[domain]
    # Every function serves the five root routes locally, `/health` above all:
    # the Web Adapter polls it on every cold start.
    assert ROOT_ROUTES <= pairs
    assert len(pairs) == EXPECTED_DOMAIN_ROUTES[domain] + ROOT_ROUTE_COUNT + len(DOCS_ROUTES)


def test_the_domains_partition_the_api_surface() -> None:
    """No route belongs to two domains, and none belongs to none."""
    owners: dict[Tuple[str, str], List[str]] = {}
    for domain in DOMAIN_NAMES:
        for pair in _root_b(domain) - ROOT_ROUTES - DOCS_ROUTES:
            owners.setdefault(pair, []).append(domain)
    shared = {pair: names for pair, names in owners.items() if len(names) > 1}
    assert shared == {}, f"routes claimed by more than one domain: {shared}"
    assert len(owners) == DOMAIN_ROUTE_COUNT


def test_the_price_alert_unsubscribe_route_is_registered_first() -> None:
    """Section 1.4's fragile pair, asserted rather than documented.

    `/api/part-price-alerts/unsubscribe` survives only because `/{alert_id}` is
    PATCH and DELETE and there is no GET detail route. Adding `GET /{alert_id}`
    after it would shadow unsubscribe silently and the only symptom would be
    that unsubscribe links stop working. This pins the registration order so
    that change fails here instead of in production.
    """
    from app.main import app

    paths = [
        getattr(route, "path")
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/part-price-alerts")
    ]
    unsubscribe = paths.index("/api/part-price-alerts/unsubscribe")
    parameterised = min(index for index, path in enumerate(paths) if "{alert_id}" in path)
    assert unsubscribe < parameterised
