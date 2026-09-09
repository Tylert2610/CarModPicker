"""
Build logs endpoint for forum-style build log threads.
Each build list automatically gets a build log thread.
"""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.build_log import (
    BuildLogPostCreate,
    BuildLogPostRead,
    BuildLogPostUpdate,
    BuildLogReadPaginated,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    create_paginated_response,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.image_utils import get_presigned_url_from_file_key
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.build_lists import BuildList
from app.db.dynamo.build_logs import BuildLog, BuildLogPost
from app.db.dynamo.tombstones import live_or_none
from app.db.dynamo.users import User as DBUser

# Create router
router = APIRouter()


def _require_build_list(repos: Repositories, build_list_id: UUID) -> BuildList:
    build_list = repos.build_lists.get(build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_list_id)
    assert build_list is not None
    return build_list


def _require_build_log(repos: Repositories, build_list_id: UUID, logger) -> BuildLog:
    """The build log for a build list; every build list is created with one."""
    build_log = repos.build_logs.for_build_list(build_list_id)
    if build_log is None:
        # Post-DATA-08 backfill invariant: every build list has a build log.
        # If this branch fires, something broke the invariant — do not silently
        # auto-create (the old fallback hid data-integrity issues).
        logger.error("Orphan build_list %s has no build_log; DATA-08 invariant violated", build_list_id)
        ResponsePatterns.raise_not_found("build log", build_list_id)
    assert build_log is not None
    return build_log


def _require_post(repos: Repositories, post_id: UUID) -> BuildLogPost:
    post = repos.build_log_posts.get(post_id)
    if post is None:
        ResponsePatterns.raise_not_found("build log post", post_id)
    assert post is not None
    return post


def _post_with_author(post: BuildLogPost, author: Optional[DBUser]) -> BuildLogPostRead:
    # Seam 1's read consequence: a tombstoned author renders exactly like an
    # absent one. Both call sites pass their author through here, so collapsing
    # the tombstone to None once covers the batch join and the single get
    # without either of them repeating the predicate. `author_username` and
    # `author_image_url` are already Optional, so no schema change follows.
    author = live_or_none(author)
    post_data = BuildLogPostRead.model_validate(post)
    post_data.author_username = author.username if author else None
    post_data.author_image_url = (
        get_presigned_url_from_file_key((author.image_urls or [None])[0]) if author and author.image_urls else None
    )
    return post_data


def _authorize_post_change(repos: Repositories, post: BuildLogPost, current_user: DBUser, action: str, logger) -> None:
    """
    A post may be changed by its author, by the owner of the build list the
    thread belongs to, or by an admin.
    """
    build_log = repos.build_logs.get(post.build_log_id)
    if build_log is None:
        ResponsePatterns.raise_not_found("build log", post.build_log_id)
    assert build_log is not None

    build_list = repos.build_lists.get(build_log.build_list_id)
    if build_list is None:
        ResponsePatterns.raise_not_found("build list", build_log.build_list_id)
    assert build_list is not None

    allowed = (
        post.user_id == current_user.id
        or build_list.user_id == current_user.id
        or current_user.is_admin
        or current_user.is_superuser
    )
    if not allowed:
        logger.warning(f"Access denied: User {current_user.id} attempted to {action} build log post {post.id}")
        ResponsePatterns.raise_forbidden(f"Not authorized to {action} this build log post")


@router.get(
    "/posts/count",
    response_model=Dict[str, int],
    responses={
        200: {"description": "Count of build log posts"},
    },
)
async def count_build_log_posts(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """
    Get total count of build log posts.
    Public access - anyone can view the count.
    """
    logger = deps["logger"]
    count = repos.build_log_posts.count()
    logger.info(f"Retrieved build log posts count: {count}")
    return {"count": count}


@router.get(
    "/build-list/{build_list_id}",
    response_model=BuildLogReadPaginated,
    responses=crud_responses("build log", "read", allow_public_read=True),
)
async def get_build_log_by_build_list(
    build_list_id: UUID,
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of posts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> BuildLogReadPaginated:
    """
    Get the build log thread for a specific build list.
    Public read access - anyone can view build logs.
    """
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)
    build_log = _require_build_log(repos, build_list_id, logger)

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    all_posts = sorted(repos.build_log_posts.all_for_build_log(build_log.id), key=lambda p: (p.created_at, str(p.id)))
    total_posts = len(all_posts)
    posts = all_posts[skip : skip + limit]

    authors = repos.users.get_many([post.user_id for post in posts if post.user_id is not None])
    posts_with_authors: List[BuildLogPostRead] = [
        _post_with_author(post, authors.get(post.user_id) if post.user_id is not None else None) for post in posts
    ]

    paginated_response = create_paginated_response(
        data=posts_with_authors,
        total=total_posts,
        skip=skip,
        limit=limit,
        message="Build log retrieved successfully",
    )

    # Map pagination response to match frontend expectations
    pagination_data = paginated_response["pagination"]
    pagination_mapped = {
        "current_page": pagination_data["current_page"],
        "total_pages": pagination_data["total_pages"],
        "total_items": pagination_data["total"],  # Map 'total' to 'total_items'
        "items_per_page": pagination_data["limit"],  # Map 'limit' to 'items_per_page'
        "has_next": pagination_data["has_next"],
        "has_previous": pagination_data["has_previous"],
    }

    build_log_paginated = BuildLogReadPaginated(
        id=build_log.id,
        build_list_id=build_log.build_list_id,
        title=build_log.title,
        created_at=build_log.created_at,
        updated_at=build_log.updated_at,
        posts=paginated_response["data"],
        pagination=pagination_mapped,
    )

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(
        f"{user_info}: Retrieved build log {build_log.id} for build list {build_list_id} (skip: {skip}, limit: {limit})"
    )

    return build_log_paginated


@router.post(
    "/build-list/{build_list_id}/posts",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "create"),
    status_code=status.HTTP_201_CREATED,
)
async def create_build_log_post(
    build_list_id: UUID,
    post_data: BuildLogPostCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildLogPostRead:
    """
    Create a new post in a build log thread.
    Requires authentication.
    """
    logger = deps["logger"]

    _require_build_list(repos, build_list_id)
    build_log = _require_build_log(repos, build_list_id, logger)

    post = repos.build_log_posts.create(
        BuildLogPost(build_log_id=build_log.id, user_id=current_user.id, content=post_data.content)
    )

    logger.info(f"User {current_user.id} created post {post.id} in build log {build_log.id}")

    return _post_with_author(post, current_user)


@router.put(
    "/posts/{post_id}",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "update"),
)
async def update_build_log_post(
    post_id: UUID,
    post_data: BuildLogPostUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
    current_user: DBUser = Depends(get_current_user),
) -> BuildLogPostRead:
    """
    Update a build log post.
    Users can update their own posts, build list owners can update any post in their build log,
    or admins can update any post.
    """
    logger = deps["logger"]

    post = _require_post(repos, post_id)
    _authorize_post_change(repos, post, current_user, "update", logger)

    if post_data.content is not None:
        post = repos.build_log_posts.update(post.id, content=post_data.content)

    author = repos.users.get(post.user_id) if post.user_id is not None else None

    logger.info(f"User {current_user.id} updated post {post.id}")

    return _post_with_author(post, author)


@router.delete(
    "/posts/{post_id}",
    responses=crud_responses("build log post", "delete"),
)
async def delete_build_log_post(
    post_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, str]:
    """
    Delete a build log post.
    Users can delete their own posts, build list owners can delete any post in their build log,
    or admins can delete any post.
    """
    logger = deps["logger"]

    post = _require_post(repos, post_id)
    _authorize_post_change(repos, post, current_user, "delete", logger)

    repos.build_log_posts.delete(post.id)

    logger.info(f"User {current_user.id} deleted post {post_id}")

    return {"message": "Build log post deleted successfully"}
