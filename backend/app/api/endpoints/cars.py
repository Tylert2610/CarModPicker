import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.subscription_service import SubscriptionService
from app.core.logging import get_logger
from app.db.session import get_db


# Helper function to get and verify car ownership
async def _verify_car_ownership(
    car_id: int,
    db: Session,
    current_user: DBUser,
    logger: logging.Logger,
    not_found_detail: str = "Car not found",
    authorization_detail: str = "Not authorized to perform this action on this car",
) -> DBCar:
    db_car = db.query(DBCar).filter(DBCar.id == car_id).first()
    if not db_car:
        logger.warning(f"Car with id {car_id} not found. User: {current_user.id}")
        raise HTTPException(status_code=404, detail=not_found_detail)

    if db_car.user_id != current_user.id:
        logger.warning(
            f"Authorization failed for car id {car_id}. User: {current_user.id}, Car Owner: {db_car.user_id}"
        )
        raise HTTPException(status_code=403, detail=authorization_detail)

    return db_car


router = APIRouter()


@router.post(
    "/",
    response_model=CarRead,
    responses={
        400: {"description": "Car already exists"},
        403: {"description": "Not authorized to create a car"},
        402: {"description": "Subscription limit reached"},
    },
)
async def create_car(
    car: CarCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBCar:
    # Check subscription limits
    if not SubscriptionService.can_create_car(db, current_user):
        limits = SubscriptionService.get_user_limits(current_user)
        usage = SubscriptionService.get_user_usage(db, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Car creation limit reached. Upgrade to premium for unlimited cars.",
                "limits": limits,
                "usage": usage,
            },
        )

    db_car = DBCar(**car.model_dump(), user_id=current_user.id)
    db.add(db_car)
    db.commit()
    db.refresh(db_car)
    logger.info(msg=f"Car added to database: {db_car}")
    return db_car


@router.get(
    "/{car_id}",
    response_model=CarRead,
    responses={
        404: {"description": "Car not found"},
        403: {"description": "Not authorized to access this car"},
    },
)
async def read_car(
    car_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBCar:

    db_car = db.query(DBCar).filter(DBCar.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")

    logger.info(msg=f"Car retrieved from database: {db_car}")
    return db_car


@router.get(
    "/user/{user_id}",
    response_model=List[CarRead],
    tags=["cars"],
)
async def read_cars_by_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBCar]:
    """
    Retrieve all cars owned by a specific user.
    """
    cars = db.query(DBCar).filter(DBCar.user_id == user_id).all()
    if not cars:
        logger.info(f"No cars found for user_id: {user_id}")
    else:
        logger.info(f"Retrieved {len(cars)} cars for user_id: {user_id}")
    return cars


@router.put(
    "/{car_id}",
    response_model=CarRead,
    responses={
        404: {"description": "Car not found"},
        403: {"description": "Not authorized to update this car"},
    },
)
async def update_car(
    car_id: int,
    car: CarUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBCar:
    db_car = await _verify_car_ownership(
        car_id=car_id,
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to update this car",
    )

    # Update model fields
    update_data = car.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_car, key, value)

    db.add(db_car)
    db.commit()
    db.refresh(db_car)
    logger.info(msg=f"Car updated in database: {db_car}")
    return db_car


@router.delete(
    "/{car_id}",
    response_model=CarRead,
    responses={
        404: {"description": "Car not found"},
        403: {"description": "Not authorized to delete this car"},
    },
)
async def delete_car(
    car_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> CarRead:
    db_car = await _verify_car_ownership(
        car_id=car_id,
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to delete this car",
    )

    # Convert the SQLAlchemy model to the Pydantic model *before* deleting
    deleted_car_data = CarRead.model_validate(db_car)

    db.delete(db_car)
    db.commit()
    # Log the deleted car data
    logger.info(msg=f"car deleted from database: {deleted_car_data}")
    return deleted_car_data
