import os
import pytest
from typing import Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Helper to create a user directly in the DB for testing login
# This is an alternative to calling the /users/ endpoint if you want to bypass API validation for setup
from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser  # For direct DB manipulation if needed
from app.core.config import settings


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_test_user_direct_db(
    db: Session, username: str, email: str, password: str, disabled: bool = False
) -> DBUser:
    hashed_password = get_password_hash(password)
    db_user = DBUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        disabled=disabled,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def test_login_for_access_token_success(client: TestClient) -> None:
    username = get_unique_username(
        "auth_test_user_cookie"
    )  # Ensure unique username for test
    password = "auth_test_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    # Create user via API
    create_user_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_user_response.status_code == 200
    ), f"Failed to create user for auth test: {create_user_response.text}"

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 200, response.text

    # 1. Check for the cookie
    assert "access_token" in response.cookies
    access_token_cookie_value = response.cookies.get("access_token")
    assert access_token_cookie_value is not None

    # 2. Check cookie attributes by parsing the Set-Cookie header
    # Note: httpx.Cookies (used by TestClient) doesn't directly expose all attributes like HttpOnly easily.
    # Parsing the header is a reliable way.
    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert "access_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/" in set_cookie_header
    assert f"Max-Age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header  # Or your configured samesite policy
    # 'secure' attribute is not set in your current /token endpoint logic for non-HTTPS dev
    assert "Secure" not in set_cookie_header

    # 3. Check the response body for user details (UserRead schema)
    response_data = response.json()
    assert response_data["username"] == username
    assert response_data["email"] == email
    assert "id" in response_data
    assert isinstance(
        response_data["id"], int
    )  # or str, depending on your UserRead schema for id
    assert response_data["disabled"] is False
    assert "hashed_password" not in response_data  # Ensure password is not returned
    assert "access_token" not in response_data  # Ensure token is not in body
    assert "token_type" not in response_data  # Ensure token_type is not in body


def test_login_for_access_token_incorrect_username(client: TestClient) -> None:
    login_data = {"username": "wronguser_cookie", "password": "password123"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
    assert "access_token" not in response.cookies  # Check no cookie is set


def test_login_for_access_token_incorrect_password(
    client: TestClient, db_session: Session
) -> None:
    username = get_unique_username(
        "auth_test_user_wrong_pass_cookie"
    )  # Ensure unique username
    password = "correct_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_response.status_code == 200
    ), f"User creation failed: {create_response.text}"

    login_data = {"username": username, "password": "wrong_password"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
    assert "access_token" not in response.cookies  # Check no cookie is set


def test_login_for_access_token_disabled_user(
    client: TestClient, db_session: Session
) -> None:
    username = get_unique_username("disabled_user_cookie")  # Ensure unique username
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_response.status_code == 200
    ), f"User creation failed: {create_response.text}"
    user_id = create_response.json()["id"]

    # Log in as the user. The cookie will be set in the client for subsequent requests.
    login_data_for_session = {"username": username, "password": password}
    token_response = client.post(
        f"{settings.API_STR}/auth/token", data=login_data_for_session  # Changed
    )
    assert (
        token_response.status_code == 200
    ), f"Login to get session cookie failed: {token_response.text}"
    assert "access_token" in token_response.cookies  # Verify cookie was set

    # Disable the user via API. The client will automatically send the cookie.
    # This assumes the PUT /users/{user_id} endpoint is protected by a dependency
    # (e.g., get_current_user) that now reads the authentication token from the cookie.
    update_payload = {
        "disabled": True,
        "current_password": password,
    }  # Add current_password
    # No explicit headers needed if the dependency reads from cookie
    update_response = client.put(
        f"{settings.API_STR}/users/{user_id}", json=update_payload
    )
    assert (
        update_response.status_code == 200
    ), f"Failed to disable user: {update_response.text}"
    assert update_response.json()["disabled"] is True

    # Clear cookies from the client to ensure the next login attempt is fresh
    client.cookies.clear()

    # Attempt to login as the now disabled user
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Inactive user"
    assert "access_token" not in response.cookies  # Ensure no new cookie is set
