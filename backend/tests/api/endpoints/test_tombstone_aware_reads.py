"""Tombstone-aware reads across the domains row 23 touches.

Row 23 of `docs/migration/split-plan.md` adds the `deleted` / `deleted_at` pair
and the reads that honour it. Nothing writes a tombstone yet, so every test here
writes one directly through the repository, which is the point: the read paths
have to be correct before rows 28 and 30 make the delete asynchronous.

The split plan's own framing of this row ("build-lists, build-logs, moderation
and vehicles all read `users` to attach an author") did not survive contact with
the code. `build-lists` and `vehicles` read no users at all, and the real surface
is the one covered below: the part join in build-lists, the author join in
build-logs, the user and part reads in moderation, and search in vehicles.
"""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from uuid6 import uuid7

from app.core.config import settings
from app.db.dynamo.build_logs import BuildLog, BuildLogPost, BuildLogPostRepository, BuildLogRepository
from app.db.dynamo.catalog import Category, Part, PartManufacturer, PartRepository
from app.db.dynamo.moderation import Report, ReportRepository, Vote, VoteRepository
from app.db.dynamo.users import User, UserRepository
from tests.conftest import auth_headers, create_car_in_db, login_user


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _headers(token: str) -> dict[str, str]:
    return auth_headers(token)


def _tombstone_part(part_id: UUID) -> None:
    """Write the tombstone rows 28 will write, so the read paths can be tested."""
    PartRepository().update(str(part_id), deleted=True, deleted_at="2026-09-08T00:00:00+00:00")


def _tombstone_user(user_id: UUID) -> None:
    """Write the tombstone row 30 will write."""
    UserRepository().update(user_id, deleted=True, deleted_at="2026-09-08T00:00:00+00:00")


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


