from typing import Any

import pytest
from fastapi import HTTPException, status

from app.api.dependencies.auth import get_current_admin_user, get_current_superuser
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


class TestAdminAuthentication:
    """Test cases for admin authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_admin_user(self, db_session: Any) -> None:
        """Test that admin user can access admin endpoints."""
        # Create an admin user
        admin_user = UserRepository().create_user(
            DBUser(
                username="admin_test",
                email="admin_test@example.com",
                is_admin=True,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Test the admin dependency by calling it directly with the admin user
        result = await get_current_admin_user(admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_superuser(self, db_session: Any) -> None:
        """Test that superuser can access admin endpoints."""
        # Create a superuser
        superuser = UserRepository().create_user(
            DBUser(
                username="superuser_test",
                email="superuser_test@example.com",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        # Test the admin dependency by calling it directly with the superuser
        result = await get_current_admin_user(superuser)
        assert result == superuser

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_regular_user(self, db_session: Any) -> None:
        """Test that regular user cannot access admin endpoints."""
        # Create a regular user
        regular_user = UserRepository().create_user(
            DBUser(
                username="regular_test",
                email="regular_test@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Test that the admin dependency raises an exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin access required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_disabled_admin(self, db_session: Any) -> None:
        """Test that disabled admin user can still access admin endpoints (disabled check is in base dependency)."""
        # Create a disabled admin user
        disabled_admin = UserRepository().create_user(
            DBUser(
                username="disabled_admin_test",
                email="disabled_admin_test@example.com",
                is_admin=True,
                is_superuser=False,
                email_verified=True,
                disabled=True,  # Disabled user
            )
        )

        # The admin dependency should still work since it only checks admin privileges
        # The disabled check happens in get_current_user, not in admin dependencies
        result = await get_current_admin_user(disabled_admin)
        assert result == disabled_admin


class TestSuperuserAuthentication:
    """Test cases for superuser authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_superuser(self, db_session: Any) -> None:
        """Test that superuser can access superuser endpoints."""
        # Create a superuser
        superuser = UserRepository().create_user(
            DBUser(
                username="superuser_test",
                email="superuser_test@example.com",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        # Test the superuser dependency by calling it directly
        result = await get_current_superuser(superuser)
        assert result == superuser

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_admin_user(self, db_session: Any) -> None:
        """Test that admin user cannot access superuser endpoints."""
        # Create an admin user (not superuser)
        admin_user = UserRepository().create_user(
            DBUser(
                username="admin_test",
                email="admin_test@example.com",
                is_admin=True,
                is_superuser=False,  # Not a superuser
                email_verified=True,
                disabled=False,
            )
        )

        # Test that the superuser dependency raises an exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(admin_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Superuser privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_regular_user(self, db_session: Any) -> None:
        """Test that regular user cannot access superuser endpoints."""
        # Create a regular user
        regular_user = UserRepository().create_user(
            DBUser(
                username="regular_test",
                email="regular_test@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Test that the superuser dependency raises an exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Superuser privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_disabled_superuser(self, db_session: Any) -> None:
        """Test that disabled superuser can still access superuser endpoints (disabled check is in base dependency)."""
        # Create a disabled superuser
        disabled_superuser = UserRepository().create_user(
            DBUser(
                username="disabled_superuser_test",
                email="disabled_superuser_test@example.com",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=True,  # Disabled user
            )
        )

        # The superuser dependency should still work since it only checks superuser privileges
        # The disabled check happens in get_current_user, not in superuser dependencies
        result = await get_current_superuser(disabled_superuser)
        assert result == disabled_superuser


class TestPrivilegeHierarchy:
    """Test cases for privilege hierarchy and edge cases."""

    @pytest.mark.asyncio
    async def test_user_with_both_admin_and_superuser_flags(self, db_session: Any) -> None:
        """Test user with both admin and superuser flags set."""
        # Create a user with both flags
        dual_user = UserRepository().create_user(
            DBUser(
                username="dual_test",
                email="dual_test@example.com",
                is_admin=True,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        # Should be able to access admin endpoints
        admin_result = await get_current_admin_user(dual_user)
        assert admin_result == dual_user

        # Should be able to access superuser endpoints
        superuser_result = await get_current_superuser(dual_user)
        assert superuser_result == dual_user

    @pytest.mark.asyncio
    async def test_user_with_no_privileges(self, db_session: Any) -> None:
        """Test user with no admin or superuser privileges."""
        # Create a user with no privileges
        no_privilege_user = UserRepository().create_user(
            DBUser(
                username="no_privilege_test",
                email="no_privilege_test@example.com",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        # Should not be able to access admin endpoints
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(no_privilege_user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

        # Should not be able to access superuser endpoints
        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(no_privilege_user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
