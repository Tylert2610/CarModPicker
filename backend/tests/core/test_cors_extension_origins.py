"""CORS admits the CarModPicker extension by id, and nothing else.

The middleware used to carry `allow_origin_regex=r"chrome-extension://.*"`
alongside `allow_credentials=True`, so every extension a user had installed
could make credentialed cross-origin reads of this API. It also appended the
literal `"null"` origin. Both are gone; these tests pin the replacement.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings

# The Chrome Web Store id of the CarModPicker Browser Companion, shared by the
# staging and production GitHub environments as `CWS_EXTENSION_ID`.
STORE_EXTENSION_ID = "dbglgmnnfandmnacdpibkfggkadjikkg"
STORE_ORIGIN = f"chrome-extension://{STORE_EXTENSION_ID}"


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, SECRET_KEY="x", **overrides)  # type: ignore[call-arg]


# --- Settings level ---------------------------------------------------------


def test_store_extension_origin_is_allowed_by_default() -> None:
    """No Terraform or Lambda env change is needed for the shipped extension."""
    s = _settings()
    assert STORE_ORIGIN in s.allowed_origins_list
    assert s.chrome_extension_origins_list == [STORE_ORIGIN]


def test_null_origin_is_not_allowed() -> None:
    """`"null"` used to be appended unconditionally.

    An MV3 service worker sends `chrome-extension://<id>`, never `null`, so no
    CarModPicker client needs it. `null` is what a sandboxed iframe, a `data:`
    document and a file:// page send, and with `allow_credentials=True` it
    handed those the same access as the real frontend.
    """
    for environment in ("development", "staging", "production"):
        s = _settings(APP_ENVIRONMENT=environment)
        assert "null" not in s.allowed_origins_list


def test_unknown_extension_id_is_not_allowed() -> None:
    s = _settings()
    assert "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in s.allowed_origins_list


def test_additional_ids_can_be_added_for_an_unpacked_build() -> None:
    """Staging may carry a developer's unpacked id alongside the store id."""
    unpacked = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    s = _settings(CHROME_EXTENSION_IDS=f"{STORE_EXTENSION_ID},{unpacked}")
    assert s.chrome_extension_origins_list == [STORE_ORIGIN, f"chrome-extension://{unpacked}"]


def test_ids_may_be_given_with_or_without_the_scheme_and_are_deduplicated() -> None:
    s = _settings(CHROME_EXTENSION_IDS=f"{STORE_EXTENSION_ID}, {STORE_ORIGIN} ,{STORE_EXTENSION_ID}")
    assert s.chrome_extension_origins_list == [STORE_ORIGIN]


def test_empty_extension_ids_yields_no_extension_origins() -> None:
    s = _settings(CHROME_EXTENSION_IDS="")
    assert s.chrome_extension_origins_list == []
    assert not any(o.startswith("chrome-extension://") for o in s.allowed_origins_list)


# --- Middleware level -------------------------------------------------------


def _preflight(client: TestClient, origin: str) -> "object":
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_preflight_from_the_store_extension_succeeds_with_credentials(client: TestClient) -> None:
    response = _preflight(client, STORE_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == STORE_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_from_an_unknown_extension_is_refused(client: TestClient) -> None:
    """The wildcard regex used to let this through."""
    response = _preflight(client, "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_the_null_origin_is_refused(client: TestClient) -> None:
    response = _preflight(client, "null")
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_an_unrelated_site_is_refused(client: TestClient) -> None:
    response = _preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", ["http://localhost:4000", "http://localhost:3000"])
def test_preflight_from_the_configured_frontend_origins_succeeds(client: TestClient, origin: str) -> None:
    if origin not in settings.allowed_origins_list:
        pytest.skip(f"{origin} is not in this environment's ALLOWED_ORIGINS")
    response = _preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
