import os
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User, UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user, save_catalog


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


class TestUnifiedReports:
    """Test cases for unified reports endpoints."""

    def test_create_build_list_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test successfully creating a report for a build list."""
        # Create a second user to own the build list
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and create a report
        test_user_token = login_user(client, test_user.username)
        headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == build_list["id"]
        assert data["entity_type"] == "build_list"
        assert data["user_id"] == str(test_user.id)
        assert data["reason"] == "spam"
        assert data["description"] == "This build list is spam"
        assert data["status"] == "pending"

    def test_create_part_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        """Test successfully creating a report for a global part."""
        # Create a second user to own the global part
        from app.db.dynamo.users import User as DBUser

        part_owner = UserRepository().create_user(
            DBUser(
                username=f"part_owner_{os.getpid()}_{id(db_session)}",
                email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Create a category first
        from app.db.dynamo.catalog import Category as DBCategory

        category = DBCategory(name=get_unique_name("Test Category"))
        category = save_catalog(category)

        # Create a part_manufacturer
        from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer

        part_manufacturer = DBPartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        # Login as part owner and create a global part
        part_owner_token = login_user(client, part_owner.username)
        headers = auth_headers(part_owner_token)

        # Create a global part
        part_data = {
            "name": get_unique_name("Test Part"),
            "description": "A test part description",
            "category_id": str(category.id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Login as test user and create a report
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "inaccurate",
            "description": "This part information is inaccurate",
        }
        response = client.post(
            f"{settings.API_STR}/reports/part/{part['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == part["id"]
        assert data["entity_type"] == "part"
        assert data["user_id"] == str(test_user.id)
        assert data["reason"] == "inaccurate"
        assert data["description"] == "This part information is inaccurate"
        assert data["status"] == "pending"

    def test_create_report_unauthorized(self, client: TestClient, db_session: Any) -> None:
        """Test creating a report without authentication."""
        # Try to create a report without authentication
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(f"{settings.API_STR}/reports/build_list/{INVALID_UUID_STR}", json=report_data)
        assert response.status_code == 401

    def test_create_report_entity_not_found(self, client: TestClient, test_user: User) -> None:
        """Test creating a report for an entity that doesn't exist."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to report non-existent entity
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{INVALID_UUID_STR}", json=report_data, headers=headers
        )
        assert response.status_code == 404

    def test_create_report_own_entity(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test that users cannot report their own entities."""
        # Login as test user and create a build list
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list owned by test user
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to report own build list (should fail)
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}", json=report_data, headers=headers
        )
        assert response.status_code == 400
        response_data = response.json()
        # Handle both "detail" and "message" response formats
        error_text = response_data.get("detail", response_data.get("message", "")).lower()
        assert "cannot report your own" in error_text or "report your own" in error_text

    def test_create_report_already_reported(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test that users cannot report the same entity twice."""
        # Create a second user to own the build list
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and create a report
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create first report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Try to create second report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 400
        assert "already reported" in response.json()["message"]

    def test_list_reports_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that listing reports requires admin access."""
        # Login as regular user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to list reports
        response = client.get(f"{settings.API_STR}/reports/admin/list", headers=headers)
        assert response.status_code == 403

    def test_list_reports_success(self, client: TestClient, test_admin_user: User, db_session: Any) -> None:
        """Test successfully listing reports as admin."""
        # Login as admin user
        token = login_user(client, test_admin_user.username)
        headers = auth_headers(token)

        # List reports
        response = client.get(f"{settings.API_STR}/reports/admin/list", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_my_reports_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully getting user's own reports."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Get my reports
        response = client.get(f"{settings.API_STR}/reports/my-reports", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_report_by_id_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully getting a specific report by ID."""
        # Create a second user to own the build list
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the report by ID
        response = client.get(f"{settings.API_STR}/reports/{report['id']}", headers=test_user_headers)
        assert response.status_code == 200
        retrieved_report = response.json()
        assert retrieved_report["id"] == report["id"]
        assert retrieved_report["entity_id"] == build_list["id"]

    def test_get_report_by_id_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting a report that doesn't exist."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to get non-existent report
        response = client.get(f"{settings.API_STR}/reports/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_update_report_status_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that updating report status requires admin access."""
        # Login as regular user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to update report status
        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(f"{settings.API_STR}/reports/{INVALID_UUID_STR}", json=update_data, headers=headers)
        assert response.status_code == 403

    def test_update_report_status_success(self, client: TestClient, test_admin_user: User, db_session: Any) -> None:
        """Test successfully updating report status as admin."""
        from app.db.dynamo.users import User as DBUser

        # Create a test user to own the build list
        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Create a test user to make the report
        test_user = UserRepository().create_user(
            DBUser(
                username=f"test_user_{os.getpid()}_{id(db_session)}",
                email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as test user and create a report
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "duplicate",
            "description": "This build list is a duplicate",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and update report status
        admin_token = login_user(client, test_admin_user.username)
        admin_headers = auth_headers(admin_token)

        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(f"{settings.API_STR}/reports/{report['id']}", json=update_data, headers=admin_headers)
        assert response.status_code == 200
        updated_report = response.json()
        assert updated_report["status"] == "resolved"
        assert updated_report["admin_notes"] == "Issue resolved"

    def test_delete_report_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that deleting reports requires admin access."""
        # Login as regular user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to delete report
        response = client.delete(f"{settings.API_STR}/reports/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 403

    def test_delete_report_success(self, client: TestClient, test_admin_user: User, db_session: Any) -> None:
        """Test successfully deleting a report as admin."""
        from app.db.dynamo.users import User as DBUser

        # Create a test user to own the build list
        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Create a test user to make the report
        test_user = UserRepository().create_user(
            DBUser(
                username=f"test_user2_{os.getpid()}_{id(db_session)}",
                email=f"test_user2_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as test user and create a report
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "other",
            "description": "Other issue with this build list",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and delete report
        admin_token = login_user(client, test_admin_user.username)
        admin_headers = auth_headers(admin_token)

        response = client.delete(f"{settings.API_STR}/reports/{report['id']}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Report deleted successfully"

    def test_report_invalid_entity_type(self, client: TestClient, test_user: User) -> None:
        """Test reporting with invalid entity type."""
        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to report with invalid entity type
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/invalid_type/{INVALID_UUID_STR}", json=report_data, headers=headers
        )
        assert response.status_code == 422  # Validation error

    def test_report_invalid_reason(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test reporting with invalid reason."""
        # Create a second user to own the build list
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to report with invalid reason
        report_data = {
            "reason": "invalid_reason",
            "description": "This build list has an invalid reason",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}", json=report_data, headers=headers
        )
        assert response.status_code == 422  # Validation error

    def test_count_reports_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test counting reports."""
        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/reports/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a second user to own the build list
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Login as build list owner and create a build list
        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user
        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/reports/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_reports_public_endpoint(self, client: TestClient) -> None:
        """Test that counting reports works without authentication."""
        # Count reports (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/reports/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_list_reports_with_details_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that listing reports with details requires admin access."""
        # Login as regular user
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        # Try to list reports with details
        response = client.get(f"{settings.API_STR}/reports/admin/list-with-details", headers=headers)
        assert response.status_code == 403

    def test_list_reports_with_details_success(
        self, client: TestClient, test_admin_user: User, db_session: Any
    ) -> None:
        """Test successfully listing reports with details as admin."""
        # Login as admin user
        token = login_user(client, test_admin_user.username)
        headers = auth_headers(token)

        # List reports with details
        response = client.get(f"{settings.API_STR}/reports/admin/list-with-details", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert "total_items" in data["pagination"]  # total is in pagination object
        assert "items_per_page" in data["pagination"]  # limit is items_per_page in pagination
        assert isinstance(data["data"], list)
        # Check pagination object instead of top-level fields
        assert isinstance(data["pagination"]["total"], int)
        assert isinstance(data["pagination"]["skip"], int)
        assert isinstance(data["pagination"]["limit"], int)

    def test_list_reports_with_details_pagination(
        self, client: TestClient, test_admin_user: User, db_session: Any
    ) -> None:
        """Test pagination for listing reports with details."""
        # Login as admin user
        token = login_user(client, test_admin_user.username)
        headers = auth_headers(token)

        # Get first page
        response = client.get(f"{settings.API_STR}/reports/admin/list-with-details?skip=0&limit=10", headers=headers)
        assert response.status_code == 200
        first_page = response.json()
        assert "data" in first_page
        assert len(first_page["data"]) <= 10

        # Get second page
        response = client.get(f"{settings.API_STR}/reports/admin/list-with-details?skip=10&limit=10", headers=headers)
        assert response.status_code == 200
        second_page = response.json()
        assert "data" in second_page

    def test_list_reports_with_details_filtering(
        self, client: TestClient, test_admin_user: User, db_session: Any
    ) -> None:
        """Test filtering for listing reports with details."""
        # Login as admin user
        token = login_user(client, test_admin_user.username)
        headers = auth_headers(token)

        # List reports with entity_type filter
        response = client.get(
            f"{settings.API_STR}/reports/admin/list-with-details?entity_type=build_list", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

        # List reports with status filter
        response = client.get(f"{settings.API_STR}/reports/admin/list-with-details?status=pending", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
