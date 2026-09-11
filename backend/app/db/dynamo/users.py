"""Users, their OAuth links and their WebAuthn credentials, with uniqueness enforced by transaction."""

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
    """A username, email, provider link or credential id is already claimed."""

    def __init__(self, attribute: str) -> None:
        """Record which attribute was already taken."""
        self.attribute = attribute
        super().__init__(f"{attribute} is already taken")


class User(TimestampedDynamoModel):
    """A user account, its profile, its subscription and its tombstone flags."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    username: str
    email: str
    image_urls: list[str] | None = None
    email_verified: bool = False
    hashed_password: str | None = None
    disabled: bool = False
    is_superuser: bool = False
    is_admin: bool = False
    is_service_account: bool = False
    subscription_tier: str = "free"
    subscription_expires_at: datetime | None = None
    subscription_status: str = "active"
    totp_secret: str | None = None
    totp_enabled: bool = False
    session_expire_minutes: int | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    reddit_url: str | None = None
    youtube_url: str | None = None
    tiktok_url: str | None = None
    deleted: bool = False
    deleted_at: datetime | None = None


class OAuthAccount(DynamoModel):
    """A third party identity linked to a user account."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    provider: str
    provider_account_id: str
    email: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class WebAuthnCredential(DynamoModel):
    """A registered passkey: its key material, counter and metadata."""

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
    """Run a transaction, raising UniqueAttributeTaken for a labelled failed claim.


    `labels` runs parallel to `actions`: a label names the attribute an action
    claims, and None marks an action whose failure is not a uniqueness conflict.
    """
    try:
        transact_write(actions)
    except TransactionCanceled as exc:
        for reason, label in zip(exc.reasons, labels):
            if label is not None and reason.get("Code") == "ConditionalCheckFailed":
                raise UniqueAttributeTaken(label) from exc
        raise


class UserRepository(DynamoRepository[User]):
    """User accounts, with username and email uniqueness held by reservation rows."""

    def __init__(self) -> None:
        """Bind to the users table."""
        super().__init__(User, USERS)

    def get_by_username(self, username: str) -> User | None:
        """The user with this username, matched case insensitively."""
        page = self.query("username_lower-index", username.lower(), limit=1)
        return page.items[0] if page.items else None

    def get_by_email(self, email: str) -> User | None:
        """The user with this email, matched case insensitively."""
        page = self.query("email_lower-index", email.lower(), limit=1)
        return page.items[0] if page.items else None

    def get_many(self, user_ids: list[UUID]) -> dict[UUID, User]:
        """The users for these ids, keyed by id, skipping missing and duplicate ids."""
        unique_ids = list({user_id for user_id in user_ids if user_id is not None})
        return {user.id: user for user in self.batch_get(unique_ids)} if unique_ids else {}

    def list_all(self) -> list[User]:
        """Every user, tombstoned ones included."""
        return self.scan_all()

    def search(self, term: str) -> list[User]:
        """Users matching `term`, excluding tombstoned rows.

        The only user read that surfaces profiles as results rather than as an
        author, so deleted accounts must be filtered out server-side here.
        """
        needle = term.lower()
        matches = Attr("username_lower").contains(needle) | Attr("email_lower").contains(needle)
        return self.scan_all(filter_expression=matches & _not_tombstoned())

    def count(self) -> int:
        """How many users exist."""
        return len(self.scan_all())

    def list_active_superusers(self) -> list[User]:
        """Superusers that are not disabled."""
        return self.scan_all(filter_expression=Attr("is_superuser").eq(True) & Attr("disabled").eq(False))

    def list_service_accounts(self) -> list[User]:
        """Accounts flagged as service accounts."""
        return self.scan_all(filter_expression=Attr("is_service_account").eq(True))

    def create_actions(self, user: User) -> tuple[list[dict[str, Any]], list[str | None]]:
        """The actions and labels that create a user and claim its username and email."""
        owner = str(user.id)
        actions = [
            self.ensure_unique_action(USERNAME, user.username.lower(), owner),
            self.ensure_unique_action(EMAIL, user.email.lower(), owner),
            self.create_action(user),
        ]
        return actions, [USERNAME, EMAIL, None]

    def create_user(self, user: User) -> User:
        """Create a user, raising UniqueAttributeTaken if its username or email is claimed."""
        actions, labels = self.create_actions(user)
        run_unique_transaction(actions, labels)
        return user

    def update_user(self, user_id: UUID, **changes: Any) -> User:
        """Apply changes, moving the username and email reservations when either changes."""
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
        """Hard delete a user and release its username and email reservations."""
        transact_write(
            [
                self.delete_action(user.id),
                self.release_unique_action(USERNAME, user.username.lower()),
                self.release_unique_action(EMAIL, user.email.lower()),
            ]
        )


