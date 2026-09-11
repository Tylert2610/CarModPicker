"""Endpoint coverage for `GET /api/parts/{id}/price-history` (S05/T02).

Exercises the aggregated object response. The pre-S05 `legacy=true` shim was
removed in S13/T03 — only the object shape remains. Seeding mirrors
`tests/services/test_part_price_aggregation_service.py` so the per-row schema
matches what the aggregation service produces.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartListing as DBPartListing
from app.db.dynamo.catalog import PartPriceHistory as DBPartPriceHistory
from app.db.dynamo.catalog import Retailer as DBRetailer
from app.db.dynamo.users import User
from tests.conftest import INVALID_UUID_STR, auth_headers, get_default_category_id, login_user, save_catalog

PRICE_HISTORY_PATH = "/api/parts/{part_id}/price-history"
BATCH_PRICE_HISTORY_PATH = "/api/parts/price-history"


TEST_API_KEY = "test-extension-api-key-0123456789"


def _auth_headers(client: TestClient, user: User) -> dict[str, str]:
    """Bearer headers for ``user``."""
    return auth_headers(login_user(client, user.username))


def _api_key_headers(key: str = TEST_API_KEY) -> dict[str, str]:
    """`X-API-Key` headers for the machine path onto the batch POST.

    The batch route takes `require_api_key_or_admin`, so an end-user token is
    not enough; the seeding tests below use the key rather than logging an
    admin in on every case.
    """
    return {"X-API-Key": key}


@pytest.fixture(autouse=True)
def _configured_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `settings.EXTENSION_API_KEY` at a known value for this module.

    `_resolve_secret` consults the live `os.environ` before anything else, so
    setting the variable is enough and no Secrets Manager call is ever made.
    """
    monkeypatch.setenv("EXTENSION_API_KEY", TEST_API_KEY)


# --- helpers (mirror tests/services/test_part_price_aggregation_service.py) --


def _make_retailer(db: Any, slug: str) -> DBRetailer:
    retailer = DBRetailer(
        name=f"retailer_{slug}_{uuid.uuid4().hex[:8]}",
        domain=f"{slug}-{uuid.uuid4().hex[:8]}.example.com",
        base_url=f"https://{slug}.example.com",
        is_active=True,
    )
    retailer = save_catalog(retailer)
    return retailer


def _make_part(
    db: Any,
    user: User,
    *,
    canonical_part_id: uuid.UUID | None = None,
    name: str = "Test Part",
) -> DBPart:
    part = DBPart(
        name=name,
        category_id=get_default_category_id(db),
        user_id=user.id,
        is_universal=True,
        canonical_part_id=canonical_part_id,
    )
    part = save_catalog(part)
    return part


def _make_listing(db: Any, part: DBPart, retailer: DBRetailer) -> DBPartListing:
    listing = DBPartListing(
        part_id=part.id,
        retailer_id=retailer.id,
        product_url=f"https://{retailer.domain}/p/{uuid.uuid4().hex[:8]}",
    )
    listing = save_catalog(listing)
    return listing


def _add_history(
    db: Any,
    listing: DBPartListing,
    *,
    price_cents: int,
    observed_at: datetime,
) -> DBPartPriceHistory:
    row = DBPartPriceHistory(
        part_listing_id=listing.id,
        price_cents=price_cents,
        observed_at=observed_at,
    )
    row = save_catalog(row)
    return row


# --- tests -------------------------------------------------------------------


def test_get_price_history_default_window_returns_summary_object(
    client: TestClient, db_session: Any, test_user: User
) -> None:
    retailer = _make_retailer(db_session, "default-window")
    part = _make_part(db_session, test_user, name="Default Window Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    for i, price in enumerate([1000, 1100, 1200, 1300, 1400]):
        _add_history(db_session, listing, price_cents=price, observed_at=now - timedelta(days=10 + i))

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id))
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict), f"expected object, got {type(body).__name__}"
    assert set(body.keys()) >= {"summary", "retailers", "history", "window"}
    assert body["window"] == "90d"
    assert body["summary"]["observation_count"] == 5
    assert len(body["history"]) == 5
    assert len(body["retailers"]) == 1


