"""
Microsoft Teams integration helpers (OAuth, storage, channel listing).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client
from core.utils.crypto import encrypt_string, decrypt_string

logger = logging.getLogger(__name__)


class TeamsServiceError(RuntimeError):
    """Raised when Teams integration fails."""


@dataclass
class TeamsWorkspace:
    tenant_id: str
    tenant_name: Optional[str]
    connected_at: str
    connected_user_email: Optional[str] = None


@dataclass
class TeamsTeam:
    id: str
    display_name: Optional[str]


@dataclass
class TeamsChannel:
    id: str
    display_name: Optional[str]
    membership_type: Optional[str]


class TeamsService:
    def __init__(self):
        self.config = get_config()
        self._pg = None

    async def _pg_client(self):
        if not self._pg:
            self._pg = await get_postgres_rls_client()
        return self._pg

    def _require_enabled(self):
        if not self.config.teams_enabled:
            raise TeamsServiceError("Teams integration is disabled")

    def _build_state(self, user_id: str) -> str:
        payload = {
            "user_id": user_id,
            "ts": int(time.time()),
            "nonce": base64.urlsafe_b64encode(hashlib.sha256(user_id.encode()).digest()[:10]).decode(),
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            self.config.teams_client_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        state = f"{base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')}.{signature}"
        return state

    def _decode_state(self, state: str) -> str:
        try:
            encoded_payload, signature = state.split(".", 1)
            padding = "=" * (-len(encoded_payload) % 4)
            payload_bytes = base64.urlsafe_b64decode(encoded_payload + padding)
            expected_sig = hmac.new(
                self.config.teams_client_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, signature):
                raise TeamsServiceError("Invalid Teams state signature")
            payload = json.loads(payload_bytes.decode("utf-8"))
            ts = payload.get("ts", 0)
            if int(time.time()) - ts > self.config.teams_state_ttl_seconds:
                raise TeamsServiceError("Teams authorization link expired")
            return payload["user_id"]
        except TeamsServiceError:
            raise
        except Exception as exc:
            raise TeamsServiceError("Invalid Teams state payload") from exc

    def build_authorize_url(self, user_id: str) -> str:
        self._require_enabled()
        state = self._build_state(user_id)
        scopes = self.config.teams_scopes.replace(",", " ")
        tenant = self.config.teams_tenant_id or "common"
        return (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
            f"?client_id={self.config.teams_client_id}"
            f"&response_type=code"
            f"&redirect_uri={self.config.teams_redirect_uri}"
            f"&scope={scopes}"
            f"&state={state}"
            f"&prompt=select_account"  # Force account picker dialog
        )

    async def exchange_code(self, code: str, state: str) -> TeamsWorkspace:
        self._require_enabled()
        user_id = self._decode_state(state)
        token_data = await self._token_request(
            grant_type="authorization_code",
            code=code,
        )

        # DEBUG: Log what Microsoft returned
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[TEAMS OAuth] Token response keys: {list(token_data.keys())}")
        logger.info(f"[TEAMS OAuth] id_token present: {'id_token' in token_data}")

        # Decode id_token to get tenant_id (tid claim) and user email
        id_token = token_data.get("id_token", "")
        tenant_id = self.config.teams_tenant_id  # Default to "common"
        tenant_name = None
        user_email = None

        logger.info(f"[TEAMS OAuth] id_token present: {bool(id_token)}")
        if id_token:
            # Decode JWT without verification (we trust Microsoft's response)
            try:
                import base64
                # JWT format: header.payload.signature
                parts = id_token.split(".")
                if len(parts) >= 2:
                    # Decode payload (add padding if needed)
                    payload_b64 = parts[1]
                    padding = "=" * (-len(payload_b64) % 4)
                    payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
                    payload = json.loads(payload_json)
                    tenant_id = payload.get("tid", tenant_id)  # Get tid (tenant ID)
                    tenant_name = payload.get("tenant_name") or payload.get("name")  # Try to get tenant name
                    user_email = payload.get("preferred_username") or payload.get("email") or payload.get("upn")
                    logger.info(f"[TEAMS OAuth] Extracted tenant_id: {tenant_id}, user: {user_email}")
            except Exception as e:
                logger.error(f"[TEAMS OAuth] JWT decode failed: {e}")
                import traceback
                traceback.print_exc()

        encrypted_access = encrypt_string(token_data["access_token"], self.config.teams_encryption_key)
        encrypted_refresh = None
        if token_data.get("refresh_token"):
            encrypted_refresh = encrypt_string(token_data["refresh_token"], self.config.teams_encryption_key)

        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO teams_integrations (
                    user_id, tenant_id, tenant_name, connected_user_email,
                    access_token_encrypted, refresh_token_encrypted,
                    scope, token_expires_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8
                )
                ON CONFLICT (user_id, tenant_id)
                DO UPDATE SET
                    tenant_name = EXCLUDED.tenant_name,
                    connected_user_email = EXCLUDED.connected_user_email,
                    access_token_encrypted = EXCLUDED.access_token_encrypted,
                    refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                    scope = EXCLUDED.scope,
                    token_expires_at = EXCLUDED.token_expires_at,
                    updated_at = NOW()
                RETURNING tenant_id, tenant_name, connected_user_email, created_at
                """,
                user_id,
                tenant_id,
                tenant_name,
                user_email,
                encrypted_access,
                encrypted_refresh,
                token_data.get("scope"),
                token_data.get("token_expires_at"),
            )
        return TeamsWorkspace(
            tenant_id=row["tenant_id"],
            tenant_name=row["tenant_name"],
            connected_at=row["created_at"].isoformat(),
            connected_user_email=row.get("connected_user_email"),
        )

    async def _token_request(self, grant_type: str, **kwargs) -> Dict[str, Any]:
        tenant = self.config.teams_tenant_id or "common"
        data = {
            "client_id": self.config.teams_client_id,
            "client_secret": self.config.teams_client_secret,
            "redirect_uri": self.config.teams_redirect_uri,
            "grant_type": grant_type,
        }
        data.update(kwargs)
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for enterprise OAuth
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        token_data = resp.json()
        if "access_token" not in token_data:
            raise TeamsServiceError(f"Teams token request failed: {token_data.get('error_description') or token_data}")
        expires_in = token_data.get("expires_in")
        token_data["token_expires_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=expires_in)
            if expires_in
            else None
        )
        return token_data

    async def refresh_token(self, user_id: str, tenant_id: str) -> None:
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT refresh_token_encrypted FROM teams_integrations WHERE tenant_id = $1",
                tenant_id,
            )
            if not row or not row["refresh_token_encrypted"]:
                raise TeamsServiceError("No refresh token available for Teams workspace")
            refresh_token = decrypt_string(row["refresh_token_encrypted"], self.config.teams_encryption_key)
            if not refresh_token:
                raise TeamsServiceError("Failed to decrypt Teams refresh token")

        token_data = await self._token_request(grant_type="refresh_token", refresh_token=refresh_token)
        new_access = encrypt_string(token_data["access_token"], self.config.teams_encryption_key)
        new_refresh = encrypt_string(token_data["refresh_token"], self.config.teams_encryption_key)

        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            await conn.execute(
                """
                UPDATE teams_integrations
                SET access_token_encrypted = $1,
                    refresh_token_encrypted = $2,
                    token_expires_at = $3,
                    updated_at = NOW()
                WHERE tenant_id = $4
                """,
                new_access,
                new_refresh,
                token_data.get("token_expires_at"),
                tenant_id,
            )

    async def list_workspaces(self, user_id: str) -> List[TeamsWorkspace]:
        self._require_enabled()
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            rows = await conn.fetch(
                "SELECT tenant_id, tenant_name, connected_user_email, created_at FROM teams_integrations ORDER BY created_at DESC"
            )
        return [
            TeamsWorkspace(
                tenant_id=row["tenant_id"],
                tenant_name=row["tenant_name"],
                connected_at=row["created_at"].isoformat(),
                connected_user_email=row.get("connected_user_email"),
            )
            for row in rows
        ]

    async def delete_workspace(self, user_id: str, tenant_id: str) -> None:
        self._require_enabled()
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            await conn.execute(
                "DELETE FROM teams_integrations WHERE tenant_id = $1",
                tenant_id,
            )

    async def list_teams(self, user_id: str, tenant_id: str) -> List[TeamsTeam]:
        token = await self._get_access_token(user_id, tenant_id)
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Graph API
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/joinedTeams",
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        if not data.get("value"):
            return []
        return [
            TeamsTeam(
                id=team.get("id"),
                display_name=team.get("displayName"),
            )
            for team in data["value"]
        ]

    async def list_channels(self, user_id: str, tenant_id: str, team_id: str) -> List[TeamsChannel]:
        token = await self._get_access_token(user_id, tenant_id)
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Graph API
            resp = await client.get(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels",
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        if not data.get("value"):
            return []
        return [
            TeamsChannel(
                id=channel.get("id"),
                display_name=channel.get("displayName"),
                membership_type=channel.get("membershipType"),
            )
            for channel in data["value"]
        ]

    async def post_message(
        self,
        user_id: str,
        tenant_id: str,
        team_id: str,
        channel_id: str,
        content: str,
        content_type: str = "html",
    ) -> None:
        token = await self._get_access_token(user_id, tenant_id)
        payload = {
            "body": {
                "contentType": content_type,
                "content": content,
            }
        }
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Graph API
            resp = await client.post(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text
            raise TeamsServiceError(f"Failed to post Teams message: {detail}")

    async def get_channel_drive_info(
        self,
        user_id: str,
        tenant_id: str,
        team_id: str,
        channel_id: str,
    ) -> Dict[str, str]:
        """
        Get SharePoint drive information for a Teams channel.

        Args:
            user_id: User ID for token retrieval
            tenant_id: Teams tenant ID
            team_id: Teams team ID
            channel_id: Channel ID

        Returns:
            Dict with keys: drive_id, folder_id, web_url

        Raises:
            TeamsServiceError: If API call fails
        """
        token = await self._get_access_token(user_id, tenant_id)

        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Graph API
            resp = await client.get(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/filesFolder",
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text
            raise TeamsServiceError(f"Failed to get channel drive info: {detail}")

        data = resp.json()
        parent_ref = data.get("parentReference", {})

        return {
            "drive_id": parent_ref.get("driveId"),
            "folder_id": data.get("id"),
            "web_url": data.get("webUrl"),
        }

    async def upload_file_to_sharepoint(
        self,
        user_id: str,
        tenant_id: str,
        drive_id: str,
        file_path: str,
    ) -> Dict[str, str]:
        """
        Upload a file to a SharePoint drive.

        Args:
            user_id: User ID for token retrieval
            tenant_id: Teams tenant ID
            drive_id: SharePoint drive ID from get_channel_drive_info()
            file_path: Local file path to upload

        Returns:
            Dict with keys: id, web_url, name, size

        Raises:
            TeamsServiceError: If file not found or upload fails
        """
        path = Path(file_path)
        if not path.exists():
            raise TeamsServiceError(f"File not found: {file_path}")

        # Check file size (simple upload has 4MB limit)
        file_size = path.stat().st_size
        if file_size > 4 * 1024 * 1024:  # 4MB
            logger.warning(
                f"File {path.name} is {file_size / 1024 / 1024:.2f}MB. "
                "Files >4MB may require chunked upload (not yet implemented)."
            )

        token = await self._get_access_token(user_id, tenant_id)

        # Read file content
        with open(path, 'rb') as f:
            file_content = f.read()

        # Upload to drive root (General folder)
        async with httpx.AsyncClient(timeout=240) as client:  # 4x for large file uploads
            resp = await client.put(
                f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/root:/{path.name}:/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                },
                content=file_content,
            )

        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text
            raise TeamsServiceError(f"Failed to upload file to SharePoint: {detail}")

        data = resp.json()
        logger.info(f"Uploaded file to SharePoint: {path.name} (size: {file_size} bytes)")

        return {
            "id": data.get("id"),
            "web_url": data.get("webUrl"),
            "name": data.get("name"),
            "size": data.get("size"),
        }

    async def post_message_with_attachments(
        self,
        user_id: str,
        tenant_id: str,
        team_id: str,
        channel_id: str,
        content: str,
        attachments: List[Dict[str, str]],
        content_type: str = "html",
    ) -> None:
        """
        Post a message to a Teams channel with SharePoint file attachments.

        Args:
            user_id: User ID for token retrieval
            tenant_id: Teams tenant ID
            team_id: Teams team ID
            channel_id: Channel ID
            content: Message HTML content
            attachments: List of dicts with keys: contentUrl, name
            content_type: "html" or "text"

        Raises:
            TeamsServiceError: If API call fails
        """
        import uuid

        token = await self._get_access_token(user_id, tenant_id)

        # Build attachment references in content
        attachment_tags = []
        formatted_attachments = []

        for att in attachments:
            att_id = str(uuid.uuid4())
            attachment_tags.append(f'<attachment id="{att_id}"></attachment>')
            formatted_attachments.append({
                "id": att_id,
                "contentType": "reference",
                "contentUrl": att["contentUrl"],
                "name": att["name"],
            })

        # Append attachment tags to content
        full_content = content
        if attachment_tags:
            full_content += "<br><br>" + "".join(attachment_tags)

        payload = {
            "body": {
                "contentType": content_type,
                "content": full_content,
            },
            "attachments": formatted_attachments,
        }

        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Graph API
            resp = await client.post(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text
            raise TeamsServiceError(f"Failed to post Teams message with attachments: {detail}")

    async def _get_access_token(self, user_id: str, tenant_id: str) -> str:
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT access_token_encrypted, token_expires_at FROM teams_integrations WHERE tenant_id = $1",
                tenant_id,
            )
            if not row:
                raise TeamsServiceError("Teams workspace not connected")
        token = decrypt_string(row["access_token_encrypted"], self.config.teams_encryption_key)
        if not token:
            raise TeamsServiceError("Unable to decrypt Teams access token")
        # If token is near expiry, refresh synchronously
        expires_at = row.get("token_expires_at")
        if expires_at:
            # expires_at is now a datetime object from the database
            time_until_expiry = (expires_at - datetime.now(timezone.utc)).total_seconds()
            if time_until_expiry < 60:
                await self.refresh_token(user_id, tenant_id)
                return await self._get_access_token(user_id, tenant_id)
        return token


_teams_service: Optional[TeamsService] = None


def get_teams_service() -> TeamsService:
    global _teams_service  # pylint: disable=global-statement
    if _teams_service is None:
        _teams_service = TeamsService()
    return _teams_service

