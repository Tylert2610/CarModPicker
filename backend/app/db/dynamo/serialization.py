"""Conversion between Pydantic models and the item shape DynamoDB stores."""

import base64
import types
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel

from app.db.dynamo.tables import TableSpec

TModel = TypeVar("TModel", bound=BaseModel)

UNIQUE_KEY_PREFIX = "#unique#"
COMPOSITE_SEPARATOR = "#"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def unique_lookup_key(attribute: str, value: str) -> str:
    """The reserved key a uniqueness reservation row is stored under."""
    return f"{UNIQUE_KEY_PREFIX}{attribute}{COMPOSITE_SEPARATOR}{value}"


def composite_key(*parts: Any) -> str:
    """Join `parts` into one sort key with the shared separator."""
    return COMPOSITE_SEPARATOR.join(str(part) for part in parts)


def encode_datetime(value: datetime) -> str:
    """Format as a UTC ISO 8601 string, assuming UTC when `value` is naive."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime(DATETIME_FORMAT)


def encode_bytes(value: bytes) -> str:
    """Base64url encode without padding, so the result is a safe key component."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_bytes(value: str) -> bytes:
    """Reverse `encode_bytes`, restoring the padding it stripped."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def to_dynamo_value(value: Any) -> Any:
    """Convert a Python value to one DynamoDB accepts, recursing into containers.


    Floats become Decimal and datetimes, bytes, UUIDs and enums become strings.
    Raises TypeError rather than storing a type this layer cannot read back.
    """
    if value is None or isinstance(value, (bool, int, str, Decimal)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return encode_datetime(value)
    if isinstance(value, (bytes, bytearray)):
        return encode_bytes(bytes(value))
    if isinstance(value, Enum):
        return to_dynamo_value(value.value)
    if isinstance(value, dict):
        return {str(key): to_dynamo_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_dynamo_value(item) for item in value]
    if isinstance(value, BaseModel):
        return to_dynamo_value(value.model_dump())
    raise TypeError(f"cannot serialize {type(value).__name__} for DynamoDB")


def from_dynamo_value(value: Any) -> Any:
    """Convert a stored value back to Python, narrowing Decimal to int or float."""
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: from_dynamo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_dynamo_value(item) for item in value]
    return value


def apply_derived_attributes(item: dict[str, Any], spec: TableSpec) -> dict[str, Any]:
    """Add the index attributes `spec` derives from other fields, in place."""
    for source, target in spec.lowercase_mirrors:
        source_value = item.get(source)
        if isinstance(source_value, str):
            item[target] = source_value.lower()
    for target, sources in spec.composite_keys:
        if all(item.get(source) is not None for source in sources):
            item[target] = composite_key(*(item[source] for source in sources))
    for target, sources in spec.coalesced_keys:
        for source in sources:
            if item.get(source) is not None:
                item[target] = item[source]
                break
    return item


def to_item(model: BaseModel, spec: TableSpec | None = None) -> dict[str, Any]:
    """Serialize `model` to an item, dropping None and adding derived attributes."""
    item: dict[str, Any] = {}
    for name, value in model.model_dump().items():
        if value is None:
            continue
        item[name] = to_dynamo_value(value)
    if spec is not None:
        apply_derived_attributes(item, spec)
    return item


def _accepts_bytes(annotation: Any) -> bool:
    """True when `annotation` is bytes or a union containing it."""
    if annotation is bytes:
        return True
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return any(_accepts_bytes(arg) for arg in get_args(annotation))
    return False


def bytes_field_names(model_cls: type[BaseModel]) -> frozenset[str]:
    """The names of the model's fields that hold bytes and so need decoding."""
    return frozenset(name for name, info in model_cls.model_fields.items() if _accepts_bytes(info.annotation))


def from_item(item: dict[str, Any], model_cls: type[TModel]) -> TModel:
    """Deserialize a stored item into `model_cls`, decoding its bytes fields."""
    data = from_dynamo_value(item)
    for name in bytes_field_names(model_cls):
        raw = data.get(name)
        if isinstance(raw, str):
            data[name] = decode_bytes(raw)
    return model_cls.model_validate(data)
