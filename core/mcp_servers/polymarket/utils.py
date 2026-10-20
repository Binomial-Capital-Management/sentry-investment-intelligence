"""
Utility helpers for Polymarket MCP server.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def prune_nones(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with None values for clean query construction."""
    return {key: value for key, value in params.items() if value is not None}


def try_parse_json(value: Any) -> Any:
    """Attempt to decode JSON strings; return original value on failure."""
    if isinstance(value, (dict, list)):
        return value

    if not isinstance(value, str):
        return value

    trimmed = value.strip()
    if not trimmed:
        return value

    try:
        return json.loads(trimmed)
    except (json.JSONDecodeError, TypeError, ValueError):
        return value


def ensure_list(value: Any) -> List[Any]:
    """
    Coerce incoming data to a list for uniform downstream handling.
    Strings are treated as comma-separated values when appropriate.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    parsed = try_parse_json(value)
    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, str):
        candidate = [item for item in parsed.replace("[", "").replace("]", "").split(",") if item]
        if candidate:
            return [item.strip() for item in candidate]
        return [parsed.strip()] if parsed.strip() else []

    return [parsed]


def extract_token_ids(raw: Any) -> List[str]:
    """Normalize the market token payload into a deduplicated list of strings."""
    values = ensure_list(raw)
    tokens = []
    for item in values:
        if isinstance(item, str):
            token = item.strip()
            if token and token not in tokens:
                tokens.append(token)
        elif isinstance(item, dict):
            for maybe_token in item.values():
                if isinstance(maybe_token, str):
                    candidate = maybe_token.strip()
                    if candidate and candidate not in tokens:
                        tokens.append(candidate)
    return tokens


def extract_outcomes(raw: Any) -> List[str]:
    """Normalize outcome labels from Gamma responses."""
    values = ensure_list(raw)
    outcomes: List[str] = []
    for item in values:
        if isinstance(item, str):
            label = item.strip()
            if label:
                outcomes.append(label)
        elif isinstance(item, dict):
            for maybe_label in item.values():
                if isinstance(maybe_label, str):
                    normalized = maybe_label.strip()
                    if normalized:
                        outcomes.append(normalized)
    return outcomes


def pair_outcomes_and_tokens(outcomes: Iterable[str], tokens: Iterable[str]) -> List[Dict[str, Optional[str]]]:
    """
    Build a safe mapping between outcomes and token IDs.
    Keeps ordering but tolerates mismatched lengths by padding with None.
    """
    outcome_list = list(outcomes)
    token_list = list(tokens)

    size = max(len(outcome_list), len(token_list))
    paired: List[Dict[str, Optional[str]]] = []
    for idx in range(size):
        outcome = outcome_list[idx] if idx < len(outcome_list) else None
        token = token_list[idx] if idx < len(token_list) else None
        paired.append({"outcome": outcome, "token_id": token})
    return paired


def utc_now_iso() -> str:
    """Return a UTC ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()

