import os
from typing import Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models.user import User
from app.api.models.category import Category
from tests.conftest import create_and_login_user


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestGlobalPartReports:
    """Test cases for global part reports endpoints."""

    def test_create_report_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test successfully creating a report for a global part."""
        # Create a second user to own the part
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        part_owner = DBUser(
            username=f"part_owner_{os.getpid()}_{id(db_session)}",
            email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(part_owner)
        db_session.commit()
        db_session.refresh(part_owner)

        # Login as part owner and create a part
        login_data = {"username": part_owner.username, "password": "testpassword"}
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

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a report without providing a description."""
        # Create a second user to own the part
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        part_owner = DBUser(
            username=f"part_owner_{os.getpid()}_{id(db_session)}",
            email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(part_owner)
        db_session.commit()
        db_session.refresh(part_owner)

        # Login as part owner and create a part
        login_data = {"username": part_owner.username, "password": "testpassword"}
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

        # Login as test user and try to create a report without description
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to create a report without description (this should work since description is optional)
        report_data = {"reason": "inappropriate_content"}
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

    def test_create_report_empty_description(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a report with an empty description."""
        # Create a second user to own the part
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        part_owner = DBUser(
            username=f"part_owner_{os.getpid()}_{id(db_session)}",
            email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(part_owner)
        db_session.commit()
        db_session.refresh(part_owner)

        # Login as part owner and create a part
        login_data = {"username": part_owner.username, "password": "testpassword"}
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

        # Login as test user and try to create a report with empty description
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to create a report with empty description (this should work since description is optional)
        report_data = {
            "reason": "inappropriate_content",
            "description": "",
        }
        response = client.post(
            f"{settings.API_STR}/global-part-reports/{global_part['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

    def test_create_report_duplicate(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a duplicate report for the same part by the same user."""
        # Create a second user to report the part
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        reporter_user = DBUser(
            username=f"reporter_user_{os.getpid()}_{id(db_session)}",
            email=f"reporter_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(reporter_user)
        db_session.commit()
        db_session.refresh(reporter_user)

        # Create a global part with the first user
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

        # Switch back to reporter user
        login_data = {"username": reporter_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test getting a report by ID."""
        # Create a second user to report the part
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        reporter_user = DBUser(
            username=f"reporter_user_{os.getpid()}_{id(db_session)}",
            email=f"reporter_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(reporter_user)
        db_session.commit()
        db_session.refresh(reporter_user)

        # Create a global part with the first user
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

        # Switch back to reporter user
        login_data = {"username": reporter_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
        assert data["user_id"] == reporter_user.id
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
        self,
        client: TestClient,
        test_admin_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test listing all reports (admin only)."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Switch to admin user to list reports
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # List reports
        response = client.get(f"{settings.API_STR}/global-part-reports/")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        report = data[0]
        assert report["global_part_id"] == global_part["id"]
        assert report["user_id"] == user_info["id"]
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
        self,
        client: TestClient,
        test_admin_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test listing reports with filters (admin only)."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Switch to admin user to list reports with filters
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # List reports with status filter
        response = client.get(f"{settings.API_STR}/global-part-reports/?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        for report in data:
            assert report["status"] == "pending"

    def test_update_report_status_success(
        self,
        client: TestClient,
        test_admin_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test updating a report status."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Switch to admin user to update report status
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
        self, client: TestClient, test_admin_user: User
    ) -> None:
        """Test updating a report that doesn't exist (admin only)."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test updating a report with an invalid status."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the first user
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
        self,
        client: TestClient,
        test_admin_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test deleting a report."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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

        # Switch to admin user to delete the report
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Delete the report
        response = client.delete(
            f"{settings.API_STR}/global-part-reports/{report['id']}"
        )
        assert response.status_code == 200

        # Verify the report was deleted
        response = client.get(f"{settings.API_STR}/global-part-reports/{report['id']}")
        assert response.status_code == 404

    def test_delete_report_not_found(
        self, client: TestClient, test_admin_user: User
    ) -> None:
        """Test deleting a report that doesn't exist."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
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
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a report with extra fields in the request."""
        # Create a second user to report the part
        user_info = create_and_login_user(client, "reporter_user")

        # Create a global part with the first user
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

        # Switch back to reporter user
        login_data = {"username": "reporter_user", "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

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
            content="invalid json",
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
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a report with a disabled user account."""
        # Disable the user and commit to database
        test_user.disabled = True
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the user is disabled
        assert response.status_code == 400

        # Since the user is disabled, they can't log in, so they can't create reports
        # The test demonstrates that disabled users cannot authenticate

    def test_create_report_with_unverified_email(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test creating a report with an unverified email user account."""
        # Set email as unverified and commit to database
        test_user.email_verified = False
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the email is not verified
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 401  # Should fail due to unverified email

        # The test demonstrates that unverified email users cannot access protected endpoints
