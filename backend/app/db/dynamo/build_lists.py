"""Build lists and their parts, phases and labor estimates on DynamoDB."""

from typing import Any, Iterable, TypeVar
from uuid import UUID

from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import DynamoModel, TimestampedDynamoModel, utc_now
from app.db.dynamo.repository import DynamoRepository, Page, transact_write
from app.db.dynamo.tables import (
    BUILD_LIST_LABOR_ESTIMATES,
    BUILD_LIST_PARTS,
    BUILD_LIST_PHASES,
    BUILD_LISTS,
)

TModel = TypeVar("TModel", bound=DynamoModel)


class BuildList(TimestampedDynamoModel):
    """A user's build for one car, with its parts, phases and labor estimates."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    description: str | None = None
    image_urls: list[str] | None = None
    car_id: UUID | None = None
    user_id: UUID
    base_price_cents: int = 0


class BuildListPart(DynamoModel):
    """A catalog part attached to a build list, with per-build metadata."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    build_list_id: UUID
    part_id: UUID
    added_by: UUID
    quantity: int = 1
    notes: str | None = None
    purchased: bool = False
    added_at: Any = Field(default_factory=utc_now)
    build_list_phase_id: UUID | None = None


class BuildListPhase(DynamoModel):
    """User-defined grouping for parts within a build list."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    build_list_id: UUID
    name: str
    sort_order: int = 0


class BuildListLaborEstimate(TimestampedDynamoModel):
    """Labor / non-part cost line item attached to a build list."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    build_list_id: UUID
    build_list_phase_id: UUID | None = None
    name: str
    description: str | None = None
    cost_cents: int = 0
    sort_order: int = 0


class BuildListChildRepository(DynamoRepository[TModel]):
    """Shared behaviour for the tables hanging off a build list.

    Every child table is indexed by ``build_list_id``; subclasses set
    ``child_index`` to their own GSI, which differ only in the range key.
    """

    child_index: str

    def list_for_build_list(
        self,
        build_list_id: UUID,
        *,
        limit: int = 100,
        cursor: str | None = None,
        scan_forward: bool = True,
    ) -> Page[TModel]:
        """One page of this build list's children."""
        return self.query(
            self.child_index,
            build_list_id,
            limit=limit,
            cursor=cursor,
            scan_forward=scan_forward,
        )

    def all_for_build_list(self, build_list_id: UUID) -> list[TModel]:
        """Every child of this build list."""
        return self.query_all(self.child_index, build_list_id)

    def delete_actions_for_build_list(self, build_list_id: UUID) -> list[dict[str, Any]]:
        """Transaction actions deleting every child of this build list."""
        return [self.delete_action(str(item.id)) for item in self.all_for_build_list(build_list_id)]


class BuildListRepository(DynamoRepository[BuildList]):
    """Build lists, queryable by owning user and by car."""

    def __init__(self) -> None:
        """Bind to the build lists table."""
        super().__init__(BuildList, BUILD_LISTS)

    def list_by_user(
        self,
        user_id: UUID,
        *,
        limit: int = 100,
        cursor: str | None = None,
        scan_forward: bool = False,
    ) -> Page[BuildList]:
        """Build lists owned by a user, newest first by default."""
        return self.query("user_id-created_at-index", user_id, limit=limit, cursor=cursor, scan_forward=scan_forward)

    def list_by_car(
        self,
        car_id: UUID,
        *,
        limit: int = 100,
        cursor: str | None = None,
        scan_forward: bool = False,
    ) -> Page[BuildList]:
        """Build lists for a car, newest first by default."""
        return self.query("car_id-created_at-index", car_id, limit=limit, cursor=cursor, scan_forward=scan_forward)

    def get_many(self, ids: Iterable[UUID]) -> dict[UUID, BuildList]:
        """The build lists for these ids, keyed by id, skipping missing ones."""
        keys = [str(item_id) for item_id in ids]
        if not keys:
            return {}
        return {item.id: item for item in self.batch_get(keys)}

    def count(self) -> int:
        """How many build lists exist."""
        return len(self.scan_all())


