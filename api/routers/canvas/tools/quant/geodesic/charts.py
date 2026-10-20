"""Geodesic Distance Chart Builders for Canvas.

Builds Plotly chart configurations for distribution comparison and distance breakdown.
"""

from typing import Dict, List, Any, Optional
import numpy as np
from scipy import stats


COLORS = {
    "portfolio_a": "#3b82f6",   # Blue
    "portfolio_b": "#f59e0b",   # Amber
    "fill_a": "rgba(59, 130, 246, 0.2)",
    "fill_b": "rgba(245, 158, 11, 0.2)",
    "mean": "#22c55e",          # Green
    "vol": "#ef4444",           # Red
    "tail": "#8b5cf6",          # Purple
}


def build_distribution_chart(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    name1: str = "Portfolio A",
    name2: str = "Portfolio B",
) -> Optional[Dict[str, Any]]:
    """Build overlay chart of two fitted distributions.
    
    Args:
        dist1, dist2: Distribution dicts with type, params, metrics
        name1, name2: Portfolio names
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not dist1 or not dist2:
        return None
    
    try:
        # Extract parameters
        params1 = dist1.get("params", {})
        params2 = dist2.get("params", {})
        
        if dist1.get("type") == "normal":
            mu1, sigma1 = params1.get("mu", 0), params1.get("sigma", 0.01)
            pdf1 = lambda x: stats.norm.pdf(x, mu1, sigma1)
        else:
            df1 = params1.get("df", 5)
            loc1, scale1 = params1.get("loc", 0), params1.get("scale", 0.01)
            pdf1 = lambda x: stats.t.pdf(x, df1, loc=loc1, scale=scale1)
        
        if dist2.get("type") == "normal":
            mu2, sigma2 = params2.get("mu", 0), params2.get("sigma", 0.01)
            pdf2 = lambda x: stats.norm.pdf(x, mu2, sigma2)
        else:
            df2 = params2.get("df", 5)
            loc2, scale2 = params2.get("loc", 0), params2.get("scale", 0.01)
            pdf2 = lambda x: stats.t.pdf(x, df2, loc=loc2, scale=scale2)
        
        # Generate x range
        sigma_max = max(
            params1.get("sigma", params1.get("scale", 0.01)),
            params2.get("sigma", params2.get("scale", 0.01))
        )
        mu_center = (
            params1.get("mu", params1.get("loc", 0)) +
            params2.get("mu", params2.get("loc", 0))
        ) / 2
        
        x = np.linspace(mu_center - 4 * sigma_max, mu_center + 4 * sigma_max, 200)
        y1 = [float(pdf1(xi)) for xi in x]
        y2 = [float(pdf2(xi)) for xi in x]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "scatter",
                        "x": (x * 100).tolist(),
                        "y": y1,
                        "mode": "lines",
                        "name": f"{name1} ({dist1.get('type', 'normal')})",
                        "line": {"color": COLORS["portfolio_a"], "width": 2},
                        "fill": "tozeroy",
                        "fillcolor": COLORS["fill_a"],
                    },
                    {
                        "type": "scatter",
                        "x": (x * 100).tolist(),
                        "y": y2,
                        "mode": "lines",
                        "name": f"{name2} ({dist2.get('type', 'normal')})",
                        "line": {"color": COLORS["portfolio_b"], "width": 2},
                        "fill": "tozeroy",
                        "fillcolor": COLORS["fill_b"],
                    },
                ],
                "layout": {
                    "title": {"text": "Return Distribution Comparison", "font": {"size": 14}},
                    "xaxis": {"title": "Daily Return (%)", "gridcolor": "#e5e7eb"},
                    "yaxis": {"title": "Probability Density", "gridcolor": "#e5e7eb"},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "legend": {"yanchor": "top", "y": 0.99, "xanchor": "right", "x": 0.99},
                    "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
                }
            },
            "type": "distribution",
            "label": "Distribution Comparison",
        }
    except Exception:
        return None


def build_breakdown_chart(
    breakdown: Dict[str, Any],
    distance: float,
) -> Optional[Dict[str, Any]]:
    """Build pie chart showing contribution of mean/vol/tail to distance.
    
    Args:
        breakdown: Dict with mean_contribution, vol_contribution, tail_contribution
        distance: Total Fisher-Rao distance
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not breakdown:
        return None
    
    try:
        labels = []
        values = []
        colors = []
        
        mean_val = breakdown.get("mean_contribution", 0)
        vol_val = breakdown.get("vol_contribution", 0)
        tail_val = breakdown.get("tail_contribution", 0)
        
        if mean_val > 0.01:
            labels.append("Mean Return")
            values.append(mean_val)
            colors.append(COLORS["mean"])
        
        if vol_val > 0.01:
            labels.append("Volatility")
            values.append(vol_val)
            colors.append(COLORS["vol"])
        
        if tail_val > 0.01:
            labels.append("Tail Behavior")
            values.append(tail_val)
            colors.append(COLORS["tail"])
        
        if not values:
            return None
        
        return {
            "plotly": {
                "data": [{
                    "type": "pie",
                    "labels": labels,
                    "values": values,
                    "marker": {"colors": colors},
                    "hole": 0.4,
                    "textinfo": "label+percent",
                    "textposition": "outside",
                }],
                "layout": {
                    "title": {
                        "text": f"What Drives the Difference?<br><span style='font-size:12px'>Distance: {distance:.3f}</span>",
                        "font": {"size": 14}
                    },
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "margin": {"t": 80, "r": 30, "b": 30, "l": 30},
                    "showlegend": False,
                }
            },
            "type": "breakdown",
            "label": "Distance Breakdown",
        }
    except Exception:
        return None


