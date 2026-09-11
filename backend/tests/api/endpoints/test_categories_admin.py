from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category as DBCategory
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import auth_headers, login_user, save_catalog


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


# Helper function to create and login a regular user
def create_and_login_regular_user(
    client: TestClient, db_session: Any, username_suffix: str = "regular"
) -> tuple[dict[str, Any], str]:
    """Create a regular user and log them in. Returns (user_dict, token)."""
    username = f"regular_test_{username_suffix}"
    email = f"regular_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create regular user directly in database
    regular_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    # Log in and get token
    token = login_user(client, username)

    return regular_user.__dict__, token


class TestCategoriesAdminAuthentication:
    """Category create/update/delete are removed; categories are seeded from backend source.
    These tests assert that write endpoints return 404 or 405 (method/path not available).
    """

    def test_create_category_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; create endpoint is removed (404/405)."""
        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "sort_order": 1,
            "is_active": True,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code in (404, 405), "Create endpoint is removed"

    def test_create_category_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; create endpoint is removed (404/405)."""
        _, token = create_and_login_regular_user(client, db_session, "create_cat")
        headers = auth_headers(token)
        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "sort_order": 1,
            "is_active": True,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code in (404, 405), "Create endpoint is removed"

    def test_create_category_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; create endpoint is removed (404/405)."""
        _, token = create_and_login_admin_user(client, db_session, "create_cat")
        headers = auth_headers(token)
        category_data = {
            "name": "test_category_admin",
            "display_name": "Test Category Admin",
            "description": "A test category created by admin",
            "sort_order": 1,
            "is_active": True,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code in (404, 405), "Create endpoint is removed"

    def test_create_category_with_superuser(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; create endpoint is removed (404/405)."""
        username = "superuser_test_create"
        email = f"{username}@example.com"
        password = "testpassword"
        superuser = UserRepository().create_user(
            DBUser(
                username=username,
                email=email,
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )
        token = login_user(client, username)
        headers = auth_headers(token)
        category_data = {
            "name": "test_category_superuser",
            "display_name": "Test Category Superuser",
            "description": "A test category created by superuser",
            "sort_order": 2,
            "is_active": True,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code in (404, 405), "Create endpoint is removed"

    def test_update_category_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; update endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_update_category",
            display_name="Test Update Category",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        update_data = {"display_name": "Updated Category Name", "description": "Updated description"}
        response = client.put(f"{settings.API_STR}/categories/{category.id}", json=update_data)
        assert response.status_code in (404, 405), "Update endpoint is removed"

    def test_update_category_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; update endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_update_category_regular",
            display_name="Test Update Category Regular",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        _, token = create_and_login_regular_user(client, db_session, "update_cat")
        headers = auth_headers(token)
        update_data = {"display_name": "Updated Category Name", "description": "Updated description"}
        response = client.put(f"{settings.API_STR}/categories/{category.id}", json=update_data, headers=headers)
        assert response.status_code in (404, 405), "Update endpoint is removed"

    def test_update_category_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; update endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_update_category_admin",
            display_name="Test Update Category Admin",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        _, token = create_and_login_admin_user(client, db_session, "update_cat")
        headers = auth_headers(token)
        update_data = {
            "display_name": "Updated Category Name by Admin",
            "description": "Updated description by admin",
            "sort_order": 5,
        }
        response = client.put(f"{settings.API_STR}/categories/{category.id}", json=update_data, headers=headers)
        assert response.status_code in (404, 405), "Update endpoint is removed"

    def test_delete_category_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; delete endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_delete_category",
            display_name="Test Delete Category",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        response = client.delete(f"{settings.API_STR}/categories/{category.id}")
        assert response.status_code in (404, 405), "Delete endpoint is removed"

    def test_delete_category_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; delete endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_delete_category_regular",
            display_name="Test Delete Category Regular",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        _, token = create_and_login_regular_user(client, db_session, "delete_cat")
        headers = auth_headers(token)
        response = client.delete(f"{settings.API_STR}/categories/{category.id}", headers=headers)
        assert response.status_code in (404, 405), "Delete endpoint is removed"

    def test_delete_category_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; delete endpoint is removed (404/405)."""
        category = DBCategory(
            name="test_delete_category_admin",
            display_name="Test Delete Category Admin",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        _, token = create_and_login_admin_user(client, db_session, "delete_cat")
        headers = auth_headers(token)
        response = client.delete(f"{settings.API_STR}/categories/{category.id}", headers=headers)
        assert response.status_code in (404, 405), "Delete endpoint is removed"

    def test_delete_category_with_parts_fails(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; delete endpoint is removed (404/405)."""
        from app.db.dynamo.catalog import Part as DBPart

        user = UserRepository().create_user(
            DBUser(
                username="test_user_for_part",
                email="test_user_for_part@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )
        category = DBCategory(
            name="test_delete_category_with_parts",
            display_name="Test Delete Category With Parts",
            description="A test category with parts",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)
        part = DBPart(
            name="Test Part",
            description="A test part",
            category_id=category.id,
            user_id=user.id,
        )
        part = save_catalog(part)
        _, token = create_and_login_admin_user(client, db_session, "delete_cat_parts")
        headers = auth_headers(token)
        response = client.delete(f"{settings.API_STR}/categories/{category.id}", headers=headers)
        assert response.status_code in (404, 405), "Delete endpoint is removed"

    def test_public_category_endpoints_remain_public(self, client: TestClient, db_session: Any) -> None:
        """Test that public category endpoints remain accessible without authentication."""
        # Create a category first
        category = DBCategory(
            name="test_public_category",
            display_name="Test Public Category",
            description="A test category for public access",
            sort_order=1,
            is_active=True,
        )
        category = save_catalog(category)

        # Test GET /categories/ (public)
        response = client.get(f"{settings.API_STR}/categories/")
        assert response.status_code == 200, "Categories list should be public"

        categories = response.json()
        assert len(categories) > 0, "Should return categories"

        # Test GET /categories/{id} (public)
        response = client.get(f"{settings.API_STR}/categories/{category.id}")
        assert response.status_code == 200, "Individual category should be public"

        category_data = response.json()
        assert category_data["name"] == category.name

        # Test GET /categories/{id}/parts (public)
        response = client.get(f"{settings.API_STR}/categories/{category.id}/parts")
        assert response.status_code == 200, "Category global parts should be public"

        parts = response.json()["items"]
        assert isinstance(parts, list), "Should return a list of parts"

    def test_duplicate_category_name_fails(self, client: TestClient, db_session: Any) -> None:
        """Categories are seeded from backend; create endpoint is removed (404/405)."""
        _, token = create_and_login_admin_user(client, db_session, "duplicate_cat")
        headers = auth_headers(token)
        category_data_1 = {
            "name": "duplicate_test_category",
            "display_name": "Duplicate Test Category 1",
            "description": "First category",
            "sort_order": 1,
            "is_active": True,
        }
        response = client.post(f"{settings.API_STR}/categories/", json=category_data_1, headers=headers)
        assert response.status_code in (404, 405), "Create endpoint is removed"
