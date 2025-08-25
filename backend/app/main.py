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
)
from .api.middleware import rate_limit_middleware
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

app.include_router(users.router, prefix=settings.API_STR + "/users", tags=["users"])
app.include_router(cars.router, prefix=settings.API_STR + "/cars", tags=["cars"])
app.include_router(
    build_lists.router, prefix=settings.API_STR + "/build-lists", tags=["build_lists"]
)
app.include_router(
    global_parts.router,
    prefix=settings.API_STR + "/global-parts",
    tags=["global_parts"],
)
app.include_router(
    build_list_parts.router,
    prefix=settings.API_STR + "/build-list-parts",
    tags=["build_list_parts"],
)
app.include_router(auth.router, prefix=settings.API_STR + "/auth", tags=["auth"])
app.include_router(
    subscriptions.router,
    prefix=settings.API_STR + "/subscriptions",
    tags=["subscriptions"],
)
app.include_router(
    categories.router,
    prefix=settings.API_STR + "/categories",
    tags=["categories"],
)
app.include_router(
    global_part_votes.router,
    prefix=settings.API_STR + "/global-part-votes",
    tags=["global_part_votes"],
)
app.include_router(
    global_part_reports.router,
    prefix=settings.API_STR + "/global-part-reports",
    tags=["global_part_reports"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}
