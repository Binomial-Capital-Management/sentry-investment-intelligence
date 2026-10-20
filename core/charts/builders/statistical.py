"""
Statistical chart builders.

Histogram, density plots, and other statistical visualizations.
"""

from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import plotly.figure_factory as ff
import numpy as np
import pandas as pd
from scipy import stats

from ..models import ChartSpec, ChartFigure, ChartListItem, ChartType


async def build_histogram(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build a histogram chart"""
    
    # Extract inputs
    data = spec.inputs.get('data', [])
    bins = spec.inputs.get('bins', 30)
    label = spec.inputs.get('label', 'Value')
    
    if not data:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Histogram",
            alt_text="Histogram (no data)",
            plotly=fig.to_dict()
        )
    
    # Create histogram
    fig = go.Figure(data=[go.Histogram(
        x=data,
        nbinsx=bins,
        name=label,
        marker_color='#2E86AB',
        opacity=0.75
    )])
    
    # Add statistics
    mean_val = np.mean(data)
    std_val = np.std(data)
    
    # Add mean line
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {mean_val:.2f}"
    )
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{label} Distribution",
        xaxis_title=label,
        yaxis_title="Frequency",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{label} Distribution",
        alt_text=f"Histogram of {label}. Mean: {mean_val:.2f}, Std: {std_val:.2f}",
        plotly=fig.to_dict(),
        metadata={'mean': mean_val, 'std': std_val, 'count': len(data)}
    )


async def build_density_kde(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build a kernel density estimation plot"""
    
    # Extract inputs
    data = spec.inputs.get('data', [])
    label = spec.inputs.get('label', 'Value')
    show_histogram = spec.inputs.get('show_histogram', True)
    
    if not data or len(data) < 2:
        fig = go.Figure()
        fig.update_layout(title="Insufficient data for KDE")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Density Plot",
            alt_text="Density plot (insufficient data)",
            plotly=fig.to_dict()
        )
    
    # Create figure
    fig = go.Figure()
    
    # Add histogram if requested
    if show_histogram:
        fig.add_trace(go.Histogram(
            x=data,
            nbinsx=30,
            name='Histogram',
            marker_color='lightblue',
            opacity=0.5,
            histnorm='probability density',
            yaxis='y2'
        ))
    
    # Calculate KDE
    kde = stats.gaussian_kde(data)
    x_range = np.linspace(min(data), max(data), 200)
    density = kde(x_range)
    
    # Add KDE curve
    fig.add_trace(go.Scatter(
        x=x_range,
        y=density,
        mode='lines',
        name='KDE',
        line=dict(color='#D62828', width=3)
    ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{label} Density",
        xaxis_title=label,
        yaxis_title="Density",
        template="plotly_white",
        height=400,
        yaxis2=dict(
            overlaying='y',
            side='right',
            showgrid=False
        ) if show_histogram else None
    )
    
    # Calculate statistics
    mean_val = np.mean(data)
    median_val = np.median(data)
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{label} Density",
        alt_text=f"Kernel density plot of {label}. Mean: {mean_val:.2f}, Median: {median_val:.2f}",
        plotly=fig.to_dict(),
        metadata={'mean': mean_val, 'median': median_val, 'count': len(data)}
    )


# Schema definitions
HISTOGRAM_SCHEMA = ChartListItem(
    type=ChartType.HISTOGRAM,
    inputs_schema={
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "number"}
            },
            "bins": {
                "type": "number",
                "description": "Number of bins (default: 30)"
            },
            "label": {
                "type": "string",
                "description": "Label for the data"
            }
        },
        "required": ["data"]
    },
    description="Histogram showing data distribution",
    example_inputs={
        "data": [1.2, 2.3, 1.8, 3.2, 2.1],
        "bins": 20,
        "label": "Returns"
    },
    constraints={"max_points": 10000}
)

DENSITY_KDE_SCHEMA = ChartListItem(
    type=ChartType.DENSITY_KDE,
    inputs_schema={
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "number"}
            },
            "label": {
                "type": "string",
                "description": "Label for the data"
            },
            "show_histogram": {
                "type": "boolean",
                "description": "Show histogram overlay (default: true)"
            }
        },
        "required": ["data"]
    },
    description="Kernel density estimation plot",
    example_inputs={
        "data": [1.2, 2.3, 1.8, 3.2, 2.1],
        "label": "Returns",
        "show_histogram": True
    },
    constraints={"min_points": 2, "max_points": 10000}
)