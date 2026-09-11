"""Per-user price-drop alert subscriptions on DynamoDB.

One item per (user, part) pair, so re-subscribing updates the threshold.
``user_id-part_id-index`` and ``part_id-index`` serve the two read paths.
"""

from datetime import datetime
from typing import Iterable
from uuid import UUID

from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository, RangeCondition
from app.db.dynamo.tables import PART_PRICE_ALERTS

USER_INDEX = "user_id-part_id-index"
PART_INDEX = "part_id-index"


class PartPriceAlert(TimestampedDynamoModel):
    """A user's subscription to a price threshold on a part."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    part_id: UUID
    threshold_cents: int = Field(ge=0)
    active: bool = True
    last_fired_at: datetime | None = None


class PartPriceAlertRepository(DynamoRepository[PartPriceAlert]):
    """Price drop alert subscriptions, one per user and part pair."""

    def __init__(self) -> None:
        """Bind to the part price alerts table."""
        super().__init__(PartPriceAlert, PART_PRICE_ALERTS)

    def get_for_user_part(self, user_id: UUID, part_id: UUID) -> PartPriceAlert | None:
        """This user's alert on this part, or None when not subscribed."""
        page = self.query(USER_INDEX, user_id, range_condition=RangeCondition.eq(part_id), limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[PartPriceAlert]:
        """Every alert this user holds, active or not."""
        return self.query_all(USER_INDEX, user_id)

    def list_active_by_user(self, user_id: UUID) -> list[PartPriceAlert]:
        """The user's active alerts, newest first."""
        alerts = [alert for alert in self.list_by_user(user_id) if alert.active]
        return sorted(alerts, key=lambda alert: (alert.created_at, str(alert.id)), reverse=True)

    def list_by_part(self, part_id: UUID) -> list[PartPriceAlert]:
        """Every alert on this part, active or not."""
        return self.query_all(PART_INDEX, part_id)

    def active_at_or_below(self, part_id: UUID, price_cents: int) -> list[PartPriceAlert]:
        """Active alerts on the part whose threshold the given price meets."""
        return [alert for alert in self.list_by_part(part_id) if alert.active and alert.threshold_cents >= price_cents]

    def count(self) -> int:
        """How many alerts exist."""
        return len(self.scan_all())

    def delete_for_parts(self, part_ids: Iterable[UUID]) -> int:
        """Delete every alert on these parts, returning how many were removed."""
        keys = [str(alert.id) for part_id in set(part_ids) for alert in self.list_by_part(part_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)

    def delete_for_user(self, user_id: UUID) -> int:
        """Delete every alert this user holds, returning how many were removed."""
        keys = [str(alert.id) for alert in self.list_by_user(user_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)
