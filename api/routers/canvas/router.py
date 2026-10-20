"""Canvas Analysis API Router.

Generic tool execution pipeline for Canvas Explorer.
Tools are registered and executed dynamically by ID.

Graph structure is GENERIC for all tools:
- DATA: input (portfolio, tickers)
- SYSTEM: external API (market data)
- TRUTH: derived data (returns, correlations)
- ACTION: the tool itself (any tool is just an action)
- OUTPUT: results (charts, stats, metrics)

The Canvas router builds the graph generically - tools don't know about graphs.
"""

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Callable, Awaitable, List, Optional, Tuple, AsyncIterator
from datetime import datetime
import asyncio
import json
import logging
import uuid
from .primitives import ProcessGraphBuilder
from .tools.risk.montecarlo import execute_monte_carlo
from .tools.risk.barra import execute_barra_factors
from .tools.risk.var import execute_var
from .tools.risk.systemic import execute_systemic_risk
from .tools.risk.optimization import execute_optimization
from .tools.risk.stresstest import execute_stress_test
from .tools.risk.drawdown import execute_drawdown
from .tools.risk.hedge import execute_hedge
from .tools.risk.network import execute_network_risk
from .tools.risk.implied_corr import execute_implied_corr
from .tools.risk.fft_denoise import execute_fft_denoise
from .tools.risk.rolling_corr import execute_rolling_corr
from .tools.quant.volsurface import execute_vol_surface
from .tools.quant.correlation import execute_correlation_matrix
from .tools.quant.pca import execute_pca_analysis
from .tools.quant.cointegration import execute_cointegration
from .tools.quant.arima import execute_arima_forecast
from .tools.quant.greeks_surface import execute_greeks_surface
from .tools.quant.corr_swap import execute_corr_swap
from .tools.quant.cross_greeks import execute_cross_greeks
from .tools.quant.greek_exposure import execute_greek_exposure
from .tools.quant.hedge_ratio import execute_hedge_ratio
from .tools.quant.dynamic_hedge import execute_dynamic_hedge
from .tools.quant.delta_hedge import execute_delta_hedge
from .tools.quant.feature_importance import execute_feature_importance
from .tools.quant.mean_reversion import execute_mean_reversion
from .tools.quant.iv_rv_screener import execute_iv_rv_screener
from .tools.quant.squeeze_detector import execute_squeeze_detector
from .tools.valuation.reverse_dcf import execute_reverse_dcf
from .tools.valuation.comps import execute_comps
from .tools.valuation.epv import execute_epv
from .tools.valuation.rim import execute_rim
from .tools.valuation.dcf_monte_carlo import execute_dcf_monte_carlo
from .tools.valuation.dcf_traditional import execute_dcf_traditional
from .tools.sentiment.finbert import execute_finbert_sentiment
from .tools.quant.sector_rotation import execute_sector_rotation
from .tools.quant.gex import execute_gex
from .tools.quant.instanton import execute_instanton
from .tools.quant.earnings_pattern import execute_earnings_pattern
from .tools.quant.vanna_charm import execute_vanna_charm
from .tools.quant.hedge_path import execute_hedge_path
from .tools.quant.recession_field import execute_recession_field
from .tools.quant.geodesic import execute_geodesic
from .tools.quant.herding import execute_herding
from .tools.quant.option_pricing import execute_option_pricing
from .tools.quant.nope import execute_nope
from .tools.structuring.dispersion import execute_dispersion
from .tools.structuring.var_swap import execute_var_swap
from .tools.structuring.exotic_pricing import execute_exotic_pricing
from .tools.structuring.swaption import execute_swaption
from .tools.structuring.irs import execute_irs
from .tools.structuring.cds import execute_cds
from .tools.alternatives.commodity_ratio import execute_commodity_ratio
from .tools.alternatives.commodity_momentum import execute_commodity_momentum
from .tools.alternatives.commodity_seasonal import execute_commodity_seasonal
from .tools.alternatives.fx_carry import execute_fx_carry
from .tools.alternatives.crypto_beta import execute_crypto_beta
from .tools.quant.arimax import execute_arimax
from .tools.quant.dealer_gamma import execute_dealer_gamma
from .tools.quant.confluence import execute_confluence

logger = logging.getLogger(__name__)

STREAM_TIMEOUT_SECONDS = 300

# Canvas chat stream registry — tracks active SSE streams for cancellation
_canvas_streams: Dict[str, Dict[str, Any]] = {}
_canvas_streams_lock = asyncio.Lock()


async def register_canvas_stream(session_id: str, user_id: str) -> asyncio.Event:
    cancel_event = asyncio.Event()
    async with _canvas_streams_lock:
        _canvas_streams[session_id] = {
            "user_id": user_id,
            "cancel_event": cancel_event,
            "task": None,
        }
    logger.info(f"Canvas stream registered: session={session_id} user={user_id}")
    return cancel_event


async def set_canvas_stream_task(session_id: str, task: asyncio.Task) -> None:
    async with _canvas_streams_lock:
        entry = _canvas_streams.get(session_id)
        if entry:
            entry["task"] = task


async def unregister_canvas_stream(session_id: str) -> None:
    async with _canvas_streams_lock:
        _canvas_streams.pop(session_id, None)


async def cancel_canvas_stream(session_id: str, user_id: str) -> bool:
    async with _canvas_streams_lock:
        entry = _canvas_streams.get(session_id)
        if not entry:
            return False
        if entry["user_id"] != user_id:
            return False
        entry["cancel_event"].set()
        task = entry.get("task")
        if task and not task.done():
            task.cancel()
        return True


async def run_canvas_stream(
    *,
    queue: asyncio.Queue,
    cancel_event: asyncio.Event,
    user_id: str,
    org_id: str,
    message: str,
    process_id: Optional[str],
    thread_id: Optional[str],
    selected_model: Optional[str],
    data_context: Optional[str],
    session_id: str,
) -> None:
    """Background task that runs the canvas agent and puts events on the queue.

    Decoupled from the SSE generator so that client disconnects do not kill
    the save logic.  The generator only reads from ``queue`` and yields.
    A ``None`` sentinel signals the generator that no more events will come.
    """
    from core.utils.context_utils import set_cancel_event, reset_cancel_event

    content_chunks: list[str] = []
    saved_message_id = None
    active_thread_id = None
    process_context = None
    cancel_token = None

    async def enqueue(payload: dict):
        await queue.put(payload)

    try:
        from core.database.postgres_client import get_postgres_client
        pg = await get_postgres_client()

        if process_id:
            process_row = await pg.get_canvas_process(user_id=user_id, process_id=process_id, org_id=org_id)
            if process_row:
                process_context = {
                    "id": str(process_row.get("id")),
                    "name": process_row.get("name"),
                    "tool_id": process_row.get("tool_id"),
                    "tickers": process_row.get("tickers", []),
                    "weights": process_row.get("weights", []),
                    "metrics": process_row.get("metrics", {}),
                    "metric_cards": process_row.get("metrics", {}).get("_metric_cards", []),
                    "stats_table": process_row.get("stats_table", []),
                    "params": process_row.get("params", {}),
                    "hmm_enabled": process_row.get("hmm_enabled", False),
                    "current_regime": process_row.get("current_regime"),
                }

        from core.agents.CanvasAgent import create_canvas_agent
        from agents import SQLiteSession
        from core.ai.langgraph_utils import execute_with_stream, execute_with_retry
        from core.config import get_config
        from core.ai.utils.message_compactor import get_provider_from_model
        from api.orchestrator import get_v6_orchestrator

        config = get_config()
        model_choice = selected_model or config.agent_model

        orchestrator = get_v6_orchestrator()
        market_server = getattr(orchestrator, 'fmp_market_server', None) or getattr(orchestrator, 'yfinance_server', None)
        economic_server = getattr(orchestrator, 'economic_server', None)
        alternatives_server = getattr(orchestrator, 'fmp_alternatives_server', None)

        parsed_data_context = None
        if data_context:
            try:
                parsed_data_context = json.loads(data_context)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse data_context: {str(data_context)[:100]}")

        canvas_agent = create_canvas_agent(
            process_context=process_context,
            data_context=parsed_data_context,
            model=model_choice,
            user_id=user_id,
            org_id=org_id,
            market_server=market_server,
            economic_server=economic_server,
            alternatives_server=alternatives_server,
        )

        provider = get_provider_from_model(model_choice) if model_choice else "openai"
        can_stream = provider in {"openai"}

        def to_uuid(value) -> uuid.UUID:
            if value is None:
                raise ValueError("UUID value cannot be None")
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))

        # ── Thread + user message ────────────────────────────────────
        is_first_message = False
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            if thread_id:
                try:
                    thread_uuid = to_uuid(thread_id)
                    thread_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM canvas_chat_threads WHERE id = $1 AND user_id = $2)",
                        thread_uuid, user_id,
                    )
                    if thread_exists:
                        active_thread_id = thread_uuid
                except (ValueError, TypeError):
                    pass

            if not active_thread_id:
                active_thread_id = await conn.fetchval("""
                    INSERT INTO canvas_chat_threads (user_id, org_id, title, last_process_id, last_tool_id)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, user_id, org_id or '', "New Chat",
                uuid.UUID(process_id) if process_id else None,
                process_context.get('tool_id') if process_context else None)

            msg_count = await conn.fetchval(
                "SELECT COUNT(*) FROM canvas_chat_messages WHERE thread_id = $1 AND user_id = $2",
                to_uuid(active_thread_id), user_id,
            )
            is_first_message = msg_count == 0

            await conn.execute("""
                INSERT INTO canvas_chat_messages (thread_id, user_id, org_id, role, content, process_id, tool_id)
                VALUES ($1, $2, $3, 'user', $4, $5, $6)
            """, to_uuid(active_thread_id), user_id, org_id or '', message,
            uuid.UUID(process_id) if process_id else None,
            process_context.get('tool_id') if process_context else None)

        # Start AI title generation in background for first message
        title_task = None
        if is_first_message:
            async def _generate_title():
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI()
                    resp = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": f"Generate a concise 3-8 word title for this chat message. No quotes:\n\n{message[:500]}"}],
                        max_tokens=30,
                        temperature=0.3,
                    )
                    title = resp.choices[0].message.content.strip().strip("'\"")
                    if len(title) > 100:
                        title = title[:97] + "..."
                    async with pg.acquire_with_org_context(user_id, org_id) as conn:
                        await conn.execute(
                            "UPDATE canvas_chat_threads SET title = $1 WHERE id = $2 AND user_id = $3",
                            title, to_uuid(active_thread_id), user_id,
                        )
                    return title
                except Exception as e:
                    logger.warning(f"Title generation failed: {e}")
                    return None
            title_task = asyncio.create_task(_generate_title())

        await enqueue({"type": "thread_id", "thread_id": str(active_thread_id)})

        sqlite_session = SQLiteSession(str(active_thread_id), config.openai_sessions_db_path)

        # ── Callbacks ────────────────────────────────────────────────
        async def on_token(content: str):
            if not content:
                return
            content_chunks.append(content)
            await enqueue({"type": "content", "content": content})

        async def on_event(event: dict):
            event_type = event.get("type")

            content_event_types = {
                "output_text.delta", "response.output_text.delta",
                "output_text.done", "response.output_text.done",
            }
            if event_type in content_event_types:
                return

            if event_type in ("tool_call.started", "response.tool_call.started"):
                event_data = {
                    "item_id": event.get("item_id"),
                    "tool_name": event.get("tool_name"),
                    "name": event.get("tool_name"),
                }
                if event.get("arguments"):
                    event_data["arguments"] = event["arguments"]
                payload = {"type": "tool_call_started", "event": event_data}
            elif event_type in ("tool_call.output", "response.tool_call.output"):
                payload = {
                    "type": "tool_call_output",
                    "event": {"item_id": event.get("item_id"), "output": event.get("output")},
                }
            elif event_type in ("agent_action", "agent_error"):
                payload = event
            else:
                payload = {"type": event_type, "event": event}

            await enqueue(payload)

        # ── Set cooperative cancel flag ──────────────────────────────
        cancel_token = set_cancel_event(cancel_event)

        # ── Execute agent (with timeout) ─────────────────────────────
        async def _run_agent():
            if can_stream:
                await execute_with_stream(
                    agent=canvas_agent,
                    query=message,
                    session=sqlite_session,
                    on_token=on_token,
                    on_event=on_event,
                    max_turns=30,
                    agent_name="canvas",
                    selected_model=model_choice,
                )
            else:
                result = await execute_with_retry(
                    canvas_agent, message, session=None,
                    max_turns=30, agent_name="canvas", selected_model=model_choice,
                )
                final_text = getattr(result, "final_output", None) or str(result)
                content_chunks.append(final_text)
                await enqueue({"type": "content", "content": final_text})

        await asyncio.wait_for(_run_agent(), timeout=STREAM_TIMEOUT_SECONDS)

        # ── Normal completion: save + done event ─────────────────────
        full_response = "".join(content_chunks)
        if full_response:
            result_row = await pg.save_canvas_chat_message(
                thread_id=str(active_thread_id),
                user_id=user_id, org_id=org_id,
                role="assistant", content=full_response,
                process_id=process_id,
                tool_id=process_context.get("tool_id") if process_context else None,
            )
            saved_message_id = str(result_row["id"]) if result_row else None
            logger.info(f"Canvas chat saved: id={saved_message_id}, thread={active_thread_id}")

        if title_task:
            try:
                new_title = await asyncio.wait_for(title_task, timeout=5.0)
                if new_title:
                    await enqueue({"type": "title_update", "title": new_title, "thread_id": str(active_thread_id)})
            except asyncio.TimeoutError:
                logger.warning("Title generation timed out")
            except Exception as e:
                logger.warning(f"Title generation failed: {e}")

        done_payload: Dict[str, Any] = {"type": "done", "full_content": full_response, "thread_id": str(active_thread_id)}
        if saved_message_id:
            done_payload["message_id"] = saved_message_id
        await enqueue(done_payload)

    except asyncio.CancelledError:
        logger.info("Canvas chat cancelled — frontend will save")
        saved_message_id = "cancel-frontend"
        await enqueue({"type": "cancelled"})

    except asyncio.TimeoutError:
        logger.warning(f"Canvas chat timed out after {STREAM_TIMEOUT_SECONDS}s: session={session_id}")
        await enqueue({"type": "error", "error": f"Stream timed out after {STREAM_TIMEOUT_SECONDS} seconds", "fatal": True})

    except Exception as e:
        logger.error(f"Canvas chat background task error: {e}", exc_info=True)
        await enqueue({"type": "error", "error": str(e), "fatal": True})

    finally:
        if cancel_token is not None:
            reset_cancel_event(cancel_token)
        if not saved_message_id and content_chunks and active_thread_id:
            partial = "".join(content_chunks)
            if partial.strip():
                try:
                    from core.database.postgres_client import get_postgres_client
                    pg = await get_postgres_client()
                    await pg.save_canvas_chat_message(
                        thread_id=str(active_thread_id),
                        user_id=user_id, org_id=org_id,
                        role="assistant", content=partial,
                        process_id=process_id,
                        tool_id=process_context.get("tool_id") if process_context else None,
                    )
                    logger.info(f"Canvas chat fallback save: thread={active_thread_id}")
                except Exception:
                    logger.error("Canvas chat fallback save failed", exc_info=True)
        await unregister_canvas_stream(session_id)
        await queue.put(None)


def build_process_graph(
    tool_name: str,
    tickers: List[str],
    has_charts: bool = False,
    has_stats: bool = False,
    has_metrics: bool = False,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Build a generic process graph for ANY tool.

    All tools follow the same pattern:
    Data → System → Truth → Action → Outputs

    The only variable is the tool name in the Action node.
    """
    builder = ProcessGraphBuilder()

    # Input data
    ticker_str = ", ".join(tickers[:3]) + ("..." if len(tickers) > 3 else "")
    builder.add_data(1, "Portfolio", ticker_str if tickers else "Input")

    # External system
    builder.add_system(1, "Market Data")

    # Derived truth
    builder.add_truth(1, "Historical Data")

    # The action (any tool)
    builder.add_action(1, tool_name)

    # Outputs - add based on what the tool produced
    output_idx = 1
    if has_charts:
        builder.add_output(output_idx, "Charts")
        output_idx += 1
    if has_stats:
        builder.add_output(output_idx, "Statistics")
        output_idx += 1
    if has_metrics:
        builder.add_output(output_idx, "Metrics")
        output_idx += 1

    # If no outputs detected, add a generic one
    if output_idx == 1:
        builder.add_output(1, "Results")
        output_idx = 2

    # Connect the flow
    builder.connect((1, 1), (5, 1))  # Data → System
    builder.connect((5, 1), (2, 1))  # System → Truth
    builder.connect((2, 1), (3, 1))  # Truth → Action

    # Action → all outputs
    for i in range(1, output_idx):
        builder.connect((3, 1), (4, i))

    return builder.build()

router = APIRouter(prefix="/api/canvas", tags=["canvas"])

# Include the data router for object registry endpoints
from .data_router import router as data_router
router.include_router(data_router)

# Include the pivot router for pivot table and statistical analysis
from .pivot_router import router as pivot_router
router.include_router(pivot_router)

# Include the chart router for chart analytics (regression, filtering)
from .chart_router import router as chart_router
router.include_router(chart_router)


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SaveProcessRequest(BaseModel):
    tool_id: str
    tickers: List[str] = []
    weights: List[float] = []
    metrics: Dict[str, Any] = {}
    metric_cards: List[Dict[str, Any]] = []  # Generic displayable metrics
    stats_table: List[Dict[str, Any]] = []
    charts: Dict[str, Any] = {}
    name: Optional[str] = None
    object_type: Optional[str] = None  # Object type from registry (equity, portfolio, crypto, etc.)
    hmm_enabled: bool = False
    current_regime: Optional[str] = None
    regime_params: Optional[Dict[str, Any]] = None
    graph_steps: Optional[List[Dict[str, Any]]] = None
    graph_edges: Optional[List[Dict[str, Any]]] = None
    params: Dict[str, Any] = {}  # Original run parameters for re-run
    process_type: str = "tool"  # 'tool' or 'data_workspace'
    config: Optional[Dict[str, Any]] = None  # Config for data_workspace


class UpdateProcessRequest(BaseModel):
    name: Optional[str] = None


class FullUpdateProcessRequest(BaseModel):
    """Full update for data workspace - same fields as SaveProcessRequest."""
    name: str
    tickers: List[str] = []
    params: Dict[str, Any] = {}
    config: Optional[Dict[str, Any]] = None


# =============================================================================
# TOOL REGISTRY
# =============================================================================

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_tool(
    tool_id: str,
    name: str,
    description: str,
    category: str,
    executor: Callable[..., Awaitable[Dict]],
    params_schema: Dict[str, Any],
):
    """Register a tool for Canvas execution.

    The frontend infers input type from params_schema:
    - Has portfolio_id + tickers array → portfolio picker + multi-ticker
    - Has only 'underlying' or 'ticker' string → single ticker input
    """
    TOOL_REGISTRY[tool_id] = {
        "id": tool_id,
        "name": name,
        "description": description,
        "category": category,
        "executor": executor,
        "params_schema": params_schema,
    }


# =============================================================================
# REGISTER TOOLS
# =============================================================================

register_tool(
    tool_id="monte_carlo",
    name="Monte Carlo Simulation",
    description="Portfolio risk simulation with price paths and VaR metrics",
    category="risk",
    executor=execute_monte_carlo,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "portfolio_value": {"type": "number", "default": 1000000, "min": 1000},
        "n_simulations": {"type": "number", "default": 1000, "min": 100, "max": 10000},
        "time_horizon": {"type": "number", "default": 252, "min": 21, "max": 504, "description": "Trading days"},
        "use_hmm": {"type": "boolean", "default": False, "description": "Use HMM regime switching"},
        "n_regimes": {"type": "number", "default": 3, "min": 2, "max": 5},
    },
)

