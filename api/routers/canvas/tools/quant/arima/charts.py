"""Chart builders for ARIMA Forecast Canvas tool."""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_arima_forecast_chart(
    ticker: str,
    historical_dates: List[str],
    historical_prices: List[float],
    fitted_values: List[float],
    forecast_dates: List[str],
    forecast_values: List[float],
    confidence_intervals: Dict[str, Dict[str, List[float]]],
) -> Optional[Dict[str, Any]]:
    """
    Build ARIMA forecast chart with historical prices, fitted line, forecast, and confidence bands.
    
    Args:
        ticker: Stock symbol
        historical_dates: List of historical date strings
        historical_prices: List of historical prices
        fitted_values: Model fitted values for historical period
        forecast_dates: List of forecast date strings
        forecast_values: List of forecasted prices
        confidence_intervals: Dict with confidence level keys and lower/upper bounds
    
    Returns:
        Plotly chart specification dict
    """
    try:
        # Limit historical data for cleaner visualization (last 90 days)
        max_historical = 90
        if len(historical_dates) > max_historical:
            historical_dates = historical_dates[-max_historical:]
            historical_prices = historical_prices[-max_historical:]
            fitted_values = fitted_values[-max_historical:] if fitted_values else []
        
        traces = []
        
        # Historical prices (actual)
        if historical_dates and historical_prices:
            traces.append({
                "type": "scatter",
                "x": historical_dates,
                "y": historical_prices,
                "mode": "lines",
                "name": "Actual Price",
                "line": {"color": "#374151", "width": 1.5},
                "hovertemplate": "<b>%{x}</b><br>Actual: $%{y:.2f}<extra></extra>",
            })
        
        # Fitted values (model fit on historical)
        if historical_dates and fitted_values and len(fitted_values) == len(historical_dates):
            traces.append({
                "type": "scatter",
                "x": historical_dates,
                "y": fitted_values,
                "mode": "lines",
                "name": "Fitted",
                "line": {"color": "#9ca3af", "width": 1, "dash": "dot"},
                "hovertemplate": "<b>%{x}</b><br>Fitted: $%{y:.2f}<extra></extra>",
            })
        
        # Confidence bands (widest first for layering)
        band_configs = [
            ("0.95", "rgba(124, 58, 237, 0.08)", "rgba(124, 58, 237, 0.2)"),
            ("0.8", "rgba(124, 58, 237, 0.15)", "rgba(124, 58, 237, 0.3)"),
            ("0.80", "rgba(124, 58, 237, 0.15)", "rgba(124, 58, 237, 0.3)"),
        ]
        
        for conf_level, fill_color, line_color in band_configs:
            if conf_level in confidence_intervals:
                bounds = confidence_intervals[conf_level]
                conf_pct = int(float(conf_level) * 100)
                
                # Upper bound
                traces.append({
                    "type": "scatter",
                    "x": forecast_dates,
                    "y": bounds.get("upper", []),
                    "mode": "lines",
                    "name": f"{conf_pct}% CI",
                    "line": {"color": line_color, "width": 0},
                    "showlegend": False,
                    "hoverinfo": "skip",
                })
                
                # Lower bound with fill to upper
                traces.append({
                    "type": "scatter",
                    "x": forecast_dates,
                    "y": bounds.get("lower", []),
                    "mode": "lines",
                    "name": f"{conf_pct}% CI",
                    "line": {"color": line_color, "width": 0},
                    "fill": "tonexty",
                    "fillcolor": fill_color,
                    "hovertemplate": f"<b>%{{x}}</b><br>{conf_pct}% CI: $%{{y:.2f}}<extra></extra>",
                })
        
        # Forecast line (on top)
        if forecast_dates and forecast_values:
            traces.append({
                "type": "scatter",
                "x": forecast_dates,
                "y": forecast_values,
                "mode": "lines",
                "name": "Forecast",
                "line": {"color": "#7c3aed", "width": 2.5},
                "hovertemplate": "<b>%{x}</b><br>Forecast: $%{y:.2f}<extra></extra>",
            })
        
        # Current price marker (transition point)
        if historical_dates and historical_prices:
            traces.append({
                "type": "scatter",
                "x": [historical_dates[-1]],
                "y": [historical_prices[-1]],
                "mode": "markers",
                "name": "Current",
                "marker": {"color": "#059669", "size": 10, "symbol": "circle"},
                "hovertemplate": "<b>Current Price</b><br>$%{y:.2f}<extra></extra>",
            })
        
        # Forecast end marker
        if forecast_dates and forecast_values:
            traces.append({
                "type": "scatter",
                "x": [forecast_dates[-1]],
                "y": [forecast_values[-1]],
                "mode": "markers",
                "name": "Target",
                "marker": {"color": "#7c3aed", "size": 8, "symbol": "diamond"},
                "hovertemplate": "<b>Forecast End</b><br>$%{y:.2f}<extra></extra>",
            })
        
        layout = {
            "title": {
                "text": f"{ticker} ARIMA Price Forecast",
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 16},
            },
            "xaxis": {
                "title": "",
                "showgrid": True,
                "gridcolor": "rgba(0,0,0,0.05)",
                "zeroline": False,
            },
            "yaxis": {
                "title": "Price ($)",
                "showgrid": True,
                "gridcolor": "rgba(0,0,0,0.05)",
                "tickprefix": "$",
                "zeroline": False,
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
            "hovermode": "x unified",
            "plot_bgcolor": "white",
            "paper_bgcolor": "white",
            "margin": {"l": 60, "r": 20, "t": 80, "b": 40},
            "height": 450,
            "shapes": [
                # Vertical line at forecast start
                {
                    "type": "line",
                    "x0": historical_dates[-1] if historical_dates else None,
                    "x1": historical_dates[-1] if historical_dates else None,
                    "y0": 0,
                    "y1": 1,
                    "yref": "paper",
                    "line": {"color": "#9ca3af", "width": 1, "dash": "dash"},
                }
            ] if historical_dates else [],
            "annotations": [
                {
                    "x": historical_dates[-1] if historical_dates else None,
                    "y": 1.05,
                    "yref": "paper",
                    "text": "Forecast Start",
                    "showarrow": False,
                    "font": {"size": 10, "color": "#6b7280"},
                }
            ] if historical_dates else [],
        }
        
        return {
            "plotly": {
                "data": traces,
                "layout": layout,
            },
            "type": "arima_forecast",
            "label": f"{ticker} ARIMA Forecast",
        }
        
    except Exception as e:
        logger.error(f"Failed to build ARIMA forecast chart for {ticker}: {e}")
        return None
