"""Chart builders for Mean Reversion Signals Canvas tool."""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_spread_bands_chart(
    ticker: str,
    spread: List[float],
    dates: List[str],
    rolling_mean: List[float],
    rolling_std: List[float],
    z_entry_long: float,
    z_entry_short: float,
) -> Optional[Dict[str, Any]]:
    """Build spread time series with rolling mean and ±σ bands."""
    if not spread or not dates or not rolling_mean or not rolling_std:
        return None
    
    try:
        # Ensure no None values
        rolling_mean = [m if m is not None else 0 for m in rolling_mean]
        rolling_std = [s if s is not None else 0.001 for s in rolling_std]
        
        # Calculate bands
        upper_1 = [m + s for m, s in zip(rolling_mean, rolling_std)]
        lower_1 = [m - s for m, s in zip(rolling_mean, rolling_std)]
        upper_entry = [m + z_entry_short * s for m, s in zip(rolling_mean, rolling_std)]
        lower_entry = [m + z_entry_long * s for m, s in zip(rolling_mean, rolling_std)]
        
        return {
            "plotly": {
                "data": [
                    # Spread line
                    {"type": "scatter", "x": dates, "y": spread, "name": "Price",
                     "mode": "lines", "line": {"color": "#2E86AB", "width": 2}},
                    # Rolling mean
                    {"type": "scatter", "x": dates, "y": rolling_mean, "name": "μ (Mean)",
                     "mode": "lines", "line": {"color": "#1f2937", "dash": "dash", "width": 2}},
                    # ±1σ bands
                    {"type": "scatter", "x": dates, "y": upper_1, "name": "+1σ",
                     "mode": "lines", "line": {"color": "#f59e0b", "dash": "dot", "width": 1.5}},
                    {"type": "scatter", "x": dates, "y": lower_1, "name": "-1σ",
                     "mode": "lines", "line": {"color": "#f59e0b", "dash": "dot", "width": 1.5},
                     "fill": "tonexty", "fillcolor": "rgba(245, 158, 11, 0.1)"},
                    # Entry bands
                    {"type": "scatter", "x": dates, "y": upper_entry, "name": f"+{z_entry_short}σ (SHORT)",
                     "mode": "lines", "line": {"color": "#ef4444", "dash": "dot", "width": 1.5}},
                    {"type": "scatter", "x": dates, "y": lower_entry, "name": f"{z_entry_long}σ (LONG)",
                     "mode": "lines", "line": {"color": "#10b981", "dash": "dot", "width": 1.5}},
                ],
                "layout": {
                    "title": {"text": f"{ticker} Price with Mean Reversion Bands", "x": 0.5},
                    "xaxis": {"title": "Date"},
                    "yaxis": {"title": "Price ($)"},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 450,
                    "hovermode": "x unified",
                },
            },
            "type": "spread_bands",
            "label": f"{ticker} Mean Reversion Bands",
        }
    except Exception as e:
        logger.error(f"Failed to build spread bands chart: {e}")
        return None


