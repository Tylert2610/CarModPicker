import logging
import os
import subprocess
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.endpoints import (
    auth,
    build_lists,
    build_list_parts,
    cars,
    global_parts,
    users,
    subscriptions,
    categories,
    global_part_votes,
    global_part_reports,
    car_votes,
    car_reports,
    build_list_votes,
    build_list_reports,
)
from .api.middleware import rate_limit_middleware
from .api.middleware.error_handler import register_error_handlers
from .api.utils.endpoint_registry import EndpointRegistry
from .core.config import settings

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run database migrations on startup"""
    try:
        logger.info("Running database migrations...")
        # Determine the correct working directory for alembic
        cwd = (
            "/app"
            if os.path.exists("/app/alembic")
            else os.path.dirname(os.path.dirname(__file__))
        )
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Migrations completed successfully: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e.stderr}")
        # Don't fail startup if migrations fail - let the app start and handle DB errors gracefully
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")


# Run migrations on startup
run_migrations()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    debug=settings.DEBUG,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Register error handlers for standardized error responses
register_error_handlers(app)

# Create endpoint registry for standardized registration
endpoint_registry = EndpointRegistry(app)

# Register all endpoints using the registry
# Core CRUD endpoints
endpoint_registry.register_crud_endpoint(
    users.router, entity_name="users", description="User management operations"
)

endpoint_registry.register_crud_endpoint(
    cars.router, entity_name="cars", description="Car management operations"
)

endpoint_registry.register_crud_endpoint(
    build_lists.router,
    entity_name="build-lists",
    description="Build list management operations",
)

endpoint_registry.register_crud_endpoint(
    global_parts.router,
    entity_name="global-parts",
    description="Global part catalog operations",
)

endpoint_registry.register_crud_endpoint(
    build_list_parts.router,
    entity_name="build-list-parts",
    description="Build list part management operations",
)

endpoint_registry.register_crud_endpoint(
    categories.router,
    entity_name="categories",
    description="Category management operations",
)

# Authentication endpoint
endpoint_registry.register_endpoint(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
    description="User authentication and authorization",
)

# Subscription endpoint
endpoint_registry.register_endpoint(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"],
    description="Subscription and billing operations",
)

# Vote endpoints
endpoint_registry.register_vote_endpoint(
    car_votes.router, entity_name="cars", description="Car voting operations"
)

endpoint_registry.register_vote_endpoint(
    global_part_votes.router,
    entity_name="global-parts",
    description="Global part voting operations",
)

endpoint_registry.register_vote_endpoint(
    build_list_votes.router,
    entity_name="build-lists",
    description="Build list voting operations",
)

# Report endpoints
endpoint_registry.register_report_endpoint(
    car_reports.router, entity_name="car", description="Car reporting operations"
)

endpoint_registry.register_report_endpoint(
    global_part_reports.router,
    entity_name="global-parts",
    description="Global part reporting operations",
)

endpoint_registry.register_report_endpoint(
    build_list_reports.router,
    entity_name="build-lists",
    description="Build list reporting operations",
)

# Print registration summary
endpoint_registry.print_registration_summary()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}
