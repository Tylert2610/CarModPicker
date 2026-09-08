"""Layer 2 of the rate limiting standard: a shared, DynamoDB backed limiter.

Layer 1 is `rate_limiter.SophisticatedRateLimiter`, which stays. It is in-memory,
so it costs nothing and absorbs a burst inside one execution environment before
any network call happens, but it keys per execution environment, is diluted by
concurrency, and is reset by every cold start. Layer 2 sits behind it and holds a
limit across execution environments, and after the per-domain split across the
nine functions, by counting into `<prefix>-rate-limits`.

Three properties are deliberate and each is pinned by a test.

**It keys on the API Gateway request context, never on `X-Forwarded-For`.**
Behind API Gateway the leftmost `X-Forwarded-For` hop is whatever the caller sent,
so a limiter keyed on it is worse than no limiter: anyone can mint a fresh identity
per request while the endpoint looks protected. `client_identity` reads the
`x-amzn-request-context` header the Lambda Web Adapter forwards and the `aws.event`
scope key Mangum populates, so it is correct under both runtimes during the
migration, and falls back to the real peer address only in local development and
tests.

**It fails open.** Every DynamoDB call is wrapped. A missing table, an expired
credential, a timeout, a throttle: all of them log at WARNING with
`rate_limit_failed_open=True` and allow the request. A rate limiter is a protective
control, not an authorisation control, so refusing traffic because DynamoDB is
unavailable turns a dependency blip into an outage, which is the worse failure. The
WARNING is the compensating control and is what an alarm should watch. Nothing in
this module can raise into the request path or produce a 5xx.

**Items expire on their own.** Each counter carries an `expires_at` TTL attribute,
so a window that is never revisited is reclaimed by DynamoDB rather than
accumulating. Reads do not trust the TTL for correctness, since DynamoDB deletes
expired items on its own schedule and can serve one for hours after it expires; an
item whose `expires_at` has passed is treated as absent and a fresh window starts.

The shape here matches WebbPulse-Portfolio's `app/core/login_limiter.py`: the same
`<prefix>-rate-limits` table, the same single `pk` string hash key, the same
`expires_at` TTL attribute name, and the same fail-open logging. The two repositories
are meant to converge on one implementation, so differences that are not forced are
avoided.
"""

import json
import logging
import time
from typing import Any, Mapping, Optional, Protocol

from botocore.exceptions import ClientError
from fastapi import Request

from ...core.config import settings

logger = logging.getLogger(__name__)

# The header the Lambda Web Adapter injects, carrying the API Gateway request context
# as a plain JSON string. It is not base64 encoded, so this is a straight parse.
REQUEST_CONTEXT_HEADER = "x-amzn-request-context"

# The TTL attribute DynamoDB is configured to watch on `<prefix>-rate-limits`. The name
# is fixed by the table declaration in terraform/ and matches Portfolio's.
TTL_ATTRIBUTE = "expires_at"

COUNT_ATTRIBUTE = "requests"


class TableClient(Protocol):
    """The slice of a boto3 DynamoDB Table this module uses.

    Declared as a Protocol so tests can pass a fake in place of a real table without
    moto or network access, which is what keeps the fail-open paths cheap to pin.
    """

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]: ...


def _error_code(error: ClientError) -> str:
    """The AWS error code, read defensively.

    Both keys are optional in botocore's TypedDict, so the chained `.get` is what keeps
    this total: a malformed error response yields "" rather than a KeyError raised from
    inside the handler that exists to stop errors escaping.
    """
    return str(error.response.get("Error", {}).get("Code", ""))


def now() -> int:
    return int(time.time())


def _source_ip_from_context(context: Any) -> str:
    """Pull the source IP out of one API Gateway request context mapping."""
    if not isinstance(context, dict):
        return ""

    # Payload format 2.0, which is what every HTTP API uses. The Web Adapter's own
    # README example shows `identity.sourceIp`, but that is the 1.0 REST shape and
    # reads as undefined on a 2.0 payload.
    http_section = context.get("http")
    if isinstance(http_section, dict):
        source_ip = http_section.get("sourceIp")
        if isinstance(source_ip, str) and source_ip:
            return source_ip

    # Payload format 1.0, REST APIs.
    identity = context.get("identity")
    if isinstance(identity, dict):
        source_ip = identity.get("sourceIp")
        if isinstance(source_ip, str) and source_ip:
            return source_ip

    return ""


def client_identity(request: Request) -> str:
    """The caller's IP as API Gateway observed it.

    Three sources are tried in order: the `x-amzn-request-context` header the Web
    Adapter forwards, the `aws.event` scope key Mangum populates, and finally the real
    peer address of the socket. The last is only ever reached in local development and
    in tests, because in production one of the first two is always present.

    `X-Forwarded-For` is never consulted.
    """
    raw = request.headers.get(REQUEST_CONTEXT_HEADER)
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Could not parse %s as JSON; ignoring it.", REQUEST_CONTEXT_HEADER)
            parsed = None

        # The adapter forwards the `requestContext` object itself, so the source IP sits
        # at the top level. A caller that hands over the whole event is tolerated too,
        # which keeps the header and scope paths interchangeable.
        source_ip = _source_ip_from_context(parsed)
        if not source_ip and isinstance(parsed, dict):
            source_ip = _source_ip_from_context(parsed.get("requestContext"))
        if source_ip:
            return source_ip

    event = request.scope.get("aws.event")
    if isinstance(event, dict):
        source_ip = _source_ip_from_context(event.get("requestContext"))
        if source_ip:
            return source_ip

    return request.client.host if request.client else "unknown"


