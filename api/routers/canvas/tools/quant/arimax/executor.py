"""
Canvas executor for ARIMAX Macro Forecast.

Multi-factor time series forecasting combining:
- FRED economic indicators (rates, inflation, employment, GDP)
- Unusual Whales options sentiment
- FMP market data

Supports stock/ETF forecasts and direct macro indicator forecasts.
"""

import logging
import math
from typing import Any, Dict, List, Optional

from .charts import build_forecast_chart, build_correlation_chart

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


# FRED series mapping: series_id -> display name
FRED_SERIES_MAP = {
    "CPIAUCSL": "CPI Inflation (Consumer Price Index)",
    "CPILFESL": "Core CPI (ex Food & Energy)",
    "PCEPI": "PCE Price Index (Personal Consumption)",
    "DGS10": "10-Year Treasury Rate",
    "DGS2": "2-Year Treasury Rate",
    "DGS30": "30-Year Treasury Rate",
    "FEDFUNDS": "Federal Funds Rate",
    "UNRATE": "Unemployment Rate",
    "ICSA": "Initial Jobless Claims (Weekly)",
    "PAYEMS": "Nonfarm Payrolls (Total Employees)",
    "GDPC1": "Real GDP (Quarterly)",
    "INDPRO": "Industrial Production Index",
    "RSXFS": "Retail Sales (ex Food Services)",
    "HOUST": "Housing Starts (New Construction)",
    "VIXCLS": "VIX Volatility Index",
    "T10Y2Y": "Yield Curve Spread (10Y-2Y)",
    "T10Y3M": "Yield Curve Spread (10Y-3M)",
    "BAMLH0A0HYM2": "High Yield Corporate Bond Spread",
    "DEXUSEU": "USD/EUR Exchange Rate",
    "DEXJPUS": "USD/JPY Exchange Rate",
    "DCOILWTICO": "Crude Oil (WTI) Price",
    "GOLDAMGBD228NLBM": "Gold Price (London PM Fix)",
    "M2SL": "M2 Money Supply",
    "WALCL": "Fed Balance Sheet (Total Assets)"
}


