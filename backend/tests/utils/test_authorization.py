"""Tests for authorization utility functions."""

from fastapi import HTTPException
from uuid6 import uuid7

from app.api.utils.authorization import (
    can_delete_build_list_part,
    can_delete_part,
    can_edit_build_list_part,
    can_edit_part,
    require_build_list_part_delete_permission,
    require_build_list_part_edit_permission,
    require_part_delete_permission,
    require_part_edit_permission,
)
from app.db.dynamo.build_lists import BuildList, BuildListPart
from app.db.dynamo.catalog import Part
from app.db.dynamo.users import User, UserRepository


class TestAuthorization:
    """Test cases for authorization utility functions."""

    def test_can_delete_part_owner(self, test_user: User) -> None:
        """Test that owner can delete their global part."""
        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,
        )
        assert can_delete_part(test_user, part) is True

    def test_can_delete_part_admin(self, test_user: User) -> None:
        """Test that admin can delete any global part."""

        admin_user = User(
            username="admin_user",
            email="admin@example.com",
            email_verified=True,
            disabled=False,
            is_admin=True,
            is_superuser=False,
        )

        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,  # Owned by different user
        )
        assert can_delete_part(admin_user, part) is True

    def test_can_delete_part_unauthorized(self, test_user: User) -> None:
        """Test that non-owner non-admin cannot delete global part."""

        other_user = User(
            username="other_user",
            email="other@example.com",
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )

        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,  # Owned by different user
        )
        assert can_delete_part(other_user, part) is False

    def test_can_edit_part_owner(self, test_user: User) -> None:
        """Test that owner can edit their global part."""
        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,
        )
        assert can_edit_part(test_user, part) is True

    def test_can_edit_part_admin(self, test_user: User) -> None:
        """Test that admin can edit any global part."""

        admin_user = User(
            username="admin_user2",
            email="admin2@example.com",
            email_verified=True,
            disabled=False,
            is_admin=True,
            is_superuser=False,
        )

        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,
        )
        assert can_edit_part(admin_user, part) is True

    def test_can_delete_build_list_part_owner(self, test_user: User) -> None:
        """Test that user who added the part can delete it."""
        build_list_part = BuildListPart(
            build_list_id=uuid7(),
            part_id=uuid7(),
            added_by=test_user.id,
        )
        assert can_delete_build_list_part(test_user, build_list_part) is True

    def test_can_delete_build_list_part_admin(self, test_user: User) -> None:
        """Test that admin can delete any build list part."""

        admin_user = User(
            username="admin_user3",
            email="admin3@example.com",
            email_verified=True,
            disabled=False,
            is_admin=True,
            is_superuser=False,
        )

        build_list_part = BuildListPart(
            build_list_id=uuid7(),
            part_id=uuid7(),
            added_by=test_user.id,  # Added by different user
        )
        assert can_delete_build_list_part(admin_user, build_list_part) is True

    def test_can_edit_build_list_part_added_by(self, test_user: User) -> None:
        """Test that user who added the part can edit it."""
        build_list_part = BuildListPart(
            build_list_id=uuid7(),
            part_id=uuid7(),
            added_by=test_user.id,
        )
        assert can_edit_build_list_part(test_user, build_list_part) is True

    def test_can_edit_build_list_part_build_list_owner(self, test_user: User) -> None:
        """Test that build list owner can edit parts in their build list."""

        other_user = UserRepository().create_user(
            User(
                username="other_user2",
                email="other2@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )

        build_list_part = BuildListPart(
            build_list_id=build_list.id,
            part_id=uuid7(),
            added_by=other_user.id,  # Added by different user
        )

        # Build list owner should be able to edit
        assert can_edit_build_list_part(test_user, build_list_part, build_list=build_list) is True

    def test_require_part_delete_permission_raises(self, test_user: User) -> None:
        """Test that require_part_delete_permission raises when unauthorized."""

        other_user = User(
            username="other_user3",
            email="other3@example.com",
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )

        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,
        )

        try:
            require_part_delete_permission(other_user, part)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403

    def test_require_part_edit_permission_raises(self, test_user: User) -> None:
        """Test that require_part_edit_permission raises when unauthorized."""

        other_user = User(
            username="other_user4",
            email="other4@example.com",
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )

        part = Part(
            category_id=uuid7(),
            name="Test Part",
            description="Test",
            user_id=test_user.id,
        )

        try:
            require_part_edit_permission(other_user, part)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
