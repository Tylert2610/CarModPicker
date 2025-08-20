from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.part import PartCreate, PartRead, PartUpdate
from app.core.config import settings
from app.tests.conftest import get_default_category_id


# Helper function to create a user and log them in (sets cookie on client)
# This function is similar to the one in test_build_lists.py and test_cars.py
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
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)

    part_data = {
        "name": "Performance Exhaust",
        "part_type": "Exhaust",
        "manufacturer": "BrandX",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 200, response.text
    created_part = response.json()
    assert created_part["name"] == part_data["name"]
    assert created_part["build_list_id"] == build_list_id
    assert "id" in created_part


def test_create_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "temp_owner_part_unauth")
    car_id_temp = create_car_for_user_cookie_auth(client)
    build_list_id_temp = create_build_list_for_car_cookie_auth(client, car_id_temp)

    client.cookies.clear()
    part_data = {"name": "Unauthorized Part", "build_list_id": build_list_id_temp}
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 401


def test_create_part_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "part_bl_not_found")
    non_existent_bl_id = 999888
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Part for Non-existent BL",
        "build_list_id": non_existent_bl_id,
        "category_id": category_id,
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_create_part_for_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates a car and build list
    _ = create_and_login_user(client, "userA_part_bl_owner")
    car_id_a = create_car_for_user_cookie_auth(client, "Honda", "S2000")
    build_list_id_a = create_build_list_for_car_cookie_auth(
        client, car_id_a, "UserA_S2000_BL"
    )

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_part_attacker")

    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Attacker's Part",
        "build_list_id": build_list_id_a,
        "category_id": category_id,
    }
    response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "Not authorized to add a part to this build list"
    )


def test_read_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "reader_part")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data_payload = {
        "name": "Intake System",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data_payload)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    client.cookies.clear()  # Assuming public read for parts
    response = client.get(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 200, response.text
    read_part_data = response.json()
    assert read_part_data["id"] == part_id
    assert read_part_data["name"] == part_data_payload["name"]


def test_read_part_not_found(client: TestClient, db_session: Session) -> None:
    response = client.get(f"{settings.API_STR}/parts/777666")
    assert response.status_code == 404
    assert response.json()["detail"] == "part not found"  # As per parts.py endpoint


def test_update_own_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_part")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data_initial = {
        "name": "Stock Spoiler",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data_initial)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    update_payload = {
        "name": "Carbon Fiber Spoiler",
        "description": "Lightweight and stylish",
    }
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 200, response.text
    updated_part = response.json()
    assert updated_part["name"] == update_payload["name"]
    assert updated_part["description"] == update_payload["description"]
    assert updated_part["build_list_id"] == build_list_id


def test_update_own_part_change_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    user_id = create_and_login_user(client, "part_bl_changer")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id_1 = create_build_list_for_car_cookie_auth(
        client, car_id, "BL_1_for_Part_Move"
    )
    build_list_id_2 = create_build_list_for_car_cookie_auth(
        client, car_id, "BL_2_for_Part_Move"
    )  # User owns both BLs

    category_id = get_default_category_id(db_session)
    part_data_initial = {
        "name": "Movable Part",
        "build_list_id": build_list_id_1,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data_initial)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    update_payload = {"build_list_id": build_list_id_2}
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 200, response.text
    updated_part = response.json()
    assert updated_part["build_list_id"] == build_list_id_2


def test_update_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "owner_for_update_unauth_part")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Part Before Unauth Update",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    client.cookies.clear()
    update_payload = {"name": "New Name Unauth Part"}
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 401


def test_update_part_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "updater_part_notfound")
    update_payload = {"name": "Update Non Existent Part"}
    response = client.put(f"{settings.API_STR}/parts/555444", json=update_payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "part not found"


def test_update_other_users_part_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates car, build list, and part
    _ = create_and_login_user(client, "userA_part_owner_update")
    car_id_a = create_car_for_user_cookie_auth(client)
    build_list_id_a = create_build_list_for_car_cookie_auth(client, car_id_a)
    category_id = get_default_category_id(db_session)
    part_data_a = {
        "name": "User A's Part",
        "build_list_id": build_list_id_a,
        "category_id": category_id,
    }
    create_response_a = client.post(f"{settings.API_STR}/parts/", json=part_data_a)
    assert create_response_a.status_code == 200
    part_id_a = create_response_a.json()["id"]

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_part_updater_attacker")

    update_payload = {"name": "Malicious Part Update"}
    response = client.put(f"{settings.API_STR}/parts/{part_id_a}", json=update_payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this part"


def test_update_part_to_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates their car, build list, and part
    _ = create_and_login_user(client, "userA_part_bl_switcher")
    car_id_a = create_car_for_user_cookie_auth(client, "Nissan", "Silvia")
    build_list_id_a_own = create_build_list_for_car_cookie_auth(
        client, car_id_a, "UserA_Silvia_BL"
    )
    category_id = get_default_category_id(db_session)
    part_data_a = {
        "name": "User A's Drift Part",
        "build_list_id": build_list_id_a_own,
        "category_id": category_id,
    }
    create_response_a = client.post(f"{settings.API_STR}/parts/", json=part_data_a)
    assert create_response_a.status_code == 200
    part_id_a = create_response_a.json()["id"]

    # User B creates their car and build list
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_bl_owner_target_part")
    car_id_b = create_car_for_user_cookie_auth(client, "Toyota", "AE86")
    build_list_id_b_target = create_build_list_for_car_cookie_auth(
        client, car_id_b, "UserB_AE86_BL"
    )

    # User A logs back in to attempt the update
    client.cookies.clear()
    _ = create_and_login_user(client, "userA_part_bl_switcher")

    update_payload = {
        "build_list_id": build_list_id_b_target
    }  # Attempt to move part to User B's BL
    response = client.put(f"{settings.API_STR}/parts/{part_id_a}", json=update_payload)
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "Not authorized to move part to the new build list"
    )


def test_update_part_to_non_existent_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    _ = create_and_login_user(client, "part_to_non_bl_updater")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id_own = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Part for BL Update Test",
        "build_list_id": build_list_id_own,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    non_existent_bl_id = 999777
    update_payload = {"build_list_id": non_existent_bl_id}
    response = client.put(f"{settings.API_STR}/parts/{part_id}", json=update_payload)
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"New Build List with id {non_existent_bl_id} not found"
    )


