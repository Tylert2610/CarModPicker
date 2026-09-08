from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.request_context import request_context_middleware
from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled


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
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/missing")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["status"] == 404
    assert body["message"] == "Resource not found"
    assert body["error_code"] == "NOT_FOUND"
    assert body["request_id"] != "-"


def test_condition_failed_maps_to_409() -> None:
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/duplicate")
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "CONFLICT"


def test_conditional_transaction_cancel_maps_to_409() -> None:
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-conditional")
    assert response.status_code == 409
    assert response.json()["error_code"] == "CONFLICT"


def test_other_transaction_cancel_maps_to_500() -> None:
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-other")
    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["status"] == 500
    assert body["message"] == "Internal server error"
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["request_id"] != "-"
