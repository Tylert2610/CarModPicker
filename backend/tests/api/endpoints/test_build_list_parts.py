import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestBuildListParts:
    """Test cases for build list parts endpoints."""

    def test_add_part_to_build_list_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test successfully adding a part to a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["global_part_id"] == global_part["id"]
        assert data["notes"] == "Test notes"
        assert "id" in data
        assert "added_at" in data

    def test_add_part_to_build_list_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test adding a part to a build list without authentication."""
        # Create a car, build list, and global part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to add part without authentication
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 401

    def test_add_part_to_build_list_not_found(
        self, client: TestClient, test_user, test_category
    ):
        """Test adding a part to a non-existent build list."""
        # Login and create a global part
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
        global_part = response.json()

        # Try to add to non-existent build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/99999/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_unauthorized_build_list(
        self, client: TestClient, test_user, test_category
    ):
        """Test adding a part to a build list owned by another user."""
        # Create a car, build list, and global part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to add part to another user's build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 401

    def test_add_part_to_build_list_global_part_not_found(
        self, client: TestClient, test_user, test_category
    ):
        """Test adding a non-existent global part to a build list."""
        # Login and create a build list
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Try to add non-existent global part
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/99999",
            json=build_list_part_data,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_duplicate(
        self, client: TestClient, test_user, test_category
    ):
        """Test adding the same global part to a build list twice."""
        # Login and create build list and global part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list first time
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200

        # Try to add the same part again
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 409

    def test_get_build_list_parts(self, client: TestClient, test_user, test_category):
        """Test getting all parts in a build list."""
        # Login and create build list and global parts
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create two global parts
        part1_data = {
            "name": get_unique_name("test_part_1"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part1_data)
        assert response.status_code == 200
        global_part1 = response.json()

        part2_data = {
            "name": get_unique_name("test_part_2"),
            "description": "Another test part description",
            "price": 8888,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part2_data)
        assert response.status_code == 200
        global_part2 = response.json()

        # Add both parts to build list
        build_list_part_data = {"notes": "Test notes 1"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part1['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200

        build_list_part_data = {"notes": "Test notes 2"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part2['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200

        # Get all parts in build list
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2

        # Verify both parts are present
        part_ids = [item["global_part_id"] for item in data]
        assert global_part1["id"] in part_ids
        assert global_part2["id"] in part_ids

    def test_get_build_list_parts_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting parts from a build list without authentication."""
        # Create build list as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to get parts without authentication
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts"
        )
        assert response.status_code == 401

    def test_get_build_list_part_by_id(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting a specific build list part by ID."""
        # Login and create build list and global part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Get all build list parts and find the specific one
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts"
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find the specific build list part we created
        found_part = None
        for part in data:
            if part["global_part_id"] == global_part["id"]:
                found_part = part
                break

        assert found_part is not None
        assert found_part["build_list_id"] == build_list["id"]
        assert found_part["global_part_id"] == global_part["id"]
        assert found_part["notes"] == "Test notes"

    def test_get_build_list_part_by_id_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting a build list part without authentication."""
        # Create build list part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to get build list parts without authentication
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts"
        )
        assert response.status_code == 401

    def test_update_build_list_part_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test successfully updating a build list part."""
        # Login and create build list and global part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Original notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Update the build list part
        update_data = {"notes": "Updated notes"}
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["notes"] == "Updated notes"

    def test_update_build_list_part_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test updating a build list part without proper authorization."""
        # Create build list part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Original notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to update build list part without authentication
        update_data = {"notes": "Updated notes"}
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=update_data,
        )
        assert response.status_code == 401

    def test_delete_build_list_part_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test successfully deleting a build list part."""
        # Login and create build list and global part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Delete the build list part
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}"
        )
        assert response.status_code == 200

        # Verify it's deleted by trying to get it
        response = client.get(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts"
        )
        assert response.status_code == 200

        data = response.json()
        # The part should no longer be in the list
        for part in data:
            assert part["global_part_id"] != global_part["id"]

    def test_delete_build_list_part_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test deleting a build list part without proper authorization."""
        # Create build list part as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {"notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to delete build list part without authentication
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}"
        )
        assert response.status_code == 401

    def test_create_and_add_part_with_invalid_price(
        self, client: TestClient, test_user, test_category
    ):
        """Test that creating a global part and adding it to build list with invalid price fails validation."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car first
        car_data = {"make": "Toyota", "model": "Camry", "year": 2020}
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a build list first
        build_list_data = {
            "name": "Test Build List for Invalid Price",
            "description": "A test build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        # Test with price too large for PostgreSQL integer
        part_data = {
            "name": "Test Part with Invalid Price",
            "description": "A test part with invalid price",
            "price": 2147483648,  # One more than max PostgreSQL integer
            "category_id": test_category.id,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_id}/create-and-add-part",
            json=part_data,
        )
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["loc"]

        # Test with negative price
        part_data["price"] = -1
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_id}/create-and-add-part",
            json=part_data,
        )
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "greater_than_equal"
        assert "price" in error_detail["loc"]

        # Test with extremely large price
        part_data["price"] = 999999999999999999
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_id}/create-and-add-part",
            json=part_data,
        )
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["loc"]
