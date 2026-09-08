import logging
import warnings
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.endpoints import (
    app_settings,
    bug_reports,
    build_list_labor_estimates,
    build_list_parts,
    build_list_phases,
    build_lists,
    build_logs,
    car_generations,
    categories,
    crawled_pages,
    images,
    part_manufacturers,
    part_price_alerts,
    parts,
    reports,
    retailers,
    search,
    users,
    votes,
)
from .api.endpoints.admin import db_ops as admin_db_ops
from .api.endpoints.admin import stats as admin_stats
from .api.endpoints.auth import core as auth_core
from .api.endpoints.auth import oauth as auth_oauth
from .api.endpoints.auth import two_factor as auth_2fa
from .api.endpoints.auth import webauthn as auth_webauthn
from .api.middleware import rate_limit_middleware, request_context_middleware
from .api.middleware.error_handler import register_error_handlers
from .api.services import sitemap_service
from .api.utils.endpoint_registry import EndpointRegistry
from .core.config import settings
from .core.init_cars import init_car_generations
from .core.log_context import RequestContextFilter
from .core.logging import LOG_FORMAT, make_formatter
from .core.sentry import init_sentry
from .db.dynamo.client import check_db_ready

# Configure logging for the entire application (single format, colorized levels)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
_formatter = make_formatter()
_ctx_filter = RequestContextFilter()
_root = logging.getLogger()
for _h in _root.handlers:
    _h.setFormatter(_formatter)
    _h.addFilter(_ctx_filter)

# Apply same format and context filter to uvicorn loggers
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _log = logging.getLogger(_name)
    for _h in _log.handlers:
        _h.setFormatter(_formatter)
        _h.addFilter(_ctx_filter)

logger = logging.getLogger(__name__)

# Sentry SDK init — must run BEFORE `app = FastAPI(...)` so FastApiIntegration +
# StarletteIntegration can patch the route handlers. No-ops in dev / test (see
# init_sentry env gates). D-12.
init_sentry(server_name="apprunner-backend")

# This root serves the auth routes, so it needs a signing key and says so once,
# at startup, instead of failing per request inside jwt.encode. Outside a
# deployed environment an empty key stays a warning, which is what keeps local
# development and the test suite runnable without one.
if settings.is_production:
    settings.require_secrets("SECRET_KEY")
elif not settings.SECRET_KEY:
    warnings.warn(
        "SECRET_KEY is empty. JWT tokens will be insecure. Set SECRET_KEY environment variable.",
        UserWarning,
    )


def run_startup_tasks() -> None:
    try:
        init_car_generations()
    except Exception:
        logger.exception("Failed to initialize car generations on startup")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    if settings.RUN_STARTUP_TASKS:
        run_startup_tasks()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Add CORS middleware
# Restrict methods and headers for better security
# Note: Chrome extensions send requests with null origin (service workers) or
# chrome-extension:// origin (popup/content scripts). We allow both via:
# - allow_origins includes "null" for service workers
# - allow_origin_regex allows chrome-extension:// origins
# Note: When allow_credentials=True, we can still use allow_origin_regex,
# but it must be used alongside allow_origins (not instead of)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",  # Allow all Chrome extensions
    allow_origins=settings.allowed_origins_list,  # Includes "null" for service workers + web origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Restrict to needed methods
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Admin-Cron-Key",
    ],  # Restrict to needed headers
    expose_headers=["*"],  # Expose all headers for debugging
)

# Assign a UUID to every request and inject request_id/user_id into all log lines
app.middleware("http")(request_context_middleware)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Register error handlers for standardized error responses
register_error_handlers(app)

# Create endpoint registry for standardized registration
endpoint_registry = EndpointRegistry(app)

# Register all endpoints using the registry
# Core CRUD endpoints
endpoint_registry.register_crud_endpoint(users.router, entity_name="users", description="User management operations")

endpoint_registry.register_crud_endpoint(
    car_generations.router, entity_name="car-generations", description="Car generation management operations"
)

endpoint_registry.register_crud_endpoint(
    build_lists.router,
    entity_name="build-lists",
    description="Build list management operations",
)

endpoint_registry.register_crud_endpoint(
    parts.router,
    entity_name="parts",
    description="Part catalog operations",
)

endpoint_registry.register_crud_endpoint(
    build_list_parts.router,
    entity_name="build-list-parts",
    description="Build list part management operations",
)

endpoint_registry.register_crud_endpoint(
    build_list_phases.router,
    entity_name="build-list-phases",
    description="Build list phase update/delete operations",
)

