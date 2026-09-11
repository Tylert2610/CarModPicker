"""Generic cursor paginated response envelope."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """One page of items plus the cursor for the next page."""

    items: list[T]
    next_cursor: str | None = None
    has_next: bool = False
