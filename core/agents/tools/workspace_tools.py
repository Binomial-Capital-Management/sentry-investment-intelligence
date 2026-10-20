"""
Workspace Action Tools for Canvas AI Agent.

These tools execute SYNCHRONOUSLY - they fetch real data and cache it,
allowing the AI to know the actual outcome before generating its response.

The workflow:
1. AI calls add_dataset_to_workspace(symbol, endpoint, fields)
2. Tool fetches data from FMP via ObjectDataService (~300-800ms)
3. Tool caches result in Redis/memory with a unique dataset_id
4. Tool returns {status: "success", action: {...}} with the dataset_id
5. Agentic hooks emit agent_action SSE event to frontend
6. Frontend fetches cached data via GET /api/canvas/data/cache/{dataset_id}
7. Frontend adds to Zustand store → UI renders

Context Management:
    Uses contextvars pattern (like memory_tools.py) to pass user context
    without polluting tool signatures.
    
    from core.agents.tools.workspace_tools import set_workspace_context
    
    set_workspace_context(user_id="user_123", org_id="org_456")
    # ... run agent with tools ...
    clear_workspace_context()
"""

import contextvars
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from agents import function_tool

from core.cache import cache_set
from core.utils.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Complex Tool Parameters
# =============================================================================

class ChartSeriesConfig(BaseModel):
    """Configuration for a single chart series."""
    field: str = Field(..., description="The field name for Y values (required)")
    label: Optional[str] = Field(None, description="Display label for the series")
    color: Optional[str] = Field(None, description="Hex color code (e.g., '#ff0000')")


class PivotValueConfig(BaseModel):
    """Configuration for a pivot table value aggregation."""
    field: str = Field(..., description="The field name to aggregate")
    aggregation: str = Field(..., description="Aggregation function: sum, avg, count, min, max, median, stddev, first, last")


class OHLCFieldsConfig(BaseModel):
    """Configuration for OHLC field mappings in candlestick charts."""
    date: str = Field(..., description="Field name for date/timestamp")
    open: str = Field(..., description="Field name for open price")
    high: str = Field(..., description="Field name for high price")
    low: str = Field(..., description="Field name for low price")
    close: str = Field(..., description="Field name for close price")
    volume: Optional[str] = Field(None, description="Field name for volume (optional)")


# =============================================================================
# Context Management (contextvars pattern)
# =============================================================================

_workspace_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    '_workspace_context', default=None
)


def set_workspace_context(
    user_id: str,
    org_id: Optional[str] = None,
    session_id: Optional[str] = None,
    context_type: str = "workspace",
    process_id: Optional[str] = None,
    tool_id: Optional[str] = None,
) -> None:
    """
    Set workspace context before tool execution.
    
    Call this before running the agent so tools can access user context.
    
    Args:
        user_id: Current user's ID
        org_id: Organization ID (optional)
        session_id: Chat session ID (optional)
        context_type: "workspace" or "process" (default: "workspace")
        process_id: Process ID if in process context (optional)
        tool_id: Tool ID if in process context (optional)
    """
    _workspace_context.set({
        "user_id": user_id,
        "org_id": org_id,
        "session_id": session_id,
        "context_type": context_type,
        "process_id": process_id,
        "tool_id": tool_id,
    })


def get_workspace_context() -> Optional[Dict[str, Any]]:
    """Get current workspace context."""
    return _workspace_context.get()


def clear_workspace_context() -> None:
    """Clear workspace context after tool execution."""
    _workspace_context.set(None)


# =============================================================================
# Workspace Tools
# =============================================================================

