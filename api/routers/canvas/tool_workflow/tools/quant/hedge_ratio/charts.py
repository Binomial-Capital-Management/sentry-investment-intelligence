"""
Hedge Ratio Canvas Chart Builders
Simple chart builders for Canvas display.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Optional


def build_hedge_ratio_timeseries_chart(
    hedge_ratios: List[float],
    dates: List[str],
    method: str,
    mean_beta: float
) -> Dict[str, Any]:
    """
    Build time series chart of dynamic hedge ratio.
    """
    if not hedge_ratios or not dates or len(hedge_ratios) != len(dates):
        return None
    
    fig = go.Figure()
    
    # Main line
    fig.add_trace(go.Scatter(
        x=dates,
        y=hedge_ratios,
        mode='lines',
        name=f'Hedge Ratio ({method.upper()})',
        line=dict(color='#2E86AB', width=2),
        hovertemplate='<b>%{x}</b><br>β: %{y:.4f}<extra></extra>'
    ))
    
    # Mean line
    fig.add_hline(
        y=mean_beta,
        line_dash="dash",
        line_color="green",
        annotation_text=f"Mean β={mean_beta:.4f}",
        annotation_position="right"
    )
    
    # Zero line
    fig.add_hline(
        y=0,
        line_dash="dot",
        line_color="gray",
        annotation_text="β=0 (no hedge)"
    )
    
    fig.update_layout(
        title=f"Dynamic Hedge Ratio: {method.upper()} Method",
        xaxis_title="Date",
        yaxis_title="Hedge Ratio (β)",
        template="plotly_white",
        height=500,
        width=900,
        hovermode='x unified',
        showlegend=True
    )
    
    return {
        "id": "hedge_ratio_timeseries",
        "title": f"Dynamic Hedge Ratio: {method.upper()}",
        "plotly": fig.to_dict()
    }


def build_scatter_chart(
    price_x: List[float],
    price_y: List[float],
    alpha: float,
    beta: float,
    r_squared: float,
    asset_x: str,
    asset_y: str
) -> Dict[str, Any]:
    """
    Build scatter plot with regression line.
    """
    if not price_x or not price_y:
        return None
    
    import numpy as np
    
    fig = go.Figure()
    
    # Scatter
    fig.add_trace(go.Scatter(
        x=price_x,
        y=price_y,
        mode='markers',
        marker=dict(size=4, color='#2E86AB', opacity=0.5),
        name='Prices',
        hovertemplate=f'{asset_x}: %{{x:.2f}}<br>{asset_y}: %{{y:.2f}}<extra></extra>'
    ))
    
    # Regression line
    x_range = np.array([min(price_x), max(price_x)])
    y_pred = alpha + beta * x_range
    
    fig.add_trace(go.Scatter(
        x=x_range.tolist(),
        y=y_pred.tolist(),
        mode='lines',
        line=dict(color='red', width=2),
        name='OLS Fit',
        hovertemplate=f'Y = {alpha:.4f} + {beta:.4f}X<extra></extra>'
    ))
    
    # Annotation
    fig.add_annotation(
        x=0.05, y=0.95,
        xref='paper', yref='paper',
        text=f'{asset_y} = {alpha:.4f} + {beta:.4f} × {asset_x}<br>R² = {r_squared:.4f}',
        showarrow=False,
        bgcolor='white',
        bordercolor='black',
        borderwidth=1
    )
    
    fig.update_layout(
        title=f"Price Scatter: {asset_y} vs {asset_x}",
        xaxis_title=f"{asset_x} Price",
        yaxis_title=f"{asset_y} Price",
        template="plotly_white",
        height=500,
        width=700
    )
    
    return {
        "id": "hedge_ratio_scatter",
        "title": f"Price Scatter: {asset_y} vs {asset_x}",
        "plotly": fig.to_dict()
    }


def build_residuals_chart(
    residuals: List[float],
    dates: List[str]
) -> Dict[str, Any]:
    """
    Simple residuals over time chart.
    """
    if not residuals or not dates:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=residuals,
        mode='markers',
        marker=dict(size=4, color='#F18F01'),
        name='Residuals',
        hovertemplate='<b>%{x}</b><br>Residual: %{y:.4f}<extra></extra>'
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    
    fig.update_layout(
        title="Residuals Over Time",
        xaxis_title="Date",
        yaxis_title="Residual",
        template="plotly_white",
        height=400,
        width=900
    )
    
    return {
        "id": "hedge_ratio_residuals",
        "title": "Residuals Over Time",
        "plotly": fig.to_dict()
    }


def build_regression_fit_chart(
    beta: float,
    alpha: float,
    r_squared: float,
    asset_x: str,
    asset_y: str,
    method: str
) -> Dict[str, Any]:
    """
    Build regression visualization showing the fitted line on a representative range.
    """
    import numpy as np
    
    fig = go.Figure()
    
    # Create representative X range (normalized 0-100 for visualization)
    x_range = np.linspace(0, 100, 50)
    y_fitted = alpha + beta * x_range
    
    # Add fitted line
    fig.add_trace(go.Scatter(
        x=x_range,
        y=y_fitted,
        mode='lines',
        name='Fitted Line',
        line=dict(color='#3b82f6', width=3),
        hovertemplate=f'{asset_y} = {alpha:.4f} + {beta:.4f} × {asset_x}<extra></extra>'
    ))
    
    # Add some noise for visual context (simulated data points)
    np.random.seed(42)
    noise_std = np.std(y_fitted) * (1 - r_squared) * 0.5 + 1
    y_noisy = y_fitted + np.random.normal(0, noise_std, len(x_range))
    
    fig.add_trace(go.Scatter(
        x=x_range,
        y=y_noisy,
        mode='markers',
        name='Sample Data (Illustrative)',
        marker=dict(size=6, color='#94a3b8', opacity=0.6),
        hovertemplate=f'{asset_x}: %{{x:.1f}}<br>{asset_y}: %{{y:.1f}}<extra></extra>'
    ))
    
    # Add annotation with equation
    quality_text = "Strong" if r_squared > 0.7 else ("Moderate" if r_squared > 0.4 else "Weak")
    equation_text = (
        f'<b>Y = {alpha:.4f} + {beta:.4f}X</b><br>'
        f'R² = {r_squared:.4f} ({quality_text} fit)<br>'
        f'Method: {method.upper()}'
    )
    
    fig.add_annotation(
        x=0.02,
        y=0.98,
        xref='paper',
        yref='paper',
        text=equation_text,
        showarrow=False,
        bgcolor='rgba(255,255,255,0.95)',
        bordercolor='#1f2937',
        borderwidth=1,
        borderpad=8,
        font=dict(size=11),
        align='left',
        xanchor='left',
        yanchor='top'
    )
    
    fig.update_layout(
        title=f"Regression Fit: {asset_y} vs {asset_x}",
        xaxis_title=f"{asset_x} (normalized)",
        yaxis_title=f"{asset_y} (normalized)",
        template="plotly_white",
        height=500,
        width=800,
        showlegend=True,
        legend=dict(yanchor="bottom", y=0.02, xanchor="right", x=0.98)
    )
    
    return {
        "id": "hedge_ratio_regression",
        "title": f"Regression Fit: {asset_y} vs {asset_x}",
        "plotly": fig.to_dict()
    }
