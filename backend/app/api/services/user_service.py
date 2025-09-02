"""
User service that extends the base CRUD service.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.schemas.user import UserCreate, UserRead, UserUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger

logger = get_logger()


class UserService(BaseCRUDService[DBUser, UserCreate, UserRead, UserUpdate]):
    """User service that extends the base CRUD service."""

    def __init__(self):
        super().__init__(
            model=DBUser,
            entity_name="user",
            subscription_check_method=None,  # Users don't have subscription limits
        )

    def get_by_username(
        self,
        db: Session,
        username: str,
        logger=None,
    ) -> Optional[DBUser]:
        """Get user by username."""
        if logger is None:
            logger = self.logger

        user = db.query(DBUser).filter(DBUser.username == username).first()
        if user:
            logger.info(f"Retrieved user by username: {username}")
        else:
            logger.info(f"No user found with username: {username}")
        return user

    def get_by_email(
        self,
        db: Session,
        email: str,
        logger=None,
    ) -> Optional[DBUser]:
        """Get user by email."""
        if logger is None:
            logger = self.logger

        user = db.query(DBUser).filter(DBUser.email == email).first()
        if user:
            logger.info(f"Retrieved user by email: {email}")
        else:
            logger.info(f"No user found with email: {email}")
        return user

    def get_all_users(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBUser]:
        """Get all users with pagination (admin only)."""
        if logger is None:
            logger = self.logger

        users = db.query(DBUser).offset(skip).limit(limit).all()
        logger.info(f"Retrieved {len(users)} users")
        return users

    def count_all(
        self,
        db: Session,
        logger=None,
    ) -> int:
        """Get total count of users."""
        if logger is None:
            logger = self.logger

        count = db.query(DBUser).count()
        logger.info(f"Total user count: {count}")
        return count
