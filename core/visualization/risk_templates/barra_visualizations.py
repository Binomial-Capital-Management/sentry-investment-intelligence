"""
Barra Factor Model Visualizations using Plotly

This module contains all visualization functions for the Barra factor model.
Migrated from matplotlib to plotly for interactive visualizations.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Tuple, Optional
import os


class BarraVisualizations:
    """Interactive visualization methods for Barra factor model results using Plotly."""
    
    @staticmethod
    def plot_factor_exposures(factor_exposures: pd.DataFrame,
                            ticker_subset: Optional[List[str]] = None, 
                            figsize: Tuple[int, int] = (14, 7)) -> go.Figure:
        """
        Visualize factor exposures (betas) as an interactive heatmap.
        Shows how much each asset is exposed to each risk factor.
        
        Args:
            factor_exposures: DataFrame with assets as rows, factors as columns
            ticker_subset: Optional list of tickers to display
            figsize: Figure size tuple (width, height in inches)
            
        Returns:
            plotly Figure object
        """
        if factor_exposures is None:
            raise ValueError("No factor exposures provided")
        
        # Select subset of tickers if specified
        if ticker_subset:
            exposures = factor_exposures.loc[ticker_subset]
        else:
            exposures = factor_exposures
        
        # Convert to numeric and fill NaNs
        exposures = exposures.astype(float).fillna(0)
        
        # Determine appropriate scale based on data
        max_exposure = max(abs(exposures.values.min()), abs(exposures.values.max()))
        vmax = min(2.0, max(1.0, np.ceil(max_exposure * 10) / 10))
        
        # Create heatmap with custom colorscale (RdBu reversed)
        fig = go.Figure(data=go.Heatmap(
            z=exposures.values,
            x=exposures.columns,
            y=exposures.index,
            colorscale='RdBu_r',
            zmid=0,
            zmin=-vmax,
            zmax=vmax,
            text=np.round(exposures.values, 2),
            texttemplate='%{text}',
            textfont={"size": 12},
            hovertemplate='Asset: %{y}<br>Factor: %{x}<br>Beta: %{z:.3f}<extra></extra>',
            colorbar=dict(
                title=dict(text="Factor Beta", side="right"),
                tickmode="linear",
                tick0=-vmax,
                dtick=vmax/2,
                thickness=20,
                len=0.9
            )
        ))
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Portfolio Factor Exposures',
                'font': {'size': 18, 'family': 'Arial, sans-serif'},
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                title='Market Factors',
                tickangle=45,
                side='bottom',
                showgrid=False
            ),
            yaxis=dict(
                title='Portfolio Holdings',
                showgrid=False
            ),
            width=figsize[0] * 80,  # Convert inches to pixels (approximate)
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family='Arial, sans-serif', size=12)
        )
        
        return fig
    
    @staticmethod
    def plot_risk_decomposition(risk_decomp: Dict,
                              figsize: Tuple[int, int] = (12, 6)) -> go.Figure:
        """
        Interactive portfolio risk decomposition visualization.
        
        Args:
            risk_decomp: Risk decomposition dictionary from calculate_portfolio_risk()
            figsize: Figure size tuple
            
        Returns:
            plotly Figure object
        """
        # Calculate values
        total_vol = risk_decomp['total_risk'] * 100
        systematic_vol = risk_decomp['factor_risk'] * 100
        idiosyncratic_vol = risk_decomp['specific_risk'] * 100
        
        # Variance percentages
        systematic_var_pct = risk_decomp['risk_decomposition']['systematic'] * 100
        idiosyncratic_var_pct = risk_decomp['risk_decomposition']['idiosyncratic'] * 100
        
        # Create figure with subplots for main chart and annotations
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.7, 0.3],
            specs=[[{"type": "bar"}, {"type": "table"}]]
        )
        
        # Risk bars
        volatilities = [total_vol, systematic_vol, idiosyncratic_vol]
        labels = ['Total Risk', 'Systematic Risk', 'Idiosyncratic Risk']
        colors = ['#1f77b4', '#004B87', '#7f7f7f']
        
        # Add bars with custom hover text
        for i, (vol, label, color) in enumerate(zip(volatilities, labels, colors)):
            hover_text = f"{label}: {vol:.1f}%"
            if i == 1:  # Systematic
                hover_text += f"<br>{systematic_var_pct:.0f}% of variance"
            elif i == 2:  # Idiosyncratic
                hover_text += f"<br>{idiosyncratic_var_pct:.0f}% of variance"
            
            fig.add_trace(
                go.Bar(
                    x=[label],
                    y=[vol],
                    name=label,
                    marker_color=color,
                    text=f'{vol:.1f}%',
                    textposition='outside',
                    hovertemplate=hover_text + '<extra></extra>',
                    showlegend=False
                ),
                row=1, col=1
            )
        
        # Add variance contribution annotations inside bars
        fig.add_annotation(
            x='Systematic Risk', y=systematic_vol/2,
            text=f'<b>{systematic_var_pct:.0f}%<br>of variance</b>',
            showarrow=False,
            font=dict(color='white', size=11),
            row=1, col=1
        )
        
        fig.add_annotation(
            x='Idiosyncratic Risk', y=idiosyncratic_vol/2,
            text=f'<b>{idiosyncratic_var_pct:.0f}%<br>of variance</b>',
            showarrow=False,
            font=dict(color='white', size=11),
            row=1, col=1
        )
        
        # Top factor exposures table
        portfolio_betas = risk_decomp['portfolio_betas']
        sorted_betas = sorted(portfolio_betas.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        
        table_data = []
        for factor, beta in sorted_betas:
            sign = '+' if beta > 0 else ''
            table_data.append([factor, f'{sign}{beta:.2f}'])
        
        fig.add_trace(
            go.Table(
                header=dict(
                    values=['<b>Top Factor Exposures</b>', '<b>Beta</b>'],
                    fill_color='#004B87',
                    font=dict(color='white', size=12),
                    align='left',
                    height=30
                ),
                cells=dict(
                    values=list(zip(*table_data)) if table_data else [[], []],
                    fill_color='white',
                    font=dict(size=11),
                    align='left',
                    height=25
                )
            ),
            row=1, col=2
        )
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Portfolio Risk Decomposition',
                'font': {'size': 16},
                'x': 0.5,
                'xanchor': 'center'
            },
            showlegend=False,
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            annotations=[
                dict(
                    text=f'<i>Total Risk² ({total_vol:.1f}²) = Systematic Risk² ({systematic_vol:.1f}²) + Idiosyncratic Risk² ({idiosyncratic_vol:.1f}²)</i>',
                    xref='paper', yref='paper',
                    x=0.35, y=-0.15,
                    showarrow=False,
                    font=dict(size=11, color='#666666')
                )
            ]
        )
        
        # Update axes for the bar chart
        fig.update_xaxes(
            showgrid=False,
            showline=False,
            row=1, col=1
        )
        
        fig.update_yaxes(
            title='Annual Volatility (%)',
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=0.5,
            range=[0, max(volatilities) * 1.15],
            row=1, col=1
        )
        
        return fig
    
    @staticmethod
    def plot_factor_returns(factor_returns: pd.DataFrame,
                          lookback_days: Optional[int] = None, 
                          figsize: Tuple[int, int] = (14, 8)) -> go.Figure:
        """
        Interactive cumulative factor performance chart.
        
        Args:
            factor_returns: DataFrame of factor returns
            lookback_days: Number of days to look back
            figsize: Figure size tuple
            
        Returns:
            plotly Figure object
        """
        if factor_returns is None:
            raise ValueError("No factor returns provided")
        
        # Use default trading days if not specified
        if lookback_days is None:
            lookback_days = int(os.getenv('TRADING_DAYS', 252))
        
        # Get recent factor returns
        recent_returns = factor_returns.iloc[-lookback_days:]
        
        # Calculate cumulative returns
        cumulative_returns = (1 + recent_returns).cumprod() - 1
        
        # Define better colors for each factor
        factor_colors = {
            'Market': '#1f77b4',
            'Financials': '#2ca02c',
            'Technology': '#ff7f0e',
            'Energy': '#d62728',
            'Healthcare': '#9467bd',
            'Momentum': '#8c564b',
            'Quality': '#e377c2',
            'Low_Volatility': '#7f7f7f'
        }
        
        # Create figure
        fig = go.Figure()
        
        # Add traces for each factor
        for factor in cumulative_returns.columns:
            color = factor_colors.get(factor, '#17becf')
            fig.add_trace(go.Scatter(
                x=cumulative_returns.index,
                y=cumulative_returns[factor],
                mode='lines',
                name=factor,
                line=dict(color=color, width=2.5),
                hovertemplate=f'{factor}<br>Date: %{{x|%Y-%m-%d}}<br>Return: %{{y:.1%}}<extra></extra>'
            ))
        
        # Add reference lines
        fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1)
        fig.add_hline(y=0.1, line_dash="dot", line_color="green", opacity=0.5)
        fig.add_hline(y=-0.1, line_dash="dot", line_color="red", opacity=0.5)
        
        # Find best and worst performers
        final_returns = cumulative_returns.iloc[-1]
        best_factor = final_returns.idxmax()
        worst_factor = final_returns.idxmin()
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Risk Factor Performance Over Time<br><sub>Cumulative returns of factor ETFs</sub>',
                'font': {'size': 16},
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                title='Date',
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            yaxis=dict(
                title='Cumulative Return',
                tickformat='.0%',
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified',
            annotations=[
                dict(
                    text=f'<b>Best: {best_factor} ({final_returns[best_factor]:.1%})</b>',
                    xref='paper', yref='paper',
                    x=0.02, y=0.98,
                    showarrow=False,
                    bgcolor='lightgreen',
                    bordercolor='green',
                    borderwidth=1,
                    font=dict(size=11)
                ),
                dict(
                    text=f'<b>Worst: {worst_factor} ({final_returns[worst_factor]:.1%})</b>',
                    xref='paper', yref='paper',
                    x=0.02, y=0.91,
                    showarrow=False,
                    bgcolor='lightcoral',
                    bordercolor='red',
                    borderwidth=1,
                    font=dict(size=11)
                )
            ]
        )
        
        return fig
    
    @staticmethod
    def plot_r_squared_distribution(r_squared: pd.Series,
                                  figsize: Tuple[int, int] = (10, 6)) -> go.Figure:
        """
        Interactive R-squared distribution chart.
        
        Args:
            r_squared: Series of R-squared values by asset
            figsize: Figure size tuple
            
        Returns:
            plotly Figure object
        """
        if r_squared is None:
            raise ValueError("No R-squared values provided")
        
        # Sort R-squared values descending
        r2_sorted = r_squared.sort_values(ascending=False)
        
        # Create gradient colors based on R² values
        colors = []
        for r2 in r2_sorted.values:
            if r2 >= 0.7:
                colors.append('#003f7f')  # Dark cobalt for high R²
            elif r2 >= 0.5:
                colors.append('#004B87')  # Medium cobalt
            else:
                colors.append('#5B9BD5')  # Light cobalt for low R²
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=list(range(len(r2_sorted))),
                y=r2_sorted.values,
                text=[f'{r2:.0%}' for r2 in r2_sorted.values],
                textposition='outside',
                marker_color=colors,
                customdata=r2_sorted.index,
                hovertemplate='Asset: %{customdata}<br>R²: %{y:.1%}<extra></extra>'
            )
        ])
        
        # Add threshold line
        fig.add_hline(y=0.5, line_dash="dash", line_color="#666666", 
                     annotation_text="50% Threshold", annotation_position="right")
        
        # Calculate average R²
        avg_r2 = r_squared.mean()
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Factor Model Quality by Asset',
                'font': {'size': 15},
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                tickmode='array',
                tickvals=list(range(len(r2_sorted))),
                ticktext=r2_sorted.index,
                showgrid=False
            ),
            yaxis=dict(
                title='R² (Explanatory Power)',
                tickformat='.0%',
                range=[0, 1.1],
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            width=figsize[0] * 80,
            height=figsize[1] * 80,
            plot_bgcolor='white',
            paper_bgcolor='white',
            showlegend=False,
            annotations=[
                dict(
                    text=f'<b>Portfolio Average<br>R² = {avg_r2:.0%}</b>',
                    xref='paper', yref='paper',
                    x=0.98, y=0.95,
                    showarrow=False,
                    bgcolor='white',
                    bordercolor='#004B87',
                    borderwidth=2,
                    font=dict(size=12)
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
            fig.write_image(filepath, format=format, scale=2)  # scale=2 for higher resolution