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


class TestGlobalPartReports:
    """Test cases for global part reports endpoints."""

    def test_create_report_success(self, client: TestClient, test_user, test_category):
        """Test successfully creating a report for a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part (this will be owned by test_user)
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200
        new_user_response = response.json()

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["reason"] == "inappropriate"
        assert data["description"] == "This part contains inappropriate content"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_report_unauthorized(self, client: TestClient, test_category):
        """Test creating a report without authentication."""
        # Try to create report without authentication
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/1/report", json=report_data
        )
        assert response.status_code == 401

    def test_create_report_part_not_found(self, client: TestClient, test_user):
        """Test creating a report for a non-existent global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to report non-existent part
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/99999/report", json=report_data
        )
        assert response.status_code == 404

    def test_create_duplicate_report(
        self, client: TestClient, test_user, test_category
    ):
        """Test creating a duplicate report from the same user."""
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create first report
        report_data = {
            "reason": "inappropriate",
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

    def test_report_own_part(self, client: TestClient, test_user, test_category):
        """Test reporting a part created by the same user."""
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

        # Report own part (should be blocked)
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 400

    def test_get_user_reports(self, client: TestClient, test_user, test_category):
        """Test getting reports created by the current user."""
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200
        new_user_response = response.json()

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Get user's reports
        response = client.get(f"{settings.API_STR}/global-part-reports/my-reports")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for report in data:
            assert report["user_id"] == new_user_response["id"]

    def test_get_user_reports_unauthorized(self, client: TestClient):
        """Test getting user reports without authentication."""
        response = client.get(f"{settings.API_STR}/global-part-reports/my-reports")
        assert response.status_code == 401

    def test_get_report_by_id(self, client: TestClient, test_user, test_category):
        """Test getting a specific report by ID."""
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200
        new_user_response = response.json()

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the specific report
        response = client.get(f"{settings.API_STR}/global-part-reports/{report['id']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == report["id"]
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == new_user_response["id"]
        assert data["reason"] == "inappropriate"

    def test_get_report_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting a report without authentication."""
        # Create a report as test_user
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to get report without authentication
        response = client.get(f"{settings.API_STR}/global-part-reports/{report['id']}")
        assert response.status_code == 401

    def test_get_reports_by_status(
        self, client: TestClient, test_user, test_category, test_admin_user
    ):
        """Test getting reports filtered by status."""
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Login as admin to get reports by status
        client.cookies.clear()

        # Login as the test admin user
        admin_login_data = {
            "username": test_admin_user.username,
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/auth/token", data=admin_login_data)
        assert response.status_code == 200

        # Get reports by status
        response = client.get(f"{settings.API_STR}/global-part-reports/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        for report in data:
            assert report["status"] == "pending"

    def test_get_all_reports_admin(
        self, client: TestClient, test_admin_user, test_category
    ):
        """Test getting all reports as an admin user."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Login as admin to get all reports
        client.cookies.clear()
        admin_login_data = {
            "username": test_admin_user.username,
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/auth/token", data=admin_login_data)
        assert response.status_code == 200

        # Get all reports as admin
        response = client.get(f"{settings.API_STR}/global-part-reports/")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_all_reports_unauthorized(self, client: TestClient):
        """Test getting all reports without admin privileges."""
        response = client.get(f"{settings.API_STR}/global-part-reports/")
        assert response.status_code == 401

    def test_update_report_status_admin(
        self, client: TestClient, test_admin_user, test_category
    ):
        """Test updating report status as an admin user."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin to update report status
        client.cookies.clear()
        admin_login_data = {
            "username": test_admin_user.username,
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/auth/token", data=admin_login_data)
        assert response.status_code == 200

        # Update report status as admin
        update_data = {
            "status": "resolved",
            "admin_notes": "Issue has been resolved",
        }
        response = client.put(
            f"{settings.API_STR}/global-part-reports/{report['id']}/status",
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "resolved"
        assert data["admin_notes"] == "Issue has been resolved"

    def test_update_report_status_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test updating report status without admin privileges."""
        # Create a report as regular user
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Try to update report status without admin privileges
        update_data = {
            "status": "resolved",
            "admin_notes": "Issue has been resolved",
        }
        response = client.put(
            f"{settings.API_STR}/global-part-reports/{report['id']}/status",
            json=update_data,
        )
        assert response.status_code == 403

    def test_invalid_report_reason(self, client: TestClient, test_user, test_category):
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

        # Try to create report with invalid reason
        report_data = {
            "reason": "invalid_reason",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 400

    def test_invalid_status_update(
        self, client: TestClient, test_admin_user, test_category
    ):
        """Test updating report status with an invalid status."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Clear cookies to simulate a different user
        client.cookies.clear()

        # Create a new user to report the part
        new_user_data = {
            "username": get_unique_name("reporter_user"),
            "email": f"{get_unique_name('reporter_user')}@example.com",
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/users/", json=new_user_data)
        assert response.status_code == 200

        # Login as the new user
        login_data = {"username": new_user_data["username"], "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin to update report status
        client.cookies.clear()
        admin_login_data = {
            "username": test_admin_user.username,
            "password": "testpassword",
        }
        response = client.post(f"{settings.API_STR}/auth/token", data=admin_login_data)
        assert response.status_code == 200

        # Try to update report status with invalid status
        update_data = {
            "status": "invalid_status",
            "admin_notes": "Issue has been resolved",
        }
        response = client.put(
            f"{settings.API_STR}/global-part-reports/{report['id']}/status",
            json=update_data,
        )
        assert response.status_code == 400
