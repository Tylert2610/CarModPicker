from datetime import datetime
from typing import Any
from uuid import UUID

from boto3.dynamodb.conditions import Attr
from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.errors import DynamoError, TransactionCanceled
from app.db.dynamo.models import DynamoModel, TimestampedDynamoModel, utc_now
from app.db.dynamo.repository import DynamoRepository, RangeCondition, transact_write
from app.db.dynamo.serialization import composite_key, encode_bytes
from app.db.dynamo.tables import OAUTH_ACCOUNTS, USERS, WEBAUTHN_CREDENTIALS
from app.db.dynamo.tombstones import DELETED_ATTRIBUTE

USERNAME = "username"
EMAIL = "email"
PROVIDER_ACCOUNT = "provider_account"
USER_PROVIDER = "user_provider"
CREDENTIAL_ID = "credential_id"


def _not_tombstoned() -> Any:
    """Condition matching rows that carry no tombstone.

    `attribute_not_exists` is the half that matters: every row written before
    row 23 lacks `deleted` entirely, and must still read as live.
    """
    return Attr(DELETED_ATTRIBUTE).not_exists() | Attr(DELETED_ATTRIBUTE).eq(False)


class UniqueAttributeTaken(DynamoError):
    def __init__(self, attribute: str) -> None:
        self.attribute = attribute
        super().__init__(f"{attribute} is already taken")


