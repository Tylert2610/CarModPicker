"""The catalog domain's `votes` stream consumer, split plan row 24.

The tenth deployed function and the first that is not an HTTP one. Every module
beside this one in `app/entrypoints/` builds a FastAPI application and is served
by the Lambda Web Adapter; this module builds no application, registers no
router and installs no middleware. It is a plain Lambda handler that an event
source mapping calls with a batch of DynamoDB stream records off the `votes`
table.

**Why it is a separate function rather than a second handler on `catalog`.** A
Lambda function has one handler. `catalog` runs `python -m
app.entrypoints.catalog` under the Web Adapter, which is a uvicorn process the
adapter proxies HTTP into; there is no way for an event source mapping to reach
a second entry point inside that process. Two functions off one image is the
shape AWS supports, and it is the better shape anyway: the consumer gets its own
concurrency, its own timeout, its own IAM policy and its own error rate, so a
vote storm cannot take request capacity away from the catalog routes and a bug
here does not page as a catalog API error.

**It shares `catalog`'s image.** Same ECR repository, same digest, same
`DOMAIN=catalog` build. What differs is the container command, set by
`image_config.command` in `terraform/lambda_domains.tf` rather than by a
separate Dockerfile target: Lambda's runtime interface client takes a handler
string, so overriding the command is enough to make the same image run this
module instead of the web server. One image means the deploy that updates
`catalog` updates the consumer with the same digest and the two cannot skew.

**`handler` is the module attribute Lambda calls.** The name matches the other
entrypoints' `handler` even though this one is not Mangum, because the deploy
tooling and anyone reading these files expects the entry point of an entrypoint
module to be called `handler`.

Logging and tracing are configured at import rather than in a `main`, which is
the one place this module has to differ from its neighbours. An HTTP entrypoint
has a `main` that the container command runs, so it has somewhere to put
process-wide setup; a Lambda handler has no such call, and the init phase is the
only chance to do it before the first invoke.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from app.composition.domains import DOMAINS
from app.composition.wiring import configure_logging, configure_tracing

#: The consumer runs inside `catalog`'s bundle, so it reaches exactly the
#: repositories that domain declares and no others. `votes` and `parts` are both
#: in `_CATALOG_REPOSITORIES` already: `parts` because it is the domain's own,
#: and `votes` because `PartService` reads it. Nothing had to be added to the
#: bundle for this row, which is what makes the seam an inversion rather than a
#: widening.
DOMAIN = DOMAINS["catalog"]

#: The service name this function logs under. Deliberately not `DOMAIN.service_name`:
#: that is `carmodpicker-catalog`, which is the HTTP function, and two functions
#: logging under one service name would make "which one erred" unanswerable from
#: the logs alone.
SERVICE_NAME = f"{DOMAIN.service_name}-votes-consumer"

configure_logging(service=SERVICE_NAME)
configure_tracing(DOMAIN)

logger = logging.getLogger(__name__)

#: Built once per execution environment rather than per invoke. The bundle
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


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, List[Dict[str, str]]]:
    """Recompute `net_votes` for every part this batch of vote records touched.

    Returns `{"batchItemFailures": [...]}`. The event source mapping is created
    with `ReportBatchItemFailures`, so an empty list retires the whole batch and
    a non-empty one retries exactly the records named.
    """
    from app.consumers.votes import handle

    return handle(event, repositories())


if __name__ == "__main__":  # pragma: no cover - parity with the HTTP entrypoints
    # There is no server to run. This exists so that running the module by hand,
    # which is what every other entrypoint in this package supports, says
    # something useful rather than exiting silently.
    print(f"{SERVICE_NAME} is a Lambda stream consumer and has no server to run.")
    print(f"Its handler is {__name__}.handler, invoked by the votes stream event source mapping.")
    print(f"RUN_STARTUP_TASKS={os.environ.get('RUN_STARTUP_TASKS', 'unset')}")
