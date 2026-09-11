"""The users domain's entrypoint.

User accounts and the global app settings singleton: 14 routes under
`/api/users` and `/api/app-settings`.

Every route is behind `get_current_user` or `get_current_admin_user`. Since
row 13 both resolve an identity access token, verified by the API Gateway JWT
authorizer against the issuer's JWKS, so this domain needs no application
secret and does not name `SECRET_KEY`.

Run by the image as `python -m app.entrypoints.users`. `handler` is the
Lambda entry point and is still Mangum, which is what `app/lambda_handler.py`
uses today; the Lambda Web Adapter switch is a later PR in the plan and changing
the adapter here would make this slice about two things at once.

`build_app` is importable on its own and reads no AWS, which is what lets the
tests build this application with no credentials and no network. Only `main`
configures logging and tracing, because those are process-wide effects a test
importing the module must not inherit.

Logging and tracing come from the shared `webbpulse` package, and tracing is
live: Terraform sets `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` on this function and
grants `xray:PutSpans`, so `main` builds a real tracer provider and spans are
exported to the X-Ray OTLP endpoint. Sampling is tail based, so errors are kept
whatever `WEBBPULSE_OTEL_SAMPLE_RATIO` says. `configure_tracing` still returns
early when the variable is unset, which is what keeps a test or a local run
free of an exporter.

Sentry is not initialised here. Row 16 of the split plan replaced it with
OpenTelemetry in the domain functions. The monolith still serving production
keeps Sentry until row 31 retires it.
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

DOMAIN = DOMAINS["users"]


def build_app() -> "FastAPI":
    """This domain's routers and the five root routes, and nothing else."""
    return build_domain_app(DOMAIN, title=DOMAIN.title)


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    # Logging first: `configure_tracing` logs its own warnings, and they are
    # worth having in the shared JSON format rather than in whatever the root
    # logger defaulted to.
    configure_logging(service=DOMAIN.service_name)
    # Tracing before the application is built, because the provider has to exist
    # by the time `build_domain_app` decides whether to instrument. Terraform
    # sets OTEL_EXPORTER_OTLP_TRACES_ENDPOINT on this function, so this is a
    # real provider here and still a no-op in a test or a local run, where the
    # variable is unset.
    configure_tracing(DOMAIN)
    check_signing_key([DOMAIN])
    # Built here rather than reusing the module-level `app`, and that is the
    # whole reason this line exists. The module-level `app` below is
    # constructed at import, which is before `configure_tracing` has run, so
    # `build_domain_app` saw tracing off and attached no instrumentation to it.
    # Rebuilding after the provider exists is what gets the server span
    # middleware installed; `instrument_app` can only inject it while the
    # middleware stack is still unbuilt, so an already-serving application
    # cannot be instrumented after the fact. Sentry used to be initialised
    # here and is gone: this function reports through OpenTelemetry now, and
    # only the monolith's composition root still calls `init_sentry`.
    #
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
