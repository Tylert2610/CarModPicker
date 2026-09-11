import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category as DBCategory
from app.db.dynamo.users import User
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user, save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_token(client: TestClient, username: str, password: str = "testpassword") -> str:
    """The credential for `username`, for use with `auth_headers`.

    A thin alias for `login_user` in `tests/conftest.py`, kept because this
    module's tests call it by this name. Row 13 of `docs/identity-adoption.md`
    deleted `POST /api/auth/token`, so what comes back is an identity request
    context rather than a bearer token; `password` is accepted and ignored.
    """
    return login_user(client, username, password)


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
    admin_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    # Log in and get token
    token = login_user(client, username)

    return admin_user.__dict__, token


class TestBuildLists:
    """Test cases for build lists endpoints."""

    def test_create_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully creating a build list."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]
        assert data["user_id"] == str(test_user.id)
        assert data["car_id"] == str(car["id"])

    def test_create_build_list_unauthorized(self, client: TestClient) -> None:
        """Test creating a build list without authentication."""
        # Try to create a build list without authentication
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 401

    def test_create_build_list_missing_name(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list without providing a name."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Try to create a build list without name
        build_list_data = {"description": "A test build list description", "car_id": str(car["id"])}
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_create_build_list_empty_name(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list with an empty name."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Try to create a build list with empty name
        build_list_data = {
            "name": "",
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_create_build_list_free_user_limit_402(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Free users are limited to 1 build list; second create returns 402."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        car = create_car_in_db(db_session)
        build_list_data = {
            "name": get_unique_name("first_build_list"),
            "description": "First",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        second_data = {
            "name": get_unique_name("second_build_list"),
            "description": "Second",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=second_data, headers=headers)
        assert response.status_code == 402
        data = response.json()
        msg = data.get("detail") or data.get("message") or ""
        if isinstance(msg, list):
            msg = msg[0].get("msg", "") if msg else ""
        assert "free" in str(msg).lower() or "limit" in str(msg).lower()

    def test_create_build_list_premium_user_unlimited(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Premium users can create multiple build lists."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)
        car = create_car_in_db(db_session)
        for i in range(3):
            build_list_data = {
                "name": get_unique_name(f"premium_build_list_{i}"),
                "description": f"Build list {i}",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200, f"Premium user should create build list {i + 1}"

    def test_get_build_list_by_id(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving a specific build list by ID."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Get the build list by ID
        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_build_list["id"]
        assert data["name"] == created_build_list["name"]

    def test_get_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test retrieving a non-existent build list."""
        # Login first since the endpoint requires authentication
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to get a non-existent build list
        response = client.get(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_unauthorized(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving a build list without authentication (public read is allowed)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list as test_user
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        # Try to get the build list without authentication (public read is allowed)
        response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}")
        assert response.status_code == 200  # Public read is allowed

    def test_get_user_build_lists(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for the current user."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Get user's build lists
        response = client.get(f"{settings.API_STR}/build-lists/user/me", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

    def test_get_user_build_lists_unauthorized(self, client: TestClient) -> None:
        """Test retrieving build lists without authentication."""
        response = client.get(f"{settings.API_STR}/build-lists/user/me")
        assert response.status_code == 401

    def test_update_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Update the build list
        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_build_list_unauthorized(self, client: TestClient) -> None:
        """Test updating a build list without proper authorization."""
        # Try to update a build list without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}", json=update_data)
        assert response.status_code == 401

    def test_delete_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test deleting a build list."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 404

    def test_delete_build_list_unauthorized(self, client: TestClient) -> None:
        """Test deleting a build list without proper authorization."""
        # Try to delete a build list without authentication
        response = client.delete(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}")
        assert response.status_code == 401

    def test_get_build_lists_by_car(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for a specific car."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Get build lists for the car
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1
        build_list: Any
        for build_list in data["data"]:
            assert build_list["car_id"] == str(car["id"])

    def test_get_build_lists_by_car_unauthorized(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for a car (public read is allowed)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Try to get build lists for a car without authentication (public read is allowed)
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}")
        assert response.status_code == 200  # Public read is allowed

    def test_create_build_list_with_extra_fields(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list with extra fields in the request."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list with extra fields (car_id is now required)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
            "extra_field": "should_be_ignored",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]

    def test_create_build_list_with_malformed_json(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with malformed JSON."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "application/json"

        # Try to create a build list with malformed JSON
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            content="invalid json",
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_build_list_with_wrong_content_type(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test creating a build list with wrong content type."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "text/plain"

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Try to create a build list with wrong content type
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            data=build_list_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_extra_fields(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list with extra fields in the request."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Update the build list with extra fields
        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "An updated build list description",
            "extra_field": "should_be_ignored",
        }
        response = client.put(f"{settings.API_STR}/build-lists/{build_list['id']}", json=update_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_build_list_with_malformed_json(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list with malformed JSON."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update with malformed JSON
        update_headers = get_auth_headers(token)
        update_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-lists/{build_list['id']}",
            content="invalid json",
            headers=update_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_wrong_content_type(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test updating a build list with wrong content type."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update with wrong content type
        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "An updated build list description",
        }
        update_headers = get_auth_headers(token)
        update_headers["Content-Type"] = "text/plain"
        response = client.put(
            f"{settings.API_STR}/build-lists/{build_list['id']}",
            data=update_data,
            headers=update_headers,
        )
        assert response.status_code == 422

    def test_create_build_list_with_disabled_user(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """A disabled account cannot create a build list.

        This used to assert that `POST /api/auth/token` answered 400, and then
        stopped, with a comment saying the build list functionality could not be
        reached because login had failed. Row 13 of `docs/identity-adoption.md`
        deleted that route, and the disabled check moved to where it belongs: an
        identity credential is issued by the package without consulting this
        product's `disabled` flag, and `get_current_user` is what refuses. So the
        test now does the thing it previously could not, and presents a valid
        credential to the real endpoint.
        """
        test_user = UserRepository().update(test_user.id, disabled=True)
        car = create_car_in_db(db_session)

        headers = auth_headers(login_user(client, test_user.username))
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }

        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)

        assert response.status_code == 401

    def test_create_build_list_with_unverified_email(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test creating a build list with an unverified email user account."""
        # Set email as unverified and commit to database
        test_user = UserRepository().update(test_user.id, email_verified=False)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # A credential is issued regardless: email verification is this product's
        # check, made in `get_current_user`, not the identity provider's.
        headers = auth_headers(login_user(client, test_user.username))

        # Try to create a build list with unverified email user
        # Even though login succeeded, the token should be invalid for protected endpoints
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 401  # Should fail due to unverified email

        # The test demonstrates that unverified email users cannot access protected endpoints

    def test_copy_build_list_success(self, client: TestClient, premium_test_user: User, db_session: Any) -> None:
        """Test successfully copying a build list.

        Uses premium_test_user: IN-02 closed the free-tier cap bypass on the copy
        path, so a free user who already has 1 build list (the source of the copy)
        hits the cap on the POST /copy call. Premium bypasses the cap entirely,
        which is the scenario this test actually cares about.
        """
        # Login as test user and get token
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        # Create a category for global parts
        category = DBCategory(name=get_unique_name("Test Category"))
        category = save_catalog(category)

        # Create a part_manufacturer for the global part
        from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer

        part_manufacturer = DBPartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(category.id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to original build list
        build_list_part_data = {"notes": "Original notes", "quantity": 2}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{original_build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Copy the build list
        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        # Verify copied build list
        assert copied_build_list["id"] != original_build_list["id"]
        assert copied_build_list["name"] == f"Copy of {original_build_list['name']}"
        assert copied_build_list["description"] == original_build_list["description"]
        assert copied_build_list["car_id"] == original_build_list["car_id"]
        assert copied_build_list["user_id"] == str(premium_test_user.id)  # Should be owned by current user

        # Verify parts were copied
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{copied_build_list['id']}",
            headers=headers,
        )
        assert response.status_code == 200
        parts = response.json()
        assert len(parts) == 1
        assert parts[0]["part_id"] == part["id"]
        assert parts[0]["notes"] == "Original notes"
        assert parts[0]["quantity"] == 2

    def test_copy_build_list_with_custom_name(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test copying a build list with a custom name. Uses premium_test_user per IN-02 (see test_copy_build_list_success)."""
        # Login as test user and get token
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        # Copy the build list with custom name
        custom_name = get_unique_name("copied_build_list")
        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={"new_name": custom_name},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        # Verify copied build list has custom name
        assert copied_build_list["name"] == custom_name
        assert copied_build_list["id"] != original_build_list["id"]

    def test_copy_build_list_without_custom_name(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test copying a build list without custom name (uses default). Uses premium_test_user per IN-02."""
        # Login as test user and get token
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        # Copy the build list without custom name
        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        # Verify copied build list uses "Copy of {original_name}" (default behavior)
        assert copied_build_list["name"] == f"Copy of {original_build_list['name']}"

    def test_copy_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test copying a non-existent build list."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to copy a non-existent build list
        response = client.post(
            f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 404

    def test_copy_build_list_unauthorized(self, client: TestClient) -> None:
        """Test copying a build list without authentication."""
        # Try to copy a build list without authentication
        response = client.post(
            f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}/copy",
            json={},
        )
        assert response.status_code == 401

    def test_copy_build_list_ownership(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test that copied build list is owned by the current user."""
        # Create a second user to own the original build list
        original_owner = UserRepository().create_user(
            DBUser(
                username=get_unique_name("original_owner"),
                email=f"{get_unique_name('original_owner')}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as original owner and create a build list
        original_token = get_auth_token(client, original_owner.username)
        original_headers = get_auth_headers(original_token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=original_headers)
        assert response.status_code == 200
        original_build_list = response.json()

        # Login as test user and copy the build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        # Verify copied build list is owned by test_user, not original_owner
        assert copied_build_list["user_id"] == str(test_user.id)
        assert copied_build_list["user_id"] != str(original_owner.id)

    def test_copy_free_tier_cap(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """IN-02 regression — free-tier user at the 1-list cap cannot copy to
        create a second list.

        Before IN-02 landed, ``copy_build_list`` bypassed the cap enforcement
        that ``create`` already applied — a free user could press Copy to grow
        unbounded. The service now raises 402 at the copy path too
        (``build_list_service.copy_build_list`` — see the ``Free accounts are
        limited`` block). This test pins the 402 so a future PR that removes
        or relaxes the check fails CI.
        """
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        # Step 1: create the one allowed build list → count=1, at cap.
        original_data = {
            "name": get_unique_name("at_cap"),
            "description": "first and only free-tier build list",
            "car_id": str(car["id"]),
        }
        resp = client.post(f"{settings.API_STR}/build-lists/", json=original_data, headers=headers)
        assert resp.status_code == 200, resp.text
        original_id = resp.json()["id"]

        # Step 2: attempt to copy → must be 402 (cap enforced at copy path).
        resp = client.post(
            f"{settings.API_STR}/build-lists/{original_id}/copy",
            json={"new_name": "should-fail"},
            headers=headers,
        )
        assert resp.status_code == 402, f"Expected 402 on copy at free-tier cap, got {resp.status_code}: {resp.text}"
        # The error-handler middleware (``app/api/middleware/error_handler.py``
        # — see the ``handle_http_exception`` function) maps
        # HTTPException.detail → response body's "message" key. Accept either
        # shape for forward-compatibility — same pattern used by the sibling
        # `test_free_user_cannot_create_second_build_list` test above.
        data = resp.json()
        msg = data.get("detail") or data.get("message") or ""
        assert (
            "Free accounts are limited to 1 build list" in msg
        ), f"Expected cap-exceeded message in 402 body, got: {data}"

        # Step 3: verify no 2nd build list was created. Uses the by-user
        # endpoint which returns a flat list (not paginated dict) so we can
        # assert length directly.
        resp = client.get(
            f"{settings.API_STR}/build-lists/user/{test_user.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        user_lists = resp.json()
        assert isinstance(user_lists, list), f"Expected list response, got {type(user_lists)}"
        assert len(user_lists) == 1, f"Expected exactly 1 build list after blocked copy, got {len(user_lists)}"
        assert user_lists[0]["id"] == original_id

    def test_get_build_lists_with_votes_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists with vote data."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a second user to vote
        voter = UserRepository().create_user(
            DBUser(
                username=get_unique_name("voter"),
                email=f"{get_unique_name('voter')}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as voter and upvote the build list
        voter_token = get_auth_token(client, voter.username)
        voter_headers = get_auth_headers(voter_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=voter_headers,
        )
        assert response.status_code == 200

        # Get build lists with votes
        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        # Verify response structure
        assert isinstance(data, dict)
        assert "data" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

        # Find our build list in the results
        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert "upvotes" in found_build_list
        assert "downvotes" in found_build_list
        assert "total_votes" in found_build_list
        assert found_build_list["upvotes"] == 1
        assert found_build_list["downvotes"] == 0
        assert found_build_list["total_votes"] == 1

    def test_get_build_lists_with_votes_no_votes(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists with no votes."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Get build lists with votes
        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        # Find our build list in the results
        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert found_build_list["upvotes"] == 0
        assert found_build_list["downvotes"] == 0
        assert found_build_list["total_votes"] == 0

    def test_get_build_lists_with_votes_public_access(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test that build lists with votes endpoint allows public access."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Login as test user and create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Get build lists with votes without authentication (public access)
        response = client.get(f"{settings.API_STR}/build-lists/with-votes")
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "data" in data

    def test_get_build_lists_with_votes_pagination(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test pagination with build lists with votes."""
        # Use premium user so we can create multiple build lists
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create multiple build lists
        for i in range(5):
            build_list_data = {
                "name": get_unique_name(f"test_build_list_{i}"),
                "description": f"Build list {i}",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200

        # Get build lists with votes with pagination
        response = client.get(f"{settings.API_STR}/build-lists/with-votes?skip=0&limit=2", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert len(data["data"]) <= 2
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_get_build_lists_with_votes_search(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test search functionality with build lists with votes."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list with unique name
        unique_name = get_unique_name("searchable_build_list")
        build_list_data = {
            "name": unique_name,
            "description": "A searchable build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search for the build list
        search_term = unique_name.split("_")[0]  # Use part of the unique name
        response = client.get(
            f"{settings.API_STR}/build-lists/with-votes?search={search_term}",
            headers=headers,
        )
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert len(data["data"]) >= 1
        # Verify the build list is in the results
        found = any(bl["name"] == unique_name for bl in data["data"])
        assert found

    def test_get_build_lists_with_votes_filter_by_car(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test filtering by car_id with build lists with votes."""
        # Use premium user so we can create multiple build lists
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create two cars in DB (cars are seeded from backend source; tests use create_car_in_db)
        car1 = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)
        car2 = create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)

        # Create build lists for each car
        build_list_data1 = {
            "name": get_unique_name("car1_build_list"),
            "description": "Build list for car 1",
            "car_id": str(car1["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data1, headers=headers)
        assert response.status_code == 200
        build_list1 = response.json()

        build_list_data2 = {
            "name": get_unique_name("car2_build_list"),
            "description": "Build list for car 2",
            "car_id": str(car2["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data2, headers=headers)
        assert response.status_code == 200

        # Filter by car1
        response = client.get(f"{settings.API_STR}/build-lists/with-votes?car_id={car1['id']}", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        # Verify all results are for car1
        for bl in data["data"]:
            assert bl["car_id"] == str(car1["id"])

        # Verify build_list1 is in the results
        found = any(bl["id"] == build_list1["id"] for bl in data["data"])
        assert found

    def test_get_build_lists_with_votes_filter_by_owner(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test filtering /with-votes by owner_id returns only that user's build lists."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        # Create a build list owned by test_user
        build_list_data = {
            "name": get_unique_name("owned_build_list"),
            "description": "Owned by test_user",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        owned_build_list = response.json()

        # Create a second user with their own build list
        other_user = UserRepository().create_user(
            DBUser(
                username=get_unique_name("other_owner"),
                email=f"{get_unique_name('other_owner')}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )
        other_token = get_auth_token(client, other_user.username)
        other_headers = get_auth_headers(other_token)
        other_build_list_data = {
            "name": get_unique_name("other_build_list"),
            "description": "Owned by other user",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=other_build_list_data, headers=other_headers)
        assert response.status_code == 200
        other_build_list = response.json()

        # Filter by test_user's id
        response = client.get(
            f"{settings.API_STR}/build-lists/with-votes?owner_id={test_user.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        returned_ids = {bl["id"] for bl in data["data"]}
        assert owned_build_list["id"] in returned_ids
        assert other_build_list["id"] not in returned_ids

    def test_get_build_lists_with_votes_multiple_votes(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test build lists with multiple votes."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create multiple users to vote
        for i in range(3):
            voter = UserRepository().create_user(
                DBUser(
                    username=get_unique_name(f"voter_{i}"),
                    email=f"{get_unique_name(f'voter_{i}')}@example.com",
                    email_verified=True,
                    disabled=False,
                    is_admin=False,
                    is_superuser=False,
                )
            )

            # Login as voter and upvote
            voter_token = get_auth_token(client, voter.username)
            voter_headers = get_auth_headers(voter_token)

            vote_data = {"vote_type": "upvote"}
            response = client.post(
                f"{settings.API_STR}/votes/build_list/{build_list['id']}",
                json=vote_data,
                headers=voter_headers,
            )
            assert response.status_code == 200

        # Create one downvote
        downvoter = UserRepository().create_user(
            DBUser(
                username=get_unique_name("downvoter"),
                email=f"{get_unique_name('downvoter')}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        downvoter_token = get_auth_token(client, downvoter.username)
        downvoter_headers = get_auth_headers(downvoter_token)

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=downvoter_headers,
        )
        assert response.status_code == 200

        # Get build lists with votes
        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        # Find our build list
        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert found_build_list["upvotes"] == 3
        assert found_build_list["downvotes"] == 1
        assert found_build_list["total_votes"] == 4
