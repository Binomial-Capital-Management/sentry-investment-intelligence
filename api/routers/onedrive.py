"""
OneDrive integration endpoints (Microsoft Graph).
Parallels Google Drive router but uses server-side Graph API calls.
"""

from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse
import base64
import hashlib
import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from core.config import get_config
from core.integrations import onedrive as onedrive_api
from core.services.integration_service import (
    build_onedrive_access_token,
    build_onedrive_picker_token,
    decode_oauth_state,
    delete_onedrive_credential,
    encode_oauth_state,
    get_onedrive_credential,
    list_onedrive_credentials,
    store_onedrive_credential,
)
from api.routers.uploads import store_file_bytes

router = APIRouter(prefix="/api/integrations/onedrive", tags=["integrations"])
logger = logging.getLogger(__name__)


def _get_org_id(request: Request) -> str:
    """Get org_id from request. Empty string for personal workspace."""
    return getattr(request.state, 'org_id', None) or ''


class OneDriveImportRequest(BaseModel):
    file_id: str


def _require_onedrive_enabled():
    config = get_config()
    if not config.onedrive_enabled:
        raise HTTPException(status_code=400, detail="OneDrive integration is disabled")
    return config


def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def _format_drive_item(item: Dict[str, Any]) -> Dict[str, Any]:
    file_info = item.get("file") or {}
    folder_info = item.get("folder") or {}
    mime_type = file_info.get("mimeType")
    if not mime_type and folder_info:
        mime_type = "application/vnd.microsoft-apps.folder"

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "mimeType": mime_type,
        "modifiedTime": item.get("lastModifiedDateTime"),
        "size": item.get("size"),
        "driveId": item.get("parentReference", {}).get("driveId"),
        "webUrl": item.get("webUrl"),
        "isFolder": bool(folder_info),
    }


@router.get("/status")
async def onedrive_status(request: Request):
    """Get OneDrive status for current workspace (personal or org)."""
    config = get_config()
    if not config.onedrive_enabled:
        return {"enabled": False, "connected": False}

    user_id = _require_user(request)
    org_id = _get_org_id(request)
    
    credentials = await list_onedrive_credentials(user_id, org_id=org_id)
    if not credentials:
        return {"enabled": True, "connected": False, "workspace": "org" if org_id else "personal"}

    cred = credentials[0]
    return {
        "enabled": True,
        "connected": True,
        "workspace": "org" if org_id else "personal",
        "credential": {
            "id": cred.id,
            "drive_user_id": cred.drive_user_id,
            "drive_email": cred.drive_email,
            "scopes": cred.scopes,
            "updated_at": cred.updated_at,
        },
    }