register_tool(
    tool_id="barra_factors",
    name="Factor Analysis",
    description="Barra-style factor exposure and risk decomposition",
    category="risk",
    executor=execute_barra_factors,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "period": {"type": "string", "default": "1y", "enum": ["6mo", "1y", "2y"], "description": "Historical data period"},
        "factor_set": {"type": "string", "default": "default", "enum": ["default", "sector", "style", "comprehensive", "custom"], "description": "Factor ETF set to use"},
        "custom_factors": {
            "type": "object",
            "required": False,
            "description": "Custom factor ETFs mapping (e.g., {'SPY': 'Market', 'XLF': 'Financials'}). Only used when factor_set='custom'",
            "example": {"SPY": "Market", "QQQ": "Tech", "IWM": "SmallCap"},
        },
    },
)

register_tool(
    tool_id="vol_surface",
    name="Volatility Surface",
    description="3D implied volatility surface modeling with IV smile and term structure",
    category="quant",
    executor=execute_vol_surface,
    params_schema={
        # Single 'underlying' string field → frontend infers single_ticker input
        "underlying": {"type": "string", "required": False, "description": "Underlying ticker (e.g., AAPL, SPY)"},
        "grid_resolution": {"type": "number", "default": 30, "min": 10, "max": 50, "description": "Surface interpolation resolution"},
        "target_dte_for_smile": {"type": "number", "required": False, "description": "DTE for IV smile cross-section (~30 days default)"},
        "compute_analytics": {"type": "boolean", "default": False, "description": "Include ATM IV, skew, term slope analytics"},
        "include_realized_vol": {"type": "boolean", "default": True, "description": "Calculate realized vol for VRP"},
        "peer_tickers": {"type": "array", "items": "string", "required": False, "description": "Peers for cross-sectional ranking"},
    },
)

register_tool(
    tool_id="correlation_matrix",
    name="Correlation Matrix",
    description="Portfolio correlation analysis with heatmap, eigenvalue decomposition, and clustering",
    category="quant",
    executor=execute_correlation_matrix,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 2)"},
        "method": {"type": "string", "default": "pearson", "enum": ["pearson", "spearman", "kendall"], "description": "Correlation method"},
        "lookback_period": {"type": "number", "default": 252, "min": 30, "max": 756, "description": "Days of historical data"},
        "hierarchical_clustering": {"type": "boolean", "default": True, "description": "Perform hierarchical clustering"},
        "tail_dependence": {"type": "boolean", "default": False, "description": "Calculate tail dependence (extreme events)"},
    },
)

register_tool(
    tool_id="pca_analysis",
    name="PCA Analysis",
    description="Principal component analysis with eigen-portfolios and factor loadings",
    category="quant",
    executor=execute_pca_analysis,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 3)"},
        "n_components": {"type": "number", "required": False, "description": "Number of components (default: all)"},
        "period": {"type": "string", "default": "1Y", "enum": ["3M", "6M", "1Y", "2Y"], "description": "Historical period"},
        "normalize": {"type": "boolean", "default": True, "description": "Standardize returns before PCA"},
    },
)

register_tool(
    tool_id="var",
    name="Value at Risk",
    description="VaR analysis with parametric, historical, and Monte Carlo methods",
    category="risk",
    executor=execute_var,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "method": {"type": "string", "default": "all", "enum": ["parametric", "historical", "monte_carlo", "all"], "description": "VaR calculation method"},
        "confidence_levels": {"type": "array", "items": "number", "required": False, "description": "Confidence levels (default: [0.95, 0.99])"},
        "portfolio_value": {"type": "number", "default": 1000000, "min": 1000, "description": "Portfolio value in dollars"},
        "period": {"type": "string", "default": "1y", "enum": ["6mo", "1y", "2y"], "description": "Historical data period"},
    },
)

register_tool(
    tool_id="cointegration",
    name="Cointegration Analysis",
    description="Pairs trading cointegration tests with spread analysis and trading signals",
    category="quant",
    executor=execute_cointegration,
    params_schema={
        # No portfolio_id - cointegration is for specific ticker pairs, not portfolios
        "tickers": {"type": "array", "items": "string", "required": True, "description": "Stock tickers to test (min 2, e.g., GLD, GDX)"},
        "lookback_period": {"type": "number", "default": 252, "min": 60, "max": 756, "description": "Days of historical data"},
        "significance_level": {"type": "number", "default": 0.05, "min": 0.01, "max": 0.10, "description": "P-value threshold for significance"},
    },
)

register_tool(
    tool_id="arima_forecast",
    name="ARIMA Forecast",
    description="Time series price forecasting with confidence intervals using auto-ARIMA. The model uses (p,d,q) parameters: p=autoregressive lags, d=differencing order, q=moving average lags.",
    category="quant",
    executor=execute_arima_forecast,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to forecast (e.g., AAPL)"},
        "forecast_periods": {"type": "number", "default": 30, "min": 5, "max": 90, "description": "Number of days to forecast ahead"},
        "period": {"type": "string", "default": "1Y", "enum": ["6M", "1Y", "2Y", "5Y"], "description": "Historical data for training. Longer = more data but older patterns"},
        "arima_order": {"type": "string", "required": False, "description": "Manual ARIMA (p,d,q) order, e.g. '5,1,2'. p=AR lags (momentum memory), d=differencing (1=returns, 2=acceleration), q=MA lags (shock memory). Leave empty for auto-selection"},
        "seasonal": {"type": "boolean", "default": True, "description": "Enable SARIMA for recurring patterns (weekly, monthly cycles)"},
        "seasonal_period": {"type": "number", "default": 5, "min": 2, "max": 252, "description": "Cycle length: 5=weekly (Mon-Fri), 21=monthly, 63=quarterly, 252=yearly"},
        "max_p": {"type": "number", "default": 10, "min": 1, "max": 20, "description": "Max AR(p) order to search. Higher p captures longer momentum patterns but risks overfitting"},
        "max_q": {"type": "number", "default": 10, "min": 1, "max": 20, "description": "Max MA(q) order to search. Higher q captures longer shock effects but risks overfitting"},
        "stepwise": {"type": "boolean", "default": True, "description": "Stepwise=fast heuristic search, False=exhaustive (slower but may find better model)"},
    },
)

