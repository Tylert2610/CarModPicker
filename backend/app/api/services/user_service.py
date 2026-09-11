"""Read side service for user accounts."""

import logging
from typing import Iterable, List, Optional
from uuid import UUID

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.auth import OAuthAccountRead
from app.api.schemas.user import UserRead
from app.core.logging import get_logger
from app.db.dynamo.users import User as DBUser

logger = get_logger()


def user_read(user: DBUser, repos: Optional[Repositories] = None) -> UserRead:
    """Build a UserRead with the user's linked OAuth accounts attached."""
    repos = repos if repos is not None else get_repositories()
    accounts = repos.oauth_accounts.list_by_user(user.id)
    return UserRead.model_validate(user).model_copy(
        update={"oauth_accounts": [OAuthAccountRead.model_validate(account) for account in accounts]}
    )


def user_reads(users: Iterable[DBUser], repos: Optional[Repositories] = None) -> List[UserRead]:
    """Build UserReads for many users in one OAuth account lookup."""
    repos = repos if repos is not None else get_repositories()
    user_list = list(users)
    accounts_by_user = repos.oauth_accounts.list_by_users([user.id for user in user_list])
    return [
        UserRead.model_validate(user).model_copy(
            update={
                "oauth_accounts": [
                    OAuthAccountRead.model_validate(account) for account in accounts_by_user.get(user.id, [])
                ]
            }
        )
        for user in user_list
    ]


class UserService:
    """Lookup and counting operations over the user repository."""

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Bind the service to a repository bundle."""
        self.repos = repos if repos is not None else get_repositories()

    def get_by_id(self, user_id: UUID, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        """Return the user with this id, or None."""
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get(user_id)
        if user:
            log.info(f"Retrieved user by id: {user_id}")
        else:
            log.info(f"No user found with id: {user_id}")
        return user

    def get_by_username(self, username: str, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        """Return the user with this username, or None."""
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get_by_username(username)
        if user:
            log.info(f"Retrieved user by username: {username}")
        else:
            log.info(f"No user found with username: {username}")
        return user

    def get_by_email(self, email: str, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        """Return the user with this email, or None."""
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get_by_email(email)
        if user:
            log.info(f"Retrieved user by email: {email}")
        else:
            log.info(f"No user found with email: {email}")
        return user

    def get_all_users(self, search: Optional[str] = None, logger: Optional[logging.Logger] = None) -> List[DBUser]:
        """Return every user, optionally filtered by a search term."""
        log = logger if logger is not None else get_logger()
        users = self.repos.users.search(search) if search else self.repos.users.list_all()
        log.info(f"Retrieved {len(users)} users")
        return users

    def count_all(self, logger: Optional[logging.Logger] = None) -> int:
        """Return the total number of users."""
        log = logger if logger is not None else get_logger()
        count = self.repos.users.count()
        log.info(f"Total user count: {count}")
        return count
