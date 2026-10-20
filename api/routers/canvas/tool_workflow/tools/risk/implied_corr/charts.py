"""
Chart builders for Implied Correlation Canvas tool.
Reconstructs Plotly charts from raw data (not from agent chart handles).
"""

import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)


def build_weights_chart(
    constituent_data: List[Dict[str, Union[str, float]]],
    index_ticker: str
) -> Dict[str, Any]:
    """
    Build horizontal bar chart of constituent weights.
    
    Args:
        constituent_data: List of dicts with 'ticker', 'weight', 'iv' keys
        index_ticker: Index ticker for title
        
    Returns:
        Plotly JSON chart dict
    """
    try:
        # Sort by weight descending
        sorted_data = sorted(constituent_data, key=lambda x: x['weight'], reverse=True)
        
        tickers = [d['ticker'] for d in sorted_data]
        weights = [d['weight'] * 100 for d in sorted_data]  # Convert to %
        
        # Create horizontal bar chart
        chart = {
            "data": [
                {
                    "type": "bar",
                    "x": weights,
                    "y": tickers,
                    "orientation": "h",
                    "marker": {
                        "color": "#4F46E5",  # Indigo
                        "line": {"color": "#312E81", "width": 1}
                    },
                    "text": [f"{w:.2f}%" for w in weights],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{y}</b><br>Weight: %{x:.2f}%<extra></extra>"
                }
            ],
            "layout": {
                "title": {
                    "text": f"{index_ticker} Constituent Weights",
                    "x": 0.5,
                    "xanchor": "center"
                },
                "xaxis": {
                    "title": "Portfolio Weight (%)",
                    "gridcolor": "#E5E7EB"
                },
                "yaxis": {
                    "title": "",
                    "automargin": True
                },
                "plot_bgcolor": "#F9FAFB",
                "paper_bgcolor": "white",
                "font": {"family": "Inter, sans-serif", "size": 12},
                "margin": {"l": 80, "r": 40, "t": 60, "b": 50},
                "height": max(400, len(tickers) * 25)
            }
        }
        
        return chart
        
    except Exception as e:
        logger.error(f"Error building weights chart: {e}")
        return {}


def build_volatility_chart(
    index_ticker: str,
    index_iv: float,
    constituent_data: List[Dict[str, Union[str, float]]]
) -> Dict[str, Any]:
    """
    Build bar chart comparing constituent IVs with index IV line.
    
    Args:
        index_ticker: Index ticker
        index_iv: Index implied volatility (decimal, e.g., 0.18)
        constituent_data: List of dicts with 'ticker', 'weight', 'iv' keys
        
    Returns:
        Plotly JSON chart dict
    """
    try:
        # Sort by IV descending
        sorted_data = sorted(constituent_data, key=lambda x: x['iv'], reverse=True)
        
        tickers = [d['ticker'] for d in sorted_data]
        ivs = [d['iv'] * 100 for d in sorted_data]  # Convert to %
        index_iv_pct = index_iv * 100
        
        # Create bar chart with index IV line
        chart = {
            "data": [
                {
                    "type": "bar",
                    "x": tickers,
                    "y": ivs,
                    "name": "Constituent IV",
                    "marker": {
                        "color": "#10B981",  # Green
                        "line": {"color": "#059669", "width": 1}
                    },
                    "hovertemplate": "<b>%{x}</b><br>IV: %{y:.1f}%<extra></extra>"
                },
                {
                    "type": "scatter",
                    "x": tickers,
                    "y": [index_iv_pct] * len(tickers),
                    "mode": "lines",
                    "name": f"{index_ticker} Index IV",
                    "line": {
                        "color": "#EF4444",  # Red
                        "width": 3,
                        "dash": "dash"
                    },
                    "hovertemplate": f"<b>{index_ticker} IV</b><br>%{{y:.1f}}%<extra></extra>"
                }
            ],
            "layout": {
                "title": {
                    "text": f"IV Comparison: {index_ticker} vs Constituents",
                    "x": 0.5,
                    "xanchor": "center"
                },
                "xaxis": {
                    "title": "Ticker",
                    "tickangle": -45
                },
                "yaxis": {
                    "title": "Implied Volatility (%)",
                    "gridcolor": "#E5E7EB"
                },
                "plot_bgcolor": "#F9FAFB",
                "paper_bgcolor": "white",
                "font": {"family": "Inter, sans-serif", "size": 12},
                "margin": {"l": 60, "r": 40, "t": 60, "b": 100},
                "legend": {
                    "orientation": "h",
                    "yanchor": "bottom",
                    "y": -0.3,
                    "xanchor": "center",
                    "x": 0.5
                },
                "height": 500
            }
        }
        
        return chart
        
    except Exception as e:
        logger.error(f"Error building volatility chart: {e}")
        return {}


