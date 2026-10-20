"""
Portfolio Optimization Canvas Executor

Markowitz mean-variance optimization with efficient frontier visualization.
"""
from typing import Dict, List, Any, Optional
import logging
import numpy as np

from .charts import build_efficient_frontier_chart, build_weights_chart

logger = logging.getLogger(__name__)


async def execute_optimization(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute portfolio optimization for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including tickers, weights, method, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.risk_modules.efficient_frontier import PortfolioOptimizer
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns
    
    tickers = params.get('tickers')
    current_weights = params.get('weights')
    
    # Resolve portfolio if provided
    if params.get('portfolio_id'):
        tickers, current_weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
    
    if not tickers or len(tickers) < 2:
        return {"status": "error", "error": "Need at least 2 tickers for optimization"}
    
    try:
        # Fetch market data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        period = params.get('period', '1y')
        combined_data = {}
        valid_tickers = []
        
        for ticker in tickers:
            try:
                result = await market_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })
                if result and hasattr(result, 'content'):
                    from core.utils.mcp_result_parser import safe_parse_json
                    data = safe_parse_json(result)
                    if data and "dates" in data:
                        combined_data[ticker] = data
                        valid_tickers.append(ticker)
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
        
        await market_server.cleanup()
        
        if len(valid_tickers) < 2:
            return {"status": "error", "error": f"Insufficient data. Only got: {valid_tickers}"}
        
        # Build prices and returns
        prices = adapt_mcp_to_prices(combined_data, valid_tickers)
        returns = prepare_returns(prices)
        
        # Configure optimizer
        min_weight = params.get('min_weight', 0.0)
        max_weight = params.get('max_weight', 0.40)
        method = params.get('method', 'max_sharpe')
        target_return = params.get('target_return')
        
        optimizer = PortfolioOptimizer(returns, min_weight=min_weight, max_weight=max_weight)
        
        # Run optimization
        if method == "min_variance":
            result = optimizer.optimize_portfolio(objective='min_variance')
        elif method == "max_sharpe":
            result = optimizer.optimize_portfolio(objective='sharpe')
        elif method == "risk_parity":
            result = optimizer.optimize_portfolio(objective='risk_parity')
        elif method == "target_return" and target_return is not None:
            result = optimizer.optimize_portfolio(objective='target_return', target_return=target_return)
        else:
            result = optimizer.optimize_portfolio(objective='sharpe')
        
        if not result or 'weights' not in result:
            return {"status": "error", "error": "Optimization failed to produce valid weights"}
        
        optimal_weights = result['weights']
        
        # Generate efficient frontier
        try:
            frontier_df = optimizer.efficient_frontier(n_portfolios=30)
            # Values already annualized by PortfolioOptimizer - just convert to percentage for display
            frontier_returns = (frontier_df['return'].values * 100).tolist()
            frontier_risks = (frontier_df['volatility'].values * 100).tolist()
        except Exception as e:
            logger.warning(f"Failed to generate efficient frontier: {e}")
            frontier_returns = []
            frontier_risks = []
        
        # Build charts
        charts = {}
        
        # Efficient frontier chart (values already annualized - just convert to percentage)
        frontier_chart = build_efficient_frontier_chart(
            frontier_returns, 
            frontier_risks,
            result.get('expected_return', 0) * 100,  # Convert to percentage points
            result.get('volatility', 0) * 100,       # Convert to percentage points
            method
        )
        if frontier_chart:
            charts["efficient_frontier"] = frontier_chart
        
        # Weights comparison chart
        weights_chart = build_weights_chart(valid_tickers, optimal_weights, current_weights)
        if weights_chart:
            charts["weights_comparison"] = weights_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(result, valid_tickers, optimal_weights, current_weights)
        
        # Build stats table
        stats_table = _build_stats_table(result, valid_tickers, optimal_weights, current_weights, method)
        
        # Extract metrics
        metrics = {
            "method": method,
            "expected_return": result.get('expected_return', 0) * 252,
            "volatility": result.get('volatility', 0) * np.sqrt(252),
            "sharpe_ratio": result.get('sharpe_ratio', 0),
            "optimal_weights": {t: float(w) for t, w in zip(valid_tickers, optimal_weights)},
        }
        
        return {
            "status": "success",
            "tool_id": "optimization",
            "tickers": valid_tickers,
            "weights": [float(w) for w in optimal_weights],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Optimization execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio(user_id: str, org_id: Optional[str], portfolio_id: str):
    """Resolve portfolio to tickers and weights."""
    from core.services.portfolio_service import PortfolioService
    
    service = PortfolioService()
    # Note: get_portfolio takes (user_id, portfolio_id_or_name) - org_id is not used
    portfolio = await service.get_portfolio(user_id, portfolio_id)
    
    if not portfolio or portfolio.get("status") == "error":
        return None, None
    
    # Unwrap API response: {"status": "success", "portfolio": {...}, "message": "..."}
    # Portfolio contains: tickers (list), weights (list), value, etc.
    actual_portfolio = portfolio.get("portfolio", {})
    
    # Get tickers and weights directly (not from positions!)
    tickers = actual_portfolio.get("tickers", [])
    weights = actual_portfolio.get("weights", [])
    
    if not tickers:
        return None, None
    
    # If weights missing, distribute equally
    if not weights or len(weights) != len(tickers):
        weights = [1.0 / len(tickers)] * len(tickers)
    
    # Normalize weights
    total = sum(weights)
    if total > 0:
        weights = [w / total for w in weights]
    
    return tickers, weights


def _build_metric_cards(result: Dict[str, Any], tickers: List[str], optimal_weights: List[float], current_weights: Optional[List[float]]) -> List[Dict[str, Any]]:
    """Build metric cards from optimization results."""
    cards = []
    
    # Expected return (already annualized by PortfolioOptimizer)
    exp_return = result.get('expected_return', 0)
    cards.append({
        "id": "expected_return",
        "label": "Expected Return",
        "value": f"{exp_return:.1%}",
        "sentiment": "positive" if exp_return > 0.08 else "neutral",
    })
    
    # Volatility (already annualized by PortfolioOptimizer)
    volatility = result.get('volatility', 0)
    cards.append({
        "id": "volatility",
        "label": "Portfolio Volatility",
        "value": f"{volatility:.1%}",
        "sentiment": "negative" if volatility > 0.25 else "neutral",
    })
    
    # Sharpe ratio
    sharpe = result.get('sharpe_ratio', 0)
    cards.append({
        "id": "sharpe",
        "label": "Sharpe Ratio",
        "value": f"{sharpe:.2f}",
        "sentiment": "positive" if sharpe > 1.0 else ("neutral" if sharpe > 0.5 else "negative"),
    })
    
    # Max allocation
    max_weight = max(optimal_weights)
    # Convert to list if numpy array to use .index()
    weights_list = list(optimal_weights) if hasattr(optimal_weights, '__array__') else optimal_weights
    max_ticker = tickers[weights_list.index(max_weight)]
    cards.append({
        "id": "max_allocation",
        "label": "Largest Position",
        "value": f"{max_ticker}: {max_weight:.1%}",
        "sentiment": "neutral",
    })
    
    # Concentration (HHI)
    hhi = sum(w**2 for w in optimal_weights)
    cards.append({
        "id": "concentration",
        "label": "Concentration (HHI)",
        "value": f"{hhi:.3f}",
        "sentiment": "negative" if hhi > 0.25 else "neutral",
    })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    tickers: List[str],
    optimal_weights: List[float],
    current_weights: Optional[List[float]],
    method: str
) -> List[Dict[str, str]]:
    """Build stats table from optimization results."""
    rows = []
    
    # Optimization summary
    rows.append({"category": "Optimization", "metric": "Method", "value": method.replace("_", " ").title()})
    rows.append({"category": "Optimization", "metric": "Assets", "value": str(len(tickers))})
    
    # Portfolio metrics (already annualized by PortfolioOptimizer)
    exp_return = result.get('expected_return', 0)
    volatility = result.get('volatility', 0)
    sharpe = result.get('sharpe_ratio', 0)
    
    rows.append({"category": "Performance", "metric": "Expected Return (Ann.)", "value": f"{exp_return:.2%}"})
    rows.append({"category": "Performance", "metric": "Volatility (Ann.)", "value": f"{volatility:.2%}"})
    rows.append({"category": "Performance", "metric": "Sharpe Ratio", "value": f"{sharpe:.3f}"})
    
    # Risk metrics
    if volatility > 0:
        var_95 = 1.645 * volatility
        rows.append({"category": "Risk", "metric": "95% VaR (Ann.)", "value": f"{var_95:.2%}"})
    
    # Concentration metrics
    hhi = sum(w**2 for w in optimal_weights)
    effective_n = 1 / hhi if hhi > 0 else len(tickers)
    rows.append({"category": "Diversification", "metric": "HHI (Concentration)", "value": f"{hhi:.4f}"})
    rows.append({"category": "Diversification", "metric": "Effective # Assets", "value": f"{effective_n:.1f}"})
    
    # Optimal weights breakdown
    rows.append({"category": "Weights", "metric": "─" * 20, "value": "─" * 15})
    
    # Sort by weight descending
    sorted_pairs = sorted(zip(tickers, optimal_weights), key=lambda x: x[1], reverse=True)
    
    for ticker, weight in sorted_pairs:
        change_str = ""
        if current_weights:
            idx = tickers.index(ticker)
            if idx < len(current_weights):
                delta = weight - current_weights[idx]
                change_str = f" ({delta:+.1%})" if abs(delta) > 0.001 else ""
        
        rows.append({
            "category": "Optimal Weight",
            "metric": ticker,
            "value": f"{weight:.1%}{change_str}",
        })
    
    return rows

