"""
Google Drive integration endpoints.
Provides OAuth handshake, credential management, and Drive file discovery.
"""

from __future__ import annotations

import io
import mimetypes
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import AuthorizedSession
from pydantic import BaseModel

from core.config import get_config
from core.services.integration_service import (
    build_authorized_credentials,
    decode_oauth_state,
    delete_drive_credential,
    encode_oauth_state,
    get_drive_credential,
    list_drive_credentials,
    store_drive_credential,
)
from core.integrations.google_drive import list_files, download_file, export_document, get_metadata
from api.routers.uploads import store_file_bytes

router = APIRouter(prefix="/api/integrations/google-drive", tags=["integrations"])


def _get_org_id(request: Request) -> str:
    """Get org_id from request. Empty string for personal workspace."""
    return getattr(request.state, 'org_id', None) or ''


GOOGLE_EXPORT_MIME_MAP: Dict[str, Dict[str, str]] = {
    "application/vnd.google-apps.document": {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extension": ".docx",
    },
    "application/vnd.google-apps.spreadsheet": {
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "extension": ".xlsx",
    },
    "application/vnd.google-apps.presentation": {
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "extension": ".pptx",
    },
    "application/vnd.google-apps.drawing": {
        "mime": "image/png",
        "extension": ".png",
    },
    "application/vnd.google-apps.script": {
        "mime": "application/zip",
        "extension": ".zip",
    },
}


class DriveImportRequest(BaseModel):
    file_id: str
    export_mime_type: Optional[str] = None


