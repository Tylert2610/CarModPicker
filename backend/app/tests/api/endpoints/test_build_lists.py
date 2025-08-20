from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


# Helper function to create a user and log them in (sets cookie on client)
def create_and_login_user(
    client: TestClient, username_suffix: str
) -> int:  # Returns user_id
    username = f"bl_test_user_{username_suffix}"
    email = f"bl_test_user_{username_suffix}@example.com"
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
    client: TestClient, car_make: str = "TestMakeBL", car_model: str = "TestModelBL"
) -> int:
    car_data = {
        "make": car_make,
        "model": car_model,
        "year": 2024,
        "trim": "TestTrimBL",
    }
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert (
        response.status_code == 200
    ), f"Failed to create car for build list tests: {response.text}"
    return int(response.json()["id"])


# --- Test Cases ---


def test_create_build_list_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "creator_bl")
    car_id = create_car_for_user_cookie_auth(client)

    build_list_data = {
        "name": "My First Build",
        "description": "A test build list",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert response.status_code == 200, response.text
    created_build_list = response.json()
    assert created_build_list["name"] == build_list_data["name"]
    assert created_build_list["car_id"] == car_id
    assert "id" in created_build_list


def test_create_build_list_unauthenticated(
    client: TestClient, db_session: Session
) -> None:
    client.cookies.clear()
    build_list_data = {"name": "Unauthorized Build", "car_id": 1}
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert response.status_code == 401


def test_create_build_list_car_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "bl_car_not_found")
    non_existent_car_id = 999888
    build_list_data = {
        "name": "Build for Non-existent Car",
        "car_id": non_existent_car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Car not found"


def test_create_build_list_for_other_users_car_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a car
    _ = create_and_login_user(client, "userA_bl_car_owner")
    car_id_a = create_car_for_user_cookie_auth(client, "Honda", "S2000")

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_bl_attacker")

    build_list_data = {"name": "Attacker's Build", "car_id": car_id_a}
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Not authorized to create a build list for this car"
    )


def test_read_build_list_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "reader_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data_payload = {
        "name": "Test Build List",
        "description": "A test build list for reading",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data_payload
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}")
    assert response.status_code == 200, response.text
    read_build_list_data = response.json()
    assert read_build_list_data["id"] == build_list_id
    assert read_build_list_data["name"] == build_list_data_payload["name"]


def test_read_build_list_not_found(client: TestClient, db_session: Session) -> None:
    response = client.get(f"{settings.API_STR}/build-lists/777666")
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_update_own_build_list_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data_initial = {
        "name": "Initial Build List",
        "description": "Initial description",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data_initial
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    update_payload = {
        "name": "Updated Build List",
        "description": "Updated description",
    }
    response = client.put(
        f"{settings.API_STR}/build-lists/{build_list_id}", json=update_payload
    )
    assert response.status_code == 200, response.text
    updated_build_list = response.json()
    assert updated_build_list["name"] == update_payload["name"]
    assert updated_build_list["description"] == update_payload["description"]
    assert updated_build_list["car_id"] == car_id


def test_update_build_list_unauthenticated(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "owner_for_update_unauth_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data = {
        "name": "Build List Before Unauth Update",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    client.cookies.clear()
    update_payload = {"name": "New Name Unauth Build List"}
    response = client.put(
        f"{settings.API_STR}/build-lists/{build_list_id}", json=update_payload
    )
    assert response.status_code == 401


def test_update_build_list_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_bl_notfound")
    update_payload = {"name": "Update Non Existent Build List"}
    response = client.put(f"{settings.API_STR}/build-lists/555444", json=update_payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_update_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates car and build list
    _ = create_and_login_user(client, "userA_bl_owner_update")
    car_id_a = create_car_for_user_cookie_auth(client)
    build_list_data_a = {
        "name": "User A's Build List",
        "car_id": car_id_a,
    }
    create_response_a = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data_a
    )
    assert create_response_a.status_code == 200
    build_list_id_a = create_response_a.json()["id"]

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_bl_updater_attacker")

    update_payload = {"name": "Malicious Build List Update"}
    response = client.put(
        f"{settings.API_STR}/build-lists/{build_list_id_a}", json=update_payload
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this build list"


def test_update_build_list_to_other_users_car_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates their car and build list
    _ = create_and_login_user(client, "userA_bl_car_switcher")
    car_id_a = create_car_for_user_cookie_auth(client, "Nissan", "Silvia")
    build_list_data_a = {
        "name": "User A's Drift Build List",
        "car_id": car_id_a,
    }
    create_response_a = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data_a
    )
    assert create_response_a.status_code == 200
    build_list_id_a = create_response_a.json()["id"]

    # User B creates their car
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_car_owner_target_bl")
    car_id_b = create_car_for_user_cookie_auth(client, "Toyota", "AE86")

    # User A logs back in to attempt the update
    client.cookies.clear()
    _ = create_and_login_user(client, "userA_bl_car_switcher")

    update_payload = {"car_id": car_id_b}  # Attempt to move build list to User B's car
    response = client.put(
        f"{settings.API_STR}/build-lists/{build_list_id_a}", json=update_payload
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Not authorized to associate build list with the new car"
    )


def test_update_build_list_to_non_existent_car_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "bl_to_non_car_updater")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data = {
        "name": "Build List for Car Update Test",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    non_existent_car_id = 999777
    update_payload = {"car_id": non_existent_car_id}
    response = client.put(
        f"{settings.API_STR}/build-lists/{build_list_id}", json=update_payload
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"] == f"New car with id {non_existent_car_id} not found"
    )


def test_delete_own_build_list_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data = {
        "name": "Build List to be Deleted",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}")
    assert response.status_code == 200, response.text
    deleted_build_list_data = response.json()
    assert deleted_build_list_data["id"] == build_list_id

    client.cookies.clear()
    get_response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}")
    assert get_response.status_code == 404


def test_delete_build_list_unauthenticated(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "owner_for_delete_unauth_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_data = {
        "name": "Build List for Unauth Delete Test",
        "car_id": car_id,
    }
    create_response = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    client.cookies.clear()
    response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id}")
    assert response.status_code == 401


