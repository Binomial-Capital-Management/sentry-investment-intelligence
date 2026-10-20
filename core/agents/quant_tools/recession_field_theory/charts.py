"""
Recession Field Theory - Charts and Visualizations

Creates visualizations for:
1. Economic field time series with regime coloring
2. Early warning signal dashboard (4 gauges)
3. Recession probability over time
4. Indicator contributions breakdown
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Any
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


# =============================================================================
# COLOR SCHEMES (Light background compatible - dark text)
# =============================================================================

COLORS = {
    "expansion": "#16a34a",      # Green (darker for visibility)
    "transition": "#d97706",     # Amber (darker)
    "recession": "#dc2626",      # Red (darker)
    "normal": "#2563eb",         # Blue (darker)
    "elevated": "#d97706",       # Amber
    "critical": "#dc2626",       # Red
    "background": "#ffffff",     # White
    "text": "#1e293b",           # Dark slate (dark text)
    "grid": "#e2e8f0",           # Light gray grid
    "field_line": "#2563eb",     # Blue (darker for visibility)
    "zero_line": "#64748b"       # Gray
}


# =============================================================================
# 1. ECONOMIC FIELD TIME SERIES
# =============================================================================

def build_field_chart(
    field: pd.Series,
    regime_history: Optional[pd.Series] = None,
    title: str = "Economic Field φ(t)"
) -> Dict[str, Any]:
    """
    Build time series chart of economic field with regime coloring.
    
    Args:
        field: Economic field series
        regime_history: Optional series of regime labels for coloring
        title: Chart title
    
    Returns:
        Plotly chart dict
    """
    fig = go.Figure()
    
    # Field line
    fig.add_trace(go.Scatter(
        x=field.index,
        y=field.values,
        mode='lines',
        name='Economic Field φ(t)',
        line=dict(color=COLORS["field_line"], width=2),
        hovertemplate='%{x|%b %Y}<br>φ = %{y:.2f}<extra></extra>'
    ))
    
    # Add regime shading if available
    if regime_history is not None and len(regime_history) > 0:
        # Find regime change points
        regime_changes = regime_history.ne(regime_history.shift()).cumsum()
        
        for regime_id in regime_changes.unique():
            mask = regime_changes == regime_id
            regime_dates = regime_history.index[mask]
            regime_name = regime_history.loc[regime_dates[0]]
            
            if len(regime_dates) >= 2:
                color = COLORS.get(regime_name, COLORS["transition"])
                fig.add_vrect(
                    x0=regime_dates[0],
                    x1=regime_dates[-1],
                    fillcolor=color,
                    opacity=0.1,
                    layer="below",
                    line_width=0
                )
    
    # Zero line
    fig.add_hline(
        y=0,
        line=dict(color=COLORS["zero_line"], width=1, dash="dash"),
        annotation_text="Neutral",
        annotation_position="right"
    )
    
    # Recession zone shading
    fig.add_hrect(
        y0=-3, y1=-0.5,
        fillcolor=COLORS["recession"],
        opacity=0.05,
        layer="below",
        line_width=0
    )
    
    # Layout
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=16)),
        xaxis_title="Date",
        yaxis_title="Field Value (z-score)",
        template="plotly_white",
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=60, b=40)
    )
    
    return {
        "id": "recession_field_timeseries",
        "title": title,
        "plotly": fig.to_dict()
    }


# =============================================================================
# 2. EARLY WARNING DASHBOARD (4 GAUGES)
# =============================================================================

def build_warning_dashboard(
    statistics: Dict[str, Dict],
    composite_score: float
) -> Dict[str, Any]:
    """
    Build dashboard with 4 gauge charts for physics statistics.
    
    Args:
        statistics: Dict from PhysicsStatsAnalyzer with ar1, xi, chi, spectral
        composite_score: Overall warning score (0-10)
    
    Returns:
        Plotly chart dict
    """
    fig = make_subplots(
        rows=2, cols=2,
        specs=[
            [{"type": "indicator"}, {"type": "indicator"}],
            [{"type": "indicator"}, {"type": "indicator"}]
        ],
        subplot_titles=[
            "Critical Slowing Down (AR1)",
            "Correlation Length (ξ)",
            "Susceptibility (χ)",
            "Spectral Dominance (λ₁/Σλ)"
        ],
        vertical_spacing=0.25,
        horizontal_spacing=0.15
    )
    
    # Helper to get value and signal
    def get_stat(key, subkey):
        stat = statistics.get(key, {})
        return stat.get(subkey), stat.get("signal", "UNKNOWN")
    
    # 1. AR1 Coefficient
    ar1_val, ar1_signal = get_stat("critical_slowing_down", "ar1_coefficient")
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=ar1_val or 0,
        number={"suffix": "", "font": {"size": 24}},
        gauge={
            "axis": {"range": [0.5, 1.0], "tickwidth": 1},
            "bar": {"color": COLORS.get(ar1_signal.lower(), COLORS["normal"])},
            "steps": [
                {"range": [0.5, 0.75], "color": "#1e3a5f"},
                {"range": [0.75, 0.88], "color": "#22763f"},
                {"range": [0.88, 0.95], "color": "#b45309"},
                {"range": [0.95, 1.0], "color": "#991b1b"}
            ],
            "threshold": {
                "line": {"color": "#1e293b", "width": 2},
                "thickness": 0.75,
                "value": ar1_val or 0
            }
        }
    ), row=1, col=1)
    
    # 2. Correlation Length
    xi_val, xi_signal = get_stat("correlation_length", "cross_sector_correlation")
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=xi_val or 0,
        number={"suffix": "", "font": {"size": 24}},
        gauge={
            "axis": {"range": [0, 1.0], "tickwidth": 1},
            "bar": {"color": COLORS.get(xi_signal.lower(), COLORS["normal"])},
            "steps": [
                {"range": [0, 0.2], "color": "#1e3a5f"},
                {"range": [0.2, 0.4], "color": "#22763f"},
                {"range": [0.4, 0.65], "color": "#b45309"},
                {"range": [0.65, 1.0], "color": "#991b1b"}
            ],
            "threshold": {
                "line": {"color": "#1e293b", "width": 2},
                "thickness": 0.75,
                "value": xi_val or 0
            }
        }
    ), row=1, col=2)
    
    # 3. Susceptibility
    chi_val, chi_signal = get_stat("susceptibility", "variance_ratio")
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=chi_val or 1,
        number={"suffix": "x", "font": {"size": 24}},
        gauge={
            "axis": {"range": [0, 4.0], "tickwidth": 1},
            "bar": {"color": COLORS.get(chi_signal.lower(), COLORS["normal"])},
            "steps": [
                {"range": [0, 0.7], "color": "#1e3a5f"},
                {"range": [0.7, 1.3], "color": "#22763f"},
                {"range": [1.3, 2.5], "color": "#b45309"},
                {"range": [2.5, 4.0], "color": "#991b1b"}
            ],
            "threshold": {
                "line": {"color": "#1e293b", "width": 2},
                "thickness": 0.75,
                "value": chi_val or 1
            }
        }
    ), row=2, col=1)
    
    # 4. Spectral Dominance
    spec_val, spec_signal = get_stat("spectral_dominance", "first_eigenvalue_share")
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=(spec_val or 0) * 100,
        number={"suffix": "%", "font": {"size": 24}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": COLORS.get(spec_signal.lower(), COLORS["normal"])},
            "steps": [
                {"range": [0, 25], "color": "#1e3a5f"},
                {"range": [25, 42], "color": "#22763f"},
                {"range": [42, 60], "color": "#b45309"},
                {"range": [60, 100], "color": "#991b1b"}
            ],
            "threshold": {
                "line": {"color": "#1e293b", "width": 2},
                "thickness": 0.75,
                "value": (spec_val or 0) * 100
            }
        }
    ), row=2, col=2)
    
    # Layout
    fig.update_layout(
        title=dict(
            text=f"<b>Early Warning Dashboard</b> | Composite Score: {composite_score:.1f}/10",
            font=dict(size=16)
        ),
        template="plotly_white",
        height=500,
        margin=dict(l=40, r=40, t=80, b=40)
    )
    
    return {
        "id": "recession_warning_dashboard",
        "title": "Early Warning Dashboard",
        "plotly": fig.to_dict()
    }


# =============================================================================
# 3. REGIME PROBABILITY BAR
# =============================================================================

def build_regime_chart(
    regime_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build horizontal stacked bar showing business cycle phase probabilities.
    
    Args:
        regime_result: Dict from RegimeAnalyzer (4 phases)
    
    Returns:
        Plotly chart dict
    """
    probs = regime_result.get("regime_probabilities", {})
    current = regime_result.get("current_regime", "unknown")
    
    # Business cycle phase colors
    phase_colors = {
        "expansion": "#16a34a",    # Green
        "peak": "#0ea5e9",         # Blue
        "contraction": "#f59e0b",  # Amber
        "trough": "#dc2626"        # Red
    }
    
    fig = go.Figure()
    
    # Stacked bar for 4 business cycle phases
    for phase in ["expansion", "peak", "contraction", "trough"]:
        prob = probs.get(phase, 0)
        
        fig.add_trace(go.Bar(
            x=[prob],
            y=["Phase"],
            orientation='h',
            name=phase.title(),
            marker_color=phase_colors.get(phase, "#666"),
            text=f"{prob:.0%}" if prob >= 0.05 else "",
            textposition='inside',
            textfont=dict(color="#1e293b", size=12),
            hovertemplate=f"{phase.title()}: {prob:.1%}<extra></extra>"
        ))
    
    # Current phase annotation
    fig.add_annotation(
        text=f"Current Phase: <b>{current.upper()}</b>",
        xref="paper", yref="paper",
        x=0.5, y=1.2,
        showarrow=False,
        font=dict(size=14, color=phase_colors.get(current, "#1e293b"))
    )
    
    fig.update_layout(
        title=dict(text="<b>Business Cycle Phase Probabilities</b>", font=dict(size=14, color="#1e293b")),
        barmode='stack',
        template="plotly_white",
        height=180,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
        xaxis=dict(range=[0, 1], tickformat=".0%", title=""),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=80, b=80)
    )
    
    return {
        "id": "business_cycle_phase_probs",
        "title": "Business Cycle Phase Probabilities",
        "plotly": fig.to_dict()
    }


