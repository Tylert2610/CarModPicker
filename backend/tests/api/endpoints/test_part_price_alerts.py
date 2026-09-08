"""Endpoint coverage for `/api/part-price-alerts` (S07/T02).

Covers the full per-user CRUD surface: subscribe (with idempotent re-subscribe),
list-mine (with cross-user isolation), patch threshold/active, delete (soft via
active=False), and the four negative paths from the task plan: anon → 401,
unknown part → 404, non-owner delete → 404, threshold_cents < 0 → 422.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Dict, Tuple

import jwt
from fastapi.testclient import TestClient

from app.api.dependencies.auth import ALGORITHM, create_access_token
from app.core.config import settings
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.part_price_alerts import PartPriceAlertRepository
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.api.endpoints.test_users import create_and_login_user, get_auth_headers
from tests.conftest import INVALID_UUID_STR, get_default_category_id, save_catalog

ALERTS_PATH = f"{settings.API_STR}/part-price-alerts"


# --- helpers ----------------------------------------------------------------


def _make_part(db: Any, owner: DBUser, *, name: str = "Brake Disc") -> DBPart:
    """Build a minimal Part owned by `owner`. Mirrors the seeding pattern from
    test_parts_price_history.py — no listings or history needed for T02."""
    part = DBPart(
        name=f"{name}_{uuid.uuid4().hex[:8]}",
        category_id=get_default_category_id(db),
        user_id=owner.id,
        is_universal=True,
    )
    part = save_catalog(part)
    return part


def _create_user_part_pair(client: TestClient, db_session: Any, suffix: str) -> Tuple[Dict[str, Any], str, DBPart]:
    """Convenience: register+login a user, return (user_dict, token, owned_part)."""
    user_info, token = create_and_login_user(client, suffix)
    db_user = UserRepository().get_by_username(user_info["username"])
    assert db_user is not None
    part = _make_part(db_session, db_user, name=f"part_{suffix}")
    return user_info, token, part


# --- anon path --------------------------------------------------------------


def test_subscribe_requires_auth(client: TestClient, db_session: Any) -> None:
    """POST without a Bearer token must 401."""
    # Need a real part_id so we don't depend on validation-order quirks.
    user_info, _ = create_and_login_user(client, "alerts_anon_seed")
    db_user = UserRepository().get_by_username(user_info["username"])
    assert db_user is not None
    part = _make_part(db_session, db_user)

    response = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
    )
    assert response.status_code == 401


def test_list_me_requires_auth(client: TestClient) -> None:
    response = client.get(f"{ALERTS_PATH}/me")
    assert response.status_code == 401


def test_patch_requires_auth(client: TestClient) -> None:
    response = client.patch(
        f"{ALERTS_PATH}/{INVALID_UUID_STR}",
        json={"threshold_cents": 1000},
    )
    assert response.status_code == 401


def test_delete_requires_auth(client: TestClient) -> None:
    response = client.delete(f"{ALERTS_PATH}/{INVALID_UUID_STR}")
    assert response.status_code == 401


# --- subscribe (POST /) -----------------------------------------------------


def test_subscribe_creates_new_alert(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_create_new")
    headers = get_auth_headers(token)

    response = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 9999},
        headers=headers,
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["part_id"] == str(part.id)
    assert body["threshold_cents"] == 9999
    assert body["active"] is True
    assert body["last_fired_at"] is None
    assert "id" in body and "created_at" in body and "updated_at" in body


def test_subscribe_unknown_part_returns_404(client: TestClient, db_session: Any) -> None:
    _, token = create_and_login_user(client, "alerts_unknown_part")
    headers = get_auth_headers(token)

    response = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": INVALID_UUID_STR, "threshold_cents": 1000},
        headers=headers,
    )
    assert response.status_code == 404, response.text
    body = response.json()
    assert body.get("error_code") == "NOT_FOUND"


def test_subscribe_negative_threshold_returns_422(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_neg_threshold")
    headers = get_auth_headers(token)

    response = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": -1},
        headers=headers,
    )
    assert response.status_code == 422, response.text


def test_resubscribe_updates_threshold_idempotent(client: TestClient, db_session: Any) -> None:
    """Re-POSTing with the same (user, part) updates threshold instead of inserting."""
    _, token, part = _create_user_part_pair(client, db_session, "alerts_resubscribe")
    headers = get_auth_headers(token)

    first = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 5000},
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 7500},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["id"] == first_id, "Re-subscribe must reuse the existing row, not insert a new one"
    assert body["threshold_cents"] == 7500
    assert body["active"] is True

    # Confirm only one row exists at the DB layer.
    rows = PartPriceAlertRepository().list_by_part(part.id)
    assert len(rows) == 1


def test_resubscribe_reactivates_soft_deleted_alert(client: TestClient, db_session: Any) -> None:
    """If a prior alert was soft-deleted (active=False), re-subscribing flips
    active back on and updates the threshold — same row, no duplicate."""
    _, token, part = _create_user_part_pair(client, db_session, "alerts_reactivate")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    assert create_resp.status_code == 201
    alert_id = create_resp.json()["id"]

    delete_resp = client.delete(f"{ALERTS_PATH}/{alert_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Re-subscribe: should reactivate the same row, not create a new one.
    re_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 4200},
        headers=headers,
    )
    assert re_resp.status_code == 201, re_resp.text
    body = re_resp.json()
    assert body["id"] == alert_id
    assert body["active"] is True
    assert body["threshold_cents"] == 4200


# --- list-mine (GET /me) ----------------------------------------------------


def test_list_me_returns_only_current_users_alerts(client: TestClient, db_session: Any) -> None:
    """Cross-user isolation: alice's /me must NOT include bob's alerts."""
    alice_info, alice_token, alice_part = _create_user_part_pair(client, db_session, "alerts_isolation_alice")
    bob_info, bob_token, bob_part = _create_user_part_pair(client, db_session, "alerts_isolation_bob")
    alice_headers = get_auth_headers(alice_token)
    bob_headers = get_auth_headers(bob_token)

    # Alice subscribes to her own part.
    r_a = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(alice_part.id), "threshold_cents": 1000},
        headers=alice_headers,
    )
    assert r_a.status_code == 201
    alice_alert_id = r_a.json()["id"]

    # Bob subscribes to his own part.
    r_b = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(bob_part.id), "threshold_cents": 2000},
        headers=bob_headers,
    )
    assert r_b.status_code == 201
    bob_alert_id = r_b.json()["id"]

    # Alice's /me sees only her alert.
    alice_list = client.get(f"{ALERTS_PATH}/me", headers=alice_headers)
    assert alice_list.status_code == 200, alice_list.text
    alice_ids = {a["id"] for a in alice_list.json()}
    assert alice_alert_id in alice_ids
    assert bob_alert_id not in alice_ids

    # And bob's /me sees only his.
    bob_list = client.get(f"{ALERTS_PATH}/me", headers=bob_headers)
    assert bob_list.status_code == 200
    bob_ids = {a["id"] for a in bob_list.json()}
    assert bob_alert_id in bob_ids
    assert alice_alert_id not in bob_ids


def test_list_me_excludes_inactive_alerts(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_list_excludes_inactive")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]
    client.delete(f"{ALERTS_PATH}/{alert_id}", headers=headers)

    list_resp = client.get(f"{ALERTS_PATH}/me", headers=headers)
    assert list_resp.status_code == 200
    ids = {a["id"] for a in list_resp.json()}
    assert alert_id not in ids


# --- patch ------------------------------------------------------------------


def test_patch_threshold_updates_value(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_patch_threshold")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 3000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"{ALERTS_PATH}/{alert_id}",
        json={"threshold_cents": 5500},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["threshold_cents"] == 5500
    assert body["id"] == alert_id


def test_patch_negative_threshold_returns_422(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_patch_neg")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 3000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"{ALERTS_PATH}/{alert_id}",
        json={"threshold_cents": -50},
        headers=headers,
    )
    assert patch_resp.status_code == 422, patch_resp.text


def test_patch_by_non_owner_returns_404(client: TestClient, db_session: Any) -> None:
    """Patching another user's alert must look identical to 'not found'."""
    _, alice_token, part = _create_user_part_pair(client, db_session, "alerts_patch_owner_alice")
    _, bob_token = create_and_login_user(client, "alerts_patch_owner_bob")

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=get_auth_headers(alice_token),
    )
    alert_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"{ALERTS_PATH}/{alert_id}",
        json={"threshold_cents": 2000},
        headers=get_auth_headers(bob_token),
    )
    assert patch_resp.status_code == 404, patch_resp.text


