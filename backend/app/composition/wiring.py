"""What a domain is, and how one application is built from any subset of them.

Both roots build through `build_domain_app`, so they cannot drift. Composition
is `include_router` and never `mount`, which would empty the OpenAPI document.
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

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

logger = logging.getLogger(__name__)

API_PREFIX = settings.API_STR

SERVICE_NAME_TEMPLATE = "carmodpicker-{domain}"


@dataclass(frozen=True)
class Domain:
    """One deployable domain."""

    name: str
    title: str
    load_routers: Callable[[], "Sequence[Tuple[APIRouter, str, Tuple[str, ...]]]"]
    router_prefix: str = API_PREFIX
    router_tags: Tuple[str, ...] = ()
    requires_secrets: Tuple[str, ...] = ()
    repositories: Tuple[str, ...] = ()
    seeds: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def service_name(self) -> str:
        """The service name this domain logs and traces under."""
        return SERVICE_NAME_TEMPLATE.format(domain=self.name)

    @property
    def tables(self) -> Tuple[str, ...]:
        """The DynamoDB tables this domain's repositories reach, sorted.

        Read from the repository registry rather than listed again, so the two and
        the Terraform IAM policy cannot disagree.
        """
        from app.db.dynamo.registry import tables_for

        return tables_for(self.repositories)


def configure_logging(service: "str | None" = None) -> None:
    """The application's log format, applied to the root and uvicorn loggers.

    A thin call into `app.core.logging.configure_app_logging`. Called at import
    by `app/main.py`; calling it twice is harmless.
    """
    from app.core.logging import configure_app_logging

    configure_app_logging(
        level=settings.log_level,
        service=service or settings.PROJECT_NAME,
        environment=settings.environment,
    )


OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"

_TRACING_CONFIGURED = False


def configure_tracing(domain: "Domain") -> bool:
    """Wire OpenTelemetry for one domain, but only when an OTLP endpoint is set.

    The gate is deliberate: without it the package would default to the X-Ray
    endpoint and every process would retry a 403 in silence.
    """
    global _TRACING_CONFIGURED
    import os

    if not os.environ.get(OTLP_ENDPOINT_ENV, "").strip():
        logger.debug(
            "Tracing not configured: %s is unset.",
            OTLP_ENDPOINT_ENV,
        )
        return False

    from webbpulse.otel import configure_tracing as _configure_tracing
    from webbpulse.otel import resolve_sample_ratio

    configured = _configure_tracing(
        domain.service_name,
        environment=settings.environment,
        sample_ratio=resolve_sample_ratio(),
    )
    _TRACING_CONFIGURED = _TRACING_CONFIGURED or configured
    return configured


def check_signing_key(domains: "Iterable[Domain]") -> None:
    """Fail fast on a missing secret, once at startup, per the domains served.

    A root serving no domain that names a secret never calls `require_secrets`,
    which is what lets `vehicles` run with no Secrets Manager grant.
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

    Building the bundle constructs no repository, so an image's import graph
    stays proportional to the routes it serves.
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
    """CORS, request context, rate limiting and the error handlers, for both roots.

    The order is load-bearing: Starlette runs middleware outermost-first in the
    order added, so CORS wraps request context which wraps the rate limiter.
    """
    from app.api.middleware import rate_limit_middleware, request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

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

    app.middleware("http")(request_context_middleware)
    app.middleware("http")(rate_limit_middleware)
    register_error_handlers(app)


_SITEMAP_CACHE = "public, max-age=3600"

_UNPUBLISHED = " "
"""Passed as a route `description` to keep a handler's docstring out of the OpenAPI schema."""


def add_root_routes(app: FastAPI) -> None:
    """`/`, `/health`, `/ready` and the two sitemap routes."""
    from app.api.services import sitemap_service
    from app.db.dynamo.client import check_db_ready

    @app.get("/", description=_UNPUBLISHED)
    def read_root() -> Dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Name, version and the two probe paths, for a bare hit on the root."""
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

    @app.get(
        "/ready",
        response_model=None,
        description=(
            "Readiness check: returns 200 when DynamoDB is reachable, 503 otherwise.\n\n"
            "Use this so load balancers or the frontend can wait until the backend\n"
            "can reach its tables before sending traffic. During a cold start, poll\n"
            "/ready until 200, then call other endpoints."
        ),
    )
    def readiness_check() -> "Dict[str, Any] | JSONResponse":  # pyright: ignore[reportUnusedFunction]
        """Return 200 when DynamoDB is reachable and 503 otherwise.

        Lets a load balancer or the frontend hold traffic back until the backend
        can reach its tables.
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

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap_index() -> Response:  # pyright: ignore[reportUnusedFunction]
        """The sitemap index listing every child sitemap."""
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
        """One page of a named child sitemap, or 404 when the name is unknown."""
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

    `startup_tasks` is injectable so `app.main` can keep the module-level
    `run_startup_tasks` name the suite patches.
    """
    from app.api.dependencies.repositories import bind_repositories
    from app.composition.domains import DOMAINS

    if isinstance(domains, (Domain, str)):
        domains = [domains]
    resolved = [DOMAINS[d] if isinstance(d, str) else d for d in domains]

    seeds = any(domain.seeds for domain in resolved)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Verify the signing key, then run startup seeding when this domain seeds."""
        check_signing_key(resolved)
        if seeds and settings.RUN_STARTUP_TASKS:
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

    bind_repositories(app, bundle_for(resolved))

    for domain in resolved:
        for router, prefix, tags in domain.load_routers():
            app.include_router(
                router,
                prefix=f"{domain.router_prefix}{prefix}",
                tags=list(tags or domain.router_tags),
            )

    for domain in resolved:
        if domain.name == "identity" and settings.IDENTITY_ISSUER:
            from app.composition.identity import build_router as build_identity_router
            from app.composition.identity_extension import build_router as build_extension_router

            app.include_router(build_identity_router(settings))

            app.include_router(build_extension_router(settings))

    if include_root_routes:
        add_root_routes(app)

    from webbpulse.otel import is_tracing_enabled

    if _TRACING_CONFIGURED and is_tracing_enabled():
        from webbpulse.otel import instrument_fastapi

        instrument_fastapi(app)

    return app
