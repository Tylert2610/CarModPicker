"""The nine domains, and how one application is built from any subset of them.

This module is the single description of what a domain is: its name, the routers
it owns, the prefix and tags those routers mount under, and which secrets a
process serving it cannot answer a request without. Root A
(`app.composition.app`) walks the whole map; Root B
(`app.entrypoints.<domain>`) picks one entry out of it. Neither holds a second
copy of the list, which is what stops the composed application and the deployed
function drifting apart.

## `load_routers` is a callable on purpose

Importing this module must import no endpoint module. `load_routers` defers that
import to the moment a root actually builds the application, so
`app.entrypoints.media` reaches `app.api.endpoints.images` and nothing else. The
other eight domains' endpoint modules, their services and their schemas are never
imported in that process, which is the whole point of the indirection and what
keeps a cold start proportional to one domain rather than to the application.
`tests/entrypoints/test_entrypoint_isolation.py` asserts it in a fresh
interpreter, because a single module-scope import added here would undo it
silently.

## Registration order is load-bearing

FastAPI resolves routes in registration order, and section 1.4 of the split plan
lists seven places where CarModPicker depends on it: `/api/parts/count` before
`/api/parts/{entity_id}`, `/api/part-price-alerts/unsubscribe` before
`/{alert_id}`, and five more. Every one of those pairs lives inside a single
endpoint module, so they survive as long as a module's own decorator order is
untouched, which this PR does not touch: the routers are the same objects
`app/main.py` has always registered.

The one thing this PR does change is the order of the modules relative to each
other. `app/main.py` registers them interleaved by kind rather than by domain
(users, car-generations, build-lists, parts, ...), and grouping them by domain
moves modules past each other. That is safe here, and it was verified rather
than assumed: no route in any domain matches a concrete path belonging to a
different domain, so no cross-domain pair can shadow. The OpenAPI document is
unaffected because it is serialised with sorted keys.

## The composition root is not `mount`

Root A composes with `include_router`, never with `mount`. Starlette strips a
mount path before the sub-application sees it, and a mounted sub-application
contributes nothing to the parent's OpenAPI document, so mounting would give an
application whose routes resolve but whose `/api/openapi.json` is empty. Both
roots therefore produce identical paths, which is what
`tests/entrypoints/test_route_split.py` compares.
"""

from __future__ import annotations

import logging
import warnings
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Dict, Iterable, Sequence, Tuple

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import APIRouter

logger = logging.getLogger(__name__)

#: CarModPicker mounts its API under `/api`, not `/api/v1`. This is the one
#: place the split plan calls out as genuinely different from Portfolio, and
#: every API Gateway route key differs by that segment.
API_PREFIX = settings.API_STR

#: Service name pattern. Terraform sets `SERVICE_NAME` to the same string, and
#: it becomes the OpenTelemetry `service.name` and the `service` field on every
#: log line, so the two have to agree.
SERVICE_NAME_TEMPLATE = "carmodpicker-{domain}"


@dataclass(frozen=True)
class Domain:
    """One deployable domain."""

    name: str
    title: str
    #: Called lazily so importing this module imports no endpoint module. An
    #: entrypoint that only serves `media` must not pay for importing `catalog`.
    #: Returns `(router, prefix, tags)` triples in the order they must be
    #: registered, because within a domain that order decides which route wins.
    load_routers: Callable[[], "Sequence[Tuple[APIRouter, str, Tuple[str, ...]]]"]
    #: Prefix prepended to each router's own prefix. `/api` for every domain
    #: here; the field exists because Portfolio has a domain that mounts at the
    #: root and the descriptor is shared in shape.
    router_prefix: str = API_PREFIX
    #: Tags applied to every router the domain loads that does not name its own.
    router_tags: Tuple[str, ...] = ()
    #: Which settings the domain cannot serve a request without. A domain that
    #: names none can run with no `secretsmanager:GetSecretValue` at all.
    requires_secrets: Tuple[str, ...] = ()
    #: The repositories a process serving this domain may use, by the attribute
    #: name routes already reach through `repos.<name>`. Root B builds a bundle
    #: from exactly this tuple, so a repository missing here is an
    #: `RepositoryNotInBundle` on the route that wants it, and a repository
    #: present here that the domain never uses is a DynamoDB grant the function
    #: does not need. `tests/entrypoints/test_repository_bundles.py` checks both
    #: directions against what the domain's modules actually reach.
    repositories: Tuple[str, ...] = ()
    #: Whether the domain seeds the tables it owns on startup.
    seeds: bool = False
    #: Extra keyword arguments for `FastAPI(...)`.
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def service_name(self) -> str:
        return SERVICE_NAME_TEMPLATE.format(domain=self.name)

    @property
    def tables(self) -> Tuple[str, ...]:
        """The DynamoDB tables this domain's repositories reach, sorted.

        The function's whole data surface, and what its Terraform IAM policy has
        to cover. Read from the repository registry rather than listed again
        here, so the two cannot disagree.
        """
        from app.db.dynamo.registry import tables_for

        return tables_for(self.repositories)


