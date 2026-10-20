"""Canvas executor for Gamma Exposure (GEX) tool."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def execute_gex(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute Gamma Exposure analysis for Canvas.
    
    Analyzes dealer gamma positioning to identify key support/resistance levels
    and estimate whether dealers are long or short gamma (mean-reverting vs trending).
    """
    from core.agents.quant_tools.dealer_gamma_regime_tool import analyze_dealer_gamma_regime_internal
    from .charts import (
        build_gamma_profile_chart,
        build_key_levels_chart,
    )
    
    # Extract parameters
    ticker = params.get("ticker", "SPY").upper().strip()
    max_dte = int(params.get("max_dte", 45))
    min_oi = int(params.get("min_oi", 100))
    use_hmm = params.get("use_hmm", False)
    
    logger.info(f"Executing GEX analysis for {ticker}")
    
    try:
        # Call internal function
        result = await analyze_dealer_gamma_regime_internal(
            underlying=ticker,
            min_oi_threshold=min_oi,
            max_dte=max_dte,
            lookback_days=60,
            use_hmm_regime=use_hmm,
        )
        
        if result.get("error"):
            return {
                "status": "error",
                "error": result.get("error", "GEX analysis failed"),
                "charts": {},
                "metric_cards": [],
                "stats_table": [],
            }
        
        # Extract data
        spot_price = result.get("spot_price", 0)
        key_levels = result.get("key_levels", {})
        regime_estimate = result.get("regime_estimate", {})
        gamma_profile = result.get("gamma_profile", [])
        data_quality = result.get("data_quality", {})
        signal = result.get("signal", "")
        
        # Key level values
        max_gamma = key_levels.get("max_gamma_strike", 0)
        put_wall = key_levels.get("put_wall", 0)
        call_wall = key_levels.get("call_wall", 0)
        total_gex = key_levels.get("total_gross_gex_millions", 0)
        
        # Regime info
        regime = regime_estimate.get("regime", "unknown")
        confidence = regime_estimate.get("confidence", 0)
        autocorr = regime_estimate.get("autocorr", 0)
        
        # Build charts
        charts = {}
        
        # Chart 1: Gamma profile by strike
        profile_chart = build_gamma_profile_chart(ticker, spot_price, gamma_profile, key_levels)
        if profile_chart:
            charts["gamma_profile"] = profile_chart
        
        # Chart 2: Key levels visualization
        levels_chart = build_key_levels_chart(ticker, spot_price, key_levels, regime, confidence)
        if levels_chart:
            charts["key_levels"] = levels_chart
        
        logger.info(f"Built {len(charts)} charts for {ticker} GEX")
        
        # Determine regime sentiment
        if regime == "short_gamma" or regime == "SHORT_GAMMA":
            regime_sentiment = "negative"
            regime_label = "SHORT γ"
        elif regime == "long_gamma" or regime == "LONG_GAMMA":
            regime_sentiment = "positive"
            regime_label = "LONG γ"
        else:
            regime_sentiment = "neutral"
            regime_label = "Neutral"
        
        # Build metric cards
        metric_cards = [
            {
                "id": "regime",
                "label": "Dealer Regime",
                "value": regime_label,
                "sentiment": regime_sentiment,
                "description": f"{confidence*100:.0f}% confidence" if confidence else None,
            },
            {
                "id": "max_gamma",
                "label": "Max Gamma Strike",
                "value": f"${max_gamma:,.0f}",
                "sentiment": "neutral",
                "description": "Highest gamma concentration",
            },
            {
                "id": "put_wall",
                "label": "Put Wall",
                "value": f"${put_wall:,.0f}",
                "sentiment": "positive" if put_wall < spot_price else "neutral",
                "description": f"Max put OI ({(spot_price - put_wall) / spot_price * 100:+.1f}% from spot)" if put_wall else None,
            },
            {
                "id": "call_wall",
                "label": "Call Wall",
                "value": f"${call_wall:,.0f}",
                "sentiment": "negative" if call_wall > spot_price else "neutral",
                "description": f"Max call OI ({(call_wall - spot_price) / spot_price * 100:+.1f}% from spot)" if call_wall else None,
            },
            {
                "id": "spot",
                "label": "Spot Price",
                "value": f"${spot_price:,.2f}",
                "sentiment": "neutral",
            },
            {
                "id": "total_gex",
                "label": "Total GEX",
                "value": f"${total_gex:,.1f}M",
                "sentiment": "neutral",
            },
        ]
        
        # Build stats table
        put_dist = (spot_price - put_wall) / spot_price * 100 if put_wall else 0
        call_dist = (call_wall - spot_price) / spot_price * 100 if call_wall else 0
        
        stats_table = [
            {"category": "Key Levels", "metric": "Spot Price", "value": f"${spot_price:,.2f}"},
            {"category": "Key Levels", "metric": "Max Gamma Strike", "value": f"${max_gamma:,.0f} ({(max_gamma - spot_price) / spot_price * 100:+.1f}%)"},
            {"category": "Key Levels", "metric": "Put Wall (Max Put OI)", "value": f"${put_wall:,.0f} ({put_dist:+.1f}% from spot)"},
            {"category": "Key Levels", "metric": "Call Wall (Max Call OI)", "value": f"${call_wall:,.0f} ({call_dist:+.1f}% from spot)"},
        ]
        
        # Regime details
        stats_table.extend([
            {"category": "Regime", "metric": "Dealer Position", "value": regime_label},
            {"category": "Regime", "metric": "Confidence", "value": f"{confidence*100:.0f}%"},
            {"category": "Regime", "metric": "Autocorrelation", "value": f"{autocorr:.4f}" if autocorr else "N/A"},
            {"category": "Regime", "metric": "Method", "value": regime_estimate.get("method", "autocorrelation").title()},
        ])
        
        # Data quality
        stats_table.extend([
            {"category": "Data", "metric": "Contracts Analyzed", "value": f"{data_quality.get('contracts_analyzed', 0):,}"},
            {"category": "Data", "metric": "Strikes Included", "value": str(data_quality.get("strikes_included", 0))},
            {"category": "Data", "metric": "Put/Call OI Ratio", "value": f"{data_quality.get('put_call_oi_ratio', 0):.2f}"},
        ])
        
        # Top gamma strikes
        sorted_profile = sorted(gamma_profile, key=lambda x: x.get("gross_gex_millions", 0), reverse=True)[:5]
        for i, strike_data in enumerate(sorted_profile):
            stats_table.append({
                "category": "Top Gamma Strikes",
                "metric": f"#{i+1} ${strike_data['strike']:,.0f}",
                "value": f"${strike_data['gross_gex_millions']:.2f}M",
            })
        
        # Interpretation
        stats_table.append({
            "category": "Signal",
            "metric": "Interpretation",
            "value": signal[:200] + "..." if len(signal) > 200 else signal,
        })
        
        return {
            "status": "success",
            "tool_id": "gex",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "regime": regime,
                "confidence": confidence,
                "max_gamma_strike": max_gamma,
                "put_wall": put_wall,
                "call_wall": call_wall,
                "spot_price": spot_price,
            },
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": f"{ticker} GEX: {regime_label} regime ({confidence*100:.0f}% confidence). Max gamma at ${max_gamma:,.0f}, put wall ${put_wall:,.0f}, call wall ${call_wall:,.0f}.",
        }
        
    except Exception as e:
        logger.error(f"GEX execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "charts": {},
            "metric_cards": [],
            "stats_table": [],
        }
