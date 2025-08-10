from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.core.config import settings


# Helper function to create a user and log them in (sets cookie on client)
# This function is similar to the one in test_build_lists.py
def create_and_login_user(
    client: TestClient, username_suffix: str
) -> int:  # Returns user_id
    username = f"car_test_user_{username_suffix}"
    email = f"car_test_user_{username_suffix}@example.com"
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
        response.raise_for_status()  # Raise an exception for other errors

    login_data = {"username": username, "password": password}
    token_response = client.post(
        f"{settings.API_STR}/auth/token", data=login_data
    )  # Changed
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    if user_id == -1:  # If user existed and was not created, fetch ID
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


# --- Test Cases ---


def test_create_car_success(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "creator_car")  # Logs in user, client gets cookie

    car_data = {"make": "Honda", "model": "Civic", "year": 2022, "trim": "Sport"}
    response = client.post(
        f"{settings.API_STR}/cars/", json=car_data
    )  # Cookie sent automatically
    assert response.status_code == 200, response.text
    created_car = response.json()
    assert created_car["make"] == car_data["make"]
    assert created_car["model"] == car_data["model"]
    assert "id" in created_car
    assert "user_id" in created_car  # Assuming user_id is part of CarRead


def test_create_car_unauthenticated(client: TestClient, db_session: Session):
    client.cookies.clear()  # Ensure no auth cookie
    car_data = {"make": "Toyota", "model": "Corolla", "year": 2021}
    response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert response.status_code == 401  # Expect unauthorized


def test_read_car_success(client: TestClient, db_session: Session):
    user_id = create_and_login_user(client, "reader_car")
    car_data_payload = {"make": "Mazda", "model": "3", "year": 2020}
    create_response = client.post(f"{settings.API_STR}/cars/", json=car_data_payload)
    assert create_response.status_code == 200
    car_id = create_response.json()["id"]

    # Reading a car might be public or require auth depending on your endpoint logic.
    # If public, clearing cookies is fine. If it requires auth (e.g. to see only own cars), don't clear.
    # Assuming public read for this example as per your `read_car` endpoint.
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/{car_id}")
    assert response.status_code == 200, response.text
    read_car_data = response.json()
    assert read_car_data["id"] == car_id
    assert read_car_data["make"] == car_data_payload["make"]
    assert read_car_data["user_id"] == user_id


def test_read_car_not_found(client: TestClient, db_session: Session):
    response = client.get(f"{settings.API_STR}/cars/999999")  # Non-existent ID
    assert response.status_code == 404


def test_update_own_car_success(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "updater_car")  # Logs in, client gets cookie

    initial_car_data = {"make": "Nissan", "model": "Altima", "year": 2019}
    create_response = client.post(f"{settings.API_STR}/cars/", json=initial_car_data)
    assert create_response.status_code == 200
    car_id = create_response.json()["id"]

    update_payload = {"model": "Maxima", "year": 2020}
    response = client.put(
        f"{settings.API_STR}/cars/{car_id}", json=update_payload
    )  # Cookie sent
    assert response.status_code == 200, response.text
    updated_car = response.json()
    assert updated_car["model"] == update_payload["model"]
    assert updated_car["year"] == update_payload["year"]
    assert updated_car["make"] == initial_car_data["make"]  # Make should be unchanged


def test_update_car_unauthenticated(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "owner_for_update_unauth_car")
    car_data = {"make": "Subaru", "model": "WRX", "year": 2021}
    create_response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert create_response.status_code == 200
    car_id = create_response.json()["id"]

    client.cookies.clear()  # Clear cookie for unauthenticated request
    update_payload = {"year": 2022}
    response = client.put(f"{settings.API_STR}/cars/{car_id}", json=update_payload)
    assert response.status_code == 401


def test_update_other_users_car_forbidden(client: TestClient, db_session: Session):
    # User A creates a car
    _ = create_and_login_user(client, "userA_car_owner")  # Client has User A's cookie
    car_data_a = {"make": "Ford", "model": "Focus", "year": 2018}
    create_response_a = client.post(f"{settings.API_STR}/cars/", json=car_data_a)
    assert create_response_a.status_code == 200
    car_id_a = create_response_a.json()["id"]

    # User B logs in (client now has User B's cookie)
    client.cookies.clear()
    _ = create_and_login_user(client, "userB_car_attacker")

    update_payload = {"year": 2023}
    response = client.put(
        f"{settings.API_STR}/cars/{car_id_a}", json=update_payload
    )  # User B tries to update User A's car
    assert response.status_code == 403  # Expect forbidden
    assert response.json()["detail"] == "Not authorized to update this car"


