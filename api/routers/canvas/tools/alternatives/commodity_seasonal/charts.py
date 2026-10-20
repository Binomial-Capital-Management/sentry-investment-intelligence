"""
Commodity Seasonality Charts for Canvas
"""
from typing import Dict, Any, Optional
from datetime import datetime


def build_seasonality_chart(
    symbol: str,
    result: Dict[str, Any],
    current_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Build seasonality visualization with monthly returns and win rates.
    
    Shows:
    - Monthly average returns (bar chart, color-coded)
    - Historical win rates (line chart)
    - Current month marker
    - YTD performance overlay
    """
    
    # Parse monthly_table to extract seasonal data
    # The result doesn't expose seasonal_stats directly, so we need to reconstruct
    # from best_months, worst_months, and signal.upcoming_months
    
    # Actually, let's call the internal calculation helper to get raw seasonal stats
    # For now, let's build a simplified version from what we have
    
    best_months = result.get("best_months", [])
    worst_months = result.get("worst_months", [])
    signal = result.get("signal", {})
    upcoming = signal.get("upcoming_months", [])
    
    # Build month data (Jan-Dec)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Initialize with zeros
    returns = [0.0] * 12
    win_rates = [50.0] * 12
    
    # This is a limitation - the result doesn't give us all 12 months' data
    # We only have best_months, worst_months, and upcoming_months
    # For a proper implementation, we'd need seasonal_stats from the internal function
    
    # Workaround: parse the monthly_table markdown
    monthly_table = result.get("monthly_table", "")
    if monthly_table:
        lines = monthly_table.split('\n')[2:]  # Skip header rows
        for i, line in enumerate(lines):
            if line.strip() and i < 12:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 3:
                    try:
                        # Format: | Month | Avg Return | Win Rate | ...
                        returns[i] = float(parts[1].replace('%', '').replace('+', ''))
                        win_rates[i] = float(parts[2].replace('%', ''))
                    except (ValueError, IndexError):
                        pass
    
    # Color code by performance
    colors = ['#22c55e' if r > 0 else '#ef4444' if r < 0 else '#9ca3af' for r in returns]
    
    # Get current month for marker
    current_month_num = datetime.now().month
    
    # Extract YTD context
    ytd_return = current_context.get("ytd_return_pct", 0)
    ytd_z = current_context.get("ytd_z_score", 0)
    
    # Build subplot chart
    data = [
        # Returns bar chart
        {
            "type": "bar",
            "x": month_names,
            "y": returns,
            "name": "Avg Return",
            "marker": {"color": colors},
            "text": [f"{r:+.1f}%" for r in returns],
            "textposition": "outside",
            "yaxis": "y",
            "hovertemplate": "%{x}<br>Return: %{text}<extra></extra>",
        },
        # Win rate line
        {
            "type": "scatter",
            "x": month_names,
            "y": win_rates,
            "name": "Win Rate",
            "mode": "lines+markers",
            "line": {"color": "#8b5cf6", "width": 2},
            "marker": {"size": 8},
            "yaxis": "y2",
            "hovertemplate": "%{x}<br>Win Rate: %{y:.0f}%<extra></extra>",
        }
    ]
    
    layout = {
        "title": {
            "text": f"{symbol} Seasonality | YTD: {ytd_return:+.1f}% | Z: {ytd_z:.2f}σ",
            "font": {"size": 14},
            "x": 0.5,
            "xanchor": "center"
        },
        "xaxis": {
            "title": "",
            "tickangle": 0
        },
        "yaxis": {
            "title": "Average Return (%)",
            "side": "left",
            "gridcolor": "#E8E8E8"
        },
        "yaxis2": {
            "title": "Win Rate (%)",
            "side": "right",
            "overlaying": "y",
            "range": [0, 100],
            "showgrid": False
        },
        "hovermode": "x unified",
        "showlegend": True,
        "legend": {"x": 0.02, "y": 0.98, "bgcolor": "rgba(255,255,255,0.9)"},
        "height": 450,
        "margin": {"l": 60, "r": 60, "t": 70, "b": 50},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "white",
        # Add vertical line for current month
        "shapes": [{
            "type": "line",
            "x0": current_month_num - 1,
            "x1": current_month_num - 1,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": "#3b82f6", "width": 2, "dash": "dash"}
        }],
        "annotations": [{
            "x": current_month_num - 1,
            "y": 1.05,
            "yref": "paper",
            "text": "NOW",
            "showarrow": False,
            "font": {"size": 10, "color": "#3b82f6", "weight": "bold"}
        }]
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "bar",
        "label": f"{symbol} Seasonality"
    }
