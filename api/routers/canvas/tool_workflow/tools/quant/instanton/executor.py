"""
Canvas executor for Instanton Rare Event Analysis.

Physics-based crash probability using instanton methods from path integral theory.
Finds the "most likely path to a crash" analytically rather than Monte Carlo.
"""

import logging
from typing import Any, Dict, List, Optional

from core.agents.quant_tools.instanton_rare_event import analyze_instanton_crash_internal
from .charts import (
    build_instanton_path_chart,
    build_severity_distribution_chart,
    build_scenario_comparison_chart,
    build_action_surface_chart,
)

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0) -> float:
    """Safely convert a value to float, handling strings with % signs."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Remove % sign and other common suffixes
        cleaned = val.replace('%', '').replace('x', '').replace('$', '').replace(',', '').strip()
        if not cleaned:
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
) -> tuple[List[str], List[float], Optional[str]]:
    """Resolve tickers and weights from portfolio or direct input."""
    if portfolio_id:
        try:
            from core.services.portfolio_service import PortfolioService
            service = PortfolioService()
            portfolio = await service.get_portfolio(user_id, portfolio_id)
            
            if not portfolio or portfolio.get("status") == "error":
                logger.warning(f"Portfolio {portfolio_id} not found for user {user_id}")
                return [], [], None
            
            actual_portfolio = portfolio.get("portfolio", {})
            resolved_tickers = actual_portfolio.get("tickers", [])
            resolved_weights = actual_portfolio.get("weights", [])
            name = actual_portfolio.get("name", "Portfolio")
            
            if not resolved_weights or len(resolved_weights) != len(resolved_tickers):
                resolved_weights = [1.0 / len(resolved_tickers)] * len(resolved_tickers) if resolved_tickers else []
            
            return resolved_tickers, resolved_weights, name
        except Exception as e:
            logger.warning(f"Failed to load portfolio {portfolio_id}: {e}")
    
    if tickers:
        if not weights:
            weights = [1.0 / len(tickers)] * len(tickers)
        return tickers, weights, None
    
    return [], [], None


async def execute_instanton(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute instanton rare event analysis for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from request
    
    Returns:
        Canvas-formatted response with charts, metrics, and summary
    """
    # Extract parameters
    portfolio_id = params.get("portfolio_id")
    tickers = params.get("tickers")
    weights = params.get("weights")
    ticker = params.get("ticker", "").strip().upper() if params.get("ticker") else None
    crash_pct = float(params.get("crash_pct")) if params.get("crash_pct") is not None else None
    crash_target = params.get("crash_target", "var_99")
    horizon_days = int(params.get("horizon_days", 30))
    lookback_days = int(params.get("lookback_days", 756))
    distribution = params.get("distribution", "auto")
    
    logger.info(f"Executing Instanton analysis: ticker={ticker}, tickers={tickers}, portfolio={portfolio_id}")
    
    try:
        # Determine mode
        if ticker:
            # Single asset mode
            mode = "single"
            analysis_tickers = None
            analysis_weights = None
            name = ticker
        else:
            # Portfolio mode
            mode = "portfolio"
            resolved_tickers, resolved_weights, portfolio_name = await _resolve_portfolio_tickers(
                user_id, org_id, portfolio_id, tickers, weights
            )
            
            if not resolved_tickers:
                return {
                    "status": "error",
                    "error": "No tickers provided. Specify ticker, tickers, or portfolio_id.",
                    "tool_id": "instanton",
                }
            
            analysis_tickers = resolved_tickers
            analysis_weights = resolved_weights
            name = portfolio_name or "Portfolio"
            ticker = None
        
        # Call internal function
        result = await analyze_instanton_crash_internal(
            ticker=ticker,
            tickers=analysis_tickers,
            weights=analysis_weights,
            portfolio_name=name if mode == "portfolio" else "Portfolio",
            crash_pct=crash_pct,
            crash_target=crash_target if not crash_pct else None,
            horizon_days=horizon_days,
            lookback_days=lookback_days,
            distribution=distribution,
            include_path_distribution=True,
            include_portfolio_decomposition=(mode == "portfolio"),
            include_severity_distribution=True,
            generate_charts=False,  # We'll build Canvas-formatted charts
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "instanton",
            }
        
        # Extract key data
        crash_prob = result.get("crash_probability", {})
        summary = result.get("summary", {})
        instanton_path = result.get("instanton_path", {})
        severity_dist = result.get("severity_distribution", {})
        scenarios = result.get("scenarios", [])
        metadata = result.get("metadata", {})
        portfolio_decomp = result.get("portfolio_decomposition")
        
        # Build metric cards
        metric_cards = []
        
        # Primary probability
        prob_pct = _safe_float(crash_prob.get("probability_pct", 0))
        if prob_pct >= 1:
            prob_display = f"{prob_pct:.1f}%"
        elif prob_pct >= 0.01:
            prob_display = f"{prob_pct:.2f}%"
        else:
            prob_display = f"{prob_pct:.4f}%"
        
        crash_pct_val = _safe_float(crash_prob.get('crash_pct', 0))
        metric_cards.append({
            "id": "crash_probability",
            "label": f"{abs(crash_pct_val):.0f}% Crash Probability",
            "value": prob_display,
            "sentiment": "negative" if prob_pct > 5 else ("neutral" if prob_pct > 1 else "positive"),
            "description": f"{horizon_days}-day horizon",
        })
        
        # Tail multiplier
        tail_mult = _safe_float(crash_prob.get("tail_multiplier", 1.0), 1.0)
        metric_cards.append({
            "id": "tail_multiplier",
            "label": "Fat Tail Effect",
            "value": f"{tail_mult:.1f}x",
            "sentiment": "negative" if tail_mult > 2 else ("neutral" if tail_mult > 1.2 else "positive"),
            "description": "vs Gaussian estimate",
        })
        
        # Distribution type
        fitted_dist = result.get("fitted_distribution", {})
        dist_type = fitted_dist.get("type", "unknown")
        if dist_type == "student_t":
            df = _safe_float(fitted_dist.get("df", 0))
            dist_display = f"Student-t (df={df:.1f})"
        else:
            dist_display = "Normal"
        
        metric_cards.append({
            "id": "distribution",
            "label": "Fitted Distribution",
            "value": dist_display,
            "sentiment": "neutral",
            "description": "BIC selected" if distribution == "auto" else "User specified",
        })
        
        # Volatility
        ann_vol = _safe_float(metadata.get("annualized_volatility", 0)) * 100
        metric_cards.append({
            "id": "volatility",
            "label": "Annualized Volatility",
            "value": f"{ann_vol:.1f}%",
            "sentiment": "negative" if ann_vol > 50 else ("neutral" if ann_vol > 25 else "positive"),
            "description": f"Based on {metadata.get('n_observations', 0)} observations",
        })
        
        # Build stats table - list of dicts with category/metric/value
        crash_price = _safe_float(crash_prob.get('crash_price', 0))
        current_price = _safe_float(metadata.get('current_price', 0))
        gaussian_est = _safe_float(crash_prob.get('gaussian_estimate', 0))
        daily_vol = _safe_float(metadata.get('daily_volatility', 0))
        
        stats_table = [
            {"category": "Crash Analysis", "metric": "Crash Target", "value": f"{crash_pct_val:.1f}%"},
            {"category": "Crash Analysis", "metric": "Crash Price", "value": f"${crash_price:,.2f}"},
            {"category": "Crash Analysis", "metric": "Current Price", "value": f"${current_price:,.2f}"},
            {"category": "Probability", "metric": "Fat-Tail Probability", "value": prob_display},
            {"category": "Probability", "metric": "Gaussian Estimate", "value": f"{gaussian_est * 100:.4f}%"},
            {"category": "Probability", "metric": "Tail Multiplier", "value": f"{tail_mult:.2f}x"},
            {"category": "Parameters", "metric": "Horizon", "value": f"{horizon_days} days"},
            {"category": "Parameters", "metric": "Distribution", "value": dist_display},
            {"category": "Volatility", "metric": "Daily Vol", "value": f"{daily_vol * 100:.2f}%"},
            {"category": "Volatility", "metric": "Ann. Vol", "value": f"{ann_vol:.1f}%"},
        ]
        
        # Build charts - dict keyed by chart name
        charts = {}
        
        # 1. Instanton path chart
        if instanton_path:
            try:
                path_chart = build_instanton_path_chart(
                    instanton_path,
                    current_price if current_price else 100,
                    crash_pct_val if crash_pct_val else -20,
                    horizon_days,
                )
                if path_chart:
                    charts["instanton_path"] = path_chart
            except Exception as e:
                logger.warning(f"Failed to build instanton path chart: {e}")
        
        # 2. Severity distribution chart
        if severity_dist or scenarios:
            try:
                severity_chart = build_severity_distribution_chart(
                    result.get("severity_distribution", {}),
                    scenarios,
                )
                if severity_chart:
                    charts["severity_distribution"] = severity_chart
            except Exception as e:
                logger.warning(f"Failed to build severity chart: {e}")
        
        # 3. Scenario comparison chart
        if scenarios and len(scenarios) > 1:
            try:
                scenario_chart = build_scenario_comparison_chart(scenarios)
                charts["scenario_comparison"] = scenario_chart
            except Exception as e:
                logger.warning(f"Failed to build scenario chart: {e}")
        
        # 4. Action surface chart
        try:
            surface_chart = build_action_surface_chart(
                current_price if current_price else 100,
                daily_vol if daily_vol else 0.02,
                horizon_days,
            )
            charts["action_surface"] = surface_chart
        except Exception as e:
            logger.warning(f"Failed to build action surface chart: {e}")
        
        logger.info(f"Built {len(charts)} charts for instanton analysis")
        
        # Build response
        response = {
            "status": "success",
            "tool_id": "instanton",
            "tickers": [ticker] if ticker else (analysis_tickers or []),
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "crash_pct": crash_prob.get("crash_pct"),
                "probability": crash_prob.get("probability"),
                "probability_pct": prob_pct,
                "tail_multiplier": tail_mult,
                "crash_price": crash_prob.get("crash_price"),
                "current_price": metadata.get("current_price"),
                "horizon_days": horizon_days,
                "distribution_type": dist_type,
                "annualized_volatility": ann_vol / 100,
            },
            "summary": (
                f"{summary.get('headline', '')}. "
                f"{summary.get('key_finding', '')}. "
                f"{summary.get('actionable_insight', '')}"
            ),
        }
        
        # Add portfolio decomposition if available
        if portfolio_decomp:
            response["portfolio_decomposition"] = portfolio_decomp
        
        return response
        
    except Exception as e:
        logger.error(f"Instanton Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "tool_id": "instanton",
        }
