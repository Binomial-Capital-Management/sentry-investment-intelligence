"""Monte Carlo Executor for Canvas.

Handles execution of Monte Carlo simulation and result formatting.
Graph building is done generically by the Canvas router - NOT here.
"""

from typing import Dict, Any, Optional, List
import logging

from .charts import build_price_paths_chart, build_histogram_chart

logger = logging.getLogger(__name__)


async def execute_monte_carlo(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Monte Carlo simulation using the internal callable.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including portfolio_id, tickers, weights, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.risk_tools.monte_carlo_tool import run_monte_carlo_internal
    
    # Resolve tickers from portfolio or direct input
    tickers = params.get('tickers')
    weights = params.get('weights')
    
    if params.get('portfolio_id'):
        tickers, weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
    
    if not tickers:
        return {"status": "error", "error": "Provide portfolio_id or tickers"}
    
    # Call the internal callable with skip_charts=True to get raw data
    # Use "tied" covariance by default to prevent HMM overfitting (extreme regimes)
    result = await run_monte_carlo_internal(
        tickers=tickers,
        weights=weights,
        portfolio_value=params.get('portfolio_value', 1_000_000),
        n_simulations=params.get('n_simulations', 1000),
        time_horizon=params.get('time_horizon', 252),
        period=params.get('period', '2y'),  # More data for HMM stability
        use_hmm=params.get('use_hmm', False),
        n_regimes=params.get('n_regimes', 2),  # 2 regimes more stable than 3
        hmm_covariance_type=params.get('hmm_covariance_type', 'tied'),  # Prevents extreme regimes
        hmm_n_init=params.get('hmm_n_init', 15),  # More initializations for robustness
        hmm_features=params.get('hmm_features', None),  # Univariate by default (most stable)
        skip_charts=True,  # Don't build chat-style charts
    )
    
    if result.get('status') == 'error':
        return {"status": "error", "error": result.get('error')}
    
    # Extract results
    mc = result.get('monte_carlo_results', {})
    raw_paths = result.get('raw_paths_data', {})
    
    logger.info(f"MC results keys: {list(mc.keys())}")
    logger.info(f"CVaR values - pct: {mc.get('CVaR_0.95_pct')}, usd: {mc.get('CVaR_0.95_usd')}")
    logger.info(f"VaR values - pct: {mc.get('VaR_0.95_pct')}, usd: {mc.get('VaR_0.95_usd')}")
    logger.info(f"Portfolio value: {result.get('portfolio_value')}")
    
    # Build Canvas-specific charts
    price_paths_chart = None
    histogram_chart = None
    
    if raw_paths:
        representative_paths = raw_paths.get('representative_paths', [])
        terminal_returns = raw_paths.get('terminal_returns', [])
        time_horizon = raw_paths.get('time_horizon', 252)
        
        price_paths_chart = build_price_paths_chart(representative_paths, time_horizon)
        histogram_chart = build_histogram_chart(terminal_returns, bin_size=2.0)
    
    # Build stats table
    stats_table = _build_stats_table(mc, result)
    
    # Build metrics (raw) and metric cards (displayable)
    metrics = _extract_metrics(mc, result)
    metric_cards = _build_metric_cards(mc, result)
    
    # Return results - graph is built generically by the Canvas router
    # Use resolved tickers/weights (from portfolio or params) as source of truth
    return {
        "status": "success",
        "tool_id": "monte_carlo",
        "tickers": result.get('tickers', tickers),
        "weights": weights if weights else result.get('weights', []),
        "metrics": metrics,
        "metric_cards": metric_cards,  # Self-describing display cards
        "stats_table": stats_table,
        "charts": {
            "price_paths": price_paths_chart,
            "histogram": histogram_chart,
        },
        "hmm_enabled": result.get('hmm_enabled', False),
        "current_regime": mc.get('current_regime'),
        "regime_params": mc.get('regime_params'),
    }


async def _resolve_portfolio(
    user_id: str, 
    org_id: Optional[str], 
    portfolio_id: str
) -> tuple[Optional[List[str]], Optional[List[float]]]:
    """Resolve tickers and weights from portfolio ID."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return None, None
        
        actual_portfolio = portfolio.get("portfolio", {})
        tickers = actual_portfolio.get('tickers', [])
        weights = actual_portfolio.get('weights', [])
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers) if tickers else None
        return tickers, weights
    except Exception as e:
        logger.warning(f"Could not fetch portfolio: {e}")
    return None, None


def _extract_metrics(mc: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metrics from MC results into standardized format."""
    return {
        "portfolio_value": result.get('portfolio_value'),
        "var_95": mc.get('VaR_0.95_usd'),
        "var_99": mc.get('VaR_0.99_usd'),
        "var_95_pct": mc.get('VaR_0.95_pct'),
        "var_99_pct": mc.get('VaR_0.99_pct'),
        "cvar_95": mc.get('CVaR_0.95_usd'),
        "cvar_99": mc.get('CVaR_0.99_usd'),
        "cvar_95_pct": mc.get('CVaR_0.95_pct'),
        "cvar_99_pct": mc.get('CVaR_0.99_pct'),
        "expected_return": mc.get('mean_return'),
        "volatility": mc.get('volatility'),
        "sharpe_ratio": mc.get('sharpe_ratio'),
        "max_drawdown": mc.get('max_drawdown'),
        "skewness": mc.get('skewness'),
        "kurtosis": mc.get('kurtosis'),
    }


def _build_metric_cards(mc: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build displayable metric cards with styling metadata."""
    def fmt_currency(v):
        return f"${v:,.0f}" if v else "—"
    def fmt_pct(v):
        if v is None:
            return "—"
        pct = v * 100 if abs(v) <= 1 else v
        return f"{pct:+.1f}%" if pct >= 0 else f"{pct:.1f}%"
    
    var_95_pct = mc.get('VaR_0.95_pct', 0)
    cvar_95_pct = mc.get('CVaR_0.95_pct', 0)
    mean_return = mc.get('mean_return', 0)
    volatility = mc.get('volatility', 0)
    
    return [
        {
            "id": "var_95",
            "label": "VaR 95%",
            "value": fmt_currency(mc.get('VaR_0.95_usd')),
            "description": fmt_pct(var_95_pct),
            "sentiment": "negative" if var_95_pct and var_95_pct < -0.1 else "neutral",
        },
        {
            "id": "cvar_95",
            "label": "CVaR 95%",
            "value": fmt_currency(mc.get('CVaR_0.95_usd')),
            "description": fmt_pct(cvar_95_pct),
            "sentiment": "negative" if cvar_95_pct and cvar_95_pct < -0.15 else "neutral",
        },
        {
            "id": "expected_return",
            "label": "Expected Return",
            "value": fmt_pct(mean_return),
            "sentiment": "positive" if mean_return and mean_return > 0 else "negative",
        },
        {
            "id": "volatility",
            "label": "Volatility",
            "value": fmt_pct(volatility),
            "sentiment": "neutral",
        },
    ]


def _build_stats_table(mc: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build comprehensive stats table for display."""
    paths_info = mc.get('paths', {})
    portfolio_value = result.get('portfolio_value', 1)
    
    return [
        {"category": "Portfolio", "metric": "Initial Value", "value": f"${result.get('portfolio_value', 0):,.0f}"},
        {"category": "Portfolio", "metric": "Simulations", "value": f"{result.get('n_simulations', 0):,}"},
        {"category": "Portfolio", "metric": "Time Horizon", "value": f"{result.get('time_horizon', 0)} days"},
        {"category": "Risk (95%)", "metric": "Value at Risk", "value": f"${mc.get('VaR_0.95_usd', 0):,.0f}", "pct": f"{mc.get('VaR_0.95_pct', 0)*100:.1f}%"},
        {"category": "Risk (95%)", "metric": "Conditional VaR", "value": f"${mc.get('CVaR_0.95_usd', 0):,.0f}", "pct": f"{mc.get('CVaR_0.95_pct', 0)*100:.1f}%"},
        {"category": "Risk (99%)", "metric": "Value at Risk", "value": f"${mc.get('VaR_0.99_usd', 0):,.0f}", "pct": f"{mc.get('VaR_0.99_pct', 0)*100:.1f}%"},
        {"category": "Risk (99%)", "metric": "Conditional VaR", "value": f"${mc.get('CVaR_0.99_usd', 0):,.0f}", "pct": f"{mc.get('CVaR_0.99_pct', 0)*100:.1f}%"},
        {"category": "Returns", "metric": "Expected Return", "value": f"{mc.get('mean_return', 0)*100:.2f}%"},
        {"category": "Returns", "metric": "Volatility", "value": f"{mc.get('volatility', 0)*100:.2f}%"},
        {"category": "Returns", "metric": "Min Return", "value": f"{mc.get('min_return', 0)*100:.2f}%"},
        {"category": "Returns", "metric": "Max Return", "value": f"{mc.get('max_return', 0)*100:.2f}%"},
        {"category": "Distribution", "metric": "Skewness", "value": f"{mc.get('skewness', 0):.3f}"},
        {"category": "Distribution", "metric": "Kurtosis", "value": f"{mc.get('kurtosis', 0):.3f}"},
        {"category": "Paths", "metric": "Median Terminal", "value": f"${paths_info.get('median', 0)*portfolio_value:,.0f}"},
        {"category": "Paths", "metric": "Mean Terminal", "value": f"${paths_info.get('mean', 0)*portfolio_value:,.0f}"},
    ]
