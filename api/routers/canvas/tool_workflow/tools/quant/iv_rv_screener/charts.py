"""Chart builders for IV vs RV Screener Canvas tool."""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_iv_rv_comparison_chart(
    ticker: str,
    iv: float,
    rv_windows: Dict[str, Optional[float]],
) -> Optional[Dict[str, Any]]:
    """Build bar chart comparing IV to various RV windows."""
    try:
        # Build bars
        labels = ["ATM IV"]
        values = [iv * 100]  # Convert to percentage
        colors = ["#8b5cf6"]  # Purple for IV
        
        rv_labels = {
            "rv_10d": "RV 10D",
            "rv_20d": "RV 20D",
            "rv_30d": "RV 30D",
        }
        
        for key, label in rv_labels.items():
            rv_val = rv_windows.get(key)
            if rv_val:
                labels.append(label)
                values.append(rv_val * 100)
                colors.append("#10b981")  # Green for RV
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": labels,
                    "y": values,
                    "marker": {"color": colors},
                    "text": [f"{v:.1f}%" for v in values],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
                }],
                "layout": {
                    "title": {"text": f"{ticker} Implied vs Realized Volatility", "x": 0.5},
                    "xaxis": {"title": ""},
                    "yaxis": {"title": "Annualized Volatility (%)", "rangemode": "tozero"},
                    "height": 350,
                    "showlegend": False,
                },
            },
            "type": "iv_rv_comparison",
            "label": f"{ticker} IV vs RV",
        }
    except Exception as e:
        logger.error(f"Failed to build IV/RV comparison chart: {e}")
        return None


def build_iv_rv_ratio_gauge(
    ticker: str,
    iv_rv_ratio: float,
    signal: str,
) -> Optional[Dict[str, Any]]:
    """Build gauge chart showing IV/RV ratio."""
    try:
        # Color based on signal
        if signal in ["RICH", "SLIGHTLY_RICH"]:
            color = "#ef4444"  # Red
        elif signal in ["CHEAP", "SLIGHTLY_CHEAP"]:
            color = "#10b981"  # Green
        else:
            color = "#6b7280"  # Gray
        
        return {
            "plotly": {
                "data": [{
                    "type": "indicator",
                    "mode": "gauge+number+delta",
                    "value": iv_rv_ratio,
                    "delta": {"reference": 1.0, "increasing": {"color": "#ef4444"}, "decreasing": {"color": "#10b981"}},
                    "gauge": {
                        "axis": {"range": [0.5, 1.5], "tickwidth": 1},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [0.5, 0.8], "color": "#dcfce7"},   # Cheap zone (light green)
                            {"range": [0.8, 0.95], "color": "#fef3c7"}, # Slightly cheap (light yellow)
                            {"range": [0.95, 1.1], "color": "#f3f4f6"}, # Fair (light gray)
                            {"range": [1.1, 1.3], "color": "#fef3c7"},  # Slightly rich (light yellow)
                            {"range": [1.3, 1.5], "color": "#fecaca"},  # Rich zone (light red)
                        ],
                        "threshold": {
                            "line": {"color": "#1f2937", "width": 2},
                            "thickness": 0.75,
                            "value": 1.0,
                        },
                    },
                    "title": {"text": f"{ticker} IV/RV Ratio"},
                }],
                "layout": {
                    "height": 300,
                    "margin": {"t": 50, "b": 20, "l": 30, "r": 30},
                },
            },
            "type": "iv_rv_gauge",
            "label": f"{ticker} IV/RV Ratio",
        }
    except Exception as e:
        logger.error(f"Failed to build IV/RV gauge: {e}")
        return None


def build_rv_history_chart(
    ticker: str,
    rv_history: List[float],
    current_iv: float,
) -> Optional[Dict[str, Any]]:
    """Build RV history chart with current IV line."""
    if not rv_history or len(rv_history) < 5:
        return None
    
    try:
        # Convert to percentage
        rv_pct = [rv * 100 for rv in rv_history]
        iv_pct = current_iv * 100
        
        days = list(range(len(rv_pct)))
        
        return {
            "plotly": {
                "data": [
                    # RV history line
                    {"type": "scatter", "x": days, "y": rv_pct, "name": "Realized Vol",
                     "mode": "lines", "line": {"color": "#10b981", "width": 2},
                     "fill": "tozeroy", "fillcolor": "rgba(16, 185, 129, 0.1)"},
                    # Current IV line
                    {"type": "scatter", "x": [0, len(days)-1], "y": [iv_pct, iv_pct], "name": f"Current IV ({iv_pct:.1f}%)",
                     "mode": "lines", "line": {"color": "#8b5cf6", "width": 2, "dash": "dash"}},
                ],
                "layout": {
                    "title": {"text": f"{ticker} RV History vs Current IV", "x": 0.5},
                    "xaxis": {"title": "Days Ago", "autorange": "reversed"},
                    "yaxis": {"title": "Volatility (%)", "rangemode": "tozero"},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 350,
                },
            },
            "type": "rv_history",
            "label": f"{ticker} RV History",
        }
    except Exception as e:
        logger.error(f"Failed to build RV history chart: {e}")
        return None


def build_vol_premium_chart(
    ticker: str,
    iv: float,
    rv: float,
    vol_premium_pct: float,
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing vol premium breakdown."""
    try:
        iv_pct = iv * 100
        rv_pct = rv * 100
        premium = iv_pct - rv_pct
        
        return {
            "plotly": {
                "data": [{
                    "type": "waterfall",
                    "x": ["Realized Vol", "Vol Premium", "Implied Vol"],
                    "y": [rv_pct, premium, 0],
                    "measure": ["absolute", "relative", "total"],
                    "text": [f"{rv_pct:.1f}%", f"{'+' if premium > 0 else ''}{premium:.1f}%", f"{iv_pct:.1f}%"],
                    "textposition": "outside",
                    "connector": {"line": {"color": "#6b7280"}},
                    "increasing": {"marker": {"color": "#ef4444"}},
                    "decreasing": {"marker": {"color": "#10b981"}},
                    "totals": {"marker": {"color": "#8b5cf6"}},
                }],
                "layout": {
                    "title": {"text": f"{ticker} Volatility Premium Breakdown", "x": 0.5},
                    "yaxis": {"title": "Volatility (%)"},
                    "height": 350,
                    "showlegend": False,
                },
            },
            "type": "vol_premium",
            "label": f"{ticker} Vol Premium",
        }
    except Exception as e:
        logger.error(f"Failed to build vol premium chart: {e}")
        return None