class SharedRateLimiter:
    """Fixed window request counter over `<prefix>-rate-limits`.

    The window is anchored on the first request in it rather than on the clock, so a
    caller's window starts when they arrive. `table_client` is injected rather than
    looked up so tests can supply a fake; leaving it None resolves the real table
    lazily, which matters because resolving it at import time would make importing this
    module require AWS configuration.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        table_client: Optional[TableClient] = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._table_client = table_client

    @property
    def table(self) -> TableClient:
        if self._table_client is not None:
            return self._table_client

        from app.db.dynamo import client as dynamo_client
        from app.db.dynamo.tables import RATE_LIMITS

        if settings.RATE_LIMITS_TABLE:
            return dynamo_client.get_resource().Table(settings.RATE_LIMITS_TABLE)
        return dynamo_client.get_table(RATE_LIMITS)

    @staticmethod
    def key(identity: str) -> dict[str, str]:
        return {"pk": f"RATE#{identity}"}

    @staticmethod
    def _failed_open(operation: str, error: BaseException) -> None:
        """Record a limiter failure that let a request through.

        Deliberately broad at the call sites. botocore raises `ClientError`,
        `EndpointConnectionError`, `NoCredentialsError` and `ReadTimeoutError` from
        unrelated base classes, and the right response to all of them is the same:
        allow the request and make the failure visible.
        """
        logger.warning(
            "Shared rate limit check failed; allowing the request. "
            "rate_limit_failed_open=True operation=%s error_type=%s error_message=%s",
            operation,
            type(error).__name__,
            error,
        )

    def _current(self, identity: str) -> Optional[Mapping[str, Any]]:
        item = self.table.get_item(Key=self.key(identity)).get("Item")
        # An item whose TTL has passed is treated as absent. DynamoDB deletes expired
        # items on its own schedule and can keep serving one well after `expires_at`,
        # so the read has to enforce the window itself rather than trust the sweeper.
        if not item or int(item.get(TTL_ATTRIBUTE, 0)) <= now():
            return None
        return item

    def is_limited(self, identity: str) -> bool:
        """True when `identity` has already spent its window. Never raises."""
        try:
            item = self._current(identity)
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("is_limited", error)
            return False
        if item is None:
            return False
        return int(item.get(COUNT_ATTRIBUTE, 0)) >= self.max_requests

    def retry_after(self, identity: str) -> Optional[int]:
        """Seconds until `identity` may retry, or None when it is not limited."""
        try:
            item = self._current(identity)
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("retry_after", error)
            return None
        if item is None or int(item.get(COUNT_ATTRIBUTE, 0)) < self.max_requests:
            return None
        return max(1, int(item[TTL_ATTRIBUTE]) - now())

    def record_request(self, identity: str) -> int:
        """Count one request and return the running total for the window.

        Returns 0 when the counter could not be written, which is below every threshold
        and so allows the request. That is the fail-open path.
        """
        current = now()
        try:
            response = self.table.update_item(
                Key=self.key(identity),
                UpdateExpression=f"ADD {COUNT_ATTRIBUTE} :one SET #ttl = if_not_exists(#ttl, :ttl)",
                ConditionExpression="attribute_not_exists(#ttl) OR #ttl > :now",
                ExpressionAttributeNames={"#ttl": TTL_ATTRIBUTE},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":ttl": current + self.window_seconds,
                    ":now": current,
                },
                ReturnValues="ALL_NEW",
            )
            return int(response["Attributes"][COUNT_ATTRIBUTE])
        except ClientError as error:
            if _error_code(error) != "ConditionalCheckFailedException":
                self._failed_open("record_request", error)
                return 0
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("record_request", error)
            return 0

        # The window that was in the item has passed, so this request starts a new one.
        # An unconditional put is correct here precisely because the old window is spent.
        try:
            self.table.put_item(
                Item={
                    **self.key(identity),
                    COUNT_ATTRIBUTE: 1,
                    TTL_ATTRIBUTE: current + self.window_seconds,
                }
            )
        except Exception as error:  # noqa: BLE001 - fail open on every backend failure
            self._failed_open("record_request", error)
            return 0
        return 1

    def check(self, identity: str) -> tuple[bool, Optional[int]]:
        """Count this request and report whether it should be rejected.

        Returns `(is_limited, retry_after_seconds)`. The count happens first so a
        caller who is already over the limit keeps extending nothing: the window is
        anchored on its first request, and `record_request` only refreshes `expires_at`
        when the previous window had already lapsed.
        """
        count = self.record_request(identity)
        if count == 0 or count <= self.max_requests:
            return False, None
        return True, self.retry_after(identity)


shared_rate_limiter = SharedRateLimiter(
    settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    60,
)
