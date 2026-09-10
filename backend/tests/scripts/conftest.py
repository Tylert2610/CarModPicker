"""Fixtures shared by the identity migration script tests.

The two migration scripts reach DynamoDB through `webbpulse.dynamodb.Repository`
rather than through `app.db.dynamo.client`, because that is the repository the
package's own stores are built on and the scripts must write through those
stores rather than around them. That means two things this module has to settle
before a moto test can work.

**The region.** `conftest.py`'s `dynamo_tables` fixture creates its tables in
`us-east-1` by patching `settings.AWS_REGION`, which only `app.db.dynamo.client`
reads. `Repository` takes its region from boto3's own resolution, so without
`AWS_DEFAULT_REGION` set to the same value it builds a resource pointed
somewhere else and every call comes back `ResourceNotFoundException`.

**The cache.** `webbpulse.dynamodb._resource` is `lru_cache`d per region and
endpoint, so a resource built inside one test's `mock_aws` block would be reused
by the next test, outside the moto patch it was created under.
`reset_resource_cache` is the package's own way out and is called on both sides
of each test.

The identity tables are created here rather than in `app/db/dynamo/tables.py`
because they are not product tables: row 4's `module.identity` creates them in
Terraform, and `TABLES` deliberately does not carry them. Their shapes are the
package's, stated in `CredentialStore` and `TotpFactorStore`.
"""

from __future__ import annotations

from typing import Any, Generator

import pytest

#: The prefix `conftest.py`'s `dynamo_tables` fixture patches onto the settings.
PREFIX = "test"

#: The region that fixture creates its tables in.
REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _package_repository_region(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Point `webbpulse.dynamodb.Repository` at moto, and never at a cached one."""
    from webbpulse.dynamodb import reset_resource_cache

    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    reset_resource_cache()
    try:
        yield
    finally:
        reset_resource_cache()


@pytest.fixture
def credentials_table(dynamo_tables: Any) -> Any:
    """The identity `credentials` table: hash `user_id`, range `credential_type`, no TTL."""
    resource = dynamo_tables
    resource.create_table(
        TableName=f"{PREFIX}-credentials",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "credential_type", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "credential_type", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return resource


@pytest.fixture
def totp_factors_table(dynamo_tables: Any) -> Any:
    """The identity `totp-factors` table: hash `user_id`, no range, and never a TTL.

    The absence of a TTL is the load bearing part, not an omission.
    `TotpFactorStore`'s docstring is explicit: a TTL attribute on this table that
    some future code sets by accident silently removes a user's second factor and
    the account quietly drops to one.
    """
    resource = dynamo_tables
    resource.create_table(
        TableName=f"{PREFIX}-totp-factors",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return resource
