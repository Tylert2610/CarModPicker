"""
Utilities for admin bucket orphan cleanup.
Collects all file keys referenced by entities so we can safely delete only unreferenced objects.
"""

from app.api.dependencies.repositories import get_repositories
from app.api.utils.image_utils import is_file_key


def get_all_referenced_file_keys() -> set[str]:
    """Collect every file key referenced by a stored entity.

    Anything in the bucket outside this set is an orphan and safe to delete.
    """
    referenced: set[str] = set()
    repos = get_repositories()

    def _collect_image_urls(image_urls: list[str] | None) -> None:
        """Add any file keys in this image list to the referenced set."""
        if image_urls:
            for k in image_urls:
                if k and is_file_key(k):
                    referenced.add(k)

    for part in repos.parts.list_all():
        _collect_image_urls(part.image_urls)

    for user in repos.users.list_all():
        _collect_image_urls(user.image_urls)

    for car in repos.car_generations.list_all():
        _collect_image_urls(car.image_urls)

    for build_list in repos.build_lists.scan_all():
        _collect_image_urls(build_list.image_urls)

    for file_key in repos.image_source_mappings.all_file_keys():
        if file_key and is_file_key(file_key):
            referenced.add(file_key)

    return referenced
