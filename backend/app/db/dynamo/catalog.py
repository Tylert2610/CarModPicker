from datetime import datetime
from typing import Any, Iterable, TypeVar
from uuid import UUID

from pydantic import Field, model_validator
from uuid6 import uuid7

from app.core.car_generations_data import slugify
from app.db.dynamo.models import DynamoModel, TimestampedDynamoModel, utc_now
from app.db.dynamo.repository import DynamoRepository, Page, RangeCondition, transact_write
from app.db.dynamo.serialization import composite_key, encode_datetime
from app.db.dynamo.tables import (
    CAR_GENERATIONS,
    CAR_MAKES,
    CAR_MODELS,
    CATEGORIES,
    PART_CARS,
    PART_LISTINGS,
    PART_MANUFACTURERS,
    PART_PRICE_HISTORY,
    PARTS,
    RETAILERS,
)
from app.db.dynamo.users import run_unique_transaction

NAME = "name"
DOMAIN = "domain"
CAR_MODEL_NAME = "car_model_name"
CAR_MODEL_SLUG = "car_model_slug"
CAR_GENERATION_SLUG = "car_generation_slug"
GTIN = "gtin"
MANUFACTURER_PART_NUMBER = "manufacturer_part_number"

UniquePair = tuple[str, str]


class CarMake(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str


class CarModel(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    car_make_id: UUID
    slug: str = ""
    name: str
    display_name: str | None = None

    @model_validator(mode="after")
    def _fill_slug(self) -> "CarModel":
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        return self


class CarGeneration(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    car_model_id: UUID
    slug: str = ""
    generation_name: str
    display_name: str | None = None
    start_year: int
    end_year: int | None = None
    description: str | None = None
    image_urls: list[str] | None = None

    @model_validator(mode="after")
    def _fill_slug(self) -> "CarGeneration":
        if not self.slug and self.generation_name:
            self.slug = slugify(self.generation_name)
        return self


class Category(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    is_active: bool = True
    sort_order: int = 0


class PartManufacturer(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    description: str | None = None
    is_active: bool = True


class Retailer(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    domain: str | None = None
    base_url: str | None = None
    is_active: bool = True


class Part(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    description: str | None = None
    image_urls: list[str] | None = None
    category_id: UUID
    user_id: UUID
    is_universal: bool = False
    part_manufacturer_id: UUID | None = None
    part_number: str | None = None
    part_number_normalized: str | None = None
    gtin: str | None = None
    canonical_part_id: UUID | None = None
    edit_count: int = 0
    car_ids: list[UUID] = Field(default_factory=list)
    best_price_cents: int | None = None
    net_votes: int = 0
    #: Seam 2's tombstone pair. Row 23 adds the attributes and the reads that
    #: honour them; row 28 is what starts writing them, when the `part-purge`
    #: stream consumer exists to drain the cascade. Rows written before row 23
    #: lack both and read as not deleted.
    deleted: bool = False
    deleted_at: datetime | None = None


class PartCar(DynamoModel):
    id: str | None = None  # pyright: ignore[reportIncompatibleVariableOverride]
    part_id: UUID
    car_id: UUID


class PartListing(TimestampedDynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    part_id: UUID
    retailer_id: UUID
    product_url: str | None = None
    last_known_price_cents: int | None = None
    last_price_updated_at: datetime | None = None


class PartPriceHistory(DynamoModel):
    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    part_listing_id: UUID
    price_cents: int
    observed_at: datetime = Field(default_factory=utc_now)


TModel = TypeVar("TModel", bound=DynamoModel)
TTimestamped = TypeVar("TTimestamped", bound=TimestampedDynamoModel)


def _ids(values: Iterable[UUID]) -> list[str]:
    return [str(value) for value in dict.fromkeys(values)]


class CatalogRepository(DynamoRepository[TModel]):
    def count(self) -> int:
        return len(self.scan_all())

    def list_all(self) -> list[TModel]:
        return self.scan_all()

    def get_many(self, ids: Iterable[UUID]) -> dict[UUID, TModel]:
        keys = _ids(ids)
        if not keys:
            return {}
        return {UUID(str(model.id)): model for model in self.batch_get(keys)}

    def first(self, index: str, key_value: Any, range_condition: RangeCondition | None = None) -> TModel | None:
        page = self.query(index, key_value, range_condition=range_condition, limit=1)
        return page.items[0] if page.items else None


class UniqueCatalogRepository(CatalogRepository[TTimestamped]):
    def unique_pairs(self, model: TTimestamped) -> list[UniquePair]:
        return []

    def create_unique(self, model: TTimestamped, extra_actions: Iterable[dict[str, Any]] = ()) -> TTimestamped:
        actions: list[dict[str, Any]] = [self.create_action(model), *extra_actions]
        labels: list[str | None] = [None] * len(actions)
        for label, value in self.unique_pairs(model):
            actions.append(self.ensure_unique_action(label, value, str(model.id)))
            labels.append(label)
        run_unique_transaction(actions, labels)
        return model

    def save_unique(
        self,
        previous: TTimestamped,
        updated: TTimestamped,
        extra_actions: Iterable[dict[str, Any]] = (),
    ) -> TTimestamped:
        updated.touch()
        before = set(self.unique_pairs(previous))
        after = set(self.unique_pairs(updated))
        actions: list[dict[str, Any]] = [self.put_action(updated), *extra_actions]
        labels: list[str | None] = [None] * len(actions)
        for label, value in sorted(after - before):
            actions.append(self.ensure_unique_action(label, value, str(updated.id)))
            labels.append(label)
        for label, value in sorted(before - after):
            actions.append(self.release_unique_action(label, value))
            labels.append(None)
        run_unique_transaction(actions, labels)
        return updated

    def update_unique(self, entity: TTimestamped, **changes: Any) -> TTimestamped:
        return self.save_unique(entity, entity.model_copy(update=changes))

    def delete_unique(self, entity: TTimestamped, extra_actions: Iterable[dict[str, Any]] = ()) -> None:
        actions: list[dict[str, Any]] = [self.delete_action(str(entity.id)), *extra_actions]
        for label, value in self.unique_pairs(entity):
            actions.append(self.release_unique_action(label, value))
        transact_write(actions)


class NamedRepository(UniqueCatalogRepository[TTimestamped]):
    def name_of(self, model: TTimestamped) -> str:
        return str(getattr(model, "name"))

    def unique_pairs(self, model: TTimestamped) -> list[UniquePair]:
        return [(NAME, self.name_of(model).strip().lower())]

    def get_by_name(self, name: str) -> TTimestamped | None:
        return self.first("name_lower-index", name.strip().lower())

    def list_sorted(self, *, active_only: bool = False) -> list[TTimestamped]:
        items = self.scan_all()
        if active_only:
            items = [item for item in items if getattr(item, "is_active", True)]
        return sorted(items, key=lambda item: (self.name_of(item).lower(), str(item.id)))


class CarMakeRepository(NamedRepository[CarMake]):
    def __init__(self) -> None:
        super().__init__(CarMake, CAR_MAKES)


class CarModelRepository(UniqueCatalogRepository[CarModel]):
    def __init__(self) -> None:
        super().__init__(CarModel, CAR_MODELS)

    def unique_pairs(self, model: CarModel) -> list[UniquePair]:
        return [
            (CAR_MODEL_NAME, composite_key(str(model.car_make_id), model.name.strip().lower())),
            (CAR_MODEL_SLUG, composite_key(str(model.car_make_id), model.slug)),
        ]

    def get_by_make_and_slug(self, car_make_id: UUID, slug: str) -> CarModel | None:
        return self.first("car_make_id-slug-index", str(car_make_id), RangeCondition.eq(slug))

    def get_by_make_and_name(self, car_make_id: UUID, name: str) -> CarModel | None:
        return self.first("car_make_id-name_lower-index", str(car_make_id), RangeCondition.eq(name.strip().lower()))

    def list_by_make(self, car_make_id: UUID) -> list[CarModel]:
        return self.query_all("car_make_id-slug-index", str(car_make_id))


class CarGenerationRepository(UniqueCatalogRepository[CarGeneration]):
    def __init__(self) -> None:
        super().__init__(CarGeneration, CAR_GENERATIONS)

    def unique_pairs(self, model: CarGeneration) -> list[UniquePair]:
        return [(CAR_GENERATION_SLUG, composite_key(str(model.car_model_id), model.slug))]

    def get_by_model_and_slug(self, car_model_id: UUID, slug: str) -> CarGeneration | None:
        return self.first("car_model_id-slug-index", str(car_model_id), RangeCondition.eq(slug))

    def list_by_model(self, car_model_id: UUID) -> list[CarGeneration]:
        return self.query_all("car_model_id-slug-index", str(car_model_id))


class CategoryRepository(NamedRepository[Category]):
    def __init__(self) -> None:
        super().__init__(Category, CATEGORIES)

    def list_active(self) -> list[Category]:
        active = [category for category in self.scan_all() if category.is_active]
        return sorted(active, key=lambda category: (category.sort_order, category.name.lower(), str(category.id)))


class PartManufacturerRepository(NamedRepository[PartManufacturer]):
    def __init__(self) -> None:
        super().__init__(PartManufacturer, PART_MANUFACTURERS)


class RetailerRepository(NamedRepository[Retailer]):
    def __init__(self) -> None:
        super().__init__(Retailer, RETAILERS)

    def unique_pairs(self, model: Retailer) -> list[UniquePair]:
        pairs = super().unique_pairs(model)
        if model.domain:
            pairs.append((DOMAIN, model.domain.strip().lower()))
        return pairs

    def get_by_domain(self, domain: str) -> Retailer | None:
        return self.first("domain-index", domain.strip().lower())


class PartRepository(UniqueCatalogRepository[Part]):
    def __init__(self) -> None:
        super().__init__(Part, PARTS)

    def unique_pairs(self, model: Part) -> list[UniquePair]:
        if model.canonical_part_id is not None:
            return []
        pairs: list[UniquePair] = []
        if model.gtin:
            pairs.append((GTIN, model.gtin))
        if model.part_manufacturer_id is not None and model.part_number_normalized:
            pairs.append(
                (MANUFACTURER_PART_NUMBER, composite_key(str(model.part_manufacturer_id), model.part_number_normalized))
            )
        return pairs

    def list_by_gtin(self, gtin: str) -> list[Part]:
        return self.query_all("gtin-index", gtin)

    def list_by_manufacturer_part_number(self, part_manufacturer_id: UUID, part_number_normalized: str) -> list[Part]:
        return self.query_all(
            "part_manufacturer_id-part_number_normalized-index",
            str(part_manufacturer_id),
            range_condition=RangeCondition.eq(part_number_normalized),
        )

    def page_by_category(self, category_id: UUID, *, limit: int, cursor: str | None) -> Page[Part]:
        return self.query(
            "category_id-created_at-index", str(category_id), limit=limit, cursor=cursor, scan_forward=False
        )

    def list_by_category(self, category_id: UUID) -> list[Part]:
        return self.query_all("category_id-created_at-index", str(category_id), scan_forward=False)

    def page_by_manufacturer(self, part_manufacturer_id: UUID, *, limit: int, cursor: str | None) -> Page[Part]:
        return self.query(
            "part_manufacturer_id-created_at-index",
            str(part_manufacturer_id),
            limit=limit,
            cursor=cursor,
            scan_forward=False,
        )

    def list_by_manufacturer(self, part_manufacturer_id: UUID) -> list[Part]:
        return self.query_all("part_manufacturer_id-created_at-index", str(part_manufacturer_id), scan_forward=False)

    def list_by_user(self, user_id: UUID) -> list[Part]:
        return self.query_all("user_id-created_at-index", str(user_id), scan_forward=False)

    def list_link_group(self, canonical_id: UUID) -> list[Part]:
        return self.query_all("canonical_id-index", str(canonical_id))

    def list_canonical(self) -> list[Part]:
        return [part for part in self.scan_all() if part.canonical_part_id is None]

    def count_by_category(self, category_id: UUID) -> int:
        return len(self.list_by_category(category_id))

    def count_by_manufacturer(self, part_manufacturer_id: UUID) -> int:
        return len(self.list_by_manufacturer(part_manufacturer_id))

    def count_by_user(self, user_id: UUID) -> int:
        return len(self.list_by_user(user_id))


class PartCarRepository(DynamoRepository[PartCar]):
    def __init__(self) -> None:
        super().__init__(PartCar, PART_CARS)

    def count(self) -> int:
        return len(self.scan_all())

    def car_ids_for_part(self, part_id: UUID) -> list[UUID]:
        return [row.car_id for row in self.query_all(None, str(part_id))]

    def part_ids_for_car(self, car_id: UUID) -> list[UUID]:
        return [row.part_id for row in self.query_all("car_id-part_id-index", str(car_id))]

    def part_ids_for_cars(self, car_ids: Iterable[UUID]) -> set[UUID]:
        found: set[UUID] = set()
        for car_id in dict.fromkeys(car_ids):
            found.update(self.part_ids_for_car(car_id))
        return found

    def link_action(self, part_id: UUID, car_id: UUID) -> dict[str, Any]:
        return self.put_action(PartCar(part_id=part_id, car_id=car_id))

    def unlink_action(self, part_id: UUID, car_id: UUID) -> dict[str, Any]:
        return self.delete_action(str(part_id), str(car_id))

    def sync_actions(self, part_id: UUID, before: Iterable[UUID], after: Iterable[UUID]) -> list[dict[str, Any]]:
        previous = set(before)
        wanted = set(after)
        actions = [self.link_action(part_id, car_id) for car_id in sorted(wanted - previous, key=str)]
        actions.extend(self.unlink_action(part_id, car_id) for car_id in sorted(previous - wanted, key=str))
        return actions

    def delete_for_part(self, part_id: UUID) -> None:
        keys = [(str(part_id), str(car_id)) for car_id in self.car_ids_for_part(part_id)]
        if keys:
            self.batch_delete(keys)

    def delete_for_car(self, car_id: UUID) -> None:
        keys = [(str(part_id), str(car_id)) for part_id in self.part_ids_for_car(car_id)]
        if keys:
            self.batch_delete(keys)


class PartListingRepository(CatalogRepository[PartListing]):
    def __init__(self) -> None:
        super().__init__(PartListing, PART_LISTINGS)

    def list_by_part(self, part_id: UUID) -> list[PartListing]:
        return self.query_all("part_id-retailer_id-index", str(part_id))

    def list_by_parts(self, part_ids: Iterable[UUID]) -> list[PartListing]:
        listings: list[PartListing] = []
        for part_id in dict.fromkeys(part_ids):
            listings.extend(self.list_by_part(part_id))
        return listings

    def get_by_part_and_retailer(self, part_id: UUID, retailer_id: UUID) -> PartListing | None:
        return self.first("part_id-retailer_id-index", str(part_id), RangeCondition.eq(str(retailer_id)))

    def list_by_product_url(self, product_url: str) -> list[PartListing]:
        return self.query_all("product_url-index", product_url)

    def get_by_product_url(self, product_url: str) -> PartListing | None:
        return self.first("product_url-index", product_url)

    def list_by_retailer(self, retailer_id: UUID) -> list[PartListing]:
        return self.query_all("retailer_id-updated_at-index", str(retailer_id))

    def count_by_retailer(self, retailer_id: UUID) -> int:
        return len(self.list_by_retailer(retailer_id))

    def delete_for_part(self, part_id: UUID) -> list[PartListing]:
        listings = self.list_by_part(part_id)
        if listings:
            self.batch_delete([str(listing.id) for listing in listings])
        return listings


class PartPriceHistoryRepository(CatalogRepository[PartPriceHistory]):
    def __init__(self) -> None:
        super().__init__(PartPriceHistory, PART_PRICE_HISTORY)

    def list_by_listing(
        self,
        part_listing_id: UUID,
        *,
        since: datetime | None = None,
        newest_first: bool = False,
    ) -> list[PartPriceHistory]:
        condition = RangeCondition.gte(encode_datetime(since)) if since is not None else None
        return self.query_all(
            "part_listing_id-observed_at-index",
            str(part_listing_id),
            range_condition=condition,
            scan_forward=not newest_first,
        )

    def latest_before(self, part_listing_id: UUID, cutoff: datetime) -> PartPriceHistory | None:
        page = self.query(
            "part_listing_id-observed_at-index",
            str(part_listing_id),
            range_condition=RangeCondition.lt(encode_datetime(cutoff)),
            limit=1,
            scan_forward=False,
        )
        return page.items[0] if page.items else None

    def find_between(self, part_listing_id: UUID, start: datetime, end: datetime) -> PartPriceHistory | None:
        return self.first(
            "part_listing_id-observed_at-index",
            str(part_listing_id),
            RangeCondition.between(encode_datetime(start), encode_datetime(end)),
        )

    def delete_for_listing(self, part_listing_id: UUID) -> None:
        rows = self.list_by_listing(part_listing_id)
        if rows:
            self.batch_delete([str(row.id) for row in rows])
