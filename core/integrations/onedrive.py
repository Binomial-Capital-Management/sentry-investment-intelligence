"""
Microsoft OneDrive (Graph API) helpers.
All network operations run asynchronously with httpx.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


async def _graph_request(
    method: str,
    url: str,
    access_token: str,
    *,
    params: Optional[Dict[str, Any]] = None,
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:  # 4x for Graph API operations
        response = await client.request(method, url, headers=headers, params=params)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("OneDrive Graph request failed (%s %s): %s", method, url, exc.response.text)
        raise
    return response


async def list_files(
    access_token: str,
    query: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 50,
) -> Dict[str, Any]:
    """List files for the authenticated OneDrive user."""
    params: Optional[Dict[str, Any]] = None
    if page_token:
        url = page_token
    elif query:
        encoded = quote(query, safe="")
        url = f"{GRAPH_BASE_URL}/me/drive/root/search(q='{encoded}')"
        params = {"$top": min(max(page_size, 1), 200)}
    else:
        url = f"{GRAPH_BASE_URL}/me/drive/root/children"
        params = {"$top": min(max(page_size, 1), 200)}

    response = await _graph_request("GET", url, access_token, params=params)
    data = response.json()
    return {
        "files": data.get("value", []),
        "next_link": data.get("@odata.nextLink"),
    }


async def get_metadata(access_token: str, item_id: str) -> Dict[str, Any]:
    """Fetch metadata for a specific OneDrive item."""
    url = f"{GRAPH_BASE_URL}/me/drive/items/{item_id}"
    response = await _graph_request("GET", url, access_token)
    return response.json()


async def download_file(access_token: str, item_id: str) -> Tuple[bytes, Dict[str, Any]]:
    """Download the raw bytes for a OneDrive file along with its metadata."""
    metadata = await get_metadata(access_token, item_id)
    url = f"{GRAPH_BASE_URL}/me/drive/items/{item_id}/content"
    response = await _graph_request("GET", url, access_token)
    content = response.content
    return content, metadata


async def get_drive_info(access_token: str) -> Dict[str, Any]:
    """Fetch metadata about the current user's drive and SharePoint site."""
    url = (
        f"{GRAPH_BASE_URL}/me/drive"
        "?$select=id,driveType,webUrl,sharepointIds"
    )
    response = await _graph_request("GET", url, access_token)
    return response.json()
