"""
Email delivery adapter for tasks.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, TYPE_CHECKING

from core.services.email_service import get_email_service, EmailServiceError
from core.tasks.types import TaskDeliveryStep
from core.database.postgres_client import get_postgres_rls_client

if TYPE_CHECKING:
    from core.tasks.executor import TaskRunContext


class EmailDeliveryAdapter:
    def __init__(self):
        self.email_service = get_email_service()

    async def _resolve_recipients(self, step: TaskDeliveryStep, user_id: str) -> List[str]:
        """
        Resolve email recipients from both direct emails and saved email lists.
        Merges recipients from params["emails"] and params["emailListIds"].
        """
        params = step.params or {}
        recipients = set(params.get("emails", []))
        list_ids = params.get("emailListIds", [])

        if list_ids:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                rows = await conn.fetch(
                    "SELECT recipients FROM email_lists WHERE id = ANY($1::uuid[])",
                    list_ids
                )
                for row in rows:
                    # Parse JSONB recipients field
                    list_recipients = row["recipients"]
                    if isinstance(list_recipients, str):
                        list_recipients = json.loads(list_recipients)
                    recipients.update(list_recipients)

        return list(recipients)

    async def deliver(self, step: TaskDeliveryStep, context: 'TaskRunContext') -> Dict[str, Any]:
        params = step.params or {}

        # Resolve recipients from both direct emails and saved lists
        recipients = await self._resolve_recipients(step, context.user_id)

        subject = params.get("subject") or f"Task Results: {context.task.name}"
        body = self._build_message(params, context)

        html = self._render_html(context, body)
        text = self._render_text(context, body)

        # Extract artifact file paths for attachments
        attachment_paths = [
            artifact.get("path")
            for artifact in context.artifacts
            if artifact.get("path")
        ]

        try:
            await self.email_service.send_email(
                recipients,
                subject,
                html,
                text,
                attachments=attachment_paths
            )
            return {
                "status": "sent",
                "recipients": recipients,
                "attachments": len(attachment_paths)
            }
        except EmailServiceError as exc:
            return {"status": "failed", "detail": str(exc)}

    def _render_html(self, context: TaskRunContext, message: str) -> str:
        artifact_lines = "".join(
            f'<li>{artifact.get("name") or artifact.get("path")}</li>'
            for artifact in context.artifacts
        )
        return f"""
        <html>
          <body>
            <p>{message}</p>
            <p><strong>Task:</strong> {context.task.name}</p>
            <p><strong>Status:</strong> {context.task.status.value}</p>
            {'<p><strong>Artifacts:</strong><ul>' + artifact_lines + '</ul></p>' if artifact_lines else ''}
          </body>
        </html>
        """

    def _render_text(self, context: TaskRunContext, message: str) -> str:
        artifact_lines = "\n".join(
            f"- {artifact.get('name') or artifact.get('path')}"
            for artifact in context.artifacts
        )
        text = f"{message}\n\nTask: {context.task.name}\nStatus: {context.task.status.value}"
        if artifact_lines:
            text += f"\nArtifacts:\n{artifact_lines}"
        return text

    def _build_message(self, params: Dict[str, Any], context: TaskRunContext) -> str:
        if params.get("aiGeneratedMessage") and context.current_output:
            # Extract text from agent result (handles _ResultLike objects from Runner.run())
            text = (
                context.current_output.final_output
                if hasattr(context.current_output, 'final_output')
                else str(context.current_output)
            )
            return text if len(text) <= 2000 else text[:1997] + "..."
        if params.get("customMessage"):
            return params["customMessage"]
        return f"Task '{context.task.name}' completed with status {context.task.status.value}."
