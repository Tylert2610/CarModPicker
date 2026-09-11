"""`CarModPickerIdentityHooks`: who may sign in here, and what a user record is.

Section 6.3 of the identity standard draws the line this file sits on. The
package owns how signing in works, and the product owns who may sign in and what
they may do. Everything below is the second half.

Section 3 of `docs/migration/cmp-identity-plan.md` is the sketch this implements,
and where it departs from that sketch the departure is written down below rather
than left for a reader to notice.

## Why this lives in `app/composition/` and not beside the endpoint modules

The same reason Portfolio's does. This module declares no route, imports no
FastAPI, and is wired into `build_identity_router` by `composition/identity.py`,
which is the composition root. Putting it under `app/api/endpoints/auth/` would
have put product policy inside the legacy flow's package, which row 13 deletes
wholesale; this survives that deletion because it belongs to the new flow.

## The protocol is satisfied structurally, not by inheritance

Not a `BaseIdentityHooks` subclass. `IdentityHooks` is `runtime_checkable` and
every hook on it is implemented here, so inheriting would buy only the
`HookNotImplemented` fallbacks for methods that do not need them, at the cost of
an import-time coupling to the package's class.
`tests/test_identity_row5.py` asserts `isinstance(hooks, IdentityHooks)`, so the
structural claim is checked rather than assumed, and a hook the package adds in
a later release fails that assertion here rather than raising `AttributeError`
mid-flow in a deployed function.

## The mapping, hook by hook

`load_user_by_id` takes the `sub` claim, which is a string, and CarModPicker's
ids are already uuid7 strings, so unlike Portfolio there is no integer
conversion. A `sub` that does not parse as a UUID is a token this service did
not mint, and "no such user" is the honest answer, so it returns `None` rather
than raising.

`load_user_by_email` goes through `UserRepository.get_by_email`, which queries
`email_lower-index`. The package guarantees the address arrives lowercased and
stripped and that index is keyed on exactly that value, so this is one GSI query
and no second casing is tried. A fallback on another casing would make "does
this address have an account" answerable by trying two spellings and timing the
difference, which is the enumeration oracle section 5.4 of the standard closes.

`may_authenticate` refuses a disabled account, a service account and an
unverified address, in that order. That is the same set `get_current_user`
already enforces on every authenticated legacy request, and writing it twice is
not duplication: the legacy resolver guards the legacy token and this guards the
package login, and the two flows are independent until row 13 retires the first.

**It gates on `email_verified`, unlike Portfolio's, and that is deliberate.**
CarModPicker's `get_current_user` already refuses an unverified user, so a
package login that admitted one would hand out an access token that every
downstream domain then rejects, which is worse than refusing at the door.

`claims_for` returns `roles` and `username`. `username` is carried deliberately
despite being mutable: 65 frontend modules and every ownership check read it, and
the alternative is the per-request `users` read this migration exists to remove.
It is a display value and never an authorisation input; `roles` is the
authorisation input and `sub` is the identity.

`create_user` is the one hook with real work, because uniqueness here is
transactional. `UserRepository.create_user` puts the `#unique#username#` and
`#unique#email#` sentinel rows and the user row in one `TransactWriteItems`, so
a colliding username or address fails the whole write rather than leaving a row
with a half-taken reservation. A collision surfaces as `UniqueAttributeTaken`,
which the package's registration flow turns into a failed registration the
caller can retry.

`mark_email_verified` sets the column on the `users` row. It is the only hook
the package gives no default, because a product that mounted the flow and forgot
it would confirm addresses that never became verified and the failure would look
exactly like success. It raises on a missing row: the link is already consumed by
the time this is called, so the user loses it either way, and what they must not
lose is the truth about whether it worked.

`on_user_created` returns `None`. There are no default rows to write, and the
verification email is sent by the package's own `register` flow, which has the
link this hook is not given.

`user_repository` hands back the product's `UserRepository`. The package types
the return as `object` and no flow mounted in this row calls it, so nothing here
depends on it being a `webbpulse.dynamodb.Repository`; CarModPicker's is its own
class with its own uuid7 ids and its own sentinel-row uniqueness.

## `has_other_sign_in_method`, and what this product counts

New in webbpulse 0.14.0, defaulted to `False` on the package's base class, and
called by exactly one caller: `OAuthService.unlink`, which refuses to remove the
last way into an account.

**What it must not count is what `unlink` already counts itself**: the package's
own `credentials` row and the package's own `oauth-links` rows. Counting those
again cannot make the answer wrong, but a product that counted only those and
forgot everything else would be reporting the very thing the hook was added to
ask about.

So this counts every sign-in method that `unlink` does not count for itself.
Row 9 makes that five rather than three, because a user may now hold a package
passkey or a package OAuth link and nothing else:

1. a **legacy password**, `users.hashed_password`, which is not the package's
   `credentials` row and is still what the legacy `POST /api/auth/token` flow
   verifies until row 7 migrates the hashes and row 13 drops the column;
2. a **legacy passkey**, any row in `webauthn_credentials` for the user, which
   is this product's own WebAuthn table and stays live until row 13 retires it;
3. a **legacy Google link**, any row in `oauth_accounts` for the user, which is
   this product's own OAuth table and is a different table from the package's
   `oauth-links`;
4. a **package passkey**, any row in the package's `passkeys` table for the
   user, new in row 9. This is the one the package cannot infer and the one
   that matters most after migration: a user who enrolled a passkey through the
   package's M5 routes and never set a package password holds exactly one way
   in, and it is not a thing `unlink` looks at;
5. a **package OAuth link for another provider**, any row in the package's
   `oauth-links` table for the user, new in row 9.

Point 5 needs a word, because `OAuthService.unlink` does count the package's
links itself and the module docstring above says not to double count them. The
reason it is here anyway is that the two answers are taken at different moments
and this one is the conservative side: `unlink` counts the links it is about to
reduce by one, this counts what exists now, and if the two ever disagree the
disagreement makes this hook answer `True` where `unlink` would have answered
`False`. That refuses an unlink that might have been allowed, which costs a user
one support ticket, rather than permitting one that locks an account out
permanently. Every other line of this method leans the same way.

**TOTP and recovery codes are still not counted**, package or legacy. A second
factor is not a sign-in method: a user holding only a TOTP factor and no first
factor cannot sign in at all, so counting it would let `unlink` remove the last
real credential and lock the account permanently.

The two package stores are **optional**, and a `None` for either reads as "no
rows", not as an error. The composition root always supplies both, but the
legacy call sites that build these hooks without them, and the tests that do the
same, are counting only the legacy tables and should not be made to stub two
stores to do it. An absent store is a store this deployment does not have, and a
deployment without the package's passkeys table has no package passkeys in it.

TOTP is deliberately **not** counted. A second factor is not a sign-in method: a
user holding only a TOTP factor and no first factor cannot sign in at all, so
counting it would let `unlink` remove the last real credential and lock the
account permanently.

The direction of the error matters and the package's own docstring says which
way to lean. Over-counting here would let a user delete their last credential,
which has no recovery path; under-counting costs a user one support ticket. Every
read below is a plain query with no filter, and a read that fails raises rather
than answering `False`, because an answer invented from a failed read is exactly
the over-count that loses an account.

**Nothing calls this in this row.** The OAuth routes mount only when the product
supplies `oauth_states` and `oauth_links` stores, and `composition/identity.py`
supplies neither, because PR 399 creates the six M1 to M4 tables and not the two
OAuth ones. It is implemented now so that row 9, which is the row that mounts
them, is a composition change rather than a composition change plus a policy
decision made under time pressure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from webbpulse.identity import AuthenticationRefused
from webbpulse.identity.oauth import OAuthLinkStore
from webbpulse.identity.storage import PasskeyStore

from app.db.dynamo.errors import ItemNotFound
from app.db.dynamo.users import (
    OAuthAccountRepository,
    User,
    UserRepository,
    WebAuthnCredentialRepository,
)

#: What `may_authenticate` says when it refuses, and it says the same thing for
#: all three reasons on purpose. Section 5.4 requires login to answer identically
#: whether the account is missing, disabled, a service account or unverified, and
#: a message that distinguished them would put that distinction in front of an
#: attacker. The `error_code` is what the frontend branches on, and it is not
#: shown to the user.
REFUSAL_MESSAGE = "This account may not sign in."

#: The role names `claims_for` emits, most privileged first. Strings rather than
#: an enum because they travel in a JWT and are read by a TypeScript client.
SUPERUSER_ROLE = "superuser"
ADMIN_ROLE = "admin"


class CarModPickerIdentityHooks:
    """CarModPicker's `IdentityHooks`, satisfying the protocol structurally.

    Stateless apart from the three repositories it builds once, so one instance
    is built per process and shared. `DynamoRepository` resolves its table
    resource on first use rather than in `__init__`, so constructing this at
    composition time makes no AWS call and caches no boto3 object across a
    Lambda freeze.
    """

    def __init__(
        self,
        users: UserRepository | None = None,
        *,
        oauth_accounts: OAuthAccountRepository | None = None,
        webauthn_credentials: WebAuthnCredentialRepository | None = None,
        package_passkeys: PasskeyStore | None = None,
        package_oauth_links: OAuthLinkStore | None = None,
    ) -> None:
        """The three repositories and the two package stores, all injectable.

        Defaulting the three rather than requiring them keeps the composition
        root's call short: the repositories are not a configuration choice, they
        are this product's tables.

        The two package stores are different and are deliberately **not**
        defaulted. They are the package's, not this product's, and constructing
        them here would mean spelling the package's table names in a second
        place and keeping them in step by hand. `app/composition/identity.py`
        already builds exactly these two for `IdentityStores` and passes the
        same objects in, so there is one construction of each per process and
        one source of truth for each table name.

        `None` for either is a supported state and means "this deployment has no
        such store", which reads as no rows rather than as an error. See
        `has_other_sign_in_method`.
        """
        self._users = users if users is not None else UserRepository()
        self._oauth_accounts = oauth_accounts if oauth_accounts is not None else OAuthAccountRepository()
        self._webauthn_credentials = (
            webauthn_credentials if webauthn_credentials is not None else WebAuthnCredentialRepository()
        )
        self._package_passkeys = package_passkeys
        self._package_oauth_links = package_oauth_links

    # -- reads ---------------------------------------------------------------

    def load_user_by_id(self, user_id: str) -> Mapping[str, Any] | None:
        """The user whose id is this `sub`, or `None`.

        A `sub` that is not a UUID is not one of this product's ids, so it gets
        the same `None` a missing row does rather than a `ValueError` that would
        surface as a 500 on a token this service simply did not mint.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            return None
        user = self._users.get(parsed)
        return _as_mapping(user) if user is not None else None

    def load_user_by_email(self, email: str) -> Mapping[str, Any] | None:
        """The user with this address, or `None`.

        `email` is already lowercased and stripped by the package, and
        `get_by_email` queries `email_lower-index`, which is keyed on exactly
        that value. No second casing is tried; see the module docstring.
        """
        user = self._users.get_by_email(email)
        return _as_mapping(user) if user is not None else None

    # -- policy --------------------------------------------------------------

    def may_authenticate(self, user: Mapping[str, Any]) -> None:
        """Permit an enabled, verified, human account and refuse everything else.

        Returns `None` to permit and raises to refuse, which is the protocol's
        shape and the one where forgetting to return lands on the refusing side.
        """
        if user.get("disabled"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="ACCOUNT_DISABLED")
        if user.get("is_service_account"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="SERVICE_ACCOUNT")
        if not user.get("email_verified"):
            raise AuthenticationRefused(REFUSAL_MESSAGE, error_code="EMAIL_NOT_VERIFIED")

    def claims_for(self, user: Mapping[str, Any]) -> Mapping[str, Any]:
        """This product's claims: the roles list and the display username.

        `roles` is a list even when it holds one entry or none, so a consumer's
        check is one shape whatever the account is. It is ordered most
        privileged first, which is presentation rather than meaning: a consumer
        must test membership and never index.
        """
        roles: list[str] = []
        if user.get("is_superuser"):
            roles.append(SUPERUSER_ROLE)
        if user.get("is_admin"):
            roles.append(ADMIN_ROLE)
        return {"roles": roles, "username": user["username"]}

    def has_other_sign_in_method(self, user_id: str) -> bool:
        """Whether this user holds a sign-in method `unlink` does not count.

        The legacy password hash, a legacy passkey, a legacy Google link, a
        package passkey, or a package OAuth link. Not TOTP or recovery codes,
        which are second factors rather than ways in. See the module docstring
        for why each is on the list it is on, and why the package's own links
        are counted here despite `unlink` counting them too.

        An unparseable id answers `False`, which is the refusing side: an
        `unlink` for a subject this product cannot resolve should not be told
        the account has other ways in.

        The five reads are ordered cheapest first and short circuit, so the
        common case of a user with a password is one `GetItem`. The two package
        stores are queried last because they are the two this product does not
        own, and one of them, `oauth-links`, is a GSI query that cannot be read
        consistently at all.

        The package stores are keyed by the `sub` string rather than by the
        parsed UUID: `PasskeyRecord.user_id` and `OAuthLinkRecord.user_id` are
        whatever `claims_for` put in `sub`, which for this product is the
        canonical string form of the id. `str(parsed)` rather than the raw
        `user_id` argument, so a differently cased or braced spelling of the
        same id normalises to the one the package wrote.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            return False

        user = self._users.get(parsed)
        if user is not None and user.hashed_password:
            return True
        if self._webauthn_credentials.list_by_user(parsed):
            return True
        if self._oauth_accounts.list_by_user(parsed):
            return True

        subject = str(parsed)
        if self._package_passkeys is not None and self._package_passkeys.list_for_user(subject):
            return True
        return bool(self._package_oauth_links is not None and self._package_oauth_links.list_for_user(subject))

    # -- writes --------------------------------------------------------------

    def create_user(self, *, email: str, attributes: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create a CarModPicker user row for a registration and return it.

        The username comes from `attributes` when the caller supplied one and is
        otherwise derived from the address's local part, because `username` is
        required and unique here and the package has no concept of one.

        `hashed_password` is deliberately not set. The password lives in the
        package's `credentials` table, which it writes immediately after this
        returns, and a placeholder in the legacy column would be a row the
        legacy flow could try to verify against.

        The write is one `TransactWriteItems` carrying both `#unique#` sentinel
        rows and the user row, so a collision on either attribute fails the whole
        registration rather than leaving a reservation behind. It raises
        `UniqueAttributeTaken`, which the package's flow renders as a failed
        registration.
        """
        record = dict(attributes)
        record.pop("id", None)
        record.pop("hashed_password", None)
        record["email"] = email
        record["username"] = str(record.get("username") or _username_from(email))
        user = User(**record)
        return _as_mapping(self._users.create_user(user))

    def mark_email_verified(self, user_id: str) -> None:
        """Record that this user's address is confirmed, on the `users` row.

        Called only after a verification link has been consumed, so it re-checks
        nothing: it sets the column and returns.

        **Raising is the contract for a failure, and this raises on a missing
        row.** The link is spent by the time this is called, so the user loses it
        either way; what they must not lose is the truth about whether it
        worked. `UserRepository.update` raises `ItemNotFound` for a row that is
        not there, and this re-raises it as a `ValueError` naming the id, so the
        message a reader sees says which link was spent on nothing.

        No retry loop. `update` is a single conditional `UpdateItem` whose
        transient failures botocore already retries, and a second retry here
        would only lengthen the window in which the same write is in flight
        twice.
        """
        parsed = _as_uuid(user_id)
        if parsed is None:
            # Unlike `load_user_by_id`, which answers `None` because a `sub`
            # this service did not mint is honestly "no such user", there is no
            # honest no-op here. Being asked to verify an id that cannot exist
            # means the token and the table disagree, and that is a fault.
            raise ValueError(f"mark_email_verified was given {user_id!r}, which is not one of this product's user ids.")
        try:
            self._users.update(parsed, email_verified=True)
        except ItemNotFound as exc:
            raise ValueError(
                f"mark_email_verified found no user with id {parsed}. The link was consumed, "
                "so the address is not verified and the user needs a new one."
            ) from exc

    def on_user_created(self, user: Mapping[str, Any], via: str) -> None:
        """No side effects to run.

        The verification email is sent by the package's `register` flow rather
        than from here, because it needs the link the flow just issued and this
        hook is not given one. There are no default rows: a CarModPicker account
        owns nothing until its owner creates it.
        """
        del user, via

    # -- the repository ------------------------------------------------------

    def user_repository(self) -> object:
        """CarModPicker's users repository. Typed `object`, as the protocol has it."""
        return self._users


def _as_uuid(value: str) -> UUID | None:
    """`value` as a UUID, or `None` when it is not one."""
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _as_mapping(user: User) -> Mapping[str, Any]:
    """A user row as the plain mapping the hooks protocol returns.

    `model_dump` rather than the model itself, because the protocol is typed
    `Mapping[str, Any]` and the package reads it with `.get`, which a pydantic
    model does not have. `mode="json"` so the `id` reaches the package as the
    string it becomes in the `sub` claim rather than as a `UUID` the token
    encoder would have to stringify itself.
    """
    return user.model_dump(mode="json")


def _username_from(email: str) -> str:
    """A username derived from the address's local part.

    No collision suffix, unlike Portfolio's. CarModPicker's uniqueness is a
    sentinel row inside the same transaction as the user row, so a collision
    fails the registration atomically and the caller retries with a username of
    their own choosing. Checking first would be a read that the transaction
    still has to re-check, and a race between the two would produce the same
    failure anyway.
    """
    return email.partition("@")[0].strip() or "user"
