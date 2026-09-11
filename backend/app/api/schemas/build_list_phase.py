"""Request and response schemas for build list phases."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BuildListPhaseCreate(BaseModel):
    """Request body for creating a build list phase."""

    name: str = Field(..., min_length=1, description="Phase name (e.g. Phase 1, Must Have)")
    sort_order: int = Field(0, ge=0, description="Display order")


class BuildListPhaseUpdate(BaseModel):
    """Request body for updating a build list phase."""

    name: str | None = Field(None, min_length=1, description="Phase name")
    sort_order: int | None = Field(None, ge=0, description="Display order")


class BuildListPhaseRead(BaseModel):
    """A build list phase as returned to clients."""

    id: UUID
    build_list_id: UUID
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
