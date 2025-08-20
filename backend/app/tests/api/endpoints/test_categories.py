import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.part import Part as DBPart
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.user import User as DBUser
from app.api.models.car import Car as DBCar
from app.tests.conftest import get_default_category_id
from app.core.config import settings


# Helper function to create a user and log them in (sets cookie on client)
def create_and_login_user(
    client: TestClient, username_suffix: str
) -> int:  # Returns user_id
    username = f"category_test_user_{username_suffix}"
    email = f"category_test_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
    elif response.status_code == 400 and "already registered" in response.json().get(
        "detail", ""
    ):
        pass
    else:
        response.raise_for_status()

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    if user_id == -1:
        me_response = client.get(f"{settings.API_STR}/users/me")
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(
                f"Could not retrieve user_id for existing user {username} via /users/me."
            )

    if user_id == -1:
        raise Exception(f"User ID for {username} could not be determined.")
    return user_id


# Helper function to create a car for the currently logged-in user (via client cookie)
def create_car_for_user_cookie_auth(
    client: TestClient,
    car_make: str = "TestMakeCategory",
    car_model: str = "TestModelCategory",
) -> int:
    car_data = {
        "make": car_make,
        "model": car_model,
        "year": 2024,
        "trim": "TestTrimCategory",
    }
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert (
        response.status_code == 200
    ), f"Failed to create car for category tests: {response.text}"
    return int(response.json()["id"])


