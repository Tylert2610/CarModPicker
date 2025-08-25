from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .global_part import GlobalPart


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        unique=True, nullable=False
    )  # 'exhaust', 'suspension'
    display_name: Mapped[str] = mapped_column(nullable=False)  # 'Exhaust Systems'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    global_parts: Mapped[list["GlobalPart"]] = relationship(
        "GlobalPart", back_populates="category"
    )
