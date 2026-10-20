"""
SQLiteSession trimming helpers.

This module is intentionally LLM-free:
- It selects a recent tail window of persisted Agents SDK session items so we stay
  within context limits.
- LLM summarization (when enabled) is handled at a higher layer, so we can reuse
  the same summarizer/model settings as cross-provider compaction.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _estimate_text_tokens(text: str, encoding: Any) -> int:
    """Best-effort token estimator; overestimates when encoding is unavailable."""
    if not text:
        return 0
    if encoding is not None:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 3)


def _truncate_text_to_tokens(text: str, max_tokens: int, encoding: Any) -> str:
    if max_tokens <= 0:
        return ""
    if _estimate_text_tokens(text, encoding) <= max_tokens:
        return text

    # Prefer a simple char-based truncation; keep some head + tail for diagnostics.
    # Use an aggressive ratio since token/char mapping is approximate.
    approx_chars = max(64, max_tokens * 3)
    if len(text) <= approx_chars:
        return text
    head = text[: int(approx_chars * 0.85)]
    tail = text[-int(approx_chars * 0.10) :]
    omitted = max(0, len(text) - (len(head) + len(tail)))
    return f"{head}\n… ({omitted} chars omitted) …\n{tail}"


def _item_as_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    try:
        return json.dumps(item, default=str)
    except Exception:
        return str(item)


def _shrink_item_in_place(item: Any, *, max_tokens: int, encoding: Any) -> Any:
    """
    Shrink an individual session item so its serialized form fits ~max_tokens.

    This is a last-resort guard for pathological single items (e.g., huge tool outputs).
    """
    if max_tokens <= 0:
        return item

    if isinstance(item, str):
        return _truncate_text_to_tokens(item, max_tokens, encoding)

    if not isinstance(item, dict):
        text = _item_as_text(item)
        return _truncate_text_to_tokens(text, max_tokens, encoding)

    item_copy = copy.deepcopy(item)

    def _prune_jsonish(value: Any, budget: int, depth: int = 0) -> Any:
        """
        Prune nested dict/list values while preserving their type.

        Important: tool history items are re-sent to providers; keep JSON-ish shapes
        instead of converting dict/list to plain strings.
        """
        if budget <= 0:
            return value
        if isinstance(value, str):
            return _truncate_text_to_tokens(value, budget, encoding)
        if isinstance(value, dict):
            if depth >= 3:
                return {}
            pruned: Dict[str, Any] = {}
            child_budget = max(8, budget // 4)
            for idx, (k, v) in enumerate(value.items()):
                if idx >= 50:
                    break
                pruned[k] = _prune_jsonish(v, child_budget, depth + 1)
            return pruned
        if isinstance(value, list):
            if depth >= 3:
                return []
            child_budget = max(8, budget // 4)
            return [_prune_jsonish(v, child_budget, depth + 1) for v in value[:50]]
        return value

    # Prioritize common large fields.
    for key in ("output", "content", "arguments", "input"):
        if key in item_copy:
            item_copy[key] = _prune_jsonish(item_copy[key], max_tokens)

    # If still huge, drop non-essential fields and aggressively clip known heavy structures.
    if _estimate_text_tokens(_item_as_text(item_copy), encoding) > max_tokens:
        tool_id = item_copy.get("call_id") or item_copy.get("tool_use_id")
        name = item_copy.get("name") or item_copy.get("tool_name")
        essential: Dict[str, Any] = {}
        for k in ("role", "type", "id", "call_id", "tool_use_id", "status"):
            if k in item_copy:
                essential[k] = item_copy[k]
        if name:
            essential["name"] = name

        if "arguments" in item_copy:
            val = item_copy["arguments"]
            essential["arguments"] = {} if isinstance(val, dict) else _prune_jsonish(val, max_tokens // 2)
        if "input" in item_copy:
            val = item_copy["input"]
            essential["input"] = {} if isinstance(val, dict) else _prune_jsonish(val, max_tokens // 2)
        if "output" in item_copy:
            val = item_copy["output"]
            if isinstance(val, dict):
                essential["output"] = _prune_jsonish(val, max_tokens // 2)
            else:
                essential["output"] = _prune_jsonish(val, max_tokens // 2)
        if "content" in item_copy:
            content = item_copy["content"]
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    first = dict(first)
                    if isinstance(first.get("text"), str):
                        first["text"] = _truncate_text_to_tokens(first["text"], max_tokens // 2, encoding)
                    essential["content"] = [first]
                else:
                    essential["content"] = [_truncate_text_to_tokens(str(first), max_tokens // 2, encoding)]
            else:
                essential["content"] = _prune_jsonish(content, max_tokens // 2)

        # Ensure we keep the tool id when present (some items store it under different keys).
        if tool_id and "call_id" not in essential and "tool_use_id" not in essential:
            essential["call_id"] = tool_id

        item_copy = essential

    return item_copy


@dataclass(frozen=True)
class SqliteSessionCompactionStats:
    original_items: int
    original_tokens: int
    target_tokens: int
    summary_tokens: int
    recent_tokens: int
    recent_items: int
    older_items: int
    result_items: int
    result_tokens: int
    did_compact: bool


def compact_sqlite_session_items(
    session_items: List[Any],
    *,
    encoding: Any,
    target_tokens: int,
    summary_budget_tokens: int = 2000,
    recent_budget_ratio: float = 0.75,
) -> Tuple[List[Any], SqliteSessionCompactionStats]:
    """
    Compact a SQLiteSession item list to fit within `target_tokens`.

    Strategy:
    - Keep a recent tail window of original items (bounded by recent_budget_ratio).
    - If a single tail item is still too large, shrink it in-place to fit.
    - Older items are dropped here; optional LLM summarization happens outside this module.
    """
    safe_target = max(256, int(target_tokens))
    recent_budget = max(128, int(safe_target * max(0.1, min(recent_budget_ratio, 0.95))))
    token_counts = [_estimate_text_tokens(_item_as_text(item), encoding) for item in session_items]
    original_tokens = int(sum(token_counts))
    original_items = len(session_items)

    # Fast path
    if original_tokens <= safe_target:
        stats = SqliteSessionCompactionStats(
            original_items=original_items,
            original_tokens=original_tokens,
            target_tokens=safe_target,
            summary_tokens=0,
            recent_tokens=original_tokens,
            recent_items=original_items,
            older_items=0,
            result_items=original_items,
            result_tokens=original_tokens,
            did_compact=False,
        )
        return list(session_items), stats

    # Keep recent tail within budget (at least 1 item).
    recent_items: List[Any] = []
    recent_tokens = 0
    for item, tokens in zip(reversed(session_items), reversed(token_counts)):
        if recent_items and recent_tokens + tokens > recent_budget:
            break
        recent_items.insert(0, item)
        recent_tokens += int(tokens)

    if not recent_items and session_items:
        recent_items = [session_items[-1]]
        recent_tokens = int(token_counts[-1]) if token_counts else _estimate_text_tokens(_item_as_text(recent_items[0]), encoding)

    # If the newest item alone is too large, shrink it to fit the recent budget.
    if recent_items:
        newest = recent_items[-1]
        newest_tokens = _estimate_text_tokens(_item_as_text(newest), encoding)
        if newest_tokens > recent_budget:
            recent_items[-1] = _shrink_item_in_place(newest, max_tokens=recent_budget, encoding=encoding)
            recent_tokens = sum(_estimate_text_tokens(_item_as_text(it), encoding) for it in recent_items)

    older_count = max(0, original_items - len(recent_items))
    older_items = older_count

    result: List[Any] = list(recent_items)

    # Final guard: ensure result fits by shrinking the oldest kept items (excluding summary) if needed.
    result_tokens = sum(_estimate_text_tokens(_item_as_text(it), encoding) for it in result)
    if result_tokens > safe_target:
        for idx in range(0, len(result)):
            item = result[idx]
            item_tokens = _estimate_text_tokens(_item_as_text(item), encoding)
            if item_tokens <= 0:
                continue
            # Budget this item to its proportional share, but not less than 64 tokens.
            remaining = max(0, safe_target - (result_tokens - item_tokens))
            budget = max(64, remaining)
            result[idx] = _shrink_item_in_place(item, max_tokens=budget, encoding=encoding)
            result_tokens = sum(_estimate_text_tokens(_item_as_text(it), encoding) for it in result)
            if result_tokens <= safe_target:
                break

    stats = SqliteSessionCompactionStats(
        original_items=original_items,
        original_tokens=original_tokens,
        target_tokens=safe_target,
        summary_tokens=0,
        recent_tokens=int(recent_tokens),
        recent_items=len(recent_items),
        older_items=int(older_items),
        result_items=len(result),
        result_tokens=int(result_tokens),
        did_compact=True,
    )

    return result, stats
