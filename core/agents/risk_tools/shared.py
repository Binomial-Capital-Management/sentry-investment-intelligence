"""
Shared utilities for risk tools
"""

import logging
import json
import math
import uuid
from typing import Optional, Any, List, Dict, Union, Tuple
from core.constants import DEFAULT_PERIOD
from core.utils import gather_dict
from core.charts.storage import store_chart
from core.utils.context_utils import user_context, session_context

logger = logging.getLogger(__name__)


async def resolve_portfolio_tickers(portfolio_id: str) -> Tuple[List[str], Dict[str, float]]:
    """
    Resolve portfolio ID to list of tickers and weights.
    Shared utility for all risk tools that support portfolio_id.
    
    Args:
        portfolio_id: Portfolio ID or name to load
        
    Returns:
        Tuple of (tickers list, weights dict {ticker: weight})
        
    Raises:
        ValueError: If portfolio cannot be loaded or has no tickers
    """
    from core.services import get_portfolio_service
    
    user_id = user_context.get()
    if not user_id:
        raise ValueError("No user context available - cannot load portfolio")
    
    service = get_portfolio_service()
    result = await service.get_portfolio(user_id, portfolio_id)
    
    if result.get("status") == "error":
        raise ValueError(f"Failed to load portfolio: {result.get('message', 'Unknown error')}")
    
    # Portfolio service returns data in 'portfolio' key with parallel arrays
    portfolio_data = result.get("portfolio", result)  # Fallback to result itself
    
    # Handle parallel arrays format (tickers[], weights[])
    tickers_list = portfolio_data.get("tickers", [])
    weights_list = portfolio_data.get("weights", [])
    
    if not tickers_list:
        # Try holdings format as fallback
        holdings = portfolio_data.get("holdings", [])
        if holdings:
            tickers_list = []
            weights_list = []
            for h in holdings:
                ticker = h.get("ticker") or h.get("symbol")
                weight = h.get("weight", 0)
                if ticker:
                    tickers_list.append(ticker)
                    weights_list.append(weight)
    
    if not tickers_list:
        raise ValueError(f"Portfolio '{portfolio_id}' has no tickers")
    
    # Build weights dict from parallel arrays
    weights = {}
    for i, ticker in enumerate(tickers_list):
        weight = weights_list[i] if i < len(weights_list) else (1.0 / len(tickers_list))
        weights[ticker] = weight
    
    return tickers_list, weights


def sanitize_date_param(date_value: Optional[str]) -> Optional[str]:
    """
    Sanitize date parameters from LLM agents.
    
    LLMs sometimes pass string "null", "undefined", or empty strings instead of None.
    This converts such values to actual None to prevent date parsing errors.
    
    Args:
        date_value: Date string or invalid placeholder
        
    Returns:
        Valid date string or None
    """
    if not date_value:
        return None
    if isinstance(date_value, str):
        # Strip whitespace
        cleaned = date_value.strip().lower()
        # Check for invalid placeholders
        if cleaned in ("null", "undefined", "none", ""):
            return None
    return date_value


def summarize_array(arr: List, max_points: int = 60) -> List:
    """
    Downsample large arrays to prevent SDK hanging.
    
    Args:
        arr: Input array
        max_points: Maximum points to keep
        
    Returns:
        Downsampled array if needed
    """
    if not isinstance(arr, list) or len(arr) <= max_points:
        return arr
    # downsample evenly
    step = max(1, math.floor(len(arr) / max_points))
    return [arr[i] for i in range(0, len(arr), step)][:max_points]


def sanitize_tool_output(obj: Any, max_bytes: int = 120_000, max_points: int = 60) -> Any:
    """
    Sanitize tool output to prevent OpenAI SDK hanging on large payloads.
    
    Args:
        obj: The output object to sanitize
        max_bytes: Maximum JSON size in bytes
        max_points: Maximum points in arrays
        
    Returns:
        Sanitized output that won't hang the SDK
    """
    # Walk and summarize large lists - always do this to handle nested arrays
    def _walk(v):
        if isinstance(v, list):
            return summarize_array(v, max_points=max_points)
        if isinstance(v, dict):
            return {k: _walk(v2) for k, v2 in v.items()}
        return v
    
    compact = _walk(obj)
    
    # final guard for size
    try:
        if len(json.dumps(compact, default=str)) > max_bytes:
            return {
                "status": obj.get("status", "success") if isinstance(obj, dict) else "success",
                "message": "Result truncated for delivery. Use charts or follow-up tool calls for full detail."
            }
    except Exception:
        pass
    
    return compact


