"""End-to-end tests for build list labor estimate endpoints."""

import os
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User, UserRepository
from tests.conftest import auth_headers, create_car_in_db, login_user


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _auth(token: str) -> dict[str, str]:
    return auth_headers(token)


def _create_build_list(
    client: TestClient,
    headers: dict[str, str],
    db_session: Any,
    suffix: str = "",
) -> dict:
    # Distinct generation_name per call so the (car_model_id, slug) unique constraint
    # doesn't trip when a single test creates multiple build lists.
    gen_name = f"Gen {_unique('lbr')}{suffix}"
    car = create_car_in_db(db_session, generation_name=gen_name)
    body = {
        "name": _unique("bl_labor") + suffix,
        "description": "labor estimate test build list",
        "car_id": str(car["id"]),
    }
    resp = client.post(f"{settings.API_STR}/build-lists/", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestBuildListLaborEstimatesCRUD:
    def test_create_list_update_delete(self, client: TestClient, test_user: User, db_session: Any) -> None:
        token = login_user(client, test_user.username)
        headers = _auth(token)
        bl = _create_build_list(client, headers, db_session)

        # Create
        create_body = {
            "name": "Paint - bumper respray",
            "cost_cents": 80000,
            "description": "Body shop estimate",
        }
        resp = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json=create_body,
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        created = resp.json()
        assert created["name"] == create_body["name"]
        assert created["cost_cents"] == 80000
        assert created["build_list_phase_id"] is None
        assert created["sort_order"] == 0

        # Second create -> sort_order auto-bumps to 1
        resp2 = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "Install labor", "cost_cents": 50000},
            headers=headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["sort_order"] == 1

        # List (public, no auth needed)
        list_resp = client.get(f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 2
        assert items[0]["sort_order"] <= items[1]["sort_order"]

        # Update
        upd = client.put(
            f"{settings.API_STR}/build-list-labor-estimates/{created['id']}",
            json={"cost_cents": 90000, "description": "Updated estimate"},
            headers=headers,
        )
        assert upd.status_code == 200
        assert upd.json()["cost_cents"] == 90000
        assert upd.json()["description"] == "Updated estimate"

        # Delete
        dele = client.delete(
            f"{settings.API_STR}/build-list-labor-estimates/{created['id']}",
            headers=headers,
        )
        assert dele.status_code == 200
        # And it's gone
        list_after = client.get(f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates").json()
        assert all(item["id"] != created["id"] for item in list_after)

    def test_non_owner_cannot_mutate(
        self,
        client: TestClient,
        test_user: User,
        db_session: Any,
    ) -> None:
        owner_token = login_user(client, test_user.username)
        bl = _create_build_list(client, _auth(owner_token), db_session)

        # Owner creates a labor estimate
        created = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "Tuning", "cost_cents": 30000},
            headers=_auth(owner_token),
        ).json()

        # Second user attempts to edit

        other = UserRepository().create_user(
            User(
                username=_unique("other"),
                email=_unique("other") + "@example.com",
                email_verified=True,
                disabled=False,
            )
        )
        other_token = login_user(client, other.username)

        forbidden = client.put(
            f"{settings.API_STR}/build-list-labor-estimates/{created['id']}",
            json={"cost_cents": 1},
            headers=_auth(other_token),
        )
        assert forbidden.status_code == 403

        forbidden_del = client.delete(
            f"{settings.API_STR}/build-list-labor-estimates/{created['id']}",
            headers=_auth(other_token),
        )
        assert forbidden_del.status_code == 403

    def test_anonymous_cannot_mutate_but_can_list(self, client: TestClient, test_user: User, db_session: Any) -> None:
        token = login_user(client, test_user.username)
        bl = _create_build_list(client, _auth(token), db_session)

        anon_create = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "x", "cost_cents": 1},
        )
        assert anon_create.status_code == 401

        anon_list = client.get(f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates")
        assert anon_list.status_code == 200


class TestBuildListLaborEstimatePhase:
    def test_phase_must_belong_to_same_build_list(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        # Premium user so the free-tier build list cap doesn't block creating two.
        token = login_user(client, premium_test_user.username)
        headers = _auth(token)
        bl_a = _create_build_list(client, headers, db_session, suffix="_a")
        bl_b = _create_build_list(client, headers, db_session, suffix="_b")

        # Create a phase on build list B
        phase_b = client.post(
            f"{settings.API_STR}/build-lists/{bl_b['id']}/phases",
            json={"name": "Phase 1"},
            headers=headers,
        ).json()

        # Try to attach it to a labor estimate on build list A — should 400
        bad = client.post(
            f"{settings.API_STR}/build-lists/{bl_a['id']}/labor-estimates",
            json={"name": "Cross-list", "cost_cents": 100, "build_list_phase_id": phase_b["id"]},
            headers=headers,
        )
        assert bad.status_code == 400

        # Same on update
        ok = client.post(
            f"{settings.API_STR}/build-lists/{bl_a['id']}/labor-estimates",
            json={"name": "OK", "cost_cents": 100},
            headers=headers,
        ).json()
        bad_upd = client.put(
            f"{settings.API_STR}/build-list-labor-estimates/{ok['id']}",
            json={"build_list_phase_id": phase_b["id"]},
            headers=headers,
        )
        assert bad_upd.status_code == 400

    def test_phase_delete_nulls_labor_estimate_link(self, client: TestClient, test_user: User, db_session: Any) -> None:
        token = login_user(client, test_user.username)
        headers = _auth(token)
        bl = _create_build_list(client, headers, db_session)

        phase = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/phases",
            json={"name": "Body work"},
            headers=headers,
        ).json()

        labor = client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "Paint", "cost_cents": 50000, "build_list_phase_id": phase["id"]},
            headers=headers,
        ).json()
        assert labor["build_list_phase_id"] == phase["id"]

        # Delete the phase
        del_resp = client.delete(f"{settings.API_STR}/build-list-phases/{phase['id']}", headers=headers)
        assert del_resp.status_code == 200

        # Labor estimate survives but phase link is now null
        items = client.get(f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates").json()
        survivor = next(item for item in items if item["id"] == labor["id"])
        assert survivor["build_list_phase_id"] is None


class TestBuildListLaborEstimateCostRollup:
    def test_with_votes_includes_labor_in_total(self, client: TestClient, test_user: User, db_session: Any) -> None:
        token = login_user(client, test_user.username)
        headers = _auth(token)
        bl = _create_build_list(client, headers, db_session)

        client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "Paint", "cost_cents": 80000},
            headers=headers,
        )
        client.post(
            f"{settings.API_STR}/build-lists/{bl['id']}/labor-estimates",
            json={"name": "Install", "cost_cents": 50000},
            headers=headers,
        )

        resp = client.get(
            f"{settings.API_STR}/build-lists/with-votes",
            params={"owner_id": str(test_user.id)},
        )
        assert resp.status_code == 200
        page = resp.json()
        match = next(item for item in page["data"] if item["id"] == bl["id"])
        assert match["total_labor_cost_cents"] == 130000
        # No parts in the build list, so parts cost is 0/None and total == labor
        assert match["total_cost_cents"] == 130000
