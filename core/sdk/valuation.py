"""
Valuation SDK helpers powered by LangGraph orchestration.

This module exposes a comparable companies helper that lets IDE users rely on
the same AI-powered peer selection and field discovery that drive the chat
experience. The LangGraph orchestration layer selects peers/metrics while the
tool execution still uses the existing `analyze_comparable_companies` utility
so results remain deterministic and export-ready.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd

from core.agents.valuation_tools.comps_tool import analyze_comparable_companies
from core.ai.langgraph_orchestrator import LangGraphOrchestrator


PeerStrategy = Union[str, Sequence[str]]
MetricsStrategy = Union[str, Sequence[str]]
AggregationMethod = Optional[str]
AICommentaryMode = Optional[str]


@dataclass(frozen=True)
class CompsParams:
    """Parameter bundle for comparable companies analysis."""

    target: str
    peer_strategy: PeerStrategy = "auto"  # 'auto' delegates to LangGraph for peer discovery
    metrics_strategy: MetricsStrategy = "auto"  # 'auto' delegates to LangGraph for metric discovery
    aggregation: AggregationMethod = "median"
    comps_count: Optional[int] = None
    model: Optional[str] = None
    ai_commentary: AICommentaryMode = "off"


@dataclass
class CompsResult:
    """Structured result for comparable companies analysis."""

    target: str
    peers: List[str]
    metrics: List[str]
    aggregation: Optional[str]
    summary: str
    comparison_table: pd.DataFrame
    key_metrics_table: pd.DataFrame
    raw: Dict[str, Any]

    def to_dataframe(self, table: str = "comparison") -> pd.DataFrame:
        if table == "comparison":
            return self.comparison_table.copy()
        if table == "metrics":
            return self.key_metrics_table.copy()
        raise ValueError(f"Unknown table '{table}'. Expected 'comparison' or 'metrics'.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "peers": list(self.peers),
            "metrics": list(self.metrics),
            "aggregation": self.aggregation,
            "summary": self.summary,
            "comparison_table": self.comparison_table.to_dict(orient="records"),
            "key_metrics_table": self.key_metrics_table.to_dict(orient="records"),
            "raw": self.raw,
        }


class ValuationSDK:
    """Expose valuation tools through a Python-friendly interface."""

    async def comps_async(self, **kwargs: Any) -> CompsResult:
        params = CompsParams(**kwargs)
        return await _run_comps_async(params)

    def comps(self, **kwargs: Any) -> CompsResult:
        params = CompsParams(**kwargs)
        return _run_sync(_run_comps_async(params))


def _run_sync(coro: Awaitable[Any]) -> Any:
    """Run a coroutine from synchronous code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # type: ignore[arg-type]
    raise RuntimeError(
        "Cannot run synchronous SDK call while an event loop is running. "
        "Use the async `comps_async` method instead."
    )


async def _run_comps_async(params: CompsParams) -> CompsResult:
    target = params.target.upper()

    peer_override = _normalize_override(params.peer_strategy, uppercase=True)
    metrics_override = _normalize_override(params.metrics_strategy, uppercase=False)

    suggestion: Optional[Dict[str, Any]] = None
    aggregation = params.aggregation

    if peer_override is not None and not peer_override:
        raise ValueError("Provided peer list is empty after normalization.")
    if metrics_override is not None and not metrics_override:
        raise ValueError("Provided metrics list is empty after normalization.")

    if peer_override is not None and metrics_override is not None:
        peers = peer_override
        metrics = metrics_override
    else:
        suggestion = await _auto_select_comps(
            target=target,
            desired_count=params.comps_count or 5,
            user_model=params.model,
        )
        peers = peer_override or suggestion.get("peer_tickers", [])
        metrics = metrics_override or suggestion.get("fields", [])
        aggregation = params.aggregation or suggestion.get("aggregation") or "all"

    if not peers:
        raise ValueError(
            "AI routing did not return any peer tickers. Provide peers explicitly via `peer_strategy`."
        )
    if not metrics:
        raise ValueError(
            "AI routing did not return any valuation metrics. Provide metrics explicitly via `metrics_strategy`."
        )

    raw_result = await analyze_comparable_companies(
        target_ticker=target,
        peer_tickers=peers,
        fields=metrics,
        method=aggregation or "all",
    )

    if raw_result.get("status") != "success":
        error = raw_result.get("error", "unknown error")
        raise RuntimeError(f"Comparable companies analysis failed: {error}")

    result_payload = raw_result["comp_results"]
    comparison_df = _build_dataframe(result_payload.get("comparison_table_formatted", []))
    key_metrics_df = _build_dataframe(result_payload.get("key_metrics_table", []))

    summary_text = _build_summary_text(
        target,
        result_payload,
        params.ai_commentary,
        suggestion_summary=(suggestion or {}).get("summary") if suggestion else None,
    )

    return CompsResult(
        target=target,
        peers=peers,
        metrics=metrics,
        aggregation=aggregation,
        summary=summary_text,
        comparison_table=comparison_df,
        key_metrics_table=key_metrics_df,
        raw=raw_result,
    )


