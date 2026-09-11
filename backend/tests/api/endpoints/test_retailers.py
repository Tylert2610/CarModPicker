"""Tests for retailer entity endpoints."""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import PartListing
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from app.db.dynamo.catalog import Retailer as DBRetailer
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
    username = f"retailer_admin_{username_suffix}"
    email = f"retailer_admin_{username_suffix}@example.com"
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


def create_and_login_user(client: TestClient, username_suffix: str, db_session: Any | None = None) -> tuple[int, str]:
    """Create a user and log them in. Returns (user_id, token)."""
    username = f"retailer_user_{username_suffix}"
    email = f"retailer_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()

    if db_session is not None:
        user = UserRepository().get_by_username(username)
        if user:
            UserRepository().update(user.id, email_verified=True)

    token = login_user(client, username)

    if user_id == -1:
        headers = auth_headers(token)
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        assert me_response.status_code == 200
        user_id = me_response.json()["id"]
    return user_id, token


def create_retailer_via_api(
    client: TestClient, token: str, name: str, domain: str | None = None, base_url: str | None = None
) -> dict[str, Any]:
    """Create a retailer via API (admin) and return the response JSON."""
    headers = auth_headers(token)
    payload: dict[str, Any] = {"name": name, "is_active": True}
    if domain is not None:
        payload["domain"] = domain
    if base_url is not None:
        payload["base_url"] = base_url
    response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create retailer: {response.text}"
    return response.json()