register_tool(
    tool_id="arimax",
    name="ARIMAX Macro Forecast",
    description="Multi-factor forecasting with macroeconomic indicators. Forecast stock prices or economic data (CPI, rates, GDP) using FRED macro drivers and options sentiment.",
    category="quant",
    executor=execute_arimax,
    params_schema={
        "forecast_mode": {
            "type": "string",
            "required": True,
            "enum": ["stock", "macro"],
            "description": "Choose what to forecast: Stock/ETF prices or Economic indicators"
        },
        "stock_symbol": {
            "type": "string",
            "required": False,
            "description": "Stock/ETF ticker to forecast (e.g., AAPL, SPY)"
        },
        "macro_indicator": {
            "type": "string",
            "required": False,
            "enum": [
                "CPIAUCSL", "CPILFESL", "PCEPI", "DGS10", "DGS2", "DGS30", "FEDFUNDS",
                "UNRATE", "ICSA", "PAYEMS", "GDPC1", "INDPRO", "RSXFS", "HOUST",
                "VIXCLS", "T10Y2Y", "T10Y3M", "BAMLH0A0HYM2", "DEXUSEU", "DEXJPUS",
                "DCOILWTICO", "GOLDAMGBD228NLBM", "M2SL", "WALCL"
            ],
            "description": "Economic indicator to forecast"
        },
        "forecast_periods": {
            "type": "number",
            "default": 30,
            "min": 7,
            "max": 180,
            "description": "Days ahead to forecast"
        },
        "period": {
            "type": "string",
            "default": "3Y",
            "enum": ["1Y", "2Y", "3Y", "5Y"],
            "description": "Historical data period for training"
        },
        "indicator_categories": {
            "type": "array",
            "items": "string",
            "default": ["rates", "inflation"],
            "enum": [
                "rates", "inflation", "employment", "growth",
                "financial_conditions", "commodities", "housing",
                "trade", "money_supply", "credit"
            ],
            "description": "Macro drivers to use as predictors"
        },
        "confidence_level": {
            "type": "number",
            "default": 0.95,
            "min": 0.80,
            "max": 0.99,
            "description": "Confidence interval level (0.95 = 95%)"
        },
        "max_indicators": {
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 8,
            "description": "Maximum macro indicators to include as exogenous variables"
        },
    },
)

register_tool(
    tool_id="dealer_gamma",
    name="Dealer Gamma Regime",
    description="Estimate dealer gamma positioning from observable price dynamics. Identifies whether dealers are SHORT gamma (trending/amplifying moves) or LONG gamma (mean-reverting/dampening moves) using autocorrelation or HMM analysis.",
    category="quant",
    executor=execute_dealer_gamma,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Stock ticker to analyze (e.g., SPY, AAPL, QQQ)"
        },
        "min_oi_threshold": {
            "type": "number",
            "default": 100,
            "min": 10,
            "max": 50000,
            "description": "Minimum open interest to include contracts in gamma calculation"
        },
        "max_dte": {
            "type": "number",
            "default": 45,
            "min": 7,
            "max": 90,
            "description": "Maximum days to expiration for options chain"
        },
        "lookback_days": {
            "type": "number",
            "default": 60,
            "min": 30,
            "max": 252,
            "description": "Days of price history for regime estimation"
        },
        "use_hmm_regime": {
            "type": "boolean",
            "default": False,
            "description": "Use Hidden Markov Model for multi-feature regime detection (vs simple autocorrelation)"
        },
        "hmm_n_states": {
            "type": "number",
            "default": 3,
            "min": 2,
            "max": 5,
            "description": "Number of HMM states (if HMM enabled)"
        },
        "hmm_features": {
            "type": "array",
            "items": "string",
            "default": ["autocorrelation", "volatility", "momentum"],
            "enum": ["autocorrelation", "volatility", "vol_dynamics", "momentum", "higher_moments", "range"],
            "description": "HMM feature families to use for regime detection"
        }
    },
)

register_tool(
    tool_id="confluence",
    name="Signal Confluence",
    description="Multi-factor anomaly scanner that detects when multiple independent signals align - the Rentec approach. Scans volatility, flow, positioning, smart money, and short interest signals. Requires UnusualWhales API access.",
    category="quant",
    executor=execute_confluence,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Stock ticker to analyze (e.g., SPY, AAPL, TSLA)"
        },
        "z_threshold": {
            "type": "number",
            "default": 1.5,
            "min": 1.0,
            "max": 3.0,
            "description": "Z-score threshold for extreme signals (1.5 = ~93rd percentile, 2.0 = ~98th)"
        },
        "min_signals": {
            "type": "number",
            "default": 3,
            "min": 2,
            "max": 10,
            "description": "Minimum aligned signals to flag confluence (3+ is statistically significant)"
        },
        "categories": {
            "type": "array",
            "items": "string",
            "required": False,
            "enum": ["volatility", "flow", "positioning", "smart_money", "short"],
            "description": "Signal categories to analyze (leave empty for all categories)"
        }
    },
)

register_tool(
    tool_id="greeks_surface",
    name="Greeks Surface",
    description="3D options Greeks surfaces (Delta, Gamma, Theta, Vega) with smile and term structure analysis",
    category="quant",
    executor=execute_greeks_surface,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Underlying stock ticker (e.g., AAPL, SPY)"},
        "greeks_to_model": {"type": "array", "items": "string", "default": ["delta", "gamma", "theta", "vega"], "enum": ["delta", "gamma", "theta", "vega"], "description": "Which Greeks to model surfaces for"},
        "max_dte": {"type": "number", "default": 90, "min": 30, "max": 180, "description": "Maximum days to expiration to include"},
        "target_dte_for_smile": {"type": "number", "default": 30, "min": 7, "max": 90, "description": "Target DTE for Greeks smile cross-section chart"},
        "grid_resolution": {"type": "number", "default": 25, "min": 15, "max": 50, "description": "Surface interpolation resolution (higher = smoother but slower)"},
    },
)

register_tool(
    tool_id="mean_reversion",
    name="Mean Reversion Signals",
    description="Z-score based mean reversion trading signals with stationarity testing and backtesting",
    category="quant",
    executor=execute_mean_reversion,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to analyze (e.g., AAPL, SPY)"},
        "lookback_period": {"type": "number", "default": 120, "min": 60, "max": 504, "description": "Days of historical data for analysis"},
        "lookback_window": {"type": "number", "default": 20, "min": 5, "max": 60, "description": "Rolling window for mean/std calculation (typical: 20 days)"},
        "z_score_entry_long": {"type": "number", "default": -2.0, "min": -4.0, "max": -0.5, "description": "Z-score threshold to enter LONG (negative = price is cheap relative to mean)"},
        "z_score_entry_short": {"type": "number", "default": 2.0, "min": 0.5, "max": 4.0, "description": "Z-score threshold to enter SHORT (positive = price is expensive relative to mean)"},
        "z_score_exit": {"type": "number", "default": 0.5, "min": 0.0, "max": 1.5, "description": "Z-score threshold to exit position (price returned to near mean)"},
        "direction": {"type": "string", "default": "both", "enum": ["both", "long_only", "short_only"], "description": "Trading direction constraint"},
        "test_stationarity": {"type": "boolean", "default": True, "description": "Run ADF stationarity test (required for mean reversion validity)"},
        "run_backtest": {"type": "boolean", "default": True, "description": "Run historical backtest with transaction costs"},
        "transaction_cost_bps": {"type": "number", "default": 10.0, "min": 0.0, "max": 50.0, "description": "Transaction cost in basis points (10 bps = 0.1%)"},
    },
)

register_tool(
    tool_id="iv_rv_screener",
    name="IV vs RV Screener",
    description="Compare implied volatility to realized volatility to find mispriced options",
    category="quant",
    executor=execute_iv_rv_screener,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to analyze (e.g., AAPL, SPY)"},
        "rv_window": {"type": "number", "default": 20, "min": 5, "max": 60, "description": "Days for realized volatility calculation (10-30 typical)"},
        "min_dte": {"type": "number", "default": 14, "min": 7, "max": 30, "description": "Minimum days to expiration for IV extraction"},
        "max_dte": {"type": "number", "default": 45, "min": 21, "max": 90, "description": "Maximum days to expiration for IV extraction"},
    },
)

register_tool(
    tool_id="squeeze_detector",
    name="Squeeze Detector",
    description="Detect gamma squeeze and short squeeze setups using dealer positioning, options flow, and short interest",
    category="quant",
    executor=execute_squeeze_detector,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to analyze (e.g., GME, AMC, TSLA)"},
        "lookback_days": {"type": "number", "default": 60, "min": 30, "max": 120, "description": "Historical window for z-score calculation"},
        "include_gamma": {"type": "boolean", "default": True, "description": "Include gamma/GEX analysis (dealer positioning)"},
        "include_momentum": {"type": "boolean", "default": True, "description": "Include options flow momentum signals"},
        "include_short": {"type": "boolean", "default": True, "description": "Include short interest analysis"},
    },
)

register_tool(
    tool_id="systemic_risk",
    name="Systemic Risk Score",
    description="PageRank-based network analysis for portfolio systemic risk concentration",
    category="risk",
    executor=execute_systemic_risk,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 2)"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "lookback_days": {"type": "number", "default": 252, "min": 60, "max": 504, "description": "Days of historical data"},
        "correlation_threshold": {"type": "number", "default": 0.3, "min": 0.1, "max": 0.7, "description": "Minimum correlation for network edge"},
    },
)

register_tool(
    tool_id="network_risk",
    name="Portfolio Network Analysis",
    description="Graph theory analysis: MST, bridges, communities, centrality, contagion risk, and shock propagation simulation",
    category="risk",
    executor=execute_network_risk,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 2)"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "lookback_days": {"type": "number", "default": 252, "min": 60, "max": 504, "description": "Days of historical data"},
        "correlation_threshold": {"type": "number", "default": 0.3, "min": 0.1, "max": 0.7, "description": "Minimum correlation for network edge"},
        "optimize_hedges": {"type": "boolean", "default": False, "description": "Generate hedge recommendations with cascade impact analysis"},
        "simulate_shock": {"type": "boolean", "default": False, "description": "Run shock propagation simulation to see how losses cascade through the portfolio"},
        "shock_ticker": {"type": "string", "required": False, "description": "Ticker to shock (leave empty to shock most central stock)"},
        "shock_magnitude": {"type": "number", "default": -10, "min": -50, "max": -1, "description": "Shock magnitude in % (e.g., -10 for a 10% drop)"},
    },
)

register_tool(
    tool_id="implied_corr",
    name="Implied Correlation",
    description="Market-implied correlation from index options using the variance-decomposition method - compare index IV vs constituent IVs to derive correlation expectations",
    category="risk",
    executor=execute_implied_corr,
    params_schema={
        "index_ticker": {
            "type": "string",
            "required": True,
            "description": "Index ETF ticker (e.g., SPY, QQQ, IWM, DIA, EFA, EEM)"
        },
        "tenor": {
            "type": "string",
            "default": "3m",
            "enum": ["1m", "3m", "6m"],
            "description": "Time horizon for implied volatility"
        },
        "strike_reference": {
            "type": "string",
            "default": "ATM",
            "enum": ["ATM", "DELTA_CALL", "DELTA_PUT"],
            "description": "Strike selection: ATM (at-the-money), DELTA_CALL (50-delta call), DELTA_PUT (50-delta put)"
        },
        "top_n_constituents": {
            "type": "number",
            "default": 20,
            "min": 5,
            "max": 50,
            "description": "Number of top holdings to analyze"
        },
        "expiry_tolerance_days": {
            "type": "number",
            "default": 7,
            "min": 1,
            "max": 30,
            "description": "Advanced: Days tolerance for expiration matching"
        },
        "atm_strike_tolerance": {
            "type": "number",
            "default": 0.05,
            "min": 0.01,
            "max": 0.20,
            "description": "Advanced: ATM strike tolerance (5% = ±5% from spot)"
        },
        "delta_call_target": {
            "type": "number",
            "default": 0.50,
            "min": 0.30,
            "max": 0.70,
            "description": "Advanced: Target delta for DELTA_CALL strike selection"
        },
        "delta_put_target": {
            "type": "number",
            "default": -0.50,
            "min": -0.70,
            "max": -0.30,
            "description": "Advanced: Target delta for DELTA_PUT strike selection"
        },
        "delta_tolerance": {
            "type": "number",
            "default": 0.10,
            "min": 0.05,
            "max": 0.30,
            "description": "Advanced: Delta matching tolerance"
        },
    },
)

register_tool(
    tool_id="fft_denoise",
    name="FFT Denoising",
    description="Fast Fourier Transform denoising to extract underlying trends and identify dominant cyclical patterns in price data. Removes noise while preserving signal at multiple resolution levels.",
    category="risk",
    executor=execute_fft_denoise,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Stock ticker to analyze (e.g., AAPL, SPY)"
        },
        "period": {
            "type": "string",
            "default": "1Y",
            "enum": ["1M", "3M", "6M", "1Y", "2Y", "5Y", "max"],
            "description": "Historical period to analyze. Longer periods reveal larger cycles."
        },
        "components": {
            "type": "array",
            "items": "number",
            "default": [3, 6, 9, 100],
            "description": "Number of frequency components to preserve at each denoising level. FFT decomposes price into frequencies (cycles); keeping fewer components = smoother trend, keeping more = retains detail. Examples: [3] = only major trend (months-long cycles), [10] = medium-term (weeks), [50] = short-term (days), [100] = minimal noise removal. Use multiple values like [3, 6, 9, 100] to see trends at different timescales simultaneously. More components ≠ better - it's about which timescale matters for your analysis."
        },
    },
)

