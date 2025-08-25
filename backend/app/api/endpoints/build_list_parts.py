import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_part import (
    BuildListPartCreate,
    BuildListPartRead,
    BuildListPartReadWithGlobalPart,
    BuildListPartUpdate,
)
from app.api.schemas.global_part import GlobalPartCreate
from app.api.utils.authorization import (
    require_build_list_part_edit_permission,
    require_build_list_part_delete_permission,
)
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


class CreateGlobalPartAndAddToBuildListRequest(BaseModel):
    """Request model for creating a global part and adding it to a build list."""

    # Global part fields
    name: str
    description: str | None = None
    price: int | None = Field(
        None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)"
    )
    image_url: str | None = None
    category_id: int
    brand: str | None = None
    part_number: str | None = None
    specifications: dict | None = None

    # Build list part fields
    notes: str | None = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError(
                "Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)"
            )
        return v


@router.post(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or global part not found"},
        403: {"description": "Not authorized to add parts to this build list"},
        409: {"description": "Global part already exists in build list"},
    },
)
async def add_global_part_to_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Add an existing global part to a build list as a build list part."""
    # Verify build list exists and user owns it or is admin
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if (
        db_build_list.user_id != current_user.id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this build list"
        )

    # Verify global part exists
    db_global_part = (
        db.query(DBGlobalPart).filter(DBGlobalPart.id == global_part_id).first()
    )
    if not db_global_part:
        raise HTTPException(status_code=404, detail="Global part not found")

    # Check if global part is already in build list
    existing_relationship = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if existing_relationship:
        raise HTTPException(
            status_code=409, detail="Global part already exists in build list"
        )

    # Create the relationship
    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        global_part_id=global_part_id,
        added_by=current_user.id,
        quantity=build_list_part.quantity,
        notes=build_list_part.notes,
    )

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Global part {global_part_id} added to build list {build_list_id} as build list part {db_build_list_part.id} by user {current_user.id}"
    )
    return db_build_list_part


@router.get(
    "/{build_list_id}",
    response_model=List[BuildListPartRead],
    responses={
        404: {"description": "Build list not found"},
        403: {"description": "Not authorized to access this build list"},
    },
)
async def get_build_list_parts(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListPartRead]:
    """Get all build list parts in a build list."""
    # Verify build list exists and user owns it or is admin
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if (
        db_build_list.user_id != current_user.id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this build list"
        )

    db_build_list_parts = (
        db.query(DBBuildListPart)
        .filter(DBBuildListPart.build_list_id == build_list_id)
        .all()
    )

    build_list_parts = [
        BuildListPartRead.model_validate(part) for part in db_build_list_parts
    ]

    logger.info(
        f"Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}"
    )
    return build_list_parts


@router.put(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list part not found"},
        403: {"description": "Not authorized to modify this build list part"},
    },
)
async def update_build_list_part(
    build_list_part_id: int,
    build_list_part: BuildListPartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part."""
    # Find the build list part
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(DBBuildListPart.id == build_list_part_id)
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(status_code=404, detail="Build list part not found")

    # Check authorization - only the user who added the part or admin can edit it
    require_build_list_part_edit_permission(current_user, db_build_list_part)

    # Update the fields
    update_data = build_list_part.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Build list part {db_build_list_part.id} updated by user {current_user.id}"
    )
    return db_build_list_part