def build_zscore_chart(
    ticker: str,
    z_scores: List[float],
    dates: List[str],
    signals: List[int],
    z_entry_long: float,
    z_entry_short: float,
    z_exit: float,
) -> Optional[Dict[str, Any]]:
    """Build z-score time series with signal coloring and thresholds."""
    if not z_scores or not dates:
        return None
    
    try:
        # Color based on signal
        colors = ['#10b981' if s == 1 else '#ef4444' if s == -1 else '#9ca3af' for s in signals]
        
        return {
            "plotly": {
                "data": [
                    # Z-score line with colored markers
                    {"type": "scatter", "x": dates, "y": z_scores, "name": "Z-Score",
                     "mode": "lines+markers", "line": {"color": "#2E86AB", "width": 1},
                     "marker": {"size": 4, "color": colors}},
                ],
                "layout": {
                    "title": {"text": f"{ticker} Z-Score with Trading Thresholds", "x": 0.5},
                    "xaxis": {"title": "Date"},
                    "yaxis": {"title": "Z-Score (σ)"},
                    "shapes": [
                        # Entry thresholds
                        {"type": "line", "y0": z_entry_short, "y1": z_entry_short, "x0": 0, "x1": 1,
                         "xref": "paper", "line": {"color": "#ef4444", "dash": "dash", "width": 2}},
                        {"type": "line", "y0": z_entry_long, "y1": z_entry_long, "x0": 0, "x1": 1,
                         "xref": "paper", "line": {"color": "#10b981", "dash": "dash", "width": 2}},
                        # Exit thresholds
                        {"type": "line", "y0": z_exit, "y1": z_exit, "x0": 0, "x1": 1,
                         "xref": "paper", "line": {"color": "#f59e0b", "dash": "dot", "width": 1.5}},
                        {"type": "line", "y0": -z_exit, "y1": -z_exit, "x0": 0, "x1": 1,
                         "xref": "paper", "line": {"color": "#f59e0b", "dash": "dot", "width": 1.5}},
                        # Zero line
                        {"type": "line", "y0": 0, "y1": 0, "x0": 0, "x1": 1,
                         "xref": "paper", "line": {"color": "#1f2937", "width": 1}},
                    ],
                    "annotations": [
                        {"x": 1.02, "y": z_entry_short, "xref": "paper", "yref": "y",
                         "text": f"SHORT +{z_entry_short}σ", "showarrow": False, "font": {"color": "#ef4444", "size": 10}},
                        {"x": 1.02, "y": z_entry_long, "xref": "paper", "yref": "y",
                         "text": f"LONG {z_entry_long}σ", "showarrow": False, "font": {"color": "#10b981", "size": 10}},
                    ],
                    "height": 400,
                    "hovermode": "x unified",
                },
            },
            "type": "zscore",
            "label": f"{ticker} Z-Score Chart",
        }
    except Exception as e:
        logger.error(f"Failed to build z-score chart: {e}")
        return None


def build_signal_timeline_chart(
    ticker: str,
    signals: List[int],
    dates: List[str],
    transitions: List[Dict],
) -> Optional[Dict[str, Any]]:
    """Build signal timeline showing long/short/flat periods."""
    if not signals or not dates:
        return None
    
    try:
        colors = ['#10b981' if s == 1 else '#ef4444' if s == -1 else '#e5e7eb' for s in signals]
        
        return {
            "plotly": {
                "data": [
                    {"type": "bar", "x": dates, "y": signals, "name": "Position",
                     "marker": {"color": colors, "line": {"color": "#1f2937", "width": 0.5}}},
                ],
                "layout": {
                    "title": {"text": f"{ticker} Trading Signal Timeline", "x": 0.5},
                    "xaxis": {"title": "Date"},
                    "yaxis": {
                        "title": "Position",
                        "tickmode": "array",
                        "tickvals": [-1, 0, 1],
                        "ticktext": ["SHORT", "FLAT", "LONG"],
                        "range": [-1.5, 1.5],
                    },
                    "height": 300,
                },
            },
            "type": "signal_timeline",
            "label": f"{ticker} Signal Timeline",
        }
    except Exception as e:
        logger.error(f"Failed to build signal timeline chart: {e}")
        return None


def build_backtest_chart(
    ticker: str,
    equity_curve: List[float],
    dates: List[str],
    drawdowns: List[float],
) -> Optional[Dict[str, Any]]:
    """Build backtest performance chart with equity curve and drawdown."""
    if not equity_curve or not dates:
        return None
    
    try:
        drawdown_pct = [d * 100 for d in drawdowns]
        
        return {
            "plotly": {
                "data": [
                    # Equity curve
                    {"type": "scatter", "x": dates, "y": equity_curve, "name": "Equity",
                     "mode": "lines", "line": {"color": "#2E86AB", "width": 2}, "yaxis": "y1"},
                    # Drawdown
                    {"type": "scatter", "x": dates, "y": drawdown_pct, "name": "Drawdown (%)",
                     "mode": "lines", "fill": "tozeroy", "line": {"color": "#ef4444", "width": 1},
                     "fillcolor": "rgba(239, 68, 68, 0.2)", "yaxis": "y2"},
                ],
                "layout": {
                    "title": {"text": f"{ticker} Backtest Performance", "x": 0.5},
                    "xaxis": {"title": "Date", "domain": [0, 1]},
                    "yaxis": {"title": "Portfolio Value ($)", "side": "left"},
                    "yaxis2": {"title": "Drawdown (%)", "side": "right", "overlaying": "y",
                               "showgrid": False},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 400,
                    "hovermode": "x unified",
                },
            },
            "type": "backtest",
            "label": f"{ticker} Backtest Performance",
        }
    except Exception as e:
        logger.error(f"Failed to build backtest chart: {e}")
        return None
