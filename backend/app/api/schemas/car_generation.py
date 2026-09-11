"""Request and response schemas for car generations."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, field_serializer

from app.api.schemas.part import apply_image_url_presigning


class CarGenerationCreate(BaseModel):
    """Request body for creating a car generation."""

    car_make_name: str
    car_model_name: str
    generation_name: str
    display_name: Optional[str] = None
    start_year: int
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


class CarGenerationUpdate(BaseModel):
    """Request body for updating a car generation."""

    car_make_name: Optional[str] = None
    car_model_name: Optional[str] = None
    generation_name: Optional[str] = None
    display_name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


class CarGenerationRead(BaseModel):
    """A car generation as returned to clients."""

    id: UUID
    car_make_name: str
    car_model_name: str
    car_model_display_name: Optional[str] = None
    generation_name: str
    display_name: Optional[str] = None
    start_year: int
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_label(self) -> str:
        """The generation's display name, falling back to its raw name."""
        return self.display_name or self.generation_name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def car_model_display_label(self) -> str:
        """The model's display name, falling back to its raw name."""
        return self.car_model_display_name or self.car_model_name

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)