@router.delete(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list part not found"},
        403: {"description": "Not authorized to delete this build list part"},
    },
)
async def delete_build_list_part(
    build_list_part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Delete a build list part."""
    # Find the build list part
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(DBBuildListPart.id == build_list_part_id)
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(status_code=404, detail="Build list part not found")

    # Check authorization - only the user who added the part or admin can delete it
    require_build_list_part_delete_permission(current_user, db_build_list_part)

    # Convert to response model before deleting
    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(
        f"Build list part {db_build_list_part.id} deleted by user {current_user.id}"
    )
    return deleted_data


@router.post(
    "/{build_list_id}/create-and-add-part",
    response_model=BuildListPartReadWithGlobalPart,
    responses={
        404: {"description": "Build list not found"},
        403: {"description": "Not authorized to add parts to this build list"},
        409: {"description": "Global part already exists in build list"},
    },
)
async def create_global_part_and_add_to_build_list(
    build_list_id: int,
    request: CreateGlobalPartAndAddToBuildListRequest,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartReadWithGlobalPart:
    """Create a new global part and automatically add it to the specified build list as a build list part."""
    # Verify build list exists and user owns it or is admin
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if (
        db_build_list.user_id != current_user.id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this build list"
        )

    # Create the global part with the current user as creator
    global_part_dict = {
        "name": request.name,
        "description": request.description,
        "price": request.price,
        "image_url": request.image_url,
        "category_id": request.category_id,
        "brand": request.brand,
        "part_number": request.part_number,
        "specifications": request.specifications,
        "user_id": current_user.id,
    }

    db_global_part = DBGlobalPart(**global_part_dict)
    db.add(db_global_part)
    db.flush()  # Get the ID without committing yet

    # Create the build list part relationship
    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        global_part_id=db_global_part.id,
        added_by=current_user.id,
        quantity=1,
        notes=request.notes,
    )

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_global_part)
    db.refresh(db_build_list_part)

    logger.info(
        f"Global part {db_global_part.id} created and added to build list {build_list_id} as build list part {db_build_list_part.id} by user {current_user.id}"
    )

    # Return the build list part with global part details
    return BuildListPartReadWithGlobalPart(
        id=db_build_list_part.id,
        build_list_id=db_build_list_part.build_list_id,
        global_part_id=db_build_list_part.global_part_id,
        added_by=db_build_list_part.added_by,
        quantity=db_build_list_part.quantity,
        notes=db_build_list_part.notes,
        added_at=db_build_list_part.added_at,
        global_part=db_global_part,
    )


@router.get(
    "/{build_list_id}/global-parts",
    response_model=List[BuildListPartReadWithGlobalPart],
    responses={
        404: {"description": "Build list not found"},
        403: {"description": "Not authorized to access this build list"},
    },
)
async def get_global_parts_in_build_list(
    build_list_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListPartReadWithGlobalPart]:
    """Get all build list parts in a build list."""
    # Verify build list exists and user owns it or is admin
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    if (
        db_build_list.user_id != current_user.id
        and not current_user.is_admin
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this build list"
        )

    db_build_list_parts = (
        db.query(DBBuildListPart)
        .options(joinedload(DBBuildListPart.global_part))
        .filter(DBBuildListPart.build_list_id == build_list_id)
        .all()
    )

    build_list_parts = [
        BuildListPartReadWithGlobalPart.model_validate(part)
        for part in db_build_list_parts
    ]

    logger.info(
        f"Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}"
    )
    return build_list_parts


@router.put(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or build list part not found"},
        403: {"description": "Not authorized to modify this build list part"},
    },
)
async def update_global_part_in_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part's notes in a build list."""
    # Verify build list exists
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(
            status_code=404, detail="Build list part not found in build list"
        )

    # Check authorization - only the user who added the part or admin can edit it
    require_build_list_part_edit_permission(current_user, db_build_list_part)

    # Update the notes
    update_data = build_list_part.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Build list part {db_build_list_part.id} updated in build list {build_list_id} by user {current_user.id}"
    )
    return db_build_list_part


@router.delete(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses={
        404: {"description": "Build list or build list part not found"},
        403: {"description": "Not authorized to modify this build list part"},
    },
)
async def remove_global_part_from_build_list(
    build_list_id: int,
    global_part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Remove a build list part from a build list."""
    # Verify build list exists
    db_build_list = (
        db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
    )
    if not db_build_list:
        raise HTTPException(status_code=404, detail="Build list not found")

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if not db_build_list_part:
        raise HTTPException(
            status_code=404, detail="Build list part not found in build list"
        )

    # Check authorization - only the user who added the part or admin can delete it
    require_build_list_part_delete_permission(current_user, db_build_list_part)

    # Convert to response model before deleting
    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(
        f"Build list part {db_build_list_part.id} removed from build list {build_list_id} by user {current_user.id}"
    )
    return deleted_data
