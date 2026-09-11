"""Request and response schemas for parts."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.api.schemas.part_listing import PartListingReadWithRetailer
from app.api.utils.image_utils import get_presigned_url_from_file_key

MAX_IMAGES_PER_PART = 12


def apply_image_url_presigning(value: Optional[List[str]]) -> Optional[List[str]]:
    """Convert list of file keys to presigned URLs."""
    if not value:
        return None
    return [get_presigned_url_from_file_key(k) or k for k in value]


class PartCreate(BaseModel):
    """Request body for creating a part."""

    name: str
    description: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_PART,
        description="Images: file keys (from images/upload) and/or external URLs (scraped); max 12. First entry is the primary/display image.",
    )
    product_url: Optional[str] = Field(
        None, description="Product URL at retailer (used only with retailer_id for listing)"
    )
    category_id: UUID
    car_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Car IDs this part fits. Ignored when is_universal is True.",
    )
    is_universal: bool = Field(
        default=False,
        description="When True, part fits all cars; no need to list car_ids.",
    )
    part_manufacturer_id: Optional[UUID] = Field(
        None,
        description=(
            "Manufacturer/brand for this part. Optional: scraped pages where the "
            "brand cannot be confidently determined leave this NULL rather than "
            "minting a sentinel 'Unknown' brand row. The DB column is also nullable."
        ),
    )
    part_number: Optional[str] = None
    gtin: Optional[str] = Field(
        None,
        description="UPC/EAN/GTIN barcode for dedup (digits only stored); e.g. 012345678901",
    )
    retailer_id: Optional[UUID] = Field(None, description="Retailer ID when product_url is from a known retailer")
    price_cents: Optional[int] = Field(
        None, ge=0, le=2147483647, description="Price in cents for this retailer (creates/updates listing)"
    )

    @field_validator("price_cents")
    @classmethod
    def validate_price_cents(cls, v: Optional[int]) -> Optional[int]:
        """Reject prices outside the stored integer range."""
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v


class PartUpdate(BaseModel):
    """Request body for updating a part."""

    name: Optional[str] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_PART,
        description="Images: file keys and/or external URLs; max 12. First entry is the primary/display image.",
    )
    category_id: Optional[UUID] = None
    car_ids: Optional[List[UUID]] = None
    is_universal: Optional[bool] = None
    part_manufacturer_id: Optional[UUID] = None
    part_number: Optional[str] = None
    gtin: Optional[str] = None


class PartRead(BaseModel):
    """A part as returned to clients."""

    id: UUID
    name: str
    description: Optional[str] = None
    best_price_cents: Optional[int] = Field(
        None, description="Lowest current price from any retailer listing (computed when available)"
    )
    image_urls: Optional[List[str]] = None
    category_id: UUID
    user_id: UUID
    car_ids: List[UUID] = Field(default_factory=list, description="Car IDs this part is associated with")
    is_universal: bool = Field(default=False, description="When True, part fits all cars")
    part_manufacturer_id: Optional[UUID] = None
    part_number: Optional[str] = None
    gtin: Optional[str] = Field(None, description="UPC/EAN/GTIN (digits only)")
    canonical_part_id: Optional[UUID] = Field(
        None,
        description=(
            "When set, this part is a duplicate. Clients should redirect or "
            "resolve to the referenced canonical part for display."
        ),
    )
    edit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)


class PartReadWithVotes(PartRead):
    """A part with its vote tallies."""

    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None


class PartAppendImages(BaseModel):
    """Request body for appending images to a part gallery."""

    file_keys: List[str] = Field(
        ...,
        max_length=MAX_IMAGES_PER_PART,
        description="Image references to append: file keys (from images/upload) or external URLs (scraped); max 12.",
    )


class SetPrimaryImageRequest(BaseModel):
    """Request body for choosing a part's primary image."""

    index: int = Field(..., ge=0, description="0-based index into the part's image_urls gallery")


def _default_listings() -> list[PartListingReadWithRetailer]:
    """Return an empty listings list for use as a field default."""
    return []


class PartReadWithListings(PartRead):
    """A part with its retailer listings and the cheapest one."""

    listings: list[PartListingReadWithRetailer] = Field(
        default_factory=_default_listings, description="Retailer listings with current price"
    )
    best_listing: Optional[PartListingReadWithRetailer] = Field(None, description="Listing with lowest current price")
