"""The vehicles domain's entrypoint.

Car makes, models and generations, plus the unified search: 11 routes under
`/api/car-generations` and `/api/search`.

The one domain that needs no secret. Every route is a public read:
`car_generations` builds its `BaseDynamoEndpointRouter` with the writing
endpoints disabled, so the generated routes that would depend on
`get_current_user` are never registered. That is what lets this function run
with no `secretsmanager:GetSecretValue` grant at all, and it is the
least-privilege claim the split rests on.

It is also the domain that seeds: `init_car_generations` writes the car tables
on startup, and its descriptor is the only one setting `seeds`.

Run by the image as `python -m app.entrypoints.vehicles`. `handler` is the
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

DOMAIN = DOMAINS["vehicles"]


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
