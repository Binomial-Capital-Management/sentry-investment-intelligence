"""
Canvas executor for Herding Regime Detector.

Ising model-inspired crowding/herding detection using physics statistics.
Computes magnetization, susceptibility, correlation length, and critical slowing.
"""

import logging
from typing import Any, Dict, List, Optional

from .charts import (
    build_herding_gauge,
    build_signal_bars,
    build_regime_chart,
    build_parameters_chart,
)

logger = logging.getLogger(__name__)


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: Optional[str] = None,
    tickers: Optional[List[str]] = None,
) -> tuple[Optional[List[str]], Optional[str]]:
    """Resolve tickers from portfolio or direct input."""
    if portfolio_id:
        try:
            from core.services.portfolio_service import PortfolioService
            service = PortfolioService()
            portfolio = await service.get_portfolio(user_id, portfolio_id)
            
            if not portfolio or portfolio.get("status") == "error":
                logger.warning(f"Portfolio {portfolio_id} not found for user {user_id}")
                return None, None
            
            actual_portfolio = portfolio.get("portfolio", {})
            resolved_tickers = actual_portfolio.get("tickers", [])
            name = actual_portfolio.get("name", "Portfolio")
            
            return resolved_tickers, name
        except Exception as e:
            logger.warning(f"Failed to load portfolio {portfolio_id}: {e}")
    
    if tickers:
        return tickers, None
    
    return None, None


