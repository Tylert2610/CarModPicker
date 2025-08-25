from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.api.dependencies.auth import get_password_hash
from app.core.config import settings


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


# Helper function to create and login a regular user
def create_and_login_regular_user(
    client: TestClient, db_session: Session, username_suffix: str = "regular"
) -> dict:
    """Create a regular user and log them in."""
    username = f"regular_test_{username_suffix}"
    email = f"regular_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create regular user directly in database
    regular_user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_admin=False,
        is_superuser=False,
        email_verified=True,
        disabled=False,
    )
    db_session.add(regular_user)
    db_session.commit()
    db_session.refresh(regular_user)

    # Log in to set cookie on the client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert (
        token_response.status_code == 200
    ), f"Failed to login regular user: {token_response.text}"

    return regular_user.__dict__


class TestCategoriesAdminAuthentication:
    """Test cases for category endpoints with admin authentication."""

    def test_create_category_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that creating a category without authentication fails."""
        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "sort_order": 1,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert response.status_code == 401, "Should require authentication"
        assert "Could not validate credentials" in response.text

    def test_create_category_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot create categories."""
        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "create_cat")

        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "sort_order": 1,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert (
            response.status_code == 403
        ), "Regular users should not be able to create categories"
        assert "Admin access required" in response.text

    def test_create_category_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can create categories."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "create_cat")

        category_data = {
            "name": "test_category_admin",
            "display_name": "Test Category Admin",
            "description": "A test category created by admin",
            "sort_order": 1,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert (
            response.status_code == 200
        ), f"Admin should be able to create categories: {response.text}"

        created_category = response.json()
        assert created_category["name"] == category_data["name"]
        assert created_category["display_name"] == category_data["display_name"]
        assert created_category["description"] == category_data["description"]

    def test_create_category_with_superuser(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that superusers can create categories."""
        # Create superuser directly in database
        username = "superuser_test_create"
        email = f"{username}@example.com"
        password = "testpassword"

        superuser = DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=False,
            is_superuser=True,
            email_verified=True,
            disabled=False,
        )
        db_session.add(superuser)
        db_session.commit()

        # Log in superuser
        login_data = {"username": username, "password": password}
        token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert token_response.status_code == 200

        category_data = {
            "name": "test_category_superuser",
            "display_name": "Test Category Superuser",
            "description": "A test category created by superuser",
            "sort_order": 2,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data)
        assert (
            response.status_code == 200
        ), f"Superuser should be able to create categories: {response.text}"

        created_category = response.json()
        assert created_category["name"] == category_data["name"]

    def test_update_category_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that updating a category without authentication fails."""
        # Create a category first
        category = DBCategory(
            name="test_update_category",
            display_name="Test Update Category",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        update_data = {
            "display_name": "Updated Category Name",
            "description": "Updated description",
        }

        response = client.put(
            f"{settings.API_STR}/categories/{category.id}", json=update_data
        )
        assert response.status_code == 401, "Should require authentication"

    def test_update_category_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot update categories."""
        # Create a category first
        category = DBCategory(
            name="test_update_category_regular",
            display_name="Test Update Category Regular",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "update_cat")

        update_data = {
            "display_name": "Updated Category Name",
            "description": "Updated description",
        }

        response = client.put(
            f"{settings.API_STR}/categories/{category.id}", json=update_data
        )
        assert (
            response.status_code == 403
        ), "Regular users should not be able to update categories"
        assert "Admin access required" in response.text

    def test_update_category_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can update categories."""
        # Create a category first
        category = DBCategory(
            name="test_update_category_admin",
            display_name="Test Update Category Admin",
            description="A test category for updating",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "update_cat")

        update_data = {
            "display_name": "Updated Category Name by Admin",
            "description": "Updated description by admin",
            "sort_order": 5,
        }

        response = client.put(
            f"{settings.API_STR}/categories/{category.id}", json=update_data
        )
        assert (
            response.status_code == 200
        ), f"Admin should be able to update categories: {response.text}"

        updated_category = response.json()
        assert updated_category["display_name"] == update_data["display_name"]
        assert updated_category["description"] == update_data["description"]
        assert updated_category["sort_order"] == update_data["sort_order"]

    def test_delete_category_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that deleting a category without authentication fails."""
        # Create a category first
        category = DBCategory(
            name="test_delete_category",
            display_name="Test Delete Category",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        response = client.delete(f"{settings.API_STR}/categories/{category.id}")
        assert response.status_code == 401, "Should require authentication"

    def test_delete_category_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot delete categories."""
        # Create a category first
        category = DBCategory(
            name="test_delete_category_regular",
            display_name="Test Delete Category Regular",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "delete_cat")

        response = client.delete(f"{settings.API_STR}/categories/{category.id}")
        assert (
            response.status_code == 403
        ), "Regular users should not be able to delete categories"
        assert "Admin access required" in response.text

    def test_delete_category_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can delete categories."""
        # Create a category first
        category = DBCategory(
            name="test_delete_category_admin",
            display_name="Test Delete Category Admin",
            description="A test category for deleting",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "delete_cat")

        response = client.delete(f"{settings.API_STR}/categories/{category.id}")
        assert (
            response.status_code == 200
        ), f"Admin should be able to delete categories: {response.text}"

        # Verify the category was deleted
        get_response = client.get(f"{settings.API_STR}/categories/{category.id}")
        assert get_response.status_code == 404, "Category should be deleted"

    def test_delete_category_with_parts_fails(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that deleting a category with parts fails."""
        from app.api.models.global_part import GlobalPart as DBGlobalPart

        # Create a user first
        user = DBUser(
            username="test_user_for_part",
            email="test_user_for_part@example.com",
            hashed_password="hashed_password",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a category first
        category = DBCategory(
            name="test_delete_category_with_parts",
            display_name="Test Delete Category With Parts",
            description="A test category with parts",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create a part in this category
        part = DBGlobalPart(
            name="Test Part",
            description="A test part",
            category_id=category.id,
            user_id=user.id,  # Use the actual user ID
        )
        db_session.add(part)
        db_session.commit()

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "delete_cat_parts")

        response = client.delete(f"{settings.API_STR}/categories/{category.id}")
        assert (
            response.status_code == 400
        ), "Should not be able to delete category with parts"
        assert "parts are using this category" in response.text

    def test_public_category_endpoints_remain_public(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that public category endpoints remain accessible without authentication."""
        # Create a category first
        category = DBCategory(
            name="test_public_category",
            display_name="Test Public Category",
            description="A test category for public access",
            sort_order=1,
            is_active=True,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

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

        # Test GET /categories/{id}/global-parts (public)
        response = client.get(
            f"{settings.API_STR}/categories/{category.id}/global-parts"
        )
        assert response.status_code == 200, "Category global parts should be public"

        parts = response.json()
        assert isinstance(parts, list), "Should return a list of parts"

    def test_duplicate_category_name_fails(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that creating a category with duplicate name fails."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "duplicate_cat")

        # Create first category
        category_data_1 = {
            "name": "duplicate_test_category",
            "display_name": "Duplicate Test Category 1",
            "description": "First category",
            "sort_order": 1,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data_1)
        assert response.status_code == 200, "First category should be created"

        # Try to create second category with same name
        category_data_2 = {
            "name": "duplicate_test_category",  # Same name
            "display_name": "Duplicate Test Category 2",
            "description": "Second category",
            "sort_order": 2,
            "is_active": True,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data_2)
        assert response.status_code == 400, "Should not allow duplicate category names"
        assert "already exists" in response.text
