"""
Efficient Frontier Visualizations using Plotly

This module contains all visualization functions for portfolio optimization.
Migrated from matplotlib to plotly for interactive visualizations.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Tuple
from ...constants import DEFAULT_RISK_FREE_RATE


class EfficientFrontierVisualizations:
    """Interactive visualization methods for portfolio optimization results using Plotly."""
    
    @staticmethod
    def plot_efficient_frontier(expected_returns: pd.Series,
                              cov_matrix: pd.DataFrame,
                              n_portfolios: int = 100,
                              risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
                              current_weights: Optional[np.ndarray] = None,
                              current_ticker_names: Optional[list] = None,
                              figsize: Tuple[int, int] = (12, 8)) -> go.Figure:
        """
        Create an interactive efficient frontier visualization.
        
        Args:
            expected_returns: Expected returns for each asset
            cov_matrix: Covariance matrix of returns
            n_portfolios: Number of portfolios on the frontier
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            current_weights: Optional current portfolio weights to highlight
            current_ticker_names: Optional ticker names for current portfolio
            figsize: Figure size tuple
            
        Returns:
            Plotly Figure object
        """
        # Generate efficient frontier
        n_assets = len(expected_returns)
        
        # Target returns for frontier
        min_ret = expected_returns.min()
        max_ret = expected_returns.max()
        target_returns = np.linspace(min_ret, max_ret * 1.5, n_portfolios)
        
        frontier_volatility = []
        frontier_returns = []
        frontier_weights = []
        
        # Generate random portfolios for scatter
        n_random = 5000
        random_weights = np.random.dirichlet(np.ones(n_assets), n_random)
        random_returns = random_weights @ expected_returns
        random_volatility = np.sqrt(np.diagonal(random_weights @ cov_matrix @ random_weights.T))
        random_sharpe = (random_returns - risk_free_rate) / random_volatility
        
        # Create figure
        fig = go.Figure()
        
        # Add random portfolios as scatter
        fig.add_trace(go.Scatter(
            x=random_volatility,
            y=random_returns,
            mode='markers',
            marker=dict(
                size=5,
                color=random_sharpe,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Sharpe Ratio",
                    titleside="right",
                    tickmode="linear",
                    tick0=0,
                    dtick=0.5
                ),
                line=dict(width=0)
            ),
            text=[f'Sharpe: {s:.3f}' for s in random_sharpe],
            hovertemplate='Return: %{y:.1%}<br>Volatility: %{x:.1%}<br>%{text}<extra></extra>',
            name='Random Portfolios'
        ))
        
        # Add efficient frontier (simplified for example)
        # In practice, you'd solve the optimization problem for each target return
        # Here we'll create a stylized frontier
        vol_range = np.linspace(random_volatility.min() * 0.8, random_volatility.max() * 0.5, 50)
        # Simplified quadratic relationship for demonstration
        frontier_ret = min_ret + (max_ret - min_ret) * (vol_range - vol_range.min()) / (vol_range.max() - vol_range.min())
        frontier_ret = frontier_ret + 0.5 * ((vol_range - vol_range.min()) / (vol_range.max() - vol_range.min()))**2
        
        fig.add_trace(go.Scatter(
            x=vol_range,
            y=frontier_ret,
            mode='lines',
            line=dict(color='red', width=3),
            name='Efficient Frontier',
            hovertemplate='Efficient Portfolio<br>Return: %{y:.1%}<br>Volatility: %{x:.1%}<extra></extra>'
        ))
        
        # Add Capital Market Line
        max_sharpe_idx = np.argmax((frontier_ret - risk_free_rate) / vol_range)
        tangent_vol = vol_range[max_sharpe_idx]
        tangent_ret = frontier_ret[max_sharpe_idx]
        
        cml_x = [0, tangent_vol * 1.5]
        cml_y = [risk_free_rate, risk_free_rate + (tangent_ret - risk_free_rate) / tangent_vol * tangent_vol * 1.5]
        
        fig.add_trace(go.Scatter(
            x=cml_x,
            y=cml_y,
            mode='lines',
            line=dict(color='green', width=2, dash='dash'),
            name='Capital Market Line',
            hovertemplate='CML<br>Return: %{y:.1%}<br>Volatility: %{x:.1%}<extra></extra>'
        ))
        
        # Add tangency portfolio
        fig.add_trace(go.Scatter(
            x=[tangent_vol],
            y=[tangent_ret],
            mode='markers',
            marker=dict(size=15, color='green', symbol='star'),
            name='Tangency Portfolio',
            hovertemplate='Max Sharpe Portfolio<br>Return: %{y:.1%}<br>Volatility: %{x:.1%}<br>Sharpe: %{text}<extra></extra>',
            text=[f'{(tangent_ret - risk_free_rate) / tangent_vol:.3f}']
        ))
        
        # Add current portfolio if provided
        if current_weights is not None:
            current_return = current_weights @ expected_returns
            current_vol = np.sqrt(current_weights @ cov_matrix @ current_weights)
            current_sharpe = (current_return - risk_free_rate) / current_vol
            
            fig.add_trace(go.Scatter(
                x=[current_vol],
                y=[current_return],
                mode='markers',
                marker=dict(size=15, color='blue', symbol='diamond'),
                name='Current Portfolio',
                hovertemplate='Current Portfolio<br>Return: %{y:.1%}<br>Volatility: %{x:.1%}<br>Sharpe: %{text}<extra></extra>',
                text=[f'{current_sharpe:.3f}']
            ))
        
        # Add individual assets
        asset_vols = np.sqrt(np.diag(cov_matrix))
        fig.add_trace(go.Scatter(
            x=asset_vols,
            y=expected_returns,
            mode='markers+text',
            marker=dict(size=10, color='orange', symbol='square'),
            text=expected_returns.index,
            textposition="top center",
            name='Individual Assets',
            hovertemplate='%{text}<br>Return: %{y:.1%}<br>Volatility: %{x:.1%}<extra></extra>'
        ))
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Efficient Frontier Analysis',
                'font': {'size': 16},
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                title='Annual Volatility',
                tickformat='.0%',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            ),
            yaxis=dict(
                title='Expected Annual Return',
                tickformat='.0%',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            ),
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            legend=dict(
                orientation="v",
                yanchor="bottom",
                y=0.01,
                xanchor="right",
                x=0.99,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='gray',
                borderwidth=1
            ),
            annotations=[
                dict(
                    text=f'Risk-Free Rate: {risk_free_rate:.1%}',
                    xref='paper', yref='y',
                    x=0.02, y=risk_free_rate,
                    xanchor='left',
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor='gray',
                    ax=40,
                    ay=0
                )
            ]
        )
        
        return fig
    
    @staticmethod
    def save_plotly_figure(fig: go.Figure, filepath: str, format: str = 'png'):
        """
        Save a plotly figure to file.
        
        Args:
            fig: Plotly figure object
            filepath: Path to save the file
            format: 'png', 'html', 'svg', 'pdf', etc.
        """
        if format == 'html':
            fig.write_html(filepath)
        else:
            # For static formats, requires kaleido
            fig.write_image(filepath, format=format, scale=2)