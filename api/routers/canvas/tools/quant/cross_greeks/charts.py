"""Chart builders for Cross-Asset Greeks Canvas tool."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional


def build_greeks_by_underlying_chart(
    underlyings: List[str],
    vanna_by_underlying: Dict[str, float],
    volga_by_underlying: Dict[str, float],
    charm_by_underlying: Dict[str, float],
    veta_by_underlying: Dict[str, float],
    greeks: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Build small multiples - one chart per Greek to handle different scales.
    """
    if not underlyings:
        return None
    
    try:
        # Count active Greeks
        active_greeks = []
        if "vanna" in greeks and vanna_by_underlying:
            active_greeks.append(("Vanna", vanna_by_underlying, "#3b82f6"))
        if "volga" in greeks and volga_by_underlying:
            active_greeks.append(("Volga", volga_by_underlying, "#10b981"))
        if "charm" in greeks and charm_by_underlying:
            active_greeks.append(("Charm", charm_by_underlying, "#f59e0b"))
        if "veta" in greeks and veta_by_underlying:
            active_greeks.append(("Veta", veta_by_underlying, "#8b5cf6"))
        
        if not active_greeks:
            return None
        
        # Create subplots - 2x2 grid or 1x4 depending on count
        n = len(active_greeks)
        if n <= 2:
            rows, cols = 1, n
        else:
            rows, cols = 2, 2
        
        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[g[0] for g in active_greeks],
            horizontal_spacing=0.12,
            vertical_spacing=0.15
        )
        
        for i, (name, data, color) in enumerate(active_greeks):
            row = (i // cols) + 1
            col = (i % cols) + 1
            
            values = [data.get(u, 0) for u in underlyings]
            
            fig.add_trace(
                go.Bar(
                    x=underlyings,
                    y=values,
                    marker=dict(color=color),
                    name=name,
                    showlegend=False,
                    hovertemplate=f'<b>%{{x}}</b><br>{name}: %{{y:.4f}}<extra></extra>',
                    width=0.6
                ),
                row=row,
                col=col
            )
            
            # Add zero line
            fig.add_hline(y=0, line_dash="dot", line_color="#cbd5e1", row=row, col=col)
        
        fig.update_layout(
            title="Second-Order Greeks by Underlying",
            template="plotly_white",
            height=400 if rows == 1 else 500,
            margin=dict(t=60, b=40, l=50, r=30),
            font=dict(size=11)
        )
        
        return {
            "id": "greeks_by_underlying",
            "title": "Greeks by Underlying",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building Greeks by underlying chart: {e}")
        return None


def build_position_details_chart(
    position_details: List[Dict[str, Any]],
    greek_type: str = "vanna"
) -> Optional[Dict[str, Any]]:
    """
    Build horizontal bar chart showing position contributions.
    """
    if not position_details:
        return None
    
    try:
        greek_display = greek_type.capitalize()
        
        # Try different key patterns for the greek value
        possible_keys = [
            f"position_{greek_type}",
            greek_type,
            f"{greek_type}_contribution"
        ]
        
        # Extract data
        labels = []
        values = []
        colors = []
        
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4']
        
        for i, pos in enumerate(position_details):
            # Find the greek value
            greek_val = None
            for key in possible_keys:
                if key in pos:
                    greek_val = pos[key]
                    break
            
            if greek_val is None:
                continue
            
            underlying = pos.get("underlying", "?")
            strike = pos.get("strike", 0)
            qty = pos.get("quantity", 0)
            opt_type = pos.get("option_type", "call")[0].upper()
            
            label = f"{underlying} ${strike:.0f}{opt_type} ×{qty}"
            labels.append(label)
            values.append(greek_val)
            colors.append(color_palette[i % len(color_palette)])
        
        if not values:
            return None
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=values,
            y=labels,
            orientation='h',
            marker=dict(color=colors),
            hovertemplate=f'<b>%{{y}}</b><br>{greek_display}: %{{x:.4f}}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f"Position-Level {greek_display}",
            xaxis_title=f"{greek_display} Value",
            template="plotly_white",
            height=max(250, len(labels) * 35 + 80),
            margin=dict(l=140, r=30, t=50, b=40),
            yaxis=dict(autorange="reversed")
        )
        
        fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
        
        return {
            "id": "position_details",
            "title": f"Position {greek_display}",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building position details chart: {e}")
        return None


def build_greeks_comparison_chart(
    vanna_total: float,
    volga_total: float,
    charm_total: float,
    veta_total: float,
    greeks: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Build separate gauge/indicator for each Greek since scales are incompatible.
    """
    if not greeks:
        return None
    
    try:
        greek_data = []
        
        if "vanna" in greeks:
            greek_data.append(("Vanna", vanna_total, "#3b82f6"))
        if "volga" in greeks:
            greek_data.append(("Volga", volga_total, "#10b981"))
        if "charm" in greeks:
            greek_data.append(("Charm", charm_total, "#f59e0b"))
        if "veta" in greeks:
            greek_data.append(("Veta", veta_total, "#8b5cf6"))
        
        if not greek_data:
            return None
        
        n = len(greek_data)
        
        # Create subplots - one row, n columns
        fig = make_subplots(
            rows=1,
            cols=n,
            subplot_titles=[d[0] for d in greek_data],
            horizontal_spacing=0.08
        )
        
        for i, (name, value, color) in enumerate(greek_data):
            col = i + 1
            
            # Single bar per subplot - each has its own scale
            fig.add_trace(
                go.Bar(
                    x=[name],
                    y=[value],
                    marker=dict(color=color),
                    text=[f"{value:+,.2f}"],
                    textposition='outside',
                    textfont=dict(size=12),
                    hovertemplate=f'<b>{name}</b><br>Value: %{{y:.4f}}<extra></extra>',
                    showlegend=False,
                    width=0.5
                ),
                row=1,
                col=col
            )
            
            # Add zero line
            fig.add_hline(y=0, line_dash="dot", line_color="#cbd5e1", row=1, col=col)
            
            # Hide x-axis labels (redundant with subplot title)
            fig.update_xaxes(showticklabels=False, row=1, col=col)
        
        fig.update_layout(
            title="Portfolio Greeks Summary",
            template="plotly_white",
            height=280,
            margin=dict(l=50, r=30, t=70, b=30),
            font=dict(size=11)
        )
        
        return {
            "id": "greeks_comparison",
            "title": "Greeks Summary",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building Greeks comparison chart: {e}")
        return None
