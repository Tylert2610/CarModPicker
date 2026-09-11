from typing import Any, List

from fastapi.testclient import TestClient

from app.api.dependencies.auth import verify_password
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, login_user


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


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

    # Log in to get Bearer token
    token = login_user(client, username)

    return admin_user.__dict__, token


# Helper function to create and login a superuser
def create_and_login_superuser(
    client: TestClient, db_session: Any, username_suffix: str = "superuser"
) -> tuple[dict[str, Any], str]:
    """Create a superuser and log them in. Returns (user_dict, token)."""
    username = f"superuser_test_{username_suffix}"
    email = f"superuser_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create superuser directly in database
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

    # Log in to get Bearer token
    token = login_user(client, username)

    return superuser.__dict__, token


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

    # Log in to get Bearer token
    token = login_user(client, username)

    return regular_user.__dict__, token


class TestAdminUserManagement:
    """Test cases for admin user management endpoints."""

    def test_get_all_users_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Test that getting all users without authentication fails."""
        response = client.get(f"{settings.API_STR}/users/admin/users")
        assert response.status_code == 401, "Should require authentication"
        response_data = response.json()
        assert (
            "not authenticated" in response_data.get("message", "").lower()
            or "unauthorized" in response_data.get("message", "").lower()
            or "credentials" in response_data.get("message", "").lower()
        )

    def test_get_all_users_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Test that regular users cannot get all users."""
        # Create and login regular user
        _, token = create_and_login_regular_user(client, db_session, "get_users")

        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/users/admin/users", headers=headers)
        assert response.status_code == 403, "Regular users should not be able to get all users"
        assert "Admin access required" in response.text

    def test_get_all_users_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Test that admin users can get all users."""
        # Create some test users first
        user1 = DBUser(
            username="test_user_1",
            email="test_user_1@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="test_user_2",
            email="test_user_2@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user1 = UserRepository().create_user(user1)
        user2 = UserRepository().create_user(user2)

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "get_users")

        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/users/admin/users", headers=headers)
        assert response.status_code == 200, f"Admin should be able to get all users: {response.text}"

        result = response.json()
        assert isinstance(result, dict)
        assert "items" in result
        users = result["items"]
        assert len(users) >= 3, "Should return at least 3 users (admin + 2 test users)"

        # Check that admin fields are included
        for user in users:
            assert "is_admin" in user
            assert "is_superuser" in user

    def test_get_all_users_with_superuser(self, client: TestClient, db_session: Any) -> None:
        """Test that superusers can get all users."""
        # Create and login superuser
        _, token = create_and_login_superuser(client, db_session, "get_users")

        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/users/admin/users", headers=headers)
        assert response.status_code == 200, f"Superuser should be able to get all users: {response.text}"

        result = response.json()
        assert isinstance(result, dict)
        assert "items" in result
        users = result["items"]
        assert len(users) >= 1, "Should return at least 1 user (superuser)"

    def test_get_all_users_pagination(self, client: TestClient, db_session: Any) -> None:
        """Test pagination for admin get all users."""
        # Create multiple test users
        test_users: List[DBUser] = []
        for i in range(5):
            user = DBUser(
                username=f"test_user_pagination_{i}",
                email=f"test_user_pagination_{i}@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
            test_users.append(UserRepository().create_user(user))

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "get_users_pagination")
        headers = get_auth_headers(token)

        response = client.get(f"{settings.API_STR}/users/admin/users?limit=2", headers=headers)
        assert response.status_code == 200, f"Admin should be able to get users: {response.text}"

        result_page1 = response.json()
        assert isinstance(result_page1, dict)
        assert "items" in result_page1
        users_page1 = result_page1["items"]
        assert len(users_page1) == 2
        assert result_page1["has_next"] is True
        assert result_page1["next_cursor"]

        response = client.get(
            f"{settings.API_STR}/users/admin/users?limit=2&cursor={result_page1['next_cursor']}", headers=headers
        )
        assert response.status_code == 200, f"Admin should be able to get users: {response.text}"

        result_page2 = response.json()
        assert isinstance(result_page2, dict)
        assert "items" in result_page2
        users_page2 = result_page2["items"]
        assert len(users_page2) == 2
        assert result_page2["has_next"] is True

        response = client.get(
            f"{settings.API_STR}/users/admin/users?limit=2&cursor={result_page2['next_cursor']}", headers=headers
        )
        assert response.status_code == 200, f"Admin should be able to get users: {response.text}"

        result_page3 = response.json()
        assert isinstance(result_page3, dict)
        assert "items" in result_page3
        users_page3 = result_page3["items"]
        assert len(users_page3) >= 1  # At least admin user

        # Verify no overlap between pages
        page1_ids = {user["id"] for user in users_page1}
        page2_ids = {user["id"] for user in users_page2}
        page3_ids = {user["id"] for user in users_page3}

        assert page1_ids.isdisjoint(page2_ids)
        assert page1_ids.isdisjoint(page3_ids)
        assert page2_ids.isdisjoint(page3_ids)

        # Check that admin fields are included
        for user in users_page1 + users_page2 + users_page3:
            assert "is_admin" in user
            assert "is_superuser" in user

    def test_admin_update_user_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Test that updating a user without authentication fails."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_update_user",
                email="test_update_user@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        update_data = {
            "username": "updated_username",
            "email": "updated_email@example.com",
        }

        response = client.put(f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data)
        assert response.status_code == 401, "Should require authentication"

    def test_admin_update_user_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Test that regular users cannot update other users."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_update_user_regular",
                email="test_update_user_regular@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login regular user
        _, token = create_and_login_regular_user(client, db_session, "update_user")

        update_data = {
            "username": "updated_username",
            "email": "updated_email@example.com",
        }

        headers = get_auth_headers(token)
        response = client.put(f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data, headers=headers)
        assert response.status_code == 403, "Regular users should not be able to update other users"
        assert "Admin access required" in response.text

    def test_admin_update_user_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Test that admin users can update other users."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_update_user_admin",
                email="test_update_user_admin@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "update_user")
        headers = get_auth_headers(token)

        update_data = {
            "username": "updated_username_by_admin",
            "email": "updated_email_by_admin@example.com",
            "is_admin": True,
            "email_verified": True,
        }

        response = client.put(f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data, headers=headers)
        assert response.status_code == 200, f"Admin should be able to update users: {response.text}"

        updated_user = response.json()
        assert updated_user["username"] == update_data["username"]
        assert updated_user["email"] == update_data["email"]
        assert updated_user["is_admin"] == update_data["is_admin"]
        assert updated_user["email_verified"] == update_data["email_verified"]

    def test_admin_update_user_with_superuser(self, client: TestClient, db_session: Any) -> None:
        """Test that superusers can update other users."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_update_user_superuser",
                email="test_update_user_superuser@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login superuser
        _, token = create_and_login_superuser(client, db_session, "update_user")
        headers = get_auth_headers(token)

        update_data = {
            "username": "updated_username_by_superuser",
            "email": "updated_email_by_superuser@example.com",
            "is_superuser": True,
        }

        response = client.put(f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data, headers=headers)
        assert response.status_code == 200, f"Superuser should be able to update users: {response.text}"

        updated_user = response.json()
        assert updated_user["username"] == update_data["username"]
        assert updated_user["email"] == update_data["email"]
        assert updated_user["is_superuser"] == update_data["is_superuser"]

    def test_admin_update_user_password(self, client: TestClient, db_session: Any) -> None:
        """Test that admin can update user password."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_update_password",
                email="test_update_password@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "update_password")

        update_data = {
            "password": "newpassword123",
        }

        headers = get_auth_headers(token)
        response = client.put(f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data, headers=headers)
        assert response.status_code == 200, f"Admin should be able to update user password: {response.text}"

        # This used to prove the write by signing in. Row 13 deleted
        # `POST /api/auth/token`, and the package's own login reads its
        # `credentials` table rather than the column this route writes, so the
        # assertion goes to the stored hash directly. It is the tighter check:
        # it distinguishes "the new password was written" from "some password
        # verifies".
        stored = UserRepository().get_legacy_password_hash(test_user.id)
        assert stored is not None
        assert verify_password("newpassword123", stored) is True
        assert verify_password("oldpassword", stored) is False

    def test_admin_cannot_remove_own_admin_privileges(self, client: TestClient, db_session: Any) -> None:
        """Test that admin cannot remove their own admin privileges."""
        # Create and login admin user
        admin_user_dict, token = create_and_login_admin_user(client, db_session, "remove_privileges")
        headers = get_auth_headers(token)

        update_data = {
            "is_admin": False,
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{admin_user_dict['id']}", json=update_data, headers=headers
        )
        assert response.status_code == 400, "Admin should not be able to remove their own admin privileges"
        assert "Cannot remove your own admin privileges" in response.text

    def test_admin_delete_user_without_authentication(self, client: TestClient, db_session: Any) -> None:
        """Test that deleting a user without authentication fails."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_delete_user",
                email="test_delete_user@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}")
        assert response.status_code == 401, "Should require authentication"

    def test_admin_delete_user_with_regular_user(self, client: TestClient, db_session: Any) -> None:
        """Test that regular users cannot delete other users."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_delete_user_regular",
                email="test_delete_user_regular@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login regular user
        _, token = create_and_login_regular_user(client, db_session, "delete_user")

        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}", headers=headers)
        assert response.status_code == 403, "Regular users should not be able to delete other users"
        assert "Admin access required" in response.text

    def test_admin_delete_user_with_admin_user(self, client: TestClient, db_session: Any) -> None:
        """Test that admin users can delete other users."""
        # Create a test user
        test_user = UserRepository().create_user(
            DBUser(
                username="test_delete_user_admin",
                email="test_delete_user_admin@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "delete_user")

        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}", headers=headers)
        assert response.status_code == 200, f"Admin should be able to delete users: {response.text}"

        # Verify the user was deleted
        get_response = client.get(f"{settings.API_STR}/users/{test_user.id}", headers=headers)
        assert get_response.status_code == 404, "User should be deleted"

    def test_admin_cannot_delete_themselves(self, client: TestClient, db_session: Any) -> None:
        """Test that admin cannot delete themselves."""
        # Create and login admin user
        admin_user_dict, token = create_and_login_admin_user(client, db_session, "delete_self")
        headers = get_auth_headers(token)

        response = client.delete(f"{settings.API_STR}/users/admin/users/{admin_user_dict['id']}", headers=headers)
        assert response.status_code == 400, "Admin should not be able to delete themselves"
        assert "Cannot delete your own account" in response.text

    def test_admin_update_nonexistent_user(self, client: TestClient, db_session: Any) -> None:
        """Test that updating a nonexistent user fails."""
        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "update_nonexistent")
        headers = get_auth_headers(token)

        update_data = {
            "username": "updated_username",
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{INVALID_UUID_STR}", json=update_data, headers=headers
        )
        assert response.status_code == 404, "Should return 404 for nonexistent user"
        assert "User" in response.json()["message"] and "not found" in response.json()["message"]

    def test_admin_delete_nonexistent_user(self, client: TestClient, db_session: Any) -> None:
        """Test that deleting a nonexistent user fails."""
        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "delete_nonexistent")

        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/users/admin/users/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404, "Should return 404 for nonexistent user"
        assert "User" in response.json()["message"] and "not found" in response.json()["message"]

    def test_admin_update_user_with_duplicate_username(self, client: TestClient, db_session: Any) -> None:
        """Test that updating user with duplicate username fails."""
        # Create two test users
        user1 = DBUser(
            username="user1",
            email="user1@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="user2",
            email="user2@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user1 = UserRepository().create_user(user1)
        user2 = UserRepository().create_user(user2)

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "duplicate_username")

        # Try to update user2 with user1's username
        update_data = {
            "username": "user1",  # Duplicate username
        }

        headers = get_auth_headers(token)
        response = client.put(f"{settings.API_STR}/users/admin/users/{user2.id}", json=update_data, headers=headers)
        assert response.status_code == 409, "Should return 409 Conflict for duplicate username"
        assert "already exists" in response.text

    def test_admin_update_user_with_duplicate_email(self, client: TestClient, db_session: Any) -> None:
        """Test that updating user with duplicate email fails."""
        # Create two test users
        user1 = DBUser(
            username="user1_email",
            email="user1@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="user2_email",
            email="user2@example.com",
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user1 = UserRepository().create_user(user1)
        user2 = UserRepository().create_user(user2)

        # Create and login admin user
        _, token = create_and_login_admin_user(client, db_session, "duplicate_email")

        # Try to update user2 with user1's email
        update_data = {
            "email": "user1@example.com",  # Duplicate email
        }

        headers = get_auth_headers(token)
        response = client.put(f"{settings.API_STR}/users/admin/users/{user2.id}", json=update_data, headers=headers)
        assert response.status_code == 409, "Should return 409 Conflict for duplicate email"
        assert "already exists" in response.text
