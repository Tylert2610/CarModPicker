"""
Retailers endpoint for managing part retailers (stores/sites).

Public read; admin-only create/update/delete.
Authenticated users can get-or-create by domain (for scrapers).
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.retailer import RetailerCreate, RetailerRead, RetailerUpdate
from app.api.services.part_listing_service import get_or_create_retailer
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.catalog import Retailer
from app.db.dynamo.users import UniqueAttributeTaken
from app.db.dynamo.users import User as DBUser

router = APIRouter()


def _get_retailer_or_404(repos: Repositories, retailer_id: UUID) -> Retailer:
    retailer = repos.retailers.get(str(retailer_id))
    if retailer is None:
        ResponsePatterns.raise_not_found("Retailer")
    assert retailer is not None
    return retailer


def _raise_domain_conflict(domain: str, existing: Retailer) -> None:
    ResponsePatterns.raise_conflict(
        f"A retailer with domain '{domain}' already exists",
        "DUPLICATE_RETAILER_DOMAIN",
        details={"existing_retailer_id": str(existing.id)},
    )


def _check_domain_available(repos: Repositories, domain: str, *, exclude_id: UUID | None = None) -> None:
    existing = repos.retailers.get_by_domain(domain.strip().lower())
    if existing is not None and existing.id != exclude_id:
        _raise_domain_conflict(domain, existing)


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={200: {"description": "Retailer count retrieved successfully"}},
)
async def count_retailers(repos: Repositories = Depends(get_repositories)) -> Dict[str, int]:
    return {"count": repos.retailers.count()}


@router.get("", response_model=List[RetailerRead])
async def get_retailers(
    active_only: bool = Query(True, description="Only return active retailers"),
    repos: Repositories = Depends(get_repositories),
) -> List[RetailerRead]:
    """Get all retailers (optionally filtered to active only)."""
    return [RetailerRead.model_validate(r) for r in repos.retailers.list_sorted(active_only=active_only)]


class RetailerGetOrCreateRequest(BaseModel):
    """Request body for get-or-create retailer by domain (scraper use)."""

    domain: str = Field(..., description="Domain e.g. a90shop.com")
    name: str | None = Field(None, description="Display name; derived from domain if omitted")
    base_url: str | None = Field(None, description="Base URL e.g. https://www.a90shop.com")


@router.post(
    "/get-or-create",
    response_model=RetailerRead,
)
async def get_or_create_retailer_by_domain(
    body: RetailerGetOrCreateRequest,
    current_user: DBUser = Depends(get_current_user),
) -> RetailerRead:
    """
    Get existing retailer by domain or create one. For use by scrapers when
    adding parts from a retailer not yet in the catalog. Any authenticated user.
    """
    domain = body.domain.strip().lower()
    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required")

    name = body.name.strip() if body.name else _domain_to_retailer_name(domain)
    retailer = get_or_create_retailer(name, domain=domain, base_url=body.base_url)
    return RetailerRead.model_validate(retailer)


def _domain_to_retailer_name(domain: str) -> str:
    """Convert domain to display name: a90shop.com -> A90Shop."""
    parts = domain.replace("www.", "").split(".")
    base = parts[0] if parts else domain
    if not base:
        return domain
    return base.title()


@router.get("/{retailer_id}", response_model=RetailerRead)
async def get_retailer(retailer_id: UUID, repos: Repositories = Depends(get_repositories)) -> RetailerRead:
    """Get a retailer by ID."""
    return RetailerRead.model_validate(_get_retailer_or_404(repos, retailer_id))


@router.post(
    "",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "create"),
)
async def create_retailer(
    retailer: RetailerCreate,
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> RetailerRead:
    """Create a new retailer (admin only)."""
    if retailer.domain:
        _check_domain_available(repos, retailer.domain)
    candidate = Retailer(**retailer.model_dump())
    try:
        created = repos.retailers.create_unique(candidate)
    except UniqueAttributeTaken as exc:
        if exc.attribute == "domain" and retailer.domain:
            existing = repos.retailers.get_by_domain(retailer.domain.strip().lower())
            if existing is not None:
                _raise_domain_conflict(retailer.domain, existing)
        ResponsePatterns.raise_conflict("A retailer with this name already exists", "DUPLICATE_RETAILER_NAME")
        raise
    return RetailerRead.model_validate(created)


@router.put(
    "/{retailer_id}",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "update"),
)
async def update_retailer(
    retailer_id: UUID,
    retailer: RetailerUpdate,
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> RetailerRead:
    """Update a retailer (admin only)."""
    db_retailer = _get_retailer_or_404(repos, retailer_id)
    if retailer.domain is not None and retailer.domain != db_retailer.domain:
        _check_domain_available(repos, retailer.domain, exclude_id=db_retailer.id)
    update_data = retailer.model_dump(exclude_unset=True)
    try:
        updated = repos.retailers.update_unique(db_retailer, **update_data)
    except UniqueAttributeTaken as exc:
        if exc.attribute == "domain" and retailer.domain:
            existing = repos.retailers.get_by_domain(retailer.domain.strip().lower())
            if existing is not None:
                _raise_domain_conflict(retailer.domain, existing)
        ResponsePatterns.raise_conflict("A retailer with this name already exists", "DUPLICATE_RETAILER_NAME")
        raise
    return RetailerRead.model_validate(updated)


@router.delete(
    "/{retailer_id}",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "delete"),
)
async def delete_retailer(
    retailer_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    repos: Repositories = Depends(get_repositories),
) -> RetailerRead:
    """Delete a retailer (admin only)."""
    db_retailer = _get_retailer_or_404(repos, retailer_id)
    listings_count = repos.part_listings.count_by_retailer(retailer_id)
    if listings_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete retailer that has {listings_count} part listing(s)",
            "RETAILER_IN_USE",
        )
    response_data = RetailerRead.model_validate(db_retailer)
    repos.retailers.delete_unique(db_retailer)
    return response_data
