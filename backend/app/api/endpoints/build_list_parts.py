"""
Refactored build list parts endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining build list part-specific functionality.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

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
    CreateGlobalPartAndAddToBuildListRequest,
)
from app.api.schemas.global_part import GlobalPartCreate
from app.api.utils.authorization import (
    require_build_list_part_edit_permission,
    require_build_list_part_delete_permission,
)
from app.api.utils.common_patterns import (
    get_entity_or_404,
    verify_entity_ownership,
    get_standard_public_endpoint_dependencies,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()


@router.post(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Global part added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def add_global_part_to_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartCreate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Add an existing global part to a build list as a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_entity_ownership(
        current_user, db_build_list.user_id, "modify this build list"
    )

    # Verify global part exists
    db_global_part = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")

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
        ResponsePatterns.raise_conflict("Global part already exists in build list")

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
    return BuildListPartRead.model_validate(db_build_list_part)


@router.get(
    "/{build_list_id}",
    response_model=List[BuildListPartRead],
    responses=standard_responses(
        success_description="Build list parts retrieved successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def get_build_list_parts(
    build_list_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListPartRead]:
    """Get all build list parts in a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_entity_ownership(
        current_user, db_build_list.user_id, "access this build list"
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
    responses=standard_responses(
        success_description="Build list part updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_part(
    build_list_part_id: int,
    build_list_part: BuildListPartUpdate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Find the build list part
    db_build_list_part = get_entity_or_404(
        db, DBBuildListPart, build_list_part_id, "build list part"
    )

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
    return BuildListPartRead.model_validate(db_build_list_part)


@router.delete(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_part(
    build_list_part_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Delete a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Find the build list part
    db_build_list_part = get_entity_or_404(
        db, DBBuildListPart, build_list_part_id, "build list part"
    )

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
    responses=standard_responses(
        success_description="Global part created and added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def create_global_part_and_add_to_build_list(
    build_list_id: int,
    request: CreateGlobalPartAndAddToBuildListRequest,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartReadWithGlobalPart:
    """Create a new global part and automatically add it to the specified build list as a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_entity_ownership(
        current_user, db_build_list.user_id, "modify this build list"
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
    responses=standard_responses(
        success_description="Global parts in build list retrieved successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def get_global_parts_in_build_list(
    build_list_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListPartReadWithGlobalPart]:
    """Get all build list parts in a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_entity_ownership(
        current_user, db_build_list.user_id, "access this build list"
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
    responses=standard_responses(
        success_description="Global part in build list updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_global_part_in_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartUpdate,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part's notes in a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

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
        ResponsePatterns.raise_not_found("Build list part not found in build list")

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
    return BuildListPartRead.model_validate(db_build_list_part)


@router.delete(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Global part removed from build list successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def remove_global_part_from_build_list(
    build_list_id: int,
    global_part_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Remove a build list part from a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

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
        ResponsePatterns.raise_not_found("Build list part not found in build list")

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
