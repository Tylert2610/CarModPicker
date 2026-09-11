"""Read the application's secrets from one JSON Secrets Manager secret.

Nothing runs at import: a field resolves on first read, so a process that
touches no secret needs no IAM grant. No value is ever logged, only key names.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from webbpulse.config import load_json_secret, reset_secret_cache

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

_cache: dict[str, dict[str, str]] = {}


def reset_cache() -> None:
    """Drop the cached secret payloads, here and in the shared loader. For tests.

    Both halves, because this map is derived from the shared parse and clearing
    only one would refill it from the stale one.
    """
    _cache.clear()
    reset_secret_cache()


def _flatten(payload: dict[str, Any]) -> dict[str, str]:
    """The secret's JSON object as a flat map of strings.

    Non-string values are JSON-encoded so callers always get strings, and nulls
    are dropped, which is how this module represents absent.
    """
    return {
        name: value if isinstance(value, str) else json.dumps(value)
        for name, value in payload.items()
        if value is not None
    }


def _fetch_with(client: Any, arn: str) -> dict[str, Any]:
    """The shared loader's read and parse, against a caller supplied client.

    Repeats the loader's checks and raises the same `ValueError`, and does not
    populate the shared cache, so an injected client cannot leak into later calls.
    """
    response = client.get_secret_value(SecretId=arn)
    raw = response.get("SecretString")
    if raw is None:
        logger.error("Secret %s is not a JSON object", arn)
        raise ValueError("APP_SECRETS_ARN secret must be a JSON object")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        logger.error("Secret %s is not a JSON object", arn)
        raise ValueError("APP_SECRETS_ARN secret must be a JSON object")
    return payload


def fetch_app_secrets(secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    """The app secret as a flat map of strings, cached per execution environment.

    Unlike `load_app_secrets` this does not touch `os.environ`. An absent ARN is
    a no-op, and anything that stops the blob being read is fatal.
    """
    arn = secret_arn if secret_arn is not None else os.getenv("APP_SECRETS_ARN", "")
    if not arn:
        return {}
    cached = _cache.get(arn)
    if cached is not None:
        return cached

    try:
        payload = _fetch_with(client, arn) if client is not None else load_json_secret(arn)
    except Exception:
        logger.exception("Failed to load application secrets from %s", arn)
        raise
    values = _flatten(payload)
    logger.info("Loaded %d application secrets from %s: %s", len(values), arn, ", ".join(sorted(values)))
    _cache[arn] = values
    return values


def load_app_secrets(secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    """Fetch the secret and export every key into `os.environ`.

    For callers outside the API that read values straight from the environment;
    the API resolves fields lazily through `Settings` instead.
    """
    applied = fetch_app_secrets(secret_arn, client)
    for name, value in applied.items():
        os.environ[name] = value
    return applied


def apply_app_secrets(settings: Settings, secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    """Export the secret into the environment and set the matching settings fields.

    Each value is validated against its field's annotation before being set.
    """
    applied = load_app_secrets(secret_arn, client)
    for name, value in applied.items():
        field = type(settings).model_fields.get(name)
        if field is not None:
            setattr(settings, name, TypeAdapter(field.annotation).validate_python(value))
    return applied
