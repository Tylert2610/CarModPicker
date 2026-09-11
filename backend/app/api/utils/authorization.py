"""Ownership and admin checks shared by the endpoints."""

from typing import Optional

from fastapi import HTTPException

from app.api.dependencies.repositories import get_repositories
from app.db.dynamo.build_lists import BuildList as DBBuildList
from app.db.dynamo.build_lists import BuildListPart as DBBuildListPart
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from app.db.dynamo.users import User as DBUser


def can_delete_part(user: DBUser, part: DBPart) -> bool:
    """Check if a user can delete a part. Only the creator or admin/superuser can."""
    return part.user_id == user.id or user.is_admin or user.is_superuser


def can_delete_build_list_part(user: DBUser, build_list_part: DBBuildListPart) -> bool:
    """Check if a user can delete a build list part."""
    return build_list_part.added_by == user.id or user.is_admin or user.is_superuser


def can_edit_part(user: DBUser, part: DBPart) -> bool:
    """Check if a user can edit a part. Only the creator or admin/superuser can."""
    return part.user_id == user.id or user.is_admin or user.is_superuser


def can_edit_build_list_part(
    user: DBUser,
    build_list_part: DBBuildListPart,
    build_list: Optional[DBBuildList] = None,
) -> bool:
    """Check if a user can edit a build list part."""
    if build_list_part.added_by == user.id or user.is_admin or user.is_superuser:
        return True

    if build_list is None:
        build_list = get_repositories().build_lists.get(build_list_part.build_list_id)
    return build_list is not None and build_list.user_id == user.id


def require_part_delete_permission(user: DBUser, part: DBPart) -> None:
    """Raise HTTPException if user cannot delete the part."""
    if not can_delete_part(user, part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this part. Only the creator or admin can delete parts.",
        )


def require_build_list_part_delete_permission(user: DBUser, build_list_part: DBBuildListPart) -> None:
    """Raise HTTPException if user cannot delete the build list part."""
    if not can_delete_build_list_part(user, build_list_part):
        raise HTTPException(
            status_code=403,
            detail=(
                "Not authorized to delete this build list part. "
                "Only the user who added it or admin can delete build list parts."
            ),
        )


def require_part_edit_permission(user: DBUser, part: DBPart) -> None:
    """Raise HTTPException if user cannot edit the part."""
    if not can_edit_part(user, part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to edit this part. Only the creator or admin can edit parts.",
        )


def require_build_list_part_edit_permission(
    user: DBUser,
    build_list_part: DBBuildListPart,
    build_list: Optional[DBBuildList] = None,
) -> None:
    """Raise HTTPException if user cannot edit the build list part."""
    if not can_edit_build_list_part(user, build_list_part, build_list):
        raise HTTPException(
            status_code=403,
            detail=(
                "Not authorized to edit this build list part. "
                "Only the user who added it, the build list owner, or admin can edit build list parts."
            ),
        )


def can_edit_part_manufacturer(user: DBUser, pm: DBPartManufacturer) -> bool:
    """Whether the user can update a manufacturer. Admin/superuser only."""
    return user.is_admin or user.is_superuser


def can_delete_part_manufacturer(user: DBUser, pm: DBPartManufacturer) -> bool:
    """Whether the user can delete a manufacturer.

    Same eligibility rules as edit. The endpoint also enforces a separate
    in-use guard (cannot delete if any Part still references the row).
    """
    return can_edit_part_manufacturer(user, pm)


def require_part_manufacturer_edit_permission(user: DBUser, pm: DBPartManufacturer) -> None:
    """Raise HTTPException if user cannot edit the manufacturer."""
    if not can_edit_part_manufacturer(user, pm):
        raise HTTPException(
            status_code=403,
            detail=(
                "Not authorized to edit this part manufacturer. "
                "Only the original creator (for user-created entries) or an admin can edit it."
            ),
        )


def require_part_manufacturer_delete_permission(user: DBUser, pm: DBPartManufacturer) -> None:
    """Raise HTTPException if user cannot delete the manufacturer."""
    if not can_delete_part_manufacturer(user, pm):
        raise HTTPException(
            status_code=403,
            detail=(
                "Not authorized to delete this part manufacturer. "
                "Only the original creator (for user-created entries) or an admin can delete it."
            ),
        )
