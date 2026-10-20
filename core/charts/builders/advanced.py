"""
Advanced chart builders for portfolio analytics.

Sector allocation, efficient frontier, factor analysis, etc.
"""

from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

from ..models import ChartSpec, ChartFigure, ChartListItem, ChartType
from ..utils.downsampling import downsample_if_needed


async def build_sector_allocation_bar(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build sector allocation bar chart"""
    
    # Extract inputs
    sectors = spec.inputs.get('sectors', [])
    allocations = spec.inputs.get('allocations', [])
    benchmark = spec.inputs.get('benchmark', None)
    
    if not sectors or not allocations:
        fig = go.Figure()
        fig.update_layout(title="No sector data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Sector Allocation",
            alt_text="Sector allocation bar chart (no data)",
            plotly=fig.to_dict()
        )
    
    # Create figure
    fig = go.Figure()
    
    # Add portfolio bars
    fig.add_trace(go.Bar(
        x=sectors,
        y=allocations,
        name='Portfolio',
        marker_color='#2E86AB',
        text=[f'{a:.1f}%' for a in allocations],
        textposition='outside'
    ))
    
    # Add benchmark if provided
    if benchmark and len(benchmark) == len(sectors):
        fig.add_trace(go.Bar(
            x=sectors,
            y=benchmark,
            name='Benchmark',
            marker_color='#F77F00',
            text=[f'{b:.1f}%' for b in benchmark],
            textposition='outside'
        ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or "Sector Allocation",
        xaxis_title="Sector",
        yaxis_title="Allocation (%)",
        template="plotly_white",
        height=400,
        barmode='group',
        showlegend=bool(benchmark)
    )
    
    # Generate alt text
    top_sector = sectors[allocations.index(max(allocations))] if allocations else "N/A"
    top_alloc = max(allocations) if allocations else 0
    alt_text = f"Sector allocation. Top sector: {top_sector} ({top_alloc:.1f}%)"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Sector Allocation",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'num_sectors': len(sectors), 'has_benchmark': benchmark is not None}
    )


async def build_beta_scatter(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build beta scatter plot (risk vs return)"""
    
    # Extract inputs
    tickers = spec.inputs.get('tickers', [])
    betas = spec.inputs.get('betas', [])
    returns = spec.inputs.get('returns', [])
    sizes = spec.inputs.get('sizes', None)  # Optional portfolio weights
    
    if not tickers or not betas or not returns:
        fig = go.Figure()
        fig.update_layout(title="No beta/return data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Risk-Return Scatter",
            alt_text="Beta scatter plot (no data)",
            plotly=fig.to_dict()
        )
    
    # Create figure
    fig = go.Figure()
    
    # Prepare marker sizes
    if sizes and len(sizes) == len(tickers):
        # Scale sizes for visibility
        marker_sizes = [s * 100 for s in sizes]
    else:
        marker_sizes = [10] * len(tickers)
    
    # Add scatter plot
    fig.add_trace(go.Scatter(
        x=betas,
        y=returns,
        mode='markers+text',
        text=tickers,
        textposition="top center",
        marker=dict(
            size=marker_sizes,
            color=returns,
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Return %"),
            line=dict(width=1, color='white')
        ),
        hovertemplate='<b>%{text}</b><br>Beta: %{x:.2f}<br>Return: %{y:.1f}%<extra></extra>'
    ))
    
    # Add reference lines
    fig.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
    fig.add_vline(x=1, line_dash="dot", line_color="gray", line_width=1)
    
    # Add quadrant labels
    x_range = [min(betas) - 0.1, max(betas) + 0.1] if betas else [-0.5, 2]
    y_range = [min(returns) - 1, max(returns) + 1] if returns else [-10, 10]
    
    fig.add_annotation(
        x=x_range[0] + 0.1, y=y_range[1] - 1,
        text="Low Risk<br>High Return",
        showarrow=False,
        font=dict(color="green", size=10),
        opacity=0.5
    )
    
    fig.add_annotation(
        x=x_range[1] - 0.1, y=y_range[1] - 1,
        text="High Risk<br>High Return",
        showarrow=False,
        font=dict(color="orange", size=10),
        opacity=0.5
    )
    
    # Update layout
    fig.update_layout(
        title=spec.title or "Risk-Return Profile (Beta vs Return)",
        xaxis_title="Beta (Market Risk)",
        yaxis_title="Return (%)",
        template="plotly_white",
        height=450,
        xaxis=dict(range=x_range),
        yaxis=dict(range=y_range)
    )
    
    # Generate alt text
    avg_beta = np.mean(betas) if betas else 0
    avg_return = np.mean(returns) if returns else 0
    alt_text = f"Risk-return scatter. Avg beta: {avg_beta:.2f}, Avg return: {avg_return:.1f}%"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Risk-Return Profile",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'num_assets': len(tickers), 'avg_beta': avg_beta, 'avg_return': avg_return}
    )


