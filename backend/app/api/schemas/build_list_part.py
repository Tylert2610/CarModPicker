from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
