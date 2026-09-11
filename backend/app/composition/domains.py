"""The nine domains of the split, as descriptors carrying their routers.

Importing this module imports no endpoint module: each loader does its own
imports in its body, which is what keeps one domain's image free of the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Sequence, Tuple

from app.composition.wiring import Domain

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

RouterSpec = Tuple["APIRouter", str, Tuple[str, ...]]


def _identity_routers() -> "Sequence[RouterSpec]":
    """The four auth routers: core, 2FA, WebAuthn and OAuth."""
    from app.api.endpoints.auth import core as auth_core
    from app.api.endpoints.auth import oauth as auth_oauth
    from app.api.endpoints.auth import two_factor as auth_2fa
    from app.api.endpoints.auth import webauthn as auth_webauthn

    return [
        (auth_core.router, "/auth", ("authentication",)),
        (auth_2fa.router, "/auth/2fa", ("authentication",)),
        (auth_webauthn.router, "/auth/webauthn", ("authentication",)),
        (auth_oauth.router, "/auth/oauth", ("authentication",)),
    ]


def _users_routers() -> "Sequence[RouterSpec]":
    """The user account router and the app settings singleton router."""
    from app.api.endpoints import app_settings, users

    return [
        (users.router, "/users", ("users",)),
        (app_settings.router, "/app-settings", ("app-settings",)),
    ]


def _catalog_routers() -> "Sequence[RouterSpec]":
    """Parts, categories, manufacturers and retailers."""
    from app.api.endpoints import categories, part_manufacturers, parts, retailers

    return [
        (parts.router, "/parts", ("parts",)),
        (categories.router, "/categories", ("categories",)),
        (part_manufacturers.router, "/part-manufacturers", ("part_manufacturers",)),
        (retailers.router, "/retailers", ("retailers",)),
    ]


def _vehicles_routers() -> "Sequence[RouterSpec]":
    """Car generations and the unified search."""
    from app.api.endpoints import car_generations, search

    return [
        (car_generations.router, "/car-generations", ("car-generations",)),
        (search.router, "/search", ("search",)),
    ]


def _build_lists_routers() -> "Sequence[RouterSpec]":
    """Build lists and their parts, phases and labor estimates."""
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
    """The build log threads and posts router."""
    from app.api.endpoints import build_logs

    return [(build_logs.router, "/build-logs", ("build-logs",))]


def _moderation_routers() -> "Sequence[RouterSpec]":
    """Votes, reports and bug reports."""
    from app.api.endpoints import bug_reports, reports, votes

    return [
        (votes.router, "/votes", ("votes",)),
        (reports.router, "/reports", ("reports",)),
        (bug_reports.router, "/bug-reports", ("bug-reports",)),
    ]


def _media_routers() -> "Sequence[RouterSpec]":
    """The image upload and serving router."""
    from app.api.endpoints import images

    return [(images.router, "/images", ("images",))]


def _admin_routers() -> "Sequence[RouterSpec]":
    """Price alerts, crawled pages and the two admin routers."""
    from app.api.endpoints import crawled_pages, part_price_alerts
    from app.api.endpoints.admin import db_ops as admin_db_ops
    from app.api.endpoints.admin import stats as admin_stats

    return [
        (part_price_alerts.router, "/part-price-alerts", ("part-price-alerts",)),
        (crawled_pages.router, "/crawled-pages", ("crawled-pages",)),
        (admin_stats.router, "/admin/stats", ("admin",)),
        (admin_db_ops.router, "/admin/db-ops", ("admin",)),
    ]


_IDENTITY_REPOSITORIES = ("users", "oauth_accounts", "webauthn_credentials")

_USERS_REPOSITORIES = (
    "users",
    "app_settings",
    "oauth_accounts",
)

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
    "votes",
)

_VEHICLES_REPOSITORIES = _CATALOG_REPOSITORIES + ("build_lists",)

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
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
)

_BUILD_LOGS_REPOSITORIES = ("users", "build_lists", "build_logs", "build_log_posts")

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

_MEDIA_REPOSITORIES = (
    "users",
    "car_generations",
    "parts",
    "build_lists",
    "image_source_mappings",
)

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
    "build_list_phases",
    "build_logs",
    "votes",
    "reports",
    "image_source_mappings",
)


DOMAINS: Dict[str, Domain] = {
    "identity": Domain(
        name="identity",
        title="CarModPicker identity",
        load_routers=_identity_routers,
        repositories=_IDENTITY_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "users": Domain(
        name="users",
        title="CarModPicker users",
        load_routers=_users_routers,
        repositories=_USERS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "catalog": Domain(
        name="catalog",
        title="CarModPicker catalog",
        load_routers=_catalog_routers,
        repositories=_CATALOG_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "vehicles": Domain(
        name="vehicles",
        title="CarModPicker vehicles",
        load_routers=_vehicles_routers,
        repositories=_VEHICLES_REPOSITORIES,
        seeds=True,
    ),
    "build-lists": Domain(
        name="build-lists",
        title="CarModPicker build lists",
        load_routers=_build_lists_routers,
        repositories=_BUILD_LISTS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "build-logs": Domain(
        name="build-logs",
        title="CarModPicker build logs",
        load_routers=_build_logs_routers,
        repositories=_BUILD_LOGS_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "moderation": Domain(
        name="moderation",
        title="CarModPicker moderation",
        load_routers=_moderation_routers,
        repositories=_MODERATION_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "media": Domain(
        name="media",
        title="CarModPicker media",
        load_routers=_media_routers,
        repositories=_MEDIA_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
    "admin": Domain(
        name="admin",
        title="CarModPicker admin",
        load_routers=_admin_routers,
        repositories=_ADMIN_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
}

DOMAIN_NAMES: Tuple[str, ...] = tuple(DOMAINS)

ENTRYPOINT_MODULES: Dict[str, str] = {name: name.replace("-", "_") for name in DOMAIN_NAMES}
