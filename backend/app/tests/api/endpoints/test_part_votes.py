import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.part import Part
from app.api.models.user import User
from app.api.models.category import Category
from app.core.config import settings
from app.tests.conftest import get_default_category_id


# Helper function to create a user and log them in
def create_and_login_user(client: TestClient, username_suffix: str) -> int:
    username = f"vote_test_user_{username_suffix}"
    email = f"vote_test_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
    elif response.status_code == 400 and "already registered" in response.json().get(
        "detail", ""
    ):
        pass
    else:
        response.raise_for_status()

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    if user_id == -1:
        me_response = client.get(f"{settings.API_STR}/users/me")
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(
                f"Could not retrieve user_id for existing user {username} via /users/me."
            )

    if user_id == -1:
        raise Exception(f"User ID for {username} could not be determined.")
    return user_id


class TestPartVotes:
    def test_vote_on_part_success(self, client: TestClient, db_session: Session):
        """Test successful voting on a part."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_success")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Vote on the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)

        assert response.status_code == 200
        data = response.json()
        assert data["vote_type"] == "upvote"
        assert data["part_id"] == part.id
        assert data["user_id"] == user_id

    def test_vote_on_part_invalid_type(self, client: TestClient, db_session: Session):
        """Test voting with invalid vote type."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_invalid")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Try to vote with invalid type
        vote_data = {"vote_type": "invalid"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)

        assert response.status_code == 400
        assert "Vote type must be 'upvote' or 'downvote'" in response.json()["detail"]

    def test_vote_on_nonexistent_part(self, client: TestClient):
        """Test voting on a part that doesn't exist."""
        # Create and login user
        create_and_login_user(client, "vote_nonexistent")

        # Try to vote on nonexistent part
        vote_data = {"vote_type": "upvote"}
        response = client.post("/api/part-votes/999/vote", json=vote_data)

        assert response.status_code == 404
        assert "Part not found" in response.json()["detail"]

    def test_update_existing_vote(self, client: TestClient, db_session: Session):
        """Test updating an existing vote."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_update")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # First vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)
        assert response.status_code == 200

        # Update vote
        vote_data = {"vote_type": "downvote"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)

        assert response.status_code == 200
        data = response.json()
        assert data["vote_type"] == "downvote"

    def test_remove_vote(self, client: TestClient, db_session: Session):
        """Test removing a vote."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_remove")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(f"/api/part-votes/{part.id}/vote")

        assert response.status_code == 200
        assert "Vote removed successfully" in response.json()["message"]

    def test_remove_nonexistent_vote(self, client: TestClient, db_session: Session):
        """Test removing a vote that doesn't exist."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_remove_nonexistent")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Try to remove vote that doesn't exist
        response = client.delete(f"/api/part-votes/{part.id}/vote")

        assert response.status_code == 404
        assert "No vote found for this part" in response.json()["detail"]

    def test_get_vote_summary(self, client: TestClient, db_session: Session):
        """Test getting vote summary for a part."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_summary")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Create some votes
        vote_data = {"vote_type": "upvote"}
        client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)

        # Get vote summary
        response = client.get(f"/api/part-votes/{part.id}/vote-summary")

        assert response.status_code == 200
        data = response.json()
        assert data["part_id"] == part.id
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["total_votes"] == 1
        assert data["user_vote"] == "upvote"

    def test_get_vote_summaries_multiple_parts(
        self, client: TestClient, db_session: Session
    ):
        """Test getting vote summaries for multiple parts."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_summaries")

        # Get category
        category_id = get_default_category_id(db_session)

        # Create test parts
        part1 = Part(
            name="Test Part 1",
            description="Test Description 1",
            category_id=category_id,
            user_id=user_id,
        )
        part2 = Part(
            name="Test Part 2",
            description="Test Description 2",
            category_id=category_id,
            user_id=user_id,
        )
        db_session.add_all([part1, part2])
        db_session.commit()

        # Create votes
        client.post(f"/api/part-votes/{part1.id}/vote", json={"vote_type": "upvote"})
        client.post(f"/api/part-votes/{part2.id}/vote", json={"vote_type": "downvote"})

        # Get vote summaries
        response = client.get(f"/api/part-votes/?part_ids={part1.id},{part2.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check first part
        part1_summary = next(item for item in data if item["part_id"] == part1.id)
        assert part1_summary["upvotes"] == 1
        assert part1_summary["user_vote"] == "upvote"

        # Check second part
        part2_summary = next(item for item in data if item["part_id"] == part2.id)
        assert part2_summary["downvotes"] == 1
        assert part2_summary["user_vote"] == "downvote"

    def test_vote_unauthorized(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_category: Category,
    ):
        """Test voting without authentication."""
        # Create a test part
        part = Part(
            name="Test Part",
            description="Test Description",
            category_id=test_category.id,
            user_id=test_user.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Try to vote without login
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"/api/part-votes/{part.id}/vote", json=vote_data)

        assert response.status_code == 401
