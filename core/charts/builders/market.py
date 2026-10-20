"""
Market and price chart builders.

Simple, clean implementations using Plotly with WebGL for performance.
"""

from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from ..models import ChartSpec, ChartFigure, ChartListItem, ChartType
from ..utils.downsampling import downsample_if_needed


async def build_price_line(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build a line chart (can be prices or any time series data)"""
    
    # Extract inputs - check for inline data first
    symbol = spec.inputs.get('symbol', 'Data')
    label = spec.inputs.get('label', 'Value')  # What the data represents
    
    # Priority: inline data > prices field (for backward compat)
    data_values = spec.inputs.get('data') or spec.inputs.get('prices', [])
    dates = spec.inputs.get('dates', None)
    
    # Downsample if needed (max 2000 points)
    data_values = downsample_if_needed(data_values, max_points=2000)
    if dates:
        dates = downsample_if_needed(dates, max_points=2000)
    
    # Create figure with WebGL for performance
    fig = go.Figure()
    
    # Use Scattergl for >1000 points
    trace_type = go.Scattergl if len(data_values) > 1000 else go.Scatter
    
    fig.add_trace(trace_type(
        x=dates if dates else list(range(len(data_values))),
        y=data_values,
        mode='lines',
        name=symbol,
        line=dict(color='#2E86AB', width=2),
        hovertemplate='%{y:.2f}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol} {label}",
        xaxis_title="Date" if dates else "Index",
        yaxis_title=label,
        template="plotly_white",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified'
    )
    
    # Generate alt text
    if data_values:
        min_val = min(data_values)
        max_val = max(data_values)
        last_val = data_values[-1]
        alt_text = f"{symbol} {label} chart. Range: {min_val:.2f} - {max_val:.2f}. Last: {last_val:.2f}"
    else:
        alt_text = f"{symbol} {label} chart (no data)"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{symbol} {label}",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'symbol': symbol, 'points': len(data_values), 'data_type': label}
    )


async def build_candlestick(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build a candlestick chart"""
    
    # Extract OHLC data
    symbol = spec.inputs.get('symbol', 'Unknown')
    dates = spec.inputs.get('dates', None)
    
    # Extract arrays - check both in ohlc dict and directly in inputs
    ohlc = spec.inputs.get('ohlc', {})
    open_prices = spec.inputs.get('open') or ohlc.get('open', [])
    high_prices = spec.inputs.get('high') or ohlc.get('high', [])
    low_prices = spec.inputs.get('low') or ohlc.get('low', [])
    close_prices = spec.inputs.get('close') or ohlc.get('close', [])
    
    # Validate data
    if not (open_prices and high_prices and low_prices and close_prices):
        # Return properly formatted empty chart with hidden axes
        fig = go.Figure()
        fig.update_layout(
            title=spec.title or f"{symbol} Candlestick",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400,
            annotations=[
                dict(
                    text="No OHLC data available",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=16, color="#666")
                )
            ]
        )
        return ChartFigure(
            id=spec.id,
            title=spec.title or f"{symbol} Candlestick",
            alt_text="Candlestick chart (no data)",
            plotly=fig.to_dict()
        )
    
    # Downsample if needed
    max_candles = 500  # Candlesticks are more complex
    if len(open_prices) > max_candles:
        # Simple stride sampling for OHLC
        stride = len(open_prices) // max_candles
        open_prices = open_prices[::stride]
        high_prices = high_prices[::stride]
        low_prices = low_prices[::stride]
        close_prices = close_prices[::stride]
        if dates:
            dates = dates[::stride]
    
    # Create candlestick figure
    fig = go.Figure(data=[go.Candlestick(
        x=dates if dates else list(range(len(open_prices))),
        open=open_prices,
        high=high_prices,
        low=low_prices,
        close=close_prices,
        name=symbol,
        increasing_line_color='#26A653',
        decreasing_line_color='#EF5350'
    )])
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol} Candlestick Chart",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Price ($)",
        template="plotly_white",
        height=450,
        margin=dict(l=50, r=50, t=50, b=50),
        xaxis_rangeslider_visible=False  # Hide rangeslider for cleaner look
    )
    
    # Generate alt text
    last_close = close_prices[-1] if close_prices else 0
    price_range = f"${min(low_prices):.2f} - ${max(high_prices):.2f}" if low_prices and high_prices else "N/A"
    alt_text = f"{symbol} candlestick chart. Range: {price_range}. Last close: ${last_close:.2f}"
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{symbol} Candlestick",
        alt_text=alt_text,
        plotly=fig.to_dict(),
        metadata={'symbol': symbol, 'candles': len(open_prices)}
    )


