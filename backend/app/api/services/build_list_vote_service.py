"""
Build list vote service that extends the base vote service.

This service provides build list-specific voting functionality while inheriting
common voting operations from the base vote service.
"""

import logging
from datetime import datetime, UTC, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Float

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_vote import BuildListVote as DBBuildListVote
from app.api.models.build_list_report import BuildListReport as DBBuildListReport
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_vote import (
    BuildListVoteCreate,
    BuildListVoteRead,
    BuildListVoteSummary,
    FlaggedBuildListSummary,
)
from app.api.services.base_vote_service import BaseVoteService
from app.api.utils.response_patterns import ResponsePatterns


class BuildListVoteService(
    BaseVoteService[
        DBBuildListVote, BuildListVoteCreate, BuildListVoteRead, DBBuildList
    ]
):
    """Build list vote service that extends the base vote service."""

    def __init__(self):
        super().__init__(
            vote_model=DBBuildListVote,
            entity_model=DBBuildList,
            entity_name="build list",
            vote_entity_id_field="build_list_id",
        )

    def get_vote_summary(
        self, db: Session, build_list_id: int, logger: logging.Logger
    ) -> BuildListVoteSummary:
        """Get vote summary for a build list."""
        # Verify build list exists
        build_list = (
            db.query(DBBuildList).filter(DBBuildList.id == build_list_id).first()
        )
        if not build_list:
            ResponsePatterns.raise_not_found("Build list", build_list_id)

        # Get vote counts
        vote_counts = (
            db.query(
                DBBuildListVote.vote_type,
                func.count(DBBuildListVote.id).label("count"),
            )
            .filter(DBBuildListVote.build_list_id == build_list_id)
            .group_by(DBBuildListVote.vote_type)
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

        return BuildListVoteSummary(
            build_list_id=build_list_id,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=total_votes,
            score=score,
            upvote_percentage=round(upvote_percentage, 1),
            downvote_percentage=round(downvote_percentage, 1),
        )

    def get_flagged_build_lists(
        self,
        db: Session,
        days: int,
        min_downvotes: int,
        logger: logging.Logger,
    ) -> List[FlaggedBuildListSummary]:
        """Get build lists flagged for review based on downvotes and reports."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Get build lists with high downvotes
        flagged_build_lists = (
            db.query(
                DBBuildList.id,
                DBBuildList.name,
                DBBuildList.description,
                func.count(
                    case(
                        (DBBuildListVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).label("downvotes"),
                func.count(
                    case(
                        (DBBuildListVote.vote_type == "upvote", 1),
                        else_=0,
                    )
                ).label("upvotes"),
                func.count(DBBuildListReport.id).label("reports"),
            )
            .outerjoin(DBBuildListVote, DBBuildList.id == DBBuildListVote.build_list_id)
            .outerjoin(
                DBBuildListReport,
                and_(
                    DBBuildList.id == DBBuildListReport.build_list_id,
                    DBBuildListReport.created_at >= cutoff_date,
                ),
            )
            .group_by(DBBuildList.id, DBBuildList.name, DBBuildList.description)
            .having(
                or_(
                    func.count(
                        case(
                            (DBBuildListVote.vote_type == "downvote", 1),
                            else_=0,
                        )
                    )
                    >= min_downvotes,
                    func.count(DBBuildListReport.id) > 0,
                )
            )
            .order_by(
                func.count(
                    case(
                        (DBBuildListVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).desc()
            )
            .all()
        )

        flagged_summaries = []
        for build_list in flagged_build_lists:
            total_votes = build_list.upvotes + build_list.downvotes
            score = build_list.upvotes - build_list.downvotes

            flagged_summaries.append(
                FlaggedBuildListSummary(
                    build_list_id=build_list.id,
                    build_list_name=build_list.name,
                    build_list_description=build_list.description,
                    upvotes=build_list.upvotes,
                    downvotes=build_list.downvotes,
                    total_votes=total_votes,
                    score=score,
                    reports=build_list.reports,
                    downvote_ratio=(
                        round((build_list.downvotes / total_votes * 100), 1)
                        if total_votes > 0
                        else 0
                    ),
                )
            )

        logger.info(f"Retrieved {len(flagged_summaries)} flagged build lists")
        return flagged_summaries

    def get_user_vote(
        self, db: Session, build_list_id: int, user_id: int
    ) -> BuildListVoteRead | None:
        """Get a user's vote on a specific build list."""
        vote = (
            db.query(DBBuildListVote)
            .filter(
                and_(
                    DBBuildListVote.build_list_id == build_list_id,
                    DBBuildListVote.user_id == user_id,
                )
            )
            .first()
        )
        return BuildListVoteRead.model_validate(vote) if vote else None

    def get_build_lists_by_vote_type(
        self,
        db: Session,
        vote_type: str,
        skip: int = 0,
        limit: int = 100,
        logger: logging.Logger = None,
    ) -> List[DBBuildList]:
        """Get build lists sorted by vote type count."""
        # Get build lists with their vote counts
        build_lists_with_votes = (
            db.query(
                DBBuildList,
                func.count(
                    case(
                        (DBBuildListVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                ).label("vote_count"),
            )
            .outerjoin(DBBuildListVote, DBBuildList.id == DBBuildListVote.build_list_id)
            .group_by(DBBuildList.id)
            .having(
                func.count(
                    case(
                        (DBBuildListVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                )
                > 0
            )
            .order_by(
                func.count(
                    case(
                        (DBBuildListVote.vote_type == vote_type, 1),
                        else_=0,
                    )
                ).desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [build_list for build_list, _ in build_lists_with_votes]
