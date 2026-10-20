"""
Cross-provider message compaction utilities.

These helpers keep provider SDK sessions isolated while still allowing
compact cross-provider context to be injected when a model switch occurs.

MEMORY NOTEBOOK: Memory notes are ALWAYS included in cross-provider context
because they must survive provider switches. See docs/memory-notebook-feature-spec.md
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional

from core.ai.utils.context_manager import (
    build_shared_context, 
    _format_memory_for_injection,
    _strip_memory_from_messages,
    MEMORY_START_MARKER,
    MEMORY_END_MARKER,
)
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

try:
    from langchain_core.messages import BaseMessage
except ImportError:  # pragma: no cover - optional dependency
    BaseMessage = ()  # type: ignore


def message_to_dict(message: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize LangChain message objects or dicts into a plain dict so downstream
    compaction logic has consistent access to role/provider metadata.
    """
    if isinstance(message, dict):
        # Copy to avoid mutating upstream state
        return dict(message)

    if BaseMessage and isinstance(message, BaseMessage):  # type: ignore[arg-type]
        content = getattr(message, "content", None)
        additional = getattr(message, "additional_kwargs", None)
        role_attr = getattr(message, "type", None) or getattr(message, "role", None)
        name = getattr(message, "name", None)
        tool_calls = getattr(message, "tool_calls", None)
    elif hasattr(message, "content"):
        content = getattr(message, "content", None)
        additional = getattr(message, "additional_kwargs", None)
        role_attr = getattr(message, "type", None) or getattr(message, "role", None)
        name = getattr(message, "name", None)
        tool_calls = getattr(message, "tool_calls", None)
    else:
        return None

    role_map = {
        "ai": "assistant",
        "human": "user",
        "system": "system",
        "tool": "tool",
        "assistant": "assistant",
        "user": "user",
    }

    normalized: Dict[str, Any] = {
        "role": role_map.get(str(role_attr).lower(), role_attr or "assistant"),
        "content": content,
    }

    if isinstance(additional, dict):
        normalized.update(additional)

    if name and "agent" not in normalized:
        normalized["agent"] = name

    if tool_calls and "tool_calls" not in normalized:
        normalized["tool_calls"] = tool_calls

    return normalized


def get_provider_from_model(model: Optional[str]) -> str:
    """
    Normalize provider labels from model identifiers.

    Returns one of: 'anthropic', 'gemini', 'deepseek', 'bedrock', 'xai',
    'moonshot', 'qwen', 'zai', 'openai', or 'unknown'.
    """
    if not model:
        return "openai"

    lowered = model.lower()
    if "anthropic" in lowered:
        return "anthropic"
    if "gemini" in lowered or "google" in lowered:
        return "gemini"
    if "deepseek" in lowered:
        return "deepseek"
    if "bedrock" in lowered:
        return "bedrock"
    if "xai" in lowered or "grok" in lowered:
        return "xai"
    if "moonshot" in lowered or "kimi" in lowered:
        return "moonshot"
    if "dashscope" in lowered or "qwen" in lowered:
        return "qwen"
    if "/zai/" in lowered or lowered.startswith("zai/") or "glm" in lowered:
        return "zai"
    if lowered.startswith("litellm/openai") or "gpt-5" in lowered or "openai" in lowered:
        return "openai"
    return "openai"  # Default to openai so legacy models share a session safely


def detect_provider_switch(previous_model: Optional[str], new_model: Optional[str]) -> bool:
    """Return True when the provider backing the models differs."""
    return get_provider_from_model(previous_model) != get_provider_from_model(new_model)


async def _summarize_cross_provider(
    text: str,
    *,
    model: str,
    max_output_tokens: int,
    timeout_seconds: float,
) -> Optional[str]:
    """Summarize cross-provider context using an OpenAI model. Returns None on failure."""
    if not text.strip():
        return None

    # Normalize common model aliases used elsewhere in the app so the OpenAI SDK
    # receives a valid OpenAI model id.
    normalized_model = (model or "").strip()
    for prefix in ("litellm/openai/", "openai/"):
        if normalized_model.lower().startswith(prefix):
            normalized_model = normalized_model[len(prefix) :]
            break
    normalized_model = normalized_model.strip()
    if not normalized_model:
        return None

    client = AsyncOpenAI()
    system_text = (
        "You compress cross-provider assistant replies into a compact, chronological briefing so the active model understands "
        "the ongoing task. Preserve timeline, provider/agent attribution when known, ticker symbols, numerical figures, tool "
        "results, and user instructions. Use concise bullet paragraphs."
    )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=normalized_model,
                input=f"{system_text}\n\n{text}",
                reasoning={"effort": "low"},
                text={"verbosity": "low"},
                max_output_tokens=max(16, max_output_tokens),
            ),
            timeout=timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "[COMPACTION SUMMARY] summarizer failed (model=%s): %s",
            normalized_model,
            exc,
        )
        return None

    summary = getattr(response, "output_text", None)
    if isinstance(summary, str) and summary.strip():
        return summary.strip()

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for part in getattr(item, "content", []) or []:
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)

    combined = "".join(chunks).strip()
    return combined or None


