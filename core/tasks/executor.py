"""
Task execution engine.
Runs a TaskDefinition produced by the parser, invokes LangGraph agents, generates outputs,
and dispatches delivery steps while updating task_runs records.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.orchestrator import get_v6_orchestrator
from api.routers.user_settings import fetch_user_export_style
from core.workflows.engine import truncate_output  # Reuse existing helper
from core.integrations.gamma_client import get_gamma_client, build_instructions_from_settings
from core.tasks.types import (
    TaskAgentStep,
    TaskDefinition,
    TaskDeliveryStep,
    TaskDeliveryChannel,
    TaskOutputSpec,
    TaskOutputType,
    TaskRecord,
    TaskRunRecord,
    TaskRunStatus,
    TaskTriggerType,
)
from core.tasks.registry import get_agent_spec
from core.services.artifact_storage import get_artifact_storage
from core.tasks.delivery import deliver as deliver_step

logger = logging.getLogger(__name__)

TASK_ARTIFACT_ROOT = Path(os.getenv("TASK_ARTIFACT_DIR", "/tmp/tasks"))
TASK_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class TaskRunContext:
    """Tracks transient state during execution."""

    task: TaskRecord
    definition: TaskDefinition
    run_id: str
    trigger_type: TaskTriggerType
    user_id: str
    current_output: Optional[Any] = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    delivery_results: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def artifact_dir(self) -> Path:
        path = TASK_ARTIFACT_ROOT / self.run_id
        path.mkdir(parents=True, exist_ok=True)
        return path


class TasksRepository:
    """Thin repository wrapper (implemented later)."""

    async def create_run(
        self,
        task_id: str,
        user_id: str,
        trigger_type: TaskTriggerType,
    ) -> TaskRunRecord:  # pragma: no cover - placeholder
        raise NotImplementedError

    async def mark_run_status(
        self,
        run_id: str,
        user_id: str,
        status: TaskRunStatus,
        *,
        result: Optional[Dict[str, Any]] = None,
        delivery_results: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
    ) -> None:  # pragma: no cover - placeholder
        raise NotImplementedError


class DeliveryAdapter:
    """Base delivery adapter interface."""

    async def deliver(self, step: TaskDeliveryStep, context: TaskRunContext) -> Dict[str, Any]:  # pragma: no cover - placeholder
        raise NotImplementedError


class TaskExecutor:
    """Runs a task definition end-to-end."""

    def __init__(
        self,
        repository: TasksRepository,
        delivery_adapters: Dict[TaskDeliveryChannel, DeliveryAdapter],
    ) -> None:
        self.repository = repository
        self.delivery_adapters = delivery_adapters
        self.artifact_storage = get_artifact_storage()

    async def run_task(self, task: TaskRecord, run: TaskRunRecord) -> TaskRunRecord:
        # Use the run provided by the caller (no duplicate creation)
        context = TaskRunContext(
            task=task,
            definition=task.agent_config,
            run_id=run.id,
            trigger_type=run.trigger_type,
            user_id=task.user_id,
        )
        context.started_at = datetime.now(timezone.utc)

        try:
            await self.repository.mark_run_status(
                run.id,
                task.user_id,
                TaskRunStatus.RUNNING,
                org_id=task.org_id,
            )
            await self._execute_agents(context)
            await self._execute_outputs(context)
            await self._execute_deliveries(context)
            context.completed_at = datetime.now(timezone.utc)
            await self.repository.mark_run_status(
                run.id,
                task.user_id,
                TaskRunStatus.COMPLETED,
                result=self._build_result_payload(context),
                delivery_results=context.delivery_results,
                org_id=task.org_id,
            )
        except Exception as exc:
            logger.exception("Task execution failed for run %s", run.id)
            await self.repository.mark_run_status(
                run.id,
                task.user_id,
                TaskRunStatus.FAILED,
                result=self._build_result_payload(context),
                delivery_results=context.delivery_results,
                error_message=str(exc),
                org_id=task.org_id,
            )
            raise

        return run

    # ===== Agent Execution =====

    async def _execute_agents(self, context: TaskRunContext) -> None:
        if not context.definition.agents:
            raise ValueError("Task must contain at least one agent node")

        orchestrator = get_v6_orchestrator()
        session_id = f"task_{context.run_id}"

        # Import runner lazily to avoid cycles
        from agents import Runner, SQLiteSession  # pylint: disable=import-outside-toplevel
        from core.ai.langgraph_utils import trim_sqlite_session_history  # pylint: disable=import-outside-toplevel
        from core.utils.context_utils import user_context, session_context  # pylint: disable=import-outside-toplevel

        session = SQLiteSession(session_id, orchestrator.db_path)

        # Hydrate input data once before agent execution
        from .data_fetchers import hydrate_inputs  # pylint: disable=import-outside-toplevel
        data_context = await hydrate_inputs(context.definition.inputs, context.user_id)

        tok_u = user_context.set(context.user_id)
        tok_s = session_context.set(session_id)

        try:
            for step in context.definition.agents:
                agent_spec = get_agent_spec(step.mode)
                agent_impl = getattr(orchestrator, agent_spec.orchestrator_attr, None)
                if agent_impl is None:
                    raise RuntimeError(f"Orchestrator missing agent '{agent_spec.orchestrator_attr}'")

                payload = self._build_agent_payload(context, step, data_context)
                logger.info("Executing agent %s for run %s", step.mode.value, context.run_id)
                # Runner.run() expects a string prompt, not a dict
                prompt = payload["instructions"]
                await trim_sqlite_session_history(
                    session,
                    getattr(step, "model", None),
                    f"task_{step.mode.value}",
                )
                result = await Runner.run(
                    agent_impl,
                    prompt,
                    session=session,
                )
                context.current_output = result
        finally:
            user_context.reset(tok_u)
            session_context.reset(tok_s)

    def _build_agent_payload(self, context: TaskRunContext, step: TaskAgentStep, data_context: str) -> Dict[str, Any]:
        base_instructions = self._build_instruction_with_modifiers(step)

        # Prepend data context to instructions (like chat does with portfolio_state)
        if data_context:
            instructions = f"{data_context}\n\n=== Task Instructions ===\n{base_instructions}" if base_instructions else data_context
        else:
            instructions = base_instructions

        payload = {
            "instructions": instructions,
            "model": step.model,
            "schedule": context.task.schedule_config.dict(),
            "previous_output": context.current_output,
            "task_metadata": {
                "task_id": context.task.id,
                "run_id": context.run_id,
                "name": context.task.name,
            },
        }
        settings = step.settings.dict(exclude_none=True)
        settings.pop("reasoning", None)
        settings.pop("response_length", None)
        if settings:
            payload["settings"] = settings
        return payload

    def _build_instruction_with_modifiers(self, step: TaskAgentStep) -> Optional[str]:
        base = (step.instructions or "").strip()
        modifiers: List[str] = []

        reasoning = (step.settings.reasoning or "").strip().lower()
        if reasoning:
            reasoning_map = {
                "low": "Use lightweight reasoning; skip detailed chains unless required.",
                "medium": "Use a balanced amount of reasoning with a few explicit steps.",
                "high": "Think through the problem step-by-step, documenting the reasoning clearly.",
            }
            text = reasoning_map.get(reasoning)
            if text:
                modifiers.append(text)

        response_length = (step.settings.response_length or "").strip().lower()
        if response_length:
            length_map = {
                "short": "Keep the response under three concise paragraphs.",
                "medium": "Provide a mid-length response (roughly 4-6 paragraphs).",
                "long": "Provide a comprehensive response with rich detail (7+ paragraphs).",
            }
            text = length_map.get(response_length)
            if text:
                modifiers.append(text)

        if not modifiers:
            return base or None
        modifier_text = "\n".join(modifiers)
        if base:
            return f"{base}\n\n{modifier_text}"
        return modifier_text

    # ===== Output Handling =====

    async def _execute_outputs(self, context: TaskRunContext) -> None:
        if not context.definition.outputs:
            return
        for spec in context.definition.outputs:
            if spec.type == TaskOutputType.PDF:
                artifact = await self._render_pdf(context, spec)
            elif spec.type == TaskOutputType.PRESENTATION:
                artifact = await self._render_ppt(context, spec)
            elif spec.type == TaskOutputType.WORKBOOK:
                artifact = await self._render_workbook(context, spec)
            else:
                continue
            context.artifacts.append(artifact)

    async def _render_pdf(self, context: TaskRunContext, spec: TaskOutputSpec) -> Dict[str, Any]:
        content = self._normalize_output_text(context.current_output)
        gamma_client = get_gamma_client()

        # Extract custom parameters from task node (if provided)
        params = spec.params or {}

        # Extract style_name from task params (if provided)
        style_name = params.get("style_name")

        # Fetch user export settings (defaults if not configured)
        user_settings = await fetch_user_export_style(context.user_id, style_name)

        # Determine final settings: user settings as baseline, task params override
        final_verbosity = params.get("verbosity", user_settings.verbosity)
        final_tone = params.get("tone", user_settings.tone)
        final_audience = params.get("audience", user_settings.audience)

        # Custom instructions: task params override user settings
        base_custom_prompt = (
            params.get("contentInstructions")
            or params.get("additional_instructions")
            or user_settings.custom_prompt
        )

        # Build natural language instructions from settings
        # Gamma doesn't accept verbosity/tone/audience as structured params
        # Instead, we inject them as instructions in additionalInstructions
        final_instructions = build_instructions_from_settings(
            base_prompt=base_custom_prompt,
            verbosity=final_verbosity,
            tone=final_tone,
            audience=final_audience
        )

        # Build card options with logo from user settings (unless task disables it)
        card_options = None
        if user_settings.logo_source != "none":
            header_footer = {
                "bottomRight": {"type": "cardNumber"},
                "hideFromFirstCard": True
            }

            logo_config = {
                "type": "image",
                "source": user_settings.logo_source,
                "size": user_settings.logo_size
            }

            # Add src only if custom logo with URL
            if user_settings.logo_source == "custom" and user_settings.logo_url:
                logo_config["src"] = user_settings.logo_url

            header_footer[user_settings.logo_position] = logo_config
            card_options = {"headerFooter": header_footer}

        # Generate PDF with Gamma API (with user settings + task customization)
        # Note: Only pass language in text_options (Gamma accepts this)
        pdf_bytes = await gamma_client.generate_presentation(
            content=content,
            format="document",
            export_as="pdf",
            theme_id=user_settings.theme_id,
            text_options={"language": user_settings.language},
            additional_instructions=final_instructions,
            cardOptions=card_options
        )

        if pdf_bytes is None:
            raise RuntimeError("Failed to generate PDF export. Please try again.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = context.artifact_dir() / f"{spec.name or 'task_report'}_{timestamp}.pdf"
        filename.write_bytes(pdf_bytes)

        await self.artifact_storage.persist_local_file("tasks", filename.name, filename)

        # Build S3 key for presigned URL generation later
        s3_key = f"tasks/{filename.name}"
        if self.artifact_storage.prefix:
            s3_key = f"{self.artifact_storage.prefix}/{s3_key}"

        return {
            "type": "pdf",
            "path": str(filename),
            "name": spec.name or filename.name,
            "s3_key": s3_key,
            "category": "tasks",
            "filename": filename.name,
        }

    async def _render_ppt(self, context: TaskRunContext, spec: TaskOutputSpec) -> Dict[str, Any]:
        content = self._normalize_output_text(context.current_output)
        gamma_client = get_gamma_client()

        # Extract custom parameters from task node (if provided)
        params = spec.params or {}

        # Extract style_name from task params (if provided)
        style_name = params.get("style_name")

        # Fetch user export settings (defaults if not configured)
        user_settings = await fetch_user_export_style(context.user_id, style_name)

        # Determine final settings: user settings as baseline, task params override
        final_verbosity = params.get("verbosity", user_settings.verbosity)
        final_tone = params.get("tone", user_settings.tone)
        final_audience = params.get("audience", user_settings.audience)

        # Custom instructions: task params override user settings
        base_custom_prompt = (
            params.get("contentInstructions")
            or params.get("additional_instructions")
            or user_settings.custom_prompt
        )

        # Build natural language instructions from settings
        # Gamma doesn't accept verbosity/tone/audience as structured params
        # Instead, we inject them as instructions in additionalInstructions
        final_instructions = build_instructions_from_settings(
            base_prompt=base_custom_prompt,
            verbosity=final_verbosity,
            tone=final_tone,
            audience=final_audience
        )

        # Build card options with logo from user settings (unless task disables it)
        card_options = None
        if user_settings.logo_source != "none":
            header_footer = {
                "bottomRight": {"type": "cardNumber"},
                "hideFromFirstCard": True
            }

            logo_config = {
                "type": "image",
                "source": user_settings.logo_source,
                "size": user_settings.logo_size
            }

            # Add src only if custom logo with URL
            if user_settings.logo_source == "custom" and user_settings.logo_url:
                logo_config["src"] = user_settings.logo_url

            header_footer[user_settings.logo_position] = logo_config
            card_options = {"headerFooter": header_footer}

        # Generate PPTX with Gamma API (with user settings + task customization)
        # Note: Only pass language in text_options (Gamma accepts this)
        ppt_bytes = await gamma_client.generate_presentation(
            content=content,
            format="presentation",
            export_as="pptx",
            theme_id=user_settings.theme_id,
            text_options={"language": user_settings.language},
            additional_instructions=final_instructions,
            cardOptions=card_options
        )

        if ppt_bytes is None:
            raise RuntimeError("Failed to generate presentation export. Please try again.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = context.artifact_dir() / f"{spec.name or 'task_presentation'}_{timestamp}.pptx"
        filename.write_bytes(ppt_bytes)

        await self.artifact_storage.persist_local_file("tasks", filename.name, filename)

        # Build S3 key for presigned URL generation later
        s3_key = f"tasks/{filename.name}"
        if self.artifact_storage.prefix:
            s3_key = f"{self.artifact_storage.prefix}/{s3_key}"

        return {
            "type": "presentation",
            "path": str(filename),
            "name": spec.name or filename.name,
            "s3_key": s3_key,
            "category": "tasks",
            "filename": filename.name,
        }

    async def _render_workbook(self, context: TaskRunContext, spec: TaskOutputSpec) -> Dict[str, Any]:
        """Generate Excel/CSV workbook using Code Interpreter."""
        from core.workbook_generator import generate_workbook
        
        content = self._normalize_output_text(context.current_output)
        extras = self._build_output_extras(context, spec)
        
        # Extract workbook-specific params from spec.params (set by frontend)
        params = spec.params or {}
        
        # Inject task settings into extras as HARD PROMPT instructions
        extras["workbook_type"] = params.get("workbookType", "excel")  # "excel" or "csv"
        extras["verbosity"] = params.get("verbosity", "mid")           # "high", "mid", "low"
        extras["content_instructions"] = params.get("contentInstructions")  # Optional user guidance
        
        # Generate using Code Interpreter (returns ZIP bytes)
        zip_bytes = await generate_workbook(
            message_id=context.run_id,  # Use run_id for container isolation
            content=content,
            extras=extras,
            portfolio=None,  # Could hydrate from inputs if portfolio node present
        )
        
        # Save ZIP file to artifact storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = context.artifact_dir() / f"{spec.name or 'task_workbook'}_{timestamp}.zip"
        filename.write_bytes(zip_bytes)

        # Persist to S3 and get the S3 key
        await self.artifact_storage.persist_local_file("tasks", filename.name, filename)

        # Build S3 key for presigned URL generation later
        s3_key = f"tasks/{filename.name}"
        if self.artifact_storage.prefix:
            s3_key = f"{self.artifact_storage.prefix}/{s3_key}"

        return {
            "type": "workbook",
            "path": str(filename),
            "name": spec.name or filename.name,
            "format": extras["workbook_type"],  # Metadata for delivery layer
            "s3_key": s3_key,  # For download endpoint to generate presigned URLs
            "category": "tasks",  # For artifact_storage.generate_presigned_url()
            "filename": filename.name,  # For artifact_storage.generate_presigned_url()
        }

    # ===== Delivery =====

    async def _execute_deliveries(self, context: TaskRunContext) -> None:
        if not context.definition.deliveries:
            return
        for step in context.definition.deliveries:
            logger.info("Delivering via %s for run %s", step.channel.value, context.run_id)
            result = await deliver_step(step, context)
            context.delivery_results.append(
                {
                    "channel": step.channel.value,
                    "result": result.get("status"),
                    "detail": result.get("detail"),
                    "metadata": result,
                }
            )

    # ===== Helpers =====

    def _build_result_payload(self, context: TaskRunContext) -> Dict[str, Any]:
        return {
            "final_output": truncate_output(context.current_output),
            "artifacts": context.artifacts,
            "trigger_type": context.trigger_type.value,
            "started_at": context.started_at.isoformat() if context.started_at else None,
            "completed_at": context.completed_at.isoformat() if context.completed_at else None,
        }

    def _normalize_output_text(self, output: Any) -> str:
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            return json.dumps(output, indent=2)
        return str(output)

    def _build_output_extras(self, context: TaskRunContext, spec: TaskOutputSpec) -> Dict[str, Any]:
        return {
            "task_name": context.task.name,
            "task_id": context.task.id,
            "run_id": context.run_id,
            "output_params": spec.params,
            "artifacts": context.artifacts,
        }
