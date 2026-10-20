"""
Canvas executor for Crypto-Equity Beta.

Detects crypto-equity correlation regime (RISK_ON/RISK_OFF/NEUTRAL).
"""

import logging
import math
from typing import Any, Dict, List, Optional

from .charts import build_regime_history_chart, build_regime_gauge_chart, build_correlation_heatmap

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


async def execute_crypto_beta(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute crypto-equity beta regime analysis for Canvas.
    """
    from core.agents.alternatives_tools.crypto_equity_beta_regime_tool import (
        analyze_crypto_equity_beta_regime_internal,
    )
    
    # Extract parameters
    crypto_symbol = params.get("crypto_symbol", "BTCUSD")
    equity_symbol = params.get("equity_symbol", "SPY")
    lookback_days = int(params.get("lookback_days", 365))
    rolling_window = int(params.get("rolling_window", 30))
    high_z = float(params.get("high_z_threshold", 1.5))
    low_z = float(params.get("low_z_threshold", -1.5))
    
    # Handle array params (from multiselect)
    additional_cryptos = params.get("additional_cryptos", [])
    if isinstance(additional_cryptos, str):
        additional_cryptos = [s.strip() for s in additional_cryptos.split(",") if s.strip()]
    
    additional_equities = params.get("additional_equities", [])
    if isinstance(additional_equities, str):
        additional_equities = [s.strip() for s in additional_equities.split(",") if s.strip()]
    
    logger.info(f"Executing Crypto Beta: {crypto_symbol} vs {equity_symbol}, {lookback_days}d lookback")
    
    try:
        # Call internal function - NO chart generation, we build our own
        result = await analyze_crypto_equity_beta_regime_internal(
            crypto_symbol=crypto_symbol,
            equity_symbol=equity_symbol,
            lookback_days=lookback_days,
            rolling_window=rolling_window,
            high_z_threshold=high_z,
            low_z_threshold=low_z,
            additional_cryptos=additional_cryptos if additional_cryptos else None,
            additional_equities=additional_equities if additional_equities else None,
            generate_chart=False,
            generate_correlation_matrix=True,
            include_regime_history=True,
        )
        
        if "error" in result:
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "crypto_beta",
            }
        
        # Extract key data
        regime = result.get("current_regime", {})
        metrics = result.get("metrics", {})
        historical_series = result.get("historical_series", {})
        cross_correlations = result.get("cross_asset_correlations", {})
        
        # Regime details (with NaN protection)
        regime_name = regime.get("regime", "UNKNOWN")
        signal = regime.get("signal", "")
        confidence = _safe_float(regime.get("confidence"), 0)
        corr_z = _safe_float(regime.get("correlation_z_score"), 0)
        beta_z = _safe_float(regime.get("beta_z_score"), 0)
        corr_percentile = _safe_float(regime.get("correlation_percentile"), 50)
        
        # Current values (with NaN protection)
        current_corr = _safe_float(metrics.get("current_correlation"), 0)
        current_beta = _safe_float(metrics.get("current_beta"), 0)
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            crypto_symbol, equity_symbol,
            regime_name, signal, confidence,
            current_corr, current_beta, corr_z, corr_percentile,
            lookback_days
        )
        
        # Build stats table
        stats_table = _build_stats_table(result, regime, metrics)
        
        # Build charts from historical_series
        charts = {}
        
        if historical_series:
            # Clean NaN values from series
            raw_corr = historical_series.get("rolling_corr", [])
            clean_corr = [_safe_float(v, 0) for v in raw_corr]
            
            regime_chart = build_regime_history_chart(
                dates=historical_series.get("dates", []),
                crypto_prices=historical_series.get("crypto_prices", []),
                equity_prices=historical_series.get("equity_prices", []),
                rolling_corr=clean_corr,
                crypto_symbol=crypto_symbol,
                equity_symbol=equity_symbol,
                corr_mean=_safe_float(metrics.get("correlation_mean"), 0),
                corr_std=_safe_float(metrics.get("correlation_std"), 0.1),
                high_z=high_z,
                low_z=low_z,
            )
            if regime_chart:
                charts["regime_history"] = regime_chart
        
        # Regime gauge
        gauge_chart = build_regime_gauge_chart(regime_name, confidence, corr_z, current_corr)
        if gauge_chart:
            charts["regime_gauge"] = gauge_chart
        
        # Correlation heatmap (if multiple assets)
        if cross_correlations and len(cross_correlations) > 2:
            heatmap = build_correlation_heatmap(cross_correlations)
            if heatmap:
                charts["correlation_matrix"] = heatmap
        
        # Build summary
        summary = (
            f"{crypto_symbol}/{equity_symbol} Regime: {regime_name}. "
            f"Correlation: {current_corr:.3f} (z={corr_z:+.2f}σ, {corr_percentile:.0f}th percentile). "
            f"Beta: {current_beta:.2f}. {signal}"
        )
        
        return {
            "status": "success",
            "tool_id": "crypto_beta",
            "tickers": [crypto_symbol, equity_symbol],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "regime": regime_name,
                "correlation": current_corr,
                "beta": current_beta,
                "corr_z_score": corr_z,
                "confidence": confidence,
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Crypto Beta Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "crypto_beta",
        }


def _build_metric_cards(
    crypto_symbol: str,
    equity_symbol: str,
    regime_name: str,
    signal: str,
    confidence: float,
    current_corr: float,
    current_beta: float,
    corr_z: float,
    corr_percentile: float,
    lookback_days: int,
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    # Regime card with color
    if "RISK_ON" in regime_name:
        sentiment = "positive"
    elif "RISK_OFF" in regime_name:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    cards.append({
        "id": "regime",
        "label": "Regime",
        "value": regime_name,
        "description": f"{lookback_days}d analysis",
        "sentiment": sentiment,
    })
    
    cards.append({
        "id": "correlation",
        "label": "Correlation",
        "value": f"{current_corr:.3f}",
        "description": f"z={corr_z:+.2f}σ",
        "sentiment": "positive" if current_corr > 0.5 else "neutral" if current_corr > 0 else "negative",
    })
    
    cards.append({
        "id": "beta",
        "label": "Beta",
        "value": f"{current_beta:.2f}",
        "description": f"{crypto_symbol} vs {equity_symbol}",
        "sentiment": "positive" if current_beta > 1 else "neutral",
    })
    
    cards.append({
        "id": "confidence",
        "label": "Confidence",
        "value": f"{confidence:.0%}",
        "description": f"{corr_percentile:.0f}th percentile",
        "sentiment": "positive" if confidence > 0.7 else "neutral",
    })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    regime: Dict[str, Any],
    metrics: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    
    # Current
    rows.append({"category": "Current", "metric": "Correlation", "value": f"{_safe_float(metrics.get('current_correlation')):.4f}"})
    rows.append({"category": "Current", "metric": "Beta", "value": f"{_safe_float(metrics.get('current_beta')):.4f}"})
    
    # Historical
    rows.append({"category": "Historical", "metric": "Corr Mean", "value": f"{_safe_float(metrics.get('correlation_mean')):.4f}"})
    rows.append({"category": "Historical", "metric": "Corr Std", "value": f"{_safe_float(metrics.get('correlation_std')):.4f}"})
    rows.append({"category": "Historical", "metric": "Corr Min", "value": f"{_safe_float(metrics.get('correlation_min')):.4f}"})
    rows.append({"category": "Historical", "metric": "Corr Max", "value": f"{_safe_float(metrics.get('correlation_max')):.4f}"})
    rows.append({"category": "Historical", "metric": "Beta Mean", "value": f"{_safe_float(metrics.get('beta_mean')):.4f}"})
    rows.append({"category": "Historical", "metric": "Beta Std", "value": f"{_safe_float(metrics.get('beta_std')):.4f}"})
    
    # Regime
    rows.append({"category": "Regime", "metric": "Classification", "value": regime.get('regime', 'N/A')})
    rows.append({"category": "Regime", "metric": "Corr Z-Score", "value": f"{_safe_float(regime.get('correlation_z_score')):+.2f}σ"})
    rows.append({"category": "Regime", "metric": "Beta Z-Score", "value": f"{_safe_float(regime.get('beta_z_score')):+.2f}σ"})
    rows.append({"category": "Regime", "metric": "Corr Percentile", "value": f"{_safe_float(regime.get('correlation_percentile')):.0f}%"})
    rows.append({"category": "Regime", "metric": "Confidence", "value": f"{_safe_float(regime.get('confidence')):.0%}"})
    
    # Period
    rows.append({"category": "Period", "metric": "Lookback", "value": f"{result.get('lookback_days', 0)} days"})
    rows.append({"category": "Period", "metric": "Data Points", "value": str(result.get('data_points', 0))})
    
    return rows
