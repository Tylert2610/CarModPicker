"""Per-user price-drop alert endpoints.

Hand-rolled router (NOT BaseEndpointRouter) because the surface is intentionally
narrower than CRUD: scoped to current_user, no admin or list-all paths.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from webbpulse.security import TokenError

from app.api.dependencies.auth import decode_access_token, get_current_user
from app.api.dependencies.repositories import get_repositories
from app.api.schemas.part_price_alert import (
    PartPriceAlertCreate,
    PartPriceAlertRead,
    PartPriceAlertUpdate,
)
from app.api.services import part_price_alert_service
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=PartPriceAlertRead,
    status_code=status.HTTP_201_CREATED,
    responses=standard_responses(
        success_description="Alert subscription created (or updated if one already existed)",
        unauthorized=True,
        not_found=True,
        validation_error=True,
    ),
)
async def subscribe_to_part_price_alert(
    payload: PartPriceAlertCreate,
    current_user: DBUser = Depends(get_current_user),
) -> PartPriceAlertRead:
    """Subscribe the current user to a price-drop alert on a part.

    Idempotent on (user_id, part_id) — re-subscribing updates the threshold and
    reactivates a previously-soft-deleted alert instead of creating a duplicate.
    """
    part = get_repositories().parts.get(str(payload.part_id))
    if part is None:
        ResponsePatterns.raise_not_found("Part", payload.part_id)

    alert = part_price_alert_service.create_or_update_alert(
        user_id=current_user.id,
        part_id=payload.part_id,
        threshold_cents=payload.threshold_cents,
    )
    logger.info(
        "part_price_alert_subscribed: alert_id=%s user_id=%s part_id=%s threshold_cents=%d",
        alert.id,
        current_user.id,
        alert.part_id,
        alert.threshold_cents,
    )
    return PartPriceAlertRead.model_validate(alert)


@router.get(
    "/me",
    response_model=list[PartPriceAlertRead],
    responses=standard_responses(
        success_description="Active price-drop alerts for the current user",
        unauthorized=True,
    ),
)
async def list_my_active_alerts(current_user: DBUser = Depends(get_current_user)) -> list[PartPriceAlertRead]:
    """List the current user's active alerts (active=True only)."""
    alerts = part_price_alert_service.list_active_alerts_for_user(current_user.id)
    return [PartPriceAlertRead.model_validate(a) for a in alerts]


def _unsubscribe_redirect_url(success: bool, message: str) -> str:
    """Build the redirect target for the unsubscribe-via-token flow.

    Uses ``settings.frontend_base_url``, the same per-environment SPA origin
    verify_email_confirm redirects to, so each environment sends users back to
    """
    base = f"{settings.frontend_base_url}/account/alerts"
    status_word = "success" if success else "error"
    return f"{base}?status={status_word}&message={message}"


@router.get(
    "/unsubscribe",
    include_in_schema=True,
    responses={
        302: {"description": "Redirected to /account/alerts with a status flag"},
    },
)
async def unsubscribe_via_token(token: str = Query(...)) -> RedirectResponse:
    """One-click unsubscribe via signed JWT (no auth dependency — token IS the auth).

    Decodes the token, requires ``purpose == 'price_alert_unsubscribe'``, looks
    up the alert by id, sets ``active=False``, and redirects the browser to the
    """
    try:
        payload = decode_access_token(token)
        purpose = payload.get("purpose")
        sub = payload.get("sub")

        if purpose != "price_alert_unsubscribe" or not sub:
            logger.warning("price_alert_unsubscribe_invalid_purpose")
            return RedirectResponse(
                url=_unsubscribe_redirect_url(False, "Invalid+or+expired+link"),
                status_code=302,
            )

        try:
            alert_id = UUID(sub)
        except ValueError:
            logger.warning("price_alert_unsubscribe_invalid_sub")
            return RedirectResponse(
                url=_unsubscribe_redirect_url(False, "Invalid+or+expired+link"),
                status_code=302,
            )

        alert = part_price_alert_service.deactivate_by_id(alert_id)
        if alert is None:
            logger.warning("price_alert_unsubscribe_alert_missing: alert_id=%s", alert_id)
            return RedirectResponse(
                url=_unsubscribe_redirect_url(False, "Invalid+or+expired+link"),
                status_code=302,
            )

        logger.info(
            "price_alert_unsubscribe_success: alert_id=%s user_id=%s",
            alert.id,
            alert.user_id,
        )
        return RedirectResponse(
            url=_unsubscribe_redirect_url(True, "Unsubscribed"),
            status_code=302,
        )

    except TokenError as e:
        logger.warning("price_alert_unsubscribe_jwt_error: %s", e)
        return RedirectResponse(
            url=_unsubscribe_redirect_url(False, "Invalid+or+expired+link"),
            status_code=302,
        )


@router.patch(
    "/{alert_id}",
    response_model=PartPriceAlertRead,
    responses=standard_responses(
        success_description="Alert updated",
        unauthorized=True,
        not_found=True,
        validation_error=True,
    ),
)
async def update_my_alert(
    alert_id: UUID,
    payload: PartPriceAlertUpdate,
    current_user: DBUser = Depends(get_current_user),
) -> PartPriceAlertRead:
    """Update threshold and/or active flag on the user's own alert.

    Returns 404 (not 403) for alerts owned by another user, to avoid leaking
    existence via endpoint behavior.
    """
    alert = part_price_alert_service.get_alert_for_owner(alert_id, current_user.id)
    if alert is None:
        ResponsePatterns.raise_not_found("Price alert", alert_id)
    assert alert is not None

    alert = part_price_alert_service.update_alert(alert, threshold_cents=payload.threshold_cents, active=payload.active)
    return PartPriceAlertRead.model_validate(alert)


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=standard_responses(
        success_description="Alert deactivated",
        unauthorized=True,
        not_found=True,
    ),
)
async def delete_my_alert(
    alert_id: UUID,
    current_user: DBUser = Depends(get_current_user),
) -> None:
    """Soft-delete the user's own alert by setting active=False.

    Idempotent at the user-experience level: a second DELETE on the same id
    returns 404 because the row is no longer ownable-and-active. (T03 will
    """
    deactivated = part_price_alert_service.deactivate_alert(alert_id, current_user.id)
    if not deactivated:
        ResponsePatterns.raise_not_found("Price alert", alert_id)
    return None
