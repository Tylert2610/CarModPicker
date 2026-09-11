"""Sentry initialisation, called once per process with a distinct `server_name`.

The DSN comes from settings, so local runs with none configured no-op. Normal
4xx control flow is ignored, and request and user ids are attached as tags.
"""

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.types import Event, Hint
from webbpulse.log_context import request_id_var, user_id_var

from app.core.config import settings

_HEALTH_SUBSTRINGS = ("health", "ready", "openapi")


def _traces_sampler(sampling_context: dict) -> float:
    """The trace sample rate for one transaction.

    Zero for health, readiness and OpenAPI noise, and five percent otherwise.
    """
    name = sampling_context.get("transaction_context", {}).get("name", "") or ""
    if any(sub in name.lower() for sub in _HEALTH_SUBSTRINGS):
        return 0.0
    return 0.05


def _before_send(event: Event, hint: Hint) -> Event | None:
    """Attach the request and user ids from the log context to every event.

    The `"-"` sentinel that means unset is not attached.
    """
    rid = request_id_var.get()
    uid = user_id_var.get()
    if rid and rid != "-":
        event.setdefault("tags", {})["request_id"] = rid
    if uid and uid != "-":
        event.setdefault("user", {})["id"] = uid
    return event


def init_sentry(*, server_name: str) -> None:
    """Initialise Sentry for this process, or no-op when it should not run.

    Skipped under `TESTING`, outside staging and production, and with no DSN.
    Tags every event with the environment, release and server name.
    """
    if os.environ.get("TESTING") == "true":
        return
    env = (settings.APP_ENVIRONMENT or "").lower()
    if env not in {"staging", "production"}:
        return
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=os.environ.get("SENTRY_RELEASE") or None,
        server_name=server_name,
        send_default_pii=False,
        traces_sampler=_traces_sampler,
        ignore_errors=[
            "fastapi.exceptions.HTTPException",
            "starlette.exceptions.HTTPException",
            "slowapi.errors.RateLimitExceeded",
        ],
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=_before_send,
    )
