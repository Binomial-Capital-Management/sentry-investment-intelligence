"""
Reverse DCF Charts for Canvas

Generates visualization charts for Reverse DCF analysis.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_growth_waterfall_chart(
    ticker: str,
    implied_growth: float,
    terminal_growth: float,
    current_price: float,
    calculated_value: float,
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing growth rate breakdown."""
    try:
        import plotly.graph_objects as go
        
        # Growth rate comparison
        categories = ['Market-Implied', 'Terminal (Perpetuity)', 'Growth Premium']
        values = [implied_growth * 100, terminal_growth * 100, (implied_growth - terminal_growth) * 100]
        colors = ['#3b82f6', '#6b7280', '#10b981']
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f'{v:.1f}%' for v in values],
            textposition='outside',
            hovertemplate='%{x}: %{y:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title=f'{ticker} - Implied Growth Rate Analysis',
            yaxis_title='Growth Rate (%)',
            height=400,
            showlegend=False,
        )
        
        fig.update_yaxes(ticksuffix='%')
        
        return {
            "id": "growth_waterfall",
            "title": f"{ticker} Implied Growth Analysis",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build growth waterfall chart: {e}")
        return None


def build_sensitivity_heatmap(
    sensitivity_grid: Dict[str, Any],
    current_implied_growth: float,
    current_discount_rate: float,
) -> Optional[Dict[str, Any]]:
    """Build sensitivity heatmap for discount rate vs terminal growth."""
    try:
        import plotly.graph_objects as go
        import numpy as np
        
        if not sensitivity_grid:
            return None
        
        # Extract data for heatmap
        dr_labels = list(sensitivity_grid.keys())
        tg_labels = list(next(iter(sensitivity_grid.values())).keys()) if sensitivity_grid else []
        
        z_data = []
        for dr in dr_labels:
            row = []
            for tg in tg_labels:
                val = sensitivity_grid.get(dr, {}).get(tg, 0)
                row.append(val * 100 if val else 0)  # Convert to percentage
            z_data.append(row)
        
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=tg_labels,
            y=dr_labels,
            colorscale='RdYlGn_r',  # Red for high growth (risk), green for low
            text=[[f'{v:.1f}%' for v in row] for row in z_data],
            texttemplate='%{text}',
            textfont={"size": 10},
            hovertemplate='Discount Rate: %{y}<br>Terminal Growth: %{x}<br>Implied Growth: %{z:.1f}%<extra></extra>',
            colorbar=dict(title='Implied Growth %')
        ))
        
        fig.update_layout(
            title='Sensitivity: Implied Growth vs Parameters',
            xaxis_title='Terminal Growth Rate',
            yaxis_title='Discount Rate',
            height=400,
        )
        
        return {
            "id": "sensitivity_heatmap",
            "title": "Growth Rate Sensitivity",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build sensitivity heatmap: {e}")
        return None
















