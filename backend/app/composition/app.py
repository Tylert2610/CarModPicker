"""Root A: all nine domains on one application, built by `build_domain_app`.

Composition is `include_router` and never `mount`, so both roots produce
identical paths and the same OpenAPI document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from app.composition.domains import DOMAINS
from app.composition.wiring import configure_logging

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI


def _startup_tasks() -> None:
    """Call `app.main.run_startup_tasks`, looked up at startup rather than bound.

    Going through the module attribute at lifespan time is what lets the suite's
    patch take effect. The import is deferred because `app.main` imports this.
    """
    from app import main

    main.run_startup_tasks()


def build_app(startup_tasks: Optional[Callable[[], None]] = None) -> "FastAPI":
    """Every domain's routers, plus the five root routes, on one application.

    Called once at the bottom of this module; `app/main.py` re-exports the result
    so there is exactly one Root A application per process.
    """
    from app.composition.wiring import build_domain_app

    return build_domain_app(
        list(DOMAINS.values()),
        startup_tasks=startup_tasks if startup_tasks is not None else _startup_tasks,
    )


configure_logging()

from app.core.sentry import init_sentry  # noqa: E402

init_sentry(server_name="apprunner-backend")


app = build_app()
