import os
from typing import Generator, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Disable rate limiting for tests
os.environ["ENABLE_RATE_LIMITING"] = "false"

# Load test environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.test")
if os.path.exists(dotenv_path):
    from dotenv import load_dotenv

    load_dotenv(dotenv_path)
else:
    print(
        f"Warning: .env.test file not found at {dotenv_path}. "
        "Test database URL might not be configured correctly."
    )

# Check if DATABASE_URL is set
if not os.getenv("DATABASE_URL"):
    print("Warning: DATABASE_URL not found in environment after loading .env.test.")

# Import after environment setup
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.api.models.category import Category
from app.api.models.user import User
from app.api.dependencies.auth import get_password_hash
from app.main import app as fastapi_app

# Create test database engine
# Use in-memory SQLite for tests by default, or PostgreSQL if DATABASE_URL is set
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or "sqlite:///./test.db"  # This engine is for test setup (creating tables, direct test sessions)
)

# Configure engine based on database type
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL or other databases
    engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the get_db dependency for testing
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override the dependency
fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with a fresh database session."""
    with TestClient(fastapi_app) as test_client:
        yield test_client


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for testing."""
    user = User(
        username="test_user",
        email="test_user@example.com",
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


@pytest.fixture
def test_category(db_session: Session) -> Category:
    """Create a test category for testing."""
    category = Category(
        name="test_category",
        display_name="Test Category",
        description="A test category",
        is_active=True,
        sort_order=1,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        username="admin_user",
        email="admin_user@example.com",
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


@pytest.fixture
def superuser_user(db_session: Session) -> User:
    """Create a superuser for testing."""
    user = User(
        username="superuser",
        email="superuser@example.com",
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


# Standardized helper functions for consistent user handling across tests
def create_and_login_user(
    client: TestClient,
    username_suffix: str,
    password: str = "testpassword",
    is_admin: bool = False,
    is_superuser: bool = False,
) -> Dict:
    """
    Create a user and log them in. Returns user data dictionary.

    Args:
        client: TestClient instance
        username_suffix: Unique suffix for username
        password: User password (default: "testpassword")
        is_admin: Whether user should be admin
        is_superuser: Whether user should be superuser

    Returns:
        Dict containing user data
    """
    from app.core.config import settings

    username = f"test_user_{username_suffix}"
    email = f"test_user_{username_suffix}@example.com"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }

    # Create user via API
    response = client.post(f"{settings.API_STR}/users/", json=user_data)

    if response.status_code == 200:
        user_data = response.json()
    elif (
        response.status_code == 400
        and "already registered" in response.json().get("detail", "").lower()
    ):
        # User exists, fetch their data
        pass
    else:
        response.raise_for_status()

    # Log in to set cookie on client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)

    if token_response.status_code != 200:
        raise Exception(f"Failed to log in user {username}: {token_response.text}")

    # If user wasn't created in this call, fetch their data
    if response.status_code != 200:
        me_response = client.get(f"{settings.API_STR}/users/me")
        if me_response.status_code == 200:
            user_data = me_response.json()
        else:
            raise Exception(f"Could not retrieve user data for {username}")

    return user_data


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> User:
    """
    Create an admin user directly in database and log them in.

    Args:
        client: TestClient instance
        db_session: Database session
        username_suffix: Unique suffix for username

    Returns:
        User object
    """
    from app.core.config import settings

    username = f"admin_user_{username_suffix}"
    email = f"admin_user_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
    admin_user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_admin=True,
        is_superuser=False,
        email_verified=True,
        disabled=False,
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    # Log in to set cookie on client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)

    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in admin user {username}: {token_response.text}"
        )

    return admin_user
