"""
Chart generation for Herding Regime Detector.

Creates visualizations:
1. Herding Index Gauge - Current risk level
2. Correlation Heatmap - Sector relationships
3. Statistics Timeseries - Historical Ising statistics
4. Regime Bar - Current state probabilities
"""

from typing import Dict, List, Optional, Any
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


# =============================================================================
# COLOR DEFINITIONS
# =============================================================================

COLORS = {
    "dispersed": "#22c55e",   # Green
    "normal": "#3b82f6",      # Blue
    "critical": "#ef4444",    # Red
    "elevated": "#f59e0b",    # Amber
    "background": "#f8fafc",  # Light gray
    "text": "#1e293b",        # Dark gray
    "grid": "#e2e8f0",        # Light gray
}

GAUGE_COLORS = [
    "#22c55e",  # 0-20: Green (dispersed)
    "#84cc16",  # 20-40: Lime (normal-low)
    "#f59e0b",  # 40-60: Amber (elevated)
    "#f97316",  # 60-80: Orange (pre-critical)
    "#ef4444",  # 80-100: Red (critical)
]


# =============================================================================
# HERDING INDEX GAUGE
# =============================================================================

def build_herding_gauge(
    herding_index: Dict[str, Any],
    title: str = "Herding Index"
) -> Dict[str, Any]:
    """
    Build a gauge chart for the herding index.
    
    Args:
        herding_index: Output from compute_composite_herding_index
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    value = herding_index.get("value", 0.5) * 100  # Convert to 0-100 scale
    regime = herding_index.get("regime", "NORMAL")
    risk_level = herding_index.get("risk_level", "MODERATE")
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": f"{title}<br><span style='font-size:0.7em;color:gray'>{regime} - {risk_level} Risk</span>"},
        number={"suffix": "%", "font": {"size": 36}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": COLORS["text"]},
            "bar": {"color": COLORS["text"]},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": COLORS["grid"],
            "steps": [
                {"range": [0, 20], "color": GAUGE_COLORS[0]},
                {"range": [20, 40], "color": GAUGE_COLORS[1]},
                {"range": [40, 60], "color": GAUGE_COLORS[2]},
                {"range": [60, 80], "color": GAUGE_COLORS[3]},
                {"range": [80, 100], "color": GAUGE_COLORS[4]},
            ],
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.75,
                "value": value
            }
        }
    ))
    
    fig.update_layout(
        template="plotly_white",
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
    )
    
    return fig.to_dict()


# =============================================================================
# CORRELATION HEATMAP
# =============================================================================

def build_correlation_heatmap(
    correlation_matrix: Dict[str, Dict[str, float]],
    title: str = "Sector Correlation Matrix"
) -> Dict[str, Any]:
    """
    Build a heatmap of sector correlations.
    
    Args:
        correlation_matrix: Dict-of-dicts correlation matrix
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    # Convert to DataFrame
    df = pd.DataFrame(correlation_matrix)
    
    # Sort sectors alphabetically for consistency
    sectors = sorted(df.columns)
    df = df.loc[sectors, sectors]
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=df.columns.tolist(),
        y=df.index.tolist(),
        colorscale="RdBu_r",
        zmid=0,
        zmin=-1,
        zmax=1,
        text=np.round(df.values, 2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=500,
        width=600,
        margin=dict(l=100, r=20, t=60, b=100),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
        xaxis=dict(tickangle=45),
    )
    
    return fig.to_dict()


# =============================================================================
# STATISTICS TIMESERIES
# =============================================================================

