"""
Charts for Instanton Rare Event Analyzer

Plotly visualizations for crash probability analysis:
- Crash severity PDF
- Instanton path cone
- Crash contribution waterfall
- Correlation heatmaps (normal vs crash)
- Probability sensitivity surface
"""

from typing import Dict, List, Any, Optional
import logging

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Color scheme - high contrast for dark backgrounds
COLORS = {
    "primary": "#60A5FA",       # Bright blue
    "secondary": "#34D399",     # Bright green
    "danger": "#F87171",        # Bright red
    "warning": "#FBBF24",       # Bright amber
    "neutral": "#9CA3AF",       # Light gray
    "background": "#111827",    # Dark background
    "surface": "#1F2937",       # Surface
    "text": "#F3F4F6",          # White text
    "grid": "rgba(75, 85, 99, 0.3)",  # Subtle gridlines
}

# Common layout settings for all charts
COMMON_LAYOUT = {
    "paper_bgcolor": COLORS["background"],
    "plot_bgcolor": COLORS["background"],
    "font": {"color": COLORS["text"], "size": 12},
    "title_font": {"color": COLORS["text"], "size": 16},
    "xaxis": {
        "gridcolor": COLORS["grid"],
        "linecolor": COLORS["neutral"],
        "tickcolor": COLORS["text"],
        "tickfont": {"color": COLORS["text"]},
        "title_font": {"color": COLORS["text"]},
    },
    "yaxis": {
        "gridcolor": COLORS["grid"],
        "linecolor": COLORS["neutral"],
        "tickcolor": COLORS["text"],
        "tickfont": {"color": COLORS["text"]},
        "title_font": {"color": COLORS["text"]},
    },
    "legend": {
        "font": {"color": COLORS["text"]},
        "bgcolor": "rgba(0,0,0,0)",
    },
}


def build_severity_pdf_chart(
    severity_distribution: Dict[str, Any],
    scenarios: Optional[List[Dict[str, Any]]] = None,
) -> go.Figure:
    """
    Build crash severity probability density chart.
    
    Shows the full distribution of crash outcomes with scenario markers.
    
    Args:
        severity_distribution: Output from compute_severity_distribution
        scenarios: Optional list of scenario results to mark
        
    Returns:
        Plotly Figure
    """
    crash_levels = severity_distribution["crash_levels"]
    cum_probs = severity_distribution["cumulative_probabilities"]
    pdf_levels = severity_distribution.get("pdf_levels", [])
    pdf_values = severity_distribution.get("pdf_values", [])
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Probability Density", "Cumulative Probability"),
        vertical_spacing=0.15,
        row_heights=[0.5, 0.5],
    )
    
    # PDF (top)
    if pdf_levels and pdf_values:
        fig.add_trace(
            go.Scatter(
                x=pdf_levels,
                y=pdf_values,
                mode="lines",
                fill="tozeroy",
                name="Probability Density",
                line=dict(color=COLORS["primary"], width=3),
                fillcolor="rgba(96, 165, 250, 0.25)",
            ),
            row=1, col=1
        )
    
    # CDF (bottom)
    fig.add_trace(
        go.Scatter(
            x=crash_levels,
            y=cum_probs,
            mode="lines",
            name="Cumulative Probability",
            line=dict(color=COLORS["secondary"], width=3),
        ),
        row=2, col=1
    )
    
    # Add scenario markers
    if scenarios:
        for scenario in scenarios:
            crash_pct = scenario["crash_pct"]
            prob = scenario.get("probability", 0)
            name = scenario.get("name", f"{crash_pct:.0f}%")
            
            # Vertical line on CDF
            fig.add_vline(
                x=crash_pct, row=2, col=1,
                line=dict(color=COLORS["danger"], dash="dash", width=1),
                annotation_text=f"{name}: {prob*100:.2f}%",
                annotation_position="top left",
            )
    
    # Add VaR markers
    stats = severity_distribution.get("statistics", {})
    if "var_95" in stats:
        fig.add_vline(
            x=stats["var_95"], row=2, col=1,
            line=dict(color=COLORS["warning"], dash="dot", width=1),
            annotation_text=f"VaR 95%: {stats['var_95']:.1f}%",
        )
    if "var_99" in stats:
        fig.add_vline(
            x=stats["var_99"], row=2, col=1,
            line=dict(color=COLORS["danger"], dash="dot", width=1),
            annotation_text=f"VaR 99%: {stats['var_99']:.1f}%",
        )
    
    fig.update_xaxes(title_text="Crash Level (%)", row=2, col=1, gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]))
    fig.update_yaxes(title_text="Density", row=1, col=1, gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]))
    fig.update_yaxes(title_text="Probability", row=2, col=1, gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]))
    fig.update_xaxes(row=1, col=1, gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]))
    
    fig.update_layout(
        title=dict(text="Crash Severity Distribution", font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        height=600,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color=COLORS["text"])),
    )
    
    # Fix subplot title colors
    for annotation in fig.layout.annotations:
        annotation.font.color = COLORS["text"]
    
    return fig


