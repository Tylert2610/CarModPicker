from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .category import Category
    from .user import User
    from .build_list_part import BuildListPart
    from .part_vote import PartVote
    from .part_report import PartReport


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    price: Mapped[Optional[int]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    # New fields for shared architecture
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )  # Creator
    brand: Mapped[Optional[str]] = mapped_column(nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(nullable=True)
    specifications: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Quality and moderation
    is_verified: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(
        default="user_created"
    )  # 'user_created', 'scraped', 'verified'
    edit_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="parts")
    creator: Mapped["User"] = relationship("User")
    build_lists: Mapped[list["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="part"
    )
    votes: Mapped[list["PartVote"]] = relationship(
        "PartVote", back_populates="part", cascade="all, delete-orphan"
    )
    reports: Mapped[list["PartReport"]] = relationship(
        "PartReport", back_populates="part", cascade="all, delete-orphan"
    )
