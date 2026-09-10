"""The whole-API application: local development, and the suite's Root A.

Row 32 retired the monolith Lambda, so nothing deploys this module any more.
It stays because it is still the application `uvicorn app.main:app` serves for
local development, and because it is Root A in the route-contract tests: the
partition check in `tests/entrypoints/test_route_split.py` asserts that the
union of the nine per-domain applications equals this one, which is the test
that would catch a router going missing from a domain descriptor. Delete this
and that check has nothing to compare against.


Everything this module used to do by hand now lives in `app.composition`:
`app.composition.domains` names the nine domains and the routers each owns, and
`app.composition.wiring.build_domain_app` assembles the middleware, the
exception handlers, the CORS policy, the lifespan and the five root routes.
Root A (`app.composition.app`) calls that with all nine descriptors, Root B
(`app.entrypoints.<domain>`) with one.

This module re-exports Root A's application rather than building its own. That
matters beyond tidiness: building a second one would give two full FastAPI
instances in every process that imports both, doubling the import cost of a
cold start and making `app.main.app` and `app.composition.app.app` different
objects, so which one a caller saw would depend on how it imported.

`uvicorn app.main:app` and every `from app.main import app` in the suite keep
working unchanged, and the OpenAPI document is byte identical to what it was.
`app/lambda_handler.py` was the third caller and row 32 deleted it with the
function it was the entrypoint for.

`run_startup_tasks` stays a module attribute here because
`tests/test_main.py::test_lifespan_honors_run_startup_tasks` patches
`app.main.run_startup_tasks` and asserts the lifespan honours
`settings.RUN_STARTUP_TASKS`. The lifespan reaches it through this module at
startup rather than holding a reference taken when the application was built,
which is what lets the patch take effect. That test lived in
`tests/test_lambda_handler.py` until row 32 and moved rather than being
retired, because what it covers is this module and not the monolith.
"""

from app.composition.app import app
from app.composition.wiring import run_startup_tasks as _run_startup_tasks


def run_startup_tasks() -> None:
    """Seed the car generation tables on startup. Patched by the suite."""
    _run_startup_tasks()


__all__ = ["app", "run_startup_tasks"]
