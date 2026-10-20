"""
Slack integration helpers: OAuth, storage, channel listing, and messaging.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client
from core.utils.crypto import decrypt_string, encrypt_string

logger = logging.getLogger(__name__)


@dataclass
class SlackWorkspace:
    team_id: str
    team_name: Optional[str]
    connected_at: str


class SlackServiceError(RuntimeError):
    """Raised for Slack integration failures."""


class SlackService:
    def __init__(self):
        self.config = get_config()
        self._pg = None

    async def _pg_client(self):
        if not self._pg:
            self._pg = await get_postgres_rls_client()
        return self._pg

    def _require_enabled(self):
        if not self.config.slack_enabled:
            raise SlackServiceError("Slack integration is disabled")

    def _build_state(self, user_id: str) -> str:
        payload = {
            "user_id": user_id,
            "ts": int(time.time()),
            "nonce": secrets.token_urlsafe(12),
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            self.config.slack_signing_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        state = (
            base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
            + "."
            + signature
        )
        return state

    def _decode_state(self, state: str) -> str:
        try:
            encoded_payload, signature = state.split(".", 1)
            padding = "=" * (-len(encoded_payload) % 4)
            payload_bytes = base64.urlsafe_b64decode(encoded_payload + padding)
            expected_sig = hmac.new(
                self.config.slack_signing_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, signature):
                raise SlackServiceError("Invalid Slack state signature")
            payload = json.loads(payload_bytes.decode("utf-8"))
            ts = payload.get("ts", 0)
            ttl = self.config.slack_state_ttl_seconds
            if int(time.time()) - ts > ttl:
                raise SlackServiceError("Slack authorization link expired")
            return payload["user_id"]
        except SlackServiceError:
            raise
        except Exception as exc:
            raise SlackServiceError("Invalid Slack state") from exc

    def build_authorize_url(self, user_id: str) -> str:
        self._require_enabled()
        state = self._build_state(user_id)
        scopes = self.config.slack_scopes
        redirect_uri = self.config.slack_redirect_uri
        return (
            "https://slack.com/oauth/v2/authorize"
            f"?client_id={self.config.slack_client_id}"
            f"&scope={scopes}"
            f"&state={state}"
            f"&redirect_uri={redirect_uri}"
        )

    async def exchange_code(self, code: str, state: str) -> SlackWorkspace:
        self._require_enabled()
        user_id = self._decode_state(state)
        payload = {
            "client_id": self.config.slack_client_id,
            "client_secret": self.config.slack_client_secret,
            "code": code,
            "redirect_uri": self.config.slack_redirect_uri,
        }
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Slack API
            resp = await client.post("https://slack.com/api/oauth.v2.access", data=payload)
        data = resp.json()
        if not data.get("ok"):
            raise SlackServiceError(f"Slack OAuth failed: {data.get('error', 'unknown_error')}")

        access_token = data.get("access_token")
        if not access_token:
            raise SlackServiceError("Slack response missing access token")

        team = data.get("team") or {}
        team_id = team.get("id")
        if not team_id:
            raise SlackServiceError("Slack response missing team id")

        encrypted_token = encrypt_string(access_token, self.config.slack_encryption_key)
        authed_user = data.get("authed_user") or {}
        bot_user_id = data.get("bot_user_id")

        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO slack_integrations (
                    user_id, team_id, team_name, bot_user_id,
                    authed_user_id, access_token_encrypted, scope
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7
                )
                ON CONFLICT (user_id, team_id)
                DO UPDATE SET
                    team_name = EXCLUDED.team_name,
                    bot_user_id = EXCLUDED.bot_user_id,
                    authed_user_id = EXCLUDED.authed_user_id,
                    access_token_encrypted = EXCLUDED.access_token_encrypted,
                    scope = EXCLUDED.scope,
                    updated_at = NOW()
                RETURNING team_id, team_name, created_at
                """,
                user_id,
                team_id,
                team.get("name"),
                bot_user_id,
                authed_user.get("id"),
                encrypted_token,
                data.get("scope"),
            )
        return SlackWorkspace(
            team_id=row["team_id"],
            team_name=row["team_name"],
            connected_at=row["created_at"].isoformat(),
        )

    async def list_workspaces(self, user_id: str) -> List[SlackWorkspace]:
        self._require_enabled()
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            rows = await conn.fetch(
                """
                SELECT team_id, team_name, created_at
                FROM slack_integrations
                ORDER BY created_at DESC
                """
            )
        return [
            SlackWorkspace(
                team_id=row["team_id"],
                team_name=row["team_name"],
                connected_at=row["created_at"].isoformat(),
            )
            for row in rows
        ]

    async def delete_workspace(self, user_id: str, team_id: str) -> None:
        self._require_enabled()
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            await conn.execute(
                "DELETE FROM slack_integrations WHERE team_id = $1",
                team_id,
            )

    async def list_channels(self, user_id: str, team_id: str) -> List[Dict[str, Any]]:
        token = await self._get_access_token(user_id, team_id)
        params = {
            "limit": 200,
            "types": "public_channel,private_channel",
        }
        channels: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Slack API
            cursor = None
            for _ in range(3):  # cap pagination to prevent runaway loops
                if cursor:
                    params["cursor"] = cursor
                resp = await client.get(
                    "https://slack.com/api/conversations.list",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                data = resp.json()
                if not data.get("ok"):
                    slack_error = data.get('error', 'unknown')
                    logger.error(f"Slack API error listing channels: {slack_error}, full response: {data}")
                    raise SlackServiceError(f"Failed to list Slack channels: {slack_error}")
                channels.extend(
                    {
                        "id": ch.get("id"),
                        "name": ch.get("name"),
                        "is_private": ch.get("is_private"),
                    }
                    for ch in data.get("channels", [])
                )
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        return channels

    async def post_message(
        self,
        user_id: str,
        team_id: str,
        channel_id: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        token = await self._get_access_token(user_id, team_id)
        payload = {"channel": channel_id, "text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient(timeout=80) as client:  # 4x for Slack API
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
        data = resp.json()
        if not data.get("ok"):
            raise SlackServiceError(f"Failed to post Slack message: {data.get('error')}")

    async def post_message_with_files(
        self,
        user_id: str,
        team_id: str,
        channel_id: str,
        text: str,
        file_paths: List[str],
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Post message with file attachments using new 3-step upload API."""
        if not file_paths:
            # No files, use regular message
            await self.post_message(user_id, team_id, channel_id, text, blocks)
            return

        token = await self._get_access_token(user_id, team_id)

        # Upload each file to Slack using new 3-step API
        async with httpx.AsyncClient(timeout=240) as client:  # 4x for large file uploads
            uploaded_file_ids = []

            for file_path in file_paths:
                path = Path(file_path)
                if not path.exists():
                    logger.warning("File not found, skipping: %s", file_path)
                    continue

                try:
                    # Step 1: Get upload URL
                    file_size = path.stat().st_size
                    step1_resp = await client.post(
                        "https://slack.com/api/files.getUploadURLExternal",
                        headers={"Authorization": f"Bearer {token}"},
                        data={
                            "filename": path.name,
                            "length": str(file_size),
                        },
                    )
                    step1_data = step1_resp.json()

                    if not step1_data.get("ok"):
                        error = step1_data.get('error', 'unknown_error')
                        logger.error("Failed to get upload URL for %s: %s", path.name, error)
                        raise SlackServiceError(f"Failed to get upload URL: {error}")

                    upload_url = step1_data["upload_url"]
                    file_id = step1_data["file_id"]

                    # Step 2: Upload file binary to the URL
                    with open(path, 'rb') as f:
                        file_content = f.read()

                    step2_resp = await client.post(
                        upload_url,
                        headers={"Content-Type": "application/octet-stream"},
                        content=file_content,
                    )

                    if step2_resp.status_code != 200:
                        logger.error("Failed to upload file binary for %s: HTTP %d", path.name, step2_resp.status_code)
                        raise SlackServiceError(f"Failed to upload file binary: HTTP {step2_resp.status_code}")

                    uploaded_file_ids.append({"id": file_id, "title": path.stem})
                    logger.info("Uploaded file to Slack: %s (file_id: %s)", path.name, file_id)

                except Exception as exc:
                    logger.error("Failed to upload file %s: %s", path.name, exc)
                    # Continue with other files instead of failing completely
                    continue

            # Step 3: Complete upload and share to channel
            if uploaded_file_ids:
                try:
                    step3_resp = await client.post(
                        "https://slack.com/api/files.completeUploadExternal",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json; charset=utf-8",
                        },
                        json={
                            "files": uploaded_file_ids,
                            "channel_id": channel_id,
                            "initial_comment": text,
                        },
                    )
                    step3_data = step3_resp.json()

                    if not step3_data.get("ok"):
                        error = step3_data.get('error', 'unknown_error')
                        logger.error("Failed to complete upload: %s", error)

                        # Provide helpful error messages
                        if error == 'not_in_channel':
                            raise SlackServiceError(
                                f"Bot not added to channel. Please invite the bot to your Slack channel: "
                                f"Type '/invite @BotName' in the channel or go to Channel Details → Integrations → Add Apps"
                            )
                        elif error == 'missing_scope':
                            raise SlackServiceError(
                                f"Missing file upload permissions. Please reinstall the Slack app at https://api.slack.com/apps "
                                f"to grant 'files:read' and 'files:write' scopes"
                            )
                        else:
                            raise SlackServiceError(f"Failed to complete file upload: {error}")

                    logger.info("Successfully shared %d files to channel %s", len(uploaded_file_ids), channel_id)

                except Exception as exc:
                    logger.error("Failed to complete upload: %s", exc)
                    raise

    async def _get_access_token(self, user_id: str, team_id: str) -> str:
        pg = await self._pg_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT access_token_encrypted FROM slack_integrations WHERE team_id = $1",
                team_id,
            )
            if not row:
                raise SlackServiceError("Slack workspace not connected")
        token = decrypt_string(row["access_token_encrypted"], self.config.slack_encryption_key)
        if not token:
            raise SlackServiceError("Unable to decrypt Slack token")
        return token


_slack_service: Optional[SlackService] = None


def get_slack_service() -> SlackService:
    global _slack_service  # pylint: disable=global-statement
    if _slack_service is None:
        _slack_service = SlackService()
    return _slack_service

