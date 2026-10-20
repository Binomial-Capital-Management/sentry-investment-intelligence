"""Canvas executor for Squeeze Detector tool."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def execute_squeeze_detector(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute squeeze detection for Canvas.
    
    Detects gamma squeeze and short squeeze setups using dealer positioning,
    options flow, and short interest data.
    """
    from core.agents.quant_tools.squeeze_detector.squeeze_tool import detect_squeeze_internal
    from .charts import (
        build_zscore_bar_chart,
        build_probability_chart,
        build_levels_chart,
        build_magnitude_chart,
    )
    
    # Extract parameters
    ticker = params.get("ticker", "GME").upper().strip()
    lookback_days = int(params.get("lookback_days", 60))
    include_gamma = params.get("include_gamma", True)
    include_momentum = params.get("include_momentum", True)
    include_short = params.get("include_short", True)
    
    logger.info(f"Executing squeeze detector for {ticker}")
    
    try:
        # Call internal function
        result = await detect_squeeze_internal(
            ticker=ticker,
            lookback_days=lookback_days,
            include_gamma=include_gamma,
            include_momentum=include_momentum,
            include_short=include_short,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Squeeze detection failed"),
                "charts": {},
                "metric_cards": [],
                "stats_table": [],
            }
        
        # Extract data
        spot_price = result.get("spot_price", 0)
        features = result.get("features", {})
        key_levels = result.get("key_levels", {})
        timing = result.get("timing", {})
        magnitude = result.get("magnitude", {})
        setup_detected = result.get("setup_detected", False)
        setup_summary = result.get("setup_summary", "")
        confidence = result.get("confidence", "low")
        elevated_signals = result.get("elevated_signals", [])
        signal_count = result.get("signal_count", 0)
        implications = result.get("implications", [])
        
        # Timing data
        trigger_prob_5d = timing.get("trigger_prob_5d", 0)
        trigger_prob_10d = timing.get("trigger_prob_10d", 0)
        
        # Magnitude data
        expected_move = magnitude.get("expected_move", 0)
        ci_90 = magnitude.get("ci_90", [0, 0])
        
        # Build charts - clean, institutional style
        charts = {}
        
        # Chart 1: Z-score bar chart
        zscore_chart = build_zscore_bar_chart(ticker, features)
        if zscore_chart:
            charts["zscores"] = zscore_chart
        
        # Chart 2: Trigger probability
        prob_chart = build_probability_chart(ticker, trigger_prob_5d, trigger_prob_10d)
        if prob_chart:
            charts["probability"] = prob_chart
        
        # Chart 3: Key levels
        levels_chart = build_levels_chart(ticker, spot_price, key_levels)
        if levels_chart:
            charts["key_levels"] = levels_chart
        
        # Chart 4: Expected magnitude
        if expected_move > 0.01:
            mag_chart = build_magnitude_chart(ticker, spot_price, expected_move, ci_90)
            if mag_chart:
                charts["magnitude"] = mag_chart
        
        logger.info(f"Built {len(charts)} charts for {ticker}")
        
        # Determine setup label and sentiment
        if setup_detected and confidence == "high":
            setup_label = "SQUEEZE DETECTED"
            setup_sentiment = "negative"
        elif setup_detected:
            setup_label = "POTENTIAL SETUP"
            setup_sentiment = "neutral"
        else:
            setup_label = "NO SETUP"
            setup_sentiment = "positive"
        
        # Build metric cards
        metric_cards = [
            {"id": "setup", "label": "Setup", "value": setup_label, "sentiment": setup_sentiment},
            {"id": "confidence", "label": "Confidence", "value": confidence.upper(),
             "sentiment": "negative" if confidence == "high" else ("neutral" if confidence == "moderate" else "positive")},
            {"id": "trigger_prob_5d", "label": "5D Trigger Prob", "value": f"{trigger_prob_5d*100:.0f}%",
             "sentiment": "negative" if trigger_prob_5d > 0.5 else ("neutral" if trigger_prob_5d > 0.3 else "positive")},
            {"id": "expected_move", "label": "Expected Move", "value": f"+{expected_move*100:.0f}%",
             "sentiment": "neutral"},
            {"id": "signals_elevated", "label": "Signals Elevated", "value": str(signal_count), "sentiment": "neutral"},
            {"id": "spot_price", "label": "Spot Price", "value": f"${spot_price:.2f}", "sentiment": "neutral"},
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Setup", "metric": "Detected", "value": "Yes" if setup_detected else "No"},
            {"category": "Setup", "metric": "Confidence", "value": confidence.capitalize()},
            {"category": "Setup", "metric": "Summary", "value": setup_summary},
        ]
        
        # Add elevated signals
        if elevated_signals:
            stats_table.append({"category": "Signals", "metric": "Elevated", "value": ", ".join(elevated_signals[:5])})
        
        # Add timing
        stats_table.extend([
            {"category": "Timing", "metric": "5-Day Trigger Prob", "value": f"{trigger_prob_5d*100:.1f}%"},
            {"category": "Timing", "metric": "10-Day Trigger Prob", "value": f"{trigger_prob_10d*100:.1f}%"},
        ])
        
        # Add magnitude
        stats_table.extend([
            {"category": "Magnitude", "metric": "Expected Move", "value": f"+{expected_move*100:.1f}%"},
            {"category": "Magnitude", "metric": "90% CI", "value": f"+{ci_90[0]*100:.0f}% to +{ci_90[1]*100:.0f}%"},
        ])
        
        # Add key levels
        for key, label in [("put_wall", "Put Wall"), ("call_wall", "Call Wall"), 
                          ("gamma_ramp", "Gamma Ramp"), ("zero_gamma", "Zero Gamma")]:
            val = key_levels.get(key)
            if val:
                stats_table.append({"category": "Key Levels", "metric": label, "value": f"${val:.2f}"})
        
        # Add implications
        for i, impl in enumerate(implications[:4]):
            stats_table.append({"category": "Implications", "metric": f"Point {i+1}", "value": impl})
        
        # Add z-scores
        for key, val in features.items():
            if "zscore" in key.lower() and isinstance(val, (int, float)):
                label = key.replace("_zscore", "").replace("_", " ").title()
                stats_table.append({"category": "Z-Scores", "metric": label, "value": f"{val:.2f}σ"})
        
        return {
            "status": "success",
            "tool_id": "squeeze_detector",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "setup_detected": setup_detected,
                "confidence": confidence,
                "trigger_prob_5d": trigger_prob_5d,
                "expected_move": expected_move,
            },
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": f"{ticker} squeeze analysis: {setup_label} ({confidence} confidence). {setup_summary}",
        }
        
    except Exception as e:
        logger.error(f"Squeeze detector execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "charts": {},
            "metric_cards": [],
            "stats_table": [],
        }
