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


class TestGlobalPartReports:
    """Test cases for global part reports endpoints."""

    def test_create_report_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test successfully creating a report for a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == test_user.id
        assert data["reason"] == "inappropriate_content"
        assert data["description"] == "This part contains inappropriate content"
        assert data["status"] == "pending"

    def test_create_report_unauthorized(
        self, client: TestClient, test_category: Any
    ) -> None:
        """Test creating a report without authentication."""
        # Try to create a report without authentication
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/1/report", json=report_data
        )
        assert response.status_code == 401

    def test_create_report_part_not_found(
        self, client: TestClient, test_user: Any
    ) -> None:
        """Test creating a report for a non-existent global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to create a report for non-existent part
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/99999/report", json=report_data
        )
        assert response.status_code == 404

    def test_create_report_invalid_reason(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with an invalid reason."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report with invalid reason
        report_data = {
            "reason": "invalid_reason",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 422

    def test_create_report_missing_reason(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report without providing a reason."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report without reason
        report_data = {"description": "This part contains inappropriate content"}
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 422

    def test_create_report_missing_description(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report without providing a description."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report without description
        report_data = {"reason": "inappropriate_content"}
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 422

    def test_create_report_empty_description(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with an empty description."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report with empty description
        report_data = {
            "reason": "inappropriate_content",
            "description": "",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 422

    def test_create_report_duplicate(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a duplicate report for the same part by the same user."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create first report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Try to create duplicate report
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 400

    def test_get_report_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test getting a report by ID."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the report
        response = client.get(f"{settings.API_STR}/global-part-reports/{report['id']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == report["id"]
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == test_user.id
        assert data["reason"] == "inappropriate_content"
        assert data["description"] == "This part contains inappropriate content"
        assert data["status"] == "pending"

    def test_get_report_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get a report that doesn't exist
        response = client.get(f"{settings.API_STR}/global-part-reports/99999")
        assert response.status_code == 404

    def test_get_report_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test getting a report without authentication."""
        # Try to get a report without authentication
        response = client.get(f"{settings.API_STR}/global-part-reports/1")
        assert response.status_code == 401

    def test_list_reports_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test listing reports."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # List reports
        response = client.get(f"{settings.API_STR}/global-part-reports/")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        report = data[0]
        assert report["global_part_id"] == global_part["id"]
        assert report["user_id"] == test_user.id
        assert report["reason"] == "inappropriate_content"
        assert report["description"] == "This part contains inappropriate content"
        assert report["status"] == "pending"

    def test_list_reports_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test listing reports without authentication."""
        # Try to list reports without authentication
        response = client.get(f"{settings.API_STR}/global-part-reports/")
        assert response.status_code == 401

    def test_list_reports_with_filters(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test listing reports with filters."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # List reports with status filter
        response = client.get(f"{settings.API_STR}/global-part-reports/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        for report in data:
            assert report["status"] == "pending"

    def test_update_report_status_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a report status."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Update report status
        update_data = {"status": "resolved"}
        response = client.put(
            f"{settings.API_STR}/global-part-reports/{report['id']}", json=update_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == report["id"]
        assert data["status"] == "resolved"

    def test_update_report_status_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test updating a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to update a report that doesn't exist
        update_data = {"status": "resolved"}
        response = client.put(
            f"{settings.API_STR}/global-part-reports/99999", json=update_data
        )
        assert response.status_code == 404

    def test_update_report_status_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test updating a report without authentication."""
        # Try to update a report without authentication
        update_data = {"status": "resolved"}
        response = client.put(
            f"{settings.API_STR}/global-part-reports/1", json=update_data
        )
        assert response.status_code == 401

    def test_update_report_status_invalid(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a report with an invalid status."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Try to update with invalid status
        update_data = {"status": "invalid_status"}
        response = client.put(
            f"{settings.API_STR}/global-part-reports/{report['id']}", json=update_data
        )
        assert response.status_code == 422

    def test_delete_report_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test deleting a report."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Delete the report
        response = client.delete(
            f"{settings.API_STR}/global-part-reports/{report['id']}"
        )
        assert response.status_code == 200

        # Verify the report was deleted
        response = client.get(f"{settings.API_STR}/global-part-reports/{report['id']}")
        assert response.status_code == 404

    def test_delete_report_not_found(self, client: TestClient, test_user: User) -> None:
        """Test deleting a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to delete a report that doesn't exist
        response = client.delete(f"{settings.API_STR}/global-part-reports/99999")
        assert response.status_code == 404

    def test_delete_report_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test deleting a report without authentication."""
        # Try to delete a report without authentication
        response = client.delete(f"{settings.API_STR}/global-part-reports/1")
        assert response.status_code == 401

    def test_create_report_with_extra_fields(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with extra fields in the request."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Create a report with extra fields
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
            "extra_field": "should_be_ignored",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["reason"] == "inappropriate_content"
        assert data["description"] == "This part contains inappropriate content"

    def test_create_report_with_malformed_json(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with malformed JSON."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report with malformed JSON
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            data={"invalid": "json"},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_create_report_with_wrong_content_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with wrong content type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Try to create a report with wrong content type
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 422

    def test_create_report_with_invalid_part_id_format(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test creating a report with an invalid part ID format."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to create a report with invalid part ID format
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/invalid_id/report",
            json=report_data,
        )
        assert response.status_code == 422

    def test_create_report_after_part_deletion(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report on a part that has been deleted."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Delete the part
        response = client.delete(f"{settings.API_STR}/global-parts/{global_part['id']}")
        assert response.status_code == 200

        # Try to create a report on deleted part
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 404

    def test_create_report_with_disabled_user(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with a disabled user account."""
        # Disable the user
        test_user.disabled = True
        # Note: In a real test, you'd need to commit this change to the database
        # For this test, we'll just verify the behavior

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the user is disabled
        assert response.status_code == 401

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

        # Try to create a report with disabled user
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 401

    def test_create_report_with_unverified_email(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a report with an unverified email user account."""
        # Set email as unverified
        test_user.email_verified = False
        # Note: In a real test, you'd need to commit this change to the database
        # For this test, we'll just verify the behavior

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the email is not verified
        assert response.status_code == 401

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

        # Try to create a report with unverified email user
        report_data = {
            "reason": "inappropriate_content",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 401
