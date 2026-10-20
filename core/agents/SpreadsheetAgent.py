"""
Spreadsheet Agent — Incremental Tool-Calling Architecture (v2)

The agent calls Excel operation tools one at a time, streamed to the
Office.js frontend via SSE for immediate execution.

Called by api/routers/excel_agent.py, NOT by the chat supervisor.

Following CODING_RULES.md: KISS, no hardcoding, dynamic discovery.
Following NASA Power of 10: bounded, no recursion, check returns.
"""

from agents import Agent, AgentHooks, ModelSettings, CodeInterpreterTool, Runner
from agents.extensions.tool_output_trimmer import ToolOutputTrimmer
from openai.types.shared import Reasoning
from typing import Any, Optional, List, Dict
from collections import deque
import asyncio
import logging
import json
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.agents.excel_tools import (
    EXCEL_TOOLS, set_op_queue, set_current_call_id,
    init_pending_reads, cancel_all_pending_reads, cleanup_pending_reads,
    init_pending_approvals, cancel_all_pending_approvals, cleanup_pending_approvals,
)

# ── CI debug file logger ──
_ci_log_path = Path(__file__).resolve().parent.parent.parent / "ci_debug.log"
_ci_logger = logging.getLogger("ci_debug")
_ci_logger.setLevel(logging.DEBUG)
_ci_logger.propagate = False
if not _ci_logger.handlers:
    _ci_fh = logging.FileHandler(str(_ci_log_path), mode="a", encoding="utf-8")
    _ci_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _ci_logger.addHandler(_ci_fh)

def _ci_log(msg: str):
    _ci_logger.info(msg)

logger = logging.getLogger(__name__)


