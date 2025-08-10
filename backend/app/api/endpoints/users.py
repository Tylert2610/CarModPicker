import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_users_me_route(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Fetch the current logged in user.
    """
    return current_user


@router.post(
    "/",
    response_model=UserRead,
    responses={
        400: {"description": "User already exists"},
        403: {"description": "Not authorized to create a user"},
    },
)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBUser:
    """
    Creates a new user in the database.
    """

    # Checked if the user already exists
    db_user_by_username = (
        db.query(DBUser).filter(DBUser.username == user.username).first()
    )
    if db_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    db_user_by_email = db.query(DBUser).filter(DBUser.email == user.email).first()
    if db_user_by_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash the received password
    hashed_password = get_password_hash(user.password)

    # Create DBUser instance (excluding plain password)
    db_user = DBUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(msg=f"User added to database: {db_user}")
    return db_user


@router.get(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {"description": "User not found"},
        403: {"description": "Not authorized to access this user"},
    },
)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBUser:
    db_user = (
        db.query(DBUser).filter(DBUser.id == user_id).first()
    )  # Query the database
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    logger.info(msg=f"User retrieved from database: {db_user}")
    return db_user


@router.put(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {"description": "User not found"},
        403: {"description": "Not authorized to update this user"},
        400: {
            "description": "Invalid input, e.g., username or email already registered"
        },
    },
)
async def update_user(
    user_id: int,
    user: UserUpdate,
    response: Response,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()

    if not db_user:
        logger.warning(f"Attempt to update non-existent user {user_id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if the current user is the user being updated
    if db_user.id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempt to update user {user_id} without authorization."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    if user.current_password and not verify_password(
        user.current_password, db_user.hashed_password
    ):
        logger.warning(
            f"User {current_user.id} provided incorrect current password for update."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password",
        )

    update_data = user.model_dump(
        exclude_unset=True, exclude={"current_password"}
    )  # Exclude current_password from data to be saved
    username_changed = False

    if (
        "username" in update_data
        and update_data["username"] is not None
        and update_data["username"] != db_user.username
    ):
        username_changed = True

    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"])
        db_user.hashed_password = hashed_password

        del update_data["password"]

    for field, value in update_data.items():
        if value is not None:  # Ensures only set fields that are explicitly provided
            setattr(db_user, field, value)

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User {user_id} updated successfully by user {current_user.id}.")

        if username_changed:
            logger.info(
                f"Username for user {user_id} changed to '{db_user.username}'. Issuing new access token."
            )
            # Create a new access token with the new username
            new_access_token_data = {"sub": db_user.username}
            new_access_token = create_access_token(data=new_access_token_data)

            # Set the new token in an HTTP-only cookie
            response.set_cookie(
                key="access_token",
                value=new_access_token,
                httponly=True,
                max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                path="/",
                samesite="lax",
                secure=False,  # TODO: Change to True in production if served over HTTPS (e.g., settings.SECURE_COOKIES)
            )

    except IntegrityError as e:
        db.rollback()
        logger.warning(
            f"IntegrityError during user update for user {user_id}: {e.orig}"
        )
        error_detail_str = str(e.orig).lower()
        if (
            "users_username_key" in error_detail_str
            or "ix_users_username" in error_detail_str
            or (
                "unique constraint" in error_detail_str
                and "users.username" in error_detail_str
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        elif (
            "users_email_key" in error_detail_str
            or "ix_users_email" in error_detail_str
            or (
                "unique constraint" in error_detail_str
                and "users.email" in error_detail_str
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with the provided username or email may already exist, or another integrity constraint was violated.",
            )
    return db_user


@router.delete(
    "/{user_id}",
    response_model=UserRead,
    responses={
        404: {"description": "User not found"},
        403: {"description": "Not authorized to delete this user"},
    },
)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> UserRead:
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )

    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Convert the SQLAlchemy model to the Pydantic model *before* deleting
    deleted_user_data = UserRead.model_validate(db_user)

    db.delete(db_user)
    db.commit()
    # Log the deleted user data
    logger.info(msg=f"User deleted from database: {deleted_user_data.id}")
    return deleted_user_data