@router.get("/picker/token")
async def get_picker_access_token(request: Request, account_type: str = "personal"):
    """Expose a short-lived access token so the frontend can launch Microsoft's native picker.

    Args:
        account_type: 'personal' for Microsoft account, 'business' for work/school OneDrive, 'sharepoint' for SharePoint sites
    """
    config = _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_onedrive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No OneDrive account linked")

    graph_token = await build_onedrive_access_token(credential)
    sharepoint_origin = None
    drive_id = None
    drive_type = None
    drive_web_url: Optional[str] = None
    sharepoint_ids: Dict[str, Optional[str]] = {}
    sharepoint_scope: Optional[str] = None
    try:
        drive_info = await onedrive_api.get_drive_info(graph_token)
        drive_id = drive_info.get("id")
        drive_type = drive_info.get("driveType")
        drive_web_url = drive_info.get("webUrl")
        raw_sharepoint_ids = {}
        if isinstance(drive_info, dict):
            raw_sharepoint_ids = drive_info.get("sharePointIds") or drive_info.get("sharepointIds") or {}
        if isinstance(raw_sharepoint_ids, dict):
            sharepoint_ids = raw_sharepoint_ids
        site_url = sharepoint_ids.get("siteUrl") or drive_web_url or ""
        if site_url:
            parsed = urlparse(site_url)
            if parsed.scheme and parsed.netloc:
                sharepoint_origin = f"{parsed.scheme}://{parsed.netloc}"
                sharepoint_scope = f"{sharepoint_origin}/.default"
    except Exception as exc:
        logger.warning("Failed to derive SharePoint metadata for picker: %s", exc)

    # Use user-selected account type to determine picker configuration.
    # Consumer picker accepts Graph tokens, SharePoint picker requires a SharePoint-scoped token.
    picker_scope = "offline_access https://graph.microsoft.com/.default"
    picker_origin = "https://onedrive.live.com"
    picker_url = f"{picker_origin}/picker"

    if account_type in ("business", "sharepoint"):
        if sharepoint_origin and sharepoint_scope:
            picker_scope = f"offline_access {sharepoint_scope}"
            picker_origin = sharepoint_origin
            picker_url = f"{sharepoint_origin}/_layouts/15/FilePicker.aspx"
            logger.info(f"Using SharePoint picker for {account_type} account: {picker_origin}")
        else:
            # SharePoint metadata missing; fall back to consumer picker but log so we can fix tenant config.
            logger.warning(
                f"OneDrive {account_type} picker requested but SharePoint metadata missing; falling back to consumer picker"
            )
    elif account_type != "personal":
        logger.warning("Unknown OneDrive account_type '%s'; defaulting to personal picker", account_type)

    picker_token, expires_at = await build_onedrive_picker_token(credential, picker_scope)
    now = datetime.now(timezone.utc)
    expires_in = max(0, int((expires_at - now).total_seconds())) if expires_at else 0

    return {
        "access_token": picker_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "tenant_id": config.onedrive_tenant_id or "common",
        "picker_origin": picker_origin,
        "picker_url": picker_url,
        "scope": picker_scope,
        "drive": {
            "id": drive_id,
            "type": drive_type,
            "web_url": drive_web_url,
            "sharepoint_site_id": sharepoint_ids.get("siteId"),
            "sharepoint_list_id": sharepoint_ids.get("listId"),
            "sharepoint_web_id": sharepoint_ids.get("webId"),
            "sharepoint_site_url": sharepoint_ids.get("siteUrl"),
        },
    }


