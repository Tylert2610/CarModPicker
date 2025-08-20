import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.part import Part
from app.api.models.user import User
from app.api.models.category import Category


class TestPartReports:
    def test_report_part_success(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_category: Category,
    ):
        """Test successful reporting of a part."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login user
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        # Report the part
        report_data = {
            "reason": "inappropriate",
            "description": "This part contains inappropriate content",
        }
        response = client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        assert response.status_code == 200
        data = response.json()
        assert data["reason"] == "inappropriate"
        assert data["part_id"] == part.id
        assert data["user_id"] == test_user.id
        assert data["status"] == "pending"

    def test_report_part_invalid_reason(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_category: Category,
    ):
        """Test reporting with invalid reason."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login user
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        # Try to report with invalid reason
        report_data = {"reason": "invalid_reason"}
        response = client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        assert response.status_code == 400
        assert "Reason must be one of:" in response.json()["detail"]

    def test_report_nonexistent_part(self, client: TestClient, test_user: User):
        """Test reporting a part that doesn't exist."""
        # Login user
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        # Try to report nonexistent part
        report_data = {"reason": "inappropriate"}
        response = client.post("/api/part-reports/999/report", json=report_data)

        assert response.status_code == 404
        assert "Part not found" in response.json()["detail"]

    def test_duplicate_report(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_category: Category,
    ):
        """Test that a user cannot report the same part twice."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login user
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        # First report
        report_data = {"reason": "inappropriate"}
        response = client.post(f"/api/part-reports/{part.id}/report", json=report_data)
        assert response.status_code == 200

        # Try to report again
        response = client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        assert response.status_code == 409
        assert "You have already reported this part" in response.json()["detail"]

    def test_report_unauthorized(
        self,
        client: TestClient,
        db_session: Session,
        test_category: Category,
        test_user: User,
    ):
        """Test reporting without authentication."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Try to report without login
        report_data = {"reason": "inappropriate"}
        response = client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        assert response.status_code == 401


class TestPartReportsAdmin:
    def test_get_reports_admin(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        test_user: User,
        test_category: Category,
    ):
        """Test admin getting all reports."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login as regular user and create a report
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        report_data = {"reason": "inappropriate"}
        client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        # Login as admin
        admin_login_response = client.post(
            "/api/auth/token",
            data={"username": admin_user.username, "password": "testpassword"},
        )
        assert admin_login_response.status_code == 200

        # Get reports
        response = client.get("/api/part-reports/reports")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["reason"] == "inappropriate"
        assert data[0]["reporter_username"] == test_user.username
        assert data[0]["part_name"] == part.name

    def test_get_reports_non_admin(self, client: TestClient, test_user: User):
        """Test that non-admin users cannot get reports."""
        # Login as regular user
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        # Try to get reports
        response = client.get("/api/part-reports/reports")

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_get_specific_report_admin(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        test_user: User,
        test_category: Category,
    ):
        """Test admin getting a specific report."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login as regular user and create a report
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        report_data = {"reason": "spam"}
        report_response = client.post(
            f"/api/part-reports/{part.id}/report", json=report_data
        )
        report_id = report_response.json()["id"]

        # Login as admin
        admin_login_response = client.post(
            "/api/auth/token",
            data={"username": admin_user.username, "password": "testpassword"},
        )
        assert admin_login_response.status_code == 200

        # Get specific report
        response = client.get(f"/api/part-reports/reports/{report_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == report_id
        assert data["reason"] == "spam"
        assert data["reporter_username"] == test_user.username
        assert data["part_name"] == part.name

    def test_update_report_admin(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        test_user: User,
        test_category: Category,
    ):
        """Test admin updating a report status."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login as regular user and create a report
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        report_data = {"reason": "inappropriate"}
        report_response = client.post(
            f"/api/part-reports/{part.id}/report", json=report_data
        )
        report_id = report_response.json()["id"]

        # Login as admin
        admin_login_response = client.post(
            "/api/auth/token",
            data={"username": admin_user.username, "password": "testpassword"},
        )
        assert admin_login_response.status_code == 200

        # Update report
        update_data = {"status": "resolved", "admin_notes": "Issue has been resolved"}
        response = client.put(
            f"/api/part-reports/reports/{report_id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["admin_notes"] == "Issue has been resolved"
        assert data["reviewed_by"] == admin_user.id

    def test_update_report_invalid_status(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        test_user: User,
        test_category: Category,
    ):
        """Test admin updating a report with invalid status."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login as regular user and create a report
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        report_data = {"reason": "inappropriate"}
        report_response = client.post(
            f"/api/part-reports/{part.id}/report", json=report_data
        )
        report_id = report_response.json()["id"]

        # Login as admin
        admin_login_response = client.post(
            "/api/auth/token",
            data={"username": admin_user.username, "password": "testpassword"},
        )
        assert admin_login_response.status_code == 200

        # Try to update with invalid status
        update_data = {"status": "invalid_status"}
        response = client.put(
            f"/api/part-reports/reports/{report_id}", json=update_data
        )

        assert response.status_code == 400
        assert "Status must be one of:" in response.json()["detail"]

    def test_get_pending_reports_count(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        test_user: User,
        test_category: Category,
    ):
        """Test admin getting pending reports count."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Login as regular user and create a report
        login_response = client.post(
            "/api/auth/token",
            data={"username": test_user.username, "password": "testpassword"},
        )
        assert login_response.status_code == 200

        report_data = {"reason": "inappropriate"}
        client.post(f"/api/part-reports/{part.id}/report", json=report_data)

        # Login as admin
        admin_login_response = client.post(
            "/api/auth/token",
            data={"username": admin_user.username, "password": "testpassword"},
        )
        assert admin_login_response.status_code == 200

        # Get pending count
        response = client.get("/api/part-reports/reports/pending/count")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_count"] == 1
