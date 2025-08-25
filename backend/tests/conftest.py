import os
from typing import Generator, Dict, Optional, Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Disable rate limiting for tests
os.environ["ENABLE_RATE_LIMITING"] = "false"

# Import after environment setup
from app.db.base import Base
from app.db.session import get_db
from app.api.models.category import Category
from app.api.models.user import User
from app.api.dependencies.auth import get_password_hash
from app.main import app as fastapi_app


# Get worker ID for parallel testing
def get_worker_id() -> Optional[str]:
    """Get the worker ID for parallel testing, or None if not in parallel mode."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id:
        # Extract the worker number from the worker ID
        return worker_id.replace("gw", "")
    return None


def get_test_database_url() -> str:
    """Get the test database URL - always use SQLite in-memory for tests."""
    # Always use in-memory database for tests to avoid file system dependencies
    # and ensure complete isolation between tests
    return "sqlite:///:memory:"


# Global session factory for testing
TestingSessionLocal: Optional[sessionmaker] = None


def get_test_session_factory() -> sessionmaker:
    """Get the test session factory, creating it if needed."""
    global TestingSessionLocal
    # Always create a fresh session factory for each test
    # Create engine for session factory
    database_url = get_test_database_url()

    engine = create_engine(
        database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal


@pytest.fixture(scope="session")
def engine() -> Generator[Any, None, None]:
    """Create a test database engine."""
    database_url = get_test_database_url()

    # Create engine with specific settings for testing
    engine = create_engine(
        database_url,
        poolclass=StaticPool,  # Use static pool for testing
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Clean up - drop all tables
    Base.metadata.drop_all(bind=engine)

    # Close the engine to release file handles
    engine.dispose()


def override_get_db() -> Generator[Session, None, None]:
    """Override the database dependency for testing."""
    session_factory = get_test_session_factory()
    try:
        db = session_factory()
        yield db
    finally:
        db.rollback()
        db.close()


# Override the dependency
fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    session_factory = get_test_session_factory()
    session = session_factory()

    try:
        yield session
    finally:
        # Clean up all data from the session
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with a fresh database session."""

    # Override the database dependency to use the same session as the test
    def override_get_db_for_test() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass  # Don't close the session here, it's managed by the fixture

    fastapi_app.dependency_overrides[get_db] = override_get_db_for_test

    with TestClient(fastapi_app) as test_client:
        yield test_client

    # Clean up the override
    fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user for testing."""
    user = User(
        username=f"test_user_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=False,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_category(db_session: Session) -> Category:
    """Create a test category for testing."""
    category = Category(
        name=f"test_category_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        display_name=f"Test Category {os.getpid()}_{id(db_session)}",
        description="A test category",
        is_active=True,
        sort_order=1,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture(scope="function")
def test_admin_user(db_session: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        username=f"admin_user_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"admin_user_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_superuser_user(db_session: Session) -> User:
    """Create a superuser for testing."""
    user = User(
        username=f"superuser_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"superuser_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Test utilities
def get_default_category_id(db_session: Session) -> int:
    """Get the ID of the 'other' category for testing."""
    category = db_session.query(Category).filter(Category.name == "other").first()
    if not category:
        # Create the 'other' category if it doesn't exist
        category = Category(
            name="other",
            display_name="Other",
            description="Miscellaneous parts",
            is_active=True,
            sort_order=999,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)
    return category.id


def login_user(
    client: TestClient, username: str, password: str = "testpassword"
) -> None:
    """Login a user and set the authentication cookie for subsequent requests."""
    from app.core.config import settings

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200
    # The cookie is automatically set by the response


def create_and_login_user(
    client: TestClient, username: str, password_override: str = "testpassword"
) -> dict:
    """Create a user and log them in, returning the user info."""
    from app.core.config import settings

    # Create user
    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": password_override,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert response.status_code == 200
    user_data_response = response.json()
    assert isinstance(user_data_response, dict)

    # Manually verify the email for testing purposes
    from app.api.models.user import User
    from app.db.session import get_db

    # Get the database session from the test client
    db = next(get_db())
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.email_verified = True
        db.commit()
        db.close()

    # Login
    login_user(client, username, password_override)

    return user_data_response


def create_car_for_user_cookie_auth(client: TestClient) -> int:
    """Create a car for the currently logged-in user."""
    from app.core.config import settings

    car_data = {
        "make": "Toyota",
        "model": "Camry",
        "year": 2020,
    }
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert response.status_code == 200
    car_data_response = response.json()
    assert isinstance(car_data_response, dict)
    car_id = car_data_response["id"]
    assert isinstance(car_id, int)
    return car_id


def create_and_login_admin_user(client: TestClient, username: str) -> User:
    """Create an admin user and log them in."""
    from app.core.config import settings

    # Create admin user
    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "testpassword",
    }
    response = client.post(f"{settings.API_STR}/auth/register", json=user_data)
    assert response.status_code == 200
    admin_user_data = response.json()
    assert isinstance(admin_user_data, dict)

    # Login
    login_user(client, username)

    # Return a mock User object since we can't easily construct one from the response
    # This is a test utility function, so this is acceptable
    from app.api.models.user import User

    return User(
        id=admin_user_data.get("id", 0),
        username=admin_user_data.get("username", ""),
        email=admin_user_data.get("email", ""),
        hashed_password="",
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=False,
    )