async def execute_herding(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute herding regime analysis for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from request
    
    Returns:
        Canvas-formatted response with charts, metrics, and summary
    """
    # Import the internal function (not the @function_tool decorated version)
    from core.agents.quant_tools.herding_regime import analyze_herding_regime_internal
    
    # Extract parameters
    portfolio_id = params.get("portfolio_id")
    tickers = params.get("tickers")
    lookback_days = int(params.get("lookback_days", 252))
    window = int(params.get("window", 21))
    field_mode = params.get("field_mode", "discretionary")
    include_vix = params.get("include_vix", True)
    include_options_flow = params.get("include_options_flow", True)
    include_hmm = params.get("include_hmm", True)
    
    logger.info(f"Executing Herding analysis: tickers={tickers}, portfolio={portfolio_id}, field_mode={field_mode}")
    
    try:
        # Resolve tickers from portfolio if provided
        resolved_tickers = None
        portfolio_name = None
        
        if portfolio_id:
            resolved_tickers, portfolio_name = await _resolve_portfolio_tickers(
                user_id, org_id, portfolio_id, tickers
            )
            if resolved_tickers:
                tickers = resolved_tickers
        
        # If tickers is a string, split it
        if isinstance(tickers, str):
            tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        elif tickers:
            tickers = [t.upper() for t in tickers]
        
        # Call the internal herding analysis function (not the @function_tool decorated one)
        # Pass generate_charts=False since we build Canvas charts ourselves
        result = await analyze_herding_regime_internal(
            tickers=tickers,
            lookback_days=lookback_days,
            window=window,
            field_mode=field_mode,
            include_vix=include_vix,
            include_options_flow=include_options_flow,
            include_hmm=include_hmm,
            generate_charts=False,  # We build Canvas-specific charts
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "herding",
            }
        
        # Extract key data
        herding_index = result.get("herding_index", {})
        ising_stats = result.get("ising_statistics", {})
        ising_params = result.get("ising_parameters", {})
        signal_summary = result.get("signal_summary", {})
        trading_implications = result.get("trading_implications", {})
        hmm_regime = result.get("hmm_regime")
        metadata = result.get("metadata", {})
        interpretation = result.get("interpretation", "")
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            herding_index, ising_stats, ising_params, signal_summary, hmm_regime
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            herding_index, ising_stats, ising_params, signal_summary, trading_implications, metadata
        )
        
        # Build charts (compact versions)
        charts = {}
        
        # 1. Herding gauge
        gauge = build_herding_gauge(herding_index)
        if gauge:
            charts["herding_gauge"] = gauge
        
        # 2. Signal bars (4 statistics)
        signals = build_signal_bars({"ising_statistics": ising_stats})
        if signals:
            charts["signal_bars"] = signals
        
        # 3. Regime probabilities (if HMM)
        if hmm_regime:
            regime = build_regime_chart(hmm_regime)
            if regime:
                charts["regime"] = regime
        
        # 4. Ising parameters (T, h, J) - optional
        params = build_parameters_chart(ising_params)
        if params:
            charts["parameters"] = params
        
        logger.info(f"Built {len(charts)} charts for herding analysis")
        
        # Build response
        analyzed_tickers = metadata.get("tickers", tickers or [])
        
        return {
            "status": "success",
            "tool_id": "herding",
            "tickers": analyzed_tickers,
            "weights": [],  # Herding doesn't use weights
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "herding_index": herding_index.get("value"),
                "regime": herding_index.get("regime"),
                "risk_level": herding_index.get("risk_level"),
                "elevated_signals": signal_summary.get("elevated_count", 0),
                "field_mode": field_mode,
            },
            "summary": interpretation,
            "trading_implications": trading_implications,
        }
        
    except Exception as e:
        logger.error(f"Herding Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "herding",
        }


def _build_metric_cards(
    herding_index: Dict[str, Any],
    ising_stats: Dict[str, Any],
    ising_params: Dict[str, Any],
    signal_summary: Dict[str, Any],
    hmm_regime: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    # Herding Index
    value = herding_index.get("value", 0)
    regime = herding_index.get("regime", "NORMAL")
    risk_level = herding_index.get("risk_level", "MODERATE")
    
    cards.append({
        "id": "herding_index",
        "label": "Herding Index",
        "value": f"{value:.0%}",
        "description": f"{regime}",
        "sentiment": "negative" if value > 0.6 else ("neutral" if value > 0.4 else "positive"),
    })
    
    # Elevated Signals
    elevated = signal_summary.get("elevated_count", 0)
    cards.append({
        "id": "elevated_signals",
        "label": "Elevated Signals",
        "value": f"{elevated}/4",
        "description": "Early warnings",
        "sentiment": "negative" if elevated >= 3 else ("neutral" if elevated >= 1 else "positive"),
    })
    
    # Current Regime (from HMM if available)
    if hmm_regime and hmm_regime.get("status") == "success":
        current_state = hmm_regime.get("current_state", "unknown")
        confidence = hmm_regime.get("state_probabilities", {}).get(current_state, 0)
        cards.append({
            "id": "regime",
            "label": "HMM Regime",
            "value": current_state.title(),
            "description": f"{confidence:.0%} confidence",
            "sentiment": (
                "negative" if current_state == "critical"
                else "positive" if current_state == "dispersed"
                else "neutral"
            ),
        })
    
    # Temperature (VIX)
    temp = ising_params.get("temperature", {})
    if temp.get("available"):
        vix = temp.get("vix_current", 0)
        T_regime = temp.get("T_regime", "NORMAL")
        cards.append({
            "id": "temperature",
            "label": "Temperature (VIX)",
            "value": f"{vix:.1f}",
            "description": T_regime.replace("_", " ").title(),
            "sentiment": "negative" if T_regime == "HIGH_TEMP" else "positive" if T_regime == "LOW_TEMP" else "neutral",
        })
    
    # Coupling divergence warning
    coupling = ising_params.get("coupling", {})
    if coupling.get("available") and coupling.get("divergence"):
        direction = coupling.get("divergence_direction", "")
        cards.append({
            "id": "divergence",
            "label": "⚠️ Divergence",
            "value": direction or "Detected",
            "description": "Price vs Options",
            "sentiment": "negative",
        })
    
    return cards


def _build_stats_table(
    herding_index: Dict[str, Any],
    ising_stats: Dict[str, Any],
    ising_params: Dict[str, Any],
    signal_summary: Dict[str, Any],
    trading_implications: Dict[str, Any],
    metadata: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    
    # Herding Index
    rows.append({
        "category": "Herding",
        "metric": "Composite Index",
        "value": f"{herding_index.get('value', 0):.1%}"
    })
    rows.append({
        "category": "Herding",
        "metric": "Regime",
        "value": herding_index.get("regime", "NORMAL")
    })
    rows.append({
        "category": "Herding",
        "metric": "Risk Level",
        "value": herding_index.get("risk_level", "MODERATE")
    })
    
    # Ising Statistics
    for stat_name, display_name in [
        ("magnetization", "Magnetization"),
        ("susceptibility", "Susceptibility"),
        ("correlation_length", "Correlation Length"),
        ("critical_slowing_down", "Critical Slowing"),
    ]:
        stat = ising_stats.get(stat_name, {})
        if stat:
            pct = stat.get("percentile", 0)
            signal = stat.get("signal", "NORMAL")
            rows.append({
                "category": "Ising Statistics",
                "metric": display_name,
                "value": f"{pct:.0%} ({signal})"
            })
    
    # Ising Parameters
    temp = ising_params.get("temperature", {})
    if temp.get("available"):
        rows.append({
            "category": "Parameters",
            "metric": "Temperature (T)",
            "value": f"VIX={temp.get('vix_current', 0):.1f} ({temp.get('T_regime', 'NORMAL')})"
        })
    
    field = ising_params.get("external_field", {})
    if field.get("available"):
        breadth = field.get("breadth", field.get("h_value", 0))
        rows.append({
            "category": "Parameters",
            "metric": "External Field (h)",
            "value": f"{breadth:.0%} ({field.get('bias', 'NEUTRAL')})"
        })
    
    coupling = ising_params.get("coupling", {})
    if coupling.get("available"):
        J = coupling.get("J_effective", 0)
        signal = coupling.get("signal", "MODERATE")
        if coupling.get("divergence"):
            signal = f"⚠️ DIVERGENCE - {coupling.get('divergence_direction', '')}"
        rows.append({
            "category": "Parameters",
            "metric": "Coupling (J)",
            "value": f"{J:.0%} ({signal})"
        })
    
    # Trading Implications
    if trading_implications:
        for key, value in trading_implications.items():
            if value and isinstance(value, str):
                rows.append({
                    "category": "Implications",
                    "metric": key.replace("_", " ").title(),
                    "value": str(value)[:50]
                })
    
    # Metadata
    rows.append({
        "category": "Analysis",
        "metric": "Lookback",
        "value": f"{metadata.get('lookback_days', 252)} days"
    })
    rows.append({
        "category": "Analysis",
        "metric": "Window",
        "value": f"{metadata.get('window', 21)} days"
    })
    rows.append({
        "category": "Analysis",
        "metric": "Tickers",
        "value": str(len(metadata.get("tickers", [])))
    })
    rows.append({
        "category": "Analysis",
        "metric": "Mode",
        "value": metadata.get("mode", "sector_etfs")
    })
    
    return rows
