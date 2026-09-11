from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user


# Helper function to create and login an admin user
def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_car_test_{username_suffix}"
    email = f"admin_car_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
    admin_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    # Log in and get token
    token = login_user(client, username)

    return admin_user.__dict__, token


# Helper function to create a user and log them in (returns user_id and token)
def create_and_login_user(
    client: TestClient, username_suffix: str, db_session: Any | None = None
) -> tuple[int, str]:  # Returns (user_id, token)
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
        user_info = response.json()
        user_id = user_info["id"]

        # Manually verify the email for testing purposes
        if db_session:
            user = UserRepository().get_by_username(username)
            if user:
                UserRepository().update(user.id, email_verified=True)
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()  # Raise an exception for other errors

    token = login_user(client, username, password)

    if user_id == -1:  # If user existed and was not created, fetch ID
        headers = auth_headers(token)
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(f"Could not retrieve user_id for existing user {username} via /users/me.")

    if user_id == -1:
        raise Exception(f"User ID for {username} could not be determined.")
    return (user_id, token)


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


# --- Test Cases ---


def test_admin_create_car_removed(client: TestClient, db_session: Any) -> None:
    """Cars are seeded from backend source; admin create endpoint is removed."""
    _, admin_token = create_and_login_admin_user(client, db_session, "creator")
    headers = get_auth_headers(admin_token)
    car_data = {
        "make": "Honda",
        "model": "Civic",
        "generation_name": "10th Gen",
        "start_year": 2016,
        "end_year": 2021,
    }
    response = client.post(f"{settings.API_STR}/car-generations/admin/cars", json=car_data, headers=headers)
    assert response.status_code in (404, 405)  # Endpoint removed (404 path not found or 405 method not allowed)


def test_read_car_success(client: TestClient, db_session: Any) -> None:
    """Test reading a car (public endpoint)."""
    car = create_car_in_db(db_session, "Mazda", "3", "4th Gen", 2019, 2023)

    # Reading a car is public, no auth needed
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/car-generations/{car['id']}")
    assert response.status_code == 200, response.text
    read_car_data = response.json()
    assert read_car_data["id"] == str(car["id"])
    assert read_car_data["car_make_name"] == car["make"]
    assert read_car_data["car_model_name"] == car["model"]
    assert read_car_data["generation_name"] == car["generation_name"]
    # Cars no longer have user_id
    assert "user_id" not in read_car_data


def test_read_car_not_found(client: TestClient, db_session: Any) -> None:
    """Test reading a non-existent car."""
    response = client.get(f"{settings.API_STR}/car-generations/{INVALID_UUID_STR}")  # Non-existent ID
    assert response.status_code == 404


def test_get_cars_by_make_success(client: TestClient, db_session: Any) -> None:
    """Test getting cars by make."""
    # Create cars in DB (cars are seeded from backend source; tests use create_car_in_db)
    create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)
    create_car_in_db(db_session, "Toyota", "Corolla", "12th Gen", 2019, 2022)
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)

    client.cookies.clear()

    # Get cars by make "Toyota"
    response = client.get(f"{settings.API_STR}/car-generations/car-makes/Toyota")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert isinstance(cars, list)
    assert len(cars) >= 2

    for car in cars:
        assert car["car_make_name"] == "Toyota"


