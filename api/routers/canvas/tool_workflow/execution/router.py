"""Canvas Tool Execution Router.

Endpoints for listing and running Canvas analysis tools.
Uses FastAPI dependency injection for auth.
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, List, Tuple
import logging

from core.exceptions import ToolNotFoundError, ToolExecutionError
from core.cache import cache_get
from ..tools.loader import TOOL_REGISTRY
from ...primitives import ProcessGraphBuilder
from ...shared.dependencies import CurrentUser, OrgId

logger = logging.getLogger(__name__)

router = APIRouter(tags=["canvas-tools"])


def build_process_graph(
    tool_name: str,
    tickers: List[str],
    has_charts: bool = False,
    has_stats: bool = False,
    has_metrics: bool = False,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Build a generic process graph for ANY tool.

    All tools follow the same pattern:
    Data → System → Truth → Action → Outputs

    The only variable is the tool name in the Action node.
    """
    builder = ProcessGraphBuilder()

    # Input data
    ticker_str = ", ".join(tickers[:3]) + ("..." if len(tickers) > 3 else "")
    builder.add_data(1, "Portfolio", ticker_str if tickers else "Input")

    # External system
    builder.add_system(1, "Market Data")

    # Derived truth
    builder.add_truth(1, "Historical Data")

    # The action (any tool)
    builder.add_action(1, tool_name)

    # Outputs - add based on what the tool produced
    output_idx = 1
    if has_charts:
        builder.add_output(output_idx, "Charts")
        output_idx += 1
    if has_stats:
        builder.add_output(output_idx, "Statistics")
        output_idx += 1
    if has_metrics:
        builder.add_output(output_idx, "Metrics")
        output_idx += 1

    # If no outputs detected, add a generic one
    if output_idx == 1:
        builder.add_output(1, "Results")
        output_idx = 2

    # Connect the flow
    builder.connect((1, 1), (5, 1))  # Data → System
    builder.connect((5, 1), (2, 1))  # System → Truth
    builder.connect((2, 1), (3, 1))  # Truth → Action

    # Action → all outputs
    for i in range(1, output_idx):
        builder.connect((3, 1), (4, i))

    return builder.build()


@router.get("/tools")
async def list_tools(user_id: CurrentUser):
    """List all available Canvas tools."""
    tools = [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t["category"],
            "params_schema": t["params_schema"],
        }
        for t in TOOL_REGISTRY.values()
    ]
    return {"tools": tools}


@router.post("/run/{tool_id}")
async def run_tool(tool_id: str, request: Request, user_id: CurrentUser, org_id: OrgId):
    """Run any registered tool by ID. Builds process graph generically."""
    if tool_id not in TOOL_REGISTRY:
        raise ToolNotFoundError(tool_id)

    tool = TOOL_REGISTRY[tool_id]

    # Parse params from request body
    try:
        params = await request.json()
    except:
        params = {}

    logger.info(f"Canvas run: {tool_id} for user {user_id}, params={params}")

    try:
        result = await tool["executor"](user_id, org_id, params)

        # Build generic process graph for ANY tool
        if result.get("status") == "success":
            graph_steps, graph_edges = build_process_graph(
                tool_name=tool["name"],
                tickers=result.get("tickers", []),
                has_charts=bool(result.get("charts")),
                has_stats=bool(result.get("stats_table")),
                has_metrics=bool(result.get("metrics")),
            )
            result["graph_steps"] = graph_steps
            result["graph_edges"] = graph_edges

        return result
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"Tool {tool_id} failed: {e}", exc_info=True)
        raise ToolExecutionError(tool_id, str(e))


@router.get("/analysis/cache/{analysis_id}")
async def get_cached_analysis(analysis_id: str, user_id: CurrentUser):
    """
    Retrieve cached tool analysis results.
    
    This endpoint is used by the frontend to fetch analysis results
    after the AI runs start_tool_analysis. Results are cached with
    a 15-minute TTL.
    
    Args:
        analysis_id: UUID of the cached analysis
        user_id: Current user (injected via dependency)
    
    Returns:
        The full analysis result including metric_cards, charts, stats_table
    
    Raises:
        HTTPException 404 if analysis not found or expired
    """
    cache_key = f"analysis:{analysis_id}"
    
    try:
        result = await cache_get(cache_key)
    except Exception as e:
        logger.error(f"Cache error retrieving {analysis_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cached analysis"
        )
    
    if not result:
        logger.warning(f"Analysis {analysis_id} not found in cache")
        raise HTTPException(
            status_code=404,
            detail="Analysis not found or expired. Please run the analysis again."
        )
    
    # Verify user owns this analysis (if user_id is stored in metadata)
    metadata = result.get("_metadata", {})
    cached_user_id = metadata.get("user_id")
    
    if cached_user_id and cached_user_id != user_id:
        logger.warning(f"User {user_id} attempted to access analysis owned by {cached_user_id}")
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this analysis."
        )
    
    # Remove internal metadata before returning
    result_copy = {k: v for k, v in result.items() if not k.startswith("_")}
    
    logger.info(f"Retrieved cached analysis {analysis_id} for user {user_id}")
    
    return result_copy