@function_tool(strict_mode=False)  # Uses Dict[str, Any] for params
async def add_dataset_to_workspace(
    symbol: str,
    endpoint: str,
    fields: Optional[List[str]] = None,
    params: Optional[str] = None,
) -> str:
    """
    Add a dataset to the user's data workspace by fetching real market data.
    
    This tool SYNCHRONOUSLY fetches data and caches it. The AI receives
    the real outcome (success with row count, or specific error) before
    generating its response.
    
    Args:
        symbol: Stock ticker or asset symbol (e.g., 'AAPL', 'BTCUSD', 'EURUSD')
        endpoint: API endpoint name. Common endpoints:
            - historical-price-full: Daily OHLCV price history
            - income-statement: Quarterly/annual income statements
            - balance-sheet-statement: Balance sheet data
            - cash-flow-statement: Cash flow statements
            - key-metrics: Valuation ratios and financial metrics
            - profile: Company overview and info
            - ratios: Financial ratios
            - enterprise-values: Enterprise value metrics
            - analyst-estimates: Analyst forecasts
            - institutional-holder: Institutional ownership
        fields: Optional list of field names to include. If not provided,
                all fields are returned. Examples: ['date', 'close', 'volume']
        params: Optional parameters for the endpoint. Examples:
            - {'period': 'annual'} for annual statements
            - {'limit': 100} to limit rows
            - {'from': '2023-01-01', 'to': '2024-01-01'} for date range
    
    Returns:
        On success: {
            "status": "success",
            "message": "Fetched 252 rows for AAPL (historical-price-full)",
            "action": {
                "type": "add_dataset",
                "dataset_id": "uuid-...",
                "symbol": "AAPL",
                "endpoint": "historical-price-full",
                "fields": ["date", "close", ...],
                "row_count": 252
            }
        }
        On error: {
            "status": "error",
            "message": "Rate limit exceeded. Please wait 60 seconds."
        }
    """
    import asyncio
    from core.canvas.object_data_service import ObjectDataService
    
    # Get user context for rate limiting
    ctx = get_workspace_context()
    user_id = ctx.get("user_id") if ctx else None
    
    # =============================================================================
    # Rate Limit Recovery with Exponential Backoff
    # =============================================================================
    MAX_RETRIES = 3
    BASE_WAIT_SECONDS = 5  # Start with 5s, then 10s, then 20s
    
    async def attempt_fetch_with_retry():
        """Inner function to handle fetch with retry logic."""
        from datetime import datetime, timedelta
        
        parsed_params = json.loads(params) if params else {}
        fetch_params = dict(parsed_params) if parsed_params else {}
        
        DATE_RANGE_ENDPOINTS = {
            'historical-price-full',
            'historical-chart',
            'historical-price',
        }
        
        if endpoint in DATE_RANGE_ENDPOINTS:
            if 'from' not in fetch_params:
                default_from = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
                fetch_params['from'] = default_from
            if 'to' not in fetch_params:
                fetch_params['to'] = datetime.now().strftime('%Y-%m-%d')
        
        service = ObjectDataService()
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            # Check internal rate limit
            if user_id and not check_rate_limit(user_id, "workspace_actions", limit=30, window=60):
                wait_time = BASE_WAIT_SECONDS * (2 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"[WORKSPACE_TOOL] Internal rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "status": "error",
                        "message": f"Rate limit exceeded after {MAX_RETRIES} attempts. Please wait ~60 seconds before adding more datasets.",
                        "code": "RATE_LIMIT",
                        "retry_after": 60,
                    }
            
            logger.info(f"[WORKSPACE_TOOL] Fetching {symbol}/{endpoint} (attempt {attempt + 1}/{MAX_RETRIES})")
            
            try:
                result = await service.fetch_datasets(
                    symbol=symbol.upper(),
                    datasets=[endpoint],
                    params=fetch_params,
                )
                
                if result.success:
                    return {"success": True, "result": result, "fetch_params": fetch_params}
                
                # Check if it's a rate limit error from FMP API
                # Get error message, preferring datasets_failed for the specific endpoint
                if result.datasets_failed and endpoint in result.datasets_failed:
                    error_msg = result.datasets_failed[endpoint]
                elif result.errors:
                    error_msg = "; ".join(result.errors)
                else:
                    error_msg = "Unknown error"
                is_rate_limit = "429" in error_msg or "rate limit" in error_msg.lower() or "too many" in error_msg.lower()
                
                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    wait_time = BASE_WAIT_SECONDS * (2 ** attempt)
                    logger.info(f"[WORKSPACE_TOOL] FMP API rate limit, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait_time)
                    last_error = error_msg
                    continue
                
                # Non-rate-limit error or final attempt
                last_error = error_msg
                break
                
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate limit" in error_str.lower()
                
                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    wait_time = BASE_WAIT_SECONDS * (2 ** attempt)
                    logger.info(f"[WORKSPACE_TOOL] Exception rate limit, waiting {wait_time}s: {error_str[:100]}")
                    await asyncio.sleep(wait_time)
                    last_error = error_str
                    continue
                
                last_error = error_str
                break
        
        # All retries exhausted
        return {
            "status": "error",
            "message": f"Failed to fetch {symbol}/{endpoint} after {MAX_RETRIES} attempts: {last_error}",
            "code": "FETCH_FAILED_AFTER_RETRIES",
        }
    
    try:
        # Execute fetch with retry logic
        fetch_result = await attempt_fetch_with_retry()
        
        if isinstance(fetch_result, dict) and fetch_result.get("status") == "error":
            return json.dumps(fetch_result)
        
        # Extract successful result
        result = fetch_result["result"]
        fetch_params = fetch_result["fetch_params"]
        
        if not result.success:
            # Get error message, preferring datasets_failed for the specific endpoint
            if result.datasets_failed and endpoint in result.datasets_failed:
                error_msg = result.datasets_failed[endpoint]
            elif result.errors:
                error_msg = "; ".join(result.errors)
            else:
                error_msg = "Unknown error"
            logger.warning(f"[WORKSPACE_TOOL] Fetch failed: {error_msg}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to fetch {symbol}/{endpoint}: {error_msg}",
                "code": "FETCH_FAILED",
            })
        
        # Extract data for the endpoint
        endpoint_data = result.data.get(endpoint)
        if not endpoint_data:
            logger.warning(f"[WORKSPACE_TOOL] No data returned for endpoint {endpoint}")
            return json.dumps({
                "status": "error",
                "message": f"No data found for {symbol} on endpoint {endpoint}",
                "code": "NO_DATA",
            })
        
        # Calculate row count
        if isinstance(endpoint_data, list):
            row_count = len(endpoint_data)
        elif isinstance(endpoint_data, dict):
            row_count = 1
        else:
            row_count = 0
        
        # Filter fields if requested
        filtered_data = endpoint_data
        actual_fields = fields
        
        if fields and isinstance(endpoint_data, list) and len(endpoint_data) > 0:
            # Get available fields from first row
            available = set(endpoint_data[0].keys()) if isinstance(endpoint_data[0], dict) else set()
            valid_fields = [f for f in fields if f in available]
            
            if valid_fields:
                filtered_data = [
                    {k: v for k, v in row.items() if k in valid_fields}
                    for row in endpoint_data
                ]
                actual_fields = valid_fields
            else:
                # If no valid fields, return all and note it
                actual_fields = list(available) if available else None
        elif isinstance(endpoint_data, list) and len(endpoint_data) > 0:
            # No fields specified - use all available
            first_row = endpoint_data[0]
            actual_fields = list(first_row.keys()) if isinstance(first_row, dict) else None
        
        # Generate unique dataset ID and cache the data
        dataset_id = str(uuid.uuid4())
        cache_payload = {
            "symbol": symbol.upper(),
            "endpoint": endpoint,
            "fields": actual_fields,
            "params": fetch_params,  # Include actual params used (with from/to dates)
            "data": filtered_data,
            "row_count": row_count,
            "fetched_at": result.fetched_at,
            "user_id": user_id,  # For auth verification on retrieval
        }
        
        # Cache with 15-minute TTL (longer than original 5 min to handle slow users)
        await cache_set(f"dataset_cache:{dataset_id}", cache_payload, ttl=900)
        
        logger.info(f"[WORKSPACE_TOOL] Cached {row_count} rows as {dataset_id}")
        
        return json.dumps({
            "status": "success",
            "message": f"Fetched {row_count} rows for {symbol} ({endpoint})",
            "action": {
                "type": "add_dataset",
                "dataset_id": dataset_id,
                "symbol": symbol.upper(),
                "endpoint": endpoint,
                "fields": actual_fields,
                "row_count": row_count,
            }
        })
        
    except Exception as e:
        logger.exception(f"[WORKSPACE_TOOL] Error fetching {symbol}/{endpoint}")
        error_msg = str(e)
        
        # Handle specific error types
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return json.dumps({
                "status": "error",
                "message": "FMP API rate limit exceeded. Try again in 60 seconds.",
                "code": "API_RATE_LIMIT",
                "retry_after": 60,
            })
        
        return json.dumps({
            "status": "error",
            "message": f"Failed to fetch {symbol}: {error_msg}",
            "code": "INTERNAL_ERROR",
        })


