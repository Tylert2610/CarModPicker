import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category, CategoryRepository, PartManufacturer
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import (
    INVALID_UUID_STR,
    auth_headers,
    create_car_in_db,
    get_default_category_id,
    login_user,
    save_catalog,
    test_part_manufacturer,
)


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


# Helper function to create and login an admin user
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


# Helper function to create a user and log them in. Returns (user_id, token)
def create_and_login_user(client: TestClient, username_suffix: str) -> tuple[UUID, str]:
    username = f"category_test_user_{username_suffix}"
    email = f"category_test_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id: UUID | None = None
    if response.status_code == 200:
        user_id = UUID(response.json()["id"])
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()

    token = login_user(client, username)

    if user_id is None:
        headers = auth_headers(token)
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            user_id = UUID(me_response.json()["id"])
        else:
            raise Exception(f"Could not retrieve user_id for existing user {username} via /users/me.")

    if user_id is None:
        raise Exception(f"User ID for {username} could not be determined.")
    return user_id, token


# Helper to create a car in DB for category tests (cars are seeded from backend source)
def create_car_for_categories_test(
    db_session: Any,
    car_make: str = "TestMakeCategory",
    car_model: str = "TestModelCategory",
    generation_name: str = "Test Gen",
    start_year: int = 2020,
    end_year: int = 2024,
) -> UUID:
    """Create a car in DB for category tests and return the car ID."""
    car = create_car_in_db(db_session, car_make, car_model, generation_name, start_year, end_year)
    return car["id"]


