"""Volatility Surface Executor for Canvas.

Wraps the existing model_volatility_surface tool for Canvas execution.
Graph building is done generically by the Canvas router - NOT here.
"""

from typing import Dict, Any, Optional, List
import logging

from .charts import build_3d_surface_chart, build_iv_smile_chart, build_term_structure_chart

logger = logging.getLogger(__name__)


async def execute_vol_surface(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute volatility surface modeling.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including underlying, grid_resolution, compute_analytics, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.quant_tools.volatility_surface_tool import model_volatility_surface_internal
    
    try:
        # Get the underlying ticker - this tool works on a single ticker
        underlying = params.get('underlying') or params.get('ticker')
        
        # Also support tickers array (take first)
        if not underlying and params.get('tickers'):
            tickers = params.get('tickers', [])
            if tickers:
                underlying = tickers[0] if isinstance(tickers, list) else tickers
        
        if not underlying:
            return {"status": "error", "error": "Please provide an underlying ticker (e.g., AAPL, SPY)"}
        
        underlying = underlying.upper().strip()
        logger.info(f"Canvas vol surface: {underlying} for user {user_id}")
        
        # Call the internal function (not the @function_tool decorated version)
        result = await model_volatility_surface_internal(
            underlying=underlying,
            underlying_price=params.get('underlying_price'),
            grid_resolution=params.get('grid_resolution', 30),
            target_dte_for_smile=params.get('target_dte_for_smile'),
            target_strike_for_term=params.get('target_strike_for_term'),
            compute_analytics=params.get('compute_analytics', False),
            include_realized_vol=params.get('include_realized_vol', True),
            peer_tickers=params.get('peer_tickers'),
            use_delta_buckets=params.get('use_delta_buckets', True),
        )
        
        if result.get('status') == 'error':
            return result
        
        # Extract nested results
        inner = result.get('results', result)
        surface_stats = inner.get('surface_stats', {})
        analytics = inner.get('analytics', {})
        realized_vol = inner.get('realized_vol', {})
        vol_risk_premium = inner.get('vol_risk_premium', {})
        surface_grid = inner.get('surface_grid', {})
        iv_points = inner.get('iv_points', {})
        spot_price = inner.get('spot_price') or result.get('spot_price', 100)
        
        # Build Canvas-specific charts from raw data (like monte_carlo does)
        surface_chart = build_3d_surface_chart(underlying, spot_price, surface_grid)
        smile_chart = build_iv_smile_chart(underlying, spot_price, iv_points, params.get('target_dte_for_smile'))
        term_chart = build_term_structure_chart(underlying, spot_price, iv_points)
        
        # Build metric cards for Canvas display
        metric_cards = _build_metric_cards(surface_stats, analytics, realized_vol, vol_risk_premium)
        
        # Build stats table
        stats_table = _build_stats_table(surface_stats, analytics, realized_vol)
        
        # Build metrics dict
        metrics = _extract_metrics(surface_stats, analytics, realized_vol, vol_risk_premium)
        
        return {
            "status": "success",
            "tool_id": "vol_surface",
            "tickers": [underlying],
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": {
                "3d_surface": surface_chart,
                "iv_smile": smile_chart,
                "term_structure": term_chart,
            },
            "surface_stats": surface_stats,
            "analytics": analytics,
            "realized_vol": realized_vol,
            "vol_risk_premium": vol_risk_premium,
        }
        
    except Exception as e:
        logger.error(f"Vol surface failed: {e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "..."
        return {"status": "error", "error": error_msg}


def _extract_metrics(
    surface_stats: Dict[str, Any],
    analytics: Dict[str, Any],
    realized_vol: Dict[str, Any],
    vol_risk_premium: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract metrics into standardized format."""
    atm_iv = analytics.get('atm_iv') or surface_stats.get('mean_iv')
    rv_20d = realized_vol.get('rv_20d')
    vrp = vol_risk_premium.get('iv_minus_rv_20d') if vol_risk_premium else None
    
    return {
        "atm_iv": atm_iv,
        "mean_iv": surface_stats.get('mean_iv'),
        "min_iv": surface_stats.get('min_iv'),
        "max_iv": surface_stats.get('max_iv'),
        "iv_range": surface_stats.get('iv_range'),
        "data_points": surface_stats.get('data_points'),
        "put_skew_25d": analytics.get('put_skew_25d'),
        "call_skew_25d": analytics.get('call_skew_25d'),
        "term_slope": analytics.get('term_slope'),
        "rv_20d": rv_20d,
        "rv_60d": realized_vol.get('rv_60d'),
        "vol_risk_premium": vrp,
    }


def _build_metric_cards(
    surface_stats: Dict[str, Any],
    analytics: Dict[str, Any],
    realized_vol: Dict[str, Any],
    vol_risk_premium: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build displayable metric cards with styling metadata."""
    cards = []
    
    # ATM IV
    atm_iv = analytics.get('atm_iv') or surface_stats.get('mean_iv')
    if atm_iv:
        cards.append({
            "id": "atm_iv",
            "label": "ATM IV",
            "value": f"{atm_iv:.1f}%",
            "sentiment": "neutral",
        })
    
    # IV Range
    if surface_stats.get('min_iv') and surface_stats.get('max_iv'):
        cards.append({
            "id": "iv_range",
            "label": "IV Range",
            "value": f"{surface_stats['min_iv']:.1f}% - {surface_stats['max_iv']:.1f}%",
            "sentiment": "neutral",
        })
    
    # 25D Put Skew
    put_skew = analytics.get('put_skew_25d')
    if put_skew:
        skew_sentiment = "negative" if put_skew > 5 else "positive" if put_skew < -2 else "neutral"
        cards.append({
            "id": "put_skew",
            "label": "25Δ Put Skew",
            "value": f"{put_skew:+.1f}%",
            "sentiment": skew_sentiment,
        })
    
    # Realized Vol
    rv_20d = realized_vol.get('rv_20d')
    if rv_20d:
        cards.append({
            "id": "rv_20d",
            "label": "20D Realized Vol",
            "value": f"{rv_20d:.1f}%",
            "sentiment": "neutral",
        })
    
    # Vol Risk Premium
    vrp = vol_risk_premium.get('iv_minus_rv_20d') if vol_risk_premium else None
    if vrp is not None:
        vrp_sentiment = "positive" if vrp > 3 else "negative" if vrp < -3 else "neutral"
        cards.append({
            "id": "vrp",
            "label": "Vol Risk Premium",
            "value": f"{vrp:+.1f}%",
            "sentiment": vrp_sentiment,
        })
    
    return cards


def _build_stats_table(
    surface_stats: Dict[str, Any],
    analytics: Dict[str, Any],
    realized_vol: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table for display."""
    rows = []
    
    if surface_stats:
        rows.append({"category": "Surface", "metric": "Mean IV", "value": f"{surface_stats.get('mean_iv', 0):.2f}%"})
        rows.append({"category": "Surface", "metric": "Median IV", "value": f"{surface_stats.get('median_iv', 0):.2f}%"})
        rows.append({"category": "Surface", "metric": "IV Range", "value": f"{surface_stats.get('iv_range', 0):.2f}%"})
        rows.append({"category": "Surface", "metric": "Data Points", "value": str(surface_stats.get('data_points', 0))})
        
        strike_range = surface_stats.get('strike_range', [0, 0])
        if strike_range and len(strike_range) >= 2:
            rows.append({"category": "Surface", "metric": "Strike Range", "value": f"${strike_range[0]:.0f} - ${strike_range[1]:.0f}"})
        
        dte_range = surface_stats.get('dte_range', [0, 0])
        if dte_range and len(dte_range) >= 2:
            rows.append({"category": "Surface", "metric": "DTE Range", "value": f"{dte_range[0]} - {dte_range[1]} days"})
    
    if analytics:
        if analytics.get('atm_iv'):
            rows.append({"category": "Analytics", "metric": "ATM IV", "value": f"{analytics['atm_iv']:.2f}%"})
        if analytics.get('front_iv'):
            rows.append({"category": "Analytics", "metric": "Front Month IV", "value": f"{analytics['front_iv']:.2f}%"})
        if analytics.get('back_iv'):
            rows.append({"category": "Analytics", "metric": "Back Month IV", "value": f"{analytics['back_iv']:.2f}%"})
        if analytics.get('put_skew_25d'):
            rows.append({"category": "Analytics", "metric": "25Δ Put Skew", "value": f"{analytics['put_skew_25d']:+.2f}%"})
        if analytics.get('term_slope'):
            rows.append({"category": "Analytics", "metric": "Term Slope", "value": f"{analytics['term_slope']:+.3f}"})
    
    if realized_vol:
        if realized_vol.get('rv_20d'):
            rows.append({"category": "Realized", "metric": "20D RV", "value": f"{realized_vol['rv_20d']:.2f}%"})
        if realized_vol.get('rv_60d'):
            rows.append({"category": "Realized", "metric": "60D RV", "value": f"{realized_vol['rv_60d']:.2f}%"})
    
    return rows
