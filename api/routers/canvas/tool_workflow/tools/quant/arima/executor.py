"""ARIMA Forecast Executor for Canvas.

Wraps the ARIMA forecasting tool for Canvas execution.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


async def execute_arima_forecast(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute ARIMA forecast for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including ticker, forecast_periods, period
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.quant_tools.arima_forecast_tool import forecast_arima_internal
    
    try:
        # Get ticker - single ticker for ARIMA
        ticker = params.get('ticker', '')
        if isinstance(ticker, list):
            ticker = ticker[0] if ticker else ''
        ticker = ticker.upper().strip()
        
        if not ticker:
            return {"status": "error", "error": "Ticker is required"}
        
        # Extract parameters with defaults
        forecast_periods = int(params.get('forecast_periods', 30))
        period = params.get('period', '1Y')
        seasonal = params.get('seasonal', True)
        seasonal_period = int(params.get('seasonal_period', 5))
        max_p = int(params.get('max_p', 10))
        max_q = int(params.get('max_q', 10))
        stepwise = params.get('stepwise', True)
        
        # Manual ARIMA order override
        arima_order = None
        manual_order = params.get('arima_order')
        if manual_order:
            if isinstance(manual_order, str):
                # Parse "5,1,2" format
                parts = [int(x.strip()) for x in manual_order.split(',')]
                if len(parts) == 3:
                    arima_order = parts
            elif isinstance(manual_order, list) and len(manual_order) == 3:
                arima_order = [int(x) for x in manual_order]
        
        logger.info(f"Canvas ARIMA forecast: {ticker}, {forecast_periods} periods, {period} history, order={arima_order}")
        
        # Call the internal function
        result = await forecast_arima_internal(
            tickers=[ticker],
            forecast_periods=forecast_periods,
            arima_order=arima_order,
            auto_select_params=(arima_order is None),  # Auto if no manual order
            period=period,
            stepwise=stepwise,
            max_p=max_p,
            max_q=max_q,
            seasonal=seasonal,
            seasonal_period=seasonal_period,
        )
        
        if result.get('status') == 'error':
            return {"status": "error", "error": result.get('error', 'ARIMA forecast failed')}
        
        # Extract ticker result
        ticker_result = result.get('results', {}).get(ticker, {})
        if not ticker_result:
            return {"status": "error", "error": f"No forecast result for {ticker}"}
        
        forecast_data = ticker_result.get('forecast', {})
        historical_data = ticker_result.get('historical', {})
        diagnostics = ticker_result.get('diagnostics', {})
        summary = ticker_result.get('summary', {})
        
        # Debug log the data we have
        logger.info(f"ARIMA result keys for {ticker}: {list(ticker_result.keys())}")
        logger.info(f"Historical data: {len(historical_data.get('dates', []))} dates, {len(historical_data.get('prices', []))} prices")
        logger.info(f"Forecast data: {len(forecast_data.get('dates', []))} dates, {len(forecast_data.get('values', []))} values")
        
        # Build Canvas charts from historical + forecast data
        from .charts import build_arima_forecast_chart
        
        charts = {}
        
        hist_dates = historical_data.get('dates', [])
        hist_prices = historical_data.get('prices', [])
        fitted_vals = historical_data.get('fitted_values', [])
        fc_dates = forecast_data.get('dates', [])
        fc_values = forecast_data.get('values', [])
        conf_ints = forecast_data.get('confidence_intervals', {})
        
        if hist_dates and fc_dates:
            forecast_chart = build_arima_forecast_chart(
                ticker=ticker,
                historical_dates=hist_dates,
                historical_prices=hist_prices,
                fitted_values=fitted_vals,
                forecast_dates=fc_dates,
                forecast_values=fc_values,
                confidence_intervals=conf_ints,
            )
            if forecast_chart:
                charts["forecast"] = forecast_chart
                logger.info(f"Built ARIMA chart for {ticker} with plotly key: {'plotly' in forecast_chart}")
            else:
                logger.warning(f"build_arima_forecast_chart returned None for {ticker}")
        else:
            logger.warning(f"Missing data for chart: hist_dates={len(hist_dates)}, fc_dates={len(fc_dates)}")
        
        if not charts:
            logger.warning(f"No charts available for {ticker}")
        
        # Build metric cards
        metric_cards = _build_metric_cards(ticker, summary, diagnostics, forecast_data)
        
        # Build stats table
        stats_table = _build_stats_table(ticker, summary, diagnostics, forecast_data)
        
        # Build metrics dict
        metrics = {
            "ticker": ticker,
            "forecast_periods": forecast_periods,
            "last_price": summary.get("last_price", 0),
            "forecast_end_price": summary.get("forecast_end_price", 0),
            "forecast_change_pct": summary.get("forecast_change_pct", 0),
            "r_squared": summary.get("r_squared", 0),
            "model_order": diagnostics.get("order", []),
            "aic": diagnostics.get("aic", 0),
        }
        
        return {
            "status": "success",
            "tool_id": "arima_forecast",
            "tickers": [ticker],
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"ARIMA forecast failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


def _build_metric_cards(
    ticker: str,
    summary: Dict[str, Any],
    diagnostics: Dict[str, Any],
    forecast_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build metric cards from ARIMA results."""
    cards = []
    
    last_price = summary.get("last_price", 0)
    forecast_end = summary.get("forecast_end_price", 0)
    change_pct = summary.get("forecast_change_pct", 0)
    
    # Current price
    cards.append({
        "id": "current_price",
        "label": "Current Price",
        "value": f"${last_price:.2f}" if last_price else "N/A",
        "sentiment": "neutral",
    })
    
    # Forecast end price
    cards.append({
        "id": "forecast_price",
        "label": f"Forecast Price",
        "value": f"${forecast_end:.2f}" if forecast_end else "N/A",
        "sentiment": "positive" if change_pct > 0 else "negative" if change_pct < 0 else "neutral",
    })
    
    # Forecast change
    cards.append({
        "id": "forecast_change",
        "label": "Expected Change",
        "value": f"{change_pct:+.1f}%",
        "sentiment": "positive" if change_pct > 2 else "negative" if change_pct < -2 else "neutral",
    })
    
    # Model fit (R²)
    r_squared = summary.get("r_squared", 0)
    cards.append({
        "id": "model_fit",
        "label": "Model R²",
        "value": f"{r_squared:.1%}",
        "sentiment": "positive" if r_squared > 0.7 else "negative" if r_squared < 0.3 else "neutral",
    })
    
    # MAPE (prediction accuracy)
    mape = diagnostics.get("mape", 0)
    cards.append({
        "id": "mape",
        "label": "MAPE",
        "value": f"{mape:.1f}%",
        "sentiment": "positive" if mape < 5 else "negative" if mape > 15 else "neutral",
    })
    
    return cards


