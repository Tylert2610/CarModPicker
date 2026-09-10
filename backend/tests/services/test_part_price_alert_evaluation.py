"""Service-level coverage for `evaluate_alerts_for_listing` (S07/T03).

Exercises every behavioral contract of the price-drop-alert evaluator:

- below-threshold observation fires email, last_fired_at = observed_at, INFO log
- above-threshold observation skips (no email, no row update)
- 24h cooldown: a fire-then-quick-revisit suppresses the second fire
- cooldown reset: a fire then 25h+ later, another below-threshold observation
  DOES fire again
- cross-user isolation: alice's alert on part A does not fire on bob's listing
  on part B (different part)
- send-failure path: SES returns False → last_fired_at stays as it was so the
  next observation retries
- exception-safe iteration: one alert raising during evaluation does not block
  another alert on the same part from firing

Split plan row 25 changed who calls the evaluator and nothing about what it
does, so every contract above is unchanged. The one test that did change is the
chokepoint integration test at the bottom, which now pins that
`create_or_update_listing_and_price` does NOT evaluate: seam 4 moved that to the
`part_listings` stream consumer. See `tests/consumers/test_price_alerts_consumer.py`.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.api.services.part_listing_service import create_or_update_listing_and_price
from app.api.services.part_price_alert_service import evaluate_alerts_for_listing
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartListingRepository
from app.db.dynamo.catalog import Retailer as DBRetailer
from app.db.dynamo.part_price_alerts import PartPriceAlert as DBPartPriceAlert
from app.db.dynamo.part_price_alerts import PartPriceAlertRepository
from app.db.dynamo.users import User, UserRepository
from tests.conftest import get_default_category_id, save_catalog

# --- helpers ----------------------------------------------------------------


def _make_user(db: Any, suffix: str) -> User:
    """Create a test user with a unique username/email."""
    u = User(
        username=f"alert_user_{suffix}_{os.getpid()}_{uuid.uuid4().hex[:8]}",
        email=f"alert_user_{suffix}_{os.getpid()}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="$2b$12$dummy.hash.for.testing.only.not.real.bcrypt.hash..",
        email_verified=True,
        disabled=False,
    )
    return UserRepository().create_user(u)


def _make_part(db: Any, owner: User, *, name: str = "Brake Disc") -> DBPart:
    part = DBPart(
        name=f"{name}_{uuid.uuid4().hex[:8]}",
        category_id=get_default_category_id(db),
        user_id=owner.id,
        is_universal=True,
    )
    part = save_catalog(part)
    return part


def _make_retailer(db: Any, slug: str = "shop") -> DBRetailer:
    r = DBRetailer(
        name=f"retailer_{slug}_{uuid.uuid4().hex[:8]}",
        domain=f"{slug}-{uuid.uuid4().hex[:8]}.example.com",
        base_url=f"https://{slug}.example.com",
        is_active=True,
    )
    r = save_catalog(r)
    return r


def _make_alert(
    db: Any,
    user: User,
    part: DBPart,
    threshold_cents: int,
    *,
    last_fired_at: datetime | None = None,
    active: bool = True,
) -> DBPartPriceAlert:
    return PartPriceAlertRepository().create(
        DBPartPriceAlert(
            user_id=user.id,
            part_id=part.id,
            threshold_cents=threshold_cents,
            active=active,
            last_fired_at=last_fired_at,
        )
    )


def _reload(alert: DBPartPriceAlert) -> DBPartPriceAlert:
    return PartPriceAlertRepository().get_or_raise(alert.id)


def _stub_email_send(*, return_value: bool = True) -> tuple[Any, list[dict[str, Any]]]:
    """Build a stub for ``send_price_drop_alert_email`` that captures every call.

    Returns ``(stub_callable, calls_list)``. Each call is recorded as a dict
    with the relevant args so tests can assert on what was sent.
    """
    calls: list[dict[str, Any]] = []

    def stub(to_email: str, part: Any, retailer: Any, price_cents: int, alert: Any) -> bool:
        calls.append(
            {
                "to_email": to_email,
                "part_id": part.id,
                "retailer_id": retailer.id,
                "price_cents": price_cents,
                "alert_id": alert.id,
            }
        )
        return return_value

    return stub, calls


# --- happy path -------------------------------------------------------------


def test_below_threshold_fires_email_and_updates_last_fired_at(
    db_session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _make_user(db_session, "below")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    alert = _make_alert(db_session, user, part, threshold_cents=10_000)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    observed_at = datetime.now(UTC)
    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_000,
        observed_at=observed_at,
    )

    assert len(calls) == 1, "below-threshold observation must fire one email"
    assert calls[0]["alert_id"] == alert.id
    assert calls[0]["price_cents"] == 8_000

    alert = _reload(alert)
    assert alert.last_fired_at is not None
    # last_fired_at is exactly observed_at (the evaluator sets it directly).
    assert alert.last_fired_at == observed_at or alert.last_fired_at.replace(tzinfo=UTC) == observed_at


def test_above_threshold_skips(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user(db_session, "above")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    alert = _make_alert(db_session, user, part, threshold_cents=5_000)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=10_000,  # well above threshold
        observed_at=datetime.now(UTC),
    )

    assert calls == [], "above-threshold observation must not fire"
    alert = _reload(alert)
    assert alert.last_fired_at is None


def test_at_threshold_fires(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """price_cents == threshold_cents is "at or below" → fires."""
    user = _make_user(db_session, "at")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    _make_alert(db_session, user, part, threshold_cents=7_500)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=7_500,
        observed_at=datetime.now(UTC),
    )
    assert len(calls) == 1


# --- cooldown ---------------------------------------------------------------


def test_24h_cooldown_suppresses_second_fire(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user(db_session, "cooldown_supp")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    # Pre-seed last_fired_at = 1 hour ago.
    fired_at = datetime.now(UTC) - timedelta(hours=1)
    _make_alert(db_session, user, part, threshold_cents=10_000, last_fired_at=fired_at)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_000,
        observed_at=datetime.now(UTC),
    )

    assert calls == [], "alert within 24h cooldown must not re-fire"


def test_cooldown_reset_after_25h_fires_again(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user(db_session, "cooldown_reset")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    # Pre-seed last_fired_at = 25 hours ago — outside the 24h window.
    fired_at = datetime.now(UTC) - timedelta(hours=25)
    alert = _make_alert(db_session, user, part, threshold_cents=10_000, last_fired_at=fired_at)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    new_observed = datetime.now(UTC)
    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_000,
        observed_at=new_observed,
    )

    assert len(calls) == 1, "alert past 24h cooldown must re-fire"
    alert = _reload(alert)
    assert alert.last_fired_at == new_observed or (
        alert.last_fired_at is not None and alert.last_fired_at.replace(tzinfo=UTC) == new_observed
    )


# --- cross-user isolation ---------------------------------------------------


def test_alert_on_one_part_does_not_fire_on_another_part(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alice's alert on part A must not fire on bob's listing observation on part B."""
    alice = _make_user(db_session, "iso_alice")
    bob = _make_user(db_session, "iso_bob")
    part_a = _make_part(db_session, alice, name="part_a")
    part_b = _make_part(db_session, bob, name="part_b")
    retailer = _make_retailer(db_session)
    _make_alert(db_session, alice, part_a, threshold_cents=10_000)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    # Observation on part_b at a price that WOULD fire alice's alert
    # if cross-part leakage happened.
    evaluate_alerts_for_listing(
        part_id=part_b.id,
        retailer_id=retailer.id,
        price_cents=1_000,
        observed_at=datetime.now(UTC),
    )

    assert calls == [], "alert on part_a must not fire when part_b is observed"


