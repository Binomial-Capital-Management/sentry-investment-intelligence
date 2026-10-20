"""
Chart generation for Portfolio Geodesic Distance tool.

ACTUAL PHYSICS VISUALIZATIONS:
1. Geodesic Path - The shortest path through portfolio manifold
2. Manifold Embedding - 2D projection preserving geodesic distances  
3. Curvature Landscape - 3D surface showing risk stability regions
4. Risk Trajectory - Animation of portfolio evolution along geodesic
5. Natural Gradient Field - Vector field of optimal optimization directions
"""

from typing import Dict, List, Optional, Any
import logging

import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


COLORS = {
    "portfolio_a": "#3b82f6",   # Blue
    "portfolio_b": "#f59e0b",   # Amber
    "geodesic": "#10b981",      # Emerald
    "euclidean": "#6b7280",     # Gray (for comparison)
    "fill_a": "rgba(59, 130, 246, 0.2)",
    "fill_b": "rgba(245, 158, 11, 0.2)",
    "mean": "#22c55e",          # Green
    "vol": "#ef4444",           # Red
    "tail": "#8b5cf6",          # Purple
    "curvature_high": "#dc2626",  # Red - unstable
    "curvature_low": "#16a34a",   # Green - stable
    "text": "#1e293b",
    "grid": "#e2e8f0",
    "background": "#ffffff",
}


def build_distribution_overlay(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    name1: str = "Portfolio A",
    name2: str = "Portfolio B",
    title: str = "Return Distribution Comparison"
) -> Dict[str, Any]:
    """
    Build overlay chart of two fitted distributions.
    
    Args:
        dist1, dist2: Output from fit_distribution()
        name1, name2: Portfolio names
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    # Extract parameters
    if dist1["type"] == "normal":
        mu1, sigma1 = dist1["params"]["mu"], dist1["params"]["sigma"]
        pdf1 = lambda x: stats.norm.pdf(x, mu1, sigma1)
    else:
        df1, loc1, scale1 = dist1["params"]["df"], dist1["params"]["loc"], dist1["params"]["scale"]
        pdf1 = lambda x: stats.t.pdf(x, df1, loc=loc1, scale=scale1)
    
    if dist2["type"] == "normal":
        mu2, sigma2 = dist2["params"]["mu"], dist2["params"]["sigma"]
        pdf2 = lambda x: stats.norm.pdf(x, mu2, sigma2)
    else:
        df2, loc2, scale2 = dist2["params"]["df"], dist2["params"]["loc"], dist2["params"]["scale"]
        pdf2 = lambda x: stats.t.pdf(x, df2, loc=loc2, scale=scale2)
    
    # Generate x range covering both distributions
    sigma_max = max(
        dist1["params"].get("sigma", dist1["params"].get("scale", 0.01)),
        dist2["params"].get("sigma", dist2["params"].get("scale", 0.01))
    )
    mu_center = (
        (dist1["params"].get("mu", dist1["params"].get("loc", 0)) +
         dist2["params"].get("mu", dist2["params"].get("loc", 0))) / 2
    )
    
    x = np.linspace(mu_center - 4 * sigma_max, mu_center + 4 * sigma_max, 200)
    y1 = [pdf1(xi) for xi in x]
    y2 = [pdf2(xi) for xi in x]
    
    fig = go.Figure()
    
    # Portfolio A
    fig.add_trace(go.Scatter(
        x=x * 100,  # Convert to percentage
        y=y1,
        mode="lines",
        name=f"{name1} ({dist1['type']})",
        line=dict(color=COLORS["portfolio_a"], width=2),
        fill="tozeroy",
        fillcolor=COLORS["fill_a"],
    ))
    
    # Portfolio B
    fig.add_trace(go.Scatter(
        x=x * 100,
        y=y2,
        mode="lines",
        name=f"{name2} ({dist2['type']})",
        line=dict(color=COLORS["portfolio_b"], width=2),
        fill="tozeroy",
        fillcolor=COLORS["fill_b"],
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis_title="Daily Return (%)",
        yaxis_title="Probability Density",
        template="plotly_white",
        height=400,
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        margin=dict(l=60, r=20, t=60, b=60),
    )
    
    return fig.to_dict()


def build_distance_breakdown_pie(
    breakdown: Dict[str, float],
    distance: float,
    title: str = "What Drives the Difference?"
) -> Dict[str, Any]:
    """
    Build pie chart showing contribution of mean/vol/tail to distance.
    
    Args:
        breakdown: Dict with mean_contribution, vol_contribution, tail_contribution
        distance: Total Fisher-Rao distance
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    labels = []
    values = []
    colors = []
    
    if breakdown.get("mean_contribution", 0) > 0.01:
        labels.append("Mean Return")
        values.append(breakdown["mean_contribution"])
        colors.append(COLORS["mean"])
    
    if breakdown.get("vol_contribution", 0) > 0.01:
        labels.append("Volatility")
        values.append(breakdown["vol_contribution"])
        colors.append(COLORS["vol"])
    
    if breakdown.get("tail_contribution", 0) > 0.01:
        labels.append("Tail Behavior")
        values.append(breakdown["tail_contribution"])
        colors.append(COLORS["tail"])
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textfont=dict(size=14),
        hovertemplate="%{label}: %{percent}<extra></extra>",
    )])
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:gray'>Fisher-Rao Distance: {distance:.3f}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=80, b=60),
    )
    
    return fig.to_dict()