def _resolve_export_target(drive_mime: str, override: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Return target MIME type and extension for Google-native files.
    """
    if override:
        extension = mimetypes.guess_extension(override) or ""
        return {"mime": override, "extension": extension}

    preferred = GOOGLE_EXPORT_MIME_MAP.get(drive_mime)
    if preferred:
        return preferred

    if drive_mime.startswith("application/vnd.google-apps."):
        return {"mime": "application/pdf", "extension": ".pdf"}

    return {"mime": None, "extension": None}


def _require_drive_enabled():
    config = get_config()
    if not config.google_drive_enabled:
        raise HTTPException(status_code=400, detail="Google Drive integration is disabled")
    return config


def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


@router.get("/status")
async def drive_status(request: Request):
    """Get Google Drive status for current workspace (personal or org)."""
    config = get_config()
    if not config.google_drive_enabled:
        return {"enabled": False, "connected": False}

    user_id = _require_user(request)
    org_id = _get_org_id(request)
    
    credentials = await list_drive_credentials(user_id, org_id=org_id)
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


@router.post("/authorize")
async def start_authorization(request: Request):
    """Start OAuth flow. Stores token for current workspace (personal or org)."""
    config = _require_drive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": config.google_drive_client_id,
                "client_secret": config.google_drive_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [config.google_drive_redirect_uri],
            }
        },
        scopes=config.google_drive_scopes,
    )
    flow.redirect_uri = config.google_drive_redirect_uri

    # Include org_id in state so callback knows where to store the token
    state_payload = encode_oauth_state({"user_id": user_id, "org_id": org_id, "nonce": uuid.uuid4().hex})
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state_payload,
    )

    return {"authorization_url": authorization_url, "state": state_payload}


@router.get("/callback")
async def oauth_callback(request: Request, state: str, code: Optional[str] = None, error: Optional[str] = None):
    config = _require_drive_enabled()

    state_data = decode_oauth_state(state)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    if error:
        raise HTTPException(status_code=400, detail=f"Google Drive authorization failed: {error}")

    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id") or ''
    if not user_id:
        raise HTTPException(status_code=400, detail="OAuth state missing user context")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": config.google_drive_client_id,
                "client_secret": config.google_drive_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [config.google_drive_redirect_uri],
            }
        },
        scopes=config.google_drive_scopes,
    )
    flow.redirect_uri = config.google_drive_redirect_uri

    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # pragma: no cover - network failure path
        raise HTTPException(status_code=400, detail=f"Failed to exchange authorization code: {exc}") from exc

    credentials = flow.credentials
    refresh_token = credentials.refresh_token

    # Reuse existing refresh token if Google did not return one (happens on re-consent)
    existing = await get_drive_credential(user_id, org_id=org_id)
    if not refresh_token and existing:
        refresh_token = existing.decrypt_refresh_token(config.google_drive_encryption_key)
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token from Google OAuth. Reauthorize with consent.")

    session = AuthorizedSession(credentials)
    profile_resp = session.get("https://www.googleapis.com/oauth2/v2/userinfo")
    if profile_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to retrieve Google account profile")
    profile = profile_resp.json()

    drive_user_id = profile.get("id") or profile.get("sub")
    drive_email = profile.get("email")
    if not drive_user_id or not drive_email:
        raise HTTPException(status_code=400, detail="Google profile response missing account identifiers")

    token_metadata: Dict[str, Any] = {
        "picture": profile.get("picture"),
        "verified_email": profile.get("verified_email"),
    }

    stored = await store_drive_credential(
        user_id=user_id,
        drive_user_id=drive_user_id,
        drive_email=drive_email,
        refresh_token=refresh_token,
        scopes=list(credentials.scopes or config.google_drive_scopes),
        token_metadata=token_metadata,
        org_id=org_id,
    )

    if "text/html" in request.headers.get("accept", ""):
        body = "<script>window.close();</script>Connected Google Drive account. You can close this window."
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
async def disconnect_drive(request: Request):
    """Disconnect Google Drive for current workspace."""
    _require_drive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_drive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No Google Drive account linked")

    await delete_drive_credential(user_id, credential.id)
    return {"status": "disconnected", "workspace": "org" if org_id else "personal"}


@router.post("/import")
async def import_drive_file(payload: DriveImportRequest, request: Request):
    """Import a Google Drive file into the standard upload store so chat/workflows can attach it."""
    _require_drive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_drive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No Google Drive account linked")

    google_credentials = await build_authorized_credentials(credential)

    try:
        metadata = await get_metadata(google_credentials, payload.file_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Google Drive metadata: {exc}") from exc

    drive_mime = metadata.get("mimeType") or ""
    filename = metadata.get("name") or "Google Drive File"

    if drive_mime.startswith("application/vnd.google-apps."):
        export_target = _resolve_export_target(drive_mime, payload.export_mime_type)
        export_mime = export_target.get("mime")
        extension = export_target.get("extension") or ""
        if not export_mime:
            raise HTTPException(status_code=400, detail=f"Unsupported Google Drive file type: {drive_mime}")
        try:
            content_bytes, exported_meta = await export_document(
                google_credentials,
                payload.file_id,
                export_mime,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to export Google Drive file: {exc}") from exc
        if exported_meta:
            metadata.update(exported_meta)
        content_type = export_mime
        if extension and not filename.lower().endswith(extension):
            filename = f"{filename}{extension}"
    else:
        try:
            content_bytes, downloaded_meta = await download_file(google_credentials, payload.file_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download Google Drive file: {exc}") from exc
        if downloaded_meta:
            metadata.update(downloaded_meta)
        content_type = metadata.get("mimeType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if "." not in filename:
            detected_ext = metadata.get("fileExtension")
            if detected_ext:
                filename = f"{filename}.{detected_ext}"

    stored = await store_file_bytes(
        user_id,
        filename,
        content_bytes,
        content_type=content_type,
        metadata={
            "source": "google_drive",
            "drive_file_id": payload.file_id,
            "drive_mime_type": drive_mime,
        },
    )

    stored.pop("stored_key", None)
    stored["source"] = "google_drive"
    stored["drive_file_id"] = payload.file_id
    stored["drive_mime_type"] = drive_mime

    return {
        "status": "success",
        "file": stored,
    }


@router.get("/files")
async def list_drive_files(
    request: Request,
    query: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[str] = None,
):
    _require_drive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_drive_credential(user_id, org_id=org_id)
    if not credential:
        return {"files": [], "next_page_token": None}

    google_credentials = await build_authorized_credentials(credential)
    response = await list_files(
        google_credentials,
        query=query,
        page_size=page_size,
        page_token=page_token,
    )

    files = response.get("files", [])
    next_token = response.get("nextPageToken")
    return {"files": files, "next_page_token": next_token}


@router.get("/files/{file_id}/download")
async def download_drive_file_endpoint(
    file_id: str,
    request: Request,
    export_mime_type: Optional[str] = None,
):
    _require_drive_enabled()
    user_id = _require_user(request)
    org_id = _get_org_id(request)

    credential = await get_drive_credential(user_id, org_id=org_id)
    if not credential:
        raise HTTPException(status_code=404, detail="No Google Drive account linked")

    google_credentials = await build_authorized_credentials(credential)

    try:
        metadata = await get_metadata(google_credentials, file_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Google Drive metadata: {exc}") from exc

    drive_mime = metadata.get("mimeType") or ""
    filename = metadata.get("name") or "GoogleDriveFile"

    if drive_mime.startswith("application/vnd.google-apps."):
        export_target = _resolve_export_target(drive_mime, export_mime_type)
        export_mime = export_target.get("mime")
        extension = export_target.get("extension") or ""
        if not export_mime:
            raise HTTPException(status_code=400, detail=f"Unsupported Google Drive file type: {drive_mime}")
        try:
            content_bytes, exported_meta = await export_document(google_credentials, file_id, export_mime)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to export Google Drive file: {exc}") from exc
        if exported_meta:
            metadata.update(exported_meta)
        content_type = export_mime
        if extension and not filename.lower().endswith(extension):
            filename = f"{filename}{extension}"
    else:
        try:
            content_bytes, downloaded_meta = await download_file(google_credentials, file_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download Google Drive file: {exc}") from exc
        if downloaded_meta:
            metadata.update(downloaded_meta)
        content_type = metadata.get("mimeType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if "." not in filename:
            detected_ext = metadata.get("fileExtension")
            if detected_ext:
                filename = f"{filename}.{detected_ext}"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Filename": filename,
        "X-Drive-Mime-Type": drive_mime or "",
    }

    return StreamingResponse(io.BytesIO(content_bytes), media_type=content_type, headers=headers)
