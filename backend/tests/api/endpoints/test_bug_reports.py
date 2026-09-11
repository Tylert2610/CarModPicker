"""Tests for bug reports endpoints."""

import os
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User, UserRepository
from tests.conftest import auth_headers, login_user


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    from app.db.dynamo.users import User as DBUser

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


class TestBugReports:
    """Test cases for bug reports endpoints."""

    def test_create_bug_report_authenticated_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test successfully creating a bug report as an authenticated user."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Create a bug report
        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
            "steps_to_reproduce": "1. Go to page\n2. Click button\n3. See error",
            "expected_behavior": "Should work",
            "actual_behavior": "Doesn't work",
            "browser_info": "Chrome 120",
            "device_info": "Windows 11",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Test Bug Report"
        assert data["description"] == "This is a test bug report"
        assert data["user_id"] == str(test_user.id)
        assert data["status"] == "pending"
        assert data["priority"] == "medium"
        assert data["steps_to_reproduce"] == "1. Go to page\n2. Click button\n3. See error"
        assert data["expected_behavior"] == "Should work"
        assert data["actual_behavior"] == "Doesn't work"
        assert data["browser_info"] == "Chrome 120"
        assert data["device_info"] == "Windows 11"

    def test_create_bug_report_anonymous_success(
        self,
        client: TestClient,
        db_session: Any,
    ) -> None:
        """Test successfully creating a bug report as an anonymous user."""
        # Create a bug report without authentication
        bug_report_data = {
            "title": "Anonymous Bug Report",
            "description": "This is an anonymous bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Anonymous Bug Report"
        assert data["description"] == "This is an anonymous bug report"
        assert data["user_id"] is None
        assert data["status"] == "pending"
        assert data["priority"] == "medium"

    def test_create_bug_report_missing_title(
        self,
        client: TestClient,
    ) -> None:
        """Test creating a bug report without a title."""
        bug_report_data = {
            "description": "This bug report has no title",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
        )
        assert response.status_code == 422  # Validation error

    def test_create_bug_report_missing_description(
        self,
        client: TestClient,
    ) -> None:
        """Test creating a bug report without a description."""
        bug_report_data = {
            "title": "Bug Report Without Description",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
        )
        assert response.status_code == 422  # Validation error

    def test_get_bug_report_authenticated_user_not_authorized(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test that regular authenticated users cannot access bug reports (admin only)."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Create a bug report
        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Try to get the bug report as regular user (should fail - admin only)
        response = client.get(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            headers=headers,
        )
        assert response.status_code == 403  # Forbidden - not an admin

    def test_get_bug_report_anonymous_not_authorized(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test that anonymous users cannot access bug reports (admin only)."""
        # Login as test user and create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Try to get the bug report without authentication
        response = client.get(f"{settings.API_STR}/bug-reports/{bug_report_id}")
        assert response.status_code == 401  # Unauthorized - requires authentication

    def test_get_bug_report_admin_access(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test that admins can access any bug report."""
        # Login as test user and create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Login as admin and get the bug report
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        response = client.get(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == bug_report_id
        assert data["reporter_username"] == test_user.username

    def test_list_bug_reports_admin_only(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test that only admins can list bug reports."""
        # Try to list bug reports as regular user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        response = client.get(
            f"{settings.API_STR}/bug-reports/admin/list",
            headers=headers,
        )
        assert response.status_code == 403  # Forbidden

        # Login as admin and list bug reports
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        response = client.get(
            f"{settings.API_STR}/bug-reports/admin/list",
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_list_bug_reports_with_filters(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test listing bug reports with status and priority filters."""
        # Create bug reports with different statuses
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Create multiple bug reports
        for i in range(3):
            bug_report_data = {
                "title": f"Test Bug Report {i}",
                "description": f"This is test bug report {i}",
            }
            client.post(
                f"{settings.API_STR}/bug-reports/",
                json=bug_report_data,
                headers=headers,
            )

        # Login as admin and filter by status
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        response = client.get(
            f"{settings.API_STR}/bug-reports/admin/list?status=pending",
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert all(report["status"] == "pending" for report in data)

    def test_list_bug_reports_with_details(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test listing bug reports with details."""
        # Create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Login as admin and get reports with details
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        response = client.get(
            f"{settings.API_STR}/bug-reports/admin/list-with-details",
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

        # Check that details are included
        report = next((r for r in data["data"] if r["title"] == "Test Bug Report"), None)
        assert report is not None
        assert report["reporter_username"] == test_user.username

    def test_update_bug_report_admin(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test updating a bug report as an admin."""
        # Create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Login as admin and update the bug report
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        update_data = {
            "status": "in_progress",
            "priority": "high",
            "admin_notes": "Working on this bug",
        }
        response = client.put(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            json=update_data,
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"
        assert data["admin_notes"] == "Working on this bug"

    def test_update_bug_report_resolved_sets_resolved_at(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test that updating a bug report to resolved sets resolved_at."""
        # Create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Login as admin and resolve the bug report
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        update_data = {
            "status": "resolved",
            "admin_notes": "Fixed this bug",
        }
        response = client.put(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            json=update_data,
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None

    def test_delete_bug_report_admin(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test deleting a bug report as an admin."""
        # Create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200
        bug_report_id = response.json()["id"]

        # Login as admin and delete the bug report
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = auth_headers(admin_token)

        response = client.delete(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200

        # Verify bug report is deleted
        response = client.get(
            f"{settings.API_STR}/bug-reports/{bug_report_id}",
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_count_bug_reports(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test counting bug reports."""
        # Create a bug report
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        bug_report_data = {
            "title": "Test Bug Report",
            "description": "This is a test bug report",
        }
        response = client.post(
            f"{settings.API_STR}/bug-reports/",
            json=bug_report_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Count bug reports (public endpoint)
        response = client.get(f"{settings.API_STR}/bug-reports/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 1
