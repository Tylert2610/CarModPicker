"""The admin domain's `part_listings` stream consumer, split plan row 25.

The second stream consumer, after row 24's. An event source
mapping on the `part_listings` table's DynamoDB stream invokes it with a batch
of records; it evaluates the price drop alerts on every listing whose price fell
and sends the alert email through SES, reporting per-record failures back to the
mapping.

**It is still a web application, and for the reason row 24 spells out.** The
shared base image (`WebbPulse-Artifacts/images/python-lambda-base`) is
`python:3.13-slim` with the Lambda Web Adapter copied into `/opt/extensions/`.
There is no `awslambdaric` in it, so there is no runtime interface client to
hand a `module.function` handler string to: the adapter is the runtime, it polls
the Lambda Runtime API itself and forwards each invoke to the application over
HTTP on `AWS_LWA_PORT`. For an event that is not an HTTP request it POSTs the
raw event JSON to `AWS_LWA_PASS_THROUGH_PATH`, which defaults to `/events`, and
returns the application's response body as the function's result. The user guide
lists DynamoDB among the triggers this covers.

**Failures must be loud.** An unexpected exception returns 500 rather than an
empty failure list. An empty list means "every record in this batch succeeded",
so swallowing an error would retire records that were never evaluated and the
subscribers on those listings would simply never hear about the price drop, with
nothing on the stream left to replay. Terraform sets
`AWS_LWA_ERROR_STATUS_CODES=500-599` on this function, which is what turns that
500 into a Lambda function error: without it the adapter returns any status as a
successful invoke and the mapping would treat a 500 as a clean batch.

**This one reads a secret, and row 24's consumer did not.** The alert email
carries a one-click unsubscribe link, which is a 30 day JWT signed with
`SECRET_KEY`, so `send_price_drop_alert_email` reaches `create_access_token` and
this function needs the app secret. That is why `main()` below calls
`check_signing_key` where `catalog_votes_consumer` deliberately does not, and
why its Terraform entry sets `secrets = true` where that one sets false. It is
also why the function is granted `ses:SendEmail` and carries `EMAIL_FROM`: those
three are one grant set, and they arrive here with the code that uses them
rather than on the `admin` HTTP function, which serves no route that sends mail.

**Why a separate function rather than a route on `admin`.** A route would work,
since the consumer is a web app. It is still the wrong answer: an event source
mapping's concurrency, timeout and error rate would be shared with the admin
API, and this function's IAM policy could not stay as narrow as it is. They
share the image instead, which is what keeps one build, one push and one digest
behind both so they cannot skew.

Run by the image as `python -m app.entrypoints.admin_price_alerts_consumer`, the
same `python -m` shape every other entrypoint uses, with `image_config.command`
overriding only which module.
"""

from typing import Any, Dict, List

from fastapi import FastAPI, Request

from app.composition.domains import DOMAINS
from app.composition.wiring import (
    add_root_routes,
    check_signing_key,
    configure_logging,
    configure_tracing,
)

#: The consumer runs inside `admin`'s bundle, so it reaches exactly the
#: repositories that domain declares and no others. `part_price_alerts`,
#: `parts`, `retailers` and `users` are all in `_ADMIN_REPOSITORIES` already:
#: the alerts because they are the domain's own, and the other three because
#: `admin/stats` and `admin/db_ops` reach them. Nothing had to be added to the
#: bundle for this row, which is what makes the seam an inversion rather than a
#: widening.
DOMAIN = DOMAINS["admin"]

#: The service name this function logs under. Deliberately not
#: `DOMAIN.service_name`: that is `carmodpicker-admin`, which is the HTTP
#: function, and two functions logging under one service name would make "which
#: one erred" unanswerable from the logs alone.
SERVICE_NAME = f"{DOMAIN.service_name}-price-alerts-consumer"

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
    """The `admin` bundle, memoised for the life of the execution environment."""
    global _repos
    if _repos is None:
        from app.composition.wiring import bundle_for

        _repos = bundle_for([DOMAIN])
    return _repos


def build_app() -> FastAPI:
    """The consumer's application: the root routes plus `POST /events`.

    Deliberately not `build_domain_app`. That would mount all 12 of `admin`'s
    routes, and this function has no API Gateway route in front of it, so every
    one of them would be unreachable. The root routes are included because the
    image's `AWS_LWA_READINESS_CHECK_PATH` is `/health`, so the adapter polls it
    before forwarding anything and a function without it never becomes ready.

    `add_shared_middleware` is deliberately not used, for the reason
    `catalog_votes_consumer` gives. CORS is meaningless: the only caller is the
    adapter on loopback, which sends no `Origin`. The rate limiter is worse than
    meaningless: it writes to the `rate-limits` table this function has no grant
    for, so every invoke would log a failed-open warning and trip the
    `rate-limit-failed-open` alarm on a function that cannot be rate limited.

    So the two pieces that do earn their place are added directly: the request
    context middleware, for the request id on every log line, and the shared
    error handlers, so a failure is logged in the same JSON shape as everywhere
    else and the aggregate `application-errors` alarm reads it without a special
    case. The handlers also produce the 500 that `AWS_LWA_ERROR_STATUS_CODES`
    turns into a function error.
    """
    from app.api.middleware import request_context_middleware
    from app.api.middleware.error_handler import register_error_handlers

    app = FastAPI(
        title=f"{DOMAIN.title} price alerts stream consumer",
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
        """Evaluate price alerts for every listing this batch dropped the price on.

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
        from app.consumers.price_alerts import handle

        event = await request.json()
        return handle(event, repositories())

    return app


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    configure_logging(service=SERVICE_NAME)

    # Unlike row 24's consumer, this one is checked. The unsubscribe link in the
    # alert email is a signed JWT, so a missing `SECRET_KEY` would not fail an
    # invoke: it would send mail whose unsubscribe link does not work, or fail
    # per alert deep inside the evaluation's own exception handling where the
    # only symptom is a warning. Failing at startup is the readable failure.
    check_signing_key([DOMAIN])

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
