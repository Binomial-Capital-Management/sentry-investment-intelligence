"""
Canvas chart builders for Herding Regime Detector.

Compact visualizations for:
1. Herding Index Gauge
2. Signal Bars (4 Ising statistics)  
3. Regime Probabilities (HMM)
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Simple color palette
COLORS = {
    "green": "#22c55e",
    "amber": "#f59e0b", 
    "red": "#ef4444",
    "blue": "#3b82f6",
    "gray": "#6b7280",
}


def build_herding_gauge(herding_index: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build compact gauge for herding index (0-100%)."""
    if not herding_index:
        return None
    
    try:
        value = herding_index.get("value", 0.5) * 100
        regime = herding_index.get("regime", "NORMAL")
        
        # Determine color based on value
        if value >= 70:
            bar_color = COLORS["red"]
        elif value >= 50:
            bar_color = COLORS["amber"]
        else:
            bar_color = COLORS["green"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "indicator",
                    "mode": "gauge+number",
                    "value": value,
                    "number": {"suffix": "%", "font": {"size": 28}},
                    "gauge": {
                        "axis": {"range": [0, 100], "tickwidth": 1},
                        "bar": {"color": bar_color, "thickness": 0.7},
                        "bgcolor": "#f3f4f6",
                        "steps": [
                            {"range": [0, 40], "color": "#dcfce7"},
                            {"range": [40, 70], "color": "#fef3c7"},
                            {"range": [70, 100], "color": "#fee2e2"},
                        ],
                    }
                }],
                "layout": {
                    "title": {"text": f"Herding Index ({regime})", "font": {"size": 14}},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 10, "l": 20},
                    "paper_bgcolor": "white",
                },
            },
            "type": "gauge",
            "label": "Herding Index",
        }
    except Exception as e:
        logger.warning(f"Failed to build herding gauge: {e}")
        return None


def build_signal_bars(ising_stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart of 4 Ising statistics (percentiles)."""
    stats = ising_stats.get("ising_statistics", {})
    if not stats:
        return None
    
    try:
        # Extract percentiles for each statistic
        data = [
            ("Magnetization", stats.get("magnetization", {}).get("percentile", 0.5)),
            ("Susceptibility", stats.get("susceptibility", {}).get("percentile", 0.5)),
            ("Correlation", stats.get("correlation_length", {}).get("percentile", 0.5)),
            ("Critical Slow", stats.get("critical_slowing_down", {}).get("percentile", 0.5)),
        ]
        
        names = [d[0] for d in data]
        values = [d[1] * 100 for d in data]
        
        # Color by value
        colors = [
            COLORS["red"] if v >= 80 else COLORS["amber"] if v >= 60 else COLORS["green"]
            for v in values
        ]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": names,
                    "x": values,
                    "orientation": "h",
                    "marker": {"color": colors},
                    "text": [f"{v:.0f}%" for v in values],
                    "textposition": "inside",
                    "textfont": {"color": "white", "size": 11},
                    "hovertemplate": "<b>%{y}</b>: %{x:.0f}%ile<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Early Warning Signals", "font": {"size": 14}},
                    "xaxis": {"range": [0, 105], "title": "Percentile"},
                    "height": 200,
                    "margin": {"t": 40, "r": 20, "b": 40, "l": 90},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                    "shapes": [{
                        "type": "line", "x0": 80, "x1": 80, "y0": -0.5, "y1": 3.5,
                        "line": {"color": COLORS["red"], "width": 1, "dash": "dot"},
                    }],
                },
            },
            "type": "bar",
            "label": "Warning Signals",
        }
    except Exception as e:
        logger.warning(f"Failed to build signal bars: {e}")
        return None


def build_regime_chart(hmm_regime: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build simple bar chart of HMM regime probabilities."""
    if not hmm_regime or hmm_regime.get("status") != "success":
        return None
    
    try:
        probs = hmm_regime.get("state_probabilities", {})
        current = hmm_regime.get("current_state", "unknown")
        
        states = ["Dispersed", "Normal", "Critical"]
        values = [
            probs.get("dispersed", 0) * 100,
            probs.get("normal", 0) * 100,
            probs.get("critical", 0) * 100,
        ]
        colors = [COLORS["green"], COLORS["blue"], COLORS["red"]]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": states,
                    "x": values,
                    "orientation": "h",
                    "marker": {"color": colors},
                    "text": [f"{v:.0f}%" for v in values],
                    "textposition": "inside",
                    "textfont": {"color": "white", "size": 12},
                    "hovertemplate": "<b>%{y}</b>: %{x:.1f}%<extra></extra>",
                }],
                "layout": {
                    "title": {"text": f"Regime: {current.title()}", "font": {"size": 14}},
                    "xaxis": {"range": [0, 100], "title": "Probability (%)"},
                    "height": 160,
                    "margin": {"t": 40, "r": 20, "b": 40, "l": 80},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Regime",
        }
    except Exception as e:
        logger.warning(f"Failed to build regime chart: {e}")
        return None


def build_parameters_chart(ising_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build compact summary of T, h, J parameters."""
    if not ising_params:
        return None
    
    try:
        temp = ising_params.get("temperature", {})
        field = ising_params.get("external_field", {})
        coupling = ising_params.get("coupling", {})
        
        names = []
        values = []
        colors = []
        texts = []
        
        # Temperature (VIX)
        if temp.get("available"):
            vix = temp.get("vix_current", 0)
            T_pct = temp.get("T_percentile", 0.5) * 100
            regime = temp.get("T_regime", "NORMAL")
            names.append("T (VIX)")
            values.append(T_pct)
            colors.append(COLORS["red"] if regime == "HIGH_TEMP" else COLORS["green"] if regime == "LOW_TEMP" else COLORS["blue"])
            texts.append(f"{vix:.0f}")
        
        # External Field
        if field.get("available"):
            bias = field.get("bias", "NEUTRAL")
            breadth = field.get("breadth", 0) * 100
            names.append("h (Field)")
            values.append(min(abs(breadth), 100))
            colors.append(COLORS["green"] if "BULL" in bias else COLORS["red"] if "BEAR" in bias else COLORS["gray"])
            texts.append(bias[:4])
        
        # Coupling
        if coupling.get("available"):
            J = coupling.get("J_effective", 0) * 100
            diverge = coupling.get("divergence", False)
            names.append("J (Coupling)")
            values.append(J)
            colors.append(COLORS["red"] if diverge else COLORS["blue"])
            texts.append("DIV!" if diverge else f"{J:.0f}%")
        
        if not names:
            return None
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": names,
                    "x": values,
                    "orientation": "h",
                    "marker": {"color": colors},
                    "text": texts,
                    "textposition": "inside",
                    "textfont": {"color": "white", "size": 11},
                    "hovertemplate": "<b>%{y}</b>: %{x:.0f}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Ising Parameters", "font": {"size": 14}},
                    "xaxis": {"range": [0, 105]},
                    "height": 150,
                    "margin": {"t": 40, "r": 20, "b": 30, "l": 80},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Parameters",
        }
    except Exception as e:
        logger.warning(f"Failed to build parameters chart: {e}")
        return None
