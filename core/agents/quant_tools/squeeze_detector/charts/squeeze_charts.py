"""
Squeeze Detection Charts

Professional data visualizations for squeeze analysis:
- GEX Profile: Area chart with key levels
- Signal Distribution: Z-score distribution visualization
- Path Fan: Probabilistic trajectory fan chart
- Squeeze Meter: Radial gauge with signal breakdown
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# COLOR PALETTES
# =============================================================================

COLORS = {
    "bg_dark": "#0f0f1a",
    "bg_card": "#16162a",
    "bg_elevated": "#1e1e3a",
    "text_primary": "#e5e7eb",
    "text_secondary": "#9ca3af",
    "text_muted": "#6b7280",
    "accent_green": "#10b981",
    "accent_green_light": "#34d399",
    "accent_orange": "#f97316",
    "accent_orange_light": "#fb923c",
    "accent_blue": "#3b82f6",
    "accent_blue_light": "#60a5fa",
    "accent_yellow": "#eab308",
    "accent_purple": "#8b5cf6",
    "grid": "rgba(100,100,100,0.12)",
    "grid_emphasis": "rgba(255,255,255,0.15)",
}


def build_gex_structure_chart(
    gamma_features: Dict,
    spot_price: float,
    ticker: str
) -> Optional[Dict[str, Any]]:
    """
    Build GEX profile as area chart with smooth gradients.
    
    Shows:
    - Positive GEX as green filled area (call wall / resistance)
    - Negative GEX as orange filled area (put wall / support)
    - Current price marker
    - Key levels with elegant annotations
    """
    import plotly.graph_objects as go
    from scipy.ndimage import gaussian_filter1d
    
    gex_data = gamma_features.get("gex_by_strike", [])
    key_levels = gamma_features.get("key_levels", {})
    
    if not gex_data:
        return None
    
    # Sort by strike
    sorted_gex = sorted(gex_data, key=lambda x: x.get("strike", 0))
    
    strikes = np.array([item["strike"] for item in sorted_gex])
    gex_values = np.array([item["gex"] for item in sorted_gex])
    
    # Auto-scale
    max_abs_gex = max(abs(g) for g in gex_values) if len(gex_values) > 0 else 1
    if max_abs_gex > 1e9:
        scale_factor = 1e9
        scale_label = "B"
    elif max_abs_gex > 1e6:
        scale_factor = 1e6
        scale_label = "M"
    else:
        scale_factor = 1
        scale_label = ""
    
    gex_scaled = gex_values / scale_factor
    
    # Smooth the curve slightly for cleaner visualization
    if len(gex_scaled) > 5:
        gex_smooth = gaussian_filter1d(gex_scaled, sigma=0.8)
    else:
        gex_smooth = gex_scaled
    
    # Separate positive and negative for dual fills
    gex_positive = np.clip(gex_smooth, 0, None)
    gex_negative = np.clip(gex_smooth, None, 0)
    
    fig = go.Figure()
    
    # Negative GEX area (put gamma - support zone)
    fig.add_trace(go.Scatter(
        x=strikes,
        y=gex_negative,
        fill='tozeroy',
        fillcolor='rgba(249, 115, 22, 0.25)',
        line=dict(color=COLORS["accent_orange"], width=1.5),
        name='Put Gamma',
        hovertemplate="<b>$%{x:.0f}</b><br>Put GEX: %{y:.2f}" + scale_label + "<extra></extra>"
    ))
    
    # Positive GEX area (call gamma - resistance zone)
    fig.add_trace(go.Scatter(
        x=strikes,
        y=gex_positive,
        fill='tozeroy',
        fillcolor='rgba(16, 185, 129, 0.25)',
        line=dict(color=COLORS["accent_green"], width=1.5),
        name='Call Gamma',
        hovertemplate="<b>$%{x:.0f}</b><br>Call GEX: %{y:.2f}" + scale_label + "<extra></extra>"
    ))
    
    # Current price - prominent vertical band
    fig.add_vrect(
        x0=spot_price * 0.995, x1=spot_price * 1.005,
        fillcolor='rgba(59, 130, 246, 0.15)',
        line_width=0
    )
    fig.add_vline(
        x=spot_price,
        line=dict(color=COLORS["accent_blue"], width=2),
    )
    fig.add_annotation(
        x=spot_price, y=1.02,
        xref="x", yref="paper",
        text=f"<b>${spot_price:.2f}</b>",
        font=dict(size=11, color=COLORS["accent_blue"]),
        showarrow=False,
        bgcolor="rgba(59,130,246,0.15)",
        borderpad=4
    )
    
    # Key level markers with elegant styling
    if key_levels.get("put_wall"):
        pw = key_levels["put_wall"]
        fig.add_annotation(
            x=pw, y=-0.08, xref="x", yref="paper",
            text=f"▲ Support ${pw:.0f}",
            font=dict(size=10, color=COLORS["accent_orange"]),
            showarrow=False
        )
        fig.add_shape(
            type="line", x0=pw, x1=pw, y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=COLORS["accent_orange"], width=1, dash="dot")
        )
    
    if key_levels.get("call_wall"):
        cw = key_levels["call_wall"]
        fig.add_annotation(
            x=cw, y=-0.08, xref="x", yref="paper",
            text=f"▼ Resistance ${cw:.0f}",
            font=dict(size=10, color=COLORS["accent_green"]),
            showarrow=False
        )
        fig.add_shape(
            type="line", x0=cw, x1=cw, y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=COLORS["accent_green"], width=1, dash="dot")
        )
    
    if key_levels.get("gamma_ramp"):
        gr = key_levels["gamma_ramp"]
        fig.add_vrect(
            x0=gr, x1=strikes[-1] if len(strikes) > 0 else gr * 1.1,
            fillcolor='rgba(234, 179, 8, 0.08)',
            line_width=0
        )
        fig.add_annotation(
            x=gr, y=0.95, xref="x", yref="paper",
            text=f"⚡ Ramp ${gr:.0f}",
            font=dict(size=11, color=COLORS["accent_yellow"]),
            showarrow=False,
            bgcolor="rgba(234,179,8,0.15)",
            borderpad=4
        )
    
    fig.update_layout(
        title=dict(
            text=f"<b>{ticker}</b> Gamma Exposure Profile",
            font=dict(size=15, color=COLORS["text_primary"]),
            x=0.5, xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Strike Price", font=dict(size=11, color=COLORS["text_secondary"])),
            gridcolor=COLORS["grid"],
            tickfont=dict(size=10, color=COLORS["text_secondary"]),
            tickprefix="$",
            showspikes=True,
            spikecolor=COLORS["accent_blue"],
            spikethickness=1
        ),
        yaxis=dict(
            title=dict(
                text=f"Gamma Exposure ({scale_label}$)" if scale_label else "Gamma Exposure",
                font=dict(size=11, color=COLORS["text_secondary"])
            ),
            gridcolor=COLORS["grid"],
            zerolinecolor=COLORS["grid_emphasis"],
            zerolinewidth=1,
            tickfont=dict(size=10, color=COLORS["text_secondary"])
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=10, color=COLORS["text_secondary"]),
            bgcolor="rgba(0,0,0,0)"
        ),
        height=420,
        margin=dict(l=60, r=30, t=80, b=60),
        plot_bgcolor=COLORS["bg_card"],
        paper_bgcolor=COLORS["bg_dark"],
        font=dict(color=COLORS["text_primary"], family="Inter, system-ui, sans-serif"),
        hovermode="x unified"
    )
    
    return {
        "plotly": fig.to_dict(),
        "title": f"{ticker} GEX Profile"
    }


def build_path_fan_chart(
    path_result: Dict,
    spot_price: float,
    ticker: str
) -> Optional[Dict[str, Any]]:
    """
    Build elegant probability fan chart showing price trajectories.
    
    Creates layered gradient bands representing confidence intervals
    with a prominent median path and key threshold markers.
    """
    import plotly.graph_objects as go
    
    percentile_paths = path_result.get("percentile_paths", {})
    horizon = path_result.get("horizon_days", 30)
    
    if not percentile_paths:
        return None
    
    days = list(range(horizon + 1))
    
    p5 = percentile_paths.get("p5", percentile_paths.get("p10", []))
    p10 = percentile_paths.get("p10", [])
    p25 = percentile_paths.get("p25", [])
    p50 = percentile_paths.get("p50", [])
    p75 = percentile_paths.get("p75", [])
    p90 = percentile_paths.get("p90", [])
    p95 = percentile_paths.get("p95", percentile_paths.get("p90", []))
    
    if not p50:
        return None
    
    fig = go.Figure()
    
    # Outermost band (p5-p95 or p10-p90)
    outer_low = p5 if p5 else p10
    outer_high = p95 if p95 else p90
    if outer_low and outer_high:
        fig.add_trace(go.Scatter(
            x=days + days[::-1],
            y=outer_high + outer_low[::-1],
            fill='toself',
            fillcolor='rgba(139, 92, 246, 0.06)',  # Purple tint
            line=dict(color='rgba(0,0,0,0)'),
            name='95% Range',
            showlegend=True,
            hoverinfo='skip'
        ))
    
    # Middle band (p10-p90)
    if p10 and p90 and (p10 != outer_low):
        fig.add_trace(go.Scatter(
            x=days + days[::-1],
            y=p90 + p10[::-1],
            fill='toself',
            fillcolor='rgba(59, 130, 246, 0.10)',
            line=dict(color='rgba(0,0,0,0)'),
            name='80% Range',
            showlegend=True,
            hoverinfo='skip'
        ))
    
    # Inner band (p25-p75)
    if p25 and p75:
        fig.add_trace(go.Scatter(
            x=days + days[::-1],
            y=p75 + p25[::-1],
            fill='toself',
            fillcolor='rgba(59, 130, 246, 0.18)',
            line=dict(color='rgba(0,0,0,0)'),
            name='50% Range',
            showlegend=True,
            hoverinfo='skip'
        ))
    
    # P75 line (upper bound)
    if p75:
        fig.add_trace(go.Scatter(
            x=days, y=p75,
            mode='lines',
            line=dict(color='rgba(96, 165, 250, 0.4)', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # P25 line (lower bound)
    if p25:
        fig.add_trace(go.Scatter(
            x=days, y=p25,
            mode='lines',
            line=dict(color='rgba(96, 165, 250, 0.4)', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Median path - prominent with glow effect
    fig.add_trace(go.Scatter(
        x=days, y=p50,
        mode='lines',
        line=dict(color=COLORS["accent_blue"], width=3),
        name='Median Path',
        hovertemplate="<b>Day %{x}</b><br>Median: $%{y:.2f}<extra></extra>"
    ))
    
    # Current price - horizontal reference
    fig.add_hline(
        y=spot_price,
        line=dict(color=COLORS["text_muted"], width=1, dash='dash'),
    )
    fig.add_annotation(
        x=0, y=spot_price,
        xref="paper", yref="y",
        text=f"  ${spot_price:.2f}",
        font=dict(size=10, color=COLORS["text_secondary"]),
        showarrow=False,
        xanchor="left"
    )
    
    # Squeeze threshold zones
    squeeze_20 = spot_price * 1.2
    squeeze_30 = spot_price * 1.3
    
    # +20% threshold
    fig.add_hline(
        y=squeeze_20,
        line=dict(color=COLORS["accent_green"], width=1.5, dash='dot'),
    )
    fig.add_annotation(
        x=1, y=squeeze_20,
        xref="paper", yref="y",
        text="+20%  ",
        font=dict(size=10, color=COLORS["accent_green"]),
        showarrow=False,
        xanchor="right"
    )
    
    # Squeeze zone highlight
    if p90 and max(p90) >= squeeze_20:
        fig.add_hrect(
            y0=squeeze_20, y1=max(p90) * 1.05,
            fillcolor='rgba(16, 185, 129, 0.05)',
            line_width=0
        )
    
    # Squeeze probability stats box
    squeeze_prob = path_result.get("squeeze_probability", 0)
    expected_peak = path_result.get("peak_timing", {}).get("p50", "—")
    max_move = ((max(p50) / spot_price) - 1) * 100 if p50 else 0
    
    stats_text = (
        f"<b>Squeeze Stats</b><br>"
        f"P(+20%): {squeeze_prob:.0%}<br>"
        f"Peak Day: ~{expected_peak}<br>"
        f"Max Move: +{max_move:.0f}%"
    )
    
    fig.add_annotation(
        x=0.02, y=0.98,
        xref="paper", yref="paper",
        text=stats_text,
        font=dict(size=10, color=COLORS["text_primary"]),
        align="left",
        showarrow=False,
        bgcolor="rgba(30,30,60,0.85)",
        bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1,
        borderpad=8,
        xanchor="left",
        yanchor="top"
    )
    
    fig.update_layout(
        title=dict(
            text=f"<b>{ticker}</b> Price Path Distribution",
            font=dict(size=15, color=COLORS["text_primary"]),
            x=0.5, xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Days Forward", font=dict(size=11, color=COLORS["text_secondary"])),
            gridcolor=COLORS["grid"],
            tickfont=dict(size=10, color=COLORS["text_secondary"]),
            showspikes=True,
            spikecolor=COLORS["accent_blue"],
            spikethickness=1
        ),
        yaxis=dict(
            title=dict(text="Price", font=dict(size=11, color=COLORS["text_secondary"])),
            gridcolor=COLORS["grid"],
            tickfont=dict(size=10, color=COLORS["text_secondary"]),
            tickprefix="$"
        ),
        height=450,
        margin=dict(l=60, r=50, t=70, b=50),
        plot_bgcolor=COLORS["bg_card"],
        paper_bgcolor=COLORS["bg_dark"],
        font=dict(color=COLORS["text_primary"], family="Inter, system-ui, sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=9, color=COLORS["text_secondary"]),
            bgcolor="rgba(0,0,0,0)"
        ),
        hovermode="x unified"
    )
    
    return {
        "plotly": fig.to_dict(),
        "title": f"{ticker} Path Distribution"
    }


def build_signal_distribution_chart(
    features: Dict,
    ticker: str,
    timing: Optional[Dict] = None,
    magnitude: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Build a beautiful signal distribution visualization.
    
    Shows z-scores as a radial/lollipop chart with distribution context,
    plus summary metrics in an elegant layout.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Extract z-scores
    z_scores = {}
    for key, val in features.items():
        if "zscore" in key and isinstance(val, (int, float)):
            clean_key = key.replace("_zscore", "").replace("_", " ").title()
            z_scores[clean_key] = val
    
    if not z_scores:
        return None
    
    # Sort by value
    sorted_items = sorted(z_scores.items(), key=lambda x: x[1], reverse=True)
    labels = [item[0] for item in sorted_items]
    values = [item[1] for item in sorted_items]
    
    # Create figure with two subplots: main chart + summary panel
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.72, 0.28],
        specs=[[{"type": "scatter"}, {"type": "scatter"}]],
        horizontal_spacing=0.08
    )
    
    # === LEFT: Signal Lollipop Chart ===
    
    # Background distribution reference (normal distribution shape)
    n_points = 100
    x_dist = np.linspace(-4, 4, n_points)
    y_dist = np.exp(-x_dist**2 / 2) / np.sqrt(2 * np.pi)
    y_dist_scaled = y_dist * len(labels) / max(y_dist)
    
    # Normal distribution backdrop
    fig.add_trace(go.Scatter(
        x=x_dist,
        y=y_dist_scaled,
        mode='lines',
        fill='tozeroy',
        fillcolor='rgba(100, 100, 120, 0.08)',
        line=dict(color='rgba(100, 100, 120, 0.2)', width=1),
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=1)
    
    # Threshold zones
    # Elevated zone (>1.5σ)
    fig.add_vrect(x0=1.5, x1=4, fillcolor='rgba(16, 185, 129, 0.06)', 
                  line_width=0, row=1, col=1)
    # Extreme zone (>2.5σ)
    fig.add_vrect(x0=2.5, x1=4, fillcolor='rgba(16, 185, 129, 0.08)',
                  line_width=0, row=1, col=1)
    
    # Signal lollipops
    for i, (label, val) in enumerate(zip(labels, values)):
        y_pos = len(labels) - i - 0.5
        
        # Color based on value
        if val >= 2.5:
            color = COLORS["accent_green"]
            size = 14
        elif val >= 1.5:
            color = COLORS["accent_green_light"]
            size = 12
        elif val >= 0.5:
            color = COLORS["accent_blue_light"]
            size = 10
        elif val > -0.5:
            color = COLORS["text_muted"]
            size = 8
        else:
            color = COLORS["accent_orange"]
            size = 10
        
        # Stem line
        fig.add_trace(go.Scatter(
            x=[0, val],
            y=[y_pos, y_pos],
            mode='lines',
            line=dict(color=color, width=2),
            showlegend=False,
            hoverinfo='skip'
        ), row=1, col=1)
        
        # Dot
        fig.add_trace(go.Scatter(
            x=[val],
            y=[y_pos],
            mode='markers+text',
            marker=dict(
                color=color,
                size=size,
                line=dict(color='rgba(255,255,255,0.3)', width=1)
            ),
            text=[f"{val:+.1f}σ"],
            textposition="middle right" if val >= 0 else "middle left",
            textfont=dict(size=10, color=color),
            showlegend=False,
            hovertemplate=f"<b>{label}</b><br>Z-Score: {val:+.2f}σ<extra></extra>"
        ), row=1, col=1)
        
        # Label on left
        fig.add_annotation(
            x=-4.2, y=y_pos,
            text=label,
            font=dict(size=11, color=COLORS["text_primary"]),
            showarrow=False,
            xanchor="right",
            row=1, col=1
        )
    
    # Reference lines
    fig.add_vline(x=0, line=dict(color=COLORS["grid_emphasis"], width=1), row=1, col=1)
    fig.add_vline(x=2, line=dict(color=COLORS["accent_green"], width=1, dash='dot'), row=1, col=1)
    
    # === RIGHT: Summary Panel ===
    
    trigger_prob = timing.get("trigger_prob_5d", 0) if timing else 0
    trigger_prob_10d = timing.get("trigger_prob_10d", 0) if timing else 0
    expected_move = magnitude.get("expected_move", 0) if magnitude else 0
    ci_90 = magnitude.get("ci_90", [0, 0]) if magnitude else [0, 0]
    signal_count = timing.get("signal_count", 0) if timing else 0
    
    # Probability arc (semi-circular gauge feel)
    theta = np.linspace(0, np.pi, 50)
    arc_x = np.cos(theta)
    arc_y = np.sin(theta)
    
    # Background arc
    fig.add_trace(go.Scatter(
        x=arc_x * 0.9,
        y=arc_y * 0.9 + 0.5,
        mode='lines',
        line=dict(color='rgba(100,100,100,0.2)', width=15),
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=2)
    
    # Filled arc based on probability
    fill_idx = int(trigger_prob * 50)
    if fill_idx > 0:
        # Color gradient based on probability
        if trigger_prob >= 0.5:
            arc_color = COLORS["accent_green"]
        elif trigger_prob >= 0.3:
            arc_color = COLORS["accent_yellow"]
        else:
            arc_color = COLORS["text_muted"]
        
        fig.add_trace(go.Scatter(
            x=arc_x[:fill_idx] * 0.9,
            y=arc_y[:fill_idx] * 0.9 + 0.5,
            mode='lines',
            line=dict(color=arc_color, width=15),
            showlegend=False,
            hoverinfo='skip'
        ), row=1, col=2)
    
    # Probability value in center
    fig.add_annotation(
        x=0, y=0.5,
        text=f"<b>{trigger_prob:.0%}</b>",
        font=dict(size=28, color=COLORS["text_primary"]),
        showarrow=False,
        row=1, col=2
    )
    fig.add_annotation(
        x=0, y=0.2,
        text="5-Day Trigger",
        font=dict(size=10, color=COLORS["text_secondary"]),
        showarrow=False,
        row=1, col=2
    )
    
    # Additional stats below
    stats_y = -0.3
    fig.add_annotation(
        x=0, y=stats_y,
        text=f"<b>Expected Move</b><br>+{expected_move:.0%} ({ci_90[0]:.0%} to {ci_90[1]:.0%})",
        font=dict(size=10, color=COLORS["text_secondary"]),
        showarrow=False,
        row=1, col=2
    )
    
    fig.add_annotation(
        x=0, y=stats_y - 0.35,
        text=f"<b>10-Day Prob:</b> {trigger_prob_10d:.0%}<br><b>Signals:</b> {signal_count} elevated",
        font=dict(size=10, color=COLORS["text_secondary"]),
        showarrow=False,
        row=1, col=2
    )
    
    # Determine status
    if trigger_prob >= 0.5 and signal_count >= 2:
        status = "SQUEEZE SETUP"
        status_color = COLORS["accent_green"]
    elif trigger_prob >= 0.3:
        status = "MONITORING"
        status_color = COLORS["accent_yellow"]
    else:
        status = "NO SETUP"
        status_color = COLORS["text_muted"]
    
    fig.add_annotation(
        x=0, y=1.6,
        text=f"<b>{status}</b>",
        font=dict(size=12, color=status_color),
        showarrow=False,
        row=1, col=2
    )
    
    # Layout
    fig.update_xaxes(
        range=[-4.5, 4.5],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        row=1, col=1
    )
    fig.update_yaxes(
        range=[-0.5, len(labels)],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        row=1, col=1
    )
    fig.update_xaxes(
        range=[-1.5, 1.5],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        row=1, col=2
    )
    fig.update_yaxes(
        range=[-1, 2],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        row=1, col=2
    )
    
    fig.update_layout(
        title=dict(
            text=f"<b>{ticker}</b> Squeeze Signal Analysis",
            font=dict(size=15, color=COLORS["text_primary"]),
            x=0.5, xanchor='center'
        ),
        height=max(320, 50 + len(labels) * 45),
        margin=dict(l=120, r=30, t=70, b=40),
        plot_bgcolor=COLORS["bg_card"],
        paper_bgcolor=COLORS["bg_dark"],
        font=dict(color=COLORS["text_primary"], family="Inter, system-ui, sans-serif"),
        showlegend=False
    )
    
    # Add threshold labels
    fig.add_annotation(
        x=2, y=-0.3,
        text="Elevated →",
        font=dict(size=9, color=COLORS["accent_green"]),
        showarrow=False,
        row=1, col=1
    )
    
    return {
        "plotly": fig.to_dict(),
        "title": f"{ticker} Squeeze Signals"
    }