register_tool(
    tool_id="rolling_corr",
    name="Rolling Correlation",
    description="Time-varying correlation analysis between two assets or portfolios using rolling windows. Supports Pearson or zero-mean (correlation swap) correlation with Fisher-transformed confidence intervals. Identifies correlation regimes and stability patterns.",
    category="risk",
    executor=execute_rolling_corr,
    params_schema={
        "input_type_x": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "First asset type: individual ticker or portfolio"
        },
        "ticker_x": {
            "type": "string",
            "required": False,
            "description": "First asset ticker (e.g., SPY)"
        },
        "x_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "First portfolio to analyze"
        },
        "input_type_y": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "Second asset type: individual ticker or portfolio"
        },
        "ticker_y": {
            "type": "string",
            "required": False,
            "description": "Second asset ticker (e.g., TLT)"
        },
        "y_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Second portfolio to analyze"
        },
        "window": {
            "type": "number",
            "default": 30,
            "min": 10,
            "max": 252,
            "description": "Rolling window size in trading days. Smaller windows (10-30) capture short-term shifts, larger windows (60-120) show long-term trends. Recommended: 30 days for monthly patterns, 63 for quarterly."
        },
        "returns_type": {
            "type": "string",
            "default": "logarithmic",
            "enum": ["simple", "logarithmic", "absolute"],
            "description": "Returns calculation: 'logarithmic' (recommended for correlation analysis, symmetric), 'simple' (percentage change), 'absolute' (volatility correlation)."
        },
        "zero_mean_mode": {
            "type": "boolean",
            "default": False,
            "description": "Use zero-mean correlation (correlation swap convention). False = Pearson correlation (standard), True = zero-mean for correlation swap pricing."
        },
        "period": {
            "type": "string",
            "default": "2Y",
            "enum": ["6M", "1Y", "2Y", "5Y", "max"],
            "description": "Historical data period. Longer periods reveal regime changes. Need at least window_size + 30 days of data."
        },
    },
)

register_tool(
    tool_id="optimization",
    name="Portfolio Optimization",
    description="Markowitz mean-variance optimization with efficient frontier",
    category="risk",
    executor=execute_optimization,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to optimize"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 2)"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Current portfolio weights"},
        "method": {"type": "string", "default": "max_sharpe", "enum": ["min_variance", "max_sharpe", "risk_parity", "target_return"], "description": "Optimization method"},
        "min_weight": {"type": "number", "default": 0.0, "min": 0.0, "max": 0.5, "description": "Minimum weight per asset"},
        "max_weight": {"type": "number", "default": 0.40, "min": 0.1, "max": 1.0, "description": "Maximum weight per asset"},
        "target_return": {"type": "number", "required": False, "description": "Target annual return (for target_return method)"},
        "period": {"type": "string", "default": "1y", "enum": ["6mo", "1y", "2y", "5y"], "description": "Historical data period"},
    },
)

register_tool(
    tool_id="stress_test",
    name="Correlation Stress Test",
    description="Simulate portfolio risk under correlation shock scenarios (market crash)",
    category="risk",
    executor=execute_stress_test,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to stress test"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers (min 2)"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "n_simulations": {"type": "number", "default": 1000, "min": 100, "max": 5000, "description": "Monte Carlo paths"},
        "time_horizon": {"type": "number", "default": 63, "min": 21, "max": 252, "description": "Forecast horizon in days"},
        "portfolio_value": {"type": "number", "default": 1000000, "min": 1000, "description": "Portfolio value in dollars"},
        "confidence_level": {"type": "number", "default": 0.95, "min": 0.90, "max": 0.99, "description": "VaR confidence level"},
        "correlation_scenarios": {"type": "array", "items": "number", "required": False, "description": "Correlation levels to test (default: [0.50, 0.75, 0.90, 0.95])"},
        "period": {"type": "string", "default": "1y", "enum": ["6mo", "1y", "2y"], "description": "Historical data period"},
    },
)

register_tool(
    tool_id="drawdown",
    name="Drawdown Analysis",
    description="Maximum drawdown, recovery periods, and underwater time analysis",
    category="risk",
    executor=execute_drawdown,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to analyze"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "period": {"type": "string", "default": "2y", "enum": ["1y", "2y", "5y", "max"], "description": "Historical data period"},
    },
)

register_tool(
    tool_id="hedge",
    name="Hedge Portfolio",
    description="Create factor-neutral hedge positions using ETFs to neutralize market/sector exposure",
    category="risk",
    executor=execute_hedge,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio ID to hedge"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers to hedge"},
        "weights": {"type": "array", "items": "number", "required": False, "description": "Portfolio weights"},
        "hedge_strategy": {"type": "string", "default": "market_neutral", "enum": ["market_neutral", "sector_neutral", "custom"], "description": "Hedging strategy"},
        "period": {"type": "string", "default": "1y", "enum": ["6mo", "1y", "2y"], "description": "Historical data period"},
    },
)

register_tool(
    tool_id="reverse_dcf",
    name="Reverse DCF",
    description="Back-solve for market-implied growth rate from current stock price",
    category="valuation",
    executor=execute_reverse_dcf,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker symbol"},
        "model_type": {"type": "string", "default": "eps", "enum": ["eps", "fcf"], "description": "Base metric for DCF"},
        "discount_rate": {"type": "number", "required": False, "description": "Discount rate (auto-calculated from CAPM if not provided)"},
        "stages": {"type": "number", "default": 2, "enum": [1, 2, 3], "description": "Number of DCF stages"},
        "stage1_years": {"type": "number", "default": 5, "min": 1, "max": 10, "description": "High-growth stage duration (years)"},
        "stage2_years": {"type": "number", "default": 5, "min": 1, "max": 10, "description": "Fade stage duration for 3-stage model (years)"},
        "terminal_growth": {"type": "number", "default": 0.025, "min": 0.0, "max": 0.05, "description": "Terminal growth rate"},
    },
)

register_tool(
    tool_id="comps",
    name="Comparable Companies",
    description="Peer comparison with football field valuation and trading multiples analysis",
    category="valuation",
    executor=execute_comps,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Target company ticker"},
        "peers": {"type": "string", "required": True, "description": "Peer tickers (comma-separated, e.g. MSFT,GOOGL,AMZN)"},
        "multiples": {
            "type": "array",
            "required": False,
            "items": "string",
            "default": ["priceToEarningsRatio", "evToEBITDA", "priceToBookRatio"],
            "enum": [
                "priceToEarningsRatio",
                "priceToEarningsRatioTTM",
                "evToEBITDA",
                "evToEBITDATTM",
                "evToSales",
                "evToSalesTTM",
                "evToFreeCashFlow",
                "evToFreeCashFlowTTM",
                "priceToBookRatio",
                "priceToBookRatioTTM",
                "priceToSalesRatio",
                "priceToSalesRatioTTM",
                "priceToFreeCashFlowRatio",
                "priceToFreeCashFlowRatioTTM",
                "priceToOperatingCashFlowRatio",
                "priceToOperatingCashFlowRatioTTM",
                "priceToEarningsGrowthRatio",
                "dividendYield",
                "dividendYieldTTM",
                "earningsYield",
                "earningsYieldTTM",
                "roe",
                "grossProfitMargin",
                "grossProfitMarginTTM",
                "operatingProfitMargin",
                "operatingProfitMarginTTM",
                "netProfitMargin",
                "netProfitMarginTTM",
                "ebitdaMargin",
                "ebitdaMarginTTM",
                "netDebtToEBITDA",
                "netDebtToEBITDATTM",
                "marketCap",
                "enterpriseValue"
            ],
            "description": "Valuation multiples to compare"
        },
    },
)

register_tool(
    tool_id="epv",
    name="EPV (Earnings Power Value)",
    description="Graham/Dodd normalized earnings valuation - conservative floor value assuming zero growth",
    category="valuation",
    executor=execute_epv,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker symbol"},
        "wacc": {"type": "number", "required": False, "description": "WACC (auto-calculated if not provided)"},
        "tax_rate": {"type": "number", "required": False, "description": "Effective tax rate (auto-calculated if not provided)"},
        "normalization_years": {"type": "number", "default": 5, "min": 3, "max": 10, "description": "Years to normalize earnings"},
        "normalization_method": {"type": "string", "default": "weighted", "enum": ["average", "median", "weighted"], "description": "Normalization method"},
    },
)

register_tool(
    tool_id="rim",
    name="RIM (Residual Income)",
    description="Residual income model for banks, insurance, and financials - values based on ROE vs cost of equity",
    category="valuation",
    executor=execute_rim,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker (best for banks/financials)"},
        "cost_of_equity": {"type": "number", "required": False, "description": "Cost of equity (auto from CAPM if not provided)"},
        "terminal_roe": {"type": "number", "required": False, "description": "Long-term sustainable ROE"},
        "terminal_growth": {"type": "number", "default": 0.02, "min": 0.0, "max": 0.04, "description": "Terminal growth rate"},
        "projection_years": {"type": "number", "default": 5, "min": 3, "max": 10, "description": "Projection period years"},
        "use_tangible_book": {"type": "boolean", "default": False, "description": "Use tangible book value (excludes goodwill)"},
        "monte_carlo": {"type": "boolean", "default": False, "description": "Run Monte Carlo simulation for probability distribution"},
        "iterations": {"type": "integer", "default": 1000, "min": 100, "max": 10000, "description": "Monte Carlo iterations"},
    },
)

register_tool(
    tool_id="dcf_monte_carlo",
    name="Monte Carlo DCF",
    description="Probabilistic DCF valuation - runs 1000+ simulations to get fair value distribution and probability stock is undervalued",
    category="valuation",
    executor=execute_dcf_monte_carlo,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Stock ticker to value (e.g., AAPL, MSFT)"
        },
        "terminal_growth": {
            "type": "number",
            "default": 0.025,
            "min": 0.01,
            "max": 0.05,
            "description": "Long-term growth rate (2-4% typical). Higher for strong moats."
        },
        "stages": {
            "type": "number",
            "default": 2,
            "enum": [1, 2, 3],
            "description": "DCF stages: 1=stable, 2=growth+terminal, 3=growth+fade+terminal"
        },
        "stage1_years": {
            "type": "number",
            "default": 5,
            "min": 3,
            "max": 10,
            "description": "High-growth period (years)"
        },
        "model_type": {
            "type": "string",
            "default": "eps",
            "enum": ["eps", "fcf"],
            "description": "Base metric: EPS or Free Cash Flow per share"
        },
        "iterations": {
            "type": "number",
            "default": 1000,
            "min": 100,
            "max": 10000,
            "description": "Number of Monte Carlo simulations"
        },
    },
)

register_tool(
    tool_id="dcf_traditional",
    name="Traditional DCF",
    description="Deterministic DCF valuation: Stable (perpetuity), 2-stage (growth→terminal), or 3-stage (growth→fade→terminal)",
    category="valuation",
    executor=execute_dcf_traditional,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Stock ticker to value"
        },
        "stages": {
            "type": "string",
            "default": "2",
            "required": True,
            "enum": ["stable", "2", "3"],
            "description": "DCF model: Stable (single-stage perpetuity for mature companies), 2-stage (growth→terminal), or 3-stage (growth→fade→terminal)"
        },
        "stage1_years": {
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 10,
            "description": "Growth period duration (years). For stable: 0-2 years before terminal."
        },
        "stage2_years": {
            "type": "number",
            "default": 5,
            "min": 3,
            "max": 10,
            "description": "Fade period duration (only for 3-stage)"
        },
        "terminal_growth": {
            "type": "number",
            "default": 0.025,
            "min": 0.01,
            "max": 0.05,
            "description": "Terminal perpetuity growth rate (2-3% typical)"
        },
        "growth_rate": {
            "type": "number",
            "required": False,
            "description": "Stage 1 growth rate (leave empty to auto-calculate from historical EPS)"
        },
        "discount_rate": {
            "type": "number",
            "required": False,
            "description": "Discount rate / cost of equity (leave empty to auto-calculate from CAPM)"
        },
        "model_type": {
            "type": "string",
            "default": "eps",
            "enum": ["eps", "fcf"],
            "description": "Base metric: EPS or FCF per share"
        },
    },
)

register_tool(
    tool_id="finbert_sentiment",
    name="FinBERT Sentiment",
    description="NLP-based news sentiment analysis using FinBERT model - analyzes financial news for bullish/bearish signals",
    category="sentiment",
    executor=execute_finbert_sentiment,
    params_schema={
        "ticker": {"type": "string", "required": False, "description": "Stock ticker (e.g., AAPL). Optional for market-wide news"},
        "news_type": {
            "type": "string",
            "default": "stock",
            "enum": ["stock", "press-releases", "general", "crypto", "forex"],
            "description": "Type of news: stock=company news, press-releases=official announcements, general=market-wide, crypto/forex=alt markets"
        },
        "max_articles": {"type": "number", "default": 20, "min": 5, "max": 50, "description": "Maximum articles to analyze"},
    },
)

register_tool(
    tool_id="sector_rotation",
    name="Sector Rotation Flow",
    description="Detect capital rotation between sectors using options flow (delta, vega, premium) - identifies where institutional money is flowing",
    category="quant",
    executor=execute_sector_rotation,
    params_schema={
        "use_regime": {"type": "boolean", "default": True, "description": "Enable market regime detection (risk-on/risk-off/transition)"},
        "use_anomaly": {"type": "boolean", "default": False, "description": "Enable anomaly detection for unusual flow patterns"},
        "include_vega": {"type": "boolean", "default": True, "description": "Include vega flow momentum in analysis"},
    },
)

register_tool(
    tool_id="gex",
    name="Gamma Exposure (GEX)",
    description="Dealer gamma positioning analysis - identifies key support/resistance levels and regime (long/short gamma)",
    category="quant",
    executor=execute_gex,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Underlying ticker (e.g., SPY, AAPL, QQQ)"},
        "max_dte": {"type": "number", "default": 45, "min": 7, "max": 90, "description": "Maximum days to expiration for options"},
        "min_oi": {"type": "number", "default": 100, "min": 10, "max": 1000, "description": "Minimum open interest filter"},
        "use_hmm": {"type": "boolean", "default": False, "description": "Use HMM for regime detection (more robust but slower)"},
    },
)

