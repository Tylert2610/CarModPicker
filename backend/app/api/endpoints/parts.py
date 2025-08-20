import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.api.schemas.part import PartCreate, PartRead, PartUpdate
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/",
    response_model=PartRead,
    responses={
        400: {"description": "Invalid part data"},
        403: {"description": "Not authorized to create parts"},
    },
)
async def create_part(
    part: PartCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBPart:
    """Create a new shared part."""
    # Create the part with the current user as creator
    part_data = part.model_dump()
    part_data["user_id"] = current_user.id

    db_part = DBPart(**part_data)
    db.add(db_part)
    db.commit()
    db.refresh(db_part)

    logger.info(f"Part created: {db_part.id} by user {current_user.id}")
    return db_part


@router.get(
    "/",
    response_model=List[PartRead],
    responses={
        200: {"description": "List of parts retrieved successfully"},
    },
)
async def read_parts(
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of parts to return"
    ),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(
        None, description="Search in part names and descriptions"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBPart]:
    """Get all parts with optional filtering and search."""
    query = db.query(DBPart)

    if category_id:
        query = query.filter(DBPart.category_id == category_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (DBPart.name.ilike(search_term)) | (DBPart.description.ilike(search_term))
        )

    parts = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(parts)} parts")
    return parts


@router.get(
    "/{part_id}",
    response_model=PartRead,
    responses={
        404: {"description": "Part not found"},
    },
)
async def read_part(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBPart:
    """Get a specific part by ID."""
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    logger.info(f"Part retrieved: {part_id}")
    return db_part


@router.put(
    "/{part_id}",
    response_model=PartRead,
    responses={
        404: {"description": "Part not found"},
        403: {"description": "Not authorized to update this part"},
    },
)
async def update_part(
    part_id: int,
    part: PartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBPart:
    """Update a part (only creator can update)."""
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    # Only the creator can update the part
    if db_part.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this part"
        )

    update_data = part.model_dump(exclude_unset=True)

    # Increment edit count
    update_data["edit_count"] = db_part.edit_count + 1

    # Update model fields
    for key, value in update_data.items():
        setattr(db_part, key, value)

    db.add(db_part)
    db.commit()
    db.refresh(db_part)

    logger.info(f"Part updated: {part_id} by user {current_user.id}")
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
) -> PartRead:
    """Delete a part (only creator can delete)."""
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    # Only the creator can delete the part
    if db_part.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this part"
        )

    # Convert the SQLAlchemy model to the Pydantic model before deleting
    deleted_part_data = PartRead.model_validate(db_part)

    db.delete(db_part)
    db.commit()

    logger.info(f"Part deleted: {part_id} by user {current_user.id}")
    return deleted_part_data


@router.get(
    "/user/{user_id}",
    response_model=List[PartRead],
    responses={
        200: {"description": "List of parts created by user"},
    },
)
async def read_parts_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of parts to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBPart]:
    """Get all parts created by a specific user."""
    parts = (
        db.query(DBPart)
        .filter(DBPart.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    logger.info(f"Retrieved {len(parts)} parts for user {user_id}")
    return parts