class BuildListPartRepository(BuildListChildRepository[BuildListPart]):
    """Parts attached to build lists, ordered by when they were added."""

    child_index = "build_list_id-added_at-index"

    def __init__(self) -> None:
        """Bind to the build list parts table."""
        super().__init__(BuildListPart, BUILD_LIST_PARTS)

    def list_for_part(self, part_id: UUID, *, limit: int = 100, cursor: str | None = None) -> Page[BuildListPart]:
        """One page of the build list entries referencing this catalogue part."""
        return self.query("part_id-index", part_id, limit=limit, cursor=cursor)

    def clear_phase(self, phase_id: UUID, build_list_id: UUID) -> list[dict[str, Any]]:
        """
        Actions detaching every part from a phase being deleted.

        Mirrors the ``ON DELETE SET NULL`` the SQL schema used: parts survive
        the phase, they just fall back to ungrouped.
        """
        return [
            self.update_action(str(part.id), build_list_phase_id=None)
            for part in self.all_for_build_list(build_list_id)
            if part.build_list_phase_id == phase_id
        ]


class BuildListPhaseRepository(BuildListChildRepository[BuildListPhase]):
    """Phases grouping the parts of a build list."""

    child_index = "build_list_id-sort_order-index"

    def __init__(self) -> None:
        """Bind to the build list phases table."""
        super().__init__(BuildListPhase, BUILD_LIST_PHASES)

    def ordered_for_build_list(self, build_list_id: UUID) -> list[BuildListPhase]:
        """This build list's phases in display order, ties broken on id."""
        phases = self.all_for_build_list(build_list_id)
        return sorted(phases, key=lambda phase: (phase.sort_order, str(phase.id)))


class BuildListLaborEstimateRepository(BuildListChildRepository[BuildListLaborEstimate]):
    """Labor and other non-part cost lines on a build list."""

    child_index = "build_list_id-sort_order-index"

    def __init__(self) -> None:
        """Bind to the build list labor estimates table."""
        super().__init__(BuildListLaborEstimate, BUILD_LIST_LABOR_ESTIMATES)

    def ordered_for_build_list(self, build_list_id: UUID) -> list[BuildListLaborEstimate]:
        """This build list's labor estimates in display order, ties broken on id."""
        estimates = self.all_for_build_list(build_list_id)
        return sorted(estimates, key=lambda estimate: (estimate.sort_order, str(estimate.id)))

    def clear_phase(self, phase_id: UUID, build_list_id: UUID) -> list[dict[str, Any]]:
        """Actions detaching every labor estimate from a phase being deleted."""
        return [
            self.update_action(str(estimate.id), build_list_phase_id=None)
            for estimate in self.all_for_build_list(build_list_id)
            if estimate.build_list_phase_id == phase_id
        ]


def delete_build_list_cascade(
    build_list_id: UUID,
    *,
    build_lists: BuildListRepository,
    parts: BuildListPartRepository,
    phases: BuildListPhaseRepository,
    labor_estimates: BuildListLaborEstimateRepository,
    extra_actions: Iterable[dict[str, Any]] = (),
) -> None:
    """Delete a build list and every child row hanging off it.

    DynamoDB has no cascade, and a transaction caps at 100 actions, so lists
    larger than that delete children in batches first and are not atomic.
    """
    actions: list[dict[str, Any]] = [
        *parts.delete_actions_for_build_list(build_list_id),
        *phases.delete_actions_for_build_list(build_list_id),
        *labor_estimates.delete_actions_for_build_list(build_list_id),
        *extra_actions,
    ]

    if len(actions) + 1 <= 100:
        transact_write([*actions, build_lists.delete_action(str(build_list_id))])
        return

    for repository in (parts, phases, labor_estimates):
        children = repository.all_for_build_list(build_list_id)
        if children:
            repository.batch_delete([str(child.id) for child in children])
    build_lists.delete(build_list_id)
