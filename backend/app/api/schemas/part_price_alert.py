"""Request and response schemas for part price alerts."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartPriceAlertCreate(BaseModel):
    """Body for POST /api/part-price-alerts/."""

    part_id: UUID = Field(..., description="ID of the part to subscribe to")
    threshold_cents: int = Field(..., ge=0, description="Notify when observed price <= this threshold (cents)")


class PartPriceAlertUpdate(BaseModel):
    """Body for PATCH /api/part-price-alerts/{id}."""

    threshold_cents: Optional[int] = Field(None, ge=0, description="New threshold in cents")
    active: Optional[bool] = Field(None, description="Whether the alert is active")


class PartPriceAlertRead(BaseModel):
    """Response shape for a single alert."""

    id: UUID
    user_id: UUID
    part_id: UUID
    threshold_cents: int = Field(..., ge=0)
    active: bool
    last_fired_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
