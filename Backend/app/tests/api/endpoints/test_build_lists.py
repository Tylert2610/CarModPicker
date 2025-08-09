from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.api.schemas.build_list import (
    BuildListRead,
    BuildListCreate,
    BuildListUpdate,
)  # Ensure this import is present
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
    # Create user
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
    elif response.status_code == 400 and "already registered" in response.json().get(
        "detail", ""
    ):
        # User might exist from a previous run, will attempt to log in.
        pass  # user_id remains -1, will be fetched after login
    else:
        raise Exception(
            f"Failed to create user {username} for tests. Status: {response.status_code}, Detail: {response.text}"
        )

    # Log in to set cookie on the client
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username} to set cookie. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    # Ensure cookie is set on client (FastAPI TestClient handles this automatically on 200 from /token setting cookie)
    # If user_id was not set during creation (because user existed and creation returned 400), get it now via /users/me
    # This /users/me call will use the cookie set by the login.
    if user_id == -1:
        me_response = client.get(
            f"{settings.API_STR}/users/me"
        )  # Cookie is sent by client
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(
                f"Could not retrieve user_id for existing user {username} via /users/me. Status: {me_response.status_code}, Detail: {me_response.text}"
            )

    if user_id == -1:  # Should not happen if logic above is correct
        raise Exception(f"User ID for {username} could not be determined.")

    return user_id


# Helper function to create a car for the currently logged-in user (via client cookie)
def create_car_for_user_cookie_auth(
    client: TestClient, car_make: str = "TestMake", car_model: str = "TestModel"
) -> int:
    car_data = {"make": car_make, "model": car_model, "year": 2023, "trim": "TestTrim"}
    # The client will automatically send the auth cookie if set
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert response.status_code == 200, f"Failed to create car: {response.text}"
    return response.json()["id"]


def test_create_build_list_success(client: TestClient, db_session: Session):
    # User logs in, client gets cookie
    user_id_creator = create_and_login_user(client, "creator_bl")
    # Car is created by the logged-in user (cookie sent automatically)
    car_id = create_car_for_user_cookie_auth(client, "Toyota", "Supra")

    build_list_data = {
        "name": "My Supra Build",
        "description": "Performance upgrades for track days",
        "car_id": car_id,
    }
    # API call uses the cookie set on the client
    response = client.post(f"{settings.API_STR}/build_lists/", json=build_list_data)
    assert response.status_code == 200, response.text
    created_bl = response.json()
    assert created_bl["name"] == build_list_data["name"]
    assert created_bl["description"] == build_list_data["description"]
    assert created_bl["car_id"] == car_id
    assert "id" in created_bl


def test_create_build_list_unauthenticated(client: TestClient, db_session: Session):
    # Create a temporary user and car to get a valid car_id.
    # This user's cookie will be set on the client.
    _ = create_and_login_user(client, "temp_owner_bl_unauth")
    car_id_temp = create_car_for_user_cookie_auth(client)

    client.cookies.clear()  # Clear cookies to simulate an unauthenticated request

    build_list_data = {"name": "Unauthorized Build", "car_id": car_id_temp}
    response = client.post(
        f"{settings.API_STR}/build_lists/", json=build_list_data
    )  # No cookie sent
    assert response.status_code == 401


def test_create_build_list_car_not_found(client: TestClient, db_session: Session):
    # User logs in, client gets cookie
    _ = create_and_login_user(client, "car_not_found_bl")
    non_existent_car_id = 999999
    build_list_data = {
        "name": "Build for Non-existent Car",
        "car_id": non_existent_car_id,
    }
    # API call uses the cookie
    response = client.post(f"{settings.API_STR}/build_lists/", json=build_list_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Car not found"


def test_create_build_list_for_other_users_car(client: TestClient, db_session: Session):
    # User A logs in and creates a car
    _ = create_and_login_user(
        client, "userA_car_owner_bl"
    )  # Client has User A's cookie
    car_id_a = create_car_for_user_cookie_auth(
        client, "Honda", "Civic"
    )  # Uses User A's cookie

    # User B logs in (this clears User A's cookie from client and sets User B's)
    client.cookies.clear()
    _ = create_and_login_user(
        client, "userB_bl_attacker"
    )  # Client now has User B's cookie

    build_list_data = {"name": "Attacker's Build on User A's Car", "car_id": car_id_a}
    # API call uses User B's cookie
    response = client.post(f"{settings.API_STR}/build_lists/", json=build_list_data)
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Not authorized to create a build list for this car"
    )


