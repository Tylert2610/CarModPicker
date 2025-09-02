"""
Global part vote service that extends the base vote service.

This service provides global part-specific voting functionality while inheriting
common voting operations from the base vote service.
"""

import logging
from datetime import datetime, UTC, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Float

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
from app.api.services.base_vote_service import BaseVoteService
from app.api.utils.response_patterns import ResponsePatterns


class GlobalPartVoteService(
    BaseVoteService[
        DBGlobalPartVote, GlobalPartVoteCreate, GlobalPartVoteRead, DBGlobalPart
    ]
):
    """Global part vote service that extends the base vote service."""

    def __init__(self):
        super().__init__(
            vote_model=DBGlobalPartVote,
            entity_model=DBGlobalPart,
            entity_name="global part",
            vote_entity_id_field="global_part_id",
        )

    def get_vote_summary(
        self, db: Session, part_id: int, logger: logging.Logger
    ) -> GlobalPartVoteSummary:
        """Get vote summary for a global part."""
        # Verify part exists
        part = db.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
        if not part:
            ResponsePatterns.raise_not_found("Part", part_id)

        # Get vote counts
        vote_counts = (
            db.query(
                DBGlobalPartVote.vote_type,
                func.count(DBGlobalPartVote.id).label("count"),
            )
            .filter(DBGlobalPartVote.global_part_id == part_id)
            .group_by(DBGlobalPartVote.vote_type)
            .all()
        )

        upvotes = 0
        downvotes = 0
        for vote_type, count in vote_counts:
            if vote_type == "upvote":
                upvotes = count
            elif vote_type == "downvote":
                downvotes = count

        total_votes = upvotes + downvotes
        score = upvotes - downvotes

        # Calculate percentages
        upvote_percentage = (upvotes / total_votes * 100) if total_votes > 0 else 0
        downvote_percentage = (downvotes / total_votes * 100) if total_votes > 0 else 0

        return GlobalPartVoteSummary(
            part_id=part_id,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=total_votes,
            score=score,
            upvote_percentage=round(upvote_percentage, 1),
            downvote_percentage=round(downvote_percentage, 1),
        )

    def get_flagged_parts(
        self,
        db: Session,
        days: int,
        min_downvotes: int,
        logger: logging.Logger,
    ) -> List[FlaggedGlobalPartSummary]:
        """Get global parts flagged for review based on downvotes and reports."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Get parts with high downvotes
        flagged_parts = (
            db.query(
                DBGlobalPart.id,
                DBGlobalPart.name,
                DBGlobalPart.description,
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).label("downvotes"),
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == "upvote", 1),
                        else_=0,
                    )
                ).label("upvotes"),
                func.count(DBGlobalPartReport.id).label("reports"),
            )
            .outerjoin(
                DBGlobalPartVote, DBGlobalPart.id == DBGlobalPartVote.global_part_id
            )
            .outerjoin(
                DBGlobalPartReport,
                and_(
                    DBGlobalPart.id == DBGlobalPartReport.global_part_id,
                    DBGlobalPartReport.created_at >= cutoff_date,
                ),
            )
            .group_by(DBGlobalPart.id, DBGlobalPart.name, DBGlobalPart.description)
            .having(
                or_(
                    func.count(
                        case(
                            (DBGlobalPartVote.vote_type == "downvote", 1),
                            else_=0,
                        )
                    )
                    >= min_downvotes,
                    func.count(DBGlobalPartReport.id) > 0,
                )
            )
            .order_by(
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).desc()
            )
            .all()
        )

        flagged_summaries = []
        for part in flagged_parts:
            total_votes = part.upvotes + part.downvotes
            score = part.upvotes - part.downvotes

            flagged_summaries.append(
                FlaggedGlobalPartSummary(
                    part_id=part.id,
                    part_name=part.name,
                    part_description=part.description,
                    upvotes=part.upvotes,
                    downvotes=part.downvotes,
                    total_votes=total_votes,
                    score=score,
                    reports=part.reports,
                    downvote_ratio=(
                        round((part.downvotes / total_votes * 100), 1)
                        if total_votes > 0
                        else 0
                    ),
                )
            )

        logger.info(f"Retrieved {len(flagged_summaries)} flagged parts")
        return flagged_summaries

    def get_user_vote(
        self, db: Session, part_id: int, user_id: int
    ) -> GlobalPartVoteRead | None:
        """Get a user's vote on a specific part."""
        vote = (
            db.query(DBGlobalPartVote)
            .filter(
                and_(
                    DBGlobalPartVote.global_part_id == part_id,
                    DBGlobalPartVote.user_id == user_id,
                )
            )
            .first()
        )
        return GlobalPartVoteRead.model_validate(vote) if vote else None

    def get_parts_by_vote_type(
        self,
        db: Session,
        vote_type: str,
        skip: int = 0,
        limit: int = 100,
        logger: logging.Logger = None,
    ) -> List[DBGlobalPart]:
        """Get parts sorted by vote type count."""
        # Get parts with their vote counts
        parts_with_votes = (
            db.query(
                DBGlobalPart,
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                ).label("vote_count"),
            )
            .outerjoin(
                DBGlobalPartVote, DBGlobalPart.id == DBGlobalPartVote.global_part_id
            )
            .group_by(DBGlobalPart.id)
            .having(
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                )
                > 0
            )
            .order_by(
                func.count(
                    case(
                        (DBGlobalPartVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                ).desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [part for part, _ in parts_with_votes]
