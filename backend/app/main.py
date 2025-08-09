from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.endpoints import auth
from .api.endpoints import users
from .api.endpoints import cars
from .api.endpoints import parts
from .api.endpoints import build_lists
import subprocess
import os
import logging

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def run_migrations():
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
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix=settings.API_STR + "/users", tags=["users"])
app.include_router(cars.router, prefix=settings.API_STR + "/cars", tags=["cars"])
app.include_router(
    build_lists.router, prefix=settings.API_STR + "/build-lists", tags=["build_lists"]
)
app.include_router(parts.router, prefix=settings.API_STR + "/parts", tags=["parts"])
app.include_router(auth.router, prefix=settings.API_STR + "/auth", tags=["auth"])


@app.get("/")
def read_root():
    return {"Hello": "World"}