def test_read_build_list_success(client: TestClient, db_session: Session):
    # User logs in to create the build list
    user_id_reader = create_and_login_user(client, "reader_bl")
    car_id = create_car_for_user_cookie_auth(client, "Mazda", "MX-5")
    build_list_data = {"name": "MX-5 Fun Build", "car_id": car_id}

    # Create build list (authenticated with reader_bl's cookie)
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=build_list_data
    )
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    # If reading a build list is public/unauthenticated:
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/build_lists/{build_list_id}")
    # If reading requires auth (e.g., to see your own, or if all reads are protected),
    # then DO NOT clear cookies. The client would still have reader_bl's cookie.
    # For this example, assuming public read as per original test comment.

    assert response.status_code == 200, response.text
    read_bl_data = response.json()
    assert read_bl_data["id"] == build_list_id
    assert read_bl_data["name"] == build_list_data["name"]
    assert read_bl_data["car_id"] == car_id
    # assert read_bl_data["owner_id"] == user_id_reader # If owner_id is part of public read


def test_read_build_list_not_found(client: TestClient, db_session: Session):
    response = client.get(
        f"{settings.API_STR}/build_lists/999999"
    )  # Assuming this ID won't exist
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_update_own_build_list_success(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "updater_bl")  # Sets cookie
    car_id = create_car_for_user_cookie_auth(client, "Nissan", "GT-R")  # Uses cookie
    build_list_data_initial = {"name": "Initial GT-R Build", "car_id": car_id}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=build_list_data_initial
    )  # Uses cookie
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    update_payload = {
        "name": "Updated GT-R Build",
        "description": "Now with more power!",
    }
    response = client.put(
        f"{settings.API_STR}/build_lists/{build_list_id}", json=update_payload
    )  # Uses cookie
    assert response.status_code == 200, response.text
    updated_bl = response.json()
    assert updated_bl["name"] == update_payload["name"]
    assert updated_bl["description"] == update_payload["description"]
    assert updated_bl["car_id"] == car_id  # Car ID should remain unchanged


def test_update_own_build_list_change_car_success(
    client: TestClient, db_session: Session
):
    _ = create_and_login_user(client, "car_changer_bl")  # Sets cookie
    car_id_1 = create_car_for_user_cookie_auth(client, "Subaru", "WRX")  # Uses cookie
    car_id_2 = create_car_for_user_cookie_auth(
        client, "Mitsubishi", "Evo"
    )  # User owns both cars, uses cookie

    build_list_data_initial = {"name": "WRX Project", "car_id": car_id_1}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=build_list_data_initial
    )  # Uses cookie
    assert create_response.status_code == 200
    build_list_id = create_response.json()["id"]

    update_payload = {"car_id": car_id_2}
    response = client.put(
        f"{settings.API_STR}/build_lists/{build_list_id}", json=update_payload
    )  # Uses cookie
    assert response.status_code == 200, response.text
    updated_bl = response.json()
    assert updated_bl["car_id"] == car_id_2
    assert updated_bl["name"] == build_list_data_initial["name"]


def test_update_build_list_unauthenticated(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "owner_for_update_unauth_bl")  # Sets cookie
    car_id = create_car_for_user_cookie_auth(client)  # Uses cookie
    bl_data = {"name": "Some Build", "car_id": car_id}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data
    )  # Uses cookie
    assert create_response.status_code == 200
    bl_id = create_response.json()["id"]

    client.cookies.clear()  # Clear cookies to simulate an unauthenticated request

    update_payload = {"name": "New Name Unauth"}
    response = client.put(
        f"{settings.API_STR}/build_lists/{bl_id}", json=update_payload
    )  # No cookie sent
    assert response.status_code == 401


