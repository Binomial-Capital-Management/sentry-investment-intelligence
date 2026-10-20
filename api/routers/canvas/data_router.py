"""
Canvas Data Router - API endpoints for the object registry data system.

Provides endpoints for:
- Object type detection
- Category browsing
- Field search
- Data fetching
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json

from core.canvas.object_type_detector import ObjectTypeDetector, ObjectTypeResult
from core.canvas.data_categories import (
    get_categories_for_object,
    get_all_categories,
    get_category_by_name,
    Category,
)
from core.canvas.object_data_service import (
    ObjectDataService, 
    FetchResult,
    get_cache_stats,
    get_data_freshness_info,
)
from core.canvas.object_registry import (
    get_object_type,
    get_all_object_types,
    list_object_types,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["canvas-data"])

# Service instances (lazy initialized)
_detector: Optional[ObjectTypeDetector] = None
_data_service: Optional[ObjectDataService] = None


def get_detector() -> ObjectTypeDetector:
    global _detector
    if _detector is None:
        _detector = ObjectTypeDetector()
    return _detector


def get_service() -> ObjectDataService:
    global _data_service
    if _data_service is None:
        _data_service = ObjectDataService()
    return _data_service


# --- Request/Response Models ---

class DetectRequest(BaseModel):
    symbol: str


class DetectResponse(BaseModel):
    object_type: str
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    is_actively_trading: bool = True


class CategoryResponse(BaseModel):
    name: str
    description: str
    icon: str
    datasets: List[str]


class FieldMatch(BaseModel):
    field: str
    endpoint: str
    type: Optional[str] = None
    category: Optional[str] = None


class FetchRequest(BaseModel):
    symbol: str
    category: Optional[str] = None
    datasets: Optional[List[str]] = None
    fields: Optional[List[str]] = None
    object_type: Optional[str] = None
    force_refresh: bool = False  # Bypass cache and fetch fresh data
    # Dataset params - passed through to FMP
    date_from: Optional[str] = None  # YYYY-MM-DD for historical data
    date_to: Optional[str] = None    # YYYY-MM-DD for historical data
    period: Optional[str] = None     # "annual" or "quarter" for financials
    limit: Optional[int] = None      # Number of records to fetch
    # Generic params (no hardcoding): if provided, these are forwarded as-is to MCP servers
    params: Optional[Dict[str, Any]] = None


class FetchResponse(BaseModel):
    success: bool
    symbol: str
    object_type: str
    data: Dict[str, Any]
    datasets_fetched: List[str]
    errors: List[str]
    cache_info: Dict[str, str] = {}  # Shows cached vs fetched per dataset
    fetched_at: Optional[float] = None  # Unix timestamp of fetch
    datasets_failed: Dict[str, str] = {}  # Datasets that failed with reason


class EndpointFetchRequest(BaseModel):
    """Request to fetch data from a specific endpoint with params."""
    symbol: str
    endpoint: str
    params: Dict[str, Any] = {}
    fields: Optional[List[str]] = None  # If provided, filter to these fields only


class ObjectTypeInfo(BaseModel):
    name: str
    display_name: str
    dataset_count: int
    parent: Optional[str] = None
    contains: Optional[List[str]] = None


# --- Endpoints ---

@router.post("/objects/detect", response_model=DetectResponse)
async def detect_object_type(request: DetectRequest):
    """
    Detect the object type for a symbol.
    
    Uses FMP API to determine if symbol is equity, ETF, crypto, forex, or commodity.
    """
    detector = get_detector()
    
    try:
        result = await detector.detect(request.symbol)
        return DetectResponse(
            object_type=result.object_type,
            symbol=result.symbol,
            name=result.name,
            exchange=result.exchange,
            currency=result.currency,
            is_actively_trading=result.is_actively_trading,
        )
    except Exception as e:
        logger.error(f"Error detecting object type for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/objects/types", response_model=List[ObjectTypeInfo])
async def get_object_types():
    """
    Get all available object types and their metadata.
    """
    types = get_all_object_types()
    return [
        ObjectTypeInfo(
            name=obj.name,
            display_name=obj.display_name,
            dataset_count=len(obj.provides),
            parent=obj.parent,
            contains=obj.contains,
        )
        for obj in types
    ]


@router.get("/objects/{object_type}/categories", response_model=List[CategoryResponse])
async def get_categories(object_type: str):
    """
    Get available data categories for an object type.
    
    Returns only categories that have datasets available for this object type.
    """
    categories = get_categories_for_object(object_type)
    
    if not categories:
        # Check if it's an unknown object type
        obj = get_object_type(object_type)
        if not obj:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown object type: {object_type}"
            )
        # Object exists but no categories match
        return []
    
    return [
        CategoryResponse(
            name=cat.name,
            description=cat.description,
            icon=cat.icon,
            datasets=cat.datasets,
        )
        for cat in categories
    ]


@router.get("/categories", response_model=List[CategoryResponse])
async def get_all_categories_endpoint():
    """
    Get all defined data categories.
    """
    categories = get_all_categories()
    return [
        CategoryResponse(
            name=cat.name,
            description=cat.description,
            icon=cat.icon,
            datasets=cat.datasets,
        )
        for cat in categories
    ]


@router.get("/fields/search", response_model=List[FieldMatch])
async def search_fields(
    q: str = Query(..., min_length=1, description="Search query"),
    source: Optional[str] = Query(None, description="Filter by source (fmp, polygon, uw)"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Search for fields matching a query.
    
    Uses the canvas_fields.db populated by discover_canvas_fields.py.
    NO HARDCODING - all fields come from the database.
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    try:
        registry = get_field_registry()
        sources = [source] if source else None
        results = registry.search_fields(q, sources=sources, limit=limit)
        
        # Add category for each result
        for r in results:
            r["category"] = get_category_for_dataset(r["endpoint"])
        
        return [FieldMatch(**r) for r in results]
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching fields for '{q}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fields/stats")
async def get_field_stats():
    """
    Get statistics about the canvas fields registry.
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    try:
        registry = get_field_registry()
        return registry.get_stats()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/fields/list")
