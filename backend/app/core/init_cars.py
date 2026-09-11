"""Seed car makes, models and generations from the source data on startup.

Rows are created when missing and synced when present, and rows absent from source
are left alone. Lookup is by stable slug, so pinning `slug` renames rather than duplicates.
"""

import logging
from uuid import UUID

from app.api.dependencies.repositories import Repositories, get_repositories
from app.core.car_generations_data import get_all_car_generations
from app.db.dynamo.catalog import CarGeneration, CarMake, CarModel
from app.db.dynamo.users import UniqueAttributeTaken

logger = logging.getLogger(__name__)

_CAR_GENERATION_SYNC_FIELDS = ("generation_name", "start_year", "end_year", "description", "display_name")


def _str_or_none(value: object) -> str | None:
    """`value` when it is a string, otherwise `None`."""
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    """`value` as an int when it is a non-empty int or string, otherwise `None`."""
    return int(value) if isinstance(value, (int, str)) and str(value).strip() else None


def _get_or_create_make(repos: Repositories, name: str, cache: dict[str, CarMake]) -> CarMake:
    """The make with this name, created if missing, memoised in `cache`.

    A concurrent create is tolerated by re-reading after a uniqueness failure.
    """
    cached = cache.get(name.lower())
    if cached is not None:
        return cached
    make = repos.car_makes.get_by_name(name)
    if make is None:
        try:
            make = repos.car_makes.create_unique(CarMake(name=name))
        except UniqueAttributeTaken:
            make = repos.car_makes.get_by_name(name)
            if make is None:
                raise
    cache[name.lower()] = make
    return make


def init_car_generations() -> None:
    """Create or sync every make, model and generation from the source data.

    Image URLs and timestamps are never synced, so they stay safe for curation;
    every other seeded field is overwritten from source on each run.
    """
    repos = get_repositories()

    logger.info("Initializing car generations...")

    all_generations = get_all_car_generations()
    gen_created = 0
    gen_updated = 0
    model_created = 0
    model_updated = 0
    make_cache: dict[str, CarMake] = {}
    model_cache: dict[tuple[UUID, str], CarModel] = {}
    generation_cache: dict[UUID, dict[str, CarGeneration]] = {}

    for gen_data in all_generations:
        car_make_name = _str_or_none(gen_data["make"]) or ""
        car_model_name = _str_or_none(gen_data["model"]) or ""
        model_slug = _str_or_none(gen_data["model_slug"]) or ""
        model_display_name = _str_or_none(gen_data.get("model_display_name"))
        generation_name = _str_or_none(gen_data["generation_name"]) or ""
        generation_slug = _str_or_none(gen_data["generation_slug"]) or ""

        car_make = _get_or_create_make(repos, car_make_name, make_cache)

        model_key = (car_make.id, model_slug)
        car_model = model_cache.get(model_key)
        if car_model is None:
            car_model = repos.car_models.get_by_make_and_slug(car_make.id, model_slug)
        if car_model is None:
            car_model = repos.car_models.create_unique(
                CarModel(
                    car_make_id=car_make.id,
                    slug=model_slug,
                    name=car_model_name,
                    display_name=model_display_name,
                )
            )
            model_created += 1
        elif car_model.name != car_model_name or car_model.display_name != model_display_name:
            car_model = repos.car_models.update_unique(car_model, name=car_model_name, display_name=model_display_name)
            model_updated += 1
        model_cache[model_key] = car_model

        by_slug = generation_cache.get(car_model.id)
        if by_slug is None:
            by_slug = {gen.slug: gen for gen in repos.car_generations.list_by_model(car_model.id)}
            generation_cache[car_model.id] = by_slug
        existing = by_slug.get(generation_slug)

        if existing:
            changes = {key: gen_data[key] for key in _CAR_GENERATION_SYNC_FIELDS if key in gen_data}
            if any(getattr(existing, key) != value for key, value in changes.items()):
                by_slug[generation_slug] = repos.car_generations.update_unique(existing, **changes)
            gen_updated += 1
        else:
            gen = repos.car_generations.create_unique(
                CarGeneration(
                    car_model_id=car_model.id,
                    slug=generation_slug,
                    generation_name=generation_name,
                    display_name=_str_or_none(gen_data.get("display_name")),
                    start_year=int(str(gen_data["start_year"])),
                    end_year=_int_or_none(gen_data.get("end_year")),
                    description=_str_or_none(gen_data.get("description")),
                )
            )
            by_slug[generation_slug] = gen
            gen_created += 1

    if model_created:
        logger.info(f"Created {model_created} new car model(s)")
    if model_updated:
        logger.info(f"Updated {model_updated} car model(s) to match source of truth")
    if gen_created:
        logger.info(f"Created {gen_created} new car generation(s)")
    if gen_updated:
        logger.info(f"Updated {gen_updated} car generation(s) to match source of truth")
    if not (gen_created or gen_updated or model_created or model_updated):
        logger.info("No car models or generations to create or update")
    logger.info("Car generation initialization complete")
