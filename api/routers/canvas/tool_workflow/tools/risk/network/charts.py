"""Chart builders for Portfolio Network Risk Canvas tool."""
from typing import Dict, List, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

COLORS = {
    "primary": "#1e3a5f",
    "secondary": "#64748b",
    "positive": "#059669",
    "negative": "#dc2626",
    "warning": "#f59e0b",
    "accent": "#3b82f6",
    "purple": "#8b5cf6",
    "grid": "#e2e8f0",
}


def build_network_chart(
    nodes: List[str],
    edges: List[tuple],
    communities: List[Dict],
    centrality: List[Dict],
    mst_edges: List[Dict],
) -> Optional[Dict[str, Any]]:
    """Build network visualization chart."""
    try:
        n = len(nodes)
        if n < 2:
            return None
        
        # Community color mapping
        community_colors = {}
        palette = [COLORS["accent"], COLORS["positive"], COLORS["warning"], 
                   COLORS["negative"], COLORS["purple"], "#ec4899", "#06b6d4"]
        for comm in communities:
            color = palette[comm.get("id", 0) % len(palette)]
            for stock in comm.get("stocks", []):
                community_colors[stock] = color
        
        # Centrality mapping
        centrality_map = {c["ticker"]: c.get("eigenvector_centrality", 0.5) for c in centrality}
        
        # Circular layout
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        positions = {node: (float(np.cos(angles[i])), float(np.sin(angles[i]))) for i, node in enumerate(nodes)}
        
        # MST edge set
        mst_set = set()
        for e in mst_edges:
            mst_set.add((e.get("source"), e.get("target")))
            mst_set.add((e.get("target"), e.get("source")))
        
        # Build edge traces
        edge_x, edge_y = [], []
        mst_edge_x, mst_edge_y = [], []
        
        for n1, n2, _ in edges:
            x0, y0 = positions.get(n1, (0, 0))
            x1, y1 = positions.get(n2, (0, 0))
            if (n1, n2) in mst_set:
                mst_edge_x.extend([x0, x1, None])
                mst_edge_y.extend([y0, y1, None])
            else:
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
        
        # Node data
        node_x = [positions[node][0] for node in nodes]
        node_y = [positions[node][1] for node in nodes]
        node_colors = [community_colors.get(node, COLORS["secondary"]) for node in nodes]
        node_sizes = [15 + 25 * centrality_map.get(node, 0.5) for node in nodes]
        
        data = []
        
        # Regular edges
        if edge_x:
            data.append({
                "type": "scatter",
                "x": edge_x,
                "y": edge_y,
                "mode": "lines",
                "line": {"width": 1, "color": "rgba(200,200,200,0.3)"},
                "hoverinfo": "skip",
                "showlegend": False,
            })
        
        # MST edges
        if mst_edge_x:
            data.append({
                "type": "scatter",
                "x": mst_edge_x,
                "y": mst_edge_y,
                "mode": "lines",
                "line": {"width": 2.5, "color": COLORS["primary"]},
                "hoverinfo": "skip",
                "showlegend": False,
                "name": "MST",
            })
        
        # Nodes
        data.append({
            "type": "scatter",
            "x": node_x,
            "y": node_y,
            "mode": "markers+text",
            "marker": {"size": node_sizes, "color": node_colors, "line": {"width": 2, "color": "white"}},
            "text": nodes,
            "textposition": "top center",
            "textfont": {"size": 10, "color": COLORS["primary"]},
            "hovertemplate": "<b>%{text}</b><extra></extra>",
            "showlegend": False,
        })
        
        return {
            "plotly": {
                "data": data,
                "layout": {
                    "title": {"text": "Portfolio Correlation Network", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "showlegend": False,
                    "hovermode": "closest",
                    "xaxis": {"showgrid": False, "zeroline": False, "showticklabels": False},
                    "yaxis": {"showgrid": False, "zeroline": False, "showticklabels": False},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "height": 450,
                    "margin": {"l": 40, "r": 40, "t": 50, "b": 40},
                },
            },
            "type": "network",
            "label": "Correlation Network",
        }
    except Exception as e:
        logger.error(f"Failed to build network chart: {e}")
        return None


def build_centrality_chart(
    centrality: List[Dict],
) -> Optional[Dict[str, Any]]:
    """Bar chart of centrality scores."""
    try:
        if not centrality:
            return None
        
        # Top 10
        top = centrality[:10]
        tickers = [c["ticker"] for c in top]
        eigen = [c.get("eigenvector_centrality", 0) for c in top]
        between = [c.get("betweenness_centrality", 0) for c in top]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "bar",
                        "name": "Eigenvector",
                        "x": tickers,
                        "y": eigen,
                        "marker": {"color": COLORS["accent"]},
                    },
                    {
                        "type": "bar",
                        "name": "Betweenness",
                        "x": tickers,
                        "y": between,
                        "marker": {"color": COLORS["purple"]},
                    },
                ],
                "layout": {
                    "title": {"text": "Centrality Scores", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "barmode": "group",
                    "xaxis": {"title": "", "tickangle": 45},
                    "yaxis": {"title": "Score", "gridcolor": COLORS["grid"]},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 350,
                    "margin": {"l": 50, "r": 30, "t": 50, "b": 80},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                },
            },
            "type": "centrality",
            "label": "Centrality Scores",
        }
    except Exception as e:
        logger.error(f"Failed to build centrality chart: {e}")
        return None


