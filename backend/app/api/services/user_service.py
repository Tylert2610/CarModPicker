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
    # Rebound to `repos` rather than to a differently named local, and that is
    # load bearing rather than cosmetic. `tests/entrypoints/test_repository_bundles.py`
    # recomputes each domain's declared tuple from the import graph by finding
    # attribute accesses whose receiver is named `repos`, so a bundle read
    # through any other name is invisible to it. This function reads
    # `oauth_accounts` on every single user response, and under the old name the
    # test could not see it: `users` declared the repository anyway, because the
    # delete cascade reached it, and row 30 moving that cascade out is what would
    # have exposed the gap as a `RepositoryNotInBundle` on `GET /users/me`.
    repos = repos if repos is not None else get_repositories()
    accounts = repos.oauth_accounts.list_by_user(user.id)
    return UserRead.model_validate(user).model_copy(
        update={"oauth_accounts": [OAuthAccountRead.model_validate(account) for account in accounts]}
    )


def user_reads(users: Iterable[DBUser], repos: Optional[Repositories] = None) -> List[UserRead]:
    # `repos` for the reason spelled out on `user_read` above.
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
    def __init__(self, repos: Optional[Repositories] = None) -> None:
        self.repos = repos if repos is not None else get_repositories()

    def get_by_id(self, user_id: UUID, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get(user_id)
        if user:
            log.info(f"Retrieved user by id: {user_id}")
        else:
            log.info(f"No user found with id: {user_id}")
        return user

    def get_by_username(self, username: str, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get_by_username(username)
        if user:
            log.info(f"Retrieved user by username: {username}")
        else:
            log.info(f"No user found with username: {username}")
        return user

    def get_by_email(self, email: str, logger: Optional[logging.Logger] = None) -> Optional[DBUser]:
        log = logger if logger is not None else get_logger()
        user = self.repos.users.get_by_email(email)
        if user:
            log.info(f"Retrieved user by email: {email}")
        else:
            log.info(f"No user found with email: {email}")
        return user

    def get_all_users(self, search: Optional[str] = None, logger: Optional[logging.Logger] = None) -> List[DBUser]:
        log = logger if logger is not None else get_logger()
        users = self.repos.users.search(search) if search else self.repos.users.list_all()
        log.info(f"Retrieved {len(users)} users")
        return users

    def count_all(self, logger: Optional[logging.Logger] = None) -> int:
        log = logger if logger is not None else get_logger()
        count = self.repos.users.count()
        log.info(f"Total user count: {count}")
        return count