endpoint_registry.register_crud_endpoint(
    build_list_labor_estimates.router,
    entity_name="build-list-labor-estimates",
    description="Build list labor estimate update/delete operations",
)

endpoint_registry.register_crud_endpoint(
    categories.router,
    entity_name="categories",
    description="Category management operations",
)

endpoint_registry.register_crud_endpoint(
    part_manufacturers.router,
    entity_name="part_manufacturers",
    description="Part manufacturer management operations",
)

endpoint_registry.register_crud_endpoint(
    retailers.router,
    entity_name="retailers",
    description="Retailer (store) management operations",
)

# Search endpoint
endpoint_registry.register_endpoint(
    search.router,
    prefix="/search",
    tags=["search"],
    description="Unified search across build lists, users, and global parts",
)

# Authentication endpoints (split into sub-routers per D-08/D-10)
endpoint_registry.register_endpoint(
    auth_core.router,
    prefix="/auth",
    tags=["authentication"],
    description="Authentication core (login, token refresh, email verify, password reset, logout)",
)
endpoint_registry.register_endpoint(
    auth_2fa.router,
    prefix="/auth/2fa",
    tags=["authentication"],
    description="TOTP 2FA setup and management",
)
endpoint_registry.register_endpoint(
    auth_webauthn.router,
    prefix="/auth/webauthn",
    tags=["authentication"],
    description="WebAuthn passkey registration and login",
)
endpoint_registry.register_endpoint(
    auth_oauth.router,
    prefix="/auth/oauth",
    tags=["authentication"],
    description="Google OAuth sign-in, link, connect, and account management",
)

# Unified vote and report endpoints
endpoint_registry.register_endpoint(
    votes.router,
    prefix="/votes",
    tags=["votes"],
    description="Unified voting operations for all entity types",
)

endpoint_registry.register_endpoint(
    reports.router,
    prefix="/reports",
    tags=["reports"],
    description="Unified reporting operations for all entity types",
)

# Bug reports endpoint
endpoint_registry.register_endpoint(
    bug_reports.router,
    prefix="/bug-reports",
    tags=["bug-reports"],
    description="Bug report operations for users to report application issues",
)

# Per-user price-drop alerts (subscribe / list-mine / patch / soft-delete)
endpoint_registry.register_endpoint(
    part_price_alerts.router,
    prefix="/part-price-alerts",
    tags=["part-price-alerts"],
    description="Per-user price-drop alerts",
)

# Image upload endpoint
endpoint_registry.register_endpoint(
    images.router,
    prefix="/images",
    tags=["images"],
    description="Image upload and management operations using S3",
)

# Chrome extension page parsing
endpoint_registry.register_endpoint(
    crawled_pages.router,
    prefix="/crawled-pages",
    tags=["crawled-pages"],
    description="Server-side parsing of chrome-extension submitted pages",
)

# Build logs endpoint
endpoint_registry.register_endpoint(
    build_logs.router,
    prefix="/build-logs",
    tags=["build-logs"],
    description="Forum-style build log threads for build lists",
)

# Admin endpoints (split into sub-routers per D-08/D-09)
endpoint_registry.register_endpoint(
    admin_stats.router,
    prefix="/admin/stats",
    tags=["admin"],
    description="Admin statistics (table counts)",
)
endpoint_registry.register_endpoint(
    admin_db_ops.router,
    prefix="/admin/db-ops",
    tags=["admin"],
    description="Admin database operations (init data, bulk delete)",
)
# Global app settings (public read, admin write)
endpoint_registry.register_endpoint(
    app_settings.router,
    prefix="/app-settings",
    tags=["app-settings"],
    description="Runtime-mutable global app settings (e.g. global ads toggle)",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "CarModPicker API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring (liveness: app is running)."""
    return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}


@app.get("/ready", response_model=None)
def readiness_check() -> dict[str, Any] | JSONResponse:
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


# --- SEO: dynamic XML sitemap ------------------------------------------------
# The frontend is a static SPA on CloudFront and can't generate a DB-driven
# sitemap, so the backend serves one. robots.txt points Google Search Console
# at /sitemap.xml (a sitemap index) which fans out to per-type child sitemaps.
# Cached for an hour at the edge — freshness within a day is plenty for SEO.
_SITEMAP_CACHE = "public, max-age=3600"


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_index() -> Response:
    return Response(
        content=sitemap_service.generate_sitemap_index(),
        media_type="application/xml",
        headers={"Cache-Control": _SITEMAP_CACHE},
    )


@app.get("/sitemap-{name}.xml", include_in_schema=False)
def sitemap_child(
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
