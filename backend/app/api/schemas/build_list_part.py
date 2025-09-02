from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .global_part import GlobalPartRead


# Schema for request body when adding a part to a build list
class BuildListPartCreate(BaseModel):
    global_part_id: Optional[int] = None
    quantity: int = Field(1, ge=1, description="Quantity of the part")
    notes: Optional[str] = None


# Schema for request body when updating a part in a build list
class BuildListPartUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1, description="Quantity of the part")
    notes: Optional[str] = None


# Schema for response body when reading a build list part
class BuildListPartRead(BaseModel):
    id: int
    build_list_id: int
    global_part_id: int
    added_by: int
    quantity: int
    notes: Optional[str] = None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for response body when reading a build list part with global part details
class BuildListPartReadWithGlobalPart(BaseModel):
    id: int
    build_list_id: int
    global_part_id: int
    added_by: int
    quantity: int
    notes: Optional[str] = None
    added_at: datetime
    global_part: GlobalPartRead

    model_config = ConfigDict(from_attributes=True)


class CreateGlobalPartAndAddToBuildListRequest(BaseModel):
    """Request model for creating a global part and adding it to a build list."""

    # Global part fields
    name: str
    description: str | None = None
    price: int | None = Field(
        None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)"
    )
    image_url: str | None = None
    category_id: int
    brand: str | None = None
    part_number: str | None = None
    specifications: dict | None = None

    # Build list part fields
    notes: str | None = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError(
                "Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)"
            )
        return v
