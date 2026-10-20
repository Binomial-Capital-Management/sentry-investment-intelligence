"""
LangGraph Utility Functions
Status: Production
Created: August 2025

PURPOSE: Utility functions for LangGraph orchestrator.
Includes retry logic, checkpointer initialization, and cache helpers.
"""

import asyncio
import copy
import json
import re
import logging
import time
import uuid
from typing import Any, Optional, Dict, List, Tuple, Callable, Awaitable, Set
from collections import defaultdict

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    tiktoken = None

try:
    from litellm import BadRequestError  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    BadRequestError = None

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from core.config import config as app_config
from core.ai.utils.message_compactor import get_provider_from_model, _summarize_cross_provider
from core.ai.utils.sqlite_session_compactor import compact_sqlite_session_items
from core.ai.utils.context_manager import build_shared_context
from core.utils.context_utils import (
    get_cancel_event,
    get_token_sink,
    set_event_emitter,
    reset_event_emitter,
)
from core.ai.agentic_hooks import create_agentic_hooks
from agents import CodeInterpreterTool

logger = logging.getLogger(__name__)


# ============================================
# Container Management for Code Interpreter
# ============================================

def create_explicit_container(agent_name: str, message_id: str):
    """
    Create explicit container for Code Interpreter.

    Uses workbook_generator.py pattern: explicit container creation per execution
    instead of session-managed containers that can expire.

    Args:
        agent_name: Agent name (e.g., "QuantCoding", "OptionsCoding")
        message_id: Unique message ID for container naming

    Returns:
        Tuple of (container_id, container_object)
    """
    from openai import OpenAI
    import os

    # Check cancellation before expensive container creation
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CONTAINER] Skipping creation for {agent_name} - cancelled")
        raise asyncio.CancelledError(f"Container creation cancelled for {agent_name}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key, timeout=120.0)
    # Keep naming simple and tied to the chat message id to avoid reuse/expiry issues
    container_name = f"chat_{message_id[:12]}"

    logger.info(f"[CONTAINER] Creating: {container_name}")
    container = client.containers.create(name=container_name)
    logger.info(f"[CONTAINER] Created {container_name} → {container.id}")

    # Check cancellation after container creation (in case it was cancelled during)
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CONTAINER] Cleaning up {container_name} - cancelled after creation")
        try:
            client.containers.delete(container.id)
        except Exception:
            pass
        raise asyncio.CancelledError(f"Container creation cancelled for {agent_name}")

    return container.id, container


def cleanup_container(container_id: str, agent_name: str) -> None:
    """Clean up explicit container after execution (optional)."""
    from openai import OpenAI
    import os

    if not container_id:
        return

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return

        client = OpenAI(api_key=api_key, timeout=30.0)
        client.containers.delete(container_id)
        logger.info(f"[CONTAINER] Cleaned up {agent_name}: {container_id}")
    except Exception as e:
        logger.warning(f"[CONTAINER] Cleanup failed {agent_name} {container_id}: {e}")


def _provider_session_token_limit(selected_model: Optional[str]) -> int:
    """Return session token limit by provider/model identifier."""
    model = (selected_model or "").lower()
    if "anthropic" in model or "claude" in model:
        return 150_000
    if "gemini" in model or "google" in model:
        return 700_000
    if "deepseek" in model:
        return 75_000
    if "bedrock" in model or "llama4" in model:
        return 3_200_000
    if "xai" in model or "grok" in model:
        return 1_000_000
    if "dashscope" in model or "qwen" in model:
        return 1_000_000
    return 280_000