class TestRetailers:
    """Test cases for retailer endpoints."""

    def test_get_retailers_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting all retailers (public, default active_only=True)."""
        response = client.get(f"{settings.API_STR}/retailers/")
        assert response.status_code == 200
        retailers: list[Any] = response.json()
        assert isinstance(retailers, list)
        for r in retailers:
            assert "id" in r
            assert "name" in r
            assert r.get("is_active", True) is True

    def test_get_retailers_active_only_param(self, client: TestClient, db_session: Any) -> None:
        """Test get retailers with active_only=false returns all retailers."""
        _, admin_token = create_and_login_admin_user(client, db_session, "list_all")
        create_retailer_via_api(client, admin_token, get_unique_name("active_ret"))

        inactive = DBRetailer(
            name=get_unique_name("inactive_ret"),
            domain=get_unique_name("inactive.com"),
            is_active=False,
        )
        inactive = save_catalog(inactive)

        response = client.get(f"{settings.API_STR}/retailers/?active_only=false")
        assert response.status_code == 200
        retailers = response.json()
        names = [r["name"] for r in retailers]
        assert inactive.name in names

    def test_get_retailer_success(self, client: TestClient, db_session: Any) -> None:
        """Test getting a specific retailer (public)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "get_one")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("get_one"), domain=get_unique_name("getone.com")
        )
        retailer_id = created["id"]

        response = client.get(f"{settings.API_STR}/retailers/{retailer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == retailer_id
        assert data["name"] == created["name"]

    def test_get_retailer_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent retailer."""
        response = client.get(f"{settings.API_STR}/retailers/{INVALID_UUID_STR}")
        assert response.status_code == 404
        msg = response.json().get("message", response.json().get("detail", ""))
        assert "retailer" in msg.lower() and "not found" in msg.lower()

    def test_post_get_or_create_success_new(self, client: TestClient, db_session: Any) -> None:
        """Test get-or-create creates new retailer when domain does not exist (authenticated)."""
        _, token = create_and_login_user(client, "getorcreate", db_session)
        headers = auth_headers(token)

        domain = get_unique_name("newshop.com")
        payload = {"domain": domain, "name": "New Shop"}

        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == domain
        assert data["name"] == "New Shop"
        assert "id" in data

    def test_post_get_or_create_success_existing(self, client: TestClient, db_session: Any) -> None:
        """Test get-or-create returns existing retailer when domain exists."""
        _, token = create_and_login_user(client, "getorcreate_existing", db_session)
        headers = auth_headers(token)

        domain = get_unique_name("existingshop.com")
        payload = {"domain": domain, "name": "Existing Shop"}

        first = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert first.status_code == 200
        first_data = first.json()
        first_id = first_data["id"]

        second = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["id"] == first_id

    def test_post_get_or_create_derives_name_from_domain(self, client: TestClient, db_session: Any) -> None:
        """Test get-or-create derives name from domain when name omitted."""
        _, token = create_and_login_user(client, "derive_name", db_session)
        headers = auth_headers(token)

        domain = get_unique_name("a90shop.com")
        payload = {"domain": domain}

        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == domain
        assert data["name"]  # Derived from domain (e.g., A90shop)

    def test_post_get_or_create_empty_domain_returns_400(self, client: TestClient, db_session: Any) -> None:
        """Test get-or-create with empty domain returns 400."""
        _, token = create_and_login_user(client, "empty_domain", db_session)
        headers = auth_headers(token)

        payload = {"domain": "   "}
        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 400
        body = response.json()
        msg = (body.get("message") or body.get("detail") or "").lower()
        assert "domain" in msg or "required" in msg

    def test_post_get_or_create_unauthorized(self, client: TestClient) -> None:
        """Test get-or-create without auth returns 401."""
        payload = {"domain": "shop.com", "name": "Shop"}
        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload)
        assert response.status_code == 401

    def test_create_retailer_success(self, client: TestClient, db_session: Any) -> None:
        """Test creating a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "create")
        headers = auth_headers(admin_token)

        name = get_unique_name("NewRetailer")
        domain = get_unique_name("newretailer.com")
        payload = {"name": name, "domain": domain, "base_url": "https://www.example.com", "is_active": True}

        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["domain"] == domain
        assert data["base_url"] == "https://www.example.com"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_retailer_unauthorized(self, client: TestClient) -> None:
        """Test creating a retailer without auth returns 401."""
        payload = {"name": get_unique_name("NoAuth"), "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload)
        assert response.status_code == 401

    def test_create_retailer_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Test creating a retailer as non-admin returns 403."""
        _, token = create_and_login_user(client, "create_forbidden", db_session)
        headers = auth_headers(token)
        payload = {"name": get_unique_name("NoCreate"), "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 403

    def test_create_retailer_duplicate_domain_returns_409(self, client: TestClient, db_session: Any) -> None:
        """Test creating a retailer with existing domain returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "dup")
        domain = get_unique_name("dupdomain.com")
        create_retailer_via_api(client, admin_token, get_unique_name("First"), domain=domain)

        headers = auth_headers(admin_token)
        payload = {"name": get_unique_name("Second"), "domain": domain, "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 409
        body = response.json()
        detail = str(body.get("detail", body.get("message", ""))).lower()
        assert "domain" in detail or "duplicate" in detail or "exists" in detail

    def test_update_retailer_success(self, client: TestClient, db_session: Any) -> None:
        """Test updating a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("ToUpdate"), domain=get_unique_name("toupdate.com")
        )
        headers = auth_headers(admin_token)

        update_data = {"name": get_unique_name("UpdatedName"), "base_url": "https://updated.com"}
        response = client.put(
            f"{settings.API_STR}/retailers/{created['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["base_url"] == update_data["base_url"]

    def test_update_retailer_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Test updating a retailer as non-admin returns 403."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update_creator")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("NoUpdate"), domain=get_unique_name("noupdate.com")
        )
        _, user_token = create_and_login_user(client, "update_forbidden", db_session)
        headers = auth_headers(user_token)

        response = client.put(
            f"{settings.API_STR}/retailers/{created['id']}",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_retailer_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test updating a non-existent retailer."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update_nf")
        headers = auth_headers(admin_token)
        response = client.put(
            f"{settings.API_STR}/retailers/{INVALID_UUID_STR}",
            json={"name": "Missing"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_update_retailer_duplicate_domain_returns_409(self, client: TestClient, db_session: Any) -> None:
        """Test updating retailer to existing domain returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "dup_update")
        first = create_retailer_via_api(
            client, admin_token, get_unique_name("FirstRet"), domain=get_unique_name("firstret.com")
        )
        second = create_retailer_via_api(
            client, admin_token, get_unique_name("SecondRet"), domain=get_unique_name("secondret.com")
        )
        headers = auth_headers(admin_token)

        response = client.put(
            f"{settings.API_STR}/retailers/{second['id']}",
            json={"domain": first["domain"]},
            headers=headers,
        )
        assert response.status_code == 409

    def test_delete_retailer_success(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("ToDelete"), domain=get_unique_name("todelete.com")
        )
        headers = auth_headers(admin_token)

        response = client.delete(f"{settings.API_STR}/retailers/{created['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

        get_resp = client.get(f"{settings.API_STR}/retailers/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_retailer_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a retailer as non-admin returns 403."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_creator")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("NoDelete"), domain=get_unique_name("nodelete.com")
        )
        _, user_token = create_and_login_user(client, "delete_forbidden", db_session)
        headers = auth_headers(user_token)

        response = client.delete(f"{settings.API_STR}/retailers/{created['id']}", headers=headers)
        assert response.status_code == 403

    def test_delete_retailer_not_found(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a non-existent retailer."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_nf")
        headers = auth_headers(admin_token)
        response = client.delete(f"{settings.API_STR}/retailers/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_delete_retailer_with_part_listings_fails(self, client: TestClient, db_session: Any) -> None:
        """Test deleting a retailer that has part listings returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_with_listings")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("RetWithListings"), domain=get_unique_name("retwithlistings.com")
        )
        retailer_id = created["id"]

        # Create part_manufacturer for global part
        part_manufacturer = DBPartManufacturer(
            name=get_unique_name("RetPartManufacturer"), description="PartManufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        # Create global part and part listing
        _, user_token = create_and_login_user(client, "ret_listings_user", db_session)
        category_id = get_default_category_id(db_session)
        part_data = {
            "name": get_unique_name("PartForListing"),
            "description": "Part",
            "category_id": str(category_id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        part_resp = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=auth_headers(user_token))
        assert part_resp.status_code == 200, f"Failed to create part: {part_resp.text}"
        part = part_resp.json()

        listing = PartListing(
            part_id=UUID(part["id"]),
            retailer_id=UUID(retailer_id),
            product_url="https://example.com/part",
        )
        listing = save_catalog(listing)

        headers = auth_headers(admin_token)
        response = client.delete(f"{settings.API_STR}/retailers/{retailer_id}", headers=headers)
        assert response.status_code == 409
        body = response.json()
        detail = str(body.get("detail", body.get("message", ""))).lower()
        assert "listing" in detail or "cannot delete" in detail or "in use" in detail