# --- delete -----------------------------------------------------------------


def test_delete_sets_active_false(client: TestClient, db_session: Any) -> None:
    _, token, part = _create_user_part_pair(client, db_session, "alerts_delete_soft")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]

    delete_resp = client.delete(f"{ALERTS_PATH}/{alert_id}", headers=headers)
    assert delete_resp.status_code == 204, delete_resp.text

    # Soft-delete: row still exists, but active=False.
    row = PartPriceAlertRepository().get(uuid.UUID(alert_id))
    assert row is not None, "soft-delete should keep the row in the DB"
    assert row.active is False


def test_delete_by_non_owner_returns_404(client: TestClient, db_session: Any) -> None:
    """Bob trying to DELETE alice's alert must 404 (not 403, not 204)."""
    _, alice_token, part = _create_user_part_pair(client, db_session, "alerts_del_owner_alice")
    _, bob_token = create_and_login_user(client, "alerts_del_owner_bob")

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=get_auth_headers(alice_token),
    )
    alert_id = create_resp.json()["id"]

    delete_resp = client.delete(f"{ALERTS_PATH}/{alert_id}", headers=get_auth_headers(bob_token))
    assert delete_resp.status_code == 404, delete_resp.text

    # Confirm alice's alert is still active — bob's failed call did not flip it.
    row = PartPriceAlertRepository().get(uuid.UUID(alert_id))
    assert row is not None
    assert row.active is True