# --- failure paths ----------------------------------------------------------


def test_send_failure_leaves_last_fired_at_unchanged(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user(db_session, "send_fail")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    alert = _make_alert(db_session, user, part, threshold_cents=10_000)
    assert alert.last_fired_at is None

    stub, calls = _stub_email_send(return_value=False)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_000,
        observed_at=datetime.now(UTC),
    )

    assert len(calls) == 1, "evaluator must attempt the send"
    alert = _reload(alert)
    assert alert.last_fired_at is None, "SES failure must leave last_fired_at None so the next observation retries"


def test_exception_in_one_alert_does_not_block_another(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two alerts on the same part — the first send raises, the second still fires."""
    alice = _make_user(db_session, "exc_alice")
    bob = _make_user(db_session, "exc_bob")
    part = _make_part(db_session, alice)
    retailer = _make_retailer(db_session)

    bad_alert = _make_alert(db_session, alice, part, threshold_cents=10_000)
    good_alert = _make_alert(db_session, bob, part, threshold_cents=9_000)

    calls: list[dict[str, Any]] = []

    def flaky_send(to_email: str, part: Any, retailer: Any, price_cents: int, alert: Any) -> bool:
        if alert.id == bad_alert.id:
            raise RuntimeError("simulated SES blowup for the first alert")
        calls.append({"alert_id": alert.id})
        return True

    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", flaky_send)

    # Should not raise — exceptions in per-alert iteration are swallowed/logged.
    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_500,
        observed_at=datetime.now(UTC),
    )

    assert len(calls) == 1
    assert calls[0]["alert_id"] == good_alert.id

    # Bad alert was never marked as fired (exception path).
    bad_alert = _reload(bad_alert)
    assert bad_alert.last_fired_at is None
    good_alert = _reload(good_alert)
    assert good_alert.last_fired_at is not None


# --- inactive alerts are skipped --------------------------------------------


def test_inactive_alert_is_skipped(db_session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user(db_session, "inactive")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    _make_alert(db_session, user, part, threshold_cents=10_000, active=False)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=8_000,
        observed_at=datetime.now(UTC),
    )
    assert calls == []


# --- the price-write chokepoint no longer evaluates -------------------------


def test_create_or_update_listing_and_price_does_not_invoke_evaluator(
    db_session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Split plan row 25 inverted this: the chokepoint must NOT send mail.

    This test used to be the integration evidence that T03 wired the evaluator
    into `create_or_update_listing_and_price`. Seam 4 removed that call, so the
    same test now pins the opposite property, which is the one that matters
    after the move: a price write returns as soon as its transaction commits,
    and it neither reads `part_price_alerts` nor reaches SES. If the
    synchronous call were ever restored, this fails.

    The write still has to happen, and it still has to land the price, because
    the stream record the consumer evaluates is produced by exactly this write.
    A chokepoint that stopped persisting the price would move the bug from a
    duplicate email to a silent one, which no consumer test would catch.
    """
    user = _make_user(db_session, "chokepoint")
    part = _make_part(db_session, user)
    retailer = _make_retailer(db_session)
    _make_alert(db_session, user, part, threshold_cents=12_000)

    stub, calls = _stub_email_send(return_value=True)
    monkeypatch.setattr("app.core.email.send_price_drop_alert_email", stub)

    create_or_update_listing_and_price(
        part_id=part.id,
        retailer_id=retailer.id,
        product_url="https://example.com/p/1",
        price_cents=11_000,
    )

    assert calls == []
    listing = PartListingRepository().get_by_part_and_retailer(part.id, retailer.id)
    assert listing is not None
    assert listing.last_known_price_cents == 11_000

    # And the observation the write persisted is exactly what the consumer needs
    # to evaluate, which is what makes the removal safe rather than merely quiet.
    assert listing.last_price_updated_at is not None
    evaluate_alerts_for_listing(
        part_id=part.id,
        retailer_id=retailer.id,
        price_cents=listing.last_known_price_cents,
        observed_at=listing.last_price_updated_at,
    )
    assert len(calls) == 1
