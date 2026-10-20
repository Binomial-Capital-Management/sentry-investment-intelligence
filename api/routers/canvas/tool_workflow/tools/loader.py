"""
Canvas Tool Registry Loader

Loads tool definitions from registry.yaml and resolves executor functions dynamically.
Called at router startup to populate TOOL_REGISTRY.
"""

import yaml
import logging
from importlib import import_module
from pathlib import Path
from typing import Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


def _resolve_executor(executor_path: str) -> Callable[..., Awaitable[Dict]]:
    """
    Resolve executor string to actual function reference.
    
    Args:
        executor_path: Dotted path like 'api.routers.canvas.tools.risk.montecarlo.execute_monte_carlo'
        
    Returns:
        The actual async function
        
    Raises:
        ImportError: If module cannot be imported
        AttributeError: If function not found in module
    """
    module_path, func_name = executor_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, func_name)


def load_tool_registry() -> Dict[str, Dict[str, Any]]:
    """
    Load all tools from registry.yaml and return populated registry dict.
    
    Returns:
        Dict mapping tool_id to tool info dict with resolved executor
    """
    registry_path = Path(__file__).parent / "registry.yaml"
    
    if not registry_path.exists():
        logger.error(f"Tool registry not found at {registry_path}")
        return {}
    
    with open(registry_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if not config or "tools" not in config:
        logger.error("Invalid registry.yaml - missing 'tools' key")
        return {}
    
    registry: Dict[str, Dict[str, Any]] = {}
    loaded_count = 0
    failed_count = 0
    
    for tool_def in config["tools"]:
        tool_id = tool_def.get("id")
        if not tool_id:
            logger.warning("Skipping tool with missing 'id'")
            continue
            
        try:
            executor = _resolve_executor(tool_def["executor"])
            
            registry[tool_id] = {
                "id": tool_id,
                "name": tool_def.get("name", tool_id),
                "description": tool_def.get("description", ""),
                "category": tool_def.get("category", "general"),
                "executor": executor,
                "params_schema": tool_def.get("params_schema", {}),
            }
            loaded_count += 1
            
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load tool '{tool_id}': {e}")
            failed_count += 1
            continue
    
    logger.info(f"Tool registry loaded: {loaded_count} tools OK, {failed_count} failed")
    return registry


# Load registry at module import time
TOOL_REGISTRY = load_tool_registry()


def get_tool_registry() -> Dict[str, Dict[str, Any]]:
    """Get the loaded tool registry."""
    return TOOL_REGISTRY


def get_tool(tool_id: str) -> Dict[str, Any] | None:
    """Get a specific tool by ID."""
    return TOOL_REGISTRY.get(tool_id)


def list_tools_by_category(category: str) -> list:
    """List all tools in a specific category."""
    return [
        tool for tool in TOOL_REGISTRY.values()
        if tool["category"] == category
    ]