register_tool(
    tool_id="instanton",
    name="Instanton Rare Event",
    description="Physics-based crash probability using instanton methods - finds the most likely path to a crash analytically (not Monte Carlo)",
    category="quant",
    executor=execute_instanton,
    params_schema={
        "portfolio_id": {"type": "string", "description": "Portfolio ID for portfolio-level analysis"},
        "ticker": {"type": "string", "description": "Single ticker for asset-level analysis (use if no portfolio)"},
        "crash_pct": {"type": "number", "min": -80, "max": -5, "description": "Crash percentage target (e.g., -20 for 20% drop). Leave empty for auto."},
        "crash_target": {"type": "string", "default": "var_99", "enum": ["var_95", "var_99", "max_drawdown", "vol_3"], "description": "Auto crash target if crash_pct not specified"},
        "horizon_days": {"type": "number", "default": 30, "min": 5, "max": 120, "description": "Time horizon in trading days"},
        "lookback_days": {"type": "number", "default": 756, "min": 252, "max": 1260, "description": "Historical lookback for fitting (756 = 3 years)"},
        "distribution": {"type": "string", "default": "auto", "enum": ["auto", "normal", "student_t"], "description": "Distribution to fit (auto uses BIC)"},
    },
)

register_tool(
    tool_id="earnings_pattern",
    name="Earnings Pattern Analyzer",
    description="Analyzes historical earnings patterns - vol crush rates, expected vs actual moves, short straddle returns. Generates SELL_VOL/BUY_VOL signals.",
    category="quant",
    executor=execute_earnings_pattern,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to analyze"},
        "lookback_quarters": {"type": "number", "default": 8, "min": 4, "max": 20, "description": "Number of historical quarters to analyze"},
    },
)

register_tool(
    tool_id="vanna_charm",
    name="Vanna/Charm Flow",
    description="Second-order Greeks analysis - vanna (delta change from vol) and charm (delta decay from time). Identifies dealer hedging flows and regime.",
    category="quant",
    executor=execute_vanna_charm,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Stock ticker to analyze"},
        "min_oi": {"type": "number", "default": 100, "min": 10, "max": 1000, "description": "Minimum open interest filter"},
        "max_dte": {"type": "number", "default": 45, "min": 7, "max": 90, "description": "Maximum days to expiration"},
    },
)

register_tool(
    tool_id="hedge_path",
    name="Dijkstra Hedge Path",
    description="Optimal hedge finder using Dijkstra algorithm.",
    category="quant",
    executor=execute_hedge_path,
    params_schema={
        "portfolio_id": {"type": "string", "description": "Portfolio to hedge"},
        "tickers": {"type": "string", "description": "Comma-separated tickers (alt to portfolio)"},
        "delta_reduction_pct": {"type": "number", "min": 10, "max": 100, "description": "Delta reduction target % (e.g., 50)"},
        "target_beta": {"type": "number", "min": 0, "max": 2, "step": 0.1, "description": "Target portfolio beta (e.g., 0.5)"},
        "target_var_1d_pct": {"type": "number", "min": 0.1, "max": 5, "step": 0.1, "description": "Target daily VaR % (e.g., 1.5)"},
        "neutralize_sectors": {"type": "string", "description": "Sectors to neutralize (e.g., XLK,XLF)"},
        "max_dte": {"type": "number", "default": 45, "min": 7, "max": 90, "description": "Max option DTE"},
    },
)

register_tool(
    tool_id="recession_field",
    name="Recession Field Theory",
    description="Physics-inspired recession early warning using phase transition theory. Detects critical slowing down, correlation divergence, and regime shifts 3-9 months before recessions.",
    category="quant",
    executor=execute_recession_field,
    params_schema={
        "lookback_years": {"type": "number", "default": 5, "min": 2, "max": 15, "description": "Years of historical macro data"},
        "field_method": {"type": "string", "default": "weighted", "enum": ["weighted", "pca"], "description": "Field construction: weighted (interpretable) or pca (data-driven)"},
        "include_ml_probability": {"type": "boolean", "default": True, "description": "Include ML-based 6-month recession probability"},
    },
)

register_tool(
    tool_id="geodesic",
    name="Portfolio Geodesic Distance",
    description="Fisher-Rao geodesic distance between portfolio return distributions using Information Geometry.",
    category="quant",
    executor=execute_geodesic,
    params_schema={
        "portfolio_id": {"type": "string", "description": "Portfolio to analyze"},
        "compare_to_portfolio_id": {"type": "string", "description": "Second portfolio to compare (optional)"},
        "tickers": {"type": "array", "items": {"type": "string"}, "description": "Manual tickers (if no portfolio)"},
        "lookback_days": {"type": "number", "default": 252, "min": 60, "max": 756, "description": "Trading days of history"},
    },
)

register_tool(
    tool_id="herding",
    name="Herding Regime Detector",
    description="Ising model-inspired crowding/herding detection using physics statistics. Computes magnetization, susceptibility, correlation length, and critical slowing down with HMM regime classification.",
    category="quant",
    executor=execute_herding,
    params_schema={
        "portfolio_id": {"type": "string", "required": False, "description": "Portfolio to analyze for herding"},
        "tickers": {"type": "array", "items": "string", "required": False, "description": "Stock tickers to analyze (defaults to 11 sector ETFs)"},
        "lookback_days": {"type": "number", "default": 252, "min": 60, "max": 756, "description": "Days of historical data"},
        "window": {"type": "number", "default": 21, "min": 5, "max": 63, "description": "Rolling window for statistics (trading days)"},
        "field_mode": {"type": "string", "default": "discretionary", "enum": ["discretionary", "macro"], "description": "External field mode: discretionary (internal participation) or macro (economy-wide pressure)"},
        "include_vix": {"type": "boolean", "default": True, "description": "Use VIX for temperature (T) parameter"},
        "include_options_flow": {"type": "boolean", "default": True, "description": "Use options flow for coupling (J) parameter (sector mode only)"},
        "include_hmm": {"type": "boolean", "default": True, "description": "Fit HMM for regime classification (dispersed/normal/critical)"},
    },
)

register_tool(
    tool_id="option_pricing",
    name="Option Pricing",
    description="Price equity options using Black-Scholes, Binomial Tree, or Monte Carlo. Returns option price, Greeks (delta, gamma, vega, theta, rho), and sensitivity analysis.",
    category="quant",
    executor=execute_option_pricing,
    params_schema={
        "ticker": {"type": "string", "required": True, "description": "Underlying stock ticker (e.g., AAPL, SPY)"},
        "strike": {"type": "number", "required": True, "description": "Strike price ($)"},
        "expiry": {"type": "string", "required": False, "description": "Expiry date YYYY-MM-DD (default: 30 days out)"},
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Call or Put",
        },
        "pricing_model": {
            "type": "string",
            "default": "black_scholes",
            "enum": ["black_scholes", "binomial", "monte_carlo"],
            "description": "BLACK-SCHOLES: Closed-form (fastest). BINOMIAL: Tree model (supports American). MONTE-CARLO: Simulation (most flexible).",
        },
        "american": {
            "type": "boolean",
            "default": False,
            "description": "American-style early exercise (only for Binomial model)",
        },
        "num_simulations": {
            "type": "number",
            "default": 10000,
            "min": 100,
            "max": 100000,
            "description": "Number of Monte Carlo simulations (100-100,000). More = accurate but slower.",
        },
    },
)

register_tool(
    tool_id="corr_swap",
    name="Correlation Swap",
    description="Price correlation swap derivatives using zero-mean correlation convention. Correlation swaps are derivatives where payoff = Notional × (Realized Correlation - Strike Correlation). Used by hedge funds to trade/hedge correlation risk separately from volatility. Supports ticker-ticker, ticker-portfolio, and portfolio-portfolio.",
    category="quant",
    executor=execute_corr_swap,
    params_schema={
        "input_type_x": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "First asset type: individual ticker or portfolio"
        },
        "asset_x": {
            "type": "string",
            "required": False,
            "description": "First asset ticker (e.g., SPY)"
        },
        "x_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "First portfolio to analyze"
        },
        "input_type_y": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "Second asset type: individual ticker or portfolio"
        },
        "asset_y": {
            "type": "string",
            "required": False,
            "description": "Second asset ticker (e.g., TLT)"
        },
        "y_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Second portfolio to analyze"
        },
        "notional": {
            "type": "number",
            "default": 1000000,
            "min": 10000,
            "max": 100000000,
            "description": "Swap notional amount ($). Typical institutional size: $1M-$10M."
        },
        "strike_correlation": {
            "type": "number",
            "default": 0.5,
            "min": -0.99,
            "max": 0.99,
            "description": "Strike correlation level (between -1 and 1). Buyer profits if realized > strike. Common strikes: 0.3-0.7 for equities."
        },
        "tenor": {
            "type": "number",
            "default": 63,
            "min": 20,
            "max": 252,
            "description": "Days to maturity. Standard tenors: 1M (21d), 3M (63d), 6M (126d), 1Y (252d)."
        },
        "risk_free_rate": {
            "type": "number",
            "required": False,
            "description": "Annual risk-free rate (%) for discounting. Leave blank to auto-fetch current rate from FRED (recommended). Example: 4.5 for 4.5%."
        },
        "rolling_window": {
            "type": "number",
            "default": 20,
            "min": 5,
            "max": 60,
            "description": "Rolling window size (days) for correlation time series. Shorter = more reactive, longer = smoother. Typical: 20d (1 month)."
        },
        "pricing_mode": {
            "type": "string",
            "default": "realized",
            "enum": ["realized", "forward"],
            "description": "REALIZED: Price with historical data (post-maturity). FORWARD: Monte Carlo simulation (pre-maturity with probability distribution)."
        },
        "days_remaining": {
            "type": "number",
            "default": 60,
            "required": False,
            "min": 1,
            "max": 252,
            "description": "⚠️ For forward pricing: days until maturity (~3 months default). WARNING: This value MUST be less than or equal to Tenor (Days). Example: if Tenor=63, days_remaining cannot exceed 63."
        },
        "num_simulations": {
            "type": "number",
            "default": 10000,
            "min": 1000,
            "max": 100000,
            "description": "Number of Monte Carlo simulations (forward mode only). More = accurate but slower. Recommended: 10,000."
        },
    },
)

register_tool(
    tool_id="hedge_ratio",
    name="Hedge Ratio",
    description="Calculate optimal hedge ratios for pairs trading. Computes β in Y = α + βX, where β tells you how much of asset Y to hold per dollar of asset X to minimize risk. Supports OLS (simple regression), TLS (errors-in-variables), and Kalman filter (time-varying) methods. Essential for pairs trading, stat arb, and market-neutral strategies.",
    category="quant",
    executor=execute_hedge_ratio,
    params_schema={
        "input_type_primary": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "Primary asset type: individual ticker or portfolio"
        },
        "primary_asset": {
            "type": "string",
            "required": False,
            "description": "Primary asset ticker (independent variable, X). This is the asset you're long."
        },
        "primary_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Primary portfolio to analyze"
        },
        "input_type_hedge": {
            "type": "string",
            "default": "ticker",
            "enum": ["ticker", "portfolio"],
            "description": "Hedge asset type: individual ticker or portfolio"
        },
        "hedge_asset": {
            "type": "string",
            "required": False,
            "description": "Hedge asset ticker (dependent variable, Y). This is the asset you'll use to hedge."
        },
        "hedge_portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Hedge portfolio to analyze"
        },
        "method": {
            "type": "string",
            "default": "ols",
            "enum": ["ols", "tls", "kalman"],
            "description": "Estimation method. OLS: ordinary least squares (simple, fast). TLS: total least squares (handles errors in both assets). Kalman: time-varying beta (for non-stationary relationships)."
        },
        "window": {
            "type": "number",
            "required": False,
            "min": 20,
            "max": 252,
            "description": "Rolling window size in days (optional). Leave blank for static estimate. Use 20-60 days for dynamic hedge ratios. Only supported for OLS and Kalman methods."
        },
        "period": {
            "type": "string",
            "default": "1Y",
            "enum": ["1M", "3M", "6M", "1Y", "2Y", "5Y"],
            "description": "Historical lookback period for data. Longer periods = more stable estimates but may miss recent regime changes."
        },
    },
)

register_tool(
    tool_id="dynamic_hedge",
    name="Dynamic Hedge",
    description="Multi-Greek monitoring and rebalancing optimization for options portfolios. Calculates delta, gamma, vega, theta exposures and optimal hedge quantities using multi-Greek drift scores. Includes historical backtesting to compare hedged vs unhedged P&L, scenario analysis across price/vol moves, and cost-benefit analysis (transaction costs vs theta income). Essential for professional options portfolio management.",
    category="quant",
    executor=execute_dynamic_hedge,
    params_schema={
        "input_type": {
            "type": "string",
            "default": "portfolio",
            "enum": ["portfolio", "ticker"],
            "description": "Input type: use portfolio holdings or manual tickers"
        },
        "portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Portfolio to analyze (generates synthetic options from holdings)"
        },
        "tickers": {
            "type": "string",
            "required": False,
            "description": "Manual tickers (comma-separated, e.g., 'AAPL,MSFT,GOOGL')"
        },
        "hedge_tickers": {
            "type": "string",
            "default": "SPY",
            "description": "Hedge instruments (comma-separated, e.g., 'SPY' or 'SPY,QQQ')"
        },
        "target_delta": {
            "type": "number",
            "default": 0.0,
            "min": -100,
            "max": 100,
            "description": "Target portfolio delta. 0 = delta-neutral."
        },
        "threshold": {
            "type": "number",
            "default": 0.1,
            "min": 0.01,
            "max": 1.0,
            "description": "Multi-Greek drift threshold for rebalancing trigger"
        },
        "frequency": {
            "type": "string",
            "default": "daily",
            "enum": ["intraday", "daily", "weekly"],
            "description": "Rebalancing frequency"
        },
        "lookback": {
            "type": "string",
            "default": "30D",
            "enum": ["30D", "60D", "90D", "6M", "1Y"],
            "description": "Historical backtest period"
        },
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Option type to generate from holdings"
        },
        "moneyness": {
            "type": "string",
            "default": "atm",
            "enum": ["atm", "otm_5", "itm_5"],
            "description": "Strike selection: ATM, 5% OTM, or 5% ITM"
        },
        "days_to_expiry": {
            "type": "number",
            "default": 30,
            "min": 7,
            "max": 365,
            "description": "Days to expiry for generated options"
        },
    },
)