def build_statistics_timeseries(
    ising_stats: Dict[str, Any],
    title: str = "Ising Statistics (Percentiles)"
) -> Dict[str, Any]:
    """
    Build a single-panel timeseries of Ising statistics as percentiles.
    
    All metrics are shown as percentiles (0-100) for easy comparison.
    
    Args:
        ising_stats: Output from compute_all_ising_statistics
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    from scipy import stats as scipy_stats
    
    ising = ising_stats.get("ising_statistics", {})
    
    # Extract raw histories
    sus_hist = ising.get("susceptibility", {}).get("history", [])
    corr_hist = ising.get("correlation_length", {}).get("history", [])
    ar1_hist = ising.get("critical_slowing_down", {}).get("history", [])
    mag_hist = ising.get("magnetization", {}).get("history", [])
    
    # Convert to percentiles for comparability
    def to_percentiles(values):
        if not values or len(values) < 2:
            return []
        return [scipy_stats.percentileofscore(values, v) for v in values]
    
    sus_pct = to_percentiles(sus_hist)
    corr_pct = to_percentiles(corr_hist)
    ar1_pct = to_percentiles(ar1_hist)
    mag_pct = to_percentiles([abs(v) for v in mag_hist])  # Use absolute magnetization
    
    fig = go.Figure()
    
    # Plot each metric
    metrics = [
        ("Susceptibility", sus_pct, "#f59e0b"),
        ("Correlation", corr_pct, "#22c55e"),
        ("Momentum (AR1)", ar1_pct, "#ef4444"),
        ("|Magnetization|", mag_pct, "#3b82f6"),
    ]
    
    for name, data, color in metrics:
        if data:
            x = list(range(len(data)))
            fig.add_trace(go.Scatter(
                x=x, y=data,
                mode="lines",
                name=name,
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{name}</b><br>Day %{{x}}: %{{y:.0f}}%ile<extra></extra>"
            ))
    
    # Add threshold zones
    fig.add_hrect(y0=80, y1=100, fillcolor=COLORS["critical"], opacity=0.1,
                  line_width=0, annotation_text="Elevated", annotation_position="top right")
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=350,
        margin=dict(l=50, r=20, t=60, b=50),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        xaxis=dict(title="Trading Days"),
        yaxis=dict(title="Percentile", range=[0, 105]),
    )
    
    return fig.to_dict()


# =============================================================================
# REGIME PROBABILITY BAR
# =============================================================================

def build_regime_bar(
    hmm_regime: Dict[str, Any],
    title: str = "Regime Probabilities"
) -> Dict[str, Any]:
    """
    Build a horizontal bar chart of regime probabilities.
    
    Args:
        hmm_regime: Output from detect_hmm_regime
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    probs = hmm_regime.get("state_probabilities", {})
    current_state = hmm_regime.get("current_state", "unknown")
    
    # Define order and colors
    states = ["dispersed", "normal", "critical"]
    state_colors = [COLORS["dispersed"], COLORS["normal"], COLORS["critical"]]
    
    # Get probabilities in order
    prob_values = [probs.get(s, 0) * 100 for s in states]
    
    # Create bar chart
    fig = go.Figure()
    
    for i, (state, prob, color) in enumerate(zip(states, prob_values, state_colors)):
        # Highlight current state
        border_width = 3 if state == current_state else 0
        border_color = "black" if state == current_state else None
        
        fig.add_trace(go.Bar(
            y=[state.title()],
            x=[prob],
            orientation="h",
            name=state.title(),
            marker=dict(
                color=color,
                line=dict(width=border_width, color=border_color)
            ),
            text=f"{prob:.1f}%",
            textposition="inside",
            textfont=dict(color="white", size=14),
            hovertemplate=f"<b>{state.title()}</b><br>Probability: {prob:.1f}%<extra></extra>",
        ))
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:0.8em;color:gray'>Current: {current_state.title()}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=200,
        showlegend=False,
        barmode="group",
        margin=dict(l=100, r=20, t=70, b=20),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
        xaxis=dict(title="Probability (%)", range=[0, 100]),
    )
    
    return fig.to_dict()


# =============================================================================
# SIGNAL DASHBOARD
# =============================================================================

