"""Seed part categories from the source data on startup.

Source is the source of truth: existing rows are synced and missing ones
are created.
"""

import logging

from app.api.dependencies.repositories import get_repositories
from app.core.part_categories_data import get_all_part_categories
from app.db.dynamo.catalog import Category
from app.db.dynamo.users import UniqueAttributeTaken

logger = logging.getLogger(__name__)

_CATEGORY_SYNC_FIELDS = ("display_name", "description", "icon", "sort_order")


def init_part_categories() -> None:
    """Create or sync every part category from the source data, matching on name."""
    categories = get_repositories().categories

    logger.info("Initializing part categories...")

    all_categories = get_all_part_categories()
    created_count = 0
    updated_count = 0

    for cat_data in all_categories:
        existing = categories.get_by_name(cat_data["name"])
        if existing:
            changes = {key: cat_data.get(key) for key in _CATEGORY_SYNC_FIELDS if key in cat_data}
            if any(getattr(existing, key) != value for key, value in changes.items()):
                categories.update_unique(existing, **changes)
            updated_count += 1
        else:
            try:
                categories.create_unique(Category(**cat_data))
            except UniqueAttributeTaken:
                continue
            created_count += 1

    if created_count > 0:
        logger.info(f"Created {created_count} new part category(ies)")
    if updated_count > 0:
        logger.info(f"Updated {updated_count} part category(ies) to match source of truth")
    if created_count == 0 and updated_count == 0:
        logger.info("No part categories to create or update")
    logger.info("Part category initialization complete")
