"""Unit coverage for layer 2 of the rate limiting standard.

Everything here runs against a fake table client rather than moto. The behaviour that
matters most is what happens when DynamoDB does not answer, and a fake is the only way
to provoke a timeout, a throttle and a missing table cheaply and deterministically. The
fake implements the same `TableClient` protocol the real boto3 table satisfies, so the
limiter is exercised through exactly the calls it makes in production.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.api.middleware.shared_rate_limiter import (
    COUNT_ATTRIBUTE,
    REQUEST_CONTEXT_HEADER,
    TTL_ATTRIBUTE,
    SharedRateLimiter,
    client_identity,
)


class FakeTable:
    """An in-memory stand-in for a boto3 DynamoDB Table.

    Implements only the three calls the limiter makes, with the same conditional-write
    semantics DynamoDB applies, so a test that passes here is testing the limiter's logic
    rather than the fake's convenience.
    """

    def __init__(self, *, clock: Optional[list[int]] = None) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.raises: Optional[BaseException] = None
        self.calls: list[str] = []
        self._clock = clock

    def _fail_if_configured(self) -> None:
        if self.raises is not None:
            raise self.raises

    @staticmethod
    def _pk(key: Mapping[str, Any]) -> str:
        return str(key["pk"])

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append("get_item")
        self._fail_if_configured()
        item = self.items.get(self._pk(kwargs["Key"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append("put_item")
        self._fail_if_configured()
        item = dict(kwargs["Item"])
        self.items[self._pk(item)] = item
        return {}

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append("update_item")
        self._fail_if_configured()

        pk = self._pk(kwargs["Key"])
        values = kwargs["ExpressionAttributeValues"]
        existing = self.items.get(pk)

        # Mirror `attribute_not_exists(#ttl) OR #ttl > :now`. A lapsed window fails the
        # condition, which is what drives the limiter's put_item fallback.
        if existing is not None and int(existing.get(TTL_ATTRIBUTE, 0)) <= int(values[":now"]):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "window lapsed"}},
                "UpdateItem",
            )

        if existing is None:
            existing = {"pk": pk, COUNT_ATTRIBUTE: 0, TTL_ATTRIBUTE: int(values[":ttl"])}

        # ADD on the counter, and if_not_exists on the TTL so an open window keeps its
        # original expiry rather than sliding forward on every request.
        existing[COUNT_ATTRIBUTE] = int(existing.get(COUNT_ATTRIBUTE, 0)) + int(values[":one"])
        existing.setdefault(TTL_ATTRIBUTE, int(values[":ttl"]))
        self.items[pk] = existing
        return {"Attributes": dict(existing)}


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Pin the limiter's clock so window arithmetic is exact rather than racy."""
    current = [1_000_000]
    monkeypatch.setattr(
        "app.api.middleware.shared_rate_limiter.now",
        lambda: current[0],
    )
    return current


def make_limiter(table: FakeTable, *, max_requests: int = 3, window_seconds: int = 60) -> SharedRateLimiter:
    return SharedRateLimiter(max_requests, window_seconds, table_client=table)


# --- allow ------------------------------------------------------------------


def test_requests_under_the_limit_are_allowed(frozen_now: list[int]) -> None:
    """Every request up to and including the limit passes."""
    table = FakeTable()
    limiter = make_limiter(table, max_requests=3)

    for _ in range(3):
        limited, retry_after = limiter.check("1.2.3.4")
        assert limited is False
        assert retry_after is None


def test_separate_identities_do_not_share_a_counter(frozen_now: list[int]) -> None:
    """One caller spending its window must not limit a different caller."""
    table = FakeTable()
    limiter = make_limiter(table, max_requests=2)

    for _ in range(3):
        limiter.check("1.1.1.1")
    assert limiter.is_limited("1.1.1.1") is True

    limited, _ = limiter.check("2.2.2.2")
    assert limited is False
    assert limiter.is_limited("2.2.2.2") is False


