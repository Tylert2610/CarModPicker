from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car import Car
    from .subscription import Subscription
    from .global_part_vote import GlobalPartVote
    from .global_part_report import GlobalPartReport
    from .global_part import GlobalPart
    from .build_list import BuildList
    from .build_list_part import BuildListPart


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    disabled: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Admin/Superuser fields
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Subscription fields
    subscription_tier: Mapped[str] = mapped_column(
        default="free", nullable=False
    )  # 'free', 'premium'
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        default="active", nullable=False
    )  # 'active', 'cancelled', 'expired'

    # Relationships
    cars: Mapped[List["Car"]] = relationship(
        "Car", back_populates="user", cascade="all, delete-orphan"
    )
    build_lists: Mapped[List["BuildList"]] = relationship(
        "BuildList", back_populates="owner", cascade="all, delete-orphan"
    )
    global_parts: Mapped[List["GlobalPart"]] = relationship(
        "GlobalPart", back_populates="creator", cascade="all, delete-orphan"
    )
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    global_part_votes: Mapped[List["GlobalPartVote"]] = relationship(
        "GlobalPartVote", back_populates="user", cascade="all, delete-orphan"
    )
    global_part_reports: Mapped[List["GlobalPartReport"]] = relationship(
        "GlobalPartReport",
        foreign_keys="GlobalPartReport.user_id",
        back_populates="reporter",
        cascade="all, delete-orphan",
    )
