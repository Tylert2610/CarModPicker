"""Lazy loader for the per-make car generation JSON under `car_generations_seed/`.

Callers must not mutate the returned dict: it is `lru_cache`d, so every call
hands back the same object.
"""

from __future__ import annotations

import functools
import json
from importlib.resources import files


@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict:
    """Load and memoize the merged car generations dict from the seed directory.

    Each file is a single-key object keyed by make, and make keys must be unique
    across files, which an assertion checks.
    """
    seed_dir = files("app.core").joinpath("car_generations_seed")
    merged: dict = {}
    for entry in sorted(seed_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".json"):
            continue
        payload = json.loads(entry.read_text(encoding="utf-8"))
        for make, models in payload.items():
            assert make not in merged, (
                f"Duplicate make key '{make}' across seed files " f"(found again in {entry.name})"
            )
            merged[make] = models
    return merged
