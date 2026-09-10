"""The catalog domain's part purge consumer, split plan row 28.

Seam 2. `PartService.purge` used to run the whole cascade inline, including the
deletes in `build_list_parts`, `votes`, `reports` and `part_price_alerts`, four
tables belonging to `build-lists`, `moderation` twice and `admin`. This function
is where that half of the cascade moved to. The part delete now writes a
tombstone and returns; the `parts` stream carries it here; this function fans it
onto the `part-purge` work queue and then drains that queue.

**One function, two event source mappings.** The stream mapping and the queue
mapping both invoke this function, and `app/consumers/part_purge.py` tells the
two events apart by `eventSource` on the records. Splitting it into two
functions was the alternative and it buys nothing: the two halves share an
image, a bundle and a set of table grants, so a second function would be a
second cold start, a second log group, a second alarm slot against a ceiling of
ten, and a second thing to keep in step, in exchange for a distinction the logs
already make.

**Why the queue is in the middle at all**, rather than the stream consumer doing
the four deletes directly. A DynamoDB stream record survives 24 hours and a
mapping's retries are spent in minutes; an SQS message survives four days, is
retried five times, and lands in a dead letter queue carrying the part id rather
than the failure metadata a stream DLQ holds. The plan asked for the work queue
by name for seam 2 and this is what it buys: a cascade that fails against a
throttled table is replayable by hand from `part-purge-dlq`, and the visible
symptom it prevents is a purged part left sitting in someone's build list.

**The rest of the shape is row 24's, for row 24's reasons.** It is a FastAPI
application because the base image carries the Lambda Web Adapter and no
`awslambdaric`, so the adapter is the runtime and it POSTs non HTTP events to
`AWS_LWA_PASS_THROUGH_PATH`. It returns `{"batchItemFailures": [...]}` as the
body because that body is the function result the mapping reads, and both
mappings set `ReportBatchItemFailures`. It answers 500 on an unexpected
exception, and Terraform sets `AWS_LWA_ERROR_STATUS_CODES=500-599` so the
adapter turns that into a function error rather than a clean batch. See
`catalog_votes_consumer.py` for the long form of each of those.

Run by the image as `python -m app.entrypoints.catalog_part_purge_consumer`.
"""

from typing import Any, Dict, List

from fastapi import FastAPI, Request

from app.composition.domains import DOMAINS
from app.composition.wiring import (
    add_root_routes,
    configure_logging,
    configure_tracing,
)

#: The domain this consumer belongs to, for its service name, its tracing and
#: its image. Not for its bundle: see `REPOSITORIES` below.
DOMAIN = DOMAINS["catalog"]

#: The four tables the cascade deletes from, named here rather than taken from
#: `DOMAIN.repositories`, because moving the cascade off the request path is
#: exactly what stops `catalog` needing them.
#:
#: This is the part of the row worth reading twice. Before this row, `catalog`,
#: `vehicles`, `build-lists` and `admin` all declared some of
#: `build_list_parts`, `reports` and `part_price_alerts`, and none of them
#: declared those tables because a route of theirs reads or writes one. They
#: declared them because their delete routes called
#: `purge_related_rows_for_parts`, which reached all four. With the cascade gone
#: from that function the declarations became surplus, and
#: `tests/entrypoints/test_repository_bundles.py` failed on all four domains
#: until they were trimmed. That failure is the seam closing, and the trimmed
#: tuples are what turn it into narrower IAM in `lambda_domains.tf`.
#:
#: So the grant did not disappear, it moved: four tables that were reachable
#: from four HTTP functions are now reachable from one function that does
#: nothing but the cascade. `votes` stays in `catalog`'s own tuple because row
#: 24's `net_votes` consumer reaches it there; it is listed here too because
#: this bundle is built from this list alone and shares nothing with that one.
REPOSITORIES = ("build_list_parts", "votes", "reports", "part_price_alerts")

#: The service name this function logs under. Not `DOMAIN.service_name`, which
#: is the HTTP function, and not the votes consumer's either: three functions
#: share this image and the logs have to say which one erred.
SERVICE_NAME = f"{DOMAIN.service_name}-part-purge-consumer"

#: The adapter's pass-through path, set explicitly in Terraform to the same
#: value so the contract is visible in the plan.
EVENTS_PATH = "/events"

#: Built once per execution environment. Two mappings invoke this function, so a
#: warm environment may serve a stream batch and a queue batch back to back off
#: the same bundle, which is the point of memoising it.
_repos: Any = None

#: The SQS client, memoised for the same reason and separately, because the
#: stream half needs it and the queue half does not. A queue only invoke never
#: constructs it.
_sqs: Any = None


def repositories() -> Any:
    """The cascade's four repositories, memoised for the execution environment.

    Built with `build_bundle` over `REPOSITORIES` rather than `bundle_for` over
    a domain, because no domain's tuple is this set any more. Building the
    bundle constructs no repository; the first delete builds the one it needs.
    """
    global _repos
    if _repos is None:
        from app.api.dependencies.repositories import build_bundle

        _repos = build_bundle(REPOSITORIES, name=SERVICE_NAME)
    return _repos


def sqs_client() -> Any:
    """The SQS client the stream half sends with, memoised.

    Built here rather than in the consumer module so a test can replace it
    without patching boto3, matching how `repositories` is replaced.
    """
    global _sqs
    if _sqs is None:
        import boto3

        from app.core.config import settings

        _sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    return _sqs


def build_app() -> FastAPI:
    """The consumer's application: the root routes plus `POST /events`.

    Deliberately not `build_domain_app`, and deliberately without
    `add_shared_middleware`. The reasoning is identical to the votes consumer's
    and is written out in full there: no CORS because the only caller is the
    adapter on loopback, and no rate limiter because it would write to a
    `rate-limits` table this function has no grant for and trip the
    `rate-limit-failed-open` alarm on every invoke.

    The request context middleware and the shared error handlers are added
    directly, for the request id on every log line and for the 500 that
    `AWS_LWA_ERROR_STATUS_CODES` turns into a function error.
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

        Which one depends on the event, and `is_queue_event` decides by reading
        `eventSource` off the records rather than by anything this route
        configures, so the two mappings need no separate paths and no separate
        functions.

        Nothing is caught here. An unexpected exception propagates to the shared
        error handler, which answers 500, and the adapter turns that into a
        function error so the mapping retries. Returning an empty failure list
        instead would tell the mapping every record succeeded, which for the
        stream half means a tombstone whose cascade was never enqueued and for
        the queue half means related rows that outlive their part.
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

    # `check_signing_key` is deliberately absent, as on the votes consumer: this
    # function reads no secret and holds no `secretsmanager:GetSecretValue`
    # grant, so asking for the key would fail on a value nothing here uses. The
    # cascade signs no token and sends no mail.
    configure_logging(service=SERVICE_NAME)
    configure_tracing(DOMAIN)

    # Rebuilt after the tracing provider exists, for the reason the domain
    # entrypoints spell out: `instrument_app` can only inject its server span
    # middleware while the middleware stack is unbuilt.
    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