def build_instanton_path_chart(
    instanton_data: Dict[str, Any],
    current_price: float,
    crash_pct: float,
    horizon_days: int,
) -> go.Figure:
    """
    Build instanton path visualization with uncertainty cone.
    
    Shows the most likely crash path plus fluctuation bands.
    
    Args:
        instanton_data: Dict with times, prices, fluctuation_band
        current_price: Starting price
        crash_pct: Crash percentage
        horizon_days: Time horizon
        
    Returns:
        Plotly Figure
    """
    times = instanton_data["times"]
    prices = instanton_data["prices"]
    
    fig = go.Figure()
    
    # Fluctuation band (if available)
    if "fluctuation_band" in instanton_data:
        band = instanton_data["fluctuation_band"]
        upper = band.get("upper", prices)
        lower = band.get("lower", prices)
        
        # Upper band
        fig.add_trace(go.Scatter(
            x=times,
            y=upper,
            mode="lines",
            line=dict(width=1, color="rgba(96, 165, 250, 0.5)"),
            showlegend=False,
            hoverinfo="skip",
        ))
        
        # Lower band (fill to upper)
        fig.add_trace(go.Scatter(
            x=times,
            y=lower,
            mode="lines",
            line=dict(width=1, color="rgba(96, 165, 250, 0.5)"),
            fill="tonexty",
            fillcolor="rgba(96, 165, 250, 0.15)",
            name="±1σ Uncertainty",
        ))
        
        # Sample paths - more visible
        sample_paths = band.get("sample_paths", [])
        for i, path in enumerate(sample_paths[:5]):
            fig.add_trace(go.Scatter(
                x=times,
                y=path,
                mode="lines",
                line=dict(color=COLORS["neutral"], width=1),
                opacity=0.5,
                showlegend=i == 0,
                name="Sample Paths" if i == 0 else None,
            ))
    
    # Main instanton path - BOLD and visible
    fig.add_trace(go.Scatter(
        x=times,
        y=prices,
        mode="lines+markers",
        name="Instanton (Most Likely Path)",
        line=dict(color=COLORS["danger"], width=4),
        marker=dict(size=4, color=COLORS["danger"]),
    ))
    
    # Start point
    fig.add_trace(go.Scatter(
        x=[0],
        y=[current_price],
        mode="markers",
        name="Current Price",
        marker=dict(color=COLORS["secondary"], size=14, symbol="circle", line=dict(width=2, color="white")),
    ))
    
    # End point
    crash_price = current_price * (1 + crash_pct / 100)
    fig.add_trace(go.Scatter(
        x=[horizon_days],
        y=[crash_price],
        mode="markers",
        name=f"Crash Target ({crash_pct:.0f}%)",
        marker=dict(color=COLORS["danger"], size=14, symbol="x", line=dict(width=3, color=COLORS["danger"])),
    ))
    
    # Horizontal line at crash level
    fig.add_hline(
        y=crash_price,
        line=dict(color=COLORS["warning"], dash="dash", width=2),
        annotation_text=f"Crash Level: ${crash_price:.2f}",
        annotation_position="right",
        annotation_font=dict(color=COLORS["text"], size=12),
    )
    
    fig.update_layout(
        title=dict(text=f"Instanton Path: Most Likely Trajectory to {crash_pct:.0f}% Crash", font=dict(color=COLORS["text"], size=16)),
        xaxis_title="Days",
        yaxis_title="Price ($)",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        yaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color=COLORS["text"])),
    )
    
    return fig


