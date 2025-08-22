from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


# Helper function to create and login a superuser
def create_and_login_superuser(
    client: TestClient, db_session: Session, username_suffix: str = "superuser"
) -> dict:
    """Create a superuser and log them in."""
    username = f"superuser_test_{username_suffix}"
    email = f"superuser_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create superuser directly in database
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
    db_session.refresh(superuser)

    # Log in to set cookie on the client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert (
        token_response.status_code == 200
    ), f"Failed to login superuser: {token_response.text}"

    return superuser.__dict__


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


class TestAdminUserManagement:
    """Test cases for admin user management endpoints."""

    def test_get_all_users_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that getting all users without authentication fails."""
        response = client.get(f"{settings.API_STR}/users/admin/users")
        assert response.status_code == 401, "Should require authentication"
        assert "Could not validate credentials" in response.text

    def test_get_all_users_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot get all users."""
        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "get_users")

        response = client.get(f"{settings.API_STR}/users/admin/users")
        assert (
            response.status_code == 403
        ), "Regular users should not be able to get all users"
        assert "Admin access required" in response.text

    def test_get_all_users_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can get all users."""
        # Create some test users first
        user1 = DBUser(
            username="test_user_1",
            email="test_user_1@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="test_user_2",
            email="test_user_2@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "get_users")

        response = client.get(f"{settings.API_STR}/users/admin/users")
        assert (
            response.status_code == 200
        ), f"Admin should be able to get all users: {response.text}"

        users = response.json()
        assert len(users) >= 3, "Should return at least 3 users (admin + 2 test users)"

        # Check that admin fields are included
        for user in users:
            assert "is_admin" in user
            assert "is_superuser" in user

    def test_get_all_users_with_superuser(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that superusers can get all users."""
        # Create and login superuser
        superuser = create_and_login_superuser(client, db_session, "get_users")

        response = client.get(f"{settings.API_STR}/users/admin/users")
        assert (
            response.status_code == 200
        ), f"Superuser should be able to get all users: {response.text}"

        users = response.json()
        assert len(users) >= 1, "Should return at least 1 user (superuser)"

    def test_get_all_users_pagination(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test pagination for admin get all users."""
        # Create multiple test users
        test_users = []
        for i in range(5):
            user = DBUser(
                username=f"test_user_pagination_{i}",
                email=f"test_user_pagination_{i}@example.com",
                hashed_password=get_password_hash("password"),
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
            test_users.append(user)

        db_session.add_all(test_users)
        db_session.commit()

        # Create and login admin user
        admin_user = create_and_login_admin_user(
            client, db_session, "get_users_pagination"
        )

        # Test first page (limit=2, skip=0)
        response = client.get(f"{settings.API_STR}/users/admin/users?limit=2&skip=0")
        assert (
            response.status_code == 200
        ), f"Admin should be able to get users: {response.text}"

        users_page1 = response.json()
        assert len(users_page1) == 2

        # Test second page (limit=2, skip=2)
        response = client.get(f"{settings.API_STR}/users/admin/users?limit=2&skip=2")
        assert (
            response.status_code == 200
        ), f"Admin should be able to get users: {response.text}"

        users_page2 = response.json()
        assert len(users_page2) == 2

        # Test third page (limit=2, skip=4)
        response = client.get(f"{settings.API_STR}/users/admin/users?limit=2&skip=4")
        assert (
            response.status_code == 200
        ), f"Admin should be able to get users: {response.text}"

        users_page3 = response.json()
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

    def test_admin_update_user_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that updating a user without authentication fails."""
        # Create a test user
        test_user = DBUser(
            username="test_update_user",
            email="test_update_user@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        update_data = {
            "username": "updated_username",
            "email": "updated_email@example.com",
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data
        )
        assert response.status_code == 401, "Should require authentication"

    def test_admin_update_user_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot update other users."""
        # Create a test user
        test_user = DBUser(
            username="test_update_user_regular",
            email="test_update_user_regular@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "update_user")

        update_data = {
            "username": "updated_username",
            "email": "updated_email@example.com",
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data
        )
        assert (
            response.status_code == 403
        ), "Regular users should not be able to update other users"
        assert "Admin access required" in response.text

    def test_admin_update_user_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can update other users."""
        # Create a test user
        test_user = DBUser(
            username="test_update_user_admin",
            email="test_update_user_admin@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "update_user")

        update_data = {
            "username": "updated_username_by_admin",
            "email": "updated_email_by_admin@example.com",
            "is_admin": True,
            "email_verified": True,
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data
        )
        assert (
            response.status_code == 200
        ), f"Admin should be able to update users: {response.text}"

        updated_user = response.json()
        assert updated_user["username"] == update_data["username"]
        assert updated_user["email"] == update_data["email"]
        assert updated_user["is_admin"] == update_data["is_admin"]
        assert updated_user["email_verified"] == update_data["email_verified"]

    def test_admin_update_user_with_superuser(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that superusers can update other users."""
        # Create a test user
        test_user = DBUser(
            username="test_update_user_superuser",
            email="test_update_user_superuser@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login superuser
        superuser = create_and_login_superuser(client, db_session, "update_user")

        update_data = {
            "username": "updated_username_by_superuser",
            "email": "updated_email_by_superuser@example.com",
            "is_superuser": True,
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data
        )
        assert (
            response.status_code == 200
        ), f"Superuser should be able to update users: {response.text}"

        updated_user = response.json()
        assert updated_user["username"] == update_data["username"]
        assert updated_user["email"] == update_data["email"]
        assert updated_user["is_superuser"] == update_data["is_superuser"]

    def test_admin_update_user_password(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin can update user password."""
        # Create a test user
        test_user = DBUser(
            username="test_update_password",
            email="test_update_password@example.com",
            hashed_password=get_password_hash("oldpassword"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "update_password")

        update_data = {
            "password": "newpassword123",
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{test_user.id}", json=update_data
        )
        assert (
            response.status_code == 200
        ), f"Admin should be able to update user password: {response.text}"

        # Verify password was updated by trying to login with new password
        login_data = {"username": test_user.username, "password": "newpassword123"}
        login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert (
            login_response.status_code == 200
        ), "Should be able to login with new password"

    def test_admin_cannot_remove_own_admin_privileges(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin cannot remove their own admin privileges."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(
            client, db_session, "remove_privileges"
        )

        update_data = {
            "is_admin": False,
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{admin_user['id']}", json=update_data
        )
        assert (
            response.status_code == 400
        ), "Admin should not be able to remove their own admin privileges"
        assert "Cannot remove your own admin privileges" in response.text

    def test_admin_delete_user_without_authentication(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that deleting a user without authentication fails."""
        # Create a test user
        test_user = DBUser(
            username="test_delete_user",
            email="test_delete_user@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}")
        assert response.status_code == 401, "Should require authentication"

    def test_admin_delete_user_with_regular_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that regular users cannot delete other users."""
        # Create a test user
        test_user = DBUser(
            username="test_delete_user_regular",
            email="test_delete_user_regular@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login regular user
        regular_user = create_and_login_regular_user(client, db_session, "delete_user")

        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}")
        assert (
            response.status_code == 403
        ), "Regular users should not be able to delete other users"
        assert "Admin access required" in response.text

    def test_admin_delete_user_with_admin_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin users can delete other users."""
        # Create a test user
        test_user = DBUser(
            username="test_delete_user_admin",
            email="test_delete_user_admin@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "delete_user")

        response = client.delete(f"{settings.API_STR}/users/admin/users/{test_user.id}")
        assert (
            response.status_code == 200
        ), f"Admin should be able to delete users: {response.text}"

        # Verify the user was deleted
        get_response = client.get(f"{settings.API_STR}/users/{test_user.id}")
        assert get_response.status_code == 404, "User should be deleted"

    def test_admin_cannot_delete_themselves(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that admin cannot delete themselves."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "delete_self")

        response = client.delete(
            f"{settings.API_STR}/users/admin/users/{admin_user['id']}"
        )
        assert (
            response.status_code == 400
        ), "Admin should not be able to delete themselves"
        assert "Cannot delete your own account" in response.text

    def test_admin_update_nonexistent_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that updating a nonexistent user fails."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(
            client, db_session, "update_nonexistent"
        )

        update_data = {
            "username": "updated_username",
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/99999", json=update_data
        )
        assert response.status_code == 404, "Should return 404 for nonexistent user"
        assert "User not found" in response.text

    def test_admin_delete_nonexistent_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that deleting a nonexistent user fails."""
        # Create and login admin user
        admin_user = create_and_login_admin_user(
            client, db_session, "delete_nonexistent"
        )

        response = client.delete(f"{settings.API_STR}/users/admin/users/99999")
        assert response.status_code == 404, "Should return 404 for nonexistent user"
        assert "User not found" in response.text

    def test_admin_update_user_with_duplicate_username(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that updating user with duplicate username fails."""
        # Create two test users
        user1 = DBUser(
            username="user1",
            email="user1@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="user2",
            email="user2@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Create and login admin user
        admin_user = create_and_login_admin_user(
            client, db_session, "duplicate_username"
        )

        # Try to update user2 with user1's username
        update_data = {
            "username": "user1",  # Duplicate username
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{user2.id}", json=update_data
        )
        assert response.status_code == 400, "Should not allow duplicate username"
        assert "already exists" in response.text

    def test_admin_update_user_with_duplicate_email(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that updating user with duplicate email fails."""
        # Create two test users
        user1 = DBUser(
            username="user1_email",
            email="user1@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        user2 = DBUser(
            username="user2_email",
            email="user2@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Create and login admin user
        admin_user = create_and_login_admin_user(client, db_session, "duplicate_email")

        # Try to update user2 with user1's email
        update_data = {
            "email": "user1@example.com",  # Duplicate email
        }

        response = client.put(
            f"{settings.API_STR}/users/admin/users/{user2.id}", json=update_data
        )
        assert response.status_code == 400, "Should not allow duplicate email"
        assert "already exists" in response.text
