import os
from typing import Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models.user import User
from app.api.models.category import Category


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestCarVotes:
    """Test cases for car votes endpoints."""

    def test_upvote_car_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully upvoting a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Honda"),
            "model": "Civic",
            "year": 2022,
            "trim": "Sport",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Upvote the car
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["car_id"] == car["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_downvote_car_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully downvoting a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Toyota"),
            "model": "Corolla",
            "year": 2021,
            "trim": "LE",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Downvote the car
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["car_id"] == car["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "downvote"

    def test_vote_car_unauthorized(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test voting on a car without authentication."""
        # Try to upvote without authentication
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/car-votes/1/vote", json=vote_data)
        assert response.status_code == 401

    def test_vote_car_not_found(self, client: TestClient, test_user: User) -> None:
        """Test voting on a car that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to vote on non-existent car
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/99999/vote", json=vote_data
        )
        assert response.status_code == 404

    def test_update_existing_vote(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test updating an existing vote on a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Ford"),
            "model": "Mustang",
            "year": 2023,
            "trim": "GT",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # First upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200
        first_vote = response.json()
        assert first_vote["vote_type"] == "upvote"

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200
        updated_vote = response.json()
        assert updated_vote["id"] == first_vote["id"]
        assert updated_vote["vote_type"] == "downvote"

    def test_remove_vote_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully removing a vote on a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Chevrolet"),
            "model": "Camaro",
            "year": 2022,
            "trim": "SS",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(f"{settings.API_STR}/car-votes/{car['id']}/vote")
        assert response.status_code == 200
        assert response.json()["message"] == "Vote removed successfully"

    def test_remove_vote_not_found(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test removing a vote that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("BMW"),
            "model": "3 Series",
            "year": 2021,
            "trim": "330i",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Try to remove non-existent vote
        response = client.delete(f"{settings.API_STR}/car-votes/{car['id']}/vote")
        assert response.status_code == 404

    def test_get_vote_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting a user's vote on a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Audi"),
            "model": "A4",
            "year": 2023,
            "trim": "Premium",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get the vote
        response = client.get(f"{settings.API_STR}/car-votes/{car['id']}/vote")
        assert response.status_code == 200
        vote = response.json()
        assert vote["car_id"] == car["id"]
        assert vote["user_id"] == test_user.id
        assert vote["vote_type"] == "upvote"

    def test_get_vote_not_found(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test getting a vote that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Mercedes"),
            "model": "C-Class",
            "year": 2022,
            "trim": "AMG",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Try to get non-existent vote
        response = client.get(f"{settings.API_STR}/car-votes/{car['id']}/vote")
        assert response.status_code == 404

    def test_get_vote_stats_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting vote statistics for a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Volkswagen"),
            "model": "Golf",
            "year": 2021,
            "trim": "GTI",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create an upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote stats
        response = client.get(f"{settings.API_STR}/car-votes/{car['id']}/vote-stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["car_id"] == car["id"]
        assert stats["upvotes"] == 1
        assert stats["downvotes"] == 0
        assert stats["total_votes"] == 1
        assert stats["vote_score"] == 1
        assert stats["user_vote"] == "upvote"

    def test_get_vote_summaries_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting vote summaries for multiple cars."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create two cars
        car1_data = {
            "make": get_unique_name("Porsche"),
            "model": "911",
            "year": 2023,
            "trim": "Carrera",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car1_data)
        assert response.status_code == 200
        car1 = response.json()

        car2_data = {
            "make": get_unique_name("Ferrari"),
            "model": "F8",
            "year": 2022,
            "trim": "Tributo",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car2_data)
        assert response.status_code == 200
        car2 = response.json()

        # Vote on both cars
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car1['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/car-votes/{car2['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote summaries
        car_ids = f"{car1['id']},{car2['id']}"
        response = client.get(f"{settings.API_STR}/car-votes/?car_ids={car_ids}")
        assert response.status_code == 200
        summaries = response.json()
        assert len(summaries) == 2

        # Check first car summary
        car1_summary = next(s for s in summaries if s["car_id"] == car1["id"])
        assert car1_summary["upvotes"] == 1
        assert car1_summary["downvotes"] == 0
        assert car1_summary["vote_score"] == 1
        assert car1_summary["user_vote"] == "upvote"

        # Check second car summary
        car2_summary = next(s for s in summaries if s["car_id"] == car2["id"])
        assert car2_summary["upvotes"] == 0
        assert car2_summary["downvotes"] == 1
        assert car2_summary["vote_score"] == -1
        assert car2_summary["user_vote"] == "downvote"

    def test_get_vote_summaries_invalid_format(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote summaries with invalid car IDs format."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get summaries with invalid format
        response = client.get(f"{settings.API_STR}/car-votes/?car_ids=invalid")
        assert response.status_code == 400

    def test_get_vote_summaries_empty(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote summaries with empty car IDs."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get summaries with empty IDs
        response = client.get(f"{settings.API_STR}/car-votes/?car_ids=")
        assert response.status_code == 400

    def test_get_flagged_cars_admin_only(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that getting flagged cars requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get flagged cars
        response = client.get(f"{settings.API_STR}/car-votes/flagged-cars")
        assert response.status_code == 403

    def test_get_flagged_cars_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully getting flagged cars as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get flagged cars
        response = client.get(f"{settings.API_STR}/car-votes/flagged-cars")
        assert response.status_code == 200
        # Should return empty list if no cars meet flagging criteria
        assert isinstance(response.json(), list)