def build_community_chart(
    communities: List[Dict],
) -> Optional[Dict[str, Any]]:
    """Pie chart of community sizes."""
    try:
        if not communities:
            return None
        
        labels = [f"Cluster {c.get('id', i+1)}" for i, c in enumerate(communities)]
        sizes = [c.get("size", 1) for c in communities]
        correlations = [c.get("avg_internal_correlation", 0) for c in communities]
        
        # Color by internal correlation
        colors = []
        for corr in correlations:
            if corr > 0.7:
                colors.append(COLORS["negative"])
            elif corr > 0.5:
                colors.append(COLORS["warning"])
            else:
                colors.append(COLORS["positive"])
        
        hover = [f"{l}<br>Stocks: {s}<br>Avg Corr: {c:.0%}" 
                 for l, s, c in zip(labels, sizes, correlations)]
        
        return {
            "plotly": {
                "data": [{
                    "type": "pie",
                    "labels": labels,
                    "values": sizes,
                    "hole": 0.4,
                    "marker": {"colors": colors},
                    "hovertext": hover,
                    "hoverinfo": "text",
                    "textinfo": "label+percent",
                }],
                "layout": {
                    "title": {"text": "Community Structure", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "height": 300,
                    "margin": {"l": 30, "r": 30, "t": 50, "b": 30},
                    "paper_bgcolor": "white",
                    "showlegend": False,
                },
            },
            "type": "communities",
            "label": "Community Structure",
        }
    except Exception as e:
        logger.error(f"Failed to build community chart: {e}")
        return None


def build_risk_gauge(
    risk_level: str,
    composite_z: float,
    diversification_score: float,
) -> Optional[Dict[str, Any]]:
    """Gauge showing contagion risk level."""
    try:
        # Map to 0-10 scale
        gauge_value = min(10, max(0, composite_z * 2.5))
        
        if risk_level == "HIGH":
            bar_color = COLORS["negative"]
        elif risk_level == "MODERATE":
            bar_color = COLORS["warning"]
        else:
            bar_color = COLORS["positive"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "indicator",
                    "mode": "gauge+number+delta",
                    "value": gauge_value,
                    "title": {"text": "Contagion Risk", "font": {"size": 14, "color": COLORS["primary"]}},
                    "delta": {"reference": 5, "position": "bottom"},
                    "gauge": {
                        "axis": {"range": [0, 10], "tickwidth": 1},
                        "bar": {"color": bar_color},
                        "steps": [
                            {"range": [0, 3], "color": "#d1fae5"},
                            {"range": [3, 5], "color": "#fef3c7"},
                            {"range": [5, 7], "color": "#fed7aa"},
                            {"range": [7, 10], "color": "#fecaca"},
                        ],
                    },
                }],
                "layout": {
                    "height": 250,
                    "margin": {"l": 30, "r": 30, "t": 50, "b": 30},
                    "paper_bgcolor": "white",
                    "annotations": [{
                        "text": f"Diversification: {diversification_score}/10",
                        "x": 0.5, "y": -0.1,
                        "xref": "paper", "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 12, "color": COLORS["secondary"]},
                    }],
                },
            },
            "type": "risk_gauge",
            "label": "Contagion Risk Gauge",
        }
    except Exception as e:
        logger.error(f"Failed to build risk gauge: {e}")
        return None


