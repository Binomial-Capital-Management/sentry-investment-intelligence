"""
Hedge Portfolio Canvas Executor

Create factor-neutral hedging positions - wraps existing hedge_tool.py
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_hedge(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Hedge Portfolio analysis for Canvas.
    
    Wraps core/agents/risk_tools/hedge_tool.py
    Creates hedge positions to neutralize factor exposures.
    """
    from core.agents.risk_tools.hedge_tool import create_hedge_portfolio_internal
    
    # Get tickers from params or resolve from portfolio
    tickers = params.get('tickers', [])
    weights = params.get('weights')
    
    # Resolve portfolio if provided
    if params.get('portfolio_id') and not tickers:
        tickers, weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
    
    if not tickers or len(tickers) < 1:
        return {"status": "error", "error": "At least 1 ticker is required"}
    
    try:
        # Call the internal hedge function
        result = await create_hedge_portfolio_internal(
            tickers=tickers,
            weights=weights,
            period=params.get('period', '1y'),
            hedge_strategy=params.get('hedge_strategy', 'market_neutral'),
            target_betas=params.get('target_betas'),
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error", "Hedge calculation failed")}
        
        # Extract data
        hedge_positions = result.get("hedge_positions", [])
        exposures_before = result.get("exposures_before", {})
        exposures_after = result.get("exposures_after", {})
        risk_reduction = result.get("expected_risk_reduction", {})
        
        # Build charts
        charts = {}
        if "charts" in result:
            for chart_id, chart_data in result["charts"].items():
                charts[chart_id] = chart_data
        
        # Build hedge positions chart
        if hedge_positions:
            charts["hedge_positions"] = _build_hedge_positions_chart(hedge_positions)
        
        # Build exposure comparison chart
        if exposures_before and exposures_after:
            charts["exposure_comparison"] = _build_exposure_chart(exposures_before, exposures_after)
        
        # Build metric cards
        total_hedge_notional = sum(abs(pos.get("notional_weight", 0)) for pos in hedge_positions)
        vol_reduction = risk_reduction.get("volatility_reduction_pct", 0)
        
        metric_cards = [
            {
                "id": "hedge_strategy",
                "label": "Strategy",
                "value": params.get('hedge_strategy', 'market_neutral').replace("_", " ").title(),
                "sentiment": "neutral",
            },
            {
                "id": "hedge_positions",
                "label": "Hedge Positions",
                "value": str(len(hedge_positions)),
                "sentiment": "neutral",
            },
            {
                "id": "hedge_notional",
                "label": "Total Hedge %",
                "value": f"{total_hedge_notional*100:.1f}%",
                "sentiment": "neutral",
            },
            {
                "id": "vol_reduction",
                "label": "Vol Reduction",
                "value": f"{vol_reduction:.1f}%",
                "sentiment": "positive" if vol_reduction > 0 else "neutral",
            },
            {
                "id": "market_beta_after",
                "label": "Market β After",
                "value": f"{exposures_after.get('Market', 0):.2f}",
                "sentiment": "positive" if abs(exposures_after.get('Market', 1)) < 0.2 else "neutral",
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Portfolio", "metric": "Tickers", "value": ", ".join(tickers[:5]) + ("..." if len(tickers) > 5 else "")},
            {"category": "Portfolio", "metric": "Strategy", "value": params.get('hedge_strategy', 'market_neutral')},
        ]
        
        # Factor exposures before
        stats_table.append({"category": "Before Hedge", "metric": "─" * 20, "value": "─" * 15})
        for factor, exposure in exposures_before.items():
            stats_table.append({
                "category": "Before",
                "metric": factor,
                "value": f"{exposure:.3f}"
            })
        
        # Factor exposures after
        stats_table.append({"category": "After Hedge", "metric": "─" * 20, "value": "─" * 15})
        for factor, exposure in exposures_after.items():
            stats_table.append({
                "category": "After",
                "metric": factor,
                "value": f"{exposure:.3f}"
            })
        
        # Hedge positions
        stats_table.append({"category": "Positions", "metric": "─" * 20, "value": "─" * 15})
        for pos in hedge_positions:
            ticker = pos.get("ticker", "Unknown")
            weight = pos.get("notional_weight", 0)
            direction = "Long" if weight > 0 else "Short"
            stats_table.append({
                "category": "Hedge",
                "metric": f"{ticker} ({direction})",
                "value": f"{abs(weight)*100:.1f}%"
            })
        
        return {
            "status": "success",
            "tool_id": "hedge",
            "tickers": tickers + [p.get("ticker") for p in hedge_positions],
            "weights": weights if weights else [],
            "metrics": {
                "hedge_positions_count": len(hedge_positions),
                "total_hedge_notional": total_hedge_notional,
                "volatility_reduction": vol_reduction,
                "market_beta_after": exposures_after.get("Market", 0),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Hedge analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio(user_id: str, org_id: Optional[str], portfolio_id: str):
    """Resolve portfolio to tickers and weights."""
    from core.services.portfolio_service import PortfolioService
    
    service = PortfolioService()
    portfolio = await service.get_portfolio(user_id, portfolio_id)
    
    if not portfolio or portfolio.get("status") == "error":
        return None, None
    
    actual_portfolio = portfolio.get("portfolio", {})
    tickers = actual_portfolio.get("tickers", [])
    weights = actual_portfolio.get("weights", [])
    
    if not tickers:
        return None, None
    
    if not weights or len(weights) != len(tickers):
        weights = [1.0 / len(tickers)] * len(tickers)
    
    return tickers, weights


def _build_hedge_positions_chart(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build hedge positions bar chart."""
    try:
        tickers = [p.get("ticker", "") for p in positions]
        weights = [p.get("notional_weight", 0) * 100 for p in positions]
        colors = ['#10b981' if w > 0 else '#ef4444' for w in weights]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": tickers,
                    "y": weights,
                    "marker": {"color": colors},
                    "hovertemplate": "%{x}: %{y:.1f}%<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Hedge Positions", "font": {"size": 14}},
                    "xaxis": {"title": "ETF"},
                    "yaxis": {"title": "Weight (%)", "ticksuffix": "%"},
                    "height": 350,
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                    "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
                },
            },
            "type": "bar",
            "label": "Hedge Positions",
        }
    except Exception as e:
        logger.warning(f"Failed to build hedge positions chart: {e}")
        return None


def _build_exposure_chart(before: Dict[str, float], after: Dict[str, float]) -> Dict[str, Any]:
    """Build factor exposure comparison chart."""
    try:
        factors = list(before.keys())
        before_vals = [before.get(f, 0) for f in factors]
        after_vals = [after.get(f, 0) for f in factors]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "bar",
                        "name": "Before Hedge",
                        "x": factors,
                        "y": before_vals,
                        "marker": {"color": "#6b7280"},
                    },
                    {
                        "type": "bar",
                        "name": "After Hedge",
                        "x": factors,
                        "y": after_vals,
                        "marker": {"color": "#3b82f6"},
                    },
                ],
                "layout": {
                    "title": {"text": "Factor Exposures: Before vs After", "font": {"size": 14}},
                    "xaxis": {"title": "Factor"},
                    "yaxis": {"title": "Beta"},
                    "height": 400,
                    "barmode": "group",
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                    "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
                },
            },
            "type": "bar",
            "label": "Factor Exposure Comparison",
        }
    except Exception as e:
        logger.warning(f"Failed to build exposure chart: {e}")
        return None

