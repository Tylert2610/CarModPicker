from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CategoryBase(BaseModel):
    name: str = Field(
        ..., description="Unique category name (e.g., 'exhaust', 'suspension')"
    )
    display_name: str = Field(
        ..., description="Human-readable display name (e.g., 'Exhaust Systems')"
    )
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    is_active: bool = Field(True, description="Whether the category is active")
    sort_order: int = Field(0, description="Sort order for display")


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Unique category name")
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    is_active: Optional[bool] = Field(
        None, description="Whether the category is active"
    )
    sort_order: Optional[int] = Field(None, description="Sort order for display")


class CategoryInDB(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(CategoryInDB):
    pass
