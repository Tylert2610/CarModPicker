from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Schema for request body when adding a part to a build list
class BuildListPartCreate(BaseModel):
    notes: Optional[str] = None


# Schema for request body when updating a part in a build list
class BuildListPartUpdate(BaseModel):
    notes: Optional[str] = None


# Schema for response body when reading a build list part
class BuildListPartRead(BaseModel):
    id: int
    build_list_id: int
    part_id: int
    added_by: int
    notes: Optional[str] = None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)