def build_signal_dashboard(
    ising_stats: Dict[str, Any],
    title: str = "Early Warning Signals"
) -> Dict[str, Any]:
    """
    Build a dashboard showing all 4 signal statuses.
    
    Args:
        ising_stats: Output from compute_all_ising_statistics
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    stats = ising_stats.get("ising_statistics", {})
    
    # Extract signal info
    signals = [
        {
            "name": "Magnetization",
            "percentile": stats.get("magnetization", {}).get("percentile", 0.5),
            "signal": stats.get("magnetization", {}).get("signal", "NORMAL"),
            "raw": stats.get("magnetization", {}).get("raw", 0),
        },
        {
            "name": "Susceptibility",
            "percentile": stats.get("susceptibility", {}).get("percentile", 0.5),
            "signal": stats.get("susceptibility", {}).get("signal", "NORMAL"),
            "raw": stats.get("susceptibility", {}).get("raw", 0),
        },
        {
            "name": "Correlation Length",
            "percentile": stats.get("correlation_length", {}).get("percentile", 0.5),
            "signal": stats.get("correlation_length", {}).get("signal", "NORMAL"),
            "raw": stats.get("correlation_length", {}).get("raw", 0),
        },
        {
            "name": "Critical Slowing",
            "percentile": stats.get("critical_slowing_down", {}).get("percentile", 0.5),
            "signal": stats.get("critical_slowing_down", {}).get("signal", "NORMAL"),
            "raw": stats.get("critical_slowing_down", {}).get("raw", 0),
        },
    ]
    
    # Create gauge-like indicators
    fig = make_subplots(
        rows=1, cols=4,
        specs=[[{"type": "indicator"}] * 4],
        subplot_titles=[s["name"] for s in signals]
    )
    
    for i, sig in enumerate(signals):
        pct = sig["percentile"] * 100
        
        # Determine color based on signal
        if sig["signal"] == "CRITICAL":
            color = COLORS["critical"]
        elif sig["signal"] == "ELEVATED":
            color = COLORS["elevated"]
        else:
            color = COLORS["dispersed"]
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=pct,
                number={"suffix": "%ile", "font": {"size": 20}},
                gauge={
                    "axis": {"range": [0, 100], "visible": False},
                    "bar": {"color": color, "thickness": 0.8},
                    "bgcolor": COLORS["grid"],
                    "borderwidth": 0,
                },
            ),
            row=1, col=i+1
        )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=250,
        margin=dict(l=20, r=20, t=80, b=20),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
    )
    
    return fig.to_dict()


# =============================================================================
# ISING PARAMETERS DASHBOARD (T, h, J)
# =============================================================================

def build_ising_parameters_chart(
    ising_params: Dict[str, Any],
    title: str = "Ising Model Parameters"
) -> Dict[str, Any]:
    """
    Build a dashboard showing Temperature (T), External Field (h), and Coupling (J).
    
    Args:
        ising_params: Dict with temperature, external_field, coupling
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    # Create 3-panel indicator chart
    fig = make_subplots(
        rows=1, cols=3,
        specs=[[{"type": "indicator"}] * 3],
        subplot_titles=["Temperature (T)", "External Field (h)", "Coupling (J)"]
    )
    
    # Temperature from VIX
    temp = ising_params.get("temperature", {})
    if temp.get("available"):
        T_pct = temp.get("T_percentile", 0.5) * 100
        T_regime = temp.get("T_regime", "NORMAL")
        vix = temp.get("vix_current", 0)
        
        # Color based on regime
        if T_regime == "HIGH_TEMP":
            T_color = COLORS["critical"]
        elif T_regime == "LOW_TEMP":
            T_color = COLORS["dispersed"]
        else:
            T_color = COLORS["normal"]
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=T_pct,
                number={"suffix": f"%ile<br>(VIX={vix:.1f})", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": T_color},
                    "steps": [
                        {"range": [0, 20], "color": "#dcfce7"},
                        {"range": [20, 80], "color": "#dbeafe"},
                        {"range": [80, 100], "color": "#fee2e2"},
                    ],
                },
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Indicator(mode="number", value=0, number={"prefix": "N/A"}),
            row=1, col=1
        )
    
    # External Field from SPY momentum
    field = ising_params.get("external_field", {})
    if field.get("available"):
        h_combined = field.get("h_combined", 0) * 100  # Convert to percentage
        bias = field.get("bias", "NEUTRAL")
        
        # Color based on bias
        if bias in ["BULLISH", "MILDLY_BULLISH"]:
            h_color = COLORS["dispersed"]
        elif bias in ["BEARISH", "MILDLY_BEARISH"]:
            h_color = COLORS["critical"]
        else:
            h_color = COLORS["normal"]
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=h_combined,
                number={"suffix": f"%<br>({bias})", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [-5, 5]},
                    "bar": {"color": h_color},
                    "steps": [
                        {"range": [-5, -2], "color": "#fee2e2"},
                        {"range": [-2, 2], "color": "#dbeafe"},
                        {"range": [2, 5], "color": "#dcfce7"},
                    ],
                },
            ),
            row=1, col=2
        )
    else:
        fig.add_trace(
            go.Indicator(mode="number", value=0, number={"prefix": "N/A"}),
            row=1, col=2
        )
    
    # Coupling from options flow
    coupling = ising_params.get("coupling", {})
    if coupling.get("available"):
        J = coupling.get("J_effective", 0) * 100
        signal = coupling.get("signal", "MODERATE")
        divergence = coupling.get("divergence", False)
        
        # Color based on signal and divergence
        if divergence:
            J_color = COLORS["critical"]
        elif signal == "STRONG_COUPLING":
            J_color = COLORS["dispersed"]
        elif signal == "WEAK_COUPLING":
            J_color = COLORS["elevated"]
        else:
            J_color = COLORS["normal"]
        
        label = "⚠️ DIVERGENCE" if divergence else signal
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=J,
                number={"suffix": f"%<br>({label})", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": J_color},
                    "steps": [
                        {"range": [0, 40], "color": "#fef3c7"},
                        {"range": [40, 70], "color": "#dbeafe"},
                        {"range": [70, 100], "color": "#dcfce7"},
                    ],
                },
            ),
            row=1, col=3
        )
    else:
        fig.add_trace(
            go.Indicator(mode="number", value=0, number={"prefix": "N/A"}),
            row=1, col=3
        )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        height=300,
        margin=dict(l=20, r=20, t=80, b=20),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
    )
    
    return fig.to_dict()


