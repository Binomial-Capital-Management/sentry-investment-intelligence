"""
VaR Canvas Executor
"""
from typing import Dict, List, Any, Optional
import logging

from core.agents.risk_tools.var_tool import calculate_var_internal
from .charts import build_returns_histogram, build_var_comparison_chart

logger = logging.getLogger(__name__)


async def execute_var(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute VaR analysis for Canvas."""
    try:
        # Resolve tickers
        portfolio_id = params.get("portfolio_id")
        tickers = params.get("tickers", [])
        weights = params.get("weights")
        
        if portfolio_id:
            tickers, weights = await _resolve_portfolio_tickers(user_id, org_id, portfolio_id)
            if not tickers:
                return {"status": "error", "error": f"Portfolio {portfolio_id} not found or empty"}
        
        if not tickers:
            return {"status": "error", "error": "No tickers provided"}
        
        # Call internal VaR function
        result = await calculate_var_internal(
            tickers=tickers,
            weights=weights,
            method=params.get("method", "all"),
            confidence_levels=params.get("confidence_levels", [0.95, 0.99]),
            portfolio_value=params.get("portfolio_value", 1000000),
            time_horizon=params.get("time_horizon", 1),
            period=params.get("period", "1y"),
        )
        
        if result.get("error"):
            return {"status": "error", "error": result.get("error"), "details": result.get("details")}
        
        # Use valid tickers from result
        valid_tickers = result.get("tickers", tickers)
        skipped_tickers = result.get("skipped_tickers", [])
        
        if skipped_tickers:
            logger.info(f"Skipped {len(skipped_tickers)} tickers: {skipped_tickers}")
        
        # Build charts
        var_summary = result.get("var_summary", {})
        portfolio_value = result.get("portfolio_value", 1000000)
        portfolio_returns = result.get("portfolio_returns", [])
        
        histogram_chart = build_returns_histogram(
            portfolio_returns, var_summary, valid_tickers, result.get("method", "all")
        )
        comparison_chart = build_var_comparison_chart(var_summary, portfolio_value)
        
        charts = {}
        if histogram_chart:
            charts["returns_histogram"] = histogram_chart
        if comparison_chart:
            charts["var_comparison"] = comparison_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(result)
        
        if skipped_tickers:
            metric_cards.append({
                "id": "skipped",
                "label": "Skipped Tickers",
                "value": ", ".join(skipped_tickers),
                "sentiment": "negative",
            })
        
        # Build stats table
        stats_table = _build_stats_table(result)
        
        # Build metrics dict
        metrics = _extract_metrics(result)
        metrics["skipped_tickers"] = skipped_tickers
        
        return {
            "status": "success",
            "tool_id": "var",
            "tickers": valid_tickers,
            "weights": result.get("weights", []),
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"VaR execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: str
) -> tuple:
    """Fetch tickers and weights from portfolio."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return [], None
        
        actual_portfolio = portfolio.get("portfolio", {})
        tickers = actual_portfolio.get('tickers', [])
        weights = actual_portfolio.get('weights', [])
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers) if tickers else None
        return tickers, weights
    except Exception as e:
        logger.warning(f"Could not fetch portfolio: {e}")
    return [], None


