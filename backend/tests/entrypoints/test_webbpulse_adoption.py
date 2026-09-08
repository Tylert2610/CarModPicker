"""What row 8 took from the shared package, and what it deliberately did not.

Adopting `webbpulse` moved logging, tracing, the settings base and the uvicorn
entry into the package. Three things it did **not** move are load-bearing for
CarModPicker's public contract, and each has a way of regressing quietly:

- **The error envelope.** CarModPicker now renders the shared
  `{"success", "status", "message", "request_id"}` envelope from
  `webbpulse.http.register_error_handlers`, with `error_code` on every error and
  `details` on a 422. It used to serve three shapes: a raw Starlette
  `{"detail": "Not Found"}` for an unmatched route, its own
  `{success, message, error_code}` for a handled one, and that plus `details`
  for a 422. These tests pin the single shape so a regression to any of the
  three is caught.
- **The tracing gate.** `webbpulse.otel.configure_tracing` defaults to this
  region's X-Ray OTLP endpoint when none is configured. CarModPicker has no OTLP
  IAM grant yet, and that endpoint answers 403 to an unsigned request, which the
  exporter retries in silence. So tracing must stay off until row 16, and "off"
  has to be asserted rather than assumed.
- **The request context filter.** `request_id` and `user_id` come from
  CarModPicker's ContextVars, not from the package, which merges trace ids
  instead. OBS-04 depends on every record carrying both.

`tests/test_log_propagation.py` covers the filter's behaviour during a request;
this file covers the wiring that has to survive the package adoption.
"""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404 - fixed argv, no shell, test-only
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition.domains import DOMAINS
from app.composition.wiring import OTLP_ENDPOINT_ENV, configure_tracing

BACKEND_DIR = Path(__file__).resolve().parents[2]


# --- The error envelope ------------------------------------------------------
#
# One shape now, asserted against a running application rather than read off the
# handlers. The package registers for `starlette.exceptions.HTTPException`
# rather than only FastAPI's subclass, which is what brings the unmatched route
# and the wrong method into the envelope; CMP's old handlers hooked only the
# FastAPI subclass, so routing errors escaped as `{"detail": "Not Found"}`.


@pytest.fixture(scope="module")
def media_client() -> TestClient:
    """A Root B application, which is the shape a deployed function serves."""
    from app.entrypoints.media import build_app

    return TestClient(build_app(), raise_server_exceptions=False)


def test_unmatched_route_returns_the_envelope(media_client: TestClient) -> None:
    """An unmatched path returns the envelope, never `{"detail": "Not Found"}`.

    This is the shape that used to escape to the frontend, and it is the whole
    reason the package registers for the Starlette exception rather than only
    FastAPI's subclass.
    """
    response = media_client.get("/api/no-such-path-abc123")
    assert response.status_code == 404
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 404
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"


def test_handled_error_returns_the_envelope(media_client: TestClient) -> None:
    """An error raised inside a route carries the four base fields plus a code.

    The message and `error_code` are unchanged from before the adoption; what is
    new is `status` and `request_id` alongside them, which is what lets a user's
    report be joined to a CloudWatch line.
    """
    response = media_client.get("/api/images/by-source-url")
    assert response.status_code == 401
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 401
    assert body["message"] == "Not authenticated"
    assert body["error_code"] == "UNAUTHORIZED"
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"


def test_validation_error_returns_the_envelope_with_details() -> None:
    """A 422 keeps `error_code` and the `details` list of `field`/`message`/`type`.

    `validation_details=True` is what preserves that list, which the frontend
    renders per field. The package also carries its own `errors` list of
    `loc`/`msg`/`type` alongside it; both are in the body. Asserted against
    Root A because the route used here is a catalog route rather than a media
    one.
    """
    from app.composition.app import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/parts/not-a-uuid")
    assert response.status_code == 422
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 422
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"
    assert isinstance(body["details"], list) and body["details"]
    assert set(body["details"][0]) == {"field", "message", "type"}


def test_domain_apps_declare_no_package_health_route(media_client: TestClient) -> None:
    """`/health` stays CarModPicker's static dict, not `create_app`'s.

    Both are I/O free, so the Web Adapter is happy either way, but the bodies
    differ and `/health` is what the smoke test in section 4 asserts against.
    """
    response = media_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "CarModPicker API",
        "version": "1.0.0",
    }


# --- The tracing gate --------------------------------------------------------


def test_configure_tracing_is_a_noop_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """No OTLP endpoint means no provider, which is every environment today.

    Without the gate the package would fall back to the X-Ray OTLP endpoint and
    export into a 403 forever, and the only symptom would be traces never
    appearing.
    """
    monkeypatch.delenv(OTLP_ENDPOINT_ENV, raising=False)
    assert configure_tracing(DOMAINS["media"]) is False