def build_geodesic_path_chart(
    geodesic_path: Dict[str, Any],
    name_a: str = "Portfolio A",
    name_b: str = "Portfolio B",
) -> Optional[Dict[str, Any]]:
    """Build 3D geodesic path visualization through portfolio manifold.
    
    Args:
        geodesic_path: Dict with path data from manifold computations
        name_a, name_b: Portfolio names
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not geodesic_path:
        return None
    
    try:
        # Handle both list (direct from compute_geodesic_path) and dict formats
        if isinstance(geodesic_path, list):
            path_points = geodesic_path
        elif isinstance(geodesic_path, dict):
            if "error" in geodesic_path:
                return None
            path_points = geodesic_path.get("path", [])
        else:
            return None
        
        if len(path_points) < 2:
            return None
        
        # Extract path coordinates (keys match manifold.py output)
        t_values = [p.get("t", i / (len(path_points) - 1)) for i, p in enumerate(path_points)]
        volatilities = [p.get("portfolio_volatility", 0) * 100 for p in path_points]
        returns = [p.get("portfolio_return", 0) * 100 for p in path_points]
        sharpes = [p.get("sharpe_ratio", 0) for p in path_points]
        curvatures = [p.get("local_curvature", 1.0) for p in path_points]
        
        # Create 3D scatter for path with curvature coloring
        path_data = []
        
        # Main path line - color by curvature (red=unstable, green=stable)
        path_data.append({
            "type": "scatter3d",
            "x": volatilities,
            "y": returns,
            "z": t_values,
            "mode": "lines+markers",
            "name": "Geodesic Path",
            "line": {"color": "#10b981", "width": 4},
            "marker": {
                "size": 6,
                "color": curvatures,
                "colorscale": "RdYlGn_r",
                "showscale": True,
                "colorbar": {"title": "Curvature", "x": 0.9},
            },
        })
        
        # Start and end points
        path_data.append({
            "type": "scatter3d",
            "x": [volatilities[0], volatilities[-1]],
            "y": [returns[0], returns[-1]],
            "z": [t_values[0], t_values[-1]],
            "mode": "markers+text",
            "name": "Endpoints",
            "marker": {"size": 12, "color": ["#3b82f6", "#f59e0b"]},
            "text": [name_a, name_b],
            "textposition": "top center",
            "showlegend": False,
        })
        
        return {
            "plotly": {
                "data": path_data,
                "layout": {
                    "title": {"text": "Geodesic Path Through Portfolio Manifold", "font": {"size": 14}},
                    "scene": {
                        "xaxis": {"title": "Volatility (%)"},
                        "yaxis": {"title": "Return (%)"},
                        "zaxis": {"title": "Path Progress (0→1)"},
                        "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.2}},
                    },
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "margin": {"t": 50, "r": 30, "b": 30, "l": 30},
                    "height": 500,
                }
            },
            "type": "geodesic_path",
            "label": "Geodesic Path",
        }
    except Exception:
        return None


def build_curvature_chart(
    curvature_map: Dict[str, Any],
    name: str = "Portfolio",
) -> Optional[Dict[str, Any]]:
    """Build curvature landscape 3D surface chart.
    
    Shows risk stability regions around the portfolio.
    Low curvature = stable, High curvature = unstable.
    """
    if not curvature_map or "error" in curvature_map:
        return None
    
    try:
        # Grid is a flat list from manifold.py, key is "grid" not "curvature_grid"
        flat_grid = curvature_map.get("grid", [])
        grid_size = curvature_map.get("grid_size", 10)
        
        if not flat_grid:
            return None
        
        # Reshape flat grid into 2D for surface plot
        z_data = []
        for i in range(grid_size):
            row = []
            for j in range(grid_size):
                idx = i * grid_size + j
                if idx < len(flat_grid):
                    row.append(flat_grid[idx].get("curvature", 0))
                else:
                    row.append(0)
            z_data.append(row)
        
        return {
            "plotly": {
                "data": [{
                    "type": "surface",
                    "z": z_data,
                    "colorscale": [
                        [0, "#16a34a"],    # Green = low curvature (stable)
                        [0.5, "#fbbf24"],  # Yellow = medium
                        [1, "#dc2626"],    # Red = high curvature (unstable)
                    ],
                    "colorbar": {"title": "Curvature", "tickformat": ".2f"},
                }],
                "layout": {
                    "title": {"text": f"Risk Stability Landscape around {name}", "font": {"size": 14}},
                    "scene": {
                        "xaxis": {"title": "Direction 1"},
                        "yaxis": {"title": "Direction 2"},
                        "zaxis": {"title": "Curvature (stability)"},
                        "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.0}},
                    },
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "margin": {"t": 50, "r": 30, "b": 30, "l": 30},
                    "height": 500,
                }
            },
            "type": "curvature",
            "label": "Curvature Landscape",
        }
    except Exception:
        return None


def build_single_distribution_chart(
    dist: Dict[str, Any],
    name: str = "Portfolio",
) -> Optional[Dict[str, Any]]:
    """Build chart for single portfolio distribution.
    
    Args:
        dist: Distribution dict with type, params, metrics
        name: Portfolio name
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not dist:
        return None
    
    try:
        params = dist.get("params", {})
        
        if dist.get("type") == "normal":
            mu, sigma = params.get("mu", 0), params.get("sigma", 0.01)
            pdf = lambda x: stats.norm.pdf(x, mu, sigma)
        else:
            df = params.get("df", 5)
            loc, scale = params.get("loc", 0), params.get("scale", 0.01)
            pdf = lambda x: stats.t.pdf(x, df, loc=loc, scale=scale)
        
        sigma_val = params.get("sigma", params.get("scale", 0.01))
        mu_val = params.get("mu", params.get("loc", 0))
        
        x = np.linspace(mu_val - 4 * sigma_val, mu_val + 4 * sigma_val, 200)
        y = [float(pdf(xi)) for xi in x]
        
        metrics = dist.get("metrics", {})
        ann_ret = metrics.get("annualized_return", 0) * 100
        ann_vol = metrics.get("annualized_volatility", 0) * 100
        
        return {
            "plotly": {
                "data": [{
                    "type": "scatter",
                    "x": (x * 100).tolist(),
                    "y": y,
                    "mode": "lines",
                    "name": name,
                    "line": {"color": COLORS["portfolio_a"], "width": 2},
                    "fill": "tozeroy",
                    "fillcolor": COLORS["fill_a"],
                }],
                "layout": {
                    "title": {
                        "text": f"{name} Return Distribution<br><span style='font-size:11px'>Ann. Return: {ann_ret:.1f}% | Ann. Vol: {ann_vol:.1f}%</span>",
                        "font": {"size": 14}
                    },
                    "xaxis": {"title": "Daily Return (%)", "gridcolor": "#e5e7eb"},
                    "yaxis": {"title": "Probability Density", "gridcolor": "#e5e7eb"},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "margin": {"t": 70, "r": 30, "b": 50, "l": 60},
                }
            },
            "type": "distribution",
            "label": "Return Distribution",
        }
    except Exception:
        return None


