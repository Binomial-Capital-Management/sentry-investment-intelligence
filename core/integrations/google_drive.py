"""
Google Drive API helpers.
All network-bound operations run in a background thread to keep async endpoints responsive.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)


def _build_service(credentials):
    """Create a Drive API service instance without discovery cache files."""
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


async def list_files(
    credentials,
    query: Optional[str] = None,
    page_size: int = 50,
    page_token: Optional[str] = None,
    fields: str = "files(id,name,mimeType,modifiedTime,owners(emailAddress,displayName),iconLink,kind,webViewLink,size),nextPageToken",
) -> Dict[str, Any]:
    """List files accessible by the current credential."""

    def _list():
        service = _build_service(credentials)
        kwargs: Dict[str, Any] = {
            "pageSize": min(max(page_size, 1), 100),
            "fields": fields,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if query:
            kwargs["q"] = query
        if page_token:
            kwargs["pageToken"] = page_token
        return service.files().list(**kwargs).execute()

    try:
        return await asyncio.to_thread(_list)
    except HttpError as exc:
        logger.error(f"Drive list_files failed: {exc}")
        raise


async def get_metadata(credentials, file_id: str, fields: str = "id,name,mimeType,modifiedTime,owners,iconLink,size,webViewLink") -> Dict[str, Any]:
    """Fetch metadata for a specific file."""

    def _get():
        service = _build_service(credentials)
        return service.files().get(
            fileId=file_id,
            fields=fields,
            supportsAllDrives=True,
        ).execute()

    try:
        return await asyncio.to_thread(_get)
    except HttpError as exc:
        logger.error(f"Drive get_metadata failed for {file_id}: {exc}")
        raise


async def download_file(credentials, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
    """Download a binary file from Drive."""

    def _download():
        service = _build_service(credentials)
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug("Drive download %.2f%%.", status.progress() * 100)
        fh.seek(0)
        metadata = service.files().get(fileId=file_id, fields="id,name,mimeType,size,modifiedTime", supportsAllDrives=True).execute()
        return fh.read(), metadata

    try:
        return await asyncio.to_thread(_download)
    except HttpError as exc:
        logger.error(f"Drive download failed for {file_id}: {exc}")
        raise


async def export_document(credentials, file_id: str, mime_type: str) -> Tuple[bytes, Dict[str, Any]]:
    """Export Google Docs/Sheets/Slides to the requested MIME type."""

    def _export():
        service = _build_service(credentials)
        request = service.files().export_media(fileId=file_id, mimeType=mime_type)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug("Drive export %.2f%%.", status.progress() * 100)
        fh.seek(0)
        metadata = service.files().get(
            fileId=file_id,
            fields="id,name,mimeType,size,modifiedTime",
            supportsAllDrives=True,
        ).execute()
        metadata["exportedMimeType"] = mime_type
        return fh.read(), metadata

    try:
        return await asyncio.to_thread(_export)
    except HttpError as exc:
        logger.error(f"Drive export failed for {file_id}: {exc}")
        raise
