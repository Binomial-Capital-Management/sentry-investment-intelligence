"""
Slack delivery adapter for Tasks.
Consumes workspace/channel selections from the canvas node and posts the final output
to each configured channel using the stored Slack OAuth token.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from core.services.slack_service import get_slack_service, SlackServiceError
from core.tasks.types import TaskDeliveryStep
from .message_helpers import (
    format_artifacts_text,
    resolve_intro,
    stringify_output,
)

if TYPE_CHECKING:
    from core.tasks.executor import TaskRunContext


logger = logging.getLogger(__name__)


class SlackDeliveryAdapter:
    """Send task outputs to Slack channels selected on the canvas."""

    def __init__(self) -> None:
        self.slack_service = get_slack_service()
        self.llm_client = None

    async def deliver(self, step: TaskDeliveryStep, context: "TaskRunContext") -> Dict[str, Any]:
        params = step.params or {}
        workspace_id = params.get("workspaceId") or params.get("workspace_id")
        channel_ids = self._normalize_channel_ids(params.get("channelIds") or params.get("channel_ids"))

        if not workspace_id:
            raise SlackServiceError("Slack workspace ID missing from delivery step")
        if not channel_ids:
            raise SlackServiceError("Slack delivery requires at least one channel")

        message = await self._build_message(params, context)

        # Extract artifact file paths for attachments
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
                    # Use file upload API when artifacts exist
                    await self.slack_service.post_message_with_files(
                        context.user_id,
                        workspace_id,
                        channel_id,
                        message,
                        file_paths,
                    )
                else:
                    # Regular message when no files
                    await self.slack_service.post_message(
                        context.user_id,
                        workspace_id,
                        channel_id,
                        message,
                    )
                sent_channels.append(channel_id)
            except SlackServiceError as exc:
                failed_channels.append({"channel": channel_id, "error": str(exc)})

        status = "sent"
        if failed_channels and sent_channels:
            status = "partial"
        elif failed_channels and not sent_channels:
            status = "failed"

        return {
            "status": status,
            "workspace_id": workspace_id,
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
        ai_generated = self._to_bool(params.get("aiGeneratedMessage"))

        analysis = stringify_output(context.current_output) or "No analysis output was generated."
        header = await resolve_intro(
            context.task.name,
            context.run_id,
            analysis,
            custom_message=custom,
            ai_generated=ai_generated,
            llm_client=self.llm_client,
        )

        artifact_section = format_artifacts_text(context.artifacts)
        body_parts = [header, analysis, artifact_section, f"Run ID: {context.run_id}"]
        message = "\n\n".join(part for part in body_parts if part)
        return message[:3500]  # Slack hard limit ~4000 chars

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)