# Schema definitions for discovery
PRICE_LINE_SCHEMA = ChartListItem(
    type=ChartType.PRICE_LINE,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Data series name"},
            "data": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Data values (inline data convention)"
            },
            "prices": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Price values (backward compatibility)"
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date/x-axis labels"
            },
            "label": {"type": "string", "description": "Y-axis label (e.g., 'Price', 'P/E Ratio', 'Revenue')"}
        },
        "required": ["symbol"],
        "oneOf": [
            {"required": ["data"]},
            {"required": ["prices"]}
        ]
    },
    description="Line chart for any time series data (prices, ratios, metrics)",
    example_inputs={
        "symbol": "AAPL",
        "data": [150, 152, 151, 153, 155],
        "label": "Price ($)"
    },
    constraints={"max_points": 2000}
)

CANDLESTICK_SCHEMA = ChartListItem(
    type=ChartType.CANDLESTICK,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "ohlc": {
                "type": "object",
                "properties": {
                    "open": {"type": "array", "items": {"type": "number"}},
                    "high": {"type": "array", "items": {"type": "number"}},
                    "low": {"type": "array", "items": {"type": "number"}},
                    "close": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["open", "high", "low", "close"]
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            }
        },
        "required": ["symbol", "ohlc"]
    },
    description="Candlestick chart showing OHLC price data",
    example_inputs={
        "symbol": "AAPL",
        "ohlc": {
            "open": [150, 152, 151],
            "high": [153, 154, 152],
            "low": [149, 151, 150],
            "close": [152, 151, 151]
        }
    },
    constraints={"max_candles": 500}
)