def build_distance_heatmap(
    distance_matrix: np.ndarray,
    portfolio_names: List[str],
    title: str = "Portfolio Distance Matrix"
) -> Dict[str, Any]:
    """
    Build heatmap of pairwise distances for multi-portfolio comparison.
    
    Args:
        distance_matrix: NxN matrix of Fisher-Rao distances
        portfolio_names: Names of portfolios
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    fig = go.Figure(data=go.Heatmap(
        z=distance_matrix,
        x=portfolio_names,
        y=portfolio_names,
        colorscale="Blues",
        text=np.round(distance_matrix, 3),
        texttemplate="%{text}",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>Distance: %{z:.4f}<extra></extra>",
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=max(400, 100 + len(portfolio_names) * 40),
        width=max(500, 150 + len(portfolio_names) * 60),
        xaxis=dict(tickangle=45),
        margin=dict(l=100, r=20, t=60, b=100),
    )
    
    return fig.to_dict()


def build_regime_timeline(
    rolling_distances: List[float],
    dates: List[str],
    percentiles: List[float],
    threshold_percentile: float = 85,
    title: str = "Regime Distance Over Time"
) -> Dict[str, Any]:
    """
    Build timeline of rolling distance to baseline for regime detection.
    
    Args:
        rolling_distances: List of distances at each point
        dates: Date labels
        percentiles: Historical percentile at each point
        threshold_percentile: Percentile above which regime is "shifted"
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("Fisher-Rao Distance to Baseline", "Historical Percentile"),
        row_heights=[0.6, 0.4]
    )
    
    # Distance line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=rolling_distances,
            mode="lines",
            name="Distance",
            line=dict(color=COLORS["portfolio_a"], width=2),
        ),
        row=1, col=1
    )
    
    # Percentile with regime coloring
    colors = [
        COLORS["vol"] if p >= threshold_percentile else COLORS["mean"]
        for p in percentiles
    ]
    
    fig.add_trace(
        go.Bar(
            x=dates,
            y=percentiles,
            name="Percentile",
            marker_color=colors,
            opacity=0.7,
        ),
        row=2, col=1
    )
    
    # Add threshold line
    fig.add_hline(
        y=threshold_percentile,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Regime Shift Threshold ({threshold_percentile}%ile)",
        row=2, col=1
    )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=500,
        showlegend=False,
        margin=dict(l=60, r=20, t=80, b=40),
    )
    
    fig.update_yaxes(title_text="Distance", row=1, col=1)
    fig.update_yaxes(title_text="Percentile", range=[0, 100], row=2, col=1)
    
    return fig.to_dict()


