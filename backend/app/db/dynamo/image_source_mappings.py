"""Image dedup cache mapping a canonical source URL to its stored S3 key.

Keeps the same product image from being uploaded twice across parts or
scrape sessions. ``source_url-index`` answers the lookup.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import DynamoModel, utc_now
from app.db.dynamo.repository import DynamoRepository
from app.db.dynamo.tables import IMAGE_SOURCE_MAPPINGS

SOURCE_URL_INDEX = "source_url-index"


class ImageSourceMapping(DynamoModel):
    """One stored image keyed by the canonical URL it came from."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    source_url: str
    file_key: str
    created_at: datetime = Field(default_factory=utc_now)


class ImageSourceMappingRepository(DynamoRepository[ImageSourceMapping]):
    """The source URL to stored file key mapping."""

    def __init__(self) -> None:
        """Bind to the image source mappings table."""
        super().__init__(ImageSourceMapping, IMAGE_SOURCE_MAPPINGS)

    def get_by_source_url(self, source_url: str) -> ImageSourceMapping | None:
        """The mapping for this source URL, or None when the image is not stored yet."""
        page = self.query(SOURCE_URL_INDEX, source_url, limit=1)
        return page.items[0] if page.items else None

    def record(self, source_url: str, file_key: str) -> ImageSourceMapping:
        """Remember ``file_key`` for ``source_url``; an existing mapping wins."""
        existing = self.get_by_source_url(source_url)
        if existing is not None:
            return existing
        return self.create(ImageSourceMapping(source_url=source_url, file_key=file_key))

    def all_file_keys(self) -> set[str]:
        """Every stored file key, for reconciling against the bucket."""
        return {mapping.file_key for mapping in self.scan_all()}

    def count(self) -> int:
        """How many mappings exist."""
        return len(self.scan_all())
