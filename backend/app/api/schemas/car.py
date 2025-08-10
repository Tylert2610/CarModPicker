from typing import Optional

from pydantic import BaseModel, ConfigDict


# Schema for request body when creating/updating a car
class CarCreate(BaseModel):
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    vin: Optional[str] = None
    image_url: Optional[str] = None


# Schema for request body when updating a car (all fields optional)
class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    trim: Optional[str] = None
    vin: Optional[str] = None
    image_url: Optional[str] = None


# Schema for response body when reading a car
class CarRead(BaseModel):
    id: int
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    vin: Optional[str] = None
    image_url: Optional[str] = None
    user_id: int

    model_config = ConfigDict(from_attributes=True)