def _build_stats_table(
    ticker: str,
    summary: Dict[str, Any],
    diagnostics: Dict[str, Any],
    forecast_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build stats table from ARIMA results."""
    rows = []
    
    # Ticker info
    rows.append({"category": "Ticker", "metric": "Symbol", "value": ticker})
    
    last_price = summary.get("last_price", 0)
    if last_price:
        rows.append({"category": "Current", "metric": "Last Price", "value": f"${last_price:.2f}"})
    
    # Forecast section
    rows.append({"category": "Forecast", "metric": "─" * 20, "value": "─" * 15})
    
    forecast_dates = forecast_data.get("dates", [])
    forecast_values = forecast_data.get("values", [])
    
    if forecast_dates and forecast_values:
        rows.append({
            "category": "Forecast",
            "metric": f"End Date ({len(forecast_dates)}d)",
            "value": forecast_dates[-1] if forecast_dates else "N/A"
        })
        rows.append({
            "category": "Forecast",
            "metric": "End Price",
            "value": f"${forecast_values[-1]:.2f}" if forecast_values else "N/A"
        })
    
    change_pct = summary.get("forecast_change_pct", 0)
    rows.append({
        "category": "Forecast",
        "metric": "Expected Change",
        "value": f"{change_pct:+.1f}%"
    })
    
    # Confidence intervals
    conf_ints = forecast_data.get("confidence_intervals", {})
    if conf_ints and forecast_values:
        for conf_level, bounds in conf_ints.items():
            conf_pct = int(float(conf_level) * 100)
            lower = bounds.get("lower", [])[-1] if bounds.get("lower") else 0
            upper = bounds.get("upper", [])[-1] if bounds.get("upper") else 0
            rows.append({
                "category": "Confidence",
                "metric": f"{conf_pct}% Range",
                "value": f"${lower:.2f} - ${upper:.2f}"
            })
    
    # Model diagnostics
    rows.append({"category": "Model", "metric": "─" * 20, "value": "─" * 15})
    
    order = diagnostics.get("order", [])
    if order:
        order_str = f"({order[0]},{order[1]},{order[2]})" if len(order) >= 3 else str(order)
        rows.append({"category": "Model", "metric": "ARIMA Order", "value": order_str})
    
    r_squared = summary.get("r_squared", 0)
    rows.append({"category": "Model", "metric": "R²", "value": f"{r_squared:.1%}"})
    
    aic = diagnostics.get("aic", 0)
    if aic:
        rows.append({"category": "Model", "metric": "AIC", "value": f"{aic:.1f}"})
    
    mape = diagnostics.get("mape", 0)
    rows.append({"category": "Model", "metric": "MAPE", "value": f"{mape:.2f}%"})
    
    # Backtest quality
    backtest = diagnostics.get("historical_fit_quality", {})
    if backtest:
        backtest_mape = backtest.get("backtest_mape", 0)
        rows.append({"category": "Backtest", "metric": "60-Day MAPE", "value": f"{backtest_mape:.2f}%"})
    
    return rows
