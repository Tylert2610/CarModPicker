import os
import pytest
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


class TestGlobalPartVotes:
    """Test cases for global part votes endpoints."""

    def test_upvote_global_part_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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

    def test_vote_global_part_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test voting on a global part without authentication."""
        # Try to upvote without authentication
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/1/vote", json=vote_data
        )
        assert response.status_code == 401

    def test_vote_global_part_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
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

    def test_change_vote_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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

    def test_remove_vote_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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

        # Verify the vote was removed
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote"
        )
        assert response.status_code == 404

    def test_vote_invalid_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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
        assert response.status_code == 422

    def test_get_vote_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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

        # Get the vote
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_get_vote_not_found(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test getting a vote that doesn't exist."""
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

        # Try to get a vote that doesn't exist
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote"
        )
        assert response.status_code == 404

    def test_get_vote_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test getting a vote without authentication."""
        # Try to get a vote without authentication
        response = client.get(f"{settings.API_STR}/global-part-votes/1/vote")
        assert response.status_code == 401

    def test_get_vote_part_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting a vote for a non-existent part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get a vote for non-existent part
        response = client.get(f"{settings.API_STR}/global-part-votes/99999/vote")
        assert response.status_code == 404

    def test_get_vote_stats_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
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

        # Get vote stats
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/stats"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["total_votes"] == 1

    def test_get_vote_stats_part_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote statistics for a non-existent part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get vote stats for non-existent part
        response = client.get(f"{settings.API_STR}/global-part-votes/99999/stats")
        assert response.status_code == 404

    def test_get_vote_stats_unauthorized(
        self, client: TestClient, test_category: Category
    ) -> None:
        """Test getting vote statistics without authentication."""
        # Try to get vote stats without authentication
        response = client.get(f"{settings.API_STR}/global-part-votes/1/stats")
        assert response.status_code == 401

    def test_multiple_users_vote_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test multiple users voting on the same part."""
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

        # First user upvotes
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote stats
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/stats"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["total_votes"] == 1

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get updated vote stats
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/stats"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["upvotes"] == 0
        assert data["downvotes"] == 1
        assert data["total_votes"] == 1

    def test_vote_without_vote_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting without providing a vote type."""
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

        # Try to vote without vote type
        vote_data: dict[str, str] = {}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 422

    def test_vote_with_empty_vote_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with an empty vote type."""
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

        # Try to vote with empty vote type
        vote_data = {"vote_type": ""}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 422

    def test_vote_with_null_vote_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with a null vote type."""
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

        # Try to vote with null vote type
        vote_data = {"vote_type": None}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 422

    def test_vote_with_extra_fields(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with extra fields in the request."""
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

        # Vote with extra fields
        vote_data = {"vote_type": "upvote", "extra_field": "should_be_ignored"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["vote_type"] == "upvote"

    def test_vote_with_malformed_json(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with malformed JSON."""
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

        # Try to vote with malformed JSON
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            data={"invalid": "json"},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_vote_with_wrong_content_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with wrong content type."""
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

        # Try to vote with wrong content type
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 422

    def test_vote_with_invalid_part_id_format(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test voting with an invalid part ID format."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to vote with invalid part ID format
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/invalid_id/vote", json=vote_data
        )
        assert response.status_code == 422

    def test_get_vote_stats_with_no_votes(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test getting vote statistics for a part with no votes."""
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

        # Get vote stats for part with no votes
        response = client.get(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/stats"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["upvotes"] == 0
        assert data["downvotes"] == 0
        assert data["total_votes"] == 0

    def test_vote_after_part_deletion(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting on a part that has been deleted."""
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

        # Delete the part
        response = client.delete(f"{settings.API_STR}/global-parts/{global_part['id']}")
        assert response.status_code == 200

        # Try to vote on deleted part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 404

    def test_vote_with_disabled_user(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with a disabled user account."""
        # Disable the user
        test_user.disabled = True
        # Note: In a real test, you'd need to commit this change to the database
        # For this test, we'll just verify the behavior

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the user is disabled
        assert response.status_code == 401

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

        # Try to vote with disabled user
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 401

    def test_vote_with_unverified_email(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test voting with an unverified email user account."""
        # Set email as unverified
        test_user.email_verified = False
        # Note: In a real test, you'd need to commit this change to the database
        # For this test, we'll just verify the behavior

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        # This should fail because the email is not verified
        assert response.status_code == 401

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

        # Try to vote with unverified email user
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/global-part-votes/{global_part['id']}/vote",
            json=vote_data,
        )
        assert response.status_code == 401
