"""The declarative shape of every DynamoDB table: keys, indexes, TTL and derived attributes."""

from dataclasses import dataclass, field
from typing import Any, Literal

KeyType = Literal["S", "N"]
Projection = Literal["ALL", "KEYS_ONLY"]


@dataclass(frozen=True)
class KeyAttribute:
    """One key attribute: its name and its DynamoDB scalar type."""

    name: str
    type: KeyType = "S"


@dataclass(frozen=True)
class IndexSpec:
    """A global secondary index: its name, its keys and its projection."""

    name: str
    hash_key: KeyAttribute
    range_key: KeyAttribute | None = None
    projection: Projection = "ALL"


@dataclass(frozen=True)
class TableSpec:
    """One table's keys, indexes, TTL and the attributes writes derive from fields."""

    suffix: str
    partition_key: KeyAttribute = field(default_factory=lambda: KeyAttribute("id"))
    sort_key: KeyAttribute | None = None
    indexes: tuple[IndexSpec, ...] = ()
    ttl_attribute: str | None = None
    lowercase_mirrors: tuple[tuple[str, str], ...] = ()
    composite_keys: tuple[tuple[str, tuple[str, ...]], ...] = ()
    coalesced_keys: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def key_attribute_names(self) -> tuple[str, ...]:
        """The table's own key attribute names, partition first."""
        names = [self.partition_key.name]
        if self.sort_key is not None:
            names.append(self.sort_key.name)
        return tuple(names)

    @property
    def is_composite(self) -> bool:
        """True when the table has a sort key as well as a partition key."""
        return self.sort_key is not None

    def index(self, name: str) -> IndexSpec:
        """The index named `name`, or KeyError when the table declares no such index."""
        for index in self.indexes:
            if index.name == name:
                return index
        raise KeyError(f"{self.suffix} has no index {name!r}")

    def attribute_definitions(self) -> list[dict[str, str]]:
        """Every key attribute across the table and its indexes, deduplicated.


        Raises ValueError when one name is declared with two different types, which
        DynamoDB would reject at create time.
        """
        seen: dict[str, str] = {}
        for attribute in self._all_key_attributes():
            existing = seen.get(attribute.name)
            if existing is not None and existing != attribute.type:
                raise ValueError(
                    f"{self.suffix}: attribute {attribute.name!r} declared as both {existing} and {attribute.type}"
                )
            seen[attribute.name] = attribute.type
        return [{"AttributeName": name, "AttributeType": type_} for name, type_ in seen.items()]

    def _all_key_attributes(self) -> list[KeyAttribute]:
        """Every key attribute of the table and of its indexes, with duplicates."""
        attributes = [self.partition_key]
        if self.sort_key is not None:
            attributes.append(self.sort_key)
        for index in self.indexes:
            attributes.append(index.hash_key)
            if index.range_key is not None:
                attributes.append(index.range_key)
        return attributes

    def key_schema(self) -> list[dict[str, str]]:
        """The table's own KeySchema, in the CreateTable shape."""
        return _key_schema(self.partition_key, self.sort_key)

    def create_table_request(self, table_name: str) -> dict[str, Any]:
        """The CreateTable request for this spec, on-demand billing."""
        request: dict[str, Any] = {
            "TableName": table_name,
            "KeySchema": self.key_schema(),
            "AttributeDefinitions": self.attribute_definitions(),
            "BillingMode": "PAY_PER_REQUEST",
        }
        if self.indexes:
            request["GlobalSecondaryIndexes"] = [
                {
                    "IndexName": index.name,
                    "KeySchema": _key_schema(index.hash_key, index.range_key),
                    "Projection": {"ProjectionType": index.projection},
                }
                for index in self.indexes
            ]
        return request


def _key_schema(hash_key: KeyAttribute, range_key: KeyAttribute | None) -> list[dict[str, str]]:
    """A KeySchema for one hash key and an optional range key."""
    schema = [{"AttributeName": hash_key.name, "KeyType": "HASH"}]
    if range_key is not None:
        schema.append({"AttributeName": range_key.name, "KeyType": "RANGE"})
    return schema