def _estimate_text_tokens(text: str, encoding) -> int:
    """Best-effort token estimator that overestimates when encoding unavailable."""
    if not text:
        return 0
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass
    # Fallback: 1 token ≈ 3 chars but round up to avoid underestimation
    return max(1, len(text) // 3)


async def trim_sqlite_session_history(
    session,
    selected_model: Optional[str],
    agent_name: str,
    *,
    force_llm_summary: bool = False,
) -> Optional[Dict[str, Any]]:
    """Trim SQLite session history to stay within provider token budgets."""
    if not session or not hasattr(session, "get_items"):
        return None

    limit = _provider_session_token_limit(selected_model)
    encoding = None
    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover - fallback to heuristic counting
            encoding = None

    try:
        session_items = await session.get_items()
    except Exception as exc:
        logger.error("[SQLITE TRIM ERROR] %s: failed to load session items: %s", agent_name, exc)
        return None

    if not session_items:
        return None

    session_items, removed_count = _sanitize_session_items(session_items)
    if removed_count:
        try:
            await session.clear_session()
            await session.add_items(session_items)
            logger.info(
                "[SQLITE TRIM] %s removed %s orphaned tool_result entries",
                agent_name,
                removed_count,
            )
        except Exception as exc:
            logger.error("[SQLITE TRIM ERROR] %s: failed to persist sanitized session: %s", agent_name, exc)

    def _item_tokens(item: Any) -> int:
        if isinstance(item, str):
            text = item
        else:
            try:
                text = json.dumps(item, default=str)
            except Exception:
                text = str(item)
        return _estimate_text_tokens(text, encoding)

    total_tokens = sum(_item_tokens(item) for item in session_items)
    logger.info(
        "[SQLITE DEBUG] %s session has %s tokens across %s items",
        agent_name,
        total_tokens,
        len(session_items),
    )

    if total_tokens <= limit:
        return {
            "did_trim": False,
            "original_items": len(session_items),
            "original_tokens": total_tokens,
            "limit": limit,
        }

    stream_sink = get_token_sink()
    if stream_sink is not None:
        try:
            await stream_sink.put({"type": "status", "message": "Compacting conversation history..."})
        except Exception:
            pass

    target_limit = max(limit // 2, 1024)
    trimmed_items, compaction_stats = compact_sqlite_session_items(
        session_items,
        encoding=encoding,
        target_tokens=target_limit,
    )
    current_tokens = compaction_stats.result_tokens

    # Optional: LLM summarize the dropped/older context and reinject as a single summary item.
    # Uses the same summarizer model/settings as cross-provider compaction.
    summary_enabled = force_llm_summary or getattr(app_config, "sqlite_session_compaction_summary_enabled", False)
    summary_model = str(getattr(app_config, "cross_provider_compaction_summary_model", "") or "").strip()
    if force_llm_summary and not summary_model:
        # When we're already in a context-window failure path, prefer a safe default summarizer.
        summary_model = "gpt-5-mini"

    if summary_enabled and summary_model and compaction_stats.older_items > 0:
        try:
            older_items = session_items[: compaction_stats.older_items]
            # Build a bounded source transcript for summarization (cap to avoid runaway prompts).
            source_tokens = min(
                int(getattr(app_config, "cross_provider_compaction_scan_tokens", 200000)),
                50_000,
            )
            summary_messages: List[Dict[str, Any]] = []

            def _extract_text(val: Any) -> str:
                if isinstance(val, str):
                    return val
                if isinstance(val, list):
                    chunks: List[str] = []
                    for block in val:
                        if isinstance(block, str):
                            chunks.append(block)
                            continue
                        if isinstance(block, dict):
                            text = block.get("text")
                            if isinstance(text, str) and text:
                                chunks.append(text)
                                continue
                            for key in ("input_text", "output_text"):
                                v = block.get(key)
                                if isinstance(v, str) and v:
                                    chunks.append(v)
                                    break
                            continue
                        chunks.append(str(block))
                    return "\n".join(chunks).strip()
                if val is None:
                    return ""
                return str(val)

            for it in older_items:
                if isinstance(it, dict) and it.get("role") in ("user", "assistant", "system"):
                    text = _extract_text(it.get("content"))
                    if text:
                        summary_messages.append({"role": it.get("role"), "content": text})
                    continue
                # Preserve non-chat tool history as text so the summary can retain key results.
                try:
                    tool_blob = json.dumps(it, default=str)
                except Exception:
                    tool_blob = str(it)
                if tool_blob:
                    summary_messages.append({"role": "system", "content": f"[TOOL HISTORY]\n{tool_blob}"})

            source_text = build_shared_context({"messages": summary_messages}, max_tokens=max(512, source_tokens)).strip()

            if source_text:
                if stream_sink is not None:
                    try:
                        await stream_sink.put({"type": "status", "message": "Summarizing conversation history..."})
                    except Exception:
                        pass

                summary = await _summarize_cross_provider(
                    source_text,
                    model=summary_model,
                    max_output_tokens=int(getattr(app_config, "cross_provider_compaction_summary_max_output_tokens", 2048)),
                    timeout_seconds=float(getattr(app_config, "cross_provider_compaction_summary_timeout_sec", 8.0)),
                )
                if summary:
                    summary_item = {
                        "role": "assistant",
                        "content": (
                            "=== Compacted Session Context (LLM Summary) ===\n"
                            "This summary compresses earlier conversation turns.\n\n"
                            f"{summary.strip()}"
                        ),
                        "type": "message",
                    }
                    trimmed_items = [summary_item, *trimmed_items]
                    current_tokens = sum(_item_tokens(item) for item in trimmed_items)
                else:
                    logger.warning(
                        "[SQLITE TRIM] %s: LLM session summary returned empty output (model=%s)",
                        agent_name,
                        summary_model,
                    )
        except Exception as exc:
            logger.warning("[SQLITE TRIM] %s: LLM session summary failed: %s", agent_name, exc)

    # Sanitize after trimming to remove orphans created by trimming
    trimmed_items, trim_orphans = _sanitize_session_items(trimmed_items)
    if trim_orphans:
        logger.warning(
            "[SQLITE TRIM] %s removed %s orphaned tool_results created by trimming",
            agent_name,
            trim_orphans,
        )
        # Recalculate tokens after removing orphans
        current_tokens = sum(_item_tokens(item) for item in trimmed_items)

    try:
        await session.clear_session()
        await session.add_items(trimmed_items)
        logger.info(
            "[SQLITE TRIM] %s trimmed session from %s to %s items (%s → %s tokens)",
            agent_name,
            len(session_items),
            len(trimmed_items),
            total_tokens,
            current_tokens,
        )
    except Exception as exc:
        logger.error("[SQLITE TRIM ERROR] %s: failed to trim session: %s", agent_name, exc)
        return None

    return {
        "did_trim": True,
        "original_items": compaction_stats.original_items,
        "original_tokens": compaction_stats.original_tokens,
        "target_tokens": compaction_stats.target_tokens,
        "summary_tokens": compaction_stats.summary_tokens,
        "recent_tokens": compaction_stats.recent_tokens,
        "result_items": compaction_stats.result_items,
        "result_tokens": current_tokens,
        "limit": limit,
    }


def _sanitize_session_items(items: List[Any]) -> Tuple[List[Any], int]:
    """Drop orphaned tool_result and function_call items missing their paired reasoning items.

    GPT-5 Pro reasoning models require that every function_call (fc_*) is preceded by its
    reasoning item (rs_*). When session trimming drops the reasoning item, the function_call
    and its output must also be removed to avoid 400 errors.
    """
    if not items:
        return items, 0

    sanitized: List[Any] = []
    pending_tool_ids: Set[str] = set()
    removed = 0

    def _mark_tool_use(tool_id: Optional[str]) -> None:
        if not tool_id:
            return
        pending_tool_ids.add(str(tool_id))

    def _maybe_keep_tool_result(tool_id: Optional[str]) -> bool:
        nonlocal removed
        if tool_id and str(tool_id) in pending_tool_ids:
            pending_tool_ids.remove(str(tool_id))
            return True
        removed += 1
        return False

    # First pass: collect all item ids present so we can check reasoning references
    present_ids: Set[str] = set()
    for item in items:
        if isinstance(item, dict):
            item_id = item.get("id") or ""
            if item_id:
                present_ids.add(str(item_id))

    for item in items:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue

        item_copy = copy.deepcopy(item)
        classification = None
        tool_id = item_copy.get("call_id") or item_copy.get("tool_use_id")

        if "output" in item_copy and tool_id:
            classification = "tool_result"
        elif any(key in item_copy for key in ("arguments", "input")) and tool_id:
            classification = "tool_use"
        elif item_copy.get("type") in ("tool_call", "function_call", "tool_use") and tool_id:
            classification = "tool_use"

        if classification == "tool_use":
            _mark_tool_use(tool_id)
            sanitized.append(item_copy)
            continue
        if classification == "tool_result":
            if _maybe_keep_tool_result(tool_id):
                if "output" in item_copy:
                    try:
                        output = item_copy["output"]
                        if isinstance(output, str):
                            output_obj = json.loads(output)
                        else:
                            output_obj = output

                        if isinstance(output_obj, dict) and "_full_charts" in output_obj:
                            output_obj.pop("_full_charts", None)
                            item_copy["output"] = json.dumps(output_obj) if isinstance(output, str) else output_obj
                    except Exception:
                        pass
                sanitized.append(item_copy)
            continue

        content = item_copy.get("content")
        if isinstance(content, list):
            filtered_blocks: List[Any] = []
            for block in content:
                if not isinstance(block, dict):
                    filtered_blocks.append(block)
                    continue

                block_type = block.get("type")
                block_id = block.get("id") or block.get("tool_use_id")
                if block_type == "tool_use":
                    _mark_tool_use(block_id)
                    filtered_blocks.append(block)
                    continue

                if block_type == "tool_result":
                    if _maybe_keep_tool_result(block.get("tool_use_id")):
                        filtered_blocks.append(block)
                    continue

                filtered_blocks.append(block)

            if len(filtered_blocks) != len(content):
                item_copy["content"] = filtered_blocks
            sanitized.append(item_copy)
            continue

        sanitized.append(item_copy)

    # Second pass: drop function_call items whose required reasoning item was trimmed away.
    # GPT-5 Pro requires every function_call (fc_*) be preceded by its reasoning (rs_*) item.
    # Items may be dicts or Pydantic-like objects; extract type/id defensively.
    def _get_item_attr(obj: Any, key: str) -> str:
        if isinstance(obj, dict):
            return str(obj.get(key, ""))
        return str(getattr(obj, key, ""))

    reasoning_ids: Set[str] = set()
    fc_items_indices: List[int] = []
    for idx, item in enumerate(sanitized):
        itype = _get_item_attr(item, "type")
        iid = _get_item_attr(item, "id")
        if itype == "reasoning" and iid:
            reasoning_ids.add(iid)
        elif itype == "function_call" and iid.startswith("fc_"):
            fc_items_indices.append(idx)

    if fc_items_indices:
        logger.debug(
            "[SANITIZE] Session has %d reasoning items, %d function_call items",
            len(reasoning_ids),
            len(fc_items_indices),
        )

    orphaned_fc_ids: Set[str] = set()
    if fc_items_indices and not reasoning_ids:
        # No reasoning items at all — every fc_ is orphaned (trimming dropped all reasoning)
        for idx in fc_items_indices:
            fc_id = _get_item_attr(sanitized[idx], "id")
            orphaned_fc_ids.add(fc_id)

    final: List[Any] = []
    for item in sanitized:
        itype = _get_item_attr(item, "type")
        iid = _get_item_attr(item, "id")
        if itype == "function_call" and iid in orphaned_fc_ids:
            removed += 1
            continue
        if itype == "function_call_output":
            fc_ref = _get_item_attr(item, "call_id")
            if fc_ref in orphaned_fc_ids:
                removed += 1
                continue
        final.append(item)

    if orphaned_fc_ids:
        logger.info(
            "[SANITIZE] Dropped %d function_call items (+ outputs) missing reasoning items: %s",
            len(orphaned_fc_ids),
            list(orphaned_fc_ids)[:3],
        )

    return final, removed


def _is_tool_history_mismatch(exc: Exception) -> bool:
    """Detect Anthropic/LiteLLM complaints about orphaned tool_use/tool_result pairs."""
    if BadRequestError is not None and isinstance(exc, BadRequestError):
        message = getattr(exc, "message", "") or getattr(exc, "body", "") or str(exc)
    else:
        message = str(exc)

    lowered = message.lower()
    if not lowered:
        return False
    if "tool_result" not in lowered or "tool_use" not in lowered:
        return False
    mismatch_markers = (
        "unexpected tool_use_id",
        "must have a corresponding tool_use block",
        "missing tool_use block",
    )
    return any(marker in lowered for marker in mismatch_markers)


async def _repair_session_history(
    session,
    selected_model: Optional[str],
    agent_name: str,
    *,
    allow_clear: bool = True,
) -> bool:
    """
    Attempt to repair the persisted session by trimming orphaned tool results.
    Falls back to clearing the session entirely when trimming fails.
    """
    if session is None:
        return False

    try:
        await trim_sqlite_session_history(session, selected_model, agent_name)
        logger.warning(
            "[SESSION REPAIR] %s trimmed session after tool mismatch (model=%s)",
            agent_name,
            selected_model,
        )
        return True
    except Exception as exc:
        logger.error(
            "[SESSION REPAIR ERROR] %s failed to trim session: %s",
            agent_name,
            exc,
        )

    if allow_clear and hasattr(session, "clear_session"):
        try:
            await session.clear_session()
            logger.warning(
                "[SESSION REPAIR] %s cleared session history due to tool mismatch (model=%s)",
                agent_name,
                selected_model,
            )
            return True
        except Exception as exc:
            logger.error(
                "[SESSION REPAIR ERROR] %s failed to clear session: %s",
                agent_name,
                exc,
            )

    return False


def _extract_retry_delay_seconds(exc: Exception, attempt: int) -> Tuple[float, str]:
    """
    Extract a provider-suggested retry delay from an exception, falling back to a
    conservative exponential backoff.
    """
    fallback_schedule = [15.0, 30.0, 60.0, 120.0]
    fallback = fallback_schedule[min(attempt, len(fallback_schedule) - 1)]

    # Common attributes surfaced by HTTP clients / LiteLLM
    attr_candidates = [
        getattr(exc, "retry_after", None),
        getattr(exc, "wait_time", None),
        getattr(exc, "retry_in", None),
    ]
    for value in attr_candidates:
        if value is None:
            continue
        parsed = _parse_delay_value(value)
        if parsed is not None:
            return parsed, "exception attribute"

    # Headers dictionary (some LiteLLM errors expose response headers)
    headers = getattr(exc, "response_headers", None) or getattr(exc, "headers", None)
    if isinstance(headers, dict):
        for key in ("retry-after", "Retry-After"):
            if key in headers:
                parsed = _parse_delay_value(headers[key])
                if parsed is not None:
                    return parsed, "retry-after header"

    # Look for hints in the error message / body
    message = str(exc) or ""
    match = re.search(r"retry (?:in|after)\s+([0-9]+(?:\.[0-9]+)?)\s*s", message, re.IGNORECASE)
    if match:
        value = match.group(1)
        parsed = _parse_delay_value(value)
        if parsed is not None:
            return parsed, "message retry hint"

    match = re.search(r"\"retryDelay\"\s*:\s*\"?([0-9]+(?:\.[0-9]+)?)[s]?\"?", message)
    if match:
        parsed = _parse_delay_value(match.group(1))
        if parsed is not None:
            return parsed, "retryDelay field"

    return fallback, "fallback backoff"


def _parse_delay_value(value: Any) -> Optional[float]:
    """Best-effort parsing of retry delay values into seconds."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return max(float(value), 0.0)
        text = str(value).strip()
        if not text:
            return None
        # Handle suffix like "11s" or "11.5 seconds"
        match = re.match(r"([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            return max(float(match.group(1)), 0.0)
    except Exception:  # pragma: no cover - best effort parsing
        return None
    return None


def _is_missing_reasoning_error(exc: Exception) -> bool:
    """Detect GPT-5 Pro errors where a function_call's paired reasoning item was dropped."""
    msg = str(exc)
    return "function_call" in msg and "without its required" in msg and "reasoning" in msg


def _is_missing_reference_error(exc: Exception) -> bool:
    """
    Detect OpenAI session reference errors where a prior response/run item
    referenced in the stored session is no longer available on the API side.
    These present as 404 errors with messages like:
      "Item with id 'rs_...' not found."
    """
    message = str(exc)
    if not message:
        return False
    if "Item with id" in message and "not found" in message:
        return True
    if _is_missing_reasoning_error(exc):
        return True
    # Some clients attach status_code attributes for HTTP errors
    status_from_response = getattr(getattr(exc, "response", None), "status_code", None)
    status = status_from_response or getattr(exc, "status_code", None)
    return status == 404 and "not found" in message.lower()


def _is_missing_container_error(exc: Exception) -> bool:
    """
    Detect when Code Interpreter containers referenced in the session have
    expired or been deleted on the OpenAI side.
    Typical messages include:
    - "Container ... not found"
    - "Container is expired"
    - "Container not available"
    - "Workspace ... expired"
    """
    message = str(exc)
    if not message:
        return False
    lowered = message.lower()

    # Check for container-related errors (not found OR expired OR not available)
    if "container" in lowered:
        if "not found" in lowered or "expired" in lowered or "not available" in lowered:
            return True

    # Check for workspace-related errors
    if "workspace" in lowered and ("expired" in lowered or "not available" in lowered):
        return True

    # Check for 404 status with container mention
    status_from_response = getattr(getattr(exc, "response", None), "status_code", None)
    status = status_from_response or getattr(exc, "status_code", None)
    if status == 404 and "container" in lowered:
        return True

    return False


def _is_context_window_error(exc: Exception) -> bool:
    """
    Detect context-window / prompt-too-long errors across providers.
    These are non-retryable because the payload will not change without trimming.
    """
    raw = ""
    try:
        raw = getattr(exc, "message", "") or getattr(exc, "body", "") or str(exc) or ""
    except Exception:
        raw = str(exc) or ""

    message = raw.lower()
    if not message:
        return False

    indicators = (
        "prompt is too long",
        "context window",
        "context_length_exceeded",
        "contextwindowexceeded",
        "maximum context length",
        "token limit",
        "too many tokens",
        "tokens >",
    )
    return any(indicator in message for indicator in indicators)


def _categorize_error(exc: Exception) -> tuple[str, bool, str]:
    """
    Categorize errors for intelligent retry behavior.

    Returns:
        (category, should_retry, user_message)

    Categories:
    - "validation": Parameter/input errors (don't retry)
    - "rate_limit": API rate limiting (retry with longer delay)
    - "network": Network/connection errors (retry with backoff)
    - "tool_error": Tool execution failures (retry, may need circuit breaker)
    - "max_turns": Agent exceeded turn limit (don't retry)
    - "unknown": Unclassified errors (retry conservatively)
    """
    raw_message = str(exc) or ""
    message = raw_message.lower()
    error_type = type(exc).__name__

    # Context window exceeded - fail fast, no retry (payload won't shrink on retry)
    compact_message = message.replace("_", "").replace(" ", "")
    context_window_indicators = [
        "prompt is too long",
        "context window",
        "context length exceeded",
        "context_length_exceeded",
        "contextwindowexceeded",
        "maximum context length",
        "maximum context",
        "token limit",
        "too many tokens",
        "tokens >",
        "maximum tokens",
        "input is too long",
    ]
    # Context window exceeded - fail fast (retrying won't change payload size)
    if any(indicator in message for indicator in context_window_indicators) or "contextwindowexceeded" in compact_message:
        return (
            "context_window",
            False,
            "Conversation context is too long for this model. Please start a new session or clear chat history.",
        )

    # Validation errors - fail fast, no retry
    validation_indicators = [
        "invalid parameter", "missing required", "validation error",
        "invalid input", "parameter validation", "schema validation",
        "invalid schema for function", "invalid schema",
        "invalid_function_parameters",
        "either 'fields' or 'dataset", # FMP specific validation
    ]
    if any(indicator in message for indicator in validation_indicators):
        return (
            "validation",
            False,
            f"Invalid request parameters or tool configuration. ({error_type})"
        )

    # Max turns exceeded - fail fast
    if "max turns" in message and "exceeded" in message:
        return (
            "max_turns",
            False,
            "Agent reached maximum conversation turns. Please start a new session or simplify your request."
        )

    # Rate limiting - retry with longer delay
    rate_limit_indicators = ["rate limit", "429", "too many requests", "quota exceeded"]
    if any(indicator in message for indicator in rate_limit_indicators):
        return (
            "rate_limit",
            True,
            "API rate limit reached. Retrying with exponential backoff..."
        )

    # Network/connection errors - retry with backoff
    network_indicators = [
        "connection", "timeout", "network", "503", "502", "504",
        "service unavailable", "gateway", "dns"
    ]
    if any(indicator in message for indicator in network_indicators):
        return (
            "network",
            True,
            "Network connection issue detected. Retrying..."
        )

    # Tool execution errors - retry, but may need circuit breaker
    tool_indicators = [
        "tool execution", "tool failed", "tool error",
        "error in get_fields", "error in discover", # FMP specific
        "mcp", "function call"
    ]
    if any(indicator in message for indicator in tool_indicators):
        return (
            "tool_error",
            True,
            "Tool execution encountered an error. Attempting recovery..."
        )

    # Unknown errors - retry conservatively
    return (
        "unknown",
        True,
        f"Unexpected error occurred ({error_type}). Retrying..."
    )


 

async def initialize_async_checkpointer(db_path: str):
    """
    Properly initialize AsyncSqliteSaver in async context.
    Must be called from within an async function.
    
    Returns context manager for use with async with.
    """
    return AsyncSqliteSaver.from_conn_string(db_path)


async def execute_with_retry(
    agent,
    query,
    session,
    max_turns=None,
    agent_name="agent",
    selected_model=None,
):
    """
    Centralized retry logic for agent execution with exponential backoff.

    Enhanced with:
    - Error categorization (validation, network, rate limit, tool errors)
    - Graceful degradation (partial results when possible)
    - Better error messages for user-facing context
    - Foundation for circuit breaker pattern
    - Cancellation support via context variable (get_cancel_event)

    Args:
        agent: The agent to execute
        query: The query to process
        session: SQLite session for persistence
        max_turns: Maximum turns for the agent (optional)
        agent_name: Name for logging purposes
        selected_model: Optional model to override agent's default model

    Returns:
        Result from Runner.run or gracefully degraded partial result

    Raises:
        Exception: Only for unrecoverable errors (validation, max_turns)
    """
    from agents import Runner, RunConfig

    # Get cancellation event from context (non-serializable, can't be in LangGraph state)
    cancel_event = get_cancel_event()
    agent_timeout = getattr(app_config, "agent_node_timeout_seconds", 1200)  # default 20 minutes to match streaming cap

    max_retries = 3  # Reduced from 5 for faster failures
    last_error = None
    session_reset_performed = False
    tool_mismatch_repaired = False
    partial_result = None  # Track partial results for graceful degradation
    context_compaction_performed = False

    # Preflight: trim persisted session history once per call (this is what Runner.run() actually prepends)
    try:
        await trim_sqlite_session_history(session, selected_model, agent_name)
    except Exception as exc:
        logger.warning("[SQLITE TRIM] %s preflight trim failed: %s", agent_name, exc)

    for attempt in range(max_retries):
        # ✅ CHECK CANCELLATION: Stop retry loop if cancelled
        if cancel_event and cancel_event.is_set():
            logger.info(f"[CANCEL] {agent_name} retry loop cancelled before attempt {attempt + 1}")
            raise asyncio.CancelledError(f"{agent_name} cancelled by user")

        _attempt_start = time.time()
        try:
            # Build kwargs dynamically
            kwargs = {"session": session}
            if max_turns is not None:
                kwargs["max_turns"] = max_turns

            # Preserve original tools so we can restore after patching containers/overrides
            orig_tools = agent.tools[:] if hasattr(agent, "tools") and agent.tools else None
            container_id = None

            # Create explicit container per run for code_interpreter tools
            try:
                import uuid as _uuid
                message_id = getattr(kwargs.get("run_config"), "message_id", None) or _uuid.uuid4().hex
                if hasattr(agent, "tools") and any(isinstance(t, CodeInterpreterTool) for t in agent.tools):
                    container_id, _ = create_explicit_container(agent_name, message_id)
                    # Swap CodeInterpreterTool to use explicit container
                    patched_tools = []
                    for tool in agent.tools:
                        if isinstance(tool, CodeInterpreterTool):
                            patched_tools.append(
                                CodeInterpreterTool(
                                    tool_config={
                                        "type": "code_interpreter",
                                        "container": container_id,
                                    }
                                )
                            )
                        else:
                            patched_tools.append(tool)
                    agent.tools = patched_tools
            except Exception as e:
                logger.debug(f"[CONTAINER] Skipping explicit container setup: {e}")

            # For Anthropic/Gemini/xAI/DeepSeek/Bedrock: temporarily replace agent's model_settings to completely remove reasoning
            # AND remove Code Interpreter tool if present (not supported natively)
            # For GPT-5 Pro: remove Code Interpreter but keep reasoning with effort="high"
            orig_ms = None
            provider = get_provider_from_model(selected_model) if selected_model else "openai"
            is_anthropic = provider == "anthropic"
            is_gemini = provider == "gemini"
            is_xai = provider == "xai"
            is_deepseek = provider == "deepseek"
            is_bedrock = provider == "bedrock"
            is_moonshot = provider == "moonshot"
            is_qwen = provider == "qwen"
            is_zai = provider == "zai"
            is_gpt5_pro = selected_model and "gpt-5.4-pro" in selected_model.lower()
            needs_override = is_anthropic or is_gemini or is_xai or is_deepseek or is_bedrock or is_moonshot or is_qwen or is_zai
            needs_code_interpreter_removal = needs_override or is_gpt5_pro

            if selected_model and selected_model not in [
                'perplexity-sonar',
                'perplexity-sonar-pro',
            ]:
                # GPT-5 Pro special handling: remove code interpreter, set reasoning to high
                if is_gpt5_pro:
                    from agents import ModelSettings
                    from openai.types.shared import Reasoning
                    # Snapshot original settings
                    orig_ms = getattr(agent, "model_settings", None)

                    # Keep existing settings but override reasoning to high
                    parallel_tool_calls = getattr(orig_ms, "parallel_tool_calls", True) if orig_ms else True
                    tool_choice = getattr(orig_ms, "tool_choice", "auto") if orig_ms else "auto"
                    max_tokens = getattr(orig_ms, "max_tokens", 15000) if orig_ms else 15000

                    forced_ms = ModelSettings(
                        tool_choice=tool_choice,
                        parallel_tool_calls=parallel_tool_calls,
                        max_tokens=max_tokens,
                        reasoning=Reasoning(effort="high", summary="detailed"),
                        include_usage=True,
                    )

                    # Temporarily replace agent's model_settings
                    agent.model_settings = forced_ms

                    # Remove Code Interpreter tool for GPT-5 Pro
                    if hasattr(agent, 'tools') and agent.tools:
                        filtered_tools = []
                        for tool in agent.tools:
                            tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                            if 'code_interpreter' in str(tool_name).lower():
                                logger.info(
                                    f"Removing Code Interpreter tool for GPT-5 Pro model in {agent_name}"
                                )
                            else:
                                filtered_tools.append(tool)
                        agent.tools = filtered_tools

                    kwargs["run_config"] = RunConfig(model=selected_model)
                    logger.debug(
                        f"Overriding agent model to {selected_model} (GPT-5 Pro): "
                        "removed Code Interpreter, reasoning set to high"
                    )
                elif needs_override:
                    from agents import ModelSettings
                    # Snapshot original settings
                    orig_ms = getattr(agent, "model_settings", None)

                    # Create new settings WITHOUT reasoning field at all
                    parallel_tool_calls = (
                        getattr(orig_ms, "parallel_tool_calls", None)
                        if orig_ms and provider not in {"xai", "deepseek", "bedrock", "moonshot", "qwen", "zai"}
                        else None
                    )
                    tool_choice = (
                        "auto"  # prevent "forced tools" conflicts
                        if provider not in {"bedrock"}
                        else None
                    )
                    max_tokens = getattr(orig_ms, "max_tokens", None) if orig_ms else None
                    if provider == "deepseek" and (max_tokens is None or max_tokens > 8192):
                        max_tokens = 8192
                    if provider == "bedrock" and (max_tokens is None or max_tokens > 8192):
                        max_tokens = 8192
                    if provider == "moonshot" and (max_tokens is None or max_tokens > 16384):
                        max_tokens = 16384
                    if provider == "qwen" and (max_tokens is None or max_tokens > 16384):
                        max_tokens = 16384
                    if provider == "zai" and (max_tokens is None or max_tokens > 15000):
                        max_tokens = 15000

                    extra_body = {}
                    if provider in {"moonshot", "qwen"}:
                        extra_body["thinking"] = {"type": "disabled"}
                    # NOTE: Anthropic adaptive thinking disabled — causes re-planning on every tool call.
                    # if is_anthropic:
                    #     extra_body["thinking"] = {"type": "adaptive"}

                    forced_ms = ModelSettings(
                        tool_choice=tool_choice,
                        parallel_tool_calls=parallel_tool_calls,
                        max_tokens=max_tokens,
                        extra_body=extra_body or None,
                        include_usage=True,
                    )

                    # Temporarily replace agent's model_settings
                    agent.model_settings = forced_ms

                    # Remove Code Interpreter tool if present (Claude/Gemini/Grok don't support it)
                    # For Bedrock, remove ALL tools to prevent looping issues
                    if hasattr(agent, 'tools') and agent.tools:
                        if provider == "bedrock":
                            # TEMPORARY: Disable all tools for Bedrock to prevent API call loops
                            logger.warning(
                                f"⚠️ Removing ALL tools for Bedrock model in {agent_name} (tool calling compatibility issue)"
                            )
                            agent.tools = []
                        else:
                            filtered_tools = []
                            for tool in agent.tools:
                                tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                                if 'code_interpreter' in str(tool_name).lower():
                                    logger.info(
                                        f"Removing Code Interpreter tool for {provider} model in {agent_name}"
                                    )
                                else:
                                    filtered_tools.append(tool)
                            agent.tools = filtered_tools

                    # DEBUG: Check for duplicate tool names
                    tool_names_list = []
                    for tool in agent.tools:
                        tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                        tool_names_list.append(tool_name)

                    # Find duplicates
                    from collections import Counter
                    name_counts = Counter(tool_names_list)
                    duplicates = [name for name, count in name_counts.items() if count > 1]

                    if duplicates:
                        logger.error(f"[DUPLICATE TOOLS] Agent {agent_name} has duplicate tool names: {duplicates}")
                        logger.error(f"[DUPLICATE TOOLS] All tool names: {tool_names_list}")

                    # Pass model in RunConfig but no model_settings (to avoid merge issues)
                    # IMPORTANT: Disable tracing for non-OpenAI providers to prevent __fake_id__ errors
                    kwargs["run_config"] = RunConfig(model=selected_model, tracing_disabled=True)
                    logger.debug(
                        f"Overriding agent model to {selected_model} ({provider}): "
                        "temporarily replaced model_settings, reasoning field omitted, tracing disabled"
                    )
                else:
                    kwargs["run_config"] = RunConfig(model=selected_model)
                    logger.debug(f"Overriding agent model to: {selected_model}")

            # DEBUG: Log what tools are being sent (debug level to avoid noisy prod logs)
            import json
            logger.debug(f"[DEBUG TOKEN CHECK] Agent {agent_name} has {len(agent.tools)} tools")
            tool_names = []
            total_docstring_length = 0
            for tool in agent.tools:
                if hasattr(tool, 'name'):
                    tool_names.append(tool.name)
                elif hasattr(tool, '__name__'):
                    tool_names.append(tool.__name__)
                else:
                    tool_names.append(str(tool))
                # Count docstring length
                if hasattr(tool, '__doc__'):
                    total_docstring_length += len(tool.__doc__ or '')
            logger.debug(f"[DEBUG TOKEN CHECK] Tool names: {tool_names}")
            logger.debug(f"[DEBUG TOKEN CHECK] Total docstring chars: {total_docstring_length}")
            
            try:
                # Execute the agent
                result = await asyncio.wait_for(
                    Runner.run(agent, query, **kwargs),
                    timeout=agent_timeout,
                )

                # ✅ CHECK CANCELLATION: Stop immediately after LLM call if cancelled
                # This is important because LLM calls (especially via LiteLLM for non-OpenAI models)
                # are blocking HTTP requests that cannot be interrupted mid-flight
                if cancel_event and cancel_event.is_set():
                    logger.info(f"[CANCEL] {agent_name} cancelled after LLM call completed")
                    raise asyncio.CancelledError(f"{agent_name} cancelled by user after LLM call")

                # Validate we got a result
                if result:
                    if app_config.enable_cost_tracking:
                        try:
                            from core.ai.cost_tracker import cost_tracker
                            _sid = getattr(session, 'session_id', None) or str(id(session))
                            cost_tracker.record_from_result(
                                result, agent_name, selected_model, _sid,
                                elapsed_s=time.time() - _attempt_start,
                            )
                        except Exception:
                            pass
                    return result
            finally:
                # Restore original model_settings and tools if we replaced them for Anthropic
                if needs_override:
                    if orig_ms is not None:
                        agent.model_settings = orig_ms
                        logger.debug(f"Restored original model_settings for {agent_name}")
                    if orig_tools is not None:
                        agent.tools = orig_tools
                        logger.debug(f"Restored original tools for {agent_name}")
                # Always restore tools if we patched
                # NOTE: Container cleanup moved to langgraph_nodes.py AFTER file extraction
                # This prevents empty generated_files due to premature container deletion
                try:
                    if orig_tools is not None:
                        agent.tools = orig_tools
                except Exception:
                    pass
                
        except Exception as e:
            # Attempt to repair session history when LiteLLM rejects orphaned tool results
            if _is_tool_history_mismatch(e):
                repaired = await _repair_session_history(
                    session,
                    selected_model,
                    agent_name,
                )
                if repaired:
                    logger.warning(
                        "%s repaired session after tool mismatch, retrying attempt %s/%s",
                        agent_name,
                        attempt + 1,
                        max_retries,
                    )
                    last_error = e
                    continue

            # Categorize error to determine retry behavior
            error_category, should_retry, user_message = _categorize_error(e)

            # Log error with category
            logger.warning(
                f"{agent_name} attempt {attempt + 1}/{max_retries} failed "
                f"[category={error_category}]: {e}"
            )
            last_error = e

            # Context-window exceeded: attempt a one-time compaction (prefer AI summary) and retry immediately.
            # This catches mid-run blowups caused by large tool outputs persisting into the SDK SQLite session.
            if error_category == "context_window" and not context_compaction_performed and attempt < max_retries - 1:
                context_compaction_performed = True
                try:
                    logger.warning(
                        "[CONTEXT WINDOW] %s: attempting session compaction + retry",
                        agent_name,
                    )
                    await trim_sqlite_session_history(
                        session,
                        selected_model,
                        agent_name,
                        force_llm_summary=True,
                    )
                except Exception as compaction_exc:
                    logger.warning(
                        "[CONTEXT WINDOW] %s: session compaction failed: %s",
                        agent_name,
                        compaction_exc,
                    )
                continue

            # Fail fast for non-retryable errors (validation, max_turns)
            if not should_retry:
                logger.error(
                    f"{agent_name} encountered non-retryable error "
                    f"[category={error_category}]: {user_message}"
                )
                # Create a user-friendly exception
                raise ValueError(user_message) from e

            # If remote session references are stale, clear local session once and retry immediately
            reset_reason = None
            if _is_missing_reference_error(e):
                reset_reason = "missing reference error"
            elif _is_missing_container_error(e):
                reset_reason = "missing container error"

            should_reset = (
                not session_reset_performed
                and hasattr(session, "clear_session")
                and reset_reason is not None
            )
            if should_reset:
                try:
                    logger.warning(
                        f"{agent_name}: clearing persisted session after {reset_reason}"
                    )
                    await session.clear_session()
                    session_reset_performed = True
                    continue
                except Exception as reset_error:
                    logger.error(
                        f"{agent_name}: failed to clear session after {reset_reason}: "
                        f"{reset_error}"
                    )

            # Last attempt - try graceful degradation
            if attempt >= max_retries - 1:
                logger.error(
                    f"All {agent_name} retry attempts failed "
                    f"[category={error_category}]. Attempting graceful degradation."
                )

                # Return partial result if we have one
                if partial_result is not None:
                    logger.warning(
                        f"{agent_name} returning partial result after {max_retries} failures"
                    )
                    return partial_result

                # No partial result - provide helpful error message
                user_friendly_error = (
                    f"Agent execution failed after {max_retries} attempts. "
                    f"Error: {user_message}\n\n"
                    f"Please try:\n"
                    f"1. Simplifying your request\n"
                    f"2. Starting a new session\n"
                    f"3. Checking if services are available\n"
                    f"4. Contacting support if the issue persists"
                )
                raise RuntimeError(user_friendly_error) from e

            # Retry with appropriate delay based on error category
            if error_category == "rate_limit":
                # Longer delay for rate limits
                delay_seconds = min(60.0 * (2 ** attempt), 300.0)  # Up to 5 minutes
                delay_source = "rate limit backoff"
            elif error_category == "network":
                # Standard exponential backoff for network errors
                delay_seconds, delay_source = _extract_retry_delay_seconds(e, attempt)
                delay_seconds = min(max(delay_seconds, 0.0), 120.0)
            else:
                # Conservative delay for tool and unknown errors
                delay_seconds, delay_source = _extract_retry_delay_seconds(e, attempt)
                delay_seconds = min(max(delay_seconds, 5.0), 60.0)  # At least 5s, max 60s

            logger.warning(
                "%s retry %s/%s after %.2fs (%s) [category=%s]",
                agent_name,
                attempt + 1,
                max_retries,
                delay_seconds,
                delay_source,
                error_category,
            )

            # ✅ CHECK CANCELLATION: Stop before retry delay
            if cancel_event and cancel_event.is_set():
                logger.info(f"[CANCEL] {agent_name} cancelled before retry delay")
                raise asyncio.CancelledError(f"{agent_name} cancelled by user")

            await asyncio.sleep(delay_seconds)
    
    # Should never reach here, but for safety
    raise last_error if last_error else Exception(f"{agent_name} failed without error")


def _extract_tool_arguments(item: Any) -> Optional[Dict[str, Any]]:
    """Extract tool arguments/parameters from an Agents SDK stream item."""
    for attr in ("arguments", "args"):
        val = getattr(item, attr, None)
        if val:
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif isinstance(val, dict):
                return val

    raw_item = getattr(item, "raw_item", None)
    if raw_item:
        for attr in ("arguments", "args"):
            val = getattr(raw_item, attr, None)
            if val:
                if isinstance(val, str):
                    try:
                        return json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        pass
                elif isinstance(val, dict):
                    return val
        fn = getattr(raw_item, "function", None)
        if fn:
            args = fn.get("arguments") if isinstance(fn, dict) else getattr(fn, "arguments", None)
            if args:
                if isinstance(args, str):
                    try:
                        return json.loads(args)
                    except (json.JSONDecodeError, ValueError):
                        pass
                elif isinstance(args, dict):
                    return args

    return None


async def execute_with_stream(
    agent,
    query,
    session,
    on_token,
    on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    max_turns=None,
    agent_name: str = "agent",
    selected_model: Optional[str] = None,
):
    """
    Streaming executor for Agents SDK.

    Uses Runner.run_streamed() and forwards ResponseTextDeltaEvent deltas to on_token.
    Aggregates higher-level run items (tools, outputs) so callers can parse sources/charts
    exactly like they do with the non-streaming path.

    Cancellation is handled via context variable (get_cancel_event from context_utils).
    """
    from agents import Runner, RunConfig

    # Get cancellation event from context (non-serializable, can't be in LangGraph state)
    cancel_event = get_cancel_event()

    # Preflight: trim persisted session history once per call (this is what Runner.run_streamed() actually prepends)
    try:
        await trim_sqlite_session_history(session, selected_model, agent_name)
    except Exception as exc:
        logger.warning("[SQLITE TRIM] %s preflight trim failed (stream): %s", agent_name, exc)

    try:
        from openai.types.responses import ResponseTextDeltaEvent  # type: ignore
        from openai.types.responses import ResponseReasoningSummaryTextDeltaEvent  # type: ignore
        from openai.types.responses import ResponseReasoningSummaryPartAddedEvent  # type: ignore
    except Exception:
        ResponseTextDeltaEvent = None  # best-effort typing
        ResponseReasoningSummaryTextDeltaEvent = None
        ResponseReasoningSummaryPartAddedEvent = None

    kwargs = {"session": session}
    if max_turns is not None:
        kwargs["max_turns"] = max_turns

    # Preserve original tools and set up explicit containers for Code Interpreter
    stream_orig_tools = agent.tools[:] if hasattr(agent, "tools") and agent.tools else None
    stream_container_id = None

    # For Anthropic/Gemini/xAI/DeepSeek/Bedrock: temporarily replace agent's model_settings to completely remove reasoning
    # AND remove Code Interpreter tool if present
    # For GPT-5 Pro: remove Code Interpreter but keep reasoning with effort="high"
    orig_ms = None
    provider = get_provider_from_model(selected_model) if selected_model else "openai"
    is_anthropic = provider == "anthropic"
    is_gemini = provider == "gemini"
    is_xai = provider == "xai"
    is_deepseek = provider == "deepseek"
    is_bedrock = provider == "bedrock"
    is_moonshot = provider == "moonshot"
    is_qwen = provider == "qwen"
    is_zai = provider == "zai"
    is_gpt5_pro = selected_model and "gpt-5.4-pro" in selected_model.lower()
    needs_override = is_anthropic or is_gemini or is_xai or is_deepseek or is_bedrock or is_moonshot or is_qwen or is_zai

    if selected_model and selected_model not in [
        'perplexity-sonar',
        'perplexity-sonar-pro',
    ]:
        # GPT-5 Pro special handling: remove code interpreter, set reasoning to high
        if is_gpt5_pro:
            from agents import ModelSettings
            from openai.types.shared import Reasoning
            # Snapshot original settings
            orig_ms = getattr(agent, "model_settings", None)

            # Keep existing settings but override reasoning to high
            parallel_tool_calls = getattr(orig_ms, "parallel_tool_calls", True) if orig_ms else True
            tool_choice = getattr(orig_ms, "tool_choice", "auto") if orig_ms else "auto"
            max_tokens = getattr(orig_ms, "max_tokens", 15000) if orig_ms else 15000

            forced_ms = ModelSettings(
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                max_tokens=max_tokens,
                reasoning=Reasoning(effort="high", summary="detailed"),
                include_usage=True,
            )

            # Temporarily replace agent's model_settings
            agent.model_settings = forced_ms

            # Remove Code Interpreter tool for GPT-5 Pro
            if hasattr(agent, 'tools') and agent.tools:
                filtered_tools = []
                for tool in agent.tools:
                    tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                    if 'code_interpreter' in str(tool_name).lower():
                        logger.info(f"Removing Code Interpreter tool for GPT-5 Pro model in {agent_name}")
                    else:
                        filtered_tools.append(tool)
                agent.tools = filtered_tools

            kwargs["run_config"] = RunConfig(model=selected_model)
            logger.debug(
                f"Overriding agent model to {selected_model} (GPT-5 Pro stream): "
                "removed Code Interpreter, reasoning set to high"
            )
        elif needs_override:
            from agents import ModelSettings
            # Snapshot original settings
            orig_ms = getattr(agent, "model_settings", None)

            # Create new settings WITHOUT reasoning field at all
            parallel_tool_calls = (
                getattr(orig_ms, "parallel_tool_calls", None)
                if orig_ms and provider not in {"xai", "deepseek", "bedrock", "moonshot", "qwen", "zai"}
                else None
            )
            tool_choice = (
                "auto"  # prevent "forced tools" conflicts
                if provider not in {"bedrock"}
                else None
            )
            max_tokens = getattr(orig_ms, "max_tokens", None) if orig_ms else None
            if provider == "deepseek" and (max_tokens is None or max_tokens > 8192):
                max_tokens = 8192
            if provider == "bedrock" and (max_tokens is None or max_tokens > 8192):
                max_tokens = 8192
            if provider == "moonshot" and (max_tokens is None or max_tokens > 16384):
                max_tokens = 16384
            if provider == "qwen" and (max_tokens is None or max_tokens > 16384):
                max_tokens = 16384
            if provider == "zai" and (max_tokens is None or max_tokens > 15000):
                max_tokens = 15000

            extra_body = {}
            if provider in {"moonshot", "qwen"}:
                extra_body["thinking"] = {"type": "disabled"}
            # NOTE: Anthropic adaptive thinking disabled — causes re-planning on every tool call.
            # if is_anthropic:
            #     extra_body["thinking"] = {"type": "adaptive"}

            forced_ms = ModelSettings(
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                max_tokens=max_tokens,
                extra_body=extra_body or None,
                include_usage=True,
            )

            # Temporarily replace agent's model_settings
            agent.model_settings = forced_ms

            # Remove Code Interpreter tool if present (Claude/Gemini/Grok don't support it)
            # For Bedrock, remove ALL tools to prevent looping issues
            if hasattr(agent, 'tools') and agent.tools:
                if provider == "bedrock":
                    # TEMPORARY: Disable all tools for Bedrock to prevent API call loops
                    logger.warning(
                        f"⚠️ Removing ALL tools for Bedrock model in {agent_name} (tool calling compatibility issue)"
                    )
                    agent.tools = []
                else:
                    filtered_tools = []
                    for tool in agent.tools:
                        tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                        if 'code_interpreter' in str(tool_name).lower():
                            logger.info(f"Removing Code Interpreter tool for {provider} model in {agent_name}")
                        else:
                            filtered_tools.append(tool)
                    agent.tools = filtered_tools

            # Pass model in RunConfig but no model_settings (to avoid merge issues)
            # IMPORTANT: Disable tracing for non-OpenAI providers to prevent __fake_id__ errors
            kwargs["run_config"] = RunConfig(model=selected_model, tracing_disabled=True)
            logger.debug(
                f"Overriding agent model to {selected_model} ({provider} stream): "
                "temporarily replaced model_settings, reasoning field omitted, tracing disabled"
            )
        else:
            kwargs["run_config"] = RunConfig(model=selected_model)
            logger.debug(f"Overriding agent model to: {selected_model}")

    session_reset_performed = False
    collected_items: list[Any] = []
    last_output_text_parts: list[str] = []
    pending_deltas: Dict[str, List[str]] = defaultdict(list)
    item_types: Dict[str, str] = {}
    TOOL_ITEM_TYPES = {"tool_call_item", "tool_call_output_item", "function_call_item", "function_call_output_item"}
    MESSAGE_ITEM_TYPES = {"message_output_item"}
    structured_events: List[Dict[str, Any]] = []
    
    seen_event_types = set()

    _stream_start = time.time()

    # ============================================================
    # AGENTIC HOOKS: Set up event emitter context and hooks
    # This ensures tool outputs with action payloads emit agent_action events
    # ============================================================
    event_emitter_token = None
    agentic_hooks = None
    if on_event is not None:
        event_emitter_token = set_event_emitter(on_event)
        agentic_hooks = create_agentic_hooks()
        kwargs["hooks"] = agentic_hooks
        logger.debug(f"[AGENTIC_HOOKS] Enabled for {agent_name} streaming")

    try:
        while True:
            collected_items = []
            last_output_text_parts = []
            try:
                # Refresh explicit container per attempt to avoid stale IDs
                try:
                    if stream_container_id:
                        cleanup_container(stream_container_id, agent_name)
                    stream_container_id = None
                    if hasattr(agent, "tools") and any(isinstance(t, CodeInterpreterTool) for t in agent.tools):
                        import uuid as _uuid
                        new_message_id = _uuid.uuid4().hex
                        stream_container_id, _ = create_explicit_container(agent_name, new_message_id)
                        patched_tools = []
                        for tool in agent.tools:
                            if isinstance(tool, CodeInterpreterTool):
                                patched_tools.append(
                                    CodeInterpreterTool(
                                        tool_config={
                                            "type": "code_interpreter",
                                            "container": stream_container_id,
                                        }
                                    )
                                )
                            else:
                                patched_tools.append(tool)
                        agent.tools = patched_tools
                except Exception as refresh_err:
                    logger.debug(f"[CONTAINER] Streaming container refresh skipped: {refresh_err}")

                # Start streamed run
                # Disable tracing to avoid ContextVar errors in FastAPI async contexts
                # See: https://github.com/openai/openai-agents-python/issues/538
                from agents import set_tracing_disabled
                set_tracing_disabled(True)

                result_streaming = Runner.run_streamed(agent, query, **kwargs)

                async for ev in result_streaming.stream_events():
                    # ✅ CHECK CANCELLATION: Stop streaming if cancelled
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"[CANCEL] {agent_name} streaming cancelled during event loop")
                        raise asyncio.CancelledError(f"{agent_name} streaming cancelled by user")

                    try:
                        if ev.type == 'raw_response_event':
                            delta = None
                            data = getattr(ev, 'data', None)
                            item_id = None
                            event_type = None

                            if ResponseTextDeltaEvent is not None and isinstance(data, ResponseTextDeltaEvent):
                                delta = getattr(data, 'delta', None)
                                item_id = getattr(data, 'item_id', None)
                                event_type = getattr(data, 'type', None)
                            elif ResponseReasoningSummaryTextDeltaEvent is not None and isinstance(data, ResponseReasoningSummaryTextDeltaEvent):
                                delta = getattr(data, 'delta', None) or getattr(data, 'text', None)
                                item_id = getattr(data, 'item_id', None)
                                event_type = getattr(data, 'type', None)
                            elif ResponseReasoningSummaryPartAddedEvent is not None and isinstance(data, ResponseReasoningSummaryPartAddedEvent):
                                delta = None
                                item_id = getattr(data, 'item_id', None)
                                event_type = getattr(data, 'type', None)
                            elif isinstance(data, dict):
                                delta = data.get('delta') or data.get('text') or data.get('content')
                                item_id = data.get('item_id')
                                event_type = data.get('type')
                            elif hasattr(data, 'delta'):
                                delta = getattr(data, 'delta')
                                item_id = getattr(data, 'item_id', None)
                                event_type = getattr(data, 'type', None)
                            elif isinstance(data, str):
                                delta = data
                                event_type = None
                            else:
                                item_id = getattr(data, 'item_id', None) if data is not None else None

                            normalized = _normalize_stream_event(event_type, data, item_id)
                            if normalized is not None:
                                norm_type = normalized.get("type")
                                if norm_type and norm_type not in seen_event_types:
                                    seen_event_types.add(norm_type)
                                    logger.info("[STREAM_EVENT] First normalized raw event: %s", norm_type)
                                structured_events.append(normalized)
                                if on_event and app_config.enable_stream_events:
                                    await on_event(normalized)

                            if not isinstance(delta, str) or not delta:
                                continue

                            is_output_text_event = event_type in (None, "response.output_text.delta")
                            if not is_output_text_event:
                                continue

                            item_type = item_types.get(item_id) if item_id else None

                            # Forward true assistant text immediately. Tool-related deltas are skipped.
                            should_forward = True
                            if item_type in TOOL_ITEM_TYPES:
                                should_forward = False

                            if should_forward:
                                await on_token(delta)
                                last_output_text_parts.append(delta)
                                continue

                            if item_id:
                                pending_deltas[item_id].append(delta)
                            continue

                        # Agent switch updates (handoffs) – forward as structured event
                        if getattr(ev, 'type', None) == 'agent_updated_stream_event':
                            try:
                                new_agent = getattr(ev, 'new_agent', None)
                                agent_name = getattr(new_agent, 'name', None) if new_agent is not None else None
                                payload = {"type": "agent.updated"}
                                if agent_name:
                                    payload["agent_name"] = agent_name
                                if on_event and app_config.enable_stream_events:
                                    await on_event(payload)
                                structured_events.append(payload)
                            except Exception:
                                pass
                            continue

                        if ev.type == 'run_item_stream_event' and getattr(ev, 'item', None) is not None:
                            # Tool lifecycle events (started/output) are handled
                            # by AgenticActionHooks — only process message items here.
                            item = ev.item
                            item_type = getattr(item, 'type', '') or ''
                            if item_type in MESSAGE_ITEM_TYPES:
                                item_id = getattr(item, 'id', None) or getattr(item, 'item_id', None)
                                if item_id:
                                    buffered = pending_deltas.pop(item_id, [])
                                    for buffered_delta in buffered:
                                        await on_token(buffered_delta)
                                        last_output_text_parts.append(buffered_delta)
                            collected_items.append(ev.item)
                            continue
                        else:
                            normalized = _normalize_stream_event(getattr(ev, 'type', None), getattr(ev, 'data', None), None)
                            if normalized is not None:
                                norm_type = normalized.get("type")
                                if norm_type and norm_type not in seen_event_types:
                                    seen_event_types.add(norm_type)
                                    logger.info("[STREAM_EVENT] First normalized event: %s", norm_type)
                                structured_events.append(normalized)
                                if on_event and app_config.enable_stream_events:
                                    await on_event(normalized)
                    except Exception as e:
                        logger.debug(f"[execute_with_stream] Ignoring streaming event error: {e}")

                # Extract reasoning summary from completed stream if available
                try:
                    if hasattr(result_streaming, 'reasoning_summary'):
                        reasoning_summary = result_streaming.reasoning_summary
                        if reasoning_summary:
                            reasoning_event = {
                                "type": "reasoning.summary_done",
                                "text": reasoning_summary
                            }
                            structured_events.append(reasoning_event)
                            if on_event and app_config.enable_stream_events:
                                await on_event(reasoning_event)
                            logger.info("[REASONING_SUMMARY] Extracted from completed stream: %d chars", len(reasoning_summary))
                except Exception as reasoning_err:
                    logger.debug(f"[REASONING_SUMMARY] Could not extract: {reasoning_err}")

                if app_config.enable_cost_tracking:
                    try:
                        from core.ai.cost_tracker import cost_tracker
                        _sid = getattr(session, 'session_id', None) or str(id(session))
                        cost_tracker.record_from_stream(
                            result_streaming, agent_name, selected_model, _sid,
                            elapsed_s=time.time() - _stream_start,
                        )
                    except Exception:
                        pass

                break  # Successful streaming run completed
            except Exception as e:
                if _is_tool_history_mismatch(e) and not tool_mismatch_repaired:
                    repaired = await _repair_session_history(
                        session,
                        selected_model,
                        agent_name,
                    )
                    if repaired:
                        tool_mismatch_repaired = True
                        logger.warning(
                            "[STREAMING REPAIR] %s repaired session after tool mismatch, retrying stream",
                            agent_name,
                        )
                        continue

                reset_reason = None
                if _is_missing_reference_error(e):
                    reset_reason = "missing reference error"
                elif _is_missing_container_error(e):
                    reset_reason = "missing container error"
                
                should_reset = (
                    not session_reset_performed
                    and hasattr(session, "clear_session")
                    and reset_reason is not None
                )
                if should_reset:
                    logger.warning(
                        "Streaming executor detected %s; clearing persisted session and retrying once",
                        reset_reason,
                    )
                    try:
                        await session.clear_session()
                        session_reset_performed = True
                        continue
                    except Exception as reset_error:
                        logger.error(
                            "Failed to clear session after streaming missing reference error: "
                            f"{reset_error}"
                        )
                raise

        # Synthesize a result-like object so callers can keep existing parsing code
        class _ResultLike:
            def __init__(self, text: str, items: list[Any], events: List[Dict[str, Any]]):
                self.final_output = text
                self.new_items = items
                self.stream_events = events

        for buffered in pending_deltas.values():
            for buffered_delta in buffered:
                await on_token(buffered_delta)
                last_output_text_parts.append(buffered_delta)

        final_text = ''.join(last_output_text_parts) if last_output_text_parts else ''
        return _ResultLike(final_text, collected_items, structured_events)
    finally:
        # Re-enable tracing after streaming completes
        from agents import set_tracing_disabled
        set_tracing_disabled(False)

        # ============================================================
        # AGENTIC HOOKS: Clean up event emitter context
        # ============================================================
        if event_emitter_token is not None:
            reset_event_emitter(event_emitter_token)
            logger.debug(f"[AGENTIC_HOOKS] Cleaned up for {agent_name} streaming")

        # Restore original model_settings if we replaced them for Anthropic/Gemini
        if needs_override and orig_ms is not None:
            agent.model_settings = orig_ms
            logger.debug(f"Restored original model_settings for {agent_name}")

        # Restore tools if we patched
        # NOTE: Container cleanup moved to langgraph_nodes.py AFTER file extraction
        # This prevents empty generated_files due to premature container deletion
        try:
            if stream_orig_tools is not None:
                agent.tools = stream_orig_tools
        except Exception:
            pass


def _normalize_stream_event(
    event_type: Optional[str],
    data: Any,
    item_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Map OpenAI Responses API event types (see docs/responses-api-streaming.md)
    into normalized payloads for downstream consumers.
    """
    if not event_type:
        return None

    normalized_type, payload_key = _RESPONSES_EVENT_TYPE_MAP.get(event_type, (None, None))
    if normalized_type is None:
        return None

    payload: Dict[str, Any] = {"type": normalized_type}
    if item_id:
        payload["item_id"] = item_id

    if isinstance(data, dict):
        payload.update(data)
    elif hasattr(data, "__dict__"):
        # Convert object attributes to JSON-serializable format
        for k, v in vars(data).items():
            if k.startswith("_"):
                continue
            # Handle non-serializable objects
            if v is None or isinstance(v, (str, int, float, bool, list, dict)):
                payload[k] = v
            elif hasattr(v, "text"):
                # Extract text from Part objects
                payload[k] = getattr(v, "text", str(v))
            elif hasattr(v, "__dict__"):
                # Convert nested objects to dict
                payload[k] = {sk: sv for sk, sv in vars(v).items() if not sk.startswith("_")}
            else:
                # Fallback to string representation
                payload[k] = str(v)
    elif data is not None:
        payload[payload_key or "value"] = data

    return payload


# ============================================
# Tool Priority Injection
# ============================================

def build_tool_priority_prompt(prioritized_tools: Optional[List[str]]) -> str:
    """
    Build a prompt injection to prioritize specific tools.
    
    Args:
        prioritized_tools: List of tool names the user wants prioritized
        
    Returns:
        Prompt string to inject, or empty string if no tools specified
    """
    if not prioritized_tools or len(prioritized_tools) == 0:
        return ""
    
    tools_list = ", ".join(f"`{t}`" for t in prioritized_tools)
    
    return f"""

**TOOL PRIORITY INSTRUCTION:**
The user has explicitly requested that you prioritize using the following tool(s) in your analysis: {tools_list}

You MUST call at least one of these prioritized tools as part of your response. These tools should be used alongside any other tools you would normally use for this query. The user selected these tools because they want specific analysis capabilities applied to their request.

"""


def inject_tool_priority(query: str, state: Dict[str, Any]) -> str:
    """
    Inject tool priority prompt into the query if prioritized tools are specified.
    
    Args:
        query: The original query string
        state: LangGraph conversation state containing prioritized_tools
        
    Returns:
        Query with tool priority prompt injected (if applicable)
    """
    prioritized_tools = state.get("prioritized_tools")
    priority_prompt = build_tool_priority_prompt(prioritized_tools)
    
    if priority_prompt:
        logger.info(f"[TOOL PRIORITY] Injecting priority prompt for tools: {prioritized_tools}")
        return query + priority_prompt
    
    return query


# Mapping derived from docs/responses-api-streaming.md to ensure consistency.
_RESPONSES_EVENT_TYPE_MAP: Dict[str, Tuple[str, Optional[str]]] = {
    "response.created": ("response.created", None),
    "response.output_text.delta": ("output_text.delta", "delta"),
    "response.output_text.done": ("output_text.done", "text"),
    "response.output_text.annotation.added": ("output_text.annotation_added", None),
    "response.refusal.delta": ("refusal.delta", "delta"),
    "response.refusal.done": ("refusal.done", "refusal"),
    "response.function_call_arguments.delta": ("function_call.arguments_delta", "delta"),
    "response.function_call_arguments.done": ("function_call.arguments_done", "arguments"),
    "response.reasoning_text.delta": ("reasoning_delta", "delta"),
    "response.reasoning_text.done": ("reasoning_done", "text"),
    "response.reasoning_summary_text.delta": ("reasoning_delta", "delta"),
    "response.reasoning_summary_part.added": ("reasoning.summary_part", None),
    "response.reasoning_summary_text.done": ("reasoning_done", "text"),
    "response.file_search_call.in_progress": ("file_search.in_progress", None),
    "response.file_search_call.searching": ("file_search.searching", None),
    "response.file_search_call.completed": ("file_search.completed", None),
    "response.web_search_call.in_progress": ("web_search.in_progress", None),
    "response.web_search_call.searching": ("web_search.searching", None),
    "response.web_search_call.completed": ("web_search.completed", None),
    "response.mcp_call.in_progress": ("mcp_call.in_progress", None),
    "response.mcp_call.completed": ("mcp_call.completed", None),
    "response.mcp_call.failed": ("mcp_call.failed", None),
    "response.mcp_call_arguments.delta": ("mcp_call.arguments_delta", "delta"),
    "response.mcp_call_arguments.done": ("mcp_call.arguments_done", "arguments"),
    "response.mcp_list_tools.in_progress": ("mcp_list_tools.in_progress", None),
    "response.mcp_list_tools.completed": ("mcp_list_tools.completed", None),
    "response.mcp_list_tools.failed": ("mcp_list_tools.failed", None),
    "response.code_interpreter_call.in_progress": ("code_interpreter.in_progress", None),
    "response.code_interpreter_call.interpreting": ("code_interpreter.interpreting", None),
    "response.code_interpreter_call.completed": ("code_interpreter.completed", None),
    "response.code_interpreter_call_code.delta": ("code_interpreter.code_delta", "code"),
    "response.code_interpreter_call_code.done": ("code_interpreter.code_done", "code"),
    "response.image_generation_call.in_progress": ("image_generation.in_progress", None),
    "response.image_generation_call.generating": ("image_generation.generating", None),
    "response.image_generation_call.partial_image": ("image_generation.partial_image", "partial_image_b64"),
    "response.image_generation_call.completed": ("image_generation.completed", None),
    "response.output_item.added": ("output_item.added", None),
    "response.output_item.done": ("output_item.done", None),
    "response.content_part.added": ("content_part.added", None),
    "response.content_part.done": ("content_part.done", None),
    "response.queued": ("response.queued", None),
    "response.in_progress": ("response.in_progress", None),
    "response.incomplete": ("response.incomplete", None),
    "response.completed": ("response.completed", None),
    "response.failed": ("response.failed", None),
    "response.custom_tool_call_input.delta": ("custom_tool_call.input_delta", "delta"),
    "response.custom_tool_call_input.done": ("custom_tool_call.input_done", "input"),
    "error": ("error", None),
}
