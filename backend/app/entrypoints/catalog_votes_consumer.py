"""The catalog domain's `votes` stream consumer, split plan row 24.

The tenth deployed function, and the first whose events are not HTTP requests.
An event source mapping on the `votes` table's DynamoDB stream invokes it with a
batch of records; it recomputes `parts.net_votes` for every part the batch
touched and reports per-record failures back to the mapping.

**It is still a web application, and that is the point.** Everything else in
this package builds a FastAPI app because it serves HTTP, and this module builds
one because of how the image runs. The shared base image
(`WebbPulse-Artifacts/images/python-lambda-base`) is `python:3.13-slim` with the
Lambda Web Adapter copied into `/opt/extensions/`. There is no `awslambdaric` in
it and none in `requirements-lambda.txt`, so there is no runtime interface
client to hand a `module.function` handler string to. The adapter *is* the
runtime here: the extension polls the Lambda Runtime API itself and forwards
each invoke to the application over HTTP on `AWS_LWA_PORT`. Pointing
`image_config.command` at a handler string would make Lambda try to execute a
file with that literal name, and adding a second runtime client beside the
adapter is not a supported shape.

**So the consumer uses the adapter's documented pass-through.** For an event
that is not an HTTP request, the adapter POSTs the raw event JSON to the
application at `AWS_LWA_PASS_THROUGH_PATH`, which defaults to `/events`, and
returns the application's response body as the function's result. The user guide
lists DynamoDB among the triggers this covers, alongside SQS, SNS, S3, Kinesis,
Kafka, EventBridge and Bedrock Agents. That is why `POST /events` below returns
the `{"batchItemFailures": [...]}` object directly as its body: that body is
what Lambda hands back to the event source mapping, and `ReportBatchItemFailures`
on the mapping is what makes the mapping read it.

**Failures must be loud.** An unexpected exception returns 500 rather than an
empty failure list. An empty list means "every record in this batch succeeded",
so swallowing an error would silently retire records that were never processed
and leave `net_votes` wrong with nothing on the stream to replay. Terraform sets
`AWS_LWA_ERROR_STATUS_CODES=500-599` on this function, which is what turns that
500 into a Lambda function error: without it the adapter returns any status as a
successful invoke, and the mapping would treat a 500 as a clean batch. With it
the invoke fails, the mapping bisects the batch and retries, and a batch that
keeps failing lands on the votes stream DLQ.

**Why a separate function rather than a route on `catalog`.** A route would
work, but the two would then share concurrency, a timeout and an IAM policy: a
vote storm would take request capacity from the catalog API, and this function's
policy could not stay as narrow as it is (no secret, no S3, write `parts`, read
`votes`). They share the image instead, which is what keeps one build, one push
and one digest behind both, so they cannot skew.

Run by the image as `python -m app.entrypoints.catalog_votes_consumer`, the same
`sh -c exec python -m "$(cat /etc/carmodpicker-entrypoint)"` shape every other
entrypoint uses, with `image_config.command` overriding only which module.
"""

from typing import Any, Dict, List

from fastapi import FastAPI, Request

from app.composition.domains import DOMAINS
from app.composition.wiring import (
    add_root_routes,
    configure_logging,
    configure_tracing,
)

#: The consumer runs inside `catalog`'s bundle, so it reaches exactly the
#: repositories that domain declares and no others. `votes` and `parts` are both
#: in `_CATALOG_REPOSITORIES` already: `parts` because it is the domain's own,
#: and `votes` because `PartService` reads it. Nothing had to be added to the
#: bundle for this row, which is what makes the seam an inversion rather than a
#: widening.
DOMAIN = DOMAINS["catalog"]

#: The service name this function logs under. Deliberately not
#: `DOMAIN.service_name`: that is `carmodpicker-catalog`, which is the HTTP
#: function, and two functions logging under one service name would make "which
#: one erred" unanswerable from the logs alone.
SERVICE_NAME = f"{DOMAIN.service_name}-votes-consumer"

