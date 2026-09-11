"""Tests for part_manufacturer entity endpoints."""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, get_default_category_id, login_user, save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"part_manufacturer_admin_{username_suffix}"
    email = f"part_manufacturer_admin_{username_suffix}@example.com"
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

    token = login_user(client, username)
    return admin_user.__dict__, token


def create_and_login_user(client: TestClient, username_suffix: str, db_session: Any | None = None) -> tuple[UUID, str]:
    """Create a user and log them in. Returns (user_id, token).
    If db_session is provided, verify email in DB so user can create global parts.
    """
    username = f"part_manufacturer_user_{username_suffix}"
    email = f"part_manufacturer_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id: UUID | None = None
    if response.status_code == 200:
        user_id = UUID(response.json()["id"])
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()

    if db_session is not None:
        user = UserRepository().get_by_username(username)
        if user:
            UserRepository().update(user.id, email_verified=True)

    token = login_user(client, username)

    if user_id is None:
        headers = auth_headers(token)
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        assert me_response.status_code == 200
        user_id = UUID(me_response.json()["id"])
    return user_id, token


def create_part_manufacturer_via_api(
    client: TestClient, token: str, name: str, description: str | None = None
) -> dict[str, Any]:
    """Create a part_manufacturer via API and return the response JSON."""
    headers = auth_headers(token)
    payload = {"name": name, "description": description, "is_active": True}
    response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create part_manufacturer: {response.text}"
    return response.json()


