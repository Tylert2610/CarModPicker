"""Tests for response patterns utility functions."""

from fastapi import HTTPException

from app.api.utils.response_patterns import ResponsePatterns


class TestResponsePatterns:
    """Test cases for response patterns utility functions."""

    def test_raise_not_found(self) -> None:
        """Test raising a not found exception."""
        try:
            ResponsePatterns.raise_not_found("Resource", 123)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Resource" in e.detail["message"]
            assert "123" in e.detail["message"]
            assert e.detail["error_code"] == "NOT_FOUND"

    def test_raise_unauthorized(self) -> None:
        """Test raising an unauthorized exception."""
        try:
            ResponsePatterns.raise_unauthorized("Authentication required")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
            # raise_unauthorized uses simple string detail for FastAPI compatibility
            assert isinstance(e.detail, str)
            assert "Authentication required" in e.detail

    def test_raise_forbidden(self) -> None:
        """Test raising a forbidden exception."""
        try:
            ResponsePatterns.raise_forbidden("Access denied")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Access denied" in e.detail["message"]
            assert e.detail["error_code"] == "FORBIDDEN"

    def test_raise_bad_request(self) -> None:
        """Test raising a bad request exception."""
        try:
            ResponsePatterns.raise_bad_request("Invalid input")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Invalid input" in e.detail["message"]
            assert e.detail["error_code"] == "BAD_REQUEST"

    def test_raise_conflict(self) -> None:
        """Test raising a conflict exception."""
        try:
            ResponsePatterns.raise_conflict("Resource already exists")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 409
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Resource already exists" in e.detail["message"]
            assert e.detail["error_code"] == "CONFLICT"

    def test_raise_validation_error(self) -> None:
        """Test raising a validation error exception."""
        try:
            ResponsePatterns.raise_validation_error("Validation failed")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 422
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Validation failed" in e.detail["message"]
            assert e.detail["error_code"] == "VALIDATION_ERROR"

    def test_raise_internal_server_error(self) -> None:
        """Test raising an internal server error exception."""
        try:
            ResponsePatterns.raise_internal_server_error("Server error")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 500
            assert isinstance(e.detail, dict)
            assert "message" in e.detail
            assert "error_code" in e.detail
            assert "Server error" in e.detail["message"]
            # `INTERNAL_ERROR` is the shared envelope's code for a 500. The old
            # handler overrode every 5xx code, so the previous default never
            # reached a client; the envelope honours a route's own code.
            assert e.detail["error_code"] == "INTERNAL_ERROR"