register_tool(
    tool_id="delta_hedge",
    name="Delta Hedge",
    description="Simple delta-neutral hedge construction using stocks/ETFs. Calculates optimal hedge quantities to neutralize portfolio delta, with beta-adjustment for hedge instruments. Lighter alternative to Dynamic Hedge for pure delta hedging without multi-Greek monitoring.",
    category="quant",
    executor=execute_delta_hedge,
    params_schema={
        "input_type": {
            "type": "string",
            "default": "portfolio",
            "enum": ["portfolio", "ticker"],
            "description": "Input type: use portfolio holdings or manual tickers"
        },
        "portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Portfolio to analyze"
        },
        "tickers": {
            "type": "string",
            "required": False,
            "description": "Manual tickers (comma-separated)"
        },
        "hedge_tickers": {
            "type": "string",
            "default": "SPY",
            "description": "Hedge instruments (e.g., 'SPY' or 'SPY,QQQ')"
        },
        "target_delta": {
            "type": "number",
            "default": 0.0,
            "min": -100,
            "max": 100,
            "description": "Target delta. 0 = delta-neutral."
        },
        "rebalance_threshold": {
            "type": "number",
            "default": 0.1,
            "min": 0.01,
            "max": 1.0,
            "description": "Delta threshold for rebalancing alert"
        },
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Option type to generate from holdings"
        },
        "moneyness": {
            "type": "string",
            "default": "atm",
            "enum": ["atm", "otm_5", "itm_5"],
            "description": "Strike selection"
        },
        "days_to_expiry": {
            "type": "number",
            "default": 30,
            "min": 7,
            "max": 365,
            "description": "Days to expiry for generated options"
        },
    },
)

register_tool(
    tool_id="feature_importance",
    name="Feature Importance",
    description="XGBoost-based ML feature importance analysis for stock return prediction. Identifies which technical indicators and computed features have the most predictive power using Gain, Permutation, and SHAP methods. Essential for quantitative strategy development.",
    category="quant",
    executor=execute_feature_importance,
    params_schema={
        "input_type": {
            "type": "string",
            "default": "ticker",
            "enum": ["portfolio", "ticker"],
            "description": "Input type"
        },
        "portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Portfolio to analyze"
        },
        "tickers": {
            "type": "string",
            "required": False,
            "description": "Tickers (comma-separated, e.g., 'AAPL,MSFT')"
        },
        "target": {
            "type": "string",
            "default": "future_5day_return",
            "enum": ["future_5day_return", "future_10day_return", "future_20day_return"],
            "description": "Prediction target"
        },
        "period": {
            "type": "string",
            "default": "1Y",
            "enum": ["6M", "1Y", "2Y"],
            "description": "Historical data period"
        },
        "top_n": {
            "type": "number",
            "default": 15,
            "min": 5,
            "max": 30,
            "description": "Number of top features to show"
        },
        "methods": {
            "type": "string",
            "default": "gain,permutation,shap",
            "description": "Importance methods (comma-separated): gain, permutation, shap"
        },
    },
)

register_tool(
    tool_id="cross_greeks",
    name="Cross-Asset Greeks",
    description="Calculate second-order Greeks (vanna, volga, charm, veta) for advanced portfolio risk management. These capture non-linear sensitivities that first-order Greeks miss: vanna (delta-vol interaction), volga (vol convexity), charm (delta decay), veta (vega decay). Essential for multi-leg strategies, vol trading, and dynamic hedging.",
    category="quant",
    executor=execute_cross_greeks,
    params_schema={
        "tickers": {
            "type": "array",
            "required": False,
            "items": "string",
            "description": "Tickers to analyze"
        },
        "portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Or select a portfolio"
        },
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Option type to generate"
        },
        "moneyness": {
            "type": "string",
            "default": "atm",
            "enum": ["atm", "otm_5", "otm_10", "itm_5", "itm_10"],
            "description": "Strike selection: ATM (at-the-money), OTM 5%/10% (out-of-the-money), ITM 5%/10% (in-the-money)"
        },
        "expiry_months": {
            "type": "number",
            "default": 3,
            "enum": [1, 2, 3, 6, 12],
            "description": "Months until expiration"
        },
        "greeks": {
            "type": "array",
            "default": ["vanna", "volga", "charm", "veta"],
            "enum": ["vanna", "volga", "charm", "veta"],
            "description": "Which second-order Greeks to calculate. Default: all four."
        },
        "use_polygon": {
            "type": "boolean",
            "default": True,
            "description": "Use Polygon API for IV (recommended)"
        }
    },
)

register_tool(
    tool_id="greek_exposure",
    name="Greek Exposure",
    description="Calculate first-order Greek exposures (Delta, Gamma, Vega, Theta) for options portfolios using Black-Scholes. Select which Greek to analyze: Delta (price sensitivity), Gamma (delta sensitivity), Vega (volatility sensitivity), or Theta (time decay).",
    category="quant",
    executor=execute_greek_exposure,
    params_schema={
        "greek_type": {
            "type": "string",
            "required": True,
            "default": "delta",
            "enum": ["delta", "gamma", "vega", "theta"],
            "description": "Which Greek to calculate. Delta: price sensitivity. Gamma: delta sensitivity. Vega: volatility sensitivity. Theta: time decay."
        },
        "tickers": {
            "type": "array",
            "required": False,
            "items": "string",
            "description": "Tickers to analyze"
        },
        "portfolio_id": {
            "type": "string",
            "required": False,
            "description": "Or select a portfolio"
        },
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Option type to generate"
        },
        "moneyness": {
            "type": "string",
            "default": "atm",
            "enum": ["atm", "otm_5", "otm_10", "itm_5", "itm_10"],
            "description": "Strike selection: ATM (at-the-money), OTM 5%/10% (out-of-the-money), ITM 5%/10% (in-the-money)"
        },
        "expiry_months": {
            "type": "number",
            "default": 3,
            "enum": [1, 2, 3, 6, 12],
            "description": "Months until expiration"
        },
        "days_forward": {
            "type": "number",
            "default": 1,
            "min": 1,
            "max": 30,
            "description": "Days to project theta decay (only for theta)"
        }
    },
)

register_tool(
    tool_id="nope",
    name="NOPE Divergence",
    description="Detect NOPE (Net Options Pricing Effect) vs price divergences. NOPE measures net delta from options trading. When NOPE diverges from price, expect reversals: NOPE↑ + Price↓ = bullish bounce, NOPE↓ + Price↑ = bearish pullback.",
    category="quant",
    executor=execute_nope,
    params_schema={
        "screener": {
            "type": "string",
            "default": "custom",
            "enum": [
                "custom", "etf_holdings", "sector",
                "sweep_storm", "floor_accumulation", "bullish_flow", "bearish_flow",
                "vol_gt_oi", "high_delta", "earnings_plays",
                "mega_cap", "large_cap", "mid_cap", "small_cap"
            ],
            "description": "CUSTOM: Enter specific tickers. ETF_HOLDINGS: Scan ETF components. SECTOR: Scan sector. Flow presets: sweep_storm (aggressive sweeps), bullish_flow, bearish_flow, vol_gt_oi (unusual volume).",
        },
        "tickers": {
            "type": "string",
            "required": False,
            "description": "Tickers to scan (for custom screener). Space or comma separated, e.g., 'AAPL MSFT NVDA'",
        },
        "etf_ticker": {
            "type": "string",
            "required": False,
            "description": "ETF to scan holdings (for etf_holdings screener), e.g., SPY, QQQ, XLK",
        },
        "sector": {
            "type": "string",
            "required": False,
            "enum": ["Technology", "Healthcare", "Financial Services", "Energy", "Consumer Cyclical", "Industrials", "Communication Services", "mag7", "semi", "cyber"],
            "description": "Sector or theme (for sector screener). mag7=Magnificent 7, semi=semiconductors, cyber=cybersecurity",
        },
        "z_threshold": {
            "type": "number",
            "default": 1.5,
            "min": 1.0,
            "max": 3.0,
            "description": "Statistical significance threshold. 1.0=more signals, 1.5=balanced, 2.0=high confidence only.",
        },
        "lookback_days": {
            "type": "number",
            "default": 5,
            "min": 3,
            "max": 7,
            "description": "Days of NOPE data to analyze (3-7). More days = more context but slower.",
        },
        "top_n": {
            "type": "number",
            "default": 10,
            "min": 1,
            "max": 50,
            "description": "Max tickers to scan (1-50). Each ticker = multiple API calls. Start small!",
        },
    },
)


# -----------------------------------------------------------------------------
# Structuring Tools
# -----------------------------------------------------------------------------

register_tool(
    tool_id="dispersion",
    name="Dispersion Trade",
    description="Index vs constituents dispersion trades. Long index vol, short constituent vols. Profits when correlation decreases (constituents move independently). Auto-fetches top ETF holdings if constituents not specified.",
    category="structuring",
    executor=execute_dispersion,
    params_schema={
        "index_ticker": {"type": "string", "default": "SPY", "description": "Index ETF (e.g., SPY, QQQ)"},
        "num_constituents": {"type": "number", "default": 10, "min": 3, "max": 30, "description": "Number of top holdings to use (auto-fetched from ETF)"},
        "notional": {"type": "number", "default": 1000000, "min": 10000, "description": "Trade notional ($)"},
        "tenor": {"type": "string", "default": "3M", "enum": ["1M", "3M", "6M", "1Y"], "description": "Option tenor"},
    },
)

register_tool(
    tool_id="var_swap",
    name="Variance Swap",
    description="Variance swap pricing with fair strike from options replicating portfolio. Payoff = Notional × (Realized_Var - Strike_Var).",
    category="structuring",
    executor=execute_var_swap,
    params_schema={
        "underlying": {"type": "string", "required": True, "description": "Stock ticker (e.g., SPY, AAPL)"},
        "notional": {"type": "number", "default": 100000, "min": 1000, "description": "Notional per variance point ($)"},
        "strike_variance": {"type": "number", "required": False, "description": "Strike variance (decimal, e.g., 0.04 = 20% vol). Leave empty for fair strike."},
        "tenor": {"type": "string", "default": "3M", "enum": ["1M", "3M", "6M", "1Y"], "description": "Swap tenor"},
    },
)

register_tool(
    tool_id="exotic_pricing",
    name="Exotic Derivatives",
    description="Price exotic options using Monte Carlo simulation. Select option type to see relevant parameters.",
    category="structuring",
    executor=execute_exotic_pricing,
    params_schema={
        "derivative_type": {
            "type": "string",
            "required": True,
            "enum": ["barrier", "asian", "lookback", "digital"],
            "default": "barrier",
            "description": "BARRIER: Knock-in/out when price hits level. ASIAN: Payoff based on average price. LOOKBACK: Strike set to best price during life. DIGITAL: Fixed payout if ITM at expiry.",
        },
        "underlying": {"type": "string", "required": True, "description": "Stock ticker (e.g., SPY, AAPL, NVDA)"},
        "option_type": {
            "type": "string",
            "default": "call",
            "enum": ["call", "put"],
            "description": "Call (profit if up) or Put (profit if down)",
        },
        "strike": {"type": "number", "required": False, "description": "Strike price in $ (leave empty for ATM = current spot)"},
        "expiry": {"type": "string", "required": False, "description": "Expiry date YYYY-MM-DD (default: 3 months out)"},
        "num_simulations": {"type": "number", "default": 5000, "min": 1000, "max": 50000, "description": "Monte Carlo paths (more = slower but more accurate)"},
        # Barrier-specific (shown when derivative_type = barrier)
        "barrier_type": {
            "type": "string",
            "enum": ["up-and-out", "up-and-in", "down-and-out", "down-and-in"],
            "default": "up-and-out",
            "description": "UP-OUT: Dies if price rises to barrier. UP-IN: Activates if price rises to barrier. DOWN-OUT: Dies if price falls. DOWN-IN: Activates if price falls.",
        },
        "barrier_level": {"type": "number", "required": False, "description": "Barrier price level in $ (e.g., 120 for knock-out at $120)"},
        # Asian-specific (shown when derivative_type = asian)
        "averaging_type": {
            "type": "string",
            "enum": ["arithmetic", "geometric"],
            "default": "arithmetic",
            "description": "ARITHMETIC: Simple average (more common). GEOMETRIC: Multiplicative average (has closed-form solution).",
        },
        "averaging_frequency": {
            "type": "string",
            "enum": ["daily", "weekly", "monthly"],
            "default": "daily",
            "description": "How often to sample price for averaging",
        },
        # Lookback-specific (shown when derivative_type = lookback)
        "lookback_type": {
            "type": "string",
            "enum": ["fixed", "floating"],
            "default": "fixed",
            "description": "FIXED: Compare max/min price to fixed strike. FLOATING: Strike = min (call) or max (put) during life.",
        },
        # Digital-specific (shown when derivative_type = digital)
        "digital_payoff": {"type": "number", "default": 100, "description": "Fixed payout amount in $ if option is ITM at expiry"},
    },
)

