"""The users domain's delete cascade consumer, split plan row 30.

Seam 1, and the largest one in the plan. `_delete_user_everywhere` used to run
the whole cascade inline: deletes across roughly fifteen tables belonging to
`identity`, `catalog`, `build-lists`, `build-logs`, `moderation` and `admin`,
all on the request thread of an account deletion inside a 29 second Lambda. This
function is where that cascade moved to. The delete now writes a tombstone, hard
deletes the user row with its two reservations, and returns; the `users` stream
carries the tombstone here; this function fans it onto the `user-delete` work
queue and then drains that queue.

**One function, two event source mappings**, the same shape row 28 established.
The stream mapping and the queue mapping both invoke this function, and
`app/consumers/user_delete.py` tells the two events apart by `eventSource` on
the records. Two functions was the alternative and it buys nothing here either:
both halves share an image, a bundle and a set of table grants, so the second
function would be a second cold start, a second log group, a second alarm slot,
and a second thing to keep in step, in exchange for a distinction the logs
already make.

**Why the queue is in the middle at all**, rather than the stream consumer doing
the deletes directly. A DynamoDB stream record survives 24 hours and a mapping's
retries are spent in minutes; an SQS message survives four days, is retried five
times, and lands in a dead letter queue carrying the user id rather than the
failure metadata a stream dead letter queue holds. Section 7 asked for the
`user-delete` queue by name for this seam and row 22 created it. What it buys is
that a cascade failing against a throttled table is replayable by hand from
`user-delete-dlq`, and the symptom it prevents is a deleted account whose build
lists are still public.

**The rest of the shape is row 24's, for row 24's reasons.** It is a FastAPI
application because the base image carries the Lambda Web Adapter and no
`awslambdaric`, so the adapter is the runtime and it POSTs non HTTP events to
`AWS_LWA_PASS_THROUGH_PATH`. It returns `{"batchItemFailures": [...]}` as the
body because that body is the function result the mapping reads, and both
mappings set `ReportBatchItemFailures`. It answers 500 on an unexpected
exception, and Terraform sets `AWS_LWA_ERROR_STATUS_CODES=500-599` so the
adapter turns that into a function error rather than a clean batch. See
`catalog_votes_consumer.py` for the long form of each of those.

Run by the image as `python -m app.entrypoints.users_delete_consumer`.
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
DOMAIN = DOMAINS["users"]

#: The eighteen tables the cascade reaches, named here rather than taken from
#: `DOMAIN.repositories`, because moving the cascade off the request path is
#: exactly what stops `users` needing them.
#:
#: This is the payoff of the whole row. Before it, `users` declared twenty-three
#: of the twenty-five repositories, and it declared almost none of them because
#: a route of its own reads or writes one: it declared them because
#: `_delete_user_everywhere` reached them. With the cascade gone from that
#: function, `app/composition/domains.py` trims to three and
#: `tests/entrypoints/test_repository_bundles.py` is what proves the trim
#: matches the import graph rather than a guess. That test failing on `users`
#: until the tuple shrank is the seam closing, and the trimmed tuple is what
#: turns it into narrower IAM in `lambda_domains.tf`.
#:
#: So the grants did not disappear, they moved: eighteen tables reachable from
#: the domain's HTTP function are now reachable from one function that does
#: nothing but the cascade.
#:
#: `users` itself is deliberately absent, and it is the one entry whose absence
#: is load bearing. The user row and its `username` and `email` reservations are
#: removed synchronously, before this function ever sees the tombstone, and
#: `app/consumers/user_delete.py` argues why. Leaving the repository out of this
#: bundle is what makes that a `RepositoryNotInBundle` rather than a silent
#: second writer if a later change reaches for it.
#:
#: The catalogue tables are here because `PartService.purge` reaches them, and
#: the service is reused rather than reimplemented so the two seams cannot
#: drift. `part_manufacturers` and `categories` come with it: `PartService`
#: imports the catalogue module and the bundle has to carry whatever a purge
#: might touch.
REPOSITORIES = (
    "oauth_accounts",
    "webauthn_credentials",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
    "reports",
)

#: The service name this function logs under. Not `DOMAIN.service_name`, which
#: is the HTTP function: two functions share this image and the logs have to say
#: which one erred.
SERVICE_NAME = f"{DOMAIN.service_name}-delete-consumer"

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
    """The cascade's repositories, memoised for the execution environment.

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
        title=f"{DOMAIN.title} delete consumer",
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
        the queue half means a deleted user's rows left behind for good.
        """
        from app.consumers.user_delete import handle_queue, handle_stream, is_queue_event

        event = await request.json()
        if is_queue_event(event):
            return handle_queue(event, repositories())
        return handle_stream(event, sqs_client())

    return app


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    # `check_signing_key` is deliberately absent, as on the other consumers:
    # this function reads no secret and holds no `secretsmanager:GetSecretValue`
    # grant, so asking for the key would fail on a value nothing here uses. The
    # cascade signs no token and sends no mail. Note that the `users` HTTP
    # function does declare `SECRET_KEY` in `requires_secrets`; this function
    # shares its image and not its needs.
    configure_logging(service=SERVICE_NAME)
    configure_tracing(DOMAIN)

    # Rebuilt after the tracing provider exists, for the reason the domain
    # entrypoints spell out: `instrument_app` can only inject its server span
    # middleware while the middleware stack is unbuilt.
    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
