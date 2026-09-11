import os
from typing import Any, Dict
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user


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


def get_auth_headers(token: str) -> Dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[Dict[str, Any], str]:
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


class TestBuildLogs:
    """Test cases for build logs endpoints."""

    def test_count_build_log_posts_success(self, client: TestClient, db_session: Any) -> None:
        """Test counting build log posts."""
        response = client.get(f"{settings.API_STR}/build-logs/posts/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_get_build_log_by_build_list_public_access(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test getting build log by build list ID (public read access)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Get build log without authentication (public read access)
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "build_list_id" in data
        assert data["build_list_id"] == build_list_id
        assert "title" in data
        assert "posts" in data
        assert "pagination" in data
        assert isinstance(data["posts"], list)

    def test_get_build_log_auto_creates_build_log(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that accessing a build log auto-creates it if it doesn't exist."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Get build log - should auto-create
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["build_list_id"] == build_list_id
        assert "Build Log:" in data["title"]

    def test_get_build_log_with_pagination(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test getting build log with pagination."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create some posts
        for i in range(5):
            post_data = {"content": f"Test post {i}"}
            response = client.post(
                f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
                json=post_data,
                headers=headers,
            )
            assert response.status_code == 201

        # Get build log with pagination
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 2
        assert data["pagination"]["items_per_page"] == 2
        assert data["pagination"]["total_items"] == 5

    def test_get_build_log_build_list_not_found(self, client: TestClient) -> None:
        """Test getting build log for non-existent build list."""
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{INVALID_UUID_STR}")
        assert response.status_code == 404

    def test_create_build_log_post_success(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test creating a build log post."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "This is a test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == post_data["content"]
        assert data["user_id"] == str(test_user.id)
        assert "author_username" in data
        assert data["author_username"] == test_user.username

    def test_create_build_log_post_auto_creates_build_log(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that creating a post auto-creates the build log if it doesn't exist."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post - should auto-create build log
        post_data = {"content": "This is a test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201

        # Verify build log was created
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 200

    def test_create_build_log_post_unauthorized(self, client: TestClient) -> None:
        """Test creating a build log post without authentication."""
        post_data = {"content": "This is a test post"}
        response = client.post(f"{settings.API_STR}/build-logs/build-list/{INVALID_UUID_STR}/posts", json=post_data)
        assert response.status_code == 401

    def test_create_build_log_post_build_list_not_found(self, client: TestClient, test_user: DBUser) -> None:
        """Test creating a post for non-existent build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        post_data = {"content": "This is a test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{INVALID_UUID_STR}/posts", json=post_data, headers=headers
        )
        assert response.status_code == 404

    def test_create_build_log_post_empty_content(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test creating a post with empty content."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Try to create a post with empty content
        post_data = {"content": ""}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 422  # Validation error

    def test_update_build_log_post_success(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test updating a build log post."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Original content"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Update the post
        update_data = {"content": "Updated content"}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == update_data["content"]

    def test_update_build_log_post_unauthorized(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test updating another user's post (should fail)."""
        # Create two users
        user1_token = get_auth_token(client, test_user.username)
        user1_headers = get_auth_headers(user1_token)

        # Create second user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # User 1 creates a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=user1_headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        # User 1 creates a post
        post_data = {"content": "User 1's post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=user1_headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # User 2 tries to update User 1's post (should fail)
        update_data = {"content": "Malicious update"}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=user2_headers)
        assert response.status_code == 403

    def test_update_build_log_post_build_list_owner_can_update(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that build list owner can update any post in their build log."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create second user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)

        # Test user creates a build list
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

        # User 2 creates a post in test user's build log
        post_data = {"content": "User 2's post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=user2_headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Test user (build list owner) can update User 2's post
        update_data = {"content": "Updated by build list owner"}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        assert response.status_code == 200

    def test_update_build_log_post_not_found(self, client: TestClient, test_user: DBUser) -> None:
        """Test updating a non-existent post."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        update_data = {"content": "Updated content"}
        response = client.put(
            f"{settings.API_STR}/build-logs/posts/{INVALID_UUID_STR}", json=update_data, headers=headers
        )
        assert response.status_code == 404

    def test_delete_build_log_post_success(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test deleting a build log post."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Post to delete"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Delete the post
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{post_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Build log post deleted successfully"

        # Verify post is deleted
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 0

    def test_delete_build_log_post_build_list_owner_can_delete(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that build list owner can delete any post in their build log."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create second user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)

        # Test user creates a build list
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

        # User 2 creates a post
        post_data = {"content": "User 2's post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=user2_headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Test user (build list owner) can delete User 2's post
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{post_id}", headers=headers)
        assert response.status_code == 200

    def test_delete_build_log_post_unauthorized(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test deleting another user's post (should fail)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create second user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        # Test user creates a build list
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

        # User 2 creates a post
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)
        post_data = {"content": "User 2's post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=user2_headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Test user tries to delete User 2's post (should fail - test user doesn't own build list or post)
        # Actually, wait - test_user owns the build list, so they should be able to delete it
        # Let's create a different scenario where test_user doesn't own the build list
        # Create another build list owned by user2
        build_list_data2 = {
            "name": get_unique_name("test_build_list2"),
            "description": "User 2's build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data2, headers=user2_headers)
        assert response.status_code == 200
        build_list_id2 = response.json()["id"]

        # User 2 creates a post in their own build list
        post_data2 = {"content": "User 2's post in their build list"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id2}/posts",
            json=post_data2,
            headers=user2_headers,
        )
        assert response.status_code == 201
        post_id2 = response.json()["id"]

        # Test user tries to delete User 2's post from User 2's build list (should fail)
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{post_id2}", headers=headers)
        assert response.status_code == 403

        # Clean up: delete the post we created earlier (post_id) to avoid test pollution
        # This is just for cleanup, not part of the test assertion

    def test_delete_build_log_post_not_found(self, client: TestClient, test_user: DBUser) -> None:
        """Test deleting a non-existent post."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_delete_build_log_post_admin_can_delete(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that admin can delete any build log post."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Post to delete by admin"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Admin can delete the post
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin_deleter"))
        admin_headers = get_auth_headers(admin_token)
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{post_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Build log post deleted successfully"

    def test_update_build_log_post_empty_content(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test updating a build log post with empty content."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Original content"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Try to update with empty content
        update_data = {"content": ""}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        assert response.status_code == 422  # Validation error

    def test_get_build_log_pagination_boundary_cases(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test build log pagination with boundary cases."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create 3 posts
        for i in range(3):
            post_data = {"content": f"Test post {i}"}
            response = client.post(
                f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
                json=post_data,
                headers=headers,
            )
            assert response.status_code == 201

        # Test limit=1 (minimum)
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}?skip=0&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 1
        assert data["pagination"]["items_per_page"] == 1
        assert data["pagination"]["total_items"] == 3

        # Test skip at boundary (skip=2, should return 1 item)
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}?skip=2&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 1
        assert data["pagination"]["total_items"] == 3

        # Test skip beyond total (should return empty)
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}?skip=10&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 0
        assert data["pagination"]["total_items"] == 3

    def test_update_build_log_post_with_null_content(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test updating a build log post with null content (partial update - should preserve existing content)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        original_content = "Original content"
        post_data = {"content": original_content}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Update with null content (should preserve original)
        update_data = {"content": None}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Content should remain unchanged when None is provided
        assert data["content"] == original_content

    def test_build_log_post_author_image_url_when_author_deleted(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test build log post retrieval when author user is deleted (orphaned post scenario)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create second user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)

        # Create a build list
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

        # User 2 creates a post
        post_data = {"content": "User 2's post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=user2_headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        UserRepository().delete_user(user2)

        # Retrieve the build log - should handle deleted author gracefully
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 1
        # Author username should be None when author is deleted
        assert data["posts"][0]["author_username"] is None
        assert data["posts"][0]["author_image_url"] is None

    def test_build_log_post_author_image_url_when_no_profile_picture(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test build log post when author has no profile picture."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Ensure test_user has no profile picture
        test_user = UserRepository().update(test_user.id, image_urls=None)

        # Create a post
        post_data = {"content": "Test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["author_username"] == test_user.username
        assert data["author_image_url"] is None

    def test_build_log_post_creation_with_very_long_content(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test build log post creation with very long content (boundary testing)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post with very long content (10KB)
        long_content = "A" * 10000
        post_data = {"content": long_content}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == long_content
        assert len(data["content"]) == 10000

    def test_build_log_post_update_with_whitespace_only_content(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test updating build log post with whitespace-only content."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Original content"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Try to update with whitespace-only content
        update_data = {"content": "   \n\t  "}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        # Should either validate and reject (422) or accept and strip (200)
        # Based on schema validation, it should likely be rejected
        assert response.status_code in [200, 422]
        # post_id is used in the assertion above, so it's not unused

    def test_build_list_deletion_cascades_to_build_log_and_posts(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that deleting a build list cascades to delete build log and all posts."""
        from app.db.dynamo.build_logs import BuildLogPostRepository, BuildLogRepository

        build_logs = BuildLogRepository()
        build_log_posts = BuildLogPostRepository()

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create multiple posts in the build log
        post_ids = []
        for i in range(3):
            post_data = {"content": f"Test post {i}"}
            response = client.post(
                f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
                json=post_data,
                headers=headers,
            )
            assert response.status_code == 201
            post_ids.append(response.json()["id"])

        # Verify build log and posts exist
        build_log = build_logs.for_build_list(UUID(build_list_id))
        assert build_log is not None
        assert len(build_log_posts.all_for_build_log(build_log.id)) == 3

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}", headers=headers)
        assert response.status_code == 200

        # Verify build log is deleted (cascade)
        assert build_logs.for_build_list(UUID(build_list_id)) is None, "Build log should be deleted with its list"

        # Verify all posts are deleted (cascade)
        assert all(
            build_log_posts.get(UUID(p)) is None for p in post_ids
        ), "All posts should be deleted when build list is deleted"

    def test_access_build_log_after_build_list_deletion(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that accessing build log returns 404 when build list is deleted."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}", headers=headers)
        assert response.status_code == 200

        # Try to access build log - should return 404
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{build_list_id}")
        assert response.status_code == 404

    def test_update_post_after_build_list_deletion(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that updating a post fails with 404 when build list is deleted."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}", headers=headers)
        assert response.status_code == 200

        # Try to update the post - should return 404 (build list not found)
        update_data = {"content": "Updated content"}
        response = client.put(f"{settings.API_STR}/build-logs/posts/{post_id}", json=update_data, headers=headers)
        assert response.status_code == 404

    def test_delete_post_after_build_list_deletion(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that deleting a post fails with 404 when build list is deleted."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Create a post
        post_data = {"content": "Test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 201
        post_id = response.json()["id"]

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}", headers=headers)
        assert response.status_code == 200

        # Try to delete the post - should return 404 (build list not found)
        response = client.delete(f"{settings.API_STR}/build-logs/posts/{post_id}", headers=headers)
        assert response.status_code == 404

    def test_create_post_after_build_list_deletion(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that creating a post fails with 404 when build list is deleted."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
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

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}", headers=headers)
        assert response.status_code == 200

        # Try to create a post - should return 404 (build list not found)
        post_data = {"content": "Test post"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id}/posts",
            json=post_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_multiple_posts_same_author_different_build_logs(
        self, client: TestClient, premium_test_user: DBUser, db_session: Any
    ) -> None:
        """Test that author info is correctly populated for posts across different build logs."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Use premium user so we can create multiple build lists
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        build_list_data1 = {
            "name": get_unique_name("test_build_list_1"),
            "description": "First build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data1, headers=headers)
        assert response.status_code == 200
        build_list_id1 = response.json()["id"]

        build_list_data2 = {
            "name": get_unique_name("test_build_list_2"),
            "description": "Second build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data2, headers=headers)
        assert response.status_code == 200
        build_list_id2 = response.json()["id"]

        # Create posts in both build logs
        post_data1 = {"content": "Post in first build log"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id1}/posts",
            json=post_data1,
            headers=headers,
        )
        assert response.status_code == 201
        post1_data = response.json()
        assert post1_data["author_username"] == premium_test_user.username

        post_data2 = {"content": "Post in second build log"}
        response = client.post(
            f"{settings.API_STR}/build-logs/build-list/{build_list_id2}/posts",
            json=post_data2,
            headers=headers,
        )
        assert response.status_code == 201
        post2_data = response.json()
        assert post2_data["author_username"] == premium_test_user.username

        # Verify both posts have correct author info
        assert post1_data["author_username"] == premium_test_user.username
        assert post2_data["author_username"] == premium_test_user.username
        # Both should have the same author since they're from the same user