def build_estimation_quality_chart(
    estimation_quality: Dict[str, Any],
    distribution: Dict[str, Any],
    name: str = "Portfolio",
    title: str = "Parameter Estimation Quality"
) -> Dict[str, Any]:
    """
    Build visualization of estimation quality and confidence intervals.
    
    Args:
        estimation_quality: Output from format_estimation_quality()
        distribution: Output from fit_distribution()
        name: Portfolio name
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    metrics = distribution["metrics"]
    
    # Prepare data
    params = ["Annual Return", "Annual Volatility"]
    values = [
        metrics["annualized_return"] * 100,
        metrics["annualized_volatility"] * 100
    ]
    errors = [
        estimation_quality["mean_std_error_annual"] * 100 * 1.96,  # 95% CI
        estimation_quality["vol_std_error_annual"] * 100 * 1.96
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=params,
        y=values,
        error_y=dict(
            type="data",
            array=errors,
            visible=True,
            color=COLORS["vol"],
            thickness=2,
            width=8,
        ),
        marker_color=COLORS["portfolio_a"],
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
    ))
    
    reliability = estimation_quality["reliability"]
    reliability_color = (
        COLORS["mean"] if reliability == "GOOD" else
        COLORS["portfolio_b"] if reliability == "MODERATE" else
        COLORS["vol"]
    )
    
    fig.update_layout(
        title=dict(
            text=f"{title}: {name}<br><span style='font-size:12px;color:{reliability_color}'>Reliability: {reliability}</span>",
            font=dict(size=16)
        ),
        yaxis_title="Value (%)",
        template="plotly_white",
        height=350,
        margin=dict(l=60, r=20, t=80, b=60),
        showlegend=False,
    )
    
    return fig.to_dict()


def generate_geodesic_charts(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    distances: Dict[str, Any],
    interpretation: Dict[str, Any],
    estimation1: Optional[Dict[str, Any]] = None,
    estimation2: Optional[Dict[str, Any]] = None,
    name1: str = "Portfolio A",
    name2: str = "Portfolio B"
) -> List[Dict[str, Any]]:
    """
    Generate all charts for pairwise geodesic distance analysis.
    
    Args:
        dist1, dist2: Fitted distributions
        distances: Output from compute_all_distances()
        interpretation: Output from interpret_distance()
        estimation1, estimation2: Estimation quality dicts
        name1, name2: Portfolio names
        
    Returns:
        List of chart dicts with plotly key for caching
    """
    charts = []
    
    # 1. Distribution overlay
    charts.append({
        "id": "distribution_overlay",
        "title": "Return Distribution Comparison",
        "plotly": build_distribution_overlay(dist1, dist2, name1, name2),
        "alt_text": f"Comparison of {name1} and {name2} return distributions"
    })
    
    # 2. Distance breakdown
    fr = distances["fisher_rao"]
    charts.append({
        "id": "distance_breakdown",
        "title": "Distance Contribution Breakdown",
        "plotly": build_distance_breakdown_pie(fr["breakdown"], fr["value"]),
        "alt_text": "Pie chart showing mean, volatility, and tail contributions to distance"
    })
    
    # 3. Estimation quality (if provided)
    if estimation1:
        charts.append({
            "id": "estimation_quality_a",
            "title": f"Estimation Quality: {name1}",
            "plotly": build_estimation_quality_chart(estimation1, dist1, name1),
            "alt_text": f"Parameter estimation confidence for {name1}"
        })
    
    if estimation2:
        charts.append({
            "id": "estimation_quality_b",
            "title": f"Estimation Quality: {name2}",
            "plotly": build_estimation_quality_chart(estimation2, dist2, name2),
            "alt_text": f"Parameter estimation confidence for {name2}"
        })
    
    return charts


def generate_cluster_charts(
    distance_matrix: np.ndarray,
    portfolio_names: List[str],
    cluster_assignments: Optional[Dict[str, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Generate charts for multi-portfolio cluster analysis.
    
    Args:
        distance_matrix: NxN pairwise distances
        portfolio_names: Portfolio names
        cluster_assignments: Optional cluster groupings
        
    Returns:
        List of chart dicts
    """
    charts = []
    
    # Distance heatmap
    charts.append({
        "id": "distance_heatmap",
        "title": "Portfolio Distance Matrix",
        "plotly": build_distance_heatmap(distance_matrix, portfolio_names),
        "alt_text": "Heatmap of pairwise Fisher-Rao distances between portfolios"
    })
    
    return charts


