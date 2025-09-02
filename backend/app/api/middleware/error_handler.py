"""
Error handling middleware for standardizing API error responses.

This middleware catches all HTTPExceptions and converts them to
standardized response formats using ResponsePatterns.
"""

import logging
from typing import Any, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..utils.response_patterns import ResponsePatterns

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """
    Middleware to catch and standardize all error responses.

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint function

    Returns:
        Standardized error response or original response
    """
    try:
        response = await call_next(request)
        return response
    except HTTPException as exc:
        # Handle FastAPI HTTPExceptions
        return handle_http_exception(exc)
    except StarletteHTTPException as exc:
        # Handle Starlette HTTPExceptions
        return handle_http_exception(exc)
    except RequestValidationError as exc:
        # Handle validation errors
        return handle_validation_error(exc)
    except Exception as exc:
        # Handle unexpected errors
        logger.error(
            f"Unexpected error in {request.url.path}: {str(exc)}", exc_info=True
        )
        return handle_unexpected_error(exc)


def handle_http_exception(exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPExceptions and convert to standardized format.

    Args:
        exc: HTTPException instance

    Returns:
        Standardized JSONResponse
    """
    # Check if the exception already has standardized format
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        # Already standardized, return as is
        return JSONResponse(
            content=exc.detail, status_code=exc.status_code, headers=exc.headers
        )

    # Convert to standardized format
    error_data = {
        "success": False,
        "message": str(exc.detail),
        "error_code": get_error_code(exc.status_code),
    }

    return JSONResponse(
        content=error_data, status_code=exc.status_code, headers=exc.headers
    )


def handle_validation_error(exc: RequestValidationError) -> JSONResponse:
    """
    Handle validation errors and convert to standardized format.

    Args:
        exc: RequestValidationError instance

    Returns:
        Standardized JSONResponse
    """
    error_details = []
    for error in exc.errors():
        error_details.append(
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    error_data = {
        "success": False,
        "message": "Validation error",
        "error_code": "VALIDATION_ERROR",
        "details": error_details,
    }

    return JSONResponse(
        content=error_data, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def handle_unexpected_error(exc: Exception) -> JSONResponse:
    """
    Handle unexpected errors and convert to standardized format.

    Args:
        exc: Exception instance

    Returns:
        Standardized JSONResponse
    """
    error_data = {
        "success": False,
        "message": "Internal server error",
        "error_code": "INTERNAL_ERROR",
    }

    return JSONResponse(
        content=error_data, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def get_error_code(status_code: int) -> str:
    """
    Get standardized error code based on HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        Standardized error code string
    """
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }

    return error_codes.get(status_code, "UNKNOWN_ERROR")


def register_error_handlers(app):
    """
    Register error handlers with FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return handle_http_exception(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return handle_validation_error(exc)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception in {request.url.path}: {str(exc)}", exc_info=True
        )
        return handle_unexpected_error(exc)
