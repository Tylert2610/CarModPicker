"""The catalog domain's entrypoint.

Parts, manufacturers, categories and retailers: 43 routes, the largest domain.

Seventeen of them verify a token, so the domain needs `SECRET_KEY`. Two do not
and are mutating: `POST /api/parts/{part_id}/listings` and
`POST /api/parts/price-history` take no user dependency at all. Section 1.1 of
the split plan flags both, and they should be settled on their own before this
domain is cut, not as part of the cut.

Run by the image as `python -m app.entrypoints.catalog`. `handler` is the
Lambda entry point and is still Mangum, which is what `app/lambda_handler.py`
uses today; the Lambda Web Adapter switch is a later PR in the plan and changing
the adapter here would make this slice about two things at once.

`build_app` is importable on its own and reads no AWS, which is what lets the
tests build this application with no credentials and no network. Only `main`
configures logging, tracing and Sentry, because those are process-wide effects
a test importing the module must not inherit.

Logging and tracing come from the shared `webbpulse` package. Tracing is wired
but inert: `configure_tracing` returns early unless
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set, and nothing sets it yet, because
this domain has no OTLP IAM grant. Row 16 of the split plan turns it on.
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

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

DOMAIN = DOMAINS["catalog"]


def build_app() -> "FastAPI":
    """This domain's routers and the five root routes, and nothing else."""
    return build_domain_app(DOMAIN, title=DOMAIN.title)


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    from app.core.sentry import init_sentry

    # Logging first: `configure_tracing` logs its own warnings, and they are
    # worth having in the shared JSON format rather than in whatever the root
    # logger defaulted to.
    configure_logging(service=DOMAIN.service_name)
    # A no-op unless OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is set, which nothing
    # sets today. See `configure_tracing` in `app.composition.wiring`: row 16 of
    # the split plan is what turns this on, per domain.
    configure_tracing(DOMAIN)
    # Before the application is built, so the Sentry integrations can patch the
    # route handlers. Sentry stays until row 16 replaces it with OpenTelemetry.
    init_sentry(server_name=DOMAIN.service_name)
    check_signing_key([DOMAIN])
    # `run_uvicorn` binds AWS_LWA_PORT, then PORT, then 8080, which is the
    # Web Adapter's own precedence. Binding a port the adapter is not polling
    # presents as the readiness check never passing, with no application logs
    # at all, so the precedence is worth taking from the package rather than
    # reimplementing against settings.PORT.
    run_uvicorn(build_app())


app = build_app()

# Mangum, matching `app/lambda_handler.py`. `lifespan="off"` for the same reason
# it is off there: Lambda gives no shutdown hook, and the startup work this
# domain does, if any, is idempotent and better driven by the seed job.
handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    main()
