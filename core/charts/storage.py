"""
Ephemeral chart storage to keep Plotly payloads out of the LLM context.

Stores full chart payloads in-process with a TTL and returns lightweight
handles that tools can pass back to the model. The orchestrator can later
hydrate handles for the frontend without re-exposing large payloads to the LLM.
"""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
from threading import Lock
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _convert_to_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy arrays and other non-JSON types to JSON-serializable format.
    This prevents 'Object of type ndarray is not JSON serializable' errors.
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        return str(obj)
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj) if hasattr(pd, 'isna') else False:
        return None
    return obj

logger = None  # Optional lazy logger to avoid import cycles


def _get_logger():
    global logger
    if logger is None:
        try:
            import logging

            logger = logging.getLogger(__name__)
        except Exception:  # pragma: no cover - logging not critical
            class _NullLogger:
                def debug(self, *args, **kwargs): ...
                def info(self, *args, **kwargs): ...
                def warning(self, *args, **kwargs): ...
                def error(self, *args, **kwargs): ...

            logger = _NullLogger()
    return logger


_store: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_lock = Lock()
_MAX_ITEMS = 200
_DEFAULT_TTL_SECONDS = 900  # 15 minutes


def _prune_locked(now: Optional[float] = None) -> None:
    """Remove expired entries while holding the lock."""
    ts = now or time.time()
    expired_keys = [k for k, (exp, _) in _store.items() if exp <= ts]
    for key in expired_keys:
        _store.pop(key, None)

    # Hard cap to avoid unbounded growth
    if len(_store) > _MAX_ITEMS:
        # Drop oldest items first
        sorted_items = sorted(_store.items(), key=lambda kv: kv[1][0])
        for key, _ in sorted_items[: len(_store) - _MAX_ITEMS]:
            _store.pop(key, None)


def store_chart(
    chart_payload: Dict[str, Any],
    chart_id: Optional[str] = None,
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    """
    Persist a chart payload and return its ID.

    Args:
        chart_payload: Dict with at least a Plotly payload under `plotly`.
        chart_id: Optional ID to force (otherwise generated).
        ttl_seconds: Time-to-live for the cached chart.

    Returns:
        The chart ID used to store the payload.
    """
    cid = chart_id or chart_payload.get("id") or f"chart_{uuid.uuid4().hex[:8]}"
    # Convert numpy arrays and other non-JSON types before storing
    # This prevents "Object of type ndarray is not JSON serializable" errors
    payload_copy = _convert_to_json_serializable(deepcopy(chart_payload))
    payload_copy["id"] = cid

    now = time.time()
    expires_at = now + max(ttl_seconds, 60)
    with _lock:
        _prune_locked(now)  # FIX: use current time, not future expiration
        _store[cid] = (expires_at, payload_copy)
        _get_logger().info("[CHART STORE] Stored chart %s (ttl=%ss, store_size=%d)", cid, ttl_seconds, len(_store))
    return cid


def get_chart(chart_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a stored chart payload by ID.

    Returns a deep copy to avoid accidental mutations of the cache.
    """
    if not chart_id:
        return None
    now = time.time()
    with _lock:
        entry = _store.get(chart_id)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at <= now:
            _store.pop(chart_id, None)
            return None
        return deepcopy(payload)


def pop_chart(chart_id: str) -> Optional[Dict[str, Any]]:
    """Remove and return a stored chart payload."""
    with _lock:
        entry = _store.pop(chart_id, None)
    if not entry:
        return None
    _, payload = entry
    return deepcopy(payload)


def clear() -> None:
    """Clear all cached charts (primarily for tests)."""
    with _lock:
        _store.clear()
