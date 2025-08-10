from typing import List, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    disabled: Mapped[bool] = mapped_column(default=False, nullable=False)

    # children
    cars: Mapped[List["Car"]] = relationship("Car", back_populates="user", cascade="all, delete-orphan")  # type: ignore