def test_delete_own_part_success(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_part")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Part to be Deleted",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    response = client.delete(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 200, response.text
    deleted_part_data = response.json()
    assert deleted_part_data["id"] == part_id

    client.cookies.clear()  # To verify it's gone
    get_response = client.get(f"{settings.API_STR}/parts/{part_id}")
    assert get_response.status_code == 404


def test_delete_part_unauthenticated(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "owner_for_delete_unauth_part")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(client, car_id)
    category_id = get_default_category_id(db_session)
    part_data = {
        "name": "Part for Unauth Delete Test",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    create_response = client.post(f"{settings.API_STR}/parts/", json=part_data)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    client.cookies.clear()
    response = client.delete(f"{settings.API_STR}/parts/{part_id}")
    assert response.status_code == 401


def test_delete_part_not_found(client: TestClient, db_session: Session) -> None:
    _ = create_and_login_user(client, "deleter_part_notfound")
    response = client.delete(f"{settings.API_STR}/parts/333222")
    assert response.status_code == 404
    assert response.json()["detail"] == "part not found"


def test_delete_other_users_part_forbidden(
    client: TestClient, db_session: Session
) -> None:
    # User A creates car, build list, and part
    _ = create_and_login_user(client, "userA_part_owner_del")
    car_id_a = create_car_for_user_cookie_auth(client)
    build_list_id_a = create_build_list_for_car_cookie_auth(client, car_id_a)
    category_id = get_default_category_id(db_session)
    part_data_a = {
        "name": "User A's Precious Part",
        "build_list_id": build_list_id_a,
        "category_id": category_id,
    }
    create_response_a = client.post(f"{settings.API_STR}/parts/", json=part_data_a)
    assert create_response_a.status_code == 200
    part_id_a = create_response_a.json()["id"]

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_part_deleter_attacker")

    response = client.delete(f"{settings.API_STR}/parts/{part_id_a}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this part"


# Tests for read_parts_by_build_list
def test_read_parts_by_build_list_success(
    client: TestClient, db_session: Session
) -> None:
    user_id = create_and_login_user(client, "owner_for_parts_by_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(
        client, car_id, "BL_for_Parts_Read"
    )

    # Create a couple of parts for this build list
    category_id = get_default_category_id(db_session)
    part_data1 = {
        "name": "Part 1 for BL",
        "part_type": "Engine",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }
    part_data2 = {
        "name": "Part 2 for BL",
        "manufacturer": "BrandY",
        "build_list_id": build_list_id,
        "category_id": category_id,
    }

    create_response1 = client.post(f"{settings.API_STR}/parts/", json=part_data1)
    assert create_response1.status_code == 200
    part_id1 = create_response1.json()["id"]

    create_response2 = client.post(f"{settings.API_STR}/parts/", json=part_data2)
    assert create_response2.status_code == 200
    part_id2 = create_response2.json()["id"]

    # Endpoint is public, clear cookies if desired, though not strictly necessary
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/parts/build-list/{build_list_id}")
    assert response.status_code == 200, response.text

    parts_list = response.json()
    assert isinstance(parts_list, list)
    assert len(parts_list) == 2

    retrieved_part_ids = {part["id"] for part in parts_list}
    assert part_id1 in retrieved_part_ids
    assert part_id2 in retrieved_part_ids

    for part in parts_list:
        assert part["build_list_id"] == build_list_id
        if part["id"] == part_id1:
            assert part["name"] == part_data1["name"]
            assert part["part_type"] == part_data1["part_type"]
        elif part["id"] == part_id2:
            assert part["name"] == part_data2["name"]
            assert part["manufacturer"] == part_data2["manufacturer"]


def test_read_parts_by_build_list_empty(
    client: TestClient, db_session: Session
) -> None:
    user_id = create_and_login_user(client, "owner_for_empty_parts_by_bl")
    car_id = create_car_for_user_cookie_auth(client)
    build_list_id = create_build_list_for_car_cookie_auth(
        client, car_id, "BL_Empty_Parts_Read"
    )

    # No parts created for this build list

    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/parts/build-list/{build_list_id}")
    assert response.status_code == 200, response.text

    parts_list = response.json()
    assert isinstance(parts_list, list)
    assert len(parts_list) == 0


def test_read_parts_by_build_list_build_list_not_found(
    client: TestClient, db_session: Session
) -> None:
    non_existent_build_list_id = 999666

    client.cookies.clear()
    response = client.get(
        f"{settings.API_STR}/parts/build-list/{non_existent_build_list_id}"
    )
    assert (
        response.status_code == 200
    ), response.text  # Endpoint returns 200 and empty list

    parts_list = response.json()
    assert isinstance(parts_list, list)
    assert len(parts_list) == 0
