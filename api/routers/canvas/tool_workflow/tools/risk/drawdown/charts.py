"""
Drawdown Charts for Canvas

Generates visualization charts for drawdown analysis.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def build_drawdown_chart(
    dates: List,
    drawdown_values: List[float],
    title_suffix: str = "Portfolio"
) -> Optional[Dict[str, Any]]:
    """Build drawdown time series chart."""
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Drawdown area
        fig.add_trace(go.Scatter(
            x=dates,
            y=[v * 100 for v in drawdown_values],
            fill='tozeroy',
            mode='lines',
            name='Drawdown',
            line=dict(color='#ef4444', width=1),
            fillcolor='rgba(239, 68, 68, 0.3)',
            hovertemplate='%{x}<br>Drawdown: %{y:.1f}%<extra></extra>'
        ))
        
        # Zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
        
        # Max drawdown highlight
        min_dd = min(drawdown_values)
        min_idx = drawdown_values.index(min_dd)
        
        fig.add_trace(go.Scatter(
            x=[dates[min_idx]],
            y=[min_dd * 100],
            mode='markers',
            name=f'Max DD: {min_dd:.1%}',
            marker=dict(color='#dc2626', size=12, symbol='circle'),
            hovertemplate=f'Max Drawdown: {min_dd:.1%}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f'{title_suffix} Drawdown',
            xaxis_title='Date',
            yaxis_title='Drawdown (%)',
            height=400,
            showlegend=True,
            legend=dict(yanchor="bottom", y=0.01, xanchor="right", x=0.99),
            hovermode='x unified',
        )
        
        fig.update_yaxes(ticksuffix='%')
        
        return {
            "id": "drawdown_chart",
            "title": f"{title_suffix} Drawdown",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build drawdown chart: {e}")
        return None


def build_underwater_chart(
    dates: List,
    portfolio_values: List[float],
    running_max: List[float],
) -> Optional[Dict[str, Any]]:
    """Build underwater equity curve chart."""
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Running maximum (high water mark)
        fig.add_trace(go.Scatter(
            x=dates,
            y=running_max,
            mode='lines',
            name='High Water Mark',
            line=dict(color='#10b981', width=2, dash='dot'),
            hovertemplate='%{x}<br>HWM: %{y:.3f}<extra></extra>'
        ))
        
        # Portfolio value
        fig.add_trace(go.Scatter(
            x=dates,
            y=portfolio_values,
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#3b82f6', width=2),
            hovertemplate='%{x}<br>Value: %{y:.3f}<extra></extra>'
        ))
        
        # Fill underwater area
        fig.add_trace(go.Scatter(
            x=dates + dates[::-1],
            y=running_max + portfolio_values[::-1],
            fill='toself',
            fillcolor='rgba(239, 68, 68, 0.2)',
            line=dict(width=0),
            name='Underwater',
            showlegend=True,
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            title='Equity Curve & High Water Mark',
            xaxis_title='Date',
            yaxis_title='Normalized Value',
            height=400,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            hovermode='x unified',
        )
        
        return {
            "id": "underwater_chart",
            "title": "Equity Curve & High Water Mark",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build underwater chart: {e}")
        return None


def build_recovery_chart(
    drawdown_periods: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build chart showing drawdown and recovery periods."""
    try:
        import plotly.graph_objects as go
        
        if not drawdown_periods:
            return None
        
        # Take top 10 worst drawdowns
        periods = sorted(drawdown_periods, key=lambda x: x['max_drawdown'])[:10]
        
        labels = []
        dd_days = []
        recovery_days = []
        max_dds = []
        
        for i, p in enumerate(periods, 1):
            start_str = p['start'].strftime('%b %Y')
            labels.append(f"#{i}: {start_str}")
            dd_days.append(p['drawdown_days'])
            recovery_days.append(p['recovery_days'] or 0)
            max_dds.append(abs(p['max_drawdown']) * 100)
        
        fig = go.Figure()
        
        # Drawdown phase
        fig.add_trace(go.Bar(
            name='Drawdown Phase',
            y=labels,
            x=dd_days,
            orientation='h',
            marker_color='#ef4444',
            text=[f"{d}d" for d in dd_days],
            textposition='inside',
            hovertemplate='%{y}<br>Drawdown: %{x} days<extra></extra>'
        ))
        
        # Recovery phase
        fig.add_trace(go.Bar(
            name='Recovery Phase',
            y=labels,
            x=recovery_days,
            orientation='h',
            marker_color='#10b981',
            text=[f"{d}d" if d else "Ongoing" for d in recovery_days],
            textposition='inside',
            hovertemplate='%{y}<br>Recovery: %{x} days<extra></extra>'
        ))
        
        fig.update_layout(
            title='Drawdown & Recovery Periods',
            xaxis_title='Days',
            yaxis_title='Event',
            height=400,
            barmode='stack',
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        )
        
        return {
            "id": "recovery_periods",
            "title": "Drawdown & Recovery Periods",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build recovery chart: {e}")
        return None
















