"""
Car service that extends BaseCRUDService to eliminate redundancy.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger


class CarService(BaseCRUDService[DBCar, CarCreate, CarRead, CarUpdate]):
    """
    Car service that provides CRUD operations for cars.

    This service eliminates redundancy by extending BaseCRUDService
    and only implementing car-specific logic.
    """

    def __init__(self):
        """Initialize the car service."""
        super().__init__(
            model=DBCar,
            entity_name="car",
            subscription_check_method="can_create_car",
        )

    def get_cars_by_make_and_year(
        self,
        db: Session,
        make: Optional[str] = None,
        year: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBCar]:
        """
        Get cars filtered by make and/or year.

        Args:
            db: Database session
            make: Car make to filter by
            year: Car year to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of cars matching the filters
        """
        filters = {}
        if make:
            filters["make"] = make
        if year:
            filters["year"] = year

        return self.list_all(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters,
            logger=logger,
        )

    def search_cars(
        self,
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBCar]:
        """
        Search cars by make, model, or year.

        Args:
            db: Database session
            search_term: Search term to look for
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of cars matching the search term
        """
        return self.list_all(
            db=db,
            skip=skip,
            limit=limit,
            search=search_term,
            search_fields=["make", "model"],
            logger=logger,
        )

    def get_cars_with_owner_details(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        logger=None,
    ) -> List[DBCar]:
        """
        Get cars with owner details loaded.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of cars with owner details
        """
        # This would need to be implemented based on your model relationships
        # For now, we'll use the base method
        return self.list_all(
            db=db,
            skip=skip,
            limit=limit,
            logger=logger,
        )

    def verify_car_ownership(
        self,
        db: Session,
        car_id: int,
        current_user: DBUser,
        logger=None,
    ) -> DBCar:
        """
        Verify that a car exists and belongs to the current user.

        Args:
            db: Database session
            car_id: ID of the car to verify
            current_user: Current authenticated user
            logger: Logger instance (optional)

        Returns:
            The found car

        Raises:
            HTTPException: If car not found or not owned by user
        """
        return self.get_by_id(
            db=db,
            entity_id=car_id,
            current_user=current_user,
            allow_public=False,
            logger=logger,
        )
