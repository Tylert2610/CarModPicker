"""Request and response schemas for build lists."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.api.schemas.part import apply_image_url_presigning

MAX_IMAGES_PER_BUILDLIST = 12


class BuildListCreate(BaseModel):
    """Request body for creating a build list."""

    name: str = Field(..., min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: UUID = Field(..., description="Car ID is required - build lists must be associated with a car")
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Images: file keys (from images/upload) and/or external URLs; max 12. First entry is the primary/display image.",
    )
    base_price_cents: int = Field(
        0,
        ge=0,
        description="Donor car purchase price in cents. Folded into total build cost.",
    )


class BuildListUpdate(BaseModel):
    """Request body for updating a build list."""

    name: Optional[str] = Field(None, min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: Optional[UUID] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Images: file keys and/or external URLs; max 12. First entry is the primary/display image.",
    )
    base_price_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Donor car purchase price in cents. Folded into total build cost.",
    )


class BuildListRead(BaseModel):
    """A build list as returned to clients."""

    id: UUID
    name: str
    description: Optional[str] = None
    car_id: Optional[UUID] = None
    user_id: UUID
    image_urls: Optional[List[str]] = None
    base_price_cents: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)


class BuildListReadWithVotes(BuildListRead):
    """A build list with vote counts and rolled up cost totals."""

    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None
    total_cost_cents: Optional[int] = Field(
        None,
        description="Combined cost: sum of (part qty * best price) plus all labor estimate costs",
    )
    total_parts_cost_cents: Optional[int] = Field(
        None,
        description="Sum of (part quantity * best price) for all parts in the build list",
    )
    total_labor_cost_cents: Optional[int] = Field(
        None,
        description="Sum of all labor estimate costs for the build list",
    )


class BuildListAppendImages(BaseModel):
    """Request body for appending images to a build list gallery."""

    file_keys: List[str] = Field(
        ...,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Image references to append: file keys (from images/upload) or external URLs; max 12.",
    )


class BuildListSetPrimaryImageRequest(BaseModel):
    """Request body for choosing a build list's primary image."""

    index: int = Field(..., ge=0, description="0-based index into the build list's image_urls gallery")
