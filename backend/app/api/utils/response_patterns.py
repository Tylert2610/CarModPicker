"""
Common response patterns utility for standardizing API responses and reducing redundancy.
"""

from typing import Any, Dict, List, NoReturn, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


class ResponsePatterns:
    """
    Utility class for standardizing API response patterns and reducing redundancy.

    This class provides consistent response formats for common operations like
    success, error, pagination, and data retrieval.
    """

    @staticmethod
    def success_response(
        data: Any = None,
        message: str = "Operation completed successfully",
        status_code: int = status.HTTP_200_OK,
    ) -> JSONResponse:
        """Create a standardized success response."""
        response_data: Dict[str, Any] = {
            "success": True,
            "message": message,
            "data": data,
        }

        return JSONResponse(
            content=response_data,
            status_code=status_code,
        )

    @staticmethod
    def error_response(
        message: str,
        error_code: str | None = None,
        details: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> JSONResponse:
        """Create a standardized error response."""
        response_data: Dict[str, Any] = {
            "success": False,
            "message": message,
            "error_code": error_code,
        }

        if details:
            response_data["details"] = details

        return JSONResponse(
            content=response_data,
            status_code=status_code,
        )

    @staticmethod
    def paginated_response(
        data: List[Any],
        total: int,
        page: int,
        limit: int,
        message: str = "Data retrieved successfully",
    ) -> JSONResponse:
        """Create a standardized paginated response."""
        total_pages = (total + limit - 1) // limit

        response_data: Dict[str, Any] = {
            "success": True,
            "message": message,
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return JSONResponse(
            content=response_data,
            status_code=status.HTTP_200_OK,
        )

    @staticmethod
    def created_response(
        data: Any,
        message: str = "Resource created successfully",
    ) -> JSONResponse:
        """Create a standardized created response."""
        return ResponsePatterns.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    @staticmethod
    def deleted_response(
        message: str = "Resource deleted successfully",
        deleted_id: Optional[int] = None,
    ) -> JSONResponse:
        """Create a standardized deleted response."""
        data = {"deleted_id": deleted_id} if deleted_id else None

        return ResponsePatterns.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_200_OK,
        )

    @staticmethod
    def not_found_response(
        resource_type: str = "Resource",
        resource_id: Optional[Union[int, str, UUID]] = None,
    ) -> JSONResponse:
        """Create a standardized not found response."""
        if resource_id:
            message = f"{resource_type} with ID {resource_id} not found"
        else:
            message = f"{resource_type} not found"

        return ResponsePatterns.error_response(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    @staticmethod
    def unauthorized_response(
        message: str = "Authentication required",
        error_code: str = "UNAUTHORIZED",
    ) -> JSONResponse:
        """Create a standardized unauthorized response."""
        return ResponsePatterns.error_response(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    @staticmethod
    def forbidden_response(
        message: str = "Access denied",
        error_code: str = "FORBIDDEN",
        details: Any = None,
    ) -> JSONResponse:
        """Create a standardized forbidden response."""
        return ResponsePatterns.error_response(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    @staticmethod
    def validation_error_response(
        message: str = "Validation error",
        details: Any = None,
    ) -> JSONResponse:
        """Create a standardized validation error response."""
        return ResponsePatterns.error_response(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @staticmethod
    def conflict_response(
        message: str = "Resource conflict",
        error_code: str = "CONFLICT",
        details: Any = None,
    ) -> JSONResponse:
        """Create a standardized conflict response."""
        return ResponsePatterns.error_response(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_409_CONFLICT,
        )

    @staticmethod
    def raise_http_exception(
        status_code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized HTTPException with consistent error format.

        This method ensures all HTTPExceptions follow the same pattern
        and can be caught by FastAPI's exception handlers.
        """
        detail_dict: Dict[str, Any] = {"message": message}
        if error_code:
            detail_dict["error_code"] = error_code
        if details is not None:
            detail_dict["details"] = details
        raise HTTPException(status_code=status_code, detail=detail_dict)

    @staticmethod
    def raise_not_found(
        resource_type: str = "Resource",
        resource_id: Optional[Union[int, str, UUID]] = None,
    ) -> NoReturn:
        """Raise a standardized 404 HTTPException."""
        if resource_id:
            message = f"{resource_type} with ID {resource_id} not found"
        else:
            message = f"{resource_type} not found"

        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            error_code="NOT_FOUND",
        )

    @staticmethod
    def raise_unauthorized(
        message: str = "Authentication required",
        error_code: str = "UNAUTHORIZED",
        headers: Optional[Dict[str, str]] = None,
    ) -> NoReturn:
        """Raise a standardized 401 HTTPException."""
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message, headers=headers)

    @staticmethod
    def raise_forbidden(
        message: str = "Access denied",
        error_code: str = "FORBIDDEN",
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized 403 HTTPException."""
        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            error_code=error_code,
            details=details,
        )

    @staticmethod
    def raise_validation_error(
        message: str = "Validation error",
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized 422 HTTPException."""
        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
        )

    @staticmethod
    def raise_conflict(
        message: str = "Resource conflict",
        error_code: str = "CONFLICT",
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized 409 HTTPException."""
        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            error_code=error_code,
            details=details,
        )

    @staticmethod
    def raise_bad_request(
        message: str = "Bad request",
        error_code: str = "BAD_REQUEST",
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized 400 HTTPException."""
        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            error_code=error_code,
            details=details,
        )

    @staticmethod
    def raise_internal_server_error(
        message: str = "Internal server error",
        error_code: str = "INTERNAL_ERROR",
        details: Any = None,
    ) -> NoReturn:
        """Raise a standardized 500 HTTPException."""
        ResponsePatterns.raise_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code=error_code,
            details=details,
        )
