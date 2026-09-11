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
    """No routers of its own. The package's router is the whole of `/api/auth`.

    Row 13 of `docs/identity-adoption.md` deleted the four legacy routers this
    returned: `core`, `two_factor`, `webauthn` and `oauth`, 24 routes in total.
    Every flow they served is served by `webbpulse.identity`'s own router, which
    `app/composition/wiring.py` mounts with no prefix because
    `build_identity_router` already places each route under the issuer's path.

    The empty sequence is the honest shape rather than an absence: this domain
    still exists, still owns `users`, `oauth_accounts` and
    `webauthn_credentials`, and still serves `/api/auth`. What changed is that
    the routes under that prefix are all the package's now, which is what
    `app/composition/identity.py` describes as the thing row 13 resolves: the
    mount ordering that used to decide which of two routers won a shared path is
    gone because there is only one router left.
    """
    return []


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

#: `users` owns `users` and `app_settings`, and reads `oauth_accounts`.
#:
#: This tuple was twenty-three of twenty-five until row 30, and almost none of
#: those entries were there because a `users` route reads or writes the table.
#: They were there because `_delete_user_everywhere` deleted a user and then
#: wrote into roughly fifteen tables across five other domains, on the request
#: thread. Row 30 moved that cascade to `carmodpicker-<env>-users-delete-consumer`,
#: which names the tables itself in `app/entrypoints/users_delete_consumer.py`,
#: and twenty entries went with it. This is seam 1 closing, and it is the
#: largest single narrowing in the plan.
#:
#: `oauth_accounts` is the one that stayed, and it is a genuine cross-domain
#: read rather than a leftover: `user_service.user_read` attaches a user's
#: linked accounts to every user response. It was invisible to
#: `tests/entrypoints/test_repository_bundles.py` until this row, because that
#: module read the bundle through a local named `repositories` rather than
#: `repos`; row 30 renamed it, so the graph now sees the read that was always
#: there.
_USERS_REPOSITORIES = (
    "users",
    "app_settings",
    "oauth_accounts",
)

#: `catalog` owns the eleven catalogue tables. Two extras are left and both are
#: seams: `users` is read by the price alert fan-out (seam 4), and `votes` is
#: read by row 24's `net_votes` stream consumer, which `catalog` owns.
#: `part_service` reads the car tables to infer fitment.
#:
#: Row 28 removed three: `build_list_parts`, `part_price_alerts` and `reports`.
#: They were here for seam 2, the synchronous part purge, and no `catalog` route
#: reaches them now that the cascade runs on
#: `catalog-part-purge-consumer`. That function names them itself in
#: `app/entrypoints/catalog_part_purge_consumer.py`.
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

#: `vehicles` owns the three car tables. The other ten are seam 5's search
#: fan-out: one route reading four domains' tables, which the plan leaves
#: synchronous because turning it into service calls would make one Dynamo round
#: trip into three or four HTTP hops on a path that is already slow.
#:
#: It tracks `catalog` by construction, so row 28's three removals applied here
#: too: the search fan-out never read `build_list_parts`, `part_price_alerts` or
#: `reports`, it inherited them from the tuple it extends.
_VEHICLES_REPOSITORIES = _CATALOG_REPOSITORIES + ("build_lists",)

#: `build-lists` owns its four tables and `catalog`'s price capture reaches the
#: listing tables. `build_logs` and `build_log_posts` are there because a build
#: log is created with the list.
#:
#: Row 28 removed two: `part_price_alerts` and `reports`. Both were reached only
#: through the synchronous part purge, which section 8's row 28 note predicted
#: for `reports` by name, and both moved to the part purge consumer.
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
#:
#: Row 28 removed one: `build_list_parts`, reached only through the part purge
#: that `admin/db_ops` triggers. `admin` keeps `part_price_alerts` because it
#: owns that table and `admin/price_alerts` reads it directly.
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
    # The package's routes under /api/auth, and none of its own since row 13
    # deleted the 24 legacy ones. It no longer names SECRET_KEY: the legacy
    # HS256 session it used to sign and verify does not exist, and the identity
    # tokens that replaced it are signed in KMS.
    "identity": Domain(
        name="identity",
        title="CarModPicker identity",
        load_routers=_identity_routers,
        repositories=_IDENTITY_REPOSITORIES,
    ),
    # 14 routes under /api/users and /api/app-settings. Every user route is
    # behind get_current_user or get_current_admin_user.
    #
    # It no longer names SECRET_KEY. Row 13 deleted the legacy HS256 branch of
    # every resolver, so those dependencies now verify an identity access token
    # signed in KMS and verified by the API Gateway JWT authorizer. Nothing in
    # this domain reads settings.SECRET_KEY on any path, and naming it would buy
    # a secretsmanager:GetSecretValue grant the function does not use.
    "users": Domain(
        name="users",
        title="CarModPicker users",
        load_routers=_users_routers,
        repositories=_USERS_REPOSITORIES,
    ),
    # 43 routes, the largest domain: parts, manufacturers, categories, retailers.
    # 17 of them verify a token, which since row 13 means an identity access
    # token and not SECRET_KEY, so this domain no longer names it.
    #
    # `POST /api/parts/price-history` also accepts an X-API-Key matching
    # EXTENSION_API_KEY, a key of the carmodpicker-<env>/app JSON. It is
    # deliberately NOT named in requires_secrets: `check_signing_key` turns that
    # tuple into a hard `require_secrets` in production, and an unset key is a
    # supported state here (the route falls back to admin tokens only) rather
    # than a reason to fail a cold start.
    "catalog": Domain(
        name="catalog",
        title="CarModPicker catalog",
        load_routers=_catalog_routers,
        repositories=_CATALOG_REPOSITORIES,
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
    # 34 routes across the four build-list modules. 28 of them verify an
    # identity access token, which needs no application secret.
    "build-lists": Domain(
        name="build-lists",
        title="CarModPicker build lists",
        load_routers=_build_lists_routers,
        repositories=_BUILD_LISTS_REPOSITORIES,
    ),
    # 5 routes. 4 verify an identity access token, which needs no secret.
    "build-logs": Domain(
        name="build-logs",
        title="CarModPicker build logs",
        load_routers=_build_logs_routers,
        repositories=_BUILD_LOGS_REPOSITORIES,
    ),
    # 20 routes: votes, reports, bug reports. 17 verify an identity access
    # token, which needs no secret.
    "moderation": Domain(
        name="moderation",
        title="CarModPicker moderation",
        load_routers=_moderation_routers,
        repositories=_MODERATION_REPOSITORIES,
    ),
    # 8 routes, every one of them behind an identity access token, which needs
    # no secret.
    "media": Domain(
        name="media",
        title="CarModPicker media",
        load_routers=_media_routers,
        repositories=_MEDIA_REPOSITORIES,
    ),
    # 12 routes: price alerts, the crawled-page parser and the two admin
    # modules. 11 verify an identity access token, which needs no secret.
    #
    # This is the last domain naming SECRET_KEY, and it names it for exactly one
    # route. `GET /api/part-price-alerts/unsubscribe` reads a 30 day HS256 token
    # that `app/core/email.py` mints into the alert email, and the recipient of
    # that email is by construction not signed in, so there is no identity
    # access token equivalent for it. The follow up that replaces that link is
    # what lets SECRET_KEY leave the estate; see `docs/identity-adoption.md`
    # row 13. Named `admin` rather than `ingestion`, per section 1.5.
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
