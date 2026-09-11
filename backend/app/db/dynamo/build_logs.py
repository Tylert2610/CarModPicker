"""Build log threads and their posts on DynamoDB."""

from typing import Any
from uuid import UUID

from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository, Page
from app.db.dynamo.tables import BUILD_LOG_POSTS, BUILD_LOGS


class BuildLog(TimestampedDynamoModel):
    """Forum-style thread attached to exactly one build list."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    build_list_id: UUID
    title: str


class BuildLogPost(TimestampedDynamoModel):
    """A post in a build log thread. ``user_id`` is None once the author is deleted."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    build_log_id: UUID
    user_id: UUID | None = None
    content: str


class BuildLogRepository(DynamoRepository[BuildLog]):
    """Build log threads, one per build list."""

    def __init__(self) -> None:
        """Bind to the build logs table."""
        super().__init__(BuildLog, BUILD_LOGS)

    def for_build_list(self, build_list_id: UUID) -> BuildLog | None:
        """The one build log a build list owns, or None when the invariant is broken."""
        page = self.query("build_list_id-index", build_list_id, limit=1)
        return page.items[0] if page.items else None

    def all_for_build_list(self, build_list_id: UUID) -> list[BuildLog]:
        """Every log thread on a build list, including any the invariant should forbid."""
        return self.query_all("build_list_id-index", build_list_id)

    def count(self) -> int:
        """How many build log threads exist."""
        return len(self.scan_all())


class BuildLogPostRepository(DynamoRepository[BuildLogPost]):
    """Posts within build log threads."""

    def __init__(self) -> None:
        """Bind to the build log posts table."""
        super().__init__(BuildLogPost, BUILD_LOG_POSTS)

    def list_for_build_log(
        self,
        build_log_id: UUID,
        *,
        limit: int = 100,
        cursor: str | None = None,
        scan_forward: bool = True,
    ) -> Page[BuildLogPost]:
        """Posts in a thread, oldest first by default."""
        return self.query(
            "build_log_id-created_at-index", build_log_id, limit=limit, cursor=cursor, scan_forward=scan_forward
        )

    def all_for_build_log(self, build_log_id: UUID) -> list[BuildLogPost]:
        """Every post in a thread, oldest first."""
        return self.query_all("build_log_id-created_at-index", build_log_id)

    def list_by_user(self, user_id: UUID) -> list[BuildLogPost]:
        """Every post this user wrote, across all threads."""
        return self.query_all("user_id-created_at-index", user_id)

    def count(self) -> int:
        """How many build log posts exist."""
        return len(self.scan_all())


def build_log_delete_actions(
    build_list_id: UUID,
    *,
    build_logs: BuildLogRepository,
    posts: BuildLogPostRepository,
) -> list[dict[str, Any]]:
    """
    Transaction actions removing a build list's log thread and every post in it.

    Fed into ``delete_build_list_cascade`` as ``extra_actions`` so the thread
    disappears with the list, as the SQL ``ON DELETE CASCADE`` used to do.
    """
    actions: list[dict[str, Any]] = []
    for log in build_logs.all_for_build_list(build_list_id):
        actions.extend(posts.delete_action(str(post.id)) for post in posts.all_for_build_log(log.id))
        actions.append(build_logs.delete_action(str(log.id)))
    return actions
