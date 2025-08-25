from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Schema for request body when creating/updating a build list
class BuildListCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: Optional[int] = None
    image_url: Optional[str] = None


# Schema for request body when updating a build list (all fields optional)
class BuildListUpdate(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, description="Build list name cannot be empty"
    )
    description: Optional[str] = None
    car_id: Optional[int] = None
    image_url: Optional[str] = None


# Schema for response body when reading a build list
class BuildListRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    car_id: Optional[int] = None
    user_id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
