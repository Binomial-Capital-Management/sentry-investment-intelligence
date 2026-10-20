"""
Data Discovery Tools for Canvas AI Agent.

These tools help the AI understand what data endpoints are available,
what fields each endpoint returns, and how to find the right endpoint
for a user's request.

The agent prompt includes a compact endpoint index (via load_endpoint_index),
and these tools provide deeper exploration when needed.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agents import function_tool

logger = logging.getLogger(__name__)


# =============================================================================
# Endpoint Index for Agent Prompt
# =============================================================================

def load_endpoint_index(
    object_type: Optional[str] = None,
    max_endpoints: int = 100,
) -> str:
    """
    Load a compact endpoint index for injection into the agent prompt.
    
    Uses CanvasFieldRegistry to get all endpoints grouped by category.
    Returns a compact text format optimized for LLM context.
    
    Args:
        object_type: Filter by object type (equity, etf, crypto, forex, etc.)
                    If None, shows all endpoints.
        max_endpoints: Maximum endpoints to include (default 100)
    
    Returns:
        Formatted string with endpoint catalog for prompt injection
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        
        registry = get_field_registry()
        
        # Get stats for header
        stats = registry.get_stats()
        
        # Build header
        lines = [
            f"Available Data: {stats['total_fields']} fields across {stats['unique_endpoints']} endpoints",
            f"Sources: {', '.join(stats['by_source'].keys())}",
            "",
        ]
        
        # Get all endpoints with metadata
        endpoints = registry.get_endpoints()
        
        if object_type:
            # Filter to endpoints supporting this object type
            from core.canvas.field_mappings import get_endpoints_for_object_type
            valid_endpoints = set(get_endpoints_for_object_type(object_type))
            endpoints = [ep for ep in endpoints if ep in valid_endpoints]
        
        # Group by category for readability
        from core.canvas.field_mappings import get_category_for_endpoint
        
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for endpoint in endpoints[:max_endpoints]:
            meta = registry.get_endpoint_metadata(endpoint)
            category = get_category_for_endpoint(endpoint)
            
            if category not in categories:
                categories[category] = []
            
            field_count = len(registry.get_fields_for_endpoint(endpoint))
            categories[category].append({
                "endpoint": endpoint,
                "source": meta.get("source", "fmp"),
                "field_count": field_count,
                "cardinality": meta.get("cardinality", "single"),
            })
        
        # Format by category
        for category in sorted(categories.keys()):
            eps = categories[category]
            lines.append(f"### {category}")
            for ep in eps:
                cardinality_tag = "" if ep["cardinality"] == "single" else f" [{ep['cardinality']}]"
                lines.append(f"- {ep['endpoint']} ({ep['source']}, {ep['field_count']} fields){cardinality_tag}")
            lines.append("")
        
        # Add guidance
        lines.extend([
            "Use `get_endpoint_schema(endpoint)` for full field list.",
            "Use `list_endpoints_by_category(category)` to explore categories.",
        ])
        
        return "\n".join(lines)
        
    except FileNotFoundError as e:
        logger.warning(f"Canvas fields database not found: {e}")
        return "Endpoint catalog unavailable. Use discovery tools to explore available data."
    except Exception as e:
        logger.exception(f"Failed to load endpoint index: {e}")
        return "Endpoint catalog unavailable. Use discovery tools to explore available data."


# =============================================================================
# Discovery Tools (function_tool decorated)
# =============================================================================

