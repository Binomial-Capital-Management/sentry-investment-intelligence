"""
Risk analysis chart builders.

Monte Carlo, VaR, returns distributions, etc.
"""

from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from ..models import ChartSpec, ChartFigure, ChartListItem, ChartType
from ..utils.downsampling import downsample_if_needed
from core.config import get_config


async def build_monte_carlo_paths(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build Monte Carlo simulation paths chart with professional styling"""
    
    # Extract inputs
    paths = spec.inputs.get('paths', [])
    percentiles = spec.inputs.get('percentiles', {})
    terminal_stats = spec.inputs.get('terminal_stats', {})
    
    # Constraints driven by config
    cfg = get_config()
    budget_points = getattr(cfg, 'charts_max_render_points', 2000)
    max_points_per_trace = min(2000, int(budget_points))
    
    # Create figure with dark theme
    fig = go.Figure()
    
    # Add simulation paths with gradient effect
    if paths:
        pct_points_est = sum(min(len(vals), max_points_per_trace) for vals in percentiles.values() if vals)
        points_for_paths = max(int(budget_points) - pct_points_est, 0)
        num_paths = len(paths)
        per_path_points = max(2, points_for_paths // max(num_paths, 1)) if points_for_paths > 0 else 2

        # Use gradient colors for paths based on terminal value
        for i, path in enumerate(paths):
            path_data = downsample_if_needed(path, per_path_points)
            terminal_val = path_data[-1] if path_data else 0
            # Color based on performance: green for gains, red for losses
            opacity = 0.4
            color = f'rgba(16, 185, 129, {opacity})' if terminal_val > path_data[0] else f'rgba(239, 68, 68, {opacity})'
            fig.add_trace(go.Scattergl(
                y=path_data,
                mode='lines',
                line=dict(width=1.5, color=color),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Add percentile bands with confidence interval shading
    if '5' in percentiles and '95' in percentiles:
        pct_5 = downsample_if_needed(percentiles['5'], max_points_per_trace)
        pct_95 = downsample_if_needed(percentiles['95'], max_points_per_trace)
        x_vals = list(range(len(pct_5)))
        
        # Fill between 5th and 95th percentile
        fig.add_trace(go.Scatter(
            x=x_vals + x_vals[::-1],
            y=pct_95 + pct_5[::-1],
            fill='toself',
            fillcolor='rgba(99, 102, 241, 0.15)',
            line=dict(color='rgba(0,0,0,0)'),
            name='90% Confidence',
            hoverinfo='skip',
            showlegend=True
        ))
    
    # Styled percentile lines
    percentile_styles = {
        '5': {'color': '#EF4444', 'width': 2, 'dash': 'dot', 'name': '5th Percentile (Worst Case)'},
        '50': {'color': '#F59E0B', 'width': 3, 'dash': 'solid', 'name': 'Median Path'},
        '95': {'color': '#10B981', 'width': 2, 'dash': 'dot', 'name': '95th Percentile (Best Case)'}
    }
    
    for pct, values in percentiles.items():
        if values and pct in percentile_styles:
            values_data = downsample_if_needed(values, max_points_per_trace)
            style = percentile_styles[pct]
            fig.add_trace(go.Scattergl(
                y=values_data,
                mode='lines',
                name=style['name'],
                line=dict(width=style['width'], color=style['color'], dash=style.get('dash', 'solid'))
            ))
    
    # Professional layout with dark theme accents
    fig.update_layout(
        title=dict(
            text=spec.title or "Monte Carlo Simulation",
            font=dict(size=20, color='#1F2937', family='Inter, system-ui, sans-serif'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Trading Days", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.2)',
            zeroline=False,
            showline=True,
            linecolor='#E5E7EB'
        ),
        yaxis=dict(
            title=dict(text="Portfolio Value ($)", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.2)',
            zeroline=False,
            showline=True,
            linecolor='#E5E7EB',
            tickformat='$,.0f'
        ),
        plot_bgcolor='rgba(249, 250, 251, 1)',
        paper_bgcolor='white',
        height=520,
        margin=dict(l=70, r=30, t=70, b=60),
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#E5E7EB',
            borderwidth=1,
            font=dict(size=11)
        ),
        font=dict(family='Inter, system-ui, sans-serif')
    )
    
    # Add terminal stats annotation if available
    if terminal_stats:
        mean_val = terminal_stats.get('mean', 0)
        var_95 = terminal_stats.get('var_95', 0)
        fig.add_annotation(
            x=0.02, y=0.98,
            xref='paper', yref='paper',
            text=f"<b>Expected Value:</b> ${mean_val:,.0f}<br><b>VaR (95%):</b> ${var_95:,.0f}",
            showarrow=False,
            font=dict(size=11, color='#374151'),
            align='left',
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='#E5E7EB',
            borderwidth=1,
            borderpad=8
        )
    
    num_paths = len(paths) if paths else 0
    alt_text = f"Monte Carlo simulation showing {num_paths} paths"
    if terminal_stats:
        alt_text += f". Terminal mean: ${terminal_stats.get('mean', 0):,.0f}, VaR 95%: ${terminal_stats.get('var_95', 0):,.0f}"

    return ChartFigure(
        id=spec.id,
        title=spec.title or "Monte Carlo Simulation",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'paths_shown': num_paths}
    )


async def build_returns_histogram(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build returns distribution histogram with professional VaR visualization"""
    
    # Extract inputs
    returns = spec.inputs.get('returns', [])
    var_lines = spec.inputs.get('var_lines', {})
    stats = spec.inputs.get('stats', {})
    
    if not returns:
        fig = go.Figure()
        fig.update_layout(title="No returns data available")
        return ChartFigure(
            id=spec.id,
            title="Returns Distribution",
            alt_text="Returns histogram (no data)",
            plotly=fig.to_dict()
        )
    
    fig = go.Figure()
    
    # Calculate histogram bins for gradient coloring
    returns_arr = np.array(returns)
    hist_values, bin_edges = np.histogram(returns_arr, bins=60)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Create gradient colors: red for negative returns, teal for positive
    colors = []
    for center in bin_centers:
        if center < 0:
            # Red gradient for losses
            intensity = min(1, abs(center) / (abs(returns_arr.min()) + 0.001))
            colors.append(f'rgba(239, 68, 68, {0.5 + intensity * 0.4})')
        else:
            # Teal gradient for gains
            intensity = min(1, center / (returns_arr.max() + 0.001))
            colors.append(f'rgba(20, 184, 166, {0.5 + intensity * 0.4})')
    
    # Add histogram with gradient bars
    fig.add_trace(go.Bar(
        x=bin_centers,
        y=hist_values / sum(hist_values),  # Normalize to probability
        marker=dict(
            color=colors,
            line=dict(color='rgba(255,255,255,0.3)', width=0.5)
        ),
        name='Returns',
        hovertemplate='Return: %{x:.2%}<br>Probability: %{y:.2%}<extra></extra>'
    ))
    
    # Add kernel density estimate overlay
    try:
        from scipy import stats as scipy_stats
        kde = scipy_stats.gaussian_kde(returns_arr)
        x_kde = np.linspace(returns_arr.min(), returns_arr.max(), 200)
        y_kde = kde(x_kde)
        # Scale KDE to match histogram
        y_kde = y_kde * (bin_edges[1] - bin_edges[0])
        
        fig.add_trace(go.Scatter(
            x=x_kde,
            y=y_kde,
            mode='lines',
            name='Density',
            line=dict(color='#6366F1', width=2.5),
            hoverinfo='skip'
        ))
    except ImportError:
        pass  # scipy not available
    
    # Add styled VaR lines with fill regions
    var_colors = {
        '99': '#7C3AED',  # Purple
        '95': '#EF4444',  # Red
        '90': '#F59E0B',  # Amber
    }
    
    if var_lines:
        for confidence, value in sorted(var_lines.items(), key=lambda x: float(x[0].replace('%', '')), reverse=True):
            conf_key = confidence.replace('%', '').strip()
            color = var_colors.get(conf_key, '#EF4444')
            
            # Add shaded VaR region
            fig.add_vrect(
                x0=returns_arr.min(),
                x1=value,
                fillcolor=f'{color}22',
                layer='below',
                line_width=0
            )
            
            # Add VaR line with professional annotation
            fig.add_vline(
                x=value,
                line=dict(color=color, width=2.5, dash='dash'),
            )
            fig.add_annotation(
                x=value,
                y=1.05,
                yref='paper',
                text=f"<b>VaR {confidence}</b><br>{value:.2%}",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor=color,
                ax=30,
                ay=-25,
                font=dict(size=10, color=color),
                bgcolor='white',
                bordercolor=color,
                borderwidth=1,
                borderpad=4
            )
    
    # Add mean line with annotation
    mean_val = stats.get('mean', np.mean(returns_arr))
    fig.add_vline(
        x=mean_val,
        line=dict(color='#10B981', width=2.5, dash='solid'),
    )
    fig.add_annotation(
        x=mean_val,
        y=0.95,
        yref='paper',
        text=f"<b>Mean</b><br>{mean_val:.2%}",
        showarrow=True,
        arrowhead=2,
        arrowcolor='#10B981',
        ax=-30 if mean_val > 0 else 30,
        ay=-20,
        font=dict(size=10, color='#10B981'),
        bgcolor='white',
        bordercolor='#10B981',
        borderwidth=1,
        borderpad=4
    )
    
    # Professional layout
    fig.update_layout(
        title=dict(
            text=spec.title or "Returns Distribution with VaR",
            font=dict(size=20, color='#1F2937', family='Inter, system-ui, sans-serif'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Daily Returns", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.15)',
            zeroline=True,
            zerolinecolor='#9CA3AF',
            zerolinewidth=1,
            tickformat='.1%',
            showline=True,
            linecolor='#E5E7EB'
        ),
        yaxis=dict(
            title=dict(text="Probability", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.15)',
            zeroline=False,
            tickformat='.1%',
            showline=True,
            linecolor='#E5E7EB'
        ),
        plot_bgcolor='rgba(249, 250, 251, 1)',
        paper_bgcolor='white',
        height=480,
        margin=dict(l=70, r=30, t=80, b=60),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#E5E7EB',
            borderwidth=1,
            font=dict(size=11)
        ),
        bargap=0.02,
        font=dict(family='Inter, system-ui, sans-serif')
    )
    
    std_return = stats.get('std', np.std(returns_arr))
    alt_text = f"Returns histogram. Mean: {mean_val:.2%}, Std: {std_return:.2%}"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Returns Distribution",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'num_returns': len(returns)}
    )


