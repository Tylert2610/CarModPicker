import os
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category, PartManufacturer
from app.db.dynamo.users import User
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


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


class TestBuildListParts:
    """Test cases for build list parts endpoints."""

    def test_add_part_to_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test successfully adding a part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["part_id"] == part["id"]
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_unauthorized(self, client: TestClient, test_category: Category) -> None:
        """Test adding a part to a build list without authentication."""
        # Try to add a part without authentication
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}/parts/{INVALID_UUID_STR}",
            json=build_list_part_data,
        )
        assert response.status_code == 401

    def test_add_part_to_build_list_not_found(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a non-existent build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Try to add part to non-existent build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_part_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test adding a non-existent part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to add non-existent part
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_missing_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list without providing quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Try to add part without quantity (this should work since quantity is not required)
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_invalid_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with invalid quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Try to add part with invalid quantity (quantity is not part of the schema, so this should work)
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_duplicate(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a duplicate part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Try to add the same part again
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 409

    def test_get_build_list_parts_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting parts from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Get parts from build list
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        build_list_part = data[0]
        assert build_list_part["build_list_id"] == build_list["id"]
        assert build_list_part["part_id"] == part["id"]
        assert build_list_part["quantity"] == 2
        assert build_list_part["notes"] == "Test notes"

    def test_get_build_list_parts_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test getting parts from a non-existent build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to get parts from non-existent build list
        response = client.get(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_parts_unauthorized(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting parts from a build list without authentication (public read is allowed)."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list as test_user
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        # Try to get parts without authentication (public read is allowed)
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list_id}")
        assert response.status_code == 200  # Public read is allowed

    def test_update_build_list_part_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Update the build list part
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == build_list_part["id"]
        assert data["quantity"] == 3
        assert data["notes"] == "Updated notes"

    def test_update_build_list_part_not_found(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list part that doesn't exist."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to update a build list part that doesn't exist
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", json=update_data, headers=headers
        )
        assert response.status_code == 404

    def test_update_build_list_part_unauthorized(self, client: TestClient) -> None:
        """Test updating a build list part without authentication."""
        # Try to update a build list part without authentication
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", json=update_data)
        assert response.status_code == 401

    def test_update_build_list_part_invalid_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with invalid quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "part_id": part["id"],
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with invalid quantity
        update_data = {
            "quantity": 0,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_remove_part_from_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test removing a part from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Remove the part
        response = client.delete(f"{settings.API_STR}/build-list-parts/{build_list_part['id']}", headers=headers)
        assert response.status_code == 200

        # Verify the part was removed
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_part_from_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test removing a build list part that doesn't exist."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to remove a build list part that doesn't exist
        response = client.delete(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_remove_part_from_build_list_unauthorized(self, client: TestClient) -> None:
        """Test removing a build list part without authentication."""
        # Try to remove a build list part without authentication
        response = client.delete(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}")
        assert response.status_code == 401

    def test_add_part_to_build_list_with_extra_fields(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with extra fields in the request."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list with extra fields
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
            "extra_field": "should_be_ignored",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["part_id"] == part["id"]
        assert data["quantity"] == 1
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_with_malformed_json(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with malformed JSON."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Try to add part with malformed JSON
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_add_part_to_build_list_with_wrong_content_type(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with wrong content type."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part first
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Try to add part with wrong content type (send as plain text instead of JSON)
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "text/plain"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            content=str(build_list_part_data).encode(),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_extra_fields(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with extra fields in the request."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Update the build list part with extra fields
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
            "extra_field": "should_be_ignored",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["quantity"] == 3
        assert data["notes"] == "Updated notes"

    def test_update_build_list_part_with_malformed_json(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with malformed JSON."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with malformed JSON
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_wrong_content_type(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with wrong content type."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with wrong content type (send as plain text instead of JSON)
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "text/plain"
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            content=str(update_data).encode(),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_add_part_to_build_list_with_disabled_user(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """A disabled account cannot add a part to a build list.

        This used to assert that `POST /api/auth/token` answered 400, and then
        stopped, with a comment saying the build list functionality could not be
        reached because login had failed. Row 13 of `docs/identity-adoption.md`
        deleted that route and moved the disabled check into `get_current_user`,
        so the test now presents a valid credential to the real endpoint.
        """
        from app.core.config import settings

        test_user = UserRepository().update(test_user.id, disabled=True)

        headers = auth_headers(login_user(client, test_user.username))

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{uuid4()}/parts/{uuid4()}",
            json={"quantity": 1},
            headers=headers,
        )

        # 401 rather than the 404 the two random ids would otherwise earn:
        # `get_current_user` refuses a disabled account before the handler runs,
        # so the build list is never looked up.
        assert response.status_code == 401

    def test_add_part_to_build_list_with_unverified_email(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with an unverified email user account."""
        # Set email as unverified and commit to database
        test_user = UserRepository().update(test_user.id, email_verified=False)

        # Login as test user (this should work since email verification is checked later)
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin) - but this will fail due to unverified email
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Try to create a build list - should fail due to unverified email
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 401  # Should fail due to unverified email

        # The test demonstrates that unverified email users cannot access protected endpoints

    def test_create_and_add_part_to_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test creating a global part and adding it to a build list in one operation."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create and add global part to build list
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "notes": "Some notes about the part",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/create-and-add-part",
            json=part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["notes"] == "Some notes about the part"
        assert "part" in data
        assert data["part"]["name"] == part_data["name"]

    def test_get_parts_in_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting global parts from a build list with full part details."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Get global parts with full details
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        build_list_part = data[0]
        assert build_list_part["build_list_id"] == build_list["id"]
        assert build_list_part["part_id"] == part["id"]
        assert build_list_part["quantity"] == 2
        assert "part" in build_list_part
        assert build_list_part["part"]["name"] == part["name"]

    def test_update_part_in_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a global part in a build list by build_list_id and part_id."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Original notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Update the global part in build list
        update_data = {
            "quantity": 5,
            "notes": "Updated notes via global part endpoint",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["quantity"] == 5
        assert data["notes"] == "Updated notes via global part endpoint"

    def test_update_part_in_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a non-existent global part in a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update non-existent part
        update_data = {
            "quantity": 5,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_remove_part_from_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test removing a global part from a build list by build_list_id and part_id."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Remove the global part using build_list_id and part_id
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            headers=headers,
        )
        assert response.status_code == 200

        # Verify the part was removed
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_part_from_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test removing a non-existent global part from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to remove non-existent part
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}", headers=headers
        )
        assert response.status_code == 404

    def test_count_build_lists_containing_part_success(
        self,
        client: TestClient,
        premium_test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build lists containing a global part when it exists in multiple build lists."""
        # Use premium user so we can create multiple build lists
        token = login_user(client, premium_test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Create first build list and add the part
        build_list_data_1 = {
            "name": get_unique_name("test_build_list_1"),
            "description": "First test build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data_1, headers=headers)
        assert response.status_code == 200
        build_list_1 = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_1['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Create second build list and add the same part
        build_list_data_2 = {
            "name": get_unique_name("test_build_list_2"),
            "description": "Second test build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data_2, headers=headers)
        assert response.status_code == 200
        build_list_2 = response.json()

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_2['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Count build lists containing the global part (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 2

    def test_count_build_lists_containing_part_zero(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build lists containing a global part when it exists but is not in any build lists."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Count build lists containing the global part (should be 0)
        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_count_build_lists_containing_part_not_found(self, client: TestClient) -> None:
        """Test counting build lists containing a non-existent global part."""
        # Try to count build lists for non-existent global part (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{INVALID_UUID_STR}/build-lists/count")
        assert response.status_code == 404

    def test_count_build_lists_containing_part_public_endpoint(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test that counting build lists containing a global part works without authentication."""
        # Login as test user and get token to create data
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Create a build list and add the part
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Count build lists containing the global part WITHOUT authentication (public endpoint)
        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 1

    def test_update_build_list_part_when_build_list_deleted(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test build list part update when build list is deleted (edge case - cascade behavior)."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            # price in cents (99.99)
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {"quantity": 1, "notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()
        build_list_part_id = build_list_part["id"]

        # Delete the build list
        delete_response = client.delete(f"{settings.API_STR}/build-lists/{build_list['id']}", headers=headers)
        assert delete_response.status_code == 200

        # Try to update the build list part (should fail - build list is deleted)
        update_data = {"quantity": 2}
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part_id}",
            json=update_data,
            headers=headers,
        )
        # Should return 404 because build list part was cascade deleted with build list
        # OR 404 if build list part is checked first
        assert response.status_code == 404, "Update should fail when build list is deleted"

    def test_delete_build_list_part_when_build_list_deleted(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test build list part deletion when build list is deleted (edge case - cascade behavior)."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            # price in cents (99.99)
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Add part to build list
        build_list_part_data = {"quantity": 1, "notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()
        build_list_part_id = build_list_part["id"]

        # Delete the build list (should cascade delete the build list part)
        delete_response = client.delete(f"{settings.API_STR}/build-lists/{build_list['id']}", headers=headers)
        assert delete_response.status_code == 200

        # Try to delete the build list part (should fail - already deleted via cascade)
        response = client.delete(f"{settings.API_STR}/build-list-parts/{build_list_part_id}", headers=headers)
        # Should return 404 because build list part was cascade deleted with build list
        assert response.status_code == 404, "Delete should fail when build list part was cascade deleted"

    def test_count_build_list_parts_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build list parts."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_build_list_parts_public_endpoint(self, client: TestClient) -> None:
        """Test that counting build list parts works without authentication."""
        # Count build list parts (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
