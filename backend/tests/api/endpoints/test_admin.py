"""Tests for admin endpoints."""

from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, catalog_repository, login_user, save_catalog


def create_and_login_admin_user(client: TestClient, db_session: Any, username_suffix: str = "admin") -> str:
    """Create an admin user and log them in. Returns token."""
    username = f"admin_ep_test_{username_suffix}"
    email = f"admin_ep_test_{username_suffix}@example.com"
    password = "testpassword"

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

    return login_user(client, username, password)


def create_and_login_user(client: TestClient, db_session: Any, username_suffix: str) -> str:
    """Create a regular user and log them in. Returns token."""
    username = f"admin_ep_user_{username_suffix}"
    email = f"admin_ep_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    if response.status_code != 200:
        # User might already exist
        response.raise_for_status()

    if db_session:
        user = UserRepository().get_by_username(username)
        if user:
            UserRepository().update(user.id, email_verified=True)

    return login_user(client, username, password)


class TestAdminDeleteAllPartManufacturers:
    """Test cases for admin delete-all-part_manufacturers endpoint."""

    def test_delete_all_part_manufacturers_unauthorized(self, client: TestClient) -> None:
        """Test delete all part_manufacturers without auth returns 401."""
        response = client.post(f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all")
        assert response.status_code == 401

    def test_delete_all_part_manufacturers_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Test delete all part_manufacturers as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "delete_part_manufacturers_forbidden")
        headers = auth_headers(token)
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 403

    def test_delete_all_part_manufacturers_success_admin(
        self, client: TestClient, db_session: Any, test_category, test_user
    ) -> None:
        """Test delete all part_manufacturers as admin returns 200 with deleted_count."""
        part_manufacturer1 = DBPartManufacturer(
            name="part_manufacturer_delete_1", description="PartManufacturer 1", is_active=True
        )
        part_manufacturer2 = DBPartManufacturer(
            name="part_manufacturer_delete_2", description="PartManufacturer 2", is_active=True
        )
        part_manufacturer1 = save_catalog(part_manufacturer1)
        part_manufacturer2 = save_catalog(part_manufacturer2)

        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_success")
        headers = auth_headers(token)
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert data["deleted_count"] == 2

        # Verify part_manufacturers are gone
        remaining = catalog_repository(DBPartManufacturer).count()
        assert remaining == 0

    def test_delete_all_part_manufacturers_nullifies_part_part_manufacturer_ids(
        self, client: TestClient, db_session: Any, test_category, test_user
    ) -> None:
        """Test that deleting all part_manufacturers nullifies part_manufacturer_id on global parts."""
        part_manufacturer = DBPartManufacturer(
            name="part_manufacturer_for_part", description="PartManufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        part = DBPart(
            name="Part with part_manufacturer",
            description="Test part",
            category_id=test_category.id,
            user_id=test_user.id,
            part_manufacturer_id=part_manufacturer.id,
        )
        part = save_catalog(part)
        part_id = part.id

        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_nullify")
        headers = auth_headers(token)
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        # Verify part still exists but part_manufacturer_id is null
        part_after = catalog_repository(DBPart).get(str(part_id))
        assert part_after is not None
        assert part_after.part_manufacturer_id is None

    def test_delete_all_part_manufacturers_empty_success(self, client: TestClient, db_session: Any) -> None:
        """Test delete all part_manufacturers when no part_manufacturers exist returns 200 with deleted_count=0."""
        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_empty")
        headers = auth_headers(token)
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0


class TestAdminTableCounts:
    """GET /admin/stats/table-counts — supplemental DB counts (admin only)."""

    def test_table_counts_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        token = create_and_login_user(client, db_session, "table_counts_forbidden")
        headers = auth_headers(token)
        response = client.get(f"{settings.API_STR}/admin/stats/table-counts", headers=headers)
        assert response.status_code == 403

    def test_table_counts_admin_ok(self, client: TestClient, db_session: Any) -> None:
        token = create_and_login_admin_user(client, db_session, "table_counts_ok")
        headers = auth_headers(token)
        response = client.get(f"{settings.API_STR}/admin/stats/table-counts", headers=headers)
        assert response.status_code == 200
        data = response.json()
        for key in (
            "build_list_phases",
            "part_listings",
            "part_price_histories",
            "image_source_mappings",
            "build_logs",
            "part_cars",
            "votes_by_entity_type",
            "reports_by_entity_type",
        ):
            assert key in data
        assert isinstance(data["build_list_phases"], int)
        assert isinstance(data["votes_by_entity_type"], dict)
        assert isinstance(data["reports_by_entity_type"], dict)
