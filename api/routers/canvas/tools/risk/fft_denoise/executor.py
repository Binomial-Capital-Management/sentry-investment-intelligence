"""Canvas executor for FFT Denoising.

Applies Fast Fourier Transform denoising to extract underlying trends
and identify dominant cyclical patterns in price data.
"""

import logging
import math
from typing import Dict, Any, List

from core.agents.risk_tools import analyze_fft_trends_internal
from .charts import build_fft_comparison_chart, build_frequency_spectrum_chart

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
    except (ValueError, TypeError):
        return default


async def execute_fft_denoise(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute FFT denoising for Canvas.
    
    Args:
        user_id: User ID (for RLS/permissions)
        org_id: Organization ID (for RLS/permissions)
        params: Dictionary of parameters from frontend form
        
    Returns:
        Canvas-formatted response with status, charts, metrics, etc.
    """
    try:
        # 1. EXTRACT PARAMETERS
        ticker = params.get("ticker", "").upper().strip()
        period = params.get("period", "1Y")
        components_selected = params.get("components", [3, 6, 9, 100])
        
        # 2. VALIDATE required parameters
        if not ticker:
            return {
                "status": "error",
                "error": "Ticker is required",
                "tool_id": "fft_denoise",
                "tickers": [],
                "weights": []
            }
        
        # Ensure components is a list
        if isinstance(components_selected, int):
            components_selected = [components_selected]
        elif not isinstance(components_selected, list):
            components_selected = [3, 6, 9, 100]
        
        logger.info(f"Executing FFT denoising for {ticker}: period={period}, components={components_selected}")
        
        # 3. CALL INTERNAL FUNCTION
        result = await analyze_fft_trends_internal(
            tickers=[ticker],
            components=components_selected,
            period=period
        )
        
        # 4. CHECK FOR ERRORS
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "FFT analysis failed"),
                "tool_id": "fft_denoise",
                "tickers": [ticker],
                "weights": []
            }
        
        # 5. EXTRACT DATA from result
        ticker_result = result.get("results", {}).get(ticker, {})
        
        if not ticker_result:
            return {
                "status": "error",
                "error": f"No data found for {ticker}",
                "tool_id": "fft_denoise",
                "tickers": [ticker],
                "weights": []
            }
        
        noise_reduction_pct = _safe_float(ticker_result.get("noise_reduction_pct", 0))
        dominant_periods = ticker_result.get("dominant_periods_days", [])
        fft_components = ticker_result.get("fft_components", {})
        
        # Get the primary (highest components) denoised signal
        max_comp = max(components_selected) if components_selected else 100
        primary_component = fft_components.get(str(max_comp), {})
        avg_period_days = _safe_float(primary_component.get("avg_period_days", 0))
        
        # Get dominant cycle (shortest period with significant amplitude)
        dominant_cycle_days = _safe_float(dominant_periods[0] if dominant_periods else 0)
        
        # 6. BUILD METRIC CARDS
        metric_cards = [
            {
                "label": "Noise Reduction",
                "value": f"{noise_reduction_pct:.1f}%",
                "subtext": "Random fluctuations filtered out"
            },
            {
                "label": "Dominant Cycle",
                "value": f"{dominant_cycle_days:.0f}d",
                "subtext": "Strongest recurring pattern detected"
            },
            {
                "label": "Trend Period",
                "value": f"{avg_period_days:.0f}d",
                "subtext": f"Average cycle at {max_comp} components"
            }
        ]
        
        # 7. BUILD STATS TABLE
        stats_table = [
            {"category": "Input", "metric": "Ticker", "value": ticker},
            {"category": "Input", "metric": "Period", "value": period},
            {"category": "Input", "metric": "Components", "value": str(components_selected)},
            {"category": "Result", "metric": "Noise Reduction", "value": f"{noise_reduction_pct:.2f}%"},
            {"category": "Result", "metric": "Dominant Cycle", "value": f"{dominant_cycle_days:.1f} days"},
            {"category": "Result", "metric": "Avg Trend Period", "value": f"{avg_period_days:.1f} days"},
        ]
        
        # Add component details
        for comp_str, comp_data in sorted(fft_components.items(), key=lambda x: int(x[0])):
            comp_period = _safe_float(comp_data.get("avg_period_days", 0))
            stats_table.append({
                "category": "Components",
                "metric": f"{comp_str} Components",
                "value": f"{comp_period:.1f} day trend"
            })
        
        # 8. BUILD CHARTS
        charts = {}
        
        # Chart 1: Price comparison (original vs denoised)
        chart1 = build_fft_comparison_chart(
            ticker=ticker,
            dates=ticker_result.get("dates", []),
            original_prices=ticker_result.get("original_prices", []),
            fft_components=fft_components,
            components_selected=components_selected
        )
        if chart1:
            charts["comparison"] = chart1
        
        # Chart 2: Frequency spectrum
        chart2 = build_frequency_spectrum_chart(
            ticker=ticker,
            dominant_frequencies=ticker_result.get("dominant_frequencies", []),
            dominant_periods=dominant_periods
        )
        if chart2:
            charts["spectrum"] = chart2
        
        # 9. BUILD SUMMARY
        component_explanation = []
        for comp in sorted(components_selected):
            if comp <= 5:
                desc = "major trend only (months)"
            elif comp <= 10:
                desc = "medium-term trend (weeks-months)"
            elif comp <= 30:
                desc = "short-term trend (weeks)"
            elif comp <= 60:
                desc = "near-term pattern (days-weeks)"
            else:
                desc = "minimal smoothing (days)"
            component_explanation.append(f"  - **{comp} components**: {desc}")
        
        summary = (
            f"**{ticker} FFT Denoising Analysis**\n\n"
            f"**Key Findings:**\n"
            f"- **Noise Reduction**: {noise_reduction_pct:.1f}% of variance removed through frequency filtering\n"
            f"- **Dominant Cycle**: {dominant_cycle_days:.0f} days (strongest recurring pattern)\n"
            f"- **Avg Trend Period** ({max_comp} comp): {avg_period_days:.0f} days\n\n"
            f"**Component Levels Analyzed:**\n"
            f"{chr(10).join(component_explanation)}\n\n"
            f"**How FFT Denoising Works:**\n"
            f"FFT (Fast Fourier Transform) decomposes price data into frequency components (cycles). "
            f"By keeping only the strongest N components and filtering out high-frequency noise, we reveal "
            f"underlying trends at different timescales. Lower component counts (3-10) show major directional trends, "
            f"while higher counts (50-100) preserve more price action but still remove random noise."
        )
        
        # 10. RETURN CANVAS FORMAT
        return {
            "status": "success",
            "tool_id": "fft_denoise",
            "tickers": [ticker],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "noise_reduction_pct": noise_reduction_pct,
                "dominant_cycle_days": dominant_cycle_days,
                "avg_period_days": avg_period_days,
                "components_analyzed": len(fft_components)
            },
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"FFT denoising execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "fft_denoise",
            "tickers": [params.get("ticker", "")],
            "weights": []
        }


