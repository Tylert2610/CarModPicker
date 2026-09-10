"""Root A: all nine domains in one process.

This is what local development, `docker-compose`, the Lambda the monolith still
runs, and the entire existing test suite run against. Root B is
`app.entrypoints.<domain>`, one module per deployed function, and both are built
from the same descriptors by the same `build_domain_app`, so neither can drift
from the other.

`app/main.py` takes its `app` from here, which is what makes the existing suite
exercise the new wiring rather than a parallel copy of it. The OpenAPI document
this produces is byte identical to the one `app/main.py` produced before, and
`tests/test_openapi_snapshot.py` is the test that says so; it was not touched by
this PR.

## What changed and what did not

The routers, their prefixes and their tags are the ones `EndpointRegistry`
applied. The middleware stack, the exception handlers, the CORS policy, the
lifespan and the five root routes moved from `app/main.py` into
`app.composition.wiring` unchanged, so that Root B gets them too.

The one real change is order. `app/main.py` registered the endpoint modules
interleaved by kind (users, car-generations, build-lists, parts, ...) and this
root registers them grouped by domain. That moves modules past each other, and
it is safe here because no route in any domain matches a concrete path belonging
to a different domain: every ordering hazard section 1.4 lists is inside a
single module, decided by that module's own decorator order, which this PR does
not touch. The OpenAPI document is unaffected because it is serialised with
sorted keys.

## Why this is not `mount`

Composition is `include_router`, never `mount`. Starlette strips a mount path
before the sub-application sees it, so a `/api/parts` application mounted at
`/api/parts` would see `/api/parts/api/parts/...` and 404 on every route, and a
mounted sub-application contributes nothing to the parent's OpenAPI document,
which would empty the published contract. Both roots therefore produce identical
paths, which is what `tests/entrypoints/test_route_split.py` compares.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from app.composition.domains import DOMAINS
from app.composition.wiring import configure_logging

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI


def _startup_tasks() -> None:
    """Call `app.main.run_startup_tasks`, looked up at startup rather than bound.

    `tests/test_main.py::test_lifespan_honors_run_startup_tasks` patches
    `app.main.run_startup_tasks` and
    asserts the lifespan honours `settings.RUN_STARTUP_TASKS`. Going through the
    module attribute here, at the moment the lifespan runs, is what lets that
    patch take effect; a reference captured when the application was built would
    have been taken before the patch existed.

    The import is inside the function because `app.main` imports this module.
    """
    from app import main

    main.run_startup_tasks()


def build_app(startup_tasks: Optional[Callable[[], None]] = None) -> "FastAPI":
    """Every domain's routers, plus the five root routes, on one application.

    Called once, at the bottom of this module. `app/main.py` re-exports the
    result rather than calling this again, so there is exactly one Root A
    application per process.
    """
    from app.composition.wiring import build_domain_app

    return build_domain_app(
        list(DOMAINS.values()),
        startup_tasks=startup_tasks if startup_tasks is not None else _startup_tasks,
    )


# Logging is configured at import, as `app/main.py` has always done it, because
# the deployed monolith imports this module and never calls a `main()`.
configure_logging()

# Sentry must be initialised BEFORE the FastAPI application is constructed, so
# FastApiIntegration and StarletteIntegration can patch the route handlers. It
# no-ops in development and in tests; see `init_sentry`'s env gates. D-12.
from app.core.sentry import init_sentry  # noqa: E402  — ordering is the point

init_sentry(server_name="apprunner-backend")

# `check_signing_key` is deliberately NOT called here, and is no longer imported.
# It reads `settings.SECRET_KEY`, which resolves through Secrets Manager on first
# read, so calling it at module scope made importing this module fetch the
# secret, which is the one thing every composition root must not do. It moved
# into `build_domain_app`'s lifespan, where it runs once per startup for both
# roots, before any request and ahead of the first `jwt.encode`.

app = build_app()
