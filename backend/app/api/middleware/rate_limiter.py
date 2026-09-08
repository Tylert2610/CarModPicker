"""
Sophisticated rate limiting middleware for FastAPI application.
Provides different rate limits for GET vs other methods and endpoint-specific limits.
"""

import logging
import os
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ...core.config import settings
from .shared_rate_limiter import client_identity, shared_rate_limiter

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting rules."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        get_requests_per_minute: int = 120,
        get_requests_per_hour: int = 2000,
        auth_requests_per_minute: int = 10,
        auth_requests_per_hour: int = 100,
        admin_requests_per_minute: int = 30,
        admin_requests_per_hour: int = 300,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.get_requests_per_minute = get_requests_per_minute
        self.get_requests_per_hour = get_requests_per_hour
        self.auth_requests_per_minute = auth_requests_per_minute
        self.auth_requests_per_hour = auth_requests_per_hour
        self.admin_requests_per_minute = admin_requests_per_minute
        self.admin_requests_per_hour = admin_requests_per_hour


class SophisticatedRateLimiter:
    """
    Sophisticated in-memory rate limiter with different limits for different HTTP methods and endpoints.
    For production use, consider using Redis or a dedicated rate limiting service.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None) -> None:
        self.config = config or RateLimitConfig()

        # Separate tracking for different rate limit types
        self.minute_requests: Dict[str, list[float]] = defaultdict(list)
        self.hour_requests: Dict[str, list[float]] = defaultdict(list)
        self.get_minute_requests: Dict[str, list[float]] = defaultdict(list)
        self.get_hour_requests: Dict[str, list[float]] = defaultdict(list)
        self.auth_minute_requests: Dict[str, list[float]] = defaultdict(list)
        self.auth_hour_requests: Dict[str, list[float]] = defaultdict(list)
        self.admin_minute_requests: Dict[str, list[float]] = defaultdict(list)
        self.admin_hour_requests: Dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxy headers."""
        # Check for forwarded headers first (for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct connection
        return request.client.host if request.client else "unknown"

    def _get_rate_limit_key(self, request: Request) -> str:
        """Generate a unique key for rate limiting based on client IP and endpoint type."""
        client_ip = self._get_client_ip(request)
        path = request.url.path
        method = request.method

        # Determine endpoint type
        if path.startswith("/api/auth"):
            return f"auth:{client_ip}"
        elif path.startswith("/api/admin") or "admin" in path:
            return f"admin:{client_ip}"
        elif method == "GET":
            return f"get:{client_ip}"
        else:
            return f"default:{client_ip}"

    def _cleanup_old_requests(self, key: str, window_seconds: int, requests_dict: Dict[str, list[float]]) -> None:
        """Remove old requests outside the time window."""
        current_time = time.time()
        requests_dict[key] = [req_time for req_time in requests_dict[key] if current_time - req_time < window_seconds]

    def _get_rate_limits_for_request(self, request: Request) -> Tuple[int, int]:
        """Get the appropriate rate limits for the request."""
        path = request.url.path
        method = request.method

        if path.startswith("/api/auth"):
            return (
                self.config.auth_requests_per_minute,
                self.config.auth_requests_per_hour,
            )
        elif path.startswith("/api/admin") or "admin" in path:
            return (
                self.config.admin_requests_per_minute,
                self.config.admin_requests_per_hour,
            )
        elif method == "GET":
            return (
                self.config.get_requests_per_minute,
                self.config.get_requests_per_hour,
            )
        else:
            return self.config.requests_per_minute, self.config.requests_per_hour

    def _get_tracking_dicts_for_request(
        self, request: Request
    ) -> Tuple[Dict[str, list[float]], Dict[str, list[float]]]:
        """Get the appropriate tracking dictionaries for the request."""
        path = request.url.path
        method = request.method

        if path.startswith("/api/auth"):
            return self.auth_minute_requests, self.auth_hour_requests
        elif path.startswith("/api/admin") or "admin" in path:
            return self.admin_minute_requests, self.admin_hour_requests
        elif method == "GET":
            return self.get_minute_requests, self.get_hour_requests
        else:
            return self.minute_requests, self.hour_requests

    def is_rate_limited(self, request: Request) -> Tuple[bool, str, Dict[str, int]]:
        """
        Check if the request should be rate limited.
        Returns (is_limited, reason, limits_info).
        """
        key = self._get_rate_limit_key(request)
        current_time = time.time()
        minute_limit, hour_limit = self._get_rate_limits_for_request(request)
        minute_dict, hour_dict = self._get_tracking_dicts_for_request(request)

        # Clean up old requests
        self._cleanup_old_requests(key, 60, minute_dict)
        self._cleanup_old_requests(key, 3600, hour_dict)

        # Check minute limit
        minute_count = len(minute_dict[key])
        if minute_count >= minute_limit:
            return (
                True,
                f"Rate limit exceeded: {minute_count} requests per minute",
                {
                    "minute_limit": minute_limit,
                    "hour_limit": hour_limit,
                    "minute_count": minute_count,
                    "hour_count": len(hour_dict[key]),
                },
            )

        # Check hour limit
        hour_count = len(hour_dict[key])
        if hour_count >= hour_limit:
            return (
                True,
                f"Rate limit exceeded: {hour_count} requests per hour",
                {
                    "minute_limit": minute_limit,
                    "hour_limit": hour_limit,
                    "minute_count": minute_count,
                    "hour_count": hour_count,
                },
            )

        # Add current request to tracking
        minute_dict[key].append(current_time)
        hour_dict[key].append(current_time)

        return (
            False,
            "",
            {
                "minute_limit": minute_limit,
                "hour_limit": hour_limit,
                "minute_count": minute_count + 1,
                "hour_count": hour_count + 1,
            },
        )

    def get_remaining_requests(self, request: Request) -> Dict[str, int]:
        """Get remaining requests for the client."""
        key = self._get_rate_limit_key(request)
        current_time = time.time()
        minute_limit, hour_limit = self._get_rate_limits_for_request(request)
        minute_dict, hour_dict = self._get_tracking_dicts_for_request(request)

        # Clean up old requests
        self._cleanup_old_requests(key, 60, minute_dict)
        self._cleanup_old_requests(key, 3600, hour_dict)

        minute_count = len(minute_dict[key])
        hour_count = len(hour_dict[key])

        return {
            "minute_remaining": max(0, minute_limit - minute_count),
            "hour_remaining": max(0, hour_limit - hour_count),
            "minute_reset": int(60 - (current_time % 60)),
            "hour_reset": int(3600 - (current_time % 3600)),
            "minute_limit": minute_limit,
            "hour_limit": hour_limit,
        }


