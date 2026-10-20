"""
Recession Field Theory Canvas Executor

Wraps the physics-inspired recession early warning tool for Canvas.
Uses phase transition theory to detect recession risk 3-9 months ahead.
"""

import logging
from typing import Any, Dict, List, Optional

from core.agents.quant_tools.recession_field_theory.tool import analyze_recession_field_internal
from .charts import (
    build_warning_gauge_chart,
    build_signals_radar_chart,
    build_regime_probability_chart,
    build_signals_dashboard_chart,
)

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert to float."""
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace("%", "").replace(",", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_signal_status(signal: Dict) -> str:
    """Extract signal status with fallback."""
    status = signal.get("status") or signal.get("signal_status") or "NORMAL"
    return status.upper()


def _get_sentiment(status: str) -> str:
    """Convert status to sentiment."""
    if status == "CRITICAL":
        return "negative"
    elif status == "ELEVATED":
        return "neutral"
    return "positive"


async def execute_recession_field(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute Recession Field Theory analysis for Canvas.
    
    Returns standardized Canvas response with metric cards, stats table, and charts.
    """
    try:
        # Extract params
        lookback_years = int(params.get("lookback_years", 5))
        field_method = params.get("field_method", "weighted")
        include_ml = params.get("include_ml_probability", True)
        
        logger.info(f"[Canvas] Recession Field: lookback={lookback_years}y, method={field_method}")
        
        # Call internal tool
        result = await analyze_recession_field_internal(
            lookback_years=lookback_years,
            field_method=field_method,
            include_ml_probability=include_ml,
            generate_charts=False,  # We build our own charts
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "recession_field",
            }
        
        # Extract key metrics
        composite_score = _safe_float(result.get("composite_warning_score", 0))
        
        economic_field = result.get("economic_field", {})
        field_value = _safe_float(economic_field.get("current_value", 0))
        field_interp = economic_field.get("interpretation", "unknown")
        
        regime = result.get("regime_detection", {})
        current_regime = regime.get("current_regime", "Unknown")
        regime_probs = regime.get("regime_probabilities", {})
        
        recession_prob = result.get("recession_probability", {})
        prob_6m = _safe_float(recession_prob.get("probability") or recession_prob.get("probability_6_month", 0))
        
        # Extract signals - early_warning_signals IS the statistics dict directly
        signals = result.get("early_warning_signals", {})
        signal_summary = result.get("signal_summary", {})
        elevated_count = signal_summary.get("signals_elevated", 0)
        critical_count = signal_summary.get("signals_critical", 0)
        
        logger.info(f"[Canvas] Signals keys: {list(signals.keys())}")
        for k, v in signals.items():
            if isinstance(v, dict):
                logger.info(f"[Canvas] Signal {k}: {list(v.keys())[:5]}")
        
        logger.info(f"[Canvas] Current regime: {current_regime}")
        logger.info(f"[Canvas] Regime probs: {regime_probs}")
        
        # Determine overall sentiment
        if composite_score >= 7:
            overall_sentiment = "negative"
            warning_label = "HIGH RISK"
        elif composite_score >= 5:
            overall_sentiment = "neutral"
            warning_label = "ELEVATED"
        elif composite_score >= 3:
            overall_sentiment = "neutral"
            warning_label = "MODERATE"
        else:
            overall_sentiment = "positive"
            warning_label = "LOW RISK"
        
        # Build metric cards
        metric_cards = [
            {
                "id": "warning_score",
                "label": "Warning Score",
                "value": f"{composite_score:.1f}/10",
                "sentiment": overall_sentiment,
                "description": warning_label,
            },
            {
                "id": "recession_prob",
                "label": "6M Recession Probability",
                "value": f"{prob_6m * 100:.0f}%" if prob_6m else "N/A",
                "sentiment": "negative" if prob_6m > 0.3 else ("neutral" if prob_6m > 0.15 else "positive"),
                "description": "ML-based estimate",
            },
            {
                "id": "current_regime",
                "label": "Business Cycle",
                "value": current_regime.title() if current_regime else "Unknown",
                "sentiment": "negative" if current_regime and any(x in current_regime.lower() for x in ["trough", "contraction"]) else (
                    "neutral" if current_regime and "peak" in current_regime.lower() else "positive"
                ),
                "description": "HMM phase detection",
            },
            {
                "id": "field_value",
                "label": "Economic Field",
                "value": f"{field_value:+.2f}",
                "sentiment": "positive" if field_value > 0.5 else ("negative" if field_value < -0.5 else "neutral"),
                "description": field_interp,
            },
            {
                "id": "critical_signals",
                "label": "Critical Signals",
                "value": f"{critical_count}/{signal_summary.get('signals_total', 4)}",
                "sentiment": "negative" if critical_count > 0 else "positive",
                "description": f"{elevated_count} elevated",
            },
        ]
        
        # Build stats table
        stats_table = []
        
        # Add signal details - extract from statistics dict
        signal_config = {
            "critical_slowing_down": {
                "name": "Critical Slowing Down (AR1)",
                "value_key": "ar1_coefficient",
            },
            "correlation_length": {
                "name": "Correlation Length",
                "value_key": "cross_sector_correlation",
            },
            "susceptibility": {
                "name": "Susceptibility (Variance)",
                "value_key": "variance_ratio",
            },
            "spectral_dominance": {
                "name": "Spectral Dominance",
                "value_key": "first_eigenvalue_share",
            },
        }
        
        for signal_key, config in signal_config.items():
            signal_data = signals.get(signal_key, {})
            value = signal_data.get(config["value_key"], 0)
            status = signal_data.get("signal", "NORMAL")
            normal_range = signal_data.get("normal_range", [0, 1])
            
            stats_table.append({
                "category": "Early Warning Signals",
                "metric": config["name"],
                "value": f"{_safe_float(value):.4f}",
                "status": status,
            })
        
        # Add regime probabilities
        for regime_name, prob in regime_probs.items():
            stats_table.append({
                "category": "Regime Probabilities",
                "metric": regime_name.title(),
                "value": f"{_safe_float(prob) * 100:.1f}%",
            })
        
        # Add field components
        components = economic_field.get("components", {})
        logger.info(f"[Canvas] Field components: {list(components.keys())}")
        if components:
            sample = list(components.items())[0]
            logger.info(f"[Canvas] Sample component '{sample[0]}': {sample[1]}")
        for comp_name, comp_data in list(components.items())[:6]:  # Top 6 components
            if isinstance(comp_data, dict):
                z_score = comp_data.get("z_score", 0)
                contribution = comp_data.get("contribution", 0)
                interpretation = comp_data.get("interpretation", "")
            else:
                z_score = comp_data
                contribution = 0
                interpretation = ""
            
            stats_table.append({
                "category": "Field Components",
                "metric": comp_name.replace("_", " ").title(),
                "value": f"{_safe_float(z_score):.2f}",
                "description": f"Contrib: {_safe_float(contribution):.3f}",
            })
        
        # Build charts (must be dict keyed by chart ID)
        charts = {}
        
        # 1. Warning gauge
        gauge_chart = build_warning_gauge_chart(composite_score, warning_label)
        if gauge_chart:
            charts["warning_gauge"] = gauge_chart
        
        # 2. Signals dashboard (2x2 subplot with all 4 signals)
        dashboard_chart = build_signals_dashboard_chart(signals)
        if dashboard_chart:
            charts["signals_dashboard"] = dashboard_chart
        
        # 3. Signals radar (alternative view)
        radar_chart = build_signals_radar_chart(signals)
        if radar_chart:
            charts["signals_radar"] = radar_chart
        
        # 4. Regime probability bar
        regime_chart = build_regime_probability_chart(regime_probs, current_regime)
        if regime_chart:
            charts["regime_probs"] = regime_chart
        
        # Build summary
        interpretation = result.get("interpretation", "")
        if not interpretation:
            interpretation = f"Recession warning score is {composite_score:.1f}/10 ({warning_label}). "
            interpretation += f"Current regime: {current_regime}. "
            if prob_6m:
                interpretation += f"6-month recession probability: {prob_6m*100:.0f}%."
        
        logger.info(f"[Canvas] Returning: {len(charts)} charts, {len(metric_cards)} metric cards, {len(stats_table)} stats rows")
        
        return {
            "status": "success",
            "tool_id": "recession_field",
            "tickers": ["MACRO"],  # Market-wide analysis
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "composite_warning_score": composite_score,
                "recession_probability_6m": prob_6m,
                "current_regime": current_regime,
                "field_value": field_value,
                "signals_critical": critical_count,
                "signals_elevated": elevated_count,
            },
            "summary": interpretation,
            "raw_result": result,
        }
        
    except Exception as e:
        logger.error(f"[Canvas] Recession Field error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "tool_id": "recession_field",
        }
