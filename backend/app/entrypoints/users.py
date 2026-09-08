"""The users domain's entrypoint.

User accounts and the global app settings singleton: 14 routes under
`/api/users` and `/api/app-settings`.

Every route is behind `get_current_user` or `get_current_admin_user`, both of
which decode a token, so this domain needs `SECRET_KEY`.

Run by the image as `python -m app.entrypoints.users`. `handler` is the
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

DOMAIN = DOMAINS["users"]


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
