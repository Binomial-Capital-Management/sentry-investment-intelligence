"""
Agentic Action Hooks for OpenAI Agents SDK

Lifecycle hooks that own the full tool event lifecycle (started + completion).
The SDK passes ToolContext to on_tool_start/on_tool_end for function tools,
giving us access to tool_call_id, tool_arguments, and tool_call.

Usage:
    from core.ai.agentic_hooks import create_agentic_hooks
    from core.utils.context_utils import set_event_emitter, reset_event_emitter

    token = set_event_emitter(on_event_callback)
    try:
        hooks = create_agentic_hooks()
        result = await Runner.run_streamed(agent, query, hooks=hooks, ...)
    finally:
        reset_event_emitter(token)
"""

import json
import logging
import uuid
from typing import Any, Optional

from agents.lifecycle import RunHooksBase

logger = logging.getLogger(__name__)


class AgenticActionHooks(RunHooksBase):
    """
    RunHooks that emit tool_call.started, tool_call.output, agent_action,
    and agent_error events for the frontend timeline UI.
    """

    TOOL_DISPLAY_NAMES = {
        'add_dataset_to_workspace': 'Add Dataset To Workspace',
        'create_chart': 'Create Chart',
        'create_tab': 'Create Tab',
        'create_pivot_table': 'Create Pivot Table',
        'remove_dataset': 'Remove Dataset',
        'remove_chart': 'Remove Chart',
        'remove_pivot_table': 'Remove Pivot Table',
        'get_workspace_summary': 'Get Workspace Summary',
        'get_workspace_context': 'Get Workspace Context',
        'discover_data_fields': 'Discover Data Fields',
        'inspect_dataset': 'Inspect Dataset',
        'create_dataset_group': 'Create Dataset Group',
    }

    def __init__(self):
        super().__init__()
        self._pending_tool_calls: dict[str, str] = {}

    def _get_call_id(self, context, tool_name: str) -> str:
        """Extract the SDK's native call_id from ToolContext, with UUID fallback."""
        call_id = getattr(context, 'tool_call_id', None)
        if not call_id:
            tc = getattr(context, 'tool_call', None)
            if tc is not None:
                call_id = getattr(tc, 'call_id', None)
        return call_id or f"tool_{tool_name}_{uuid.uuid4().hex[:8]}"

    async def on_tool_start(self, context, agent, tool) -> None:
        """Emit tool_call.started with the SDK's native call_id."""
        from core.utils.context_utils import get_event_emitter

        tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
        on_event = get_event_emitter()
        if on_event is None:
            return

        call_id = self._get_call_id(context, tool_name)
        self._pending_tool_calls[call_id] = tool_name

        display_name = self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        event = {
            "type": "tool_call.started",
            "item_id": call_id,
            "tool_name": display_name,
        }
        raw_args = getattr(context, 'tool_arguments', None)
        if not raw_args:
            tc = getattr(context, 'tool_call', None)
            if tc is not None:
                raw_args = getattr(tc, 'arguments', None)
        if raw_args:
            try:
                event["arguments"] = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except (json.JSONDecodeError, ValueError):
                pass

        logger.info(f"[AGENTIC_HOOKS] tool_call.started: {display_name} (id={call_id})")
        try:
            await on_event(event)
        except Exception as e:
            logger.warning(f"[AGENTIC_HOOKS] Failed to emit tool_call.started: {e}")

    async def on_tool_end(self, context, agent, tool, result: str) -> None:
        """Emit completion event for every tool call — action or not."""
        from core.utils.context_utils import get_event_emitter

        tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
        call_id = self._get_call_id(context, tool_name)
        self._pending_tool_calls.pop(call_id, None)

        on_event = get_event_emitter()
        if on_event is None:
            return

        parsed = result if isinstance(result, dict) else self._parse_tool_result(result)

        if isinstance(parsed, dict):
            status = parsed.get("status")
            action = parsed.get("action")
            pending_update = parsed.get("pending_update")

            if pending_update:
                event = {
                    "type": "tool_call.output",
                    "item_id": call_id,
                    "output": result if isinstance(result, str) else json.dumps(parsed),
                    "tool_name": tool_name,
                }
                logger.info(f"[AGENTIC_HOOKS] tool_call.output (pending_update): {tool_name}")
                try:
                    await on_event(event)
                except Exception as e:
                    logger.error(f"[AGENTIC_HOOKS] Failed to emit tool_call.output: {e}")
                return

            if status in ("success", "pending_confirmation") and action:
                display_name = self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                event = {
                    "type": "agent_action",
                    "action": action,
                    "actionId": call_id,
                    "itemId": call_id,
                    "message": parsed.get("message"),
                    "toolName": display_name,
                    "pending_confirmation": status == "pending_confirmation",
                }
                logger.info(f"[AGENTIC_HOOKS] agent_action: type={action.get('type')}, id={call_id}")
                try:
                    await on_event(event)
                except Exception as e:
                    logger.warning(f"[AGENTIC_HOOKS] Failed to emit agent_action: {e}")
                return

            if status == "error":
                event = {
                    "type": "agent_error",
                    "message": parsed.get("message", "Tool execution failed"),
                    "itemId": call_id,
                    "toolName": tool_name,
                }
                logger.warning(f"[AGENTIC_HOOKS] agent_error: {parsed.get('message')}")
                try:
                    await on_event(event)
                except Exception as e:
                    logger.warning(f"[AGENTIC_HOOKS] Failed to emit agent_error: {e}")
                return

        output_str = result if isinstance(result, str) else json.dumps(parsed) if parsed else str(result)
        event = {
            "type": "tool_call.output",
            "item_id": call_id,
            "output": output_str,
            "tool_name": tool_name,
        }
        logger.info(f"[AGENTIC_HOOKS] tool_call.output: {tool_name} (id={call_id})")
        try:
            await on_event(event)
        except Exception as e:
            logger.warning(f"[AGENTIC_HOOKS] Failed to emit tool_call.output: {e}")
    
    def _parse_tool_result(self, result: str) -> Optional[Any]:
        """
        Parse tool result string into a Python object.
        
        Handles:
        - JSON strings
        - Double-stringified JSON
        - Dict repr strings (e.g., "{'key': 'value'}")
        
        Args:
            result: The tool result as a string
            
        Returns:
            Parsed Python object or None if parsing fails
        """
        if not result or not isinstance(result, str):
            return None
        
        result = result.strip()
        if not result:
            return None
        
        # Try standard JSON parse
        try:
            parsed = json.loads(result)
            # Handle double-stringified JSON
            if isinstance(parsed, str):
                try:
                    return json.loads(parsed)
                except (json.JSONDecodeError, TypeError):
                    return parsed
            return parsed
        except json.JSONDecodeError:
            pass
        
        # Try Python dict literal (e.g., "{'key': 'value'}")
        if result.startswith("{") or result.startswith("["):
            try:
                import ast
                return ast.literal_eval(result)
            except (ValueError, SyntaxError):
                pass
        
        return None


def create_agentic_hooks() -> AgenticActionHooks:
    """
    Create an AgenticActionHooks instance.
    
    The hooks use contextvars to get the event emitter, so make sure to
    set it before running the agent:
    
        from core.utils.context_utils import set_event_emitter
        token = set_event_emitter(my_callback)
        hooks = create_agentic_hooks()
        ...
    
    Returns:
        AgenticActionHooks instance
    """
    return AgenticActionHooks()
