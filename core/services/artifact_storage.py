"""
Artifact storage helper that mirrors workflow/task exports to optional shared storage (S3).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from core.config import get_config

logger = logging.getLogger(__name__)


class ArtifactStorage:
    """Persist artifacts locally and optionally mirror them to S3."""

    def __init__(self):
        self.config = get_config()
        self.local_root = Path(self.config.artifact_local_root)
        self.backend = self.config.artifact_storage_backend
        self.bucket = self.config.artifact_s3_bucket
        self.prefix = self.config.artifact_s3_prefix.rstrip("/")
        self.region = self.config.artifact_s3_region
        self._s3_client = None

        self.local_root.mkdir(parents=True, exist_ok=True)

        if self.backend == "s3":
            if not self.bucket:
                raise ValueError("ARTIFACT_S3_BUCKET must be set when ARTIFACT_STORAGE_BACKEND=s3")
            self._s3_client = boto3.client("s3", region_name=self.region)
            logger.info("Artifact storage configured for S3 bucket %s", self.bucket)
        else:
            logger.info("Artifact storage using local filesystem at %s", self.local_root)

    def _category_dir(self, category: str) -> Path:
        path = self.local_root / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_key(self, category: str, filename: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{category}/{filename}"
        return f"{category}/{filename}"

    async def persist_local_file(self, category: str, filename: str, file_path: Path) -> Path:
        """
        Ensure the artifact is stored under the managed local root and mirrored to S3 if enabled.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Artifact file not found: {file_path}")

        target = self._category_dir(category) / filename
        if file_path.resolve() != target.resolve():
            shutil.copyfile(file_path, target)
        else:
            target = file_path

        if self.backend == "s3":
            await self._upload_to_s3(category, filename, target)

        return target

    async def ensure_local_file(self, category: str, filename: str) -> Optional[Path]:
        """
        Return a local path to the artifact, downloading from S3 when necessary.
        """
        target = self._category_dir(category) / filename
        if target.exists():
            return target

        if self.backend != "s3":
            return None

        key = self._build_key(category, filename)
        try:
            await asyncio.to_thread(self._s3_client.download_file, self.bucket, key, str(target))
            return target if target.exists() else None
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                logger.warning("Artifact %s not found in S3 (key=%s)", filename, key)
                return None
            raise
        except BotoCoreError as exc:
            logger.error("Failed to download artifact %s from S3: %s", filename, exc)
            return None

    async def _upload_to_s3(self, category: str, filename: str, local_path: Path) -> None:
        key = self._build_key(category, filename)
        try:
            await asyncio.to_thread(self._s3_client.upload_file, str(local_path), self.bucket, key)
            logger.info("Uploaded artifact %s to s3://%s/%s", filename, self.bucket, key)
        except (ClientError, BotoCoreError) as exc:
            logger.error("Failed to upload artifact %s to S3: %s", filename, exc)

    async def delete_file(self, category: str, filename: str) -> bool:
        """
        Delete a file from S3 (production) or local filesystem (development).
        Returns True if deleted, False if not found.
        """
        if self.backend == "s3":
            key = self._build_key(category, filename)
            try:
                await asyncio.to_thread(
                    self._s3_client.delete_object,
                    Bucket=self.bucket,
                    Key=key
                )
                logger.info("Deleted %s from s3://%s/%s", filename, self.bucket, key)
                return True
            except (ClientError, BotoCoreError) as exc:
                logger.error("Failed to delete %s from S3: %s", filename, exc)
                return False
        else:
            # Delete from local filesystem
            target = self._category_dir(category) / filename
            if target.exists():
                target.unlink()
                logger.info("Deleted %s locally from %s", filename, target)
                return True
            return False

    def generate_presigned_url(self, category: str, filename: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for downloading an artifact from S3.
        Returns None if S3 backend is not configured or if generation fails.

        Args:
            category: Artifact category (e.g., "tasks")
            filename: Name of the file
            expiration: URL expiration time in seconds (default: 1 hour)
        """
        if self.backend != "s3" or not self._s3_client:
            logger.warning("Cannot generate presigned URL: S3 backend not configured")
            return None

        key = self._build_key(category, filename)
        try:
            url = self._s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiration
            )
            logger.debug("Generated presigned URL for %s (expires in %ds)", filename, expiration)
            return url
        except (ClientError, BotoCoreError) as exc:
            logger.error("Failed to generate presigned URL for %s: %s", filename, exc)
            return None


_artifact_storage: Optional[ArtifactStorage] = None


def get_artifact_storage() -> ArtifactStorage:
    global _artifact_storage  # pylint: disable=global-statement
    if _artifact_storage is None:
        _artifact_storage = ArtifactStorage()
    return _artifact_storage