@function_tool
def get_endpoint_schema(
    endpoint: str,
) -> str:
    """
    Get the full schema for a data endpoint including all fields and metadata.
    
    Use this tool when:
    - You need to know what fields an endpoint returns before calling add_dataset_to_workspace
    - The user asks what data is available for an endpoint
    - You want to verify field names before creating charts or pivots
    
    Args:
        endpoint: The endpoint name (e.g., 'historical-price-full', 'income-statement', 'key-metrics')
    
    Returns:
        Dict containing:
        - endpoint: The endpoint name
        - source: Data source (fmp, polygon, uw)
        - category: Data category (Price & Volume, Fundamentals, etc.)
        - structure_type: Data structure (daily_ohlcv, fiscal_period_series, snapshot, etc.)
        - cardinality: single/multi/none - whether endpoint accepts single or multiple symbols
        - required_params: List of required parameters beyond symbol
        - fields: List of all field names
        - field_count: Total number of fields
        - example: Example usage with add_dataset_to_workspace
    
    Example:
        get_endpoint_schema("income-statement")
        → Returns full schema with revenue, netIncome, grossProfit, etc.
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        from core.canvas.field_mappings import get_category_for_endpoint, get_cardinality_for_endpoint
        
        registry = get_field_registry()
        
        # Get metadata
        meta = registry.get_endpoint_metadata(endpoint)
        
        if meta.get("structure_type") == "unknown":
            all_endpoints = registry.get_endpoints()
            matches = [ep for ep in all_endpoints if endpoint.lower() in ep.lower()]
            if matches:
                return json.dumps({
                    "status": "error",
                    "message": f"Endpoint '{endpoint}' not found. Did you mean one of: {', '.join(matches[:5])}?",
                    "suggestions": matches[:10],
                })
            return json.dumps({
                "status": "error",
                "message": f"Endpoint '{endpoint}' not found in registry.",
            })
        
        fields = registry.get_fields_for_endpoint(endpoint)
        category = get_category_for_endpoint(endpoint)
        cardinality = get_cardinality_for_endpoint(endpoint)
        
        if cardinality == "none":
            example = f'add_dataset_to_workspace("", "{endpoint}", {fields[:3] if fields else []})'
        else:
            example = f'add_dataset_to_workspace("AAPL", "{endpoint}", {fields[:3] if fields else []})'
        
        return json.dumps({
            "status": "success",
            "endpoint": endpoint,
            "source": meta.get("source", "unknown"),
            "category": category,
            "structure_type": meta.get("structure_type", "unknown"),
            "cardinality": cardinality,
            "required_params": meta.get("required_params", []),
            "time_key": meta.get("time_key"),
            "fields": fields,
            "field_count": len(fields),
            "example": example,
        })
        
    except FileNotFoundError:
        return json.dumps({
            "status": "error",
            "message": "Canvas fields database not found. Run discovery script first.",
        })
    except Exception as e:
        logger.exception(f"Error getting endpoint schema: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to get schema: {str(e)}",
        })


@function_tool
def list_endpoints_by_category(
    category: Optional[str] = None,
    object_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
) -> str:
    """
    List available data endpoints, optionally filtered by category, object type, or source.
    
    Use this tool when:
    - User asks what data categories are available
    - User wants to explore endpoints for a specific asset type
    - You need to find the right endpoint for a user request
    
    Args:
        category: Filter by category. Common categories:
            - "Price & Volume": Historical prices, quotes, market cap
            - "Fundamentals": Income statements, balance sheets, cash flows
            - "Valuation": Ratios, DCF, key metrics
            - "Analyst Ratings": Price targets, grades, estimates
            - "Ownership": Insider trading, institutional holders
            - "Options Flow": Options flow, greek exposure (requires UnusualWhales)
            - "ETF Data": ETF holdings, sector weights
            - "Economic": Treasury rates, economic calendar
        object_type: Filter by asset type:
            - "equity": Stocks
            - "etf": ETFs
            - "crypto": Cryptocurrencies
            - "forex": Foreign exchange
            - "options": Options contracts
            - "market": Market-wide data (no symbol required)
        source: Filter by data source:
            - "fmp": Financial Modeling Prep (most endpoints)
            - "polygon": Polygon.io (crypto, forex, options)
            - "uw": UnusualWhales (options flow, dark pool)
        limit: Maximum endpoints to return (default 50)
    
    Returns:
        Dict with:
        - endpoints: List of endpoint info dicts
        - total: Total count
        - categories: Available categories (if no category filter)
    
    Example:
        list_endpoints_by_category(category="Fundamentals", object_type="equity")
        → Returns income-statement, balance-sheet-statement, cash-flow-statement, etc.
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        from core.canvas.field_mappings import (
            get_category_for_endpoint,
            get_endpoints_for_object_type,
            get_cardinality_for_endpoint,
            ENDPOINT_TO_OBJECT_TYPES,
        )
        
        registry = get_field_registry()
        
        # Start with all endpoints
        all_endpoints = registry.get_endpoints()
        
        # Filter by object_type first (most restrictive)
        if object_type:
            valid_for_type = set(get_endpoints_for_object_type(object_type))
            all_endpoints = [ep for ep in all_endpoints if ep in valid_for_type]
        
        # Build endpoint info list
        endpoints_info = []
        categories_seen = set()
        
        for endpoint in all_endpoints:
            meta = registry.get_endpoint_metadata(endpoint)
            ep_category = get_category_for_endpoint(endpoint)
            ep_source = meta.get("source", "fmp")
            
            # Apply filters
            if category and ep_category != category:
                continue
            if source and ep_source != source:
                continue
            
            categories_seen.add(ep_category)
            
            field_count = len(registry.get_fields_for_endpoint(endpoint))
            object_types = ENDPOINT_TO_OBJECT_TYPES.get(endpoint, ["equity"])
            
            endpoints_info.append({
                "endpoint": endpoint,
                "source": ep_source,
                "category": ep_category,
                "field_count": field_count,
                "cardinality": get_cardinality_for_endpoint(endpoint),
                "object_types": object_types,
            })
        
        # Sort by category then endpoint name
        endpoints_info.sort(key=lambda x: (x["category"], x["endpoint"]))
        
        # Apply limit
        total = len(endpoints_info)
        endpoints_info = endpoints_info[:limit]
        
        result: Dict[str, Any] = {
            "status": "success",
            "endpoints": endpoints_info,
            "returned": len(endpoints_info),
            "total": total,
        }
        
        if not category:
            result["categories"] = sorted(categories_seen)
        
        if total > limit:
            result["message"] = f"Showing {limit} of {total} endpoints. Add filters to narrow results."
        
        return json.dumps(result)
        
    except FileNotFoundError:
        return json.dumps({
            "status": "error",
            "message": "Canvas fields database not found. Run discovery script first.",
        })
    except Exception as e:
        logger.exception(f"Error listing endpoints: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to list endpoints: {str(e)}",
        })


