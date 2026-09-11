"""The admin domain's entrypoint, run as `python -m app.entrypoints.admin`.

Price-drop alerts, the Chrome extension page parser and the two admin
modules: 12 routes. Needs `SECRET_KEY`.
"""

from typing import TYPE_CHECKING

from mangum import Mangum

from app.composition.domains import DOMAINS
from app.composition.wiring import (
    build_domain_app,
    check_signing_key,
    configure_logging,
    configure_tracing,
)

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI

DOMAIN = DOMAINS["admin"]


def build_app() -> "FastAPI":
    """This domain's routers and the five root routes, and nothing else."""
    return build_domain_app(DOMAIN, title=DOMAIN.title)


def main() -> None:
    """Configure logging and tracing process-wide, then serve the application.

    Tracing is configured before the app is built so the server span middleware
    can still be injected into an unbuilt middleware stack.
    """
    from webbpulse.lambda_entry import run_uvicorn

    configure_logging(service=DOMAIN.service_name)
    configure_tracing(DOMAIN)
    check_signing_key([DOMAIN])
    # No init_sentry here: these functions report through OpenTelemetry.
    run_uvicorn(build_app())


app = build_app()

handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    main()