# Global rate limiter instance with configuration from settings
rate_limiter = SophisticatedRateLimiter(
    RateLimitConfig(
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        requests_per_hour=settings.RATE_LIMIT_REQUESTS_PER_HOUR,
        get_requests_per_minute=getattr(settings, "RATE_LIMIT_GET_REQUESTS_PER_MINUTE", 120),
        get_requests_per_hour=getattr(settings, "RATE_LIMIT_GET_REQUESTS_PER_HOUR", 2000),
        auth_requests_per_minute=getattr(settings, "RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE", 10),
        auth_requests_per_hour=getattr(settings, "RATE_LIMIT_AUTH_REQUESTS_PER_HOUR", 100),
        admin_requests_per_minute=getattr(settings, "RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE", 30),
        admin_requests_per_hour=getattr(settings, "RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR", 300),
    )
)


# Paths that must match exactly to be exempt from rate limiting. These are single
# endpoints, so a prefix test would wrongly exempt unrelated paths. In particular "/"
# is a prefix of every path, so testing it with startswith exempts the entire API.
RATE_LIMIT_EXEMPT_EXACT: Tuple[str, ...] = ("/", "/health", "/ready", "/openapi.json")

# Paths that are exempt along with everything beneath them. The documentation UIs serve
# their own sub-resources (for example /docs/oauth2-redirect), so they match as prefixes.
RATE_LIMIT_EXEMPT_PREFIXES: Tuple[str, ...] = ("/docs", "/redoc")


def is_rate_limit_exempt(path: str) -> bool:
    """Return True when ``path`` is exempt from rate limiting.

    Exemption is deliberately split into two kinds. Entries in
    ``RATE_LIMIT_EXEMPT_EXACT`` are matched exactly, so the root path "/" exempts only
    the root and not every path that begins with it. Entries in
    ``RATE_LIMIT_EXEMPT_PREFIXES`` are matched as prefixes, so the docs UIs also exempt
    the sub-resources they load.
    """
    if path in RATE_LIMIT_EXEMPT_EXACT:
        return True

    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in RATE_LIMIT_EXEMPT_PREFIXES)


async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    FastAPI middleware for sophisticated rate limiting.
    """
    # Skip rate limiting if disabled in settings or in test environment
    if not settings.ENABLE_RATE_LIMITING or os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "false":
        response = await call_next(request)
        return response

    # Skip rate limiting for health checks, readiness, the root, and documentation
    if is_rate_limit_exempt(request.url.path):
        response = await call_next(request)
        return response

    # Check rate limit
    is_limited, reason, limits_info = rate_limiter.is_rate_limited(request)

    if is_limited:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Rate limit exceeded for {client_ip}: {reason}")

        # Determine retry after time based on which limit was hit
        retry_after = 60 if "minute" in reason else 3600

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests",
                "message": reason,
                "retry_after": retry_after,
                "limits": limits_info,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit-Minute": str(limits_info["minute_limit"]),
                "X-RateLimit-Limit-Hour": str(limits_info["hour_limit"]),
                "X-RateLimit-Remaining-Minute": "0",
                "X-RateLimit-Remaining-Hour": str(max(0, limits_info["hour_limit"] - limits_info["hour_count"])),
            },
        )

    # Layer 2: the shared limiter. Layer 1 above is in-memory, so it only sees the
    # traffic that reached this execution environment; the shared counter is what makes
    # a limit hold across environments and, after the split, across the nine functions.
    # It runs only once layer 1 has allowed the request, so a burst that layer 1 already
    # rejected costs no DynamoDB call.
    #
    # Every failure mode inside is swallowed and logged at WARNING, so this call cannot
    # raise into the request path or turn a DynamoDB problem into a 5xx.
    if settings.ENABLE_SHARED_RATE_LIMITING:
        identity = client_identity(request)
        shared_limited, shared_retry_after = shared_rate_limiter.check(identity)
        if shared_limited:
            retry_after = shared_retry_after or 60
            logger.warning("Shared rate limit exceeded for %s", identity)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining-Minute": "0",
                },
            )

    # Add rate limit headers to response
    response = await call_next(request)
    remaining = rate_limiter.get_remaining_requests(request)

    response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["minute_remaining"])
    response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour_remaining"])
    response.headers["X-RateLimit-Reset-Minute"] = str(remaining["minute_reset"])
    response.headers["X-RateLimit-Reset-Hour"] = str(remaining["hour_reset"])
    response.headers["X-RateLimit-Limit-Minute"] = str(remaining["minute_limit"])
    response.headers["X-RateLimit-Limit-Hour"] = str(remaining["hour_limit"])

    return response