def build_crash_contribution_chart(
    contributions: Dict[str, Any],
) -> go.Figure:
    """
    Build waterfall chart showing crash risk contribution by asset.
    
    Args:
        contributions: Output from compute_crash_contributions
        
    Returns:
        Plotly Figure
    """
    by_asset = contributions.get("by_asset", {})
    
    tickers = list(by_asset.keys())
    weights = [by_asset[t]["weight"] * 100 for t in tickers]
    contrib = [by_asset[t]["crash_contribution"] * 100 for t in tickers]
    
    # Sort by contribution
    sorted_idx = np.argsort(contrib)[::-1]
    tickers = [tickers[i] for i in sorted_idx]
    weights = [weights[i] for i in sorted_idx]
    contrib = [contrib[i] for i in sorted_idx]
    
    fig = go.Figure()
    
    # Weight bars
    fig.add_trace(go.Bar(
        x=tickers,
        y=weights,
        name="Portfolio Weight",
        marker_color=COLORS["primary"],
        opacity=0.8,
        marker_line=dict(width=1, color=COLORS["text"]),
    ))
    
    # Contribution bars
    fig.add_trace(go.Bar(
        x=tickers,
        y=contrib,
        name="Crash Risk Contribution",
        marker_color=COLORS["danger"],
        marker_line=dict(width=1, color=COLORS["text"]),
    ))
    
    fig.update_layout(
        title=dict(text="Crash Risk Contribution vs Portfolio Weight", font=dict(color=COLORS["text"], size=16)),
        xaxis_title="Asset",
        yaxis_title="Percentage (%)",
        barmode="group",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        yaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color=COLORS["text"])),
    )
    
    # Add annotation for dominant contributor
    interpretation = contributions.get("interpretation", "")
    if interpretation:
        fig.add_annotation(
            text=interpretation,
            xref="paper", yref="paper",
            x=0.5, y=-0.15,
            showarrow=False,
            font=dict(size=11, color=COLORS["text"]),
        )
    
    return fig