async def build_efficient_frontier(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build efficient frontier chart with professional modern styling"""
    
    frontier_returns = spec.inputs.get('frontier_returns', [])
    frontier_risks = spec.inputs.get('frontier_risks', [])
    portfolios = spec.inputs.get('portfolios', {})
    current = spec.inputs.get('current', None)
    
    if not frontier_returns or not frontier_risks:
        fig = go.Figure()
        fig.update_layout(title="No frontier data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Efficient Frontier",
            alt_text="Efficient frontier chart (no data)",
            plotly=fig.to_dict()
        )
    
    fig = go.Figure()
    
    # Add gradient-filled feasible region
    fig.add_trace(go.Scatter(
        x=frontier_risks,
        y=[min(frontier_returns) - 2] * len(frontier_risks),
        mode='lines',
        line=dict(color='rgba(0,0,0,0)'),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Efficient frontier with gradient fill to base
    fig.add_trace(go.Scatter(
        x=frontier_risks,
        y=frontier_returns,
        mode='lines',
        name='Efficient Frontier',
        line=dict(
            color='#6366F1',
            width=4,
            shape='spline'
        ),
        fill='tonexty',
        fillcolor='rgba(99, 102, 241, 0.08)',
        hovertemplate='<b>Efficient Frontier</b><br>Risk: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>'
    ))
    
    # Add frontier glow effect
    fig.add_trace(go.Scatter(
        x=frontier_risks,
        y=frontier_returns,
        mode='lines',
        line=dict(color='rgba(99, 102, 241, 0.3)', width=12, shape='spline'),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Professional portfolio markers
    portfolio_styles = {
        'max_sharpe': {'color': '#10B981', 'symbol': 'star', 'size': 18, 'label': 'Max Sharpe'},
        'max sharpe': {'color': '#10B981', 'symbol': 'star', 'size': 18, 'label': 'Max Sharpe'},
        'min_variance': {'color': '#3B82F6', 'symbol': 'diamond', 'size': 16, 'label': 'Min Variance'},
        'min variance': {'color': '#3B82F6', 'symbol': 'diamond', 'size': 16, 'label': 'Min Variance'},
        'risk_parity': {'color': '#8B5CF6', 'symbol': 'hexagon', 'size': 16, 'label': 'Risk Parity'},
        'target_return': {'color': '#F59E0B', 'symbol': 'circle', 'size': 14, 'label': 'Target Return'}
    }
    
    for name, portfolio in portfolios.items():
        if 'risk' in portfolio and 'return' in portfolio:
            name_lower = name.lower().replace('_', ' ')
            style = portfolio_styles.get(name_lower, portfolio_styles.get(name.lower(), 
                    {'color': '#6B7280', 'symbol': 'circle', 'size': 14, 'label': name.replace('_', ' ').title()}))
            
            # Outer glow
            fig.add_trace(go.Scatter(
                x=[portfolio['risk']],
                y=[portfolio['return']],
                mode='markers',
                marker=dict(
                    size=style['size'] + 10,
                    color=style['color'],
                    opacity=0.2
                ),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            # Main marker
            fig.add_trace(go.Scatter(
                x=[portfolio['risk']],
                y=[portfolio['return']],
                mode='markers',
                name=style['label'],
                marker=dict(
                    size=style['size'],
                    color=style['color'],
                    symbol=style['symbol'],
                    line=dict(width=2, color='white')
                ),
                hovertemplate=f"<b>{style['label']}</b><br>Risk: %{{x:.2f}}%<br>Return: %{{y:.2f}}%<extra></extra>"
            ))
    
    # Current portfolio with prominent styling
    if current and 'risk' in current and 'return' in current:
        # Pulsing glow effect
        fig.add_trace(go.Scatter(
            x=[current['risk']],
            y=[current['return']],
            mode='markers',
            marker=dict(size=28, color='#EF4444', opacity=0.15),
            showlegend=False,
            hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=[current['risk']],
            y=[current['return']],
            mode='markers',
            name='Current Portfolio',
            marker=dict(
                size=16,
                color='#EF4444',
                symbol='x',
                line=dict(width=3, color='white')
            ),
            hovertemplate='<b>Current Portfolio</b><br>Risk: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>'
        ))
    
    # Professional layout
    fig.update_layout(
        title=dict(
            text=spec.title or "Efficient Frontier",
            font=dict(size=22, color='#1F2937', family='Inter, system-ui, sans-serif'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Risk (Annualized Volatility %)", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.15)',
            zeroline=False,
            showline=True,
            linecolor='#E5E7EB',
            ticksuffix='%'
        ),
        yaxis=dict(
            title=dict(text="Expected Return (%)", font=dict(size=13, color='#6B7280')),
            showgrid=True,
            gridcolor='rgba(156, 163, 175, 0.15)',
            zeroline=False,
            showline=True,
            linecolor='#E5E7EB',
            ticksuffix='%'
        ),
        plot_bgcolor='rgba(249, 250, 251, 1)',
        paper_bgcolor='white',
        height=520,
        margin=dict(l=70, r=30, t=80, b=60),
        hovermode='closest',
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.02,
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='#E5E7EB',
            borderwidth=1,
            font=dict(size=11)
        ),
        font=dict(family='Inter, system-ui, sans-serif')
    )
    
    max_return = max(frontier_returns) if frontier_returns else 0
    min_risk = min(frontier_risks) if frontier_risks else 0
    alt_text = f"Efficient frontier. Max return: {max_return:.1f}%, Min risk: {min_risk:.1f}%"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Efficient Frontier",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={
            'max_return': max_return,
            'min_risk': min_risk,
            'num_portfolios': len(portfolios)
        }
    )


async def build_factor_exposure(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build factor exposure heatmap with professional modern styling"""
    
    factors = spec.inputs.get('factors', [])
    tickers = spec.inputs.get('tickers', [])
    exposures = spec.inputs.get('exposures', [])
    
    if not factors or not tickers or not exposures:
        fig = go.Figure()
        fig.update_layout(title="No factor exposure data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Factor Exposures",
            alt_text="Factor exposure heatmap (no data)",
            plotly=fig.to_dict()
        )
    
    # Custom colorscale: deep red -> white -> deep teal
    custom_colorscale = [
        [0.0, '#DC2626'],      # Deep red for negative
        [0.25, '#FCA5A5'],     # Light red
        [0.5, '#F9FAFB'],      # Near white for zero
        [0.75, '#6EE7B7'],     # Light teal
        [1.0, '#059669']       # Deep teal for positive
    ]
    
    # Calculate max absolute value for symmetric scale
    flat_exposures = [val for row in exposures for val in row]
    max_abs = max(abs(min(flat_exposures)), abs(max(flat_exposures))) if flat_exposures else 1
    
    fig = go.Figure(data=go.Heatmap(
        z=exposures,
        x=factors,
        y=tickers,
        colorscale=custom_colorscale,
        zmid=0,
        zmin=-max_abs,
        zmax=max_abs,
        text=[[f'{val:+.2f}' for val in row] for row in exposures],
        texttemplate='%{text}',
        textfont=dict(size=11, color='#1F2937', family='Inter, system-ui, sans-serif'),
        colorbar=dict(
            title=dict(text="Factor Beta", font=dict(size=12, color='#374151')),
            thickness=18,
            len=0.8,
            tickfont=dict(size=10),
            tickformat='+.1f',
            outlinewidth=1,
            outlinecolor='#E5E7EB'
        ),
        hovertemplate='<b>%{y}</b><br>Factor: %{x}<br>Exposure: %{z:+.3f}<extra></extra>',
        xgap=2,
        ygap=2
    ))
    
    # Add cell borders for clarity
    fig.update_traces(
        showscale=True
    )
    
    # Professional layout
    fig.update_layout(
        title=dict(
            text=spec.title or "Factor Exposures",
            font=dict(size=20, color='#1F2937', family='Inter, system-ui, sans-serif'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(text="Risk Factors", font=dict(size=13, color='#6B7280')),
            side='bottom',
            tickangle=-30,
            tickfont=dict(size=11, color='#374151'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB'
        ),
        yaxis=dict(
            title=dict(text="Assets", font=dict(size=13, color='#6B7280')),
            autorange='reversed',
            tickfont=dict(size=11, color='#374151'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB'
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=max(420, 45 * len(tickers) + 100),
        width=max(500, 80 * len(factors) + 150),
        margin=dict(l=100, r=80, t=80, b=80),
        font=dict(family='Inter, system-ui, sans-serif')
    )
    
    # Add summary annotation
    avg_exposure = np.mean(flat_exposures)
    fig.add_annotation(
        x=0.02, y=-0.12,
        xref='paper', yref='paper',
        text=f"Avg Exposure: {avg_exposure:+.3f} | Range: [{min(flat_exposures):+.2f}, {max(flat_exposures):+.2f}]",
        showarrow=False,
        font=dict(size=10, color='#6B7280'),
        align='left'
    )
    
    max_exposure = max(flat_exposures) if flat_exposures else 0
    min_exposure = min(flat_exposures) if flat_exposures else 0
    alt_text = f"Factor exposure heatmap. Range: {min_exposure:.2f} to {max_exposure:.2f}"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Factor Exposures",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={
            'num_factors': len(factors),
            'num_assets': len(tickers),
            'max_exposure': max_exposure,
            'min_exposure': min_exposure
        }
    )


async def build_factor_contribution_bar(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build factor contribution bar chart"""
    
    # Extract inputs
    factors = spec.inputs.get('factors', [])
    contributions = spec.inputs.get('contributions', [])
    specific_risk = spec.inputs.get('specific_risk', 0)
    
    if not factors or not contributions:
        fig = go.Figure()
        fig.update_layout(title="No factor contribution data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Factor Contributions",
            alt_text="Factor contribution bar chart (no data)",
            plotly=fig.to_dict()
        )
    
    # Prepare data with specific risk
    all_factors = factors + ['Specific']
    all_contributions = contributions + [specific_risk]
    
    # Sort by absolute contribution
    sorted_data = sorted(zip(all_factors, all_contributions), 
                        key=lambda x: abs(x[1]), reverse=True)
    sorted_factors, sorted_contribs = zip(*sorted_data)
    
    # Color based on positive/negative
    colors = ['#26A653' if c >= 0 else '#EF5350' for c in sorted_contribs]
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=list(sorted_factors),
        y=list(sorted_contribs),
        marker_color=colors,
        text=[f'{c:.2f}%' for c in sorted_contribs],
        textposition='outside',
        hovertemplate='%{x}<br>Contribution: %{y:.2f}%<extra></extra>'
    ))
    
    # Add total line
    total_contribution = sum(all_contributions)
    fig.add_hline(
        y=total_contribution,
        line_dash="dash",
        line_color="black",
        annotation_text=f"Total: {total_contribution:.2f}%"
    )
    
    # Update layout
    fig.update_layout(
        title=spec.title or "Factor Contributions to Risk",
        xaxis_title="Factor",
        yaxis_title="Contribution (%)",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    
    # Generate alt text
    top_factor = sorted_factors[0]
    top_contrib = sorted_contribs[0]
    alt_text = f"Factor contributions. Top factor: {top_factor} ({top_contrib:.2f}%)"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Factor Contributions",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={
            'num_factors': len(factors),
            'total_contribution': total_contribution,
            'specific_risk': specific_risk
        }
    )


# Schema definitions
SECTOR_ALLOCATION_SCHEMA = ChartListItem(
    type=ChartType.SECTOR_ALLOCATION_BAR,
    inputs_schema={
        "type": "object",
        "properties": {
            "sectors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "allocations": {
                "type": "array",
                "items": {"type": "number"}
            },
            "benchmark": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Optional benchmark allocations"
            }
        },
        "required": ["sectors", "allocations"]
    },
    description="Bar chart showing sector allocations",
    example_inputs={
        "sectors": ["Tech", "Finance", "Healthcare"],
        "allocations": [40, 30, 30],
        "benchmark": [35, 25, 40]
    },
    constraints={"max_sectors": 20}
)

BETA_SCATTER_SCHEMA = ChartListItem(
    type=ChartType.BETA_SCATTER,
    inputs_schema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"}
            },
            "betas": {
                "type": "array",
                "items": {"type": "number"}
            },
            "returns": {
                "type": "array",
                "items": {"type": "number"}
            },
            "sizes": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Optional sizes (e.g., portfolio weights)"
            }
        },
        "required": ["tickers", "betas", "returns"]
    },
    description="Scatter plot of beta vs returns",
    example_inputs={
        "tickers": ["AAPL", "MSFT", "GOOGL"],
        "betas": [1.2, 0.9, 1.1],
        "returns": [15, 12, 18],
        "sizes": [0.4, 0.3, 0.3]
    },
    constraints={"max_assets": 50}
)

EFFICIENT_FRONTIER_SCHEMA = ChartListItem(
    type=ChartType.EFFICIENT_FRONTIER,
    inputs_schema={
        "type": "object",
        "properties": {
            "frontier_returns": {
                "type": "array",
                "items": {"type": "number"}
            },
            "frontier_risks": {
                "type": "array",
                "items": {"type": "number"}
            },
            "portfolios": {
                "type": "object",
                "description": "Special portfolios (max_sharpe, min_variance, etc.)"
            },
            "current": {
                "type": "object",
                "description": "Current portfolio position"
            }
        },
        "required": ["frontier_returns", "frontier_risks"]
    },
    description="Efficient frontier with optimal portfolios",
    example_inputs={
        "frontier_returns": [5, 7, 9, 11],
        "frontier_risks": [10, 12, 15, 20],
        "portfolios": {
            "max_sharpe": {"risk": 14, "return": 9.5},
            "min_variance": {"risk": 10, "return": 5}
        }
    },
    constraints={"max_points": 500}
)

FACTOR_EXPOSURE_SCHEMA = ChartListItem(
    type=ChartType.FACTOR_EXPOSURE,
    inputs_schema={
        "type": "object",
        "properties": {
            "factors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "tickers": {
                "type": "array",
                "items": {"type": "string"}
            },
            "exposures": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "number"}
                },
                "description": "2D array of exposures [assets x factors]"
            }
        },
        "required": ["factors", "tickers", "exposures"]
    },
    description="Heatmap showing factor exposures",
    example_inputs={
        "factors": ["Market", "Size", "Value"],
        "tickers": ["AAPL", "MSFT"],
        "exposures": [[1.2, 0.3, -0.1], [0.9, -0.2, 0.4]]
    },
    constraints={"max_factors": 20, "max_assets": 50}
)

FACTOR_CONTRIBUTION_SCHEMA = ChartListItem(
    type=ChartType.FACTOR_CONTRIBUTION_BAR,
    inputs_schema={
        "type": "object",
        "properties": {
            "factors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "contributions": {
                "type": "array",
                "items": {"type": "number"}
            },
            "specific_risk": {
                "type": "number",
                "description": "Specific (idiosyncratic) risk contribution"
            }
        },
        "required": ["factors", "contributions"]
    },
    description="Bar chart showing factor contributions to risk",
    example_inputs={
        "factors": ["Market", "Size", "Value"],
        "contributions": [5.2, 1.3, -0.8],
        "specific_risk": 2.1
    },
    constraints={"max_factors": 20}
)