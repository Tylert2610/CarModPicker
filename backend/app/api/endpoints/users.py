"""User account routes: registration, profile reads and updates, and deletion."""

import logging
import os
from typing import Any, Dict, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.dependencies.auth import (
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
    get_password_hash,
    verify_password,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.pagination import CursorPage
from app.api.schemas.user import (
    AdminUserUpdate,
    PublicUserRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.services.storage_service import storage_service
from app.api.services.user_service import UserService, user_read, user_reads
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params, paginate_in_memory
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.dynamo.models import utc_now
from app.db.dynamo.users import EMAIL, UniqueAttributeTaken
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()

user_service = UserService()


def _raise_duplicate(error: UniqueAttributeTaken) -> None:
    """Raise the 409 matching whichever unique attribute was already taken."""
    if error.attribute == EMAIL:
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
    ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")


def _delete_user_everywhere(repos: Repositories, user: DBUser) -> None:
    """Mark a user deleted and cascade the removal to everything referencing them."""
    repos.users.update(str(user.id), deleted=True, deleted_at=utc_now())

    repos.users.delete_user(user)


def _user_page(
    users: list[DBUser], params: CursorParams, repos: Repositories, full: bool
) -> CursorPage[Union[UserRead, PublicUserRead]]:
    """Return one page of users, as full or public reads."""
    if full:
        reads = {read.id: read for read in user_reads(users, repos)}
        return paginate_in_memory(
            users,
            limit=params.limit,
            cursor=params.cursor,
            sort_key=lambda user: user.username.lower(),
            item_id=lambda user: str(user.id),
            transform=lambda user: reads[user.id],
        )
    return paginate_in_memory(
        users,
        limit=params.limit,
        cursor=params.cursor,
        sort_key=lambda user: user.username.lower(),
        item_id=lambda user: str(user.id),
        transform=PublicUserRead.model_validate,
    )


@router.get("/me", response_model=UserRead)
async def read_users_me_route(
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> UserRead:
    """
    Fetch the current logged in user.
    """
    return user_read(current_user, repos)


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={
        200: {"description": "Count of users"},
    },
)
async def count_users() -> Dict[str, int]:
    """
    Get total count of users.
    """
    try:
        count = user_service.count_all(logger=logger)
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting users: {str(e)}")
        raise


@router.post("/me/profile-picture", response_model=UserRead)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> UserRead:
    """Upload a profile picture for the current user.

    This endpoint uploads the image to storage and automatically updates
    the user's image_urls field. If the user already has a profile picture,
    """
    try:
        file_key = storage_service.upload_image(
            file=file,
            entity_type="user",
            user_id=current_user.id,
            entity_id=current_user.id,
            force_square=True,
        )

        old_key = (current_user.image_urls or [None])[0]
        if old_key:
            try:
                storage_service.delete_image(old_key)
                logger.info(f"Deleted old profile picture for user {current_user.id}: {old_key}")
            except Exception as e:
                logger.warning(f"Failed to delete old profile picture for user {current_user.id}: {str(e)}")

        updated = repos.users.update(current_user.id, image_urls=[file_key])

        logger.info(f"User {current_user.id} uploaded new profile picture: {file_key}")
        return user_read(updated, repos)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during profile picture upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during profile picture upload",
        )


@router.delete("/me/profile-picture", response_model=UserRead)
async def delete_profile_picture(
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> UserRead:
    """Delete the current user's profile picture.

    This endpoint removes the profile picture from storage and clears
    the user's image_urls field.
    """
    old_file_key = (current_user.image_urls or [None])[0]
    if not old_file_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile picture found to delete",
        )

    try:
        storage_service.delete_image(old_file_key)
        updated = repos.users.update(current_user.id, image_urls=None)

        logger.info(f"User {current_user.id} deleted profile picture: {old_file_key}")
        return user_read(updated, repos)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during profile picture deletion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during profile picture deletion",
        )


@router.get(
    "/{user_id}",
    response_model=Union[UserRead, PublicUserRead],
    responses={
        404: {"description": "User not found"},
    },
)
async def get_user(
    user_id: UUID,
    repos: Repositories = Depends(get_repositories),
    current_user: Union[DBUser, None] = Depends(get_optional_current_user),
) -> Union[UserRead, PublicUserRead]:
    """Get a user by ID.

    Returns full UserRead (with email_verified and totp_enabled) if:
    """
    db_user = repos.users.get(user_id)
    if not db_user:
        ResponsePatterns.raise_not_found("User", user_id)

    if current_user is not None and (current_user.id == user_id or current_user.is_admin or current_user.is_superuser):
        assert current_user is not None
        logger.info(f"User {current_user.id} retrieved full user data for user {user_id}")
        return user_read(db_user, repos)
    else:
        user_id_str = "anonymous" if current_user is None else str(current_user.id)
        logger.info(f"User {user_id_str} retrieved public user data for user {user_id}")
        return PublicUserRead.model_validate(db_user)


