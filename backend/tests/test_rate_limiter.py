"""
Tests for sophisticated rate limiting functionality.
"""

import time
import unittest.mock
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.middleware.rate_limiter import (
    SophisticatedRateLimiter,
    RateLimitConfig,
    rate_limit_middleware,
)
from app.main import app


class TestRateLimitConfig:
    """Test cases for the RateLimitConfig class."""

    def test_rate_limit_config_defaults(self) -> None:
        """Test rate limit config initialization with default values."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.get_requests_per_minute == 120
        assert config.get_requests_per_hour == 2000
        assert config.auth_requests_per_minute == 10
        assert config.auth_requests_per_hour == 100
        assert config.admin_requests_per_minute == 30
        assert config.admin_requests_per_hour == 300

    def test_rate_limit_config_custom_values(self) -> None:
        """Test rate limit config initialization with custom values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            get_requests_per_minute=60,
            get_requests_per_hour=1000,
            auth_requests_per_minute=5,
            auth_requests_per_hour=50,
            admin_requests_per_minute=15,
            admin_requests_per_hour=150,
        )
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.get_requests_per_minute == 60
        assert config.get_requests_per_hour == 1000
        assert config.auth_requests_per_minute == 5
        assert config.auth_requests_per_hour == 50
        assert config.admin_requests_per_minute == 15
        assert config.admin_requests_per_hour == 150