def configure_logging(service: "str | None" = None) -> None:
    """The application's log format, applied to the root and uvicorn loggers.

    Now a thin call into `app.core.logging.configure_app_logging`, which puts
    the shared package's JSON formatter on the root handler when stdout is not a
    TTY and CarModPicker's colorized one when it is, and attaches
    `webbpulse.log_context`'s `LogContextFilter` either way. The uvicorn loggers are handled inside
    the package: it clears their handlers and sets `propagate = True` so their
    access lines go through the root formatter, which is what the loop this
    replaces was doing by hand.

    Still module-level work in practice, because `app/main.py` has always
    configured logging at import and the deployed monolith depends on that.
    Calling it twice is harmless.
    """
    from app.core.logging import configure_app_logging

    configure_app_logging(
        level=settings.log_level,
        service=service or settings.PROJECT_NAME,
        environment=settings.environment,
    )


#: The environment variable that turns tracing on. Empty means off, and off is
#: the state every CarModPicker process is in today.
OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"

#: Set by `configure_tracing` when it installed a provider, and read by
#: `build_domain_app` to decide whether instrumenting the application is worth
#: anything. A module flag rather than a call into the package because
#: `webbpulse.otel` keeps its own private `_CONFIGURED`, and an entrypoint that
#: never called `configure_tracing` must not be able to observe a provider some
#: other test installed in the same interpreter.
_TRACING_CONFIGURED = False


def configure_tracing(domain: "Domain") -> bool:
    """Wire OpenTelemetry for one domain, but only when an endpoint is set.

    Returns whether tracing was configured, which is `False` everywhere today.

    **The gate is the point, and it is deliberately not the package's default.**
    `webbpulse.otel.configure_tracing` falls back to this region's X-Ray OTLP
    endpoint when no endpoint is configured, which is the right default for a
    service whose Terraform grants `xray:PutTraceSegments`. CarModPicker is not
    that service yet: staging still runs the monolith zip, no function has an
    OTLP IAM grant, and Transaction Search is not enabled on the account. Taking
    the package default here would have every process open a batch exporter to an
    endpoint that answers 403, which the OTLP exporter retries in silence, so the
    cost would be a background retry loop and no visible error anywhere.

    Requiring the endpoint variable makes the off state explicit and makes
    turning tracing on a Terraform change rather than a code change. Row 16 sets
    it per domain, adds the `aws-otel` extra for the SigV4 signing exporter, and
    attaches `AWSXrayWriteOnlyAccess`; until then this function returns early and
    the package is never asked to build a provider.
    """
    global _TRACING_CONFIGURED
    import os

    if not os.environ.get(OTLP_ENDPOINT_ENV, "").strip():
        logger.debug(
            "Tracing not configured: %s is unset. Row 16 of the split plan turns it on.",
            OTLP_ENDPOINT_ENV,
        )
        return False

    from webbpulse.otel import configure_tracing as _configure_tracing
    from webbpulse.otel import resolve_sample_ratio

    # The ratio is resolved explicitly rather than left to the default so the
    # value this process is actually running with appears in the configuration
    # log line, which is the only way to tell a misread
    # WEBBPULSE_OTEL_SAMPLE_RATIO from a correctly read one.
    configured = _configure_tracing(
        domain.service_name,
        environment=settings.environment,
        sample_ratio=resolve_sample_ratio(),
    )
    _TRACING_CONFIGURED = _TRACING_CONFIGURED or configured
    return configured