class TestBuildListsDropsTombstonedParts:
    """Seam 2's read consequence: a purged part must not render a hole."""

    def _build_list_with_part(
        self,
        client: TestClient,
        headers: dict[str, str],
        db_session: Any,
        category: Category,
        manufacturer: PartManufacturer,
    ) -> tuple[Any, Any]:
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        )
        assert response.status_code == 200
        build_list = response.json()

        part = _make_part(client, headers, category, manufacturer)
        added = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json={"quantity": 2, "notes": "n"},
            headers=headers,
        )
        assert added.status_code == 200
        return build_list, part

    def test_a_tombstoned_part_is_dropped_from_the_join(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        token = login_user(client, test_user.username)
        headers = _headers(token)
        build_list, part = self._build_list_with_part(
            client, headers, db_session, test_category, test_part_manufacturer
        )

        listed = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        _tombstone_part(UUID(part["id"]))

        after = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts", headers=headers)
        assert after.status_code == 200
        assert after.json() == [], "a tombstoned part must drop the row, not render a hole"

    def test_a_hard_deleted_part_is_dropped_from_the_join(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Regression for the pre-existing, previously untested drop.

        `build_list_parts.py` has always filtered rows whose part is missing
        from the table. Row 23 adds the tombstone case beside it, so this locks
        the hard-delete case that was carrying the behaviour on its own.
        """
        token = login_user(client, test_user.username)
        headers = _headers(token)
        build_list, part = self._build_list_with_part(
            client, headers, db_session, test_category, test_part_manufacturer
        )

        deleted = client.delete(f"{settings.API_STR}/parts/{part['id']}", headers=headers)
        assert deleted.status_code == 200

        after = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts", headers=headers)
        assert after.status_code == 200
        assert after.json() == []

    def test_a_tombstoned_part_cannot_be_added_to_a_build_list(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        token = login_user(client, test_user.username)
        headers = _headers(token)
        car = create_car_in_db(db_session, "Honda", "Civic", "11th Gen", 2022, 2025)
        build_list = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl2"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        ).json()
        part = _make_part(client, headers, test_category, test_part_manufacturer)

        _tombstone_part(UUID(part["id"]))

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json={"quantity": 1},
            headers=headers,
        )
        assert response.status_code == 404


class TestCatalogTreatsTombstonedPartsAsAbsent:
    def test_a_direct_fetch_of_a_tombstoned_part_is_404(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)

        assert client.get(f"{settings.API_STR}/parts/{part['id']}").status_code == 200
        _tombstone_part(UUID(part["id"]))
        assert client.get(f"{settings.API_STR}/parts/{part['id']}").status_code == 404

    def test_a_tombstoned_part_is_filtered_from_the_listing(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)

        listed = client.get(f"{settings.API_STR}/parts/")
        assert part["id"] in [row["id"] for row in listed.json()["items"]]

        _tombstone_part(UUID(part["id"]))

        after = client.get(f"{settings.API_STR}/parts/")
        assert part["id"] not in [row["id"] for row in after.json()["items"]]


class TestSearchExcludesTombstonedRows:
    """The vehicles domain's real surface: search lists users and parts."""

    def test_a_tombstoned_part_disappears_from_search(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)

        found = client.get(f"{settings.API_STR}/search/", params={"q": part["name"]})
        assert found.status_code == 200
        assert part["id"] in [row["id"] for row in found.json()["parts"]["items"]]

        _tombstone_part(UUID(part["id"]))

        after = client.get(f"{settings.API_STR}/search/", params={"q": part["name"]})
        assert part["id"] not in [row["id"] for row in after.json()["parts"]["items"]]

    def test_a_tombstoned_user_disappears_from_search(self, client: TestClient, dynamo_tables: Any) -> None:
        users = UserRepository()
        username = _unique("searchable")
        user = users.create_user(
            User(
                username=username,
                email=f"{username}@example.com",
                email_verified=True,
            )
        )

        found = client.get(f"{settings.API_STR}/search/", params={"q": username})
        assert found.status_code == 200
        assert str(user.id) in [row["id"] for row in found.json()["users"]["items"]]

        _tombstone_user(user.id)

        after = client.get(f"{settings.API_STR}/search/", params={"q": username})
        assert str(user.id) not in [row["id"] for row in after.json()["users"]["items"]]


class TestBuildLogsDropsTombstonedAuthors:
    """Seam 1's read consequence in the one domain that truly attaches an author."""

    def test_a_tombstoned_author_renders_as_absent(
        self, client: TestClient, test_user: User, db_session: Any, dynamo_tables: Any
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        car = create_car_in_db(db_session, "Mazda", "MX-5", "ND", 2016, 2024)
        build_list = client.post(
            f"{settings.API_STR}/build-lists/",
            json={"name": _unique("bl3"), "description": "d", "car_id": str(car["id"])},
            headers=headers,
        ).json()

        logs = BuildLogRepository()
        posts = BuildLogPostRepository()
        log = next(iter(logs.all_for_build_list(UUID(build_list["id"]))), None)
        if log is None:
            log = logs.create(BuildLog(build_list_id=UUID(build_list["id"]), title=_unique("log")))

        author = UserRepository().create_user(
            User(
                username=_unique("author"),
                email=f"{_unique('author')}@example.com",
                email_verified=True,
            )
        )
        posts.create(BuildLogPost(build_log_id=log.id, user_id=author.id, content="hello"))

        url = f"{settings.API_STR}/build-logs/build-list/{build_list['id']}"
        listed = client.get(url, headers=headers)
        assert listed.status_code == 200
        assert listed.json()["posts"][0]["author_username"] == author.username

        _tombstone_user(author.id)

        after = client.get(url, headers=headers)
        assert after.status_code == 200
        assert after.json()["posts"][0]["author_username"] is None, "a deleted author renders as absent"


class TestModerationTreatsTombstonesAsAbsent:
    def test_a_report_on_a_tombstoned_part_falls_back_to_unknown(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        dynamo_tables: Any,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)

        from app.api.services.report_service import ReportService

        # A user may not report their own part, so the reporter is a second account.
        reporter_name = _unique("reporter")
        UserRepository().create_user(
            User(
                username=reporter_name,
                email=f"{reporter_name}@example.com",
                email_verified=True,
            )
        )
        reporter_headers = _headers(login_user(client, reporter_name))

        created = client.post(
            f"{settings.API_STR}/reports/part/{part['id']}",
            json={"reason": "spam"},
            headers=reporter_headers,
        )
        assert created.status_code in (200, 201)
        report_id = UUID(created.json()["id"])

        service = ReportService()
        before = service.get_report_by_id(report_id, current_user_id=test_user.id, is_admin=True)
        assert before is not None and before.entity_name == part["name"]

        _tombstone_part(UUID(part["id"]))

        after = service.get_report_by_id(report_id, current_user_id=test_user.id, is_admin=True)
        assert after is not None
        assert after.entity_name == "Unknown part", "a purged target must not keep naming the tombstone"

    def test_a_tombstoned_part_cannot_be_reported(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)
        _tombstone_part(UUID(part["id"]))

        response = client.post(
            f"{settings.API_STR}/reports/part/{part['id']}",
            json={"reason": "spam"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_a_tombstoned_part_cannot_be_voted_on(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
    ) -> None:
        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)
        _tombstone_part(UUID(part["id"]))

        response = client.post(
            f"{settings.API_STR}/votes/part/{part['id']}",
            json={"vote_type": "upvote"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_a_tombstoned_reporter_reads_as_absent(self, dynamo_tables: Any) -> None:
        """`ReportService` degrades a missing reporter to an empty username."""
        from app.api.services.report_service import ReportService

        reporter = UserRepository().create_user(
            User(
                username=_unique("reporter"),
                email=f"{_unique('reporter')}@example.com",
                email_verified=True,
            )
        )
        report = ReportRepository().create(
            Report(user_id=reporter.id, entity_type="part", entity_id=uuid7(), reason="spam")
        )

        service = ReportService()
        before = service.get_report_by_id(report.id, current_user_id=reporter.id, is_admin=True)
        assert before is not None and before.reporter_username == reporter.username

        _tombstone_user(reporter.id)

        after = service.get_report_by_id(report.id, current_user_id=reporter.id, is_admin=True)
        assert after is not None and after.reporter_username == ""

    def test_flagged_listing_skips_tombstoned_parts(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        dynamo_tables: Any,
    ) -> None:
        """`VoteService._get_entities` is the chokepoint both vote paths share."""
        from app.api.services.vote_service import EntityType, VoteService

        headers = _headers(login_user(client, test_user.username))
        part = _make_part(client, headers, test_category, test_part_manufacturer)
        part_id = UUID(part["id"])

        votes = VoteRepository()
        for _ in range(3):
            votes.create(Vote(user_id=uuid7(), entity_type="part", entity_id=part_id, vote_type="downvote"))

        service = VoteService()
        assert part_id in service._get_entities(EntityType.PART, [part_id])

        _tombstone_part(part_id)

        assert service._get_entities(EntityType.PART, [part_id]) == {}
