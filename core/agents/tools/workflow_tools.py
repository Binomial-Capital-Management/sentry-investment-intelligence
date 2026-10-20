"""
Workflow Tools for Canvas AI Agent - Tool Workflow Launcher.

These tools enable the AI to start any Canvas tool workflow analysis
from natural language prompts, e.g.:
- "Run a Monte Carlo simulation on AAPL, MSFT with 10,000 simulations"
- "Analyze factor exposures for my portfolio"

The workflow:
1. AI calls start_tool_analysis(tool_id, tickers, weights, params)
2. Tool validates inputs against TOOL_REGISTRY
3. Tool executes the tool's executor function (same as /api/canvas/run/{tool_id})
4. Tool caches result for frontend retrieval
5. Tool returns {status: "success", action: {...}} with analysis_id
6. Agentic hooks emit agent_action SSE event to frontend
7. Frontend fetches cached results and displays in ToolWorkflow Step 4 view

Context Management:
    Uses the same contextvars pattern as workspace_tools.py.
    Tools access user_id, org_id from the workspace context.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from agents import function_tool

from core.cache import cache_set
from core.agents.tools.workspace_tools import get_workspace_context
from core.utils.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


@function_tool(strict_mode=False)  # Uses Dict[str, Any] for params
async def start_tool_analysis(
    tool_id: str,
    tickers: List[str],
    weights: Optional[List[float]] = None,
    params: Optional[str] = None,
) -> str:
    """
    Start a Canvas tool workflow analysis.
    
    Use this to run any quantitative analysis tool from the Canvas platform.
    The analysis results (charts, metrics, statistics) will be displayed
    in the ToolWorkflow results view.
    
    Args:
        tool_id: The tool to run. Available tools by category:
        
            RISK:
            - monte_carlo: Monte Carlo simulation with VaR metrics
            - var: Value at Risk (parametric, historical, Monte Carlo)
            - barra_factors: Factor exposure and risk decomposition
            - optimization: Markowitz portfolio optimization
            - stress_test: Correlation stress testing
            - drawdown: Maximum drawdown analysis
            - hedge: Factor-neutral hedge construction
            - systemic_risk: PageRank network risk analysis
            - network_risk: Graph theory portfolio analysis
            - rolling_corr: Time-varying correlation
            - implied_corr: Market-implied correlation from options
            - fft_denoise: FFT denoising for trend extraction
            
            QUANT:
            - vol_surface: 3D implied volatility surface
            - correlation_matrix: Correlation heatmap with clustering
            - pca_analysis: Principal component analysis
            - cointegration: Pairs trading cointegration tests
            - arima_forecast: Time series forecasting
            - arimax: Multi-factor macro forecasting
            - dealer_gamma: Dealer gamma regime estimation
            - confluence: Multi-factor signal scanner
            - greeks_surface: 3D options Greeks surfaces
            - mean_reversion: Mean reversion trading signals
            - iv_rv_screener: IV vs RV comparison
            - squeeze_detector: Gamma/short squeeze detection
            - sector_rotation: Sector rotation flow analysis
            - gex: Gamma exposure analysis
            - option_pricing: Black-Scholes option pricing
            - earnings_pattern: Earnings pattern analysis
            - vanna_charm: Second-order Greeks flow
            - hedge_path: Dijkstra optimal hedge finder
            - recession_field: Recession early warning
            - geodesic: Portfolio geodesic distance
            - herding: Herding regime detection
            
            VALUATION:
            - reverse_dcf: Implied growth rate from price
            - comps: Comparable companies analysis
            - epv: Earnings Power Value
            - rim: Residual Income Model (banks)
            - dcf_monte_carlo: Probabilistic DCF
            - dcf_traditional: Traditional 2/3-stage DCF
            
            STRUCTURING:
            - dispersion: Index vs constituent dispersion
            - var_swap: Variance swap pricing
            - exotic_pricing: Exotic options (barrier, asian, etc.)
            - swaption: Interest rate swaption pricing
            - irs: Interest rate swap pricing
            - cds: Credit default swap pricing
            
            SENTIMENT:
            - finbert_sentiment: NLP news sentiment analysis
            
            ALTERNATIVES:
            - commodity_ratio: Commodity ratio analysis
            - commodity_momentum: Commodity momentum screening
            - commodity_seasonal: Seasonality analysis
            - crypto_beta: Crypto-equity correlation
            - fx_carry: FX carry trade screener
        
        tickers: Stock tickers to analyze (e.g., ["AAPL", "MSFT", "GOOGL"]).
                 Most tools require at least 1 ticker, portfolio tools need 2+.
        
        weights: Optional portfolio weights. Must sum to 1.0 if provided.
                 If not provided, equal weights are used.
                 Example: [0.5, 0.3, 0.2] for 50%, 30%, 20% allocation.
        
        params: Optional tool-specific parameters. Common params include:
            - n_simulations (int): Monte Carlo paths (100-10000)
            - time_horizon (int): Forecast horizon in trading days
            - confidence_level (float): VaR confidence (0.90-0.99)
            - period (str): Historical data period ("6mo", "1y", "2y", "5y")
            - method (str): Calculation method (varies by tool)
            
            Check tool documentation for full parameter schemas.
    
    Returns:
        On success: {
            "status": "success",
            "message": "Completed Monte Carlo Simulation analysis",
            "action": {
                "type": "start_tool_analysis",
                "analysis_id": "uuid-...",
                "tool_id": "monte_carlo",
                "tool_name": "Monte Carlo Simulation",
                "tickers": ["AAPL", "MSFT"]
            },
            "summary": {
                "metric_count": 12,
                "chart_count": 3
            }
        }
        On error: {
            "status": "error",
            "message": "Unknown tool: invalid_tool"
        }
    
    Examples:
        # Basic Monte Carlo simulation
        start_tool_analysis("monte_carlo", ["AAPL", "MSFT", "GOOGL"])
        
        # VaR with custom parameters
        start_tool_analysis("var", ["AAPL"], params={"confidence_levels": [0.95, 0.99], "method": "all"})
        
        # Portfolio optimization with weights
        start_tool_analysis("optimization", ["AAPL", "MSFT", "NVDA"], [0.4, 0.4, 0.2], {"method": "max_sharpe"})
        
        # DCF valuation
        start_tool_analysis("dcf_traditional", ["AAPL"], params={"stages": "2", "terminal_growth": 0.025})
    """
    params_dict: Dict[str, Any] = json.loads(params) if isinstance(params, str) and params else (params if isinstance(params, dict) else {})

    from api.routers.canvas.tool_workflow.tools.loader import TOOL_REGISTRY
    
    ctx = get_workspace_context()
    user_id = ctx.get("user_id") if ctx else None
    org_id = ctx.get("org_id") if ctx else None
    
    if not user_id:
        return json.dumps({
            "status": "error",
            "message": "No user context available. Cannot execute tool analysis.",
            "code": "NO_CONTEXT",
        })
    
    if not check_rate_limit(user_id, "tool_analysis", limit=5, window=60):
        return json.dumps({
            "status": "error",
            "message": "Rate limit exceeded. Please wait before running more analyses.",
            "code": "RATE_LIMIT",
            "retry_after": 60,
        })
    
    if tool_id not in TOOL_REGISTRY:
        available_tools = sorted(TOOL_REGISTRY.keys())
        return json.dumps({
            "status": "error",
            "message": f"Unknown tool: '{tool_id}'. Use one of: {', '.join(available_tools[:20])}...",
            "code": "UNKNOWN_TOOL",
            "available_tools": available_tools,
        })
    
    if not tickers or len(tickers) == 0:
        return json.dumps({
            "status": "error",
            "message": "At least one ticker is required.",
            "code": "NO_TICKERS",
        })
    
    tickers = [t.upper().strip() for t in tickers]
    
    if weights:
        if len(weights) != len(tickers):
            return json.dumps({
                "status": "error",
                "message": f"Weights count ({len(weights)}) must match tickers count ({len(tickers)}).",
                "code": "WEIGHT_COUNT_MISMATCH",
            })
        
        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 0.01:
            return json.dumps({
                "status": "error",
                "message": f"Weights must sum to 1.0, but got {weight_sum:.4f}.",
                "code": "WEIGHT_SUM_INVALID",
            })
    else:
        weights = [1.0 / len(tickers)] * len(tickers)
    
    tool_info = TOOL_REGISTRY[tool_id]
    tool_name = tool_info.get("name", tool_id)
    
    logger.info(f"[WORKFLOW_TOOL] Starting {tool_id} analysis: tickers={tickers}, params={params_dict}")
    
    try:
        full_params = {
            "tickers": tickers,
            "weights": weights,
            **params_dict,
        }
        
        executor = tool_info["executor"]
        result = await executor(user_id, org_id, full_params)
        
        if result.get("status") == "error":
            error_msg = result.get("error") or result.get("message") or "Unknown error"
            logger.warning(f"[WORKFLOW_TOOL] Tool execution failed: {error_msg}")
            return json.dumps({
                "status": "error",
                "message": f"{tool_name} failed: {error_msg}",
                "code": "EXECUTION_FAILED",
            })
        
        analysis_id = str(uuid.uuid4())
        
        cached_result = {
            **result,
            "_metadata": {
                "analysis_id": analysis_id,
                "tool_id": tool_id,
                "tool_name": tool_name,
                "tickers": tickers,
                "weights": weights,
                "params": params_dict,
                "user_id": user_id,
            }
        }
        
        await cache_set(f"analysis:{analysis_id}", cached_result, ttl=900)
        
        metric_count = len(result.get("metric_cards", []))
        chart_count = len(result.get("charts", {}))
        stats_count = len(result.get("stats_table", []))
        
        logger.info(f"[WORKFLOW_TOOL] Completed {tool_id}: {metric_count} metrics, {chart_count} charts, {stats_count} stats")
        
        return json.dumps({
            "status": "success",
            "message": f"Completed {tool_name} analysis for {', '.join(tickers)}",
            "action": {
                "type": "start_tool_analysis",
                "analysis_id": analysis_id,
                "tool_id": tool_id,
                "tool_name": tool_name,
                "tickers": tickers,
            },
            "summary": {
                "metric_count": metric_count,
                "chart_count": chart_count,
                "stats_count": stats_count,
            }
        })
        
    except Exception as e:
        logger.exception(f"[WORKFLOW_TOOL] Error executing {tool_id}")
        error_msg = str(e)
        
        return json.dumps({
            "status": "error",
            "message": f"Failed to execute {tool_name}: {error_msg}",
            "code": "INTERNAL_ERROR",
        })


# =============================================================================
# List of all workflow tools for registration
# =============================================================================

WORKFLOW_TOOLS = [
    start_tool_analysis,
]
