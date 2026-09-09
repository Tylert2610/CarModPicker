import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

# IN-07: declare the logger at module level (QUAL-07 idiom) so log records
# emitted from ``email.py`` carry ``name="app.core.email"`` instead of the
# shared ``app.core.logging.logger`` module name. Importing the module-level
# ``logger`` helper directly from ``app.core.logging`` is fine for runtime
# behavior, but it tags records with the logging-module's name and breaks
# log-routing filters keyed on module origin.
logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"
_CONFIG_SET = "carmodpicker-transactional"

VERIFY_EMAIL_SUBJECT = "Verify your CarModPicker email address"
RESET_PASSWORD_SUBJECT = "Reset your CarModPicker password"
PRICE_DROP_ALERT_SUBJECT_PREFIX = "[CarModPicker] Price drop on"


def _load_template(name: str) -> str:
    return (_TEMPLATES_DIR / f"{name}.html").read_text(encoding="utf-8")


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send a single transactional email via SES. Returns True on success."""
    if not settings.EMAIL_ENABLED:
        logger.debug(f"Email disabled — skipping send to {to_email} (subject: {subject!r})")
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
    """Send a price-drop alert email for `part` to `to_email`.

    Builds a 30-day signed JWT with ``purpose='price_alert_unsubscribe'`` so the
    one-click unsubscribe link in the email body deactivates the alert without
    requiring login. Returns False on SES failure (matches send_verify_email
    contract); the evaluator leaves last_fired_at unchanged on False so the
    retry on the next observation is idempotent.

    Redaction: this function does not log the email address, the unsubscribe
    token, or the user_id — those are emitted by the evaluator with safe
    fields only.
    """
    # Local imports defer until first send so test environments without an
    # email-enabled config still import cleanly even if SECRET_KEY/DEBUG are
    # not yet set up at module-import time.
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
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
