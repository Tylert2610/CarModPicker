import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_part import (
    BuildListPartCreate,
    BuildListPartRead,
    BuildListPartUpdate,
)
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/build-lists/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or part not found"},
        403: {"description": "Not authorized to add parts to this build list"},
        409: {"description": "Part already exists in build list"},
    },
)
async def add_part_to_build_list(
    build_list_id: int,
    part_id: int,
    build_list_part: BuildListPartCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildListPart:
    """Add an existing part to a build list."""
    # Verify build list exists and user owns it
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if db_build_list.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this build list"
        )

    # Verify part exists
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check if part is already in build list
    existing_relationship = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
        .first()
    )
    if existing_relationship:
        raise HTTPException(status_code=409, detail="Part already exists in build list")

    # Create the relationship
    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        part_id=part_id,
        added_by=current_user.id,
        notes=build_list_part.notes,
    )

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Part {part_id} added to build list {build_list_id} by user {current_user.id}"
    )
    return db_build_list_part


@router.get(
    "/build-lists/{build_list_id}/parts",
    response_model=List[BuildListPartRead],
    responses={
        404: {"description": "Build list not found"},
        403: {"description": "Not authorized to access this build list"},
    },
)
async def get_parts_in_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[DBBuildListPart]:
    """Get all parts in a build list."""
    # Verify build list exists and user owns it
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if db_build_list.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this build list"
        )

    build_list_parts = (
        db.query(DBBuildListPart)
        .filter(DBBuildListPart.build_list_id == build_list_id)
        .all()
    )

    logger.info(
        f"Retrieved {len(build_list_parts)} parts from build list {build_list_id}"
    )
    return build_list_parts


@router.put(
    "/build-lists/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or part relationship not found"},
        403: {"description": "Not authorized to modify this build list"},
    },
)
async def update_part_in_build_list(
    build_list_id: int,
    part_id: int,
    build_list_part: BuildListPartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBBuildListPart:
    """Update a part's notes in a build list."""
    # Verify build list exists and user owns it
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if db_build_list.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this build list"
        )

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(status_code=404, detail="Part not found in build list")

    # Update the notes
    update_data = build_list_part.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Part {part_id} updated in build list {build_list_id} by user {current_user.id}"
    )
    return db_build_list_part


@router.delete(
    "/build-lists/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or part relationship not found"},
        403: {"description": "Not authorized to modify this build list"},
    },
)
async def remove_part_from_build_list(
    build_list_id: int,
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Remove a part from a build list."""
    # Verify build list exists and user owns it
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if db_build_list.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this build list"
        )

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(status_code=404, detail="Part not found in build list")

    # Convert to response model before deleting
    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(
        f"Part {part_id} removed from build list {build_list_id} by user {current_user.id}"
    )
    return deleted_data