def _s(name: str) -> KeyAttribute:
    """A string key attribute named `name`."""
    return KeyAttribute(name, "S")


def _n(name: str) -> KeyAttribute:
    """A numeric key attribute named `name`."""
    return KeyAttribute(name, "N")


def gsi(
    hash_key: str, range_key: str | None = None, *, name: str | None = None, numeric_range: bool = False
) -> IndexSpec:
    """A global secondary index, naming itself after its keys when unnamed."""
    index_name = name or (f"{hash_key}-{range_key}-index" if range_key else f"{hash_key}-index")
    range_attribute = None
    if range_key is not None:
        range_attribute = _n(range_key) if numeric_range else _s(range_key)
    return IndexSpec(name=index_name, hash_key=_s(hash_key), range_key=range_attribute)


USERS = TableSpec(
    suffix="users",
    indexes=(gsi("username_lower"), gsi("email_lower")),
    lowercase_mirrors=(("username", "username_lower"), ("email", "email_lower")),
)

OAUTH_ACCOUNTS = TableSpec(
    suffix="oauth_accounts",
    indexes=(gsi("provider_account_key"), gsi("user_id", "provider")),
    composite_keys=(("provider_account_key", ("provider", "provider_account_id")),),
)

WEBAUTHN_CREDENTIALS = TableSpec(
    suffix="webauthn_credentials",
    indexes=(gsi("credential_id"), gsi("user_id", "created_at")),
)

CAR_MAKES = TableSpec(
    suffix="car_makes",
    indexes=(gsi("name_lower"),),
    lowercase_mirrors=(("name", "name_lower"),),
)

CAR_MODELS = TableSpec(
    suffix="car_models",
    indexes=(gsi("car_make_id", "slug"), gsi("car_make_id", "name_lower")),
    lowercase_mirrors=(("name", "name_lower"),),
)

CAR_GENERATIONS = TableSpec(
    suffix="car_generations",
    indexes=(gsi("car_model_id", "slug"),),
)

CATEGORIES = TableSpec(
    suffix="categories",
    indexes=(gsi("name_lower"),),
    lowercase_mirrors=(("name", "name_lower"),),
)

RETAILERS = TableSpec(
    suffix="retailers",
    indexes=(gsi("name_lower"), gsi("domain")),
    lowercase_mirrors=(("name", "name_lower"),),
)

PART_MANUFACTURERS = TableSpec(
    suffix="part_manufacturers",
    indexes=(gsi("name_lower"),),
    lowercase_mirrors=(("name", "name_lower"),),
)

PARTS = TableSpec(
    suffix="parts",
    indexes=(
        gsi("category_id", "created_at"),
        gsi("part_manufacturer_id", "part_number_normalized"),
        gsi("part_manufacturer_id", "created_at"),
        gsi("user_id", "created_at"),
        gsi("canonical_id"),
        gsi("gtin"),
    ),
    coalesced_keys=(("canonical_id", ("canonical_part_id", "id")),),
)

PART_CARS = TableSpec(
    suffix="part_cars",
    partition_key=_s("part_id"),
    sort_key=_s("car_id"),
    indexes=(gsi("car_id", "part_id"),),
)

PART_LISTINGS = TableSpec(
    suffix="part_listings",
    indexes=(gsi("part_id", "retailer_id"), gsi("product_url"), gsi("retailer_id", "updated_at")),
)

PART_PRICE_HISTORY = TableSpec(
    suffix="part_price_history",
    indexes=(gsi("part_listing_id", "observed_at"),),
)

PART_PRICE_ALERTS = TableSpec(
    suffix="part_price_alerts",
    indexes=(gsi("user_id", "part_id"), gsi("part_id")),
)

BUILD_LISTS = TableSpec(
    suffix="build_lists",
    indexes=(gsi("user_id", "created_at"), gsi("car_id", "created_at")),
)

