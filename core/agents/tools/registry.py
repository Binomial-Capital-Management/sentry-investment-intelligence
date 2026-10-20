"""
Tool Registry with Context-Aware Availability.

This module provides context-aware tool selection for the Canvas Agent.
Tools are categorized by context:
- WORKSPACE: Data Workspace tools (add/remove datasets, charts, pivots)
- PROCESS: Tool Workflow tools (update params, modify tickers)
- SHARED: Tools available in both contexts (data discovery, code interpreter)

Usage:
    from core.agents.tools.registry import get_tools_for_context, ToolContext
    
    # Get tools for data workspace
    tools = get_tools_for_context(ToolContext.WORKSPACE)
    
    # Get tools for tool workflow process
    tools = get_tools_for_context(ToolContext.PROCESS)
"""

import logging
from enum import Enum
from typing import Callable, List

logger = logging.getLogger(__name__)


class ToolContext(Enum):
    """Context types that determine which tools are available."""
    WORKSPACE = "workspace"   # Data Workspace - ad-hoc data exploration
    PROCESS = "process"       # Tool Workflow - structured analysis with params


# Tool name -> context mapping
# This is the authoritative list of which tools belong to which context
TOOL_CONTEXT_MAP = {
    # ==========================================================================
    # WORKSPACE-ONLY TOOLS
    # These only make sense in the Data Workspace context
    # ==========================================================================
    "add_dataset_to_workspace": ToolContext.WORKSPACE,
    "remove_dataset": ToolContext.WORKSPACE,
    "create_chart": ToolContext.WORKSPACE,
    "create_pivot_table": ToolContext.WORKSPACE,
    "create_dataset_group": ToolContext.WORKSPACE,
    "start_tool_analysis": ToolContext.WORKSPACE,
    
    # ==========================================================================
    # PROCESS-ONLY TOOLS
    # These only make sense in the Tool Workflow (process) context
    # ==========================================================================
    "update_process_params": ToolContext.PROCESS,
    "modify_process_tickers": ToolContext.PROCESS,
    "get_process_info": ToolContext.PROCESS,
    # Note: rerun_canvas_analysis is defined inline in CanvasAgent.py
    # and is only included when process_context is present
    
    # ==========================================================================
    # SHARED TOOLS
    # These are available in both contexts
    # ==========================================================================
    # Data discovery tools - useful in both contexts
    "get_endpoint_schema": ToolContext.WORKSPACE,  # Workspace primary, but useful in process
    "list_endpoints_by_category": ToolContext.WORKSPACE,
    "search_fields": ToolContext.WORKSPACE,
}


def get_tools_for_context(context: ToolContext, include_shared: bool = True) -> List[Callable]:
    """
    Get the list of tools available for a given context.
    
    Args:
        context: The context type (WORKSPACE or PROCESS)
        include_shared: Whether to include shared tools (default: True)
    
    Returns:
        List of tool functions to register with the agent
    """
    from core.agents.tools.workspace_tools import WORKSPACE_TOOLS
    from core.agents.tools.process_tools import PROCESS_TOOLS
    from core.agents.tools.data_discovery import DATA_DISCOVERY_TOOLS
    from core.agents.tools.workflow_tools import WORKFLOW_TOOLS
    
    tools = []
    
    if context == ToolContext.WORKSPACE:
        # Workspace context: workspace tools + workflow tools + discovery tools
        tools.extend(WORKSPACE_TOOLS)
        tools.extend(WORKFLOW_TOOLS)
        tools.extend(DATA_DISCOVERY_TOOLS)
        logger.info(f"[REGISTRY] Loaded {len(WORKSPACE_TOOLS)} workspace tools + {len(WORKFLOW_TOOLS)} workflow tools + {len(DATA_DISCOVERY_TOOLS)} discovery tools")
        
    elif context == ToolContext.PROCESS:
        # Process context: process tools only
        # rerun_canvas_analysis is added separately in CanvasAgent.py
        tools.extend(PROCESS_TOOLS)
        logger.info(f"[REGISTRY] Loaded {len(PROCESS_TOOLS)} process tools")
    
    return tools


def get_tool_names_for_context(context: ToolContext) -> List[str]:
    """
    Get the names of tools available for a given context.
    Useful for documentation and debugging.
    
    Args:
        context: The context type (WORKSPACE or PROCESS)
    
    Returns:
        List of tool names
    """
    return [
        name for name, tool_context in TOOL_CONTEXT_MAP.items()
        if tool_context == context
    ]


def is_tool_available_in_context(tool_name: str, context: ToolContext) -> bool:
    """
    Check if a specific tool is available in a given context.
    
    Args:
        tool_name: Name of the tool to check
        context: The context to check against
    
    Returns:
        True if the tool is available, False otherwise
    """
    tool_context = TOOL_CONTEXT_MAP.get(tool_name)
    if tool_context is None:
        logger.warning(f"[REGISTRY] Unknown tool: {tool_name}")
        return False
    return tool_context == context
