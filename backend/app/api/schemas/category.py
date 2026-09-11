"""Request and response schemas for part categories."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Fields shared by every category schema."""

    name: str = Field(..., description="Unique category name (e.g., 'exhaust', 'suspension')")
    display_name: str = Field(..., description="Human-readable display name (e.g., 'Exhaust Systems')")
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    is_active: bool = Field(True, description="Whether the category is active")
    sort_order: int = Field(0, description="Sort order for display")


class CategoryCreate(CategoryBase):
    """Request body for creating a category."""

    pass


class CategoryUpdate(BaseModel):
    """Request body for updating a category."""

    name: Optional[str] = Field(None, description="Unique category name")
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    is_active: Optional[bool] = Field(None, description="Whether the category is active")
    sort_order: Optional[int] = Field(None, description="Sort order for display")


class CategoryInDB(CategoryBase):
    """A stored category with its identifiers and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(CategoryInDB):
    """A category as returned to clients."""

    pass