@function_tool
def remove_dataset(dataset_id: str) -> str:
    """
    Request to remove a dataset from the user's data workspace.
    
    IMPORTANT: This action requires user confirmation. The dataset will NOT be 
    removed until the user clicks "Allow" in the confirmation card that appears.
    
    Use this when the user asks to remove, delete, or clear a dataset.
    The dataset_id can be found in the current data context shown in square brackets,
    e.g., "[abc123-uuid] AAPL: historical-price-full".
    
    Args:
        dataset_id: The ID of the dataset to remove (UUID from context)
    
    Returns:
        {"status": "pending_confirmation", "action": {"type": "remove_dataset", ...}}
        
    After calling this, tell the user you've requested the removal and they 
    need to confirm it in the chat panel. Do NOT say the dataset has been removed.
    """
    logger.info(f"[WORKSPACE_TOOL] Requesting removal of dataset {dataset_id} (pending user confirmation)")
    return json.dumps({
        "status": "pending_confirmation",
        "message": f"Removal of dataset {dataset_id} requires user confirmation",
        "action": {
            "type": "remove_dataset",
            "dataset_id": dataset_id,
        }
    })


@function_tool(strict_mode=False)  # Uses List[Dict[str, Any]] for y_series
def create_chart(
    chart_type: str,
    x_axis: str,
    y_series: Optional[List[ChartSeriesConfig]] = None,
    title: Optional[str] = None,
    show_legend: bool = True,
    show_grid: bool = True,
    dataset_ids: Optional[List[str]] = None,
    ohlc_fields: Optional[OHLCFieldsConfig] = None,
) -> str:
    """
    Create a chart visualization from the current workspace data.
    
    The chart will be created as a new tab, using data from the active tab's datasets.
    
    Args:
        chart_type: Type of chart to create. Options:
            - 'line': Line chart (best for time series)
            - 'area': Area chart (line with fill)
            - 'bar': Bar chart (categorical comparison)
            - 'scatter': Scatter plot (correlations)
            - 'candlestick': OHLC candlestick (price data) - REQUIRES ohlc_fields!
            - 'heatmap': Heatmap (matrix visualization)
            - 'pie': Pie chart (proportions)
            - 'histogram': Distribution histogram
        x_axis: Field name for X-axis (usually 'date' for time series)
        y_series: List of series configurations. Each item has:
            - 'field' (required): The field name for Y values
            - 'label' (optional): Display label for the series
            - 'color' (optional): Hex color code (e.g., '#ff0000')
        title: Optional chart title
        show_legend: Show legend (default: True)
        show_grid: Show grid lines (default: True)
        dataset_ids: Optional list of specific dataset IDs to include.
                     If not provided, uses all datasets in current context.
        ohlc_fields: REQUIRED for candlestick charts. Specifies field mappings:
            - 'date': Field name for date/timestamp
            - 'open': Field name for open price
            - 'high': Field name for high price  
            - 'low': Field name for low price
            - 'close': Field name for close price
            - 'volume': Field name for volume (optional)
    
    Returns:
        On success: {"status": "success", "action": {"type": "create_chart", "config": {...}}}
    
    Example usage:
        # Line chart
        create_chart("line", "date", [{"field": "close", "label": "AAPL Price"}], title="AAPL Stock Price")
        
        # Candlestick chart (MUST specify ohlc_fields)
        create_chart("candlestick", "date", [], title="NVDA Price",
                     ohlc_fields={"date": "date", "open": "open", "high": "high", 
                                 "low": "low", "close": "close", "volume": "volume"})
    """
    logger.info(f"[WORKSPACE_TOOL] create_chart called: chart_type={chart_type}, x_axis={x_axis}, "
                f"y_series={y_series}, title={title}, ohlc_fields={ohlc_fields}")
    
    # Validate ohlc_fields has required keys for candlestick
    if ohlc_fields:
        ohlc_dict = ohlc_fields.model_dump() if hasattr(ohlc_fields, 'model_dump') else ohlc_fields
        required_keys = {'date', 'open', 'high', 'low', 'close'}
        missing_keys = required_keys - set(ohlc_dict.keys())
        if missing_keys:
            logger.warning(f"[WORKSPACE_TOOL] ohlc_fields missing required keys: {missing_keys}")
            return json.dumps({
                "status": "error",
                "message": f"ohlc_fields missing required keys: {missing_keys}. Required: date, open, high, low, close (volume optional).",
                "code": "INVALID_OHLC_FORMAT",
            })
    
    # Validate chart type
    valid_chart_types = ['line', 'area', 'bar', 'scatter', 'candlestick', 'heatmap', 'pie', 'histogram', 'bubble', 'box', 'violin', 'radar', 'scatter3d', 'surface3d', 'scatterMatrix', 'dotPlot']
    if chart_type not in valid_chart_types:
        return json.dumps({
            "status": "error",
            "message": f"Invalid chart type '{chart_type}'. Valid types: {', '.join(valid_chart_types)}",
            "code": "INVALID_CHART_TYPE",
        })
    
    # Validate candlestick requires ohlc_fields
    if chart_type == 'candlestick' and not ohlc_fields:
        return json.dumps({
            "status": "error",
            "message": "Candlestick charts REQUIRE ohlc_fields. FIRST check 'Datasets in workspace' for actual field names. "
                       "Multi-symbol data uses PREFIXED fields (e.g., NVDA_open, NVDA_close, NVDA_high, NVDA_low). "
                       "Single-symbol data uses unprefixed fields (open, close, high, low). "
                       "Example: ohlc_fields={'date': 'date', 'open': 'NVDA_open', 'high': 'NVDA_high', "
                       "'low': 'NVDA_low', 'close': 'NVDA_close', 'volume': 'NVDA_volume'}",
            "code": "MISSING_OHLC_FIELDS",
        })
    
    # Validate y_series (not required for candlestick which uses ohlc_fields)
    if not y_series and chart_type != 'candlestick':
        return json.dumps({
            "status": "error",
            "message": "y_series must be a non-empty list of series configurations",
            "code": "INVALID_Y_SERIES",
        })
    
    y_series_dicts = [s.model_dump() for s in y_series] if y_series else []
    ohlc_fields_dict = ohlc_fields.model_dump() if ohlc_fields else None
    
    logger.info(f"[WORKSPACE_TOOL] Creating {chart_type} chart: x={x_axis}, y_series={y_series_dicts}, ohlc_fields={ohlc_fields_dict}")
    
    return json.dumps({
        "status": "success",
        "message": f"Created {chart_type} chart" + (f" with {len(y_series)} series" if y_series else ""),
        "action": {
            "type": "create_chart",
            "config": {
                "chartType": chart_type,
                "xAxis": x_axis,
                "ySeries": y_series_dicts,
                "title": title,
                "showLegend": show_legend,
                "showGrid": show_grid,
                "selectedDatasetIds": dataset_ids,
                "ohlcFields": ohlc_fields_dict,
            }
        }
    })