# Helper function to create a build list for a car owned by the currently logged-in user
def create_build_list_for_car_cookie_auth(
    client: TestClient, car_id: int, bl_name: str = "TestBLCategory"
) -> int:
    build_list_data = {
        "name": bl_name,
        "description": "Test BL for categories",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert (
        response.status_code == 200
    ), f"Failed to create build list for category tests: {response.text}"
    return int(response.json()["id"])


class TestCategories:
    """Test cases for category endpoints."""

    def test_get_categories_success(self, client: TestClient, db_session: Session):
        """Test getting all active categories."""
        response = client.get("/api/categories/")
        assert response.status_code == 200

        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) > 0

        # Check that all categories have required fields
        for category in categories:
            assert "id" in category
            assert "name" in category
            assert "display_name" in category
            assert "is_active" in category
            assert "sort_order" in category
            assert category["is_active"] is True

    def test_get_categories_ordered_by_sort_order(
        self, client: TestClient, db_session: Session
    ):
        """Test that categories are returned in sort order."""
        response = client.get("/api/categories/")
        assert response.status_code == 200

        categories = response.json()
        assert len(categories) > 1

        # Check that categories are ordered by sort_order
        sort_orders = [cat["sort_order"] for cat in categories]
        assert sort_orders == sorted(sort_orders)

    def test_get_category_success(self, client: TestClient, db_session: Session):
        """Test getting a specific category."""
        # First get all categories to get an ID
        response = client.get("/api/categories/")
        assert response.status_code == 200
        categories = response.json()
        category_id = categories[0]["id"]

        response = client.get(f"/api/categories/{category_id}")
        assert response.status_code == 200

        category = response.json()
        assert category["id"] == category_id
        assert "name" in category
        assert "display_name" in category

    def test_get_category_not_found(self, client: TestClient, db_session: Session):
        """Test getting a non-existent category."""
        response = client.get("/api/categories/99999")
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_get_parts_by_category_success(
        self, client: TestClient, db_session: Session
    ):
        """Test getting parts by category."""
        # Create a user and log them in
        _ = create_and_login_user(client, "parts_by_category")

        # Create a car for the user
        car_id = create_car_for_user_cookie_auth(client)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

        # Get a category ID
        category_id = get_default_category_id(db_session)

        # Create a part in that category
        part_data = {
            "name": "Test Part",
            "description": "Test part description",
            "price": 100,
            "build_list_id": build_list_id,
            "category_id": category_id,
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data)
        assert response.status_code == 200
        part_id = response.json()["id"]

        response = client.get(f"/api/categories/{category_id}/parts")
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)
        assert len(parts) >= 1

        # Check that the part is in the response
        part_found = any(p["id"] == part_id for p in parts)
        assert part_found

    def test_get_parts_by_category_empty(self, client: TestClient, db_session: Session):
        """Test getting parts by category when no parts exist."""
        # Get a category ID
        response = client.get("/api/categories/")
        assert response.status_code == 200
        categories = response.json()
        category_id = categories[0]["id"]

        response = client.get(f"/api/categories/{category_id}/parts")
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)
        # Note: This might not be empty if there are existing parts in the test database

    def test_get_parts_by_category_not_found(
        self, client: TestClient, db_session: Session
    ):
        """Test getting parts by non-existent category."""
        response = client.get("/api/categories/99999/parts")
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_get_parts_by_category_pagination(
        self, client: TestClient, db_session: Session
    ):
        """Test pagination for parts by category."""
        # Create a user and log them in
        _ = create_and_login_user(client, "parts_pagination")

        # Create a car for the user
        car_id = create_car_for_user_cookie_auth(client)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

        # Get a category ID
        category_id = get_default_category_id(db_session)

        # Create multiple parts in that category
        for i in range(5):
            part_data = {
                "name": f"Test Part {i}",
                "description": f"Test part description {i}",
                "price": 100 + i,
                "build_list_id": build_list_id,
                "category_id": category_id,
            }
            response = client.post(f"{settings.API_STR}/parts/", json=part_data)
            assert response.status_code == 200

        # Test with limit
        response = client.get(f"/api/categories/{category_id}/parts?limit=3")
        assert response.status_code == 200

        parts = response.json()
        assert len(parts) <= 3

        # Test with skip
        response = client.get(f"/api/categories/{category_id}/parts?skip=2&limit=2")
        assert response.status_code == 200

        parts = response.json()
        assert len(parts) <= 2

    def test_create_category_success(self, client: TestClient, db_session: Session):
        """Test creating a new category."""
        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "icon": "test-icon",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post("/api/categories/", json=category_data)
        assert response.status_code == 200

        category = response.json()
        assert category["name"] == category_data["name"]
        assert category["display_name"] == category_data["display_name"]
        assert category["description"] == category_data["description"]
        assert category["icon"] == category_data["icon"]
        assert category["is_active"] == category_data["is_active"]
        assert category["sort_order"] == category_data["sort_order"]

    def test_create_category_duplicate_name(
        self, client: TestClient, db_session: Session
    ):
        """Test creating a category with duplicate name."""
        # First create a category
        category_data = {
            "name": "duplicate_test",
            "display_name": "Duplicate Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post("/api/categories/", json=category_data)
        assert response.status_code == 200

        # Try to create another category with the same name
        response = client.post("/api/categories/", json=category_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_update_category_success(self, client: TestClient, db_session: Session):
        """Test updating a category."""
        # First create a category
        category_data = {
            "name": "update_test",
            "display_name": "Update Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post("/api/categories/", json=category_data)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Update the category
        update_data = {
            "display_name": "Updated Test Category",
            "description": "Updated description",
            "sort_order": 60,
        }

        response = client.put(f"/api/categories/{category_id}", json=update_data)
        assert response.status_code == 200

        category = response.json()
        assert category["display_name"] == update_data["display_name"]
        assert category["description"] == update_data["description"]
        assert category["sort_order"] == update_data["sort_order"]
        # Original values should remain unchanged
        assert category["name"] == category_data["name"]
        assert category["is_active"] == category_data["is_active"]

    def test_update_category_not_found(self, client: TestClient, db_session: Session):
        """Test updating a non-existent category."""
        update_data = {"display_name": "Updated Test Category"}

        response = client.put("/api/categories/99999", json=update_data)
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_delete_category_success(self, client: TestClient, db_session: Session):
        """Test deleting a category."""
        # First create a category
        category_data = {
            "name": "delete_test",
            "display_name": "Delete Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post("/api/categories/", json=category_data)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Delete the category
        response = client.delete(f"/api/categories/{category_id}")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify it's deleted
        response = client.get(f"/api/categories/{category_id}")
        assert response.status_code == 404

    def test_delete_category_not_found(self, client: TestClient, db_session: Session):
        """Test deleting a non-existent category."""
        response = client.delete("/api/categories/99999")
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_delete_category_with_parts(self, client: TestClient, db_session: Session):
        """Test deleting a category that has parts (should fail)."""
        # Create a user and log them in
        _ = create_and_login_user(client, "delete_with_parts")

        # Create a car for the user
        car_id = create_car_for_user_cookie_auth(client)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

        # Get a category ID that has parts
        category_id = get_default_category_id(db_session)

        # Create a part in that category
        part_data = {
            "name": "Test Part",
            "description": "Test part description",
            "price": 100,
            "build_list_id": build_list_id,
            "category_id": category_id,
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data)
        assert response.status_code == 200

        # Try to delete the category
        response = client.delete(f"/api/categories/{category_id}")
        assert response.status_code == 400
        assert "parts are using this category" in response.json()["detail"]

    def test_pre_populated_categories_exist(
        self, client: TestClient, db_session: Session
    ):
        """Test that the pre-populated categories exist."""
        response = client.get("/api/categories/")
        assert response.status_code == 200

        categories = response.json()
        category_names = [cat["name"] for cat in categories]

        # Check for expected pre-populated categories
        expected_categories = [
            "exhaust",
            "intake",
            "suspension",
            "wheels",
            "brakes",
            "engine",
            "exterior",
            "interior",
            "electrical",
            "maintenance",
            "other",
        ]

        for expected_name in expected_categories:
            assert (
                expected_name in category_names
            ), f"Expected category '{expected_name}' not found"

        # Check that they have proper display names
        for category in categories:
            if category["name"] in expected_categories:
                assert category[
                    "display_name"
                ], f"Category '{category['name']}' missing display name"
                assert (
                    category["is_active"] is True
                ), f"Category '{category['name']}' should be active"
