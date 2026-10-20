"""
Shared helpers for chart handling in quant tools.

Wraps Plotly payloads into lightweight handles to keep LLM context small.
"""

from typing import Any, Dict, List


def wrap_plotly_charts(charts: List[Any], default_type: str) -> List[Any]:
    """
    Convert chart dicts containing Plotly payloads into cache-backed handles.

    Args:
        charts: List of chart dicts or other objects.
        default_type: Fallback chart type when none is present.

    Returns:
        List with Plotly charts replaced by lightweight handles.
    """
    # Lazy import to avoid circular dependency
    from core.agents.risk_tools.shared import register_chart_handle
    
    wrapped: List[Any] = []
    for chart in charts or []:
        if isinstance(chart, dict) and chart.get("plotly"):
            title = chart.get("title") or chart.get("id") or default_type
            wrapped.append(
                register_chart_handle(
                    chart["plotly"],
                    chart_type=chart.get("id") or default_type,
                    title=title,
                    alt_text=chart.get("alt_text") or title,
                    metadata=chart.get("metadata"),
                    chart_id=chart.get("id"),
                )
            )
        else:
            wrapped.append(chart)
    return wrapped
