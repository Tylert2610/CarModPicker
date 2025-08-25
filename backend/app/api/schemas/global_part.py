from typing import Optional, Dict
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Schema for request body when creating a part
class GlobalPartCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[int] = Field(
        None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)"
    )
    image_url: Optional[str] = None
    category_id: int
    brand: Optional[str] = None
    part_number: Optional[str] = None
    specifications: Optional[Dict] = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError(
                "Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)"
            )
        return v


# Schema for request body when updating a part (all fields optional)
class GlobalPartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = Field(
        None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)"
    )
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    part_number: Optional[str] = None
    specifications: Optional[Dict] = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError(
                "Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)"
            )
        return v


# Schema for response body when reading a part
class GlobalPartRead(BaseModel):
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


# Schema for response body when reading a part with vote summary
class GlobalPartReadWithVotes(GlobalPartRead):
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None
