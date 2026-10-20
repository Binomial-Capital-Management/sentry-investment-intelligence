"""
Teams delivery adapter for Tasks.
Posts analysis summaries to Microsoft Teams channels selected in the canvas.
Supports file attachments via SharePoint upload.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

logger = logging.getLogger(__name__)

from core.services.teams_service import get_teams_service, TeamsServiceError
from core.tasks.types import TaskDeliveryStep
from .message_helpers import (
    format_artifacts_html,
    resolve_intro,
    stringify_output,
)

if TYPE_CHECKING:
    from core.tasks.executor import TaskRunContext


class TeamsDeliveryAdapter:
    """Send task outputs to Teams channels."""

    def __init__(self) -> None:
        self.teams_service = get_teams_service()
        self.llm_client = None

    async def deliver(self, step: TaskDeliveryStep, context: "TaskRunContext") -> Dict[str, Any]:
        params = step.params or {}
        tenant_id = params.get("tenantId")
        team_id = params.get("teamId")
        channel_ids = self._normalize_channel_ids(params.get("channelIds"))

        if not tenant_id:
            raise TeamsServiceError("Teams tenant ID missing from delivery step")
        if not team_id:
            raise TeamsServiceError("Teams team ID missing from delivery step")
        if not channel_ids:
            raise TeamsServiceError("Teams delivery requires at least one channel")

        html_body = await self._build_message(params, context)

        # Extract artifact file paths
        file_paths = [
            artifact.get("path")
            for artifact in context.artifacts
            if artifact.get("path")
        ]

        sent_channels: List[str] = []
        failed_channels: List[Dict[str, str]] = []

        for channel_id in channel_ids:
            try:
                if file_paths:
                    # Upload files to SharePoint and attach to message
                    await self._deliver_with_files(
                        context.user_id,
                        tenant_id,
                        team_id,
                        channel_id,
                        html_body,
                        file_paths,
                    )
                else:
                    # Regular message without files
                    await self.teams_service.post_message(
                        context.user_id,
                        tenant_id,
                        team_id,
                        channel_id,
                        html_body,
                        content_type="html",
                    )
                sent_channels.append(channel_id)
            except TeamsServiceError as exc:
                failed_channels.append({"channel": channel_id, "error": str(exc)})

        status = "sent"
        if failed_channels and sent_channels:
            status = "partial"
        elif failed_channels and not sent_channels:
            status = "failed"

        return {
            "status": status,
            "tenant_id": tenant_id,
            "team_id": team_id,
            "sent_channels": sent_channels,
            "failed_channels": failed_channels or None,
            "attachments": len(file_paths),
        }

    def _normalize_channel_ids(self, raw: Optional[Any]) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, Sequence):
            return [str(item) for item in raw if item]
        return []

    async def _build_message(self, params: Dict[str, Any], context: "TaskRunContext") -> str:
        custom = params.get("customMessage")
        ai_generated = bool(params.get("aiGeneratedMessage"))

        analysis = stringify_output(context.current_output) or "No analysis output was generated."
        intro = await resolve_intro(
            context.task.name,
            context.run_id,
            analysis,
            custom_message=custom,
            ai_generated=ai_generated,
            llm_client=self.llm_client,
        )

        intro_html = html.escape(intro).replace("\n", "<br>")
        analysis_html = html.escape(analysis).replace("\n", "<br>")
        artifacts_html = format_artifacts_html(context.artifacts)

        sections = [
            f"<p><strong>{intro_html}</strong></p>",
            f"<p>{analysis_html}</p>",
            artifacts_html,
            f"<p style='font-size:11px;color:#666;'>Run ID: {html.escape(context.run_id)}</p>",
        ]
        return "".join(section for section in sections if section)

    async def _deliver_with_files(
        self,
        user_id: str,
        tenant_id: str,
        team_id: str,
        channel_id: str,
        html_body: str,
        file_paths: List[str],
    ) -> None:
        """
        Upload files to SharePoint and post message with file attachments.

        This implements the 2-step process:
        1. Upload files to channel's SharePoint document library
        2. Reference uploaded files as attachments in the message

        Args:
            user_id: User ID for authentication
            tenant_id: Teams tenant ID
            team_id: Teams team ID
            channel_id: Channel ID
            html_body: HTML message content
            file_paths: List of local file paths to upload

        Raises:
            TeamsServiceError: If critical operation fails
        """
        from pathlib import Path

        # Step 1: Get channel's SharePoint drive information
        drive_info = await self.teams_service.get_channel_drive_info(
            user_id,
            tenant_id,
            team_id,
            channel_id,
        )
        drive_id = drive_info.get("drive_id")
        if not drive_id:
            raise TeamsServiceError("Failed to get SharePoint drive ID for channel")

        # Step 2: Upload each file to SharePoint
        uploaded_files: List[Dict[str, str]] = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found, skipping: {file_path}")
                continue

            try:
                file_info = await self.teams_service.upload_file_to_sharepoint(
                    user_id,
                    tenant_id,
                    drive_id,
                    file_path,
                )
                uploaded_files.append({
                    "contentUrl": file_info["web_url"],
                    "name": file_info["name"],
                })
                logger.info(f"Uploaded file to SharePoint: {file_info['name']}")
            except TeamsServiceError as exc:
                logger.error(f"Failed to upload file {path.name}: {exc}")
                # Continue with other files instead of failing completely
                continue

        # Step 3: Post message with file references
        if uploaded_files:
            await self.teams_service.post_message_with_attachments(
                user_id,
                tenant_id,
                team_id,
                channel_id,
                html_body,
                uploaded_files,
                content_type="html",
            )
            logger.info(f"Posted message with {len(uploaded_files)} attachments to channel {channel_id}")
        else:
            # No files uploaded successfully, post message without attachments
            logger.warning("No files uploaded successfully, posting message without attachments")
            await self.teams_service.post_message(
                user_id,
                tenant_id,
                team_id,
                channel_id,
                html_body,
                content_type="html",
            )