def test_delete_unknown_alert_returns_404(client: TestClient, db_session: Any) -> None:
    _, token = create_and_login_user(client, "alerts_del_unknown")
    headers = get_auth_headers(token)
    response = client.delete(f"{ALERTS_PATH}/{INVALID_UUID_STR}", headers=headers)
    assert response.status_code == 404


# --- unsubscribe-via-token (T03) -------------------------------------------


def _build_unsubscribe_token(alert_id: str, *, purpose: str = "price_alert_unsubscribe") -> str:
    """Mint the same JWT shape the email path uses, parameterizing the purpose
    so we can test bad-purpose rejection without mocking the email sender."""
    return create_access_token(
        data={"sub": str(alert_id), "purpose": purpose},
        expires_delta=timedelta(days=30),
    )


def test_unsubscribe_with_valid_token_redirects_and_deactivates(client: TestClient, db_session: Any) -> None:
    """Valid token → 302 to /account/alerts?status=success and alert.active=False."""
    _, token, part = _create_user_part_pair(client, db_session, "unsub_valid")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    assert create_resp.status_code == 201
    alert_id = create_resp.json()["id"]

    unsubscribe_token = _build_unsubscribe_token(alert_id)
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": unsubscribe_token},
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    location = response.headers.get("location", "")
    assert "/account/alerts" in location
    assert "status=success" in location
    assert "Unsubscribed" in location

    row = PartPriceAlertRepository().get(uuid.UUID(alert_id))
    assert row is not None
    assert row.active is False


