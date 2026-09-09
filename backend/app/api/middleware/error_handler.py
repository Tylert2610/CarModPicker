"""Error handlers, delegating to the shared `webbpulse` envelope.

Every error response in this API is the org standard envelope::

    {"success": false, "status": 404, "message": "...", "request_id": "...",
     "error_code": "NOT_FOUND"}

with `details` added for a 422 and for the handful of routes that attach
structured information to a conflict.

`webbpulse.http.register_error_handlers` owns the `HTTPException`,
`RequestValidationError` and bare-`Exception` handlers, including the Starlette
routing errors: an unmatched path and a wrong method used to fall through as
`{"detail": "Not Found"}`, a shape unlike every other error this API returns,
and the package now renders those in the envelope too.

CarModPicker's repository layer translates botocore errors into its own
`ItemNotFound`, `ConditionFailed` and `TransactionCanceled` exceptions, so those
never reach the botocore handlers. Two of the three are now declared to the
package as an `exception_map` rather than written out here: a status and a
message is all they ever were, and `webbpulse` builds the identical envelope
from that. `dynamodb=True` still covers the botocore `ClientError` the
repository deliberately re-raises, which is how a DynamoDB throttle becomes a
503 with `Retry-After` instead of a flat 500.

`TransactionCanceled` keeps a hand-written handler, and that is not an
oversight. Its status depends on the exception's own contents: a cancellation
caused by a failed condition is a 409, and a cancellation caused by anything
else is a genuine fault that must stay a 500, or a real outage reads as an
ordinary lost race. `ErrorSpec` maps a type to one fixed status, so it cannot
express that branch, and flattening it to 409 would be a behaviour change
dressed up as a refactor.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from webbpulse.http import ErrorSpec, error_body

from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

logger = logging.getLogger(__name__)

#: CarModPicker's repository exceptions that map onto one fixed status each.
#: The messages and codes are the ones the hand-written handlers sent, spelled
#: out rather than left to the package defaults, because the package's own 404
#: wording is "The requested resource was not found." and the frontend's
#: envelope reader keys off `error_code`. Both are therefore explicit here so
#: the response bodies stay byte identical.
DYNAMO_EXCEPTION_MAP: dict[type[BaseException], int | ErrorSpec] = {
    ItemNotFound: ErrorSpec(
        status.HTTP_404_NOT_FOUND,
        message="Resource not found",
        error_code="NOT_FOUND",
    ),
    ConditionFailed: ErrorSpec(
        status.HTTP_409_CONFLICT,
        message="Resource already exists or was modified concurrently",
        error_code="CONFLICT",
    ),
}


def register_error_handlers(app: FastAPI) -> None:
    """Install the shared envelope handlers plus CarModPicker's DynamoDB ones.

    `error_codes=True` keeps the `error_code` key every existing client and test
    reads. `validation_details=True` keeps the 422 `details` list. A route that
    wants its own code still raises `HTTPException(status, {"message": ...,
    "error_code": ...})`, which `ResponsePatterns.raise_http_exception` already
    builds, so no raise site had to change.

    `exception_map` carries the two repository exceptions whose rendering is a
    constant. The package validates it while the application is being built, so
    a typo in the mapping fails at import rather than as a 500 under load.
    """
    from webbpulse.http import register_error_handlers as register_shared_handlers

    register_shared_handlers(
        app,
        error_codes=True,
        validation_details=True,
        dynamodb=True,
        exception_map=DYNAMO_EXCEPTION_MAP,
    )

    @app.exception_handler(TransactionCanceled)
    async def transaction_canceled_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: TransactionCanceled
    ) -> JSONResponse:
        # A cancelled transaction is only a conflict when a condition is what
        # cancelled it. Anything else is a genuine fault and must not be dressed
        # up as a 409, or a real outage reads as an ordinary lost race. This is
        # the branch `exception_map` cannot express, which is why this handler
        # stays while the other two are gone.
        if exc.conditional_check_failed:
            logger.warning("DynamoDB condition failed: %s", exc)
            return JSONResponse(
                content=error_body(
                    status.HTTP_409_CONFLICT,
                    "Resource already exists or was modified concurrently",
                    request,
                    error_code="CONFLICT",
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        logger.error(f"Transaction canceled in {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            content=error_body(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal server error",
                request,
                error_code="INTERNAL_ERROR",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