def build_shock_propagation_chart(
    shock_result: Dict[str, Any],
    shocked_ticker: str,
    shock_magnitude: float,
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing shock propagation through portfolio."""
    try:
        if not shock_result:
            return None
        
        affected = shock_result.get("affected_positions", {})
        if not affected:
            return None
        
        # Build waterfall data
        # Start with direct impact, then show propagation to each position
        labels = [f"{shocked_ticker} (Direct)"]
        values = [float(shock_result.get("direct_portfolio_impact", "0").replace("%", ""))]
        
        # Add top affected positions (limit to 8 for readability)
        sorted_affected = sorted(
            affected.items(),
            key=lambda x: abs(x[1].get("estimated_impact_pct", 0)),
            reverse=True
        )[:8]
        
        for ticker, impact_data in sorted_affected:
            labels.append(ticker)
            values.append(impact_data.get("estimated_impact_pct", 0))
        
        # Add total
        labels.append("Total Impact")
        total_impact = float(shock_result.get("total_portfolio_impact", "0").replace("%", ""))
        
        # Determine colors: negative impacts are red, the origin is dark red
        colors = []
        for i, val in enumerate(values):
            if i == 0:
                colors.append("#991b1b")  # Dark red for shocked ticker
            elif val < 0:
                colors.append(COLORS["negative"])
            else:
                colors.append(COLORS["positive"])
        
        # Create waterfall
        data = [{
            "type": "waterfall",
            "orientation": "v",
            "x": labels[:-1],  # Exclude total for waterfall items
            "y": values,
            "connector": {"line": {"color": "rgb(63, 63, 63)", "width": 1}},
            "decreasing": {"marker": {"color": COLORS["negative"]}},
            "increasing": {"marker": {"color": COLORS["positive"]}},
            "totals": {"marker": {"color": COLORS["primary"]}},
            "textposition": "outside",
            "text": [f"{v:.2f}%" for v in values],
            "hovertemplate": "<b>%{x}</b><br>Impact: %{y:.2f}%<extra></extra>",
        }]
        
        cascade_mult = shock_result.get("cascade_multiplier", 1.0)
        positions_affected = shock_result.get("positions_impacted", 0)
        
        return {
            "plotly": {
                "data": data,
                "layout": {
                    "title": {
                        "text": f"Shock Propagation: {shocked_ticker} {shock_magnitude*100:.0f}% Drop",
                        "x": 0,
                        "font": {"size": 14, "color": COLORS["primary"]}
                    },
                    "xaxis": {"title": "", "tickangle": 45},
                    "yaxis": {"title": "Portfolio Impact (%)", "gridcolor": COLORS["grid"]},
                    "height": 400,
                    "margin": {"l": 60, "r": 40, "t": 80, "b": 100},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "annotations": [{
                        "text": f"Cascade Multiplier: {cascade_mult:.2f}x | Positions Affected: {positions_affected}",
                        "x": 0.5, "y": 1.08,
                        "xref": "paper", "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 11, "color": COLORS["secondary"]},
                    }],
                },
            },
            "type": "shock_propagation",
            "label": "Shock Propagation",
        }
    except Exception as e:
        logger.error(f"Failed to build shock propagation chart: {e}")
        return None