def _setup_timeline_logger() -> logging.Logger:
    tl = logging.getLogger("agent_timeline")
    tl.setLevel(logging.INFO)
    tl.propagate = False
    if tl.handlers:
        return tl
    log_dir = Path(os.getenv("AGENT_TIMELINE_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(log_dir / "agent_timeline.jsonl"),
        maxBytes=20 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    tl.addHandler(handler)
    return tl


_timeline = _setup_timeline_logger()


def _tl(record: dict) -> None:
    """Write one pretty-printed JSON record to agent_timeline.jsonl."""
    record["ts"] = round(time.time() * 1000)  # epoch ms
    _timeline.info(json.dumps(record, indent=2))

MAX_CONTEXT_CHUNKS = 20
MAX_TURNS = 1000


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Factory
# ═══════════════════════════════════════════════════════════════════════════════


def create_spreadsheet_agent(
    mcp_servers: Optional[List[Any]] = None,
    model: str = None,
) -> Agent:
    """
    Create the SpreadsheetAgent with full tool set.

    ~70 function tools + MCP server tools (~65 from 7 servers) = ~135 total.
    """
    from core.agents.prompts.spreadsheet_agent_prompt import get_spreadsheet_agent_prompt
    from core.agents.valuation_tools import VALUATION_TOOLS
    from core.agents.memory_tools import MEMORY_TOOLS
    from core.tools.web_search import web_search
    from core.agents.sentiment_tools import analyze_news_sentiment

    instructions = get_spreadsheet_agent_prompt()

    tools = [
        *VALUATION_TOOLS,          # 10: DCF, comps, EPV, RIM, etc.
        *EXCEL_TOOLS,              # 19: write, format, chart, table, etc.
        CodeInterpreterTool(       # 1: custom Python
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
        web_search,                # 1: fallback data
        analyze_news_sentiment,    # 1: FinBERT news sentiment
    ]

    # Risk + Correlation + Quant (9)
    try:
        from core.agents.risk_tools.var_tool import calculate_var
        from core.agents.risk_tools.optimization_tool import optimize_portfolio
        from core.agents.risk_tools.barra_factors_tool import analyze_barra_factors
        from core.agents.risk_tools.rolling_correlation_tool import calculate_rolling_correlation
        from core.agents.risk_tools.implied_correlation_tool import calculate_implied_correlation
        from core.agents.risk_tools.correlation_stress_test_tool import stress_test_correlation
        from core.agents.risk_tools.fft_denoising_tool import analyze_fft_trends
        tools.extend([
            calculate_var, optimize_portfolio, analyze_barra_factors,
            calculate_rolling_correlation, calculate_implied_correlation,
            stress_test_correlation, analyze_fft_trends,
        ])
    except (ImportError, Exception) as e:
        logger.warning(f"Risk tools unavailable: {e}")

    # Quant + Options (20) — correlation, PCA, Greeks, vol surface, flow, screening
    try:
        from core.agents.quant_tools.correlation_matrix_tool import analyze_correlation_matrix
        from core.agents.quant_tools.pca_analysis_tool import analyze_pca_eigen_portfolios
        from core.agents.quant_tools.delta_exposure_tool import calculate_delta_exposure
        from core.agents.quant_tools.gamma_exposure_tool import calculate_gamma_exposure
        from core.agents.quant_tools.vega_exposure_tool import calculate_vega_exposure
        from core.agents.quant_tools.theta_decay_tool import calculate_theta_decay
        from core.agents.quant_tools.cross_greeks_tool import calculate_cross_greeks
        from core.agents.quant_tools.dynamic_hedge_tool import construct_dynamic_hedge
        from core.agents.quant_tools.equity_option_pricing_tool import price_equity_options
        from core.agents.quant_tools.volatility_surface_tool import model_volatility_surface
        from core.agents.quant_tools.greeks_surface_tool import model_greeks_surface
        from core.agents.quant_tools.dealer_gamma_regime_tool import analyze_dealer_gamma_regime
        from core.agents.quant_tools.vanna_charm_flow_tool import analyze_vanna_charm_flow
        from core.agents.quant_tools.iv_rv_screener_tool import analyze_iv_rv_vs_peers
        from core.agents.quant_tools.signal_confluence_detector import detect_signal_confluence
        from core.agents.quant_tools.earnings_pattern_analyzer import analyze_earnings_patterns
        from core.agents.quant_tools.gex_support_resistance_tool import analyze_gex_levels
        from core.agents.quant_tools.squeeze_detector import detect_squeeze_setup
        from core.agents.quant_tools.nope_divergence_tool import scan_nope_divergences
        tools.extend([
            analyze_correlation_matrix, analyze_pca_eigen_portfolios,
            calculate_delta_exposure, calculate_gamma_exposure,
            calculate_vega_exposure, calculate_theta_decay,
            calculate_cross_greeks, construct_dynamic_hedge,
            price_equity_options, model_volatility_surface,
            model_greeks_surface, analyze_dealer_gamma_regime,
            analyze_vanna_charm_flow, analyze_iv_rv_vs_peers,
            detect_signal_confluence, analyze_earnings_patterns,
            analyze_gex_levels, detect_squeeze_setup,
            scan_nope_divergences,
        ])
    except (ImportError, Exception) as e:
        logger.warning(f"Quant/options tools unavailable: {e}")

    # Structuring (6)
    try:
        from core.agents.structuring_tools import STRUCTURING_TOOLS
        tools.extend(STRUCTURING_TOOLS)
    except (ImportError, Exception) as e:
        logger.warning(f"Structuring tools unavailable: {e}")

    # Portfolio (4)
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
    except (ImportError, Exception):
        pass

    # File reading (1) — allows agent to read user-uploaded files
    try:
        from core.agents.file_tools import read_file_content
        tools.append(read_file_content)
    except (ImportError, Exception) as e:
        logger.warning(f"File tools unavailable: {e}")

    tools.extend(MEMORY_TOOLS)     # 2: save/recall

    # BinomialHash tools (14) — data: retrieve, aggregate, query, schema, group_by, to_excel | manifold: state, insights, navigate, slice | nav: geodesic, walk_axis | stats: regress, partial_corr
    from core.agents.bh_tools import BINOMIAL_HASH_TOOLS
    tools.extend(BINOMIAL_HASH_TOOLS)

    # Temporary synthetic BH stress-test tools
    try:
        from core.agents.cancer_test_bh_tool import cancer_test_bh
        tools.append(cancer_test_bh)
    except (ImportError, Exception) as e:
        logger.warning(f"Cancer test BH tool unavailable: {e}")

    try:
        from core.agents.hotsauce_test_bh_tool import hotsauce_test_bh
        tools.append(hotsauce_test_bh)
    except (ImportError, Exception) as e:
        logger.warning(f"Hotsauce test BH tool unavailable: {e}")

    if not model:
        from core.config import get_config
        model = get_config().agent_model

    agent = Agent(
        name="SpreadsheetAgent",
        instructions=instructions,
        model=model,
        tools=tools,
        mcp_servers=mcp_servers or [],
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            max_tokens=32000,
            truncation="auto",
            reasoning=Reasoning(effort="medium", summary="detailed"),
            response_include=["code_interpreter_call.outputs"],
        ),
    )

    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in tools]
    bh_tools_loaded = [n for n in tool_names if n.startswith("bh_")]
    logger.info(f"SpreadsheetAgent: {len(tools)} function tools, {len(mcp_servers or [])} MCP servers")
    logger.info(f"SpreadsheetAgent BH tools ({len(bh_tools_loaded)}): {bh_tools_loaded}")
    return agent


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton + MCP Connection
# ═══════════════════════════════════════════════════════════════════════════════

_agent: Optional[Agent] = None


async def _connect_mcp(cls: type, name: str) -> Optional[Any]:
    """Safely instantiate and connect an MCP server."""
    try:
        server = cls()
        await server.connect()
        logger.info(f"MCP {name} connected")
        return server
    except Exception as e:
        logger.warning(f"MCP {name} unavailable: {e}")
        return None


async def _get_agent() -> Agent:
    """
    Get or create the singleton SpreadsheetAgent.

    MCP servers: 7 total (3 FMP/Economic + 1 Polygon Options + 3 Unusual Whales).
    FMP Market (~11) + FMP Valuation (~8) + Economic (~8) + Polygon Options (~10)
    + UW Options (~14) + UW Market (~7) + UW Institutional (~7) = ~65 MCP tools
    + ~70 function tools = ~135 total.
    """
    global _agent
    if _agent is not None:
        return _agent

    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
    from core.mcp_servers.fmp.FMPDocumentServer import FMPDocumentServer
    from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
    from core.mcp_servers.EconomicDataServer import EconomicDataServer
    from core.mcp_servers.YFinanceServer import YFinanceServer
    from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
    from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
    from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
    from core.mcp_servers.unusualwhales.UWInstitutionalServer import UWInstitutionalServer

    t0 = time.time()

    # 10 servers: FMP (market, valuation, docs, alternatives) + economic + YFinance + Polygon options + 3 Unusual Whales
    results = await asyncio.gather(
        _connect_mcp(FMPMarketDataServer, "FMPMarketData"),
        _connect_mcp(FMPAdvancedValuationServer, "FMPAdvancedValuation"),
        _connect_mcp(FMPDocumentServer, "FMPDocuments"),
        _connect_mcp(FMPAlternativesServer, "FMPAlternatives"),
        _connect_mcp(EconomicDataServer, "EconomicData"),
        _connect_mcp(YFinanceServer, "YFinance"),
        _connect_mcp(PolygonOptionsFuturesServer, "PolygonOptions"),
        _connect_mcp(UWOptionsServer, "UWOptions"),
        _connect_mcp(UWMarketServer, "UWMarket"),
        _connect_mcp(UWInstitutionalServer, "UWInstitutional"),
        return_exceptions=True,
    )
    mcp_servers = [s for s in results if s is not None and not isinstance(s, Exception)]
    mcp_errors = [str(s) for s in results if isinstance(s, Exception)]

    elapsed = time.time() - t0
    logger.info(f"MCP init: {len(mcp_servers)} servers in {elapsed:.1f}s")

    _agent = create_spreadsheet_agent(mcp_servers=mcp_servers)
    return _agent


# ═══════════════════════════════════════════════════════════════════════════════
# Context Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def _format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format pgvector chunks into a context block."""
    if not chunks:
        # Tool-first mode: encourage agent to use read tools to discover workbook
        return """(No pre-loaded workbook context)

Use your workbook exploration tools to understand the structure:
- excel_get_workbook_structure() → see all sheets and their headers
- excel_get_sheet_summary(sheet) → detailed view of one sheet (column types, sample rows)
- excel_read_range(sheet, range) → read specific cell values
- excel_find_columns_by_header(pattern) → find columns by header name across all sheets

Start with excel_get_workbook_structure() to understand what sheets exist and their structure."""

    lines: List[str] = []
    for i, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS]):
        sim = chunk.get("similarity", 0)
        lines.append(f"--- Chunk {i + 1} (relevance: {sim:.2f}) ---")
        lines.append(f"Sheet: {chunk.get('sheet_name', '?')}")
        lines.append(f"Type: {chunk.get('chunk_type', '?')}")
        cr = chunk.get("cell_range")
        if cr:
            lines.append(f"Range: {cr}")
        lines.append(f"Content: {chunk.get('content', '')}")
        meta = chunk.get("metadata", {})
        formulas = meta.get("formulas_sample", [])
        if formulas:
            lines.append(f"Formulas: {', '.join(formulas[:5])}")
        headers = meta.get("headers", [])
        if headers:
            # Add explicit column letter mapping to help agent write correct formulas
            col_mapping_str = ", ".join(f"{chr(65 + idx)}={h}" for idx, h in enumerate(headers[:20]) if h)
            lines.append(f"Column mapping: {col_mapping_str}")
            lines.append(f"Headers: {', '.join(h for h in headers[:10] if h)}")
        lines.append("")
    
    return "\n".join(lines)


