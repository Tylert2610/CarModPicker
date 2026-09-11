"""Schemas for part price history and its aggregated summaries."""

from datetime import UTC, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartPriceHistoryBase(BaseModel):
    """Fields shared by every price history schema."""

    part_listing_id: UUID = Field(..., description="Part listing ID")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    observed_at: datetime = Field(..., description="When this price was observed")


class PartPriceHistoryCreate(BaseModel):
    """Request body for recording an observed price."""

    part_listing_id: UUID = Field(..., description="Part listing ID")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When this price was observed")


class PartPriceHistoryRead(PartPriceHistoryBase):
    """A price observation as returned to clients."""

    id: UUID

    model_config = ConfigDict(from_attributes=True)


class PartPriceHistoryReadWithRetailer(PartPriceHistoryRead):
    """Price history entry with retailer info for API responses."""

    retailer_id: UUID = Field(..., description="Retailer ID")
    retailer_name: str = Field(..., description="Retailer display name")


PriceTrend = Literal["up", "down", "flat"]
PriceWindow = Literal["7d", "30d", "90d", "180d", "1y", "all"]


class PriceHistorySummary(BaseModel):
    """Aggregated price stats over a window for one part (or one retailer slice of it)."""

    min_cents: Optional[int] = Field(None, description="Lowest observed price in window (None if no observations)")
    max_cents: Optional[int] = Field(None, description="Highest observed price in window (None if no observations)")
    last_cents: Optional[int] = Field(None, description="Most recent observed price in window")
    last_observed_at: Optional[datetime] = Field(None, description="When the most recent price was observed")
    trend: PriceTrend = Field("flat", description="Linear-regression slope sign over the window")
    observation_count: int = Field(0, ge=0, description="Number of observations contributing to this summary")


class RetailerPriceBreakdown(BaseModel):
    """Per-retailer summary inside a single-part response."""

    retailer_id: UUID
    retailer_name: str
    min_cents: Optional[int] = None
    max_cents: Optional[int] = None
    last_cents: Optional[int] = None
    last_observed_at: Optional[datetime] = None
    observation_count: int = Field(0, ge=0)


class PriceHistorySinglePartResponse(BaseModel):
    """Response for GET /api/parts/{id}/price-history (object shape)."""

    summary: PriceHistorySummary
    retailers: list[RetailerPriceBreakdown] = Field(default_factory=list)
    history: list[PartPriceHistoryReadWithRetailer] = Field(default_factory=list)
    pre_window_anchors: list[PartPriceHistoryReadWithRetailer] = Field(
        default_factory=list,
        description=(
            "Most recent observation per retailer occurring strictly before the "
            "window cutoff. Lets clients render a 'last known' carry-over point "
            "so a sparse window doesn't show a stranded observation. Empty for "
            "window='all'."
        ),
    )
    window: str = Field(..., description="Echoed window literal applied to this response")


class PriceHistoryBatchSummaryItem(PriceHistorySummary):
    """Per-part summary inside a batch response. Same shape as PriceHistorySummary."""


class PriceHistoryBatchRequest(BaseModel):
    """Body for POST /api/parts/price-history."""

    part_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    window: PriceWindow = Field("90d")


class PriceHistoryBatchResponse(BaseModel):
    """Response for POST /api/parts/price-history."""

    summaries: dict[UUID, PriceHistoryBatchSummaryItem]
    window: str
    requested_count: int = Field(..., ge=0)
    found_count: int = Field(..., ge=0)
