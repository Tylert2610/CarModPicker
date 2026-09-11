"""The car generation seed data, loaded from `car_generations_seed/`.

Edit the per-make JSON rather than this module; `init_cars` reconciles it on the
next boot. `CAR_GENERATIONS` is `lru_cache`d, so callers must not mutate it.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from typing_extensions import NotRequired

from app.core.car_generations import load_car_generations


def slugify(value: str) -> str:
    """Convert a name into the stable, url-safe slug `init_cars` looks rows up by.

    Lowercases, collapses non-alphanumeric runs to single hyphens, and trims
    them from both ends.
    """
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


class CarGenerationData(TypedDict):
    """Type definition for car generation data."""

    generation_name: str
    start_year: int
    end_year: int | None
    description: NotRequired[str]
    display_name: NotRequired[str]
    slug: NotRequired[str]


class CarModelData(TypedDict):
    """Type definition for car model data."""

    model: str
    generations: list[CarGenerationData]
    model_display_name: NotRequired[str]
    slug: NotRequired[str]


def __getattr__(name: str) -> Any:
    """Defer the JSON load until `CAR_GENERATIONS` is actually accessed.

    The dict returned is the loader's `lru_cache`d output, so identity
    comparisons against it still hold.
    """
    if name == "CAR_GENERATIONS":
        return load_car_generations()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_all_car_generations() -> list[dict[str, str | int | None]]:
    """Flatten the nested seed structure into one row per generation.

    `model_slug` and `generation_slug` are the stable lookup keys, and a `None`
    display name tells `init_cars` to clear any stale value.
    """
    generations: list[dict[str, str | int | None]] = []
    for make, models in load_car_generations().items():
        for model_data in models:
            model = model_data["model"]
            model_display_name = model_data.get("model_display_name")
            model_slug = model_data.get("slug") or slugify(model)
            for gen in model_data["generations"]:
                gen_dict: dict[str, str | int | None] = {
                    "make": make,
                    "model": model,
                    "model_slug": model_slug,
                    "model_display_name": model_display_name,
                    "generation_name": gen["generation_name"],
                    "generation_slug": gen.get("slug") or slugify(gen["generation_name"]),
                    "display_name": gen.get("display_name"),
                    "start_year": gen["start_year"],
                    "end_year": gen["end_year"],
                }
                if "description" in gen:
                    gen_dict["description"] = gen["description"]
                generations.append(gen_dict)
    return generations
