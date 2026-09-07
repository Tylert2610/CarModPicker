"""Sentry SDK 2.x init helper for CarModPicker backend (OBS-01).

Single entry point (`init_sentry(*, server_name)`) called from every process:

- `app/main.py`                      → server_name="apprunner-backend"
- `app/crawlers/__main__.py`         → server_name="crawler-cli"
- `app/crawlers/ecs_runner.py`       → server_name="ecs-crawler"
- `app/crawlers/ecs_rescrape_runner.py` → server_name="ecs-crawler"

# DSN source

DSN is pulled from `SENTRY_DSN` env var at init time. In production the Lambda
API reads the `${prefix}/app` JSON secret at cold start (via `APP_SECRETS_ARN`)
and applies `SENTRY_DSN` from it; in local dev the value is simply unset so
`init_sentry()` no-ops. Never hard-code the DSN, see `terraform/secretsmanager.tf`
and `app/core/secrets.py` for the injection path (D-01, D-55).

# Release tag

`SENTRY_RELEASE` is the git commit SHA baked at Docker build time by GitHub
Actions. Empty release → Sentry shows "(unknown)" for that event but the SDK
still works. Release is passed as `release=...` to `sentry_sdk.init` (D-02).

# Ignored exceptions

These never reach Sentry, because they're normal 4xx control-flow, not bugs:

- `fastapi.exceptions.HTTPException`      — FastAPI 4xx/redirect raises
- `starlette.exceptions.HTTPException`    — Starlette base class (caught by safety net)
- `slowapi.errors.RateLimitExceeded`      — defensive entry; our rate limiter
   currently returns JSONResponse directly rather than raising. Kept so if we
   ever swap to slowapi, 429s still won't flood Sentry quota (D-07, Landmine 1).

Rate limiter in `backend/app/api/middleware/rate_limiter.py` returns
`JSONResponse(status_code=429)` directly (verified via grep — no `raise`
call) so HTTPException(429) does not currently flow through Sentry.

# Server name

Each process passes a distinct `server_name` so Sentry's "server" facet
separates App Runner exceptions from Fargate crawler exceptions from CLI
runs. Keep the three canonical values: `apprunner-backend`, `ecs-crawler`,
`crawler-cli` (D-11).

# Scope processor

`_before_send` reads `request_id_var.get()` and `user_id_var.get()` from
`log_context.py` ContextVars (populated by plan 02-01's
`bg_log_context` / `request_context_middleware` / CLI bootstrap) and
attaches them as `tags.request_id` + `user.id`. Only ever attaches tags
when the values are not the sentinel "-" default (D-09).

# See also

- `CLAUDE.md` "Architecture / Backend" bullet for a one-line pointer
- `.planning/phases/02-observability/02-CONTEXT.md` §D-01..D-15 for all decisions
- `.planning/phases/02-observability/02-RESEARCH.md` §5 Landmines 1, 2, 3, 16, 17
"""

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

# Starlette integration REQUIRED even with FastApi — NOT auto-enabled (Landmine 2)
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.types import Event, Hint

from app.core.config import settings
from app.core.log_context import request_id_var, user_id_var

_HEALTH_SUBSTRINGS = ("health", "ready", "openapi")


def _traces_sampler(sampling_context: dict) -> float:
    """Return trace sample rate per-transaction.

    0.0 for health/ready/openapi noise; 0.05 (5%) otherwise. Keeps Sentry
    Performance free-tier under budget while still producing a representative
    transaction sample for the dashboard (D-06).
    """
    name = sampling_context.get("transaction_context", {}).get("name", "") or ""
    if any(sub in name.lower() for sub in _HEALTH_SUBSTRINGS):
        return 0.0
    return 0.05


def _before_send(event: Event, hint: Hint) -> Event | None:
    """Attach request_id + user_id from ContextVars to every Sentry event.

    Reads from plan 02-01's `request_id_var` + `user_id_var` (populated by
    `request_context_middleware` for HTTP requests, `bg_log_context` for
    background tasks, and the CLI bootstrap in `crawlers/__main__.py`). The
    sentinel "-" default is not attached (D-09).
    """
    rid = request_id_var.get()
    uid = user_id_var.get()
    if rid and rid != "-":
        event.setdefault("tags", {})["request_id"] = rid
    if uid and uid != "-":
        event.setdefault("user", {})["id"] = uid
    return event


def init_sentry(*, server_name: str) -> None:
    """Initialize Sentry for the current process.

    No-ops when any of the following hold (D-01, D-13):
    - `TESTING` env var is "true" (prevents test collection from firing init)
    - `APP_ENVIRONMENT` is not "staging" or "production" (dev runs don't emit)
    - `SENTRY_DSN` env var is empty or whitespace

    On active init: registers FastAPI + Starlette + SQLAlchemy + Logging
    integrations (all four explicit — Starlette is NOT auto-enabled),
    installs `_traces_sampler` + `_before_send`, and tags every event with
    `environment`, `release`, `server_name`.
    """
    if os.environ.get("TESTING") == "true":
        return
    env = (settings.APP_ENVIRONMENT or "").lower()
    if env not in {"staging", "production"}:
        return
    dsn = os.environ.get("SENTRY_DSN", "").strip()
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
