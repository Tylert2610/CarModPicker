import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.core.config import settings


def api_gateway_v2_event(path: str, method: str = "GET") -> dict[str, Any]:
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "api.example.com", "user-agent": "pytest"},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "domainName": "api.example.com",
            "domainPrefix": "api",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "request-id",
            "routeKey": "$default",
            "stage": "$default",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1767225600000,
        },
        "isBase64Encoded": False,
    }


def lambda_context() -> SimpleNamespace:
    return SimpleNamespace(
        aws_request_id="request-id",
        function_name="carmodpicker-api",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-west-2:123456789012:function:carmodpicker-api",
        memory_limit_in_mb=512,
        log_group_name="/aws/lambda/carmodpicker-api",
        log_stream_name="stream",
        get_remaining_time_in_millis=lambda: 30000,
    )


def test_handler_serves_health_check() -> None:
    from app.lambda_handler import handler

    response = handler(api_gateway_v2_event("/health"), lambda_context())

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "healthy"
    assert body["service"] == "CarModPicker API"


def test_handler_returns_404_for_unknown_route() -> None:
    from app.lambda_handler import handler

    response = handler(api_gateway_v2_event("/definitely-not-a-route"), lambda_context())

    assert response["statusCode"] == 404
    # The envelope, not Starlette's raw `{"detail": "Not Found"}`: an unmatched
    # route is the one place that shape used to escape.
    body = json.loads(response["body"])
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 404
    assert body["error_code"] == "NOT_FOUND"
    assert body["request_id"] != "-"


@pytest.mark.parametrize("run_startup_tasks", [True, False])
def test_lifespan_honors_run_startup_tasks(monkeypatch: pytest.MonkeyPatch, run_startup_tasks: bool) -> None:
    monkeypatch.setattr(settings, "RUN_STARTUP_TASKS", run_startup_tasks)
    with patch.object(main_module, "run_startup_tasks") as startup:
        with TestClient(main_module.app):
            pass
    assert startup.called is run_startup_tasks