# =============================================================================
# ACTUAL PHYSICS CHARTS
# =============================================================================

def build_geodesic_path_chart(
    geodesic_path: List[Dict[str, Any]],
    name_start: str = "Portfolio A",
    name_end: str = "Portfolio B",
    title: str = "Geodesic Path Through Portfolio Manifold"
) -> Dict[str, Any]:
    """
    Visualize the geodesic (shortest) path between two portfolios.
    
    Simple 3D chart showing the path through risk-return space.
    """
    if not geodesic_path:
        return {"error": "No geodesic path data"}
    
    # Extract data
    returns = [p["portfolio_return"] * 100 for p in geodesic_path]
    vols = [p["portfolio_volatility"] * 100 for p in geodesic_path]
    sharpes = [p["sharpe_ratio"] for p in geodesic_path]
    curvatures = [p["local_curvature"] for p in geodesic_path]
    
    fig = go.Figure()
    
    # Main geodesic path
    fig.add_trace(go.Scatter3d(
        x=vols,
        y=returns,
        z=sharpes,
        mode="lines+markers",
        marker=dict(
            size=6,
            color=curvatures,
            colorscale="RdYlGn_r",  # Red = unstable
            colorbar=dict(title="Curvature", x=1.02),
            showscale=True,
        ),
        line=dict(color=COLORS["geodesic"], width=4),
        name="Geodesic Path",
        hovertemplate=(
            "Return: %{y:.1f}%<br>"
            "Volatility: %{x:.1f}%<br>"
            "Sharpe: %{z:.2f}"
            "<extra></extra>"
        ),
    ))
    
    # Start and end points
    fig.add_trace(go.Scatter3d(
        x=[vols[0], vols[-1]],
        y=[returns[0], returns[-1]],
        z=[sharpes[0], sharpes[-1]],
        mode="markers+text",
        marker=dict(size=12, color=[COLORS["portfolio_a"], COLORS["portfolio_b"]]),
        text=[name_start, name_end],
        textposition="top center",
        name="Endpoints",
        showlegend=False,
    ))
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:gray'>"
                 f"Path through risk-return-Sharpe space | Red = unstable regions</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=600,
        showlegend=False,
        margin=dict(l=20, r=80, t=80, b=40),
        scene=dict(
            xaxis_title="Volatility (%)",
            yaxis_title="Return (%)",
            zaxis_title="Sharpe Ratio",
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.8)),
        ),
    )
    
    return fig.to_dict()


