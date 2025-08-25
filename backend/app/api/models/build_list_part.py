from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .global_part import GlobalPart
    from .user import User


class BuildListPart(Base):
    """
    Build list part relationship model - represents the relationship between
    a catalog part and a build list, with additional metadata like notes.
    This allows users to add global catalog parts to their personal build lists.
    """

    __tablename__ = "build_list_parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(
        ForeignKey("build_lists.id"), nullable=False
    )
    global_part_id: Mapped[int] = mapped_column(
        ForeignKey("global_parts.id"), nullable=False
    )
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # Relationships
    build_list: Mapped["BuildList"] = relationship(
        "BuildList", back_populates="build_list_parts"
    )
    global_part: Mapped["GlobalPart"] = relationship(
        "GlobalPart", back_populates="build_lists"
    )
    user: Mapped["User"] = relationship("User", back_populates="build_list_parts")