def test_delete_build_list_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_bl_notfound")
    response = client.delete(f"{settings.API_STR}/build-lists/333222")
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_delete_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates car and build list
    _ = create_and_login_user(client, "userA_bl_owner_del")
    car_id_a = create_car_for_user_cookie_auth(client)
    build_list_data_a = {
        "name": "User A's Precious Build List",
        "car_id": car_id_a,
    }
    create_response_a = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data_a
    )
    assert create_response_a.status_code == 200
    build_list_id_a = create_response_a.json()["id"]

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_bl_deleter_attacker")

    response = client.delete(f"{settings.API_STR}/build-lists/{build_list_id_a}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this build list"


# Tests for read_build_lists_by_car
def test_read_build_lists_by_car_success(
    client: TestClient, db_session: Session
) -> None:
    user_id = create_and_login_user(client, "owner_for_bls_by_car")
    car_id = create_car_for_user_cookie_auth(client)

    # Create a couple of build lists for this car
    build_list_data1 = {
        "name": "Build List 1 for Car",
        "description": "First build list",
        "car_id": car_id,
    }
    build_list_data2 = {
        "name": "Build List 2 for Car",
        "description": "Second build list",
        "car_id": car_id,
    }

    create_response1 = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data1
    )
    assert create_response1.status_code == 200
    build_list_id1 = create_response1.json()["id"]

    create_response2 = client.post(
        f"{settings.API_STR}/build-lists/", json=build_list_data2
    )
    assert create_response2.status_code == 200
    build_list_id2 = create_response2.json()["id"]

    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/build-lists/car/{car_id}")
    assert response.status_code == 200, response.text

    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 2

    retrieved_build_list_ids = {bl["id"] for bl in build_lists}
    assert build_list_id1 in retrieved_build_list_ids
    assert build_list_id2 in retrieved_build_list_ids

    for build_list in build_lists:
        assert build_list["car_id"] == car_id
        if build_list["id"] == build_list_id1:
            assert build_list["name"] == build_list_data1["name"]
            assert build_list["description"] == build_list_data1["description"]
        elif build_list["id"] == build_list_id2:
            assert build_list["name"] == build_list_data2["name"]
            assert build_list["description"] == build_list_data2["description"]


def test_read_build_lists_by_car_empty(client: TestClient, db_session: Session) -> None:
    user_id = create_and_login_user(client, "owner_for_empty_bls_by_car")
    car_id = create_car_for_user_cookie_auth(client)

    # No build lists created for this car

    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/build-lists/car/{car_id}")
    assert response.status_code == 200, response.text

    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 0


def test_read_build_lists_by_car_car_not_found(
    client: TestClient, db_session: Session
) -> None:
    non_existent_car_id = 999666

    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/build-lists/car/{non_existent_car_id}")
    assert response.status_code == 200, response.text

    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 0
