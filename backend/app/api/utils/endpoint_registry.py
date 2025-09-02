"""
Endpoint registry utility for standardizing endpoint registration and reducing redundancy.
"""

from typing import Dict, List, Any
from fastapi import FastAPI, APIRouter
from app.core.config import settings


class EndpointRegistry:
    """
    Utility class for standardizing endpoint registration and reducing redundancy.

    This class provides a centralized way to register endpoints with consistent
    patterns for prefixes, tags, and error handling.
    """

    def __init__(self, app: FastAPI):
        """Initialize the endpoint registry with a FastAPI app instance."""
        self.app = app
        self.registered_endpoints: Dict[str, Dict[str, Any]] = {}

    def register_endpoint(
        self,
        router: APIRouter,
        prefix: str,
        tags: List[str],
        description: str = "",
        include_in_openapi: bool = True,
    ) -> None:
        """
        Register an endpoint with standardized configuration.

        Args:
            router: FastAPI router to register
            prefix: URL prefix for the endpoint
            tags: OpenAPI tags for grouping
            description: Description of the endpoint group
            include_in_openapi: Whether to include in OpenAPI documentation
        """
        full_prefix = f"{settings.API_STR}{prefix}"

        # Register the router
        self.app.include_router(
            router,
            prefix=full_prefix,
            tags=tags,
        )

        # Store registration info
        self.registered_endpoints[prefix] = {
            "router": router,
            "prefix": full_prefix,
            "tags": tags,
            "description": description,
            "include_in_openapi": include_in_openapi,
        }

        # Log registration
        print(f"Registered endpoint: {full_prefix} ({', '.join(tags)})")

    def register_crud_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: List[str] = None,
        description: str = "",
    ) -> None:
        """
        Register a CRUD endpoint with standardized naming.

        Args:
            router: FastAPI router to register
            entity_name: Name of the entity (e.g., "cars", "users")
            tags: OpenAPI tags for grouping
            description: Description of the endpoint group
        """
        if tags is None:
            tags = [entity_name]

        # Convert entity name to kebab-case for URL
        prefix = f"/{entity_name.replace('_', '-')}"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags,
            description=description,
        )

    def register_vote_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: List[str] = None,
        description: str = "",
    ) -> None:
        """
        Register a vote endpoint with standardized naming.

        Args:
            router: FastAPI router to register
            entity_name: Name of the entity (e.g., "cars", "parts")
            tags: OpenAPI tags for grouping
            description: Description of the endpoint group
        """
        if tags is None:
            tags = [f"{entity_name}_votes"]

        prefix = f"/{entity_name.replace('_', '-')}-votes"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags,
            description=description,
        )

    def register_report_endpoint(
        self,
        router: APIRouter,
        entity_name: str,
        tags: List[str] = None,
        description: str = "",
    ) -> None:
        """
        Register a report endpoint with standardized naming.

        Args:
            router: FastAPI router to register
            entity_name: Name of the entity (e.g., "cars", "parts")
            tags: OpenAPI tags for grouping
            description: Description of the endpoint group
        """
        if tags is None:
            tags = [f"{entity_name}_reports"]

        prefix = f"/{entity_name.replace('_', '-')}-reports"

        self.register_endpoint(
            router=router,
            prefix=prefix,
            tags=tags,
            description=description,
        )

    def get_registered_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered endpoints."""
        return self.registered_endpoints

    def print_registration_summary(self) -> None:
        """Print a summary of all registered endpoints."""
        print("\n" + "=" * 60)
        print("ENDPOINT REGISTRATION SUMMARY")
        print("=" * 60)

        for prefix, info in self.registered_endpoints.items():
            print(f"✓ {info['prefix']}")
            print(f"  Tags: {', '.join(info['tags'])}")
            if info["description"]:
                print(f"  Description: {info['description']}")
            print()

        print(f"Total endpoints registered: {len(self.registered_endpoints)}")
        print("=" * 60)
