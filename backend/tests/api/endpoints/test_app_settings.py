"""Tests for global app settings endpoints."""

from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.api.endpoints.test_admin import create_and_login_admin_user, create_and_login_user
from tests.conftest import auth_headers


class TestAppSettings:
    """GET is public; PUT is admin-only. Row is lazily created with defaults on first read."""

    def test_get_public_returns_defaults(self, client: TestClient) -> None:
        response = client.get(f"{settings.API_STR}/app-settings/")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["premium_disabled"] is False
        assert "updated_at" in body

    def test_put_unauthorized(self, client: TestClient) -> None:
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            json={"premium_disabled": True},
        )
        assert response.status_code == 401

    def test_put_forbidden_non_admin(self, client: TestClient, db_session: Any) -> None:
        token = create_and_login_user(client, db_session, "app_settings_forbidden")
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers=auth_headers(token),
            json={"premium_disabled": True},
        )
        assert response.status_code == 403

    def test_put_admin_toggles_premium_disabled(self, client: TestClient, db_session: Any) -> None:
        token = create_and_login_admin_user(client, db_session, "app_settings_toggle")
        headers = auth_headers(token)

        # Flip on
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers=headers,
            json={"premium_disabled": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["premium_disabled"] is True

        # Public read reflects update
        response = client.get(f"{settings.API_STR}/app-settings/")
        assert response.status_code == 200
        assert response.json()["premium_disabled"] is True

        # Flip off
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers=headers,
            json={"premium_disabled": False},
        )
        assert response.status_code == 200
        assert response.json()["premium_disabled"] is False
