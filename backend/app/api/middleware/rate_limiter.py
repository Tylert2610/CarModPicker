"""
Sophisticated rate limiting middleware for FastAPI application.
Provides different rate limits for GET vs other methods and endpoint-specific limits.
"""

import logging
import os
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, Tuple, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ...core.config import settings

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
        self.minute_requests: Dict[str, list] = defaultdict(list)
        self.hour_requests: Dict[str, list] = defaultdict(list)
        self.get_minute_requests: Dict[str, list] = defaultdict(list)
        self.get_hour_requests: Dict[str, list] = defaultdict(list)
        self.auth_minute_requests: Dict[str, list] = defaultdict(list)
        self.auth_hour_requests: Dict[str, list] = defaultdict(list)
        self.admin_minute_requests: Dict[str, list] = defaultdict(list)
        self.admin_hour_requests: Dict[str, list] = defaultdict(list)

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

    def _cleanup_old_requests(
        self, key: str, window_seconds: int, requests_dict: Dict[str, list]
    ) -> None:
        """Remove old requests outside the time window."""
        current_time = time.time()
        requests_dict[key] = [
            req_time
            for req_time in requests_dict[key]
            if current_time - req_time < window_seconds
        ]

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
    ) -> Tuple[Dict[str, list], Dict[str, list]]:
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
        get_requests_per_minute=getattr(
            settings, "RATE_LIMIT_GET_REQUESTS_PER_MINUTE", 120
        ),
        get_requests_per_hour=getattr(
            settings, "RATE_LIMIT_GET_REQUESTS_PER_HOUR", 2000
        ),
        auth_requests_per_minute=getattr(
            settings, "RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE", 10
        ),
        auth_requests_per_hour=getattr(
            settings, "RATE_LIMIT_AUTH_REQUESTS_PER_HOUR", 100
        ),
        admin_requests_per_minute=getattr(
            settings, "RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE", 30
        ),
        admin_requests_per_hour=getattr(
            settings, "RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR", 300
        ),
    )
)


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    FastAPI middleware for sophisticated rate limiting.
    """
    # Skip rate limiting if disabled in settings or in test environment
    if (
        not settings.ENABLE_RATE_LIMITING
        or os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "false"
    ):
        response = await call_next(request)
        return response

    # Skip rate limiting for health checks, static files, and documentation
    skip_paths = ["/", "/health", "/docs", "/openapi.json", "/redoc"]
    if any(request.url.path.startswith(path) for path in skip_paths):
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
                "X-RateLimit-Remaining-Hour": str(
                    max(0, limits_info["hour_limit"] - limits_info["hour_count"])
                ),
            },
        )

    # Add rate limit headers to response
    response = await call_next(request)
    remaining = rate_limiter.get_remaining_requests(request)

    response.headers["X-RateLimit-Remaining-Minute"] = str(
        remaining["minute_remaining"]
    )
    response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour_remaining"])
    response.headers["X-RateLimit-Reset-Minute"] = str(remaining["minute_reset"])
    response.headers["X-RateLimit-Reset-Hour"] = str(remaining["hour_reset"])
    response.headers["X-RateLimit-Limit-Minute"] = str(remaining["minute_limit"])
    response.headers["X-RateLimit-Limit-Hour"] = str(remaining["hour_limit"])

    return response
