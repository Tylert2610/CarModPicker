"""Schemas for global application settings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppSettingsRead(BaseModel):
    """Global app settings returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    premium_disabled: bool
    updated_at: datetime


class AppSettingsUpdate(BaseModel):
    """Partial update for global app settings. All fields optional."""

    premium_disabled: bool | None = None
