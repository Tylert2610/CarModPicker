from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.tests.conftest import get_default_category_id


# Helper function to create a user and log them in (sets cookie on client)
def create_and_login_user(
    client: TestClient, username_suffix: str
) -> int:  # Returns user_id
    username = f"build_list_part_test_user_{username_suffix}"
    email = f"build_list_part_test_user_{username_suffix}@example.com"
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
    client: TestClient, car_make: str = "TestMakeBLP", car_model: str = "TestModelBLP"
) -> int:
    car_data = {
        "make": car_make,
        "model": car_model,
        "year": 2024,
        "trim": "TestTrimBLP",
    }
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert (
        response.status_code == 200
    ), f"Failed to create car for build list part tests: {response.text}"
    return int(response.json()["id"])


# Helper function to create a build list for a car owned by the currently logged-in user
def create_build_list_for_car_cookie_auth(
    client: TestClient, car_id: int, bl_name: str = "TestBLPart"
) -> int:
    build_list_data = {
        "name": bl_name,
        "description": "Test BL for build list parts",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert (
        response.status_code == 200
    ), f"Failed to create build list for build list part tests: {response.text}"
    return int(response.json()["id"])


# Helper function to create a part for the currently logged-in user
def create_part_for_user_cookie_auth(
    client: TestClient, db_session: Session, part_name: str = "Test Part"
) -> int:
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": part_name,
        "description": "Test part for build list parts",
        "category_id": category_id,
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert (
        response.status_code == 200
    ), f"Failed to create part for build list part tests: {response.text}"
    return int(response.json()["id"])


# --- Test Cases ---


def test_add_part_to_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "add_part_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    part_id = create_part_for_user_cookie_auth(client, db_session, "Test Part")

    build_list_part_data = {"notes": "Test notes for this part"}
    response = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json=build_list_part_data,
    )
    assert response.status_code == 200, response.text
    created_relationship = response.json()
    assert created_relationship["build_list_id"] == build_list_id
    assert created_relationship["part_id"] == part_id
    assert created_relationship["notes"] == build_list_part_data["notes"]


def test_add_part_to_build_list_unauthenticated(
    client: TestClient, db_session: Session
) -> None:
    build_list_part_data = {"notes": "Test notes"}
    response = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/1/parts/1",
        json=build_list_part_data,
    )
    assert response.status_code == 401


def test_add_part_to_build_list_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "add_part_bl_not_found")
    part_id = create_part_for_user_cookie_auth(client, db_session, "Test Part")

    build_list_part_data = {"notes": "Test notes"}
    response = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/999999/parts/{part_id}",
        json=build_list_part_data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Build list not found"


def test_add_part_to_build_list_part_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "add_part_not_found")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

    build_list_part_data = {"notes": "Test notes"}
    response = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/999999",
        json=build_list_part_data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found"


def test_add_part_to_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a car and build list
    _ = create_and_login_user(client, "userA_blp_owner")
    car_id = create_car_for_user_cookie_auth(client, "Honda", "S2000")
    build_list_id = create_build_list_for_car_cookie_auth(
        client, car_id, "UserA_S2000_BL"
    )

    # User B logs in and creates a part
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_blp_attacker")
    part_id = create_part_for_user_cookie_auth(client, db_session, "User B's Part")

    # User B tries to add their part to User A's build list
    build_list_part_data = {"notes": "Unauthorized addition"}
    response = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json=build_list_part_data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to modify this build list"


def test_add_duplicate_part_to_build_list_conflict(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "duplicate_part_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    part_id = create_part_for_user_cookie_auth(client, db_session, "Duplicate Part")

    build_list_part_data = {"notes": "First addition"}

    # Add the part the first time
    response1 = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json=build_list_part_data,
    )
    assert response1.status_code == 200

    # Try to add the same part again
    response2 = client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json=build_list_part_data,
    )
    assert response2.status_code == 409
    assert response2.json()["detail"] == "Part already exists in build list"


def test_get_parts_in_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "get_parts_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

    # Create and add multiple parts
    part_id1 = create_part_for_user_cookie_auth(client, db_session, "Part 1")
    part_id2 = create_part_for_user_cookie_auth(client, db_session, "Part 2")

    client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id1}",
        json={"notes": "First part"},
    )
    client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id2}",
        json={"notes": "Second part"},
    )

    response = client.get(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts"
    )
    assert response.status_code == 200, response.text
    parts = response.json()
    assert len(parts) == 2

    part_ids = [part["part_id"] for part in parts]
    assert part_id1 in part_ids
    assert part_id2 in part_ids


def test_get_parts_in_build_list_empty(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "get_empty_parts_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

    response = client.get(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts"
    )
    assert response.status_code == 200, response.text
    parts = response.json()
    assert len(parts) == 0


def test_get_parts_in_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "get_parts_not_found_user")

    response = client.get(
        f"{settings.API_STR}/build-list-parts/build-lists/999999/parts"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Build list not found"


def test_get_parts_in_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a car and build list
    _ = create_and_login_user(client, "userA_blp_owner_get")
    car_id = create_car_for_user_cookie_auth(client, "Toyota", "Supra")
    build_list_id = create_build_list_for_car_cookie_auth(
        client, car_id, "UserA_Supra_BL"
    )

    # User B logs in and tries to access User A's build list
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_blp_attacker_get")

    response = client.get(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this build list"


def test_update_part_in_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "update_part_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    part_id = create_part_for_user_cookie_auth(client, db_session, "Update Part")

    # Add the part first
    client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json={"notes": "Original notes"},
    )

    # Update the notes
    update_data = {"notes": "Updated notes"}
    response = client.put(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json=update_data,
    )
    assert response.status_code == 200, response.text
    updated_relationship = response.json()
    assert updated_relationship["notes"] == update_data["notes"]


def test_update_part_in_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "update_part_not_found_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

    update_data = {"notes": "Updated notes"}
    response = client.put(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/999999",
        json=update_data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found in build list"


def test_remove_part_from_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "remove_part_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    part_id = create_part_for_user_cookie_auth(client, db_session, "Remove Part")

    # Add the part first
    client.post(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}",
        json={"notes": "Part to remove"},
    )

    # Remove the part
    response = client.delete(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/{part_id}"
    )
    assert response.status_code == 200, response.text
    removed_relationship = response.json()
    assert removed_relationship["build_list_id"] == build_list_id
    assert removed_relationship["part_id"] == part_id

    # Verify it's gone
    get_response = client.get(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts"
    )
    assert get_response.status_code == 200
    parts = get_response.json()
    assert len(parts) == 0


def test_remove_part_from_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "remove_part_not_found_user")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)

    response = client.delete(
        f"{settings.API_STR}/build-list-parts/build-lists/{build_list_id}/parts/999999"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Part not found in build list"
