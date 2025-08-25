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


class TestGlobalPartVotes:
    """Test cases for global part votes endpoints."""

    def test_upvote_global_part_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test successfully upvoting a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_downvote_global_part_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test successfully downvoting a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Downvote the part
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "downvote"

    def test_vote_global_part_unauthorized(self, client: TestClient, test_category):
        """Test voting on a global part without authentication."""
        # Try to upvote without authentication
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/1/vote", json=vote_data
        )
        assert response.status_code == 401

    def test_vote_global_part_not_found(self, client: TestClient, test_user):
        """Test voting on a non-existent global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to upvote non-existent part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/99999/vote", json=vote_data
        )
        assert response.status_code == 404

    def test_change_vote_success(self, client: TestClient, test_user, test_category):
        """Test changing a vote from upvote to downvote."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["vote_type"] == "downvote"

    def test_remove_vote_success(self, client: TestClient, test_user, test_category):
        """Test removing a vote."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote"
        )
        assert response.status_code == 200

        # Verify vote is removed by trying to vote again (should create new vote)
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

    def test_remove_vote_unauthorized(
        self, client: TestClient, test_user, test_category
    ):
        """Test removing a vote without proper authorization."""
        # Create a vote as test_user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Clear cookies to simulate different user
        client.cookies.clear()

        # Try to remove vote without authentication
        response = client.delete(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote"
        )
        assert response.status_code == 401

    def test_get_user_vote_success(self, client: TestClient, test_user, test_category):
        """Test getting a user's vote on a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get the user's vote summary
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote-summary"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["part_id"] == global_part["id"]
        assert data["user_vote"] == "upvote"
        assert data["upvotes"] >= 1
        assert data["total_votes"] >= 1

    def test_get_user_vote_not_found(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting a user's vote when they haven't voted."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Get the user's vote summary (should show no vote)
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote-summary"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_vote"] is None
        assert data["upvotes"] == 0
        assert data["downvotes"] == 0
        assert data["total_votes"] == 0

    def test_get_user_vote_unauthorized(self, client: TestClient, test_category):
        """Test getting a user's vote without authentication."""
        # Try to get vote without authentication
        response = client.get(f"{settings.API_STR}/global-part-votes/1/vote-summary")
        assert response.status_code == 401

    def test_get_part_vote_stats_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting vote statistics for a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote statistics
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote-summary"
        )
        assert response.status_code == 200

        data = response.json()
        assert "upvotes" in data
        assert "downvotes" in data
        assert "total_votes" in data
        assert data["upvotes"] >= 1
        assert data["total_votes"] >= 1

    def test_get_part_vote_stats_not_found(self, client: TestClient, test_user):
        """Test getting vote statistics for a non-existent global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        response = client.get(
            f"{settings.API_STR}/global-part-votes/99999/vote-summary"
        )
        assert response.status_code == 404

    def test_vote_on_own_part_success(
        self, client: TestClient, test_user, test_category
    ):
        """Test voting on a part created by the same user."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Vote on own part (should be allowed)
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

    def test_multiple_votes_same_user(
        self, client: TestClient, test_user, test_category
    ):
        """Test that a user can only have one vote per part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # First upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Second upvote (should update existing vote)
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote stats to verify only one vote exists
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote-summary"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_votes"] == 1

    def test_invalid_vote_type(self, client: TestClient, test_user, test_category):
        """Test voting with an invalid vote type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        global_part = response.json()

        # Try to vote with invalid type
        vote_data = {"vote_type": "invalid"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 400

    def test_get_vote_summaries_multiple_parts(
        self, client: TestClient, test_user, test_category
    ):
        """Test getting vote summaries for multiple parts."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create two global parts
        part1_data = {
            "name": get_unique_name("test_part_1"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part1_data)
        assert response.status_code == 200
        global_part1 = response.json()

        part2_data = {
            "name": get_unique_name("test_part_2"),
            "description": "Another test part description",
            "price": 8888,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part2_data)
        assert response.status_code == 200
        global_part2 = response.json()

        # Vote on both parts
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part1['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part2['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote summaries for both parts
        part_ids = f"{global_part1['id']},{global_part2['id']}"
        response = client.get(
            f"{settings.API_STR}/global-part-votes/?part_ids={part_ids}"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2

        # Find the summaries for each part
        part1_summary = next(
            (s for s in data if s["part_id"] == global_part1["id"]), None
        )
        part2_summary = next(
            (s for s in data if s["part_id"] == global_part2["id"]), None
        )

        assert part1_summary is not None
        assert part2_summary is not None
        assert part1_summary["user_vote"] == "upvote"
        assert part2_summary["user_vote"] == "downvote"

    def test_get_vote_summaries_invalid_format(self, client: TestClient, test_user):
        """Test getting vote summaries with invalid part IDs format."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try with invalid format
        response = client.get(f"{settings.API_STR}/global-part-votes/?part_ids=invalid")
        assert response.status_code == 400

    def test_get_vote_summaries_empty(self, client: TestClient, test_user):
        """Test getting vote summaries with empty part IDs."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try with empty part IDs
        response = client.get(f"{settings.API_STR}/global-part-votes/?part_ids=")
        assert response.status_code == 400

    def test_get_vote_summaries_unauthorized(self, client: TestClient):
        """Test getting vote summaries without authentication."""
        response = client.get(f"{settings.API_STR}/global-part-votes/?part_ids=1,2,3")
        assert response.status_code == 401