def build_manifold_embedding_chart(
    embedding_data: Dict[str, Any],
    title: str = "Portfolio Manifold Embedding"
) -> Optional[Dict[str, Any]]:
    """
    Visualize portfolios embedded on a 3D manifold preserving geodesic distances.
    
    Points close together = statistically similar risk profiles
    Points far apart = fundamentally different behavior
    
    Copied 1:1 from core agent tool.
    """
    if not embedding_data or "error" in embedding_data:
        return None
    
    portfolios = embedding_data.get("embedding", [])
    if not portfolios:
        return None
    
    try:
        # Extract coordinates and metrics (with safe defaults)
        x = [p.get("x", 0) for p in portfolios]
        y = [p.get("y", 0) for p in portfolios]
        z = [p.get("z", 0) for p in portfolios]
        names = [p.get("name", f"Portfolio {i}") for i, p in enumerate(portfolios)]
        vols = [p.get("volatility", 0.1) * 100 for p in portfolios]
        returns = [p.get("return", 0) * 100 for p in portfolios]
        sharpes = [p.get("sharpe", 0) for p in portfolios]
        kurtosis = [p.get("kurtosis", 0) for p in portfolios]
        
        # Size by volatility
        sizes = [max(6, min(12, v * 0.5)) for v in vols]
        
        traces = []
        
        # 1. CONNECTING LINES - opacity by distance
        distance_matrix = embedding_data.get("distance_matrix", [])
        if distance_matrix and len(portfolios) >= 2:
            flat_dists = [d for row in distance_matrix for d in row if d > 0]
            max_dist = max(flat_dists) if flat_dists else 1
            
            for i in range(len(portfolios)):
                for j in range(i + 1, len(portfolios)):
                    dist = distance_matrix[i][j] if distance_matrix else 0
                    opacity = max(0.1, 1 - (dist / max_dist) * 0.8)
                    width = max(1, 4 * (1 - dist / max_dist))
                    
                    traces.append({
                        "type": "scatter3d",
                        "x": [x[i], x[j]],
                        "y": [y[i], y[j]],
                        "z": [z[i], z[j]],
                        "mode": "lines",
                        "line": {"color": f"rgba(100, 150, 200, {opacity})", "width": width},
                        "showlegend": False,
                        "hoverinfo": "skip",
                    })
        
        # 2. FLOOR PROJECTION (shadow)
        z_floor = min(z) - 0.5
        traces.append({
            "type": "scatter3d",
            "x": x,
            "y": y,
            "z": [z_floor] * len(x),
            "mode": "markers",
            "marker": {"size": 4, "color": "rgba(150, 150, 150, 0.3)"},
            "showlegend": False,
            "hoverinfo": "skip",
        })
        
        # Vertical lines from floor to points
        for i in range(len(portfolios)):
            traces.append({
                "type": "scatter3d",
                "x": [x[i], x[i]],
                "y": [y[i], y[i]],
                "z": [z_floor, z[i]],
                "mode": "lines",
                "line": {"color": "rgba(150, 150, 150, 0.2)", "width": 1, "dash": "dot"},
                "showlegend": False,
                "hoverinfo": "skip",
            })
        
        # 3. MAIN SCATTER - portfolios colored by return
        traces.append({
            "type": "scatter3d",
            "x": x,
            "y": y,
            "z": z,
            "mode": "markers+text",
            "marker": {
                "size": sizes,
                "color": returns,
                "colorscale": [[0.0, "#ef4444"], [0.4, "#fbbf24"], [0.6, "#22c55e"], [1.0, "#059669"]],
                "colorbar": {"title": "Ann. Return (%)", "x": 1.02, "tickformat": ".1f"},
                "showscale": True,
                "line": {"color": "white", "width": 2},
                "opacity": 0.9,
            },
            "text": names,
            "textposition": "top center",
            "textfont": {"size": 11, "color": "#1e293b"},
            "customdata": list(zip(returns, vols, sharpes, kurtosis)),
            "hovertemplate": "<b>%{text}</b><br>Return: %{customdata[0]:.1f}%<br>Volatility: %{customdata[1]:.1f}%<br>Sharpe: %{customdata[2]:.2f}<extra></extra>",
        })
        
        # 4. HIGHLIGHT EXTREMES - best/worst Sharpe
        if len(sharpes) >= 2:
            best_idx = int(np.argmax(sharpes))
            worst_idx = int(np.argmin(sharpes))
            
            # Best Sharpe - gold ring
            traces.append({
                "type": "scatter3d",
                "x": [x[best_idx]],
                "y": [y[best_idx]],
                "z": [z[best_idx]],
                "mode": "markers",
                "marker": {"size": sizes[best_idx] + 4, "color": "rgba(0,0,0,0)", "line": {"color": "#fbbf24", "width": 3}},
                "showlegend": False,
                "hoverinfo": "skip",
            })
            
            # Worst Sharpe - red ring
            traces.append({
                "type": "scatter3d",
                "x": [x[worst_idx]],
                "y": [y[worst_idx]],
                "z": [z[worst_idx]],
                "mode": "markers",
                "marker": {"size": sizes[worst_idx] + 4, "color": "rgba(0,0,0,0)", "line": {"color": "#ef4444", "width": 3}},
                "showlegend": False,
                "hoverinfo": "skip",
            })
        
        stress = embedding_data.get("stress")
        stress_text = f" | MDS Stress: {stress:.3f}" if stress else ""
        
        return {
            "plotly": {
                "data": traces,
                "layout": {
                    "title": {
                        "text": f"{title}<br><span style='font-size:12px;color:gray'>3D distance = Geodesic distance | Lines = Similarity | Gold = Best Sharpe | Red = Worst{stress_text}</span>",
                        "font": {"size": 16},
                    },
                    "scene": {
                        "xaxis": {"title": "Manifold Dim 1", "showgrid": True, "gridcolor": "rgba(100,100,100,0.4)", "showbackground": True, "backgroundcolor": "rgba(240,240,240,0.5)"},
                        "yaxis": {"title": "Manifold Dim 2", "showgrid": True, "gridcolor": "rgba(100,100,100,0.4)", "showbackground": True, "backgroundcolor": "rgba(240,240,240,0.5)"},
                        "zaxis": {"title": "Manifold Dim 3", "showgrid": True, "gridcolor": "rgba(100,100,100,0.4)", "showbackground": True, "backgroundcolor": "rgba(240,240,240,0.5)"},
                        "camera": {"eye": {"x": 1.8, "y": 1.8, "z": 1.2}},
                        "aspectmode": "cube",
                    },
                    "showlegend": False,
                    "height": 700,
                    "margin": {"l": 20, "r": 100, "t": 100, "b": 20},
                }
            },
            "type": "manifold_embedding",
            "label": "Portfolio Manifold Map",
        }
    except Exception:
        return None