def _build_user_content(
    message: str,
    context_chunks: List[Dict[str, Any]],
    blueprint: Optional[Dict[str, Any]] = None,
    portfolio_context: Optional[Dict[str, Any]] = None,
    file_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    selection: Optional[Dict[str, Any]] = None,
    images: Optional[List[Dict[str, str]]] = None,
):
    """Build the prompt for the agent. Returns str or list of content blocks when images are attached."""
    parts: List[str] = []
    
    # Conversation history (most important for understanding context like "yes")
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-10:]:  # Last 10 messages
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")[:500]  # Truncate long messages
            history_lines.append(f"{role}: {content}")
        history_block = f"<conversation_history>\n" + "\n\n".join(history_lines) + "\n</conversation_history>\n"
        parts.append(history_block)
        logger.info(f"[Excel] Including {len(conversation_history)} messages in prompt ({len(history_block)} chars)")
    
    if blueprint:
        parts.append(f"<workbook_blueprint>\n{json.dumps(blueprint, indent=2, default=str)}\n</workbook_blueprint>\n")

    context_block = _format_context(context_chunks)
    parts.append(f"<workbook_context>\n{context_block}\n</workbook_context>\n")

    # Portfolio context
    if portfolio_context and isinstance(portfolio_context, dict):
        compact = {
            "tickers": portfolio_context.get("tickers", []),
            "weights": portfolio_context.get("weights", []),
            "value": portfolio_context.get("value"),
            "cash_balance": portfolio_context.get("cash_balance"),
        }
        holdings = portfolio_context.get("holdings")
        if holdings:
            compact["holdings_count"] = len(holdings)
        parts.append(f"<attached_portfolio>\n{json.dumps(compact, default=str)}\n</attached_portfolio>\n")

    # File context
    if file_ids:
        user_hint = user_id or "current_user"
        ids_str = ", ".join(file_ids[:10])
        parts.append(
            f"<attached_files>\n"
            f"User has attached {len(file_ids)} file(s) (IDs: {ids_str}). "
            f"Use read_file_content(file_id=<target_id>, user_id=\"{user_hint}\") to read each file.\n"
            f"</attached_files>\n"
        )

    # Selection context (user-highlighted range in Excel)
    if selection and isinstance(selection, dict):
        sheet = selection.get("sheet", "")
        rng = selection.get("range", "")
        rows = selection.get("rowCount", 0)
        cols = selection.get("colCount", 0)
        values = selection.get("values", [])
        headers = selection.get("headers", [])
        
        selection_lines = [f"User has selected {sheet}!{rng} ({rows} rows × {cols} cols)."]
        if headers:
            headers_str = ", ".join(str(h) for h in headers[:20])
            selection_lines.append(f"Headers: {headers_str}")
        if values and len(values) > 1:
            preview_rows = min(5, len(values) - 1)
            selection_lines.append(f"Data preview ({preview_rows} of {len(values)-1} data rows):")
            for row in values[1:preview_rows+1]:
                row_str = " | ".join(str(v)[:30] if v is not None else "" for v in row[:10])
                selection_lines.append(f"  {row_str}")
        
        parts.append(f"<user_selection>\n" + "\n".join(selection_lines) + "\n</user_selection>\n")
        logger.info(f"[Excel] Including selection context: {sheet}!{rng} ({rows}x{cols})")

    if images:
        parts.append(
            f"<attached_images>\n"
            f"User has attached {len(images)} image(s). They are included below as visual content. "
            f"Analyze the images to understand what the user is asking about.\n"
            f"</attached_images>\n"
        )

    parts.append(f"<user_request>\n{message}\n</user_request>\n")
    parts.append(
        "Use your excel_* tools to build the requested model/analysis directly. "
        "Fetch data first with MCP/valuation tools, then write values and formulas "
        "to the workbook step by step. Format professionally when done."
    )

    text_content = "\n".join(parts)

    if not images:
        return text_content

    content_blocks: list = [{"type": "input_text", "text": text_content}]
    for img in images:
        data_url = img.get("data_url", "")
        if data_url:
            content_blocks.append({"type": "input_image", "image_url": data_url})
    return [{"type": "message", "role": "user", "content": content_blocks}]


# ═══════════════════════════════════════════════════════════════════════════════
# Incremental Execution (v2 — tool-calling loop)
# ═══════════════════════════════════════════════════════════════════════════════


class ToolTimingHooks(AgentHooks):
    """Emit real-time tool_done + tool_server_done events as each tool completes."""

    def __init__(self, on_event, call_id_map: Dict[str, deque], emitted_call_ids: set):
        self._on_event = on_event
        self._call_id_map = call_id_map
        self._emitted_call_ids = emitted_call_ids
        # Per-tool-name FIFO for call_id correlation (asyncio.current_task()
        # differs between on_tool_start and on_tool_end because the SDK wraps
        # each hook call in a separate asyncio.gather sub-task)
        self._pending_call_ids: Dict[str, deque] = {}
        self._start_times: dict = {}

    async def on_tool_start(self, context, agent, tool):
        q = self._call_id_map.get(tool.name)
        call_id = q.popleft() if q else None
        if call_id:
            self._pending_call_ids.setdefault(tool.name, deque()).append(call_id)
            self._start_times[call_id] = time.time()

    async def on_tool_end(self, context, agent, tool, result):
        q = self._pending_call_ids.get(tool.name)
        call_id = q.popleft() if q else None
        start = self._start_times.pop(call_id, None) if call_id else None
        duration_ms = round((time.time() - start) * 1000) if start else None
        if self._on_event and call_id:
            # Emit tool_done with result in real-time (before SDK batches them)
            output_str = str(result)[:2500] if result else ""
            result_obj = _parse_tool_result(result)
            tool_done_event: dict = {"type": "tool_done", "output": output_str, "call_id": call_id}
            if result_obj:
                tool_done_event["result"] = result_obj
            await self._on_event(tool_done_event)
            self._emitted_call_ids.add(call_id)
            # Emit tool_server_done with timing
            server_event: dict = {"type": "tool_server_done", "tool": tool.name, "call_id": call_id}
            if duration_ms is not None:
                server_event["server_duration_ms"] = duration_ms
            await self._on_event(server_event)
        elif self._on_event:
            # No call_id — emit timing-only (stream handler will provide result)
            event: dict = {"type": "tool_server_done", "tool": tool.name}
            if duration_ms is not None:
                event["server_duration_ms"] = duration_ms
            await self._on_event(event)


def _is_content_policy_error(exc: Exception) -> bool:
    """Detect OpenAI content-filter / usage-policy rejections."""
    msg = str(exc).lower()
    return any(marker in msg for marker in (
        "usage policy",
        "content policy",
        "content_policy",
        "content management policy",
        "flagged as potentially violating",
    ))


