"""The `deleted` / `deleted_at` tombstone pair and the predicates that read it.

The predicate is a plain function rather than a repository filter because the
widest read is a `batch_get`, and `BatchGetItem` takes no filter expression.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, TypeGuard, TypeVar

DELETED_ATTRIBUTE = "deleted"
DELETED_AT_ATTRIBUTE = "deleted_at"

T = TypeVar("T")


def is_tombstoned(entity: Any) -> bool:
    """True when `entity` carries a tombstone and must be treated as absent.

    Accepts a model, a raw item mapping or `None`; `None` is missing, not deleted.
    Only `deleted` is consulted, since `deleted_at` is an audit trail.
    """
    if entity is None:
        return False
    if isinstance(entity, Mapping):
        return bool(entity.get(DELETED_ATTRIBUTE))
    return bool(getattr(entity, DELETED_ATTRIBUTE, False))


def is_live(entity: Optional[T]) -> TypeGuard[T]:
    """The inverse of `is_tombstoned`, for filtering sequences that may contain misses.

    A `TypeGuard` so filters narrow `Optional[T]` to `T` without a cast.
    """
    return entity is not None and not is_tombstoned(entity)


def drop_tombstoned(entities: Iterable[Optional[T]]) -> list[T]:
    """Filter a sequence down to the rows that are neither missing nor deleted."""
    return [entity for entity in entities if is_live(entity)]


def live_or_none(entity: Optional[T]) -> Optional[T]:
    """Collapse a tombstoned row to `None` so existing not-found handling applies."""
    return entity if is_live(entity) else None


def drop_tombstoned_values(entities: Mapping[Any, T]) -> dict[Any, T]:
    """Filter a keyed batch-get result down to its live rows."""
    return {key: value for key, value in entities.items() if is_live(value)}
