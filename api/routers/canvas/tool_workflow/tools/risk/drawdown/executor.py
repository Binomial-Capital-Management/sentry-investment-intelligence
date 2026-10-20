"""
Drawdown Analysis Canvas Executor

Analyzes maximum drawdown, recovery periods, and underwater time.
"""
from typing import Dict, List, Any, Optional
import logging
import numpy as np
import pandas as pd

from .charts import build_drawdown_chart, build_underwater_chart, build_recovery_chart

logger = logging.getLogger(__name__)


async def execute_drawdown(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute drawdown analysis for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.utils.mcp_result_parser import safe_parse_json
    
    tickers = params.get('tickers')
    weights = params.get('weights')
    
    # Resolve portfolio if provided
    if params.get('portfolio_id'):
        tickers, weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
    
    if not tickers:
        return {"status": "error", "error": "Provide portfolio_id or tickers"}
    
    n_assets = len(tickers)
    
    # Default to equal weights
    if not weights:
        weights = [1.0 / n_assets] * n_assets
    weights = np.array(weights)
    weights = weights / weights.sum()
    
    try:
        # Fetch market data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        period = params.get('period', '2y')
        price_data = {}
        valid_tickers = []
        
        for ticker in tickers:
            try:
                result = await market_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })
                if result and hasattr(result, 'content'):
                    data = safe_parse_json(result)
                    if data and "dates" in data:
                        dates = data.get("dates", [])
                        prices = data.get("prices", []) or data.get("closes", [])
                        if dates and prices:
                            price_data[ticker] = pd.Series(prices, index=pd.to_datetime(dates))
                            valid_tickers.append(ticker)
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
        
        await market_server.cleanup()
        
        if not valid_tickers:
            return {"status": "error", "error": "No price data available"}
        
        # Adjust weights
        if len(valid_tickers) != n_assets:
            ticker_to_weight = dict(zip(tickers, weights))
            weights = np.array([ticker_to_weight.get(t, 0) for t in valid_tickers])
            weights = weights / weights.sum()
        
        # Build portfolio values
        prices_df = pd.DataFrame(price_data).sort_index().dropna()
        
        # Normalize prices to start at 1
        normalized = prices_df / prices_df.iloc[0]
        
        # Calculate portfolio value
        portfolio_values = (normalized * weights).sum(axis=1)
        portfolio_values = portfolio_values / portfolio_values.iloc[0]  # Re-normalize
        
        # Calculate drawdowns
        running_max = portfolio_values.expanding().max()
        drawdown = (portfolio_values - running_max) / running_max
        
        # Find drawdown periods
        drawdown_periods = _identify_drawdown_periods(portfolio_values, drawdown)
        
        # Calculate metrics
        max_drawdown = drawdown.min()
        max_dd_date = drawdown.idxmin()
        current_drawdown = drawdown.iloc[-1]
        
        # Find the peak before max drawdown
        peak_before_max = running_max.loc[:max_dd_date].idxmax()
        
        # Average drawdown
        avg_drawdown = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0
        
        # Underwater time
        underwater_pct = (drawdown < 0).sum() / len(drawdown) * 100
        
        # Recovery analysis
        recovery_stats = _calculate_recovery_stats(drawdown_periods)
        
        # Individual asset drawdowns
        asset_drawdowns = {}
        for ticker in valid_tickers:
            asset_prices = prices_df[ticker]
            asset_max = asset_prices.expanding().max()
            asset_dd = (asset_prices - asset_max) / asset_max
            asset_drawdowns[ticker] = {
                'max_drawdown': float(asset_dd.min()),
                'current_drawdown': float(asset_dd.iloc[-1]),
            }
        
        # Build charts
        charts = {}
        
        # Drawdown chart
        dd_chart = build_drawdown_chart(
            portfolio_values.index.tolist(),
            drawdown.values.tolist(),
            valid_tickers[0] if len(valid_tickers) == 1 else "Portfolio"
        )
        if dd_chart:
            charts["drawdown"] = dd_chart
        
        # Underwater chart
        uw_chart = build_underwater_chart(
            portfolio_values.index.tolist(),
            portfolio_values.values.tolist(),
            running_max.values.tolist()
        )
        if uw_chart:
            charts["underwater"] = uw_chart
        
        # Recovery periods chart
        if drawdown_periods:
            recovery_chart = build_recovery_chart(drawdown_periods)
            if recovery_chart:
                charts["recovery_periods"] = recovery_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            max_drawdown, current_drawdown, avg_drawdown,
            underwater_pct, recovery_stats
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            max_drawdown, max_dd_date, peak_before_max, current_drawdown,
            avg_drawdown, underwater_pct, recovery_stats, drawdown_periods,
            asset_drawdowns, valid_tickers
        )
        
        # Build metrics dict - ensure all values are JSON serializable
        metrics = {
            "max_drawdown": float(max_drawdown),
            "max_drawdown_date": str(max_dd_date),
            "current_drawdown": float(current_drawdown),
            "avg_drawdown": float(avg_drawdown) if avg_drawdown else 0.0,
            "underwater_pct": float(underwater_pct),
            "recovery_stats": recovery_stats,
            "asset_drawdowns": asset_drawdowns,
        }
        
        return {
            "status": "success",
            "tool_id": "drawdown",
            "tickers": valid_tickers,
            "weights": weights.tolist(),
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Drawdown analysis failed: {e}", exc_info=True)
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


def _identify_drawdown_periods(portfolio_values: pd.Series, drawdown: pd.Series, threshold: float = -0.05) -> List[Dict[str, Any]]:
    """Identify significant drawdown periods."""
    periods = []
    in_drawdown = False
    period_start = None
    period_peak_value = None
    
    for date, dd in drawdown.items():
        if dd < threshold and not in_drawdown:
            # Start of drawdown
            in_drawdown = True
            period_start = date
            period_peak_value = portfolio_values.loc[:date].max()
        elif dd >= 0 and in_drawdown:
            # Recovery complete
            period_end = date
            period_trough = drawdown.loc[period_start:period_end].min()
            trough_date = drawdown.loc[period_start:period_end].idxmin()
            
            periods.append({
                'start': period_start,
                'trough_date': trough_date,
                'end': period_end,
                'max_drawdown': float(period_trough),
                'duration_days': (period_end - period_start).days,
                'drawdown_days': (trough_date - period_start).days,
                'recovery_days': (period_end - trough_date).days,
            })
            in_drawdown = False
    
    # Handle ongoing drawdown
    if in_drawdown:
        period_trough = drawdown.loc[period_start:].min()
        trough_date = drawdown.loc[period_start:].idxmin()
        periods.append({
            'start': period_start,
            'trough_date': trough_date,
            'end': None,  # Ongoing
            'max_drawdown': float(period_trough),
            'duration_days': (drawdown.index[-1] - period_start).days,
            'drawdown_days': (trough_date - period_start).days,
            'recovery_days': None,  # Not recovered
        })
    
    return sorted(periods, key=lambda x: x['max_drawdown'])


def _calculate_recovery_stats(periods: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate recovery statistics from drawdown periods."""
    if not periods:
        return {"avg_recovery_days": 0, "max_recovery_days": 0, "periods_analyzed": 0}
    
    recovered_periods = [p for p in periods if p['recovery_days'] is not None]
    
    if not recovered_periods:
        return {"avg_recovery_days": None, "max_recovery_days": None, "periods_analyzed": len(periods)}
    
    recovery_days = [p['recovery_days'] for p in recovered_periods]
    
    return {
        "avg_recovery_days": float(np.mean(recovery_days)),
        "max_recovery_days": max(recovery_days),
        "min_recovery_days": min(recovery_days),
        "periods_analyzed": len(periods),
        "periods_recovered": len(recovered_periods),
    }


def _build_metric_cards(
    max_drawdown: float,
    current_drawdown: float,
    avg_drawdown: float,
    underwater_pct: float,
    recovery_stats: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Build metric cards from drawdown analysis."""
    cards = []
    
    # Max drawdown
    cards.append({
        "id": "max_drawdown",
        "label": "Maximum Drawdown",
        "value": f"{max_drawdown:.1%}",
        "sentiment": "negative" if max_drawdown < -0.20 else "neutral",
    })
    
    # Current drawdown
    if current_drawdown < 0:
        cards.append({
            "id": "current_drawdown",
            "label": "Current Drawdown",
            "value": f"{current_drawdown:.1%}",
            "sentiment": "negative",
        })
    else:
        cards.append({
            "id": "current_drawdown",
            "label": "Current Drawdown",
            "value": "At All-Time High",
            "sentiment": "positive",
        })
    
    # Underwater time
    cards.append({
        "id": "underwater",
        "label": "Time Underwater",
        "value": f"{underwater_pct:.0f}%",
        "sentiment": "negative" if underwater_pct > 50 else "neutral",
    })
    
    # Average recovery
    avg_recovery = recovery_stats.get('avg_recovery_days')
    if avg_recovery:
        cards.append({
            "id": "avg_recovery",
            "label": "Avg Recovery Time",
            "value": f"{avg_recovery:.0f} days",
            "sentiment": "neutral",
        })
    
    return cards


def _build_stats_table(
    max_drawdown: float,
    max_dd_date,
    peak_before_max,
    current_drawdown: float,
    avg_drawdown: float,
    underwater_pct: float,
    recovery_stats: Dict[str, Any],
    drawdown_periods: List[Dict[str, Any]],
    asset_drawdowns: Dict[str, Dict[str, float]],
    tickers: List[str]
) -> List[Dict[str, str]]:
    """Build stats table from drawdown analysis."""
    rows = []
    
    # Summary
    rows.append({"category": "Summary", "metric": "Maximum Drawdown", "value": f"{max_drawdown:.2%}"})
    rows.append({"category": "Summary", "metric": "Max DD Date", "value": str(max_dd_date.date())})
    rows.append({"category": "Summary", "metric": "Peak Before Max DD", "value": str(peak_before_max.date())})
    rows.append({"category": "Summary", "metric": "Current Drawdown", "value": f"{current_drawdown:.2%}" if current_drawdown < 0 else "At ATH"})
    rows.append({"category": "Summary", "metric": "Average Drawdown", "value": f"{avg_drawdown:.2%}"})
    rows.append({"category": "Summary", "metric": "Time Underwater", "value": f"{underwater_pct:.1f}%"})
    
    # Recovery stats
    if recovery_stats.get('avg_recovery_days'):
        rows.append({"category": "Recovery", "metric": "Avg Recovery Time", "value": f"{recovery_stats['avg_recovery_days']:.0f} days"})
        rows.append({"category": "Recovery", "metric": "Max Recovery Time", "value": f"{recovery_stats.get('max_recovery_days', 0):.0f} days"})
        rows.append({"category": "Recovery", "metric": "Drawdown Events (>5%)", "value": str(recovery_stats.get('periods_analyzed', 0))})
    
    # Worst drawdown periods
    if drawdown_periods:
        rows.append({"category": "Drawdowns", "metric": "─" * 20, "value": "─" * 15})
        
        for i, period in enumerate(drawdown_periods[:5], 1):
            start_str = period['start'].strftime('%Y-%m-%d')
            end_str = period['end'].strftime('%Y-%m-%d') if period['end'] else "Ongoing"
            
            rows.append({
                "category": f"#{i} Drawdown",
                "metric": f"{start_str} → {end_str}",
                "value": f"{period['max_drawdown']:.1%}",
                "pct": f"{period['duration_days']}d total" + (f", {period['recovery_days']}d recovery" if period['recovery_days'] else ", not recovered"),
            })
    
    # Individual asset drawdowns
    if len(tickers) > 1:
        rows.append({"category": "Assets", "metric": "─" * 20, "value": "─" * 15})
        
        for ticker in tickers:
            dd = asset_drawdowns.get(ticker, {})
            max_dd = dd.get('max_drawdown', 0)
            curr_dd = dd.get('current_drawdown', 0)
            
            rows.append({
                "category": "Asset Max DD",
                "metric": ticker,
                "value": f"{max_dd:.1%}",
                "pct": f"Current: {curr_dd:.1%}" if curr_dd < 0 else "At ATH",
            })
    
    return rows