# =============================================================================
# 4. INDICATOR CONTRIBUTIONS
# =============================================================================

def build_contributions_chart(
    breakdown: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build bar chart showing indicator contributions to field.
    
    Args:
        breakdown: Dict from EconomicFieldBuilder.get_breakdown()
    
    Returns:
        Plotly chart dict
    """
    components = breakdown.get("components", {})
    
    if not components:
        return None
    
    # Extract data
    names = []
    contributions = []
    colors = []
    
    for name, data in components.items():
        contrib = data.get("contribution", 0)
        names.append(name.replace("_", " ").title())
        contributions.append(contrib)
        colors.append(COLORS["expansion"] if contrib > 0 else COLORS["recession"])
    
    # Sort by absolute contribution
    sorted_idx = np.argsort(np.abs(contributions))[::-1]
    names = [names[i] for i in sorted_idx]
    contributions = [contributions[i] for i in sorted_idx]
    colors = [colors[i] for i in sorted_idx]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=contributions,
        y=names,
        orientation='h',
        marker_color=colors,
        text=[f"{c:+.3f}" for c in contributions],
        textposition='outside',
        hovertemplate='%{y}: %{x:+.3f}<extra></extra>'
    ))
    
    # Zero line
    fig.add_vline(x=0, line=dict(color=COLORS["zero_line"], width=1))
    
    total = breakdown.get("total_field_value", sum(contributions))
    
    fig.update_layout(
        title=dict(
            text=f"<b>Indicator Contributions</b> | Total φ = {total:+.2f}",
            font=dict(size=14)
        ),
        template="plotly_white",
        height=max(300, len(names) * 25 + 100),
        xaxis_title="Contribution to Field",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=150, r=60, t=60, b=40)
    )
    
    return {
        "id": "recession_contributions",
        "title": "Indicator Contributions",
        "plotly": fig.to_dict()
    }


# =============================================================================
# 5. RECESSION PROBABILITY GAUGE
# =============================================================================

def build_probability_gauge(
    recession_prob: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build gauge showing recession probability.
    
    Args:
        recession_prob: Dict from estimate_recession_probability()
    
    Returns:
        Plotly chart dict
    """
    prob = recession_prob.get("probability", 0)
    ci = recession_prob.get("confidence_interval", [0, 1])
    interpretation = recession_prob.get("interpretation", "")
    
    fig = go.Figure()
    
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=prob * 100,
        number={"suffix": "%", "font": {"size": 36}},
        title={"text": "6-Month Recession Probability", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "ticksuffix": "%"},
            "bar": {"color": "#60a5fa"},
            "steps": [
                {"range": [0, 20], "color": "#166534"},
                {"range": [20, 35], "color": "#ca8a04"},
                {"range": [35, 60], "color": "#c2410c"},
                {"range": [60, 100], "color": "#991b1b"}
            ],
            "threshold": {
                "line": {"color": "#1e293b", "width": 3},
                "thickness": 0.8,
                "value": prob * 100
            }
        }
    ))
    
    # Confidence interval annotation
    fig.add_annotation(
        text=f"95% CI: [{ci[0]*100:.0f}%, {ci[1]*100:.0f}%]",
        xref="paper", yref="paper",
        x=0.5, y=-0.1,
        showarrow=False,
        font=dict(size=11, color="#94a3b8")
    )
    
    # Interpretation
    fig.add_annotation(
        text=interpretation,
        xref="paper", yref="paper",
        x=0.5, y=-0.2,
        showarrow=False,
        font=dict(size=12, color="#f8fafc")
    )
    
    fig.update_layout(
        template="plotly_white",
        height=300,
        margin=dict(l=40, r=40, t=40, b=80)
    )
    
    return {
        "id": "recession_probability_gauge",
        "title": "Recession Probability",
        "plotly": fig.to_dict()
    }


