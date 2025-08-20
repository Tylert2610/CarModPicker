from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class BuildList(Base):
    __tablename__ = "build_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # owner
    car: Mapped["Car"] = relationship("Car", back_populates="build_lists")  # type: ignore
    owner: Mapped["User"] = relationship("User")  # type: ignore
    # children
    parts: Mapped[List["Part"]] = relationship("Part", back_populates="build_list", cascade="all, delete-orphan")  # type: ignore