def _normalize_override(strategy: Union[str, Sequence[str], None], uppercase: bool) -> Optional[List[str]]:
    if strategy is None:
        return None
    if isinstance(strategy, str):
        if strategy.strip().lower() == "auto":
            return None
        items = [item.strip() for item in strategy.split(",") if item.strip()]
    else:
        items = [item.strip() for item in strategy if isinstance(item, str) and item.strip()]

    if uppercase:
        items = [item.upper() for item in items]
    return items


_ORCH_INSTANCE: Optional[LangGraphOrchestrator] = None
_ORCH_LOCK = asyncio.Lock()


async def _get_orchestrator() -> LangGraphOrchestrator:
    global _ORCH_INSTANCE
    if _ORCH_INSTANCE is None:
        async with _ORCH_LOCK:
            if _ORCH_INSTANCE is None:
                _ORCH_INSTANCE = LangGraphOrchestrator()
    return _ORCH_INSTANCE


async def _auto_select_comps(
    target: str,
    desired_count: int,
    user_model: Optional[str],
) -> Dict[str, Any]:
    orchestrator = await _get_orchestrator()
    session_id = f"sdk-{uuid.uuid4().hex}"
    prompt = _build_selection_prompt(target, desired_count)

    response_text = await orchestrator.process_query(
        query=prompt,
        session_id=session_id,
        history=[],
        agent_mode="multiples",
        selected_model=user_model,
        deep_analysis_mode=False,
    )

    data = _extract_json_payload(response_text)
    if not isinstance(data, dict):
        raise ValueError("AI selection response was not valid JSON.")

    peer_tickers = [ticker.upper() for ticker in data.get("peer_tickers", []) if isinstance(ticker, str)]
    fields = [field for field in data.get("fields", []) if isinstance(field, str)]
    aggregation = data.get("aggregation")
    summary = data.get("summary")

    suggestion: Dict[str, Any] = {
        "peer_tickers": peer_tickers,
        "fields": fields,
        "aggregation": aggregation,
        "summary": summary,
    }

    if isinstance(data.get("tool_output"), dict):
        suggestion["tool_output"] = data["tool_output"]

    return suggestion


def _build_selection_prompt(target: str, desired_count: int) -> str:
    return (
        f"You are powering Sentry's programmable SDK. "
        f"Select the best comparable tickers and valuation metrics for {target}. "
        f"Return STRICT JSON (no markdown, no commentary) with the schema:\n"
        f"{{\n"
        f'  "target": "{target}",\n'
        f'  "peer_tickers": ["TICKER1", ...],\n'
        f'  "fields": ["peRatio", "evToEbitda", ...],\n'
        f'  "aggregation": "median" | "mean" | "harmonic_mean",\n'
        f'  "summary": "short justification (<= 50 words)",\n'
        f'  "tool_output": null or the JSON returned by analyze_comparable_companies if executed\n'
        f"}}\n\n"
        f"Constraints:\n"
        f"- Provide at least {desired_count} peer tickers where feasible.\n"
        f"- Use MCP discovery to ensure field names are valid.\n"
        f"- If you run analyze_comparable_companies, include its JSON output verbatim in tool_output.\n"
        f"- DO NOT include any text outside the JSON object."
    )


def _extract_json_payload(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty AI selection response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse AI selection JSON: {exc}") from exc

    raise ValueError("Could not locate JSON payload in AI selection response.")


def _build_dataframe(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    try:
        data = list(rows)
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def _build_summary_text(
    target: str,
    comp_payload: Dict[str, Any],
    mode: Optional[str],
    suggestion_summary: Optional[str] = None,
) -> str:
    summary = comp_payload.get("summary", {})
    base_text = (
        suggestion_summary
        or summary.get("data_quality", "")
        or f"Comparable companies summary for {target}."
    )

    if not mode or mode == "off":
        return base_text

    stats = comp_payload.get("field_statistics", {})
    if not stats:
        return base_text

    top_lines: List[str] = [base_text, ""]

    interesting_fields: List[Tuple[str, Dict[str, Any]]] = list(stats.items())[:3]
    for metric, values in interesting_fields:
        median = values.get("median")
        target_value = values.get("target_value")
        percentile = values.get("target_percentile")
        if median is None or target_value is None:
            continue
        line = f"{metric}: target {target_value} vs. peer median {median}"
        if percentile is not None:
            line += f" ({percentile}% percentile)"
        top_lines.append(line)

    if mode == "verbose":
        ranges = comp_payload.get("valuation_ranges", {})
        for metric, bands in list(ranges.items())[:2]:
            low = bands.get("low")
            high = bands.get("high")
            if low is not None and high is not None:
                top_lines.append(f"{metric} valuation suggests range {low} – {high}.")

    return "\n".join(line for line in top_lines if line)

