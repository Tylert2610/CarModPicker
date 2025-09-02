"""
Build list service that extends the base CRUD service.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.schemas.build_list import BuildListCreate, BuildListRead, BuildListUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger

logger = get_logger()


class BuildListService(
    BaseCRUDService[DBBuildList, BuildListCreate, BuildListRead, BuildListUpdate]
):
    """Build list service that extends the base CRUD service."""

    def __init__(self):
        super().__init__(
            model=DBBuildList,
            entity_name="build list",
            subscription_check_method="can_create_build_list",
        )

    def get_build_lists_by_car(
        self,
        db: Session,
        car_id: int,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBBuildList]:
        """Get build lists by car ID with pagination."""
        if logger is None:
            logger = self.logger

        build_lists = (
            db.query(DBBuildList)
            .filter(DBBuildList.car_id == car_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

        logger.info(f"Retrieved {len(build_lists)} build lists for car {car_id}")
        return build_lists

    def get_build_lists_by_user(
        self,
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBBuildList]:
        """Get build lists by user ID with pagination."""
        if logger is None:
            logger = self.logger

        build_lists = (
            db.query(DBBuildList)
            .filter(DBBuildList.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

        logger.info(f"Retrieved {len(build_lists)} build lists for user {user_id}")
        return build_lists

    def count_by_user(
        self,
        db: Session,
        user_id: int,
        logger=None,
    ) -> int:
        """Count build lists owned by a specific user."""
        if logger is None:
            logger = self.logger

        count = db.query(DBBuildList).filter(DBBuildList.user_id == user_id).count()
        logger.info(f"Counted {count} build lists for user {user_id}")
        return count