@router.post("/authorize")
async def start_authorization(request: Request):
    """Start OAuth flow. Stores token for current workspace (personal or org)."""
    config = _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()

    # Include org_id in state so callback knows where to store the token
    state_payload = encode_oauth_state({"user_id": user_id, "org_id": org_id, "code_verifier": code_verifier})
    params = {
        "client_id": config.onedrive_client_id,
        "response_type": "code",
        "redirect_uri": config.onedrive_redirect_uri,
        "response_mode": "query",
        "scope": " ".join(config.onedrive_scopes),
        "state": state_payload,
        "prompt": "select_account",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = (
        f"https://login.microsoftonline.com/{config.onedrive_tenant_id or 'common'}/oauth2/v2.0/authorize?"
        f"{urlencode(params)}"
    )

    return {"authorization_url": authorize_url, "state": state_payload}


@router.get("/callback")
async def oauth_callback(request: Request, state: str, code: Optional[str] = None, error: Optional[str] = None):
    config = _require_onedrive_enabled()

    state_data = decode_oauth_state(state)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    if error:
        raise HTTPException(status_code=400, detail=f"OneDrive authorization failed: {error}")

    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id") or ''
    code_verifier = state_data.get("code_verifier")
    if not user_id:
        raise HTTPException(status_code=400, detail="OAuth state missing user context")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="OAuth state missing PKCE verifier")

    token_url = f"https://login.microsoftonline.com/{config.onedrive_tenant_id or 'common'}/oauth2/v2.0/token"
    data = {
        "client_id": config.onedrive_client_id,
        "client_secret": config.onedrive_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.onedrive_redirect_uri,
        "scope": " ".join(config.onedrive_scopes),
        "code_verifier": code_verifier,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(token_url, data=data)
        token_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {exc.response.text}") from exc

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(status_code=400, detail="OneDrive token response missing credentials")

    # Fetch user info
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            profile_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        profile_resp.raise_for_status()
        profile = profile_resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch OneDrive profile: {exc.response.text}") from exc

    drive_user_id = profile.get("id")
    drive_email = profile.get("userPrincipalName") or profile.get("mail")
    if not drive_user_id:
        raise HTTPException(status_code=400, detail="OneDrive profile missing user identifier")

    stored = await store_onedrive_credential(
        user_id=user_id,
        drive_user_id=drive_user_id,
        drive_email=drive_email or "",
        refresh_token=refresh_token,
        scopes=list(config.onedrive_scopes),
        token_metadata={"displayName": profile.get("displayName")},
        org_id=org_id,
    )

    if "text/html" in request.headers.get("accept", ""):
        body = "<script>window.close();</script>Connected OneDrive account. You can close this window."
        return HTMLResponse(content=body)

    return JSONResponse(
        content={
            "status": "connected",
            "credential": {
                "id": stored.id if stored else None,
                "drive_user_id": drive_user_id,
                "drive_email": drive_email,
            },
        }
    )


@router.post("/disconnect")
async def disconnect_onedrive(request: Request):
    """Disconnect OneDrive for current workspace."""
    _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_onedrive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No OneDrive account linked")

    await delete_onedrive_credential(user_id, credential.id)
    return {"status": "disconnected", "workspace": "org" if org_id else "personal"}


@router.get("/files")
async def list_drive_files(
    request: Request,
    query: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[str] = None,
):
    _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_onedrive_credential(user_id, org_id=org_id)
    if not credential:
        return {"files": [], "next_page_token": None}

    access_token = await build_onedrive_access_token(credential)
    result = await onedrive_api.list_files(access_token, query=query, page_token=page_token, page_size=page_size)
    files = [_format_drive_item(item) for item in result.get("files", [])]
    return {"files": files, "next_page_token": result.get("next_link")}


@router.post("/import")
async def import_drive_file(payload: OneDriveImportRequest, request: Request):
    """Download a OneDrive file into the upload store so chat/workflows can attach it."""
    _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_onedrive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No OneDrive account linked")

    access_token = await build_onedrive_access_token(credential)

    try:
        content_bytes, metadata = await onedrive_api.download_file(access_token, payload.file_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to download OneDrive file: {exc.response.text}") from exc

    filename = metadata.get("name") or "OneDrive file"
    mime_type = (metadata.get("file") or {}).get("mimeType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    stored = await store_file_bytes(
        user_id,
        filename,
        content_bytes,
        content_type=mime_type,
        metadata={
            "source": "onedrive",
            "onedrive_item_id": payload.file_id,
            "onedrive_drive_id": metadata.get("parentReference", {}).get("driveId"),
        },
    )

    stored.pop("stored_key", None)
    stored["source"] = "onedrive"
    stored["onedrive_item_id"] = payload.file_id
    stored["onedrive_drive_id"] = metadata.get("parentReference", {}).get("driveId")

    return {"status": "success", "file": stored}


@router.get("/files/{file_id}/download")
async def download_file(file_id: str, request: Request):
    _require_onedrive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_onedrive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No OneDrive account linked")

    access_token = await build_onedrive_access_token(credential)

    try:
        content_bytes, metadata = await onedrive_api.download_file(access_token, file_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to download OneDrive file: {exc.response.text}") from exc

    filename = metadata.get("name") or "OneDrive file"
    mime_type = (metadata.get("file") or {}).get("mimeType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-OneDrive-Item-Id": file_id,
        "X-OneDrive-Mime-Type": mime_type,
    }

    return StreamingResponse(
        iter([content_bytes]),
        media_type=mime_type,
        headers=headers,
    )
