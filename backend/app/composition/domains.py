"""The nine domains of the split, as descriptors.

One entry per row of section 1.1 of `docs/migration/split-plan.md`, carrying the
same endpoint modules, the same path prefixes and the same route counts. The
counts in the comments were taken by walking `app.routes`, not by grepping
decorators: nine routes across three modules are generated at runtime by
`BaseDynamoEndpointRouter` and are invisible to a grep, which is why the
decorator count is 162 and the real count is 171.

**Importing this module imports no endpoint module.** Each `_<domain>_routers`
function does its imports in its own body, and nothing at module scope reaches
`app.api.endpoints`. That is what lets `app.entrypoints.media` build an
application carrying `images` and nothing else, and
`tests/entrypoints/test_entrypoint_isolation.py` proves it in a fresh
interpreter rather than trusting the reading.

**The prefixes and tags are the ones `EndpointRegistry` produced.** `app/main.py`
registered every router through `EndpointRegistry`, which prepends
`settings.API_STR` and applies a tag list. Those two values are the whole of what
the registry contributed to the routing table, so they are recorded here on the
descriptor instead, and `Domain.router_prefix` supplies the `/api`. The registry
itself is untouched and still exports `register_crud_endpoint`; this PR simply
stops `app/main.py` being the only place that knows which prefix a router takes.

The tuple order inside each loader is the order `app/main.py` registered those
modules in, relative to each other. Section 1.4's seven ordering hazards are all
inside a single module, so they are decided by that module's own decorator order
and are untouched here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Sequence, Tuple

from app.composition.wiring import Domain

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import APIRouter

RouterSpec = Tuple["APIRouter", str, Tuple[str, ...]]


def _identity_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints.auth import core as auth_core
    from app.api.endpoints.auth import oauth as auth_oauth
    from app.api.endpoints.auth import two_factor as auth_2fa
    from app.api.endpoints.auth import webauthn as auth_webauthn

    # `/auth` first: `core` declares the literal login and token routes, and the
    # three sub-prefixes are strictly longer, so no pair here can shadow.
    return [
        (auth_core.router, "/auth", ("authentication",)),
        (auth_2fa.router, "/auth/2fa", ("authentication",)),
        (auth_webauthn.router, "/auth/webauthn", ("authentication",)),
        (auth_oauth.router, "/auth/oauth", ("authentication",)),
    ]


def _users_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import app_settings, users

    return [
        (users.router, "/users", ("users",)),
        (app_settings.router, "/app-settings", ("app-settings",)),
    ]


def _catalog_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import categories, part_manufacturers, parts, retailers

    return [
        (parts.router, "/parts", ("parts",)),
        (categories.router, "/categories", ("categories",)),
        (part_manufacturers.router, "/part-manufacturers", ("part_manufacturers",)),
        (retailers.router, "/retailers", ("retailers",)),
    ]


def _vehicles_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import car_generations, search

    return [
        (car_generations.router, "/car-generations", ("car-generations",)),
        (search.router, "/search", ("search",)),
    ]


def _build_lists_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import (
        build_list_labor_estimates,
        build_list_parts,
        build_list_phases,
        build_lists,
    )

    return [
        (build_lists.router, "/build-lists", ("build-lists",)),
        (build_list_parts.router, "/build-list-parts", ("build-list-parts",)),
        (build_list_phases.router, "/build-list-phases", ("build-list-phases",)),
        (
            build_list_labor_estimates.router,
            "/build-list-labor-estimates",
            ("build-list-labor-estimates",),
        ),
    ]


def _build_logs_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import build_logs

    return [(build_logs.router, "/build-logs", ("build-logs",))]


def _moderation_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import bug_reports, reports, votes

    return [
        (votes.router, "/votes", ("votes",)),
        (reports.router, "/reports", ("reports",)),
        (bug_reports.router, "/bug-reports", ("bug-reports",)),
    ]


def _media_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import images

    return [(images.router, "/images", ("images",))]


def _admin_routers() -> "Sequence[RouterSpec]":
    from app.api.endpoints import crawled_pages, part_price_alerts
    from app.api.endpoints.admin import db_ops as admin_db_ops
    from app.api.endpoints.admin import stats as admin_stats

    # `part_price_alerts` declares `/unsubscribe` before its two `/{alert_id}`
    # routes, which is the one ordering hazard in section 1.4 that is a route
    # away from breaking silently. It is decided inside that module, so it is
    # preserved by not touching the module.
    return [
        (part_price_alerts.router, "/part-price-alerts", ("part-price-alerts",)),
        (crawled_pages.router, "/crawled-pages", ("crawled-pages",)),
        (admin_stats.router, "/admin/stats", ("admin",)),
        (admin_db_ops.router, "/admin/db-ops", ("admin",)),
    ]


# --- Repository bundles ------------------------------------------------------
# Which of the twenty-five repositories each domain's process carries. The
# blocker section 2.3 of the split plan describes was that every route reached a
# module-level object holding all twenty-five, so a `media` function would have
# imported the whole data layer at cold start and held a `UserRepository`
# pointed at a table it has no IAM grant for. These tuples are what replaced it.
#
# Each tuple is the set of `repos.<name>` attributes reachable from that
# domain's endpoint modules through their real import graph, not a guess and not
# the plan's ownership column. The two differ, and the difference is exactly the
# cross-domain reads section 1.3 leaves synchronous: `media` owns one table and
# reads four more for the orphan sweep, `vehicles` owns three and reads the rest
# for search. `tests/entrypoints/test_repository_bundles.py` recomputes the
# reachable set from the import graph and fails if a tuple drifts from it, in
# either direction, so this list cannot rot quietly and a domain cannot acquire
# a table by accident.
#
# Ownership, in the sense section 1.2 means it, is not expressed here. A
# repository in two domains' tuples is two domains reading one table; which of
# them may write to it is a Terraform IAM question and rows 22 onward are what
# make the writer single. Nothing here grants or withholds a write.

#: `identity` owns `oauth_accounts` and `webauthn_credentials` and writes
#: `users`, which `users` owns. That write is seam 1's neighbour and stays
#: synchronous until the tombstone lands.
_IDENTITY_REPOSITORIES = ("users", "oauth_accounts", "webauthn_credentials")

#: `users` is the widest bundle and stays that way until row 30 makes the delete
#: cascade asynchronous. Twenty-three of twenty-five, because `users.py` deletes
#: a user and then writes into roughly fifteen tables across five other domains.
_USERS_REPOSITORIES = (
    "users",
    "oauth_accounts",
    "webauthn_credentials",
    "app_settings",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
    "reports",
)

#: `catalog` owns the eleven catalogue tables. The extras are the seams: the
#: part purge writes `build_list_parts`, `votes` and `reports` (seam 2), the
#: price alert fan-out reads `part_price_alerts` and `users` (seam 4), and
#: `part_service` reads the car tables to infer fitment.
_CATALOG_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_list_parts",
    "votes",
    "reports",
)

#: `vehicles` owns the three car tables. The other thirteen are seam 5's search
#: fan-out: one route reading four domains' tables, which the plan leaves
#: synchronous because turning it into service calls would make one Dynamo round
#: trip into three or four HTTP hops on a path that is already slow.
_VEHICLES_REPOSITORIES = _CATALOG_REPOSITORIES + ("build_lists",)

#: `build-lists` owns its four tables and `catalog`'s price capture reaches the
#: listing tables. `build_logs` and `build_log_posts` are there because a build
#: log is created with the list.
_BUILD_LISTS_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
    "reports",
)

#: `build-logs` owns two tables and reads `build_lists` for the parent and
#: `users` for the author.
_BUILD_LOGS_REPOSITORIES = ("users", "build_lists", "build_logs", "build_log_posts")

#: `moderation` owns three tables. `parts` is seam 3, the `net_votes`
#: denormalisation, and it is the only cross-domain write left here; row 24
#: inverts it into a stream handler `catalog` owns. The rest are author and
#: target reads.
_MODERATION_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "parts",
    "build_lists",
    "votes",
    "reports",
    "bug_reports",
)

#: `media` owns one table. The other four are seam 5's orphan sweep, which
#: full-scans `parts`, `users`, `car_generations`, `build_lists` and
#: `image_source_mappings` to find unreferenced S3 objects and stays synchronous
#: with read-only grants. This is the narrowest bundle and the first domain the
#: plan cuts, which is why it is the one the isolation tests name.
_MEDIA_REPOSITORIES = (
    "users",
    "car_generations",
    "parts",
    "build_lists",
    "image_source_mappings",
)

#: `admin` owns `part_price_alerts`, and the two admin modules read and write
#: most of the application by design: `admin/stats` counts twelve tables and
#: `admin/db_ops` seeds and purges. It is the second widest bundle, and the
#: breadth is why the domain is called `admin`: section 1.5 argued the contents
#: were closer to administration than to ingestion, and the name now says so.
_ADMIN_REPOSITORIES = (
    "users",
    "oauth_accounts",
    "webauthn_credentials",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_logs",
    "votes",
    "reports",
    "image_source_mappings",
)


DOMAINS: Dict[str, Domain] = {
    # 24 routes under /api/auth. Signs and verifies every token the application
    # issues, so it names SECRET_KEY.
    "identity": Domain(
        name="identity",
        title="CarModPicker identity",
        load_routers=_identity_routers,
        repositories=_IDENTITY_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 14 routes under /api/users and /api/app-settings. Every user route is
    # behind get_current_user or get_current_admin_user, both of which decode a
    # token, so it names SECRET_KEY.
    "users": Domain(
        name="users",
        title="CarModPicker users",
        load_routers=_users_routers,
        repositories=_USERS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 43 routes, the largest domain: parts, manufacturers, categories, retailers.
    # 17 of them verify a token.
    "catalog": Domain(
        name="catalog",
        title="CarModPicker catalog",
        load_routers=_catalog_routers,
        repositories=_CATALOG_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 11 routes, and the one domain that needs no secret: every route under
    # /api/car-generations and /api/search is a public read. `car_generations`
    # builds a BaseDynamoEndpointRouter with the writing endpoints disabled, so
    # the generated `get_current_user` routes are never registered. This is what
    # lets the vehicles function run with no secretsmanager:GetSecretValue.
    "vehicles": Domain(
        name="vehicles",
        title="CarModPicker vehicles",
        load_routers=_vehicles_routers,
        repositories=_VEHICLES_REPOSITORIES,
        seeds=True,
    ),
    # 34 routes across the four build-list modules. 28 of them verify a token.
    "build-lists": Domain(
        name="build-lists",
        title="CarModPicker build lists",
        load_routers=_build_lists_routers,
        repositories=_BUILD_LISTS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 5 routes. 4 verify a token.
    "build-logs": Domain(
        name="build-logs",
        title="CarModPicker build logs",
        load_routers=_build_logs_routers,
        repositories=_BUILD_LOGS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 20 routes: votes, reports, bug reports. 17 verify a token.
    "moderation": Domain(
        name="moderation",
        title="CarModPicker moderation",
        load_routers=_moderation_routers,
        repositories=_MODERATION_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 8 routes, every one of them behind a token.
    "media": Domain(
        name="media",
        title="CarModPicker media",
        load_routers=_media_routers,
        repositories=_MEDIA_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    # 12 routes: price alerts, the crawled-page parser and the two admin
    # modules. 11 verify a token, and the price-alert unsubscribe route decodes
    # one of its own. Named `admin` rather than `ingestion`, per section 1.5.
    "admin": Domain(
        name="admin",
        title="CarModPicker admin",
        load_routers=_admin_routers,
        repositories=_ADMIN_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
}

#: The nine names, in the order the plan lists them.
DOMAIN_NAMES: Tuple[str, ...] = tuple(DOMAINS)

#: The module name under `app.entrypoints` for each domain. `build-lists` and
#: `build-logs` are hyphenated as domain names, because that is what the ECR
#: repository, the function name and the log group carry, but a Python module
#: cannot be.
ENTRYPOINT_MODULES: Dict[str, str] = {name: name.replace("-", "_") for name in DOMAIN_NAMES}
