import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import auth_headers, create_car_in_db, login_user


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_token(client: TestClient, username: str, password: str = "testpassword") -> str:
    """The credential for `username`, for use with `auth_headers`.

    A thin alias for `login_user` in `tests/conftest.py`, kept because this
    module's tests call it by this name. Row 13 of `docs/identity-adoption.md`
    deleted `POST /api/auth/token`, so what comes back is an identity request
    context rather than a bearer token; `password` is accepted and ignored.
    """
    return login_user(client, username, password)


def get_auth_headers(token: str) -> Dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[Dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
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


class TestSearch:
    """Test cases for search endpoint."""

    def test_search_all_public_access(self, client: TestClient) -> None:
        """Test that search endpoint is publicly accessible."""
        response = client.get(f"{settings.API_STR}/search/?q=test")
        assert response.status_code == 200
        data = response.json()
        assert "build_lists" in data
        assert "users" in data
        assert "parts" in data
        assert "query" in data

    def test_search_build_lists_by_name(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test searching build lists by name."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("searchable_build_list")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search for the build list
        search_term = build_list_name.split("_")[0]  # Use part of the name
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["items"]) > 0
        assert any(build_list_name in bl["name"] for bl in data["build_lists"]["items"])

    def test_search_build_lists_by_car_make(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test searching build lists by associated car make."""
        # Create a car in DB (cars are seeded from backend source; tests use create_car_in_db)
        car = create_car_in_db(db_session, "Honda", "Civic")

        # Create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("honda_build_list"),
            "description": "A Honda build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search for "Honda"
        response = client.get(f"{settings.API_STR}/search/?q=Honda")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["items"]) > 0
        # Verify the build list was found (search by car make works)
        # BuildListRead schema only includes car_id, not the full car object
        assert any(bl.get("car_id") == str(car["id"]) for bl in data["build_lists"]["items"])

    def test_search_users_by_username(self, client: TestClient, test_user: DBUser) -> None:
        """Test searching users by username."""
        # Search for the test user's username
        search_term = test_user.username.split("_")[0]  # Use part of the username
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]["items"]) > 0
        assert any(search_term.lower() in u["username"].lower() for u in data["users"]["items"])

    def test_search_users_by_email(self, client: TestClient, test_user: DBUser) -> None:
        """Test searching users by email."""
        # Search for part of the email
        search_term = test_user.email.split("@")[0]  # Use part before @
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        # Note: email might not be in PublicUserRead, so we check username matches
        assert len(data["users"]["items"]) > 0

    def test_search_parts_by_name(
        self, client: TestClient, test_user: DBUser, test_category, test_part_manufacturer, db_session: Any
    ) -> None:
        """Test searching global parts by name."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a global part
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        part_name = get_unique_name("searchable_part")
        part_data = {
            "name": part_name,
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Search for the part
        search_term = part_name.split("_")[0]  # Use part of the name
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["parts"]["items"]) > 0
        assert any(search_term.lower() in gp["name"].lower() for gp in data["parts"]["items"])

    def test_search_parts_by_part_manufacturer(
        self, client: TestClient, test_user: DBUser, test_category, db_session: Any
    ) -> None:
        """Search by manufacturer name surfaces parts for that manufacturer."""
        from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
        from app.db.dynamo.catalog import PartManufacturerRepository

        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        curated = PartManufacturerRepository().create_unique(
            DBPartManufacturer(
                name=get_unique_name("ACME"),
                description="ACME part_manufacturer",
                is_active=True,
            )
        )
        part_manufacturer_id = str(curated.id)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": part_manufacturer_id,
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/search/?q={curated.name}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["parts"]["items"]) > 0
        assert any(gp.get("part_manufacturer_id") == part_manufacturer_id for gp in data["parts"]["items"])

    def test_search_empty_query(self, client: TestClient) -> None:
        """Test search with empty query."""
        response = client.get(f"{settings.API_STR}/search/?q=")
        assert response.status_code == 200
        data = response.json()
        assert data["build_lists"]["items"] == []
        assert data["users"]["items"] == []
        assert data["parts"]["items"] == []
        assert data["query"] == ""

    def test_search_no_results(self, client: TestClient) -> None:
        """Test search with query that returns no results."""
        response = client.get(f"{settings.API_STR}/search/?q=nonexistentxyz123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["items"]) == 0
        assert len(data["users"]["items"]) == 0
        assert len(data["parts"]["items"]) == 0

    def test_search_case_insensitive(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that search is case-insensitive."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list with lowercase name
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("lowercase_build_list")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with uppercase
        search_term = build_list_name.upper()
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        # Should find results (case-insensitive)
        assert len(data["build_lists"]["items"]) > 0

    def test_search_with_pagination(self, client: TestClient, premium_test_user: DBUser, db_session: Any) -> None:
        """Test search with pagination parameters."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Use premium user so we can create multiple build lists
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)
        base_name = get_unique_name("paginated")
        for i in range(5):
            build_list_data = {
                "name": f"{base_name}_{i}",
                "description": f"Build list {i}",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200

        # Search with pagination
        response = client.get(f"{settings.API_STR}/search/?q={base_name}&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["items"]) == 2
        assert data["build_lists"]["has_next"] is True
        assert data["build_lists"]["next_cursor"]

        response = client.get(
            f"{settings.API_STR}/search/?q={base_name}&limit=2"
            f"&build_lists_cursor={data['build_lists']['next_cursor']}"
        )
        assert response.status_code == 200
        second = response.json()
        first_ids = {bl["id"] for bl in data["build_lists"]["items"]}
        assert all(bl["id"] not in first_ids for bl in second["build_lists"]["items"])

    def test_search_partial_match(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that search supports partial matches."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list with a specific name
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("partial_match_test")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with partial match (just "partial")
        response = client.get(f"{settings.API_STR}/search/?q=partial")
        assert response.status_code == 200
        data = response.json()
        # Should find the build list with partial match
        assert len(data["build_lists"]["items"]) > 0

    def test_search_sql_injection_attempt(self, client: TestClient) -> None:
        """Test that search handles SQL injection attempts safely."""
        # Common SQL injection patterns
        sql_injection_attempts = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "1' UNION SELECT NULL--",
        ]

        for attempt in sql_injection_attempts:
            response = client.get(f"{settings.API_STR}/search/?q={attempt}")
            # Should not crash, return 200 with empty or safe results
            assert response.status_code == 200
            data = response.json()
            assert "build_lists" in data
            assert "users" in data
            assert "parts" in data

    def test_search_special_characters(self, client: TestClient) -> None:
        """Test search with special characters."""
        special_chars = ["%", "_", "@", "#", "$", "&", "*", "(", ")", "[", "]", "{", "}", "|", "\\"]

        for char in special_chars:
            response = client.get(f"{settings.API_STR}/search/?q={char}")
            assert response.status_code == 200
            data = response.json()
            assert "build_lists" in data
            assert "users" in data
            assert "parts" in data

    def test_search_unicode_characters(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test search with unicode and emoji characters."""
        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        # Create a build list with unicode characters
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("unicode_test_🚗")
        build_list_data = {
            "name": build_list_name,
            "description": "Test with unicode: 测试 🚗",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with unicode
        response = client.get(f"{settings.API_STR}/search/?q=🚗")
        assert response.status_code == 200
        data = response.json()
        # Should handle unicode gracefully
        assert "build_lists" in data

    def test_search_very_long_query(self, client: TestClient) -> None:
        """Test search with very long query string."""
        # Create a very long query (1000 characters)
        long_query = "a" * 1000
        response = client.get(f"{settings.API_STR}/search/?q={long_query}")
        # Should handle gracefully, not crash
        assert response.status_code == 200
        data = response.json()
        assert "build_lists" in data
        assert "users" in data
        assert "parts" in data

    def test_search_whitespace_only(self, client: TestClient) -> None:
        """Test search with whitespace-only query."""
        from urllib.parse import quote

        # Test with spaces, tabs, newlines (URL encode them)
        whitespace_queries = ["   ", "\t\t", "\n\n", "   \t\n   "]

        for query in whitespace_queries:
            encoded_query = quote(query)
            response = client.get(f"{settings.API_STR}/search/?q={encoded_query}")
            assert response.status_code == 200
            data = response.json()
            # Should return empty results or handle gracefully
            assert "build_lists" in data
            assert "users" in data
            assert "parts" in data

    def test_search_pagination_cursor_exhausts(
        self, client: TestClient, premium_test_user: DBUser, db_session: Any
    ) -> None:
        """Following build list cursors ends with an empty next_cursor."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        base_name = get_unique_name("test_build_list")
        for i in range(3):
            build_list_data = {
                "name": f"{base_name}_{i}",
                "description": "A test build list",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200

        seen: list[str] = []
        cursor = None
        for _ in range(10):
            url = f"{settings.API_STR}/search/?q={base_name}&limit=1"
            if cursor:
                url += f"&build_lists_cursor={cursor}"
            response = client.get(url)
            assert response.status_code == 200
            page = response.json()["build_lists"]
            seen.extend(bl["id"] for bl in page["items"])
            cursor = page["next_cursor"]
            if not page["has_next"]:
                assert cursor is None
                break
        else:
            raise AssertionError("cursor never exhausted")
        assert len(seen) == 3
        assert len(set(seen)) == 3

    def test_search_pagination_limit_zero(self, client: TestClient) -> None:
        """Test search with limit=0 (should validate and reject)."""
        response = client.get(f"{settings.API_STR}/search/?q=test&limit=0")
        # Should validate and reject (400 or 422)
        assert response.status_code in [400, 422]

    def test_search_pagination_very_large_limit(self, client: TestClient) -> None:
        """Test search with very large limit value (should respect max limit)."""
        response = client.get(f"{settings.API_STR}/search/?q=test&limit=10000")
        # Endpoint validates limit with le=100, so 10000 should be rejected with 422
        assert response.status_code == 422
        data = response.json()
        # When validation fails, response is an error format, not search results
        assert "message" in data or "detail" in data

    def test_search_invalid_cursor(self, client: TestClient) -> None:
        """Test search with a malformed cursor."""
        response = client.get(f"{settings.API_STR}/search/?q=test&build_lists_cursor=not-a-cursor&limit=10")
        assert response.status_code == 400

    def test_search_case_insensitive_matching(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that search is case-insensitive."""
        # Create a build list with mixed case
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        car = create_car_in_db(db_session)

        build_list_name = get_unique_name("MiXeDcAsE")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with different case variations
        for query in ["mixedcase", "MIXEDCASE", "MixedCase", "MiXeDcAsE"]:
            response = client.get(f"{settings.API_STR}/search/?q={query}")
            assert response.status_code == 200
            data = response.json()
            # Should find the build list regardless of case
            found = any(item.get("name") == build_list_name for item in data["build_lists"]["items"])
            assert found, f"Search with '{query}' should find '{build_list_name}'"
