"""The tombstone predicate: `app/db/dynamo/tombstones.py`.

Row 23 of `docs/migration/split-plan.md` adds the `deleted` / `deleted_at` pair
to `users` and `parts` and the reads that honour it. Nothing writes a tombstone
yet (rows 28 and 30 do that), so these tests construct tombstoned rows directly,
which is also what proves the predicate is right before its producer exists.
"""

from typing import Any

from uuid6 import uuid7

from app.db.dynamo.catalog import Part
from app.db.dynamo.models import utc_now
from app.db.dynamo.tombstones import (
    DELETED_AT_ATTRIBUTE,
    DELETED_ATTRIBUTE,
    drop_tombstoned,
    drop_tombstoned_values,
    is_live,
    is_tombstoned,
    live_or_none,
)
from app.db.dynamo.users import User


def _user(**extra: Any) -> User:
    return User(username=f"u{uuid7().hex[:8]}", email=f"{uuid7().hex[:8]}@example.com", **extra)


def _part(**extra: Any) -> Part:
    return Part(name="Cold air intake", category_id=uuid7(), user_id=uuid7(), **extra)


def test_a_row_written_before_row_23_reads_as_live() -> None:
    """The no-backfill guarantee: an item with neither attribute is not deleted."""
    assert is_tombstoned(_user()) is False
    assert is_tombstoned(_part()) is False
    assert is_tombstoned({"id": "x"}) is False


def test_a_tombstoned_row_reads_as_deleted() -> None:
    assert is_tombstoned(_user(deleted=True)) is True
    assert is_tombstoned(_part(deleted=True)) is True
    assert is_tombstoned({DELETED_ATTRIBUTE: True}) is True


def test_deleted_at_alone_does_not_make_a_row_deleted() -> None:
    """`deleted` is the flag; `deleted_at` is only the audit trail."""
    assert is_tombstoned(_user(deleted_at=utc_now())) is False
    assert is_tombstoned({DELETED_AT_ATTRIBUTE: "2026-09-08T00:00:00Z"}) is False


def test_none_is_missing_rather_than_deleted() -> None:
    """A miss is not a tombstone: conflating them would 404 every absent author."""
    assert is_tombstoned(None) is False
    assert is_live(None) is False
    assert live_or_none(None) is None


def test_live_or_none_collapses_a_tombstone_onto_the_miss_path() -> None:
    live = _user()
    assert live_or_none(live) is live
    assert live_or_none(_user(deleted=True)) is None


def test_drop_tombstoned_filters_both_misses_and_tombstones() -> None:
    live = _part()
    assert drop_tombstoned([live, _part(deleted=True), None]) == [live]


def test_drop_tombstoned_values_filters_a_batch_get_result() -> None:
    """The shape `get_many` returns, which `batch_get` cannot filter server-side."""
    live, dead = _part(), _part(deleted=True)
    filtered = drop_tombstoned_values({live.id: live, dead.id: dead})
    assert filtered == {live.id: live}


def test_the_tombstone_pair_round_trips_through_dynamo(dynamo_tables: Any) -> None:
    """The attributes persist and reload, so the predicate works on stored rows."""
    from app.db.dynamo.users import UserRepository

    users = UserRepository()
    stored = users.create(_user())
    assert is_tombstoned(users.get(stored.id)) is False

    moment = utc_now()
    users.update(stored.id, deleted=True, deleted_at=moment)
    reloaded = users.get(stored.id)
    assert reloaded is not None
    assert is_tombstoned(reloaded) is True
    assert reloaded.deleted_at is not None