async def execute_streamed(
    message: str,
    context_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    blueprint: Optional[Dict[str, Any]] = None,
    on_event: Optional[Any] = None,
    selected_model: Optional[str] = None,
    portfolio_context: Optional[Dict[str, Any]] = None,
    file_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    bloomberg: bool = False,
    cancel_event: Optional[asyncio.Event] = None,
    request_id: Optional[str] = None,
    selection: Optional[Dict[str, Any]] = None,
    edit_approval_mode: str = "accept",
    on_stream_created: Optional[Any] = None,
    images: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Run the agent with streaming. Excel tool calls are emitted via SSE.

    Supports per-request model override — applies provider-specific settings
    for Claude, Gemini, xAI, DeepSeek (mirrors langgraph_utils.execute_with_stream).

    Args:
        cancel_event: Optional asyncio.Event that signals cancellation when set.

    Returns:
        {"status": "ok", "summary": "...", "operations_count": N}
    """
    from agents import set_tracing_disabled, RunConfig
    from core.ai.utils.message_compactor import get_provider_from_model

    agent = await _get_agent()
    user_content = _build_user_content(
        message, context_chunks, blueprint,
        portfolio_context=portfolio_context,
        file_ids=file_ids,
        user_id=user_id,
        conversation_history=conversation_history,
        selection=selection,
        images=images,
    )

    op_queue: asyncio.Queue = asyncio.Queue()
    set_op_queue(op_queue)
    if request_id:
        init_pending_reads(request_id)
        init_pending_approvals(request_id, edit_approval_mode)

    # Initialize per-request BinomialHash for compacted tool outputs
    from core.agents.binomial_hash import init_binomial_hash
    init_binomial_hash()

    operations_count = 0
    drain_done = False
    set_tracing_disabled(True)
    t0 = time.time()

    logger.info(f"[Excel] Starting execution: '{message[:80]}...' model={selected_model or 'default'}")
    _tl({"event": "request_start", "model": selected_model or "default", "request_id": request_id})

    # ── Provider-specific overrides (mirrors langgraph_utils.execute_with_stream) ──
    run_kwargs: Dict[str, Any] = {"max_turns": MAX_TURNS}

    # Trim large tool outputs from older turns to prevent context overload.
    # Keeps full output for the last 3 turns; older outputs trimmed to 1000 chars.
    _tool_output_trimmer = ToolOutputTrimmer(recent_turns=3, max_output_chars=1000)

    provider = get_provider_from_model(selected_model) if selected_model else "openai"
    needs_override = provider in ("anthropic", "gemini", "xai", "deepseek", "bedrock", "moonshot", "qwen", "zai")

    def _strip_code_interpreter(tools):
        return [
            t for t in tools
            if "code_interpreter" not in str(getattr(t, "name", getattr(t, "__name__", str(t)))).lower()
        ]

    if selected_model:
        if needs_override:
            filtered_tools = _strip_code_interpreter(agent.tools) if agent.tools else []

            orig_ms = getattr(agent, "model_settings", None)
            ptc = (
                getattr(orig_ms, "parallel_tool_calls", None)
                if orig_ms and provider not in ("xai", "deepseek", "bedrock", "moonshot", "qwen", "zai")
                else None
            )
            tc = "auto" if provider not in ("bedrock",) else None
            mt = getattr(orig_ms, "max_tokens", None) if orig_ms else None
            if provider == "deepseek" and (mt is None or mt > 8192):
                mt = 8192
            if provider == "bedrock" and (mt is None or mt > 8192):
                mt = 8192
            if provider == "moonshot" and (mt is None or mt > 16384):
                mt = 16384
            if provider == "qwen" and (mt is None or mt > 16384):
                mt = 16384
            if provider == "zai" and (mt is None or mt > 15000):
                mt = 15000

            extra_body = {}
            if provider in ("moonshot", "qwen"):
                extra_body["thinking"] = {"type": "disabled"}
            # NOTE: Anthropic adaptive thinking + interleaved thinking DISABLED.
            # With adaptive mode, the model re-plans from scratch on every tool call
            # round (72-98s thinking blocks of repetitive content). Disabling thinking
            # lets the model write its plan as visible response text and execute
            # immediately — matching the pattern Claude for Excel uses (Programmatic
            # Tool Calling). See: conversation analysis 2026-03-17.
            #
            # if provider == "anthropic":
            #     extra_body["thinking"] = {"type": "adaptive"}
            #     extra_body["output_config"] = {"effort": "low"}

            forced_ms = ModelSettings(
                tool_choice=tc,
                parallel_tool_calls=ptc,
                max_tokens=mt,
                extra_body=extra_body or None,
                include_usage=True,
                # NOTE: reasoning=Reasoning(effort="low") removed for Anthropic.
                # It was a sentinel for preserve_thinking_blocks in litellm_model.py,
                # but litellm also passes it as reasoning_effort to the API, which
                # enables extended thinking on Claude models. Since we disabled
                # adaptive thinking above, this must also be removed.
                # For OpenAI models, the default agent's reasoning setting still applies.
                reasoning=Reasoning(effort="low") if provider != "anthropic" else None,
            )
            
            # Use CachingLitellmModel for Anthropic to enable prompt caching
            # (90% cost reduction on system prompt + tools after first API call)
            if provider == "anthropic":
                from core.ai.caching_litellm_model import CachingLitellmModel
                # Strip "litellm/" prefix — the framework normally does this via
                # MultiProvider._get_prefix_and_model_name, but we instantiate directly.
                _model_id = selected_model.removeprefix("litellm/")
                _caching_model = CachingLitellmModel(model=_model_id, api_key=None)
                run_kwargs["run_config"] = RunConfig(model=_caching_model, tracing_disabled=True, call_model_input_filter=_tool_output_trimmer)
            else:
                run_kwargs["run_config"] = RunConfig(model=selected_model, tracing_disabled=True, call_model_input_filter=_tool_output_trimmer)
            logger.info(f"[Excel] {provider} override: CodeInterpreter removed, tracing disabled")

            agent = Agent(
                name=agent.name,
                instructions=agent.instructions,
                model=agent.model,
                tools=filtered_tools,
                mcp_servers=agent.mcp_servers,
                model_settings=forced_ms,
                output_type=agent.output_type,
            )

            # Emit the actual params used — read from the already-computed variables
            if on_event:
                _params: dict = {
                    k: v for k, v in {
                        "max_tokens": mt,
                        "parallel_tool_calls": ptc,
                        "tool_choice": tc,
                    }.items() if v is not None
                }
                # Flatten extra_body keys (thinking, output_config, etc.) directly
                for k, v in extra_body.items():
                    _params[k] = v
                await on_event({"type": "model_params", "model": selected_model, "params": _params})
        else:
            run_kwargs["run_config"] = RunConfig(model=selected_model, call_model_input_filter=_tool_output_trimmer)
            logger.info(f"[Excel] Model override: {selected_model}")

            # OpenAI path — read from the singleton agent's model_settings
            if on_event:
                orig_ms = getattr(agent, "model_settings", None)
                _reasoning = getattr(orig_ms, "reasoning", None)
                _params = {
                    k: v for k, v in {
                        "max_tokens": getattr(orig_ms, "max_tokens", None) if orig_ms else None,
                        "parallel_tool_calls": getattr(orig_ms, "parallel_tool_calls", None) if orig_ms else None,
                        "tool_choice": getattr(orig_ms, "tool_choice", None) if orig_ms else None,
                        "reasoning_effort": getattr(_reasoning, "effort", None) if _reasoning else None,
                        "reasoning_summary": getattr(_reasoning, "summary", None) if _reasoning else None,
                    }.items() if v is not None
                }
                await on_event({"type": "model_params", "model": selected_model, "params": _params})

    # Default RunConfig with trimmer if none was set above
    if "run_config" not in run_kwargs:
        run_kwargs["run_config"] = RunConfig(call_model_input_filter=_tool_output_trimmer)

    # ── Snapshot mutable agent state before per-request mutation ──
    orig_tools = agent.tools
    orig_instructions = agent.instructions
    orig_hooks = agent.hooks

    # ── Bloomberg conditional injection ──
    if bloomberg:
        try:
            from core.agents.bloomberg_tools import BLOOMBERG_TOOLS, BLOOMBERG_PROMPT_ADDENDUM
            agent.tools = [*(agent.tools or []), *BLOOMBERG_TOOLS]
            agent.instructions = agent.instructions + BLOOMBERG_PROMPT_ADDENDUM
            logger.info(f"[Excel] Bloomberg tools injected ({len(BLOOMBERG_TOOLS)} tools)")
        except (ImportError, Exception) as e:
            logger.warning(f"[Excel] Bloomberg tools unavailable: {e}")

    # ── Real-time tool timing hooks ──
    tool_call_id_map: Dict[str, deque] = {}
    emitted_call_ids: set = set()
    if on_event:
        agent.hooks = ToolTimingHooks(on_event, tool_call_id_map, emitted_call_ids)

    # ── Drain loop: emits operations via SSE in real-time ──

    async def _drain_loop():
        """Drain op queue every 200ms — model-agnostic (works with any provider)."""
        nonlocal operations_count
        while not drain_done:
            while not op_queue.empty():
                op = op_queue.get_nowait()
                operations_count += 1
                logger.info(f"[Excel] Op #{operations_count}: {op.get('action', '?')} on {op.get('sheet', '?')}")
                if on_event:
                    await on_event({"type": "operation", **op})
            await asyncio.sleep(0.2)
        # Final drain
        while not op_queue.empty():
            op = op_queue.get_nowait()
            operations_count += 1
            logger.info(f"[Excel] Op #{operations_count}: {op.get('action', '?')} on {op.get('sheet', '?')}")
            if on_event:
                await on_event({"type": "operation", **op})

    # ── Main streaming loop with summary timeout ──

    drain_task = None  # Initialize before try block to avoid UnboundLocalError in finally
    result_streaming = None
    try:
        result_streaming = Runner.run_streamed(agent, user_content, **run_kwargs)
        if on_stream_created:
            await on_stream_created(result_streaming)
        final_text_parts: List[str] = []

        drain_task = asyncio.ensure_future(_drain_loop())

        turn_count = 0
        last_activity_time = time.time()
        text_output_start = 0.0      # when final text output started (not reasoning)
        thinking_start = 0.0         # when current reasoning-summary block started
        thinking_chars = 0           # chars accumulated in current reasoning-summary block
        last_tool_output_time = 0.0  # when the last tool output landed (silent-think gap)
        active_tool_count = 0        # mirrors frontend activeToolCallCount for status tracking
        ci_active_call_ids: set = set()  # call_ids of in-flight Code Interpreter calls
        current_status = "executing" # mirrors frontend AgentStatus
        status_start = time.time()   # when current status began
        SUMMARY_TIMEOUT = 120  # max seconds of final TEXT output (not reasoning) with no tool calls

        # Per-API-call token usage tracking (for dev export)
        api_call_count = 0
        cumulative_input_tokens = 0
        cumulative_output_tokens = 0
        stream_start_time = time.time()

        def _set_status(new_status: str) -> None:
            nonlocal current_status, status_start
            if new_status == current_status:
                return
            elapsed = round((time.time() - status_start) * 1000)
            logger.info(f"[Excel] Status: {current_status} → {new_status} ({elapsed}ms)")
            _tl({"event": "status", "from": current_status, "to": new_status, "duration_ms": elapsed})
            current_status = new_status
            status_start = time.time()

        async for ev in result_streaming.stream_events():
            # Check for cancellation (user clicked stop)
            if cancel_event and cancel_event.is_set():
                logger.info("[Excel] Cancellation signaled — cancelling stream")
                result_streaming.cancel()
                break

            # Timeout logic: only cut off if the model has been emitting final
            # text output (not reasoning/thinking) for SUMMARY_TIMEOUT seconds
            # without any tool calls.  Reasoning tokens mean it's still working.
            if text_output_start > 0 and (time.time() - text_output_start) > SUMMARY_TIMEOUT:
                logger.warning(f"[Excel] Summary timeout ({SUMMARY_TIMEOUT}s of text output) — breaking stream")
                break

            try:
                if ev.type == "raw_response_event":
                    data = getattr(ev, "data", None)
                    if data is None:
                        continue
                    event_type = getattr(data, "type", None)

                    if event_type == "response.output_text.delta":
                        delta = getattr(data, "delta", "")
                        if delta:
                            logger.info(f"[Excel] DEBUG text_delta: {len(delta)} chars, status={current_status}, text_output_start={'set' if text_output_start > 0 else 'unset'}")
                            final_text_parts.append(delta)
                            if text_output_start == 0.0:
                                text_output_start = time.time()
                                if active_tool_count == 0:
                                    _set_status("responding")
                                if last_tool_output_time > 0.0 and thinking_start == 0.0:
                                    silent_gap = time.time() - last_tool_output_time
                                    logger.info(f"[Excel] Silent thinking: {silent_gap:.1f}s → final output")
                                    _tl({"event": "silent_thinking_end", "duration_s": round(silent_gap, 3), "next": "output"})
                                    last_tool_output_time = 0.0
                                if thinking_start > 0.0:
                                    elapsed_thinking = time.time() - thinking_start
                                    logger.info(f"[Excel] Thinking done: {elapsed_thinking:.1f}s, ~{thinking_chars} chars → final output")
                                    _tl({"event": "thinking_end", "duration_s": round(elapsed_thinking, 3), "chars": thinking_chars, "next": "output"})
                                    thinking_start = 0.0
                                    thinking_chars = 0
                            if on_event:
                                await on_event({"type": "token", "text": delta})

                    elif event_type in (
                        "response.reasoning_summary_text.delta",
                        "response.reasoning_summary.text.delta",
                    ):
                        delta = getattr(data, "delta", "")
                        if delta:
                            last_activity_time = time.time()  # reasoning = still working
                            if thinking_start == 0.0:
                                thinking_start = time.time()
                                if last_tool_output_time > 0.0:
                                    silent_gap = time.time() - last_tool_output_time
                                    logger.info(f"[Excel] Silent thinking: {silent_gap:.1f}s → reasoning started")
                                    _tl({"event": "silent_thinking_end", "duration_s": round(silent_gap, 3), "next": "reasoning"})
                                    last_tool_output_time = 0.0
                                _set_status("thinking")
                                logger.info("[Excel] Thinking started")
                                _tl({"event": "thinking_start"})
                            thinking_chars += len(delta)
                            if on_event:
                                await on_event({"type": "thinking", "text": delta})

                    elif event_type == "response.completed":
                        # Extract per-API-call token usage from response.completed events
                        response_obj = getattr(data, "response", None)
                        usage = getattr(response_obj, "usage", None) if response_obj else getattr(data, "usage", None)
                        if usage:
                            input_tk = getattr(usage, "input_tokens", 0) or 0
                            output_tk = getattr(usage, "output_tokens", 0) or 0
                            cached_tk = 0
                            input_details = getattr(usage, "input_tokens_details", None)
                            if input_details:
                                cached_tk = getattr(input_details, "cached_tokens", 0) or 0

                            api_call_count += 1
                            cumulative_input_tokens += input_tk
                            cumulative_output_tokens += output_tk
                            now = time.time()
                            elapsed_min = (now - stream_start_time) / 60.0
                            tokens_per_min = round(cumulative_input_tokens / elapsed_min) if elapsed_min > 0.01 else 0

                            logger.info(
                                f"[Excel] API call #{api_call_count}: {input_tk:,} in / {output_tk:,} out "
                                f"(cached: {cached_tk:,}) | cumulative: {cumulative_input_tokens:,} in | "
                                f"rate: {tokens_per_min:,}/min"
                            )
                            _tl({
                                "event": "api_usage",
                                "index": api_call_count - 1,
                                "input_tokens": input_tk,
                                "output_tokens": output_tk,
                                "cached_tokens": cached_tk,
                                "cumulative_input_tokens": cumulative_input_tokens,
                                "tokens_per_min": tokens_per_min,
                            })
                            if on_event:
                                await on_event({
                                    "type": "api_usage",
                                    "index": api_call_count - 1,
                                    "timestamp": round(now * 1000),
                                    "input_tokens": input_tk,
                                    "output_tokens": output_tk,
                                    "cached_tokens": cached_tk,
                                    "cumulative_input_tokens": cumulative_input_tokens,
                                    "tokens_per_min": tokens_per_min,
                                })

                    elif event_type in ("response.incomplete", "response.failed"):
                        # Log WHY the API stopped — this is the smoking gun
                        response_obj = getattr(data, "response", None)
                        status = getattr(response_obj, "status", "unknown") if response_obj else "unknown"
                        incomplete_details = getattr(response_obj, "incomplete_details", None) if response_obj else None
                        reason = getattr(incomplete_details, "reason", None) if incomplete_details else None
                        resp_id = getattr(response_obj, "id", None) if response_obj else None
                        logger.warning(
                            f"[Excel] Response {event_type}: status={status}, reason={reason}, "
                            f"response_id={resp_id}, details={incomplete_details}"
                        )
                        _tl({
                            "event": "response_terminal",
                            "type": event_type,
                            "status": status,
                            "reason": reason,
                            "response_id": resp_id,
                        })

                    elif event_type == "response.code_interpreter_call.in_progress":
                        ci_call_id = getattr(data, "item_id", None) or getattr(data, "call_id", None)
                        if ci_call_id:
                            ci_active_call_ids.add(ci_call_id)
                            active_tool_count += 1
                            _set_status("executing")
                            turn_count += 1
                            last_activity_time = time.time()
                            text_output_start = 0.0
                            logger.info(f"[Excel] Turn {turn_count}: code_interpreter started (call_id={ci_call_id})")
                            _tl({"event": "tool_call", "turn": turn_count, "tool": "code_interpreter", "call_id": ci_call_id})
                            if on_event:
                                await on_event({"type": "tool_call", "tool": "code_interpreter", "call_id": ci_call_id})

                    elif event_type == "response.code_interpreter_call_code.delta":
                        delta = getattr(data, "delta", "")
                        ci_call_id = getattr(data, "item_id", None) or getattr(data, "call_id", None)
                        if delta and on_event:
                            await on_event({"type": "ci_code_delta", "delta": delta, "call_id": ci_call_id})

                    elif event_type == "response.code_interpreter_call.interpreting":
                        ci_call_id = getattr(data, "item_id", None) or getattr(data, "call_id", None)
                        if on_event:
                            await on_event({"type": "ci_interpreting", "call_id": ci_call_id})

                    elif event_type == "response.code_interpreter_call.completed":
                        ci_call_id = getattr(data, "item_id", None) or getattr(data, "call_id", None)
                        # Note: CI outputs are not available during streaming (API limitation).
                        # The model sees them internally but they're not exposed to us.
                        active_tool_count = max(0, active_tool_count - 1)
                        last_tool_output_time = time.time()
                        last_activity_time = time.time()
                        if active_tool_count == 0:
                            _set_status("thinking")
                            _tl({"event": "silent_thinking_start"})
                        if ci_call_id:
                            ci_active_call_ids.discard(ci_call_id)
                            emitted_call_ids.add(ci_call_id)
                            logger.info(f"[Excel] code_interpreter completed (call_id={ci_call_id})")
                            _tl({"event": "tool_done", "call_id": ci_call_id})
                            # Send tool_done to mark item as "done" in UI (output empty here,
                            # will be backfilled from run_item if available)
                            if on_event:
                                await on_event({"type": "tool_done", "output": "", "call_id": ci_call_id})

                    elif event_type == "response.output_item.done":
                        # With response_include=["code_interpreter_call.outputs"],
                        # CI outputs should now be populated here
                        item = getattr(data, "item", None)
                        if item and getattr(item, "type", "") == "code_interpreter_call":
                            ci_item_id = getattr(item, "id", None)
                            ci_outputs = getattr(item, "outputs", None) or []
                            output_text = ""
                            for out in ci_outputs:
                                out_type = getattr(out, "type", "")
                                if out_type == "logs":
                                    output_text = getattr(out, "logs", "") or ""
                                    break
                                elif out_type == "text" and not output_text:
                                    output_text = getattr(out, "text", "") or ""
                            _ci_log(f"output_item.done: id={ci_item_id}, outputs={len(ci_outputs)}, text_len={len(output_text)}, preview={output_text[:200]!r}")
                            if output_text and ci_item_id and on_event:
                                await on_event({
                                    "type": "tool_done",
                                    "output": output_text[:2500],
                                    "call_id": ci_item_id,
                                    "result": {"output": output_text},
                                })

                    else:
                        logger.info(f"[Excel] raw_response_event: {event_type} | status={current_status} text_start={'set' if text_output_start > 0 else 'unset'} tools={active_tool_count}")
                        _tl({"event": "raw", "type": event_type})
                        # Keepalive during "responding" = text stopped, model generating
                        # tool calls server-side. Emit thinking event so frontend transitions.
                        if event_type == "keepalive" and current_status == "responding" and text_output_start > 0:
                            text_output_start = 0.0
                            _set_status("thinking")
                            if on_event:
                                await on_event({"type": "thinking", "text": ""})

                elif ev.type == "run_item_stream_event":
                    item = getattr(ev, "item", None)
                    if item is None:
                        continue
                    item_type = getattr(item, "type", "")
                    logger.info(f"[Excel] DEBUG run_item: type={item_type} status={current_status} text_start={'set' if text_output_start > 0 else 'unset'}")

                    if item_type in ("tool_call_item", "function_call_item"):
                        call_id = _extract_call_id(item)
                        # Code Interpreter items — extract output from run item (SDK has it here)
                        if call_id and call_id.startswith("ci_"):
                            raw_item = getattr(item, "raw_item", item)
                            ri_outputs = getattr(raw_item, "outputs", None)
                            _ci_log(f"RUN_ITEM CI: id={call_id}, raw_item type={type(raw_item).__name__}, outputs={ri_outputs!r:.500}")
                            if ri_outputs and on_event:
                                ci_text = ""
                                for o in ri_outputs:
                                    o_type = getattr(o, "type", "")
                                    if o_type == "logs":
                                        ci_text = getattr(o, "logs", "") or ""
                                        break
                                    elif o_type == "text" and not ci_text:
                                        ci_text = getattr(o, "text", "") or ""
                                if ci_text:
                                    _ci_log(f"RUN_ITEM CI output FOUND: id={call_id}, len={len(ci_text)}, preview={ci_text[:300]!r}")
                                    await on_event({
                                        "type": "tool_done",
                                        "output": ci_text[:2500],
                                        "call_id": call_id,
                                        "result": {"output": ci_text},
                                    })
                            continue
                        tool_name = _extract_tool_name(item)
                        tool_args = _extract_tool_arguments(item)
                        turn_count += 1
                        last_activity_time = time.time()
                        text_output_start = 0.0  # reset — new tool call means not done yet
                        if last_tool_output_time > 0.0 and thinking_start == 0.0:
                            silent_gap = time.time() - last_tool_output_time
                            logger.info(f"[Excel] Silent thinking: {silent_gap:.1f}s → {tool_name}")
                            _tl({"event": "silent_thinking_end", "duration_s": round(silent_gap, 3), "next": tool_name})
                        last_tool_output_time = 0.0
                        if thinking_start > 0.0:
                            elapsed_thinking = time.time() - thinking_start
                            logger.info(f"[Excel] Thinking done: {elapsed_thinking:.1f}s, ~{thinking_chars} chars → {tool_name}")
                            _tl({"event": "thinking_end", "duration_s": round(elapsed_thinking, 3), "chars": thinking_chars, "next": tool_name})
                            thinking_start = 0.0
                            thinking_chars = 0

                        # Enqueue call_id (FIFO) for Excel write tools only
                        set_current_call_id(call_id, request_id, tool_name)
                        # Track call_id for real-time hook correlation
                        if call_id:
                            tool_call_id_map.setdefault(tool_name, deque()).append(call_id)

                        active_tool_count += 1
                        _set_status("executing")
                        logger.info(f"[Excel] Turn {turn_count}: calling {tool_name} (call_id={call_id})")
                        _tl({"event": "tool_call", "turn": turn_count, "tool": tool_name, "call_id": call_id})
                        if on_event:
                            event_data = {"type": "tool_call", "tool": tool_name}
                            if tool_args:
                                event_data["parameters"] = tool_args
                            if call_id:
                                event_data["call_id"] = call_id
                            await on_event(event_data)

                    elif item_type in ("tool_call_output_item", "function_call_output_item"):
                        output_call_id = _extract_call_id(item)
                        last_activity_time = time.time()
                        last_tool_output_time = time.time()
                        text_output_start = 0.0  # reset — tool just returned, more calls may follow
                        _tl({"event": "tool_done", "call_id": output_call_id})
                        active_tool_count = max(0, active_tool_count - 1)
                        if active_tool_count == 0:
                            _set_status("thinking")
                            logger.info("[Excel] Silent thinking started")
                            _tl({"event": "silent_thinking_start"})
                        # Skip if already emitted in real-time by on_tool_end hook
                        if output_call_id and output_call_id in emitted_call_ids:
                            emitted_call_ids.discard(output_call_id)
                            continue
                        output_val = getattr(item, "output", None)
                        output_str = str(output_val)[:2500] if output_val else ""
                        result_obj = _parse_tool_result(output_val)
                        if on_event:
                            event_data = {"type": "tool_done", "output": output_str}
                            if result_obj:
                                event_data["result"] = result_obj
                            if output_call_id:
                                event_data["call_id"] = output_call_id
                            await on_event(event_data)

            except Exception as e:
                logger.debug(f"[Excel] Stream event error: {e}")

        drain_done = True
        await drain_task

        # ── Post-stream diagnostic: check if the API finished server-side ──
        try:
            if result_streaming:
                _resp = getattr(result_streaming, "response", None)
                _status = getattr(_resp, "status", None) if _resp else None
                _resp_id = getattr(_resp, "id", None) if _resp else None
                _incomplete = getattr(_resp, "incomplete_details", None) if _resp else None
                _reason = getattr(_incomplete, "reason", None) if _incomplete else None
                _output = getattr(_resp, "output", []) if _resp else []
                _output_count = len(_output) if _output else 0
                logger.info(
                    f"[Excel] Post-stream diagnostic: status={_status}, response_id={_resp_id}, "
                    f"reason={_reason}, output_items={_output_count}, "
                    f"is_complete={getattr(result_streaming, 'is_complete', '?')}"
                )
                _tl({
                    "event": "post_stream_diagnostic",
                    "status": _status,
                    "response_id": _resp_id,
                    "reason": _reason,
                    "output_items": _output_count,
                    "is_complete": getattr(result_streaming, "is_complete", None),
                })
                # Note: CI outputs are always None in streaming responses (OpenAI API limitation).
        except Exception as diag_err:
            logger.debug(f"[Excel] Post-stream diagnostic failed: {diag_err}")

        summary = "".join(final_text_parts).strip()
        if not summary:
            summary = getattr(result_streaming, "final_output", "") or ""

    except asyncio.CancelledError:
        # User clicked stop — clean exit with partial results
        logger.info("[Excel] Execution cancelled by user")
        summary = "".join(final_text_parts).strip() if final_text_parts else "Cancelled by user."
    except Exception as exc:
        from agents.exceptions import ModelBehaviorError
        if isinstance(exc, ModelBehaviorError):
            summary = "".join(final_text_parts).strip()
            logger.warning(f"[Excel] Model did not produce final response. Returning partial result ({len(summary)} chars).")
        elif _is_content_policy_error(exc):
            # OpenAI content filter rejected the prompt — typically after many
            # tool-call rounds accumulate dense financial data in the
            # conversation history.  Return partial results (the sheets already
            # built) instead of crashing the entire request.
            summary = "".join(final_text_parts).strip() if final_text_parts else ""
            partial_note = (
                f"Completed {operations_count} operations before the model's content filter "
                f"interrupted execution. The sheets created so far should be intact."
            )
            summary = f"{summary}\n\n{partial_note}".strip() if summary else partial_note
            logger.warning(
                "[Excel] Content policy error after %d ops / %d turns: %s",
                operations_count, turn_count, exc,
            )
            _tl({"event": "content_policy_error", "ops": operations_count, "turns": turn_count})
            if on_event:
                try:
                    await on_event({"type": "warning", "code": "content_policy", "message": partial_note})
                except Exception:
                    pass
        else:
            raise
    finally:
        drain_done = True

        # Cancel SDK streaming run to stop in-flight MCP tool calls
        if result_streaming and not getattr(result_streaming, "is_complete", True):
            result_streaming.cancel()

        # Cancel drain task to prevent resource leaks
        if drain_task and not drain_task.done():
            drain_task.cancel()
            try:
                await drain_task
            except asyncio.CancelledError:
                pass
        
        set_tracing_disabled(False)
        set_op_queue(None)
        if request_id:
            cancel_all_pending_reads(request_id)
            cleanup_pending_reads(request_id)
            cancel_all_pending_approvals(request_id)
            cleanup_pending_approvals(request_id)

        agent.tools = orig_tools
        agent.instructions = orig_instructions
        agent.hooks = orig_hooks

    elapsed = time.time() - t0
    logger.info(f"[Excel] Done: {operations_count} ops, {turn_count} turns, {elapsed:.1f}s")
    _tl({"event": "request_end", "request_id": request_id, "ops": operations_count, "turns": turn_count, "elapsed_s": round(elapsed, 3)})

    # Cost tracking (estimates based on March 2026 OpenAI pricing)
    from core.config import config
    if config.enable_cost_tracking:
        try:
            from core.ai.cost_tracker import cost_tracker
            cost_tracker.record_from_stream(
                result_streaming, "SpreadsheetAgent", selected_model, request_id or "excel",
                elapsed_s=elapsed
            )
        except Exception as exc:
            logger.warning(f"[Excel] Cost tracking failed: {exc}")

    return {
        "status": "ok",
        "summary": summary if summary else f"Completed {operations_count} operations.",
        "operations_count": operations_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Name Extraction
# ═══════════════════════════════════════════════════════════════════════════════


def _extract_tool_name(item: Any) -> str:
    """Robustly extract tool name from an Agents SDK stream item."""
    for attr in ("name", "tool_name"):
        val = getattr(item, attr, None)
        if val and isinstance(val, str):
            return val

    raw_item = getattr(item, "raw_item", None)
    if raw_item:
        val = getattr(raw_item, "name", None)
        if val and isinstance(val, str):
            return val
        fn = getattr(raw_item, "function", None)
        if fn:
            name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", None)
            if name and isinstance(name, str):
                return name

    item_repr = repr(item)
    match = re.search(r"name='([^']+)'", item_repr)
    if match:
        return match.group(1)

    return "tool"


def _extract_call_id(item: Any) -> Optional[str]:
    """Extract call_id from an Agents SDK stream item for correlation."""
    # Try direct attribute
    for attr in ("call_id", "id", "item_id"):
        val = getattr(item, attr, None)
        if val and isinstance(val, str):
            return val

    # Try raw_item
    raw_item = getattr(item, "raw_item", None)
    if raw_item:
        for attr in ("call_id", "id"):
            val = getattr(raw_item, attr, None)
            if val and isinstance(val, str):
                return val
        # Handle dict raw_item (e.g., ToolCallOutputItem where raw_item is a plain dict)
        if isinstance(raw_item, dict):
            for key in ("call_id", "id"):
                val = raw_item.get(key)
                if val and isinstance(val, str):
                    return val

    return None


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


def _parse_tool_result(output: Any) -> Optional[Dict[str, Any]]:
    """Parse tool output into a structured result dict."""
    if output is None:
        return None
    if isinstance(output, dict):
        return output
    if isinstance(output, list):
        return {"items": output}
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        except (json.JSONDecodeError, ValueError):
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy (backward compat)
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_plan_json(raw: str) -> Dict[str, Any]:
    """Parse JSON from agent output. Legacy — used by validate_step."""
    if not raw or not raw.strip():
        return {"summary": "Empty response", "steps": []}
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    for pattern in [r"```json\s*\n(.*)\n\s*```", r"```\s*\n(.*)\n\s*```"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1).strip())
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                continue
    return {"summary": text[:500], "steps": [], "parse_error": True}


async def validate_step(
    step: Dict[str, Any],
    actual: Dict[str, Any],
    context_chunks: List[Dict[str, Any]],
    attempt: int = 0,
) -> Dict[str, Any]:
    """Validate a completed step (legacy)."""
    agent = await _get_agent()
    user_content = f"""Validate this Excel operation. Compare planned vs actual.
Planned: {json.dumps(step, indent=2, default=str)[:3000]}
Actual: {json.dumps(actual, indent=2, default=str)[:3000]}
Attempt: {attempt}
Respond with JSON: {{"passed": true/false, "reason": "...", "corrected_operations": null or [...]}}"""

    import time as _time
    _t0 = _time.time()
    result = await Runner.run(agent, user_content)
    _elapsed = _time.time() - _t0
    
    # Cost tracking
    from core.config import config
    if config.enable_cost_tracking:
        try:
            from core.ai.cost_tracker import cost_tracker
            cost_tracker.record_from_result(result, "SpreadsheetAgent.validate", None, "validate", elapsed_s=_elapsed)
        except Exception as exc:
            logger.warning(f"[Excel] Cost tracking failed: {exc}")
    
    validation = _parse_plan_json(result.final_output or "")
    validation.setdefault("passed", True)
    validation.setdefault("reason", "")
    logger.info(f"Validation attempt {attempt}: passed={validation['passed']}")
    return validation