# --- deny -------------------------------------------------------------------


def test_request_past_the_limit_is_denied_with_a_retry_after(frozen_now: list[int]) -> None:
    """The request after the limit is rejected and reports when to retry."""
    table = FakeTable()
    limiter = make_limiter(table, max_requests=2, window_seconds=60)

    assert limiter.check("9.9.9.9")[0] is False
    assert limiter.check("9.9.9.9")[0] is False

    limited, retry_after = limiter.check("9.9.9.9")
    assert limited is True
    assert retry_after is not None
    assert 1 <= retry_after <= 60


def test_counter_accumulates_across_limiter_instances(frozen_now: list[int]) -> None:
    """The point of layer 2: the count is in the table, not in the process.

    Two limiter instances over one table stand in for two execution environments, which
    is exactly what the in-memory layer 1 limiter cannot do.
    """
    table = FakeTable()
    first = make_limiter(table, max_requests=2)
    second = make_limiter(table, max_requests=2)

    first.check("5.5.5.5")
    second.check("5.5.5.5")

    limited, _ = first.check("5.5.5.5")
    assert limited is True


# --- fail open --------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}}, "UpdateItem"),
        ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}}, "UpdateItem"
        ),
        EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com"),
        RuntimeError("something entirely unexpected"),
    ],
    ids=["missing-table", "throttled", "unreachable", "unexpected"],
)
def test_backend_failure_allows_the_request(frozen_now: list[int], error: BaseException) -> None:
    """A limiter that cannot reach its table must allow traffic, never reject it."""
    table = FakeTable()
    table.raises = error
    limiter = make_limiter(table)

    limited, retry_after = limiter.check("1.2.3.4")
    assert limited is False
    assert retry_after is None

    # The individual entry points fail open too, not just the combined check.
    assert limiter.is_limited("1.2.3.4") is False
    assert limiter.retry_after("1.2.3.4") is None
    assert limiter.record_request("1.2.3.4") == 0