class OAuthAccountRepository(DynamoRepository[OAuthAccount]):
    """Third party identity links, unique per provider account and per user provider."""

    def __init__(self) -> None:
        """Bind to the OAuth accounts table."""
        super().__init__(OAuthAccount, OAUTH_ACCOUNTS)

    def count(self) -> int:
        """How many OAuth links exist."""
        return len(self.scan_all())

    def get_by_provider_account(self, provider: str, provider_account_id: str) -> OAuthAccount | None:
        """The link for this provider's account id, or None."""
        page = self.query("provider_account_key-index", composite_key(provider, provider_account_id), limit=1)
        return page.items[0] if page.items else None

    def get_for_user_provider(self, user_id: UUID, provider: str) -> OAuthAccount | None:
        """This user's link to this provider, or None."""
        page = self.query("user_id-provider-index", user_id, range_condition=RangeCondition.eq(provider), limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[OAuthAccount]:
        """This user's links, newest first."""
        accounts = self.query_all("user_id-provider-index", user_id)
        return sorted(accounts, key=lambda account: account.created_at, reverse=True)

    def list_by_users(self, user_ids: list[UUID]) -> dict[UUID, list[OAuthAccount]]:
        """Each user's links, keyed by user id."""
        return {user_id: self.list_by_user(user_id) for user_id in set(user_ids)}

    def create_actions(self, account: OAuthAccount) -> tuple[list[dict[str, Any]], list[str | None]]:
        """The actions and labels that create a link and claim both of its unique keys."""
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
        """Create a link, raising UniqueAttributeTaken if either key is claimed."""
        actions, labels = self.create_actions(account)
        run_unique_transaction(actions, labels)
        return account

    def delete_link(self, account: OAuthAccount) -> None:
        """Delete a link and release both of its reservations."""
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
        """Delete every link this user holds."""
        for account in self.list_by_user(user_id):
            self.delete_link(account)


class WebAuthnCredentialRepository(DynamoRepository[WebAuthnCredential]):
    """Registered passkeys, unique by credential id."""

    def __init__(self) -> None:
        """Bind to the WebAuthn credentials table."""
        super().__init__(WebAuthnCredential, WEBAUTHN_CREDENTIALS)

    def count(self) -> int:
        """How many credentials exist."""
        return len(self.scan_all())

    def get_by_credential_id(self, credential_id: bytes) -> WebAuthnCredential | None:
        """The credential with this id, or None."""
        page = self.query("credential_id-index", credential_id, limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[WebAuthnCredential]:
        """This user's credentials, newest first."""
        return self.query_all("user_id-created_at-index", user_id, scan_forward=False)

    def create_credential(self, credential: WebAuthnCredential) -> WebAuthnCredential:
        """Register a credential, raising UniqueAttributeTaken if its id is claimed."""
        actions = [
            self.ensure_unique_action(CREDENTIAL_ID, encode_bytes(credential.credential_id), str(credential.id)),
            self.create_action(credential),
        ]
        run_unique_transaction(actions, [CREDENTIAL_ID, None])
        return credential

    def delete_credential(self, credential: WebAuthnCredential) -> None:
        """Delete a credential and release its id reservation."""
        transact_write(
            [
                self.delete_action(credential.id),
                self.release_unique_action(CREDENTIAL_ID, encode_bytes(credential.credential_id)),
            ]
        )

    def delete_all_for_user(self, user_id: UUID) -> None:
        """Delete every credential this user holds."""
        for credential in self.list_by_user(user_id):
            self.delete_credential(credential)
