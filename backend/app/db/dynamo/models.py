"""Pydantic base models and id and time helpers for stored DynamoDB items."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from uuid6 import uuid7


def new_id() -> str:
    """A fresh uuid7, time ordered so ids sort by creation."""
    return str(uuid7())


def utc_now() -> datetime:
    """The current time, timezone aware in UTC."""
    return datetime.now(UTC)


class DynamoModel(BaseModel):
    """Base for stored items: an id, and tolerance of unknown attributes."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str = Field(default_factory=new_id)


class TimestampedDynamoModel(DynamoModel):
    """A stored item that tracks its creation and last update times."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        """Mark the item as updated now."""
        self.updated_at = utc_now()
