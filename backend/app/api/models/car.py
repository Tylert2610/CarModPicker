from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    make: Mapped[str] = mapped_column(index=True, nullable=False)
    model: Mapped[str] = mapped_column(index=True, nullable=False)
    year: Mapped[int] = mapped_column(index=True, nullable=False)
    trim: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # owner
    user: Mapped["User"] = relationship("User", back_populates="cars")  # type: ignore
    # children
    build_lists: Mapped[List["BuildList"]] = relationship("BuildList", back_populates="car", cascade="all, delete-orphan")  # type: ignore
