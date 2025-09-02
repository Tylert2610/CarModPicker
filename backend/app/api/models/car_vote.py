from typing import TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .car import Car


class CarVote(Base):
    __tablename__ = "car_votes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"), nullable=False)
    vote_type: Mapped[str] = mapped_column(nullable=False)  # 'upvote', 'downvote'
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="car_votes")
    car: Mapped["Car"] = relationship("Car", back_populates="votes")

    # Ensure one vote per user per car
    __table_args__ = (
        UniqueConstraint("user_id", "car_id", name="unique_user_car_vote"),
    )