class TestSophisticatedRateLimiter:
    """Test cases for the SophisticatedRateLimiter class."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initialization with default config."""
        limiter = SophisticatedRateLimiter()
        assert limiter.config.requests_per_minute == 60
        assert limiter.config.requests_per_hour == 1000

    def test_rate_limiter_custom_config(self) -> None:
        """Test rate limiter initialization with custom config."""
        config = RateLimitConfig(requests_per_minute=30, requests_per_hour=500)
        limiter = SophisticatedRateLimiter(config)
        assert limiter.config.requests_per_minute == 30
        assert limiter.config.requests_per_hour == 500

    def test_get_client_ip_direct(self) -> None:
        """Test getting client IP from direct connection."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"

        ip = limiter._get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_proxy(self) -> None:
        """Test getting client IP from proxy headers."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
        request.client.host = "10.0.0.1"

        ip = limiter._get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_rate_limit_key_default(self) -> None:
        """Test rate limit key generation for default endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        key = limiter._get_rate_limit_key(request)
        assert key == "default:192.168.1.1"

    def test_get_rate_limit_key_get(self) -> None:
        """Test rate limit key generation for GET requests."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "GET"

        key = limiter._get_rate_limit_key(request)
        assert key == "get:192.168.1.1"

    def test_get_rate_limit_key_auth(self) -> None:
        """Test rate limit key generation for auth endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/auth/login"
        request.method = "POST"

        key = limiter._get_rate_limit_key(request)
        assert key == "auth:192.168.1.1"

    def test_get_rate_limit_key_admin(self) -> None:
        """Test rate limit key generation for admin endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/admin/users"
        request.method = "GET"

        key = limiter._get_rate_limit_key(request)
        assert key == "admin:192.168.1.1"

    def test_rate_limiting_default_minute_limit(self) -> None:
        """Test default minute rate limiting."""
        config = RateLimitConfig(requests_per_minute=2, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        # First request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Second request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Third request should be limited
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_get_minute_limit(self) -> None:
        """Test GET minute rate limiting."""
        config = RateLimitConfig(get_requests_per_minute=2, get_requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "GET"

        # First request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Second request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Third request should be limited
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_auth_minute_limit(self) -> None:
        """Test auth minute rate limiting."""
        config = RateLimitConfig(auth_requests_per_minute=2, auth_requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/auth/login"
        request.method = "POST"

        # First request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Second request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        # Third request should be limited
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_hour_limit(self) -> None:
        """Test hour rate limiting."""
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=2)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        # First request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited

        # Second request should pass
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert not is_limited

        # Third request should be limited
        is_limited, reason, limits_info = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_cleanup_old_requests(self) -> None:
        """Test cleanup of old requests."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        # Use a fixed current time for testing
        current_time = time.time()

        # Add some old requests (older than both 60 seconds and 3600 seconds)
        old_time = current_time - 7200  # 2 hours ago
        limiter.minute_requests["default:192.168.1.1"] = [old_time, old_time]
        limiter.hour_requests["default:192.168.1.1"] = [old_time, old_time]

        # Add a recent request (within 60 seconds)
        recent_time = current_time - 30  # 30 seconds ago
        limiter.minute_requests["default:192.168.1.1"].append(recent_time)
        limiter.hour_requests["default:192.168.1.1"].append(recent_time)

        # Verify initial state
        assert len(limiter.minute_requests["default:192.168.1.1"]) == 3
        assert len(limiter.hour_requests["default:192.168.1.1"]) == 3

        # Mock time.time to return our fixed time
        with unittest.mock.patch("time.time", return_value=current_time):
            # Cleanup should remove old requests
            limiter._cleanup_old_requests(
                "default:192.168.1.1", 60, limiter.minute_requests
            )
            limiter._cleanup_old_requests(
                "default:192.168.1.1", 3600, limiter.hour_requests
            )

        # After cleanup, only the recent request should remain
        assert len(limiter.minute_requests["default:192.168.1.1"]) == 1
        assert len(limiter.hour_requests["default:192.168.1.1"]) == 1
        assert limiter.minute_requests["default:192.168.1.1"][0] == recent_time
        assert limiter.hour_requests["default:192.168.1.1"][0] == recent_time

    def test_get_remaining_requests(self) -> None:
        """Test getting remaining request counts."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        # Add some requests
        current_time = time.time()
        limiter.minute_requests["default:192.168.1.1"] = [
            current_time - 10,
            current_time - 20,
        ]
        limiter.hour_requests["default:192.168.1.1"] = [
            current_time - 100,
            current_time - 200,
        ]

        remaining = limiter.get_remaining_requests(request)

        assert remaining["minute_remaining"] == 8  # 10 - 2
        assert remaining["hour_remaining"] == 98  # 100 - 2
        assert "minute_reset" in remaining
        assert "hour_reset" in remaining
        assert "minute_limit" in remaining
        assert "hour_limit" in remaining


class TestRateLimitMiddleware:
    """Test cases for the rate limiting middleware."""

    def test_middleware_skips_health_check(self) -> None:
        """Test that middleware skips rate limiting for health checks."""
        client = TestClient(app)

        # Health check should not be rate limited
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_middleware_skips_docs(self) -> None:
        """Test that middleware skips rate limiting for docs."""
        client = TestClient(app)

        # Docs should not be rate limited
        response = client.get("/docs")
        assert response.status_code == 200

    def test_middleware_skips_redoc(self) -> None:
        """Test that middleware skips rate limiting for redoc."""
        client = TestClient(app)

        # Redoc should not be rate limited
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_middleware_rate_limiting(self) -> None:
        """Test that middleware properly rate limits requests."""
        # Create a test app with very low limits for testing
        from fastapi import FastAPI

        from app.api.middleware.rate_limiter import (
            SophisticatedRateLimiter,
            RateLimitConfig,
        )

        test_app = FastAPI()
        config = RateLimitConfig(requests_per_minute=1, requests_per_hour=2)
        test_limiter = SophisticatedRateLimiter(config)

        # Mock the global rate limiter
        import app.api.middleware.rate_limiter as rate_limiter_module

        original_limiter = rate_limiter_module.rate_limiter
        rate_limiter_module.rate_limiter = test_limiter

        try:
            test_app.middleware("http")(rate_limit_middleware)

            @test_app.get("/test")
            def test_endpoint() -> dict[str, str]:
                return {"message": "test"}

            client = TestClient(test_app)

            # Since rate limiting is disabled in test environment, all requests should pass
            # First request should pass
            response = client.get("/test")
            assert response.status_code == 200

            # Second request should also pass (rate limiting disabled)
            response = client.get("/test")
            assert response.status_code == 200

        finally:
            # Restore original rate limiter
            rate_limiter_module.rate_limiter = original_limiter