def build_cross_provider_context(
    state: Dict[str, Any],
    current_provider: str,
    *,
    scan_budget: int,
    inject_budget: int,
    memory_notes: Optional[List[Dict]] = None,
) -> str:
    """
    Build a compact transcript limited to assistant messages generated by
    providers other than `current_provider`.
    
    MEMORY NOTEBOOK: If memory_notes is provided, they are prepended to the
    context and are NEVER compacted. This ensures critical user-pinned info
    survives provider switches.
    
    Previous memory injections are stripped from messages to prevent duplication.
    """
    raw_messages = list(state.get("messages") or [])
    provider_messages = state.get("_provider_messages") or []
    if provider_messages:
        raw_messages.extend(provider_messages)
    if not raw_messages and not memory_notes:
        return ""

    # Strip previous memory injections to prevent duplication
    raw_messages = _strip_memory_from_messages(raw_messages)

    messages: list[Dict[str, Any]] = []
    for msg in raw_messages:
        normalized = message_to_dict(msg)
        if normalized:
            messages.append(normalized)

    filtered: list[Dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        provider = msg.get("provider")
        # Include assistant messages if:
        # 1. They have a provider field that differs from current_provider, OR
        # 2. They have NO provider field (legacy messages or untagged - include for safety)
        # Exclude only if provider explicitly matches current_provider
        if role == "assistant":
            if provider is None or provider != current_provider:
                filtered.append(msg)
            # Skip if provider == current_provider (same provider, no need to include)
        elif role == "user":
            filtered.append(msg)

    # Build memory block (NEVER compacted, always at top)
    memory_block = ""
    if memory_notes:
        memory_block = _format_memory_for_injection(memory_notes)
    
    if not filtered and not memory_block:
        return ""

    filtered_state = {"messages": filtered}

    # Warm up by trimming to the scan budget (no output needed)
    if scan_budget > 0:
        build_shared_context(filtered_state, max_tokens=scan_budget)

    compact = build_shared_context(filtered_state, max_tokens=max(1, inject_budget))
    
    # Prepend memory block if present
    if memory_block:
        compact = f"{memory_block}\n{compact}" if compact.strip() else memory_block
    
    return compact.strip()


async def maybe_inject_on_switch(
    state: Dict[str, Any],
    text: str,
    *,
    enabled: bool,
    scan_budget: int,
    inject_budget: int,
    summary_model: Optional[str],
    summary_timeout: float,
    summary_max_output_tokens: int,
) -> str:
    """
    Append a compact cross-provider context block to `text` when a provider switch
    occurs for the current run. No-op when disabled, no prior provider, or no
    cross-provider messages exist.
    
    MEMORY NOTEBOOK: Memory notes are ALWAYS included in cross-provider context
    because they must survive provider switches.
    """
    if not enabled:
        return text

    current_provider = get_provider_from_model(state.get("selected_model"))
    previous_provider = state.get("last_provider")

    if not previous_provider or previous_provider == current_provider:
        logger.info(
            "[COMPACTION] skipped - no provider switch (previous=%s, current=%s, model=%s)",
            previous_provider,
            current_provider,
            state.get("selected_model"),
        )
        return text

    logger.info(
        "[COMPACTION] provider switch DETECTED: %s -> %s (model=%s)",
        previous_provider,
        current_provider,
        state.get("selected_model"),
    )

    # Load memory notes for this session (MUST survive provider switch)
    memory_notes: List[Dict] = []
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    if session_id and user_id:
        try:
            from core.services.memory_service import get_memory_service
            service = get_memory_service()
            result = await service.get_session_notes(user_id=user_id, session_id=session_id)
            if result.get("status") == "success":
                memory_notes = result.get("notes", [])
                if memory_notes:
                    logger.info(
                        "[COMPACTION] including %d memory notes in cross-provider context",
                        len(memory_notes),
                    )
        except Exception as e:
            logger.debug(f"Could not load memory notes for cross-provider: {e}")

    compact = build_cross_provider_context(
        state,
        current_provider=current_provider,
        scan_budget=scan_budget,
        inject_budget=inject_budget,
        memory_notes=memory_notes,
    )

    if not compact:
        logger.info("[COMPACTION] no cross-provider context found to inject")
        return text

    state["_compaction_original_tokens"] = len(compact)
    summary_used = False

    if summary_model:
        summary = await _summarize_cross_provider(
            compact,
            model=summary_model,
            max_output_tokens=summary_max_output_tokens,
            timeout_seconds=max(0.1, summary_timeout),
        )
        if summary:
            compact = summary.strip()
            summary_used = True
            state["_compaction_summary_model"] = summary_model
            state["_compaction_summary_tokens"] = len(compact)
        else:
            state["_compaction_summary_model"] = None
            state["_compaction_summary_tokens"] = len(compact)
    else:
        state["_compaction_summary_model"] = None
        state["_compaction_summary_tokens"] = len(compact)

    # Record compaction metadata for downstream consumers (e.g., SSE/analytics)
    state["_compaction_applied"] = True
    state["_compaction_tokens"] = len(compact)
    state["_compaction_from_provider"] = previous_provider
    state["_compaction_to_provider"] = current_provider
    state["_compaction_summary_used"] = summary_used
    state["_compaction_meta"] = {
        "summary_text": compact,
        "from_provider": previous_provider,
        "to_provider": current_provider,
    }

    try:
        logger.info(
            "[COMPACTION] provider switch %s -> %s | tokens=%s | summary=%s model=%s | preview=%.120s",
            previous_provider,
            current_provider,
            state["_compaction_tokens"],
            "used" if summary_used else "deterministic",
            state.get("_compaction_summary_model"),
            compact.replace("\n", " ")[:120],
        )
    except Exception:
        pass

    return f"{text}\n\n<conversation-context>\n{compact}\n</conversation-context>"