def test_delete_own_car_success(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "deleter_car")  # Logs in, client gets cookie
    car_data = {"make": "Kia", "model": "Stinger", "year": 2020}
    create_response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert create_response.status_code == 200
    car_id = create_response.json()["id"]

    response = client.delete(f"{settings.API_STR}/cars/{car_id}")  # Cookie sent
    assert response.status_code == 200, response.text
    deleted_car_data = response.json()
    assert deleted_car_data["id"] == car_id

    # Verify car is deleted
    client.cookies.clear()  # Clear cookie to ensure public 404 if car is gone
    get_response = client.get(f"{settings.API_STR}/cars/{car_id}")
    assert get_response.status_code == 404


def test_delete_car_unauthenticated(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "owner_for_delete_unauth_car")
    car_data = {"make": "Hyundai", "model": "Elantra", "year": 2019}
    create_response = client.post(f"{settings.API_STR}/cars/", json=car_data)
    assert create_response.status_code == 200
    car_id = create_response.json()["id"]

    client.cookies.clear()  # Clear cookie
    response = client.delete(f"{settings.API_STR}/cars/{car_id}")
    assert response.status_code == 401


def test_delete_other_users_car_forbidden(client: TestClient, db_session: Session):
    # User A creates a car
    _ = create_and_login_user(
        client, "userA_car_owner_del"
    )  # Client has User A's cookie
    car_data_a = {"make": "BMW", "model": "M3", "year": 2021}
    create_response_a = client.post(f"{settings.API_STR}/cars/", json=car_data_a)
    assert create_response_a.status_code == 200
    car_id_a = create_response_a.json()["id"]

    # User B logs in
    client.cookies.clear()
    _ = create_and_login_user(
        client, "userB_car_deleter_attacker"
    )  # Client has User B's cookie

    response = client.delete(
        f"{settings.API_STR}/cars/{car_id_a}"
    )  # User B tries to delete User A's car
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this car"


def test_update_car_not_found(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "updater_car_notfound")  # Sets cookie
    update_payload = {"make": "NonExistent"}
    response = client.put(
        f"{settings.API_STR}/cars/888888", json=update_payload
    )  # Uses cookie
    assert response.status_code == 404
    assert response.json()["detail"] == "Car not found"


def test_delete_car_not_found(client: TestClient, db_session: Session):
    _ = create_and_login_user(client, "deleter_car_notfound")  # Sets cookie
    response = client.delete(
        f"{settings.API_STR}/cars/777777"
    )  # Uses cookie, Non-existent ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Car not found"


# --- Tests for read_cars_by_user ---


def test_read_cars_by_user_success(client: TestClient, db_session: Session):
    # Create a user and log them in to create cars
    user_id = create_and_login_user(client, "car_owner_for_list")

    # Create a couple of cars for this user
    car_data1 = {"make": "Toyota", "model": "Supra", "year": 1998}
    car_data2 = {"make": "Nissan", "model": "Skyline R34", "year": 1999, "trim": "GT-R"}

    response1 = client.post(f"{settings.API_STR}/cars/", json=car_data1)  # Uses cookie
    assert response1.status_code == 200
    car_id1 = response1.json()["id"]

    response2 = client.post(f"{settings.API_STR}/cars/", json=car_data2)  # Uses cookie
    assert response2.status_code == 200
    car_id2 = response2.json()["id"]

    # Clear cookies as the endpoint is public
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/user/{user_id}")
    assert response.status_code == 200, response.text

    cars_list = response.json()
    assert isinstance(cars_list, list)
    assert len(cars_list) == 2

    retrieved_car_ids = {car["id"] for car in cars_list}
    assert car_id1 in retrieved_car_ids
    assert car_id2 in retrieved_car_ids

    for car in cars_list:
        assert car["user_id"] == user_id
        if car["id"] == car_id1:
            assert car["make"] == car_data1["make"]
            assert car["model"] == car_data1["model"]
        elif car["id"] == car_id2:
            assert car["make"] == car_data2["make"]
            assert car["model"] == car_data2["model"]
            assert car["trim"] == car_data2["trim"]


def test_read_cars_by_user_no_cars(client: TestClient, db_session: Session):
    # Create a user but no cars for them
    user_id = create_and_login_user(client, "car_owner_no_cars")

    # Clear cookies as the endpoint is public
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/user/{user_id}")
    assert response.status_code == 200, response.text

    cars_list = response.json()
    assert isinstance(cars_list, list)
    assert len(cars_list) == 0


def test_read_cars_by_user_non_existent_user(client: TestClient, db_session: Session):
    non_existent_user_id = 9999999

    # Clear cookies as the endpoint is public
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/cars/user/{non_existent_user_id}")
    assert (
        response.status_code == 200
    ), response.text  # Endpoint returns 200 and empty list

    cars_list = response.json()
    assert isinstance(cars_list, list)
    assert len(cars_list) == 0