@function_tool(strict_mode=False)  # Uses List[Dict[str, Any]] for values
def create_pivot_table(
    rows: Optional[List[str]] = None,
    columns: Optional[List[str]] = None,
    values: Optional[List[PivotValueConfig]] = None,
    dataset_ids: Optional[List[str]] = None,
) -> str:
    """
    Create a pivot table to aggregate and summarize workspace data.
    
    The pivot table will be created as a new tab, using data from the active tab's datasets.
    
    IMPORTANT - Field naming for pivots (DIFFERENT from charts):
    - Pivots use UNPREFIXED field names (e.g., 'priceToEarningsRatioTTM', 'revenue')
    - For multi-symbol data, use '_source_symbol' as a row grouping to compare across companies
    - Do NOT use symbol-prefixed field names like 'NVDA_revenue' - those are for charts only
    
    Args:
        rows: List of field names to use as row groups. For multi-symbol comparison,
              include '_source_symbol' to group by company (e.g., ['_source_symbol'])
        columns: List of field names to use as column groups (e.g., ['calendarYear', 'period'])
        values: List of value configurations for aggregation. Each item has:
            - 'field' (required): The UNPREFIXED field name to aggregate (e.g., 'priceToEarningsRatioTTM')
            - 'aggregation' (required): Aggregation function (sum, avg, count, min, max, median, stddev, first, last)
        dataset_ids: Optional list of specific dataset IDs to include.
                     If not provided, uses all datasets in current context.
    
    Returns:
        On success: {"status": "success", "action": {"type": "create_pivot", "config": {...}}}
    
    Example - Compare P/E ratios across multiple companies:
        create_pivot_table(
            rows=["_source_symbol"],
            values=[
                {"field": "priceToEarningsRatioTTM", "aggregation": "first"},
                {"field": "enterpriseValueMultipleTTM", "aggregation": "first"}
            ]
        )
    """
    # Validate values
    valid_aggregations = ['none', 'sum', 'avg', 'count', 'min', 'max', 'median', 'stddev', 'first', 'last']
    
    if not values:
        return json.dumps({
            "status": "error",
            "message": "values must be a non-empty list of value configurations",
            "code": "INVALID_VALUES",
        })
    
    for i, val in enumerate(values):
        agg = val.aggregation if hasattr(val, 'aggregation') else val.get('aggregation', '')
        if agg not in valid_aggregations:
            return json.dumps({
                "status": "error",
                "message": f"Invalid aggregation '{agg}'. Valid: {', '.join(valid_aggregations)}",
                "code": "INVALID_AGGREGATION",
            })
    
    values_dicts = [v.model_dump() for v in values]
    rows_list = rows or []
    columns_list = columns or []
    
    logger.info(f"[WORKSPACE_TOOL] Creating pivot table: rows={rows_list}, columns={columns_list}, values={values_dicts}")
    
    return json.dumps({
        "status": "success",
        "message": f"Created pivot table with {len(rows_list)} row fields, {len(columns_list)} column fields, {len(values)} value fields",
        "action": {
            "type": "create_pivot",
            "config": {
                "rows": rows_list,
                "columns": columns_list,
                "values": values_dicts,
                "selectedDatasetIds": dataset_ids,
            }
        }
    })


