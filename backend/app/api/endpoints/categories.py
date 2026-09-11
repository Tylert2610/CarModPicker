"""
Categories endpoint - read-only.

Part categories are hardcoded in part_categories_data.py and seeded into the
database on startup. The backend source code is the source of truth; no create/update/delete.
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.category import CategoryResponse
from app.api.schemas.pagination import CursorPage
from app.api.schemas.part import PartRead
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params
from app.api.utils.endpoint_decorators import pagination_responses, standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo import search
from app.db.dynamo.catalog import Category

router = APIRouter()


def _get_category_or_404(repos: Repositories, category_id: UUID) -> Category:
    """Return the category or raise 404."""
    category = repos.categories.get(str(category_id))
    if category is None:
        ResponsePatterns.raise_not_found("Category")
    assert category is not None
    return category


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={200: {"description": "Category count retrieved successfully"}},
)
async def count_categories(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    """Return the total number of categories."""
    return {"count": repos.categories.count()}


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(repos: Repositories = Depends(get_repositories)) -> List[CategoryResponse]:
    """Get all active categories (seeded from backend source code)."""
    return [CategoryResponse.model_validate(c) for c in repos.categories.list_active()]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: UUID, repos: Repositories = Depends(get_repositories)) -> CategoryResponse:
    """Get specific category details."""
    return CategoryResponse.model_validate(_get_category_or_404(repos, category_id))


@router.get(
    "/{category_id}/parts",
    response_model=CursorPage[PartRead],
    responses=pagination_responses("part", allow_public_read=True),
)
async def get_parts_by_category(
    category_id: UUID,
    params: CursorParams = Depends(get_cursor_params),
    repos: Repositories = Depends(get_repositories),
) -> CursorPage[PartRead]:
    """Get parts by category with pagination."""
    _get_category_or_404(repos, category_id)
    return search.paginate(
        repos.parts.list_by_category(category_id),
        limit=params.limit,
        cursor=params.cursor,
        sort_key=lambda part: search.datetime_key(part.created_at, descending=True),
        transform=PartRead.model_validate,
    )


@router.get(
    "/{category_id}/parts-count",
    responses=standard_responses(
        success_description="Category parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_category_parts_count(
    category_id: UUID, repos: Repositories = Depends(get_repositories)
) -> Dict[str, int]:
    """
    Get the count of parts in a specific category.
    """
    _get_category_or_404(repos, category_id)
    return {"parts_count": repos.parts.count_by_category(category_id)}