# =============================================================================
# COUPLING DIVERGENCE CHART
# =============================================================================

def build_coupling_divergence_chart(
    coupling: Dict[str, Any],
    title: str = "Price vs Options Magnetization"
) -> Dict[str, Any]:
    """
    Build a chart comparing price magnetization vs options magnetization.
    
    Divergence between these signals potential reversal.
    
    Args:
        coupling: Dict with M_price, M_options, sectors_analyzed
        title: Chart title
        
    Returns:
        Plotly figure as dict
    """
    if not coupling.get("available"):
        return {
            "error": "Coupling data not available",
            "type": "error"
        }
    
    M_price = coupling.get("M_price", 0)
    M_options = coupling.get("M_options", 0)
    J = coupling.get("J_effective", 0)
    divergence = coupling.get("divergence", False)
    
    # Create comparison chart
    fig = go.Figure()
    
    # Price magnetization bar
    fig.add_trace(go.Bar(
        x=["Price Sentiment"],
        y=[M_price],
        name="Price M",
        marker_color=COLORS["normal"],
        text=f"{M_price:.2f}",
        textposition="outside",
    ))
    
    # Options magnetization bar
    fig.add_trace(go.Bar(
        x=["Options Sentiment"],
        y=[M_options],
        name="Options M",
        marker_color=COLORS["elevated"],
        text=f"{M_options:.2f}",
        textposition="outside",
    ))
    
    # Add reference lines
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_hline(y=0.3, line_dash="dot", line_color="green", annotation_text="Bullish threshold")
    fig.add_hline(y=-0.3, line_dash="dot", line_color="red", annotation_text="Bearish threshold")
    
    # Add divergence warning annotation
    if divergence:
        fig.add_annotation(
            x=0.5, y=1.1,
            xref="paper", yref="paper",
            text="⚠️ DIVERGENCE DETECTED - Potential Reversal",
            showarrow=False,
            font=dict(size=14, color=COLORS["critical"]),
            bgcolor="#fee2e2",
            bordercolor=COLORS["critical"],
            borderwidth=2,
        )
    
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:0.8em;color:gray'>Coupling J = {J:.0%}</span>",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=100, b=40),
        paper_bgcolor="white",
        font={"color": COLORS["text"]},
        yaxis=dict(title="Magnetization", range=[-1.2, 1.2]),
        barmode="group",
    )
    
    return fig.to_dict()