@router.get(
    "/",
    response_model=CursorPage[Union[UserRead, PublicUserRead]],
    responses={
        200: {"description": "List of users retrieved successfully"},
    },
)
async def list_users(
    search: Optional[str] = Query(None, description="Search in usernames and emails"),
    params: CursorParams = Depends(get_cursor_params),
    repos: Repositories = Depends(get_repositories),
    current_user: Union[DBUser, None] = Depends(get_optional_current_user),
) -> CursorPage[Union[UserRead, PublicUserRead]]:
    """List all users with pagination and search.

    Returns full UserRead (with email_verified and totp_enabled) for each user if:
    """
    users = user_service.get_all_users(search=search, logger=logger)

    can_see_sensitive_fields = current_user is not None and (current_user.is_admin or current_user.is_superuser)
    page = _user_page(users, params, repos, full=can_see_sensitive_fields)

    if can_see_sensitive_fields:
        assert current_user is not None
        logger.info(f"Admin/superuser {current_user.id} retrieved {len(page.items)} users with full data")
    else:
        user_id_str = "anonymous" if current_user is None else str(current_user.id)
        logger.info(f"User {user_id_str} retrieved {len(page.items)} users with public data")
    return page


@router.post(
    "/",
    response_model=UserRead,
    responses=crud_responses("user", "create"),
)
async def create_user(
    user: UserCreate,
    repos: Repositories = Depends(get_repositories),
) -> UserRead:
    """
    Creates a new user in the database.
    """
    if repos.users.get_by_username(user.username):
        ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")

    if repos.users.get_by_email(user.email):
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")

    hashed_password = get_password_hash(user.password)
    email_verified = os.environ.get("TESTING") == "true"

    db_user = DBUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        email_verified=email_verified,
    )

    try:
        repos.users.create_user(db_user)
    except UniqueAttributeTaken as e:
        _raise_duplicate(e)
    logger.info(msg=f"User added to database: {db_user.id}")
    return user_read(db_user, repos)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "update"),
)
async def update_user(
    user_id: UUID,
    user: UserUpdate,
    response: Response,
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_user),
) -> UserRead:
    """Update a user profile the caller is allowed to modify."""
    db_user = repos.users.get(user_id)

    if not db_user:
        logger.warning(f"Attempt to update non-existent user {user_id}.")
        ResponsePatterns.raise_not_found("User", user_id)

    if db_user.id != current_user.id:
        logger.warning(f"User {current_user.id} attempt to update user {user_id} " f"without authorization.")
        ResponsePatterns.raise_forbidden("Not authorized to update this user")

    update_data_dict = user.model_dump(exclude_unset=True)
    password_is_being_changed = "password" in update_data_dict and update_data_dict["password"]
    current_password_provided = user.current_password is not None

    if password_is_being_changed:
        if not current_password_provided:
            ResponsePatterns.raise_bad_request("Current password is required to change your password")
        assert user.current_password is not None
        if not verify_password(user.current_password, db_user.hashed_password):
            logger.warning(f"User {current_user.id} provided incorrect current password for update.")
            ResponsePatterns.raise_unauthorized("Incorrect current password")
    elif current_password_provided:
        assert user.current_password is not None
        if not verify_password(user.current_password, db_user.hashed_password):
            logger.warning(f"User {current_user.id} provided incorrect current password for update.")
            ResponsePatterns.raise_unauthorized("Incorrect current password")

    update_data = user.model_dump(exclude_unset=True, exclude={"current_password", "otp"})
    username_changed = False
    session_expire_minutes_changed = False
    changes: dict[str, Any] = {}

    if (
        "username" in update_data
        and update_data["username"] is not None
        and update_data["username"] != db_user.username
    ):
        username_changed = True

    if "session_expire_minutes" in update_data:
        val = update_data["session_expire_minutes"]
        if val is None:
            if db_user.session_expire_minutes is not None:
                session_expire_minutes_changed = True
            changes["session_expire_minutes"] = None
        else:
            clamped = max(
                settings.ACCESS_TOKEN_EXPIRE_MINUTES_MIN,
                min(settings.ACCESS_TOKEN_EXPIRE_MINUTES_MAX, val),
            )
            if clamped != db_user.session_expire_minutes:
                session_expire_minutes_changed = True
            changes["session_expire_minutes"] = clamped
        del update_data["session_expire_minutes"]

    if "password" in update_data and update_data["password"]:
        changes["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]

    for field, value in update_data.items():
        if value is not None:
            changes[field] = value

    try:
        db_user = repos.users.update_user(user_id, **changes) if changes else db_user
        logger.info(f"User {user_id} updated successfully by user {current_user.id}.")

        if username_changed or session_expire_minutes_changed:
            if username_changed:
                logger.info(
                    f"Username for user {user_id} changed to '{db_user.username}'. "
                    f"Client should re-authenticate to get new token."
                )
            if session_expire_minutes_changed:
                logger.info(
                    f"Session expiry preference updated for user {user_id}. "
                    f"Returning new token with updated expiry."
                )
            new_access_token_data = {"sub": db_user.username}
            expires_delta = get_access_token_expires_delta_for_user(db_user)
            new_access_token = create_access_token(data=new_access_token_data, expires_delta=expires_delta)
            response.headers["X-New-Access-Token"] = new_access_token

    except UniqueAttributeTaken as e:
        logger.warning(f"Duplicate {e.attribute} during user update for user {user_id}")
        _raise_duplicate(e)
    return user_read(db_user, repos)


@router.delete(
    "/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "delete"),
)
async def delete_user(
    user_id: UUID,
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_user),
) -> UserRead:
    """
    Delete a user account. Users can only delete their own account.
    """
    if user_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to delete user {user_id} " f"without authorization.")
        ResponsePatterns.raise_forbidden("Not authorized to delete this user")

    db_user = repos.users.get(user_id)
    if not db_user:
        ResponsePatterns.raise_not_found("User", user_id)

    deleted_user_data = user_read(db_user, repos)

    _delete_user_everywhere(repos, db_user)
    logger.info(f"User {current_user.id} deleted their own account")
    return deleted_user_data