def test_get_cars_by_make_no_results(client: TestClient, db_session: Any) -> None:
    """Test getting cars by make with no results."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/car-generations/car-makes/NonExistentMake")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert isinstance(cars, list)
    assert len(cars) == 0


def test_get_cars_by_make_model_success(client: TestClient, db_session: Any) -> None:
    """Test getting cars by make and model."""
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_in_db(db_session, "Honda", "Civic", "11th Gen", 2022, 2024)
    create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

    client.cookies.clear()

    # Get Honda Civics
    response = client.get(f"{settings.API_STR}/car-generations/car-makes/Honda/car-models/Civic")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert isinstance(cars, list)
    assert len(cars) >= 2

    for car in cars:
        assert car["car_make_name"] == "Honda"
        assert car["car_model_name"] == "Civic"


def test_search_cars_by_make(client: TestClient, db_session: Any) -> None:
    """Test searching cars by make."""
    create_car_in_db(db_session, "Tesla", "Model 3", "1st Gen", 2017, 2023)
    create_car_in_db(db_session, "Toyota", "Corolla", "12th Gen", 2019, 2022)

    client.cookies.clear()

    # Search for "Tesla"
    response = client.get(f"{settings.API_STR}/car-generations/search?q=Tesla")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert isinstance(cars, list)
    assert len(cars) >= 1

    # Verify Tesla cars are in results
    tesla_found = any(car["car_make_name"] == "Tesla" for car in cars)
    assert tesla_found


def test_search_cars_by_model(client: TestClient, db_session: Any) -> None:
    """Test searching cars by model."""
    create_car_in_db(db_session, "BMW", "M3", "G80", 2021, 2024)
    create_car_in_db(db_session, "BMW", "M4", "G82", 2021, 2024)

    client.cookies.clear()

    # Search for "M3"
    response = client.get(f"{settings.API_STR}/car-generations/search?q=M3")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert len(cars) >= 1

    # Verify M3 is in results
    m3_found = any(car["car_model_name"] == "M3" for car in cars)
    assert m3_found


def test_search_cars_no_query(client: TestClient, db_session: Any) -> None:
    """Test search without query parameter."""
    client.cookies.clear()

    # The search endpoint requires a 'q' parameter
    response = client.get(f"{settings.API_STR}/car-generations/search")
    assert response.status_code == 422  # Validation error for missing required param


def test_search_cars_no_results(client: TestClient, db_session: Any) -> None:
    """Test search with no matching results."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/car-generations/search?q=NonExistentCarBrandXYZ123")
    assert response.status_code == 200, response.text

    cars: list[Any] = response.json()["items"]
    assert isinstance(cars, list)
    assert len(cars) == 0


def test_get_car_make_stats(client: TestClient, db_session: Any) -> None:
    """Test getting car make statistics."""
    create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)
    create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

    client.cookies.clear()

    # Get make statistics
    response = client.get(f"{settings.API_STR}/car-generations/stats/car-makes")
    assert response.status_code == 200

    stats = response.json()
    assert isinstance(stats, dict)
    # Should have at least Honda and Toyota
    assert "Honda" in stats or "Toyota" in stats


def test_count_makes(client: TestClient, db_session: Any) -> None:
    """Test counting makes (Make entities)."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/car-generations/car-makes/count")
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0


def test_count_car_models(client: TestClient, db_session: Any) -> None:
    """Test counting car models (CarModel entities)."""
    client.cookies.clear()

    response = client.get(f"{settings.API_STR}/car-generations/car-models/count")
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0


def test_admin_car_write_endpoints_removed(client: TestClient, db_session: Any) -> None:
    """Cars are seeded from backend source; admin write endpoints are removed (405)."""
    car = create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)
    _, admin_token = create_and_login_admin_user(client, db_session, "write_removed")
    headers = get_auth_headers(admin_token)
    # PUT and DELETE should return 405
    response = client.put(
        f"{settings.API_STR}/car-generations/admin/cars/{car['id']}",
        json={"model": "Civic Si"},
        headers=headers,
    )
    assert response.status_code in (404, 405)
    response = client.delete(f"{settings.API_STR}/car-generations/admin/cars/{car['id']}", headers=headers)
    assert response.status_code in (404, 405)
    response = client.delete(f"{settings.API_STR}/car-generations/admin/cars", headers=headers)
    assert response.status_code in (404, 405)


def test_count_cars_success(client: TestClient, db_session: Any) -> None:
    """Test counting cars."""
    response = client.get(f"{settings.API_STR}/car-generations/count")
    assert response.status_code == 200
    initial_data = response.json()
    assert "count" in initial_data
    initial_count = initial_data["count"]
    assert isinstance(initial_count, int)
    assert initial_count >= 0

    car = create_car_in_db(db_session, "Tesla", "Model 3", "1st Gen", 2017, 2023)
    response = client.get(f"{settings.API_STR}/car-generations/count")
    assert response.status_code == 200
    assert response.json()["count"] == initial_count + 1

    # Remove car via DB (no delete API)
    from app.db.dynamo.catalog import CarGenerationRepository

    generations = CarGenerationRepository()
    generations.delete_unique(generations.get_or_raise(str(car["id"])))
    response = client.get(f"{settings.API_STR}/car-generations/count")
    assert response.status_code == 200
    assert response.json()["count"] == initial_count


def test_count_cars_public_endpoint(client: TestClient, db_session: Any) -> None:
    """Test that counting cars works without authentication."""
    # Count cars (public endpoint, no auth required)
    client.cookies.clear()
    response = client.get(f"{settings.API_STR}/car-generations/count")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0
