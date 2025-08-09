from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.core.logging import get_logger
from app.db.session import get_db
from app.api.models.part import Part as DBPart
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.models.build_list import BuildList as DBBuildList
from app.api.schemas.part import PartCreate, PartRead, PartUpdate
from app.api.dependencies.auth import get_current_user


# Shared function to verify build list ownership (via car)
async def _verify_build_list_ownership(
    build_list_id: int,
    db: Session,
    current_user: DBUser,
    logger: logging.Logger,
    build_list_not_found_detail: str | None = None,
    authorization_detail: str | None = None,
) -> DBBuildList:
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )

    if not db_build_list:
        detail = (
            build_list_not_found_detail
            or f"Build List with id {build_list_id} not found"
        )
        logger.warning(
            f"Build list ownership verification failed: {detail} (User: {current_user.id if current_user else 'Unknown'})"
        )
        raise HTTPException(status_code=404, detail=detail)

    # Assuming DBBuildList has a relationship 'car' which has a 'user_id'
    if not hasattr(db_build_list, "car") or db_build_list.car is None:
        # This case might indicate a data integrity issue or a build list not linked to a car
        detail = f"Build List with id {build_list_id} is not associated with a car."
        logger.error(
            f"Build list ownership verification failed: {detail} (User: {current_user.id if current_user else 'Unknown'}, BuildListID: {build_list_id})"
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Build list data is inconsistent.",
        )

    if db_build_list.car.user_id != current_user.id:
        detail = (
            authorization_detail
            or "Not authorized to perform this action on this build list"
        )
        logger.warning(
            f"Build list ownership verification failed: {detail} (User: {current_user.id}, Car Owner: {db_build_list.car.user_id})"
        )
        raise HTTPException(status_code=403, detail=detail)

    return db_build_list


router = APIRouter()


@router.post(
    "/",
    response_model=PartRead,
    responses={
        400: {"description": "Part already exists"},
        403: {"description": "Not authorized to create a part"},
    },
)
async def create_part(
    part: PartCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
):
    # Verify ownership of the build list (via the car)
    db_build_list = await _verify_build_list_ownership(
        build_list_id=part.build_list_id,
        db=db,
        current_user=current_user,
        logger=logger,
        build_list_not_found_detail="Build List not found",
        authorization_detail="Not authorized to add a part to this build list",
    )

    db_part = DBPart(**part.model_dump())
    db.add(db_part)
    db.commit()
    db.refresh(db_part)
    logger.info(msg=f"part added to database: {db_part}")
    return db_part


@router.get(
    "/{part_id}",
    response_model=PartRead,
    responses={
        404: {"description": "Part not found"},
        403: {"description": "Not authorized to access this part"},
    },
)
async def read_part(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
):
    db_part = (
        db.query(DBPart).filter(DBPart.id == part_id).first()
    )  # Query the database
    if db_part is None:
        raise HTTPException(status_code=404, detail="part not found")

    logger.info(msg=f"part retrieved from database: {db_part}")
    return db_part


@router.get(
    "/build-list/{build_list_id}",
    response_model=list[PartRead],
    tags=["parts"],
)
async def read_parts_by_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
):
    """
    Retrieve all parts for a specific build list by its ID.
    """
    parts = db.query(DBPart).filter(DBPart.build_list_id == build_list_id).all()
    if not parts:
        logger.info(f"No parts found for Build List ID {build_list_id}")
    else:
        logger.info(f"Retrieved {len(parts)} parts for Build List ID {build_list_id}")
    return parts


@router.put(
    "/{part_id}",
    response_model=PartRead,
    responses={
        404: {"description": "Part not found or New Build List not found"},
        403: {
            "description": "Not authorized to update this part or move part to the new build list"
        },
    },
)
async def update_part(
    part_id: int,
    part: PartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
):
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="part not found")

    # Verify ownership of the current build list (via the car)
    await _verify_build_list_ownership(
        build_list_id=db_part.build_list_id,
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to update this part",
    )

    update_data = part.model_dump(exclude_unset=True)

    # If build_list_id is being updated, verify ownership of the new build list
    if (
        "build_list_id" in update_data
        and update_data["build_list_id"] != db_part.build_list_id
    ):
        new_build_list_id = update_data["build_list_id"]
        await _verify_build_list_ownership(
            build_list_id=new_build_list_id,
            db=db,
            current_user=current_user,
            logger=logger,
            build_list_not_found_detail=f"New Build List with id {new_build_list_id} not found",
            authorization_detail="Not authorized to move part to the new build list",
        )

    # Update model fields
    for key, value in update_data.items():
        setattr(db_part, key, value)

    db.add(db_part)
    db.commit()
    db.refresh(db_part)
    logger.info(msg=f"part updated in database: {db_part}")
    return db_part


@router.delete(
    "/{part_id}",
    response_model=PartRead,
    responses={
        404: {"description": "Part not found"},
        403: {"description": "Not authorized to delete this part"},
    },
)
async def delete_part(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
):
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="part not found")

    # Verify ownership of the build list (via the car)
    await _verify_build_list_ownership(
        build_list_id=db_part.build_list_id,
        db=db,
        current_user=current_user,
        logger=logger,
        authorization_detail="Not authorized to delete this part",
    )

    # Convert the SQLAlchemy model to the Pydantic model *before* deleting
    deleted_part_data = PartRead.model_validate(db_part)

    db.delete(db_part)
    db.commit()
    # Log the deleted part data
    logger.info(msg=f"part deleted from database: {deleted_part_data}")
    return deleted_part_data
