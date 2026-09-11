"""The whole-API application, re-exported from Root A rather than built again.

Nothing deploys this module; it is what `uvicorn app.main:app` serves locally
and what the route-partition test compares the nine per-domain apps against.
"""

from app.composition.app import app
from app.composition.wiring import run_startup_tasks as _run_startup_tasks


def run_startup_tasks() -> None:
    """Seed the car generation tables on startup. Patched by the suite."""
    _run_startup_tasks()


__all__ = ["app", "run_startup_tasks"]
