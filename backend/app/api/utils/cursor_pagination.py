"""Opaque cursor pagination helpers shared by the list endpoints."""

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable, TypeVar

from fastapi import Query

from app.api.schemas.pagination import CursorPage
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.models import DynamoModel
from app.db.dynamo.repository import Page

T = TypeVar("T")
U = TypeVar("U")
TModel = TypeVar("TModel", bound=DynamoModel)

MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 100


@dataclass(frozen=True)
class CursorParams:
    """The limit and cursor a list request was called with."""

    limit: int
    cursor: str | None


def get_cursor_params(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Maximum number of items to return"),
    cursor: str | None = Query(None, description="Opaque cursor from a previous page's next_cursor"),
) -> CursorParams:
    """FastAPI dependency supplying validated pagination parameters."""
    return CursorParams(limit=limit, cursor=cursor)


def encode_position(position: dict[str, Any]) -> str:
    """Encode a sort position into an opaque cursor string."""
    raw = json.dumps(position, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_position(cursor: str | None) -> dict[str, Any] | None:
    """Decode an opaque cursor, raising 400 when it is malformed."""
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        ResponsePatterns.raise_bad_request("Invalid pagination cursor")
    if not isinstance(decoded, dict):
        ResponsePatterns.raise_bad_request("Invalid pagination cursor")
    return decoded


def page_from_repository(page: Page[TModel], transform: Callable[[TModel], U]) -> CursorPage[U]:
    """Convert a repository page into the API's cursor page shape."""
    return CursorPage(
        items=[transform(item) for item in page.items],
        next_cursor=page.next_cursor,
        has_next=page.next_cursor is not None,
    )


def paginate_in_memory(
    items: Iterable[T],
    *,
    limit: int,
    cursor: str | None,
    sort_key: Callable[[T], str],
    item_id: Callable[[T], str],
    transform: Callable[[T], U],
) -> CursorPage[U]:
    """Sort, slice and cursor a fully loaded collection."""
    ordered = sorted(items, key=lambda item: (sort_key(item), item_id(item)))
    position = decode_position(cursor)
    if position is not None:
        after = (str(position.get("k", "")), str(position.get("id", "")))
        ordered = [item for item in ordered if (sort_key(item), item_id(item)) > after]
    window = ordered[:limit]
    has_next = len(ordered) > limit
    next_cursor = None
    if has_next:
        last = window[-1]
        next_cursor = encode_position({"k": sort_key(last), "id": item_id(last)})
    return CursorPage(items=[transform(item) for item in window], next_cursor=next_cursor, has_next=has_next)