BUILD_LIST_PARTS = TableSpec(
    suffix="build_list_parts",
    indexes=(gsi("build_list_id", "added_at"), gsi("part_id")),
)

BUILD_LIST_PHASES = TableSpec(
    suffix="build_list_phases",
    indexes=(gsi("build_list_id", "sort_order", numeric_range=True),),
)

BUILD_LIST_LABOR_ESTIMATES = TableSpec(
    suffix="build_list_labor_estimates",
    indexes=(gsi("build_list_id", "sort_order", numeric_range=True),),
)

BUILD_LOGS = TableSpec(
    suffix="build_logs",
    indexes=(gsi("build_list_id"),),
)

BUILD_LOG_POSTS = TableSpec(
    suffix="build_log_posts",
    indexes=(gsi("build_log_id", "created_at"), gsi("user_id", "created_at")),
)

VOTES = TableSpec(
    suffix="votes",
    indexes=(gsi("entity_key", "user_id"), gsi("user_id", "created_at")),
    composite_keys=(("entity_key", ("entity_type", "entity_id")),),
)

REPORTS = TableSpec(
    suffix="reports",
    indexes=(gsi("entity_key", "user_id"), gsi("user_id", "created_at"), gsi("status", "created_at")),
    composite_keys=(("entity_key", ("entity_type", "entity_id")),),
)

BUG_REPORTS = TableSpec(
    suffix="bug_reports",
    indexes=(gsi("user_id", "created_at"), gsi("status", "created_at")),
)

IMAGE_SOURCE_MAPPINGS = TableSpec(
    suffix="image_source_mappings",
    indexes=(gsi("source_url"),),
)

APP_SETTINGS = TableSpec(
    suffix="app_settings",
    partition_key=_n("id"),
)

RATE_LIMITS = TableSpec(
    suffix="rate-limits",
    partition_key=_s("pk"),
    ttl_attribute="expires_at",
)


TABLES: tuple[TableSpec, ...] = (
    USERS,
    OAUTH_ACCOUNTS,
    WEBAUTHN_CREDENTIALS,
    CAR_MAKES,
    CAR_MODELS,
    CAR_GENERATIONS,
    CATEGORIES,
    RETAILERS,
    PART_MANUFACTURERS,
    PARTS,
    PART_CARS,
    PART_LISTINGS,
    PART_PRICE_HISTORY,
    PART_PRICE_ALERTS,
    BUILD_LISTS,
    BUILD_LIST_PARTS,
    BUILD_LIST_PHASES,
    BUILD_LIST_LABOR_ESTIMATES,
    BUILD_LOGS,
    BUILD_LOG_POSTS,
    VOTES,
    REPORTS,
    BUG_REPORTS,
    IMAGE_SOURCE_MAPPINGS,
    APP_SETTINGS,
    RATE_LIMITS,
)


def table_by_suffix(suffix: str) -> TableSpec:
    """The spec whose suffix is `suffix`, or KeyError when none matches."""
    for spec in TABLES:
        if spec.suffix == suffix:
            return spec
    raise KeyError(f"no table spec with suffix {suffix!r}")


def export_table_definitions() -> dict[str, dict[str, Any]]:
    """Every table's shape keyed by suffix, for Terraform to consume."""
    return {spec.suffix: _table_definition(spec) for spec in TABLES}


def _table_definition(spec: TableSpec) -> dict[str, Any]:
    """One table's keys, indexes and TTL in the shape Terraform reads."""
    return {
        "hash_key": spec.partition_key.name,
        "range_key": spec.sort_key.name if spec.sort_key is not None else None,
        "attributes": [
            {"name": definition["AttributeName"], "type": definition["AttributeType"]}
            for definition in spec.attribute_definitions()
        ],
        "global_secondary_indexes": [
            {
                "name": index.name,
                "hash_key": index.hash_key.name,
                "range_key": index.range_key.name if index.range_key is not None else None,
                "projection_type": index.projection,
            }
            for index in spec.indexes
        ],
        "ttl_attribute": spec.ttl_attribute,
    }
