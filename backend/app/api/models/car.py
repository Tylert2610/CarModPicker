from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .build_list import BuildList
    from .car_vote import CarVote
    from .car_report import CarReport


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    make: Mapped[str] = mapped_column(index=True, nullable=False)
    model: Mapped[str] = mapped_column(index=True, nullable=False)
    year: Mapped[int] = mapped_column(index=True, nullable=False)
    trim: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # owner
    user: Mapped["User"] = relationship("User", back_populates="cars")
    # children
    build_lists: Mapped[List["BuildList"]] = relationship(
        "BuildList", back_populates="car", cascade="all, delete-orphan"
    )
    # votes and reports
    votes: Mapped[List["CarVote"]] = relationship(
        "CarVote", back_populates="car", cascade="all, delete-orphan"
    )
    reports: Mapped[List["CarReport"]] = relationship(
        "CarReport", back_populates="car", cascade="all, delete-orphan"
    )