def build_correlation_heatmaps(
    correlation_analysis: Dict[str, Any],
) -> go.Figure:
    """
    Build side-by-side correlation heatmaps for normal vs crash regimes.
    
    Args:
        correlation_analysis: Output from estimate_crash_correlations
        
    Returns:
        Plotly Figure
    """
    normal_corr = np.array(correlation_analysis["normal_correlation"])
    crash_corr = np.array(correlation_analysis["crash_correlation"])
    tickers = correlation_analysis["tickers"]
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Normal Regime Correlations", "Crash Regime Correlations"),
        horizontal_spacing=0.1,
    )
    
    # Normal regime heatmap - dark text on heatmap cells
    fig.add_trace(
        go.Heatmap(
            z=normal_corr,
            x=tickers,
            y=tickers,
            colorscale="RdBu_r",
            zmin=-1, zmax=1,
            showscale=False,
            text=np.round(normal_corr, 2),
            texttemplate="%{text}",
            textfont=dict(size=10, color="#1F2937"),
        ),
        row=1, col=1
    )
    
    # Crash regime heatmap
    fig.add_trace(
        go.Heatmap(
            z=crash_corr,
            x=tickers,
            y=tickers,
            colorscale="RdBu_r",
            zmin=-1, zmax=1,
            colorbar=dict(title=dict(text="Correlation", font=dict(color=COLORS["text"])), tickfont=dict(color=COLORS["text"]), x=1.02),
            text=np.round(crash_corr, 2),
            texttemplate="%{text}",
            textfont=dict(size=10, color="#1F2937"),
        ),
        row=1, col=2
    )
    
    avg_normal = correlation_analysis["average_normal_correlation"]
    avg_crash = correlation_analysis["average_crash_correlation"]
    spike = correlation_analysis["correlation_spike"]
    
    fig.update_xaxes(tickfont=dict(color=COLORS["text"]))
    fig.update_yaxes(tickfont=dict(color=COLORS["text"]))
    
    fig.update_layout(
        title=dict(text=f"Correlation Regime Analysis (Spike: +{spike:.2f})", font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        height=450,
        annotations=[
            dict(
                text=f"Avg: {avg_normal:.2f}",
                xref="x domain", yref="y domain",
                x=0.5, y=-0.12,
                showarrow=False,
                font=dict(size=11, color=COLORS["text"]),
                xanchor="center",
            ),
            dict(
                text=f"Avg: {avg_crash:.2f}",
                xref="x2 domain", yref="y2 domain",
                x=0.5, y=-0.12,
                showarrow=False,
                font=dict(size=11, color=COLORS["text"]),
                xanchor="center",
            ),
        ]
    )
    
    # Fix subplot title colors
    for annotation in fig.layout.annotations:
        if annotation.text in ("Normal Regime Correlations", "Crash Regime Correlations"):
            annotation.font.color = COLORS["text"]
    
    return fig


def build_probability_comparison_chart(
    scenarios: List[Dict[str, Any]],
) -> go.Figure:
    """
    Build bar chart comparing crash probabilities across scenarios.
    
    Args:
        scenarios: List of scenario results
        
    Returns:
        Plotly Figure
    """
    names = [s["name"] for s in scenarios]
    probs = [s["probability"] * 100 for s in scenarios]
    gaussian = [s.get("gaussian_estimate", s["probability"]) * 100 for s in scenarios]
    
    fig = go.Figure()
    
    # Gaussian estimates
    fig.add_trace(go.Bar(
        x=names,
        y=gaussian,
        name="Gaussian Estimate",
        marker_color=COLORS["neutral"],
        opacity=0.7,
        marker_line=dict(width=1, color=COLORS["text"]),
    ))
    
    # Actual estimates (with fat tails)
    fig.add_trace(go.Bar(
        x=names,
        y=probs,
        name="Fat-Tail Estimate",
        marker_color=COLORS["danger"],
        marker_line=dict(width=1, color=COLORS["text"]),
    ))
    
    fig.update_layout(
        title=dict(text="Crash Probability by Scenario", font=dict(color=COLORS["text"], size=16)),
        xaxis_title="Scenario",
        yaxis_title="Probability (%)",
        barmode="group",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        yaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color=COLORS["text"])),
    )
    
    # Add tail multiplier annotations
    for i, s in enumerate(scenarios):
        mult = s.get("tail_multiplier", 1.0)
        if mult > 1.1:
            fig.add_annotation(
                x=names[i],
                y=probs[i],
                text=f"{mult:.1f}x",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor=COLORS["warning"],
                ax=0, ay=-30,
                font=dict(size=11, color=COLORS["warning"]),
            )
    
    return fig


def build_action_surface_chart(
    S0: float,
    sigma: float,
    mu: float = 0.0,
    horizon_range: tuple = (5, 60),
    crash_range: tuple = (-40, -5),
) -> go.Figure:
    """
    Build heatmap of action (crash probability) vs horizon and severity.
    
    Args:
        S0: Starting price
        sigma: Daily volatility
        mu: Daily drift
        horizon_range: Range of horizons (min_days, max_days)
        crash_range: Range of crash percentages (min_pct, max_pct)
        
    Returns:
        Plotly Figure
    """
    horizons = np.linspace(horizon_range[0], horizon_range[1], 20).astype(int)
    crashes = np.linspace(crash_range[0], crash_range[1], 20)
    
    # Compute action for each combination
    action_matrix = np.zeros((len(crashes), len(horizons)))
    
    for i, crash_pct in enumerate(crashes):
        for j, horizon in enumerate(horizons):
            log_return = np.log(1 + crash_pct / 100)
            daily_return = log_return / horizon
            
            # Action for constant daily return
            deviation = daily_return - mu
            action = horizon * deviation**2 / (2 * sigma**2)
            action_matrix[i, j] = action
    
    # Convert action to probability (clamped for visualization)
    prob_matrix = np.exp(-action_matrix)
    prob_matrix = np.clip(prob_matrix, 1e-10, 1)
    
    fig = go.Figure(data=go.Heatmap(
        z=np.log10(prob_matrix),  # Log scale for visibility
        x=horizons,
        y=crashes,
        colorscale="RdYlGn_r",
        colorbar=dict(
            title=dict(text="log₁₀(Probability)", font=dict(color=COLORS["text"])),
            tickvals=[-6, -4, -2, 0],
            ticktext=["0.0001%", "0.01%", "1%", "100%"],
            tickfont=dict(color=COLORS["text"]),
        ),
        hovertemplate="Horizon: %{x} days<br>Crash: %{y:.0f}%<br>Prob: %{customdata:.2e}<extra></extra>",
        customdata=prob_matrix,
    ))
    
    fig.update_layout(
        title=dict(text="Crash Probability Surface (Action Landscape)", font=dict(color=COLORS["text"], size=16)),
        xaxis_title="Horizon (Days)",
        yaxis_title="Crash Level (%)",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        yaxis=dict(gridcolor=COLORS["grid"], tickfont=dict(color=COLORS["text"]), title_font=dict(color=COLORS["text"])),
        height=500,
    )
    
    return fig


