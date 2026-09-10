"""The tombstone pair and the one predicate every domain reads it through.

Section 7 of `docs/migration/split-plan.md` adds two attributes, `deleted` and
`deleted_at`, to `users` and to `parts`. They are new attributes on existing
items, so every row written before this module existed simply lacks them and
reads as not deleted. There is no backfill and no Terraform change: DynamoDB is
schemaless for non-key attributes, and `terraform/dynamodb_tables.json` carries
only key attributes, secondary indexes and the TTL field, none of which move.

**Row 23 adds the attributes and the reads, not the writes.** Nothing in the
application sets `deleted` yet. The user delete in `app/api/endpoints/users.py`
and the part purge in `app/api/services/part_service.py` are still hard deletes
that cascade synchronously, and they stay that way until rows 28 and 30 build
the stream consumers that drain the cascade off a work queue. Flipping the write
before those consumers exist would strand the related rows in eleven tables with
nothing to clean them up. So the predicate below is deliberately live ahead of
its producer: it is what rows 28 and 30 will write against, and the read paths
that call it are correct today (every row reads as not deleted) and stay correct
the moment a tombstone first appears.

**Why the predicate lives here rather than in the repositories.** The obvious
home is a filter inside `DynamoRepository`, applied to every read. It does not
work, because the widest join in the application goes through
`CatalogRepository.get_many`, which is a `batch_get`, and DynamoDB's
`BatchGetItem` takes no filter expression. Any design that hides the predicate
in the repository layer would silently miss that path. It is a plain function
instead, applied at the call sites, so the places that cannot filter server-side
and the places that can both go through the same one line of logic.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, TypeGuard, TypeVar

#: The two attribute names, spelled once. Anything writing a tombstone (rows 28
#: and 30) and anything reading one goes through these rather than a literal.
DELETED_ATTRIBUTE = "deleted"
DELETED_AT_ATTRIBUTE = "deleted_at"

T = TypeVar("T")


def is_tombstoned(entity: Any) -> bool:
    """True when `entity` carries a tombstone and must be treated as absent.

    Accepts a Pydantic model, a raw DynamoDB item mapping, or `None`, because
    the call sites hold a mix of all three: a repository `get` returns a model
    or `None`, and a few paths still inspect items. `None` is not tombstoned,
    it is simply missing, and the caller's existing not-found handling covers
    it; conflating the two here would turn every optional author into a 404.

    The check is on `deleted` alone. `deleted_at` is the audit trail and is not
    consulted, so a row carrying a timestamp but no flag reads as live. Rows 28
    and 30 write both together in one update.
    """
    if entity is None:
        return False
    if isinstance(entity, Mapping):
        return bool(entity.get(DELETED_ATTRIBUTE))
    return bool(getattr(entity, DELETED_ATTRIBUTE, False))


def is_live(entity: Optional[T]) -> TypeGuard[T]:
    """The inverse of `is_tombstoned`, for use as a filter predicate.

    `None` is not live: a filter over a sequence that may contain misses should
    drop them alongside the tombstones, which is the opposite of what
    `is_tombstoned` wants for an optional single get. It is a `TypeGuard` so the
    filters below narrow `Optional[T]` to `T` rather than needing a cast.
    """
    return entity is not None and not is_tombstoned(entity)


def drop_tombstoned(entities: Iterable[Optional[T]]) -> list[T]:
    """Filter a sequence down to the rows that are neither missing nor deleted."""
    return [entity for entity in entities if is_live(entity)]


def live_or_none(entity: Optional[T]) -> Optional[T]:
    """Collapse a tombstoned row to `None` so existing miss handling applies.

    This is the shape most of the single-get call sites want. They already read
    `author.username if author else None`, so mapping a tombstone onto `None`
    makes a deleted user render exactly like an absent one with no change to the
    formatting code below it.
    """
    return entity if is_live(entity) else None


def drop_tombstoned_values(entities: Mapping[Any, T]) -> dict[Any, T]:
    """Filter a keyed batch-get result down to its live rows.

    `CatalogRepository.get_many` and `UserRepository.get_many` both return a
    dict keyed by id. This is the post-`batch_get` filter the module docstring
    describes, and it is why the predicate is a function rather than a
    repository concern.
    """
    return {key: value for key, value in entities.items() if is_live(value)}
