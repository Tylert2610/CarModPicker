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

What stays here is the part the package cannot know about: CarModPicker's
repository layer translates botocore errors into its own `ItemNotFound`,
`ConditionFailed` and `TransactionCanceled` exceptions, so those three need
handlers of their own. They are built on the package's `error_body`, so they
produce the same envelope rather than a parallel shape. `dynamodb=True` covers
the botocore `ClientError` the repository deliberately re-raises, which is how
a DynamoDB throttle becomes a 503 with `Retry-After` instead of a flat 500.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from webbpulse.http import error_body

from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Install the shared envelope handlers plus CarModPicker's DynamoDB ones.

    `error_codes=True` keeps the `error_code` key every existing client and test
    reads. `validation_details=True` keeps the 422 `details` list. A route that
    wants its own code still raises `HTTPException(status, {"message": ...,
    "error_code": ...})`, which `ResponsePatterns.raise_http_exception` already
    builds, so no raise site had to change.
    """
    from webbpulse.http import register_error_handlers as register_shared_handlers

    register_shared_handlers(
        app,
        error_codes=True,
        validation_details=True,
        dynamodb=True,
    )

    @app.exception_handler(ItemNotFound)
    async def item_not_found_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ItemNotFound
    ) -> JSONResponse:
        logger.info("DynamoDB item not found in %s: %s", exc.table, exc.key)
        return JSONResponse(
            content=error_body(
                status.HTTP_404_NOT_FOUND,
                "Resource not found",
                request,
                error_code="NOT_FOUND",
            ),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(ConditionFailed)
    async def condition_failed_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ConditionFailed
    ) -> JSONResponse:
        return _conflict(request, exc)

    @app.exception_handler(TransactionCanceled)
    async def transaction_canceled_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: TransactionCanceled
    ) -> JSONResponse:
        # A cancelled transaction is only a conflict when a condition is what
        # cancelled it. Anything else is a genuine fault and must not be dressed
        # up as a 409, or a real outage reads as an ordinary lost race.
        if exc.conditional_check_failed:
            return _conflict(request, exc)
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


def _conflict(request: Request, exc: ConditionFailed | TransactionCanceled) -> JSONResponse:
    """The 409 both condition failures render. The AWS text never reaches the caller."""
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
