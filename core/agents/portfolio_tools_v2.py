"""
Portfolio Management Tools for AI Agents (v2)
Thin wrappers around portfolio service with proper separation of concerns.
Following CODING_RULES.md: No DB access in tools, no tool-to-tool recursion.
"""

try:
    from agents import function_tool
except ImportError:
    # Fallback for when agents SDK is not available
    def function_tool(func):
        """Dummy decorator when agents SDK is not available"""
        return func

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Import context vars at module level for consistent availability
from core.utils.context_utils import user_context, session_context

@function_tool
async def list_user_portfolios() -> Dict[str, Any]:
    """
    List all portfolios for the current user.
    Returns portfolio names, IDs, and which one is default/active.
    
    Returns:
        Dictionary with list of portfolios and active/default info
    """
    from core.services import get_portfolio_service
    
    user_id = user_context.get()
    if not user_id:
        return {
            "status": "error",
            "message": "No user context available"
        }
    
    service = get_portfolio_service()
    return await service.list_user_portfolios(user_id)


@function_tool
async def get_portfolio(portfolio_id: str) -> Dict[str, Any]:
    """
    Fetch detailed portfolio data including holdings.
    
    Args:
        portfolio_id: ID of the portfolio to fetch (or name for fuzzy matching)
        
    Returns:
        Portfolio details including tickers, weights, and metadata
    """
    from core.services import get_portfolio_service
    
    user_id = user_context.get()
    if not user_id:
        return {
            "status": "error",
            "message": "No user context available"
        }
    
    service = get_portfolio_service()
    return await service.get_portfolio(user_id, portfolio_id)


@function_tool
async def set_active_portfolio(portfolio_id: str) -> Dict[str, Any]:
    """
    Set the active portfolio for the current session.
    This portfolio will be used for subsequent risk calculations.
    
    Args:
        portfolio_id: ID or name of the portfolio to set as active
        
    Returns:
        Confirmation of active portfolio setting
    """
    from core.services import get_portfolio_service
    
    user_id = user_context.get()
    session_id = session_context.get()
    
    if not user_id:
        return {
            "status": "error",
            "message": "No user context available"
        }
    
    if not session_id:
        return {
            "status": "error",
            "message": "No session context available"
        }
    
    service = get_portfolio_service()
    return await service.set_active_portfolio(session_id, user_id, portfolio_id)


@function_tool
async def get_active_portfolio() -> Dict[str, Any]:
    """
    Get the currently active portfolio for this session.
    If no active portfolio is set, returns the default portfolio.
    
    Returns:
        The active or default portfolio details
    """
    from core.services import get_portfolio_service
    
    user_id = user_context.get()
    session_id = session_context.get()
    
    if not user_id:
        return {
            "status": "error",
            "message": "No user context available"
        }
    
    if not session_id:
        # If no session, just get default portfolio
        service = get_portfolio_service()
        portfolios = await service.list_user_portfolios(user_id)
        if portfolios["status"] == "success" and portfolios.get("default_portfolio_id"):
            return await service.get_portfolio(user_id, portfolios["default_portfolio_id"])
        return {
            "status": "error",
            "message": "No session context and no default portfolio"
        }
    
    service = get_portfolio_service()
    return await service.get_active_portfolio(session_id, user_id)


# Export tools list for agent registration
PORTFOLIO_TOOLS = [
    list_user_portfolios,
    get_portfolio,
    set_active_portfolio,
    get_active_portfolio
]