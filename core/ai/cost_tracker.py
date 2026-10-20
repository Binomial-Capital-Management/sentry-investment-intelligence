"""
Per-request LLM cost tracking with dedicated log file.

Logs token usage and estimated USD cost for every agent execution to logs/llm_costs.json,
broken down by agent name, model, and session. Maintains in-memory session
totals and emits a running summary after each call.

Pricing: Updated March 2026 from OpenAI pricing page.
- GPT-5.4: $2.50/1M input, $15/1M output
- Cached tokens: 90% discount (10% of input price)
"""

import logging
import os
from collections import defaultdict
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Per-1M-token pricing (input, output) — updated March 2026 from OpenAI pricing page
# Cached tokens get 90% discount (10% of input price) per OpenAI docs
# Extended context (>272K tokens) doubles input pricing and 1.5x output pricing
_FALLBACK_PRICING: Dict[str, Tuple[float, float]] = {
    "gpt-5.4": (2.50, 15.0),       # Standard context (<272K)
    "gpt-5.4-pro": (30.0, 180.0),  # Pro tier
    "gpt-5.2": (1.75, 14.0),
    "gpt-5.1": (2.50, 15.0),
    "gpt-5-mini": (0.25, 2.0),
    "gpt-5-nano": (0.10, 0.40),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "o1": (15.0, 60.0),
    "o1-mini": (1.10, 4.40),
}



def _calculate_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Calculate USD cost for a given model and token counts.
    
    Cached tokens are charged at 10% of input price (90% discount per OpenAI March 2026 pricing).
    """
    model_key = (model or "").strip()
    non_cached_input = input_tokens - cached_tokens

    # Skip LiteLLM for GPT-5.x models — use our accurate pricing instead
    normalized = model_key.lower()
    for prefix in ("litellm/", "litellm/anthropic/", "litellm/gemini/",
                   "litellm/deepseek/", "litellm/xai/", "litellm/moonshot/",
                   "litellm/dashscope/", "litellm/zai/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # Use our pricing table (more accurate for GPT-5.x)
    for key, (inp_per_m, out_per_m) in _FALLBACK_PRICING.items():
        if key in normalized:
            non_cached_cost = non_cached_input * inp_per_m / 1_000_000
            cached_cost = cached_tokens * inp_per_m * 0.1 / 1_000_000  # 90% discount (10% of input)
            output_cost = output_tokens * out_per_m / 1_000_000
            return non_cached_cost + cached_cost + output_cost

    # Try LiteLLM for unknown models
    try:
        from litellm import cost_per_token
        input_cost, output_cost = cost_per_token(
            model=model_key,
            prompt_tokens=non_cached_input,
            completion_tokens=output_tokens,
        )
        # Add cached tokens at 10% of input rate
        cached_cost, _ = cost_per_token(model=model_key, prompt_tokens=cached_tokens, completion_tokens=0)
        return input_cost + (cached_cost * 0.1) + output_cost
    except Exception:
        pass

    # Last resort: assume $2.50/$15 per 1M (GPT-5.4 pricing)
    non_cached_cost = non_cached_input * 2.50 / 1_000_000
    cached_cost = cached_tokens * 2.50 * 0.1 / 1_000_000  # 90% discount
    output_cost = output_tokens * 15.0 / 1_000_000
    return non_cached_cost + cached_cost + output_cost


class CostTracker:
    """Singleton that records LLM costs to a dedicated rotating log file."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "total_cost": 0.0, "total_input": 0, "total_output": 0}
        )
        self._cost_logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        cost_log = logging.getLogger("llm_cost_tracker")
        cost_log.setLevel(logging.INFO)
        cost_log.propagate = False

        if cost_log.handlers:
            return cost_log

        log_dir = Path(os.getenv("LLM_COST_LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "llm_costs.json"

        handler = RotatingFileHandler(
            str(log_path), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        cost_log.addHandler(handler)
        return cost_log

    def _extract_usage(self, result: Any) -> Dict[str, int]:
        """Extract token usage from an Agents SDK RunResult or streaming result."""
        usage = None

        # RunResult path: result.context_wrapper.usage
        if hasattr(result, "context_wrapper"):
            cw = result.context_wrapper
            if hasattr(cw, "usage"):
                usage = cw.usage

        # Streaming path: result.usage (on StreamedRunResult)
        if usage is None and hasattr(result, "usage"):
            usage = result.usage

        if usage is None:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                    "requests": 0, "cached_tokens": 0}

        cached = 0
        if hasattr(usage, "input_tokens_details"):
            details = usage.input_tokens_details
            if details and hasattr(details, "cached_tokens"):
                cached = getattr(details, "cached_tokens", 0) or 0

        return {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            "requests": getattr(usage, "requests", 0) or 0,
            "cached_tokens": cached,
        }

    def _record(
        self,
        usage: Dict[str, int],
        agent_name: str,
        model: Optional[str],
        session_id: str,
        elapsed_s: float,
    ) -> None:
        model_str = model or "unknown"
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        cached_tokens = usage["cached_tokens"]
        requests = usage["requests"]

        if input_tokens == 0 and output_tokens == 0:
            return

        cost = _calculate_cost(model_str, input_tokens, output_tokens, cached_tokens)

        # Update session accumulator
        sess = self._sessions[session_id]
        sess["calls"] += 1
        sess["total_cost"] += cost
        sess["total_input"] += input_tokens
        sess["total_output"] += output_tokens

        # JSON log entry
        import json
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "agent": agent_name,
            "model": model_str,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "requests": requests,
            "cost_usd": round(cost, 6),
            "elapsed_s": round(elapsed_s, 2),
            "session_total": {
                "calls": sess["calls"],
                "cost_usd": round(sess["total_cost"], 6),
                "tokens": sess["total_input"] + sess["total_output"],
            },
        }
        
        self._cost_logger.info(json.dumps(entry, indent=2))

    def record_from_result(
        self,
        result: Any,
        agent_name: str,
        model: Optional[str],
        session_id: str,
        elapsed_s: float = 0.0,
    ) -> None:
        """Record cost from a Runner.run() result."""
        try:
            usage = self._extract_usage(result)
            self._record(usage, agent_name, model, session_id, elapsed_s)
        except Exception as exc:
            logger.debug("[COST] Failed to record cost from result: %s", exc)

    def record_from_stream(
        self,
        stream_result: Any,
        agent_name: str,
        model: Optional[str],
        session_id: str,
        elapsed_s: float = 0.0,
    ) -> None:
        """Record cost from a Runner.run_streamed() result."""
        try:
            usage = self._extract_usage(stream_result)
            self._record(usage, agent_name, model, session_id, elapsed_s)
        except Exception as exc:
            logger.debug("[COST] Failed to record cost from stream: %s", exc)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        sess = self._sessions.get(session_id)
        if not sess:
            return {"calls": 0, "total_cost": 0.0, "total_tokens": 0}
        return {
            "calls": sess["calls"],
            "total_cost": sess["total_cost"],
            "total_tokens": sess["total_input"] + sess["total_output"],
        }

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        return {sid: self.get_session_summary(sid) for sid in self._sessions}

    def reset(self) -> None:
        self._sessions.clear()


# Module-level singleton
cost_tracker = CostTracker()
