"""
Recession Field Theory Charts for Canvas

Properly extracts and displays physics statistics data.
"""

import logging
from typing import Any, Dict, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Institutional color palette
COLORS = {
    "low_risk": "#10B981",      # Green
    "moderate": "#F59E0B",      # Amber
    "elevated": "#F97316",      # Orange
    "high_risk": "#EF4444",     # Red
    "expansion": "#10B981",
    "transition": "#F59E0B",
    "recession": "#EF4444",
    "neutral": "#6B7280",
    "background": "#FFFFFF",
    "grid": "#E5E7EB",
    "text": "#111827",
}


def build_warning_gauge_chart(
    score: float,
    label: str,
) -> Optional[Dict[str, Any]]:
    """Build gauge chart for composite warning score."""
    try:
        # Determine color
        if score >= 7:
            bar_color = COLORS["high_risk"]
        elif score >= 5:
            bar_color = COLORS["elevated"]
        elif score >= 3:
            bar_color = COLORS["moderate"]
        else:
            bar_color = COLORS["low_risk"]
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": "Recession Warning Score", "font": {"size": 16}},
            number={"suffix": "/10", "font": {"size": 28}},
            gauge={
                "axis": {"range": [0, 10], "tickwidth": 1, "tickcolor": COLORS["grid"]},
                "bar": {"color": bar_color},
                "bgcolor": COLORS["background"],
                "borderwidth": 2,
                "bordercolor": COLORS["grid"],
                "steps": [
                    {"range": [0, 3], "color": "rgba(16, 185, 129, 0.1)"},
                    {"range": [3, 5], "color": "rgba(245, 158, 11, 0.1)"},
                    {"range": [5, 7], "color": "rgba(249, 115, 22, 0.1)"},
                    {"range": [7, 10], "color": "rgba(239, 68, 68, 0.1)"},
                ],
                "threshold": {
                    "line": {"color": COLORS["text"], "width": 2},
                    "thickness": 0.8,
                    "value": score,
                },
            },
        ))
        
        fig.add_annotation(
            x=0.5, y=-0.15,
            text=f"<b>{label}</b>",
            showarrow=False,
            font={"size": 14, "color": bar_color},
            xref="paper", yref="paper",
        )
        
        fig.update_layout(
            height=280,
            margin={"l": 30, "r": 30, "t": 60, "b": 40},
            paper_bgcolor="white",
            font={"family": "Inter, system-ui, sans-serif"},
        )
        
        return {"plotly": fig.to_dict()}
        
    except Exception as e:
        logger.warning(f"Failed to build warning gauge: {e}")
        return None


