import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.part import Part
from app.api.models.part_vote import PartVote
from app.api.models.part_report import PartReport
from app.api.models.user import User
from app.api.models.category import Category
from app.core.config import settings
from app.api.dependencies.auth import get_password_hash
from app.tests.conftest import get_default_category_id


# Helper function to create a user and log them in
def create_and_login_user(
    client: TestClient, username_suffix: str, db_session: Session = None
) -> int:
    username = f"vote_test_user_{username_suffix}"
    email = f"vote_test_user_{username_suffix}@example.com"
    password = "testpassword"

    # Create user via API
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

    # Login via API
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


# Helper function to create an admin user and log them in
def create_and_login_admin_user(
    client: TestClient, username_suffix: str, db_session: Session
) -> int:
    username = f"admin_test_user_{username_suffix}"
    email = f"admin_test_user_{username_suffix}@example.com"
    password = "testpassword"

    # Create user via API
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

    # Make user admin using the test database session
    if user_id != -1:
        user = db_session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_admin = True
            db_session.commit()
    else:
        user = db_session.query(User).filter(User.username == username).first()
        if user:
            user.is_admin = True
            user_id = user.id
            db_session.commit()

    # Login via API
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in admin user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    if user_id == -1:
        me_response = client.get(f"{settings.API_STR}/users/me")
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(
                f"Could not retrieve user_id for existing admin user {username} via /users/me."
            )

    if user_id == -1:
        raise Exception(f"Admin user ID for {username} could not be determined.")
    return user_id