async def execute_arimax(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute ARIMAX Macro Forecast for Canvas.
    
    Modes:
    1. Stock/ETF forecast: Set forecast_mode='stock' and ticker='AAPL'
    2. Macro forecast: Set forecast_mode='macro' and indicator='CPIAUCSL'
    """
    from core.agents.quant_tools import forecast_arimax_macro_internal
    
    # Extract mode (required field, no default)
    forecast_mode = params.get("forecast_mode", "").strip().lower()
    
    if not forecast_mode:
        return {
            "status": "error",
            "error": "Please select a forecast mode (stock or macro)",
            "tool_id": "arimax",
        }
    
    # Extract ticker or FRED series based on mode
    ticker = None
    fred_series = None
    
    if forecast_mode == "stock":
        ticker = params.get("stock_symbol", "").strip().upper()
        if not ticker:
            return {
                "status": "error",
                "error": "Please provide a stock/ETF symbol for stock forecast mode",
                "tool_id": "arimax",
            }
    elif forecast_mode == "macro":
        indicator = params.get("macro_indicator", "").strip()
        if not indicator:
            return {
                "status": "error",
                "error": "Please select an economic indicator for macro forecast mode",
                "tool_id": "arimax",
            }
        # Map display name back to series ID if needed
        if indicator in FRED_SERIES_MAP:
            fred_series = indicator
        else:
            # Try reverse lookup
            for series_id, display_name in FRED_SERIES_MAP.items():
                if indicator == display_name:
                    fred_series = series_id
                    break
            if not fred_series:
                fred_series = indicator  # Use as-is if not in map
    else:
        return {
            "status": "error",
            "error": f"Invalid forecast_mode: {forecast_mode}. Use 'stock' or 'macro'",
            "tool_id": "arimax",
        }
    
    # Extract parameters
    forecast_periods = int(params.get("forecast_periods", 30))
    period = params.get("period", "3Y")
    confidence_level = float(params.get("confidence_level", 0.95))
    max_indicators = int(params.get("max_indicators", 5))
    
    # Indicator categories (multi-select)
    indicator_categories = params.get("indicator_categories", ["rates", "inflation"])
    if isinstance(indicator_categories, str):
        indicator_categories = [cat.strip() for cat in indicator_categories.split(",") if cat.strip()]
    
    target_name = ticker if ticker else fred_series
    logger.info(f"Executing ARIMAX: mode={forecast_mode}, target={target_name}, periods={forecast_periods}")
    
    try:
        # Call the internal function
        result = await forecast_arimax_macro_internal(
            ticker=ticker,
            fred_series=fred_series,
            forecast_periods=forecast_periods,
            period=period,
            confidence_level=confidence_level,
            indicator_categories=indicator_categories,
            auto_select_indicators=True,
            max_indicators=max_indicators,
            include_uw_sentiment=False,  # UW sentiment disabled - not suitable for long historical periods
            include_macro_dashboard=True,
            include_correlation_analysis=True
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "ARIMAX forecast failed"),
                "tool_id": "arimax",
            }
        
        # Extract summary data
        summary = result.get("summary", {})
        diagnostics = result.get("diagnostics", {})
        forecast_data = result.get("forecast", {})
        
        last_value = _safe_float(summary.get("last_value"))
        forecast_end = _safe_float(summary.get("forecast_end_value"))
        forecast_change_pct = _safe_float(summary.get("forecast_change_pct"))
        r_squared = _safe_float(summary.get("r_squared"))
        mape = _safe_float(summary.get("mape"))
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            target_name=target_name,
            last_value=last_value,
            forecast_end=forecast_end,
            forecast_change_pct=forecast_change_pct,
            r_squared=r_squared,
            mape=mape,
            indicators_used=diagnostics.get("exogenous_variables", 0)
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            result=result,
            target_name=target_name,
            forecast_mode=forecast_mode
        )
        
        # Build charts from raw data
        charts = {}
        
        # Extract historical and forecast data
        historical = result.get("historical", {})
        forecast_data = result.get("forecast", {})
        
        hist_dates = historical.get("dates", [])
        hist_values = historical.get("values", [])
        fitted_values = historical.get("fitted", [])
        
        forecast_dates = forecast_data.get("dates", [])
        forecast_values = forecast_data.get("values", [])
        conf_interval = forecast_data.get("confidence_interval", {})
        conf_lower = conf_interval.get("lower", [])
        conf_upper = conf_interval.get("upper", [])
        
        # Build main forecast chart
        if hist_dates and hist_values and forecast_dates and forecast_values:
            forecast_chart = build_forecast_chart(
                target_name=target_name,
                historical_dates=hist_dates,
                historical_values=hist_values,
                fitted_values=fitted_values,
                forecast_dates=forecast_dates,
                forecast_values=forecast_values,
                conf_lower=conf_lower,
                conf_upper=conf_upper,
                selected_indicators=diagnostics.get("selected_indicators", []),
                confidence_level=confidence_level
            )
            if forecast_chart:
                charts["forecast"] = forecast_chart
        
        # Build correlation chart from selected indicators
        selected = diagnostics.get("selected_indicators", [])
        if selected:
            corr_chart = build_correlation_chart(selected)
            if corr_chart:
                charts["correlations"] = corr_chart
        
        logger.info(f"Built {len(charts)} charts for ARIMAX")
        
        # Build summary text
        direction = "↑" if forecast_change_pct > 0 else "↓"
        direction_text = "increase" if forecast_change_pct > 0 else "decrease"
        
        summary_text = f"**ARIMAX Forecast: {target_name}**\n\n"
        summary_text += f"**Forecast Summary**\n"
        summary_text += f"- Current Value: ${last_value:,.2f}\n"
        summary_text += f"- {forecast_periods}-Day Forecast: ${forecast_end:,.2f} ({direction} {abs(forecast_change_pct):.1f}%)\n"
        summary_text += f"- Direction: {direction_text.upper()}\n"
        summary_text += f"- Model Quality: R² = {r_squared:.3f}, MAPE = {mape:.1f}%\n\n"
        
        summary_text += f"**Model Details**\n"
        summary_text += f"- ARIMA Order: {diagnostics.get('order', 'N/A')}\n"
        summary_text += f"- Exogenous Variables: {diagnostics.get('exogenous_variables', 0)} macro indicators\n"
        summary_text += f"- Training Points: {diagnostics.get('training_points', 0)}\n"
        summary_text += f"- Confidence Level: {int(confidence_level * 100)}%\n\n"
        
        # Add selected indicators
        selected = diagnostics.get("selected_indicators", [])
        if selected:
            summary_text += f"**Top Correlated Indicators**\n"
            for ind in selected[:5]:
                series_name = ind.get("series", "")
                corr = ind.get("correlation", 0)
                lag = ind.get("lag", 0)
                lag_str = f" (lag {lag}d)" if lag > 0 else ""
                summary_text += f"- {series_name}{lag_str}: ρ = {corr:+.3f}\n"
        
        return {
            "status": "success",
            "tool_id": "arimax",
            "tickers": [ticker] if ticker else [],
            "weights": [1.0] if ticker else [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "last_value": last_value,
                "forecast_end": forecast_end,
                "forecast_change_pct": forecast_change_pct,
                "r_squared": r_squared,
                "mape": mape,
                "indicators_used": diagnostics.get("exogenous_variables", 0)
            },
            "summary": summary_text,
        }
        
    except Exception as e:
        logger.error(f"ARIMAX Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "arimax",
        }


def _build_metric_cards(
    target_name: str,
    last_value: float,
    forecast_end: float,
    forecast_change_pct: float,
    r_squared: float,
    mape: float,
    indicators_used: int
) -> List[Dict[str, Any]]:
    """Build metric cards for display."""
    cards = []
    
    # Current value
    cards.append({
        "id": "current_value",
        "label": "Current Value",
        "value": f"${last_value:,.2f}",
        "description": f"{target_name} current",
        "sentiment": "neutral",
    })
    
    # Forecast value
    cards.append({
        "id": "forecast_value",
        "label": "Forecast Value",
        "value": f"${forecast_end:,.2f}",
        "description": "Expected end value",
        "sentiment": "positive" if forecast_change_pct > 0 else "negative",
    })
    
    # Expected change
    direction_symbol = "↑" if forecast_change_pct > 0 else "↓"
    cards.append({
        "id": "forecast_change",
        "label": "Expected Change",
        "value": f"{direction_symbol} {abs(forecast_change_pct):.1f}%",
        "description": "Over forecast period",
        "sentiment": "positive" if forecast_change_pct > 0 else "negative",
    })
    
    # Model quality
    quality_sentiment = "positive" if r_squared >= 0.7 else ("warning" if r_squared >= 0.4 else "negative")
    cards.append({
        "id": "r_squared",
        "label": "Model R²",
        "value": f"{r_squared:.3f}",
        "description": f"MAPE: {mape:.1f}%",
        "sentiment": quality_sentiment,
    })
    
    # Indicators used
    cards.append({
        "id": "indicators",
        "label": "Macro Indicators",
        "value": str(indicators_used),
        "description": "Exogenous variables",
        "sentiment": "neutral",
    })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    target_name: str,
    forecast_mode: str
) -> List[Dict[str, str]]:
    """Build stats table rows."""
    rows = []
    
    summary = result.get("summary", {})
    diagnostics = result.get("diagnostics", {})
    
    # Input section
    rows.append({
        "category": "Input",
        "metric": "Target",
        "value": target_name,
    })
    
    rows.append({
        "category": "Input",
        "metric": "Mode",
        "value": "Stock Forecast" if forecast_mode == "stock" else "Macro Forecast",
    })
    
    rows.append({
        "category": "Input",
        "metric": "Training Points",
        "value": str(diagnostics.get("training_points", 0)),
    })
    
    # Model section
    rows.append({
        "category": "Model",
        "metric": "ARIMA Order (p,d,q)",
        "value": str(diagnostics.get("order", "N/A")),
    })
    
    seasonal_order = diagnostics.get("seasonal_order")
    if seasonal_order:
        rows.append({
            "category": "Model",
            "metric": "Seasonal Order",
            "value": str(seasonal_order),
        })
    
    rows.append({
        "category": "Model",
        "metric": "Exogenous Variables",
        "value": str(diagnostics.get("exogenous_variables", 0)),
    })
    
    rows.append({
        "category": "Model",
        "metric": "AIC",
        "value": f"{diagnostics.get('aic', 0):,.1f}",
    })
    
    rows.append({
        "category": "Model",
        "metric": "BIC",
        "value": f"{diagnostics.get('bic', 0):,.1f}",
    })
    
    # Forecast section
    rows.append({
        "category": "Forecast",
        "metric": "Current Value",
        "value": f"${summary.get('last_value', 0):,.2f}",
    })
    
    rows.append({
        "category": "Forecast",
        "metric": "Forecast End",
        "value": f"${summary.get('forecast_end_value', 0):,.2f}",
    })
    
    change_pct = summary.get("forecast_change_pct", 0)
    direction = "↑" if change_pct > 0 else "↓"
    rows.append({
        "category": "Forecast",
        "metric": "Expected Change",
        "value": f"{direction} {abs(change_pct):.1f}%",
    })
    
    # Quality section
    rows.append({
        "category": "Quality",
        "metric": "R² Score",
        "value": f"{summary.get('r_squared', 0):.3f}",
    })
    
    rows.append({
        "category": "Quality",
        "metric": "MAPE",
        "value": f"{summary.get('mape', 0):.1f}%",
    })
    
    return rows
