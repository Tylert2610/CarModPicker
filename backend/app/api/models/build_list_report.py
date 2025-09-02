from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .build_list import BuildList


class BuildListReport(Base):
    __tablename__ = "build_list_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    build_list_id: Mapped[int] = mapped_column(
        ForeignKey("build_lists.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(
        nullable=False
    )  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        default="pending", nullable=False
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    reporter: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="build_list_reports"
    )
    build_list: Mapped["BuildList"] = relationship(
        "BuildList", back_populates="reports"
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[reviewed_by]
    )