def build_breakdown_chart(calculation_details: Dict[str, float]) -> Dict[str, Any]:
    """
    Build waterfall chart showing GS formula calculation steps.
    
    Args:
        calculation_details: Dict from _calculate_gs_correlation with keys:
            - index_variance
            - weighted_var_sum
            - numerator
            - weighted_vol_sum
            - denominator
            - correlation_pct
            
    Returns:
        Plotly JSON chart dict
    """
    try:
        index_var = calculation_details.get('index_variance', 0)
        weighted_var_sum = calculation_details.get('weighted_var_sum', 0)
        numerator = calculation_details.get('numerator', 0)
        weighted_vol_sum = calculation_details.get('weighted_vol_sum', 0)
        denominator = calculation_details.get('denominator', 0)
        correlation_pct = calculation_details.get('correlation_pct', 0)
        
        # Waterfall-style bar chart
        # Steps: index_var → numerator → denominator → correlation
        labels = [
            "Index Variance",
            "Weighted Var Sum",
            "Numerator",
            "Weighted Vol² Sum",
            "Denominator",
            "Correlation %"
        ]
        
        values = [
            index_var,
            -weighted_var_sum,
            numerator,
            weighted_vol_sum ** 2,
            denominator,
            correlation_pct / 100  # Scale down for visibility
        ]
        
        colors = [
            "#3B82F6",  # Blue
            "#EF4444",  # Red
            "#10B981",  # Green
            "#3B82F6",  # Blue
            "#10B981",  # Green
            "#F59E0B"   # Amber
        ]
        
        chart = {
            "data": [
                {
                    "type": "bar",
                    "x": labels,
                    "y": values,
                    "marker": {"color": colors},
                    "text": [
                        f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
                        for v in values
                    ],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{x}</b><br>Value: %{y:.4f}<extra></extra>"
                }
            ],
            "layout": {
                "title": {
                    "text": "Implied Correlation Formula Breakdown",
                    "x": 0.5,
                    "xanchor": "center"
                },
                "xaxis": {
                    "title": "Calculation Step",
                    "tickangle": -30
                },
                "yaxis": {
                    "title": "Value",
                    "gridcolor": "#E5E7EB"
                },
                "plot_bgcolor": "#F9FAFB",
                "paper_bgcolor": "white",
                "font": {"family": "Inter, sans-serif", "size": 12},
                "margin": {"l": 60, "r": 40, "t": 80, "b": 100},
                "height": 500,
                "annotations": [
                    {
                        "text": (
                            "Formula: ρ = (σ²<sub>index</sub> - Σ(w<sub>i</sub>² σ<sub>i</sub>²)) / "
                            "(Σ(w<sub>i</sub> σ<sub>i</sub>)² - Σ(w<sub>i</sub>² σ<sub>i</sub>²))"
                        ),
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": -0.25,
                        "xanchor": "center",
                        "yanchor": "top",
                        "showarrow": False,
                        "font": {"size": 11, "color": "#6B7280"}
                    }
                ]
            }
        }
        
        return chart
        
    except Exception as e:
        logger.error(f"Error building breakdown chart: {e}")
        return {}