def check_signing_key(domains: "Iterable[Domain]") -> None:
    """Fail fast on a missing secret, once at startup, per the domains served.

    This is `app/main.py`'s SECRET_KEY block, generalised. A root that serves no
    domain naming `SECRET_KEY` never calls `require_secrets`, which is what lets
    the `vehicles` function run with no Secrets Manager grant. Outside a
    deployed environment an empty key stays a warning, which is what keeps local
    development and the test suite runnable without one.
    """
    wanted = sorted({name for domain in domains for name in domain.requires_secrets})
    if not wanted:
        return
    if settings.is_production:
        settings.require_secrets(*wanted)
        return
    if "SECRET_KEY" in wanted and not settings.SECRET_KEY:
        warnings.warn(
            "SECRET_KEY is empty. JWT tokens will be insecure. Set SECRET_KEY environment variable.",
            UserWarning,
        )


def bundle_for(domains: "Sequence[Domain]") -> "Any":
    """The bundle carrying exactly the repositories these domains declare.

    The union across the domains served, which is one domain's tuple under Root
    B and all twenty-five under Root A. Section 2.3 of the split plan is the
    reason this exists: the twenty-five repositories used to be constructed at
    module import, so every function would have imported the whole data layer at
    cold start and held handles on tables it has no grant for.

    Building the bundle constructs no repository. The first route that reaches
    `repos.users` builds `UserRepository` and nothing else, which is what keeps
    an image's import graph proportional to the routes it actually serves.

    Imported inside the function because `app.composition.domains` imports this
    module, and the bundle module reaches the repository registry.
    """
    from app.api.dependencies.repositories import build_bundle

    names: "list[str]" = []
    for domain in domains:
        for repository in domain.repositories:
            if repository not in names:
                names.append(repository)
    label = "+".join(domain.name for domain in domains) or "none"
    return build_bundle(names, name=label)


def run_startup_tasks() -> None:
    """Seed work that runs once per process, on the first request in the app.

    Only a root serving a domain whose descriptor sets `seeds` wires this, so a
    function with read-only IAM on the car tables never attempts the write.
    """
    from app.core.init_cars import init_car_generations

    try:
        init_car_generations()
    except Exception:
        logger.exception("Failed to initialize car generations on startup")


def add_shared_middleware(app: FastAPI) -> None:
    """CORS, request context, rate limiting and the error handlers.

    Both roots go through here, so the middleware stack is identical locally, in
    the test suite, and in each deployed function. The order is the order
    `app/main.py` has always added them in, and it is load-bearing: Starlette
    runs middleware outermost-first in the order added, so CORS wraps the
    request-context middleware which wraps the rate limiter.

    Imported inside the function rather than at module scope. `app.api.middleware`
    pulls in the rate limiter and its DynamoDB client, and this module is
    imported by `domains.py`, which must stay import-light.
    """
    from app.api.middleware import rate_limit_middleware, request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

    # The Chrome extension's popup, content scripts and MV3 service worker all
    # send `Origin: chrome-extension://<id>` for its own fixed store id, so the
    # id is listed explicitly in `settings.allowed_origins_list` rather than
    # matched by a `chrome-extension://.*` regex. The regex plus
    # `allow_credentials=True` admitted every extension the user had installed,
    # which is a credentialed read of this API's authenticated responses by any
    # third-party extension.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-Admin-Cron-Key",
        ],
        expose_headers=["*"],
    )

    # Assign a UUID to every request and inject request_id/user_id into log lines.
    app.middleware("http")(request_context_middleware)
    app.middleware("http")(rate_limit_middleware)
    register_error_handlers(app)


# --- Root routes -------------------------------------------------------------
# The five routes in section 1.1 that belong to no domain. Every function serves
# them locally: `/health` because the Lambda Web Adapter polls it on every cold
# start and it must do no I/O, `/ready` because it is the readiness probe, and
# the two sitemap routes because the SPA is static and cannot generate a
# database-driven sitemap. They are declared here so both roots declare them
# identically rather than Root A having them and Root B not.

_SITEMAP_CACHE = "public, max-age=3600"


