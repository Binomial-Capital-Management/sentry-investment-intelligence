"""
Canvas executor for Optimal Hedge Path Finder.

Uses Dijkstra's algorithm to find minimum-cost hedging paths from current
portfolio state to target risk profile. Supports Greek targets, beta targets,
sector neutralization.
"""

import logging
from typing import Any, Dict, List, Optional

from core.agents.quant_tools.optimal_hedge_path_tool import find_optimal_hedge_path_internal
from core.services.portfolio_service import PortfolioService
from .charts import build_hedge_allocation_chart, build_factor_comparison_chart, build_path_flow_chart

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0) -> float:
    """Safely convert value to float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace('%', '').replace('x', '').replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned) if cleaned else default
        except ValueError:
            return default
    return default


async def _resolve_portfolio_positions(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
) -> tuple[List[Dict[str, Any]], Optional[float]]:
    """
    Resolve positions from portfolio ID or direct tickers input.
    
    Returns:
        tuple of (positions list, portfolio_value or None)
    """
    positions = []
    portfolio_value = None
    
    # Try portfolio first
    if portfolio_id:
        try:
            service = PortfolioService()
            result = await service.get_portfolio(user_id, portfolio_id)
            
            if result and result.get("status") != "error":
                # Get nested portfolio object
                actual_portfolio = result.get("portfolio", {})
                
                # Extract portfolio value
                portfolio_value = actual_portfolio.get("value")
                logger.info(f"Resolved portfolio '{actual_portfolio.get('name')}': value={portfolio_value}")
                
                # Extract tickers and weights
                ticker_list = actual_portfolio.get("tickers", [])
                weight_list = actual_portfolio.get("weights", [])
                
                if ticker_list:
                    n = len(ticker_list)
                    if not weight_list or len(weight_list) != n:
                        weight_list = [1.0 / n] * n
                    
                    for i, t in enumerate(ticker_list):
                        positions.append({
                            "ticker": t.upper().strip() if isinstance(t, str) else str(t),
                            "weight": weight_list[i],
                        })
                    return positions, portfolio_value
        except Exception as e:
            logger.warning(f"Failed to resolve portfolio {portfolio_id}: {e}")
    
    # Fallback to direct tickers
    if tickers:
        ticker_list = tickers
        if isinstance(tickers, str):
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        else:
            ticker_list = [t.upper().strip() for t in tickers if t]
        
        n = len(ticker_list)
        if n == 0:
            return [], None
        
        # Use provided weights or equal weight
        if weights and len(weights) == n:
            weight_list = weights
        else:
            weight_list = [1.0 / n] * n
        
        for i, ticker in enumerate(ticker_list):
            positions.append({
                "ticker": ticker,
                "weight": weight_list[i],
            })
    
    return positions, portfolio_value


async def execute_hedge_path(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute Dijkstra-based hedge path optimization for Canvas.
    """
    # Extract parameters
    portfolio_id = params.get("portfolio_id")
    tickers = params.get("tickers")
    weights = params.get("weights")
    
    # Parse weights if string
    if isinstance(weights, str):
        try:
            weights = [float(w.strip()) for w in weights.split(",") if w.strip()]
        except ValueError:
            weights = None
    
    # Resolve positions from portfolio or direct tickers
    positions, resolved_portfolio_value = await _resolve_portfolio_positions(
        user_id, org_id, portfolio_id, tickers, weights
    )
    
    # Determine portfolio value:
    # 1. User-provided param takes priority (override)
    # 2. Fall back to portfolio's stored value
    # 3. Default to 1M
    param_portfolio_value = params.get("portfolio_value")
    if param_portfolio_value is not None and float(param_portfolio_value) > 0:
        portfolio_value = float(param_portfolio_value)
        logger.info(f"Portfolio value: ${portfolio_value:,.0f} (from user param)")
    elif resolved_portfolio_value is not None and resolved_portfolio_value > 0:
        portfolio_value = float(resolved_portfolio_value)
        logger.info(f"Portfolio value: ${portfolio_value:,.0f} (from portfolio)")
    else:
        portfolio_value = 1000000.0
        logger.info(f"Portfolio value: ${portfolio_value:,.0f} (default)")
    
    if len(positions) < 1:
        return {
            "status": "error",
            "error": "No positions found. Provide portfolio_id or tickers.",
            "tool_id": "hedge_path",
        }
    
    # Extract targets from params
    delta_reduction_pct = None
    target_beta = None
    target_var_1d_pct = None
    
    raw_delta = params.get("delta_reduction_pct")
    if raw_delta is not None:
        val = _safe_float(raw_delta)
        delta_reduction_pct = val / 100 if val > 1 else val
    
    raw_beta = params.get("target_beta")
    if raw_beta is not None:
        target_beta = _safe_float(raw_beta)
    
    raw_var = params.get("target_var_1d_pct")
    if raw_var is not None:
        val = _safe_float(raw_var)
        target_var_1d_pct = val / 100 if val > 1 else val
    
    neutralize_sectors = params.get("neutralize_sectors")
    if isinstance(neutralize_sectors, str):
        neutralize_sectors = [s.strip().upper() for s in neutralize_sectors.split(",") if s.strip()]
    
    # Default to 50% delta reduction if no targets specified
    if delta_reduction_pct is None and target_beta is None and target_var_1d_pct is None and not neutralize_sectors:
        delta_reduction_pct = 0.50
        logger.info("No targets specified - defaulting to 50% delta reduction")
    
    max_dte = int(params.get("max_dte", 45))
    min_dte = int(params.get("min_dte", 14))
    
    logger.info(f"Hedge targets: delta={delta_reduction_pct}, beta={target_beta}, var={target_var_1d_pct}, sectors={neutralize_sectors}")
    
    logger.info(f"Executing Hedge Path optimization for {len(positions)} positions")
    
    try:
        # Call internal function
        result = await find_optimal_hedge_path_internal(
            positions=positions,
            portfolio_value=portfolio_value,
            target_var_1d_pct=target_var_1d_pct,
            delta_reduction_pct=delta_reduction_pct,
            target_beta=target_beta,
            neutralize_sectors=neutralize_sectors,
            max_dte=max_dte,
            min_dte=min_dte,
        )
        
        if isinstance(result, str):
            import json
            result = json.loads(result)
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error"),
                "tool_id": "hedge_path",
            }
        
        # Extract data
        hedge_portfolio = result.get("hedge_portfolio", {})
        instruments = hedge_portfolio.get("instruments", [])
        total_cost = _safe_float(hedge_portfolio.get("total_cost", 0))
        instrument_count = hedge_portfolio.get("instrument_count", 0)
        
        current_factors = result.get("current_factors", {})
        final_factors = result.get("final_factors_after_hedge", {})
        gaps = result.get("gaps", {})
        gap_closure = result.get("gap_closure", {})
        
        # Build metric cards
        metric_cards = []
        
        # Hedge cost
        metric_cards.append({
            "id": "total_cost",
            "label": "Hedge Cost",
            "value": f"${total_cost:,.0f}",
            "sentiment": "neutral",
            "description": f"{instrument_count} instruments",
        })
        
        # Delta reduction
        delta_before = _safe_float(current_factors.get("delta", 0))
        delta_after = _safe_float(final_factors.get("delta", 0)) if final_factors else delta_before
        delta_reduction = (1 - delta_after / delta_before) * 100 if delta_before != 0 else 0
        metric_cards.append({
            "id": "delta_reduction",
            "label": "Delta Reduction",
            "value": f"{delta_reduction:.0f}%",
            "sentiment": "positive" if delta_reduction > 50 else "neutral",
            "description": f"${delta_before:,.0f} → ${delta_after:,.0f}",
        })
        
        # Beta change
        beta_before = _safe_float(current_factors.get("beta", 1))
        beta_after = _safe_float(final_factors.get("beta", beta_before)) if final_factors else beta_before
        metric_cards.append({
            "id": "beta",
            "label": "Beta",
            "value": f"{beta_after:.2f}",
            "sentiment": "positive" if beta_after < beta_before else "neutral",
            "description": f"From {beta_before:.2f}",
        })
        
        # Gap closure
        delta_closure = _safe_float(gap_closure.get("delta_pct", 0))
        metric_cards.append({
            "id": "gap_closure",
            "label": "Gap Closure",
            "value": f"{delta_closure:.0f}%",
            "sentiment": "positive" if delta_closure > 80 else ("neutral" if delta_closure > 50 else "negative"),
            "description": "Target achieved",
        })
        
        # Build stats table
        stats_table = [
            {"category": "Portfolio", "metric": "Positions", "value": str(len(positions))},
            {"category": "Portfolio", "metric": "Total Value", "value": f"${portfolio_value:,.0f}"},
            {"category": "Before", "metric": "Delta", "value": f"${delta_before:,.0f}"},
            {"category": "Before", "metric": "Beta", "value": f"{beta_before:.2f}"},
            {"category": "Before", "metric": "VaR 95%", "value": f"${_safe_float(current_factors.get('var_1d_95', 0)):,.0f}"},
            {"category": "After", "metric": "Delta", "value": f"${delta_after:,.0f}"},
            {"category": "After", "metric": "Beta", "value": f"{beta_after:.2f}"},
            {"category": "Hedge", "metric": "Instruments", "value": str(instrument_count)},
            {"category": "Hedge", "metric": "Total Cost", "value": f"${total_cost:,.0f}"},
        ]
        
        # Add top instruments
        for i, inst in enumerate(instruments[:5]):
            stats_table.append({
                "category": "Instruments",
                "metric": f"#{i+1} {inst.get('instrument', '')}",
                "value": f"${inst.get('cost', 0):,.0f}",
            })
        
        # Build charts
        charts = {}
        
        # Chart 1: Hedge allocation
        try:
            alloc_chart = build_hedge_allocation_chart(instruments)
            if alloc_chart:
                charts["allocation"] = alloc_chart
        except Exception as e:
            logger.warning(f"Failed to build allocation chart: {e}")
        
        # Chart 2: Factor comparison
        try:
            factor_chart = build_factor_comparison_chart(current_factors, final_factors)
            if factor_chart:
                charts["factors"] = factor_chart
        except Exception as e:
            logger.warning(f"Failed to build factor chart: {e}")
        
        # Chart 3: Path flow
        try:
            flow_chart = build_path_flow_chart(instruments)
            if flow_chart:
                charts["path_flow"] = flow_chart
        except Exception as e:
            logger.warning(f"Failed to build path flow chart: {e}")
        
        logger.info(f"Built {len(charts)} charts for hedge path")
        
        # Build summary
        summary = f"Found {instrument_count} hedge instruments at ${total_cost:,.0f} total cost. "
        summary += f"Delta reduced by {delta_reduction:.0f}%, Beta: {beta_before:.2f} → {beta_after:.2f}."
        
        return {
            "status": "success",
            "tool_id": "hedge_path",
            "tickers": [inst.get("instrument", "") for inst in instruments],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "total_cost": total_cost,
                "instrument_count": instrument_count,
                "delta_before": delta_before,
                "delta_after": delta_after,
                "delta_reduction_pct": delta_reduction,
                "beta_before": beta_before,
                "beta_after": beta_after,
            },
            "hedge_portfolio": instruments,
            "current_factors": current_factors,
            "final_factors": final_factors,
            "gap_closure": gap_closure,
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Hedge path execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "hedge_path",
        }