async def build_var_cone(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build VaR cone chart showing risk bounds over time"""
    
    # Extract inputs
    expected = spec.inputs.get('expected', [])
    var_95 = spec.inputs.get('var_95', [])
    var_99 = spec.inputs.get('var_99', [])
    actual = spec.inputs.get('actual', None)
    
    # Create figure
    fig = go.Figure()
    
    # Time axis
    time_steps = list(range(len(expected))) if expected else []
    
    # Add expected path
    if expected:
        expected_data = downsample_if_needed(expected, 2000)
        fig.add_trace(go.Scattergl(
            x=time_steps[:len(expected_data)],
            y=expected_data,
            mode='lines',
            name='Expected',
            line=dict(color='#2E86AB', width=2)
        ))
    
    # Add VaR bounds as filled areas
    if var_95 and expected:
        var_95_data = downsample_if_needed(var_95, 2000)
        expected_data = downsample_if_needed(expected, 2000)
        
        # Upper bound (expected + VaR)
        upper_95 = [e - v for e, v in zip(expected_data, var_95_data)]
        # Lower bound (expected - VaR)
        lower_95 = [e + v for e, v in zip(expected_data, var_95_data)]
        
        fig.add_trace(go.Scatter(
            x=time_steps[:len(upper_95)] + time_steps[:len(lower_95)][::-1],
            y=upper_95 + lower_95[::-1],
            fill='toself',
            fillcolor='rgba(46, 134, 171, 0.2)',
            line=dict(color='rgba(46, 134, 171, 0.5)', width=1),
            name='95% VaR Cone',
            hoverinfo='skip'
        ))
    
    if var_99 and expected:
        var_99_data = downsample_if_needed(var_99, 2000)
        expected_data = downsample_if_needed(expected, 2000)
        
        upper_99 = [e - v for e, v in zip(expected_data, var_99_data)]
        lower_99 = [e + v for e, v in zip(expected_data, var_99_data)]
        
        fig.add_trace(go.Scatter(
            x=time_steps[:len(upper_99)] + time_steps[:len(lower_99)][::-1],
            y=upper_99 + lower_99[::-1],
            fill='toself',
            fillcolor='rgba(239, 83, 80, 0.1)',
            line=dict(color='rgba(239, 83, 80, 0.3)', width=1),
            name='99% VaR Cone',
            hoverinfo='skip'
        ))
    
    # Add actual path if provided
    if actual:
        actual_data = downsample_if_needed(actual, 2000)
        fig.add_trace(go.Scattergl(
            x=time_steps[:len(actual_data)],
            y=actual_data,
            mode='lines',
            name='Actual',
            line=dict(color='#000000', width=2, dash='dot')
        ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or "VaR Cone",
        xaxis_title="Time Steps",
        yaxis_title="Portfolio Value ($)",
        template="plotly_white",
        height=450,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified'
    )
    
    # Generate alt text
    alt_text = "VaR cone showing expected path with 95% and 99% confidence bounds"
    if actual:
        alt_text += " and actual realized path"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "VaR Cone",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'has_actual': actual is not None}
    )


# Schema definitions
MONTE_CARLO_SCHEMA = ChartListItem(
    type=ChartType.MONTE_CARLO_PATHS,
    inputs_schema={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "Array of simulation paths"
            },
            "percentiles": {
                "type": "object",
                "description": "Percentile bands (e.g., {'5': [...], '95': [...]})"
            },
            "terminal_stats": {
                "type": "object",
                "description": "Terminal statistics (mean, var_95, etc.)"
            }
        },
        "required": ["paths"]
    },
    description="Monte Carlo simulation paths with percentile bands",
    constraints={"max_paths": 100, "max_points_per_path": 2000}
)

RETURNS_HISTOGRAM_SCHEMA = ChartListItem(
    type=ChartType.RETURNS_HISTOGRAM,
    inputs_schema={
        "type": "object",
        "properties": {
            "returns": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Array of return values"
            },
            "var_lines": {
                "type": "object",
                "description": "VaR lines to overlay (e.g., {'95': -0.05})"
            },
            "stats": {
                "type": "object",
                "description": "Statistics (mean, std, etc.)"
            }
        },
        "required": ["returns"]
    },
    description="Histogram of returns distribution with VaR markers",
    constraints={"max_returns": 10000}
)

VAR_CONE_SCHEMA = ChartListItem(
    type=ChartType.VAR_CONE,
    inputs_schema={
        "type": "object",
        "properties": {
            "expected": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Expected portfolio path"
            },
            "var_95": {
                "type": "array",
                "items": {"type": "number"},
                "description": "95% VaR values over time"
            },
            "var_99": {
                "type": "array",
                "items": {"type": "number"},
                "description": "99% VaR values over time"
            },
            "actual": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Actual realized path (optional)"
            }
        },
        "required": ["expected", "var_95"]
    },
    description="VaR cone showing risk bounds over time",
    constraints={"max_points": 2000}
)


async def build_drawdown_curve(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build drawdown curve chart"""
    
    # Extract inputs
    prices = spec.inputs.get('prices', [])
    dates = spec.inputs.get('dates', None)
    symbol = spec.inputs.get('symbol', 'Portfolio')
    
    if not prices:
        fig = go.Figure()
        fig.update_layout(title="No price data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Drawdown Curve",
            alt_text="Drawdown curve (no data)",
            plotly=fig.to_dict()
        )
    
    # Calculate drawdown
    # Respect chart budget: downsample inputs before heavy computation
    cfg = get_config()
    budget_points = getattr(cfg, 'charts_max_render_points', 2000)
    if prices and len(prices) > budget_points:
        # Downsample prices and dates together if dates provided
        prices = downsample_if_needed(prices, budget_points)
        if dates:
            dates = downsample_if_needed(dates, budget_points)
    prices_series = pd.Series(prices)
    cummax = prices_series.expanding().max()
    drawdown = (prices_series - cummax) / cummax * 100
    
    # Find maximum drawdown
    max_dd = drawdown.min()
    max_dd_idx = drawdown.idxmin()
    
    # Create figure
    fig = go.Figure()
    
    # Add drawdown area
    fig.add_trace(go.Scatter(
        x=dates if dates else list(range(len(drawdown))),
        y=drawdown.tolist(),
        fill='tozeroy',
        fillcolor='rgba(214, 40, 40, 0.3)',
        line=dict(color='#D62828', width=2),
        name='Drawdown'
    ))
    
    # Mark maximum drawdown
    if dates and max_dd_idx < len(dates):
        x_coord = dates[max_dd_idx]
    else:
        x_coord = max_dd_idx
    
    fig.add_annotation(
        x=x_coord,
        y=max_dd,
        text=f"Max DD: {max_dd:.2f}%",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#D62828",
        ax=0,
        ay=-40
    )
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol} Drawdown",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        height=400,
        yaxis=dict(tickformat=".1f")
    )
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{symbol} Drawdown",
        alt_text=f"Drawdown curve. Maximum drawdown: {max_dd:.2f}%",
        plotly=fig.to_dict(),
        metadata={'max_drawdown': max_dd, 'max_dd_period': int(max_dd_idx)}
    )


