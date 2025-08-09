import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

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


# Create a test-specific settings object that will be used
# Important: This needs to happen BEFORE any other imports from the app
from app.core.config import Settings, get_settings


def get_test_settings():
    # Settings will now be initialized using environment variables
    # loaded from .env.test, including DATABASE_URL
    return Settings()


# Override the settings provider
import app.core.config

app.core.config.get_settings = get_test_settings

# Only now import the rest of the app
from app.main import app
from app.db.base import Base
from app.db.session import get_db

engine = create_engine(
    TEST_DATABASE_URL  # This engine is for test setup (creating tables, direct test sessions)
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    # Create tables in the test database before any tests run
    # Ensure all models are imported so Base.metadata is complete
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="function")
def db_session(create_test_tables):
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
def client(db_session):
    # Define an override_get_db that uses the db_session for the current test
    def _override_get_db_for_test():
        yield db_session

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db_for_test

    with TestClient(app) as c:
        yield c

    # Clean up the override after the test
    if original_override:
        app.dependency_overrides[get_db] = original_override
    else:
        del app.dependency_overrides[get_db]
