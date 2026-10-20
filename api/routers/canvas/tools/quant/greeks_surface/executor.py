"""Greeks Surface Executor for Canvas.

Wraps the Greeks surface modeling tool for Canvas execution.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


async def execute_greeks_surface(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Greeks surface modeling for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including ticker, greeks_to_model, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.quant_tools.greeks_surface_tool import model_greeks_surface_internal
    
    try:
        # Get ticker - single ticker for Greeks surface
        ticker = params.get('ticker', '')
        if isinstance(ticker, list):
            ticker = ticker[0] if ticker else ''
        ticker = ticker.upper().strip()
        
        if not ticker:
            return {"status": "error", "error": "Ticker is required"}
        
        # Extract parameters
        greeks_to_model = params.get('greeks_to_model', ['delta', 'gamma', 'theta', 'vega'])
        if isinstance(greeks_to_model, str):
            greeks_to_model = [g.strip() for g in greeks_to_model.split(',')]
        
        max_dte = int(params.get('max_dte', 90))
        grid_resolution = int(params.get('grid_resolution', 25))
        target_dte = params.get('target_dte_for_smile')
        if target_dte:
            target_dte = int(target_dte)
        
        logger.info(f"Canvas Greeks surface: {ticker}, greeks={greeks_to_model}, max_dte={max_dte}")
        
        # Call the internal function
        result = await model_greeks_surface_internal(
            underlying=ticker,
            greeks_to_model=greeks_to_model,
            grid_resolution=grid_resolution,
            target_dte_for_smile=target_dte,
            compute_analytics=True,
            max_dte=max_dte,
        )
        
        if result.get('error'):
            return {"status": "error", "error": result.get('error')}
        
        # Extract results
        results_data = result.get('results', {})
        analytics = results_data.get('analytics', {})
        surface_stats = results_data.get('surface_stats', {})
        spot_price = results_data.get('spot_price', 0)
        
        # Build Canvas charts from raw data (same pattern as correlation, cointegration, etc.)
        from .charts import build_greek_3d_surface, build_greeks_smile, build_greeks_term_structure
        
        charts = {}
        greeks_points = results_data.get('greeks_points', {})
        surface_grids = results_data.get('surface_grids', {})
        greeks_modeled = results_data.get('greeks_modeled', [])
        
        # Build 3D surface for each Greek
        for greek_name in greeks_modeled:
            if greek_name in surface_grids:
                surface_chart = build_greek_3d_surface(
                    ticker=ticker,
                    spot_price=spot_price,
                    greek_name=greek_name,
                    surface_grid=surface_grids[greek_name],
                )
                if surface_chart:
                    charts[f"{greek_name}_surface"] = surface_chart
        
        # Build Greeks smile chart
        target_dte = params.get('target_dte_for_smile', 30)
        smile_chart = build_greeks_smile(ticker, spot_price, greeks_points, target_dte)
        if smile_chart:
            charts["greeks_smile"] = smile_chart
        
        # Build term structure chart
        term_chart = build_greeks_term_structure(ticker, spot_price, greeks_points)
        if term_chart:
            charts["term_structure"] = term_chart
        
        logger.info(f"Built {len(charts)} charts for {ticker}: {list(charts.keys())}")
        
        # Build metric cards
        metric_cards = _build_metric_cards(ticker, spot_price, analytics, surface_stats)
        
        # Build stats table
        stats_table = _build_stats_table(ticker, spot_price, analytics, surface_stats, results_data)
        
        # Build metrics dict
        metrics = {
            "ticker": ticker,
            "spot_price": spot_price,
            "data_points": results_data.get('data_points', 0),
            "greeks_modeled": results_data.get('greeks_modeled', []),
            "atm_delta": analytics.get('atm_delta', 0),
            "atm_gamma": analytics.get('atm_gamma', 0),
            "max_gamma_strike": analytics.get('max_gamma_strike', 0),
        }
        
        return {
            "status": "success",
            "tool_id": "greeks_surface",
            "tickers": [ticker],
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Greeks surface failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


def _build_metric_cards(
    ticker: str,
    spot_price: float,
    analytics: Dict[str, Any],
    surface_stats: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build metric cards from Greeks surface results."""
    cards = []
    
    # Spot price
    cards.append({
        "id": "spot_price",
        "label": "Spot Price",
        "value": f"${spot_price:.2f}" if spot_price else "N/A",
        "sentiment": "neutral",
    })
    
    # ATM Delta
    atm_delta = analytics.get('atm_delta', 0)
    cards.append({
        "id": "atm_delta",
        "label": "ATM Delta",
        "value": f"{atm_delta:.3f}" if atm_delta else "N/A",
        "sentiment": "positive" if atm_delta and atm_delta > 0.4 else "neutral",
    })
    
    # ATM Gamma
    atm_gamma = analytics.get('atm_gamma', 0)
    cards.append({
        "id": "atm_gamma",
        "label": "ATM Gamma",
        "value": f"{atm_gamma:.4f}" if atm_gamma else "N/A",
        "sentiment": "neutral",
    })
    
    # ATM Theta
    atm_theta = analytics.get('atm_theta', 0)
    cards.append({
        "id": "atm_theta",
        "label": "ATM Theta",
        "value": f"${atm_theta:.2f}/day" if atm_theta else "N/A",
        "sentiment": "negative" if atm_theta and atm_theta < -0.5 else "neutral",
    })
    
    # ATM Vega
    atm_vega = analytics.get('atm_vega', 0)
    cards.append({
        "id": "atm_vega",
        "label": "ATM Vega",
        "value": f"${atm_vega:.2f}" if atm_vega else "N/A",
        "sentiment": "neutral",
    })
    
    # Max Gamma Strike
    max_gamma_strike = analytics.get('max_gamma_strike')
    if max_gamma_strike:
        cards.append({
            "id": "max_gamma_strike",
            "label": "Max Gamma Strike",
            "value": f"${max_gamma_strike:.2f}",
            "sentiment": "neutral",
        })
    
    return cards


