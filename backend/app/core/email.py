"""Transactional email through SES: verification, password reset and price alerts.

Bodies come from the HTML templates beside this module. Every send returns a
bool rather than raising, and nothing is sent when email is disabled.
"""

import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"
_CONFIG_SET = "carmodpicker-transactional"

VERIFY_EMAIL_SUBJECT = "Verify your CarModPicker email address"
RESET_PASSWORD_SUBJECT = "Reset your CarModPicker password"
PRICE_DROP_ALERT_SUBJECT_PREFIX = "[CarModPicker] Price drop on"


def _load_template(name: str) -> str:
    """One named HTML template from the templates directory."""
    return (_TEMPLATES_DIR / f"{name}.html").read_text(encoding="utf-8")


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send a single transactional email via SES. Returns True on success."""
    if not settings.EMAIL_ENABLED:
        logger.debug(f"Email disabled, skipping send to {to_email} (subject: {subject!r})")
        return False
    try:
        client = boto3.client("sesv2", region_name=settings.AWS_REGION)
        client.send_email(
            FromEmailAddress=settings.EMAIL_FROM,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
                }
            },
            ConfigurationSetName=_CONFIG_SET,
        )
        return True
    except (BotoCoreError, ClientError) as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return False


def send_verify_email(to_email: str, verify_url: str) -> bool:
    """Send the email-verification message."""
    html = _load_template("verify_email").replace("{{VERIFY_EMAIL_LINK}}", verify_url)
    return _send(to_email, VERIFY_EMAIL_SUBJECT, html)


def send_reset_password_email(to_email: str, reset_url: str) -> bool:
    """Send the password-reset message."""
    html = _load_template("reset_password").replace("{{RESET_PASSWORD_LINK}}", reset_url)
    return _send(to_email, RESET_PASSWORD_SUBJECT, html)


def send_price_drop_alert_email(
    to_email: str,
    part: Any,
    retailer: Any,
    price_cents: int,
    alert: Any,
) -> bool:
    """Send a price drop alert for `part` to `to_email`, returning success.

    The unsubscribe link carries a 30 day signed token so it works without a login.
    A `False` return leaves `last_fired_at` alone, so the next observation retries.
    """
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token

    token = create_access_token(
        data={"sub": str(alert.id), "purpose": "price_alert_unsubscribe"},
        expires_delta=timedelta(days=30),
    )

    unsubscribe_url = f"{settings.api_base_url}/api/part-price-alerts/unsubscribe?token={token}"
    part_url = f"{settings.frontend_base_url}/parts/{part.id}"

    formatted_price = f"${price_cents / 100:.2f}"
    part_name = getattr(part, "name", "your watched part") or "your watched part"
    retailer_name = getattr(retailer, "name", "Retailer") or "Retailer"

    subject = f"{PRICE_DROP_ALERT_SUBJECT_PREFIX} {part_name}"

    html = (
        _load_template("price_drop_alert")
        .replace("{{PART_NAME}}", _escape_html(part_name))
        .replace("{{CURRENT_PRICE}}", _escape_html(formatted_price))
        .replace("{{RETAILER_NAME}}", _escape_html(retailer_name))
        .replace("{{PART_URL}}", part_url)
        .replace("{{UNSUBSCRIBE_URL}}", unsubscribe_url)
    )
    return _send(to_email, subject, html)


def _escape_html(text: str) -> str:
    """Escape the five characters that must not appear raw in template HTML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
