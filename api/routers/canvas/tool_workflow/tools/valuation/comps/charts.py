"""
Comparable Companies Charts for Canvas

Football field and peer comparison visualizations.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def build_football_field_chart(
    target: str,
    current_price: float,
    valuation_ranges: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build football field valuation chart."""
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        methods = []
        bear_cases = []
        base_cases = []
        bull_cases = []
        
        for vr in valuation_ranges:
            methods.append(vr.get("method", "Unknown"))
            bear_cases.append(vr.get("bear_case", 0))
            base_cases.append(vr.get("base_case", 0))
            bull_cases.append(vr.get("bull_case", 0))
        
        # Create range bars
        for i, method in enumerate(methods):
            bear = bear_cases[i]
            base = base_cases[i]
            bull = bull_cases[i]
            
            # Range bar from bear to bull
            fig.add_trace(go.Bar(
                name=method,
                y=[method],
                x=[bull - bear],
                base=[bear],
                orientation='h',
                marker=dict(
                    color='rgba(59, 130, 246, 0.3)',
                    line=dict(color='#3b82f6', width=1)
                ),
                hovertemplate=f'{method}<br>Bear: ${bear:.0f}<br>Bull: ${bull:.0f}<extra></extra>',
                showlegend=False,
            ))
            
            # Base case marker
            fig.add_trace(go.Scatter(
                x=[base],
                y=[method],
                mode='markers',
                marker=dict(color='#3b82f6', size=12, symbol='diamond'),
                name='Base Case',
                hovertemplate=f'Base Case: ${base:.0f}<extra></extra>',
                showlegend=i == 0,
            ))
        
        # Current price line
        fig.add_vline(
            x=current_price,
            line=dict(color='#ef4444', width=2, dash='dash'),
            annotation_text=f'Current: ${current_price:.0f}',
            annotation_position='top',
        )
        
        fig.update_layout(
            title=f'{target} Valuation Football Field',
            xaxis_title='Share Price ($)',
            height=max(300, len(methods) * 60 + 100),
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
            bargap=0.3,
        )
        
        fig.update_xaxes(tickprefix='$')
        
        return {
            "id": "football_field",
            "title": "Football Field Valuation",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build football field chart: {e}")
        return None


def build_multiples_comparison_chart(
    target: str,
    peer_stats: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build peer multiples comparison chart."""
    try:
        import plotly.graph_objects as go
        
        multiples = list(peer_stats.keys())
        target_values = []
        peer_medians = []
        
        for mult in multiples:
            stats = peer_stats[mult]
            target_values.append(stats.get("target_value", 0))
            peer_medians.append(stats.get("peer_median", 0))
        
        fig = go.Figure()
        
        # Target values
        fig.add_trace(go.Bar(
            name=target,
            x=multiples,
            y=target_values,
            marker_color='#3b82f6',
        ))
        
        # Peer median
        fig.add_trace(go.Bar(
            name='Peer Median',
            x=multiples,
            y=peer_medians,
            marker_color='#9ca3af',
        ))
        
        fig.update_layout(
            title=f'{target} vs Peer Multiples',
            xaxis_title='Multiple',
            yaxis_title='Value',
            height=400,
            barmode='group',
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        )
        
        return {
            "id": "multiples_comparison",
            "title": "Multiples Comparison",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build multiples chart: {e}")
        return None