def _build_stats_table(
    ticker: str,
    spot_price: float,
    analytics: Dict[str, Any],
    surface_stats: Dict[str, Any],
    results_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build stats table from Greeks surface results."""
    rows = []
    
    # Underlying info
    rows.append({"category": "Underlying", "metric": "Symbol", "value": ticker})
    rows.append({"category": "Underlying", "metric": "Spot Price", "value": f"${spot_price:.2f}"})
    rows.append({"category": "Underlying", "metric": "Data Points", "value": str(results_data.get('data_points', 0))})
    
    # ATM Greeks section
    rows.append({"category": "ATM Greeks", "metric": "─" * 20, "value": "─" * 15})
    
    if analytics.get('atm_delta') is not None:
        rows.append({"category": "ATM Greeks", "metric": "Delta (Δ)", "value": f"{analytics['atm_delta']:.4f}"})
    if analytics.get('atm_gamma') is not None:
        rows.append({"category": "ATM Greeks", "metric": "Gamma (Γ)", "value": f"{analytics['atm_gamma']:.5f}"})
    if analytics.get('atm_theta') is not None:
        rows.append({"category": "ATM Greeks", "metric": "Theta (Θ)", "value": f"${analytics['atm_theta']:.3f}/day"})
    if analytics.get('atm_vega') is not None:
        rows.append({"category": "ATM Greeks", "metric": "Vega (ν)", "value": f"${analytics['atm_vega']:.3f}"})
    
    # Key Strikes section
    rows.append({"category": "Key Strikes", "metric": "─" * 20, "value": "─" * 15})
    
    if analytics.get('max_gamma_strike'):
        rows.append({
            "category": "Key Strikes", 
            "metric": "Max Gamma Strike", 
            "value": f"${analytics['max_gamma_strike']:.2f} (Γ={analytics.get('max_gamma_value', 0):.5f})"
        })
    
    if analytics.get('delta_neutral_strike'):
        rows.append({
            "category": "Key Strikes", 
            "metric": "50-Delta Strike", 
            "value": f"${analytics['delta_neutral_strike']:.2f}"
        })
    
    # Ratios section
    if any(analytics.get(k) for k in ['gamma_delta_ratio', 'theta_gamma_ratio', 'vega_theta_ratio']):
        rows.append({"category": "Ratios", "metric": "─" * 20, "value": "─" * 15})
        
        if analytics.get('gamma_delta_ratio'):
            rows.append({"category": "Ratios", "metric": "Gamma/Delta", "value": f"{analytics['gamma_delta_ratio']:.4f}"})
        if analytics.get('theta_gamma_ratio'):
            rows.append({"category": "Ratios", "metric": "|Theta|/Gamma", "value": f"{analytics['theta_gamma_ratio']:.2f}"})
        if analytics.get('vega_theta_ratio'):
            rows.append({"category": "Ratios", "metric": "Vega/|Theta|", "value": f"{analytics['vega_theta_ratio']:.2f}"})
    
    # Surface stats
    for greek_name, stats in surface_stats.items():
        rows.append({"category": f"{greek_name.capitalize()} Surface", "metric": "─" * 20, "value": "─" * 15})
        rows.append({"category": f"{greek_name.capitalize()} Surface", "metric": "Min", "value": f"{stats['min']:.4f}"})
        rows.append({"category": f"{greek_name.capitalize()} Surface", "metric": "Max", "value": f"{stats['max']:.4f}"})
        rows.append({"category": f"{greek_name.capitalize()} Surface", "metric": "Mean", "value": f"{stats['mean']:.4f}"})
    
    return rows
