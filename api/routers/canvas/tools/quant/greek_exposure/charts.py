"""Chart builders for Greek Exposure Canvas tool."""

import plotly.graph_objects as go
from typing import Dict, Any, List, Optional


def build_greek_by_underlying_chart(
    by_underlying: Dict[str, float],
    greek_name: str,
    greek_symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Build horizontal bar chart showing Greek exposure by underlying.
    """
    if not by_underlying:
        return None
    
    try:
        # Sort by absolute value
        sorted_items = sorted(by_underlying.items(), key=lambda x: abs(x[1]), reverse=True)
        underlyings = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]
        
        # Color based on sign
        colors = ['#10b981' if v >= 0 else '#ef4444' for v in values]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=values,
            y=underlyings,
            orientation='h',
            marker=dict(color=colors),
            text=[f"{v:+,.2f}" for v in values],
            textposition='outside',
            textfont=dict(size=11),
            hovertemplate=f'<b>%{{y}}</b><br>{greek_name}: %{{x:+,.4f}}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f"{greek_name} ({greek_symbol}) by Underlying",
            xaxis_title=f"{greek_name} Exposure",
            template="plotly_white",
            height=max(200, len(underlyings) * 40 + 80),
            margin=dict(l=80, r=80, t=50, b=40),
            yaxis=dict(autorange="reversed")
        )
        
        fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
        
        return {
            "id": "greek_by_underlying",
            "title": f"{greek_name} by Underlying",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building greek by underlying chart: {e}")
        return None


def build_position_breakdown_chart(
    position_details: List[Dict[str, Any]],
    position_key: str,
    greek_name: str
) -> Optional[Dict[str, Any]]:
    """
    Build horizontal bar chart showing each position's Greek contribution.
    """
    if not position_details:
        return None
    
    try:
        labels = []
        values = []
        colors = []
        
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4']
        
        for i, pos in enumerate(position_details):
            greek_val = pos.get(position_key, 0)
            underlying = pos.get("underlying", "?")
            strike = pos.get("strike", 0) if "strike" in pos else 0
            qty = pos.get("quantity", 0)
            opt_type = pos.get("option_type", "call")
            
            if strike:
                opt_letter = opt_type[0].upper() if opt_type else "C"
                label = f"{underlying} ${strike:.0f}{opt_letter} ×{qty}"
            else:
                label = f"{underlying} ×{qty}"
            
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
            text=[f"{v:+,.2f}" for v in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate=f'<b>%{{y}}</b><br>{greek_name}: %{{x:+,.4f}}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f"Position-Level {greek_name}",
            xaxis_title=f"{greek_name} Contribution",
            template="plotly_white",
            height=max(250, len(labels) * 30 + 80),
            margin=dict(l=140, r=60, t=50, b=40),
            yaxis=dict(autorange="reversed")
        )
        
        fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
        
        return {
            "id": "position_breakdown",
            "title": f"Position {greek_name}",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building position breakdown chart: {e}")
        return None


def build_greek_summary_chart(
    total_value: float,
    greek_name: str,
    greek_symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Build simple indicator/gauge for total Greek exposure.
    """
    try:
        color = '#10b981' if total_value >= 0 else '#ef4444'
        
        fig = go.Figure()
        
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=total_value,
            number=dict(
                font=dict(size=48, color=color),
                valueformat="+,.2f"
            ),
            title=dict(
                text=f"Total {greek_name} ({greek_symbol})",
                font=dict(size=16)
            )
        ))
        
        fig.update_layout(
            template="plotly_white",
            height=200,
            margin=dict(l=30, r=30, t=60, b=30)
        )
        
        return {
            "id": "greek_summary",
            "title": f"Total {greek_name}",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building greek summary chart: {e}")
        return None