def test_update_build_list_not_found(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "updater_bl_notfound")  # Sets cookie
    update_payload = {"name": "Update Non Existent"}
    response = client.put(
        f"{settings.API_STR}/build_lists/777777", json=update_payload
    )  # Uses cookie
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_update_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
):
    # User A logs in and creates a car and a build list
    _ = create_and_login_user(client, "userA_bl_owner")  # Client has User A's cookie
    car_id_a = create_car_for_user_cookie_auth(
        client, "Ford", "Mustang"
    )  # Uses User A's cookie
    bl_data_a = {"name": "User A's Build", "car_id": car_id_a}
    create_response_a = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data_a
    )  # Uses User A's cookie
    assert create_response_a.status_code == 200
    bl_id_a = create_response_a.json()["id"]

    # User B logs in (this clears User A's cookie from client and sets User B's)
    client.cookies.clear()
    _ = create_and_login_user(
        client, "userB_bl_updater_attacker"
    )  # Client now has User B's cookie

    update_payload = {"name": "Malicious Update"}
    response = client.put(
        f"{settings.API_STR}/build_lists/{bl_id_a}", json=update_payload
    )  # Uses User B's cookie
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this build list"


def test_update_build_list_to_other_users_car_forbidden(
    client: TestClient, db_session: Session
):
    # User A logs in, creates their own car and build list
    _ = create_and_login_user(
        client, "userA_bl_car_switcher"
    )  # Client has User A's cookie
    car_id_a_own = create_car_for_user_cookie_auth(
        client, "BMW", "M3"
    )  # Uses User A's cookie
    bl_data_a = {"name": "User A's M3 Build", "car_id": car_id_a_own}
    create_response_a = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data_a
    )  # Uses User A's cookie
    assert create_response_a.status_code == 200
    bl_id_a = create_response_a.json()["id"]

    # User B logs in and creates a car
    client.cookies.clear()  # Clear User A's cookie
    _ = create_and_login_user(
        client, "userB_car_owner_target"
    )  # Client has User B's cookie
    car_id_b_target = create_car_for_user_cookie_auth(
        client, "Audi", "R8"
    )  # Uses User B's cookie

    # User A logs back in to attempt the update
    client.cookies.clear()  # Clear User B's cookie
    _ = create_and_login_user(
        client, "userA_bl_car_switcher"
    )  # Client has User A's cookie again

    update_payload = {"car_id": car_id_b_target}
    response = client.put(
        f"{settings.API_STR}/build_lists/{bl_id_a}", json=update_payload
    )  # Uses User A's cookie
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Not authorized to associate build list with the new car"
    )


def test_update_build_list_to_non_existent_car_not_found(
    client: TestClient, db_session: Session
):
    _ = create_and_login_user(client, "bl_to_non_car_updater")  # Sets cookie
    car_id_own = create_car_for_user_cookie_auth(
        client, "Porsche", "911"
    )  # Uses cookie
    bl_data = {"name": "911 Build", "car_id": car_id_own}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data
    )  # Uses cookie
    assert create_response.status_code == 200
    bl_id = create_response.json()["id"]

    non_existent_car_id = 999888
    update_payload = {"car_id": non_existent_car_id}
    response = client.put(
        f"{settings.API_STR}/build_lists/{bl_id}", json=update_payload
    )  # Uses cookie
    assert response.status_code == 404
    assert (
        response.json()["detail"] == f"New car with id {non_existent_car_id} not found"
    )


def test_delete_own_build_list_success(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "deleter_bl")  # Sets cookie
    car_id = create_car_for_user_cookie_auth(client, "Lexus", "LC500")  # Uses cookie
    bl_data = {"name": "LC500 Project", "car_id": car_id}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data
    )  # Uses cookie
    assert create_response.status_code == 200
    bl_id = create_response.json()["id"]

    response = client.delete(f"{settings.API_STR}/build_lists/{bl_id}")  # Uses cookie
    assert response.status_code == 200, response.text
    deleted_bl_data = response.json()
    assert deleted_bl_data["id"] == bl_id

    # Verify build list is deleted
    client.cookies.clear()  # Clear cookies to ensure public 404
    get_response = client.get(f"{settings.API_STR}/build_lists/{bl_id}")
    assert get_response.status_code == 404


