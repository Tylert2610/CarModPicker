"""
Endpoint registry utility for standardizing endpoint registration and reducing redundancy.
"""

from typing import Dict, List, Optional, Sequence, TypedDict

from fastapi import APIRouter, FastAPI

from app.core.config import settings


class EndpointInfo(TypedDict):
    """Type definition for endpoint registration information."""

    router: APIRouter
    prefix: str
    tags: List[str]
    description: str
    include_in_openapi: bool


class EndpointRegistry:
    """
    Utility class for standardizing endpoint registration and reducing redundancy.

    This class provides a centralized way to register endpoints with consistent
    patterns for prefixes, tags, and error handling.
    """

    def __init__(self, app: FastAPI):
        """Initialize the endpoint registry with a FastAPI app instance."""
        self.app = app
        self.registered_endpoints: Dict[str, EndpointInfo] = {}

    def register_endpoint(
        self,
        router: APIRouter,
        prefix: str,
        tags: Sequence[str],
        description: str = "",
        include_in_openapi: bool = True,
    ) -> None:
        """Register an endpoint with standardized configuration."""
        full_prefix = f"{settings.API_STR}{prefix}"

        self.app.include_router(
            router,
            prefix=full_prefix,
            tags=list(tags),
        )

        tags_list = list(tags)
        self.registered_endpoints[prefix] = {
            "router": router,
            "prefix": full_prefix,
            "tags": tags_list,
            "description": description,
            "include_in_openapi": include_in_openapi,
        }

    def register_crud_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """Register a CRUD endpoint with standardized naming."""
        tags_to_use: Sequence[str] = [entity_name] if tags is None else tags

        prefix = f"/{entity_name.replace('_', '-')}"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags_to_use,
            description=description,
        )

    def register_vote_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """Register a vote endpoint with standardized naming."""
        tags_to_use: Sequence[str] = [f"{entity_name}_votes"] if tags is None else tags

        prefix = f"/{entity_name.replace('_', '-')}-votes"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags_to_use,
            description=description,
        )

    def register_report_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """Register a report endpoint with standardized naming."""
        tags_to_use: Sequence[str] = [f"{entity_name}_reports"] if tags is None else tags

        prefix = f"/{entity_name.replace('_', '-')}-reports"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags_to_use,
            description=description,
        )

    def get_registered_endpoints(self) -> Dict[str, EndpointInfo]:
        """Get all registered endpoints."""
        return self.registered_endpoints