register_tool(
    tool_id="swaption",
    name="Swaption Pricing",
    description="Price interest rate swaptions (options on swaps) using Black or Bachelier models. Payer = right to pay fixed. Receiver = right to receive fixed.",
    category="structuring",
    executor=execute_swaption,
    params_schema={
        "notional": {
            "type": "number",
            "default": 10000000,
            "min": 100000,
            "max": 1000000000,
            "description": "Notional amount in $"
        },
        "tenor": {
            "type": "string",
            "default": "5Y",
            "enum": ["2Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"],
            "description": "Swap maturity"
        },
        "float_index": {
            "type": "string",
            "default": "SOFR",
            "enum": ["SOFR", "EFFR", "FEDFUNDS"],
            "description": "Floating rate index (SOFR = Secured Overnight Financing Rate, EFFR = Effective Fed Funds Rate)"
        },
        "payment_freq": {
            "type": "string",
            "default": "semiannual",
            "enum": ["quarterly", "semiannual", "annual"],
            "description": "Payment frequency"
        },
        "option_type": {
            "type": "string",
            "required": True,
            "enum": ["payer", "receiver"],
            "description": "PAYER: Right to pay fixed (bet rates rise). RECEIVER: Right to receive fixed (bet rates fall)."
        },
        "expiry": {
            "type": "string",
            "required": False,
            "description": "Option expiry date (YYYY-MM-DD). Default: 3 months from now."
        },
        "strike": {
            "type": "number",
            "default": 0.045,
            "min": 0.001,
            "max": 0.20,
            "description": "Strike rate (decimal). E.g., 0.045 = 4.5%"
        },
        "pricing_model": {
            "type": "string",
            "default": "black",
            "enum": ["black", "bachelier"],
            "description": "BLACK: Lognormal (industry standard). BACHELIER: Normal (for near-zero rates)."
        },
        "volatility": {
            "type": "number",
            "required": False,
            "description": "Optional: Override volatility (decimal, e.g., 0.50 = 50%). Leave empty to auto-estimate from historical swap rates."
        },
        "pricing_date": {
            "type": "string",
            "required": False,
            "description": "Valuation date (YYYY-MM-DD). Default: today."
        }
    },
)

register_tool(
    tool_id="irs",
    name="Interest Rate Swap (IRS)",
    description="Price vanilla interest rate swaps using FRED treasury data. Calculate swap value, DV01, and compare fixed vs floating legs.",
    category="structuring",
    executor=execute_irs,
    params_schema={
        "notional": {
            "type": "number",
            "default": 10000000,
            "min": 100000,
            "max": 1000000000,
            "description": "Notional amount in $"
        },
        "fixed_rate": {
            "type": "number",
            "default": 0.04,
            "min": 0.001,
            "max": 0.20,
            "description": "Fixed rate (decimal, e.g., 0.045 = 4.5%)"
        },
        "float_index": {
            "type": "string",
            "default": "SOFR",
            "enum": ["SOFR", "EFFR", "FEDFUNDS"],
            "description": "Floating rate index"
        },
        "tenor": {
            "type": "string",
            "default": "5Y",
            "enum": ["2Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"],
            "description": "Swap maturity"
        },
        "payment_freq": {
            "type": "string",
            "default": "semiannual",
            "enum": ["quarterly", "semiannual", "annual"],
            "description": "Payment frequency"
        },
        "pricing_date": {
            "type": "string",
            "required": False,
            "description": "Valuation date (YYYY-MM-DD). Default: today."
        }
    },
)

register_tool(
    tool_id="cds",
    name="Credit Default Swap (CDS)",
    description="Calculate fair CDS spread using Merton model. Auto-estimates recovery rate from balance sheet and default probability from equity data.",
    category="structuring",
    executor=execute_cds,
    params_schema={
        "ticker": {
            "type": "string",
            "required": True,
            "description": "Reference entity ticker (e.g., AAPL, TSLA)"
        },
        "notional": {
            "type": "number",
            "default": 10000000,
            "min": 100000,
            "max": 1000000000,
            "description": "Notional amount in $"
        },
        "tenor": {
            "type": "string",
            "default": "5Y",
            "enum": ["1Y", "3Y", "5Y", "7Y", "10Y"],
            "description": "CDS maturity"
        },
        "pricing_date": {
            "type": "string",
            "required": False,
            "description": "Valuation date (YYYY-MM-DD). Default: today."
        }
    },
)


# -----------------------------------------------------------------------------
# Alternatives Tools
# -----------------------------------------------------------------------------

register_tool(
    tool_id="commodity_ratio",
    name="Commodity Ratio",
    description="Analyze any commodity ratio for mean reversion. Presets: Gold/Silver, Gold/Oil, Oil/Gas, Copper/Gold, Silver/Copper. Or use custom symbols.",
    category="alternatives",
    executor=execute_commodity_ratio,
    params_schema={
        "preset": {
            "type": "string",
            "default": "gold_silver",
            "enum": ["gold_silver", "gold_oil", "oil_gas", "copper_gold", "silver_copper", "custom"],
            "description": "Preset pair or 'custom' for manual symbols"
        },
        "numerator": {"type": "string", "required": False, "description": "Numerator symbol (for custom, e.g. GCUSD)"},
        "denominator": {"type": "string", "required": False, "description": "Denominator symbol (for custom, e.g. SIUSD)"},
        "lookback_days": {"type": "number", "default": 365, "min": 60, "max": 756, "description": "Historical lookback (days)"},
        "high_z_threshold": {"type": "number", "default": 1.5, "min": 1.0, "max": 3.0, "description": "Z-score for DENOM_CHEAP signal"},
        "low_z_threshold": {"type": "number", "default": -1.5, "min": -3.0, "max": -1.0, "description": "Z-score for NUM_CHEAP signal"},
    },
)

register_tool(
    tool_id="commodity_momentum",
    name="Commodity Momentum",
    description="Screen and rank commodities by momentum with optional HMM regime detection. Calculates ROC, trend strength, and signal multipliers.",
    category="alternatives",
    executor=execute_commodity_momentum,
    params_schema={
        "symbols": {
            "type": "array",
            "items": "string",
            "default": ["Gold (GCUSD)", "Silver (SIUSD)", "Crude Oil WTI (CLUSD)", "Natural Gas (NGUSD)", "Copper (HGUSD)", "Brent Crude (BZUSD)"],
            "enum": [
                "Gold (GCUSD)",
                "Silver (SIUSD)",
                "Platinum (PLUSD)",
                "Palladium (PAUSD)",
                "Copper (HGUSD)",
                "Crude Oil WTI (CLUSD)",
                "Brent Crude (BZUSD)",
                "Natural Gas (NGUSD)",
                "Heating Oil (HOUSD)",
                "RBOB Gasoline (RBUSD)",
                "Corn (ZCUSD)",
                "Soybeans (ZSUSD)",
                "Soybean Meal (ZMUSD)",
                "Soybean Oil (ZLUSD)",
                "Wheat (ZWUSD)",
                "Wheat CBOT (KEUSD)",
                "Oats (ZOUSD)",
                "Rough Rice (ZRUSD)",
                "Sugar (SBUSD)",
                "Cocoa (CCUSD)",
                "Coffee (KCUSD)",
                "Cotton (CTUSD)",
                "Live Cattle (LCUSD)",
                "Lean Hogs (LHUSD)",
                "Feeder Cattle (FCUSD)",
                "Class III Milk (DAUSD)",
                "Nonfat Dry Milk (DKUSD)",
                "Butter (GFUSD)",
                "Orange Juice (OJUSD)",
                "Lumber (LBUSD)",
            ],
            "description": "Select commodities to screen"
        },
        "lookback_days": {"type": "number", "default": 120, "min": 30, "max": 365, "description": "Historical lookback (days)"},
        "detect_regime": {"type": "boolean", "default": True, "description": "Enable HMM regime detection"},
    },
)

register_tool(
    tool_id="commodity_seasonal",
    name="Commodity Seasonality",
    description="Analyze historical seasonal patterns for commodities. Identifies best/worst months, YTD vs seasonal expectations, and forward-looking bias.",
    category="alternatives",
    executor=execute_commodity_seasonal,
    params_schema={
        "symbol": {
            "type": "string",
            "required": True,
            "enum": [
                "Gold (GCUSD)",
                "Silver (SIUSD)",
                "Platinum (PLUSD)",
                "Palladium (PAUSD)",
                "Copper (HGUSD)",
                "Crude Oil WTI (CLUSD)",
                "Brent Crude (BZUSD)",
                "Natural Gas (NGUSD)",
                "Heating Oil (HOUSD)",
                "RBOB Gasoline (RBUSD)",
                "Corn (ZCUSD)",
                "Soybeans (ZSUSD)",
                "Soybean Meal (ZMUSD)",
                "Soybean Oil (ZLUSD)",
                "Wheat (ZWUSD)",
                "Wheat CBOT (KEUSD)",
                "Oats (ZOUSD)",
                "Rough Rice (ZRUSD)",
                "Sugar (SBUSD)",
                "Cocoa (CCUSD)",
                "Coffee (KCUSD)",
                "Cotton (CTUSD)",
                "Live Cattle (LCUSD)",
                "Lean Hogs (LHUSD)",
                "Feeder Cattle (FCUSD)",
                "Class III Milk (DAUSD)",
                "Nonfat Dry Milk (DKUSD)",
                "Butter (GFUSD)",
                "Orange Juice (OJUSD)",
                "Lumber (LBUSD)",
            ],
            "description": "Select commodity to analyze"
        },
        "years_history": {
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 5,
            "description": "Years of historical data (1-5)"
        },
    },
)

register_tool(
    tool_id="crypto_beta",
    name="Crypto-Equity Beta",
    description="Detect crypto-equity correlation regime (RISK_ON/RISK_OFF/NEUTRAL). Analyze how crypto correlates with equity markets.",
    category="alternatives",
    executor=execute_crypto_beta,
    params_schema={
        "crypto_symbol": {
            "type": "string",
            "default": "BTCUSD",
            "enum": ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "MATICUSD", "DOTUSD", "LINKUSD"],
            "description": "Primary cryptocurrency"
        },
        "equity_symbol": {
            "type": "string",
            "default": "SPY",
            "enum": ["SPY", "QQQ", "IWM", "DIA", "VTI", "XLK", "XLF", "XLE", "ARKK", "TLT"],
            "description": "Primary equity benchmark"
        },
        "additional_cryptos": {
            "type": "array",
            "items": "string",
            "default": [],
            "enum": ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "MATICUSD", "DOTUSD", "LINKUSD"],
            "description": "Additional cryptos for correlation matrix"
        },
        "additional_equities": {
            "type": "array",
            "items": "string",
            "default": [],
            "enum": ["SPY", "QQQ", "IWM", "DIA", "VTI", "XLK", "XLF", "XLE", "ARKK", "TLT"],
            "description": "Additional equities for correlation matrix"
        },
        "lookback_days": {"type": "number", "default": 365, "min": 60, "max": 756, "description": "Historical lookback (days)"},
        "high_z_threshold": {"type": "number", "default": 1.5, "min": 1.0, "max": 3.0, "description": "Z-score for RISK_ON signal"},
        "low_z_threshold": {"type": "number", "default": -1.5, "min": -3.0, "max": -1.0, "description": "Z-score for RISK_OFF signal"},
    },
)