@router.get(
    "/admin/users",
    response_model=CursorPage[UserRead],
    responses=crud_responses("user", "list", allow_public_read=False),
)
async def get_all_users(
    search: Optional[str] = Query(None, description="Search in usernames and emails"),
    params: CursorParams = Depends(get_cursor_params),
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CursorPage[UserRead]:
    """
    Get all users (admin only) with pagination and search.
    """
    users = user_service.get_all_users(search=search, logger=logger)
    reads = {read.id: read for read in user_reads(users, repos)}
    page = paginate_in_memory(
        users,
        limit=params.limit,
        cursor=params.cursor,
        sort_key=lambda user: user.username.lower(),
        item_id=lambda user: str(user.id),
        transform=lambda user: reads[user.id],
    )

    logger.info(
        f"Admin {current_user.id} retrieved {len(page.items)} users (total: {len(users)})"
        + (f" with search: '{search}'" if search else "")
    )
    return page


@router.put(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "update"),
)
async def admin_update_user(
    user_id: UUID,
    user_update: AdminUserUpdate,
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_admin_user),
) -> UserRead:
    """
    Update a user with admin privileges (admin only).
    """
    db_user = repos.users.get(user_id)
    if db_user is None:
        ResponsePatterns.raise_not_found("User", user_id)

    if user_id == current_user.id and (user_update.is_admin is False or user_update.is_superuser is False):
        ResponsePatterns.raise_bad_request("Cannot remove your own admin privileges")

    update_data = user_update.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    for key in ("username", "email"):
        if key in update_data and update_data[key] is None:
            del update_data[key]

    try:
        updated = repos.users.update_user(user_id, **update_data) if update_data else db_user
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        return user_read(updated, repos)
    except UniqueAttributeTaken as e:
        logger.warning(f"Duplicate {e.attribute} during admin user update")
        ResponsePatterns.raise_conflict("Username or email already exists", "USERNAME_EMAIL_EXISTS")


@router.delete(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "delete"),
)
async def admin_delete_user(
    user_id: UUID,
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_admin_user),
) -> UserRead:
    """
    Delete a user with admin privileges (admin only).
    """
    if user_id == current_user.id:
        ResponsePatterns.raise_bad_request("Cannot delete your own account")

    db_user = repos.users.get(user_id)
    if db_user is None:
        ResponsePatterns.raise_not_found("User", user_id)

    deleted_user_data = user_read(db_user, repos)

    _delete_user_everywhere(repos, db_user)
    logger.info(f"Admin {current_user.id} deleted user {user_id}")
    return deleted_user_data
