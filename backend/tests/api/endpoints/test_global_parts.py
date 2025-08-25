import os
import pytest
from typing import Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models.user import User
from app.api.models.category import Category


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestGlobalParts:
    """Test cases for global parts endpoints."""

    def test_create_global_part_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test successful creation of a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,  # Price in cents (integer)
            "category_id": test_category.id,
            "image_url": "https://example.com/image.jpg",
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == part_data["name"]
        assert data["description"] == part_data["description"]
        assert data["price"] == part_data["price"]
        assert data["category_id"] == test_category.id
        assert data["user_id"] == test_user.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_global_part_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test creating a global part without authentication."""
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,  # Price in cents (integer)
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 401

    def test_get_global_parts_list(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test retrieving list of global parts."""
        # Login and create a part first
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        # Get the list
        response = client.get(f"{settings.API_STR}/global-parts/")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_global_parts_with_pagination(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test pagination for global parts list."""
        # Login and create multiple parts
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create multiple parts
        for i in range(3):
            part_data = {
                "name": get_unique_name(f"test_part_{i}"),
                "description": f"Test part {i}",
                "price": 9999 + i,  # Price in cents (integer)
                "category_id": test_category.id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
            assert response.status_code == 200

        # Test pagination
        response = client.get(f"{settings.API_STR}/global-parts/?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    def test_get_global_parts_with_category_filter(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test filtering global parts by category."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        # Filter by category
        response = client.get(
            f"{settings.API_STR}/global-parts/?category_id={test_category.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for part in data:
            assert part["category_id"] == test_category.id

    def test_get_global_parts_with_search(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test searching global parts."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        unique_name = get_unique_name("searchable_part")
        part_data = {
            "name": unique_name,
            "description": "A searchable part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        # Search by name
        response = client.get(f"{settings.API_STR}/global-parts/?search={unique_name}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(unique_name in part["name"] for part in data)

    def test_get_global_part_by_id(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test retrieving a specific global part by ID."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        created_part = response.json()

        # Get the part by ID
        response = client.get(f"{settings.API_STR}/global-parts/{created_part['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_part["id"]
        assert data["name"] == created_part["name"]

    def test_get_global_part_not_found(self, client: TestClient) -> None:
        """Test retrieving a non-existent global part."""
        response = client.get(f"{settings.API_STR}/global-parts/99999")
        assert response.status_code == 404

    def test_update_global_part_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test successful update of a global part."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        created_part = response.json()

        # Update the part
        update_data = {
            "name": get_unique_name("updated_part"),
            "description": "Updated description",
            "price": 14999,  # Price in cents (integer)
        }
        response = client.put(
            f"{settings.API_STR}/global-parts/{created_part['id']}", json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["price"] == update_data["price"]

    def test_update_global_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a global part without proper authorization."""
        # Create a part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        created_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to update without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(
            f"{settings.API_STR}/global-parts/{created_part['id']}", json=update_data
        )
        assert response.status_code == 401

    def test_delete_global_part_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test successful deletion of a global part."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        created_part = response.json()

        # Delete the part
        response = client.delete(
            f"{settings.API_STR}/global-parts/{created_part['id']}"
        )
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f"{settings.API_STR}/global-parts/{created_part['id']}")
        assert response.status_code == 404

    def test_delete_global_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test deleting a global part without proper authorization."""
        # Create a part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        created_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to delete without authentication
        response = client.delete(
            f"{settings.API_STR}/global-parts/{created_part['id']}"
        )
        assert response.status_code == 401

    def test_get_global_parts_with_votes(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test retrieving global parts with vote data."""
        # Login and create a part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200

        # Get parts with votes
        response = client.get(f"{settings.API_STR}/global-parts/with-votes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            part = data[0]
            assert "upvotes" in part
            assert "downvotes" in part
            assert "user_vote" in part

    def test_create_global_part_with_invalid_price(
        self, client: TestClient, test_user: Any, test_category: Any
    ) -> None:
        """Test that creating a global part with an invalid price fails validation."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Test with price too large for PostgreSQL integer
        part_data = {
            "name": "Test Part with Invalid Price",
            "description": "A test part with invalid price",
            "price": 2147483648,  # One more than max PostgreSQL integer
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["loc"]

        # Test with negative price
        part_data["price"] = -1
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "greater_than_equal"
        assert "price" in error_detail["loc"]

        # Test with extremely large price
        part_data["price"] = 999999999999999999
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["loc"]