@function_tool
def remove_chart(tab_id: str) -> str:
    """
    Request to remove a chart tab from the user's data workspace.
    
    IMPORTANT: This action requires user confirmation. The chart will NOT be 
    removed until the user clicks "Allow" in the confirmation card that appears.
    
    Use this when the user asks to remove, delete, or close a chart.
    The tab_id can be found in the current data context under "Charts in workspace",
    shown in square brackets, e.g., "[tab-123456] Line chart: AAPL Price".
    
    Args:
        tab_id: The ID of the chart tab to remove (from context)
    
    Returns:
        {"status": "pending_confirmation", "action": {"type": "remove_chart", ...}}
        
    After calling this, tell the user you've requested the removal and they 
    need to confirm it in the chat panel. Do NOT say the chart has been removed.
    """
    logger.info(f"[WORKSPACE_TOOL] Requesting removal of chart {tab_id} (pending user confirmation)")
    return json.dumps({
        "status": "pending_confirmation",
        "message": f"Removal of chart {tab_id} requires user confirmation",
        "action": {
            "type": "remove_chart",
            "tab_id": tab_id,
        }
    })


@function_tool
def remove_pivot_table(tab_id: str) -> str:
    """
    Request to remove a pivot table tab from the user's data workspace.
    
    IMPORTANT: This action requires user confirmation. The pivot table will NOT be 
    removed until the user clicks "Allow" in the confirmation card that appears.
    
    Use this when the user asks to remove, delete, or close a pivot table.
    The tab_id can be found in the current data context under "Pivot tables in workspace",
    shown in square brackets, e.g., "[tab-123456] Revenue by Quarter".
    
    Args:
        tab_id: The ID of the pivot table tab to remove (from context)
    
    Returns:
        {"status": "pending_confirmation", "action": {"type": "remove_pivot", ...}}
        
    After calling this, tell the user you've requested the removal and they 
    need to confirm it in the chat panel. Do NOT say the pivot table has been removed.
    """
    logger.info(f"[WORKSPACE_TOOL] Requesting removal of pivot table {tab_id} (pending user confirmation)")
    return json.dumps({
        "status": "pending_confirmation",
        "message": f"Removal of pivot table {tab_id} requires user confirmation",
        "action": {
            "type": "remove_pivot",
            "tab_id": tab_id,
        }
    })


@function_tool
def create_dataset_group(name: str) -> str:
    """Create a named dataset group within the current tab.

    Groups organize datasets, charts, pivots, and analysis results into
    logical sections. All subsequent add_dataset, create_chart, create_pivot,
    and start_tool_analysis calls will add results to this group until a new
    group is created.

    Call this BEFORE adding datasets to organize them:
      create_dataset_group("Price Data")      → then add price datasets + charts
      create_dataset_group("Financials")      → then add income statements + pivots
      create_dataset_group("Risk Analysis")   → then run tool analyses

    Args:
        name: Display name for the group (e.g., "Price Data", "Annual Financials")
    """
    logger.info(f"[WORKSPACE_TOOL] Creating dataset group: {name}")
    return json.dumps({
        "status": "success",
        "action": {"type": "create_group", "name": name},
        "message": f"Created group '{name}' — subsequent items will be added here",
    })


# =============================================================================
# List of all workspace tools for registration
# =============================================================================

WORKSPACE_TOOLS = [
    add_dataset_to_workspace,
    remove_dataset,
    create_chart,
    create_pivot_table,
    remove_chart,
    remove_pivot_table,
    create_dataset_group,
]
