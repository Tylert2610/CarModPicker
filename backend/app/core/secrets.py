"""Read the application's secrets from AWS Secrets Manager.

One secret per service per environment: `APP_SECRETS_ARN` names a single
Secrets Manager secret whose string is a JSON object whose keys are the
settings names the application expects (`SECRET_KEY`, `SENTRY_DSN`). That is
the shape `terraform/secretsmanager.tf`'s `app-secrets` module creates.

Nothing here runs at import time. `config.py` resolves a secret field on first
read, so a process that never touches a secret never calls Secrets Manager and
never needs the IAM grant, and a warm Lambda invocation makes no call either.

**The fetch, the parse and the cache come from `webbpulse.config`.** This module
used to carry its own boto3 client, its own `json.loads`, its own check that the
payload is a JSON object, and its own module level `_cache` dict keyed by ARN.
All four are `load_json_secret` in the shared package, cached per ARN with an
`lru_cache`, so the copy here was a second implementation of a solved problem
that could drift from the one Portfolio runs. What is left is the part that is
genuinely CarModPicker's: flattening the object to a map of strings, which is
what `Settings._resolve_secret` reads one key at a time and what
`apply_app_secrets` feeds through `TypeAdapter`.

No value is ever logged: the log line names the keys and counts them, never
their contents.
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

# CarModPicker's own flattening of the shared loader's result, cached separately
# from it and keyed by ARN. `load_json_secret` caches the parsed object; this
# caches the string map built from it, so repeated reads do neither the fetch
# nor the flatten. Keyed by ARN rather than a single slot for the same reason it
# always was: a caller that passes an explicit arn cannot be served another
# arn's payload, which a single slot would happily do.
_cache: dict[str, dict[str, str]] = {}


def reset_cache() -> None:
    """Drop the cached secret payloads, here and in the shared loader. For tests.

    Both halves, because the shared cache holds the parsed object this one is
    derived from: clearing only the local map would refill it from a stale parse
    and a rotation test would still see the old value.
    """
    _cache.clear()
    reset_secret_cache()


def _flatten(payload: dict[str, Any]) -> dict[str, str]:
    """The secret's JSON object as a flat map of strings.

    Values that are not strings are JSON-encoded so the caller always gets
    strings; null values are dropped, which is how this module represents
    "absent".
    """
    return {
        name: value if isinstance(value, str) else json.dumps(value)
        for name, value in payload.items()
        if value is not None
    }


def _fetch_with(client: Any, arn: str) -> dict[str, Any]:
    """The shared loader's read and parse, against a caller supplied client.

    `load_json_secret` owns its client so it can cache one per process, which
    leaves no seam for an injected one. Rather than reach into that cache, this
    repeats the same checks against the given client and raises the same
    `ValueError` the shared loader raises, so the two paths agree on what an
    unusable secret is. A client given here is used directly and its result is
    not put in the shared cache, which keeps an injected client from leaking
    into a later call that did not ask for one.
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
    """Return the `APP_SECRETS_ARN` secret as a flat map of strings.

    Unlike `load_app_secrets` this does not touch `os.environ`, which is what
    lets a caller resolve one field without the side effect of exporting every
    other key in the blob. The blob is fetched once per execution environment
    and cached; an empty or absent ARN is a no-op returning an empty map, so
    local development and the test suite never call AWS.

    Anything that stops the blob being read is fatal: a denied read, a missing
    secret, a body that is not JSON, a JSON document that is not an object. All
    of them mean the function is misconfigured and must fail at the point of use
    rather than run on with no signing key. The shared loader raises botocore's
    own error for the first two and `SecretNotJsonObjectError`, a `ValueError`,
    for the rest, which is the same distinction this module used to draw itself.
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
