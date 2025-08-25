from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Schema for request body when creating/updating a build list
class BuildListCreate(BaseModel):
    name: str
    description: Optional[str] = None
    car_id: int
    image_url: Optional[str] = None


# Schema for request body when updating a build list (all fields optional)
class BuildListUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    car_id: Optional[int] = None
    image_url: Optional[str] = None


# Schema for response body when reading a build list
class BuildListRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    car_id: int
    user_id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
