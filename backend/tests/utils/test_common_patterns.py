"""Tests for common patterns utility functions."""

import logging

import pytest
from fastapi import HTTPException
from uuid6 import uuid7

from app.api.utils.common_patterns import (
    create_paginated_response,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
    verify_user_access_or_admin,
)
from app.db.dynamo.users import User


def _user(*, is_admin: bool = False, is_superuser: bool = False) -> User:
    return User(
        username=f"u{uuid7().hex[:10]}",
        email=f"{uuid7().hex[:10]}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=is_admin,
        is_superuser=is_superuser,
    )


class TestValidatePaginationParams:
    def test_valid(self) -> None:
        skip, limit = validate_pagination_params(0, 100)
        assert skip == 0
        assert limit == 100

    def test_negative_skip(self) -> None:
        skip, limit = validate_pagination_params(-1, 100)
        assert skip == 0
        assert limit == 100

    def test_zero_limit(self) -> None:
        skip, limit = validate_pagination_params(0, 0)
        assert skip == 0
        assert limit == 1

    def test_exceeds_max_limit(self) -> None:
        skip, limit = validate_pagination_params(0, 2000)
        assert skip == 0
        assert limit == 1000


class TestVerifyUserAccessOrAdmin:
    def test_owner_allowed(self) -> None:
        user = _user()
        verify_user_access_or_admin(user, user.id, "edit profile")

    @pytest.mark.parametrize("kwargs", [{"is_admin": True}, {"is_superuser": True}])
    def test_admin_or_superuser_allowed(self, kwargs: dict[str, bool]) -> None:
        verify_user_access_or_admin(_user(**kwargs), uuid7(), "edit profile")

    def test_other_user_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        user = _user()
        with caplog.at_level(logging.WARNING):
            with pytest.raises(HTTPException) as excinfo:
                verify_user_access_or_admin(user, uuid7(), "edit profile", logger=logging.getLogger("test"))
        assert excinfo.value.status_code == 403
        assert "edit profile" in str(excinfo.value.detail)
        assert any("Access denied" in rec.getMessage() for rec in caplog.records)


class TestResponseHelpers:
    def test_public_endpoint_dependencies_expose_logger(self) -> None:
        deps = get_standard_public_endpoint_dependencies()
        assert isinstance(deps["logger"], logging.Logger)

    def test_create_paginated_response_envelope(self) -> None:
        result = create_paginated_response([{"id": 1}, {"id": 2}], total=5, skip=2, limit=2, message="ok")
        assert result["success"] is True
        assert result["message"] == "ok"
        assert result["pagination"]["current_page"] == 2
        assert result["pagination"]["total_pages"] == 3
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_previous"] is True
