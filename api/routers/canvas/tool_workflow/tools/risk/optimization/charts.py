"""
Optimization Charts for Canvas

Generates visualization charts for portfolio optimization results.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def build_efficient_frontier_chart(
    frontier_returns: List[float],
    frontier_risks: List[float],
    optimal_return: float,
    optimal_risk: float,
    method: str
) -> Optional[Dict[str, Any]]:
    """Build efficient frontier chart with optimal portfolio marked."""
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Efficient frontier line
        if frontier_returns and frontier_risks:
            fig.add_trace(go.Scatter(
                x=frontier_risks,
                y=frontier_returns,
                mode='lines',
                name='Efficient Frontier',
                line=dict(color='#3b82f6', width=3),
                hovertemplate='Risk: %{x:.1f}%<br>Return: %{y:.1f}%<extra></extra>'
            ))
        
        # Optimal portfolio point (values already in percentage form)
        fig.add_trace(go.Scatter(
            x=[optimal_risk],
            y=[optimal_return],  # Already in percentage form
            mode='markers',
            name=f'Optimal ({method.replace("_", " ").title()})',
            marker=dict(
                color='#10b981',
                size=15,
                symbol='star',
                line=dict(color='white', width=2)
            ),
            hovertemplate=f'Optimal Portfolio<br>Risk: %{{x:.1f}}%<br>Return: %{{y:.1f}}%<extra></extra>'
        ))
        
        fig.update_layout(
            title='Efficient Frontier',
            xaxis_title='Annualized Volatility (%)',
            yaxis_title='Annualized Return (%)',
            height=450,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            hovermode='closest',
        )
        
        fig.update_xaxes(ticksuffix='%')
        fig.update_yaxes(ticksuffix='%')
        
        return {
            "id": "efficient_frontier",
            "title": "Efficient Frontier",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build efficient frontier chart: {e}")
        return None


def build_weights_chart(
    tickers: List[str],
    optimal_weights: List[float],
    current_weights: Optional[List[float]] = None
) -> Optional[Dict[str, Any]]:
    """Build weights comparison chart (current vs optimal)."""
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Current weights if provided
        if current_weights:
            fig.add_trace(go.Bar(
                name='Current',
                x=tickers,
                y=[w * 100 for w in current_weights],
                marker_color='#6b7280',
                opacity=0.7,
                hovertemplate='%{x}: %{y:.1f}%<extra>Current</extra>'
            ))
        
        # Optimal weights
        fig.add_trace(go.Bar(
            name='Optimal',
            x=tickers,
            y=[w * 100 for w in optimal_weights],
            marker_color='#10b981',
            hovertemplate='%{x}: %{y:.1f}%<extra>Optimal</extra>'
        ))
        
        fig.update_layout(
            title='Portfolio Weights',
            xaxis_title='Asset',
            yaxis_title='Weight (%)',
            height=400,
            barmode='group',
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        )
        
        fig.update_yaxes(ticksuffix='%')
        fig.update_xaxes(tickangle=45)
        
        return {
            "id": "weights_comparison",
            "title": "Portfolio Weights",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build weights chart: {e}")
        return None

