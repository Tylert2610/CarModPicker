import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.build_list import BuildListCreate, BuildListRead, BuildListUpdate
from app.api.services.subscription_service import SubscriptionService
from app.core.logging import get_logger
from app.db.session import get_db


# Shared function to verify car ownership
async def _verify_car_ownership(
    car_id: int,
    db: Session,
    current_user: DBUser,
    logger: logging.Logger,
    car_not_found_detail: str | None = None,
    authorization_detail: str | None = None,
) -> DBCar:
    db_car = db.query(DBCar).filter(DBCar.id == car_id).first()
    if not db_car:
        detail = car_not_found_detail or f"Car with id {car_id} not found"
        logger.warning(
            f"Car ownership verification failed: {detail} (User: {current_user.id if current_user else 'Unknown'})"
        )
        raise HTTPException(status_code=404, detail=detail)

    if db_car.user_id != current_user.id:
        detail = (
            authorization_detail
            or "Not authorized to perform this action on the specified car"
        )
        logger.warning(
            f"Car ownership verification failed: {detail} (User: {current_user.id}, Car Owner: {db_car.user_id})"
        )
        raise HTTPException(status_code=403, detail=detail)

    return db_car


router = APIRouter()


@router.post(
    "/",
    response_model=BuildListRead,
    responses={
        400: {"description": "Build List already exists"},
        403: {"description": "Not authorized to create a build list"},
        402: {"description": "Subscription limit reached"},
    },
)
async def create_build_list(
    build_list: BuildListCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildList:
    # Check subscription limits
    if not SubscriptionService.can_create_build_list(db, current_user):
        limits = SubscriptionService.get_user_limits(current_user)
        usage = SubscriptionService.get_user_usage(db, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Build list creation limit reached. Upgrade to premium for unlimited build lists.",
                "limits": limits,
                "usage": usage,
            },
        )

    # Verify car ownership
    db_car = await _verify_car_ownership(
        car_id=build_list.car_id,
        db=db,
        current_user=current_user,
        logger=logger,
        car_not_found_detail="Car not found",
        authorization_detail="Not authorized to create a build list for this car",
    )

    db_build_list = DBBuildList(**build_list.model_dump(), user_id=current_user.id)
    db.add(db_build_list)
    db.commit()
    db.refresh(db_build_list)
    logger.info(msg=f"Build List added to database: {db_build_list}")
    return db_build_list


@router.get(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        404: {"description": "Build List not found"},
        403: {"description": "Not authorized to access this build list"},
        401: {"description": "Not authenticated"},
    },
)
async def read_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildList:
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )  # Query the database
    if db_build_list is None:
        raise HTTPException(status_code=404, detail="Build List not found")

    # Check authorization - users can only access their own build lists, or admins can access any
    if (
        current_user.id != db_build_list.user_id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this build list"
        )

    logger.info(msg=f"Build List retrieved from database: {db_build_list}")
    return db_build_list


@router.get(
    "/car/{car_id}",
    response_model=list[BuildListRead],
    tags=["build_lists"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to access this car's build lists"},
    },
)
async def read_build_lists_by_car(
    car_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of build lists to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[DBBuildList]:
    """
    Retrieve all build lists associated with a specific car with pagination.
    Users can only access build lists for cars they own, or admins can access any car's build lists.
    """
    # First check if the car exists and get its owner
    from app.api.models.car import Car as DBCar

    db_car = db.query(DBCar).filter(DBCar.id == car_id).first()
    if not db_car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Check authorization - users can only access build lists for cars they own, or admins can access any
    if (
        current_user.id != db_car.user_id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this car's build lists"
        )

    build_lists = (
        db.query(DBBuildList)
        .filter(DBBuildList.car_id == car_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not build_lists:
        logger.info(f"No Build Lists found for car with id {car_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for car {car_id}: {build_lists}")
    return build_lists


@router.get(
    "/user/me",
    response_model=list[BuildListRead],
    tags=["build_lists"],
    responses={
        401: {"description": "Not authenticated"},
    },
)
async def read_my_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of build lists to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[DBBuildList]:
    """
    Retrieve all build lists owned by the current user with pagination.
    """
    build_lists = (
        db.query(DBBuildList)
        .filter(DBBuildList.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {current_user.id}")
    else:
        logger.info(
            msg=f"Build Lists retrieved for user {current_user.id}: {build_lists}"
        )
    return build_lists


@router.get(
    "/user/{user_id}",
    response_model=list[BuildListRead],
    tags=["build_lists"],
    responses={
        403: {"description": "Not authorized to access this user's build lists"},
    },
)
async def read_build_lists_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of build lists to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[DBBuildList]:
    """
    Retrieve all build lists owned by a specific user with pagination.
    Users can only access their own build lists, or admins can access any user's build lists.
    """
    # Check authorization - users can only access their own build lists, or admins can access any
    if (
        current_user.id != user_id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this user's build lists"
        )

    build_lists = (
        db.query(DBBuildList)
        .filter(DBBuildList.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {user_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {user_id}: {build_lists}")
    return build_lists


@router.put(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        404: {"description": "Build List not found or New Car not found"},
        403: {
            "description": "Not authorized to update this build list or associate it with the new car"
        },
    },
)
async def update_build_list(
    build_list_id: int,
    build_list: BuildListUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildList:
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if db_build_list is None:
        raise HTTPException(status_code=404, detail="Build List not found")

    # Verify car ownership for the build list
    await _verify_car_ownership(
        car_id=int(db_build_list.car_id),
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to update this build list",
    )

    # If car_id is being updated, verify ownership of the new car
    update_data = build_list.model_dump(exclude_unset=True)
    if "car_id" in update_data and update_data["car_id"] != db_build_list.car_id:
        new_car_id = update_data["car_id"]
        await _verify_car_ownership(
            car_id=new_car_id,
            db=db,
            current_user=current_user,
            logger=logger,
            car_not_found_detail=f"New car with id {new_car_id} not found",
            authorization_detail="Not authorized to associate build list with the new car",
        )

    # Update model fields
    for key, value in update_data.items():
        setattr(db_build_list, key, value)

    db.add(db_build_list)
    db.commit()
    db.refresh(db_build_list)
    logger.info(msg=f"Build List updated in database: {db_build_list}")
    return db_build_list


@router.delete(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        404: {"description": "Build List not found"},
        403: {"description": "Not authorized to delete this build list"},
    },
)
async def delete_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListRead:
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if db_build_list is None:
        raise HTTPException(status_code=404, detail="Build List not found")

    # Verify car ownership for the build list
    await _verify_car_ownership(
        car_id=int(db_build_list.car_id),
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to delete this build list",
    )

    # Convert the SQLAlchemy model to the Pydantic model *before* deleting
    deleted_build_list_data = BuildListRead.model_validate(db_build_list)

    db.delete(db_build_list)
    db.commit()
    # Log the deleted build_list data
    logger.info(msg=f"Build List deleted from database: {deleted_build_list_data}")
    return deleted_build_list_data
