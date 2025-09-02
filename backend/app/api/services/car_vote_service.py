"""
Car vote service that extends the base vote service.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Float

from app.api.models.car import Car as DBCar
from app.api.models.car_vote import CarVote as DBCarVote
from app.api.models.car_report import CarReport as DBCarReport
from app.api.schemas.car_vote import (
    CarVoteCreate,
    CarVoteRead,
    CarVoteSummary,
    FlaggedCarSummary,
)
from app.api.services.base_vote_service import BaseVoteService
from app.core.logging import get_logger


class CarVoteService(BaseVoteService[DBCarVote, CarVoteCreate, CarVoteRead, DBCar]):
    """
    Car vote service that extends the base vote service.

    This service provides car-specific voting functionality while inheriting
    common operations from the base vote service.
    """

    def __init__(self):
        """Initialize the car vote service."""
        super().__init__(
            vote_model=DBCarVote,
            entity_model=DBCar,
            entity_name="car",
            vote_entity_id_field="car_id",
        )

    def get_car_vote_summary(self, db: Session, car_id: int, logger) -> CarVoteSummary:
        """
        Get detailed vote summary for a car.

        Args:
            db: Database session
            car_id: ID of the car
            logger: Logger instance

        Returns:
            CarVoteSummary with detailed vote information
        """
        # Get basic vote summary from base service
        basic_summary = self.get_vote_summary(db, car_id, logger)

        # Get car details for additional context
        car = db.query(DBCar).filter(DBCar.id == car_id).first()
        if not car:
            raise ValueError(f"Car {car_id} not found")

        # Calculate percentages
        total_votes = basic_summary["total_votes"]
        upvote_percentage = (
            (basic_summary["upvotes"] / total_votes * 100) if total_votes > 0 else 0
        )
        downvote_percentage = (
            (basic_summary["downvotes"] / total_votes * 100) if total_votes > 0 else 0
        )

        return CarVoteSummary(
            car_id=car_id,
            total_votes=total_votes,
            upvotes=basic_summary["upvotes"],
            downvotes=basic_summary["downvotes"],
            score=basic_summary["score"],
            upvote_percentage=upvote_percentage,
            downvote_percentage=downvote_percentage,
        )

    def get_flagged_cars(
        self,
        db: Session,
        days: int = 30,
        min_downvotes: int = 5,
        logger=None,
    ) -> List[FlaggedCarSummary]:
        """
        Get cars flagged for review based on downvotes and reports.

        Args:
            db: Database session
            days: Number of days to look back
            min_downvotes: Minimum downvotes to consider flagged
            logger: Logger instance

        Returns:
            List of flagged car summaries
        """
        from datetime import datetime, UTC, timedelta

        # Calculate date threshold
        date_threshold = datetime.now(UTC) - timedelta(days=days)

        # Get cars with high downvote counts
        flagged_cars = (
            db.query(
                DBCar.id,
                DBCar.user_id,
                func.count(
                    case(
                        (DBCarVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).label("downvote_count"),
                func.count(
                    case(
                        (DBCarVote.vote_type == "upvote", 1),
                        else_=0,
                    )
                ).label("upvote_count"),
            )
            .join(
                DBCarVote,
                DBCar.id == DBCarVote.car_id,
            )
            .filter(DBCarVote.created_at >= date_threshold)
            .group_by(DBCar.id, DBCar.user_id)
            .having(
                func.count(
                    case(
                        (DBCarVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                )
                >= min_downvotes
            )
            .order_by(
                func.count(
                    case(
                        (DBCarVote.vote_type == "downvote", 1),
                        else_=0,
                    )
                ).desc()
            )
            .all()
        )

        # Add report counts and create summaries
        flagged_summaries = []
        for car_id, user_id, downvote_count, upvote_count in flagged_cars:
            # Get report count
            report_count = (
                db.query(DBCarReport)
                .filter(
                    DBCarReport.car_id == car_id,
                    DBCarReport.status == "pending",
                )
                .count()
            )

            # Calculate score and percentage
            total_votes = upvote_count + downvote_count
            score = upvote_count - downvote_count
            downvote_percentage = (
                (downvote_count / total_votes * 100) if total_votes > 0 else 0
            )

            flagged_summary = FlaggedCarSummary(
                car_id=car_id,
                user_id=user_id,
                total_votes=total_votes,
                upvotes=upvote_count,
                downvotes=downvote_count,
                score=score,
                downvote_percentage=downvote_percentage,
                report_count=report_count,
            )
            flagged_summaries.append(flagged_summary)

        if logger:
            logger.info(f"Retrieved {len(flagged_summaries)} flagged cars")

        return flagged_summaries
