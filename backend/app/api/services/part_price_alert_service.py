"""
Service for per-user price-drop alert subscriptions.

Module-level functions (no class) to mirror part_listing_service.py style.
T02 surface: subscribe upsert, list-mine, deactivate.
T03 surface: evaluate_alerts_for_listing, which fires emails when an
observation breaches an active alert's threshold (24h cooldown, exception-safe
per-alert iteration, SES failure leaves last_fired_at unchanged so retries are
idempotent).

Split plan row 25 changed who calls it and nothing about what it does. It used
to run at the end of create_or_update_listing_and_price, on the request thread,
which was `catalog` reading `admin`'s alerts and calling SES. Seam 4 inverted
that: the `part_listings` stream consumer in `app/consumers/price_alerts.py`
calls it now, so a price write returns as soon as its transaction commits and
`catalog` holds no SES grant.
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

# Cooldown window between consecutive fires for the same alert. Prevents an alert
# from spamming the user when several observations land below threshold in rapid
# succession (e.g. a crawler revisiting a listing every few hours).
ALERT_COOLDOWN = timedelta(hours=24)


def create_or_update_alert(user_id: UUID, part_id: UUID, threshold_cents: int) -> PartPriceAlert:
    """Subscribe-or-update upsert keyed on (user_id, part_id).

    Behavior:
    - existing alert, active=True  → update threshold_cents
    - existing alert, active=False → reactivate (active=True) + update threshold_cents
    - no existing alert            → create a new active alert

    Idempotent for callers: re-subscribing the same user+part mutates the
    existing item in place.
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
    map False → 404 (uniform 'not currently active for this user' meaning).
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
    `create_or_update_listing_and_price` on the request thread; the
    `part_listings` stream consumer in `app/consumers/price_alerts.py` calls it,
    which is seam 4. The semantics below did not change, and this function is
    still the single place they live.

    `repos` is the bundle to read and write through, defaulting to the process
    bundle for the scripts and tests that call this directly. The consumer
    passes its own, which is `admin`'s narrow bundle built once per execution
    environment, rather than letting `get_repositories()` build all twenty-five.

    Contract:
    - Only active alerts are considered (`active=True`).
    - Threshold semantics: ``price_cents <= threshold_cents`` fires.
    - 24h cooldown: an alert that fired within ``ALERT_COOLDOWN`` of ``observed_at``
      is suppressed (logged ``verdict=suppressed_cooldown``) without touching
      ``last_fired_at`` so the user-facing window is honest.
    - Exception-safe per-alert iteration: a bad alert (raises during email send,
      template build, or the write) is logged at WARNING with ``alert_id`` and
      iteration continues. One bad alert MUST NOT block other alerts on the
      same part from firing.
    - SES failure (``send_price_drop_alert_email`` returns False) is treated as
      non-firing — ``last_fired_at`` stays unchanged so the next observation
      retries. Email-success path sets ``last_fired_at = observed_at``.
    - Logging: one ``price_alert_evaluated`` INFO log per evaluated alert with
      verdict ∈ {fired, suppressed_cooldown, skip_above_threshold}, and one
      ``price_alert_email_sent`` INFO log per attempted send (success or False).
      Email addresses and unsubscribe tokens are NEVER logged — alert_id +
      user_id (UUID) only.
    """
    # Local import — avoids a circular import with app.core.email at module
    # load (email.py is the leaf side; it does not import services). Keeping
    # the import lazy also makes monkeypatching trivial in tests:
    # `monkeypatch.setattr("app.core.email.send_price_drop_alert_email", ...)`.
    from app.core import email as email_module

    observed_at = _ensure_aware(observed_at)

    if repos is None:
        repos = get_repositories()
    candidate_alerts = repos.part_price_alerts.active_at_or_below(part_id, price_cents)
    if not candidate_alerts:
        return

    # Resolve part + retailer once; both are referenced by every email body.
    part = repos.parts.get(str(part_id))
    retailer = repos.retailers.get(str(retailer_id))
    if part is None or retailer is None:
        # Defensive — the chokepoint guarantees both exist, but evaluate should
        # never crash a price write.
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
                # Alert points at a deleted user — skip and log; do not crash.
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
            # On failure leave last_fired_at as-is so the next observation re-attempts.
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
            # Per-alert iteration must NEVER poison the price write.
            # Log with alert_id (UUID — safe) and continue.
            logger.warning(
                "price_alert_evaluator_exception: alert_id=%s error=%s",
                getattr(alert, "id", "?"),
                exc,
            )
            continue
