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


def _ingestion_routers() -> "Sequence[RouterSpec]":
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


DOMAINS: Dict[str, Domain] = {
    # 24 routes under /api/auth. Signs and verifies every token the application
    # issues, so it names SECRET_KEY.
    "identity": Domain(
        name="identity",
        title="CarModPicker identity",
        load_routers=_identity_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 14 routes under /api/users and /api/app-settings. Every user route is
    # behind get_current_user or get_current_admin_user, both of which decode a
    # token, so it names SECRET_KEY.
    "users": Domain(
        name="users",
        title="CarModPicker users",
        load_routers=_users_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 43 routes, the largest domain: parts, manufacturers, categories, retailers.
    # 17 of them verify a token.
    "catalog": Domain(
        name="catalog",
        title="CarModPicker catalog",
        load_routers=_catalog_routers,
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
        seeds=True,
    ),
    # 34 routes across the four build-list modules. 28 of them verify a token.
    "build-lists": Domain(
        name="build-lists",
        title="CarModPicker build lists",
        load_routers=_build_lists_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 5 routes. 4 verify a token.
    "build-logs": Domain(
        name="build-logs",
        title="CarModPicker build logs",
        load_routers=_build_logs_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 20 routes: votes, reports, bug reports. 17 verify a token.
    "moderation": Domain(
        name="moderation",
        title="CarModPicker moderation",
        load_routers=_moderation_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 8 routes, every one of them behind a token.
    "media": Domain(
        name="media",
        title="CarModPicker media",
        load_routers=_media_routers,
        requires_secrets=("SECRET_KEY",),
    ),
    # 12 routes: price alerts, the crawled-page parser and the two admin
    # modules. 11 verify a token, and the price-alert unsubscribe route decodes
    # one of its own.
    "ingestion": Domain(
        name="ingestion",
        title="CarModPicker ingestion",
        load_routers=_ingestion_routers,
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
