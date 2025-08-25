from typing import Optional
from fastapi import HTTPException
from app.api.models.user import User as DBUser
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.build_list_part import BuildListPart as DBBuildListPart


def can_delete_global_part(user: DBUser, global_part: DBGlobalPart) -> bool:
    """
    Check if a user can delete a global part.
    Only the creator or admin/superuser can delete global parts.
    """
    return global_part.user_id == user.id or user.is_admin or user.is_superuser


def can_delete_build_list_part(user: DBUser, build_list_part: DBBuildListPart) -> bool:
    """
    Check if a user can delete a build list part.
    Only the user who added it or admin/superuser can delete build list parts.
    """
    return build_list_part.added_by == user.id or user.is_admin or user.is_superuser


def can_edit_global_part(user: DBUser, global_part: DBGlobalPart) -> bool:
    """
    Check if a user can edit a global part.
    Only the creator or admin/superuser can edit global parts.
    """
    return global_part.user_id == user.id or user.is_admin or user.is_superuser


def can_edit_build_list_part(user: DBUser, build_list_part: DBBuildListPart) -> bool:
    """
    Check if a user can edit a build list part.
    Only the user who added it or admin/superuser can edit build list parts.
    """
    return build_list_part.added_by == user.id or user.is_admin or user.is_superuser


def require_global_part_delete_permission(
    user: DBUser, global_part: DBGlobalPart
) -> None:
    """
    Raise HTTPException if user cannot delete the global part.
    """
    if not can_delete_global_part(user, global_part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this global part. Only the creator or admin can delete global parts.",
        )


def require_build_list_part_delete_permission(
    user: DBUser, build_list_part: DBBuildListPart
) -> None:
    """
    Raise HTTPException if user cannot delete the build list part.
    """
    if not can_delete_build_list_part(user, build_list_part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this build list part. Only the user who added it or admin can delete build list parts.",
        )


def require_global_part_edit_permission(
    user: DBUser, global_part: DBGlobalPart
) -> None:
    """
    Raise HTTPException if user cannot edit the global part.
    """
    if not can_edit_global_part(user, global_part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to edit this global part. Only the creator or admin can edit global parts.",
        )


def require_build_list_part_edit_permission(
    user: DBUser, build_list_part: DBBuildListPart
) -> None:
    """
    Raise HTTPException if user cannot edit the build list part.
    """
    if not can_edit_build_list_part(user, build_list_part):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to edit this build list part. Only the user who added it or admin can edit build list parts.",
        )
