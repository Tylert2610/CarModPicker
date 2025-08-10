import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.build_list import BuildListCreate, BuildListRead, BuildListUpdate
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
    },
)
async def create_build_list(
    build_list: BuildListCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildList:
    # Verify car ownership
    db_car = await _verify_car_ownership(
        car_id=build_list.car_id,
        db=db,
        current_user=current_user,
        logger=logger,
        car_not_found_detail="Car not found",
        authorization_detail="Not authorized to create a build list for this car",
    )

    db_build_list = DBBuildList(**build_list.model_dump())
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
    },
)
async def read_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBBuildList:
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )  # Query the database
    if db_build_list is None:
        raise HTTPException(status_code=404, detail="Build List not found")

    logger.info(msg=f"Build List retrieved from database: {db_build_list}")
    return db_build_list


@router.get(
    "/car/{car_id}",
    response_model=list[BuildListRead],
    tags=["build_lists"],
    responses={},
)
async def read_build_lists_by_car(
    car_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBBuildList]:
    """
    Retrieve all build lists associated with a specific car.
    """
    build_lists = db.query(DBBuildList).filter(DBBuildList.car_id == car_id).all()
    if not build_lists:
        logger.info(f"No Build Lists found for car with id {car_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for car {car_id}: {build_lists}")
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