# =============================================================================
# MAIN CHART GENERATOR
# =============================================================================

def generate_herding_charts(
    ising_stats: Dict[str, Any],
    hmm_regime: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generate all charts for the herding regime detector.
    
    Args:
        ising_stats: Output from compute_all_ising_statistics
        hmm_regime: Optional output from detect_hmm_regime
        
    Returns:
        List of Plotly figures as dicts
    """
    charts = []
    
    try:
        # 1. Herding Index Gauge
        herding_index = ising_stats.get("herding_index", {})
        if herding_index:
            charts.append({
                "id": "herding_gauge",
                "title": "Herding Index",
                "plotly": build_herding_gauge(herding_index),
                "alt_text": "Gauge showing current herding index level"
            })
        
        # 2. Signal Dashboard
        charts.append({
            "id": "signal_dashboard",
            "title": "Early Warning Signals",
            "plotly": build_signal_dashboard(ising_stats),
            "alt_text": "Dashboard of 4 Ising early warning signals"
        })
        
        # 3. Ising Parameters Dashboard (T, h, J)
        ising_params = ising_stats.get("ising_parameters", {})
        if ising_params:
            # Check if any parameter is available
            has_params = any(
                ising_params.get(k, {}).get("available", False)
                for k in ["temperature", "external_field", "coupling"]
            )
            if has_params:
                charts.append({
                    "id": "ising_parameters",
                    "title": "Ising Model Parameters (T, h, J)",
                    "plotly": build_ising_parameters_chart(ising_params),
                    "alt_text": "Temperature, External Field, and Coupling parameters"
                })
        
        # 4. Coupling Divergence Chart (if coupling available)
        coupling = ising_params.get("coupling", {})
        if coupling.get("available"):
            charts.append({
                "id": "coupling_divergence",
                "title": "Price vs Options Magnetization",
                "plotly": build_coupling_divergence_chart(coupling),
                "alt_text": "Comparison of price and options sentiment"
            })
        
        # 5. Correlation Heatmap
        corr_matrix = ising_stats.get("ising_statistics", {}).get("correlation_length", {}).get("correlation_matrix", {})
        if corr_matrix:
            charts.append({
                "id": "correlation_heatmap",
                "title": "Sector Correlations",
                "plotly": build_correlation_heatmap(corr_matrix),
                "alt_text": "Heatmap of sector correlation matrix"
            })
        
        # 6. Statistics Timeseries (single panel, percentiles)
        charts.append({
            "id": "statistics_timeseries",
            "title": "Ising Statistics (Percentiles)",
            "plotly": build_statistics_timeseries(ising_stats),
            "alt_text": "Timeseries of all Ising statistics as percentiles"
        })
        
        # 7. Regime Probability Bar (if HMM available)
        if hmm_regime and hmm_regime.get("status") == "success":
            charts.append({
                "id": "regime_bar",
                "title": "Regime Probabilities",
                "plotly": build_regime_bar(hmm_regime),
                "alt_text": "Bar chart of regime state probabilities"
            })
        
    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        charts.append({
            "type": "error",
            "title": "Chart Error",
            "error": str(e)
        })
    
    return charts

