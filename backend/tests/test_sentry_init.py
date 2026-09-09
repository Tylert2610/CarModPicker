"""OBS-01 unit + integration coverage for backend Sentry init.

Decision refs: 02-CONTEXT.md D-01..D-15, D-49. Landmine refs: 02-RESEARCH.md
§5 Landmine 1 (ignore_errors strings), Landmine 2 (StarletteIntegration
MUST be explicit), Landmine 3 (capture_envelope 2.x API), Landmine 16
(init is process-global; fixture tears down client).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from webbpulse.log_context import request_id_var, user_id_var

from app.core.sentry import _before_send, _traces_sampler, init_sentry


class TestInitGating:
    """D-01, D-13: init_sentry must no-op on three gate conditions."""

    def test_testing_true_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "true")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0

    def test_wrong_environment_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "development")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0

    def test_empty_dsn_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("SENTRY_DSN", "")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "staging")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0


class TestInitKwargs:
    """D-02, D-03, D-06, D-07, D-08, D-11: kwargs shape when init fires."""

    @pytest.fixture
    def active_init(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("SENTRY_DSN", "http://key@localhost/1")
        monkeypatch.setenv("SENTRY_RELEASE", "abc123")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "staging")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 1
        return mock_init

    def test_send_default_pii_false(self, active_init: MagicMock) -> None:
        kwargs = active_init.call_args.kwargs
        assert kwargs["send_default_pii"] is False

    def test_server_name_passed(self, active_init: MagicMock) -> None:
        assert active_init.call_args.kwargs["server_name"] == "apprunner-backend"

    def test_release_from_env(self, active_init: MagicMock) -> None:
        assert active_init.call_args.kwargs["release"] == "abc123"

    def test_environment_tag(self, active_init: MagicMock) -> None:
        assert active_init.call_args.kwargs["environment"] == "staging"

    def test_traces_sampler_is_callable(self, active_init: MagicMock) -> None:
        assert callable(active_init.call_args.kwargs["traces_sampler"])

    def test_ignore_errors_strings(self, active_init: MagicMock) -> None:
        """Landmine 1: ignore_errors uses STRING class names in 2.x (not class refs)."""
        ignore = active_init.call_args.kwargs["ignore_errors"]
        assert "fastapi.exceptions.HTTPException" in ignore
        assert "starlette.exceptions.HTTPException" in ignore
        # slowapi entry is defensive — rate_limiter.py currently returns JSONResponse
        # directly rather than raising, but this future-proofs the suppression.
        assert "slowapi.errors.RateLimitExceeded" in ignore

    def test_all_three_integrations_loaded(self, active_init: MagicMock) -> None:
        """Landmine 2: StarletteIntegration MUST be explicit — it is NOT auto-enabled
        by FastApiIntegration despite what some older docs claim."""
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations = active_init.call_args.kwargs["integrations"]
        types = {type(i) for i in integrations}
        assert StarletteIntegration in types
        assert FastApiIntegration in types
        assert LoggingIntegration in types


class TestTracesSampler:
    """D-06: traces_sampler returns 0.0 for health noise, 0.05 otherwise."""

    @pytest.mark.parametrize("path", ["/health", "/ready", "/openapi.json", "health_check", "api/ready", "openapi"])
    def test_health_routes_zero(self, path: str) -> None:
        assert _traces_sampler({"transaction_context": {"name": path}}) == 0.0

    @pytest.mark.parametrize("path", ["/api/users/me", "users.read_user_by_id", "/api/cars/1"])
    def test_real_routes_sampled(self, path: str) -> None:
        assert _traces_sampler({"transaction_context": {"name": path}}) == 0.05

    def test_empty_name_sampled(self) -> None:
        """Missing / empty transaction name falls through to default sample rate."""
        assert _traces_sampler({}) == 0.05


class TestBeforeSend:
    """D-09: scope processor attaches request_id + user_id from ContextVars."""

    def test_attaches_request_id_when_set(self) -> None:
        token = request_id_var.set("abc-123")
        try:
            event = _before_send({}, None)
            assert event["tags"]["request_id"] == "abc-123"
        finally:
            request_id_var.reset(token)

    def test_attaches_user_id_when_set(self) -> None:
        token = user_id_var.set("42")
        try:
            event = _before_send({}, None)
            assert event["user"]["id"] == "42"
        finally:
            user_id_var.reset(token)

    def test_no_tag_when_default(self) -> None:
        """When ContextVars still hold sentinel '-', neither tag nor user is added."""
        event = _before_send({}, None)
        assert "tags" not in event or "request_id" not in event.get("tags", {})
        assert "user" not in event or "id" not in event.get("user", {})


class TestIgnoreErrorsIntegration:
    """Full-SDK integration: raise HTTPException and confirm no envelope captured."""

    def test_http_exception_not_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Landmine 1 runtime gate: if this fails, the string form of ignore_errors
        isn't matching on this SDK version — switch to class refs in sentry.py."""
        import sentry_sdk

        from tests.conftest import _CapturingTransport

        sentry_sdk.init(
            dsn="http://key@localhost/1",
            transport=_CapturingTransport,
            ignore_errors=[
                "fastapi.exceptions.HTTPException",
                "starlette.exceptions.HTTPException",
            ],
        )
        _CapturingTransport.events = []

        from fastapi import HTTPException

        try:
            raise HTTPException(status_code=404, detail="not found")
        except HTTPException as exc:
            sentry_sdk.capture_exception(exc)

        assert len(_CapturingTransport.events) == 0, (
            "HTTPException leaked to Sentry — ignore_errors string format "
            "not working on this SDK version (Landmine 1)"
        )
        client = sentry_sdk.get_client()
        if client is not None:
            client.close()

    def test_runtime_error_captured(self, sentry_events) -> None:
        """Control: ensure the transport works in principle. Without this, a
        broken transport could silently make `test_http_exception_not_captured`
        pass for the wrong reason."""
        import sentry_sdk

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            sentry_sdk.capture_exception(exc)
        sentry_sdk.flush(timeout=2.0)
        # sentry_events fixture uses passthrough before_send; envelope should land
        # on the shared _CapturingTransport.events list after flush.
        from tests.conftest import _CapturingTransport

        assert len(_CapturingTransport.events) >= 1 or len(sentry_events) >= 1
