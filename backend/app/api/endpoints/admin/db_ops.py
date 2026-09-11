"""Admin database operations: data init, bulk delete."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies.auth import get_current_admin_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.services.part_service import PartService, purge_related_rows_for_parts
from app.api.utils.endpoint_decorators import standard_responses
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.db.dynamo.catalog import Part
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)
router = APIRouter()


def _init_result(success: bool, message: str) -> Dict[str, Any]:
    """Standard response for init endpoints."""
    return {"success": success, "message": message}


def _purge_parts(repos: Repositories, parts: list[Part]) -> int:
    """Tombstone every given part and purge the rows that reference them."""
    service = PartService(repos)
    for part in parts:
        service.purge(part)
    purge_related_rows_for_parts([part.id for part in parts])
    return len(parts)


@router.post(
    "/init/car-generations",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Car generations initialized successfully",
        forbidden=True,
    ),
)
async def init_car_generations_endpoint(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Initialize car generations from source of truth (admin only).

    Syncs makes, car models, and car generations from car_generations_data
    into the database. Run this manually after deploying or when seed data
    """
    try:
        logger.info(f"Admin {current_user.id} triggered car generations init")
        init_car_generations()
        return _init_result(True, "Car generations initialized successfully")
    except Exception as e:
        logger.exception("Car generations init failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/init/part-categories",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Part categories initialized successfully",
        forbidden=True,
    ),
)
async def init_part_categories_endpoint(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Initialize part categories from source of truth (admin only).

    Syncs part categories from part_categories_data into the database.
    Run this manually after deploying or when seed data has been updated.
    """
    try:
        logger.info(f"Admin {current_user.id} triggered part categories init")
        init_part_categories()
        return _init_result(True, "Part categories initialized successfully")
    except Exception as e:
        logger.exception("Part categories init failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class DeleteAllCarsResponse(BaseModel):
    """Response for delete-all cars (admin only)."""

    deleted_count: int = Field(..., description="Number of cars (generations) deleted")
    deleted_car_models_count: int = Field(..., description="Number of car models deleted")
    deleted_makes_count: int = Field(..., description="Number of makes deleted")


@router.post(
    "/cars/delete-all",
    response_model=DeleteAllCarsResponse,
    responses=standard_responses(
        success_description="All cars deleted",
        forbidden=True,
    ),
)
async def delete_all_cars(
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> DeleteAllCarsResponse:
    """Delete all cars / car generations (admin only).

    Unlinks build lists from cars (sets car_id to null), removes car votes and
    part_cars links, then deletes all Car, CarModel, and Make rows so
    """
    try:
        for build_list in repos.build_lists.scan_all():
            if build_list.car_id is not None:
                repos.build_lists.update(build_list.id, car_id=None)
        repos.votes.delete_for_entity_type("car_generation")
        generations = repos.car_generations.list_all()
        for generation in generations:
            repos.part_cars.delete_for_car(generation.id)
            repos.car_generations.delete_unique(generation)
        count = len(generations)
        car_models = repos.car_models.list_all()
        for car_model in car_models:
            repos.car_models.delete_unique(car_model)
        car_models_count = len(car_models)
        makes = repos.car_makes.list_all()
        for make in makes:
            repos.car_makes.delete_unique(make)
        makes_count = len(makes)
        logger.info(
            "Admin %s deleted all cars: %s cars, %s car models, %s makes",
            current_user.id,
            count,
            car_models_count,
            makes_count,
        )
        return DeleteAllCarsResponse(
            deleted_count=count,
            deleted_car_models_count=car_models_count,
            deleted_makes_count=makes_count,
        )
    except Exception as e:
        logger.exception("Delete all cars failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class DeleteAllPartsResponse(BaseModel):
    """Response for delete-all parts (admin only)."""

    deleted_count: int = Field(..., description="Number of parts deleted")


@router.post(
    "/parts/delete-all",
    response_model=DeleteAllPartsResponse,
    responses=standard_responses(
        success_description="All parts deleted",
        forbidden=True,
    ),
)
async def delete_all_parts(
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> DeleteAllPartsResponse:
    """
    Delete all parts (admin only).

    Cascades to part listings, votes, reports, build list parts, and car associations.
    This action cannot be undone.
    """
    try:
        count = _purge_parts(repos, repos.parts.list_all())
        logger.info("Admin %s deleted all %s parts", current_user.id, count)
        return DeleteAllPartsResponse(deleted_count=count)
    except Exception as e:
        logger.exception("Delete all global parts failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class DeleteAllPartManufacturersResponse(BaseModel):
    """Response for delete-all part manufacturers (admin only)."""

    deleted_count: int = Field(..., description="Number of part manufacturers deleted")


@router.post(
    "/part-manufacturers/delete-all",
    response_model=DeleteAllPartManufacturersResponse,
    responses=standard_responses(
        success_description="All part manufacturers deleted",
        forbidden=True,
    ),
)
async def delete_all_part_manufacturers(
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> DeleteAllPartManufacturersResponse:
    """
    Delete all part manufacturers (admin only).

    First nullifies part_manufacturer_id on all global parts, then deletes all part_manufacturers.
    This action cannot be undone.
    """
    try:
        for part in repos.parts.list_all():
            if part.part_manufacturer_id is not None:
                repos.parts.update_unique(part, part_manufacturer_id=None)
        part_manufacturers = repos.part_manufacturers.list_all()
        count = len(part_manufacturers)
        for part_manufacturer in part_manufacturers:
            repos.part_manufacturers.delete_unique(part_manufacturer)
        logger.info("Admin %s deleted all %s part manufacturers", current_user.id, count)
        return DeleteAllPartManufacturersResponse(deleted_count=count)
    except Exception as e:
        logger.exception("Delete all part manufacturers failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