def build_manifold_embedding_chart(
    embedding_data: Dict[str, Any],
    title: str = "Portfolio Manifold Embedding"
) -> Dict[str, Any]:
    """
    Visualize portfolios embedded on a 3D manifold preserving geodesic distances.
    
    This is NOT a simple scatter plot - the positions reflect the TRUE
    statistical distance between portfolios accounting for risk geometry.
    
    Points close together = statistically similar risk profiles
    Points far apart = fundamentally different behavior
    """
    if not embedding_data:
        return {"error": "No embedding data provided"}
    
    if "error" in embedding_data:
        return {"error": embedding_data["error"]}
    
    portfolios = embedding_data.get("embedding", [])
    if not portfolios:
        return {"error": "No embedding data"}
    
    # Extract coordinates and metrics (with safe defaults)
    try:
        x = [p.get("x", 0) for p in portfolios]
        y = [p.get("y", 0) for p in portfolios]
        z = [p.get("z", 0) for p in portfolios]
        names = [p.get("name", f"Portfolio {i}") for i, p in enumerate(portfolios)]
        vols = [p.get("volatility", 0.1) * 100 for p in portfolios]
        returns = [p.get("return", 0) * 100 for p in portfolios]
        sharpes = [p.get("sharpe", 0) for p in portfolios]
        kurtosis = [p.get("kurtosis", 0) for p in portfolios]
    except Exception as e:
        return {"error": f"Failed to extract embedding data: {e}"}
    
    # Size by volatility (smaller nodes)
    sizes = [max(6, min(12, v * 0.5)) for v in vols]
    
    fig = go.Figure()
    
    # =========================================================================
    # 1. ADD CONNECTING LINES (edges) between all pairs - opacity by distance
    # =========================================================================
    distance_matrix = embedding_data.get("distance_matrix", [])
    if distance_matrix and len(portfolios) >= 2:
        # Get max distance for normalization
        flat_dists = [d for row in distance_matrix for d in row if d > 0]
        max_dist = max(flat_dists) if flat_dists else 1
        
        for i in range(len(portfolios)):
            for j in range(i + 1, len(portfolios)):
                dist = distance_matrix[i][j] if distance_matrix else 0
                # Opacity inversely proportional to distance (closer = more visible)
                opacity = max(0.1, 1 - (dist / max_dist) * 0.8)
                # Line width also inversely proportional
                width = max(1, 4 * (1 - dist / max_dist))
                
                fig.add_trace(go.Scatter3d(
                    x=[x[i], x[j]],
                    y=[y[i], y[j]],
                    z=[z[i], z[j]],
                    mode="lines",
                    line=dict(
                        color=f"rgba(100, 150, 200, {opacity})",
                        width=width,
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                ))
    
    # =========================================================================
    # 2. ADD FLOOR PROJECTION (shadow) for spatial reference
    # =========================================================================
    z_floor = min(z) - 0.5  # Put floor below all points
    fig.add_trace(go.Scatter3d(
        x=x,
        y=y,
        z=[z_floor] * len(x),
        mode="markers",
        marker=dict(
            size=4,
            color="rgba(150, 150, 150, 0.3)",
            symbol="circle",
        ),
        showlegend=False,
        hoverinfo="skip",
        name="Floor Shadow",
    ))
    
    # Vertical lines from floor to points
    for i in range(len(portfolios)):
        fig.add_trace(go.Scatter3d(
            x=[x[i], x[i]],
            y=[y[i], y[i]],
            z=[z_floor, z[i]],
            mode="lines",
            line=dict(color="rgba(150, 150, 150, 0.2)", width=1, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        ))
    
    # =========================================================================
    # 3. MAIN SCATTER - portfolios as spheres with better colors
    # =========================================================================
    # Color by return (diverging: red=negative, green=positive)
    fig.add_trace(go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=returns,
            colorscale=[
                [0.0, "#ef4444"],    # Red for negative
                [0.4, "#fbbf24"],    # Yellow for low positive  
                [0.6, "#22c55e"],    # Green for medium
                [1.0, "#059669"],    # Deep green for high
            ],
            colorbar=dict(
                title="Ann. Return (%)",
                x=1.02,
                tickformat=".1f",
            ),
            showscale=True,
            line=dict(color="white", width=2),
            opacity=0.9,
        ),
        text=names,
        textposition="top center",
        textfont=dict(size=11, color="#1e293b"),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "─────────────<br>"
            "Return: %{customdata[0]:.1f}%<br>"
            "Volatility: %{customdata[1]:.1f}%<br>"
            "Sharpe: %{customdata[2]:.2f}<br>"
            "Kurtosis: %{customdata[3]:.2f}<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(returns, vols, sharpes, kurtosis)),
        name="Portfolios",
    ))
    
    # =========================================================================
    # 4. HIGHLIGHT EXTREMES - mark best/worst Sharpe
    # =========================================================================
    if len(sharpes) >= 2:
        best_idx = np.argmax(sharpes)
        worst_idx = np.argmin(sharpes)
        
        # Best Sharpe - gold ring
        fig.add_trace(go.Scatter3d(
            x=[x[best_idx]],
            y=[y[best_idx]],
            z=[z[best_idx]],
            mode="markers",
            marker=dict(
                size=sizes[best_idx] + 4,
                color="rgba(0,0,0,0)",
                line=dict(color="#fbbf24", width=3),
            ),
            showlegend=False,
            hoverinfo="skip",
        ))
        
        # Worst Sharpe - red ring
        fig.add_trace(go.Scatter3d(
            x=[x[worst_idx]],
            y=[y[worst_idx]],
            z=[z[worst_idx]],
            mode="markers",
            marker=dict(
                size=sizes[worst_idx] + 4,
                color="rgba(0,0,0,0)",
                line=dict(color="#ef4444", width=3),
            ),
            showlegend=False,
            hoverinfo="skip",
        ))
    
    # Annotations explaining the embedding
    stress = embedding_data.get("stress")
    stress_text = f" | MDS Stress: {stress:.3f}" if stress else ""
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:gray'>"
                 f"3D distance = Geodesic distance | Lines = Similarity | Gold ring = Best Sharpe | Red ring = Worst{stress_text}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=750,
        width=950,
        scene=dict(
            xaxis=dict(
                title=dict(text="Manifold Dim 1", font=dict(size=12, color="black")),
                showgrid=True,
                gridcolor="rgba(100,100,100,0.4)",
                showbackground=True,
                backgroundcolor="rgba(240,240,240,0.5)",
                showline=True,
                linecolor="black",
                linewidth=2,
                showticklabels=True,
                tickfont=dict(size=10, color="black"),
                zeroline=True,
                zerolinecolor="black",
                zerolinewidth=2,
            ),
            yaxis=dict(
                title=dict(text="Manifold Dim 2", font=dict(size=12, color="black")),
                showgrid=True,
                gridcolor="rgba(100,100,100,0.4)",
                showbackground=True,
                backgroundcolor="rgba(240,240,240,0.5)",
                showline=True,
                linecolor="black",
                linewidth=2,
                showticklabels=True,
                tickfont=dict(size=10, color="black"),
                zeroline=True,
                zerolinecolor="black",
                zerolinewidth=2,
            ),
            zaxis=dict(
                title=dict(text="Manifold Dim 3", font=dict(size=12, color="black")),
                showgrid=True,
                gridcolor="rgba(100,100,100,0.4)",
                showbackground=True,
                backgroundcolor="rgba(240,240,240,0.5)",
                showline=True,
                linecolor="black",
                linewidth=2,
                showticklabels=True,
                tickfont=dict(size=10, color="black"),
                zeroline=True,
                zerolinecolor="black",
                zerolinewidth=2,
            ),
            camera=dict(eye=dict(x=1.8, y=1.8, z=1.2)),
            aspectmode="cube",
        ),
        showlegend=False,
        margin=dict(l=20, r=100, t=100, b=20),
    )
    
    return fig.to_dict()


