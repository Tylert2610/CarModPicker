"""Global app settings on DynamoDB.

A single item (numeric partition key ``id`` = 1) holds runtime-mutable
toggles that apply to every user, such as the premium-system kill switch.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.db.dynamo.models import DynamoModel, utc_now
from app.db.dynamo.repository import DynamoRepository
from app.db.dynamo.tables import APP_SETTINGS

SETTINGS_ID = 1


class AppSettings(DynamoModel):
    """Singleton settings item (``id`` is always 1)."""

    id: int = SETTINGS_ID  # pyright: ignore[reportIncompatibleVariableOverride]
    premium_disabled: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class AppSettingsRepository(DynamoRepository[AppSettings]):
    """The singleton app settings item."""

    def __init__(self) -> None:
        """Bind to the app settings table."""
        super().__init__(AppSettings, APP_SETTINGS)

    def get_or_create(self) -> AppSettings:
        """Return the singleton settings item, creating it with defaults on first access."""
        current = self.get(SETTINGS_ID)
        if current is not None:
            return current
        return self.put(AppSettings())

    def update_settings(self, **changes: Any) -> AppSettings:
        """Apply the given field changes to the singleton item and return the result."""
        self.get_or_create()
        if not changes:
            return self.get_or_create()
        return self.update(SETTINGS_ID, updated_at=utc_now(), **changes)

    def premium_disabled(self) -> bool:
        """True when the premium kill switch is set."""
        current = self.get(SETTINGS_ID)
        return bool(current and current.premium_disabled)
