import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.dependencies.auth import get_current_user
from app.api.models.part import Part as DBPart
from app.api.models.part_vote import PartVote as DBPartVote
from app.api.models.user import User as DBUser
from app.api.schemas.part_vote import PartVoteCreate, PartVoteRead, PartVoteSummary
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/{part_id}/vote",
    response_model=PartVoteRead,
    responses={
        400: {"description": "Invalid vote data"},
        404: {"description": "Part not found"},
        409: {"description": "User has already voted on this part"},
    },
)
async def vote_on_part(
    part_id: int,
    vote: PartVoteCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBPartVote:
    """Vote on a part (upvote or downvote)."""
    # Validate vote type
    if vote.vote_type not in ["upvote", "downvote"]:
        raise HTTPException(
            status_code=400, detail="Vote type must be 'upvote' or 'downvote'"
        )

    # Check if part exists
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check if user has already voted on this part
    existing_vote = (
        db.query(DBPartVote)
        .filter(DBPartVote.user_id == current_user.id, DBPartVote.part_id == part_id)
        .first()
    )

    if existing_vote:
        # Update existing vote
        existing_vote.vote_type = vote.vote_type
        db.commit()
        db.refresh(existing_vote)
        logger.info(
            f"Vote updated: {existing_vote.id} by user {current_user.id} on part {part_id}"
        )
        return existing_vote
    else:
        # Create new vote
        db_vote = DBPartVote(
            user_id=current_user.id, part_id=part_id, vote_type=vote.vote_type
        )
        db.add(db_vote)
        db.commit()
        db.refresh(db_vote)
        logger.info(
            f"Vote created: {db_vote.id} by user {current_user.id} on part {part_id}"
        )
        return db_vote


@router.delete(
    "/{part_id}/vote",
    responses={
        404: {"description": "Part not found or no vote exists"},
    },
)
async def remove_vote(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
):
    """Remove user's vote on a part."""
    # Check if part exists
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Find and delete the vote
    db_vote = (
        db.query(DBPartVote)
        .filter(DBPartVote.user_id == current_user.id, DBPartVote.part_id == part_id)
        .first()
    )

    if not db_vote:
        raise HTTPException(status_code=404, detail="No vote found for this part")

    db.delete(db_vote)
    db.commit()
    logger.info(
        f"Vote removed: {db_vote.id} by user {current_user.id} on part {part_id}"
    )
    return {"message": "Vote removed successfully"}


@router.get(
    "/{part_id}/vote-summary",
    response_model=PartVoteSummary,
    responses={
        404: {"description": "Part not found"},
    },
)
async def get_vote_summary(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> PartVoteSummary:
    """Get vote summary for a part including user's vote."""
    # Check if part exists
    db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Get vote counts
    upvotes = (
        db.query(func.count(DBPartVote.id))
        .filter(DBPartVote.part_id == part_id, DBPartVote.vote_type == "upvote")
        .scalar()
    )

    downvotes = (
        db.query(func.count(DBPartVote.id))
        .filter(DBPartVote.part_id == part_id, DBPartVote.vote_type == "downvote")
        .scalar()
    )

    # Get user's vote
    user_vote = (
        db.query(DBPartVote)
        .filter(DBPartVote.user_id == current_user.id, DBPartVote.part_id == part_id)
        .first()
    )

    vote_summary = PartVoteSummary(
        part_id=part_id,
        upvotes=upvotes,
        downvotes=downvotes,
        total_votes=upvotes + downvotes,
        user_vote=user_vote.vote_type if user_vote else None,
    )

    logger.info(f"Vote summary retrieved for part {part_id}")
    return vote_summary


@router.get(
    "/",
    response_model=List[PartVoteSummary],
    responses={
        200: {"description": "List of vote summaries retrieved successfully"},
    },
)
async def get_vote_summaries(
    part_ids: str = Query(..., description="Comma-separated list of part IDs"),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[PartVoteSummary]:
    """Get vote summaries for multiple parts."""
    try:
        part_id_list = [int(pid.strip()) for pid in part_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid part IDs format")

    if not part_id_list:
        raise HTTPException(status_code=400, detail="No part IDs provided")

    vote_summaries = []

    for part_id in part_id_list:
        # Check if part exists
        db_part = db.query(DBPart).filter(DBPart.id == part_id).first()
        if not db_part:
            continue

        # Get vote counts
        upvotes = (
            db.query(func.count(DBPartVote.id))
            .filter(DBPartVote.part_id == part_id, DBPartVote.vote_type == "upvote")
            .scalar()
        )

        downvotes = (
            db.query(func.count(DBPartVote.id))
            .filter(DBPartVote.part_id == part_id, DBPartVote.vote_type == "downvote")
            .scalar()
        )

        # Get user's vote
        user_vote = (
            db.query(DBPartVote)
            .filter(
                DBPartVote.user_id == current_user.id, DBPartVote.part_id == part_id
            )
            .first()
        )

        vote_summary = PartVoteSummary(
            part_id=part_id,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=upvotes + downvotes,
            user_vote=user_vote.vote_type if user_vote else None,
        )
        vote_summaries.append(vote_summary)

    logger.info(f"Vote summaries retrieved for {len(vote_summaries)} parts")
    return vote_summaries
