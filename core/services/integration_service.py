"""
Integration services for external providers (Google Drive, etc.).
Handles secure storage, encryption, and token lifecycle management.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client
from core.utils.crypto import encrypt_string, decrypt_string

logger = logging.getLogger(__name__)

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_token_cache: Dict[str, Dict[str, Any]] = {}
_token_cache_lock = asyncio.Lock()
_ONEDRIVE_TOKEN_URI_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_onedrive_token_cache: Dict[str, Dict[str, Any]] = {}
_onedrive_token_cache_lock = asyncio.Lock()
_onedrive_picker_token_cache: Dict[str, Dict[str, Any]] = {}
_onedrive_picker_token_cache_lock = asyncio.Lock()


@dataclass
class DriveCredential:
    """Domain object representing a stored Google Drive credential."""

    id: str
    user_id: str
    drive_user_id: str
    drive_email: Optional[str]
    refresh_token_encrypted: str
    scopes: List[str]
    token_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def decrypt_refresh_token(self, encryption_key: str) -> str:
        token = decrypt_string(self.refresh_token_encrypted, encryption_key)
        if not token:
            raise ValueError("Failed to decrypt Google Drive refresh token")
        return token


@dataclass
class OneDriveCredential:
    """Domain object representing a stored OneDrive credential."""

    id: str
    user_id: str
    drive_user_id: str
    drive_email: Optional[str]
    refresh_token_encrypted: str
    scopes: List[str]
    token_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def decrypt_refresh_token(self, encryption_key: str) -> str:
        token = decrypt_string(self.refresh_token_encrypted, encryption_key)
        if not token:
            raise ValueError("Failed to decrypt OneDrive refresh token")
        return token


def _deserialize_drive_row(row: Dict[str, Any]) -> DriveCredential:
    metadata = row.get("token_metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}

    scopes = row.get("scopes") or []
    if isinstance(scopes, str):
        scopes = [scope.strip() for scope in scopes.split(",") if scope.strip()]

    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return DriveCredential(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        drive_user_id=str(row["drive_user_id"]),
        drive_email=row.get("drive_email"),
        refresh_token_encrypted=str(row["refresh_token_encrypted"]),
        scopes=list(scopes),
        token_metadata=metadata if isinstance(metadata, dict) else {},
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def _deserialize_onedrive_row(row: Dict[str, Any]) -> OneDriveCredential:
    metadata = row.get("token_metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}

    scopes = row.get("scopes") or []
    if isinstance(scopes, str):
        scopes = [scope.strip() for scope in scopes.split(",") if scope.strip()]

    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return OneDriveCredential(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        drive_user_id=str(row["drive_user_id"]),
        drive_email=row.get("drive_email"),
        refresh_token_encrypted=str(row["refresh_token_encrypted"]),
        scopes=list(scopes),
        token_metadata=metadata if isinstance(metadata, dict) else {},
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=updated_at or datetime.now(timezone.utc),
    )


async def store_drive_credential(
    user_id: str,
    drive_user_id: str,
    drive_email: str,
    refresh_token: str,
    scopes: List[str],
    token_metadata: Optional[Dict[str, Any]] = None,
    org_id: str = '',
) -> Optional[DriveCredential]:
    """Persist (or update) a Google Drive credential. org_id='' for personal, org_id='org_xxx' for org token."""
    config = get_config()
    encrypted_token = encrypt_string(refresh_token, config.google_drive_encryption_key)

    pg = await get_postgres_rls_client()
    row = await pg.upsert_drive_credential(
        user_id=user_id,
        drive_user_id=drive_user_id,
        drive_email=drive_email,
        refresh_token_encrypted=encrypted_token,
        scopes=scopes,
        token_metadata=token_metadata or {},
        org_id=org_id,
    )

    if not row:
        return None

    # Clear cache entry to avoid stale tokens
    async with _token_cache_lock:
        _token_cache.pop(str(row["id"]), None)

    # Normalize timestamps to timezone-aware datetimes
    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    normalized = dict(row)
    normalized["created_at"] = created_at
    normalized["updated_at"] = updated_at

    return _deserialize_drive_row(normalized)


async def list_drive_credentials(user_id: str, org_id: str = '') -> List[DriveCredential]:
    """Return Drive credentials. For personal (org_id='') or org tokens."""
    pg = await get_postgres_rls_client()
    rows = await pg.get_drive_credentials(user_id=user_id, org_id=org_id)
    normalized_rows = []
    for row in rows:
        created_at = row.get("created_at")
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        normalized = dict(row)
        normalized["created_at"] = created_at
        normalized["updated_at"] = updated_at
        normalized_rows.append(normalized)

    return [_deserialize_drive_row(row) for row in normalized_rows]


async def get_drive_credential(user_id: str, credential_id: Optional[str] = None, org_id: str = '') -> Optional[DriveCredential]:
    """Fetch a Drive credential. For personal (org_id='') or org tokens."""
    credentials = await list_drive_credentials(user_id, org_id=org_id)
    if not credentials:
        return None

    if credential_id:
        for cred in credentials:
            if cred.id == credential_id:
                return cred
        return None

    return credentials[0]


async def delete_drive_credential(user_id: str, credential_id: str) -> bool:
    """Remove a Drive credential owned by the user."""
    pg = await get_postgres_rls_client()
    deleted = await pg.delete_drive_credential(user_id=user_id, credential_id=credential_id)
    if deleted:
        async with _token_cache_lock:
            _token_cache.pop(credential_id, None)
    return deleted


async def store_onedrive_credential(
    user_id: str,
    drive_user_id: str,
    drive_email: str,
    refresh_token: str,
    scopes: List[str],
    token_metadata: Optional[Dict[str, Any]] = None,
    org_id: str = '',
) -> Optional[OneDriveCredential]:
    """Persist (or update) a OneDrive credential. org_id='' for personal, org_id='org_xxx' for org token."""
    config = get_config()
    encrypted_token = encrypt_string(refresh_token, config.onedrive_encryption_key)

    pg = await get_postgres_rls_client()
    row = await pg.upsert_onedrive_credential(
        user_id=user_id,
        drive_user_id=drive_user_id,
        drive_email=drive_email,
        refresh_token_encrypted=encrypted_token,
        scopes=scopes,
        token_metadata=token_metadata or {},
        org_id=org_id,
    )

    if not row:
        return None

    async with _onedrive_token_cache_lock:
        _onedrive_token_cache.pop(str(row["id"]), None)

    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    normalized = dict(row)
    normalized["created_at"] = created_at
    normalized["updated_at"] = updated_at
    return _deserialize_onedrive_row(normalized)


async def list_onedrive_credentials(user_id: str, org_id: str = '') -> List[OneDriveCredential]:
    """Return OneDrive credentials. For personal (org_id='') or org tokens."""
    pg = await get_postgres_rls_client()
    rows = await pg.get_onedrive_credentials(user_id=user_id, org_id=org_id)
    normalized_rows = []
    for row in rows:
        created_at = row.get("created_at")
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        normalized = dict(row)
        normalized["created_at"] = created_at
        normalized["updated_at"] = updated_at
        normalized_rows.append(normalized)

    return [_deserialize_onedrive_row(row) for row in normalized_rows]


async def get_onedrive_credential(user_id: str, credential_id: Optional[str] = None, org_id: str = '') -> Optional[OneDriveCredential]:
    """Fetch a OneDrive credential. For personal (org_id='') or org tokens."""
    credentials = await list_onedrive_credentials(user_id, org_id=org_id)
    if not credentials:
        return None

    if credential_id:
        for cred in credentials:
            if cred.id == credential_id:
                return cred
        return None

    return credentials[0]


async def delete_onedrive_credential(user_id: str, credential_id: str) -> bool:
    """Remove a OneDrive credential owned by the user."""
    pg = await get_postgres_rls_client()
    deleted = await pg.delete_onedrive_credential(user_id=user_id, credential_id=credential_id)
    if deleted:
        async with _onedrive_token_cache_lock:
            _onedrive_token_cache.pop(credential_id, None)
    return deleted


async def build_authorized_credentials(credential: DriveCredential) -> Credentials:
    """
    Build a google.oauth2.credentials.Credentials instance with a fresh access token.
    Uses an in-memory cache to avoid redundant refreshes for the same credential.
    """
    config = get_config()
    refresh_token = credential.decrypt_refresh_token(config.google_drive_encryption_key)

    async with _token_cache_lock:
        cached = _token_cache.get(credential.id)

    now = datetime.now(timezone.utc)
    if cached:
        expires_at: datetime = cached.get("expires_at", now)
        if expires_at - now > timedelta(seconds=45):
            creds = Credentials(
                token=cached["token"],
                refresh_token=refresh_token,
                token_uri=_TOKEN_URI,
                client_id=config.google_drive_client_id,
                client_secret=config.google_drive_client_secret,
                scopes=credential.scopes,
            )
            creds.expiry = expires_at
            return creds

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=_TOKEN_URI,
        client_id=config.google_drive_client_id,
        client_secret=config.google_drive_client_secret,
        scopes=credential.scopes,
    )

    request = Request()
    creds.refresh(request)
    expiry = creds.expiry or (now + timedelta(hours=1))
    # Ensure expiry is timezone-aware (google-auth returns naive datetimes)
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    async with _token_cache_lock:
        _token_cache[credential.id] = {"token": creds.token, "expires_at": expiry}

    return creds


async def _ensure_onedrive_access_token(credential: OneDriveCredential) -> Tuple[str, datetime]:
    """Shared helper returning a OneDrive access token and its expiry."""
    config = get_config()
    refresh_token = credential.decrypt_refresh_token(config.onedrive_encryption_key)

    async with _onedrive_token_cache_lock:
        cached = _onedrive_token_cache.get(credential.id)

    now = datetime.now(timezone.utc)
    if cached:
        expires_at: datetime = cached.get("expires_at", now)
        if expires_at - now > timedelta(seconds=45):
            return cached["token"], expires_at

    token_url = _ONEDRIVE_TOKEN_URI_TEMPLATE.format(tenant=config.onedrive_tenant_id or "common")
    data = {
        "client_id": config.onedrive_client_id,
        "client_secret": config.onedrive_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(credential.scopes or config.onedrive_scopes),
    }

    async with httpx.AsyncClient(timeout=120.0) as client:  # 2 minutes for enterprise token requests
        response = await client.post(token_url, data=data)
    if response.status_code != 200:
        logger.error("OneDrive token refresh failed: %s", response.text)
        response.raise_for_status()

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("OneDrive token response missing access_token")
    expires_in = int(token_data.get("expires_in", 3600))

    new_refresh = token_data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        # Persist rotated refresh token
        await store_onedrive_credential(
            user_id=credential.user_id,
            drive_user_id=credential.drive_user_id,
            drive_email=credential.drive_email or "",
            refresh_token=new_refresh,
            scopes=credential.scopes,
            token_metadata=credential.token_metadata,
        )

    expiry = now + timedelta(seconds=expires_in)
    async with _onedrive_token_cache_lock:
        _onedrive_token_cache[credential.id] = {"token": access_token, "expires_at": expiry}

    return access_token, expiry


async def build_onedrive_access_token(credential: OneDriveCredential) -> str:
    """Return a valid OneDrive access token, refreshing when necessary."""
    token, _ = await _ensure_onedrive_access_token(credential)
    return token


async def build_onedrive_access_token_with_expiry(credential: OneDriveCredential) -> Tuple[str, datetime]:
    """Return OneDrive access token plus expiry timestamp for clients that need metadata."""
    return await _ensure_onedrive_access_token(credential)


async def build_onedrive_picker_token(credential: OneDriveCredential, scope: str) -> Tuple[str, datetime]:
    """Return a SharePoint-scoped token for the native picker (resource-specific)."""
    scope = (scope or "").strip()
    if not scope:
        raise ValueError("Scope required for OneDrive picker token")

    config = get_config()
    refresh_token = credential.decrypt_refresh_token(config.onedrive_encryption_key)

    cache_key = f"{credential.id}:{scope}"
    async with _onedrive_picker_token_cache_lock:
        cached = _onedrive_picker_token_cache.get(cache_key)

    now = datetime.now(timezone.utc)
    if cached:
        expires_at: datetime = cached.get("expires_at", now)
        if expires_at - now > timedelta(seconds=45):
            return cached["token"], expires_at

    token_url = _ONEDRIVE_TOKEN_URI_TEMPLATE.format(tenant=config.onedrive_tenant_id or "common")
    data = {
        "client_id": config.onedrive_client_id,
        "client_secret": config.onedrive_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": scope,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:  # 2 minutes for enterprise SharePoint token requests
        response = await client.post(token_url, data=data)
    if response.status_code != 200:
        logger.error("OneDrive picker token refresh failed: %s", response.text)
        response.raise_for_status()

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("OneDrive picker token response missing access_token")
    expires_in = int(token_data.get("expires_in", 3600))

    new_refresh = token_data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        await store_onedrive_credential(
            user_id=credential.user_id,
            drive_user_id=credential.drive_user_id,
            drive_email=credential.drive_email or "",
            refresh_token=new_refresh,
            scopes=credential.scopes,
            token_metadata=credential.token_metadata,
        )

    expiry = now + timedelta(seconds=expires_in)
    async with _onedrive_picker_token_cache_lock:
        _onedrive_picker_token_cache[cache_key] = {"token": access_token, "expires_at": expiry}

    return access_token, expiry


def encode_oauth_state(payload: Dict[str, Any]) -> str:
    """Encrypt OAuth state payload for round-trip validation."""
    config = get_config()
    state_payload = dict(payload)
    state_payload.setdefault("ts", time.time())
    raw = json.dumps(state_payload)
    return encrypt_string(raw, config.google_drive_encryption_key)


def decode_oauth_state(state: str, ttl_seconds: int = 600) -> Optional[Dict[str, Any]]:
    """Decode and validate OAuth state payload. Returns None when invalid or expired."""
    config = get_config()
    raw = decrypt_string(state, config.google_drive_encryption_key)
    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode Google Drive OAuth state payload")
        return None

    ts = data.get("ts")
    if isinstance(ts, (int, float)) and ttl_seconds > 0:
        if time.time() - ts > ttl_seconds:
            logger.warning("Google Drive OAuth state expired")
            return None

    return data