def test_fail_open_is_logged_at_warning(
    frozen_now: list[int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The WARNING is the compensating control, so it has to actually be emitted.

    It carries `rate_limit_failed_open=True` so an alarm can match on it, and the error
    type so the cause is visible without a redeploy.
    """
    table = FakeTable()
    table.raises = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}},
        "UpdateItem",
    )
    limiter = make_limiter(table)

    with caplog.at_level(logging.WARNING, logger="app.api.middleware.shared_rate_limiter"):
        limiter.check("1.2.3.4")

    records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert records, "the fail-open path must log at WARNING"
    message = records[0].getMessage()
    assert "rate_limit_failed_open=True" in message
    assert "ClientError" in message


def test_fail_open_never_raises_into_the_request_path(frozen_now: list[int]) -> None:
    """Nothing in the limiter may propagate an exception, which is what would 5xx."""
    table = FakeTable()
    table.raises = RuntimeError("boom")
    limiter = make_limiter(table)

    # No pytest.raises: the assertion is that these simply return.
    limiter.check("1.2.3.4")
    limiter.is_limited("1.2.3.4")
    limiter.retry_after("1.2.3.4")
    limiter.record_request("1.2.3.4")


# --- TTL --------------------------------------------------------------------


def test_written_items_carry_a_ttl_in_the_future(frozen_now: list[int]) -> None:
    """Every counter must expire on its own, or the table grows without bound."""
    table = FakeTable()
    limiter = make_limiter(table, window_seconds=90)

    limiter.check("1.2.3.4")

    item = table.items["RATE#1.2.3.4"]
    assert item[TTL_ATTRIBUTE] == frozen_now[0] + 90


def test_ttl_is_not_extended_by_later_requests_in_the_same_window(frozen_now: list[int]) -> None:
    """The window is anchored on its first request.

    If each request slid `expires_at` forward, a caller sending steady traffic would
    never leave the window and a single burst would lock them out permanently.
    """
    table = FakeTable()
    limiter = make_limiter(table, max_requests=10, window_seconds=60)

    limiter.check("1.2.3.4")
    first_expiry = table.items["RATE#1.2.3.4"][TTL_ATTRIBUTE]

    frozen_now[0] += 30
    limiter.check("1.2.3.4")

    assert table.items["RATE#1.2.3.4"][TTL_ATTRIBUTE] == first_expiry


def test_expired_window_starts_a_fresh_count(frozen_now: list[int]) -> None:
    """Once the window lapses the caller is allowed again with a new counter."""
    table = FakeTable()
    limiter = make_limiter(table, max_requests=2, window_seconds=60)

    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
    assert limiter.check("1.2.3.4")[0] is True

    frozen_now[0] += 61

    limited, _ = limiter.check("1.2.3.4")
    assert limited is False
    assert table.items["RATE#1.2.3.4"][COUNT_ATTRIBUTE] == 1
    assert table.items["RATE#1.2.3.4"][TTL_ATTRIBUTE] == frozen_now[0] + 60


def test_expired_item_is_treated_as_absent_even_if_dynamodb_still_serves_it(
    frozen_now: list[int],
) -> None:
    """DynamoDB deletes expired items on its own schedule, sometimes hours late.

    A read that trusted the sweeper would keep a caller locked out past the end of their
    window, so the limiter enforces the window itself.
    """
    table = FakeTable()
    limiter = make_limiter(table, max_requests=1, window_seconds=60)

    # An item that is well over the limit but whose window has already passed.
    table.items["RATE#1.2.3.4"] = {
        "pk": "RATE#1.2.3.4",
        COUNT_ATTRIBUTE: 500,
        TTL_ATTRIBUTE: frozen_now[0] - 1,
    }

    assert limiter.is_limited("1.2.3.4") is False
    assert limiter.retry_after("1.2.3.4") is None


# --- identity ---------------------------------------------------------------


class FakeRequest:
    """Minimal stand-in carrying only what `client_identity` reads."""

    def __init__(self, headers: Optional[dict[str, str]] = None, scope: Optional[dict[str, Any]] = None) -> None:
        self.headers = headers or {}
        self.scope = scope or {}
        self.client = None


def test_identity_uses_the_web_adapter_request_context() -> None:
    """Payload format 2.0, which is what every HTTP API sends."""
    request = FakeRequest(headers={REQUEST_CONTEXT_HEADER: json.dumps({"http": {"sourceIp": "203.0.113.7"}})})
    assert client_identity(request) == "203.0.113.7"  # type: ignore[arg-type]


def test_identity_falls_back_to_the_mangum_event_scope() -> None:
    """The zip runtime is still serving traffic during the migration."""
    request = FakeRequest(scope={"aws.event": {"requestContext": {"http": {"sourceIp": "198.51.100.9"}}}})
    assert client_identity(request) == "198.51.100.9"  # type: ignore[arg-type]


def test_identity_never_trusts_x_forwarded_for() -> None:
    """The whole point of keying on the request context.

    A caller can put anything in `X-Forwarded-For`, so honouring it would let anyone mint
    a fresh identity per request while the endpoint looked protected.
    """
    request = FakeRequest(
        headers={
            "X-Forwarded-For": "1.2.3.4",
            REQUEST_CONTEXT_HEADER: json.dumps({"http": {"sourceIp": "203.0.113.7"}}),
        }
    )
    assert client_identity(request) == "203.0.113.7"  # type: ignore[arg-type]

    # And with no request context at all it still must not read the header.
    spoofed = FakeRequest(headers={"X-Forwarded-For": "1.2.3.4"})
    assert client_identity(spoofed) != "1.2.3.4"  # type: ignore[arg-type]


def test_identity_degrades_on_a_malformed_request_context() -> None:
    """A header that is not JSON must not raise out of the middleware."""
    request = FakeRequest(headers={REQUEST_CONTEXT_HEADER: "{not json"})
    assert client_identity(request) == "unknown"  # type: ignore[arg-type]
