"""Error handlers, delegating to the shared `webbpulse` envelope.

Every error response in this API is the org standard envelope::
{"success": false, "status": 404, "message": "...", "request_id": "...",
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from webbpulse.http import ErrorSpec, error_body

from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

logger = logging.getLogger(__name__)

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
        """Map a cancelled DynamoDB transaction to a 409 or 400 response."""
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