def test_unsubscribe_with_wrong_purpose_redirects_to_error(client: TestClient, db_session: Any) -> None:
    """Token with purpose != 'price_alert_unsubscribe' must not unsubscribe."""
    _, token, part = _create_user_part_pair(client, db_session, "unsub_bad_purpose")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]

    bogus_token = _build_unsubscribe_token(alert_id, purpose="verify_email")
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": bogus_token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "status=error" in location

    # Alert must still be active.
    row = PartPriceAlertRepository().get(uuid.UUID(alert_id))
    assert row is not None
    assert row.active is True


def test_unsubscribe_with_expired_token_redirects_to_error(client: TestClient, db_session: Any) -> None:
    """Expired token → 302 to error redirect; alert untouched."""
    _, token, part = _create_user_part_pair(client, db_session, "unsub_expired")
    headers = get_auth_headers(token)

    create_resp = client.post(
        f"{ALERTS_PATH}/",
        json={"part_id": str(part.id), "threshold_cents": 1000},
        headers=headers,
    )
    alert_id = create_resp.json()["id"]

    expired_token = create_access_token(
        data={"sub": str(alert_id), "purpose": "price_alert_unsubscribe"},
        expires_delta=timedelta(seconds=-10),  # already expired
    )
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": expired_token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "status=error" in location

    row = PartPriceAlertRepository().get(uuid.UUID(alert_id))
    assert row is not None
    assert row.active is True


def test_unsubscribe_with_garbage_token_redirects_to_error(client: TestClient, db_session: Any) -> None:
    """Random non-JWT garbage → 302 to error redirect (does not 500)."""
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": "not-a-jwt"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "status=error" in response.headers.get("location", "")


def test_unsubscribe_with_non_uuid_sub_redirects_to_error(client: TestClient, db_session: Any) -> None:
    """JWT with a `sub` that isn't a UUID → error redirect, no 500."""
    bad_token = create_access_token(
        data={"sub": "not-a-uuid", "purpose": "price_alert_unsubscribe"},
        expires_delta=timedelta(days=1),
    )
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": bad_token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "status=error" in response.headers.get("location", "")


def test_unsubscribe_unknown_alert_id_redirects_to_error(client: TestClient, db_session: Any) -> None:
    """Well-formed token referencing a nonexistent alert → error redirect."""
    fake_token = _build_unsubscribe_token(INVALID_UUID_STR)
    response = client.get(
        f"{ALERTS_PATH}/unsubscribe",
        params={"token": fake_token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "status=error" in response.headers.get("location", "")


# --- route ordering regression (split-plan section 1.4) ---------------------


def test_unsubscribe_is_registered_before_parameterised_routes() -> None:
    """`/unsubscribe` must be registered ahead of every `/{alert_id}` route.

    FastAPI resolves in registration order, so a literal that is registered after a
    parameterised sibling of the same shape is only reachable while no route with a
    matching method exists on the parameter. Unsubscribe survived on that accident:
    `/{alert_id}` carries PATCH and DELETE and there is no GET detail route, so a GET
    for `/unsubscribe` fell through to the literal. Adding `GET /{alert_id}` would have
    swallowed it silently, redirecting nothing and returning 422 for a token that is
    not a UUID.

    Asserting on registration order rather than on a live request is deliberate: a
    request-level test passes either way today and would only start failing once the
    GET detail route lands, which is exactly the silent break this guards against.
    """
    from app.api.endpoints.part_price_alerts import router

    paths = [route.path for route in router.routes if getattr(route, "path", None)]

    assert "/unsubscribe" in paths, paths
    unsubscribe_index = paths.index("/unsubscribe")

    parameterised_indexes = [index for index, path in enumerate(paths) if "{alert_id}" in path]
    assert parameterised_indexes, paths

    assert unsubscribe_index < min(parameterised_indexes), (
        "/unsubscribe must be registered before the /{alert_id} routes, " f"got order {paths}"
    )
