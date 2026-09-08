"""Read the application's secrets from AWS Secrets Manager.

One secret per service per environment: `APP_SECRETS_ARN` names a single
Secrets Manager secret whose string is a JSON object whose keys are the
settings names the application expects (`SECRET_KEY`, `SENTRY_DSN`). That is
the shape `terraform/secretsmanager.tf`'s `app-secrets` module creates.

Nothing here runs at import time. `config.py` resolves a secret field on first
read and caches the fetched blob in module scope, so a process that never
touches a secret never calls Secrets Manager and never needs the IAM grant,
and a warm Lambda invocation makes no call either.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import boto3
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

# Keyed by ARN rather than a single slot: a process only ever reads one secret,
# but keying it means a caller that passes an explicit arn cannot be served
# another arn's payload, which a single slot would happily do.
_cache: dict[str, dict[str, str]] = {}


def reset_cache() -> None:
    """Drop the cached secret payloads. For tests."""
    _cache.clear()


def _parse_payload(arn: str, response: Any) -> dict[str, str]:
    payload = json.loads(response["SecretString"])
    if not isinstance(payload, dict):
        logger.error("Secret %s is not a JSON object", arn)
        raise ValueError("APP_SECRETS_ARN secret must be a JSON object")
    return {
        name: value if isinstance(value, str) else json.dumps(value)
        for name, value in payload.items()
        if value is not None
    }


def fetch_app_secrets(secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    """Return the `APP_SECRETS_ARN` secret as a flat map of strings.

    Unlike `load_app_secrets` this does not touch `os.environ`, which is what
    lets a caller resolve one field without the side effect of exporting every
    other key in the blob. The blob is fetched once per execution environment
    and cached in module scope; an empty or absent ARN is a no-op returning an
    empty map, so local development and the test suite never call AWS.
    """
    arn = secret_arn if secret_arn is not None else os.getenv("APP_SECRETS_ARN", "")
    if not arn:
        return {}
    cached = _cache.get(arn)
    if cached is not None:
        return cached

    try:
        secrets_client = client if client is not None else boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=arn)
    except Exception:
        logger.exception("Failed to load application secrets from %s", arn)
        raise
    values = _parse_payload(arn, response)
    logger.info("Loaded %d application secrets from %s: %s", len(values), arn, ", ".join(sorted(values)))
    _cache[arn] = values
    return values


def load_app_secrets(secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    """Fetch the secret and export every key into `os.environ`.

    Retained for callers that want the whole blob in the environment, notably
    processes outside the API (the crawler entrypoints) that read values such
    as `SENTRY_DSN` straight from `os.environ`. The API itself no longer calls
    this at import; see `Settings` in `config.py`.
    """
    applied = fetch_app_secrets(secret_arn, client)
    for name, value in applied.items():
        os.environ[name] = value
    return applied


def apply_app_secrets(settings: Settings, secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    applied = load_app_secrets(secret_arn, client)
    for name, value in applied.items():
        field = type(settings).model_fields.get(name)
        if field is not None:
            setattr(settings, name, TypeAdapter(field.annotation).validate_python(value))
    return applied
