"""
Monte Carlo Simulation Visualizations using Plotly

This module contains all visualization functions for Monte Carlo simulations.
Migrated from matplotlib to plotly for interactive visualizations.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Optional, Tuple
import os
from ...constants import DEFAULT_PORTFOLIO_VALUE

class MonteCarloVisualizations:
    """Interactive visualization methods for Monte Carlo simulation results using Plotly."""
    
    @staticmethod
    def plot_monte_carlo_paths(returns: pd.DataFrame,
                             weights: np.ndarray,
                             n_simulations: int = 1000,
                             time_horizon: int = 21,
                             portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
                             confidence_levels: list = [0.95, 0.99],
                             figsize: Tuple[int, int] = (12, 8)) -> go.Figure:
        """
        Visualize Monte Carlo simulation paths with confidence intervals.
        
        Args:
            returns: Historical returns DataFrame
            weights: Portfolio weights
            n_simulations: Number of simulation paths
            time_horizon: Time horizon in days
            portfolio_value: Initial portfolio value
            confidence_levels: Confidence levels for bands
            figsize: Figure size tuple
            
        Returns:
            Plotly Figure object
        """
        # Calculate portfolio returns
        portfolio_returns = returns @ weights
        
        # Parameters for simulation
        mu = portfolio_returns.mean()
        sigma = portfolio_returns.std()
        
        # Generate random paths
        dt = 1
        paths = np.zeros((time_horizon + 1, n_simulations))
        paths[0] = portfolio_value
        
        # Use numpy's random generator for reproducibility
        np.random.seed(42)
        for t in range(1, time_horizon + 1):
            Z = np.random.standard_normal(n_simulations)
            paths[t] = paths[t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z)
        
        # Calculate percentiles
        percentiles = {}
        for level in confidence_levels:
            lower = (1 - level) / 2
            upper = 1 - lower
            percentiles[f'{int(level*100)}%_lower'] = np.percentile(paths, lower * 100, axis=1)
            percentiles[f'{int(level*100)}%_upper'] = np.percentile(paths, upper * 100, axis=1)
        
        median_path = np.percentile(paths, 50, axis=1)
        
        # Create figure
        fig = go.Figure()
        
        # Add sample paths (show only 100 for clarity)
        sample_indices = np.random.choice(n_simulations, min(100, n_simulations), replace=False)
        
        for i in sample_indices:
            fig.add_trace(go.Scatter(
                x=list(range(time_horizon + 1)),
                y=paths[:, i],
                mode='lines',
                line=dict(color='lightgray', width=0.5),
                showlegend=False,
                hovertemplate='Day: %{x}<br>Value: $%{y:,.0f}<extra></extra>'
            ))
        
        # Add confidence bands
        colors = ['rgba(255, 0, 0, 0.2)', 'rgba(255, 165, 0, 0.2)']
        for i, level in enumerate(confidence_levels):
            lower_key = f'{int(level*100)}%_lower'
            upper_key = f'{int(level*100)}%_upper'
            
            # Add confidence band
            fig.add_trace(go.Scatter(
                x=list(range(time_horizon + 1)) + list(range(time_horizon, -1, -1)),
                y=list(percentiles[upper_key]) + list(percentiles[lower_key][::-1]),
                fill='toself',
                fillcolor=colors[i],
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            # Add confidence band boundaries
            fig.add_trace(go.Scatter(
                x=list(range(time_horizon + 1)),
                y=percentiles[upper_key],
                mode='lines',
                line=dict(color='red' if i == 0 else 'orange', width=1, dash='dash'),
                name=f'{int(level*100)}% Upper',
                hovertemplate='%{y:$,.0f}<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=list(range(time_horizon + 1)),
                y=percentiles[lower_key],
                mode='lines',
                line=dict(color='red' if i == 0 else 'orange', width=1, dash='dash'),
                name=f'{int(level*100)}% Lower',
                hovertemplate='%{y:$,.0f}<extra></extra>'
            ))
        
        # Add median path
        fig.add_trace(go.Scatter(
            x=list(range(time_horizon + 1)),
            y=median_path,
            mode='lines',
            line=dict(color='blue', width=3),
            name='Median Path',
            hovertemplate='Day: %{x}<br>Median Value: $%{y:,.0f}<extra></extra>'
        ))
        
        # Add initial value reference
        fig.add_hline(y=portfolio_value, line_dash="dot", line_color="black", 
                     annotation_text=f"Initial: ${portfolio_value:,.0f}")
        
        # Calculate and display final statistics
        final_values = paths[-1]
        stats_text = (
            f"Final Value Statistics:<br>"
            f"Mean: ${np.mean(final_values):,.0f}<br>"
            f"Median: ${np.median(final_values):,.0f}<br>"
            f"Std Dev: ${np.std(final_values):,.0f}<br>"
            f"VaR 95%: ${np.percentile(final_values, 5):,.0f}<br>"
            f"VaR 99%: ${np.percentile(final_values, 1):,.0f}"
        )
        
        # Update layout
        fig.update_layout(
            title={
                'text': f'Monte Carlo Simulation<br><sub>{n_simulations:,} paths over {time_horizon} days</sub>',
                'font': {'size': 16},
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                title='Days',
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title='Portfolio Value ($)',
                tickformat='$,.0f',
                showgrid=True,
                gridcolor='lightgray'
            ),
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='gray',
                borderwidth=1
            ),
            annotations=[
                dict(
                    text=stats_text,
                    xref='paper', yref='paper',
                    x=0.98, y=0.02,
                    xanchor='right', yanchor='bottom',
                    showarrow=False,
                    bgcolor='rgba(255, 255, 255, 0.8)',
                    bordercolor='gray',
                    borderwidth=1,
                    font=dict(size=11)
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