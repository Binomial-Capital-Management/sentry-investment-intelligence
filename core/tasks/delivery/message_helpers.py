"""
Shared helpers for constructing delivery messages (Slack, Teams, etc.).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def stringify_output(output: Any) -> str:
    """
    Extract readable text from agent output.
    Handles _ResultLike objects from Runner.run() by accessing .final_output attribute.
    """
    if output is None:
        return ""

    # Extract text from agent result (handles _ResultLike objects from Runner.run())
    if hasattr(output, 'final_output'):
        text = output.final_output
        if isinstance(text, str):
            return text

    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        try:
            return json.dumps(output, indent=2)
        except Exception:  # pragma: no cover - best effort
            return str(output)
    return str(output)


def format_artifacts_text(artifacts: List[Dict[str, Any]], heading: str = "Artifacts:") -> str:
    if not artifacts:
        return ""
    lines = [heading]
    for artifact in artifacts:
        name = artifact.get("name") or artifact.get("path") or "Unnamed artifact"
        path = artifact.get("path")
        if path:
            lines.append(f"- {name} ({path})")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def format_artifacts_html(artifacts: List[Dict[str, Any]], heading: str = "Artifacts") -> str:
    if not artifacts:
        return ""
    from html import escape  # local import to avoid global cost

    items = []
    for artifact in artifacts:
        name = artifact.get("name") or artifact.get("path") or "Unnamed artifact"
        path = artifact.get("path")
        if path:
            items.append(f"<li>{escape(name)} (<code>{escape(path)}</code>)</li>")
        else:
            items.append(f"<li>{escape(name)}</li>")
    return f"<p><strong>{escape(heading)}</strong></p><ul>{''.join(items)}</ul>"


async def resolve_intro(
    task_name: str,
    run_id: str,
    analysis: str,
    *,
    custom_message: Optional[str],
    ai_generated: bool,
    llm_client=None,
    preview_chars: int = 500,
) -> str:
    if custom_message:
        return custom_message.strip()
    if not ai_generated:
        return f"Task '{task_name}' completed."
    llm = llm_client or openai_client
    if not llm:
        return f"Automated update for task '{task_name}'."
    preview = (analysis or "")[:preview_chars]
    if not preview:
        preview = f"Task '{task_name}' completed."
    try:
        response = await llm.responses.create(
            model="gpt-5-nano",
            input=(
                "You draft concise notifications (max 260 characters) for investment research updates.\n"
                "Tone: professional but warm. Reference the task/run when helpful.\n"
                f"Task: {task_name}\nRun ID: {run_id}\nAnalysis preview:\n{preview}"
            ),
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
        )
        message = (response.output_text or "").strip()
        return message or f"Automated update for task '{task_name}'."
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("AI intro generation failed: %s", exc)
        return f"Automated update for task '{task_name}'."
