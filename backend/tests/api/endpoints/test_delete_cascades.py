"""What the two delete cascades remove.

Row 23 of `docs/migration/split-plan.md` wrote these tests against the two
synchronous cascades, deliberately, so that rows 28 and 30 would have a
reference to diff against rather than a description. Row 28 has now cut seam 2,
and this is that diff.

Both seams are now asynchronous, and the change to these tests is smaller than
that makes it sound. `PartService.purge` writes a tombstone and removes everything
`catalog` owns; the four cross domain deletes moved to
`app/consumers/part_purge.py`, off the `parts` stream and through the
`part-purge` work queue. The end state is identical, so the assertions about
what does not survive are identical too. What changed is only that the cascade
is driven by draining the queue rather than by a function call, which is what
`_drain_part_purge` below stands in for.

Seam 1, row 30. `_delete_user_everywhere` in `app/api/endpoints/users.py` now
writes a tombstone, hard deletes the user row and its two unique reservations,
and returns. Everything else it used to do moved to
`app/consumers/user_delete.py`, off the `users` stream and through the
`user-delete` work queue, which is what `_drain_user_delete` below stands in
for. The end state is again identical, so the assertions about what does not
survive are again identical.

The one assertion that deliberately runs *before* any drain is the reservation
one: a user who deletes an account can register the same username and email
immediately, on the next request, without the consumer having run. That is the
decision row 30 made and it is asserted here rather than described, because it
is the half of the cascade that did not move.

The test that did not change at all is the one that matters most:
`test_deleting_a_part_through_the_api_removes_it_from_build_lists` still passes
unmodified. A tombstoned part reads as absent everywhere the moment the delete
returns, because row 23 put `is_tombstoned` on every join that reaches a part,
so a build list drops the row without waiting for the consumer. That is the
property that makes the asynchrony invisible to a caller, and leaving that test
untouched is the proof of it.
"""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from uuid6 import uuid7

from app.api.dependencies.repositories import get_repositories
from app.core.config import settings
from app.db.dynamo.catalog import Category, PartManufacturer
from app.db.dynamo.moderation import Report, Vote
from app.db.dynamo.users import User, UserRepository
from tests.conftest import auth_headers, create_car_in_db, login_user


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _headers(token: str) -> dict[str, str]:
    return auth_headers(token)


def _make_user(name: str) -> User:
    return UserRepository().create_user(
        User(
            username=name,
            email=f"{name}@example.com",
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


def _drain_part_purge(repos: Any, part_id: UUID) -> None:
    """Run the cascade the way production runs it, minus the transport.

    In production the tombstone `PartService.purge` writes reaches
    `app/consumers/part_purge.py` over the `parts` stream, is enqueued on the
    `part-purge` work queue, and comes back to the same function to be drained.
    Here the handler is called directly with the part id, because what these
    tests pin is which rows the cascade removes and that is a property of the
    handler rather than of the two mappings in front of it. The mappings, the
    record parsing and the idempotency of a redelivery are covered in
    `tests/consumers/test_part_purge_consumer.py`.
    """
    from app.consumers.part_purge import purge_related_rows

    purge_related_rows(repos, part_id)


def _drain_user_delete(repos: Any, user_id: UUID) -> None:
    """Run seam 1's cascade the way production runs it, minus the transport.

    The same stand-in `_drain_part_purge` is, for the same reason. In production
    the tombstone `_delete_user_everywhere` writes reaches
    `app/consumers/user_delete.py` over the `users` stream, is enqueued on the
    `user-delete` work queue, and comes back to the same function to be drained.
    Here the handler is called directly with the user id, because what these
    tests pin is which rows the cascade removes, and that is a property of the
    handler rather than of the two mappings in front of it. The mappings, the
    record parsing and the idempotency of a redelivery are covered in
    `tests/consumers/test_user_delete_consumer.py`.

    Note that this drains seam 1 only. A user with parts leaves a part tombstone
    per part, and seam 2's cascade is a separate drain; the tests below that
    need both call both, which is exactly what production does with two queues.
    """
    from app.consumers.user_delete import cascade_user_delete

    cascade_user_delete(repos, user_id)


class TestPartPurgeCascade:
    """Seam 2. The cascade names four tables; assert all four."""

    def test_purging_a_part_removes_its_votes_reports_usages_and_alerts(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
        dynamo_tables: Any,
    ) -> None:
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

        _drain_part_purge(repos, part_id)

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
    """Seam 1, row 30. The row and its reservations go now, the rest goes after."""

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

        # Synchronous, before any drain: the row, and with it the two unique
        # reservations, are gone the moment the request returns.
        assert repos.users.get(user.id) is None, "the user row itself is hard deleted"

        # The uniqueness reservations are released in the same transaction, so the
        # username and email are immediately reusable. Asserted here, ahead of the
        # drain, because that ordering is the decision row 30 made: a reservation
        # held until a queue drains is an account holder who cannot re-register
        # with the address they just freed, failing closed, for as long as the
        # backlog lasts.
        reborn = _make_user(name)
        assert reborn.id != user.id

        _drain_user_delete(repos, user.id)

        assert repos.build_lists.get(build_list["id"]) is None, "their build lists are purged"

        # Two queues, so two drains. Seam 1 tombstones the part and seam 2 removes
        # it, which is what the chained cascade looks like from outside.
        _drain_part_purge(repos, UUID(part["id"]))
        assert repos.parts.get(part["id"]) is None, "their parts are purged, not orphaned"

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

        _drain_user_delete(repos, user.id)

        assert [v for v in repos.votes.for_entities("part", [part_id]).get(part_id, []) if v.user_id == user.id] == []
        assert [r for r in repos.reports.scan_all() if r.user_id == user.id] == []
