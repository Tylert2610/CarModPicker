from typing import TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .part import Part


class PartVote(Base):
    __tablename__ = "part_votes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    vote_type: Mapped[str] = mapped_column(nullable=False)  # 'upvote', 'downvote'
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="part_votes")
    part: Mapped["Part"] = relationship("Part", back_populates="votes")

    # Ensure one vote per user per part
    __table_args__ = (
        UniqueConstraint("user_id", "part_id", name="unique_user_part_vote"),
    )