class TestPartManufacturers:
    """Test cases for part_manufacturer endpoints."""

    def test_get_part_manufacturers_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting all active part_manufacturers (public)."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/")
        assert response.status_code == 200
        part_manufacturers: list[Any] = response.json()
        assert isinstance(part_manufacturers, list)
        for b in part_manufacturers:
            assert "id" in b
            assert "name" in b
            assert b.get("is_active", True) is True

    def test_get_part_manufacturers_active_only_param(self, client: TestClient, db_session: Any) -> None:
        """Test get part_manufacturers with active_only=false returns all part_manufacturers."""
        _, token = create_and_login_user(client, "part_manufacturers_all")
        create_part_manufacturer_via_api(client, token, get_unique_name("inactive_part_manufacturer"))

        inactive = DBPartManufacturer(
            name=get_unique_name("inactive"),
            description="Inactive",
            is_active=False,
        )
        inactive = save_catalog(inactive)

        response = client.get(f"{settings.API_STR}/part-manufacturers/?active_only=false")
        assert response.status_code == 200
        part_manufacturers = response.json()
        names = [b["name"] for b in part_manufacturers]
        assert inactive.name in names

    def test_get_part_manufacturer_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting a specific part_manufacturer (public)."""
        _, token = create_and_login_user(client, "get_one")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("get_one"))
        part_manufacturer_id = created["id"]

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == part_manufacturer_id
        assert data["name"] == created["name"]

    def test_get_part_manufacturer_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent part_manufacturer."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}")
        assert response.status_code == 404
        msg = response.json().get("message", response.json().get("detail", ""))
        assert "part manufacturer" in msg.lower() and "not found" in msg.lower()

    def test_search_part_manufacturers_success(self, client: TestClient, db_session: Any) -> None:
        """Test searching part_manufacturers by name (public)."""
        _, token = create_and_login_user(client, "search")
        create_part_manufacturer_via_api(client, token, get_unique_name("AcmeParts"), "Acme parts")

        response = client.get(
            f"{settings.API_STR}/part-manufacturers/search",
            params={"q": "Acme", "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()["items"]
        assert isinstance(data, list)

    def test_search_part_manufacturers_missing_q(self, client: TestClient) -> None:
        """Test search requires q parameter."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/search", params={"skip": 0, "limit": 10})
        assert response.status_code == 422

    def test_create_part_manufacturer_success(self, client: TestClient, db_session: Any) -> None:
        """Test creating a part_manufacturer as authenticated user (non-admin)."""
        _, token = create_and_login_user(client, "create")
        headers = auth_headers(token)

        name = get_unique_name("NewPartManufacturer")
        payload = {"name": name, "description": "A new part_manufacturer", "is_active": True}

        response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["description"] == "A new part_manufacturer"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_part_manufacturer_duplicate_returns_existing(self, client: TestClient, db_session: Any) -> None:
        """Test creating a part_manufacturer with existing name returns existing part_manufacturer (case-insensitive)."""
        _, token = create_and_login_user(client, "dup")
        name = get_unique_name("DupPartManufacturer")
        first = create_part_manufacturer_via_api(client, token, name)
        first_id = first["id"]

        # Create again with same name (case variation)
        second = create_part_manufacturer_via_api(client, token, name.upper())
        assert second["id"] == first_id
        assert second["name"] == first["name"]

    def test_create_part_manufacturer_unauthorized(self, client: TestClient) -> None:
        """Test creating a part_manufacturer without auth returns 401."""
        payload = {"name": get_unique_name("NoAuth"), "is_active": True}
        response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload)
        assert response.status_code == 401

    def test_update_part_manufacturer_success(self, client: TestClient, db_session: Any) -> None:
        """Test updating a part_manufacturer (admin only)."""
        _, user_token = create_and_login_user(client, "update_creator")
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("ToUpdate"))

        _, admin_token = create_and_login_admin_user(client, db_session, "update_admin")
        headers = auth_headers(admin_token)

        update_data = {
            "name": get_unique_name("UpdatedName"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_part_manufacturer_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Non-admin who is NOT the creator can't update a UGC manufacturer."""
        _, creator_token = create_and_login_user(client, "update_forbidden_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("NoUpdate"))

        _, other_token = create_and_login_user(client, "update_forbidden_other")
        headers = auth_headers(other_token)

        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json={"description": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_part_manufacturer_curated_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Non-admin can't edit catalog manufacturers — edits are admin-only."""
        curated = DBPartManufacturer(
            name=get_unique_name("CuratedNoEdit"),
            description="Curated",
            is_active=True,
        )
        curated = save_catalog(curated)

        _, token = create_and_login_user(client, "update_curated_forbidden")
        headers = auth_headers(token)
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{curated.id}",
            json={"description": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_part_manufacturer_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test updating a non-existent part_manufacturer."""
        _, token = create_and_login_admin_user(client, db_session, "update_nf")
        headers = auth_headers(token)
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}",
            json={"description": "Missing"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_delete_part_manufacturer_success(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a part_manufacturer (admin only)."""
        _, user_token = create_and_login_user(client, "delete_creator")
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("ToDelete"))

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_admin")
        headers = auth_headers(admin_token)

        response = client.delete(f"{settings.API_STR}/part-manufacturers/{created['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

        get_resp = client.get(f"{settings.API_STR}/part-manufacturers/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_part_manufacturer_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Non-admin who is NOT the creator can't delete a UGC manufacturer."""
        _, creator_token = create_and_login_user(client, "delete_forbidden_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("NoDelete"))

        _, other_token = create_and_login_user(client, "delete_forbidden_other")
        headers = auth_headers(other_token)

        response = client.delete(f"{settings.API_STR}/part-manufacturers/{created['id']}", headers=headers)
        assert response.status_code == 403

    def test_delete_part_manufacturer_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a non-existent part_manufacturer."""
        _, token = create_and_login_admin_user(client, db_session, "delete_nf")
        headers = auth_headers(token)
        response = client.delete(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_delete_part_manufacturer_with_parts_fails(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a part_manufacturer that has parts returns 409."""
        _, user_token = create_and_login_user(client, "delete_with_parts", db_session)
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("PartManufacturerWithParts"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = auth_headers(user_token)

        part_data = {
            "name": get_unique_name("PartForPartManufacturer"),
            "description": "Part",
            "category_id": category_id,
            "part_manufacturer_id": part_manufacturer_id,
        }
        part_resp = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert part_resp.status_code == 200

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_wp_admin")
        admin_headers = auth_headers(admin_token)
        response = client.delete(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}", headers=admin_headers)
        assert response.status_code == 409
        body = response.json()
        detail = body.get("detail", body.get("message", ""))
        assert "associated parts" in detail.lower() or "cannot delete" in detail.lower()

    def test_get_parts_by_part_manufacturer_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting global parts by part_manufacturer (public)."""
        _, token = create_and_login_user(client, "parts_by_part_manufacturer", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerForParts"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = auth_headers(token)

        part_data = {
            "name": get_unique_name("PartInPartManufacturer"),
            "description": "Part",
            "category_id": category_id,
            "part_manufacturer_id": part_manufacturer_id,
        }
        client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts")
        assert response.status_code == 200
        parts = response.json()["items"]
        assert isinstance(parts, list)
        assert len(parts) >= 1
        assert all(p["part_manufacturer_id"] == part_manufacturer_id for p in parts)

    def test_get_parts_by_part_manufacturer_pagination(self, client: TestClient, db_session: Any) -> None:
        """Test pagination for parts by part_manufacturer."""
        _, token = create_and_login_user(client, "parts_pag", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerPag"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = auth_headers(token)

        for i in range(3):
            part_data = {
                "name": get_unique_name(f"PartPag_{i}"),
                "description": f"Part {i}",
                "category_id": category_id,
                "part_manufacturer_id": part_manufacturer_id,
            }
            client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(
            f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts",
            params={"limit": 2},
        )
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) == 2
        assert page["has_next"] is True

    def test_get_part_manufacturer_parts_count_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting parts count for a part_manufacturer (public)."""
        _, token = create_and_login_user(client, "count_user", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerCount"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = auth_headers(token)

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts-count")
        assert response.status_code == 200
        data = response.json()
        assert "parts_count" in data
        initial = data["parts_count"]
        assert isinstance(initial, int)
        assert initial >= 0

        part_data = {
            "name": get_unique_name("PartCount"),
            "description": "Part",
            "category_id": category_id,
            "part_manufacturer_id": part_manufacturer_id,
        }
        client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts-count")
        assert response.status_code == 200
        assert response.json()["parts_count"] == initial + 1

    def test_get_part_manufacturer_parts_count_not_found(self, client: TestClient) -> None:
        """Test parts count for non-existent part_manufacturer."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}/parts-count")
        assert response.status_code == 404

    def test_count_part_manufacturers_success(self, client: TestClient, db_session: Any) -> None:
        """Test counting part_manufacturers (public)."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        initial = data["count"]
        assert isinstance(initial, int)
        assert initial >= 0

        _, token = create_and_login_user(client, "count_inc")
        create_part_manufacturer_via_api(client, token, get_unique_name("CountInc"))

        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        assert response.json()["count"] == initial + 1

    def test_count_part_manufacturers_public(self, client: TestClient) -> None:
        """Test count works without authentication."""
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    # --- name dedup + counts ---------------------------------------------

    def test_create_pm_dedups_into_existing(self, client: TestClient, db_session: Any) -> None:
        """A user typing an existing brand name auto-links to that row (no dup).

        Manufacturers live in a single global namespace, deduped
        case-insensitively by name.
        """
        existing_name = get_unique_name("HKS")
        existing = DBPartManufacturer(
            name=existing_name,
            is_active=True,
        )
        existing = save_catalog(existing)

        _, token = create_and_login_user(client, "dedup_into_existing")
        # Use a case variant to also confirm case-insensitive match.
        result = create_part_manufacturer_via_api(client, token, existing_name.lower())
        assert result["id"] == str(existing.id)

    def test_create_pm_dedups_into_own_prior_create(self, client: TestClient, db_session: Any) -> None:
        """A user POSTing the same name twice gets the same row back."""
        _, token = create_and_login_user(client, "dedup_self")
        name = get_unique_name("FooCo")
        first = create_part_manufacturer_via_api(client, token, name)
        second = create_part_manufacturer_via_api(client, token, name)
        assert first["id"] == second["id"]

    def test_two_users_same_name_dedup_to_one_row(self, client: TestClient, db_session: Any) -> None:
        """Manufacturers are globally unique by case-insensitive name: two
        users POSTing the same name resolve to a single shared row."""
        name = get_unique_name("BarCo")
        _, token_a = create_and_login_user(client, "same_name_a")
        _, token_b = create_and_login_user(client, "same_name_b")

        a = create_part_manufacturer_via_api(client, token_a, name)
        b = create_part_manufacturer_via_api(client, token_b, name)
        assert a["id"] == b["id"]

    def test_get_pm_still_returns_200(self, client: TestClient, db_session: Any) -> None:
        """No read boundary: a manufacturer row is fetchable by id by anyone."""
        _, creator_token = create_and_login_user(client, "pm_readable_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("PmReadable"))

        # Anonymous fetch still works.
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/part-manufacturers/{created['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

    def test_get_pm_parts_returns_only_owner_parts(self, client: TestClient, db_session: Any) -> None:
        """GET /{id}/parts returns only the creator's parts."""
        creator_id, creator_token = create_and_login_user(client, "pm_parts_creator", db_session)
        pm = create_part_manufacturer_via_api(client, creator_token, get_unique_name("PmParts"))
        category_id = str(get_default_category_id(db_session))

        # Creator adds a part.
        part_resp = client.post(
            f"{settings.API_STR}/parts/",
            json={
                "name": get_unique_name("OwnerPart"),
                "category_id": category_id,
                "part_manufacturer_id": pm["id"],
            },
            headers=auth_headers(creator_token),
        )
        assert part_resp.status_code == 200

        response = client.get(f"{settings.API_STR}/part-manufacturers/{pm['id']}/parts")
        assert response.status_code == 200
        parts = response.json()["items"]
        assert all(p["user_id"] == str(creator_id) for p in parts)

    def test_creator_cannot_update_own_manufacturer(self, client: TestClient, db_session: Any) -> None:
        """Edits are admin-only: a non-admin creator can't update their own row."""
        _, token = create_and_login_user(client, "creator_cannot_update")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("MyEditable"))

        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json={"name": get_unique_name("Renamed"), "description": "Renamed by owner"},
            headers=auth_headers(token),
        )
        assert response.status_code == 403

    def test_counts_by_source(self, client: TestClient, db_session: Any) -> None:
        """The counts/by-source endpoint returns only a total."""
        before = client.get(f"{settings.API_STR}/part-manufacturers/counts/by-source").json()
        assert set(before.keys()) == {"total"}

        _, token = create_and_login_user(client, "counts_total")
        create_part_manufacturer_via_api(client, token, get_unique_name("PmForCount"))

        after = client.get(f"{settings.API_STR}/part-manufacturers/counts/by-source").json()
        assert set(after.keys()) == {"total"}
        assert after["total"] == before["total"] + 1
