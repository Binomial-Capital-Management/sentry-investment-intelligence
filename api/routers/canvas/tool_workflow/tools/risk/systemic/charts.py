"""
Systemic Risk Canvas Charts
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_risk_contribution_chart(
    risk_contributions: List[Dict[str, Any]],
    portfolio_score: float
) -> Optional[Dict[str, Any]]:
    """Build bar chart showing PageRank vs Betweenness per position."""
    if not risk_contributions:
        return None
    
    tickers = [c["ticker"] for c in risk_contributions]
    pageranks = [c["pagerank"] for c in risk_contributions]
    betweenness = [c["betweenness"] for c in risk_contributions]
    risk_contribs = [c["risk_contribution"] for c in risk_contributions]
    
    # Color by risk contribution
    colors = []
    for rc in risk_contribs:
        if rc > 0.3:
            colors.append('#ef4444')  # Red - high risk
        elif rc > 0.15:
            colors.append('#f97316')  # Orange - elevated
        else:
            colors.append('#22c55e')  # Green - acceptable
    
    data = [
        {
            "type": "bar",
            "name": "PageRank",
            "x": tickers,
            "y": pageranks,
            "marker": {"color": "#3b82f6", "opacity": 0.8},
            "hovertemplate": "<b>%{x}</b><br>PageRank: %{y:.3f}<extra></extra>"
        },
        {
            "type": "bar",
            "name": "Betweenness",
            "x": tickers,
            "y": betweenness,
            "marker": {"color": "#8b5cf6", "opacity": 0.8},
            "hovertemplate": "<b>%{x}</b><br>Betweenness: %{y:.3f}<extra></extra>"
        },
        {
            "type": "scatter",
            "name": "Risk Contribution",
            "x": tickers,
            "y": risk_contribs,
            "mode": "lines+markers",
            "line": {"color": "#ef4444", "width": 3},
            "marker": {"size": 10, "color": colors, "line": {"width": 2, "color": "white"}},
            "hovertemplate": "<b>%{x}</b><br>Risk Contribution: %{y:.1%}<extra></extra>"
        }
    ]
    
    layout = {
        "title": f"Systemic Risk Contributions (Portfolio Score: {portfolio_score}/10)",
        "barmode": "group",
        "xaxis": {"title": "Position", "tickangle": -45},
        "yaxis": {"title": "Score"},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        "template": "plotly_white",
        "height": 450,
        "margin": {"l": 60, "r": 40, "t": 80, "b": 80}
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "risk_contributions",
        "label": "Risk Contributions"
    }


def build_score_gauge(portfolio_score: float) -> Optional[Dict[str, Any]]:
    """Build gauge chart for portfolio systemic risk score."""
    # Determine color based on score
    if portfolio_score <= 3:
        color = "#22c55e"  # Green
    elif portfolio_score <= 5:
        color = "#eab308"  # Yellow
    elif portfolio_score <= 7:
        color = "#f97316"  # Orange
    else:
        color = "#ef4444"  # Red
    
    data = [{
        "type": "indicator",
        "mode": "gauge+number",
        "value": portfolio_score,
        "title": {"text": "Systemic Risk Score", "font": {"size": 16}},
        "gauge": {
            "axis": {"range": [0, 10], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 3], "color": "#dcfce7"},
                {"range": [3, 5], "color": "#fef9c3"},
                {"range": [5, 7], "color": "#fed7aa"},
                {"range": [7, 10], "color": "#fecaca"}
            ],
            "threshold": {
                "line": {"color": "#1f2937", "width": 4},
                "thickness": 0.75,
                "value": portfolio_score
            }
        }
    }]
    
    layout = {
        "template": "plotly_white",
        "height": 250,
        "margin": {"l": 30, "r": 30, "t": 50, "b": 30}
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "gauge",
        "label": "Risk Gauge"
    }


def build_network_density_chart(
    tickers: List[str],
    avg_correlation: float,
    network_density: float
) -> Optional[Dict[str, Any]]:
    """Build simple bar chart showing network metrics."""
    if not tickers:
        return None
    
    data = [{
        "type": "bar",
        "x": ["Avg Correlation", "Network Density"],
        "y": [avg_correlation, network_density],
        "marker": {
            "color": ["#3b82f6", "#8b5cf6"]
        },
        "text": [f"{avg_correlation:.2%}", f"{network_density:.2%}"],
        "textposition": "outside",
        "hovertemplate": "%{x}: %{y:.2%}<extra></extra>"
    }]
    
    layout = {
        "title": f"Network Metrics ({len(tickers)} positions)",
        "yaxis": {"title": "Value", "tickformat": ".0%", "range": [0, 1]},
        "template": "plotly_white",
        "height": 300,
        "showlegend": False
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "network_metrics",
        "label": "Network Metrics"
    }
