async def build_rolling_volatility(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build rolling volatility chart"""
    
    # Extract inputs
    returns = spec.inputs.get('returns', [])
    dates = spec.inputs.get('dates', None)
    window = spec.inputs.get('window', 30)
    annualize = spec.inputs.get('annualize', True)
    symbol = spec.inputs.get('symbol', 'Portfolio')
    
    if not returns or len(returns) < window:
        fig = go.Figure()
        fig.update_layout(title="Insufficient data for rolling volatility")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Rolling Volatility",
            alt_text="Rolling volatility (insufficient data)",
            plotly=fig.to_dict()
        )
    
    # Calculate rolling volatility
    returns_series = pd.Series(returns)
    rolling_vol = returns_series.rolling(window=window).std()
    
    # Annualize if requested
    if annualize:
        rolling_vol *= np.sqrt(252)  # Assuming daily returns
        rolling_vol *= 100  # Convert to percentage
    
    # Create figure
    fig = go.Figure()
    
    # Downsample result series if needed to respect budget
    cfg = get_config()
    budget_points = getattr(cfg, 'charts_max_render_points', 2000)
    vol_y = rolling_vol.tolist()
    vol_x = dates if dates else list(range(len(rolling_vol)))
    if len(vol_y) > budget_points:
        vol_y = downsample_if_needed(vol_y, budget_points)
        if dates:
            vol_x = downsample_if_needed(vol_x, budget_points)
        else:
            vol_x = list(range(len(vol_y)))
    # Add volatility line
    fig.add_trace(go.Scatter(
        x=vol_x,
        y=vol_y,
        mode='lines',
        name=f'{window}-day Volatility',
        line=dict(color='#662E9B', width=2)
    ))
    
    # Add mean line
    mean_vol = rolling_vol.mean()
    if not pd.isna(mean_vol):
        fig.add_hline(
            y=mean_vol,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Mean: {mean_vol:.1f}%"
        )
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol} Rolling {window}-Day Volatility",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Volatility (%)" if annualize else "Volatility",
        template="plotly_white",
        height=400
    )
    
    current_vol = rolling_vol.iloc[-1] if not rolling_vol.empty else 0
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{symbol} Rolling Volatility",
        alt_text=f"Rolling {window}-day volatility. Current: {current_vol:.1f}%",
        plotly=fig.to_dict(),
        metadata={'window': window, 'current_vol': float(current_vol), 'mean_vol': float(mean_vol)}
    )


async def build_rolling_correlation(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build rolling correlation chart"""
    
    # Extract inputs
    returns1 = spec.inputs.get('returns1', [])
    returns2 = spec.inputs.get('returns2', [])
    dates = spec.inputs.get('dates', None)
    window = spec.inputs.get('window', 60)
    symbol1 = spec.inputs.get('symbol1', 'Asset 1')
    symbol2 = spec.inputs.get('symbol2', 'Asset 2')
    
    if not returns1 or not returns2 or len(returns1) != len(returns2) or len(returns1) < window:
        fig = go.Figure()
        fig.update_layout(title="Insufficient data for rolling correlation")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Rolling Correlation",
            alt_text="Rolling correlation (insufficient data)",
            plotly=fig.to_dict()
        )
    
    # Calculate rolling correlation
    df = pd.DataFrame({'r1': returns1, 'r2': returns2})
    rolling_corr = df['r1'].rolling(window=window).corr(df['r2'])
    
    # Create figure
    fig = go.Figure()
    
    # Downsample to respect budget
    cfg = get_config()
    budget_points = getattr(cfg, 'charts_max_render_points', 2000)
    corr_y = rolling_corr.tolist()
    corr_x = dates if dates else list(range(len(rolling_corr)))
    if len(corr_y) > budget_points:
        corr_y = downsample_if_needed(corr_y, budget_points)
        if dates:
            corr_x = downsample_if_needed(corr_x, budget_points)
        else:
            corr_x = list(range(len(corr_y)))
    # Add correlation line
    fig.add_trace(go.Scatter(
        x=corr_x,
        y=corr_y,
        mode='lines',
        name=f'{window}-day Correlation',
        line=dict(color='#06A77D', width=2)
    ))
    
    # Add reference lines
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.add_hline(y=1, line_dash="dot", line_color="gray")
    fig.add_hline(y=-1, line_dash="dot", line_color="gray")
    
    # Add mean line
    mean_corr = rolling_corr.mean()
    if not pd.isna(mean_corr):
        fig.add_hline(
            y=mean_corr,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Mean: {mean_corr:.2f}"
        )
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol1} vs {symbol2} Rolling Correlation",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Correlation",
        template="plotly_white",
        height=400,
        yaxis=dict(range=[-1.1, 1.1])
    )
    
    current_corr = rolling_corr.iloc[-1] if not rolling_corr.empty else 0
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"Rolling Correlation: {symbol1} vs {symbol2}",
        alt_text=f"Rolling {window}-day correlation. Current: {current_corr:.2f}",
        plotly=fig.to_dict(),
        metadata={'window': window, 'current_corr': float(current_corr), 'mean_corr': float(mean_corr)}
    )


