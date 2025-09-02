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


class TestBuildListVotes:
    """Test cases for build list votes endpoints."""

    def test_upvote_build_list_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully upvoting a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Upvote the build list
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_downvote_build_list_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully downvoting a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Another Build List"),
            "description": "Another test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Downvote the build list
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "downvote"

    def test_vote_build_list_unauthorized(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test voting on a build list without authentication."""
        # Try to upvote without authentication
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/1/vote", json=vote_data
        )
        assert response.status_code == 401

    def test_vote_build_list_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test voting on a build list that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to vote on non-existent build list
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/99999/vote", json=vote_data
        )
        assert response.status_code == 404

    def test_update_existing_vote(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test updating an existing vote on a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Update Test Build List"),
            "description": "A build list for testing vote updates",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # First upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200
        first_vote = response.json()
        assert first_vote["vote_type"] == "upvote"

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200
        updated_vote = response.json()
        assert updated_vote["id"] == first_vote["id"]
        assert updated_vote["vote_type"] == "downvote"

    def test_remove_vote_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully removing a vote on a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Remove Vote Test Build List"),
            "description": "A build list for testing vote removal",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote"
        )
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

        # Create a build list
        build_list_data = {
            "name": get_unique_name("No Vote Test Build List"),
            "description": "A build list with no votes",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Try to remove non-existent vote
        response = client.delete(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote"
        )
        assert response.status_code == 404

    def test_get_vote_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting a user's vote on a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Get Vote Test Build List"),
            "description": "A build list for testing vote retrieval",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get the vote
        response = client.get(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote"
        )
        assert response.status_code == 200
        vote = response.json()
        assert vote["build_list_id"] == build_list["id"]
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

        # Create a build list
        build_list_data = {
            "name": get_unique_name("No Vote Test Build List 2"),
            "description": "Another build list with no votes",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Try to get non-existent vote
        response = client.get(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote"
        )
        assert response.status_code == 404

    def test_get_vote_stats_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting vote statistics for a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Stats Test Build List"),
            "description": "A build list for testing vote statistics",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Create an upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote stats
        response = client.get(
            f"{settings.API_STR}/build-list-votes/{build_list['id']}/vote-stats"
        )
        assert response.status_code == 200
        stats = response.json()
        assert stats["build_list_id"] == build_list["id"]
        assert stats["upvotes"] == 1
        assert stats["downvotes"] == 0
        assert stats["total_votes"] == 1
        assert stats["vote_score"] == 1
        assert stats["user_vote"] == "upvote"

    def test_get_vote_summaries_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting vote summaries for multiple build lists."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create two build lists
        build_list1_data = {
            "name": get_unique_name("Summary Test Build List 1"),
            "description": "First build list for testing vote summaries",
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list1_data
        )
        assert response.status_code == 200
        build_list1 = response.json()

        build_list2_data = {
            "name": get_unique_name("Summary Test Build List 2"),
            "description": "Second build list for testing vote summaries",
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list2_data
        )
        assert response.status_code == 200
        build_list2 = response.json()

        # Vote on both build lists
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list1['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/build-list-votes/{build_list2['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote summaries
        build_list_ids = f"{build_list1['id']},{build_list2['id']}"
        response = client.get(
            f"{settings.API_STR}/build-list-votes/?build_list_ids={build_list_ids}"
        )
        assert response.status_code == 200
        summaries = response.json()
        assert len(summaries) == 2

        # Check first build list summary
        build_list1_summary = next(
            s for s in summaries if s["build_list_id"] == build_list1["id"]
        )
        assert build_list1_summary["upvotes"] == 1
        assert build_list1_summary["downvotes"] == 0
        assert build_list1_summary["vote_score"] == 1
        assert build_list1_summary["user_vote"] == "upvote"

        # Check second build list summary
        build_list2_summary = next(
            s for s in summaries if s["build_list_id"] == build_list2["id"]
        )
        assert build_list2_summary["upvotes"] == 0
        assert build_list2_summary["downvotes"] == 1
        assert build_list2_summary["vote_score"] == -1
        assert build_list2_summary["user_vote"] == "downvote"

    def test_get_vote_summaries_invalid_format(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote summaries with invalid build list IDs format."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get summaries with invalid format
        response = client.get(
            f"{settings.API_STR}/build-list-votes/?build_list_ids=invalid"
        )
        assert response.status_code == 400

    def test_get_vote_summaries_empty(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote summaries with empty build list IDs."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get summaries with empty IDs
        response = client.get(f"{settings.API_STR}/build-list-votes/?build_list_ids=")
        assert response.status_code == 400

    def test_get_flagged_build_lists_admin_only(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that getting flagged build lists requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get flagged build lists
        response = client.get(
            f"{settings.API_STR}/build-list-votes/flagged-build-lists"
        )
        assert response.status_code == 403

    def test_get_flagged_build_lists_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully getting flagged build lists as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get flagged build lists
        response = client.get(
            f"{settings.API_STR}/build-list-votes/flagged-build-lists"
        )
        assert response.status_code == 200
        # Should return empty list if no build lists meet flagging criteria
        assert isinstance(response.json(), list)
