"""
Rate limiting middleware for FastAPI application.
Provides basic rate limiting to prevent abuse for small web applications.
"""

import logging
import os
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, Tuple

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ...core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter for small applications.
    For production use, consider using Redis or a dedicated rate limiting service.
    """

    def __init__(
        self,
        requests_per_minute: int | None = None,
        requests_per_hour: int | None = None,
    ) -> None:
        self.requests_per_minute = (
            requests_per_minute or settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        )
        self.requests_per_hour = (
            requests_per_hour or settings.RATE_LIMIT_REQUESTS_PER_HOUR
        )
        self.minute_requests: Dict[str, list] = defaultdict(list)
        self.hour_requests: Dict[str, list] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxy headers."""
        # Check for forwarded headers first (for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct connection
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, client_ip: str) -> None:
        """Remove old requests outside the time windows."""
        current_time = time.time()

        # Clean up minute requests (older than 60 seconds)
        self.minute_requests[client_ip] = [
            req_time
            for req_time in self.minute_requests[client_ip]
            if current_time - req_time < 60
        ]

        # Clean up hour requests (older than 3600 seconds)
        self.hour_requests[client_ip] = [
            req_time
            for req_time in self.hour_requests[client_ip]
            if current_time - req_time < 3600
        ]

    def is_rate_limited(self, request: Request) -> Tuple[bool, str]:
        """
        Check if the request should be rate limited.
        Returns (is_limited, reason).
        """
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Clean up old requests
        self._cleanup_old_requests(client_ip)

        # Check minute limit
        minute_count = len(self.minute_requests[client_ip])
        if minute_count >= self.requests_per_minute:
            return True, f"Rate limit exceeded: {minute_count} requests per minute"

        # Check hour limit
        hour_count = len(self.hour_requests[client_ip])
        if hour_count >= self.requests_per_hour:
            return True, f"Rate limit exceeded: {hour_count} requests per hour"

        # Add current request to tracking
        self.minute_requests[client_ip].append(current_time)
        self.hour_requests[client_ip].append(current_time)

        return False, ""

    def get_remaining_requests(self, request: Request) -> Dict[str, int]:
        """Get remaining requests for the client."""
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Clean up old requests
        self._cleanup_old_requests(client_ip)

        minute_count = len(self.minute_requests[client_ip])
        hour_count = len(self.hour_requests[client_ip])

        return {
            "minute_remaining": max(0, self.requests_per_minute - minute_count),
            "hour_remaining": max(0, self.requests_per_hour - hour_count),
            "minute_reset": int(60 - (current_time % 60)),
            "hour_reset": int(3600 - (current_time % 3600)),
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    FastAPI middleware for rate limiting.
    """
    # Skip rate limiting if disabled in settings or in test environment
    if (
        not settings.ENABLE_RATE_LIMITING
        or os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "false"
    ):
        response = await call_next(request)
        return response

    # Skip rate limiting for health checks and static files
    if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
        response = await call_next(request)
        return response

    # Check rate limit
    is_limited, reason = rate_limiter.is_rate_limited(request)

    if is_limited:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Rate limit exceeded for {client_ip}: {reason}")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests",
                "message": reason,
                "retry_after": 60,
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit-Minute": str(rate_limiter.requests_per_minute),
                "X-RateLimit-Limit-Hour": str(rate_limiter.requests_per_hour),
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

    return response
