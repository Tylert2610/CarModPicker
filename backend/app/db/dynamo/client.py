"""The shared boto3 DynamoDB resource, and environment prefixed table lookup."""

from typing import TYPE_CHECKING, Any

import boto3

from app.core.config import settings
from app.db.dynamo.tables import USERS, TableSpec

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

_resource: "DynamoDBServiceResource | None" = None


def _region_name() -> str | None:
    """The configured region, or None when unset or "auto" so boto3 resolves it."""
    region = settings.AWS_REGION
    if not region or region == "auto":
        return None
    return region


def _resource_kwargs() -> dict[str, Any]:
    """Region and endpoint overrides for the boto3 resource, omitting unset ones."""
    kwargs: dict[str, Any] = {}
    region = _region_name()
    if region:
        kwargs["region_name"] = region
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    return kwargs


def get_resource() -> "DynamoDBServiceResource":
    """The process-wide DynamoDB resource, built on first use."""
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", **_resource_kwargs())
    return _resource


def get_client() -> "DynamoDBClient":
    """The low-level DynamoDB client behind the shared resource."""
    return get_resource().meta.client


def reset_clients() -> None:
    """Drop the memoised resource so the next call rebuilds it."""
    global _resource
    _resource = None


def table_name(spec: TableSpec) -> str:
    """The deployed table name for `spec`, prefixed for this environment."""
    return f"{settings.dynamodb_table_prefix}-{spec.suffix}"


def get_table(spec: TableSpec) -> "Table":
    """The boto3 Table for `spec` in this environment."""
    return get_resource().Table(table_name(spec))


def check_db_ready() -> bool:
    """Return True if DynamoDB is reachable (for /ready)."""
    try:
        get_client().describe_table(TableName=table_name(USERS))
        return True
    except Exception:
        return False