async def list_fields(
    source: Optional[str] = Query(None, description="Filter by source (fmp, polygon, uw)"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint name"),
    object_type: Optional[str] = Query(None, description="Filter by object type (equity, etf, crypto, forex, commodity, macro, options)"),
    category: Optional[str] = Query(None, description="Filter by category (Valuation, Fundamentals, etc.)"),
    q: Optional[str] = Query(None, description="Search query for field name"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List all available fields from canvas_fields.db.
    
    Returns canonical field names with their associated metadata.
    NO HARDCODING - all fields come from the database populated by discover_canvas_fields.py.
    
    Filter by object_type to get fields relevant to equity, etf, crypto, etc.
    Filter by category to get fields in Valuation, Fundamentals, Price & Volume, etc.
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    try:
        registry = get_field_registry()
        results = registry.list_fields(
            source=source,
            endpoint=endpoint,
            object_type=object_type,
            category=category,
            query=q,
            limit=limit,
            offset=offset,
        )
        
        return results
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e) + " Run scripts/discover_canvas_fields.py first."
        )


@router.get("/fields/categories/{object_type}")
async def get_categories_for_object(object_type: str):
    """
    Get all available categories for an object type.
    
    Returns list of categories with field counts, useful for building
    a hierarchical field picker.
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    try:
        registry = get_field_registry()
        categories = registry.get_categories_for_object_type(object_type)
        return categories
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e) + " Run scripts/discover_canvas_fields.py first."
        )


@router.get("/fields/grouped/{object_type}")
async def get_fields_grouped(object_type: str):
    """
    Get all fields for an object type, grouped by category and endpoint.
    
    Returns a hierarchical structure:
    {
        "Valuation": {
            "ratios-ttm": [{"field": "pe", "type": "float", ...}],
            "key-metrics": [...]
        },
        "Fundamentals": {...}
    }
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    try:
        registry = get_field_registry()
        grouped = registry.get_fields_grouped(object_type)
        return grouped
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e) + " Run scripts/discover_canvas_fields.py first."
        )


@router.get("/fields/browse")
async def browse_fields(
    object_type: str = Query(..., description="Object type to browse"),
    grouped: bool = Query(True, description="Group by category"),
):
    """
    Browse all available fields for an object type.
    
    Returns all fields, optionally grouped by category.
    """
    obj = get_object_type(object_type)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown object type: {object_type}"
        )
    
    if grouped:
        # Group datasets by category
        categories = get_categories_for_object(object_type)
        return {
            cat.name: {
                "description": cat.description,
                "icon": cat.icon,
                "datasets": cat.datasets,
            }
            for cat in categories
        }
    else:
        # Return flat list of datasets
        return {
            "datasets": list(obj.provides),
            "count": len(obj.provides),
        }


@router.post("/fetch", response_model=FetchResponse)
async def fetch_data(request: FetchRequest):
    """
    Fetch data for a symbol.
    
    Can fetch by:
    - category: All data for a category (e.g., "Valuation")
    - datasets: Specific datasets (e.g., ["ratios-ttm", "key-metrics-ttm"])
    - fields: Specific field names (e.g., ["priceEarningsRatioTTM"])
    
    At least one of category, datasets, or fields must be provided.
    
    Set force_refresh=True to bypass cache and fetch fresh data.
    """
    if not request.category and not request.datasets and not request.fields:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one of: category, datasets, fields"
        )
    
    service = get_service()
    
    # Build params dict from request (and merge request.params)
    params: Dict[str, Any] = {}
    if request.date_from:
        params["from"] = request.date_from
    if request.date_to:
        params["to"] = request.date_to
    if request.period:
        params["period"] = request.period
    if request.limit:
        params["limit"] = request.limit
    if request.params:
        params.update(request.params)
    
    try:
        if request.category:
            result = await service.fetch_category(
                symbol=request.symbol,
                category=request.category,
                object_type=request.object_type,
                force_refresh=request.force_refresh,
                params=params,
            )
        elif request.datasets:
            result = await service.fetch_datasets(
                symbol=request.symbol,
                datasets=request.datasets,
                object_type=request.object_type,
                force_refresh=request.force_refresh,
                params=params,
            )
        else:  # fields
            result = await service.fetch_fields(
                symbol=request.symbol,
                fields=request.fields,
                object_type=request.object_type,
                force_refresh=request.force_refresh,
                params=params,
            )
        
        return FetchResponse(
            success=result.success,
            symbol=result.symbol,
            object_type=result.object_type,
            data=result.data,
            datasets_fetched=result.datasets_fetched,
            errors=result.errors,
            cache_info=result.cache_info,
            fetched_at=result.fetched_at,
            datasets_failed=result.datasets_failed,
        )
    
    except Exception as e:
        logger.error(f"Error fetching data for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/endpoint/fetch")
