"""`settings.api_base_url` per environment.

The verification email link used to be a DEBUG/else branch that produced either
`http://localhost:8000/...` or `https://api.carmodpicker.com/...`, so staging
mailed production links. These tests pin the per-environment value the way
`test_config_frontend_url.py` pins the SPA origin.
"""

import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, SECRET_KEY="x", **overrides)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("app_environment", "debug", "expected"),
    [
        ("development", True, "http://localhost:8000"),
        ("development", False, "http://localhost:8000"),
        ("staging", False, "https://api.staging.carmodpicker.com"),
        ("production", False, "https://api.carmodpicker.com"),
        # DEBUG=True anywhere means a local run, so it wins over the name.
        ("production", True, "http://localhost:8000"),
        ("staging", True, "http://localhost:8000"),
    ],
)
def test_defaults_when_api_url_unset(app_environment: str, debug: bool, expected: str) -> None:
    s = _settings(APP_ENVIRONMENT=app_environment, DEBUG=debug, API_URL="")
    assert s.api_base_url == expected


def test_staging_does_not_use_the_production_api_host() -> None:
    """The regression this change fixes."""
    staging = _settings(APP_ENVIRONMENT="staging", DEBUG=False, API_URL="")
    production = _settings(APP_ENVIRONMENT="production", DEBUG=False, API_URL="")
    assert staging.api_base_url != production.api_base_url
    assert "api.staging." in staging.api_base_url


@pytest.mark.parametrize(
    ("api_url", "expected"),
    [
        ("https://api.example.com", "https://api.example.com"),
        ("https://api.example.com/", "https://api.example.com"),
        ("  https://api.example.com/  ", "https://api.example.com"),
        ("https://abc123.execute-api.us-west-2.amazonaws.com", "https://abc123.execute-api.us-west-2.amazonaws.com"),
    ],
)
def test_api_url_override_wins_and_is_normalized(api_url: str, expected: str) -> None:
    s = _settings(APP_ENVIRONMENT="staging", DEBUG=False, API_URL=api_url)
    assert s.api_base_url == expected


def test_api_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_URL", "https://api.d456.example.com")
    s = Settings(_env_file=None, SECRET_KEY="x", APP_ENVIRONMENT="staging", DEBUG=False)  # type: ignore[call-arg]
    assert s.api_base_url == "https://api.d456.example.com"


def test_local_api_base_url_follows_port() -> None:
    s = _settings(APP_ENVIRONMENT="development", DEBUG=True, API_URL="", PORT=9001)
    assert s.api_base_url == "http://localhost:9001"


@pytest.mark.parametrize(
    ("app_environment", "debug", "expected_prefix"),
    [
        ("development", True, "http://localhost:8000/api/auth/verify-email/confirm?token="),
        ("staging", False, "https://api.staging.carmodpicker.com/api/auth/verify-email/confirm?token="),
        ("production", False, "https://api.carmodpicker.com/api/auth/verify-email/confirm?token="),
    ],
)
def test_verification_link_shape_per_environment(app_environment: str, debug: bool, expected_prefix: str) -> None:
    """The exact string `verify_email` builds, per environment."""
    s = _settings(APP_ENVIRONMENT=app_environment, DEBUG=debug, API_URL="")
    verify_url = f"{s.api_base_url}/api/auth/verify-email/confirm?token=tok"
    assert verify_url == f"{expected_prefix}tok"
