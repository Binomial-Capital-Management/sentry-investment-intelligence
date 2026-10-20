"""
Visualization configuration module for Binomial Risk Analyst.
Provides consistent Plotly-based styling with typewriter fonts and professional color schemes.
"""

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

class VisualizationConfig:
    """Central configuration for all risk module visualizations."""
    
    # Professional color palettes optimized for financial dashboards
    COLOR_SCHEMES = {
        'binomial_blue': {
            'primary': ['#1E3A8A', '#3B82F6', '#60A5FA', '#93BBFD', '#C7DBFF'],
            'secondary': ['#DC2626', '#059669', '#7C3AED', '#F59E0B', '#6366F1'],
            'positive': '#059669',
            'negative': '#DC2626',
            'neutral': '#6B7280',
            'background': '#F9FAFB',
            'grid': '#E5E7EB',
            'text': '#111827',
            'text_secondary': '#6B7280'
        },
        'dark_professional': {
            'primary': ['#1A1A2E', '#0F3460', '#16213E', '#533483', '#E94560'],
            'secondary': ['#F39422', '#4ECDC4', '#8B5CF6', '#10B981', '#F59E0B'],
            'positive': '#10B981',
            'negative': '#E94560',
            'neutral': '#9CA3AF',
            'background': '#111827',
            'grid': '#374151',
            'text': '#F9FAFB',
            'text_secondary': '#D1D5DB'
        },
        'terminal_green': {
            'primary': ['#00FF41', '#39FF14', '#7FFF00', '#ADFF2F', '#32CD32'],
            'secondary': ['#FF006E', '#FFD23F', '#3BCEAC', '#0EAD69', '#EE4266'],
            'positive': '#00FF41',
            'negative': '#FF006E',
            'neutral': '#C0C0C0',
            'background': '#0A0A0A',
            'grid': '#1A1A1A',
            'text': '#00FF41',
            'text_secondary': '#7FFF00'
        }
    }
    
    # Typewriter-style fonts in order of preference
    TYPEWRITER_FONTS = [
        'Courier New',
        'Courier',
        'Lucida Console',
        'Monaco',
        'Consolas',
        'Liberation Mono',
        'DejaVu Sans Mono',
        'Bitstream Vera Sans Mono',
        'monospace'
    ]
    
    # Font sizes for different elements (scaled properly)
    FONT_SIZES = {
        'title': 20,
        'subtitle': 14,
        'axis_title': 12,
        'axis_label': 10,
        'legend': 10,
        'annotation': 9,
        'data_label': 8
    }
    
    @classmethod
    def get_layout_template(cls, 
                          title: str = "",
                          color_scheme: str = 'binomial_blue',
                          height: int = 600,
                          width: Optional[int] = None,
                          show_grid: bool = True) -> go.Layout:
        """
        Get a consistent Plotly layout template with typewriter fonts.
        
        Args:
            title: Chart title
            color_scheme: Color scheme name from COLOR_SCHEMES
            height: Chart height in pixels
            width: Chart width in pixels (None for responsive)
            show_grid: Whether to show gridlines
            
        Returns:
            Plotly Layout object with consistent styling
        """
        colors = cls.COLOR_SCHEMES.get(color_scheme, cls.COLOR_SCHEMES['binomial_blue'])
        font_family = ', '.join(cls.TYPEWRITER_FONTS)
        
        layout = go.Layout(
            title={
                'text': title,
                'font': {
                    'family': font_family,
                    'size': cls.FONT_SIZES['title'],
                    'color': colors['text']
                },
                'x': 0.5,
                'xanchor': 'center',
                'y': 0.95,
                'yanchor': 'top'
            },
            font={
                'family': font_family,
                'size': cls.FONT_SIZES['axis_label'],
                'color': colors['text']
            },
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            height=height,
            width=width,
            margin=dict(l=80, r=80, t=100, b=80),
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor=colors['background'],
                font_size=cls.FONT_SIZES['annotation'],
                font_family=font_family,
                font_color=colors['text']
            ),
            xaxis=dict(
                showgrid=show_grid,
                gridwidth=1,
                gridcolor=colors['grid'],
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor=colors['grid'],
                title_font=dict(
                    family=font_family,
                    size=cls.FONT_SIZES['axis_title'],
                    color=colors['text']
                ),
                tickfont=dict(
                    family=font_family,
                    size=cls.FONT_SIZES['axis_label'],
                    color=colors['text_secondary']
                )
            ),
            yaxis=dict(
                showgrid=show_grid,
                gridwidth=1,
                gridcolor=colors['grid'],
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor=colors['grid'],
                title_font=dict(
                    family=font_family,
                    size=cls.FONT_SIZES['axis_title'],
                    color=colors['text']
                ),
                tickfont=dict(
                    family=font_family,
                    size=cls.FONT_SIZES['axis_label'],
                    color=colors['text_secondary']
                )
            ),
            legend=dict(
                font=dict(
                    family=font_family,
                    size=cls.FONT_SIZES['legend'],
                    color=colors['text']
                ),
                bgcolor='rgba(0,0,0,0)',
                bordercolor=colors['grid'],
                borderwidth=1
            )
        )
        
        return layout
    
    @classmethod
    def style_line_trace(cls, 
                        trace: go.Scatter,
                        color_index: int = 0,
                        color_scheme: str = 'binomial_blue',
                        line_width: int = 2) -> go.Scatter:
        """Apply consistent styling to a line trace."""
        colors = cls.COLOR_SCHEMES[color_scheme]['primary']
        color = colors[color_index % len(colors)]
        
        trace.line = dict(color=color, width=line_width)
        trace.hovertemplate = '<b>%{fullData.name}</b><br>%{x}<br>%{y:.2f}<extra></extra>'
        
        return trace
    
    @classmethod
    def style_bar_trace(cls,
                       trace: go.Bar,
                       color_index: int = 0,
                       color_scheme: str = 'binomial_blue') -> go.Bar:
        """Apply consistent styling to a bar trace."""
        colors = cls.COLOR_SCHEMES[color_scheme]['primary']
        color = colors[color_index % len(colors)]
        
        trace.marker = dict(
            color=color,
            line=dict(color=cls.COLOR_SCHEMES[color_scheme]['text'], width=1)
        )
        trace.hovertemplate = '<b>%{x}</b><br>%{y:.2f}<extra></extra>'
        
        return trace
    
    @classmethod
    def style_scatter_trace(cls,
                           trace: go.Scatter,
                           color_value: Optional[float] = None,
                           color_scheme: str = 'binomial_blue',
                           marker_size: int = 8) -> go.Scatter:
        """Apply consistent styling to a scatter trace."""
        colors = cls.COLOR_SCHEMES[color_scheme]
        
        if color_value is not None:
            # Color based on value (e.g., positive/negative)
            color = colors['positive'] if color_value >= 0 else colors['negative']
        else:
            color = colors['primary'][0]
        
        trace.marker = dict(
            color=color,
            size=marker_size,
            line=dict(color=colors['text'], width=1)
        )
        trace.hovertemplate = '<b>%{text}</b><br>X: %{x:.2f}<br>Y: %{y:.2f}<extra></extra>'
        
        return trace
    
    @classmethod
    def add_risk_threshold_lines(cls,
                                fig: go.Figure,
                                thresholds: Dict[str, float],
                                orientation: str = 'horizontal',
                                color_scheme: str = 'binomial_blue'):
        """Add threshold lines to a figure (e.g., VaR limits)."""
        colors = cls.COLOR_SCHEMES[color_scheme]
        
        for name, value in thresholds.items():
            if orientation == 'horizontal':
                fig.add_hline(
                    y=value,
                    line_dash="dash",
                    line_color=colors['negative'],
                    annotation_text=name,
                    annotation_position="right",
                    annotation_font=dict(
                        family=', '.join(cls.TYPEWRITER_FONTS),
                        size=cls.FONT_SIZES['annotation'],
                        color=colors['text_secondary']
                    )
                )
            else:
                fig.add_vline(
                    x=value,
                    line_dash="dash",
                    line_color=colors['negative'],
                    annotation_text=name,
                    annotation_position="top",
                    annotation_font=dict(
                        family=', '.join(cls.TYPEWRITER_FONTS),
                        size=cls.FONT_SIZES['annotation'],
                        color=colors['text_secondary']
                    )
                )
    
    @classmethod
    def create_gauge_chart(cls,
                          value: float,
                          min_value: float,
                          max_value: float,
                          title: str,
                          thresholds: Optional[Dict[str, float]] = None,
                          color_scheme: str = 'binomial_blue') -> go.Figure:
        """Create a styled gauge chart for risk metrics."""
        colors = cls.COLOR_SCHEMES[color_scheme]
        
        # Define color ranges based on thresholds
        if thresholds:
            # Sort thresholds by value
            sorted_thresholds = sorted(thresholds.items(), key=lambda x: x[1])
            
            # Create color steps
            steps = []
            range_start = min_value
            
            for i, (name, threshold) in enumerate(sorted_thresholds):
                color = colors['primary'][i % len(colors['primary'])]
                steps.append(dict(range=[range_start, threshold], color=color))
                range_start = threshold
            
            # Add final range
            steps.append(dict(
                range=[range_start, max_value], 
                color=colors['negative']
            ))
        else:
            steps = [dict(range=[min_value, max_value], color=colors['primary'][0])]
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            title={'text': title, 'font': {'family': ', '.join(cls.TYPEWRITER_FONTS)}},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [min_value, max_value]},
                'bar': {'color': colors['text']},
                'steps': steps,
                'threshold': {
                    'line': {'color': colors['negative'], 'width': 4},
                    'thickness': 0.75,
                    'value': value
                }
            }
        ))
        
        fig.update_layout(
            font={'family': ', '.join(cls.TYPEWRITER_FONTS)},
            paper_bgcolor=colors['background'],
            height=400
        )
        
        return fig
    
    @classmethod
    def format_number(cls, value: float, format_type: str = 'general') -> str:
        """Format numbers consistently across all visualizations."""
        if format_type == 'percentage':
            return f"{value:.2%}"
        elif format_type == 'currency':
            return f"${value:,.0f}"
        elif format_type == 'basis_points':
            return f"{value * 10000:.0f} bps"
        else:
            if abs(value) >= 1e6:
                return f"{value/1e6:.2f}M"
            elif abs(value) >= 1e3:
                return f"{value/1e3:.1f}K"
            else:
                return f"{value:.2f}"