def add_root_routes(app: FastAPI) -> None:
    """`/`, `/health`, `/ready` and the two sitemap routes."""
    from app.api.services import sitemap_service
    from app.db.dynamo.client import check_db_ready

    @app.get("/")
    def read_root() -> Dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {
            "name": "CarModPicker API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    def health_check() -> Dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint for monitoring (liveness: app is running)."""
        return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}

    @app.get("/ready", response_model=None)
    def readiness_check() -> "Dict[str, Any] | JSONResponse":  # pyright: ignore[reportUnusedFunction]
        """
        Readiness check: returns 200 when DynamoDB is reachable, 503 otherwise.

        Use this so load balancers or the frontend can wait until the backend
        can reach its tables before sending traffic. During a cold start, poll
        /ready until 200, then call other endpoints.
        """
        if check_db_ready():
            return {"status": "ready", "database": "up"}
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "Service starting; database not ready. Please retry.",
                "error_code": "SERVICE_UNAVAILABLE",
            },
            headers={"Retry-After": "2"},
        )

    # SEO: the frontend is a static SPA on CloudFront and cannot generate a
    # database-driven sitemap, so the backend serves one. robots.txt points
    # Search Console at /sitemap.xml, a sitemap index that fans out to per-type
    # child sitemaps. Cached for an hour at the edge; freshness within a day is
    # plenty for SEO.
    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap_index() -> Response:  # pyright: ignore[reportUnusedFunction]
        return Response(
            content=sitemap_service.generate_sitemap_index(),
            media_type="application/xml",
            headers={"Cache-Control": _SITEMAP_CACHE},
        )

    @app.get("/sitemap-{name}.xml", include_in_schema=False)
    def sitemap_child(  # pyright: ignore[reportUnusedFunction]
        name: str,
        page: int = Query(1, ge=1),
    ) -> Response:
        xml = sitemap_service.generate_child_sitemap(name, page)
        if xml is None:
            return Response(
                content="Not found",
                status_code=404,
                media_type="text/plain",
            )
        return Response(
            content=xml,
            media_type="application/xml",
            headers={"Cache-Control": _SITEMAP_CACHE},
        )