async def fetch_endpoint(request: EndpointFetchRequest):
    """
    Fetch data from a specific endpoint with given params.
    
    This is the preferred method for the data workspace:
    - Specify exactly which endpoint to call
    - Provide all required params for that endpoint
    - Optionally filter to specific fields
    
    Returns the endpoint's data, optionally filtered to requested fields.
    """
    service = get_service()
    
    try:
        # Fetch the single endpoint with provided params
        result = await service.fetch_datasets(
            symbol=request.symbol,
            datasets=[request.endpoint],
            params=request.params,
        )
        
        # Force fresh Python objects via JSON round-trip to prevent lazy dict issues
        import json as _json_fix
        serialized = _json_fix.dumps(result.data)
        result.data = _json_fix.loads(serialized)
        
        # If fields specified, filter the response data
        # But only if the fields actually exist in the data (don't filter with bogus field names)
        if request.fields and result.data.get(request.endpoint):
            endpoint_data = result.data[request.endpoint]
            if isinstance(endpoint_data, list) and len(endpoint_data) > 0:
                # Check if any requested fields exist in the first row
                first_row_keys = set(endpoint_data[0].keys()) if isinstance(endpoint_data[0], dict) else set()
                valid_fields = [f for f in request.fields if f in first_row_keys]
                
                # Only filter if we have valid fields, otherwise return all data
                if valid_fields:
                    result.data[request.endpoint] = [
                        {k: v for k, v in row.items() if k in valid_fields}
                        for row in endpoint_data
                    ]
                # else: keep all data unfiltered
            elif isinstance(endpoint_data, dict):
                valid_fields = [f for f in request.fields if f in endpoint_data]
                if valid_fields:
                    result.data[request.endpoint] = {
                        k: v for k, v in endpoint_data.items() if k in valid_fields
                    }
        
        response = FetchResponse(
            success=result.success,
            symbol=result.symbol,
            object_type=result.object_type,
            data=result.data,
            datasets_fetched=result.datasets_fetched,
            errors=result.errors,
            cache_info=result.cache_info,
            fetched_at=result.fetched_at,
            datasets_failed=result.datasets_failed,
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Error fetching endpoint {request.endpoint} for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Compatibility Check Endpoints ---

class EndpointMetadataResponse(BaseModel):
    """Metadata for an endpoint's compatibility characteristics."""
    endpoint: str
    structure_type: str
    compatibility_group: str
    time_key: Optional[str] = None
    cardinality: str  # 'single', 'multi', or 'none'


class CompatibilityCheckResponse(BaseModel):
    """Response for compatibility check between endpoints."""
    compatible: bool
    group: Optional[str] = None
    groups: Optional[List[str]] = None
    endpoints_by_group: Optional[Dict[str, List[str]]] = None
    reason: Optional[str] = None


@router.get("/compatibility/check", response_model=CompatibilityCheckResponse)
async def check_endpoint_compatibility(
    endpoints: List[str] = Query(..., description="List of endpoints to check compatibility for")
):
    """
    Check if a list of endpoints are compatible for merging into a unified view.
    
    Compatible endpoints share the same compatibility_group, meaning they can be
    joined on a common time key (e.g., calendarYear+period for fiscal data).
    
    Returns:
    - compatible: True if all endpoints can be merged
    - group: The shared compatibility group (if compatible)
    - groups: List of different groups found (if not compatible)
    - reason: Explanation of why endpoints are not compatible
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        registry = get_field_registry()
        result = registry.check_compatibility(endpoints)
        return CompatibilityCheckResponse(**result)
    except FileNotFoundError:
        # DB not populated yet, use mappings directly
        from core.canvas.field_mappings import get_compatibility_group_for_endpoint
        groups = {}
        for ep in endpoints:
            groups[ep] = get_compatibility_group_for_endpoint(ep)
        
        unique_groups = set(groups.values())
        if len(unique_groups) <= 1:
            return CompatibilityCheckResponse(
                compatible=True,
                group=list(unique_groups)[0] if unique_groups else None
            )
        else:
            return CompatibilityCheckResponse(
                compatible=False,
                groups=list(unique_groups),
                endpoints_by_group={
                    g: [ep for ep, grp in groups.items() if grp == g]
                    for g in unique_groups
                },
                reason=f"Endpoints span {len(unique_groups)} incompatible groups: {unique_groups}"
            )
    except Exception as e:
        logger.error(f"Error checking compatibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compatibility/endpoint/{endpoint}", response_model=EndpointMetadataResponse)
async def get_endpoint_metadata(endpoint: str):
    """
    Get compatibility metadata for a single endpoint.
    
    Returns structure_type, compatibility_group, time_key, and cardinality
    which can be used to determine merge strategies and validation rules.
    """
    try:
        from core.canvas.canvas_field_registry import get_field_registry
        registry = get_field_registry()
        meta = registry.get_endpoint_metadata(endpoint)
        return EndpointMetadataResponse(**meta)
    except FileNotFoundError:
        # DB not populated yet, use mappings directly
        from core.canvas.field_mappings import (
            get_structure_type_for_endpoint,
            get_compatibility_group_for_endpoint,
            get_time_key_for_endpoint,
            get_cardinality_for_endpoint,
        )
        return EndpointMetadataResponse(
            endpoint=endpoint,
            structure_type=get_structure_type_for_endpoint(endpoint),
            compatibility_group=get_compatibility_group_for_endpoint(endpoint),
            time_key=get_time_key_for_endpoint(endpoint),
            cardinality=get_cardinality_for_endpoint(endpoint),
        )
    except Exception as e:
        logger.error(f"Error getting endpoint metadata for {endpoint}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compatibility/endpoints", response_model=List[EndpointMetadataResponse])
async def get_endpoints_metadata(endpoints: List[str]):
    """
    Get compatibility metadata for multiple endpoints in a single request.
    """
    results = []
    for endpoint in endpoints:
        try:
            from core.canvas.field_mappings import (
                get_structure_type_for_endpoint,
                get_compatibility_group_for_endpoint,
                get_time_key_for_endpoint,
                get_cardinality_for_endpoint,
            )
            results.append(EndpointMetadataResponse(
                endpoint=endpoint,
                structure_type=get_structure_type_for_endpoint(endpoint),
                compatibility_group=get_compatibility_group_for_endpoint(endpoint),
                time_key=get_time_key_for_endpoint(endpoint),
                cardinality=get_cardinality_for_endpoint(endpoint),
            ))
        except Exception as e:
            logger.warning(f"Could not get metadata for {endpoint}: {e}")
            results.append(EndpointMetadataResponse(
                endpoint=endpoint,
                structure_type="unknown",
                compatibility_group="unknown",
                time_key=None,
                cardinality="single",
            ))
    return results


@router.get("/compatibility/groups")
async def list_compatibility_groups():
    """
    List all available compatibility groups and the endpoints in each.
    
    Useful for the frontend to show which datasets can be combined.
    """
    try:
        from core.canvas.field_mappings import (
            STRUCTURE_TO_COMPATIBILITY_GROUP,
            ENDPOINT_TO_STRUCTURE_TYPE,
        )
        
        # Build group -> endpoints mapping
        group_endpoints: Dict[str, List[str]] = {}
        for endpoint, structure in ENDPOINT_TO_STRUCTURE_TYPE.items():
            group = STRUCTURE_TO_COMPATIBILITY_GROUP.get(structure, "unknown")
            if group not in group_endpoints:
                group_endpoints[group] = []
            group_endpoints[group].append(endpoint)
        
        return {
            "groups": [
                {
                    "name": group,
                    "endpoint_count": len(endpoints),
                    "endpoints": sorted(endpoints),
                }
                for group, endpoints in sorted(group_endpoints.items())
            ]
        }
    except Exception as e:
        logger.error(f"Error listing compatibility groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint Equivalence for Cross-Asset Joins ---

class EndpointEquivalenceGroup(BaseModel):
    """An equivalence group containing endpoints that can be cross-joined."""
    canonical: str
    endpoints: Dict[str, str]  # object_type -> endpoint_name
    structure_type: str
    category: str
    granularity: str  # "daily", "quarterly", "snapshot", etc.
    avg_field_overlap: float


class EndpointEquivalenceRequest(BaseModel):
    """Request body for endpoint equivalence computation."""
    object_types: List[str]
    threshold: float = 0.5


class EndpointEquivalenceResponse(BaseModel):
    """Response containing equivalence groups for cross-asset joins."""
    equivalence_groups: List[EndpointEquivalenceGroup]
    granularities_detected: List[str]
    has_mixed_granularity: bool


@router.post("/endpoint-equivalence", response_model=EndpointEquivalenceResponse)
async def get_endpoint_equivalence(request: EndpointEquivalenceRequest):
    """
    Compute endpoint equivalence groups for cross-asset joins.
    
    Given multiple object types (e.g., ["equity", "crypto", "forex"]), finds
    endpoints that serve the same semantic purpose across those asset types.
    
    For example:
    - historical-price-full (equity) ≈ crypto-historical-eod-full (crypto) ≈ forex-historical-eod-full (forex)
    
    Uses hybrid scoring based on:
    - Structure type (must match)
    - Category similarity
    - Field overlap (Jaccard similarity)
    
    Returns:
        Equivalence groups that can be used for cross-asset joins,
        plus metadata about detected granularities for alignment UI.
    """
    try:
        from core.canvas.field_mappings import (
            compute_endpoint_equivalence,
            get_joinable_granularities,
        )
        
        # Compute equivalence groups
        groups = compute_endpoint_equivalence(
            object_types=request.object_types,
            threshold=request.threshold,
        )
        
        # Get all available granularities for the selected object types
        granularities = get_joinable_granularities(request.object_types)
        detected = list(granularities.keys())
        
        # Check if there are mixed granularities among the groups
        group_granularities = {g["granularity"] for g in groups}
        has_mixed = len(group_granularities) > 1
        
        return EndpointEquivalenceResponse(
            equivalence_groups=[
                EndpointEquivalenceGroup(**g) for g in groups
            ],
            granularities_detected=detected,
            has_mixed_granularity=has_mixed,
        )
    except Exception as e:
        logger.error(f"Error computing endpoint equivalence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Time-Key Based Endpoint Grouping ---

class EndpointTimeInfo(BaseModel):
    """Endpoint info with time-key metadata."""
    endpoint: str
    granularity: str
    category: str
    fields: List[str]
    structure_type: str
    time_key: Optional[str] = None
    time_group: str
    required_params: List[str] = []
    source: str = "fmp"


class TimeGroupEndpoints(BaseModel):
    """Endpoints grouped by time-key compatibility."""
    date: List[EndpointTimeInfo] = []
    fiscal_period: List[EndpointTimeInfo] = []
    snapshot: List[EndpointTimeInfo] = []


class EndpointsByTimeGroupRequest(BaseModel):
    """Request for endpoints grouped by time-key."""
    object_types: List[str]


class EndpointsByTimeGroupResponse(BaseModel):
    """Response with endpoints per object type, grouped by time-key."""
    endpoints_by_type: Dict[str, TimeGroupEndpoints]


class JoinStrategyRequest(BaseModel):
    """Request to analyze join strategy for selected endpoints."""
    selected_endpoints: Dict[str, str]  # object_type -> endpoint_name


class JoinStrategyResponse(BaseModel):
    """Response with join strategy analysis."""
    strategy: str  # "same_group" | "cross_group" | "incompatible"
    time_groups: List[str]
    granularities: List[str]
    common_time_key: Optional[str] = None
    needs_aggregation: bool
    aggregation_target: Optional[str] = None
    error: Optional[str] = None


@router.post("/endpoints-by-time-group", response_model=EndpointsByTimeGroupResponse)
async def get_endpoints_by_time_group(request: EndpointsByTimeGroupRequest):
    """
    Get endpoints grouped by time-key compatibility for each object type.
    
    This enables the Multi-Object form to show endpoint pickers per object type,
    with endpoints grouped by their joinability:
    
    - "date" group: daily/intraday endpoints joinable on date field
    - "fiscal_period" group: quarterly/annual endpoints joinable on period
    - "snapshot" group: point-in-time data, NOT joinable on time
    
    Usage: Call this when user selects symbols of multiple object types,
    then show per-type endpoint pickers in the UI.
    """
    try:
        from core.canvas.field_mappings import get_endpoints_by_time_group_multi
        
        result = get_endpoints_by_time_group_multi(request.object_types)
        
        # Convert to response models
        endpoints_by_type = {}
        for obj_type, grouped in result.items():
            endpoints_by_type[obj_type] = TimeGroupEndpoints(
                date=[EndpointTimeInfo(**ep) for ep in grouped.get("date", [])],
                fiscal_period=[EndpointTimeInfo(**ep) for ep in grouped.get("fiscal_period", [])],
                snapshot=[EndpointTimeInfo(**ep) for ep in grouped.get("snapshot", [])],
            )
        
        return EndpointsByTimeGroupResponse(endpoints_by_type=endpoints_by_type)
    except Exception as e:
        logger.error(f"Error getting endpoints by time group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join-strategy", response_model=JoinStrategyResponse)
async def analyze_join_strategy(request: JoinStrategyRequest):
    """
    Analyze the join strategy for selected endpoints across object types.
    
    Given selected endpoints (one per object type), determines:
    - Whether they can be joined on time
    - What granularity alignment is needed
    - Suggested target granularity for aggregation
    
    Usage: Call this when user selects endpoints in Multi-Object form
    to show appropriate join/aggregation options.
    """
    try:
        from core.canvas.field_mappings import detect_join_strategy
        
        result = detect_join_strategy(request.selected_endpoints)
        
        return JoinStrategyResponse(
            strategy=result.get("strategy", "incompatible"),
            time_groups=result.get("time_groups", []),
            granularities=result.get("granularities", []),
            common_time_key=result.get("common_time_key"),
            needs_aggregation=result.get("needs_aggregation", False),
            aggregation_target=result.get("aggregation_target"),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Error analyzing join strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/objects/{object_type}/datasets")
async def get_object_datasets(object_type: str):
    """
    Get all datasets provided by an object type.
    """
    obj = get_object_type(object_type)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown object type: {object_type}"
        )
    
    return {
        "object_type": object_type,
        "display_name": obj.display_name,
        "datasets": sorted(list(obj.provides)),
        "count": len(obj.provides),
        "data_sources": [
            {"server": ds.server, "catalog": ds.catalog_path}
            for ds in obj.data_sources
        ],
    }


@router.get("/datasets/{dataset_name}/params")
async def get_dataset_params(dataset_name: str):
    """
    Get the parameter requirements for a dataset.
    
    Returns the params schema from the DDC catalog, helping the frontend
    know what inputs to collect (date range, period, limit, etc.)
    """
    # No hardcoding: scan all catalog JSONs under core/mcp_servers and return the first match.
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]  # repo root
    mcp_dir = root / "core" / "mcp_servers"

    catalog_files = sorted([p for p in mcp_dir.rglob("*.json") if "catalog" in p.name])
    for p in catalog_files:
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        datasets = data.get("datasets")
        if not isinstance(datasets, list):
            continue
        for ds in datasets:
            if isinstance(ds, dict) and ds.get("dataset") == dataset_name:
                params_schema = ds.get("params_schema", {}) or {}
                # Filter out identifiers that are handled automatically by servers
                user_params = {k: v for k, v in params_schema.items() if k not in ("symbol", "apikey")}
                return {
                    "dataset": dataset_name,
                    "params": user_params,
                    "notes": ds.get("notes"),
                    "url": ds.get("url"),
                }

    raise HTTPException(status_code=404, detail=f"Dataset not found in catalogs: {dataset_name}")


@router.get("/cache/stats")
async def cache_stats():
    """
    Get cache statistics.
    
    Returns hit/miss counts and entry count.
    """
    return get_cache_stats()


@router.get("/cache/freshness")
async def cache_freshness():
    """
    Get data freshness information.
    
    Returns TTLs for different data categories, helping users
    understand how fresh different types of data are.
    """
    return get_data_freshness_info()


@router.post("/cache/invalidate")
async def invalidate_cache(
    symbol: Optional[str] = None,
    dataset: Optional[str] = None,
):
    """
    Invalidate cache entries.
    
    Args:
        symbol: Optional - invalidate for specific symbol only
        dataset: Optional - invalidate specific dataset (requires symbol)
        
    If no args, clears entire cache.
    """
    service = get_service()
    service.invalidate_cache(symbol, dataset)
    
    return {
        "success": True,
        "invalidated": {
            "symbol": symbol or "all",
            "dataset": dataset or "all",
        },
    }


@router.get("/cache/{dataset_id}")
async def get_cached_dataset(dataset_id: str):
    """
    Retrieve a cached dataset by ID.

    Used by the frontend after the AI agent's add_dataset_to_workspace tool
    caches fetched data. The frontend fetches the cached payload to populate
    the data workspace store.
    """
    from core.cache import cache_get
    cached = await cache_get(f"dataset_cache:{dataset_id}")
    if cached is None:
        raise HTTPException(status_code=404, detail="Dataset cache expired or not found")
    return cached


# --- Unified Data Workspace Endpoint ---

class ObjectSelection(BaseModel):
    """Single object selection for unified data fetch."""
    type: str  # equity, etf, crypto, forex, macro_series
    symbol: str


class UnifiedDataRequest(BaseModel):
    """Request for unified data across multiple objects."""
    objects: List[ObjectSelection]
    date_from: str  # YYYY-MM-DD
    date_to: str  # YYYY-MM-DD
    frequency: str = "daily"  # daily, weekly, monthly
    columns: Optional[List[str]] = None  # e.g., ["close", "volume"]
    datasets: Optional[List[str]] = None  # e.g., ["ratios-ttm", "key-metrics-ttm"]
    mode: str = "time_series"  # time_series or snapshot
    params: Optional[Dict[str, Any]] = None


class UnifiedDataResponse(BaseModel):
    """Response with unified data - either time-series or snapshot."""
    success: bool
    mode: str  # time_series or snapshot
    columns: List[str]  # For time_series: ["date", "AAPL_close", ...], For snapshot: ["symbol", "field", "value"]
    data: List[List[Any]]  # Row data
    row_count: int
    datasets_fetched: List[str] = []
    errors: List[str] = []


@router.post("/unified", response_model=UnifiedDataResponse)
async def fetch_unified_data(request: UnifiedDataRequest):
    """
    Fetch unified data for multiple objects.
    
    Two modes:
    - time_series: Returns aligned time-series with date column (for price data)
    - snapshot: Returns current/latest values for each symbol-dataset (for fundamentals)
    
    Used by Data Workspace to create multi-asset comparison tables.
    """
    import pandas as pd
    from datetime import datetime
    
    if not request.objects:
        raise HTTPException(status_code=400, detail="Must provide at least one object")
    
    if len(request.objects) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 objects per request")
    
    service = get_service()
    errors: List[str] = []
    datasets_fetched: List[str] = []
    
    # Params forwarded into ObjectDataService/MCP where supported
    # (FMP supports from/to on historical endpoints; other servers may ignore)
    fetch_params: Dict[str, Any] = {}
    if request.date_from:
        fetch_params["from"] = request.date_from
    if request.date_to:
        fetch_params["to"] = request.date_to
    if request.params:
        fetch_params.update(request.params)
    
    # Determine which datasets to fetch
    datasets_to_fetch = request.datasets or ["historical-price-full"]
    
    # MODE: SNAPSHOT - Fetch latest values for fundamentals/ratios
    if request.mode == "snapshot":
        snapshot_data: List[Dict[str, Any]] = []
        
        for obj in request.objects:
            for dataset in datasets_to_fetch:
                try:
                    result = await service.fetch_datasets(
                        symbol=obj.symbol,
                        datasets=[dataset],
                        object_type=obj.type,
                        params=fetch_params if fetch_params else None,
                    )
                    
                    if not result.success or not result.data:
                        continue
                    
                    data = result.data.get(dataset, {})
                    datasets_fetched.append(dataset)
                    
                    # Flatten the data into rows
                    if isinstance(data, list) and len(data) > 0:
                        # Take the first/latest record
                        record = data[0] if isinstance(data[0], dict) else {}
                        for key, val in record.items():
                            if key not in ['symbol', 'date', 'cik', 'link', 'finalLink']:
                                snapshot_data.append({
                                    'symbol': obj.symbol,
                                    'dataset': dataset,
                                    'field': key,
                                    'value': val,
                                })
                    elif isinstance(data, dict):
                        for key, val in data.items():
                            if key not in ['symbol', 'date', 'cik', 'link', 'finalLink'] and not isinstance(val, (dict, list)):
                                snapshot_data.append({
                                    'symbol': obj.symbol,
                                    'dataset': dataset,
                                    'field': key,
                                    'value': val,
                                })
                                
                except Exception as e:
                    errors.append(f"Error fetching {obj.symbol}/{dataset}: {str(e)}")
        
        if not snapshot_data:
            return UnifiedDataResponse(
                success=False,
                mode="snapshot",
                columns=["symbol", "dataset", "field", "value"],
                data=[],
                row_count=0,
                datasets_fetched=list(set(datasets_fetched)),
                errors=errors or ["No data found"],
            )
        
        # Convert to table format
        columns = ["symbol", "dataset", "field", "value"]
        data_rows = [[r['symbol'], r['dataset'], r['field'], r['value']] for r in snapshot_data]
        
        return UnifiedDataResponse(
            success=True,
            mode="snapshot",
            columns=columns,
            data=data_rows,
            row_count=len(data_rows),
            datasets_fetched=list(set(datasets_fetched)),
            errors=errors,
        )
    
    # MODE: TIME_SERIES - Aligned time-series data
    all_series: Dict[str, pd.Series] = {}
    columns_to_fetch = request.columns or ["close", "value", "price"]
    
    for obj in request.objects:
        try:
            # Determine dataset based on object type
            if obj.type in ["equity", "etf"]:
                dataset = "historical-price-full"
            elif obj.type == "crypto":
                dataset = "historical-price-full"
            elif obj.type == "forex":
                dataset = "historical-price-full"
            elif obj.type == "commodity":
                dataset = "historical-price-full"
            elif obj.type == "macro_series":
                dataset = "get_economic_data"
            else:
                dataset = "historical-price-full"
            
            # Fetch data for this object
            result = await service.fetch_datasets(
                symbol=obj.symbol,
                datasets=[dataset],
                object_type=obj.type,
            )
            
            if not result.success or not result.data:
                errors.append(f"Failed to fetch {obj.symbol}: no data")
                continue
            
            datasets_fetched.append(dataset)
            
            # Extract time series data
            data = result.data.get(dataset, {})
            
            # Handle FMP historical price response (list of records)
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                
                # Ensure date column exists
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date').sort_index()
                    
                    # Filter by date range
                    try:
                        start = pd.to_datetime(request.date_from)
                        end = pd.to_datetime(request.date_to)
                        df = df[(df.index >= start) & (df.index <= end)]
                    except Exception:
                        pass
                    
                    # Extract requested columns
                    for col in columns_to_fetch:
                        if col in df.columns:
                            series_name = f"{obj.symbol}_{col}"
                            all_series[series_name] = df[col]
                        elif col == "price" and "close" in df.columns:
                            series_name = f"{obj.symbol}_price"
                            all_series[series_name] = df["close"]
                        elif col == "value" and "close" in df.columns:
                            series_name = f"{obj.symbol}_value"
                            all_series[series_name] = df["close"]
                            
            elif isinstance(data, dict):
                # Handle dict response (e.g., economic data)
                if 'historical' in data:
                    records = data['historical']
                    if isinstance(records, list) and len(records) > 0:
                        df = pd.DataFrame(records)
                        if 'date' in df.columns:
                            df['date'] = pd.to_datetime(df['date'])
                            df = df.set_index('date').sort_index()
                            
                            # Filter by date range
                            try:
                                start = pd.to_datetime(request.date_from)
                                end = pd.to_datetime(request.date_to)
                                df = df[(df.index >= start) & (df.index <= end)]
                            except Exception:
                                pass
                            
                            # Extract value column
                            for col in ['value', 'close', 'price']:
                                if col in df.columns:
                                    series_name = f"{obj.symbol}_value"
                                    all_series[series_name] = df[col]
                                    break
                                    
        except Exception as e:
            logger.error(f"Error fetching unified data for {obj.symbol}: {e}")
            errors.append(f"Error fetching {obj.symbol}: {str(e)}")
    
    if not all_series:
        return UnifiedDataResponse(
            success=False,
            mode="time_series",
            columns=["date"],
            data=[],
            row_count=0,
            datasets_fetched=list(set(datasets_fetched)),
            errors=errors or ["No data found for any object"],
        )
    
    # Combine all series into a single DataFrame
    combined = pd.DataFrame(all_series)
    
    # Apply frequency resampling if needed
    if request.frequency == "weekly":
        combined = combined.resample('W').last()
    elif request.frequency == "monthly":
        combined = combined.resample('M').last()
    
    # Drop rows with all NaN values
    combined = combined.dropna(how='all')
    
    # Convert to response format
    combined = combined.reset_index()
    combined.columns = ['date'] + list(combined.columns[1:])
    
    # Format date as string
    combined['date'] = combined['date'].dt.strftime('%Y-%m-%d')
    
    # Convert to list of lists
    columns = list(combined.columns)
    data = combined.values.tolist()
    
    # Handle NaN values in output
    cleaned_data = []
    for row in data:
        cleaned_row = []
        for val in row:
            if pd.isna(val):
                cleaned_row.append(None)
            elif isinstance(val, (float, int)) and not isinstance(val, bool):
                cleaned_row.append(round(float(val), 4) if isinstance(val, float) else int(val))
            else:
                cleaned_row.append(val)
        cleaned_data.append(cleaned_row)
    
    return UnifiedDataResponse(
        success=True,
        mode="time_series",
        columns=columns,
        data=cleaned_data,
        row_count=len(cleaned_data),
        datasets_fetched=list(set(datasets_fetched)),
        errors=errors,
    )


# =============================================================================
# OBJECT SUMMARY ENDPOINT - For Object Cards with live metrics
# =============================================================================

class ObjectSummaryRequest(BaseModel):
    symbol: str
    object_type: Optional[str] = None


class ObjectSummaryResponse(BaseModel):
    symbol: str
    type: str
    name: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    changePercent: Optional[float] = None
    peRatio: Optional[float] = None
    marketCap: Optional[float] = None
    sector: Optional[str] = None


@router.post("/object-summary", response_model=ObjectSummaryResponse)
async def get_object_summary(request: ObjectSummaryRequest):
    """
    Get a quick summary of key metrics for displaying an object card.
    
    Returns price, change, PE ratio, market cap, and sector for quick display.
    Optimized for speed - uses cached quote data when available.
    """
    service = get_service()
    
    try:
        result = await service.fetch_object_summary(
            symbol=request.symbol,
            object_type=request.object_type,
        )
        
        return ObjectSummaryResponse(**result)
    
    except Exception as e:
        logger.error(f"Error fetching object summary for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/object-summary/{symbol}", response_model=ObjectSummaryResponse)
async def get_object_summary_by_symbol(
    symbol: str,
    object_type: Optional[str] = Query(None, description="Object type (equity, etf, crypto, forex)")
):
    """
    GET endpoint for object summary - convenience wrapper.
    """
    service = get_service()
    
    try:
        result = await service.fetch_object_summary(
            symbol=symbol,
            object_type=object_type,
        )
        
        return ObjectSummaryResponse(**result)
    
    except Exception as e:
        logger.error(f"Error fetching object summary for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FOREX/CRYPTO/OPTIONS HELPER ENDPOINTS - For enhanced input modes
# =============================================================================

class ForexPairResponse(BaseModel):
    pairs: List[str]
    count: int


class CryptoPairResponse(BaseModel):
    pairs: List[str]
    count: int


class OptionsExpirationsResponse(BaseModel):
    ticker: str
    expirations: List[str]
    count: int


@router.get("/forex/pairs", response_model=ForexPairResponse)
async def get_forex_pairs():
    """
    Get list of available forex pairs.
    
    Returns major and minor forex pairs for dropdown selection.
    Uses FMP forex-list endpoint when available, falls back to static list.
    """
    try:
        service = get_service()
        
        # Try fetching from FMP forex-list
        try:
            result = await service.fetch_datasets(
                symbol="",  # No symbol needed
                datasets=["forex-list"],
                params={},
            )
            
            if result.success and result.data.get("forex-list"):
                forex_data = result.data["forex-list"]
                if isinstance(forex_data, list):
                    pairs = []
                    for item in forex_data:
                        if isinstance(item, dict):
                            # FMP returns objects with 'symbol' or 'ticker' field
                            pair = item.get("symbol") or item.get("ticker") or item.get("name", "")
                            if pair:
                                pairs.append(pair)
                    if pairs:
                        # Sort with majors first
                        majors = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
                        sorted_pairs = [p for p in majors if p in pairs or p.replace("USD", "/USD") in pairs]
                        sorted_pairs += [p for p in sorted(pairs) if p not in sorted_pairs]
                        return ForexPairResponse(pairs=sorted_pairs[:100], count=len(sorted_pairs[:100]))
        except Exception as e:
            logger.warning(f"Could not fetch forex list from API: {e}")
        
        # Fallback: static list of major forex pairs
        static_pairs = [
            # Majors
            "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
            # Crosses
            "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
            "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
            "AUDJPY", "AUDCHF", "AUDNZD", "AUDCAD",
            "NZDJPY", "NZDCHF", "NZDCAD",
            "CADJPY", "CADCHF",
            "CHFJPY",
            # Exotics
            "USDMXN", "USDZAR", "USDTRY", "USDHKD", "USDSGD", "USDNOK", "USDSEK",
            "EURTRY", "EURMXN", "EURNOK", "EURSEK",
        ]
        return ForexPairResponse(pairs=static_pairs, count=len(static_pairs))
    
    except Exception as e:
        logger.error(f"Error getting forex pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crypto/pairs", response_model=CryptoPairResponse)
async def get_crypto_pairs():
    """
    Get list of available crypto pairs.
    
    Returns major cryptocurrencies paired with USD for dropdown selection.
    Uses FMP crypto-list endpoint when available, falls back to static list.
    """
    try:
        service = get_service()
        
        # Try fetching from FMP crypto-list
        try:
            result = await service.fetch_datasets(
                symbol="",
                datasets=["cryptocurrencies-list"],
                params={},
            )
            
            if result.success and result.data.get("cryptocurrencies-list"):
                crypto_data = result.data["cryptocurrencies-list"]
                if isinstance(crypto_data, list):
                    pairs = []
                    for item in crypto_data:
                        if isinstance(item, dict):
                            symbol = item.get("symbol") or item.get("ticker") or ""
                            # Filter to USD pairs
                            if "USD" in symbol:
                                pairs.append(symbol)
                    if pairs:
                        # Sort with majors first
                        majors = ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "DOTUSD", "LINKUSD"]
                        sorted_pairs = [p for p in majors if p in pairs]
                        sorted_pairs += [p for p in sorted(pairs) if p not in sorted_pairs]
                        return CryptoPairResponse(pairs=sorted_pairs[:100], count=len(sorted_pairs[:100]))
        except Exception as e:
            logger.warning(f"Could not fetch crypto list from API: {e}")
        
        # Fallback: static list of major crypto pairs
        static_pairs = [
            # Major cryptos
            "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD",
            "DOTUSD", "LINKUSD", "MATICUSD", "UNIUSD", "AVAXUSD", "ATOMUSD",
            "LTCUSD", "BCHUSD", "XLMUSD", "ALGOUSD", "VETUSD", "FILUSD",
            "TRXUSD", "ETCUSD", "XMRUSD", "NEARUSD", "APTUSD", "ARBUSD",
            "OPUSD", "IMXUSD", "INJUSD", "SUIUSD", "SEIUSD", "TIAUSD",
            # Stablecoins (for reference)
            "USDTUSD", "USDCUSD",
        ]
        return CryptoPairResponse(pairs=static_pairs, count=len(static_pairs))
    
    except Exception as e:
        logger.error(f"Error getting crypto pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/expirations/{ticker}", response_model=OptionsExpirationsResponse)
async def get_options_expirations(ticker: str):
    """
    Get available expiration dates for options on a given underlying ticker.
    
    Returns list of expiration dates (YYYY-MM-DD) that can be used to construct
    options contract tickers.
    
    Uses Polygon options contracts endpoint when available.
    """
    ticker = ticker.upper()
    
    try:
        # Try fetching from Polygon
        import httpx
        import os
        from datetime import datetime, timedelta
        
        polygon_key = os.getenv("POLYGON_API_KEY")
        if polygon_key:
            try:
                async with httpx.AsyncClient() as client:
                    # Polygon v3 options contracts endpoint
                    url = f"https://api.polygon.io/v3/reference/options/contracts"
                    params = {
                        "underlying_ticker": ticker,
                        "expired": "false",
                        "limit": 1000,
                        "apiKey": polygon_key,
                    }
                    response = await client.get(url, params=params, timeout=15.0)
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        
                        # Extract unique expiration dates
                        expirations = set()
                        for contract in results:
                            exp_date = contract.get("expiration_date")
                            if exp_date:
                                expirations.add(exp_date)
                        
                        sorted_expirations = sorted(list(expirations))
                        if sorted_expirations:
                            return OptionsExpirationsResponse(
                                ticker=ticker,
                                expirations=sorted_expirations,
                                count=len(sorted_expirations),
                            )
            except Exception as e:
                logger.warning(f"Polygon options fetch failed: {e}")
        
        # Fallback: generate common expiration dates
        # Standard monthly options expire on 3rd Friday of each month
        # Weekly options on Fridays
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        expirations = []
        
        # Next 12 months of monthly expirations (3rd Friday)
        current = today.replace(day=1)
        for _ in range(12):
            # Find 3rd Friday
            first_day = current
            # Find first Friday
            days_until_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_until_friday)
            third_friday = first_friday + timedelta(weeks=2)
            
            if third_friday >= today:
                expirations.append(third_friday.strftime("%Y-%m-%d"))
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        # Add next 4 weekly expirations (Fridays)
        next_friday = today + timedelta(days=(4 - today.weekday()) % 7)
        if next_friday == today:
            next_friday += timedelta(weeks=1)
        
        for i in range(4):
            weekly = next_friday + timedelta(weeks=i)
            date_str = weekly.strftime("%Y-%m-%d")
            if date_str not in expirations:
                expirations.insert(i, date_str)  # Insert at beginning
        
        expirations = sorted(list(set(expirations)))
        
        return OptionsExpirationsResponse(
            ticker=ticker,
            expirations=expirations,
            count=len(expirations),
        )
    
    except Exception as e:
        logger.error(f"Error getting options expirations for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- UW Enum Values Endpoint ---

class UWEnumResponse(BaseModel):
    """Response for UW enum values."""
    enum: str
    values: List[Any]
    count: int


@router.get("/uw/enums/{enum_name}", response_model=UWEnumResponse)
async def get_uw_enum_values(enum_name: str):
    """
    Get available values for a UW enum (sector, flow_group, month, etc.)
    
    These are used to populate dropdowns for UW endpoints that require
    specific enum values like sector-tide, group-greek-flow, seasonality-performers.
    
    Available enums:
    - sector: Basic Materials, Communication Services, Consumer Cyclical, etc.
    - flow_group: mag7, semi, energy, airline, bank, etc.
    - month: 1-12
    - order: desc, asc
    - option_type: call, put
    - trade_side: ask, bid, mid
    - moneyness: all, itm, otm, atm
    """
    try:
        from core.mcp_servers.unusualwhales.uw_ddc_loader import get_default_loader
        
        loader = get_default_loader()
        values = loader.get_enum_values(enum_name)
        
        if not values:
            raise HTTPException(
                status_code=404, 
                detail=f"Enum not found: {enum_name}. Available enums: sector, flow_group, month, order, option_type, trade_side, moneyness"
            )
        
        return UWEnumResponse(
            enum=enum_name,
            values=values,
            count=len(values),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting UW enum {enum_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uw/enums")
async def list_uw_enums():
    """
    List all available UW enums.
    
    Returns enum names and their value counts.
    """
    try:
        from core.mcp_servers.unusualwhales.uw_ddc_loader import get_default_loader
        
        loader = get_default_loader()
        
        # Known enum names from UW catalogs
        enum_names = ["sector", "flow_group", "month", "order", "option_type", 
                      "trade_side", "moneyness", "expiration_filter", "tide_type",
                      "issue_type", "rule_name", "flow_filter", "screener_order_by"]
        
        enums = {}
        for name in enum_names:
            values = loader.get_enum_values(name)
            if values:
                enums[name] = {"count": len(values), "values": values}
        
        return {"enums": enums, "count": len(enums)}
    
    except Exception as e:
        logger.error(f"Error listing UW enums: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PIVOTED DATA ENDPOINT - For Property Table
# =============================================================================

class PivotedDataRequest(BaseModel):
    symbols: List[str]
    fields: List[str]
    object_type: Optional[str] = None
    # Dataset params
    date_from: Optional[str] = None  # YYYY-MM-DD for historical data
    date_to: Optional[str] = None    # YYYY-MM-DD for historical data
    period: Optional[str] = None     # "annual" or "quarter" for financials
    limit: Optional[int] = None      # Number of records to fetch


class PivotedDataResponse(BaseModel):
    columns: List[str]
    data: List[List[Any]]
    row_count: int
    errors: List[str]


@router.post("/pivoted", response_model=PivotedDataResponse)
async def get_pivoted_data(request: PivotedDataRequest):
    """
    Get data as a pivoted table with symbols as rows and fields as columns.
    
    This is the proper table format for the Data Workspace:
    - columns: ["symbol", "peRatio", "revenue", "marketCap", ...]
    - data: [["AAPL", 28.5, 383B, 3T], ["MSFT", 35.2, 211B, 2.8T], ...]
    
    The endpoint automatically resolves which datasets contain the requested fields.
    """
    if not request.symbols:
        raise HTTPException(status_code=400, detail="Must provide at least one symbol")
    if not request.fields:
        raise HTTPException(status_code=400, detail="Must provide at least one field")
    
    service = get_service()
    
    # Build params dict
    params = {}
    if request.date_from:
        params["from"] = request.date_from
    if request.date_to:
        params["to"] = request.date_to
    if request.period:
        params["period"] = request.period
    if request.limit:
        params["limit"] = request.limit
    
    try:
        result = await service.fetch_pivoted_snapshot(
            symbols=request.symbols,
            fields=request.fields,
            object_type=request.object_type,
            params=params if params else None,
        )
        
        return PivotedDataResponse(**result)
    
    except Exception as e:
        logger.error(f"Error fetching pivoted data: {e}")
        raise HTTPException(status_code=500, detail=str(e))



