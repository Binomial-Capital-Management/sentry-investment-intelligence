"""
Canvas executor for Dealer Gamma Regime tool.
"""
import logging
from typing import Dict, Any
from core.agents.quant_tools import analyze_dealer_gamma_regime_internal
from .charts import build_gamma_profile_chart

logger = logging.getLogger(__name__)


async def execute_dealer_gamma(user_id: str, org_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute dealer gamma regime analysis for Canvas.
    
    Analyzes dealer gamma positioning by estimating regime from observable price dynamics.
    """
    try:
        # Extract parameters
        ticker = params.get("ticker", "").upper().strip()
        min_oi = params.get("min_oi_threshold", 100)
        max_dte = params.get("max_dte", 45)
        lookback_days = params.get("lookback_days", 60)
        use_hmm = params.get("use_hmm_regime", False)
        hmm_n_states = params.get("hmm_n_states", 3)
        hmm_features_list = params.get("hmm_features", ["autocorrelation", "volatility", "momentum"])
        
        # Convert list to comma-separated string for the internal function
        if isinstance(hmm_features_list, list):
            hmm_features = ",".join(hmm_features_list)
        else:
            hmm_features = hmm_features_list  # Fallback if it's already a string
        
        if not ticker:
            return {
                "status": "error",
                "error": "Ticker is required",
                "tool_id": "dealer_gamma"
            }
        
        logger.info(f"Analyzing dealer gamma regime for {ticker}: min_oi={min_oi}, max_dte={max_dte}, lookback={lookback_days}, hmm={use_hmm}")
        
        # Call internal function
        result = await analyze_dealer_gamma_regime_internal(
            underlying=ticker,
            min_oi_threshold=min_oi,
            max_dte=max_dte,
            lookback_days=lookback_days,
            use_hmm_regime=use_hmm,
            hmm_n_states=hmm_n_states,
            hmm_features=hmm_features
        )
        
        # Check for errors
        if "error" in result:
            return {
                "status": "error",
                "error": result["error"],
                "tool_id": "dealer_gamma",
                "tickers": [ticker],
                "weights": []
            }
        
        # Extract key data
        spot_price = result.get("spot_price", 0)
        key_levels = result.get("key_levels", {})
        regime_estimate = result.get("regime_estimate", {})
        data_quality = result.get("data_quality", {})
        hmm_regime = result.get("hmm_regime")
        
        regime = regime_estimate.get("regime", "unknown")
        confidence = regime_estimate.get("confidence", 0)
        autocorr = regime_estimate.get("autocorr")
        method = regime_estimate.get("method", "autocorrelation")
        
        max_gamma_strike = key_levels.get("max_gamma_strike", 0)
        put_wall = key_levels.get("put_wall", 0)
        call_wall = key_levels.get("call_wall", 0)
        total_gex = key_levels.get("total_gross_gex_millions", 0)
        
        # Build metric cards
        metric_cards = [
            {
                "label": "Spot Price",
                "value": f"${spot_price:.2f}",
                "subtext": ticker
            },
            {
                "label": "Gamma Regime",
                "value": regime.replace("_", " ").upper() if regime else "UNKNOWN",
                "subtext": f"{confidence:.0%} confidence · {method.upper()}"
            },
            {
                "label": "Max Gamma Strike",
                "value": f"${max_gamma_strike:.2f}",
                "subtext": f"Moneyness: {(max_gamma_strike/spot_price if spot_price else 0):.2%}"
            }
        ]
        
        # Add HMM-specific metrics if available
        if hmm_regime:
            current_state = hmm_regime.get("current_state", "")
            regime_persistence = hmm_regime.get("regime_persistence", 0)
            metric_cards.append({
                "label": "HMM State",
                "value": current_state.replace("state_", "State ").upper(),
                "subtext": f"Persistence: {regime_persistence:.0%}"
            })
        else:
            # Add autocorrelation if simple method
            if autocorr is not None:
                metric_cards.append({
                    "label": "Autocorrelation",
                    "value": f"{autocorr:+.3f}",
                    "subtext": "Lag-1 return autocorr"
                })
        
        # Build stats table (Canvas format: list of dicts with category/metric/value)
        stats_table = [
            {"category": "Price", "metric": "Spot Price", "value": f"${spot_price:.2f}"},
            {"category": "Key Levels", "metric": "Max Gamma Strike", "value": f"${max_gamma_strike:.2f}"},
            {"category": "Key Levels", "metric": "Put Wall", "value": f"${put_wall:.2f}"},
            {"category": "Key Levels", "metric": "Call Wall", "value": f"${call_wall:.2f}"},
            {"category": "Exposure", "metric": "Total Gross GEX", "value": f"${total_gex:.1f}M"},
            {"category": "Regime", "metric": "Gamma Regime", "value": regime.replace("_", " ").title()},
            {"category": "Regime", "metric": "Confidence", "value": f"{confidence:.1%}"},
            {"category": "Regime", "metric": "Detection Method", "value": method.upper()},
            {"category": "Data Quality", "metric": "Contracts Analyzed", "value": f"{data_quality.get('contracts_analyzed', 0):,}"},
            {"category": "Data Quality", "metric": "Put/Call OI Ratio", "value": f"{data_quality.get('put_call_oi_ratio', 0):.2f}"}
        ]
        
        if autocorr is not None:
            stats_table.append({"category": "Regime", "metric": "Autocorrelation", "value": f"{autocorr:+.3f}"})
        
        if hmm_regime:
            stats_table.append({"category": "HMM", "metric": "Current State", "value": hmm_regime.get("current_state", "").replace("state_", "State ")})
            stats_table.append({"category": "HMM", "metric": "Regime Persistence", "value": f"{hmm_regime.get('regime_persistence', 0):.1%}"})
        
        # Build charts (Canvas format: dict with keys for each chart)
        gamma_profile = result.get("gamma_profile", [])
        charts = {}
        
        if gamma_profile:
            chart = build_gamma_profile_chart(
                ticker=ticker,
                gamma_profile=gamma_profile,
                spot_price=spot_price,
                key_levels=key_levels,
                regime_estimate=regime_estimate
            )
            if chart:
                charts["gamma_profile"] = chart
        
        # Summary
        signal = result.get("signal", "")
        summary = (
            f"**{ticker} Dealer Gamma Regime Analysis**\n\n"
            f"**Regime:** {regime.replace('_', ' ').title()} ({confidence:.0%} confidence)\n"
            f"**Method:** {method.upper()}\n"
            f"**Spot Price:** ${spot_price:.2f}\n\n"
            f"**Key Levels:**\n"
            f"- Max Gamma Strike: ${max_gamma_strike:.2f}\n"
            f"- Put Wall: ${put_wall:.2f}\n"
            f"- Call Wall: ${call_wall:.2f}\n\n"
            f"**Signal:** {signal}\n\n"
            f"**Data Quality:** {data_quality.get('contracts_analyzed', 0):,} contracts analyzed "
            f"across {data_quality.get('strikes_included', 0)} strikes."
        )
        
        return {
            "status": "success",
            "tool_id": "dealer_gamma",
            "tickers": [ticker],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "spot_price": spot_price,
                "gamma_regime": regime,
                "confidence": confidence,
                "max_gamma_strike": max_gamma_strike,
                "put_wall": put_wall,
                "call_wall": call_wall,
                "total_gex_millions": total_gex,
                "autocorr": autocorr,
                "method": method
            },
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Dealer gamma execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "tool_id": "dealer_gamma",
            "tickers": [params.get("ticker", "")],
            "weights": []
        }
