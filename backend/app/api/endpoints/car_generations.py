"""
Car generations endpoint - read-only.

Car generations are hardcoded in car_generations_data.py and seeded into the
database on startup. The backend source code is the source of truth; no create/update/delete.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.car_generation import CarGenerationCreate, CarGenerationRead, CarGenerationUpdate
from app.api.schemas.pagination import CursorPage
from app.api.services.car_generation_service import CarGenerationService
from app.api.utils.base_dynamo_endpoint_router import BaseDynamoEndpointRouter
from app.api.utils.common_patterns import PublicEndpointDeps, get_standard_public_endpoint_dependencies
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    search_responses,
    standard_responses,
)

router = APIRouter()
car_generation_service = CarGenerationService()


@router.get(
    "/search",
    response_model=CursorPage[CarGenerationRead],
    responses=search_responses("car_generation", allow_public_read=True),
)
async def search_car_generations(
    q: str = Query(..., description="Search term for car make or model"),
    page: CursorParams = Depends(get_cursor_params),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> CursorPage[CarGenerationRead]:
    """Search car generations by make or model with pagination."""
    logger = deps["logger"]
    return car_generation_service.search_car_generations(q, limit=page.limit, cursor=page.cursor, logger=logger)


@router.get(
    "/car-makes/count",
    response_model=dict,
    responses=standard_responses(success_description="CarMake count retrieved successfully"),
)
async def count_car_makes(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> dict:
    """Get total count of CarMake entities (e.g. Honda, Toyota)."""
    logger = deps["logger"]
    count = repos.car_makes.count()
    logger.info(f"Retrieved car_makes count: {count}")
    return {"count": count}


@router.get(
    "/car-models/count",
    response_model=dict,
    responses=standard_responses(success_description="CarModel count retrieved successfully"),
)
async def count_car_models(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> dict:
    """Get total count of CarModel entities (e.g. Civic, Camry under a CarMake)."""
    logger = deps["logger"]
    count = repos.car_models.count()
    logger.info(f"Retrieved car_models count: {count}")
    return {"count": count}


@router.get(
    "/car-makes/{car_make_name}/car-models/{car_model_name}",
    response_model=CursorPage[CarGenerationRead],
    responses=pagination_responses("car_generation", allow_public_read=True),
)
async def get_car_generations_by_car_make_model(
    car_make_name: str,
    car_model_name: str,
    page: CursorParams = Depends(get_cursor_params),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> CursorPage[CarGenerationRead]:
    """Get car generations by car make and model with pagination."""
    logger = deps["logger"]
    return car_generation_service.get_car_generations_by_make_model(
        car_make_name, car_model_name, limit=page.limit, cursor=page.cursor, logger=logger
    )


@router.get(
    "/car-makes/{car_make_name}",
    response_model=CursorPage[CarGenerationRead],
    responses=pagination_responses("car_generation", allow_public_read=True),
)
async def get_car_generations_by_car_make(
    car_make_name: str,
    page: CursorParams = Depends(get_cursor_params),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> CursorPage[CarGenerationRead]:
    """Get car generations by car make with pagination."""
    logger = deps["logger"]
    return car_generation_service.get_car_generations_by_make_model(
        car_make_name, limit=page.limit, cursor=page.cursor, logger=logger
    )


@router.get(
    "/stats/car-makes",
    response_model=dict[str, int],
    responses=standard_responses(success_description="Car make statistics retrieved successfully"),
)
async def get_car_make_stats(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of car generations by car make."""
    logger = deps["logger"]
    result = car_generation_service.count_by_make()
    logger.info(f"Retrieved car_make statistics: {len(result)} car_makes")
    return result


@router.get(
    "/by-ids",
    response_model=List[CarGenerationRead],
    responses=standard_responses(success_description="Car generations retrieved successfully"),
)
async def get_car_generations_by_ids(
    ids: List[UUID] = Query(..., description="Car generation IDs to fetch"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarGenerationRead]:
    """Batch-fetch car generations by a list of IDs."""
    logger = deps["logger"]
    return car_generation_service.get_by_ids(ids, logger=logger)


base_router = BaseDynamoEndpointRouter(
    service=car_generation_service,
    router=router,
    entity_name="car_generation",
    allow_public_read=True,
    disable_endpoints=["create", "update", "delete"],
    create_schema=CarGenerationCreate,
    read_schema=CarGenerationRead,
    update_schema=CarGenerationUpdate,
    serialize=car_generation_service.hydrate_one,
    serialize_many=car_generation_service.hydrate,
)
