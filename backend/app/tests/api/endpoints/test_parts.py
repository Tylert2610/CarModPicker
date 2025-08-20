from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.tests.conftest import get_default_category_id


# Helper function to create a user and log them in (sets cookie on client)
def create_and_login_user(
    client: TestClient, username_suffix: str
) -> int:  # Returns user_id
    username = f"part_test_user_{username_suffix}"
    email = f"part_test_user_{username_suffix}@example.com"
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


# Helper function to create a car for the currently logged-in user (via client cookie)
def create_car_for_user_cookie_auth(
    client: TestClient, car_make: str = "TestMakePart", car_model: str = "TestModelPart"
) -> int:
    car_data = {
        "make": car_make,
        "model": car_model,
        "year": 2024,
        "trim": "TestTrimPart",
    }
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert (
        response.status_code == 200
    ), f"Failed to create car for part tests: {response.text}"
    return int(response.json()["id"])


# Helper function to create a build list for a car owned by the currently logged-in user
def create_build_list_for_car_cookie_auth(
    client: TestClient, car_id: int, bl_name: str = "TestBLPart"
) -> int:
    build_list_data = {
        "name": bl_name,
        "description": "Test BL for parts",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert (
        response.status_code == 200
    ), f"Failed to create build list for part tests: {response.text}"
    return int(response.json()["id"])


# --- Test Cases ---


def test_create_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "creator_part")
    category_id = get_default_category_id(db_session)

    part_data = {
        "name": "Performance Exhaust",
        "description": "High-performance exhaust system",
        "price": 50000,
        "category_id": category_id,
        "brand": "BrandX",
        "part_number": "EXH-001",
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 200, response.text
    created_part = response.json()
    assert created_part["name"] == part_data["name"]
    assert created_part["description"] == part_data["description"]
    assert created_part["price"] == part_data["price"]
    assert created_part["category_id"] == category_id
    assert created_part["brand"] == part_data["brand"]
    assert created_part["part_number"] == part_data["part_number"]
    assert "user_id" in created_part  # Creator ID
    assert created_part["is_verified"] is False
    assert created_part["source"] == "user_created"
    assert created_part["edit_count"] == 0


def test_create_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Unauthorized Part",
        "category_id": category_id,
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 401


def test_read_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "reader_part")
    category_id = get_default_category_id(db_session)

    # Create a part first
    part_data = {
        "name": "Test Part for Reading",
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    # Read the part
    response = client.get(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 200, response.text
    part = response.json()
    assert part["id"] == part_id
    assert part["name"] == part_data["name"]


def test_read_part_not_found(client: TestClient, db_session: Session) -> None:
    response = client.get(f"{settings.API_STR}/parts/777666")
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found"


def test_update_own_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_part")
    category_id = get_default_category_id(db_session)

    # Create a part first
    part_data_initial = {
        "name": "Stock Spoiler",
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data_initial)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    update_payload = {
        "name": "Carbon Fiber Spoiler",
        "description": "Lightweight and stylish",
        "price": 75000,
    }
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 200, response.text
    updated_part = response.json()
    assert updated_part["name"] == update_payload["name"]
    assert updated_part["description"] == update_payload["description"]
    assert updated_part["price"] == update_payload["price"]
    assert updated_part["edit_count"] == 1  # Should be incremented


def test_update_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    update_payload = {"name": "Unauthorized Update"}
    response = client.put(f"{settings.API_STR}/parts/1", json=update_payload)
    assert response.status_code == 401


def test_update_part_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_part_notfound")
    update_payload = {"name": "Update Non Existent Part"}
    response = client.put(f"{settings.API_STR}/parts/555444", json=update_payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found"


def test_update_other_users_part_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a part
    _ = create_and_login_user(client, "userA_part_owner")
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "User A's Part",
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    # User B logs in and tries to update User A's part
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_part_attacker")
    update_payload = {"name": "User B's Unauthorized Update"}
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this part"


def test_delete_own_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_part")
    category_id = get_default_category_id(db_session)

    # Create a part first
    part_data = {
        "name": "Part to Delete",
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    response = client.delete(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 200, response.text
    deleted_part = response.json()
    assert deleted_part["id"] == part_id
    assert deleted_part["name"] == part_data["name"]


def test_delete_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    response = client.delete(f"{settings.API_STR}/parts/1")
    assert response.status_code == 401


def test_delete_part_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_part_notfound")
    response = client.delete(f"{settings.API_STR}/parts/333222")
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found"


def test_delete_other_users_part_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a part
    _ = create_and_login_user(client, "userA_part_owner_delete")
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "User A's Part to Delete",
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    # User B logs in and tries to delete User A's part
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_part_deleter")
    response = client.delete(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this part"


def test_read_parts_with_filtering(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "parts_filter_user")
    category_id = get_default_category_id(db_session)

    # Create multiple parts
    part_data1 = {
        "name": "Exhaust System",
        "description": "Performance exhaust",
        "category_id": category_id,
        "price": 50000,
    }
    part_data2 = {
        "name": "Air Intake",
        "description": "Cold air intake",
        "category_id": category_id,
        "price": 25000,
    }

    client.post(f"{settings.API_STR}/parts/", json=part_data1)
    client.post(f"{settings.API_STR}/parts/", json=part_data2)

    # Test getting all parts
    response = client.get(f"{settings.API_STR}/parts/")
    assert response.status_code == 200
    parts = response.json()
    assert len(parts) >= 2

    # Test filtering by category
    response = client.get(f"{settings.API_STR}/parts/?category_id={category_id}")
    assert response.status_code == 200
    parts = response.json()
    assert len(parts) >= 2

    # Test search functionality
    response = client.get(f"{settings.API_STR}/parts/?search=exhaust")
    assert response.status_code == 200
    parts = response.json()
    assert len(parts) >= 1
    assert any("exhaust" in part["name"].lower() for part in parts)


def test_read_parts_by_user(client: TestClient, db_session: Session) -> None:
    user_id = create_and_login_user(client, "parts_by_user_creator")
    category_id = get_default_category_id(db_session)

    # Create parts for this user
    part_data1 = {
        "name": "User's Part 1",
        "category_id": category_id,
    }
    part_data2 = {
        "name": "User's Part 2",
        "category_id": category_id,
    }

    client.post(f"{settings.API_STR}/parts/", json=part_data1)
    client.post(f"{settings.API_STR}/parts/", json=part_data2)

    # Get parts by user
    response = client.get(f"{settings.API_STR}/parts/user/{user_id}")
    assert response.status_code == 200
    parts = response.json()
    assert len(parts) >= 2
    for part in parts:
        assert part["user_id"] == user_id