# Helper function to create a build list for a car (cars are centrally managed, not owned by users)
def create_build_list_for_car_cookie_auth(
    client: TestClient, token: str, car_id: UUID, bl_name: str = "TestBLCategory"
) -> UUID:
    headers = auth_headers(token)
    build_list_data = {
        "name": bl_name,
        "description": "Test BL for categories",
        "car_id": str(car_id),
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
    assert response.status_code == 200, f"Failed to create build list for category tests: {response.text}"
    return UUID(response.json()["id"])


class TestCategories:
    """Test cases for category endpoints."""

    def test_get_categories_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting all active categories."""
        # Create a default category if none exist
        if CategoryRepository().count() == 0:
            default_category = Category(
                name="test_category",
                display_name="Test Category",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            default_category = save_catalog(default_category)

        response = client.get(f"{settings.API_STR}/categories/")
        assert response.status_code == 200

        categories: list[Any] = response.json()
        assert isinstance(categories, list)
        # Should return at least the default categories
        assert len(categories) > 0

        # Check that all returned categories are active
        category: Any
        for category in categories:
            assert category["is_active"] is True

    def test_get_category_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting a specific category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}")
        assert response.status_code == 200

        category = response.json()
        assert category["id"] == str(category_id)
        assert "name" in category
        assert "display_name" in category

    def test_get_category_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test getting a non-existent category."""
        response = client.get(f"{settings.API_STR}/categories/{INVALID_UUID_STR}")
        assert response.status_code == 404
        assert "Category not found" in response.json()["message"]

    def test_get_parts_by_category_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting parts by category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts")
        assert response.status_code == 200

        parts = response.json()["items"]
        assert isinstance(parts, list)

    def test_get_parts_by_category_with_pagination(
        self, client: TestClient, test_part_manufacturer: PartManufacturer, db_session: Any
    ) -> None:
        """Test getting parts by category with pagination."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Create a user and log them in
        _, token = create_and_login_user(client, "parts_by_category")
        headers = auth_headers(token)

        car_id = create_car_for_categories_test(db_session)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, token, car_id)

        # Create some parts in the category
        for i in range(3):
            part_data = {
                "name": f"Test Part {i}",
                "description": f"Test part description {i}",
                "category_id": str(category_id),
                "part_manufacturer_id": str(test_part_manufacturer.id),
            }
            response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts?limit=2")
        assert response.status_code == 200

        page = response.json()
        parts: list[Any] = page["items"]
        assert isinstance(parts, list)
        assert len(parts) == 2
        assert page["has_next"] is True

    def test_get_parts_by_category_empty(self, client: TestClient, db_session: Any) -> None:
        """Test getting parts by category when no parts exist."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts")
        assert response.status_code == 200

        parts = response.json()["items"]
        assert isinstance(parts, list)
        # Note: This might not be empty if there are existing parts in the test database

    def test_create_category_removed(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend source; create endpoint is removed."""
        _, token = create_and_login_admin_user(client, db_session, "create_cat")
        headers = auth_headers(token)
        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code in (404, 405)

    def test_update_category_removed(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend source; update endpoint is removed."""
        category_id = get_default_category_id(db_session)
        _, token = create_and_login_admin_user(client, db_session, "update_cat")
        headers = auth_headers(token)
        response = client.put(
            f"{settings.API_STR}/categories/{category_id}",
            json={"display_name": "Updated"},
            headers=headers,
        )
        assert response.status_code in (404, 405)

    def test_delete_category_removed(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend source; delete endpoint is removed."""
        category_id = get_default_category_id(db_session)
        _, token = create_and_login_admin_user(client, db_session, "delete_cat")
        headers = auth_headers(token)
        response = client.delete(f"{settings.API_STR}/categories/{category_id}", headers=headers)
        assert response.status_code in (404, 405)

    def test_delete_category_with_parts(self, client: TestClient, db_session: Any) -> None:
        """Categories are read-only; delete with parts would have returned 409, now endpoint removed."""
        _, user_token = create_and_login_user(client, "delete_with_parts")
        user_headers = auth_headers(user_token)

        car_id = create_car_for_categories_test(db_session)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, user_token, car_id)

        # Get a category ID that has parts
        category_id = get_default_category_id(db_session)

        # Create a part in that category
        # Create a part_manufacturer for the part
        part_manufacturer = PartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        part_data = {
            "name": "Test Part",
            "description": "Test part description",
            "category_id": str(category_id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=user_headers)
        assert response.status_code == 200

        # Re-login as admin user for the delete operation
        _, admin_token2 = create_and_login_admin_user(client, db_session, "delete_with_parts_admin")
        admin_headers = auth_headers(admin_token2)

        # Delete endpoint is removed (categories are read-only)
        response = client.delete(f"{settings.API_STR}/categories/{category_id}", headers=admin_headers)
        assert response.status_code in (404, 405)

    def test_get_category_parts_count_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting parts count for a category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Get initial count
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "parts_count" in initial_data
        initial_count = initial_data["parts_count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a user and log them in
        _, user_token = create_and_login_user(client, "parts_count_user")
        user_headers = auth_headers(user_token)

        car_id = create_car_for_categories_test(db_session)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, user_token, car_id)

        # Create a part_manufacturer for the part
        part_manufacturer = PartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        # Create a part in that category
        part_data = {
            "name": "Test Part for Count",
            "description": "Test part description",
            "category_id": str(category_id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=user_headers)
        assert response.status_code == 200

        # Get count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "parts_count" in updated_data
        assert updated_data["parts_count"] == initial_count + 1

    def test_get_category_parts_count_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test getting parts count for a non-existent category."""
        response = client.get(f"{settings.API_STR}/categories/{INVALID_UUID_STR}/parts-count")
        assert response.status_code == 404
        assert (
            "category" in response.json().get("message", "").lower()
            or "not found" in response.json().get("message", "").lower()
        )

    def test_get_category_parts_count_public_endpoint(self, client: TestClient, db_session: Any) -> None:
        """Test that getting parts count works without authentication."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Get parts count (public endpoint, no auth required)
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        data = response.json()
        assert "parts_count" in data
        assert isinstance(data["parts_count"], int)
        assert data["parts_count"] >= 0

    def test_count_categories_success(self, client: TestClient, db_session: Any) -> None:
        """Test counting categories (categories are seeded from backend source)."""
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_count_categories_public_endpoint(self, client: TestClient, db_session: Any) -> None:
        """Test that counting categories works without authentication."""
        # Count categories (public endpoint, no auth required)
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
