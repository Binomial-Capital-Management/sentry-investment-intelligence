"""
Plotly-based chart implementations for risk analysis modules.
Replaces matplotlib visualizations with interactive Plotly charts.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from .config import VisualizationConfig

class RiskCharts:
    """Collection of Plotly-based risk analysis charts."""
    
    def __init__(self, color_scheme: str = 'binomial_blue'):
        """Initialize with a color scheme."""
        self.color_scheme = color_scheme
        self.config = VisualizationConfig()
    
    def plot_factor_exposures_heatmap(self,
                                    factor_exposures: pd.DataFrame,
                                    title: str = "Portfolio Factor Exposures",
                                    height: int = 600) -> go.Figure:
        """
        Create an interactive heatmap of factor exposures.
        Replaces matplotlib implementation with Plotly.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        # Create custom colorscale
        colorscale = [
            [0.0, colors['negative']],
            [0.5, colors['background']],
            [1.0, colors['positive']]
        ]
        
        # Determine scale
        max_exposure = max(abs(factor_exposures.values.min()), abs(factor_exposures.values.max()))
        vmax = min(2.0, max(1.0, np.ceil(max_exposure * 10) / 10))
        
        fig = go.Figure(data=go.Heatmap(
            z=factor_exposures.values.tolist(),
            x=factor_exposures.columns.tolist(),
            y=factor_exposures.index.tolist(),
            colorscale=colorscale,
            zmid=0,
            zmin=-vmax,
            zmax=vmax,
            text=factor_exposures.values.tolist(),
            texttemplate='%{text:.2f}',
            textfont={"size": self.config.FONT_SIZES['data_label']},
            colorbar=dict(
                title=dict(
                    text="Factor Beta",
                    font=dict(
                        family=', '.join(self.config.TYPEWRITER_FONTS),
                        size=self.config.FONT_SIZES['axis_title']
                    )
                ),
                tickfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['axis_label']
                )
            ),
            hovertemplate='<b>%{y}</b><br>%{x}: %{z:.3f}<extra></extra>'
        ))
        
        layout = self.config.get_layout_template(
            title=title,
            color_scheme=self.color_scheme,
            height=height,
            show_grid=False
        )
        
        # Update axes for heatmap
        layout.update(
            xaxis=dict(
                title="Market Factors",
                side="bottom",
                tickangle=-45
            ),
            yaxis=dict(
                title="Portfolio Holdings",
                autorange="reversed"  # Put first item at top
            )
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_risk_decomposition(self,
                              risk_data: Dict[str, float],
                              title: str = "Risk Decomposition",
                              height: int = 500) -> go.Figure:
        """
        Create an interactive donut chart for risk decomposition.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        # Prepare data
        labels = list(risk_data.keys())
        values = list(risk_data.values())
        
        # Create donut chart
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(
                colors=colors['primary'][:len(labels)],
                line=dict(color=colors['text'], width=2)
            ),
            textposition='auto',
            textinfo='label+percent',
            textfont=dict(
                family=', '.join(self.config.TYPEWRITER_FONTS),
                size=self.config.FONT_SIZES['data_label'],
                color=colors['text']
            ),
            hovertemplate='<b>%{label}</b><br>%{value:.2%}<br>%{percent}<extra></extra>'
        )])
        
        layout = self.config.get_layout_template(
            title=title,
            color_scheme=self.color_scheme,
            height=height,
            show_grid=False
        )
        
        # Add center annotation
        layout.annotations = [{
            'text': 'Total Risk',
            'font': {
                'family': ', '.join(self.config.TYPEWRITER_FONTS),
                'size': self.config.FONT_SIZES['subtitle'],
                'color': colors['text']
            },
            'showarrow': False
        }]
        
        fig.update_layout(layout)
        return fig
    
    def plot_efficient_frontier(self,
                              frontier_data: Dict[str, Any],
                              current_portfolio: Optional[Dict[str, float]] = None,
                              height: int = 700) -> go.Figure:
        """
        Create an interactive efficient frontier plot.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        fig = go.Figure()
        
        # Add random portfolios as colorful scatter
        if 'random_portfolios' in frontier_data:
            random = frontier_data['random_portfolios']
            fig.add_trace(go.Scatter(
                x=random['volatility'],
                y=random['returns'],
                mode='markers',
                name='Random Portfolios',
                marker=dict(
                    size=4,
                    color=random.get('sharpe_ratios', random['returns']),
                    colorscale='Viridis',  # Green-yellow colorscale like in the image
                    colorbar=dict(
                        title=dict(
                            text="Sharpe Ratio",
                            font=dict(family=', '.join(self.config.TYPEWRITER_FONTS))
                        ),
                        tickfont=dict(family=', '.join(self.config.TYPEWRITER_FONTS))
                    ),
                    line=dict(width=0),
                    opacity=0.8
                ),
                text=[f"Sharpe: {s:.2f}" for s in random.get('sharpe_ratios', [])],
                hovertemplate='<b>Random Portfolio</b><br>Risk: %{x:.2%}<br>Return: %{y:.2%}<br>%{text}<extra></extra>'
            ))
        
        # Add efficient frontier line
        if 'efficient_frontier' in frontier_data:
            frontier = frontier_data['efficient_frontier']
            fig.add_trace(go.Scatter(
                x=frontier['volatility'],
                y=frontier['returns'],
                mode='lines',
                name='Efficient Frontier',
                line=dict(
                    color='#1E40AF',  # Deep blue
                    width=4
                ),
                hovertemplate='<b>Efficient Portfolio</b><br>Risk: %{x:.2%}<br>Return: %{y:.2%}<extra></extra>'
            ))
        
        # Add special portfolios
        if 'min_variance_portfolio' in frontier_data:
            mvp = frontier_data['min_variance_portfolio']
            fig.add_trace(go.Scatter(
                x=[mvp['volatility']],
                y=[mvp['return']],
                mode='markers+text',
                name='Min Variance',
                marker=dict(
                    size=20,
                    color='#10B981',  # Green
                    symbol='circle',
                    line=dict(color='white', width=2)
                ),
                text=['Min Var'],
                textposition='top center',
                textfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['annotation']
                ),
                hovertemplate='<b>Minimum Variance Portfolio</b><br>Risk: %{x:.2%}<br>Return: %{y:.2%}<br>Sharpe: ' + f"{mvp.get('sharpe_ratio', 0):.2f}<extra></extra>"
            ))
        
        if 'max_sharpe_portfolio' in frontier_data:
            msp = frontier_data['max_sharpe_portfolio']
            fig.add_trace(go.Scatter(
                x=[msp['volatility']],
                y=[msp['return']],
                mode='markers+text',
                name='Max Sharpe',
                marker=dict(
                    size=20,
                    color='#F59E0B',  # Orange
                    symbol='circle',
                    line=dict(color='white', width=2)
                ),
                text=['Max Sharpe'],
                textposition='top center',
                textfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['annotation']
                ),
                hovertemplate='<b>Maximum Sharpe Portfolio</b><br>Risk: %{x:.2%}<br>Return: %{y:.2%}<br>Sharpe: ' + f"{msp.get('sharpe_ratio', 0):.2f}<extra></extra>"
            ))
        
        # Add current portfolio
        if current_portfolio:
            fig.add_trace(go.Scatter(
                x=[current_portfolio['volatility']],
                y=[current_portfolio['return']],
                mode='markers+text',
                name='Current Portfolio',
                marker=dict(
                    size=20,
                    color='#EF4444',  # Red
                    symbol='circle',
                    line=dict(color='white', width=2)
                ),
                text=['Current'],
                textposition='bottom center',
                textfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['annotation']
                ),
                hovertemplate='<b>Current Portfolio</b><br>Risk: %{x:.2%}<br>Return: %{y:.2%}<br>Sharpe: ' + f"{current_portfolio.get('sharpe_ratio', 0):.2f}<extra></extra>"
            ))
        
        layout = self.config.get_layout_template(
            title="Efficient Frontier Analysis",
            color_scheme=self.color_scheme,
            height=height
        )
        
        layout.update(
            xaxis=dict(
                title="Volatility (Standard Deviation)",
                tickformat=".1%"
            ),
            yaxis=dict(
                title="Expected Return",
                tickformat=".1%"
            ),
            hovermode='closest'
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_monte_carlo_simulation(self,
                                  simulation_data: Dict[str, Any],
                                  show_percentiles: List[int] = [5, 25, 50, 75, 95],
                                  height: int = 600) -> go.Figure:
        """
        Create an interactive Monte Carlo simulation visualization.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        fig = go.Figure()
        
        # Add sample paths with rainbow colors
        if 'paths' in simulation_data:
            paths = simulation_data['paths']
            n_paths_to_show = min(100, len(paths))
            sample_indices = np.random.choice(len(paths), n_paths_to_show, replace=False)
            
            # Create proper rainbow colors using HSV color space
            import colorsys
            rainbow_colors = []
            for i in range(n_paths_to_show):
                hue = i / n_paths_to_show  # Distribute hues evenly from 0 to 1
                # Convert HSV to RGB (full saturation and value for bright colors)
                rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
                hex_color = '#{:02x}{:02x}{:02x}'.format(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
                rainbow_colors.append(hex_color)
            
            # Shuffle for better distribution
            np.random.shuffle(rainbow_colors)
            
            for i, idx in enumerate(sample_indices):
                path_data = paths[idx]
                # Paths are already indexed to base 100
                
                fig.add_trace(go.Scatter(
                    x=simulation_data['time_points'],
                    y=path_data.tolist() if hasattr(path_data, 'tolist') else path_data,
                    mode='lines',
                    line=dict(color=rainbow_colors[i], width=0.8),
                    opacity=0.6,
                    showlegend=False,
                    hovertemplate='<b>Simulation %{text}</b><br>Day: %{x}<br>Index: %{y:.1f}<br>Return: %{customdata:.1%}<extra></extra>',
                    text=[f'{idx+1}'] * len(simulation_data['time_points']),
                    customdata=[(val/100 - 1) for val in (path_data.tolist() if hasattr(path_data, 'tolist') else path_data)]
                ))
        
        # Add percentile bands
        if 'percentiles' in simulation_data:
            percentiles = simulation_data['percentiles']
            time_points = simulation_data['time_points']
            
            # Percentiles are already based on indexed paths starting at 100
            
            # Add confidence bands
            for i in range(len(show_percentiles) // 2):
                lower_p = show_percentiles[i]
                upper_p = show_percentiles[-(i+1)]
                
                # Use percentiles directly (already indexed)
                upper_indexed = percentiles[f'p{upper_p}']
                lower_indexed = percentiles[f'p{lower_p}']
                
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=upper_indexed.tolist() if hasattr(upper_indexed, 'tolist') else upper_indexed,
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                # Create subtle bands for percentiles with proper colors
                if i == 0:  # 5-95 percentile (outermost)
                    fillcolor = 'rgba(255, 192, 203, 0.2)'  # Light pink
                    band_name = '90% Confidence Interval'
                else:  # 25-75 percentile (inner)
                    fillcolor = 'rgba(173, 216, 230, 0.3)'  # Light blue
                    band_name = '50% Confidence Interval'
                
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=lower_indexed.tolist() if hasattr(lower_indexed, 'tolist') else lower_indexed,
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor=fillcolor,
                    name=band_name,
                    hovertemplate=f'<b>{band_name}</b><br>Day %{{x}}<br>Lower: %{{y:.1f}}<br>Upper: %{{customdata:.1f}}<extra></extra>',
                    customdata=upper_indexed.tolist() if hasattr(upper_indexed, 'tolist') else upper_indexed,
                    showlegend=True if i == 0 else False  # Only show in legend once
                ))
            
            # Add expected path (mean) if available, otherwise use median
            if 'mean' in simulation_data:
                mean_data = simulation_data['mean']
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=mean_data.tolist() if hasattr(mean_data, 'tolist') else mean_data,
                    mode='lines',
                    line=dict(color='black', width=3, dash='solid'),
                    name='Expected Path',
                    hovertemplate='<b>Expected Path</b><br>Day %{x}<br>Index: %{y:.1f}<br>Return: %{customdata:.1%}<extra></extra>',
                    customdata=[(val/100 - 1) for val in (mean_data.tolist() if hasattr(mean_data, 'tolist') else mean_data)]
                ))
            elif 'p50' in percentiles:
                median_data = percentiles['p50']
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=median_data.tolist() if hasattr(median_data, 'tolist') else median_data,
                    mode='lines',
                    line=dict(color='black', width=3, dash='solid'),
                    name='Expected Path',
                    hovertemplate='<b>Expected Path (Median)</b><br>Day %{x}<br>Index: %{y:.1f}<br>Return: %{customdata:.1%}<extra></extra>',
                    customdata=[(val/100 - 1) for val in (median_data.tolist() if hasattr(median_data, 'tolist') else median_data)]
                ))
            
            # Add 5th and 95th percentile lines
            if 'p5' in percentiles:
                p5_data = percentiles['p5']
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=p5_data.tolist() if hasattr(p5_data, 'tolist') else p5_data,
                    mode='lines',
                    line=dict(color='darkred', width=2, dash='dash'),
                    name='5th/95th Percentile',
                    hovertemplate='<b>5th Percentile</b><br>Day %{x}<br>Index: %{y:.1f}<br>Return: %{customdata:.1%}<extra></extra>',
                    customdata=[(val/100 - 1) for val in (p5_data.tolist() if hasattr(p5_data, 'tolist') else p5_data)]
                ))
            
            if 'p95' in percentiles:
                p95_data = percentiles['p95']
                fig.add_trace(go.Scatter(
                    x=time_points,
                    y=p95_data.tolist() if hasattr(p95_data, 'tolist') else p95_data,
                    mode='lines',
                    line=dict(color='darkred', width=2, dash='dash'),
                    name='95th Percentile',
                    showlegend=False,  # Already shown in 5th percentile
                    hovertemplate='<b>95th Percentile</b><br>Day %{x}<br>Index: %{y:.1f}<br>Return: %{customdata:.1%}<extra></extra>',
                    customdata=[(val/100 - 1) for val in (p95_data.tolist() if hasattr(p95_data, 'tolist') else p95_data)]
                ))
        
        # Add VaR line
        if 'var_95' in simulation_data:
            self.config.add_risk_threshold_lines(
                fig,
                {'95% VaR': simulation_data['var_95']},
                orientation='horizontal',
                color_scheme=self.color_scheme
            )
        
        layout = self.config.get_layout_template(
            title=f"Monte Carlo Simulation - Portfolio Paths ({simulation_data.get('n_simulations', 0):,} simulations)",
            color_scheme=self.color_scheme,
            height=height
        )
        
        layout.update(
            xaxis=dict(
                title="Trading Days",
                tickformat="d",
                gridcolor='rgba(128, 128, 128, 0.2)',
                showgrid=True
            ),
            yaxis=dict(
                title="Indexed Value (Base = 100)",
                tickformat=".0f",
                gridcolor='rgba(128, 128, 128, 0.2)',
                showgrid=True,
                range=[50, 300]  # Fixed range for indexed values
            ),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            )
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_var_comparison(self,
                          var_data: Dict[str, float],
                          confidence_level: float = 0.95,
                          height: int = 500) -> go.Figure:
        """
        Create a bar chart comparing different VaR methodologies.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        methods = list(var_data.keys())
        values = [-v for v in var_data.values()]  # Convert to positive for display
        
        fig = go.Figure()
        
        # Add bars
        for i, (method, value) in enumerate(zip(methods, values)):
            fig.add_trace(go.Bar(
                x=[method],
                y=[value],
                name=method,
                marker=dict(
                    color=colors['primary'][i % len(colors['primary'])],
                    line=dict(color=colors['text'], width=1)
                ),
                text=f"{value:.2%}",
                textposition='outside',
                textfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['data_label']
                ),
                hovertemplate='<b>%{x}</b><br>VaR: %{y:.2%}<extra></extra>'
            ))
        
        layout = self.config.get_layout_template(
            title=f"Value at Risk Comparison ({confidence_level:.0%} Confidence)",
            color_scheme=self.color_scheme,
            height=height
        )
        
        layout.update(
            xaxis=dict(title="VaR Methodology"),
            yaxis=dict(
                title="Potential Loss",
                tickformat=".1%"
            ),
            showlegend=False,
            bargap=0.3
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_correlation_matrix(self,
                              correlation: pd.DataFrame,
                              title: str = "Asset Correlation Matrix",
                              height: int = 600) -> go.Figure:
        """
        Create an interactive correlation matrix heatmap.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        # Create custom colorscale for correlations
        colorscale = [
            [0.0, colors['negative']],
            [0.5, colors['background']],
            [1.0, colors['positive']]
        ]
        
        # Create mask for upper triangle
        mask = np.triu(np.ones_like(correlation), k=1)
        correlation_masked = correlation.copy()
        correlation_masked[mask == 1] = np.nan
        
        fig = go.Figure(data=go.Heatmap(
            z=correlation_masked.values.tolist(),
            x=correlation.columns.tolist(),
            y=correlation.index.tolist(),
            colorscale=colorscale,
            zmid=0,
            zmin=-1,
            zmax=1,
            text=correlation_masked.values.tolist(),
            texttemplate='%{text:.2f}',
            textfont={"size": self.config.FONT_SIZES['data_label']},
            colorbar=dict(
                title=dict(
                    text="Correlation",
                    font=dict(
                        family=', '.join(self.config.TYPEWRITER_FONTS),
                        size=self.config.FONT_SIZES['axis_title']
                    )
                ),
                tickfont=dict(
                    family=', '.join(self.config.TYPEWRITER_FONTS),
                    size=self.config.FONT_SIZES['axis_label']
                )
            ),
            hovertemplate='<b>%{x} vs %{y}</b><br>Correlation: %{z:.3f}<extra></extra>'
        ))
        
        layout = self.config.get_layout_template(
            title=title,
            color_scheme=self.color_scheme,
            height=height,
            show_grid=False
        )
        
        layout.update(
            xaxis=dict(
                side="bottom",
                tickangle=-45
            ),
            yaxis=dict(
                autorange="reversed"
            )
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_portfolio_allocation(self, 
                                weights: Dict[str, float],
                                title: str = "Portfolio Allocation",
                                height: int = 500) -> go.Figure:
        """Create a simple pie chart for portfolio allocation."""
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=list(weights.keys()),
            values=list(weights.values()),
            marker=dict(
                colors=colors['primary'][:len(weights)],
                line=dict(color=colors['text'], width=1)
            ),
            textposition='auto',
            textinfo='label+percent',
            textfont=dict(
                family=', '.join(self.config.TYPEWRITER_FONTS),
                size=self.config.FONT_SIZES['data_label']
            ),
            hovertemplate='<b>%{label}</b><br>Weight: %{value:.1%}<extra></extra>'
        )])
        
        layout = self.config.get_layout_template(
            title=title,
            color_scheme=self.color_scheme,
            height=height,
            show_grid=False
        )
        
        fig.update_layout(layout)
        return fig
    
    def plot_returns_distribution(self,
                                returns: pd.Series,
                                var_lines: Optional[Dict[str, float]] = None,
                                bins: int = 50,
                                height: int = 500) -> go.Figure:
        """
        Create a histogram of returns with optional VaR lines.
        """
        colors = self.config.COLOR_SCHEMES[self.color_scheme]
        
        fig = go.Figure()
        
        # Add histogram
        fig.add_trace(go.Histogram(
            x=returns,
            nbinsx=bins,
            name='Returns Distribution',
            marker=dict(
                color=colors['primary'][0],
                line=dict(color=colors['text'], width=1)
            ),
            opacity=0.7,
            hovertemplate='<b>Return Range</b><br>%{x}<br>Count: %{y}<extra></extra>'
        ))
        
        # Add normal distribution overlay
        x_range = np.linspace(returns.min(), returns.max(), 100)
        mean = returns.mean()
        std = returns.std()
        normal_dist = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mean) / std) ** 2)
        normal_dist = normal_dist * len(returns) * (returns.max() - returns.min()) / bins
        
        fig.add_trace(go.Scatter(
            x=x_range,
            y=normal_dist,
            mode='lines',
            name='Normal Distribution',
            line=dict(color=colors['secondary'][0], width=2, dash='dash'),
            hovertemplate='<b>Normal Distribution</b><br>Return: %{x:.2%}<br>Density: %{y:.4f}<extra></extra>'
        ))
        
        layout = self.config.get_layout_template(
            title="Returns Distribution",
            color_scheme=self.color_scheme,
            height=height
        )
        
        layout.update(
            xaxis=dict(
                title="Daily Returns",
                tickformat=".1%"
            ),
            yaxis=dict(title="Frequency"),
            bargap=0.05
        )
        
        fig.update_layout(layout)
        
        # Add VaR lines if provided
        if var_lines:
            self.config.add_risk_threshold_lines(
                fig,
                var_lines,
                orientation='vertical',
                color_scheme=self.color_scheme
            )
        
        return fig