def generate_all_charts(
    instanton_data: Dict[str, Any],
    severity_distribution: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    portfolio_decomposition: Optional[Dict[str, Any]],
    current_price: float,
    crash_pct: float,
    horizon_days: int,
    sigma: float,
) -> List[Dict[str, Any]]:
    """
    Generate all charts for instanton analysis.
    
    Args:
        instanton_data: Instanton path data
        severity_distribution: Severity distribution data
        scenarios: Scenario results
        portfolio_decomposition: Portfolio analysis (None for single asset)
        current_price: Current price/value
        crash_pct: Primary crash percentage
        horizon_days: Time horizon
        sigma: Daily volatility
        
    Returns:
        List of chart dicts with id, title, plotly figure
    """
    charts = []
    
    # 1. Severity PDF
    try:
        severity_fig = build_severity_pdf_chart(severity_distribution, scenarios)
        charts.append({
            "id": "severity_distribution",
            "title": "Crash Severity Distribution",
            "plotly": severity_fig.to_dict(),
            "alt_text": "Probability distribution over crash severity levels",
        })
    except Exception as e:
        logger.warning(f"Failed to build severity chart: {e}")
    
    # 2. Instanton path
    try:
        path_fig = build_instanton_path_chart(
            instanton_data, current_price, crash_pct, horizon_days
        )
        charts.append({
            "id": "instanton_path",
            "title": "Most Likely Crash Path (Instanton)",
            "plotly": path_fig.to_dict(),
            "alt_text": "The most likely price trajectory to the crash target",
        })
    except Exception as e:
        logger.warning(f"Failed to build path chart: {e}")
    
    # 3. Probability comparison
    if scenarios:
        try:
            prob_fig = build_probability_comparison_chart(scenarios)
            charts.append({
                "id": "probability_comparison",
                "title": "Crash Probability by Scenario",
                "plotly": prob_fig.to_dict(),
                "alt_text": "Comparison of crash probabilities across scenarios",
            })
        except Exception as e:
            logger.warning(f"Failed to build probability chart: {e}")
    
    # 4. Action surface
    try:
        surface_fig = build_action_surface_chart(
            current_price, sigma, horizon_range=(5, max(60, horizon_days*2))
        )
        charts.append({
            "id": "action_surface",
            "title": "Crash Probability Landscape",
            "plotly": surface_fig.to_dict(),
            "alt_text": "Heatmap of crash probability vs horizon and severity",
        })
    except Exception as e:
        logger.warning(f"Failed to build surface chart: {e}")
    
    # Portfolio-specific charts
    if portfolio_decomposition:
        # 5. Crash contributions
        contributions = portfolio_decomposition.get("crash_contributions")
        if contributions:
            try:
                contrib_fig = build_crash_contribution_chart(contributions)
                charts.append({
                    "id": "crash_contributions",
                    "title": "Crash Risk Contribution by Asset",
                    "plotly": contrib_fig.to_dict(),
                    "alt_text": "Which assets drive portfolio crash risk",
                })
            except Exception as e:
                logger.warning(f"Failed to build contribution chart: {e}")
        
        # 6. Correlation heatmaps
        corr_analysis = portfolio_decomposition.get("correlation_analysis")
        if corr_analysis:
            try:
                corr_fig = build_correlation_heatmaps(corr_analysis)
                charts.append({
                    "id": "correlation_regimes",
                    "title": "Normal vs Crash Correlations",
                    "plotly": corr_fig.to_dict(),
                    "alt_text": "Correlation matrices for normal and crash regimes",
                })
            except Exception as e:
                logger.warning(f"Failed to build correlation chart: {e}")
    
    return charts


















