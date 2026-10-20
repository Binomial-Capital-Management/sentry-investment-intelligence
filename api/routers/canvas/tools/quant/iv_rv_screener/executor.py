"""Canvas executor for IV vs RV Screener tool."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def execute_iv_rv_screener(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute IV vs RV analysis for Canvas.
    
    Compares implied volatility (from options) to realized volatility (from price history)
    to identify if options are cheap or expensive.
    """
    from core.agents.quant_tools.iv_rv_screener_tool import analyze_iv_rv_internal
    from .charts import (
        build_iv_rv_comparison_chart,
        build_iv_rv_ratio_gauge,
        build_rv_history_chart,
        build_vol_premium_chart,
    )
    
    # Extract parameters
    ticker = params.get("ticker", "SPY").upper().strip()
    rv_window = int(params.get("rv_window", 20))
    min_dte = int(params.get("min_dte", 14))
    max_dte = int(params.get("max_dte", 45))
    
    logger.info(f"Executing IV/RV screener for {ticker}")
    
    try:
        # Call internal function
        result = await analyze_iv_rv_internal(
            ticker=ticker,
            rv_window=rv_window,
            min_dte=min_dte,
            max_dte=max_dte,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "IV/RV analysis failed"),
                "charts": {},
                "metric_cards": [],
                "stats_table": [],
            }
        
        # Extract data
        iv = result.get("iv", 0)
        rv = result.get("rv", 0)
        iv_rv_ratio = result.get("iv_rv_ratio", 1.0)
        iv_rv_percentile = result.get("iv_rv_percentile", 50)
        vol_premium_pct = result.get("vol_premium_pct", 0)
        signal = result.get("signal", "FAIR")
        signal_desc = result.get("signal_description", "")
        rv_windows = result.get("rv_windows", {})
        rv_history = result.get("rv_history", [])
        spot_price = result.get("spot_price", 0)
        
        # Build charts
        charts = {}
        
        # Chart 1: IV vs RV bars
        comparison_chart = build_iv_rv_comparison_chart(ticker, iv, rv_windows)
        if comparison_chart:
            charts["iv_rv_comparison"] = comparison_chart
        
        # Chart 2: IV/RV ratio gauge
        gauge_chart = build_iv_rv_ratio_gauge(ticker, iv_rv_ratio, signal)
        if gauge_chart:
            charts["iv_rv_gauge"] = gauge_chart
        
        # Chart 3: RV history with IV line
        history_chart = build_rv_history_chart(ticker, rv_history, iv)
        if history_chart:
            charts["rv_history"] = history_chart
        
        # Chart 4: Vol premium waterfall
        premium_chart = build_vol_premium_chart(ticker, iv, rv, vol_premium_pct)
        if premium_chart:
            charts["vol_premium"] = premium_chart
        
        logger.info(f"Built {len(charts)} charts for {ticker}")
        
        # Determine signal sentiment
        if signal in ["RICH"]:
            signal_sentiment = "negative"
        elif signal in ["SLIGHTLY_RICH"]:
            signal_sentiment = "neutral"
        elif signal in ["CHEAP"]:
            signal_sentiment = "positive"
        elif signal in ["SLIGHTLY_CHEAP"]:
            signal_sentiment = "positive"
        else:
            signal_sentiment = "neutral"
        
        # Build metric cards
        metric_cards = [
            {"id": "signal", "label": "Signal", "value": signal.replace("_", " "), "sentiment": signal_sentiment},
            {"id": "iv_rv_percentile", "label": "IV/RV Percentile", "value": f"{iv_rv_percentile:.0f}th",
             "sentiment": "negative" if iv_rv_percentile >= 70 else ("positive" if iv_rv_percentile <= 30 else "neutral")},
            {"id": "iv_rv_ratio", "label": "IV/RV Ratio", "value": f"{iv_rv_ratio:.2f}", "sentiment": "neutral"},
            {"id": "atm_iv", "label": "ATM IV", "value": f"{iv*100:.1f}%", "sentiment": "neutral"},
            {"id": "rv", "label": f"RV {rv_window}D", "value": f"{rv*100:.1f}%", "sentiment": "neutral"},
            {"id": "vol_premium", "label": "Vol Premium", "value": f"{vol_premium_pct:+.1f}%",
             "sentiment": "negative" if vol_premium_pct > 10 else ("positive" if vol_premium_pct < -10 else "neutral")},
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Volatility", "metric": "ATM Implied Vol", "value": f"{iv*100:.2f}%"},
            {"category": "Volatility", "metric": f"Realized Vol ({rv_window}D)", "value": f"{rv*100:.2f}%"},
            {"category": "Volatility", "metric": "IV/RV Ratio", "value": f"{iv_rv_ratio:.3f}"},
            {"category": "Volatility", "metric": "IV/RV Percentile", "value": f"{iv_rv_percentile:.0f}th"},
            {"category": "Volatility", "metric": "Vol Premium", "value": f"{vol_premium_pct:+.1f}%"},
            {"category": "Signal", "metric": "Rating", "value": signal.replace("_", " ")},
            {"category": "Signal", "metric": "Description", "value": signal_desc},
        ]
        
        # Add RV windows
        for key, label in [("rv_10d", "RV 10D"), ("rv_20d", "RV 20D"), ("rv_30d", "RV 30D")]:
            rv_val = rv_windows.get(key)
            if rv_val:
                stats_table.append({"category": "RV Windows", "metric": label, "value": f"{rv_val*100:.2f}%"})
        
        # Add trade ideas based on signal
        if signal == "RICH":
            stats_table.extend([
                {"category": "Trade Ideas", "metric": "Strategy", "value": "Consider selling volatility"},
                {"category": "Trade Ideas", "metric": "Structures", "value": "Iron condor, credit spreads, strangles"},
            ])
        elif signal == "CHEAP":
            stats_table.extend([
                {"category": "Trade Ideas", "metric": "Strategy", "value": "Consider buying volatility"},
                {"category": "Trade Ideas", "metric": "Structures", "value": "Straddles, calendars, debit spreads"},
            ])
        else:
            stats_table.append({"category": "Trade Ideas", "metric": "Strategy", "value": "No clear vol edge - focus on direction"})
        
        # Add params
        stats_table.extend([
            {"category": "Parameters", "metric": "RV Window", "value": f"{rv_window} days"},
            {"category": "Parameters", "metric": "IV DTE Range", "value": f"{min_dte}-{max_dte} days"},
        ])
        
        return {
            "status": "success",
            "tool_id": "iv_rv_screener",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "iv": iv,
                "rv": rv,
                "iv_rv_ratio": iv_rv_ratio,
                "iv_rv_percentile": iv_rv_percentile,
                "signal": signal,
            },
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": f"{ticker} IV/RV analysis: {signal.replace('_', ' ')} (ratio: {iv_rv_ratio:.2f}). {signal_desc}",
        }
        
    except Exception as e:
        logger.error(f"IV/RV screener execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "charts": {},
            "metric_cards": [],
            "stats_table": [],
        }
