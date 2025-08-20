from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    part_type: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    price: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    build_list_id: Mapped[int] = mapped_column(
        ForeignKey("build_lists.id"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )

    # owner
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="parts")  # type: ignore
    category: Mapped["Category"] = relationship("Category", back_populates="parts")  # type: ignore