def _build_metric_cards(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build metric cards from VaR results."""
    cards = []
    var_summary = result.get("var_summary", {})
    
    # Find primary VaR (Historical 95%)
    primary_var = None
    for name, data in var_summary.items():
        if "Historical" in name and "95" in name:
            primary_var = data
            break
    
    if not primary_var and var_summary:
        primary_var = list(var_summary.values())[0]
    
    if primary_var:
        var_pct = primary_var.get("percentage", 0)
        var_dollar = primary_var.get("dollar", 0)
        
        cards.append({
            "id": "var_95",
            "label": "VaR (95%)",
            "value": f"{var_pct:.2%}",
            "sentiment": "negative" if var_pct > 0.03 else "neutral",
        })
        
        cards.append({
            "id": "var_dollar",
            "label": "VaR ($)",
            "value": f"${var_dollar:,.0f}",
            "sentiment": "neutral",
        })
    
    # Add 99% VaR
    for name, data in var_summary.items():
        if "99" in name:
            cards.append({
                "id": "var_99",
                "label": "VaR (99%)",
                "value": f"{data.get('percentage', 0):.2%}",
                "sentiment": "negative" if data.get('percentage', 0) > 0.05 else "neutral",
            })
            break
    
    # Portfolio stats
    cards.append({
        "id": "portfolio_value",
        "label": "Portfolio Value",
        "value": f"${result.get('portfolio_value', 0):,.0f}",
        "sentiment": "neutral",
    })
    
    cards.append({
        "id": "daily_vol",
        "label": "Daily Volatility",
        "value": f"{result.get('returns_std', 0):.2%}",
        "sentiment": "neutral",
    })
    
    return cards


def _build_stats_table(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build stats table from VaR results."""
    rows = []
    var_summary = result.get("var_summary", {})
    
    # VaR results by method
    for var_name, var_data in var_summary.items():
        rows.append({
            "category": "VaR Results",
            "metric": var_name,
            "value": f"{var_data.get('percentage', 0):.2%}",
            "pct": f"${var_data.get('dollar', 0):,.0f}",
        })
    
    # Portfolio overview
    portfolio_value = result.get("portfolio_value", 0)
    rows.append({"category": "Portfolio", "metric": "Portfolio Value", "value": f"${portfolio_value:,.0f}"})
    
    # Return statistics
    returns_mean = result.get("returns_mean", 0)
    returns_std = result.get("returns_std", 0)
    rows.append({"category": "Returns", "metric": "Daily Mean Return", "value": f"{returns_mean:.4%}"})
    rows.append({"category": "Returns", "metric": "Daily Volatility", "value": f"{returns_std:.4%}"})
    
    # Annualized metrics
    ann_return = returns_mean * 252
    ann_vol = returns_std * (252 ** 0.5)
    rows.append({"category": "Returns", "metric": "Annualized Return", "value": f"{ann_return:.2%}"})
    rows.append({"category": "Returns", "metric": "Annualized Volatility", "value": f"{ann_vol:.2%}"})
    
    # Risk-adjusted metrics
    if ann_vol > 0:
        sharpe = ann_return / ann_vol
        rows.append({"category": "Risk-Adjusted", "metric": "Sharpe Ratio (Est.)", "value": f"{sharpe:.2f}"})
    
    # Skewness & Kurtosis if available
    skewness = result.get("skewness")
    kurtosis = result.get("kurtosis")
    if skewness is not None:
        rows.append({"category": "Distribution", "metric": "Skewness", "value": f"{skewness:.3f}"})
    if kurtosis is not None:
        rows.append({"category": "Distribution", "metric": "Excess Kurtosis", "value": f"{kurtosis:.3f}"})
    
    # Analysis parameters
    confidence_levels = result.get("confidence_levels", [])
    if confidence_levels:
        rows.append({"category": "Parameters", "metric": "Confidence Levels", "value": ", ".join(f"{c:.0%}" for c in confidence_levels)})
    
    time_horizon = result.get("time_horizon", 1)
    rows.append({"category": "Parameters", "metric": "Time Horizon", "value": f"{time_horizon} day(s)"})
    
    method = result.get("method", "all")
    rows.append({"category": "Parameters", "metric": "Method", "value": method.replace("_", " ").title()})
    
    # Worst-case scenario
    if var_summary:
        worst_var = max(var_summary.values(), key=lambda x: abs(x.get('percentage', 0)))
        worst_method = max(var_summary.keys(), key=lambda k: abs(var_summary[k].get('percentage', 0)))
        rows.append({
            "category": "Risk Scenario",
            "metric": f"Worst Case ({worst_method})",
            "value": f"Max 1-day loss: ${worst_var.get('dollar', 0):,.0f}",
        })
    
    return rows


def _extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metrics for persistence."""
    return {
        "portfolio_value": result.get("portfolio_value"),
        "confidence_levels": result.get("confidence_levels"),
        "method": result.get("method"),
        "var_summary": result.get("var_summary"),
        "returns_mean": result.get("returns_mean"),
        "returns_std": result.get("returns_std"),
    }