#: The adapter's default pass-through path. Terraform sets
#: `AWS_LWA_PASS_THROUGH_PATH` to this same value explicitly rather than relying
#: on the default, so the contract between the mapping and this route is visible
#: in the plan instead of implied.
EVENTS_PATH = "/events"

#: Built once per execution environment rather than per request. The bundle
#: constructs nothing on creation, so this costs an object; the repositories it
#: builds on first access are then reused across every invoke the environment
#: serves, which is what keeps a warm consumer to one client per table.
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

    Deliberately not `build_domain_app`. That would mount all 43 of `catalog`'s
    routes, and this function has no API Gateway route, no `SECRET_KEY` and no
    S3 grant: every one of those routes would be unreachable, and the ones that
    verify a token would fail on a secret this function is not allowed to read.
    The root routes are included because the image's
    `AWS_LWA_READINESS_CHECK_PATH` is `/health`, so the adapter polls it before
    forwarding anything and a function without it never becomes ready.

    `add_shared_middleware` is deliberately not used, and this is the one place
    this module diverges from the shared stack rather than reusing it. It
    bundles four things, and two of them are wrong here. CORS is meaningless:
    the only caller is the adapter on loopback, which sends no `Origin`. The
    rate limiter is worse than meaningless: it is keyed on the client of an HTTP
    request, there is no client here, and it writes to the `rate-limits` table
    this function has no grant for, so every invoke would log a failed-open
    warning and trip the `rate-limit-failed-open` alarm on a function that
    cannot be rate limited.

    So the two pieces that do earn their place are added directly: the request
    context middleware, for the request id on every log line, and the shared
    error handlers, so a failure is logged in the same JSON shape as everywhere
    else and the aggregate `application-errors` alarm reads it without a special
    case. The handlers also produce the 500 that
    `AWS_LWA_ERROR_STATUS_CODES` turns into a function error.
    """
    from app.api.middleware import request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

    app = FastAPI(
        title=f"{DOMAIN.title} votes stream consumer",
        # No OpenAPI document. This application serves no public API, and a
        # schema for it would only ever be misleading.
        openapi_url=None,
    )

    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)
    add_root_routes(app)

    @app.post(EVENTS_PATH)
    async def consume_events(
        request: Request,
    ) -> Dict[str, List[Dict[str, str]]]:  # pyright: ignore[reportUnusedFunction]
        """Recompute `net_votes` for every part this batch of records touched.

        The body is the raw DynamoDB stream event the adapter passed through,
        and the returned object is what the event source mapping reads as the
        function result. An empty `batchItemFailures` retires the whole batch; a
        non-empty one retries exactly the records named.

        Nothing is caught here. An unexpected exception propagates to the shared
        error handler, which answers 500, and
        `AWS_LWA_ERROR_STATUS_CODES=500-599` turns that into a function error so
        the mapping bisects and retries. Returning an empty failure list instead
        would tell the mapping every record succeeded.
        """
        from app.consumers.votes import handle

        event = await request.json()
        return handle(event, repositories())

    return app


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    # Logging first, then tracing, matching the other entrypoints:
    # `configure_tracing` logs its own warnings and they are worth having in the
    # shared JSON format. `check_signing_key` is deliberately absent, which is
    # the one step this module drops: this function reads no secret and has no
    # `secretsmanager:GetSecretValue` grant, so asking for the key would fail on
    # a value nothing here uses.
    configure_logging(service=SERVICE_NAME)
    configure_tracing(DOMAIN)

    # Rebuilt after the tracing provider exists, for the reason the domain
    # entrypoints spell out: `instrument_app` can only inject its server span
    # middleware while the middleware stack is unbuilt, so the module-level
    # `app` below, constructed at import, was built before the provider existed
    # and cannot be instrumented after the fact.
    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