class User(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    username: str
    email: str
    image_urls: list[str] | None = None
    email_verified: bool = False
    disabled: bool = False
    is_superuser: bool = False
    is_admin: bool = False
    is_service_account: bool = False
    subscription_tier: str = "free"
    subscription_expires_at: datetime | None = None
    subscription_status: str = "active"
    # `totp_enabled` stays and `totp_secret` is gone. The flag is what the
    # profile UI renders and what `UserRead` publishes; the seed itself lives
    # sealed in the package's `totp-factors` table, which is the whole point of
    # row 7's sealing migration. Row 13 removed the plaintext column from this
    # model, and `backend/scripts/clear_legacy_credentials.py` removes it from
    # the rows. `model_config` is `extra="ignore"`, so a row written before that
    # script runs still loads here with the stale attribute simply dropped.
    totp_enabled: bool = False
    session_expire_minutes: int | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    reddit_url: str | None = None
    youtube_url: str | None = None
    tiktok_url: str | None = None
    #: Seam 1's tombstone pair. Row 23 adds the attributes and the reads that
    #: honour them; row 30 is what starts writing them, when the `user-delete`
    #: stream consumer exists to drain the cascade. Rows written before row 23
    #: lack both and read as not deleted.
    deleted: bool = False
    deleted_at: datetime | None = None


class OAuthAccount(DynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    provider: str
    provider_account_id: str
    email: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class WebAuthnCredential(DynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    credential_id: bytes
    public_key: bytes
    sign_count: int = 0
    transports: list[str] | None = None
    aaguid: str | None = None
    nickname: str
    backup_eligible: bool = False
    backup_state: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime | None = None


def run_unique_transaction(actions: list[dict[str, Any]], labels: list[str | None]) -> None:
    try:
        transact_write(actions)
    except TransactionCanceled as exc:
        for reason, label in zip(exc.reasons, labels):
            if label is not None and reason.get("Code") == "ConditionalCheckFailed":
                raise UniqueAttributeTaken(label) from exc
        raise


class UserRepository(DynamoRepository[User]):
    def __init__(self) -> None:
        super().__init__(User, USERS)

    def get_by_username(self, username: str) -> User | None:
        page = self.query("username_lower-index", username.lower(), limit=1)
        return page.items[0] if page.items else None

    def get_by_email(self, email: str) -> User | None:
        page = self.query("email_lower-index", email.lower(), limit=1)
        return page.items[0] if page.items else None

    def get_many(self, user_ids: list[UUID]) -> dict[UUID, User]:
        unique_ids = list({user_id for user_id in user_ids if user_id is not None})
        return {user.id: user for user in self.batch_get(unique_ids)} if unique_ids else {}

    def list_all(self) -> list[User]:
        return self.scan_all()

    def search(self, term: str) -> list[User]:
        """Users matching `term`, excluding tombstoned rows.

        This is the one user read that surfaces profiles as search *results*
        rather than attaching an author to something else, so a tombstoned user
        has to be excluded here or a deleted account keeps appearing in search.
        The filter is server-side because this path already carries a filter
        expression; `attribute_not_exists` is what makes rows written before the
        attribute existed match, so no backfill is needed.
        """
        needle = term.lower()
        matches = Attr("username_lower").contains(needle) | Attr("email_lower").contains(needle)
        return self.scan_all(filter_expression=matches & _not_tombstoned())

    def count(self) -> int:
        return len(self.scan_all())

    def list_active_superusers(self) -> list[User]:
        return self.scan_all(filter_expression=Attr("is_superuser").eq(True) & Attr("disabled").eq(False))

    def list_service_accounts(self) -> list[User]:
        return self.scan_all(filter_expression=Attr("is_service_account").eq(True))

    def create_actions(self, user: User) -> tuple[list[dict[str, Any]], list[str | None]]:
        owner = str(user.id)
        actions = [
            self.ensure_unique_action(USERNAME, user.username.lower(), owner),
            self.ensure_unique_action(EMAIL, user.email.lower(), owner),
            self.create_action(user),
        ]
        return actions, [USERNAME, EMAIL, None]

    def create_user(self, user: User) -> User:
        actions, labels = self.create_actions(user)
        run_unique_transaction(actions, labels)
        return user

    # ---- the legacy password column -------------------------------------------------
    #
    # `hashed_password` is no longer a field on `User`, and these two methods are
    # the only code left in the backend that reads or writes it. They exist
    # because row 13 could not finish the job, and the shape of them is chosen to
    # make that visible rather than comfortable.
    #
    # Three routes in `app/api/endpoints/users.py` still take a password:
    # `POST /api/users/` (public registration), the password change on
    # `PUT /api/users/{user_id}`, and the admin password set on
    # `PUT /api/users/admin/users/{user_id}`. They are not `/api/auth` routes, so
    # row 13 did not delete them, and the frontend still calls all three. The
    # package serves `POST /api/auth/register` and `POST /api/auth/password`,
    # which supersede the first two, but re-pointing the SPA at them is a
    # frontend change with its own review rather than a line of this row.
    #
    # Writing through the package's `DynamoCredentialStore` instead would be a
    # small code change and is blocked on infrastructure this row must not touch:
    # the `credentials` table and its IAM grant belong to `module.identity`,
    # which takes exactly one role (`identity_role_name`), and the users function
    # holds no grant on that table. Giving it one means a new input on a
    # versioned platform module in another repository, or a hand written policy
    # in this one reaching into module owned ARNs. Either is its own row.
    #
    # So the column stays until that row lands, and these two methods keep it
    # reachable without putting it back on the model. Keeping it off the model
    # is what makes `UserRead` unable to leak it, makes every other read path
    # structurally incapable of touching it, and leaves exactly one pair of call
    # sites for the follow up row to delete.
    #
    # `backend/scripts/clear_legacy_credentials.py` must therefore NOT be run
    # until that follow up row has shipped: clearing the column while these
    # three routes are the only way a password is set would lock out every
    # account that has one.

    def get_legacy_password_hash(self, user_id: UUID) -> str | None:
        """The stored bcrypt hash, read straight off the item.

        A raw read rather than a model attribute, because `User` no longer
        declares the field and `model_config` is `extra="ignore"`, so loading the
        row would silently drop it.
        """
        response = self.table.get_item(Key=self.key(user_id))
        item = response.get("Item")
        if item is None:
            return None
        value = item.get("hashed_password")
        return str(value) if isinstance(value, str) and value else None

    def set_legacy_password_hash(self, user_id: UUID, hashed_password: str) -> None:
        """Write the stored bcrypt hash, leaving every other attribute alone."""
        self.update(user_id, hashed_password=hashed_password)

    def update_user(self, user_id: UUID, **changes: Any) -> User:
        current = self.get_or_raise(user_id)
        actions: list[dict[str, Any]] = []
        labels: list[str | None] = []
        for attribute in (USERNAME, EMAIL):
            new_value = changes.get(attribute)
            if new_value is None:
                continue
            old_value = getattr(current, attribute).lower()
            if new_value.lower() == old_value:
                continue
            actions.append(self.ensure_unique_action(attribute, new_value.lower(), str(user_id)))
            labels.append(attribute)
            actions.append(self.release_unique_action(attribute, old_value))
            labels.append(None)
        if not actions:
            return self.update(user_id, **changes)
        actions.append(self.update_action(user_id, **changes))
        labels.append(None)
        run_unique_transaction(actions, labels)
        return self.get_or_raise(user_id)

    def delete_user(self, user: User) -> None:
        transact_write(
            [
                self.delete_action(user.id),
                self.release_unique_action(USERNAME, user.username.lower()),
                self.release_unique_action(EMAIL, user.email.lower()),
            ]
        )


class OAuthAccountRepository(DynamoRepository[OAuthAccount]):
    def __init__(self) -> None:
        super().__init__(OAuthAccount, OAUTH_ACCOUNTS)

    def count(self) -> int:
        return len(self.scan_all())

    def get_by_provider_account(self, provider: str, provider_account_id: str) -> OAuthAccount | None:
        page = self.query("provider_account_key-index", composite_key(provider, provider_account_id), limit=1)
        return page.items[0] if page.items else None

    def get_for_user_provider(self, user_id: UUID, provider: str) -> OAuthAccount | None:
        page = self.query("user_id-provider-index", user_id, range_condition=RangeCondition.eq(provider), limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[OAuthAccount]:
        accounts = self.query_all("user_id-provider-index", user_id)
        return sorted(accounts, key=lambda account: account.created_at, reverse=True)

    def list_by_users(self, user_ids: list[UUID]) -> dict[UUID, list[OAuthAccount]]:
        return {user_id: self.list_by_user(user_id) for user_id in set(user_ids)}

    def create_actions(self, account: OAuthAccount) -> tuple[list[dict[str, Any]], list[str | None]]:
        owner = str(account.id)
        actions = [
            self.ensure_unique_action(
                PROVIDER_ACCOUNT, composite_key(account.provider, account.provider_account_id), owner
            ),
            self.ensure_unique_action(USER_PROVIDER, composite_key(account.user_id, account.provider), owner),
            self.create_action(account),
        ]
        return actions, [PROVIDER_ACCOUNT, USER_PROVIDER, None]

    def create_link(self, account: OAuthAccount) -> OAuthAccount:
        actions, labels = self.create_actions(account)
        run_unique_transaction(actions, labels)
        return account

    def delete_link(self, account: OAuthAccount) -> None:
        transact_write(
            [
                self.delete_action(account.id),
                self.release_unique_action(
                    PROVIDER_ACCOUNT, composite_key(account.provider, account.provider_account_id)
                ),
                self.release_unique_action(USER_PROVIDER, composite_key(account.user_id, account.provider)),
            ]
        )

    def delete_all_for_user(self, user_id: UUID) -> None:
        for account in self.list_by_user(user_id):
            self.delete_link(account)


class WebAuthnCredentialRepository(DynamoRepository[WebAuthnCredential]):
    def __init__(self) -> None:
        super().__init__(WebAuthnCredential, WEBAUTHN_CREDENTIALS)

    def count(self) -> int:
        return len(self.scan_all())

    def get_by_credential_id(self, credential_id: bytes) -> WebAuthnCredential | None:
        page = self.query("credential_id-index", credential_id, limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[WebAuthnCredential]:
        return self.query_all("user_id-created_at-index", user_id, scan_forward=False)

    def create_credential(self, credential: WebAuthnCredential) -> WebAuthnCredential:
        actions = [
            self.ensure_unique_action(CREDENTIAL_ID, encode_bytes(credential.credential_id), str(credential.id)),
            self.create_action(credential),
        ]
        run_unique_transaction(actions, [CREDENTIAL_ID, None])
        return credential

    def delete_credential(self, credential: WebAuthnCredential) -> None:
        transact_write(
            [
                self.delete_action(credential.id),
                self.release_unique_action(CREDENTIAL_ID, encode_bytes(credential.credential_id)),
            ]
        )

    def delete_all_for_user(self, user_id: UUID) -> None:
        for credential in self.list_by_user(user_id):
            self.delete_credential(credential)