def build_signals_radar_chart(
    signals: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Build radar chart showing the 4 early warning signals.
    
    Signals structure:
    {
        "critical_slowing_down": {
            "ar1_coefficient": 0.85,
            "normal_range": [0.75, 0.88],
            "signal": "NORMAL",
            ...
        },
        "correlation_length": {
            "cross_sector_correlation": 0.35,
            "normal_range": [0.20, 0.40],
            "signal": "ELEVATED",
            ...
        },
        ...
    }
    """
    try:
        # Map signal keys to display names and value keys
        signal_config = {
            "critical_slowing_down": {
                "name": "Slowing Down",
                "value_key": "ar1_coefficient",
                "normal_range": [0.75, 0.88],
            },
            "correlation_length": {
                "name": "Correlation",
                "value_key": "cross_sector_correlation",
                "normal_range": [0.20, 0.40],
            },
            "susceptibility": {
                "name": "Susceptibility",
                "value_key": "variance_ratio",
                "normal_range": [0.7, 1.3],
            },
            "spectral_dominance": {
                "name": "Spectral Dom.",
                "value_key": "first_eigenvalue_share",
                "normal_range": [0.25, 0.42],
            },
        }
        
        categories = []
        values = []
        statuses = []
        
        for signal_key, config in signal_config.items():
            signal_data = signals.get(signal_key, {})
            
            # Extract value
            raw_value = signal_data.get(config["value_key"])
            if raw_value is None:
                raw_value = 0
            
            # Normalize to 0-10 scale based on normal range
            normal_low, normal_high = config["normal_range"]
            normal_mid = (normal_low + normal_high) / 2
            normal_range = normal_high - normal_low
            
            if raw_value <= normal_low:
                normalized = 2  # Below normal = low risk
            elif raw_value >= normal_high:
                # Above normal = elevated risk, scale up to 10
                excess = (raw_value - normal_high) / normal_range
                normalized = min(10, 5 + excess * 5)
            else:
                # Within normal range = 2-5
                normalized = 2 + ((raw_value - normal_low) / normal_range) * 3
            
            # Get status
            status = signal_data.get("signal", "NORMAL").upper()
            
            categories.append(config["name"])
            values.append(max(0, min(10, normalized)))
            statuses.append(status)
        
        # Close the radar
        categories.append(categories[0])
        values.append(values[0])
        
        fig = go.Figure()
        
        # Add filled area
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            fillcolor="rgba(239, 68, 68, 0.2)",
            line={"color": COLORS["high_risk"], "width": 2},
            name="Current Signals",
        ))
        
        # Add normal threshold (5 on normalized scale)
        normal_threshold = [5] * len(categories)
        fig.add_trace(go.Scatterpolar(
            r=normal_threshold,
            theta=categories,
            fill=None,
            line={"color": COLORS["low_risk"], "width": 1, "dash": "dash"},
            name="Normal Threshold",
        ))
        
        fig.update_layout(
            polar={
                "radialaxis": {
                    "visible": True,
                    "range": [0, 10],
                    "tickvals": [0, 3, 5, 7, 10],
                    "gridcolor": COLORS["grid"],
                },
                "angularaxis": {"gridcolor": COLORS["grid"]},
                "bgcolor": "white",
            },
            showlegend=True,
            legend={"x": 0, "y": -0.15, "orientation": "h"},
            title={"text": "Early Warning Signals", "x": 0.5, "font": {"size": 14}},
            height=320,
            margin={"l": 60, "r": 60, "t": 60, "b": 60},
            paper_bgcolor="white",
            font={"family": "Inter, system-ui, sans-serif", "size": 11},
        )
        
        return {"plotly": fig.to_dict()}
        
    except Exception as e:
        logger.warning(f"Failed to build signals radar: {e}")
        return None


def build_regime_probability_chart(
    regime_probs: Dict[str, float],
    current_regime: str,
) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart showing regime probabilities."""
    try:
        # Actual regime names from HMM (4 business cycle states)
        regime_order = ["expansion", "peak", "contraction", "trough"]
        regime_display = {
            "expansion": "Expansion",
            "peak": "Peak",
            "contraction": "Contraction",
            "trough": "Trough",
        }
        regime_colors = {
            "expansion": "#10B981",   # Green
            "peak": "#3B82F6",        # Blue
            "contraction": "#F59E0B", # Amber
            "trough": "#EF4444",      # Red
        }
        
        # Build data directly from regime_probs
        regimes = []
        probs = []
        colors = []
        
        for regime in regime_order:
            prob = regime_probs.get(regime, 0)
            # Handle both 0-1 and 0-100 scales
            if isinstance(prob, (int, float)):
                if prob > 1:
                    prob = prob / 100
            else:
                prob = 0
            
            regimes.append(regime_display.get(regime, regime.title()))
            probs.append(prob * 100)
            colors.append(regime_colors.get(regime, COLORS["neutral"]))
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=regimes,
            x=probs,
            orientation="h",
            marker={"color": colors},
            text=[f"{p:.0f}%" for p in probs],
            textposition="auto",
            textfont={"color": "white", "size": 12},
        ))
        
        # Highlight current regime
        current_lower = current_regime.lower() if current_regime else ""
        for i, regime in enumerate(regime_order):
            if regime == current_lower or regime in current_lower:
                fig.add_annotation(
                    x=probs[i] + 5,
                    y=regime_display[regime],
                    text="◀ CURRENT",
                    showarrow=False,
                    font={"size": 10, "color": COLORS["text"]},
                )
                break
        
        fig.update_layout(
            title={"text": "Business Cycle Phase (HMM)", "x": 0.5, "font": {"size": 14}},
            xaxis={"title": "Probability (%)", "range": [0, 100], "gridcolor": COLORS["grid"]},
            yaxis={
                "title": None,
                "categoryorder": "array",
                "categoryarray": list(reversed([regime_display[r] for r in regime_order])),
            },
            height=220,
            margin={"l": 100, "r": 60, "t": 50, "b": 40},
            paper_bgcolor="white",
            plot_bgcolor="white",
            font={"family": "Inter, system-ui, sans-serif"},
            showlegend=False,
        )
        
        return {"plotly": fig.to_dict()}
        
    except Exception as e:
        logger.warning(f"Failed to build regime chart: {e}")
        return None