# Schema definitions for new charts
DRAWDOWN_SCHEMA = ChartListItem(
    type=ChartType.DRAWDOWN_CURVE,
    inputs_schema={
        "type": "object",
        "properties": {
            "prices": {
                "type": "array",
                "items": {"type": "number"}
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            },
            "symbol": {"type": "string"}
        },
        "required": ["prices"]
    },
    description="Drawdown curve showing peak-to-trough declines",
    example_inputs={
        "prices": [100, 98, 95, 97, 94, 96],
        "symbol": "Portfolio"
    },
    constraints={"max_points": 5000}
)

ROLLING_VOL_SCHEMA = ChartListItem(
    type=ChartType.ROLLING_VOLATILITY,
    inputs_schema={
        "type": "object",
        "properties": {
            "returns": {
                "type": "array",
                "items": {"type": "number"}
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            },
            "window": {
                "type": "number",
                "description": "Rolling window size (default: 30)"
            },
            "annualize": {
                "type": "boolean",
                "description": "Annualize volatility (default: true)"
            },
            "symbol": {"type": "string"}
        },
        "required": ["returns"]
    },
    description="Rolling volatility over time",
    example_inputs={
        "returns": [0.01, -0.02, 0.015, -0.005, 0.02],
        "window": 30,
        "symbol": "Portfolio"
    },
    constraints={"min_window": 5, "max_points": 5000}
)

ROLLING_CORR_SCHEMA = ChartListItem(
    type=ChartType.ROLLING_CORRELATION,
    inputs_schema={
        "type": "object",
        "properties": {
            "returns1": {
                "type": "array",
                "items": {"type": "number"}
            },
            "returns2": {
                "type": "array",
                "items": {"type": "number"}
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            },
            "window": {
                "type": "number",
                "description": "Rolling window size (default: 60)"
            },
            "symbol1": {"type": "string"},
            "symbol2": {"type": "string"}
        },
        "required": ["returns1", "returns2"]
    },
    description="Rolling correlation between two assets",
    example_inputs={
        "returns1": [0.01, -0.02, 0.015, -0.005, 0.02],
        "returns2": [0.008, -0.015, 0.012, -0.003, 0.018],
        "window": 60,
        "symbol1": "AAPL",
        "symbol2": "MSFT"
    },
    constraints={"min_window": 10, "max_points": 5000}
)