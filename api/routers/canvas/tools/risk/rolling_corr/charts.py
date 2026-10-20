"""Chart builders for Rolling Correlation."""

import logging
from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import numpy as np

logger = logging.getLogger(__name__)


def build_correlation_timeseries_chart(
    correlation: List[float],
    dates: List[str],
    ticker_x: str,
    ticker_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build correlation time series chart with color-coded markers and reference lines.
    
    Args:
        correlation: List of correlation values
        dates: List of date strings
        ticker_x: First ticker
        ticker_y: Second ticker
        
    Returns:
        Chart dict in Canvas format or None if no data
    """
    try:
        if not correlation or not dates:
            logger.warning("No data for correlation timeseries chart")
            return None
        
        fig = go.Figure()
        
        # Main correlation line with color-coded markers
        fig.add_trace(go.Scatter(
            x=dates,
            y=correlation,
            mode='lines+markers',
            name='Correlation',
            line=dict(color='#1976D2', width=2),
            marker=dict(
                size=4,
                color=correlation,
                colorscale=[[0, '#C62828'], [0.5, '#FFF176'], [1, '#2E7D32']],
                showscale=True,
                colorbar=dict(
                    title="ρ",
                    thickness=15,
                    len=0.7,
                    x=1.12
                ),
                cmin=-1,
                cmax=1
            ),
            hovertemplate='<b>%{x}</b><br>Correlation: %{y:.4f}<extra></extra>'
        ))
        
        # Reference lines for correlation strength
        fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1,
                     annotation_text="Zero", annotation_position="right")
        fig.add_hline(y=0.5, line_dash="dash", line_color="green", opacity=0.5,
                     annotation_text="Weak Positive", annotation_position="right")
        fig.add_hline(y=-0.5, line_dash="dash", line_color="red", opacity=0.5,
                     annotation_text="Weak Negative", annotation_position="right")
        fig.add_hline(y=0.8, line_dash="dot", line_color="darkgreen", opacity=0.5,
                     annotation_text="Strong Positive", annotation_position="right")
        fig.add_hline(y=-0.8, line_dash="dot", line_color="darkred", opacity=0.5,
                     annotation_text="Strong Negative", annotation_position="right")
        
        fig.update_layout(
            title=dict(
                text=f"<b>Rolling Correlation:</b> {ticker_x} vs {ticker_y}",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title="Date",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            yaxis=dict(
                title="Correlation Coefficient (ρ)",
                range=[-1.05, 1.05],
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            width=1200,
            height=500,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            hovermode='x unified',
            showlegend=True
        )
        
        return {
            "id": f"rolling_corr_timeseries_{ticker_x.lower()}_{ticker_y.lower()}",
            "title": f"{ticker_x} vs {ticker_y} Correlation",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build correlation timeseries chart: {e}", exc_info=True)
        return None


def build_confidence_intervals_chart(
    correlation: List[float],
    upper_bound: List[float],
    lower_bound: List[float],
    dates: List[str],
    ticker_x: str,
    ticker_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build confidence interval chart with shaded bands (Fisher transformation).
    
    Args:
        correlation: List of correlation values
        upper_bound: Upper 95% confidence bound
        lower_bound: Lower 95% confidence bound
        dates: List of date strings
        ticker_x: First ticker
        ticker_y: Second ticker
        
    Returns:
        Chart dict in Canvas format or None if no data
    """
    try:
        if not correlation or not dates or not upper_bound or not lower_bound:
            logger.warning("No data for confidence intervals chart")
            return None
        
        fig = go.Figure()
        
        # Upper confidence bound
        fig.add_trace(go.Scatter(
            x=dates,
            y=upper_bound,
            mode='lines',
            name='Upper 95% CI',
            line=dict(color='rgba(0,100,80,0)', width=0),
            showlegend=True,
            hovertemplate='Upper CI: %{y:.4f}<extra></extra>'
        ))
        
        # Lower confidence bound with fill to upper
        fig.add_trace(go.Scatter(
            x=dates,
            y=lower_bound,
            mode='lines',
            name='Lower 95% CI',
            line=dict(color='rgba(0,100,80,0)', width=0),
            fill='tonexty',
            fillcolor='rgba(68,138,255,0.2)',
            showlegend=True,
            hovertemplate='Lower CI: %{y:.4f}<extra></extra>'
        ))
        
        # Main correlation line on top
        fig.add_trace(go.Scatter(
            x=dates,
            y=correlation,
            mode='lines',
            name='Correlation',
            line=dict(color='#1976D2', width=2.5),
            hovertemplate='Correlation: %{y:.4f}<extra></extra>'
        ))
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            title=dict(
                text=f"<b>Correlation with 95% Confidence Intervals:</b> {ticker_x} vs {ticker_y}",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title="Date",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            yaxis=dict(
                title="Correlation Coefficient (ρ)",
                range=[-1.05, 1.05],
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            width=1200,
            height=500,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor="rgba(255, 255, 255, 0.95)",
                bordercolor="#e2e8f0",
                borderwidth=1
            )
        )
        
        return {
            "id": f"rolling_corr_confidence_{ticker_x.lower()}_{ticker_y.lower()}",
            "title": f"{ticker_x} vs {ticker_y} Confidence Intervals",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build confidence intervals chart: {e}", exc_info=True)
        return None


def build_returns_scatter_chart(
    returns_x: List[float],
    returns_y: List[float],
    dates: List[str],
    ticker_x: str,
    ticker_y: str,
    current_corr: float
) -> Optional[Dict[str, Any]]:
    """
    Build scatter plot of returns relationship with regression line.
    
    Args:
        returns_x: Returns for first asset
        returns_y: Returns for second asset
        dates: List of date strings
        ticker_x: First ticker
        ticker_y: Second ticker
        current_corr: Current correlation value
        
    Returns:
        Chart dict in Canvas format or None if no data
    """
    try:
        if not returns_x or not returns_y or len(returns_x) != len(returns_y):
            logger.warning("No data or mismatched data for returns scatter chart")
            return None
        
        # Create time-based color gradient (blue to red)
        n_points = len(returns_x)
        time_colors = np.linspace(0, 1, n_points)
        
        fig = go.Figure()
        
        # Scatter plot
        fig.add_trace(go.Scatter(
            x=returns_x,
            y=returns_y,
            mode='markers',
            name='Returns',
            marker=dict(
                size=6,
                color=time_colors,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Time",
                    tickvals=[0, 0.5, 1],
                    ticktext=['Early', 'Mid', 'Recent'],
                    thickness=15,
                    len=0.7
                ),
                opacity=0.6
            ),
            text=dates,
            hovertemplate='<b>%{text}</b><br>%{xaxis.title.text}: %{x:.4f}<br>%{yaxis.title.text}: %{y:.4f}<extra></extra>'
        ))
        
        # OLS regression line
        if len(returns_x) > 1:
            # Calculate regression coefficients
            coefficients = np.polyfit(returns_x, returns_y, 1)
            regression_line = np.poly1d(coefficients)
            
            # Create smooth line
            x_range = np.linspace(min(returns_x), max(returns_x), 100)
            y_fit = regression_line(x_range)
            
            fig.add_trace(go.Scatter(
                x=x_range,
                y=y_fit,
                mode='lines',
                name=f'OLS Fit (ρ={current_corr:.4f})',
                line=dict(color='red', width=2, dash='dash'),
                hovertemplate='Fitted Line<extra></extra>'
            ))
        
        # Add origin lines
        fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.3)
        fig.add_vline(x=0, line_dash="dot", line_color="gray", opacity=0.3)
        
        # Add correlation annotation
        fig.add_annotation(
            text=f"Current Correlation: {current_corr:.4f}",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            bgcolor="white",
            bordercolor="black",
            borderwidth=1,
            font=dict(size=12)
        )
        
        fig.update_layout(
            title=dict(
                text=f"<b>Returns Scatter:</b> {ticker_x} vs {ticker_y}",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title=f"{ticker_x} Returns",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            yaxis=dict(
                title=f"{ticker_y} Returns",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            width=1200,
            height=600,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            hovermode='closest',
            showlegend=True
        )
        
        return {
            "id": f"rolling_corr_scatter_{ticker_x.lower()}_{ticker_y.lower()}",
            "title": f"{ticker_x} vs {ticker_y} Returns Scatter",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build returns scatter chart: {e}", exc_info=True)
        return None