def build_curvature_landscape_chart(
    curvature_map: Dict[str, Any],
    title: str = "Portfolio Stability Landscape"
) -> Dict[str, Any]:
    """
    Simple 3D surface showing portfolio space curvature (stability).
    
    Green = Stable regions
    Red = Unstable regions
    """
    if "error" in curvature_map:
        return {"error": curvature_map["error"]}
    
    grid = curvature_map["grid"]
    base_curvature = curvature_map["base_curvature"]
    
    # Reshape grid data
    alphas = sorted(list(set(p["alpha"] for p in grid)))
    betas = sorted(list(set(p["beta"] for p in grid)))
    
    z_matrix = np.zeros((len(betas), len(alphas)))
    
    for p in grid:
        i = alphas.index(p["alpha"])
        j = betas.index(p["beta"])
        z_matrix[j, i] = np.log10(p["curvature"] + 1)
    
    fig = go.Figure()
    
    # 3D surface
    fig.add_trace(go.Surface(
        x=alphas,
        y=betas,
        z=z_matrix,
        colorscale="RdYlGn_r",
        colorbar=dict(title="Curvature", x=1.02),
        showscale=True,
        hovertemplate="Curvature: %{z:.2f}<extra></extra>",
    ))
    
    # Mark current portfolio position
    current_curv = np.log10(base_curvature["scalar_curvature"] + 1)
    fig.add_trace(go.Scatter3d(
        x=[0],
        y=[0],
        z=[current_curv],
        mode="markers",
        marker=dict(size=10, color="blue", symbol="diamond"),
        name="Current Position",
        hovertemplate=f"<b>Current</b><br>Stability: {base_curvature['stability']}<extra></extra>",
    ))
    
    stability = base_curvature["stability"]
    stability_color = "#16a34a" if stability == "STABLE" else "#f59e0b" if stability == "MODERATELY_UNSTABLE" else "#dc2626"
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:{stability_color}'>"
                 f"Current: {stability}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=500,
        showlegend=False,
        margin=dict(l=20, r=80, t=80, b=40),
        scene=dict(
            xaxis_title="Direction 1",
            yaxis_title="Direction 2",
            zaxis_title="Curvature",
            camera=dict(eye=dict(x=1.2, y=1.2, z=0.8)),
        ),
    )
    
    return fig.to_dict()