def test_get_price_history_window_30d_filters_old(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "win30")
    part = _make_part(db_session, test_user, name="Window 30 Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # 3 rows inside 30 days, 2 rows older.
    for i, days in enumerate([1, 10, 20]):
        _add_history(db_session, listing, price_cents=1000 + i, observed_at=now - timedelta(days=days))
    for i, days in enumerate([45, 90]):
        _add_history(db_session, listing, price_cents=2000 + i, observed_at=now - timedelta(days=days))

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "30d"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["observation_count"] == 3
    assert len(body["history"]) == 3
    assert body["window"] == "30d"


def test_get_price_history_window_all_includes_everything(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "win-all")
    part = _make_part(db_session, test_user, name="Window All Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # 4 rows spanning ~2 years.
    for days in [10, 200, 500, 700]:
        _add_history(db_session, listing, price_cents=1000 + days, observed_at=now - timedelta(days=days))

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "all"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["observation_count"] == 4
    assert len(body["history"]) == 4
    assert body["window"] == "all"


def test_get_price_history_invalid_window_returns_422(client: TestClient, db_session: Any, test_user: User) -> None:
    part = _make_part(db_session, test_user, name="Bad Window Part")

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "99x"})
    assert response.status_code == 422
    body = response.json()
    # Standardized error envelope from app.api.middleware.error_handler.
    assert body["error_code"] == "INVALID_WINDOW"
    allowed = body["details"]["allowed"]
    assert isinstance(allowed, list)
    # Must mention the canonical literals so callers can correct themselves.
    assert {"30d", "90d", "180d", "1y", "all"}.issubset(set(allowed))


def test_get_price_history_retailer_filter_narrows_summary(
    client: TestClient, db_session: Any, test_user: User
) -> None:
    retailer_a = _make_retailer(db_session, "filt-a")
    retailer_b = _make_retailer(db_session, "filt-b")
    part = _make_part(db_session, test_user, name="Retailer Filter Part")
    listing_a = _make_listing(db_session, part, retailer_a)
    listing_b = _make_listing(db_session, part, retailer_b)

    now = datetime.now(UTC)
    # Retailer A: cheap rows (500-700). Retailer B: pricier (1500-2000).
    for i, price in enumerate([500, 600, 700]):
        _add_history(db_session, listing_a, price_cents=price, observed_at=now - timedelta(days=20 - i))
    for i, price in enumerate([1500, 1800, 2000]):
        _add_history(db_session, listing_b, price_cents=price, observed_at=now - timedelta(days=15 - i))

    response = client.get(
        PRICE_HISTORY_PATH.format(part_id=part.id),
        params={"retailer_id": str(retailer_a.id)},
    )
    assert response.status_code == 200
    body = response.json()
    # Only retailer A in `retailers`.
    assert len(body["retailers"]) == 1
    assert body["retailers"][0]["retailer_id"] == str(retailer_a.id)
    # Summary reflects retailer A's slice only — NOT the cross-retailer aggregate.
    assert body["summary"]["min_cents"] == 500
    assert body["summary"]["max_cents"] == 700
    assert body["summary"]["observation_count"] == 3
    assert all(h["retailer_id"] == str(retailer_a.id) for h in body["history"])


def test_get_price_history_part_not_found_returns_404(client: TestClient) -> None:
    response = client.get(PRICE_HISTORY_PATH.format(part_id=INVALID_UUID_STR))
    assert response.status_code == 404


# --- POST /api/parts/price-history (T03) -------------------------------------


def test_post_batch_price_history_basic(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "batch-basic")
    parts = []
    now = datetime.now(UTC)
    for idx in range(3):
        part = _make_part(db_session, test_user, name=f"Batch Basic {idx}")
        listing = _make_listing(db_session, part, retailer)
        for j, price in enumerate([1000 + idx * 100, 1100 + idx * 100, 1200 + idx * 100]):
            _add_history(db_session, listing, price_cents=price, observed_at=now - timedelta(days=5 + j))
        parts.append(part)

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(p.id) for p in parts]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["window"] == "90d"
    assert body["requested_count"] == 3
    assert body["found_count"] == 3
    assert set(body["summaries"].keys()) == {str(p.id) for p in parts}
    for p in parts:
        item = body["summaries"][str(p.id)]
        assert item["observation_count"] == 3
        assert item["min_cents"] is not None
        assert item["max_cents"] is not None


