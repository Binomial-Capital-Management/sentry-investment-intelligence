"""
Portfolio analytics chart builders.

Allocation, correlation, sector breakdowns, etc.
"""

from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

from ..models import ChartSpec, ChartFigure, ChartListItem, ChartType


async def build_allocation_pie(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build portfolio allocation pie chart"""
    
    # Extract inputs
    symbols = spec.inputs.get('symbols', [])
    weights = spec.inputs.get('weights', [])
    values = spec.inputs.get('values', None)
    
    if not symbols or not weights:
        # Empty chart
        fig = go.Figure()
        fig.update_layout(title="No allocation data available")
        return ChartFigure(
            id=spec.id,
            title="Portfolio Allocation",
            alt_text="Portfolio allocation (no data)",
            plotly=fig.to_dict()
        )
    
    # Create pie chart
    fig = go.Figure(data=[go.Pie(
        labels=symbols,
        values=values if values else weights,
        hole=0.3,  # Donut chart
        marker=dict(
            colors=px.colors.qualitative.Set2[:len(symbols)],
            line=dict(color='white', width=2)
        ),
        textinfo='label+percent',
        textposition='outside',
        hovertemplate='<b>%{label}</b><br>Weight: %{percent}<br>Value: $%{value:,.0f}<extra></extra>'
    )])
    
    # Update layout
    fig.update_layout(
        title=spec.title or "Portfolio Allocation",
        template="plotly_white",
        height=450,
        margin=dict(l=50, r=50, t=50, b=50),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05
        )
    )
    
    # Generate alt text
    top_holding = symbols[weights.index(max(weights))] if weights else "N/A"
    top_weight = max(weights) * 100 if weights else 0
    alt_text = f"Portfolio allocation across {len(symbols)} holdings. Top: {top_holding} ({top_weight:.1f}%)"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Portfolio Allocation",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'num_holdings': len(symbols)}
    )


async def build_correlation_matrix(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build correlation matrix heatmap with professional modern styling"""
    
    symbols = spec.inputs.get('symbols', [])
    matrix = spec.inputs.get('matrix', [])
    
    if not matrix or not symbols:
        fig = go.Figure()
        fig.update_layout(title="No correlation data available")
        return ChartFigure(
            id=spec.id,
            title="Correlation Matrix",
            alt_text="Correlation matrix (no data)",
            plotly=fig.to_dict()
        )
    
    # Cap at 20x20 matrix
    max_symbols = 20
    if len(symbols) > max_symbols:
        symbols = symbols[:max_symbols]
        matrix = [row[:max_symbols] for row in matrix[:max_symbols]]
    
    # Custom colorscale: deep coral -> white -> deep teal
    custom_colorscale = [
        [0.0, '#B91C1C'],      # Deep red for -1
        [0.25, '#FCA5A5'],     # Light coral
        [0.5, '#FAFAFA'],      # Near white for 0
        [0.75, '#6EE7B7'],     # Light mint
        [1.0, '#047857']       # Deep teal for +1
    ]
    
    # Create text annotations with conditional formatting
    text_matrix = []
    for i, row in enumerate(matrix):
        text_row = []
        for j, val in enumerate(row):
            if i == j:
                text_row.append('')  # No text on diagonal
            else:
                text_row.append(f'{val:.2f}')
        text_matrix.append(text_row)
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=symbols,
        y=symbols,
        colorscale=custom_colorscale,
        zmid=0,
        zmin=-1,
        zmax=1,
        text=text_matrix,
        texttemplate='%{text}',
        textfont=dict(size=11, color='#1F2937', family='Inter, system-ui, sans-serif'),
        colorbar=dict(
            title=dict(text="ρ", font=dict(size=14, color='#374151')),
            thickness=18,
            len=0.75,
            tickvals=[-1, -0.5, 0, 0.5, 1],
            ticktext=['-1.0', '-0.5', '0', '+0.5', '+1.0'],
            tickfont=dict(size=10),
            outlinewidth=1,
            outlinecolor='#E5E7EB',
            x=1.02
        ),
        hovertemplate='<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>',
        xgap=2,
        ygap=2
    ))
    
    # Add diagonal line indicator (optional visual enhancement)
    n = len(symbols)
    
    # Professional layout
    fig.update_layout(
        title=dict(
            text=spec.title or "Asset Correlation Matrix",
            font=dict(size=20, color='#1F2937', family='Inter, system-ui, sans-serif'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            tickangle=-45,
            side='bottom',
            tickfont=dict(size=11, color='#374151'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB',
            constrain='domain'
        ),
        yaxis=dict(
            autorange='reversed',
            tickfont=dict(size=11, color='#374151'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB',
            scaleanchor='x',
            scaleratio=1
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=max(500, 40 * len(symbols) + 120),
        width=max(550, 40 * len(symbols) + 180),
        margin=dict(l=90, r=90, t=80, b=90),
        font=dict(family='Inter, system-ui, sans-serif')
    )
    
    # Find highest and lowest correlations (excluding diagonal)
    max_corr = -2
    min_corr = 2
    max_pair = ("", "")
    min_pair = ("", "")
    
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            if i != j:
                if matrix[i][j] > max_corr:
                    max_corr = matrix[i][j]
                    max_pair = (symbols[i], symbols[j])
                if matrix[i][j] < min_corr:
                    min_corr = matrix[i][j]
                    min_pair = (symbols[i], symbols[j])
    
    # Add summary annotation
    if max_pair[0]:
        fig.add_annotation(
            x=0.5, y=-0.15,
            xref='paper', yref='paper',
            text=f"Highest: {max_pair[0]}-{max_pair[1]} ({max_corr:+.2f}) | Lowest: {min_pair[0]}-{min_pair[1]} ({min_corr:+.2f})",
            showarrow=False,
            font=dict(size=10, color='#6B7280'),
            align='center'
        )
    
    alt_text = f"Correlation matrix for {len(symbols)} assets. "
    if max_pair[0]:
        alt_text += f"Highest correlation: {max_pair[0]}-{max_pair[1]} ({max_corr:.2f})"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Correlation Matrix",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'matrix_size': len(symbols)}
    )


# Schema definitions
ALLOCATION_PIE_SCHEMA = ChartListItem(
    type=ChartType.ALLOCATION_PIE,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Asset symbols"
            },
            "weights": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Portfolio weights (0-1)"
            },
            "values": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Optional dollar values"
            }
        },
        "required": ["symbols", "weights"]
    },
    description="Portfolio allocation pie/donut chart",
    example_inputs={
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "weights": [0.4, 0.35, 0.25],
        "values": [400000, 350000, 250000]
    },
    constraints={"max_holdings": 20}
)

CORRELATION_MATRIX_SCHEMA = ChartListItem(
    type=ChartType.CORRELATION_MATRIX,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Asset symbols"
            },
            "matrix": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "number"}
                },
                "description": "Correlation matrix (NxN)"
            }
        },
        "required": ["symbols", "matrix"]
    },
    description="Correlation matrix heatmap",
    example_inputs={
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "matrix": [
            [1.0, 0.85, 0.72],
            [0.85, 1.0, 0.68],
            [0.72, 0.68, 1.0]
        ]
    },
    constraints={"max_symbols": 20}
)