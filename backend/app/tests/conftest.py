import os
import sys
from pathlib import Path
from typing import Any, Callable, Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add the parent directory to sys.path to make app imports work
sys.path.append(str(Path(__file__).parent.parent.parent))

# Load environment variables from .env.test first
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.test")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path, override=True)
else:
    print(
        f"Warning: .env.test file not found at {dotenv_path}. Test database URL might not be configured correctly."
    )

TEST_DATABASE_URL = os.getenv("DATABASE_URL")
if not TEST_DATABASE_URL:
    print("Warning: DATABASE_URL not found in environment after loading .env.test.")

# Set environment variable to disable rate limiting for tests
os.environ["ENABLE_RATE_LIMITING"] = "false"

# Create a test-specific settings object that will be used
# Important: This needs to happen BEFORE any other imports from the app
from app.core.config import Settings, get_settings


def get_test_settings() -> Settings:
    # Settings will now be initialized using environment variables
    # loaded from .env.test, including DATABASE_URL
    # Disable rate limiting for tests
    settings = Settings(
        SECRET_KEY="test-secret-key",
        SENDGRID_API_KEY="test-sendgrid-key",
        EMAIL_FROM="test@example.com",
        SENDGRID_VERIFY_EMAIL_TEMPLATE_ID="test-verify-template",
        SENDGRID_RESET_PASSWORD_TEMPLATE_ID="test-reset-template",
    )
    settings.ENABLE_RATE_LIMITING = False
    return settings


# Override the settings provider and clear the cache
import app.core.config

# Clear the cache to ensure fresh settings
app.core.config.get_settings.cache_clear()
# Type ignore for the assignment since we're intentionally overriding the function
app.core.config.get_settings = get_test_settings  # type: ignore

from app.db.base import Base
from app.db.session import get_db

# Only now import the rest of the app
from app.main import app as fastapi_app

engine = create_engine(
    TEST_DATABASE_URL
    or "sqlite:///./test.db"  # This engine is for test setup (creating tables, direct test sessions)
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables() -> Generator[None, None, None]:
    # Create tables in the test database before any tests run
    # Ensure all models are imported so Base.metadata is complete
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="function")
def db_session(create_test_tables: None) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    # Create a session bound to this specific connection and transaction
    session = TestingSessionLocal(bind=connection)

    try:
        yield session  # provide the session for the test
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    # Define an override_get_db that uses the db_session for the current test
    def _override_get_db_for_test() -> Generator[Session, None, None]:
        yield db_session

    original_override = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_get_db_for_test

    with TestClient(fastapi_app) as c:
        yield c

    # Clean up the override after the test
    if original_override:
        fastapi_app.dependency_overrides[get_db] = original_override
    else:
        del fastapi_app.dependency_overrides[get_db]
