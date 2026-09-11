"""Request and response schemas for build logs and their posts."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BuildLogPostCreate(BaseModel):
    """Request body for creating a build log post."""

    content: str = Field(..., min_length=1, description="Post content cannot be empty")


class BuildLogPostUpdate(BaseModel):
    """Request body for updating a build log post."""

    content: Optional[str] = Field(None, min_length=1, description="Post content cannot be empty")


class BuildLogPostRead(BaseModel):
    """A build log post as returned to clients."""

    id: UUID
    build_log_id: UUID
    user_id: Optional[UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author_username: Optional[str] = None
    author_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BuildLogRead(BaseModel):
    """A build log with its posts."""

    id: UUID
    build_list_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    posts: List[BuildLogPostRead] = []

    model_config = ConfigDict(from_attributes=True)


class BuildLogReadPaginated(BaseModel):
    """A build log whose posts carry pagination metadata."""

    id: UUID
    build_list_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    posts: List[BuildLogPostRead] = []
    pagination: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class BuildLogPostReadWithAuthor(BaseModel):
    """A build log post with its author resolved."""

    id: UUID
    build_log_id: UUID
    user_id: Optional[UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author_username: str
    author_id: UUID

    model_config = ConfigDict(from_attributes=True)