def test_delete_build_list_unauthenticated(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "owner_for_delete_unauth_bl")  # Sets cookie
    car_id = create_car_for_user_cookie_auth(client)  # Uses cookie
    bl_data = {"name": "Build to be deleted unauth", "car_id": car_id}
    create_response = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data
    )  # Uses cookie
    assert create_response.status_code == 200
    bl_id = create_response.json()["id"]

    client.cookies.clear()  # Clear cookies for unauthenticated attempt
    response = client.delete(
        f"{settings.API_STR}/build_lists/{bl_id}"
    )  # No cookie sent
    assert response.status_code == 401


def test_delete_build_list_not_found(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "deleter_bl_notfound")  # Sets cookie
    response = client.delete(
        f"{settings.API_STR}/build_lists/666666"
    )  # Uses cookie, Non-existent ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Build List not found"


def test_delete_other_users_build_list_forbidden(
    client: TestClient, db_session: Session
):
    # User A logs in and creates a car and a build list
    _ = create_and_login_user(
        client, "userA_bl_owner_del"
    )  # Client has User A's cookie
    car_id_a = create_car_for_user_cookie_auth(
        client, "Ferrari", "488"
    )  # Uses User A's cookie
    bl_data_a = {"name": "User A's Ferrari Build", "car_id": car_id_a}
    create_response_a = client.post(
        f"{settings.API_STR}/build_lists/", json=bl_data_a
    )  # Uses User A's cookie
    assert create_response_a.status_code == 200
    bl_id_a = create_response_a.json()["id"]

    # User B logs in (this clears User A's cookie from client and sets User B's)
    client.cookies.clear()
    _ = create_and_login_user(
        client, "userB_bl_deleter_attacker"
    )  # Client now has User B's cookie
    response = client.delete(
        f"{settings.API_STR}/build_lists/{bl_id_a}"
    )  # Uses User B's cookie
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this build list"


# Tests for read_build_lists_by_car
def test_read_build_lists_by_car_success(client: TestClient, db_session: Session):
    user_id = create_and_login_user(client, "owner_for_bl_by_car")
    car_id = create_car_for_user_cookie_auth(client, "Mazda", "RX-7")

    # Create a couple of build lists for this car
    bl_data1 = {"name": "RX-7 Street Build", "car_id": car_id}
    bl_data2 = {"name": "RX-7 Track Build", "description": "For race days", "car_id": car_id}
    
    response1 = client.post(f"{settings.API_STR}/build_lists/", json=bl_data1)
    assert response1.status_code == 200
    bl_id1 = response1.json()["id"]

    response2 = client.post(f"{settings.API_STR}/build_lists/", json=bl_data2)
    assert response2.status_code == 200
    bl_id2 = response2.json()["id"]

    client.cookies.clear() # Endpoint is public
    response = client.get(f"{settings.API_STR}/build_lists/car/{car_id}")
    assert response.status_code == 200, response.text
    
    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 2
    
    retrieved_bl_ids = {bl["id"] for bl in build_lists}
    assert bl_id1 in retrieved_bl_ids
    assert bl_id2 in retrieved_bl_ids

    for bl in build_lists:
        assert bl["car_id"] == car_id
        if bl["id"] == bl_id1:
            assert bl["name"] == bl_data1["name"]
        elif bl["id"] == bl_id2:
            assert bl["name"] == bl_data2["name"]
            assert bl["description"] == bl_data2["description"]


def test_read_build_lists_by_car_empty(client: TestClient, db_session: Session):
    user_id = create_and_login_user(client, "owner_for_bl_by_car_empty")
    car_id = create_car_for_user_cookie_auth(client, "Subaru", "BRZ")

    # No build lists created for this car

    client.cookies.clear() # Endpoint is public
    response = client.get(f"{settings.API_STR}/build_lists/car/{car_id}")
    assert response.status_code == 200, response.text
    
    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 0


def test_read_build_lists_by_car_car_not_found(client: TestClient, db_session: Session):
    non_existent_car_id = 999888
    
    client.cookies.clear() # Endpoint is public
    response = client.get(f"{settings.API_STR}/build_lists/car/{non_existent_car_id}")
    assert response.status_code == 200, response.text # Endpoint returns 200 and empty list
    
    build_lists = response.json()
    assert isinstance(build_lists, list)
    assert len(build_lists) == 0
