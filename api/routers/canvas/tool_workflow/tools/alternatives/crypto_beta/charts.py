"""
Canvas chart builders for Crypto-Equity Beta.

Builds proper historical charts with regime zones.
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

COLORS = {
    "bitcoin": "#F7931A",
    "equity": "#2E86AB",
    "correlation": "#8E44AD",
    "risk_on": "#27AE60",
    "risk_off": "#E74C3C",
    "neutral": "#6b7280",
}


def build_regime_history_chart(
    dates: List[str],
    crypto_prices: List[float],
    equity_prices: List[float],
    rolling_corr: List[float],
    crypto_symbol: str,
    equity_symbol: str,
    corr_mean: float,
    corr_std: float,
    high_z: float,
    low_z: float,
) -> Optional[Dict[str, Any]]:
    """Build two-panel chart: normalized prices + rolling correlation with regime zones."""
    try:
        if not dates or not rolling_corr:
            return None
        
        # Calculate thresholds
        risk_on_threshold = corr_mean + high_z * corr_std
        risk_off_threshold = corr_mean + low_z * corr_std
        
        return {
            "plotly": {
                "data": [
                    # Panel 1: Normalized prices
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": crypto_prices,
                        "name": crypto_symbol,
                        "line": {"color": COLORS["bitcoin"], "width": 2},
                        "xaxis": "x",
                        "yaxis": "y",
                    },
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": equity_prices,
                        "name": equity_symbol,
                        "line": {"color": COLORS["equity"], "width": 2},
                        "xaxis": "x",
                        "yaxis": "y",
                    },
                    # Panel 2: Rolling correlation
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": rolling_corr,
                        "name": "Correlation",
                        "line": {"color": COLORS["correlation"], "width": 2.5},
                        "xaxis": "x2",
                        "yaxis": "y2",
                    },
                    # Mean line
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [corr_mean, corr_mean],
                        "name": "Mean",
                        "line": {"color": "#555", "width": 1.5, "dash": "solid"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                    # Risk-on threshold
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [risk_on_threshold, risk_on_threshold],
                        "name": f"+{high_z}σ",
                        "line": {"color": COLORS["risk_on"], "width": 1, "dash": "dash"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                    # Risk-off threshold
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [risk_off_threshold, risk_off_threshold],
                        "name": f"{low_z}σ",
                        "line": {"color": COLORS["risk_off"], "width": 1, "dash": "dash"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                ],
                "layout": {
                    "title": {"text": f"<b>{crypto_symbol} vs {equity_symbol} Regime</b>", "x": 0.5},
                    "height": 500,
                    "grid": {"rows": 2, "columns": 1, "pattern": "independent", "roworder": "top to bottom"},
                    "xaxis": {"domain": [0, 1], "showticklabels": False},
                    "yaxis": {"domain": [0.55, 1], "title": "Normalized (100)"},
                    "xaxis2": {"domain": [0, 1], "anchor": "y2"},
                    "yaxis2": {"domain": [0, 0.45], "title": "Correlation (ρ)", "range": [-0.5, 1]},
                    "legend": {"orientation": "h", "y": 1.12, "x": 0.5, "xanchor": "center"},
                    "margin": {"t": 60, "b": 40, "l": 60, "r": 40},
                    "template": "plotly_white",
                    "shapes": [
                        # Risk-on zone
                        {"type": "rect", "xref": "x2", "yref": "y2", "x0": dates[0], "x1": dates[-1], "y0": risk_on_threshold, "y1": 1, "fillcolor": "rgba(39, 174, 96, 0.15)", "line": {"width": 0}},
                        # Risk-off zone
                        {"type": "rect", "xref": "x2", "yref": "y2", "x0": dates[0], "x1": dates[-1], "y0": -0.5, "y1": risk_off_threshold, "fillcolor": "rgba(231, 76, 60, 0.15)", "line": {"width": 0}},
                    ],
                },
            },
            "type": "line",
            "label": f"{crypto_symbol}/{equity_symbol} Regime History",
        }
    except Exception as e:
        logger.warning(f"Failed to build regime history chart: {e}")
        return None


def build_regime_gauge_chart(
    regime: str,
    confidence: float,
    corr_z: float,
    current_corr: float,
) -> Optional[Dict[str, Any]]:
    """Build gauge showing current regime with confidence."""
    try:
        # Color based on regime
        if "RISK_ON" in regime:
            color = COLORS["risk_on"]
        elif "RISK_OFF" in regime:
            color = COLORS["risk_off"]
        else:
            color = COLORS["neutral"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "indicator",
                    "mode": "gauge+number",
                    "value": current_corr,
                    "number": {"valueformat": ".3f", "suffix": ""},
                    "gauge": {
                        "axis": {"range": [-0.5, 1], "tickformat": ".1f"},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [-0.5, 0], "color": "rgba(231, 76, 60, 0.2)"},
                            {"range": [0, 0.5], "color": "rgba(107, 114, 128, 0.2)"},
                            {"range": [0.5, 1], "color": "rgba(39, 174, 96, 0.2)"},
                        ],
                        "threshold": {
                            "line": {"color": "#333", "width": 2},
                            "thickness": 0.75,
                            "value": current_corr,
                        },
                    },
                    "title": {"text": f"{regime}<br><span style='font-size:12px'>z={corr_z:+.2f}σ | {confidence:.0%} conf</span>"},
                }],
                "layout": {
                    "height": 200,
                    "margin": {"t": 50, "r": 20, "b": 20, "l": 20},
                    "paper_bgcolor": "white",
                },
            },
            "type": "gauge",
            "label": "Regime Gauge",
        }
    except Exception as e:
        logger.warning(f"Failed to build regime gauge: {e}")
        return None


def build_correlation_heatmap(
    cross_correlations: Dict[str, Dict[str, float]],
) -> Optional[Dict[str, Any]]:
    """Build correlation heatmap for multiple assets."""
    try:
        if not cross_correlations:
            return None
        
        symbols = list(cross_correlations.keys())
        n = len(symbols)
        
        # Build matrix
        z = []
        for row_sym in symbols:
            row = []
            for col_sym in symbols:
                val = cross_correlations.get(row_sym, {}).get(col_sym, 0)
                row.append(val)
            z.append(row)
        
        # Format text
        text = [[f"{val:.2f}" for val in row] for row in z]
        
        return {
            "plotly": {
                "data": [{
                    "type": "heatmap",
                    "z": z,
                    "x": symbols,
                    "y": symbols,
                    "colorscale": "RdBu_r",
                    "zmin": -1,
                    "zmax": 1,
                    "text": text,
                    "texttemplate": "%{text}",
                    "colorbar": {"title": "ρ"},
                }],
                "layout": {
                    "title": {"text": "Cross-Asset Correlations", "font": {"size": 14}},
                    "height": 350,
                    "width": 400,
                    "margin": {"t": 50, "r": 80, "b": 50, "l": 80},
                    "template": "plotly_white",
                },
            },
            "type": "heatmap",
            "label": "Correlation Matrix",
        }
    except Exception as e:
        logger.warning(f"Failed to build correlation heatmap: {e}")
        return None