async def build_ma_overlay(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build price chart with moving averages"""
    
    # Extract inputs - check for inline data first
    symbol = spec.inputs.get('symbol', 'Data')
    prices = spec.inputs.get('data') or spec.inputs.get('prices', [])
    dates = spec.inputs.get('dates', None)
    ma_periods = spec.inputs.get('ma_periods', [20, 50, 200])
    
    if not prices:
        fig = go.Figure()
        fig.update_layout(title="No price data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or f"{symbol} MA Overlay",
            alt_text="MA overlay chart (no data)",
            plotly=fig.to_dict()
        )
    
    # Create figure
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=dates if dates else list(range(len(prices))),
        y=prices,
        mode='lines',
        name=symbol,
        line=dict(color='#2E86AB', width=2)
    ))
    
    # Add moving averages
    colors = ['#F77F00', '#06A77D', '#D62828', '#662E9B']
    prices_series = pd.Series(prices)
    
    for i, period in enumerate(ma_periods):
        if len(prices) >= period:
            ma = prices_series.rolling(window=period).mean()
            fig.add_trace(go.Scatter(
                x=dates if dates else list(range(len(prices))),
                y=ma.tolist(),
                mode='lines',
                name=f"MA{period}",
                line=dict(color=colors[i % len(colors)], width=1.5, dash='dash')
            ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or f"{symbol} with Moving Averages",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Price ($)",
        template="plotly_white",
        height=400,
        hovermode='x unified'
    )
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or f"{symbol} with Moving Averages",
        alt_text=f"Price chart with {', '.join([f'MA{p}' for p in ma_periods])} overlays",
        plotly=fig.to_dict(),
        metadata={'symbol': symbol, 'ma_periods': ma_periods}
    )


async def build_price_compare(spec: ChartSpec, context: Dict[str, Any]) -> ChartFigure:
    """Build normalized price comparison chart"""
    
    # Extract inputs - check for inline data first
    symbols = spec.inputs.get('symbols', [])
    prices_dict = spec.inputs.get('data_dict') or spec.inputs.get('prices_dict', {})
    dates = spec.inputs.get('dates', None)
    
    if not symbols or not prices_dict:
        fig = go.Figure()
        fig.update_layout(title="No comparison data available")
        return ChartFigure(
            id=spec.id,
            title=spec.title or "Price Comparison",
            alt_text="Price comparison chart (no data)",
            plotly=fig.to_dict()
        )
    
    # Create figure
    fig = go.Figure()
    
    # Normalize prices to base 100
    colors = ['#2E86AB', '#F77F00', '#06A77D', '#D62828', '#662E9B']
    
    for i, symbol in enumerate(symbols):
        if symbol in prices_dict:
            prices = prices_dict[symbol]
            if prices and len(prices) > 0:
                # Find first non-None value for normalization base
                base_value = None
                first_valid_idx = 0
                for idx, p in enumerate(prices):
                    if p is not None:
                        base_value = p
                        first_valid_idx = idx
                        break
                
                if base_value is None or base_value == 0:
                    # Skip this series if all None or base is 0
                    continue
                
                # Normalize to 100 at first valid value, preserving None for gaps
                normalized = [
                    (p / base_value) * 100 if p is not None else None 
                    for p in prices
                ]
                
                # Use corresponding dates
                x_values = dates[first_valid_idx:] if dates else list(range(first_valid_idx, len(prices)))
                y_values = normalized[first_valid_idx:]
                
                fig.add_trace(go.Scatter(
                    x=x_values if dates else list(range(len(y_values))),
                    y=y_values,
                    mode='lines',
                    name=symbol,
                    line=dict(color=colors[i % len(colors)], width=2),
                    connectgaps=False  # Don't connect across None gaps
                ))
    
    # Update layout
    fig.update_layout(
        title=spec.title or "Price Comparison (Normalized)",
        xaxis_title="Date" if dates else "Period",
        yaxis_title="Normalized Price (Base=100)",
        template="plotly_white",
        height=400,
        hovermode='x unified'
    )
    
    return ChartFigure(
        id=spec.id,
        title=spec.title or "Price Comparison",
        alt_text=f"Normalized price comparison for {', '.join(symbols)}",
        plotly=fig.to_dict(),
        metadata={'symbols': symbols}
    )


# Schema definitions for new charts
MA_OVERLAY_SCHEMA = ChartListItem(
    type=ChartType.MA_OVERLAY,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "prices": {
                "type": "array",
                "items": {"type": "number"}
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            },
            "ma_periods": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Moving average periods (e.g., [20, 50, 200])"
            }
        },
        "required": ["symbol", "prices"]
    },
    description="Price chart with moving average overlays",
    example_inputs={
        "symbol": "AAPL",
        "prices": [150, 152, 151, 153, 155],
        "ma_periods": [20, 50]
    },
    constraints={"max_points": 2000}
)

PRICE_COMPARE_SCHEMA = ChartListItem(
    type=ChartType.PRICE_OVERLAY_COMPARE,
    inputs_schema={
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"}
            },
            "prices_dict": {
                "type": "object",
                "description": "Dictionary mapping symbols to price arrays"
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional date labels"
            }
        },
        "required": ["symbols", "prices_dict"]
    },
    description="Compare multiple securities on normalized price basis",
    example_inputs={
        "symbols": ["AAPL", "MSFT"],
        "prices_dict": {
            "AAPL": [150, 152, 151],
            "MSFT": [300, 305, 303]
        }
    },
    constraints={"max_symbols": 10}
)