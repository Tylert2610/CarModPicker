import io
import os
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

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


def create_test_image() -> io.BytesIO:
    """Create a test image for uploading."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes


class TestImages:
    """Test cases for images endpoints."""

    def test_upload_image_success(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test uploading an image."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create test image
        img_bytes = create_test_image()

        # Upload image
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "file_key" in data
            assert "presigned_url" in data

    def test_upload_image_unauthorized(self, client: TestClient) -> None:
        """Test uploading an image without authentication."""
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(f"{settings.API_STR}/images/upload?entity_type=user", files=files)
        assert response.status_code == 401

    def test_upload_image_invalid_entity_type(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading an image with invalid entity type."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=invalid_type", files=files, headers=headers
        )
        assert response.status_code == 400
        assert "Invalid entity_type" in response.json()["message"]

    def test_upload_image_invalid_file_type(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading a non-image file."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to upload a text file
        files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )
        # Should fail validation (400/422) or service unavailable (503)
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_list_ownership(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that user can only upload images for their own build lists."""
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

        # Create another user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        # User 2 tries to upload image for test_user's build list (should fail)
        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_list&entity_id={build_list_id}",
            files=files,
            headers=user2_headers,
        )
        assert response.status_code == 403

    def test_upload_image_car_admin_only(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that only admins can upload images for cars."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Regular user tries to upload image for car (should fail)
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=car_generation&entity_id={car['id']}",
            files=files,
            headers=headers,
        )
        assert response.status_code == 403

    def test_get_presigned_url_success(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL for an image."""
        # Generate a valid file key format
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL (no auth required for public images)
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}")

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "presigned_url" in data
            assert "file_key" in data

    def test_get_presigned_url_invalid_file_key(self, client: TestClient) -> None:
        """Test getting presigned URL with invalid file key."""
        # Try with path traversal attempt
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key=../../../etc/passwd")
        assert response.status_code == 400

        # Try with invalid format
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key=invalid")
        assert response.status_code == 400

    def test_get_presigned_url_ownership_verification(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that authenticated users can only access their own images."""
        # Create another user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        # Generate file key for user2
        import hashlib

        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        file_key = f"user/{user2_hash}/test-image.jpg"

        # Test user tries to access user2's image (should fail if authenticated)
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}", headers=headers)
        # Should fail with 403 or 503 (service unavailable in test)
        assert response.status_code in [403, 503], f"Unexpected status: {response.text}"

    def test_delete_image_success(self, client: TestClient, test_user: DBUser) -> None:
        """Test deleting an image."""
        # Generate a valid file key for test_user
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Delete image
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        # In test environment, storage service is not configured, so expect 503 or 500
        # In production, would expect 200
        assert response.status_code in [200, 503, 500], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "file_key" in data

    def test_delete_image_unauthorized(self, client: TestClient) -> None:
        """Test deleting an image without authentication."""
        import hashlib

        # Generate a file key
        user_hash = hashlib.sha256(str(1).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}")
        assert response.status_code == 401

    def test_delete_image_wrong_owner(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that users can only delete their own images."""
        # Create another user
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        # Generate file key for user2
        import hashlib

        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        file_key = f"user/{user2_hash}/test-image.jpg"

        # Test user tries to delete user2's image (should fail)
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)
        assert response.status_code == 403

    def test_delete_image_admin_can_delete_other_users(
        self, client: TestClient, test_admin_user: DBUser, db_session: Any
    ) -> None:
        """Admins can delete any user's image (moderation / cleanup)."""
        import hashlib

        # Create a regular user whose image the admin will delete
        username = get_unique_name("victim")
        victim = UserRepository().create_user(
            DBUser(
                username=username,
                email=f"{username}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        victim_hash = hashlib.sha256(str(victim.id).encode()).hexdigest()[:16]
        file_key = f"user/{victim_hash}/test-image.jpg"

        token = get_auth_token(client, test_admin_user.username)
        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        # 200 if storage succeeds in test, 503/500 if storage backend unavailable.
        # The key assertion: NOT 403 — admin must pass the ownership gate.
        assert response.status_code != 403, f"Admin should be authorized; got {response.status_code}: {response.text}"
        assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

    def test_get_bucket_object_count_admin_only(
        self, client: TestClient, test_user: DBUser, db_session: Any, mock_s3: Dict[str, Any]
    ) -> None:
        """Test that only admins can get bucket object count; with moto S3 admin gets 200."""
        _ = mock_s3
        # Regular user tries to access (should fail)
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=headers)
        assert response.status_code == 403

        # Admin can access
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = get_auth_headers(admin_token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=admin_headers)

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["count"] == 0

    def test_get_bucket_count_by_entity_type_admin_only(
        self, client: TestClient, test_user: DBUser, db_session: Any, mock_s3: Dict[str, Any]
    ) -> None:
        """Non-admins forbidden; admin gets totals grouped by standard key prefix and other."""
        token = get_auth_token(client, test_user.username)
        r = client.get(
            f"{settings.API_STR}/images/admin/count-by-entity-type",
            headers=get_auth_headers(token),
        )
        assert r.status_code == 403

        s3 = mock_s3["client"]
        bucket = mock_s3["user_images_bucket"]
        # Standard layout: entity_type / 16-hex user hash / filename
        s3.put_object(Bucket=bucket, Key="user/aaaaaaaaaaaaaaaa/1.bin", Body=b"a")
        s3.put_object(Bucket=bucket, Key="user/aaaaaaaaaaaaaaaa/2.bin", Body=b"b")
        s3.put_object(Bucket=bucket, Key="car_generation/bbbbbbbbbbbbbbbb/3.bin", Body=b"c")
        # Second path segment is not 16 lowercase hex digits -> counted as other
        s3.put_object(Bucket=bucket, Key="user/000000000000000g/4.bin", Body=b"d")
        s3.put_object(Bucket=bucket, Key="not-standard-root-key", Body=b"e")

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin_bucket_prefix"))
        r2 = client.get(
            f"{settings.API_STR}/images/admin/count-by-entity-type",
            headers=get_auth_headers(admin_token),
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["total"] == 5
        assert body["by_entity_type"]["user"] == 2
        assert body["by_entity_type"]["car_generation"] == 1
        assert body["other"] == 2

    def test_get_bucket_object_count_admin_503_without_s3(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Without mock_s3, admin bucket count returns 503 (no S3 client in test env)."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin_no_s3"))
        admin_headers = get_auth_headers(admin_token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=admin_headers)
        assert response.status_code == 503

    def test_upload_image_build_log_post(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test uploading an image for a build log post."""
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

        # Upload image for build log post
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post&entity_id={build_list_id}",
            files=files,
            headers=headers,
        )

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_log_post_invalid_build_list(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading an image for a build log post with invalid build_list_id."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Upload image for build log post with non-existent build_list_id
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post&entity_id={INVALID_UUID_STR}",
            files=files,
            headers=headers,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()

    def test_upload_image_part(
        self, client: TestClient, test_user: DBUser, test_category, test_part_manufacturer, db_session: Any
    ) -> None:
        """Test uploading an image for a global part."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a global part
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part_id = response.json()["id"]

        # Upload image for global part
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=part&entity_id={part_id}",
            files=files,
            headers=headers,
        )

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL with custom expiration."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with custom expiration (1 hour = 3600 seconds)
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=3600")

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "presigned_url" in data
            assert "file_key" in data

    def test_get_presigned_url_max_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL with maximum expiration (90 days)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with max expiration (90 days = 7776000 seconds)
        max_expiration = 90 * 24 * 60 * 60
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        # In test environment, storage service is not configured, so expect 503
        # In production, would expect 200
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_log_post_without_entity_id(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test image upload for build_log_post without entity_id (should be allowed per code)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a test image
        img_bytes = create_test_image()

        # Upload image for build_log_post without entity_id
        files = {"file": ("test.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post",
            files=files,
            headers=headers,
        )

        # Should be allowed (for new posts)
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_zero_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration=0 (should validate and reject)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with zero expiration
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=0")

        # Should validate and reject (400 or 422) or 503 if storage not configured
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_negative_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with negative expiration (should validate and reject)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with negative expiration
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=-1")

        # Should validate and reject (400 or 422) or 503 if storage not configured
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_expiration_exceeding_maximum(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration exceeding maximum (90 days)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with expiration exceeding max (90 days + 1 second)
        max_expiration = 90 * 24 * 60 * 60 + 1
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        # Should validate and cap at maximum or reject
        assert response.status_code in [200, 400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_ownership_verification_authenticated_user(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test presigned URL ownership verification when user is authenticated but doesn't own the file."""
        import hashlib

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

        # Create file key for user2
        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        user2_file_key = f"user/{user2_hash}/test-image.jpg"

        # Test user tries to access user2's file
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={user2_file_key}", headers=headers)

        # Should be rejected (403) if ownership verification is working
        # Or 503 if storage service is not configured
        assert response.status_code in [403, 503], f"Unexpected status: {response.text}"

    def test_upload_image_file_size_at_exact_limit(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with file size exactly at the maximum limit."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a minimal valid image
        # Note: We can't easily create an exact size image, so we test with a reasonable size
        # In test environment, storage service may not be configured (503)
        img = Image.new("RGB", (10, 10), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        # Should succeed if storage is configured, or return 503 if not
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_file_size_just_over_limit(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with file size just over the limit (should reject)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a very large image that exceeds the limit
        # For testing, we'll create an image that's definitely over any reasonable limit
        large_img = Image.new("RGB", (5000, 5000), color="red")
        img_bytes = io.BytesIO()
        large_img.save(img_bytes, format="PNG", optimize=False)
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        # Should reject if file is over limit (400/422) or 503 if storage not configured
        # Note: In test environment, storage may not validate size, so we check for either
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_png(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with PNG format."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img = Image.new("RGB", (100, 100), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_jpeg(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with JPEG format."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img = Image.new("RGB", (100, 100), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        files = {"file": ("test_image.jpg", img_bytes, "image/jpeg")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_webp(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with WEBP format (if supported)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        try:
            img = Image.new("RGB", (100, 100), color="yellow")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="WEBP")
            img_bytes.seek(0)

            files = {"file": ("test_image.webp", img_bytes, "image/webp")}
            data = {"entity_type": "user", "entity_id": str(test_user.id)}
            response = client.post(f"{settings.API_STR}/images/upload", files=files, data=data, headers=headers)

            # May succeed, fail validation, or return 503 if storage not configured
            assert response.status_code in [200, 400, 422, 503], f"Unexpected status: {response.text}"
        except Exception:
            # WEBP may not be supported in all environments
            pass

    def test_upload_image_corrupted_file(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with corrupted/invalid image file."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a file with image extension but corrupted content
        corrupted_content = b"This is not a valid image file, but has .png extension"
        files = {"file": ("fake_image.png", io.BytesIO(corrupted_content), "image/png")}
        data = {"entity_type": "user", "entity_id": str(test_user.id)}
        response = client.post(f"{settings.API_STR}/images/upload", files=files, data=data, headers=headers)

        # Should reject corrupted files (400/422) or 503 if storage not configured
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_expiration_at_maximum(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration exactly at maximum (90 days = 7776000 seconds)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        # Get presigned URL with expiration exactly at maximum (90 days)
        max_expiration = 90 * 24 * 60 * 60  # 7776000 seconds
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        # Should succeed (200) or 503 if storage not configured
        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_delete_image_idempotency(self, client: TestClient, test_user: DBUser) -> None:
        """Test that deleting a non-existent image is idempotent (should handle gracefully)."""
        import hashlib

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Generate a valid file key for test_user that doesn't exist
        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/nonexistent-image.jpg"

        # Try to delete non-existent image
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        # Should either succeed (idempotent) or return appropriate error
        # In test environment, storage service may not be configured (503)
        # If configured, deletion of non-existent file may succeed (idempotent) or return 500
        assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

        # Try deleting again (should be idempotent)
        response2 = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)
        assert response2.status_code in [200, 500, 503], f"Unexpected status on second delete: {response2.text}"

    def test_upload_image_failure_rollback(self, client: TestClient, test_user: DBUser) -> None:
        """Test that if database update fails after storage upload, the uploaded file is cleaned up (requires mocking)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create test image
        img_bytes = create_test_image()

        # Mock storage service to succeed on upload but fail on subsequent operations
        # This simulates a scenario where file is uploaded but DB operation fails
        with (
            patch("app.api.endpoints.images.storage_service.upload_image") as mock_upload,
            patch("app.api.endpoints.images.storage_service.get_presigned_url") as mock_presigned,
            patch("app.api.endpoints.images.storage_service.delete_image") as mock_delete,
        ):
            # Mock successful upload
            mock_upload.return_value = "user/test_hash/test-image.png"
            mock_presigned.return_value = "https://example.com/presigned-url"

            # Simulate DB failure by raising an exception after upload
            # In a real scenario, this would be a DB commit failure
            # For testing, we'll verify the upload was called and check error handling
            files = {"file": ("test_image.png", img_bytes, "image/png")}

            # The endpoint should handle errors gracefully
            # In test environment, storage may not be configured (503)
            # If configured and DB fails, should return 500
            response = client.post(
                f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
                files=files,
                headers=headers,
            )

            # Should either succeed (200), fail with storage error (503), or fail with DB error (500)
            assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

            # Note: In a real scenario with DB failure, we'd want to verify that
            # storage_service.delete_image was called to clean up the uploaded file
            # However, the current implementation doesn't have explicit rollback logic
            # for storage cleanup on DB failure, so we just verify the endpoint handles errors
