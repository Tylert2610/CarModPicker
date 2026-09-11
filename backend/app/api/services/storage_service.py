"""
Secure image storage service using AWS S3.
The S3 bucket is private; presigned URLs are used for serving images.
"""

import hashlib
import logging
import os
import re
import uuid
from collections import defaultdict
from io import BytesIO
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from PIL import Image

from app.core.config import settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

_STANDARD_IMAGE_OBJECT_KEY = re.compile(r"^([a-z_]+)/[a-f0-9]{16}/[^/]+$")


def _is_test_environment() -> bool:
    """Check if we're running in a test environment."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    import sys

    if "pytest" in sys.modules:
        return True
    if os.environ.get("TESTING", "").lower() in ("true", "1", "yes"):
        return True
    return False


class StorageService:
    """Service for handling secure image uploads to S3."""

    s3_client: Optional[S3Client]
    s3_client_presigner: Optional[S3Client]
    bucket_name: Optional[str]
    max_size_bytes: int
    allowed_extensions: list[str]
    presigned_url_expiration: int

    def __init__(self) -> None:
        """Initialize S3 client with S3 bucket configuration."""
        self.bucket_name = settings.USER_IMAGES_BUCKET
        self.max_size_bytes = settings.max_image_size_bytes
        self.allowed_extensions = settings.allowed_image_extensions_list
        self.presigned_url_expiration = min(settings.PRESIGNED_URL_EXPIRATION, 7776000)
        self.s3_client = None
        self.s3_client_presigner = None

        if not self.bucket_name:
            logger.warning("USER_IMAGES_BUCKET not configured. Image uploads will be disabled.")

    def _ensure_client(self) -> None:
        """Create the S3 clients on first use, outside tests."""
        if self.s3_client is not None and self.s3_client_presigner is not None:
            return
        if not self.bucket_name or _is_test_environment():
            return

        try:
            client_kwargs = {
                "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
                "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
                "aws_session_token": settings.AWS_SESSION_TOKEN or None,
                "region_name": settings.AWS_REGION or None,
                "endpoint_url": settings.S3_ENDPOINT_URL or None,
                "config": BotoConfig(max_pool_connections=100),
            }

            s3_client = boto3.client("s3", **client_kwargs)  # type: ignore[redundant-cast]

            try:
                s3_client.head_bucket(Bucket=self.bucket_name)  # type: ignore[attr-defined]
                logger.info(f"S3 bucket '{self.bucket_name}' is accessible")
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "404":
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"S3 bucket '{self.bucket_name}' not found. Ensure the bucket is created and variables are referenced correctly.",
                    )
                elif error_code == "403":
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Access denied to S3 bucket '{self.bucket_name}'. Check bucket credentials.",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error accessing S3 bucket: {str(e)}",
                    )

            self.s3_client = s3_client
            self.s3_client_presigner = boto3.client("s3", **client_kwargs)  # type: ignore[redundant-cast]

        except Exception as e:
            logger.error(f"Failed to initialize S3 bucket client: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize storage service: {str(e)}",
            )

    def _validate_file(self, file: UploadFile) -> tuple[str, bytes]:
        """Validate uploaded file for security."""
        file_content = file.file.read()
        file.file.seek(0)

        if len(file_content) > self.max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_IMAGE_SIZE_MB}MB",
            )

        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

        filename = file.filename or ""
        file_extension = filename.split(".")[-1].lower() if "." in filename else ""

        if not file_extension or file_extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{file_extension}' not allowed. Allowed extensions: {', '.join(self.allowed_extensions)}",
            )

        try:
            image = Image.open(BytesIO(file_content))
            image.verify()

            image = Image.open(BytesIO(file_content))

            max_dimension = 10000
            if image.width > max_dimension or image.height > max_dimension:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image dimensions too large. Maximum dimension: {max_dimension}px",
                )

            if image.mode != "RGB":
                image = image.convert("RGB")  # type: ignore[assignment]
                output = BytesIO()
                image.save(output, format="JPEG", quality=95, optimize=True)
                file_content = output.getvalue()

        except Exception as e:
            logger.warning(f"Image validation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is not a valid image or is corrupted",
            )

        return file_extension, file_content

    def _process_image_to_square(self, file_content: bytes, target_size: int = 512) -> bytes:
        """Process an image to a square aspect ratio by cropping and resizing.

        The image is cropped to the center square of the original image,
        then resized to the target size.
        """
        try:
            image = Image.open(BytesIO(file_content))

            if image.mode != "RGB":
                image = image.convert("RGB")  # type: ignore[assignment]

            width, height = image.size

            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            right = left + size
            bottom = top + size

            image = image.crop((left, top, right, bottom))

            image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)

            output = BytesIO()
            image.save(output, format="JPEG", quality=95, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to process image to square: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process image to square format",
            )

    def _generate_file_key(
        self, entity_type: str, entity_id: Optional[UUID], user_id: UUID, file_extension: str
    ) -> str:
        """Generate a unique, secure file key for S3 bucket."""
        unique_id = uuid.uuid4().hex[:8]

        user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]

        if entity_id:
            filename = f"{entity_id}-{unique_id}.{file_extension}"
        else:
            filename = f"{unique_id}.{file_extension}"

        return f"{entity_type}/{user_hash}/{filename}"

    def verify_file_key_ownership(self, file_key: str, user_id: UUID) -> bool:
        """Verify that a file key belongs to a specific user."""
        if not file_key:
            return False

        parts = file_key.split("/")
        if len(parts) < 3:
            return False

        user_hash_in_key = parts[1]

        expected_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]

        return user_hash_in_key == expected_hash

    def validate_file_key(self, file_key: str) -> None:
        """Validate that a file key is safe and doesn't contain path traversal attempts."""
        if not file_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File key is required",
            )

        if ".." in file_key or file_key.startswith("/") or "//" in file_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key: path traversal detected",
            )

        pattern = r"^[a-z_]+/[a-f0-9]{16}/[^/]+$"
        if not re.match(pattern, file_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file key format",
            )

    def object_exists(self, key: str) -> bool:
        """Check if an object exists in the bucket (head_object)."""
        try:
            self._ensure_client()
        except HTTPException:
            return False
        if not self.s3_client or not self.bucket_name:
            return False
        try:
            assert self.bucket_name is not None
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            logger.warning(f"head_object failed for {key}: {e}")
            return False
        except Exception as e:
            logger.warning(f"object_exists failed for {key}: {e}")
            return False

    def upload_image(
        self,
        file: UploadFile,
        entity_type: str,
        user_id: UUID,
        entity_id: Optional[UUID] = None,
        force_square: bool = False,
    ) -> str:
        """Upload an image file to S3 bucket and return a presigned URL.

        The S3 bucket is private; we store the file key in the database
        and generate presigned URLs when serving images.
        """
        self._ensure_client()
        if not self.s3_client or not self.bucket_name:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image storage is not configured. Please contact administrator.",
            )

        file_extension, file_content = self._validate_file(file)

        if force_square:
            file_content = self._process_image_to_square(file_content)
            file_extension = "jpg"

        file_key = self._generate_file_key(entity_type, entity_id, user_id, file_extension)

        try:
            content_type = f"image/{file_extension}" if file_extension != "jpg" else "image/jpeg"

            assert self.bucket_name is not None
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
            )

            logger.info(f"Successfully uploaded image to S3 bucket: {file_key}")
            return file_key

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"S3 bucket upload error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image: {error_code}",
            )
        except BotoCoreError as e:
            logger.error(f"Boto3 error during upload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload image due to storage service error",
            )
        except Exception as e:
            logger.error(f"Unexpected error during upload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during image upload",
            )

    def get_presigned_url(self, file_key: str, expiration: Optional[int] = None) -> str:
        """Generate a presigned URL for accessing a file in S3 bucket.

        The S3 bucket is private; presigned URLs are used to serve images.
        These URLs are temporary and expire after the specified time.
        """
        self._ensure_client()
        if not self.s3_client_presigner:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image storage is not configured. Please contact administrator.",
            )

        if not file_key:
            return ""

        try:
            expiration_time = expiration or self.presigned_url_expiration

            presigned_url = self.s3_client_presigner.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_key},
                ExpiresIn=expiration_time,
            )

            return str(presigned_url)

        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {file_key}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate image URL",
            )

    def delete_image(self, file_key: str) -> bool:
        """Delete an image from S3 bucket."""
        try:
            self._ensure_client()
        except HTTPException:
            return False
        if not self.s3_client or not self.bucket_name:
            logger.warning("S3 bucket client not initialized, cannot delete image")
            return False

        if not file_key:
            return False

        try:
            assert self.bucket_name is not None
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"Successfully deleted image from S3 bucket: {file_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete image from S3 bucket: {str(e)}")
            return False

    def count_bucket_objects(self) -> int:
        """Count the total number of objects in the S3 bucket.

        Uses list_objects_v2 with pagination to handle buckets with many objects.
        """
        self._ensure_client()
        if not self.s3_client or not self.bucket_name:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image storage is not configured. Please contact administrator.",
            )

        try:
            assert self.bucket_name is not None

            total_count = 0
            continuation_token = None

            while True:
                list_kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
                if continuation_token:
                    list_kwargs["ContinuationToken"] = continuation_token

                response = self.s3_client.list_objects_v2(**list_kwargs)

                if "Contents" in response:
                    total_count += len(response["Contents"])

                if response.get("IsTruncated", False):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break

            logger.info(f"Counted {total_count} objects in S3 bucket '{self.bucket_name}'")
            return total_count

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"S3 bucket count error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to count bucket objects: {error_code}",
            )
        except BotoCoreError as e:
            logger.error(f"Boto3 error during bucket count: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to count bucket objects due to storage service error",
            )
        except Exception as e:
            logger.error(f"Unexpected error during bucket count: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while counting bucket objects",
            )

    def count_bucket_objects_by_entity_prefix(self) -> dict[str, Any]:
        """Single S3 list pass: total object count plus counts grouped by first path segment

        for keys matching the standard upload layout (entity_type/user_hash/filename).
        Keys that do not match are counted under ``other`` (legacy or stray objects).
        """
        self._ensure_client()
        if not self.s3_client or not self.bucket_name:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image storage is not configured. Please contact administrator.",
            )

        try:
            assert self.bucket_name is not None

            total = 0
            total_bytes = 0
            other = 0
            by_prefix: dict[str, int] = defaultdict(int)
            continuation_token = None

            while True:
                list_kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
                if continuation_token:
                    list_kwargs["ContinuationToken"] = continuation_token

                response = self.s3_client.list_objects_v2(**list_kwargs)

                if "Contents" in response:
                    for obj in response["Contents"]:
                        key = obj.get("Key")
                        if not key:
                            continue
                        total += 1
                        total_bytes += obj.get("Size", 0)
                        m = _STANDARD_IMAGE_OBJECT_KEY.match(key)
                        if m:
                            by_prefix[m.group(1)] += 1
                        else:
                            other += 1

                if response.get("IsTruncated", False):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break

            size_gb = round(total_bytes / (1024**3), 3)
            logger.info(
                f"Bucket '{self.bucket_name}' prefix summary: total={total}, "
                f"prefixes={len(by_prefix)}, other={other}, size_gb={size_gb}"
            )
            return {
                "total": total,
                "by_entity_type": dict(by_prefix),
                "other": other,
                "size_gb": size_gb,
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"S3 bucket prefix count error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to summarize bucket objects: {error_code}",
            )
        except BotoCoreError as e:
            logger.error(f"Boto3 error during bucket prefix count: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to summarize bucket objects due to storage service error",
            )
        except Exception as e:
            logger.error(f"Unexpected error during bucket prefix count: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while summarizing bucket objects",
            )

    def list_bucket_object_keys(self) -> list[str]:
        """List all object keys in the S3 bucket (for admin orphan cleanup).

        Uses list_objects_v2 with pagination. Use with care on large buckets.
        """
        self._ensure_client()
        if not self.s3_client or not self.bucket_name:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image storage is not configured. Please contact administrator.",
            )

        try:
            assert self.bucket_name is not None
            keys: list[str] = []
            continuation_token = None

            while True:
                list_kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
                if continuation_token:
                    list_kwargs["ContinuationToken"] = continuation_token

                response = self.s3_client.list_objects_v2(**list_kwargs)

                if "Contents" in response:
                    for obj in response["Contents"]:
                        if "Key" in obj:
                            keys.append(obj["Key"])

                if response.get("IsTruncated", False):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break

            return keys

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"S3 bucket list error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list bucket objects: {error_code}",
            )
        except BotoCoreError as e:
            logger.error(f"Boto3 error during bucket list: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list bucket objects due to storage service error",
            )
        except Exception as e:
            logger.error(f"Unexpected error during bucket list: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while listing bucket objects",
            )


storage_service = StorageService()
