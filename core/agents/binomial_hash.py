"""BinomialHash — thin shim that re-exports from the ``binomialhash`` package.

All implementation lives in the standalone ``binomialhash`` package
(installed via ``pip install -e ./binomialhash``).  This module keeps the
original import path (``from core.agents.binomial_hash import ...``) working
and adds Sentry-specific runtime logic that does not belong in the package:

* ``_caller_requests_bh_raw_mode()`` — stack-frame inspection to auto-bypass
  BH compaction when the call originates from internal agent tools.
* ``bh_ingest()`` — wraps the package helper with the frame-based bypass.
* ``infer_schema()`` — 2-arg wrapper around the package's 3-arg version.
"""

from __future__ import annotations

import contextvars
import logging
import sys
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Re-exports from the binomialhash package ─────────────────────────────────
from binomialhash import (  # noqa: F401  (re-export)
    BinomialHash,
    BinomialHashSlot,
    NestingProfile,
    _bh_raw_mode_depth,
    get_binomial_hash,
    init_binomial_hash,
    is_raw_mode,
)
from binomialhash.schema import (
    infer_schema as _pkg_infer_schema,
    to_float_strict,
)

logger = logging.getLogger(__name__)

# ── Sentry-specific: frame-based auto-raw-mode ──────────────────────────────

_BH_RAW_MODE_AGENT_EXCLUDES = (
    "/core/agents/binomial_hash.py",
    "/core/agents/bh_tools.py",
    "/core/agents/prompts/",
    "/core/agents/cancer_test_bh_tool.py",
    "/core/agents/hotsauce_test_bh_tool.py",
)
_BH_RAW_MODE_AGENT_HINTS = (
    "/core/agents/quant_tools/",
    "/core/agents/valuation_tools/",
    "/core/agents/risk_tools/",
    "/core/agents/alternatives_tools/",
    "/core/agents/structuring_tools/",
    "/core/agents/sentiment_tools/",
    "/core/agents/fund_tools/",
    "/api/routers/portfolio_risk.py",
    "/core/canvas/",
)


def _caller_requests_bh_raw_mode(max_frames: int = 16) -> bool:
    """Auto-bypass BH when a call originates from internal agent tools or
    programmatic endpoints that need raw data (portfolio analytics, canvas)."""
    frame = sys._getframe(2)
    for _ in range(max_frames):
        if frame is None:
            break
        filename = (frame.f_code.co_filename or "").replace("\\", "/")
        if any(excluded in filename for excluded in _BH_RAW_MODE_AGENT_EXCLUDES):
            frame = frame.f_back
            continue
        if any(hint in filename for hint in _BH_RAW_MODE_AGENT_HINTS) or filename.endswith("_tool.py"):
            return True
        frame = frame.f_back
    return False


# ── Public helpers (override / wrap the package versions) ────────────────────

@contextmanager
def bh_raw_mode():
    """Temporarily bypass BH compaction for internal custom-tool fetches."""
    token = _bh_raw_mode_depth.set(_bh_raw_mode_depth.get(0) + 1)
    try:
        yield
    finally:
        _bh_raw_mode_depth.reset(token)


def bh_ingest(raw_text: str, label: str) -> str:
    """Ingest a tool output — adds Sentry frame-based bypass before delegating."""
    if _bh_raw_mode_depth.get(0) > 0 or _caller_requests_bh_raw_mode():
        return raw_text
    return get_binomial_hash().ingest(raw_text, label)


def infer_schema(
    rows: List[Dict[str, Any]],
    columns: List[str],
) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
    """2-arg wrapper around the package's ``infer_schema(rows, cols, to_float)``."""
    return _pkg_infer_schema(rows, columns, to_float_strict)
