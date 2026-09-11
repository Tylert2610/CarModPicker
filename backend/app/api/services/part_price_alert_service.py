"""Service for per-user price-drop alert subscriptions.

Module-level functions (no class) to mirror part_listing_service.py style.
T02 surface: subscribe upsert, list-mine, deactivate.
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from app.api.dependencies.repositories import get_repositories
from app.db.dynamo.models import utc_now
from app.db.dynamo.part_price_alerts import PartPriceAlert

logger = logging.getLogger(__name__)

ALERT_COOLDOWN = timedelta(hours=24)


def create_or_update_alert(user_id: UUID, part_id: UUID, threshold_cents: int) -> PartPriceAlert:
    """Subscribe-or-update upsert keyed on (user_id, part_id).

    Behavior:
    """
    alerts = get_repositories().part_price_alerts
    existing = alerts.get_for_user_part(user_id, part_id)
    if existing is not None:
        return alerts.update(existing.id, threshold_cents=threshold_cents, active=True, updated_at=utc_now())
    return alerts.create(PartPriceAlert(user_id=user_id, part_id=part_id, threshold_cents=threshold_cents))


def list_active_alerts_for_user(user_id: UUID) -> list[PartPriceAlert]:
    """Return every active alert (active=True) belonging to the user, newest-first."""
    return get_repositories().part_price_alerts.list_active_by_user(user_id)


def get_alert_for_owner(alert_id: UUID, user_id: UUID) -> Optional[PartPriceAlert]:
    """Return the alert if it exists AND belongs to user_id; None otherwise.

    Used by PATCH/DELETE endpoints to enforce per-user ownership without
    leaking existence (404 on both not-found and wrong-owner).
    """
    alert = get_repositories().part_price_alerts.get(alert_id)
    if alert is None or alert.user_id != user_id:
        return None
    return alert


def update_alert(
    alert: PartPriceAlert, *, threshold_cents: Optional[int] = None, active: Optional[bool] = None
) -> PartPriceAlert:
    """Apply the provided threshold/active changes to an alert the caller already owns."""
    changes: dict[str, object] = {}
    if threshold_cents is not None:
        changes["threshold_cents"] = threshold_cents
    if active is not None:
        changes["active"] = active
    if not changes:
        return alert
    return get_repositories().part_price_alerts.update(alert.id, updated_at=utc_now(), **changes)


def deactivate_alert(alert_id: UUID, user_id: UUID) -> bool:
    """Soft-delete: set active=False on the alert if it belongs to user_id and is active.

    Returns True if an alert was found-active-and-owned and deactivated; False if the
    alert doesn't exist, belongs to another user, or is already inactive. Endpoints
    """
    alert = get_alert_for_owner(alert_id, user_id)
    if alert is None or not alert.active:
        return False
    update_alert(alert, active=False)
    return True


def deactivate_by_id(alert_id: UUID) -> Optional[PartPriceAlert]:
    """Deactivate an alert regardless of owner (one-click unsubscribe). None when missing."""
    alert = get_repositories().part_price_alerts.get(alert_id)
    if alert is None:
        return None
    return update_alert(alert, active=False)


def _ensure_aware(ts: datetime) -> datetime:
    """Treat naive datetimes as UTC — observation timestamps from the
    crawler/test paths sometimes come in naive."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def evaluate_alerts_for_listing(
    part_id: UUID,
    retailer_id: UUID,
    price_cents: int,
    observed_at: datetime,
    repos: Optional[Any] = None,
) -> None:
    """Evaluate every active alert on `part_id` against this observation and

    fire emails for those whose threshold is breached.
    Split plan row 25 moved the only caller. This is no longer invoked from
    """
    from app.core import email as email_module

    observed_at = _ensure_aware(observed_at)

    if repos is None:
        repos = get_repositories()
    candidate_alerts = repos.part_price_alerts.active_at_or_below(part_id, price_cents)
    if not candidate_alerts:
        return

    part = repos.parts.get(str(part_id))
    retailer = repos.retailers.get(str(retailer_id))
    if part is None or retailer is None:
        logger.warning(
            "price_alert_evaluator_missing_entity: part_id=%s retailer_id=%s " "part_present=%s retailer_present=%s",
            part_id,
            retailer_id,
            part is not None,
            retailer is not None,
        )
        return

    for alert in candidate_alerts:
        start = time.monotonic()
        try:
            if alert.last_fired_at is not None and observed_at - _ensure_aware(alert.last_fired_at) < ALERT_COOLDOWN:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "price_alert_evaluated: alert_id=%s part_id=%s "
                    "price_cents=%d threshold_cents=%d verdict=suppressed_cooldown "
                    "elapsed_ms=%d",
                    alert.id,
                    part_id,
                    price_cents,
                    alert.threshold_cents,
                    elapsed_ms,
                )
                continue

            user = repos.users.get(alert.user_id)
            if user is None:
                logger.warning(
                    "price_alert_evaluator_missing_user: alert_id=%s user_id=%s",
                    alert.id,
                    alert.user_id,
                )
                continue

            success = email_module.send_price_drop_alert_email(user.email, part, retailer, price_cents, alert)
            logger.info(
                "price_alert_email_sent: alert_id=%s user_id=%s success=%s",
                alert.id,
                alert.user_id,
                bool(success),
            )

            if success:
                repos.part_price_alerts.update(alert.id, last_fired_at=observed_at, updated_at=utc_now())
            verdict = "fired"

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "price_alert_evaluated: alert_id=%s part_id=%s "
                "price_cents=%d threshold_cents=%d verdict=%s elapsed_ms=%d",
                alert.id,
                part_id,
                price_cents,
                alert.threshold_cents,
                verdict,
                elapsed_ms,
            )
        except Exception as exc:
            logger.warning(
                "price_alert_evaluator_exception: alert_id=%s error=%s",
                getattr(alert, "id", "?"),
                exc,
            )
            continue
