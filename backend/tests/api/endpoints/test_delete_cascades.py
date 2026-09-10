"""What the two synchronous delete cascades remove today.

Row 23 of `docs/migration/split-plan.md` deliberately leaves both deletes hard:
`_delete_user_everywhere` in `app/api/endpoints/users.py` (seam 1) and
`PartService.purge` plus `purge_related_rows_for_parts` in
`app/api/services/part_service.py` (seam 2) still fan out across every related
table inside the request. Rows 30 and 28 replace that fan-out with a tombstone
write and a stream consumer draining a work queue.

Neither cascade had a test pinning what it removes, which is a bad position from
which to make it asynchronous: the async version is correct only if it ends in
the same state, and nothing recorded what that state was. These tests are that
record. They are written against the current synchronous behaviour on purpose,
so rows 28 and 30 have a reference to diff against rather than a description.
"""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from uuid6 import uuid7

from app.api.dependencies.auth import get_password_hash
from app.api.dependencies.repositories import get_repositories
from app.core.config import settings
from app.db.dynamo.catalog import Category, PartManufacturer
from app.db.dynamo.moderation import Report, Vote
from app.db.dynamo.users import User, UserRepository
from tests.conftest import create_car_in_db, login_user


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(name: str) -> User:
    return UserRepository().create_user(
        User(
            username=name,
            email=f"{name}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
        )
    )


def _make_part(client: TestClient, headers: dict[str, str], category: Category, manufacturer: PartManufacturer) -> Any:
    response = client.post(
        f"{settings.API_STR}/parts/",
        json={
            "name": _unique("part"),
            "description": "A part",
            "category_id": str(category.id),
            "part_manufacturer_id": str(manufacturer.id),
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


class TestPartPurgeCascade:
    """Seam 2. `purge_related_rows_for_parts` names four tables; assert all four."""

    def test_purging_a_part_removes_its_votes_reports_usages_and_alerts(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
        dynamo_tables: Any,
    ) -> None:
        from app.api.services.part_service import purge_related_rows_for_parts

        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)
        part_id = UUID(part["id"])

        car = create_car_in_db(db_session, "Subaru", "WRX", "VA", 2015, 2021)
        build_list = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        ).json()
        added = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json={"quantity": 1, "notes": "n"},
            headers=headers,
        )
        assert added.status_code in (200, 201)

        repos = get_repositories()
        voter = _make_user(_unique("voter"))
        repos.votes.create(Vote(user_id=voter.id, entity_type="part", entity_id=part_id, vote_type="upvote"))
        reporter = _make_user(_unique("reporter"))
        repos.reports.create(Report(user_id=reporter.id, entity_type="part", entity_id=part_id, reason="spam"))

        assert repos.votes.for_entities("part", [part_id])[part_id]
        assert repos.build_list_parts.query_all("part_id-index", part_id)

        purge_related_rows_for_parts([part_id])

        assert repos.votes.for_entities("part", [part_id]).get(part_id, []) == [], "votes must not survive"
        assert repos.build_list_parts.query_all("part_id-index", part_id) == [], "build list usages must be dropped"
        remaining_reports = [r for r in repos.reports.scan_all() if r.entity_id == part_id]
        assert remaining_reports == [], "reports on a purged part must not survive"

    def test_deleting_a_part_through_the_api_removes_it_from_build_lists(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
        dynamo_tables: Any,
    ) -> None:
        """The whole point of seam 2: no hole is left where the part was."""
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)
        car = create_car_in_db(db_session, "Toyota", "GR86", "ZN8", 2022, 2025)
        build_list = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl2"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        ).json()
        client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json={"quantity": 1, "notes": "n"},
            headers=headers,
        )

        url = f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts"
        before = client.get(url, headers=headers)
        assert before.status_code == 200
        assert len(before.json()) == 1

        deleted = client.delete(f"{settings.API_STR}/parts/{part['id']}", headers=headers)
        assert deleted.status_code == 200

        after = client.get(url, headers=headers)
        assert after.status_code == 200
        assert after.json() == [], "a hard deleted part leaves no row behind"


class TestUserDeleteCascade:
    """Seam 1. `_delete_user_everywhere` fans out before it releases the uniques."""

    def test_deleting_a_user_purges_their_parts_build_lists_and_unique_reservations(
        self,
        client: TestClient,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
        dynamo_tables: Any,
    ) -> None:
        name = _unique("doomed")
        user = _make_user(name)
        headers = _headers(login_user(client, name))

        part = _make_part(client, headers, test_category, test_part_manufacturer)
        car = create_car_in_db(db_session, "Nissan", "370Z", "Z34", 2009, 2020)
        build_list = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl3"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        ).json()

        repos = get_repositories()
        assert repos.parts.get(part["id"]) is not None
        assert repos.build_lists.get(build_list["id"]) is not None

        response = client.delete(f"{settings.API_STR}/users/{user.id}", headers=headers)
        assert response.status_code == 200

        assert repos.users.get(user.id) is None, "the user row itself is hard deleted"
        assert repos.parts.get(part["id"]) is None, "their parts are purged, not orphaned"
        assert repos.build_lists.get(build_list["id"]) is None, "their build lists are purged"

        # The uniqueness reservations are released in the same transaction, so the
        # username and email are immediately reusable. Row 30 has to keep doing
        # this at tombstone time or the pair leaks forever.
        reborn = _make_user(name)
        assert reborn.id != user.id

    def test_deleting_a_user_removes_their_votes_and_reports(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        dynamo_tables: Any,
    ) -> None:
        owner_headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, owner_headers, test_category, test_part_manufacturer)
        part_id = UUID(part["id"])

        name = _unique("moderated")
        user = _make_user(name)
        headers = _headers(login_user(client, name))

        repos = get_repositories()
        repos.votes.create(Vote(user_id=user.id, entity_type="part", entity_id=part_id, vote_type="upvote"))
        repos.reports.create(Report(user_id=user.id, entity_type="part", entity_id=uuid7(), reason="spam"))

        assert repos.votes.for_entities("part", [part_id])[part_id]

        response = client.delete(f"{settings.API_STR}/users/{user.id}", headers=headers)
        assert response.status_code == 200

        assert [v for v in repos.votes.for_entities("part", [part_id]).get(part_id, []) if v.user_id == user.id] == []
        assert [r for r in repos.reports.scan_all() if r.user_id == user.id] == []
