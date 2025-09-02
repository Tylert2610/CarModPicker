import os
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


class TestBuildListReports:
    """Test cases for build list reports endpoints."""

    def test_create_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test successfully creating a report for a build list."""
        # Create a second user to own the build list
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        build_list_owner = DBUser(
            username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["user_id"] == test_user.id
        assert data["reason"] == "inappropriate_content"
        assert data["description"] == "This build list contains inappropriate content"
        assert data["status"] == "pending"

    def test_create_report_unauthorized(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test creating a report without authentication."""
        # Try to create a report without authentication
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/1/report", json=report_data
        )
        assert response.status_code == 401

    def test_create_report_build_list_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test creating a report for a build list that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to report non-existent build list
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/99999/report", json=report_data
        )
        assert response.status_code == 404

    def test_create_report_own_build_list(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that users cannot report their own build lists."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list owned by the test user
        build_list_data = {
            "name": get_unique_name("My Build List"),
            "description": "My own build list",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Try to report own build list
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 400
        assert "cannot report your own build list" in response.json()["detail"]

    def test_create_report_already_reported(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that users cannot report the same build list twice."""
        # Create a second user to own the build list
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        build_list_owner = DBUser(
            username=f"build_list_owner2_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner2_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Another Test Build List"),
            "description": "Another test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create first report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Try to create second report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 400
        assert "already reported" in response.json()["detail"]

    def test_list_reports_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that listing reports requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to list reports
        response = client.get(f"{settings.API_STR}/build-list-reports/")
        assert response.status_code == 403

    def test_list_reports_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully listing reports as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # List reports
        response = client.get(f"{settings.API_STR}/build-list-reports/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_reports_with_filters(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test listing reports with status and reason filters."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # List reports with status filter
        response = client.get(f"{settings.API_STR}/build-list-reports/?status=pending")
        assert response.status_code == 200

        # List reports with reason filter
        response = client.get(
            f"{settings.API_STR}/build-list-reports/?reason=inappropriate_content"
        )
        assert response.status_code == 200

    def test_get_my_reports_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting user's own reports."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get my reports
        response = client.get(f"{settings.API_STR}/build-list-reports/my-reports")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_report_by_id_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting a specific report by ID."""
        # Create a second user to own the build list
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        build_list_owner = DBUser(
            username=f"build_list_owner3_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner3_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Get Report Test Build List"),
            "description": "A build list for testing report retrieval",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the report by ID
        response = client.get(f"{settings.API_STR}/build-list-reports/{report['id']}")
        assert response.status_code == 200
        retrieved_report = response.json()
        assert retrieved_report["id"] == report["id"]
        assert retrieved_report["build_list_id"] == build_list["id"]

    def test_get_report_by_id_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get non-existent report
        response = client.get(f"{settings.API_STR}/build-list-reports/99999")
        assert response.status_code == 404

    def test_get_report_by_id_unauthorized(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that users cannot access other users' reports."""
        # Create a second user
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        other_user = DBUser(
            username=f"other_user_{os.getpid()}_{id(db_session)}",
            email=f"other_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # Create a build list owner
        build_list_owner = DBUser(
            username=f"build_list_owner4_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner4_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Unauthorized Report Test Build List"),
            "description": "A build list for testing unauthorized report access",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Login as other user and create a report
        login_data = {"username": other_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inaccurate",
            "description": "This build list information is inaccurate",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as test user and try to access other user's report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-reports/{report['id']}")
        assert response.status_code == 404

    def test_get_reports_with_details_admin_only(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test that getting reports with details requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get reports with details
        response = client.get(f"{settings.API_STR}/build-list-reports/reports")
        assert response.status_code == 403

    def test_get_reports_with_details_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully getting reports with details as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get reports with details
        response = client.get(f"{settings.API_STR}/build-list-reports/reports")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_specific_report_with_details_admin_only(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test that getting a specific report with details requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get report with details
        response = client.get(f"{settings.API_STR}/build-list-reports/reports/1")
        assert response.status_code == 403

    def test_update_report_status_admin_only(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test that updating report status requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to update report status
        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(
            f"{settings.API_STR}/build-list-reports/1", json=update_data
        )
        assert response.status_code == 403

    def test_update_report_status_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully updating report status as admin."""
        # Create a build list owner
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        build_list_owner = DBUser(
            username=f"build_list_owner5_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner5_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Update Status Test Build List"),
            "description": "A build list for testing status updates",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create a test user to make the report
        test_user = DBUser(
            username=f"test_user_{os.getpid()}_{id(db_session)}",
            email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "duplicate",
            "description": "This build list is a duplicate",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and update report status
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(
            f"{settings.API_STR}/build-list-reports/{report['id']}", json=update_data
        )
        assert response.status_code == 200
        updated_report = response.json()
        assert updated_report["status"] == "resolved"
        assert updated_report["admin_notes"] == "Issue resolved"

    def test_delete_report_admin_only(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test that deleting reports requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to delete report
        response = client.delete(f"{settings.API_STR}/build-list-reports/1")
        assert response.status_code == 403

    def test_delete_report_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully deleting a report as admin."""
        # Create a build list owner
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        build_list_owner = DBUser(
            username=f"build_list_owner6_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner6_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Delete Report Test Build List"),
            "description": "A build list for testing report deletion",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create a test user to make the report
        test_user = DBUser(
            username=f"test_user2_{os.getpid()}_{id(db_session)}",
            email=f"test_user2_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "other",
            "description": "Other issue with this build list",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-reports/{build_list['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and delete report
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        response = client.delete(
            f"{settings.API_STR}/build-list-reports/{report['id']}"
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Report deleted successfully"

    def test_get_pending_reports_count_admin_only(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test that getting pending reports count requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get pending reports count
        response = client.get(
            f"{settings.API_STR}/build-list-reports/reports/pending/count"
        )
        assert response.status_code == 403

    def test_get_pending_reports_count_success(
        self, client: TestClient, test_admin_user: User
    ) -> None:
        """Test successfully getting pending reports count as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get pending reports count
        response = client.get(
            f"{settings.API_STR}/build-list-reports/reports/pending/count"
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_count" in data
        assert isinstance(data["pending_count"], int)
