import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestSubscriptions:
    """Test cases for subscriptions endpoints."""

    def test_get_subscription_status(self, client: TestClient, test_user):
        """Test retrieving subscription status for the current user."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200

        data = response.json()
        assert "tier" in data
        assert "status" in data
        assert "limits" in data
        assert "usage" in data

    def test_get_subscription_status_unauthorized(self, client: TestClient):
        """Test retrieving subscription status without authentication."""
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 401

    def test_upgrade_subscription_success(self, client: TestClient, test_user):
        """Test successfully upgrading to premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 200

        data = response.json()
        assert "user_id" in data
        assert "tier" in data
        assert "status" in data

    def test_upgrade_subscription_unauthorized(self, client: TestClient):
        """Test upgrading subscription without authentication."""
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 401

    def test_upgrade_subscription_invalid_tier(self, client: TestClient, test_user):
        """Test upgrading to an invalid subscription tier."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to upgrade to invalid tier
        upgrade_data = {
            "tier": "invalid_tier",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 400

    def test_upgrade_subscription_already_premium(self, client: TestClient, test_user):
        """Test upgrading when user already has premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # First upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 200

        # Try to upgrade again
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 400

    def test_cancel_subscription_success(self, client: TestClient, test_user):
        """Test successfully canceling premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # First upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 200

        # Cancel subscription
        response = client.post(f"{settings.API_STR}/subscriptions/cancel")
        assert response.status_code == 200

        data = response.json()
        assert "user_id" in data
        assert "tier" in data
        assert "status" in data

    def test_cancel_subscription_unauthorized(self, client: TestClient):
        """Test canceling subscription without authentication."""
        response = client.post(f"{settings.API_STR}/subscriptions/cancel")
        assert response.status_code == 401

    def test_cancel_subscription_not_premium(self, client: TestClient, test_user):
        """Test canceling subscription when user doesn't have premium."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to cancel without having premium
        response = client.post(f"{settings.API_STR}/subscriptions/cancel")
        assert response.status_code == 400

    def test_subscription_limits_and_usage(self, client: TestClient, test_user):
        """Test that subscription status includes limits and usage information."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200

        data = response.json()

        # Check limits structure
        assert "limits" in data
        limits = data["limits"]
        assert "build_lists" in limits
        assert "cars" in limits
        assert isinstance(limits["build_lists"], (int, type(None)))
        assert isinstance(limits["cars"], (int, type(None)))

        # Check usage structure
        assert "usage" in data
        usage = data["usage"]
        assert "build_lists" in usage
        assert "cars" in usage
        assert isinstance(usage["build_lists"], int)
        assert isinstance(usage["cars"], int)

    def test_subscription_tier_transitions(self, client: TestClient, test_user):
        """Test subscription tier transitions (free -> premium -> canceled)."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Check initial status (should be free)
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200
        initial_data = response.json()
        assert initial_data["tier"] == "free"

        # Upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(
            f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data
        )
        assert response.status_code == 200

        # Check premium status
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200
        premium_data = response.json()
        assert premium_data["tier"] == "premium"
        assert premium_data["status"] == "active"

        # Cancel subscription
        response = client.post(f"{settings.API_STR}/subscriptions/cancel")
        assert response.status_code == 200

        # Check canceled status
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200
        canceled_data = response.json()
        assert canceled_data["tier"] == "premium"
        assert canceled_data["status"] == "cancelled"

    def test_subscription_service_integration(self, client: TestClient, test_user):
        """Test that subscription service properly integrates with user limits."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get initial subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200
        initial_data = response.json()
        initial_usage = initial_data["usage"]["build_lists"]

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a build list (should increment usage)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "Test build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200

        # Check that usage increased
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 200
        updated_data = response.json()
        updated_usage = updated_data["usage"]["build_lists"]
        assert updated_usage == initial_usage + 1