def test_post_batch_price_history_includes_empty_entries(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "batch-empty")
    now = datetime.now(UTC)
    part_with = _make_part(db_session, test_user, name="HasHistory")
    listing = _make_listing(db_session, part_with, retailer)
    for i, price in enumerate([800, 900]):
        _add_history(db_session, listing, price_cents=price, observed_at=now - timedelta(days=3 + i))
    part_other = _make_part(db_session, test_user, name="AlsoHistory")
    listing_other = _make_listing(db_session, part_other, retailer)
    _add_history(db_session, listing_other, price_cents=1500, observed_at=now - timedelta(days=2))
    part_empty = _make_part(db_session, test_user, name="NoHistory")

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part_with.id), str(part_other.id), str(part_empty.id)]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 3
    assert body["found_count"] == 2
    assert len(body["summaries"]) == 3
    empty_item = body["summaries"][str(part_empty.id)]
    assert empty_item["observation_count"] == 0
    assert empty_item["min_cents"] is None
    assert empty_item["max_cents"] is None
    assert empty_item["last_cents"] is None
    assert empty_item["trend"] == "flat"


def test_post_batch_price_history_window_default_90d(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "batch-default-window")
    part = _make_part(db_session, test_user, name="Default Window Batch")
    listing = _make_listing(db_session, part, retailer)
    _add_history(db_session, listing, price_cents=999, observed_at=datetime.now(UTC) - timedelta(days=1))

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part.id)]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "90d"


def test_post_batch_price_history_window_custom(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "batch-custom-window")
    part = _make_part(db_session, test_user, name="Custom Window Batch")
    listing = _make_listing(db_session, part, retailer)
    now = datetime.now(UTC)
    # 2 inside 30d, 2 older.
    for days in [5, 20]:
        _add_history(db_session, listing, price_cents=1000 + days, observed_at=now - timedelta(days=days))
    for days in [40, 60]:
        _add_history(db_session, listing, price_cents=2000 + days, observed_at=now - timedelta(days=days))

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part.id)], "window": "30d"},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "30d"
    assert body["summaries"][str(part.id)]["observation_count"] == 2


def test_post_batch_price_history_invalid_window_returns_422(
    client: TestClient, db_session: Any, test_user: User
) -> None:
    part = _make_part(db_session, test_user, name="Bad Window Batch")

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part.id)], "window": "xyz"},
        headers=_api_key_headers(),
    )
    # Pydantic Literal validation rejects "xyz" before the handler runs, producing
    # the standard VALIDATION_ERROR envelope. The endpoint's INVALID_WINDOW path
    # is reachable only when the schema is bypassed (e.g. service-layer callers).
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] in {"INVALID_WINDOW", "VALIDATION_ERROR"}


def test_post_batch_price_history_empty_part_ids_returns_422(client: TestClient, test_user: User) -> None:
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": []},
        headers=_api_key_headers(),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"


def test_post_batch_price_history_too_many_ids_returns_422(client: TestClient, test_user: User) -> None:
    too_many = [str(uuid.uuid4()) for _ in range(101)]
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": too_many},
        headers=_api_key_headers(),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    # Pydantic surfaces the at_most_100 constraint in the per-field error details.
    rendered = repr(body)
    assert "100" in rendered or "at_most" in rendered or "max_length" in rendered


def test_post_batch_price_history_unknown_ids_return_empty_entries(client: TestClient, test_user: User) -> None:
    unknown_a = str(uuid.uuid4())
    unknown_b = str(uuid.uuid4())
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [unknown_a, unknown_b]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 2
    assert body["found_count"] == 0
    assert set(body["summaries"].keys()) == {unknown_a, unknown_b}
    for entry in body["summaries"].values():
        assert entry["observation_count"] == 0
        assert entry["min_cents"] is None
        assert entry["trend"] == "flat"


def test_post_batch_price_history_aggregates_link_group(client: TestClient, db_session: Any, test_user: User) -> None:
    retailer_a = _make_retailer(db_session, "batch-lg-a")
    retailer_b = _make_retailer(db_session, "batch-lg-b")
    canonical = _make_part(db_session, test_user, name="Batch Canon")
    duplicate = _make_part(db_session, test_user, canonical_part_id=canonical.id, name="Batch Dupe")
    listing_canon = _make_listing(db_session, canonical, retailer_a)
    listing_dupe = _make_listing(db_session, duplicate, retailer_b)

    now = datetime.now(UTC)
    _add_history(db_session, listing_canon, price_cents=5000, observed_at=now - timedelta(days=10))
    _add_history(db_session, listing_canon, price_cents=4800, observed_at=now - timedelta(days=5))
    _add_history(db_session, listing_dupe, price_cents=3000, observed_at=now - timedelta(days=8))
    _add_history(db_session, listing_dupe, price_cents=3200, observed_at=now - timedelta(days=2))

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(canonical.id)]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    item = body["summaries"][str(canonical.id)]
    assert item["observation_count"] == 4
    assert item["min_cents"] == 3000
    assert item["max_cents"] == 5000


