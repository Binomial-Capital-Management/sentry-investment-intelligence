"""Chart builders for Delta Hedge Canvas tool."""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

COLORS = {
    "primary": "#1e3a5f",
    "positive": "#059669",
    "negative": "#dc2626",
    "warning": "#f59e0b",
    "accent": "#3b82f6",
    "purple": "#8b5cf6",
    "grid": "#e2e8f0",
}


def build_hedge_comparison_chart(
    current_delta: float,
    residual_delta: float,
    target_delta: float,
    hedge_strategies: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Build gauge + indicator chart showing delta before/after hedge."""
    try:
        # Calculate hedge effectiveness
        delta_reduction = abs(current_delta) - abs(residual_delta)
        effectiveness_pct = (delta_reduction / abs(current_delta) * 100) if current_delta != 0 else 0
        
        # Determine colors based on how close to target
        if abs(residual_delta - target_delta) < 0.1:
            gauge_color = COLORS["positive"]
        elif abs(residual_delta - target_delta) < 0.5:
            gauge_color = COLORS["warning"]
        else:
            gauge_color = COLORS["negative"]
        
        # Build indicator showing before → after
        data = [
            # Main gauge showing residual delta position
            {
                "type": "indicator",
                "mode": "gauge+number+delta",
                "value": residual_delta,
                "title": {"text": "Residual Delta", "font": {"size": 16, "color": COLORS["primary"]}},
                "delta": {"reference": current_delta, "position": "bottom", "relative": False},
                "gauge": {
                    "axis": {
                        "range": [min(-abs(current_delta) * 1.2, residual_delta * 1.2), 
                                  max(abs(current_delta) * 1.2, residual_delta * 1.2)],
                        "tickwidth": 1
                    },
                    "bar": {"color": gauge_color, "thickness": 0.75},
                    "steps": [
                        {"range": [-0.5, 0.5], "color": "#d1fae5"},  # Near neutral zone
                    ],
                    "threshold": {
                        "line": {"color": COLORS["positive"], "width": 4},
                        "thickness": 0.75,
                        "value": target_delta
                    }
                },
                "domain": {"x": [0, 0.45], "y": [0.2, 1]}
            },
            # Hedge effectiveness indicator
            {
                "type": "indicator",
                "mode": "number+delta",
                "value": effectiveness_pct,
                "number": {"suffix": "%", "font": {"size": 40, "color": COLORS["positive"] if effectiveness_pct > 80 else COLORS["warning"]}},
                "title": {"text": "Hedge Effectiveness", "font": {"size": 14, "color": COLORS["primary"]}},
                "delta": {"reference": 100, "position": "bottom", "suffix": "%"},
                "domain": {"x": [0.55, 1], "y": [0.55, 1]}
            },
        ]
        
        # Add hedge instrument info as annotation
        annotations = []
        if hedge_strategies:
            single_strategies = [s for s in hedge_strategies if s.get('strategy_type') == 'single_instrument']
            if single_strategies:
                hedge_text = "<br>".join([
                    f"<b>{s['ticker']}</b>: {s['quantity']:,.0f} shares (${s['notional_value']:,.0f})"
                    for s in single_strategies[:3]
                ])
                annotations.append({
                    "x": 0.77,
                    "y": 0.35,
                    "xref": "paper",
                    "yref": "paper",
                    "text": f"<b>Hedge Instruments</b><br>{hedge_text}",
                    "showarrow": False,
                    "font": {"size": 12, "color": COLORS["primary"]},
                    "align": "center",
                    "bgcolor": "rgba(255,255,255,0.9)",
                    "bordercolor": COLORS["grid"],
                    "borderwidth": 1,
                    "borderpad": 8
                })
        
        layout = {
            "height": 400,
            "margin": {"l": 30, "r": 30, "t": 40, "b": 30},
            "paper_bgcolor": "white",
            "annotations": annotations,
        }
        
        return {
            "id": "hedge_comparison",
            "title": "Delta Hedge Analysis",
            "plotly": {"data": data, "layout": layout}
        }
    except Exception as e:
        logger.warning(f"Hedge comparison chart failed: {e}")
        return None


def build_delta_breakdown_chart(
    position_details: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing delta contribution by position."""
    try:
        if not position_details:
            return None
        
        # Extract position data
        labels = []
        deltas = []
        
        for pos in position_details[:12]:  # Limit to 12 positions
            ticker = pos.get('underlying', pos.get('ticker', 'Unknown'))
            opt_type = pos.get('option_type', 'call')[0].upper()
            strike = pos.get('strike', 0)
            
            label = f"{ticker} {opt_type}{strike:.0f}"
            labels.append(label)
            deltas.append(pos.get('position_delta', pos.get('delta', 0)))
        
        if not deltas or all(d == 0 for d in deltas):
            return None
        
        # Add total
        labels.append("Total")
        total_delta = sum(deltas)
        
        # Build waterfall
        measures = ["relative"] * len(deltas) + ["total"]
        
        return {
            "id": "delta_breakdown",
            "title": "Delta Contribution by Position",
            "plotly": {
                "data": [{
                    "type": "waterfall",
                    "orientation": "v",
                    "x": labels,
                    "y": deltas + [total_delta],
                    "measure": measures,
                    "textposition": "outside",
                    "text": [f"{d:+.2f}" for d in deltas] + [f"{total_delta:.2f}"],
                    "connector": {"line": {"color": COLORS["grid"], "width": 1}},
                    "decreasing": {"marker": {"color": COLORS["negative"]}},
                    "increasing": {"marker": {"color": COLORS["positive"]}},
                    "totals": {"marker": {"color": COLORS["primary"]}},
                    "hovertemplate": "<b>%{x}</b><br>Delta: %{y:+.4f}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Delta Contribution Waterfall", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "", "tickangle": 45},
                    "yaxis": {"title": "Delta Contribution", "gridcolor": COLORS["grid"]},
                    "height": 400,
                    "margin": {"l": 60, "r": 40, "t": 60, "b": 120},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "showlegend": False,
                }
            }
        }
    except Exception as e:
        logger.warning(f"Delta breakdown chart failed: {e}")
        return None


def build_hedge_instruments_chart(
    hedge_strategies: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Build treemap showing hedge instrument allocation."""
    try:
        single_strategies = [s for s in hedge_strategies if s.get('strategy_type') == 'single_instrument']
        if not single_strategies:
            return None
        
        labels = []
        parents = []
        values = []
        colors = []
        hover_text = []
        
        # Root
        labels.append("Hedge Portfolio")
        parents.append("")
        values.append(0)
        colors.append(COLORS["primary"])
        hover_text.append("")
        
        for s in single_strategies:
            ticker = s['ticker']
            notional = abs(s.get('notional_value', 0))
            qty = s.get('quantity', 0)
            price = s.get('current_price', 0)
            beta = s.get('beta', 1)
            
            labels.append(ticker)
            parents.append("Hedge Portfolio")
            values.append(notional)
            colors.append(COLORS["negative"] if qty < 0 else COLORS["positive"])
            hover_text.append(
                f"<b>{ticker}</b><br>"
                f"Quantity: {qty:,.0f}<br>"
                f"Price: ${price:.2f}<br>"
                f"Beta: {beta:.2f}<br>"
                f"Notional: ${notional:,.0f}"
            )
        
        return {
            "id": "hedge_instruments",
            "title": "Hedge Allocation",
            "plotly": {
                "data": [{
                    "type": "treemap",
                    "labels": labels,
                    "parents": parents,
                    "values": values,
                    "marker": {"colors": colors},
                    "hovertext": hover_text,
                    "hoverinfo": "text",
                    "textinfo": "label+value",
                    "texttemplate": "<b>%{label}</b><br>$%{value:,.0f}",
                }],
                "layout": {
                    "title": {"text": "Hedge Instrument Allocation", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "height": 350,
                    "margin": {"l": 10, "r": 10, "t": 50, "b": 10},
                    "paper_bgcolor": "white",
                }
            }
        }
    except Exception as e:
        logger.warning(f"Hedge instruments chart failed: {e}")
        return None
