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
configures logging and initialises Sentry, because those are process-wide
effects a test importing the module must not inherit.
"""

from typing import TYPE_CHECKING

from mangum import Mangum

from app.composition.domains import DOMAINS
from app.composition.wiring import build_domain_app, check_signing_key, configure_logging

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

DOMAIN = DOMAINS["vehicles"]


def build_app() -> "FastAPI":
    """This domain's routers and the five root routes, and nothing else."""
    return build_domain_app(DOMAIN, title=DOMAIN.title)


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    import uvicorn

    from app.core.config import settings
    from app.core.sentry import init_sentry

    configure_logging()
    # Before the application is built, so the Sentry integrations can patch the
    # route handlers.
    init_sentry(server_name=DOMAIN.service_name)
    check_signing_key([DOMAIN])
    uvicorn.run(build_app(), host="0.0.0.0", port=settings.PORT)  # nosec B104


app = build_app()

# Mangum, matching `app/lambda_handler.py`. `lifespan="off"` for the same reason
# it is off there: Lambda gives no shutdown hook, and the startup work this
# domain does, if any, is idempotent and better driven by the seed job.
handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    main()
