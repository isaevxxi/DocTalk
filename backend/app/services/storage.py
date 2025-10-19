"""MinIO storage service for audio file management."""

import asyncio
import logging
from datetime import timedelta
from functools import lru_cache
from typing import BinaryIO, Optional
from uuid import UUID

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOService:
    """
    MinIO storage service for audio file operations.

    Handles:
    - Audio file uploads to S3-compatible storage
    - Presigned URL generation for secure file access
    - File deletion and cleanup
    - Bucket management
    """

    def __init__(self) -> None:
        """
        Initialize MinIO client with application settings.

        Raises:
            RuntimeError: If MinIO client initialization fails
        """
        try:
            logger.info(f"Initializing MinIO client (endpoint={settings.MINIO_ENDPOINT})")

            self.client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_USE_SSL,
                region=settings.MINIO_REGION,
            )
            self.recordings_bucket = settings.MINIO_BUCKET_RECORDINGS
            self.media_bucket = settings.MINIO_BUCKET_MEDIA
            self.exports_bucket = settings.MINIO_BUCKET_EXPORTS
            self.backups_bucket = settings.MINIO_BUCKET_BACKUPS

            logger.info("MinIO client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise RuntimeError(f"MinIO client initialization failed: {e}") from e

    async def ensure_buckets_exist(self) -> None:
        """
        Ensure all required buckets exist, create if missing.

        Should be called on application startup.
        """
        buckets = [
            self.recordings_bucket,
            self.media_bucket,
            self.exports_bucket,
            self.backups_bucket,
        ]

        def _create_bucket_if_not_exists(bucket_name: str) -> None:
            """Create bucket if it doesn't exist (sync wrapper for MinIO)."""
            try:
                if not self.client.bucket_exists(bucket_name):
                    logger.info(f"Creating bucket: {bucket_name}")
                    self.client.make_bucket(bucket_name)
                    logger.info(f"Bucket created: {bucket_name}")
                else:
                    logger.debug(f"Bucket already exists: {bucket_name}")
            except S3Error as e:
                logger.error(f"Failed to create bucket {bucket_name}: {e}")
                raise RuntimeError(f"Failed to create bucket {bucket_name}: {e}") from e

        # Run bucket creation in thread pool (MinIO client is synchronous)
        for bucket in buckets:
            await asyncio.to_thread(_create_bucket_if_not_exists, bucket)

    async def upload_recording(
        self,
        tenant_id: UUID,
        encounter_id: UUID,
        recording_id: UUID,
        file_data: BinaryIO,
        file_size: int,
        content_type: str,
        file_extension: str,
    ) -> str:
        """
        Upload audio recording to MinIO.

        Args:
            tenant_id: Tenant UUID for multi-tenant isolation
            encounter_id: Encounter UUID for organization
            recording_id: Unique recording ID
            file_data: Binary file data stream
            file_size: File size in bytes
            content_type: MIME type (e.g., 'audio/mpeg', 'audio/wav')
            file_extension: File extension (e.g., 'mp3', 'wav')

        Returns:
            Storage key (path) in MinIO bucket

        Raises:
            RuntimeError: If upload fails
        """
        # Generate hierarchical storage key: tenant_id/encounter_id/recording_id.ext
        storage_key = f"{tenant_id}/{encounter_id}/{recording_id}.{file_extension}"

        def _upload() -> None:
            """Sync wrapper for MinIO upload."""
            try:
                logger.debug(f"Uploading to MinIO: {storage_key} ({file_size} bytes)")
                self.client.put_object(
                    bucket_name=self.recordings_bucket,
                    object_name=storage_key,
                    data=file_data,
                    length=file_size,
                    content_type=content_type,
                )
                logger.info(f"Upload complete: {storage_key}")
            except S3Error as e:
                logger.error(f"Upload failed for {storage_key}: {e}")
                raise RuntimeError(f"Failed to upload recording {recording_id}: {e}") from e

        # Run upload in thread pool
        await asyncio.to_thread(_upload)
        return storage_key

    async def download_recording(self, storage_key: str) -> bytes:
        """
        Download audio recording from MinIO.

        Args:
            storage_key: Path to file in MinIO bucket

        Returns:
            File data as bytes

        Raises:
            RuntimeError: If download fails
        """

        def _download() -> bytes:
            """Sync wrapper for MinIO download."""
            response = None
            try:
                response = self.client.get_object(
                    bucket_name=self.recordings_bucket,
                    object_name=storage_key,
                )
                return response.read()
            except S3Error as e:
                raise RuntimeError(f"Failed to download recording {storage_key}: {e}") from e
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()

        return await asyncio.to_thread(_download)

    async def get_presigned_url(
        self,
        storage_key: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        Generate presigned URL for secure file access.

        Args:
            storage_key: Path to file in MinIO bucket
            expires: URL expiration time (default: 1 hour)

        Returns:
            Presigned URL for direct file access

        Raises:
            RuntimeError: If URL generation fails
        """

        def _generate_url() -> str:
            """Sync wrapper for MinIO presigned URL."""
            try:
                return self.client.presigned_get_object(
                    bucket_name=self.recordings_bucket,
                    object_name=storage_key,
                    expires=expires,
                )
            except S3Error as e:
                raise RuntimeError(
                    f"Failed to generate presigned URL for {storage_key}: {e}"
                ) from e

        return await asyncio.to_thread(_generate_url)

    async def delete_recording(self, storage_key: str) -> None:
        """
        Delete audio recording from MinIO.

        Args:
            storage_key: Path to file in MinIO bucket

        Raises:
            RuntimeError: If deletion fails
        """

        def _delete() -> None:
            """Sync wrapper for MinIO delete."""
            try:
                self.client.remove_object(
                    bucket_name=self.recordings_bucket,
                    object_name=storage_key,
                )
            except S3Error as e:
                raise RuntimeError(f"Failed to delete recording {storage_key}: {e}") from e

        await asyncio.to_thread(_delete)

    async def stat_recording(self, storage_key: str) -> Optional[dict]:
        """
        Get metadata about a recording file.

        Args:
            storage_key: Path to file in MinIO bucket

        Returns:
            File metadata dict with size, etag, last_modified, or None if not found

        Raises:
            RuntimeError: If stat operation fails
        """

        def _stat() -> Optional[dict]:
            """Sync wrapper for MinIO stat."""
            try:
                stat = self.client.stat_object(
                    bucket_name=self.recordings_bucket,
                    object_name=storage_key,
                )
                return {
                    "size": stat.size,
                    "etag": stat.etag,
                    "last_modified": stat.last_modified,
                    "content_type": stat.content_type,
                }
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return None
                raise RuntimeError(f"Failed to stat recording {storage_key}: {e}") from e

        return await asyncio.to_thread(_stat)


@lru_cache
def get_minio_service() -> MinIOService:
    """Get cached MinIO service instance."""
    return MinIOService()