# --- auth on the batch POST -------------------------------------------------
# `POST /api/parts/price-history` was public, then briefly behind
# `get_current_user`, and is now behind `require_api_key_or_admin`. Its only
# legitimate writers are the Chrome extension and ingestion/admin jobs, so it
# takes an `X-API-Key` matching `EXTENSION_API_KEY` or an admin bearer token.


def _batch_body() -> dict[str, Any]:
    return {"part_ids": [str(uuid.uuid4())]}


def test_post_batch_price_history_anonymous_returns_401(client: TestClient) -> None:
    """No credential of any kind -> 401."""
    response = client.post(BATCH_PRICE_HISTORY_PATH, json=_batch_body())
    assert response.status_code == 401, response.text


def test_post_batch_price_history_wrong_api_key_returns_401(client: TestClient) -> None:
    """A wrong `X-API-Key` and no token is indistinguishable from no credential."""
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json=_batch_body(),
        headers=_api_key_headers("not-the-configured-key"),
    )
    assert response.status_code == 401, response.text


def test_post_batch_price_history_empty_api_key_returns_401(client: TestClient) -> None:
    """An empty header value must not match, even against an empty config."""
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json=_batch_body(),
        headers=_api_key_headers(""),
    )
    assert response.status_code == 401, response.text


def test_post_batch_price_history_api_key_unset_rejects_any_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no key configured the route fails closed: the key path is shut."""
    monkeypatch.delenv("EXTENSION_API_KEY", raising=False)
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json=_batch_body(),
        headers=_api_key_headers(),
    )
    assert response.status_code == 401, response.text


def test_post_batch_price_history_correct_api_key_succeeds(
    client: TestClient, db_session: Any, test_user: User
) -> None:
    """The configured `X-API-Key` gets the unchanged 200 response shape."""
    retailer = _make_retailer(db_session, "batch-apikey")
    part = _make_part(db_session, test_user, name="Batch Api Key")
    listing = _make_listing(db_session, part, retailer)
    _add_history(db_session, listing, price_cents=1234, observed_at=datetime.now(UTC) - timedelta(days=1))

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part.id)]},
        headers=_api_key_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) >= {"summaries", "window", "requested_count", "found_count"}
    assert body["requested_count"] == 1
    assert body["found_count"] == 1
    assert body["summaries"][str(part.id)]["observation_count"] == 1


def test_post_batch_price_history_admin_token_succeeds(
    client: TestClient, db_session: Any, test_user: User, test_admin_user: User
) -> None:
    """An admin bearer token is the human path onto the same route."""
    retailer = _make_retailer(db_session, "batch-admin")
    part = _make_part(db_session, test_user, name="Batch Admin")
    listing = _make_listing(db_session, part, retailer)
    _add_history(db_session, listing, price_cents=4321, observed_at=datetime.now(UTC) - timedelta(days=1))

    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json={"part_ids": [str(part.id)]},
        headers=_auth_headers(client, test_admin_user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requested_count"] == 1
    assert body["found_count"] == 1
    assert body["summaries"][str(part.id)]["observation_count"] == 1


def test_post_batch_price_history_superuser_token_succeeds(client: TestClient, test_superuser_user: User) -> None:
    """`get_current_admin_user` accepts a superuser too, so this route does."""
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json=_batch_body(),
        headers=_auth_headers(client, test_superuser_user),
    )
    assert response.status_code == 200, response.text


def test_post_batch_price_history_non_admin_token_returns_403(client: TestClient, test_user: User) -> None:
    """A valid token for an ordinary user is authenticated but not authorized."""
    response = client.post(
        BATCH_PRICE_HISTORY_PATH,
        json=_batch_body(),
        headers=_auth_headers(client, test_user),
    )
    assert response.status_code == 403, response.text


def test_post_batch_price_history_bad_key_falls_through_to_token(client: TestClient, test_admin_user: User) -> None:
    """A junk key alongside a good admin token still gets in on the token."""
    headers = {**_api_key_headers("junk"), **_auth_headers(client, test_admin_user)}
    response = client.post(BATCH_PRICE_HISTORY_PATH, json=_batch_body(), headers=headers)
    assert response.status_code == 200, response.text


def test_post_batch_price_history_key_wins_over_non_admin_token(client: TestClient, test_user: User) -> None:
    """The key is checked first, so it rescues a request from a non-admin token."""
    headers = {**_api_key_headers(), **_auth_headers(client, test_user)}
    response = client.post(BATCH_PRICE_HISTORY_PATH, json=_batch_body(), headers=headers)
    assert response.status_code == 200, response.text