@function_tool
def search_fields(
    query: str,
    source: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Search for fields by name across all endpoints.
    
    Use this tool when:
    - User asks for a specific metric but you don't know which endpoint has it
    - You need to find fields like "pe", "revenue", "volume", etc.
    - Exploring what's available
    
    Args:
        query: Search string (case-insensitive). Examples: "pe", "revenue", "volume", "ebitda"
        source: Optional filter by source (fmp, polygon, uw)
        limit: Max results (default 20)
    
    Returns:
        Dict with matched fields and their endpoints
    
    Example:
        search_fields("revenue")
        → Returns fields like revenue, revenueGrowth, revenuePerShare with their endpoints
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        
        registry = get_field_registry()
        sources = [source] if source else None
        
        results = registry.search_fields(query, sources=sources, limit=limit)
        
        if not results:
            return json.dumps({
                "status": "success",
                "message": f"No fields found matching '{query}'",
                "fields": [],
                "total": 0,
            })
        
        return json.dumps({
            "status": "success",
            "fields": results,
            "total": len(results),
            "query": query,
        })
        
    except FileNotFoundError:
        return json.dumps({
            "status": "error",
            "message": "Canvas fields database not found.",
        })
    except Exception as e:
        logger.exception(f"Error searching fields: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Search failed: {str(e)}",
        })


@function_tool
def get_endpoint_structure_type(endpoint: str) -> str:
    """
    Get the structure type and compatibility group for an endpoint.
    
    **Use this BEFORE adding datasets** to understand if they can be joined in the same tab.
    Endpoints in DIFFERENT compatibility groups CANNOT be in the same tab.
    
    Structure types:
    - **snapshot**: No time dimension, 1 row per symbol (e.g., ratios-ttm, key-metrics-ttm)
    - **fiscal_period_series**: Indexed by year+quarter (e.g., enterprise-values, analyst-estimates, income-statement)
    - **daily_ohlcv**: Daily time series (e.g., historical-price-full)
    - **event_list**: Event-based data with dates (e.g., stock-news, insider-trading)
    
    CRITICAL RULE: Call create_dataset_group() BEFORE adding data from a DIFFERENT compatibility group!
    
    Args:
        endpoint: The endpoint name (e.g., "ratios-ttm", "enterprise-values", "historical-price-full")
    
    Returns:
        Dict with structure_type, compatibility_group, and time_key
        
    Example:
        get_endpoint_structure_type("ratios-ttm")
        → {"structure_type": "snapshot", "compatibility_group": "snapshot", "time_key": null}
        
        get_endpoint_structure_type("enterprise-values")
        → {"structure_type": "fiscal_period_series", "compatibility_group": "fiscal_period", "time_key": "calendarYear,period"}
    """
    try:
        from core.canvas.field_mappings import (
            ENDPOINT_TO_STRUCTURE_TYPE,
            STRUCTURE_TO_COMPATIBILITY_GROUP,
            STRUCTURE_TO_TIME_KEY,
        )
        
        structure_type = ENDPOINT_TO_STRUCTURE_TYPE.get(endpoint, "unknown")
        compat_group = STRUCTURE_TO_COMPATIBILITY_GROUP.get(structure_type, "unknown")
        time_key = STRUCTURE_TO_TIME_KEY.get(structure_type)
        
        if structure_type == "unknown":
            return json.dumps({
                "status": "warning",
                "endpoint": endpoint,
                "structure_type": "unknown",
                "compatibility_group": "unknown",
                "time_key": None,
                "note": f"Endpoint '{endpoint}' not found in structure mappings. Use get_endpoint_schema() to check if it exists.",
            })
        
        return json.dumps({
            "status": "success",
            "endpoint": endpoint,
            "structure_type": structure_type,
            "compatibility_group": compat_group,
            "time_key": time_key,
            "note": "Endpoints with DIFFERENT compatibility_groups CANNOT be joined in the same tab. Call create_dataset_group() first!",
        })
        
    except Exception as e:
        logger.exception(f"Error getting structure type: {e}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to get structure type: {str(e)}",
        })


# =============================================================================
# List of all discovery tools for registration
# =============================================================================

DATA_DISCOVERY_TOOLS = [
    get_endpoint_schema,
    list_endpoints_by_category,
    search_fields,
    get_endpoint_structure_type,
]
