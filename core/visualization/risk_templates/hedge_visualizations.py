"""
Hedge Portfolio Visualizations using Plotly

This module contains all visualization functions for hedge portfolio analysis.
Migrated from matplotlib to plotly for interactive visualizations.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Tuple


class HedgePortfolioVisualizations:
    """Interactive visualization methods for hedge portfolio analysis using Plotly."""
    
    @staticmethod
    def plot_hedge_analysis(original_betas: Dict[str, float],
                          hedged_betas: Dict[str, float],
                          hedge_weights: Dict[str, float],
                          figsize: Tuple[int, int] = (14, 10)) -> go.Figure:
        """
        Visualize hedge portfolio analysis with before/after factor exposures.
        
        Args:
            original_betas: Original portfolio factor exposures
            hedged_betas: Hedged portfolio factor exposures
            hedge_weights: Hedge portfolio weights
            figsize: Figure size tuple
            
        Returns:
            Plotly Figure object
        """
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Factor Exposures: Before vs After Hedge',
                'Hedge Portfolio Composition',
                'Factor Neutralization Effectiveness',
                'Risk Reduction Summary'
            ),
            specs=[
                [{"type": "bar"}, {"type": "pie"}],
                [{"type": "bar"}, {"type": "table"}]
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.12
        )
        
        # 1. Factor Exposures Comparison
        factors = list(original_betas.keys())
        original_values = list(original_betas.values())
        hedged_values = list(hedged_betas.values())
        
        # Original exposures
        fig.add_trace(
            go.Bar(
                name='Original',
                x=factors,
                y=original_values,
                marker_color='lightblue',
                hovertemplate='%{x}<br>Original Beta: %{y:.3f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Hedged exposures
        fig.add_trace(
            go.Bar(
                name='Hedged',
                x=factors,
                y=hedged_values,
                marker_color='darkgreen',
                hovertemplate='%{x}<br>Hedged Beta: %{y:.3f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1, row=1, col=1)
        
        # 2. Hedge Portfolio Composition (Pie Chart)
        # Filter and sort hedge weights
        significant_weights = {k: v for k, v in hedge_weights.items() if abs(v) > 0.01}
        sorted_weights = dict(sorted(significant_weights.items(), key=lambda x: abs(x[1]), reverse=True))
        
        labels = list(sorted_weights.keys())
        values = [abs(v) for v in sorted_weights.values()]
        colors = ['red' if sorted_weights[k] < 0 else 'green' for k in labels]
        
        fig.add_trace(
            go.Pie(
                labels=[f"{k} ({'Short' if sorted_weights[k] < 0 else 'Long'})" for k in labels],
                values=values,
                marker=dict(colors=colors),
                textinfo='label+percent',
                hovertemplate='%{label}<br>Weight: %{value:.1%}<extra></extra>'
            ),
            row=1, col=2
        )
        
        # 3. Factor Neutralization Effectiveness
        neutralization = [(1 - abs(hedged_betas[f]) / abs(original_betas[f])) * 100 
                         if original_betas[f] != 0 else 100 
                         for f in factors]
        
        fig.add_trace(
            go.Bar(
                x=factors,
                y=neutralization,
                marker_color=['green' if n > 80 else 'orange' if n > 50 else 'red' for n in neutralization],
                text=[f'{n:.0f}%' for n in neutralization],
                textposition='outside',
                hovertemplate='%{x}<br>Neutralization: %{y:.1f}%<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )
        
        # 4. Risk Reduction Summary Table
        # Calculate summary statistics
        orig_total_exposure = sum(abs(b) for b in original_betas.values())
        hedged_total_exposure = sum(abs(b) for b in hedged_betas.values())
        reduction_pct = (1 - hedged_total_exposure / orig_total_exposure) * 100 if orig_total_exposure > 0 else 0
        
        summary_data = [
            ['Total Absolute Exposure (Original)', f'{orig_total_exposure:.3f}'],
            ['Total Absolute Exposure (Hedged)', f'{hedged_total_exposure:.3f}'],
            ['Exposure Reduction', f'{reduction_pct:.1f}%'],
            ['Number of Hedge Positions', str(len(significant_weights))],
            ['Largest Hedge Position', f'{max(abs(v) for v in hedge_weights.values()):.1%}']
        ]
        
        fig.add_trace(
            go.Table(
                header=dict(
                    values=['<b>Metric</b>', '<b>Value</b>'],
                    fill_color='darkblue',
                    font=dict(color='white', size=12),
                    align='left'
                ),
                cells=dict(
                    values=list(zip(*summary_data)),
                    fill_color='lightgray',
                    align='left',
                    height=30
                )
            ),
            row=2, col=2
        )
        
        # Update subplot layouts
        fig.update_xaxes(title_text="Factor", row=1, col=1)
        fig.update_yaxes(title_text="Beta", row=1, col=1)
        
        fig.update_xaxes(title_text="Factor", row=2, col=1)
        fig.update_yaxes(title_text="Neutralization %", range=[0, 105], row=2, col=1)
        
        # Update overall layout
        fig.update_layout(
            title={
                'text': 'Hedge Portfolio Analysis',
                'font': {'size': 18},
                'x': 0.5,
                'xanchor': 'center'
            },
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5
            ),
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig
    
    @staticmethod
    def plot_hedge_impact_analysis(portfolio_metrics: Dict[str, float],
                                 hedged_metrics: Dict[str, float],
                                 figsize: Tuple[int, int] = (10, 6)) -> go.Figure:
        """
        Compare portfolio metrics before and after hedging.
        
        Args:
            portfolio_metrics: Metrics for original portfolio
            hedged_metrics: Metrics for hedged portfolio
            figsize: Figure size tuple
            
        Returns:
            Plotly Figure object
        """
        # Prepare data
        metrics = list(portfolio_metrics.keys())
        original = list(portfolio_metrics.values())
        hedged = list(hedged_metrics.values())
        
        # Create figure
        fig = go.Figure()
        
        # Add original metrics
        fig.add_trace(go.Bar(
            name='Original Portfolio',
            x=metrics,
            y=original,
            marker_color='lightblue',
            text=[f'{v:.2%}' if v < 1 else f'{v:.2f}' for v in original],
            textposition='outside'
        ))
        
        # Add hedged metrics
        fig.add_trace(go.Bar(
            name='Hedged Portfolio',
            x=metrics,
            y=hedged,
            marker_color='darkgreen',
            text=[f'{v:.2%}' if v < 1 else f'{v:.2f}' for v in hedged],
            textposition='outside'
        ))
        
        # Update layout
        fig.update_layout(
            title='Portfolio Metrics: Before vs After Hedging',
            xaxis_title='Metric',
            yaxis_title='Value',
            barmode='group',
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
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