from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.core.config import settings


def test_read_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CarModPicker API"
    assert data["status"] == "running"


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint for monitoring (liveness)."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CarModPicker API"
    assert "version" in data


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint (DB reachable)."""
    response = client.get("/ready")
    # With test DB, should return 200 when DB is ready
    assert response.status_code in (200, 503)
    data = response.json()
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert data["database"] == "up"
    else:
        assert "database" in data or "message" in data


# Moved here from `tests/test_lambda_handler.py` when row 32 retired the monolith.
# That file's other two tests were Mangum's, and Mangum went with the zip; this
# one is `app/main.py`'s and `app/main.py` survives, so it moves rather than
# being deleted with its old neighbours. The patch point is the module attribute
# `app.main.run_startup_tasks`, which is why `app/composition/app.py` imports
# `app.main` inside the lifespan rather than capturing a reference at build time.
@pytest.mark.parametrize("run_startup_tasks", [True, False])
def test_lifespan_honors_run_startup_tasks(monkeypatch: pytest.MonkeyPatch, run_startup_tasks: bool) -> None:
    monkeypatch.setattr(settings, "RUN_STARTUP_TASKS", run_startup_tasks)
    with patch.object(main_module, "run_startup_tasks") as startup:
        with TestClient(main_module.app):
            pass
    assert startup.called is run_startup_tasks