def build_domain_app(
    domains: "Domain | str | Sequence[Domain | str]",
    *,
    title: "str | None" = None,
    include_root_routes: bool = True,
    startup_tasks: "Callable[[], None] | None" = None,
) -> FastAPI:
    """Build one application from one domain or many: Root B's whole job.

    Root A calls this with all nine descriptors and Root B with one, so the
    middleware stack, the exception handlers, the CORS policy, the lifespan and
    the root routes come from this one place and cannot differ between them.

    `startup_tasks` is injectable so `app.main` can keep the module-level
    `run_startup_tasks` name that `tests/test_lambda_handler.py` patches. It
    defaults to this module's own, which is the same function body.
    """
    from app.api.dependencies.repositories import bind_repositories
    from app.composition.domains import DOMAINS

    if isinstance(domains, (Domain, str)):
        domains = [domains]
    resolved = [DOMAINS[d] if isinstance(d, str) else d for d in domains]

    # A root serving no domain that seeds does not wire the seed at all, so a
    # function with read-only IAM on the car tables never attempts the write.
    seeds = any(domain.seeds for domain in resolved)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # The signing key check runs on every startup, ungated, and before the
        # seed. It cannot live at module scope in a composition root, because
        # `settings.SECRET_KEY` resolves through Secrets Manager on first read
        # and a module-scope read would put that fetch on the import path of
        # every process importing the root, the test suite included. It also
        # cannot ride along inside the `seeds and RUN_STARTUP_TASKS` branch
        # below: Lambda sets `RUN_STARTUP_TASKS` false and a domain that seeds
        # nothing skips that branch entirely, so the check would be silently
        # skipped exactly where a missing key matters most.
        #
        # `resolved` is this application's own domains, so a root serving no
        # domain that names SECRET_KEY still asks for nothing and still needs no
        # Secrets Manager grant.
        check_signing_key(resolved)
        if seeds and settings.RUN_STARTUP_TASKS:
            # Resolved on each startup rather than bound when the application is
            # built, so `tests/test_lambda_handler.py` can patch
            # `app.main.run_startup_tasks` and have the patch take effect. A
            # callable bound at build time would have been captured before the
            # patch existed.
            (startup_tasks or run_startup_tasks)()
        yield

    app = FastAPI(
        title=title if title is not None else settings.PROJECT_NAME,
        openapi_url=f"{settings.API_STR}/openapi.json",
        debug=settings.DEBUG,
        lifespan=lifespan,
        **{k: v for domain in resolved for k, v in domain.extra.items()},
    )

    add_shared_middleware(app)

    # Bind this application's repository bundle before the routers are
    # registered, so every route it carries resolves `Depends(get_repositories)`
    # to the domains actually being served. Root A passes nine domains and gets
    # the union, which is all twenty-five; Root B passes one and gets that
    # domain's tuple, and every other repository raises rather than handing back
    # a live handle on a table the function has no grant for.
    #
    # Bound to the application rather than installed on the module, because
    # `tests/entrypoints/test_route_split.py` builds all nine Root B
    # applications in one interpreter and a process-wide install would leave the
    # last one serving every test after it.
    bind_repositories(app, bundle_for(resolved))

    for domain in resolved:
        for router, prefix, tags in domain.load_routers():
            app.include_router(
                router,
                prefix=f"{domain.router_prefix}{prefix}",
                tags=list(tags or domain.router_tags),
            )

    # The shared identity standard's M1 through M4, on the `identity` domain only.
    # Row 5 of `docs/migration/cmp-identity-plan.md`;
    # `app/composition/identity.py` carries the full rationale for what mounts
    # and why, and `app/composition/identity_hooks.py` for the product policy it
    # is given.
    #
    # AFTER the loop above, which is load bearing rather than tidy. The four
    # legacy routers declare `POST /api/auth/logout` and
    # `POST /api/auth/verify-email`, which the package also declares, and FastAPI
    # keeps the first match. Mounting this second is what leaves both legacy
    # routes serving, which is what makes this row additive: the legacy flow is
    # untouched until row 13 deletes it.
    #
    # WITH NO PREFIX OF ITS OWN. `build_identity_router` places every route it
    # declares under `identity_prefix(settings)`, the issuer's path, which
    # `terraform/identity.tf` renders as `/api/auth`. Passing a prefix here would
    # double every path to `/api/auth/api/auth/...`, and reimplementing the
    # derivation would be a second source of truth for a URL that API Gateway
    # builds from the issuer at `CreateAuthorizer` time. This is also why it does
    # not go through `domain.load_routers`, which mounts everything it loads
    # under this domain's own `/api`.
    #
    # Guarded on `IDENTITY_ISSUER` being set, for the reason that field's own
    # comment in `app/core/config.py` gives: `IdentitySettings` requires it and
    # raises without it, and a local checkout or a test that builds the identity
    # application with no identity environment at all must not fail to construct.
    # In a deployed identity function Terraform always sets it, so the guard is
    # never the reason a document is missing there; a function whose environment
    # is half configured still fails loudly at startup, inside `IdentitySettings`,
    # naming the field it is missing.
    #
    # This is why Root A is unaffected. The monolith's environment carries no
    # `IDENTITY_ISSUER`, so `tests/fixtures/route_contract.json` and
    # `tests/test_openapi_snapshot.py` pin exactly what they pinned before, and
    # the package's routes are a thing the identity function serves rather than a
    # thing the published contract grows.
    for domain in resolved:
        if domain.name == "identity" and settings.IDENTITY_ISSUER:
            from app.composition.identity import build_router as build_identity_router

            app.include_router(build_identity_router(settings))

    if include_root_routes:
        add_root_routes(app)

    # Attach the FastAPI instrumentation only when `configure_tracing` actually
    # installed a provider, which today is never. Calling it unconditionally
    # would be safe but pointless: with no provider the instrumentation records
    # into the API's no-op spans and only costs a middleware on every request.
    # It has to happen here rather than after the application starts serving:
    # `instrument_app` can only inject its server span middleware while the
    # middleware stack is still unbuilt, and past that point the application
    # looks instrumented and emits nothing.
    from webbpulse.otel import is_tracing_enabled

    if _TRACING_CONFIGURED and is_tracing_enabled():
        from webbpulse.otel import instrument_fastapi

        instrument_fastapi(app)

    return app
