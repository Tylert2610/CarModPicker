"""Exceptions raised by the DynamoDB repository layer."""

from typing import Any


class DynamoError(Exception):
    """Base class for every error this layer raises."""


class ItemNotFound(DynamoError):
    """No item exists in `table` under `key`."""

    def __init__(self, table: str, key: dict[str, Any]) -> None:
        """Record the table and key that had no item."""
        self.table = table
        self.key = key
        super().__init__(f"{table}: no item with key {key}")


class ConditionFailed(DynamoError):
    """A conditional write was rejected because its condition did not hold."""

    def __init__(self, table: str, condition: str, key: dict[str, Any] | None = None) -> None:
        """Record the table, the condition expression, and the key it guarded."""
        self.table = table
        self.condition = condition
        self.key = key
        super().__init__(f"{table}: condition failed ({condition}) for key {key}")


class TransactionCanceled(DynamoError):
    """A transactional write was cancelled, carrying DynamoDB's per-item reasons."""

    def __init__(self, reasons: list[dict[str, Any]]) -> None:
        """Record DynamoDB's cancellation reasons, one per item in the transaction."""
        self.reasons = reasons
        super().__init__(f"transaction canceled: {reasons}")

    @property
    def conditional_check_failed(self) -> bool:
        """True when any item was cancelled by a failed conditional check."""
        return any(reason.get("Code") == "ConditionalCheckFailed" for reason in self.reasons)