# =============================================================================
# MAIN CHART BUILDER
# =============================================================================

def build_all_charts(
    field: pd.Series,
    physics_stats: Dict[str, Any],
    regime_result: Dict[str, Any],
    recession_prob: Dict[str, Any],
    field_breakdown: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Build all charts for recession field theory output.
    
    Returns:
        List of chart dicts
    """
    charts = []
    
    # 1. Field time series
    try:
        field_chart = build_field_chart(field)
        if field_chart:
            charts.append(field_chart)
    except Exception as e:
        logger.warning(f"Failed to build field chart: {e}")
    
    # 2. Warning dashboard
    try:
        stats = physics_stats.get("statistics", {})
        score = physics_stats.get("composite_warning_score", 0)
        dashboard = build_warning_dashboard(stats, score)
        if dashboard:
            charts.append(dashboard)
    except Exception as e:
        logger.warning(f"Failed to build warning dashboard: {e}")
    
    # 3. Regime bar
    try:
        regime_chart = build_regime_chart(regime_result)
        if regime_chart:
            charts.append(regime_chart)
    except Exception as e:
        logger.warning(f"Failed to build regime chart: {e}")
    
    # 4. Probability gauge
    try:
        prob_chart = build_probability_gauge(recession_prob)
        if prob_chart:
            charts.append(prob_chart)
    except Exception as e:
        logger.warning(f"Failed to build probability gauge: {e}")
    
    # 5. Contributions
    try:
        if field_breakdown and "components" in field_breakdown:
            contrib_chart = build_contributions_chart(field_breakdown)
            if contrib_chart:
                charts.append(contrib_chart)
    except Exception as e:
        logger.warning(f"Failed to build contributions chart: {e}")
    
    return charts