class TestPartVotes:
    def test_vote_on_part_success(self, client: TestClient, db_session: Session):
        """Test successful voting on a part."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_success", db_session)

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
        user_id = create_and_login_user(client, "vote_invalid", db_session)

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

    def test_vote_on_nonexistent_part(self, client: TestClient, db_session: Session):
        """Test voting on a part that doesn't exist."""
        # Create and login user
        create_and_login_user(client, "vote_nonexistent", db_session)

        # Try to vote on nonexistent part
        vote_data = {"vote_type": "upvote"}
        response = client.post("/api/part-votes/999/vote", json=vote_data)

        assert response.status_code == 404
        assert "Part not found" in response.json()["detail"]

    def test_update_existing_vote(self, client: TestClient, db_session: Session):
        """Test updating an existing vote."""
        # Create and login user
        user_id = create_and_login_user(client, "vote_update", db_session)

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
        user_id = create_and_login_user(client, "vote_remove", db_session)

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
        user_id = create_and_login_user(client, "vote_remove_nonexistent", db_session)

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
        user_id = create_and_login_user(client, "vote_summary", db_session)

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
        user_id = create_and_login_user(client, "vote_summaries", db_session)

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

    def test_get_flagged_parts_success(self, client: TestClient, db_session: Session):
        """Test successful retrieval of flagged parts by admin."""
        # Create admin user
        admin_id = create_and_login_admin_user(client, "flagged_success", db_session)

        # Create regular users for voting
        user1_id = create_and_login_user(client, "voter1", db_session)
        user2_id = create_and_login_user(client, "voter2", db_session)
        user3_id = create_and_login_user(client, "voter3", db_session)

        # Get category
        category_id = get_default_category_id(db_session)

        # Create test parts
        good_part = Part(
            name="Good Part",
            brand="TestBrand",
            category_id=category_id,
            user_id=admin_id,
        )
        bad_part = Part(
            name="Bad Part",
            brand="TestBrand",
            category_id=category_id,
            user_id=admin_id,
        )
        db_session.add_all([good_part, bad_part])
        db_session.commit()
        db_session.refresh(good_part)
        db_session.refresh(bad_part)

        # Create votes to make bad_part flagged (6 downvotes, 2 upvotes = 8 total, 75% downvote ratio, score = -4)
        votes = [
            PartVote(user_id=user1_id, part_id=bad_part.id, vote_type="downvote"),
            PartVote(user_id=user2_id, part_id=bad_part.id, vote_type="downvote"),
            PartVote(user_id=user3_id, part_id=bad_part.id, vote_type="downvote"),
            PartVote(user_id=admin_id, part_id=bad_part.id, vote_type="upvote"),
        ]
        db_session.add_all(votes)
        db_session.commit()

        # Login as admin for the request
        create_and_login_admin_user(client, "flagged_success", db_session)

        # Test with default parameters
        response = client.get(
            "/api/part-votes/flagged-parts?min_votes=4&threshold=-2&min_downvote_ratio=0.6"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        flagged_part = data[0]
        assert flagged_part["part_id"] == bad_part.id
        assert flagged_part["part_name"] == "Bad Part"
        assert flagged_part["part_brand"] == "TestBrand"
        assert flagged_part["upvotes"] == 1
        assert flagged_part["downvotes"] == 3
        assert flagged_part["total_votes"] == 4
        assert flagged_part["vote_score"] == -2
        assert flagged_part["downvote_ratio"] == 0.75
        assert flagged_part["has_reports"] is False
        assert "flagged_at" in flagged_part

    def test_get_flagged_parts_with_custom_thresholds(
        self, client: TestClient, db_session: Session
    ):
        """Test flagged parts with custom threshold parameters."""
        # Create admin user
        admin_id = create_and_login_admin_user(client, "flagged_custom", db_session)

        # Create regular users
        user1_id = create_and_login_user(client, "voter1_custom", db_session)
        user2_id = create_and_login_user(client, "voter2_custom", db_session)

        # Get category
        category_id = get_default_category_id(db_session)

        # Create test part
        part = Part(
            name="Moderately Bad Part",
            category_id=category_id,
            user_id=admin_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Create votes (3 downvotes, 2 upvotes = score -1, 60% downvote ratio)
        votes = [
            PartVote(user_id=user1_id, part_id=part.id, vote_type="downvote"),
            PartVote(user_id=user2_id, part_id=part.id, vote_type="downvote"),
            PartVote(user_id=admin_id, part_id=part.id, vote_type="upvote"),
        ]
        db_session.add_all(votes)
        db_session.commit()

        # Login as admin
        create_and_login_admin_user(client, "flagged_custom", db_session)

        # Test with custom thresholds that should capture this part
        response = client.get(
            "/api/part-votes/flagged-parts?"
            "threshold=-1&min_votes=3&min_downvote_ratio=0.5"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["part_id"] == part.id

    def test_get_flagged_parts_with_reports(
        self, client: TestClient, db_session: Session
    ):
        """Test flagged parts that also have pending reports."""
        # Create admin user
        admin_id = create_and_login_admin_user(client, "flagged_reports", db_session)

        # Create regular user
        user_id = create_and_login_user(client, "voter_reports", db_session)

        # Get category
        category_id = get_default_category_id(db_session)

        # Create test part
        part = Part(
            name="Reported Part",
            category_id=category_id,
            user_id=admin_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Create votes to make it flagged
        votes = [
            PartVote(user_id=user_id, part_id=part.id, vote_type="downvote"),
            PartVote(user_id=admin_id, part_id=part.id, vote_type="downvote"),
        ]
        db_session.add_all(votes)

        # Create a pending report
        report = PartReport(
            user_id=user_id,
            part_id=part.id,
            reason="inappropriate",
            description="This part is inappropriate",
            status="pending",
        )
        db_session.add(report)
        db_session.commit()

        # Login as admin
        create_and_login_admin_user(client, "flagged_reports", db_session)

        # Test flagged parts endpoint
        response = client.get(
            "/api/part-votes/flagged-parts?min_votes=2&min_downvote_ratio=0.8&threshold=-1"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["part_id"] == part.id
        assert data[0]["has_reports"] is True

    def test_get_flagged_parts_unauthorized(
        self, client: TestClient, db_session: Session
    ):
        """Test that non-admin users cannot access flagged parts."""
        # Create regular user (not admin)
        create_and_login_user(client, "not_admin", db_session)

        # Try to access flagged parts
        response = client.get("/api/part-votes/flagged-parts")

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_get_flagged_parts_no_login(self, client: TestClient):
        """Test that unauthenticated users cannot access flagged parts."""
        # Try to access without login
        response = client.get("/api/part-votes/flagged-parts")

        assert response.status_code == 401

    def test_get_flagged_parts_empty_result(
        self, client: TestClient, db_session: Session
    ):
        """Test flagged parts when no parts meet the criteria."""
        # Create admin user
        admin_id = create_and_login_admin_user(client, "flagged_empty", db_session)

        # Create user
        user_id = create_and_login_user(client, "voter_empty", db_session)

        # Get category
        category_id = get_default_category_id(db_session)

        # Create test part with good votes
        part = Part(
            name="Good Part",
            category_id=category_id,
            user_id=admin_id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        # Create only upvotes
        votes = [
            PartVote(user_id=user_id, part_id=part.id, vote_type="upvote"),
            PartVote(user_id=admin_id, part_id=part.id, vote_type="upvote"),
        ]
        db_session.add_all(votes)
        db_session.commit()

        # Login as admin
        create_and_login_admin_user(client, "flagged_empty", db_session)

        # Test flagged parts
        response = client.get("/api/part-votes/flagged-parts")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_flagged_parts_pagination(
        self, client: TestClient, db_session: Session
    ):
        """Test pagination parameters for flagged parts."""
        # Create admin user
        admin_id = create_and_login_admin_user(client, "flagged_pagination", db_session)

        # Create user
        user_id = create_and_login_user(client, "voter_pagination", db_session)

        # Get category
        category_id = get_default_category_id(db_session)

        # Create multiple flagged parts
        parts = []
        for i in range(3):
            part = Part(
                name=f"Bad Part {i}",
                category_id=category_id,
                user_id=admin_id,
            )
            parts.append(part)

        db_session.add_all(parts)
        db_session.commit()
        db_session.refresh(parts[0])
        db_session.refresh(parts[1])
        db_session.refresh(parts[2])

        # Create votes to make all parts flagged
        votes = []
        for part in parts:
            votes.extend(
                [
                    PartVote(user_id=user_id, part_id=part.id, vote_type="downvote"),
                    PartVote(user_id=admin_id, part_id=part.id, vote_type="downvote"),
                ]
            )
        db_session.add_all(votes)
        db_session.commit()

        # Login as admin
        create_and_login_admin_user(client, "flagged_pagination", db_session)

        # Test pagination
        response = client.get(
            "/api/part-votes/flagged-parts?min_votes=2&min_downvote_ratio=0.8&threshold=-1&limit=2&skip=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Test second page
        response = client.get(
            "/api/part-votes/flagged-parts?min_votes=2&min_downvote_ratio=0.8&threshold=-1&limit=2&skip=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
