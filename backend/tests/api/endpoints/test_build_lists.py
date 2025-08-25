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


class TestBuildLists:
    """Test cases for build lists endpoints."""

    def test_create_build_list_success(self, client: TestClient, test_user):
        """Test successful creation of a build list."""
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]
        assert data["car_id"] == car["id"]
        assert data["user_id"] == test_user.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_build_list_unauthorized(self, client: TestClient):
        """Test creating a build list without authentication."""
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": 1,
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 401

    def test_create_build_list_car_not_found(self, client: TestClient, test_user):
        """Test creating a build list with non-existent car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": 99999,  # Non-existent car ID
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 404

    def test_create_build_list_unauthorized_car(self, client: TestClient, test_user):
        """Test creating a build list for a car owned by another user."""
        # Create a car as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to create build list for another user's car
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 401

    def test_get_build_list_by_id(self, client: TestClient, test_user):
        """Test retrieving a specific build list by ID."""
        # Login and create a build list
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Get the build list by ID
        response = client.get(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_build_list["id"]
        assert data["name"] == created_build_list["name"]

    def test_get_build_list_not_found(self, client: TestClient, test_user):
        """Test retrieving a non-existent build list."""
        # Login first since the endpoint requires authentication
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get a non-existent build list
        response = client.get(f"{settings.API_STR}/build-lists/99999")
        assert response.status_code == 404

    def test_get_build_list_unauthorized(self, client: TestClient, test_user):
        """Test retrieving a build list owned by another user."""
        # Create a build list as test_user
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to get another user's build list
        response = client.get(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}"
        )
        assert response.status_code == 401

    def test_get_user_build_lists(self, client: TestClient, test_user):
        """Test retrieving build lists for the current user."""
        # Login and create a build list
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200

        # Get user's build lists
        response = client.get(f"{settings.API_STR}/build-lists/user/me")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_user_build_lists_unauthorized(self, client: TestClient):
        """Test retrieving build lists without authentication."""
        response = client.get(f"{settings.API_STR}/build-lists/user/me")
        assert response.status_code == 401

    def test_update_build_list_success(self, client: TestClient, test_user):
        """Test successful update of a build list."""
        # Login and create a build list
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Update the build list
        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}",
            json=update_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_build_list_unauthorized(self, client: TestClient, test_user):
        """Test updating a build list without proper authorization."""
        # Create a build list as test_user
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to update without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}",
            json=update_data,
        )
        assert response.status_code == 401

    def test_delete_build_list_success(self, client: TestClient, test_user):
        """Test successful deletion of a build list."""
        # Login and create a build list
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Delete the build list
        response = client.delete(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}"
        )
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}"
        )
        assert response.status_code == 404

    def test_delete_build_list_unauthorized(self, client: TestClient, test_user):
        """Test deleting a build list without proper authorization."""
        # Create a build list as test_user
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        created_build_list = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to delete without authentication
        response = client.delete(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}"
        )
        assert response.status_code == 401

    def test_get_build_lists_by_car(self, client: TestClient, test_user):
        """Test retrieving build lists for a specific car."""
        # Login and create a build list
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200

        # Get build lists for the car
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for build_list in data:
            assert build_list["car_id"] == car["id"]

    def test_get_build_lists_by_car_unauthorized(self, client: TestClient, test_user):
        """Test retrieving build lists for a car owned by another user."""
        # Create a car as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to get build lists for another user's car
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}")
        assert response.status_code == 401
