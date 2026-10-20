"""
Google Drive tools exposed to agents.
Leverages the integration service for credential management and reuses file extraction utilities.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agents import function_tool
from googleapiclient.errors import HttpError

from core.agents.file_tools import extract_file_preview_from_bytes
from core.integrations import google_drive as drive_api
from core.services.integration_service import (
    build_authorized_credentials,
    get_drive_credential,
)
from core.utils.context_utils import get_drive_context, get_user_id


async def _resolve_drive_credential():
    """Resolve the current Drive credential using context or database lookup."""
    user_id = get_user_id()
    if not user_id:
        raise ValueError("No user context available for Google Drive access")

    ctx = get_drive_context()
    credential = None
    if isinstance(ctx, dict):
        credential = ctx.get("credential")

    if credential is None:
        credential = await get_drive_credential(user_id)

    if credential is None:
        raise ValueError("No Google Drive account linked for this user")

    return credential


@function_tool
async def drive_list_files(limit: int = 20, query: Optional[str] = None) -> Dict[str, Any]:
    """
    List files in the connected Google Drive account.

    Args:
        limit: Maximum number of files to return (1-100).
        query: Optional Drive search query string.
    """
    try:
        credential = await _resolve_drive_credential()
        google_credentials = await build_authorized_credentials(credential)
        response = await drive_api.list_files(
            google_credentials,
            page_size=limit,
            query=query,
        )
        return {
            "status": "success",
            "files": response.get("files", []),
            "nextPageToken": response.get("nextPageToken"),
        }
    except HttpError as exc:
        return {"status": "error", "message": f"Drive API error: {exc}"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@function_tool
async def drive_get_file_preview(
    file_id: str,
    export_mime_type: Optional[str] = None,
    mode: str = "auto",
) -> Dict[str, Any]:
    """
    Download a Google Drive file (or export Google Docs) and return a sanitized preview.

    Args:
        file_id: The Drive file identifier.
        export_mime_type: Optional export format for Google Docs/Sheets/Slides.
        mode: "auto", "text", or "table" to guide extraction strategy.
    """
    try:
        credential = await _resolve_drive_credential()
        google_credentials = await build_authorized_credentials(credential)

        # Determine whether to export or download
        metadata = await drive_api.get_metadata(google_credentials, file_id)
        mime_type = metadata.get("mimeType", "")

        export_type = export_mime_type
        if mime_type.startswith("application/vnd.google-apps."):
            if not export_type:
                export_type = "text/plain" if "document" in mime_type else "text/csv"
            content_bytes, exported_meta = await drive_api.export_document(
                google_credentials,
                file_id,
                export_type,
            )
            content_mime = export_type
            metadata.update(exported_meta)
        else:
            content_bytes, downloaded_meta = await drive_api.download_file(
                google_credentials,
                file_id,
            )
            content_mime = downloaded_meta.get("mimeType", mime_type)
            metadata.update(downloaded_meta)

        filename = metadata.get("name") or f"drive-file-{file_id}"
        preview = extract_file_preview_from_bytes(
            content=content_bytes,
            filename=filename,
            content_type=content_mime or mime_type,
            mode=mode,
        )

        size_value = metadata.get("size")
        try:
            size_int = int(size_value) if size_value is not None else None
        except (ValueError, TypeError):
            size_int = None

        return {
            "status": "success",
            "file": {
                "id": metadata.get("id", file_id),
                "name": filename,
                "content_type": content_mime or mime_type,
                "size": size_int,
                "source": "google_drive",
                "last_modified": metadata.get("modifiedTime"),
            },
            "extract": preview,
        }
    except HttpError as exc:
        return {"status": "error", "message": f"Drive API error: {exc}"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


__all__ = ["drive_list_files", "drive_get_file_preview"]
