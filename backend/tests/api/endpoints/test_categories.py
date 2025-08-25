import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.dependencies.auth import get_password_hash
from tests.conftest import get_default_category_id
from app.core.config import settings
from app.api.models.category import Category


# Helper function to create and login an admin user
def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> dict:
    """Create an admin user and log them in."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
    admin_user = DBUser(
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

    # Log in to set cookie on the client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert (
        token_response.status_code == 200
    ), f"Failed to login admin user: {token_response.text}"

    return admin_user.__dict__


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

    def test_get_categories_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting all active categories."""
        # Create a default category if none exist
        if db_session.query(Category).count() == 0:
            default_category = Category(
                name="test_category",
                display_name="Test Category",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            db_session.add(default_category)
            db_session.commit()

        response = client.get(f"{settings.API_STR}/categories/")
        assert response.status_code == 200

        categories = response.json()
        assert isinstance(categories, list)
        # Should return at least the default categories
        assert len(categories) > 0

        # Check that all returned categories are active
        for category in categories:
            assert category["is_active"] is True

    def test_get_category_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting a specific category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}")
        assert response.status_code == 200

        category = response.json()
        assert category["id"] == category_id
        assert "name" in category
        assert "display_name" in category

    def test_get_category_not_found(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting a non-existent category."""
        response = client.get(f"{settings.API_STR}/categories/99999")
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_get_parts_by_category_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting parts by category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(
            f"{settings.API_STR}/categories/{category_id}/global-parts"
        )
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)

    def test_get_parts_by_category_with_pagination(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting parts by category with pagination."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Create a user and log them in
        _ = create_and_login_user(client, "parts_by_category")

        # Create a car for the user
        car_id = create_car_for_user_cookie_auth(client)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

        # Create some parts in the category
        for i in range(3):
            part_data = {
                "name": f"Test Part {i}",
                "description": f"Test part description {i}",
                "price": 100 + i * 10,
                "build_list_id": build_list_id,
                "category_id": category_id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
            assert response.status_code == 200

        response = client.get(
            f"{settings.API_STR}/categories/{category_id}/global-parts?skip=2&limit=2"
        )
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)
        assert len(parts) <= 2

    def test_get_parts_by_category_empty(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting parts by category when no parts exist."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(
            f"{settings.API_STR}/categories/{category_id}/global-parts"
        )
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)
        # Note: This might not be empty if there are existing parts in the test database

    def test_create_category_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test creating a new category."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "create_cat")

        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "icon": "test-icon",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
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
    ) -> None:
        """Test creating a category with duplicate name."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "duplicate_cat")

        # First create a category
        category_data = {
            "name": "duplicate_test",
            "display_name": "Duplicate Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code == 200

        # Try to create another category with the same name
        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_update_category_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test updating a category."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "update_cat")

        # First create a category
        category_data = {
            "name": "update_test",
            "display_name": "Update Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Update the category
        update_data = {
            "display_name": "Updated Test Category",
            "description": "Updated description",
            "sort_order": 60,
        }

        response = client.put(
            f"{settings.API_STR}/categories/{category_id}", json=update_data
        )
        assert response.status_code == 200

        category = response.json()
        assert category["display_name"] == update_data["display_name"]
        assert category["description"] == update_data["description"]
        assert category["sort_order"] == update_data["sort_order"]
        # Original values should remain unchanged
        assert category["name"] == category_data["name"]
        assert category["is_active"] == category_data["is_active"]

    def test_update_category_not_found(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test updating a non-existent category."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "update_not_found")

        update_data = {"display_name": "Updated Test Category"}

        response = client.put(f"{settings.API_STR}/categories/99999", json=update_data)
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_delete_category_success(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test deleting a category."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "delete_cat")

        # First create a category
        category_data = {
            "name": "delete_test",
            "display_name": "Delete Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Delete the category
        response = client.delete(f"{settings.API_STR}/categories/{category_id}")
        assert response.status_code == 200

        # Verify the category is deleted
        get_response = client.get(f"{settings.API_STR}/categories/{category_id}")
        assert get_response.status_code == 404

    def test_delete_category_not_found(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test deleting a non-existent category."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "delete_not_found")

        response = client.delete(f"{settings.API_STR}/categories/99999")
        assert response.status_code == 404
        assert "Category not found" in response.json()["detail"]

    def test_delete_category_with_parts(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test deleting a category that has parts (should fail)."""
        # Create and login as admin user
        _ = create_and_login_admin_user(client, db_session, "delete_with_parts")

        # Create a user and log them in (this will change the client's session)
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
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        # Re-login as admin user for the delete operation
        _ = create_and_login_admin_user(client, db_session, "delete_with_parts_admin")

        # Try to delete the category
        response = client.delete(f"{settings.API_STR}/categories/{category_id}")
        assert response.status_code == 400
        assert "parts are using this category" in response.json()["detail"]
