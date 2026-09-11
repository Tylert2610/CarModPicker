"""
Build list service on DynamoDB.

Build lists, their parts, phases, labor estimates and the build log thread
auto-created alongside every list all live in DynamoDB.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_list import BuildListCreate, BuildListUpdate
from app.api.services.base_dynamo_crud_service import BaseDynamoCRUDService
from app.api.utils.subscription_utils import is_user_premium
from app.db.dynamo.build_lists import (
    BuildList,
    BuildListPart,
    BuildListPhase,
    delete_build_list_cascade,
)
from app.db.dynamo.build_logs import BuildLog, build_log_delete_actions
from app.db.dynamo.users import User as DBUser

FREE_TIER_BUILD_LIST_LIMIT = 1
FREE_TIER_LIMIT_DETAIL = "Free accounts are limited to 1 build list. Upgrade to premium for unlimited build lists."


class BuildListService(BaseDynamoCRUDService[BuildList, BuildListCreate, BuildListUpdate]):
    """Build list CRUD with car validation and free tier limits."""

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Bind the service to a repository bundle."""
        self.repos = repos or get_repositories()
        super().__init__(self.repos.build_lists, "build list")

    def _verify_car_exists(self, car_id: UUID) -> None:
        """Raise 404 when the referenced car generation is missing."""
        if self.repos.car_generations.get(str(car_id)) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")

    def _enforce_free_tier_limit(self, current_user: DBUser) -> None:
        """Raise 402 when a free account is at its build list limit."""
        if is_user_premium(current_user, check_kill_switch=True):
            return
        if self.count_by_user(current_user.id) >= FREE_TIER_BUILD_LIST_LIMIT:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=FREE_TIER_LIMIT_DETAIL)

    def _create_build_log(self, build_list: BuildList) -> BuildLog:
        """Create the build log thread that accompanies a new build list."""
        return self.repos.build_logs.create(
            BuildLog(build_list_id=build_list.id, title=f"Build Log: {build_list.name}")
        )

    def get_build_lists_by_car(self, car_id: UUID, skip: int = 0, limit: int = 100) -> List[BuildList]:
        """Return build lists for a car, newest first."""
        items = self.repos.build_lists.query_all("car_id-created_at-index", car_id)
        return items[skip : skip + limit]

    def get_build_lists_by_user(self, user_id: UUID, skip: int = 0, limit: int = 100) -> List[BuildList]:
        """Return build lists owned by a user, newest first."""
        items = self.repos.build_lists.query_all("user_id-created_at-index", user_id)
        return items[skip : skip + limit]

    def count_by_user(self, user_id: UUID) -> int:
        """Return how many build lists a user owns."""
        return len(self.repos.build_lists.query_all("user_id-created_at-index", user_id))

    def create(
        self,
        data: BuildListCreate,
        current_user: DBUser,
        additional_data: Optional[Dict[str, Any]] = None,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> BuildList:
        """Create a build list and its build log after the eligibility checks."""
        self._verify_car_exists(data.car_id)
        self._enforce_free_tier_limit(current_user)

        build_list = self.repository.create(self.build_entity(data, current_user, additional_data))
        self._create_build_log(build_list)
        if logger:
            logger.info(f"User {current_user.id} created build list {build_list.id}")
        return build_list

    def update(self, entity_id: UUID, data: BuildListUpdate, current_user: DBUser) -> BuildList:
        """Update a build list, revalidating the car when it changes."""
        changes = data.model_dump(exclude_unset=True)
        if changes.get("car_id") is not None:
            self._verify_car_exists(changes["car_id"])
        return super().update(entity_id, data, current_user)

    def delete(self, entity_id: UUID, current_user: DBUser) -> BuildList:
        """Delete a build list with its parts, phases, labor estimates and build log thread."""
        entity = self.get_by_id(entity_id, allow_public=True)
        if not self.can_modify(entity, current_user):
            raise self.forbidden("delete")
        delete_build_list_cascade(
            entity_id,
            build_lists=self.repos.build_lists,
            parts=self.repos.build_list_parts,
            phases=self.repos.build_list_phases,
            labor_estimates=self.repos.build_list_labor_estimates,
            extra_actions=build_log_delete_actions(
                entity_id, build_logs=self.repos.build_logs, posts=self.repos.build_log_posts
            ),
        )
        return entity

    def copy_build_list(
        self,
        build_list_id: UUID,
        current_user: DBUser,
        logger: Optional[logging.Logger] = None,
        new_name: Optional[str] = None,
    ) -> BuildList:
        """
        Copy a build list, its phases and its parts into a new list owned by
        the current user. Purchased flags are not carried over.
        """
        original = self.get_by_id(build_list_id, allow_public=True)
        self._enforce_free_tier_limit(current_user)

        new_build_list = self.repository.create(
            BuildList(
                name=new_name or f"Copy of {original.name}",
                description=original.description,
                car_id=original.car_id,
                image_urls=list(original.image_urls) if original.image_urls else None,
                base_price_cents=original.base_price_cents,
                user_id=current_user.id,
            )
        )
        self._create_build_log(new_build_list)

        phase_id_map: Dict[UUID, UUID] = {}
        for phase in self.repos.build_list_phases.ordered_for_build_list(original.id):
            new_phase = self.repos.build_list_phases.create(
                BuildListPhase(build_list_id=new_build_list.id, name=phase.name, sort_order=phase.sort_order)
            )
            phase_id_map[phase.id] = new_phase.id

        for part in self.repos.build_list_parts.all_for_build_list(original.id):
            self.repos.build_list_parts.create(
                BuildListPart(
                    build_list_id=new_build_list.id,
                    part_id=part.part_id,
                    added_by=current_user.id,
                    quantity=part.quantity,
                    notes=part.notes,
                    build_list_phase_id=(
                        phase_id_map.get(part.build_list_phase_id) if part.build_list_phase_id else None
                    ),
                )
            )

        if logger:
            logger.info(f"User {current_user.id} copied build list {build_list_id} to {new_build_list.id}")
        return new_build_list
