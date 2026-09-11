"""The catalog domain's `votes` stream consumer.

A FastAPI app because the base image's Lambda Web Adapter is the runtime and POSTs
non-HTTP events to `AWS_LWA_PASS_THROUGH_PATH`.
"""

from typing import Any, Dict, List

from fastapi import FastAPI, Request

from app.composition.domains import DOMAINS
from app.composition.wiring import (
    add_root_routes,
    configure_logging,
    configure_tracing,
)

DOMAIN = DOMAINS["catalog"]

SERVICE_NAME = f"{DOMAIN.service_name}-votes-consumer"

EVENTS_PATH = "/events"

_repos: Any = None


def repositories() -> Any:
    """The `catalog` bundle, memoised for the life of the execution environment."""
    global _repos
    if _repos is None:
        from app.composition.wiring import bundle_for

        _repos = bundle_for([DOMAIN])
    return _repos


def build_app() -> FastAPI:
    """The consumer's application: the root routes plus `POST /events`.

    Not `build_domain_app`, whose routes are unreachable here, and not
    `add_shared_middleware`, whose CORS and rate limiter cannot apply on loopback.
    """
    from app.api.middleware import request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

    app = FastAPI(
        title=f"{DOMAIN.title} votes stream consumer",
        openapi_url=None,
    )

    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)
    add_root_routes(app)

    @app.post(EVENTS_PATH)
    async def consume_events(
        request: Request,
    ) -> Dict[str, List[Dict[str, str]]]:  # pyright: ignore[reportUnusedFunction]
        """Recompute `parts.net_votes` for every record this batch touched.

        The returned `batchItemFailures` is the function result the mapping reads.
        Errors propagate: a 500 becomes a function error, so the mapping retries.
        """
        from app.consumers.votes import handle

        event = await request.json()
        return handle(event, repositories())

    return app


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    configure_logging(service=SERVICE_NAME)
    configure_tracing(DOMAIN)

    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