def build_signals_dashboard_chart(
    signals: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Build a 2x2 subplot dashboard showing all 4 signals with their values and status.
    """
    try:
        signal_config = {
            "critical_slowing_down": {
                "name": "Critical Slowing Down",
                "value_key": "ar1_coefficient",
                "unit": "",
                "normal_range": [0.75, 0.88],
            },
            "correlation_length": {
                "name": "Correlation Length",
                "value_key": "cross_sector_correlation",
                "unit": "",
                "normal_range": [0.20, 0.40],
            },
            "susceptibility": {
                "name": "Susceptibility",
                "value_key": "variance_ratio",
                "unit": "x",
                "normal_range": [0.7, 1.3],
            },
            "spectral_dominance": {
                "name": "Spectral Dominance",
                "value_key": "first_eigenvalue_share",
                "unit": "",
                "normal_range": [0.25, 0.42],
            },
        }
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[config["name"] for config in signal_config.values()],
            specs=[[{"type": "indicator"}, {"type": "indicator"}],
                   [{"type": "indicator"}, {"type": "indicator"}]],
            vertical_spacing=0.15,
            horizontal_spacing=0.15,
        )
        
        positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
        
        for idx, (signal_key, config) in enumerate(signal_config.items()):
            signal_data = signals.get(signal_key, {})
            raw_value = signal_data.get(config["value_key"], 0)
            status = signal_data.get("signal", "NORMAL").upper()
            normal_low, normal_high = config["normal_range"]
            
            # Determine color
            if status == "CRITICAL":
                color = COLORS["high_risk"]
            elif status == "ELEVATED":
                color = COLORS["elevated"]
            else:
                color = COLORS["low_risk"]
            
            row, col = positions[idx]
            
            fig.add_trace(
                go.Indicator(
                    mode="number+gauge",
                    value=raw_value,
                    number={"suffix": config["unit"], "font": {"size": 20, "color": color}},
                    gauge={
                        "axis": {"range": [normal_low * 0.8, normal_high * 1.2]},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [normal_low * 0.8, normal_low], "color": "rgba(16, 185, 129, 0.1)"},
                            {"range": [normal_low, normal_high], "color": "rgba(245, 158, 11, 0.1)"},
                            {"range": [normal_high, normal_high * 1.2], "color": "rgba(239, 68, 68, 0.1)"},
                        ],
                        "threshold": {
                            "line": {"color": color, "width": 2},
                            "thickness": 0.8,
                            "value": raw_value,
                        },
                    },
                    title={"text": f"<b>{status}</b>", "font": {"size": 12}},
                ),
                row=row, col=col
            )
        
        fig.update_layout(
            height=500,
            margin={"l": 20, "r": 20, "t": 60, "b": 20},
            paper_bgcolor="white",
            font={"family": "Inter, system-ui, sans-serif"},
        )
        
        return {"plotly": fig.to_dict()}
        
    except Exception as e:
        logger.warning(f"Failed to build signals dashboard: {e}")
        return None
