"""The catalog domain's part purge cascade consumer.

One function behind two event source mappings: the `parts` stream fans a tombstone
onto the `part-purge` queue, and the queue drains the related rows.
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

REPOSITORIES = ("build_list_parts", "votes", "reports", "part_price_alerts")

SERVICE_NAME = f"{DOMAIN.service_name}-part-purge-consumer"

EVENTS_PATH = "/events"

_repos: Any = None

_sqs: Any = None


def repositories() -> Any:
    """The cascade's repositories, memoised for the execution environment.

    Built from `REPOSITORIES` rather than a domain tuple, because no domain
    is this set. Building the bundle constructs no repository.
    """
    global _repos
    if _repos is None:
        from app.api.dependencies.repositories import build_bundle

        _repos = build_bundle(REPOSITORIES, name=SERVICE_NAME)
    return _repos


def sqs_client() -> Any:
    """The SQS client the stream half sends with, memoised.

    Built here rather than in the consumer module so a test can replace it
    without patching boto3.
    """
    global _sqs
    if _sqs is None:
        import boto3

        from app.core.config import settings

        _sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    return _sqs


def build_app() -> FastAPI:
    """The consumer's application: the root routes plus `POST /events`.

    Not `build_domain_app`, whose routes are unreachable here, and not
    `add_shared_middleware`, whose CORS and rate limiter cannot apply on loopback.
    """
    from app.api.middleware import request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

    app = FastAPI(
        title=f"{DOMAIN.title} part purge consumer",
        openapi_url=None,
    )

    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)
    add_root_routes(app)

    @app.post(EVENTS_PATH)
    async def consume_events(
        request: Request,
    ) -> Dict[str, List[Dict[str, str]]]:  # pyright: ignore[reportUnusedFunction]
        """Fan a tombstone onto the work queue, or drain a cascade off it.

        `is_queue_event` decides which by `eventSource`, so both mappings can share
        one path. Errors propagate: a 500 becomes a function error and a retry.
        """
        from app.consumers.part_purge import handle_queue, handle_stream, is_queue_event

        event = await request.json()
        if is_queue_event(event):
            return handle_queue(event, repositories())
        return handle_stream(event, sqs_client())

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