def register_chart_handle(
    plotly_payload: Dict[str, Any],
    *,
    chart_type: str,
    title: str,
    alt_text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 900,
    chart_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Store full Plotly payload server-side and return a lightweight handle.

    Args:
        plotly_payload: Plotly figure dict.
        chart_type: Logical chart type identifier (for UI and dedup).
        title: Chart title (used as fallback alt text).
        alt_text: Optional accessibility text.
        metadata: Optional additional metadata to persist with the chart.
        ttl_seconds: Cache TTL.
        chart_id: Optional explicit ID; otherwise generated.

    Returns:
        Dict with minimal chart metadata safe for LLM context.
    """
    cid = chart_id or f"{chart_type}_{uuid.uuid4().hex[:8]}"
    stored_payload: Dict[str, Any] = {
        "id": cid,
        "title": title,
        "type": chart_type,
        "alt_text": alt_text or title,
        "plotly": plotly_payload,
    }
    if metadata:
        stored_payload["metadata"] = metadata

    store_chart(stored_payload, chart_id=cid, ttl_seconds=ttl_seconds)

    logger.info(
        "[CHART HANDLE] Stored chart payload (type=%s, id=%s, ttl=%ss)",
        chart_type,
        cid,
        ttl_seconds,
    )

    handle = {
        "id": cid,
        "chart_id": cid,
        "title": title,
        "type": chart_type,
        "alt_text": alt_text or title,
    }
    if metadata:
        handle["metadata"] = metadata
    return handle


def _parse_market_data_response(data: Any) -> Optional[Dict[str, Any]]:
    """
    Parse market data response from either YFinanceServer or FMPMarketDataServer.
    
    Args:
        data: Response from get_historical_data (dict or JSON string)
        
    Returns:
        Parsed dict or None if invalid
    """
    if data is None:
        return None
    
    # FMPMarketDataServer returns JSON string, YFinanceServer returns dict
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    
    if not isinstance(data, dict):
        return None
    
    return data


def _count_data_points(data: Dict[str, Any]) -> int:
    """
    Count data points in market data response, handling both formats.
    
    Args:
        data: Parsed market data dict
        
    Returns:
        Number of data points
    """
    # YFinance/FMP unified format with "data" array
    if 'data' in data and isinstance(data['data'], list):
        return len(data['data'])
    
    # FMP array format with "dates" array
    if 'dates' in data and isinstance(data['dates'], list):
        return len(data['dates'])
    
    return 0


async def _fetch_via_call_tool(market_server, ticker: str, period: str, start_date: str, end_date: str) -> Any:
    """
    Fetch data using MCP call_tool interface (for FMPMarketDataServer).
    """
    from core.utils.mcp_result_parser import safe_parse_json
    
    args = {"symbol": ticker}
    if start_date and end_date:
        args["start"] = start_date
        args["end"] = end_date
        args["period"] = "max"
    else:
        args["period"] = period
    
    result = await market_server.call_tool("get_historical_data", args)
    
    # Use the standard MCP result parser
    return safe_parse_json(result) or None


async def _fetch_via_direct_method(market_server, ticker: str, period: str, start_date: str, end_date: str) -> Any:
    """
    Fetch data using direct method (for YFinanceServer compatibility).
    """
    if start_date and end_date:
        return await market_server.get_historical_data(ticker, period="max", start=start_date, end=end_date)
    else:
        return await market_server.get_historical_data(ticker, period)


async def fetch_market_data_batch(market_server, tickers, period=DEFAULT_PERIOD, start_date=None, end_date=None):
    """
    Centralized data fetching to eliminate code duplication.
    Gracefully handles missing tickers by skipping them.
    
    Supports both YFinanceServer (direct method) and FMPMarketDataServer (call_tool).
    
    Args:
        market_server: YFinanceServer or FMPMarketDataServer instance
        tickers: List of ticker symbols
        period: Historical data period
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        JSON string of combined price data (only tickers with valid data)
    """
    # Sanitize date parameters to handle LLM passing "null" strings
    start_date = sanitize_date_param(start_date)
    end_date = sanitize_date_param(end_date)
    
    # Detect which interface to use
    use_call_tool = hasattr(market_server, 'call_tool')
    
    async def _fetch_ticker(ticker: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"data": None, "reason": None}
        try:
            logger.info("Fetching historical data for %s %s", ticker, 
                       f"from {start_date} to {end_date}" if start_date and end_date else f"for period {period}")
            
            if use_call_tool:
                data = await _fetch_via_call_tool(market_server, ticker, period, start_date, end_date)
            else:
                data = await _fetch_via_direct_method(market_server, ticker, period, start_date, end_date)

            # Parse response (handles both JSON string from FMP and dict from YFinance)
            parsed_data = _parse_market_data_response(data)
            
            if parsed_data:
                points = _count_data_points(parsed_data)
                if points > 10:
                    result["data"] = parsed_data
                else:
                    result["reason"] = f"insufficient data ({points} points)"
            else:
                result["reason"] = "invalid or empty response"
        except Exception as exc:  # noqa: BLE001
            result["reason"] = str(exc)
        return result

    factories = {ticker: (lambda t=ticker: _fetch_ticker(t)) for ticker in tickers}
    outcomes = await gather_dict(factories) if factories else {}

    all_price_data: Dict[str, Any] = {}
    skipped_tickers: List[str] = []

    for ticker, outcome in outcomes.items():
        if outcome.get("data"):
            all_price_data[ticker] = outcome["data"]
        else:
            skipped_tickers.append(ticker)
            reason = outcome.get("reason") or "unknown reason"
            logger.warning("Skipping %s: %s", ticker, reason)

    if skipped_tickers:
        logger.info("Skipped tickers with insufficient/missing data: %s", ", ".join(skipped_tickers))
    
    if not all_price_data:
        raise ValueError(f"No valid data available for any ticker. Attempted: {', '.join(tickers)}")
    
    return json.dumps(all_price_data)
