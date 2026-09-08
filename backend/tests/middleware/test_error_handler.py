"""Tests for the error envelope every error response in this API carries.

These used to call the handler functions directly. They now drive a real app,
because the handlers live in the shared `webbpulse` package and what matters to
CarModPicker is the body that reaches the caller, not which function built it.
The envelope is `{success, status, message, request_id}` plus `error_code`, and
`details` where a route attaches structured information.
"""

from typing import Any, Dict

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.request_context import request_context_middleware
from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

#: The four fields every error body must carry, whatever produced it.
ENVELOPE_KEYS = {"success", "status", "message", "request_id"}


class _Payload(BaseModel):
    name: str
    count: int


@pytest.fixture
def envelope_app() -> TestClient:
    """A minimal app carrying the same middleware and handlers the real one does."""
    app = FastAPI()
    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)

    @app.get("/boom-4xx")
    def boom_4xx() -> None:
        raise HTTPException(status_code=403, detail="You may not do that")

    @app.get("/boom-5xx")
    def boom_5xx() -> None:
        raise HTTPException(status_code=500, detail="secret internal detail")

    @app.get("/boom-structured")
    def boom_structured() -> None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "You already have one of those.",
                "error_code": "PART_ALREADY_EXISTS",
                "details": {"existing_part_id": "abc123"},
            },
        )

    @app.get("/boom-unhandled")
    def boom_unhandled() -> None:
        raise RuntimeError("a leaked stack trace would be bad")

    @app.get("/boom-item-not-found")
    def boom_item_not_found() -> None:
        raise ItemNotFound("parts", {"id": "abc"})

    @app.get("/boom-condition-failed")
    def boom_condition_failed() -> None:
        raise ConditionFailed("parts", "attribute_not_exists(id)", {"id": "abc"})

    @app.get("/boom-txn-conflict")
    def boom_txn_conflict() -> None:
        raise TransactionCanceled([{"Code": "ConditionalCheckFailed"}])

    @app.get("/boom-txn-fault")
    def boom_txn_fault() -> None:
        raise TransactionCanceled([{"Code": "ValidationError"}])

    @app.post("/validate")
    def validate(payload: _Payload) -> Dict[str, str]:
        return {"name": payload.name}

    return TestClient(app, raise_server_exceptions=False)


def assert_envelope(body: Dict[str, Any], status_code: int) -> None:
    """Every error body carries the four base fields, with a real request id."""
    assert ENVELOPE_KEYS <= set(body), f"missing envelope keys: {ENVELOPE_KEYS - set(body)}"
    assert body["success"] is False
    assert body["status"] == status_code
    assert isinstance(body["message"], str) and body["message"]
    # "-" is the placeholder the package uses when no middleware set an id, so a
    # real value here is what proves the request-context bridge is wired up.
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"
    # The old raw Starlette shape must be gone everywhere.
    assert "detail" not in body


class TestErrorEnvelope:
    def test_4xx_keeps_its_message_and_code(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-4xx")
        assert response.status_code == 403
        body = response.json()
        assert_envelope(body, 403)
        assert body["message"] == "You may not do that"
        assert body["error_code"] == "FORBIDDEN"

    def test_5xx_is_sanitised(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-5xx")
        assert response.status_code == 500
        body = response.json()
        assert_envelope(body, 500)
        assert "secret internal detail" not in response.text
        assert body["error_code"] == "INTERNAL_ERROR"

    def test_unhandled_exception_leaks_nothing(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-unhandled")
        assert response.status_code == 500
        body = response.json()
        assert_envelope(body, 500)
        assert "a leaked stack trace would be bad" not in response.text
        assert body["error_code"] == "INTERNAL_ERROR"

    def test_structured_detail_carries_route_code_and_details(self, envelope_app: TestClient) -> None:
        """A route's own `error_code` and `details` survive into the envelope."""
        response = envelope_app.get("/boom-structured")
        assert response.status_code == 409
        body = response.json()
        assert_envelope(body, 409)
        assert body["message"] == "You already have one of those."
        assert body["error_code"] == "PART_ALREADY_EXISTS"
        assert body["details"] == {"existing_part_id": "abc123"}

    def test_validation_error_has_flat_field_details(self, envelope_app: TestClient) -> None:
        response = envelope_app.post("/validate", json={})
        assert response.status_code == 422
        body = response.json()
        assert_envelope(body, 422)
        assert body["error_code"] == "VALIDATION_ERROR"
        fields = {entry["field"] for entry in body["details"]}
        # The "body" prefix is dropped, so the caller sees the field it sent.
        assert fields == {"name", "count"}
        for entry in body["details"]:
            assert set(entry) == {"field", "message", "type"}

    def test_validation_error_never_echoes_the_input(self, envelope_app: TestClient) -> None:
        """A rejected value could be a password, so it must not come back."""
        response = envelope_app.post("/validate", json={"name": "n", "count": "hunter2"})
        assert response.status_code == 422
        assert "hunter2" not in response.text


class TestDynamoEnvelope:
    """CarModPicker's own repository exceptions render the same envelope."""

    def test_item_not_found_is_404(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-item-not-found")
        assert response.status_code == 404
        body = response.json()
        assert_envelope(body, 404)
        assert body["error_code"] == "NOT_FOUND"
        # The table name and key are logged, never returned.
        assert "parts" not in response.text

    def test_condition_failed_is_409(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-condition-failed")
        assert response.status_code == 409
        body = response.json()
        assert_envelope(body, 409)
        assert body["error_code"] == "CONFLICT"

    def test_transaction_cancelled_by_condition_is_409(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/boom-txn-conflict")
        assert response.status_code == 409
        body = response.json()
        assert_envelope(body, 409)
        assert body["error_code"] == "CONFLICT"

    def test_transaction_cancelled_for_another_reason_is_500(self, envelope_app: TestClient) -> None:
        """Only a failed condition is a conflict; anything else is a real fault."""
        response = envelope_app.get("/boom-txn-fault")
        assert response.status_code == 500
        body = response.json()
        assert_envelope(body, 500)
        assert body["error_code"] == "INTERNAL_ERROR"


class TestRoutingErrors:
    """The shape that used to escape as raw `{"detail": "Not Found"}`."""

    def test_unknown_path_returns_the_envelope(self, envelope_app: TestClient) -> None:
        response = envelope_app.get("/no/such/route")
        assert response.status_code == 404
        body = response.json()
        assert_envelope(body, 404)
        assert body["error_code"] == "NOT_FOUND"
        assert body != {"detail": "Not Found"}

    def test_wrong_method_returns_the_envelope(self, envelope_app: TestClient) -> None:
        response = envelope_app.delete("/boom-4xx")
        assert response.status_code == 405
        body = response.json()
        assert_envelope(body, 405)
        assert body["error_code"] == "METHOD_NOT_ALLOWED"