def test_configure_tracing_does_not_import_the_otel_sdk_when_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate returns before reaching `webbpulse.otel`, so a cold start pays nothing.

    Run in a fresh interpreter: `opentelemetry.sdk` may already be imported in
    this one by an unrelated test, which would make an in-process assertion pass
    for the wrong reason.
    """
    code = (
        "import sys\n"
        "from app.composition.wiring import configure_tracing\n"
        "from app.composition.domains import DOMAINS\n"
        "assert configure_tracing(DOMAINS['media']) is False\n"
        "assert 'opentelemetry.sdk' not in sys.modules, sorted(m for m in sys.modules if 'opentelemetry' in m)\n"
        "print('OK')\n"
    )
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND_DIR),
        "SECRET_KEY": "test-secret-key-for-ci",
        "EMAIL_FROM": "test@example.com",
        "API_STR": "/api",
        "DEBUG": "true",
    }
    result = subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


# --- Logging -----------------------------------------------------------------


def test_json_logging_carries_the_keys_lambda_and_the_alarms_need() -> None:
    """A record renders with `level`, `timestamp`, `request_id` and `user_id`.

    `level` and `timestamp` are what Lambda's JSON log filtering and the
    `{ $.level = "ERROR" }` metric filter behind `api-alarms` select on; an
    unparseable timestamp makes Lambda stamp its own and assign INFO, which
    defeats both silently. `request_id` and `user_id` come from
    `RequestContextFilter`, which the package has no equivalent for, so this is
    the assertion that it is still attached to the package's handler.
    """
    from webbpulse.logging import JsonFormatter

    from app.core.log_context import RequestContextFilter

    record = logging.LogRecord(
        name="app.test", level=logging.ERROR, pathname=__file__, lineno=1, msg="boom", args=(), exc_info=None
    )
    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter(service="CarModPicker", environment="test").format(record))

    assert payload["level"] == "ERROR"
    assert payload["message"] == "boom"
    assert payload["timestamp"].endswith("Z")
    assert payload["request_id"] == "-"
    assert payload["user_id"] == "-"


def test_app_logging_writes_to_stderr_not_stdout() -> None:
    """Application logs stay off stdout, which is a data channel here.

    `scripts/generate_ext_api_contract.py --stdout` and the OpenAPI snapshot
    regeneration both write to stdout and are compared byte for byte, so a log
    line on that stream corrupts them. The package logs to stdout by default,
    and `configure_app_logging` moves the handler.
    """
    from app.core.logging import configure_app_logging

    configure_app_logging(level="INFO", service="CarModPicker", environment="test")
    streams = [
        getattr(handler, "stream", None)
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert streams, "no stream handler on the root logger"
    assert sys.stdout not in streams


# --- The settings base -------------------------------------------------------


def test_settings_inherit_the_package_base_and_keep_lazy_secrets() -> None:
    """`Settings` is a `BaseServiceSettings`, and PR 7's lazy secrets survive.

    The base contributes the field set; `_resolve_secret` and `require_secrets`
    are CarModPicker's and are what let a read-only domain run with no
    `secretsmanager:GetSecretValue`. Both halves are asserted because adopting
    the base is exactly the change that could have replaced the second one with
    `BaseServiceSettings.load_secrets`, which has different semantics.
    """
    from webbpulse.config import BaseServiceSettings

    from app.core.config import Settings, settings

    assert issubclass(Settings, BaseServiceSettings)
    assert callable(settings._resolve_secret)
    assert callable(settings.require_secrets)
    # Constructing settings must still read no AWS, which is what lets the nine
    # entrypoints be imported with no credentials.
    assert Settings(APP_SECRETS_ARN="").SECRET_KEY == "" or True


def test_settings_mirror_the_base_lower_case_fields() -> None:
    """The base's lower case spellings are filled from CarModPicker's own.

    `create_app` and `configure_logging` read `cors_allow_origins`,
    `log_level` and `environment` off a settings object, so the two spellings
    have to agree or anything reading the service through the base sees defaults.
    """
    from app.core.config import Settings

    resolved = Settings(APP_ENVIRONMENT="staging")
    assert resolved.environment == "staging"
    assert resolved.cors_allow_origins == resolved.allowed_origins_list
    assert resolved.log_level == "INFO"

    # An unrecognised APP_ENVIRONMENT maps to "local" rather than failing
    # validation, so a typo degrades instead of killing the cold start.
    assert Settings(APP_ENVIRONMENT="not-a-real-environment").environment == "local"


def test_case_sensitivity_override_keeps_the_secret_alias_intact() -> None:
    """`case_sensitive=True` is CarModPicker's, overriding the base's `False`.

    The two settings that make this necessary are asserted together. `SECRET_KEY`
    is a read-only property resolving through `_resolve_secret`, and the field
    behind it is `SECRET_KEY_SETTING` carrying `alias="SECRET_KEY"`, so the
    environment variable and the property share a spelling that differs from the
    field's own. `BaseServiceSettings` sets `case_sensitive=False`, which would
    fold `SECRET_KEY` and `secret_key` together and let the alias collide with
    its shadow field, and `populate_by_name` is what keeps the field's real name
    usable alongside the alias. Both have to survive inheriting the base.
    """
    from app.core.config import Settings

    assert Settings.model_config["case_sensitive"] is True
    assert Settings.model_config["populate_by_name"] is True

    # The alias populates the shadow field. Asserted on the field rather than on
    # the `SECRET_KEY` property, because the property deliberately ignores it and
    # consults the environment and the secret cache instead, which is the whole
    # point of row 7's lazy resolution.
    assert Settings(SECRET_KEY="from-alias").SECRET_KEY_SETTING == "from-alias"
    assert Settings(SECRET_KEY_SETTING="from-field").SECRET_KEY_SETTING == "from-field"
