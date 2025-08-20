from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .part import Part
    from .user import User


class BuildListPart(Base):
    __tablename__ = "build_list_parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(
        ForeignKey("build_lists.id"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="parts")
    part: Mapped["Part"] = relationship("Part", back_populates="build_lists")
    user: Mapped["User"] = relationship("User")
