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
    #: Whether the domain seeds the tables it owns on startup.
    seeds: bool = False
    #: Extra keyword arguments for `FastAPI(...)`.
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def service_name(self) -> str:
        return SERVICE_NAME_TEMPLATE.format(domain=self.name)


def configure_logging() -> None:
    """The application's log format, applied to the root and uvicorn loggers.

    Lifted verbatim out of `app/main.py`'s module body so both roots get the
    same handlers rather than Root B getting whatever the default is. Still
    module-level work in practice, because `app/main.py` has always done it at
    import and the deployed monolith depends on that, but calling it twice is
    harmless: it re-points the same handlers at the same formatter.
    """
    from app.core.log_context import RequestContextFilter
    from app.core.logging import LOG_FORMAT, make_formatter

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )
    formatter = make_formatter()
    context_filter = RequestContextFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        for handler in log.handlers:
            handler.setFormatter(formatter)
            handler.addFilter(context_filter)


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

    # Chrome extensions send requests with a null origin (service workers) or a
    # chrome-extension:// origin (popup and content scripts). Both are allowed:
    # `allow_origins` carries "null" and `allow_origin_regex` carries the scheme.
    # With `allow_credentials=True` the regex is used alongside `allow_origins`,
    # not instead of it.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"chrome-extension://.*",
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
    from app.composition.domains import DOMAINS

    if isinstance(domains, (Domain, str)):
        domains = [domains]
    resolved = [DOMAINS[d] if isinstance(d, str) else d for d in domains]

    # A root serving no domain that seeds does not wire the seed at all, so a
    # function with read-only IAM on the car tables never attempts the write.
    seeds = any(domain.seeds for domain in resolved)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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

    for domain in resolved:
        for router, prefix, tags in domain.load_routers():
            app.include_router(
                router,
                prefix=f"{domain.router_prefix}{prefix}",
                tags=list(tags or domain.router_tags),
            )

    if include_root_routes:
        add_root_routes(app)

    return app