def build_natural_gradient_chart(
    natural_gradient: Dict[str, Any],
    asset_names: List[str],
    title: str = "Natural vs Standard Gradient"
) -> Dict[str, Any]:
    """
    Visualize the natural gradient for portfolio optimization.
    
    The natural gradient accounts for the curvature of portfolio space.
    When it differs significantly from the standard gradient, it means
    the geometry matters - use natural gradient for optimization.
    """
    if "error" in natural_gradient:
        return {"error": natural_gradient["error"]}
    
    standard = np.array(natural_gradient["standard_gradient"])
    natural = np.array(natural_gradient["natural_gradient"])
    angle = natural_gradient["angle_between_degrees"]
    
    # Normalize for comparison
    std_norm = standard / (np.linalg.norm(standard) + 1e-10)
    nat_norm = natural / (np.linalg.norm(natural) + 1e-10)
    
    n_assets = len(standard)
    if len(asset_names) < n_assets:
        asset_names = [f"Asset {i+1}" for i in range(n_assets)]
    
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "polar"}, {"type": "xy"}]],
        column_widths=[0.45, 0.55],
        subplot_titles=("Gradient Directions (Polar)", "Component Comparison"),
        horizontal_spacing=0.1
    )
    
    # Polar plot showing direction vectors
    # We project onto first 2 principal components for visualization
    if n_assets >= 2:
        # Use first 2 assets as axes for visualization
        fig.add_trace(
            go.Scatterpolar(
                r=[0, 1],
                theta=[0, np.degrees(np.arctan2(std_norm[1], std_norm[0]))],
                mode="lines+markers",
                marker=dict(size=[0, 12], color=COLORS["euclidean"]),
                line=dict(color=COLORS["euclidean"], width=3),
                name="Standard Gradient",
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatterpolar(
                r=[0, 1],
                theta=[0, np.degrees(np.arctan2(nat_norm[1], nat_norm[0]))],
                mode="lines+markers",
                marker=dict(size=[0, 12], color=COLORS["geodesic"]),
                line=dict(color=COLORS["geodesic"], width=3),
                name="Natural Gradient",
            ),
            row=1, col=1
        )
    
    # Bar chart comparing components
    x_positions = np.arange(n_assets)
    width = 0.35
    
    fig.add_trace(
        go.Bar(
            x=[asset_names[i] for i in range(n_assets)],
            y=std_norm,
            name="Standard",
            marker_color=COLORS["euclidean"],
            opacity=0.7,
            width=width,
            offset=-width/2,
        ),
        row=1, col=2
    )
    
    fig.add_trace(
        go.Bar(
            x=[asset_names[i] for i in range(n_assets)],
            y=nat_norm,
            name="Natural",
            marker_color=COLORS["geodesic"],
            opacity=0.7,
            width=width,
            offset=width/2,
        ),
        row=1, col=2
    )
    
    # Interpretation color
    matters = angle > 30
    angle_color = COLORS["vol"] if matters else COLORS["mean"]
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:12px;color:{angle_color}'>"
                 f"Angle Difference: {angle:.1f}° | "
                 f"{'GEOMETRY MATTERS - use natural gradient' if matters else 'Standard gradient is adequate'}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=450,
        width=900,
        showlegend=True,
        legend=dict(x=0.85, y=0.98),
        margin=dict(l=60, r=40, t=100, b=60),
        polar=dict(
            radialaxis=dict(visible=False),
            angularaxis=dict(direction="counterclockwise"),
        ),
    )
    
    fig.update_yaxes(title_text="Normalized Component", row=1, col=2)
    
    return fig.to_dict()


