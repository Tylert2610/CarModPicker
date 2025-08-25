import logging
from datetime import datetime, UTC, timedelta
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Float

from app.api.dependencies.auth import get_current_user, get_current_admin_user
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.global_part_vote import GlobalPartVote as DBGlobalPartVote
from app.api.models.global_part_report import GlobalPartReport as DBGlobalPartReport
from app.api.models.user import User as DBUser
from app.api.schemas.global_part_vote import (
    GlobalPartVoteCreate,
    GlobalPartVoteRead,
    GlobalPartVoteSummary,
    FlaggedGlobalPartSummary,
)
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post(
    "/{part_id}/vote",
    response_model=GlobalPartVoteRead,
    responses={
        400: {"description": "Invalid vote data"},
        404: {"description": "Part not found"},
        409: {"description": "User has already voted on this part"},
    },
)
async def vote_on_part(
    part_id: int,
    vote: GlobalPartVoteCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> DBGlobalPartVote:
    """Vote on a part (upvote or downvote)."""
    # Check if part exists
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check if user has already voted on this part
    existing_vote = (
        db.query(DBGlobalPartVote)
        .filter(
            DBGlobalPartVote.user_id == current_user.id,
            DBGlobalPartVote.global_part_id == part_id,
        )
        .first()
    )

    if existing_vote:
        # Update existing vote
        existing_vote.vote_type = vote.vote_type.value
        db.commit()
        db.refresh(existing_vote)
        logger.info(
            f"Vote updated: {existing_vote.id} by user {current_user.id} on part {part_id}"
        )
        return existing_vote
    else:
        # Create new vote
        db_vote = DBGlobalPartVote(
            user_id=current_user.id,
            global_part_id=part_id,
            vote_type=vote.vote_type.value,
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
) -> Dict[str, str]:
    """Remove user's vote on a part."""
    # Check if part exists
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Find and delete the vote
    db_vote = (
        db.query(DBGlobalPartVote)
        .filter(
            DBGlobalPartVote.user_id == current_user.id,
            DBGlobalPartVote.global_part_id == part_id,
        )
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
    "/{part_id}/vote",
    response_model=GlobalPartVoteRead,
    responses={
        404: {"description": "Part not found or no vote exists"},
        401: {"description": "Authentication required"},
    },
)
async def get_vote(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartVoteRead:
    """Get the current user's vote on a specific part."""
    # Check if part exists
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Get user's vote on this part
    db_vote = (
        db.query(DBGlobalPartVote)
        .filter(
            DBGlobalPartVote.user_id == current_user.id,
            DBGlobalPartVote.global_part_id == part_id,
        )
        .first()
    )

    if not db_vote:
        raise HTTPException(status_code=404, detail="No vote found for this part")

    logger.info(
        f"Retrieved vote {db_vote.id} for user {current_user.id} on part {part_id}"
    )
    return GlobalPartVoteRead.model_validate(db_vote)


@router.get(
    "/{part_id}/vote-stats",
    response_model=GlobalPartVoteSummary,
    responses={
        404: {"description": "Part not found"},
        401: {"description": "Authentication required"},
    },
)
async def get_vote_stats(
    part_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartVoteSummary:
    """Get vote statistics for a specific part."""
    # Check if part exists
    db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Get vote statistics
    upvotes = (
        db.query(func.count(DBGlobalPartVote.id))
        .filter(
            DBGlobalPartVote.global_part_id == part_id,
            DBGlobalPartVote.vote_type == "upvote",
        )
        .scalar()
    )

    downvotes = (
        db.query(func.count(DBGlobalPartVote.id))
        .filter(
            DBGlobalPartVote.global_part_id == part_id,
            DBGlobalPartVote.vote_type == "downvote",
        )
        .scalar()
    )

    total_votes = upvotes + downvotes
    vote_score = upvotes - downvotes

    # Get user's vote if it exists
    user_vote = (
        db.query(DBGlobalPartVote)
        .filter(
            DBGlobalPartVote.user_id == current_user.id,
            DBGlobalPartVote.global_part_id == part_id,
        )
        .first()
    )

    user_vote_type = user_vote.vote_type if user_vote else None

    vote_summary = GlobalPartVoteSummary(
        global_part_id=part_id,
        upvotes=upvotes,
        downvotes=downvotes,
        total_votes=total_votes,
        vote_score=vote_score,
        user_vote=user_vote_type,
    )

    logger.info(f"Retrieved vote stats for part {part_id}: {vote_summary}")
    return vote_summary


@router.get(
    "/",
    response_model=List[GlobalPartVoteSummary],
    responses={
        200: {"description": "List of vote summaries retrieved successfully"},
    },
)
async def get_vote_summaries(
    part_ids: str = Query(..., description="Comma-separated list of part IDs"),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> List[GlobalPartVoteSummary]:
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
        db_part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
        if not db_part:
            continue

        # Get vote counts
        upvotes = (
            db.query(func.count(DBGlobalPartVote.id))
            .filter(
                DBGlobalPartVote.global_part_id == part_id,
                DBGlobalPartVote.vote_type == "upvote",
            )
            .scalar()
        )

        downvotes = (
            db.query(func.count(DBGlobalPartVote.id))
            .filter(
                DBGlobalPartVote.global_part_id == part_id,
                DBGlobalPartVote.vote_type == "downvote",
            )
            .scalar()
        )

        # Get user's vote
        user_vote = (
            db.query(DBGlobalPartVote)
            .filter(
                DBGlobalPartVote.user_id == current_user.id,
                DBGlobalPartVote.global_part_id == part_id,
            )
            .first()
        )

        vote_summary = GlobalPartVoteSummary(
            global_part_id=part_id,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=upvotes + downvotes,
            vote_score=upvotes - downvotes,
            user_vote=user_vote.vote_type if user_vote else None,
        )
        vote_summaries.append(vote_summary)

    logger.info(f"Vote summaries retrieved for {len(vote_summaries)} parts")
    return vote_summaries


@router.get(
    "/flagged-parts",
    response_model=List[FlaggedGlobalPartSummary],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
    },
)
async def get_flagged_parts(
    threshold: int = Query(
        -10, description="Minimum vote score to flag (upvotes - downvotes)"
    ),
    min_votes: int = Query(
        5, description="Minimum total votes required to consider flagging"
    ),
    min_downvote_ratio: float = Query(
        0.6, description="Minimum downvote ratio to flag (0.0-1.0)"
    ),
    days_back: int = Query(
        30, description="Number of days to look back for recent activity"
    ),
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of parts to return"
    ),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_admin: DBUser = Depends(get_current_admin_user),
) -> List[FlaggedGlobalPartSummary]:
    """Get parts with concerning vote patterns for admin review."""

    # Calculate date threshold for recent activity
    recent_threshold = datetime.now(UTC) - timedelta(days=days_back)
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    # Subquery to get vote counts per part
    vote_counts = (
        db.query(
            DBGlobalPartVote.global_part_id,
            func.sum(case((DBGlobalPartVote.vote_type == "upvote", 1), else_=0)).label(
                "upvotes"
            ),
            func.sum(
                case((DBGlobalPartVote.vote_type == "downvote", 1), else_=0)
            ).label("downvotes"),
            func.count(DBGlobalPartVote.id).label("total_votes"),
            func.sum(
                case(
                    (
                        and_(
                            DBGlobalPartVote.vote_type == "downvote",
                            DBGlobalPartVote.created_at >= seven_days_ago,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("recent_downvotes"),
        )
        .group_by(DBGlobalPartVote.global_part_id)
        .subquery()
    )

    # Subquery to check for pending reports
    pending_reports = (
        db.query(
            DBGlobalPartReport.global_part_id,
            func.count(DBGlobalPartReport.id).label("report_count"),
        )
        .filter(DBGlobalPartReport.status == "pending")
        .group_by(DBGlobalPartReport.global_part_id)
        .subquery()
    )

    # Main query to get flagged parts
    flagged_query = (
        db.query(
            DBGlobalPart.id.label("part_id"),
            DBGlobalPart.name.label("part_name"),
            DBGlobalPart.brand.label("part_brand"),
            DBGlobalPart.category_id,
            DBGlobalPart.created_at,
            vote_counts.c.upvotes,
            vote_counts.c.downvotes,
            vote_counts.c.total_votes,
            vote_counts.c.recent_downvotes,
            func.coalesce(pending_reports.c.report_count, 0).label("report_count"),
        )
        .join(vote_counts, DBGlobalPart.id == vote_counts.c.global_part_id)
        .outerjoin(pending_reports, DBGlobalPart.id == pending_reports.c.global_part_id)
        .filter(
            and_(
                vote_counts.c.total_votes >= min_votes,  # Minimum votes threshold
                vote_counts.c.upvotes - vote_counts.c.downvotes
                <= threshold,  # Vote score threshold
                func.cast(vote_counts.c.downvotes, Float) / vote_counts.c.total_votes
                >= min_downvote_ratio,  # Downvote ratio threshold
            )
        )
        .order_by(
            (
                vote_counts.c.upvotes - vote_counts.c.downvotes
            ).asc(),  # Worst score first
            vote_counts.c.recent_downvotes.desc(),  # Most recent activity second
        )
        .offset(skip)
        .limit(limit)
    )

    results = flagged_query.all()

    # Build response objects
    flagged_parts = []
    flagged_at = datetime.now(UTC)

    for result in results:
        vote_score = result.upvotes - result.downvotes
        downvote_ratio = (
            result.downvotes / result.total_votes if result.total_votes > 0 else 0.0
        )

        flagged_part = FlaggedGlobalPartSummary(
            part_id=result.part_id,
            part_name=result.part_name,
            part_brand=result.part_brand,
            category_id=result.category_id,
            upvotes=result.upvotes,
            downvotes=result.downvotes,
            total_votes=result.total_votes,
            vote_score=vote_score,
            downvote_ratio=round(downvote_ratio, 3),
            recent_downvotes=result.recent_downvotes,
            has_reports=result.report_count > 0,
            created_at=result.created_at,
            flagged_at=flagged_at,
        )
        flagged_parts.append(flagged_part)

    logger.info(
        f"Retrieved {len(flagged_parts)} flagged parts with threshold={threshold}, "
        f"min_votes={min_votes}, min_downvote_ratio={min_downvote_ratio}"
    )

    return flagged_parts
