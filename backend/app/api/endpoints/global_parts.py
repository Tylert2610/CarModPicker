import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.dependencies.auth import get_current_user, get_current_active_user_optional
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.global_part import (
    GlobalPartCreate,
    GlobalPartRead,
    GlobalPartUpdate,
    GlobalPartReadWithVotes,
)
from app.api.utils.authorization import (
    require_global_part_delete_permission,
    require_global_part_edit_permission,
)
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/",
    response_model=GlobalPartRead,
    responses={
        400: {"description": "Invalid part data"},
        403: {"description": "Not authorized to create parts"},
    },
)
async def create_global_part(
    part: GlobalPartCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBGlobalPart:
    """Create a new global part (shared part in the global catalog)."""
    # Create the part with the current user as creator
    part_data = part.model_dump()
    part_data["user_id"] = current_user.id

    db_part = DBGlobalPart(**part_data)
    db.add(db_part)
    db.commit()
    db.refresh(db_part)

    logger.info(f"Part created: {db_part.id} by user {current_user.id}")
    return db_part


@router.get(
    "/",
    response_model=List[GlobalPartRead],
    responses={
        200: {"description": "List of parts retrieved successfully"},
    },
)
async def read_global_parts(
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of global parts to return"
    ),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(
        None, description="Search in global part names and descriptions"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBGlobalPart]:
    """Get all global parts (shared parts in the global catalog) with optional filtering and search."""
    query = db.query(DBGlobalPart)

    if category_id:
        query = query.filter(DBGlobalPart.category_id == category_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (DBGlobalPart.name.ilike(search_term))
            | (DBGlobalPart.description.ilike(search_term))
        )

    parts = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(parts)} parts")
    return parts


@router.get(
    "/with-votes",
    response_model=List[GlobalPartReadWithVotes],
    responses={
        200: {"description": "List of parts with vote data retrieved successfully"},
    },
)
async def read_global_parts_with_votes(
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of global parts to return"
    ),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(
        None, description="Search in global part names and descriptions"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: Optional[DBUser] = Depends(get_current_active_user_optional),
) -> List[GlobalPartReadWithVotes]:
    """Get all global parts (shared parts in the global catalog) with vote data and optional filtering and search."""
    from app.api.models.global_part_vote import GlobalPartVote as DBGlobalPartVote

    query = db.query(DBGlobalPart)

    if category_id:
        query = query.filter(DBGlobalPart.category_id == category_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (DBGlobalPart.name.ilike(search_term))
            | (DBGlobalPart.description.ilike(search_term))
        )

    parts = query.offset(skip).limit(limit).all()

    # Get vote data for each part
    parts_with_votes = []
    for part in parts:
        # Get vote counts
        upvotes = (
            db.query(func.count(DBGlobalPartVote.id))
            .filter(
                DBGlobalPartVote.global_part_id == part.id,
                DBGlobalPartVote.vote_type == "upvote",
            )
            .scalar()
        )

        downvotes = (
            db.query(func.count(DBGlobalPartVote.id))
            .filter(
                DBGlobalPartVote.global_part_id == part.id,
                DBGlobalPartVote.vote_type == "downvote",
            )
            .scalar()
        )

        # Get user's vote if authenticated
        user_vote = None
        if current_user:
            user_vote_obj = (
                db.query(DBGlobalPartVote)
                .filter(
                    DBGlobalPartVote.user_id == current_user.id,
                    DBGlobalPartVote.global_part_id == part.id,
                )
                .first()
            )
            user_vote = user_vote_obj.vote_type if user_vote_obj else None

        part_with_votes = GlobalPartReadWithVotes(
            **part.__dict__,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=upvotes + downvotes,
            user_vote=user_vote,
        )
        parts_with_votes.append(part_with_votes)

    logger.info(f"Retrieved {len(parts_with_votes)} parts with vote data")
    return parts_with_votes


@router.get(
    "/{part_id}",
    response_model=GlobalPartRead,
    responses={
        404: {"description": "Part not found"},
    },
)
async def read_global_part(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBGlobalPart:
    """Get a specific global part (shared part in the global catalog) by ID."""
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    logger.info(f"Part retrieved: {part_id}")
    return db_part


@router.put(
    "/{part_id}",
    response_model=GlobalPartRead,
    responses={
        404: {"description": "Part not found"},
        403: {"description": "Not authorized to update this part"},
    },
)
async def update_global_part(
    part_id: int,
    part: GlobalPartUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBGlobalPart:
    """Update a global part (shared part in the global catalog, only creator can update)."""
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check authorization using utility function
    require_global_part_edit_permission(current_user, db_part)

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
    response_model=GlobalPartRead,
    responses={
        404: {"description": "Part not found"},
        403: {"description": "Not authorized to delete this part"},
    },
)
async def delete_global_part(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartRead:
    """Delete a global part (shared part in the global catalog, only creator or admin can delete)."""
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if db_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check authorization using utility function
    require_global_part_delete_permission(current_user, db_part)

    # Count how many build lists this part is in
    build_list_count = len(db_part.build_lists)

    # Convert the SQLAlchemy model to the Pydantic model before deleting
    deleted_part_data = GlobalPartRead.model_validate(db_part)

    db.delete(db_part)
    db.commit()

    logger.info(
        f"Global part {part_id} deleted by user {current_user.id}. "
        f"This also removed the part from {build_list_count} build list(s)."
    )
    return deleted_part_data


@router.get(
    "/user/{user_id}",
    response_model=List[GlobalPartRead],
    responses={
        200: {"description": "List of parts created by user"},
    },
)
async def read_global_parts_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of global parts to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> List[DBGlobalPart]:
    """Get all global parts (shared parts in the global catalog) created by a specific user."""
    parts = (
        db.query(DBGlobalPart)
        .filter(DBGlobalPart.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    logger.info(f"Retrieved {len(parts)} parts for user {user_id}")
    return parts