register_tool(
    tool_id="fx_carry",
    name="FX Carry Trade Screener",
    description="Screen FX pairs by carry trade opportunities. Auto-fetches interest rates from FRED and calculates risk-adjusted carry (Sharpe ratio).",
    category="alternatives",
    executor=execute_fx_carry,
    params_schema={
        "pairs": {
            "type": "array",
            "items": "string",
            "required": True,
            "default": ["AUD/JPY (AUDJPY)", "NZD/JPY (NZDJPY)", "USD/JPY (USDJPY)", "EUR/USD (EURUSD)", "GBP/USD (GBPUSD)", "AUD/USD (AUDUSD)"],
            "enum": [
                "AUD/JPY (AUDJPY)", "NZD/JPY (NZDJPY)", "USD/JPY (USDJPY)", "EUR/USD (EURUSD)",
                "GBP/USD (GBPUSD)", "AUD/USD (AUDUSD)", "NZD/USD (NZDUSD)", "USD/CHF (USDCHF)",
                "EUR/JPY (EURJPY)", "GBP/JPY (GBPJPY)", "CHF/JPY (CHFJPY)", "CAD/JPY (CADJPY)",
                "EUR/GBP (EURGBP)", "EUR/CHF (EURCHF)", "EUR/AUD (EURAUD)", "EUR/CAD (EURCAD)",
                "GBP/CHF (GBPCHF)", "GBP/AUD (GBPAUD)", "USD/CAD (USDCAD)", "AUD/CAD (AUDCAD)",
                "AUD/NZD (AUDNZD)", "NZD/CAD (NZDCAD)", "USD/MXN (USDMXN)", "USD/ZAR (USDZAR)",
                "EUR/NOK (EURNOK)", "EUR/SEK (EURSEK)", "USD/NOK (USDNOK)", "USD/SEK (USDSEK)",
                "USD/SGD (USDSGD)", "USD/HKD (USDHKD)", "USD/CNY (USDCNY)", "USD/INR (USDINR)",
                "USD/BRL (USDBRL)", "USD/TRY (USDTRY)", "USD/PLN (USDPLN)", "USD/KRW (USDKRW)",
            ],
            "description": "Select FX pairs to screen (multi-select)"
        },
        "lookback_days": {
            "type": "number",
            "default": 180,
            "min": 60,
            "max": 365,
            "description": "Historical lookback period (days)"
        },
        "use_regime_detection": {
            "type": "boolean",
            "default": False,
            "description": "Enable HMM regime detection (advanced)"
        },
    },
)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/tools")
async def list_tools(request: Request):
    """List all available Canvas tools."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    tools = [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t["category"],
            "params_schema": t["params_schema"],
        }
        for t in TOOL_REGISTRY.values()
    ]
    return {"tools": tools}


@router.get("/analysis/cache/{analysis_id}")
async def get_cached_analysis(analysis_id: str, request: Request):
    """Retrieve cached tool analysis results (from start_tool_analysis agent action)."""
    from core.cache import cache_get

    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    cache_key = f"analysis:{analysis_id}"
    result = await cache_get(cache_key)

    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found or expired.")

    # Verify ownership — deny unless user_id explicitly matches
    metadata = result.get("_metadata", {})
    cached_user_id = metadata.get("user_id")
    if not cached_user_id or cached_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Strip internal metadata
    return {k: v for k, v in result.items() if not k.startswith("_")}


@router.post("/run/{tool_id}")
async def run_tool(tool_id: str, request: Request):
    """Run any registered tool by ID. Builds process graph generically."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if tool_id not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    tool = TOOL_REGISTRY[tool_id]

    # Parse params from request body
    try:
        params = await request.json()
    except:
        params = {}

    logger.info(f"Canvas run: {tool_id} for user {user_id}, params={params}")

    try:
        result = await tool["executor"](user_id, org_id, params)

        # Build generic process graph for ANY tool
        if result.get("status") == "success":
            graph_steps, graph_edges = build_process_graph(
                tool_name=tool["name"],
                tickers=result.get("tickers", []),
                has_charts=bool(result.get("charts")),
                has_stats=bool(result.get("stats_table")),
                has_metrics=bool(result.get("metrics")),
            )
            result["graph_steps"] = graph_steps
            result["graph_edges"] = graph_edges

        return result
    except Exception as e:
        logger.error(f"Tool {tool_id} failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# =============================================================================
# PROCESS PERSISTENCE ENDPOINTS
# =============================================================================

@router.post("/processes")
async def save_process(request: Request, body: SaveProcessRequest):
    """Save a canvas process to the database."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    # Store metric_cards inside metrics to avoid schema changes
    metrics_with_cards = {**body.metrics, "_metric_cards": body.metric_cards}

    process_id = await pg.save_canvas_process(
        user_id=user_id,
        org_id=org_id,
        tool_id=body.tool_id,
        tickers=body.tickers,
        weights=body.weights,
        metrics=metrics_with_cards,
        stats_table=body.stats_table,
        charts=body.charts,
        name=body.name,
        object_type=body.object_type,
        hmm_enabled=body.hmm_enabled,
        current_regime=body.current_regime,
        regime_params=body.regime_params,
        graph_steps=body.graph_steps,
        graph_edges=body.graph_edges,
        params=body.params,
        process_type=body.process_type,
        config=body.config,
    )

    if not process_id:
        raise HTTPException(status_code=500, detail="Failed to save process")

    logger.info(f"Canvas process saved: {process_id} for user {user_id}")
    return {"status": "success", "id": process_id}


@router.get("/processes")
async def list_processes(
    request: Request,
    tool_id: Optional[str] = None,
    process_type: Optional[str] = None,
    limit: int = 50,
    archived: Optional[bool] = False,
):
    """List saved canvas processes for the user."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    processes = await pg.get_canvas_processes(
        user_id=user_id,
        org_id=org_id,
        tool_id=tool_id,
        process_type=process_type,
        limit=limit,
        archived=archived,
    )

    return {"processes": processes}


@router.get("/processes/{process_id}")
async def get_process(process_id: str, request: Request):
    """Get a single canvas process by ID."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    process = await pg.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )

    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    return process


@router.patch("/processes/{process_id}")
async def update_process(process_id: str, request: Request, body: UpdateProcessRequest):
    """Update a canvas process (e.g., rename)."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    success = await pg.update_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
        name=body.name,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Process not found")

    logger.info(f"Canvas process updated: {process_id} for user {user_id}")
    return {"status": "success"}


@router.put("/processes/{process_id}")
async def full_update_process(process_id: str, request: Request, body: FullUpdateProcessRequest):
    """Full update of a canvas process (name, tickers, params, config)."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    # Verify process exists and belongs to user
    existing = await pg.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Process not found")

    success = await pg.full_update_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
        name=body.name,
        tickers=body.tickers,
        params=body.params,
        config=body.config,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update process")

    logger.info(f"Canvas process fully updated: {process_id} for user {user_id}")
    return {"status": "success", "id": process_id}


@router.delete("/processes/{process_id}")
async def delete_process(process_id: str, request: Request, permanent: bool = False):
    """Delete a canvas process. Soft-deletes by default; permanent=true for hard delete."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    if permanent:
        success = await pg.permanent_delete_canvas_process(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
        )
    else:
        success = await pg.delete_canvas_process(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
        )

    if not success:
        raise HTTPException(status_code=404, detail="Process not found or already deleted")

    logger.info(f"Canvas process {'permanently deleted' if permanent else 'archived'}: {process_id} for user {user_id}")
    return {"status": "success"}


@router.post("/processes/{process_id}/restore")
async def restore_process(process_id: str, request: Request):
    """Restore a soft-deleted (archived) canvas process."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    success = await pg.restore_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Process not found")

    return {"status": "success"}


# =============================================================================
# CANVAS CHAT THREAD MANAGEMENT
# =============================================================================


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


@router.get("/chat/threads")
async def get_chat_threads(request: Request):
    """Get all Canvas chat threads for the user."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    threads = await pg.get_canvas_chat_threads(
        user_id=user_id,
        org_id=org_id,
    )
    return {"threads": threads}


@router.post("/chat/threads")
async def create_chat_thread(request: Request, body: CreateThreadRequest):
    """Create a new Canvas chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    thread = await pg.create_canvas_chat_thread(
        user_id=user_id,
        org_id=org_id,
        title=body.title,
    )

    if not thread:
        raise HTTPException(status_code=500, detail="Failed to create thread")

    return thread


@router.get("/chat/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, request: Request):
    """Get messages for a Canvas chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    messages = await pg.get_canvas_chat_messages(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )
    return {"messages": messages}


@router.post("/chat/threads/{thread_id}/messages")
async def append_canvas_chat_message(thread_id: str, request: Request):
    """Append a message to a Canvas chat thread (used by frontend on cancel)."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    role = body.get("role")
    content = body.get("content", "")
    if role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'assistant'")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    result = await pg.save_canvas_chat_message(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        content=content,
        metadata=body.get("metadata"),
        process_id=body.get("process_id"),
        tool_id=body.get("tool_id"),
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to save message")

    return result


@router.delete("/chat/threads/{thread_id}")
async def delete_chat_thread(thread_id: str, request: Request):
    """Delete a Canvas chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    success = await pg.delete_canvas_chat_thread(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")

    return {"status": "success"}


@router.patch("/chat/messages/{message_id}/metadata")
async def update_message_metadata(message_id: str, request: Request):
    """Update metadata (tool events, reasoning) on a chat message."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    metadata = body.get("metadata")
    if metadata is None:
        raise HTTPException(status_code=400, detail="metadata field required")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    success = await pg.update_canvas_chat_message_metadata(
        user_id=user_id,
        message_id=message_id,
        metadata=metadata,
        org_id=org_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"status": "success"}


# ─── Workspace Snapshot (Chat-Workspace Binding) ────────────────────────────

@router.get("/chat/threads/{thread_id}/workspace")
async def get_workspace_snapshot(thread_id: str, request: Request):
    """Get workspace snapshot for a chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()
    snapshot = await pg.get_canvas_workspace_snapshot(
        thread_id=thread_id, user_id=user_id, org_id=org_id,
    )
    return {"snapshot": snapshot}


@router.patch("/chat/threads/{thread_id}/workspace")
async def save_workspace_snapshot(thread_id: str, request: Request):
    """Save workspace snapshot for a chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    snapshot = {
        "captured_at": body.get("captured_at"),
        "tabs": body.get("tabs"),
        "activeTabId": body.get("activeTabId"),
    }

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()
    success = await pg.save_canvas_workspace_snapshot(
        thread_id=thread_id, user_id=user_id, snapshot=snapshot, org_id=org_id,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save workspace snapshot")
    return {"status": "success"}


@router.delete("/chat/threads/{thread_id}/workspace")
async def clear_workspace_snapshot(thread_id: str, request: Request):
    """Clear workspace snapshot for a chat thread."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()
    success = await pg.clear_canvas_workspace_snapshot(
        thread_id=thread_id, user_id=user_id, org_id=org_id,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear workspace snapshot")
    return {"status": "success"}


class ApplyUpdateRequest(BaseModel):
    """Request to apply a pending tool re-run to a process."""
    process_id: str
    tool_id: str
    tickers: List[str]
    weights: Optional[List[float]] = None
    params: Optional[Dict[str, Any]] = None
    full_result: Dict[str, Any]


@router.post("/processes/{process_id}/apply-update")
async def apply_tool_update(process_id: str, request: Request, body: ApplyUpdateRequest):
    """Apply a pending tool re-run result to update the process."""
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()

    # Verify process exists and belongs to user
    existing = await pg.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Process not found")

    # Build the updated process data
    result = body.full_result
    metrics = result.get("metrics", {})
    if result.get("metric_cards"):
        metrics["_metric_cards"] = result["metric_cards"]

    # Prefer new HMM values from result, fall back to existing
    hmm_enabled = result.get("hmm_enabled", existing.get("hmm_enabled", False))
    current_regime = result.get("current_regime") or existing.get("current_regime")
    regime_params = result.get("regime_params") or existing.get("regime_params")

    # Update the process using the full update method
    success = await pg.update_canvas_process_full(
        user_id=user_id,
        process_id=process_id,
        tool_id=body.tool_id,
        tickers=body.tickers,
        weights=body.weights,
        metrics=metrics,
        stats_table=result.get("stats_table", []),
        charts=result.get("charts", {}),
        org_id=org_id,
        params=body.params,
        name=existing.get("name"),
        hmm_enabled=hmm_enabled,
        current_regime=current_regime,
        regime_params=regime_params,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update process")

    logger.info(f"Applied tool update to process {process_id} for user {user_id}")
    return {"status": "success", "process_id": process_id}


# =============================================================================
# TEMPORARY DEBUG ENDPOINT
# =============================================================================

@router.post("/chat/debug-log")
async def debug_log(request: Request):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    for line in body.get("lines", []):
        logger.info(f"[FRONTEND] {line}")
    return {"ok": True}


@router.post("/chat/cancel")
async def canvas_chat_cancel(request: Request, session_id: str = Query(...)):
    """Cancel an active canvas chat stream."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    cancelled = await cancel_canvas_stream(session_id, user_id)
    logger.info(f"Canvas chat cancel: session={session_id} user={user_id} result={'cancelled' if cancelled else 'not_found'}")
    return {"status": "cancelled" if cancelled else "not_found"}


# CANVAS AI CHAT STREAMING ENDPOINT
# =============================================================================


@router.get("/chat/stream")
async def canvas_chat_stream(
    message: str,
    request: Request,
    process_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    selected_model: Optional[str] = Query(None, alias="model"),
    last_event_id: Optional[str] = None,
    data_context: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """
    Stream Canvas AI chat with SSE events.

    Args:
        message: User's message/question
        process_id: Optional Canvas process ID to provide context
        thread_id: Optional thread ID for conversation continuity
        selected_model: Optional model override
        last_event_id: Optional event ID for resume (skip thread creation if present)
    """
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None) or ''

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Register stream for cancellation (generate session_id if not provided)
    effective_session_id = session_id or str(uuid.uuid4())
    cancel_event = await register_canvas_stream(effective_session_id, user_id)

    # Handle resume requests before starting the generator
    if last_event_id:
        async def resume_rejected():
            yield f"id: 1\ndata: {json.dumps({'type': 'resume_rejected', 'message': 'Please wait for current response'})}\n\n"
        return StreamingResponse(resume_rejected(), media_type="text/event-stream")

    async def event_generator() -> AsyncIterator[str]:
        seq = 0
        queue: asyncio.Queue = asyncio.Queue()

        bg_task = asyncio.create_task(
            run_canvas_stream(
                queue=queue,
                cancel_event=cancel_event,
                user_id=user_id,
                org_id=org_id,
                message=message,
                process_id=process_id,
                thread_id=thread_id,
                selected_model=selected_model,
                data_context=data_context,
                session_id=effective_session_id,
            )
        )
        await set_canvas_stream_task(effective_session_id, bg_task)

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if payload is None:
                    break

                seq += 1
                yield f"id: {seq}\ndata: {json.dumps(payload)}\n\n"
        finally:
            if not cancel_event.is_set():
                cancel_event.set()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
