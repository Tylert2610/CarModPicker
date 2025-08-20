from typing import Optional, Dict
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Schema for request body when creating a part
class PartCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    category_id: int
    brand: Optional[str] = None
    part_number: Optional[str] = None
    specifications: Optional[Dict] = None


# Schema for request body when updating a part (all fields optional)
class PartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    part_number: Optional[str] = None
    specifications: Optional[Dict] = None


# Schema for response body when reading a part
class PartRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    category_id: int
    user_id: int  # Creator
    brand: Optional[str] = None
    part_number: Optional[str] = None
    specifications: Optional[Dict] = None
    is_verified: bool
    source: str
    edit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
