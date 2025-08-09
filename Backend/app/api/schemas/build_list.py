from pydantic import BaseModel, ConfigDict
from typing import Optional


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
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
