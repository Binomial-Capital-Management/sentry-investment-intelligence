"""Chart builders for Correlation Swap Canvas tool."""

import plotly.graph_objects as go
from typing import Dict, Any, List, Optional
import numpy as np


def build_correlation_timeseries_chart(
    correlation_series: List[tuple],
    strike_correlation: float,
    realized_correlation: float,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build rolling correlation time series chart with strike level.
    
    Args:
        correlation_series: List of (date_str, correlation) tuples
        strike_correlation: Strike correlation level
        realized_correlation: Average realized correlation
        asset_x: First asset ticker
        asset_y: Second asset ticker
    
    Returns:
        Canvas chart dict or None if data invalid
    """
    if not correlation_series:
        return None
    
    try:
        dates = [item[0] for item in correlation_series]
        correlations = [item[1] for item in correlation_series]
        
        fig = go.Figure()
        
        # Rolling correlation line
        fig.add_trace(go.Scatter(
            x=dates,
            y=correlations,
            mode='lines',
            name='Rolling Correlation',
            line=dict(color='#3b82f6', width=2.5),
            hovertemplate='<b>%{x}</b><br>Correlation: %{y:.4f}<extra></extra>'
        ))
        
        # Strike level line
        fig.add_trace(go.Scatter(
            x=[dates[0], dates[-1]],
            y=[strike_correlation, strike_correlation],
            mode='lines',
            name='Strike Level',
            line=dict(color='#ef4444', width=2, dash='dash'),
            hovertemplate=f'Strike: {strike_correlation:.4f}<extra></extra>'
        ))
        
        # Average realized level
        fig.add_trace(go.Scatter(
            x=[dates[0], dates[-1]],
            y=[realized_correlation, realized_correlation],
            mode='lines',
            name='Avg Realized',
            line=dict(color='#10b981', width=2, dash='dot'),
            hovertemplate=f'Avg Realized: {realized_correlation:.4f}<extra></extra>'
        ))
        
        # Styling
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Rolling Correlation vs Strike",
            xaxis_title="Date",
            yaxis_title="Correlation",
            template="plotly_white",
            width=1200,
            height=500,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
        )
        
        fig.update_yaxes(range=[-1.05, 1.05])
        
        return {
            "id": "correlation_timeseries",
            "title": f"{asset_x} vs {asset_y} Rolling Correlation",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building correlation timeseries chart: {e}")
        return None


def build_payoff_breakdown_chart(
    swap_value: float,
    payoff_at_maturity: float,
    notional: float,
    correlation_difference: float,
    discount_factor: float
) -> Optional[Dict[str, Any]]:
    """
    Build waterfall chart showing swap value components.
    
    Args:
        swap_value: Present value of swap
        payoff_at_maturity: Undiscounted payoff
        notional: Swap notional
        correlation_difference: Realized - Strike
        discount_factor: PV discount factor
    
    Returns:
        Canvas chart dict or None if invalid
    """
    try:
        # Build waterfall components
        labels = [
            'Notional',
            'Corr Diff',
            'Payoff',
            'Discount',
            'PV'
        ]
        
        # Calculate intermediate values
        corr_effect = notional * correlation_difference - notional
        discount_effect = swap_value - payoff_at_maturity
        
        values = [
            notional,
            corr_effect,
            payoff_at_maturity - notional - corr_effect,
            discount_effect,
            swap_value - payoff_at_maturity - discount_effect
        ]
        
        measures = ['absolute', 'relative', 'total', 'relative', 'total']
        
        fig = go.Figure(go.Waterfall(
            name="Payoff",
            orientation="v",
            measure=measures,
            x=labels,
            y=values,
            text=[f"${v:,.0f}" for v in values],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#10b981"}},
            decreasing={"marker": {"color": "#ef4444"}},
            totals={"marker": {"color": "#3b82f6"}}
        ))
        
        fig.update_layout(
            title="Swap Payoff Breakdown",
            xaxis_title="Component",
            yaxis_title="Value ($)",
            template="plotly_white",
            width=1200,
            height=500,
            showlegend=False
        )
        
        return {
            "id": "payoff_breakdown",
            "title": "Correlation Swap Payoff Breakdown",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building payoff breakdown chart: {e}")
        return None


def build_sensitivity_chart(
    notional: float,
    strike_correlation: float,
    realized_correlation: float,
    discount_factor: float,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build P&L sensitivity chart across correlation scenarios.
    
    Args:
        notional: Swap notional
        strike_correlation: Strike correlation
        realized_correlation: Actual realized correlation
        discount_factor: PV discount factor
        asset_x: First asset ticker
        asset_y: Second asset ticker
    
    Returns:
        Canvas chart dict or None if invalid
    """
    try:
        # Generate correlation scenario range
        corr_range = np.linspace(-0.95, 0.95, 100)
        
        # Calculate P&L for each scenario
        pnl_values = [
            notional * (corr - strike_correlation) * discount_factor
            for corr in corr_range
        ]
        
        fig = go.Figure()
        
        # P&L curve
        fig.add_trace(go.Scatter(
            x=corr_range,
            y=pnl_values,
            mode='lines',
            name='Swap P&L',
            line=dict(color='#3b82f6', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)',
            hovertemplate='<b>Corr: %{x:.3f}</b><br>P&L: $%{y:,.0f}<extra></extra>'
        ))
        
        # Strike level (zero P&L)
        fig.add_vline(
            x=strike_correlation,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text=f"Strike ({strike_correlation:.3f})",
            annotation_position="top"
        )
        
        # Realized correlation marker
        realized_pnl = notional * (realized_correlation - strike_correlation) * discount_factor
        fig.add_trace(go.Scatter(
            x=[realized_correlation],
            y=[realized_pnl],
            mode='markers',
            name='Realized',
            marker=dict(size=12, color='#10b981', symbol='diamond'),
            hovertemplate=f'<b>Realized</b><br>Corr: {realized_correlation:.4f}<br>P&L: ${realized_pnl:,.0f}<extra></extra>'
        ))
        
        # Styling
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Swap P&L Sensitivity",
            xaxis_title="Realized Correlation",
            yaxis_title="Swap P&L ($)",
            template="plotly_white",
            width=1200,
            height=500,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8", opacity=0.5)
        
        return {
            "id": "pnl_sensitivity",
            "title": "P&L Sensitivity to Realized Correlation",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building sensitivity chart: {e}")
        return None


def build_monte_carlo_distribution_chart(
    payoff_distribution: list,
    expected_value: float,
    percentiles: dict,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build histogram of Monte Carlo payoff distribution for Canvas.
    
    Args:
        payoff_distribution: List of simulated PV values
        expected_value: Mean PV
        percentiles: Dict with p5, p25, p50, p75, p95
        asset_x, asset_y: Asset labels
    
    Returns:
        Canvas chart dict or None if error
    """
    try:
        import numpy as np
        
        fig = go.Figure()
        
        # Histogram bars (color-coded by value)
        colors = ['#ef4444' if v < 0 else '#10b981' if v > 0 else '#94a3b8' for v in payoff_distribution]
        
        fig.add_trace(go.Histogram(
            x=payoff_distribution,
            nbinsx=50,
            name='Payoff Distribution',
            marker=dict(
                color='#3b82f6',
                opacity=0.7,
                line=dict(color='white', width=0.5)
            ),
            hovertemplate='P&L: $%{x:,.0f}<br>Frequency: %{y}<extra></extra>'
        ))
        
        # Add vertical lines for key statistics
        # Expected value
        fig.add_vline(
            x=expected_value,
            line_dash="solid",
            line_color="#1e40af",
            line_width=3,
            annotation_text=f"Expected: ${expected_value/1e6:.1f}M",
            annotation_position="top"
        )
        
        # 5th percentile (downside risk)
        fig.add_vline(
            x=percentiles['p5'],
            line_dash="dash",
            line_color="#ef4444",
            line_width=2,
            annotation_text=f"P5: ${percentiles['p5']/1e6:.1f}M",
            annotation_position="bottom left"
        )
        
        # 95th percentile (upside)
        fig.add_vline(
            x=percentiles['p95'],
            line_dash="dash",
            line_color="#10b981",
            line_width=2,
            annotation_text=f"P95: ${percentiles['p95']/1e6:.1f}M",
            annotation_position="bottom right"
        )
        
        # Median (50th)
        fig.add_vline(
            x=percentiles['p50'],
            line_dash="dot",
            line_color="#8b5cf6",
            line_width=2,
            annotation_text=f"Median: ${percentiles['p50']/1e6:.1f}M",
            annotation_position="top left"
        )
        
        # Add shaded region for 90% confidence interval
        fig.add_vrect(
            x0=percentiles['p5'],
            x1=percentiles['p95'],
            fillcolor="#3b82f6",
            opacity=0.1,
            layer="below",
            line_width=0
        )
        
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Monte Carlo P&L Distribution",
            xaxis_title="Swap Present Value ($)",
            yaxis_title="Frequency (Number of Simulations)",
            template="plotly_white",
            width=1200,
            height=500,
            hovermode='x',
            showlegend=False
        )
        
        # Add zero line
        fig.add_vline(x=0, line_dash="solid", line_color="#94a3b8", line_width=1, opacity=0.5)
        
        return {
            "id": "mc_payoff_distribution",
            "title": "Monte Carlo Payoff Distribution",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building MC payoff distribution chart: {e}")
        return None


def build_correlation_distribution_chart(
    correlation_distribution: list,
    mean_correlation: float,
    strike_correlation: float,
    historical_correlation: float,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build histogram of simulated correlation values for Canvas.
    
    Args:
        correlation_distribution: List of simulated correlation values
        mean_correlation: Mean simulated correlation
        strike_correlation: Strike level
        historical_correlation: Historical correlation
        asset_x, asset_y: Asset labels
    
    Returns:
        Canvas chart dict or None if error
    """
    try:
        fig = go.Figure()
        
        # Histogram
        fig.add_trace(go.Histogram(
            x=correlation_distribution,
            nbinsx=40,
            name='Simulated Correlation',
            marker=dict(color='#3b82f6', opacity=0.7),
            hovertemplate='Correlation: %{x:.4f}<br>Frequency: %{y}<extra></extra>'
        ))
        
        # Strike line (red)
        fig.add_vline(
            x=strike_correlation,
            line_dash="dash",
            line_color="#ef4444",
            line_width=3,
            annotation_text=f"Strike: {strike_correlation:.3f}",
            annotation_position="top left"
        )
        
        # Mean simulated line (green)
        fig.add_vline(
            x=mean_correlation,
            line_dash="solid",
            line_color="#10b981",
            line_width=3,
            annotation_text=f"Mean Simulated: {mean_correlation:.3f}",
            annotation_position="top right"
        )
        
        # Historical line (orange)
        fig.add_vline(
            x=historical_correlation,
            line_dash="dot",
            line_color="#f59e0b",
            line_width=2,
            annotation_text=f"Historical: {historical_correlation:.3f}",
            annotation_position="bottom"
        )
        
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Simulated Correlation Distribution",
            xaxis_title="Correlation",
            yaxis_title="Frequency (Number of Simulations)",
            template="plotly_white",
            width=1200,
            height=500,
            showlegend=False
        )
        
        fig.update_xaxes(range=[-1.05, 1.05])
        
        return {
            "id": "mc_correlation_distribution",
            "title": "Simulated Correlation Distribution",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building correlation distribution chart: {e}")
        return None


def build_price_paths_chart(
    sample_paths_x: list,
    sample_paths_y: list,
    current_price_x: float,
    current_price_y: float,
    days_remaining: int,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build chart showing sample Monte Carlo price path simulations.
    
    Args:
        sample_paths_x: List of sample paths for asset X (list of lists)
        sample_paths_y: List of sample paths for asset Y (list of lists)
        current_price_x: Current price of asset X
        current_price_y: Current price of asset Y
        days_remaining: Days until maturity
        asset_x, asset_y: Asset labels
    
    Returns:
        Canvas chart dict or None if error
    """
    try:
        import numpy as np
        
        if not sample_paths_x or not sample_paths_y:
            return None
        
        num_paths = len(sample_paths_x)
        days = len(sample_paths_x[0]) - 1  # Paths include t=0
        time_steps = list(range(days + 1))
        
        fig = go.Figure()
        
        # Plot sample paths for asset X (blue, thin, transparent)
        for i, path in enumerate(sample_paths_x):
            fig.add_trace(go.Scatter(
                x=time_steps,
                y=path,
                mode='lines',
                name=f'{asset_x} Path {i+1}' if i < 3 else None,  # Only name first 3 for legend
                line=dict(color='rgba(59, 130, 246, 0.3)', width=1),
                showlegend=(i < 3),
                legendgroup='asset_x',
                hovertemplate=f'<b>{asset_x}</b><br>Day: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>'
            ))
        
        # Plot sample paths for asset Y (green, thin, transparent)
        for i, path in enumerate(sample_paths_y):
            fig.add_trace(go.Scatter(
                x=time_steps,
                y=path,
                mode='lines',
                name=f'{asset_y} Path {i+1}' if i < 3 else None,
                line=dict(color='rgba(16, 185, 129, 0.3)', width=1),
                showlegend=(i < 3),
                legendgroup='asset_y',
                hovertemplate=f'<b>{asset_y}</b><br>Day: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>'
            ))
        
        # Add current price markers (starting points)
        fig.add_trace(go.Scatter(
            x=[0],
            y=[current_price_x],
            mode='markers',
            name=f'{asset_x} Current',
            marker=dict(size=10, color='#1e40af', symbol='diamond'),
            hovertemplate=f'<b>{asset_x} Current</b><br>Price: ${current_price_x:.2f}<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=[0],
            y=[current_price_y],
            mode='markers',
            name=f'{asset_y} Current',
            marker=dict(size=10, color='#059669', symbol='diamond'),
            hovertemplate=f'<b>{asset_y} Current</b><br>Price: ${current_price_y:.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Monte Carlo Price Paths ({num_paths} samples)",
            xaxis_title=f"Days into Future (0 to {days_remaining})",
            yaxis_title="Price ($)",
            template="plotly_white",
            width=1200,
            height=500,
            hovermode='closest',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
        )
        
        return {
            "id": "mc_price_paths",
            "title": "Monte Carlo Simulated Price Paths",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building price paths chart: {e}")
        return None


def build_sensitivity_chart_with_confidence(
    notional: float,
    strike_correlation: float,
    realized_correlation: float,
    discount_factor: float,
    percentiles: dict,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build P&L sensitivity chart with confidence bands from Monte Carlo.
    
    Args:
        notional: Swap notional
        strike_correlation: Strike
        realized_correlation: Mean simulated correlation
        discount_factor: Discount factor
        percentiles: Dict with p5, p25, p50, p75, p95 as correlation values
        asset_x, asset_y: Asset labels
    
    Returns:
        Canvas chart dict or None if error
    """
    try:
        import numpy as np
        
        # Generate correlation scenario range
        corr_range = np.linspace(-0.95, 0.95, 100)
        
        # Calculate P&L for each scenario (mean)
        pnl_values = [
            notional * (corr - strike_correlation) * discount_factor
            for corr in corr_range
        ]
        
        fig = go.Figure()
        
        # Main P&L curve
        fig.add_trace(go.Scatter(
            x=corr_range,
            y=pnl_values,
            mode='lines',
            name='Expected P&L',
            line=dict(color='#3b82f6', width=3),
            hovertemplate='<b>Corr: %{x:.3f}</b><br>P&L: $%{y:,.0f}<extra></extra>'
        ))
        
        # If we have percentile correlations (not P&L), we can show uncertainty
        # For now, show the realized/mean simulated correlation point
        realized_pnl = notional * (realized_correlation - strike_correlation) * discount_factor
        
        fig.add_trace(go.Scatter(
            x=[realized_correlation],
            y=[realized_pnl],
            mode='markers',
            name='Mean Simulated',
            marker=dict(size=14, color='#10b981', symbol='diamond', line=dict(width=2, color='white')),
            hovertemplate=f'<b>Mean Simulated</b><br>Corr: {realized_correlation:.4f}<br>P&L: ${realized_pnl:,.0f}<extra></extra>'
        ))
        
        # Strike line
        fig.add_vline(
            x=strike_correlation,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text=f"Strike ({strike_correlation:.3f})",
            annotation_position="top"
        )
        
        # Styling
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - P&L Sensitivity (Monte Carlo)",
            xaxis_title="Realized Correlation",
            yaxis_title="Swap P&L ($)",
            template="plotly_white",
            width=1200,
            height=500,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8", opacity=0.5)
        
        return {
            "id": "mc_pnl_sensitivity",
            "title": "P&L Sensitivity with Monte Carlo",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        print(f"Error building MC sensitivity chart: {e}")
        return None
