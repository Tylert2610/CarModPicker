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


class TestCarReports:
    """Test cases for car reports endpoints."""

    def test_create_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test successfully creating a report for a car."""
        # Create a second user to own the car
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        car_owner = DBUser(
            username=f"car_owner_{os.getpid()}_{id(db_session)}",
            email=f"car_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Honda"),
            "model": "Civic",
            "year": 2022,
            "trim": "Sport",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This car contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["car_id"] == car["id"]
        assert data["user_id"] == test_user.id
        assert data["reason"] == "inappropriate_content"
        assert data["description"] == "This car contains inappropriate content"
        assert data["status"] == "pending"

    def test_create_report_unauthorized(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test creating a report without authentication."""
        # Try to create a report without authentication
        report_data = {
            "reason": "inappropriate_content",
            "description": "This car contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/1/report", json=report_data
        )
        assert response.status_code == 401

    def test_create_report_car_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test creating a report for a car that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to report non-existent car
        report_data = {
            "reason": "inappropriate_content",
            "description": "This car contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/99999/report", json=report_data
        )
        assert response.status_code == 404

    def test_create_report_own_car(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that users cannot report their own cars."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car owned by the test user
        car_data = {
            "make": get_unique_name("Toyota"),
            "model": "Camry",
            "year": 2021,
            "trim": "SE",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Try to report own car
        report_data = {
            "reason": "inappropriate_content",
            "description": "This car contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report", json=report_data
        )
        assert response.status_code == 400
        assert "cannot report your own car" in response.json()["detail"]

    def test_create_report_already_reported(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that users cannot report the same car twice."""
        # Create a second user to own the car
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        car_owner = DBUser(
            username=f"car_owner2_{os.getpid()}_{id(db_session)}",
            email=f"car_owner2_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Ford"),
            "model": "Mustang",
            "year": 2023,
            "trim": "GT",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create first report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This car contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200

        # Try to create second report
        report_data = {
            "reason": "spam",
            "description": "This car is spam",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
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
        response = client.get(f"{settings.API_STR}/car-reports/")
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
        response = client.get(f"{settings.API_STR}/car-reports/")
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
        response = client.get(f"{settings.API_STR}/car-reports/?status=pending")
        assert response.status_code == 200

        # List reports with reason filter
        response = client.get(
            f"{settings.API_STR}/car-reports/?reason=inappropriate_content"
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
        response = client.get(f"{settings.API_STR}/car-reports/my-reports")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_report_by_id_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting a specific report by ID."""
        # Create a second user to own the car
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        car_owner = DBUser(
            username=f"car_owner3_{os.getpid()}_{id(db_session)}",
            email=f"car_owner3_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Chevrolet"),
            "model": "Camaro",
            "year": 2022,
            "trim": "SS",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This car is spam",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the report by ID
        response = client.get(f"{settings.API_STR}/car-reports/{report['id']}")
        assert response.status_code == 200
        retrieved_report = response.json()
        assert retrieved_report["id"] == report["id"]
        assert retrieved_report["car_id"] == car["id"]

    def test_get_report_by_id_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get non-existent report
        response = client.get(f"{settings.API_STR}/car-reports/99999")
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

        # Create a car owner
        car_owner = DBUser(
            username=f"car_owner4_{os.getpid()}_{id(db_session)}",
            email=f"car_owner4_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("BMW"),
            "model": "3 Series",
            "year": 2021,
            "trim": "330i",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Login as other user and create a report
        login_data = {"username": other_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a report
        report_data = {
            "reason": "inaccurate",
            "description": "This car information is inaccurate",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as test user and try to access other user's report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/car-reports/{report['id']}")
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
        response = client.get(f"{settings.API_STR}/car-reports/reports")
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
        response = client.get(f"{settings.API_STR}/car-reports/reports")
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
        response = client.get(f"{settings.API_STR}/car-reports/reports/1")
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
        response = client.put(f"{settings.API_STR}/car-reports/1", json=update_data)
        assert response.status_code == 403

    def test_update_report_status_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully updating report status as admin."""
        # Create a car owner
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        car_owner = DBUser(
            username=f"car_owner5_{os.getpid()}_{id(db_session)}",
            email=f"car_owner5_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Audi"),
            "model": "A4",
            "year": 2023,
            "trim": "Premium",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

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
            "description": "This car is a duplicate",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
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
            f"{settings.API_STR}/car-reports/{report['id']}", json=update_data
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
        response = client.delete(f"{settings.API_STR}/car-reports/1")
        assert response.status_code == 403

    def test_delete_report_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully deleting a report as admin."""
        # Create a car owner
        from app.api.models.user import User as DBUser
        from app.api.dependencies.auth import get_password_hash

        car_owner = DBUser(
            username=f"car_owner6_{os.getpid()}_{id(db_session)}",
            email=f"car_owner6_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(car_owner)
        db_session.commit()
        db_session.refresh(car_owner)

        # Login as car owner and create a car
        login_data = {"username": car_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Mercedes"),
            "model": "C-Class",
            "year": 2022,
            "trim": "AMG",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

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
            "description": "Other issue with this car",
        }
        response = client.post(
            f"{settings.API_STR}/car-reports/{car['id']}/report",
            json=report_data,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and delete report
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        response = client.delete(f"{settings.API_STR}/car-reports/{report['id']}")
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
        response = client.get(f"{settings.API_STR}/car-reports/reports/pending/count")
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
        response = client.get(f"{settings.API_STR}/car-reports/reports/pending/count")
        assert response.status_code == 200
        data = response.json()
        assert "pending_count" in data
        assert isinstance(data["pending_count"], int)
