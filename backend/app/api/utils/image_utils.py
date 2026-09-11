"""
Utility functions for handling image file keys and presigned URLs.
"""

import logging
from typing import Optional

from app.api.services.storage_service import storage_service

logger = logging.getLogger(__name__)


def is_file_key(value: Optional[str]) -> bool:
    """Check if a string is an S3 file key vs a regular URL.

    File keys typically have the format: entity_type/user_hash/entity_id-unique_id.extension
    Regular URLs start with http:// or https://
    """
    if not value:
        return False

    if value.startswith(("http://", "https://")):
        return False

    if "/" in value and not value.startswith(("http://", "https://")):
        return True

    return False


def get_presigned_url_from_file_key(file_key: Optional[str]) -> Optional[str]:
    """Convert a file key to a presigned URL if it's a file key, otherwise return as-is."""
    if not file_key:
        return None

    if not is_file_key(file_key):
        return file_key

    try:
        return storage_service.get_presigned_url(file_key)
    except Exception as e:
        logger.warning(f"Failed to generate presigned URL for {file_key}: {str(e)}")
        return file_key
