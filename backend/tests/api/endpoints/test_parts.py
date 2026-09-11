import os
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category, PartManufacturer, Retailer
from app.db.dynamo.users import User, UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, login_user, save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_token_and_headers(client: TestClient, username: str, password: str = "testpassword") -> dict[str, str]:
    """Login and return Authorization headers with Bearer token."""
    token = login_user(client, username)
    return auth_headers(token)


class TestParts:
    """Test cases for global parts endpoints."""

    def test_create_part_success(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test successful creation of a global part."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Create global part (pricing is per-retailer via listings, not on part)
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "image_urls": ["https://example.com/image.jpg"],
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == part_data["name"]
        assert data["description"] == part_data["description"]
        assert data["category_id"] == str(test_category.id)
        assert data["user_id"] == str(test_user.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_part_unauthorized(
        self, client: TestClient, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test creating a global part without authentication."""
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data)
        assert response.status_code == 401

    def test_get_parts_list(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test retrieving list of global parts."""
        # Login and create a part first
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get the list
        response = client.get(f"{settings.API_STR}/parts/", headers=headers)
        assert response.status_code == 200

        data: list[Any] = response.json()["items"]
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_parts_with_pagination(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test pagination for global parts list."""
        # Login and create multiple parts
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple parts
        for i in range(3):
            part_data = {
                "name": get_unique_name(f"test_part_{i}"),
                "description": f"Test part {i}",
                "category_id": str(test_category.id),
                "part_manufacturer_id": str(test_part_manufacturer.id),
            }
            response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        # Test pagination
        response = client.get(f"{settings.API_STR}/parts/?limit=2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["has_next"] is True
        assert data["next_cursor"]

    def test_get_parts_with_category_filter(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test filtering global parts by category."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Filter by category
        response = client.get(f"{settings.API_STR}/parts/?category_id={test_category.id}", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()["items"]
        assert isinstance(data, list)
        part: Any
        for part in data:
            assert part["category_id"] == str(test_category.id)

    def test_get_parts_with_search(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test searching global parts."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        unique_name = get_unique_name("searchable_part")
        part_data = {
            "name": unique_name,
            "description": "A searchable part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Search by name
        response = client.get(f"{settings.API_STR}/parts/?search={unique_name}", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()["items"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(unique_name in part["name"] for part in data)  # type: ignore[misc]

    def test_get_part_by_id(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test retrieving a specific global part by ID."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Get the part by ID
        response = client.get(f"{settings.API_STR}/parts/{created_part['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_part["id"]
        assert data["name"] == created_part["name"]

    def test_get_part_not_found(self, client: TestClient) -> None:
        """Test retrieving a non-existent global part."""
        response = client.get(f"{settings.API_STR}/parts/{INVALID_UUID_STR}")
        assert response.status_code == 404

    def test_update_part_success(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test successful update of a global part."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Update the part (price is per-retailer via listings, not on part)
        update_data = {
            "name": get_unique_name("updated_part"),
            "description": "Updated description",
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.put(f"{settings.API_STR}/parts/{created_part['id']}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test updating a global part without proper authorization."""
        # Create a part as test_user
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Try to update without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(f"{settings.API_STR}/parts/{created_part['id']}", json=update_data)
        assert response.status_code == 401

    def test_delete_part_success(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test successful deletion of a global part."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Delete the part
        response = client.delete(f"{settings.API_STR}/parts/{created_part['id']}", headers=headers)
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f"{settings.API_STR}/parts/{created_part['id']}", headers=headers)
        assert response.status_code == 404

    def test_delete_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test deleting a global part without proper authorization."""
        # Create a part as test_user
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Try to delete without authentication
        response = client.delete(f"{settings.API_STR}/parts/{created_part['id']}")
        assert response.status_code == 401

    def test_get_parts_with_votes(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test retrieving global parts with vote data."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get parts with votes
        response = client.get(f"{settings.API_STR}/parts/with-votes", headers=headers)
        assert response.status_code == 200
        result: dict[str, Any] = response.json()
        assert isinstance(result, dict)
        assert "items" in result
        assert "has_next" in result
        data: list[Any] = result["items"]
        assert isinstance(data, list)
        if len(data) > 0:
            part: Any = data[0]
            assert "upvotes" in part
            assert "downvotes" in part
            assert "user_vote" in part

    def test_get_parts_with_votes_universal_filter(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test that universal=true returns only parts with is_universal=True."""
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create a universal part
        universal_data = {
            "name": get_unique_name("universal_part"),
            "description": "Universal part",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "is_universal": True,
        }
        r1 = client.post(f"{settings.API_STR}/parts/", json=universal_data, headers=headers)
        assert r1.status_code == 200
        universal_id = r1.json()["id"]

        # Create a non-universal part
        non_universal_data = {
            "name": get_unique_name("car_specific_part"),
            "description": "Car-specific part",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "is_universal": False,
        }
        r2 = client.post(f"{settings.API_STR}/parts/", json=non_universal_data, headers=headers)
        assert r2.status_code == 200
        non_universal_id = r2.json()["id"]

        # Without filter: both parts can appear
        response = client.get(f"{settings.API_STR}/parts/with-votes", headers=headers)
        assert response.status_code == 200
        all_data = response.json()["items"]
        all_ids = {p["id"] for p in all_data}
        assert universal_id in all_ids
        assert non_universal_id in all_ids

        # With universal=true: only universal part
        response = client.get(f"{settings.API_STR}/parts/with-votes?universal=true", headers=headers)
        assert response.status_code == 200
        result = response.json()
        universal_only = result["items"]
        universal_only_ids = {p["id"] for p in universal_only}
        assert universal_id in universal_only_ids
        assert non_universal_id not in universal_only_ids
        assert all(p["is_universal"] for p in universal_only)

    def test_create_part_with_invalid_price_cents(
        self, client: TestClient, test_user: Any, test_category: Any, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test that creating a global part with invalid price_cents (for retailer listing) fails validation."""
        # Login as test user
        headers = get_auth_token_and_headers(client, test_user.username)

        # Test with price_cents too large for PostgreSQL integer (schema validation)
        part_data = {
            "name": "Test Part with Invalid Price Cents",
            "description": "A test part",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "price_cents": 2147483648,  # One more than max PostgreSQL integer
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 422
        error_detail = response.json()["details"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price_cents" in error_detail["field"]

        # Test with negative price_cents
        part_data["price_cents"] = -1
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 422
        error_detail = response.json()["details"][0]
        assert error_detail["type"] == "greater_than_equal"
        assert "price_cents" in error_detail["field"]

    def test_get_parts_by_category_success(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test retrieving global parts by category."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple global parts in the same category
        part_names = [get_unique_name(f"test_part_{i}") for i in range(3)]
        created_parts = []
        for part_name in part_names:
            part_data = {
                "name": part_name,
                "description": "A test part description",
                "category_id": str(test_category.id),
                "part_manufacturer_id": str(test_part_manufacturer.id),
            }
            response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
            assert response.status_code == 200
            created_parts.append(response.json())

        # Get global parts by category (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/parts/category/{test_category.id}")
        assert response.status_code == 200

        data = response.json()["items"]
        assert isinstance(data, list)
        # Should return at least the parts we created
        assert len(data) >= len(created_parts)

        # Verify all returned parts are in the correct category
        for part in data:
            assert part["category_id"] == str(test_category.id)

        # Verify our created parts are in the results
        part_ids = {part["id"] for part in data}
        created_part_ids = {part["id"] for part in created_parts}
        assert created_part_ids.issubset(part_ids)

    def test_get_parts_by_category_with_pagination(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test pagination for global parts by category."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple global parts in the same category
        for i in range(5):
            part_data = {
                "name": get_unique_name(f"test_part_{i}"),
                "description": "A test part description",
                "category_id": str(test_category.id),
                "part_manufacturer_id": str(test_part_manufacturer.id),
            }
            response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        # Get first page
        response = client.get(f"{settings.API_STR}/parts/category/{test_category.id}?limit=2")
        assert response.status_code == 200
        first_body = response.json()
        first_page = first_body["items"]
        assert isinstance(first_page, list)
        assert len(first_page) == 2
        assert first_body["has_next"] is True

        # Get second page
        response = client.get(
            f"{settings.API_STR}/parts/category/{test_category.id}?limit=2&cursor={first_body['next_cursor']}"
        )
        assert response.status_code == 200
        second_page = response.json()["items"]
        assert isinstance(second_page, list)
        assert len(second_page) == 2

        # Verify no overlap
        first_page_ids = {part["id"] for part in first_page}
        second_page_ids = {part["id"] for part in second_page}
        assert first_page_ids.isdisjoint(second_page_ids)

    def test_get_parts_by_category_not_found(self, client: TestClient) -> None:
        """Test retrieving global parts for a non-existent category."""
        # Try to get parts for non-existent category (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/parts/category/{INVALID_UUID_STR}")
        assert response.status_code == 200
        data = response.json()["items"]
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_parts_by_category_public_endpoint(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test that getting global parts by category works without authentication."""
        # Login as test user to create data
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get global parts by category without authentication (public endpoint)
        response = client.get(f"{settings.API_STR}/parts/category/{test_category.id}")
        assert response.status_code == 200
        data = response.json()["items"]
        assert isinstance(data, list)

    def test_count_parts_by_user_success(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test counting global parts created by a specific user."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/parts/user/{test_user.id}/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/parts/user/{test_user.id}/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_parts_by_user_zero(self, client: TestClient, db_session: Any) -> None:
        """Test counting global parts for a user with no parts."""
        # Create a new user with no parts
        from app.db.dynamo.users import User as DBUser

        new_user = UserRepository().create_user(
            DBUser(
                username=f"new_user_{os.getpid()}_{id(db_session)}",
                email=f"new_user_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Count global parts for this user (should be 0)
        response = client.get(f"{settings.API_STR}/parts/user/{new_user.id}/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_count_parts_by_user_public_endpoint(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test that counting global parts by user works without authentication."""
        # Login as test user to create data
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Count global parts by user without authentication (public endpoint)
        response = client.get(f"{settings.API_STR}/parts/user/{test_user.id}/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_get_parts_filter_options(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test getting filter options for cascading filters."""
        # Create a part first
        headers = get_auth_token_and_headers(client, test_user.username)
        part_data = {
            "name": get_unique_name("filter_options_part"),
            "description": "Test part for filter options",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get filter options (public endpoint)
        response = client.get(f"{settings.API_STR}/parts/filter-options")
        assert response.status_code == 200
        data = response.json()
        assert "category_ids" in data
        assert "part_manufacturer_ids" in data
        assert isinstance(data["category_ids"], list)
        assert isinstance(data["part_manufacturer_ids"], list)
        assert str(test_category.id) in data["category_ids"]
        assert str(test_part_manufacturer.id) in data["part_manufacturer_ids"]

    def test_get_parts_filter_options_with_filters(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test filter options with category/part_manufacturer filters."""
        response = client.get(
            f"{settings.API_STR}/parts/filter-options"
            f"?category_ids={test_category.id}&part_manufacturer_ids={test_part_manufacturer.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "category_ids" in data
        assert "part_manufacturer_ids" in data

    def test_check_product_url_exists_empty(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test check-url with no or empty product_url returns null."""
        response = client.get(f"{settings.API_STR}/parts/check-url")
        assert response.status_code == 200
        data = response.json()
        assert data["existing_part_id"] is None

        response = client.get(f"{settings.API_STR}/parts/check-url?product_url=")
        assert response.status_code == 200
        data = response.json()
        assert data["existing_part_id"] is None

    def test_check_product_url_exists_nonexistent(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test check-url with non-existent URL returns null."""
        response = client.get(
            f"{settings.API_STR}/parts/check-url" "?product_url=https://example.com/nonexistent/product"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["existing_part_id"] is None

    def test_count_parts(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """Test counting total global parts (public endpoint)."""
        response = client.get(f"{settings.API_STR}/parts/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


class TestPartListingsAuth:
    """`POST /api/parts/{part_id}/listings` was public until it was brought in
    line with every other mutating route and put behind `get_current_user`."""

    def _make_retailer(self) -> Retailer:
        retailer = Retailer(
            name=get_unique_name(f"retailer_{uuid.uuid4().hex[:8]}"),
            domain=f"{uuid.uuid4().hex[:8]}.example.com",
            base_url="https://retailer.example.com",
            is_active=True,
        )
        return save_catalog(retailer)

    def _make_part(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> dict[str, Any]:
        headers = get_auth_token_and_headers(client, test_user.username)
        part_data = {
            "name": get_unique_name(f"listing_part_{uuid.uuid4().hex[:8]}"),
            "description": "Part used for listing auth coverage",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200, response.text
        created: dict[str, Any] = response.json()
        return created

    def test_create_listing_anonymous_returns_401(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """No Authorization header -> 401, same as every other authed route."""
        part = self._make_part(client, test_user, test_category, test_part_manufacturer)
        retailer = self._make_retailer()

        response = client.post(
            f"{settings.API_STR}/parts/{part['id']}/listings",
            json={
                "part_id": part["id"],
                "retailer_id": str(retailer.id),
                "product_url": "https://retailer.example.com/p/anon",
                "price_cents": 4999,
            },
        )
        assert response.status_code == 401, response.text

    def test_create_listing_authenticated_succeeds(
        self, client: TestClient, test_user: User, test_category: Category, test_part_manufacturer: PartManufacturer
    ) -> None:
        """A valid Bearer token still gets the unchanged 200 response shape."""
        part = self._make_part(client, test_user, test_category, test_part_manufacturer)
        retailer = self._make_retailer()
        headers = get_auth_token_and_headers(client, test_user.username)

        response = client.post(
            f"{settings.API_STR}/parts/{part['id']}/listings",
            json={
                "part_id": part["id"],
                "retailer_id": str(retailer.id),
                "product_url": "https://retailer.example.com/p/authed",
                "price_cents": 4999,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["part_id"] == part["id"]
        assert data["retailer_id"] == str(retailer.id)
        assert data["last_known_price_cents"] == 4999
        # Response shape is unchanged: the retailer is still embedded.
        assert data["retailer"]["id"] == str(retailer.id)

    def test_create_listing_still_404s_for_unknown_part_when_authenticated(
        self, client: TestClient, test_user: User
    ) -> None:
        """Auth runs before the handler, but a valid token still reaches the 404 path."""
        retailer = self._make_retailer()
        headers = get_auth_token_and_headers(client, test_user.username)

        response = client.post(
            f"{settings.API_STR}/parts/{INVALID_UUID_STR}/listings",
            json={
                "part_id": INVALID_UUID_STR,
                "retailer_id": str(retailer.id),
                "product_url": "https://retailer.example.com/p/missing",
            },
            headers=headers,
        )
        assert response.status_code == 404, response.text
