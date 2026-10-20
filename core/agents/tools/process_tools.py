"""
Process-Specific Tools for Tool Workflow Context.

These tools execute SYNCHRONOUSLY - they update the database directly and return
real results to the AI. This ensures the AI knows the actual outcome before
generating its response.

Context Management:
    Uses the same contextvars pattern as workspace_tools.py.
    Tools access process_id, tool_id, user_id from the workspace context.

Workflow:
1. AI calls update_process_params({"num_simulations": 10000})
2. Tool updates the database directly via PostgresClient
3. Tool returns {"status": "success", "message": "..."}
4. AI can then offer to re-run the analysis with the new params

Note: Re-running analysis uses the existing rerun_canvas_analysis tool 
      defined in CanvasAgent.py, which calls the tool executor directly.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agents import function_tool

from core.agents.tools.workspace_tools import get_workspace_context

logger = logging.getLogger(__name__)


# =============================================================================
# Process Tools (Sync - DB operations)
# =============================================================================

@function_tool(strict_mode=False)  # Uses Dict[str, Any] for params
async def update_process_params(
    params: str,
) -> str:
    """
    Update parameters for the current tool analysis process.
    
    Use this to modify analysis parameters without re-running the analysis.
    After updating params, you can offer to re-run with rerun_canvas_analysis().
    
    Args:
        params: Dictionary of parameter updates. Keys depend on the tool type:
            - Monte Carlo: {'num_simulations': 10000, 'time_horizon': 252}
            - VaR: {'confidence_level': 0.99, 'method': 'historical'}
            - DCF: {'wacc': 0.10, 'terminal_growth': 0.025}
            - Barra: {'factor_model': 'BARRA_USE4'}
            - Stress Test: {'scenario': 'covid_crash'}
            
    Returns:
        On success: {"status": "success", "message": "Parameters updated", "updated_params": {...}}
        On error: {"status": "error", "message": "Error description"}
    
    Example:
        update_process_params('{"num_simulations": 10000, "confidence_level": 0.99}')
    """
    params_dict: Dict[str, Any] = json.loads(params) if isinstance(params, str) else params

    ctx = get_workspace_context()
    if not ctx:
        return json.dumps({
            "status": "error",
            "message": "No context available. This tool only works in Tool Workflow context.",
            "code": "NO_CONTEXT",
        })
    
    if ctx.get("context_type") not in ("process", "unified"):
        return json.dumps({
            "status": "error",
            "message": "update_process_params only works in Tool Workflow (process) context, not Data Workspace.",
            "code": "WRONG_CONTEXT",
        })
    
    process_id = ctx.get("process_id")
    user_id = ctx.get("user_id")
    org_id = ctx.get("org_id")
    
    if not process_id:
        return json.dumps({
            "status": "error",
            "message": "No process_id in context. Cannot update parameters.",
            "code": "NO_PROCESS_ID",
        })
    
    if process_id == "unsaved":
        return json.dumps({
            "status": "info",
            "message": "This analysis hasn't been saved yet, so parameters can't be persisted to database. Use rerun_canvas_analysis() directly with the new parameters to re-run the analysis. The user can then save the updated results.",
            "code": "UNSAVED_PROCESS",
            "suggested_action": "rerun_canvas_analysis",
            "params_to_use": params_dict,
        })
    
    if not user_id:
        return json.dumps({
            "status": "error",
            "message": "No user_id in context. Cannot update parameters.",
            "code": "NO_USER_ID",
        })
    
    logger.info(f"[PROCESS_TOOL] Updating params for process {process_id}: {params_dict}")
    
    try:
        from core.database.postgres_client import get_postgres_client
        db = await get_postgres_client()
        
        success = await db.update_process_params_and_tickers(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
            params=params_dict,
        )
        
        if success:
            return json.dumps({
                "status": "success",
                "message": "Parameters updated successfully. You can now re-run the analysis with rerun_canvas_analysis() to see the new results.",
                "updated_params": params_dict,
                "process_id": process_id,
            })
        else:
            return json.dumps({
                "status": "error",
                "message": "Failed to update parameters. Process may not exist or you may not have permission.",
                "code": "UPDATE_FAILED",
            })
            
    except Exception as e:
        logger.exception(f"[PROCESS_TOOL] Error updating params for {process_id}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to update parameters: {str(e)}",
            "code": "INTERNAL_ERROR",
        })


@function_tool
async def modify_process_tickers(
    tickers: List[str],
    weights: Optional[List[float]] = None,
) -> str:
    """
    Modify the portfolio composition (tickers and weights) for this analysis.
    
    Use this when the user wants to change which assets are analyzed or
    their allocation weights. After modifying, offer to re-run the analysis.
    
    Args:
        tickers: New list of ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
        weights: Optional portfolio weights. If provided:
            - Must have same length as tickers
            - Must sum to 1.0 (100%)
            - If not provided, equal weights are used
    
    Returns:
        JSON string with status and details.
    
    Example:
        modify_process_tickers(['AAPL', 'MSFT', 'NVDA'], [0.5, 0.3, 0.2])
    """
    ctx = get_workspace_context()
    if not ctx:
        return json.dumps({
            "status": "error",
            "message": "No context available. This tool only works in Tool Workflow context.",
            "code": "NO_CONTEXT",
        })
    
    if ctx.get("context_type") not in ("process", "unified"):
        return json.dumps({
            "status": "error",
            "message": "modify_process_tickers only works in Tool Workflow (process) context.",
            "code": "WRONG_CONTEXT",
        })
    
    process_id = ctx.get("process_id")
    user_id = ctx.get("user_id")
    org_id = ctx.get("org_id")
    
    if not process_id:
        return json.dumps({
            "status": "error",
            "message": "No process_id in context.",
            "code": "NO_PROCESS_ID",
        })
    
    if process_id == "unsaved":
        return json.dumps({
            "status": "info",
            "message": "This analysis hasn't been saved yet, so tickers can't be persisted to database. Use rerun_canvas_analysis() directly with the new tickers to re-run the analysis.",
            "code": "UNSAVED_PROCESS",
            "suggested_action": "rerun_canvas_analysis",
            "tickers_to_use": tickers,
            "weights_to_use": weights,
        })
    
    if not user_id:
        return json.dumps({
            "status": "error",
            "message": "No user_id in context.",
            "code": "NO_USER_ID",
        })
    
    if not tickers or len(tickers) == 0:
        return json.dumps({
            "status": "error",
            "message": "At least one ticker is required.",
            "code": "NO_TICKERS",
        })
    
    tickers = [t.upper().strip() for t in tickers]
    
    if weights:
        if len(weights) != len(tickers):
            return json.dumps({
                "status": "error",
                "message": f"Weights count ({len(weights)}) must match tickers count ({len(tickers)}).",
                "code": "WEIGHT_COUNT_MISMATCH",
            })
        
        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 0.01:
            return json.dumps({
                "status": "error",
                "message": f"Weights must sum to 1.0, but got {weight_sum:.4f}.",
                "code": "WEIGHT_SUM_INVALID",
            })
    else:
        weights = [1.0 / len(tickers)] * len(tickers)
    
    logger.info(f"[PROCESS_TOOL] Modifying tickers for process {process_id}: {tickers}, weights: {weights}")
    
    try:
        from core.database.postgres_client import get_postgres_client
        db = await get_postgres_client()
        
        success = await db.update_process_params_and_tickers(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
            tickers=tickers,
            weights=weights,
        )
        
        if success:
            weight_strs = [f"{t}: {w:.1%}" for t, w in zip(tickers, weights)]
            return json.dumps({
                "status": "success",
                "message": f"Portfolio updated to {', '.join(weight_strs)}. Re-run the analysis with rerun_canvas_analysis() to see results for the new portfolio.",
                "tickers": tickers,
                "weights": weights,
                "process_id": process_id,
            })
        else:
            return json.dumps({
                "status": "error",
                "message": "Failed to update portfolio. Process may not exist or you may not have permission.",
                "code": "UPDATE_FAILED",
            })
            
    except Exception as e:
        logger.exception(f"[PROCESS_TOOL] Error modifying tickers for {process_id}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to modify portfolio: {str(e)}",
            "code": "INTERNAL_ERROR",
        })


@function_tool
async def get_process_info() -> str:
    """
    Get current process information including tool_id, tickers, weights, and params.
    
    Use this to check the current state before making modifications.
    
    Returns:
        JSON string with process info (tool_id, tickers, weights, params, name).
    """
    ctx = get_workspace_context()
    if not ctx:
        return json.dumps({
            "status": "error",
            "message": "No context available.",
            "code": "NO_CONTEXT",
        })
    
    if ctx.get("context_type") not in ("process", "unified"):
        return json.dumps({
            "status": "error",
            "message": "get_process_info only works in Tool Workflow context.",
            "code": "WRONG_CONTEXT",
        })
    
    process_id = ctx.get("process_id")
    user_id = ctx.get("user_id")
    org_id = ctx.get("org_id")
    
    if not process_id or not user_id:
        return json.dumps({
            "status": "error",
            "message": "Missing process_id or user_id in context.",
            "code": "MISSING_IDS",
        })

    if process_id == "unsaved":
        return json.dumps({
            "status": "success",
            "process_id": "unsaved",
            "note": "This is an unsaved analysis. The process information (tool_id, tickers, weights, params) is already provided in your system context under <current-process-context>. Use that information directly.",
        })
    
    try:
        from core.database.postgres_client import get_postgres_client
        db = await get_postgres_client()
        
        process = await db.get_canvas_process(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
        )
        
        if not process:
            return json.dumps({
                "status": "error",
                "message": f"Process {process_id} not found.",
                "code": "NOT_FOUND",
            })
        
        return json.dumps({
            "status": "success",
            "process_id": process_id,
            "tool_id": process.get("tool_id"),
            "name": process.get("name"),
            "tickers": process.get("tickers", []),
            "weights": process.get("weights", []),
            "params": process.get("params", {}),
            "hmm_enabled": process.get("hmm_enabled", False),
            "current_regime": process.get("current_regime"),
        })
        
    except Exception as e:
        logger.exception(f"[PROCESS_TOOL] Error getting process info for {process_id}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to get process info: {str(e)}",
            "code": "INTERNAL_ERROR",
        })


# =============================================================================
# List of all process tools for registration
# =============================================================================

PROCESS_TOOLS = [
    update_process_params,
    modify_process_tickers,
    get_process_info,
]
