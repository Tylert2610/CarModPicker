"""The application the monolith Lambda and local development serve.

Everything this module used to do by hand now lives in `app.composition`:
`app.composition.domains` names the nine domains and the routers each owns, and
`app.composition.wiring.build_domain_app` assembles the middleware, the
exception handlers, the CORS policy, the lifespan and the five root routes.
Root A (`app.composition.app`) calls that with all nine descriptors, Root B
(`app.entrypoints.<domain>`) with one, and this module simply re-exports Root A's
application so the existing test suite exercises the new wiring rather than a
parallel copy of it.

`uvicorn app.main:app`, `app/lambda_handler.py` and every `from app.main import
app` in the suite keep working unchanged, and the OpenAPI document is byte
identical to what it was.

`run_startup_tasks` stays a module attribute here, and is handed to the builder
rather than looked up inside it, because `tests/test_lambda_handler.py` patches
`app.main.run_startup_tasks` and asserts the lifespan honours
`settings.RUN_STARTUP_TASKS`. Threading it through keeps that seam where the
test expects it.
"""

from app.composition import app as composition_root
from app.composition.wiring import run_startup_tasks as _run_startup_tasks


def run_startup_tasks() -> None:
    """Seed the car generation tables on startup. Patched by the suite."""
    _run_startup_tasks()


app = composition_root.build_app(startup_tasks=lambda: run_startup_tasks())
