"""The repository exceptions' rendering, pinned field by field.

`ItemNotFound` and `ConditionFailed` are declared to `webbpulse` as an
`exception_map` rather than handled here, and `TransactionCanceled` keeps a
hand-written handler because its status depends on the cancellation reason.
These tests assert the bodies all three produce, so moving a handler into the
package cannot change what a caller receives.
"""

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient
from webbpulse.http import ErrorSpec

from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.request_context import request_context_middleware
from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

#: The exact body each case must produce, `request_id` aside. Spelled out as
#: whole dicts rather than field assertions so an extra or a renamed key fails
#: too, which is the thing a handler swap could silently change.
NOT_FOUND_BODY = {
    "success": False,
    "status": 404,
    "message": "Resource not found",
    "error_code": "NOT_FOUND",
}
CONFLICT_BODY = {
    "success": False,
    "status": 409,
    "message": "Resource already exists or was modified concurrently",
    "error_code": "CONFLICT",
}
INTERNAL_BODY = {
    "success": False,
    "status": 500,
    "message": "Internal server error",
    "error_code": "INTERNAL_ERROR",
}


def assert_body(body: Dict[str, Any], expected: Dict[str, Any]) -> None:
    """The whole envelope, with a real request id and nothing else besides."""
    assert body.keys() == expected.keys() | {"request_id"}
    assert {key: body[key] for key in expected} == expected
    # "-" is the placeholder the package uses when no middleware set an id.
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"
    # The raw Starlette shape must not reappear alongside the envelope.
    assert "detail" not in body


def build_app() -> FastAPI:
    app = FastAPI()
    # The request id middleware is what fills the envelope's `request_id`, so it
    # belongs here too or every body would carry the "-" placeholder.
    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        raise ItemNotFound("test-users", {"id": "abc"})

    @app.get("/duplicate")
    def duplicate() -> None:
        raise ConditionFailed("test-users", "attribute_not_exists(id)", {"id": "abc"})

    @app.get("/canceled-conditional")
    def canceled_conditional() -> None:
        raise TransactionCanceled([{"Code": "None"}, {"Code": "ConditionalCheckFailed"}])

    @app.get("/canceled-other")
    def canceled_other() -> None:
        raise TransactionCanceled([{"Code": "TransactionConflict"}])

    return app


def test_item_not_found_maps_to_404() -> None:
    """Mapped by `exception_map`; the table name and key are logged, not returned."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/missing")
    assert response.status_code == 404
    assert_body(response.json(), NOT_FOUND_BODY)
    assert "test-users" not in response.text


def test_condition_failed_maps_to_409() -> None:
    """Mapped by `exception_map`; the DynamoDB condition never reaches the caller."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/duplicate")
    assert response.status_code == 409
    assert_body(response.json(), CONFLICT_BODY)
    assert "attribute_not_exists" not in response.text


def test_conditional_transaction_cancel_maps_to_409() -> None:
    """A cancellation caused by a failed condition reads as an ordinary lost race."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-conditional")
    assert response.status_code == 409
    assert_body(response.json(), CONFLICT_BODY)


def test_other_transaction_cancel_maps_to_500() -> None:
    """Anything else is a real fault, which is why this one is not in `exception_map`."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-other")
    assert response.status_code == 500
    assert_body(response.json(), INTERNAL_BODY)
    assert "TransactionConflict" not in response.text


def test_exception_map_declares_the_two_constant_renderings() -> None:
    """The map is the contract; `TransactionCanceled` must stay out of it.

    Putting it in would flatten a real fault into a 409, so this asserts the
    absence as deliberately as it asserts the two entries.
    """
    from app.api.middleware.error_handler import DYNAMO_EXCEPTION_MAP

    assert set(DYNAMO_EXCEPTION_MAP) == {ItemNotFound, ConditionFailed}
    assert TransactionCanceled not in DYNAMO_EXCEPTION_MAP

    not_found = DYNAMO_EXCEPTION_MAP[ItemNotFound]
    assert isinstance(not_found, ErrorSpec)
    assert (not_found.status, not_found.message, not_found.error_code) == (
        404,
        NOT_FOUND_BODY["message"],
        NOT_FOUND_BODY["error_code"],
    )

    conflict = DYNAMO_EXCEPTION_MAP[ConditionFailed]
    assert isinstance(conflict, ErrorSpec)
    assert (conflict.status, conflict.message, conflict.error_code) == (
        409,
        CONFLICT_BODY["message"],
        CONFLICT_BODY["error_code"],
    )
