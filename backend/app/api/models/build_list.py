from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car import Car
    from .user import User
    from .build_list_part import BuildListPart


class BuildList(Base):
    __tablename__ = "build_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    car: Mapped["Car"] = relationship("Car", back_populates="build_lists")
    owner: Mapped["User"] = relationship("User")
    parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="build_list"
    )