# =============================================================================
# MAIN CHART GENERATORS (WITH PHYSICS)
# =============================================================================

def generate_manifold_charts(
    geodesic_path: Optional[List[Dict]] = None,
    embedding_data: Optional[Dict] = None,
    curvature_map: Optional[Dict] = None,
    natural_gradient: Optional[Dict] = None,
    asset_names: Optional[List[str]] = None,
    name_start: str = "Portfolio A",
    name_end: str = "Portfolio B"
) -> List[Dict[str, Any]]:
    """
    Generate all physics-based manifold charts.
    
    These show ACTUAL geometry - not just statistics with fancy names.
    """
    charts = []
    
    # 1. Geodesic path visualization
    if geodesic_path:
        charts.append({
            "id": "geodesic_path",
            "title": "Geodesic Path Through Portfolio Manifold",
            "plotly": build_geodesic_path_chart(geodesic_path, name_start, name_end),
            "alt_text": "3D visualization of the shortest path through portfolio risk space"
        })
    
    # 2. Manifold embedding
    if embedding_data and "embedding" in embedding_data:
        charts.append({
            "id": "manifold_embedding",
            "title": "Portfolio Manifold Embedding",
            "plotly": build_manifold_embedding_chart(embedding_data),
            "alt_text": "2D map of portfolios preserving geodesic distances"
        })
    
    # 3. Curvature landscape
    if curvature_map and "grid" in curvature_map:
        charts.append({
            "id": "curvature_landscape",
            "title": "Curvature Landscape",
            "plotly": build_curvature_landscape_chart(curvature_map),
            "alt_text": "3D surface showing portfolio space stability regions"
        })
    
    # 4. Natural gradient
    if natural_gradient and "natural_gradient" in natural_gradient:
        charts.append({
            "id": "natural_gradient",
            "title": "Natural Gradient Analysis",
            "plotly": build_natural_gradient_chart(
                natural_gradient, 
                asset_names or []
            ),
            "alt_text": "Comparison of standard vs geometry-aware optimization direction"
        })
    
    return charts

