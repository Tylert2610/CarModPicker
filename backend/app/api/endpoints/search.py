"""Search endpoint that searches across multiple entity types.

This endpoint provides unified search functionality across:
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list import BuildListRead
from app.api.schemas.pagination import CursorPage
from app.api.schemas.part import PartRead
from app.api.schemas.user import PublicUserRead
from app.api.services.car_generation_service import CarGenerationService
from app.api.services.part_service import PartService
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
)
from app.api.utils.cursor_pagination import paginate_in_memory
from app.api.utils.endpoint_decorators import search_responses
from app.db.dynamo import search

router = APIRouter()


@router.get(
    "/",
    response_model=Dict[str, Any],
    responses=search_responses("entities", allow_public_read=True),
)
async def search_all(
    q: str = Query(..., description="Search term to search across all entities"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return per category"),
    build_lists_cursor: str | None = Query(None, description="Opaque cursor for the next page of build list results"),
    users_cursor: str | None = Query(None, description="Opaque cursor for the next page of user results"),
    parts_cursor: str | None = Query(None, description="Opaque cursor for the next page of part results"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """
    Search across build lists, user profiles, and global parts.
    Returns results separated by entity type, each as a cursor page.
    """
    logger = deps["logger"]

    if not q or not q.strip():
        logger.warning("Empty search query provided")
        return {
            "build_lists": CursorPage[BuildListRead](items=[]),
            "users": CursorPage[PublicUserRead](items=[]),
            "parts": CursorPage[PartRead](items=[]),
            "query": q or "",
        }

    search_term = q.strip()

    matching_car_ids = [
        gen.id for gen in CarGenerationService(repos).matching_generations(search_term, include_years=True)
    ]
    term = search.normalize_term(search_term)
    matching_car_id_set = set(matching_car_ids)
    build_lists = search.scan_matching(
        repos.build_lists,
        lambda bl: search.contains(term, bl.name, bl.description) or bl.car_id in matching_car_id_set,
    )
    build_list_page = paginate_in_memory(
        build_lists,
        limit=limit,
        cursor=build_lists_cursor,
        sort_key=lambda bl: bl.name.lower(),
        item_id=lambda bl: str(bl.id),
        transform=BuildListRead.model_validate,
    )

    matched_users = repos.users.search(search_term)
    user_page = paginate_in_memory(
        matched_users,
        limit=limit,
        cursor=users_cursor,
        sort_key=lambda user: user.username.lower(),
        item_id=lambda user: str(user.id),
        transform=PublicUserRead.model_validate,
    )

    part_page = PartService(repos).search_parts(search_term, limit=limit, cursor=parts_cursor)

    logger.info(
        f"Search for '{search_term}' returned {len(build_list_page.items)}/{len(build_lists)} build lists, "
        f"{len(user_page.items)}/{len(matched_users)} users, and {len(part_page.items)} parts"
    )

    return {
        "build_lists": build_list_page,
        "users": user_page,
        "parts": part_page,
        "query": search_term,
    }
