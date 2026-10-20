"""
Comparable Companies Agent - Focused on comps-based valuation
Status: Production
Created: December 2025

PURPOSE: Agent specialized in comparable companies analysis using trading multiples.
         Following the exact pattern from RiskSpecialistAgent.
"""

from agents import Agent, ModelSettings, CodeInterpreterTool
from openai.types.shared import Reasoning
from typing import Any, Optional
import logging

# Import only comps tools (DCF tools moved to DCF Agent)
from core.agents.valuation_tools import COMPS_TOOLS

# Import memory tools for saving important info
from core.agents.memory_tools import MEMORY_TOOLS

logger = logging.getLogger(__name__)


def create_comparable_companies_agent(market_server: Optional[Any] = None, model: str = None) -> Agent:
    """
    Factory function to create the Comparable Companies Agent.
    Following RiskSpecialistAgent pattern - uses tools, optionally has MCP servers.
    
    Args:
        market_server: Optional FMPMarketDataServer instance for additional market data access
        model: Optional model override (defaults to config.agent_model)
    
    Returns:
        Configured Agent instance for comparable companies analysis
    """
    
    # Import the prompt from the prompts module
    from core.agents.prompts.comparable_companies_prompt import get_comparable_companies_prompt
    
    # Collect MCP servers if provided (like RiskSpecialistAgent does)
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info("Comparable Companies agent includes FMP Market Data Server")
    
    # Get the prompt
    instructions = get_comparable_companies_prompt()

    # Use only the comps tools (like RiskSpecialistAgent uses RISK_TOOLS)
    tools = list(COMPS_TOOLS)
    tools.append(
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        )
    )

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to comparable companies specialist")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for comparable companies specialist: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model
    
    # Create the agent with tools AND optional MCP servers
    agent = Agent(
        name="ComparableCompaniesSpecialist",
        instructions=instructions,
        model=model,  # Dynamic model selection, not hardcoded
        tools=tools,  # Use valuation tools
        mcp_servers=mcp_servers,  # Optional MCP servers for additional access
        model_settings=ModelSettings(
            parallel_tool_calls=True,  # Can run tools in parallel
            max_tokens=15000,  # Increased output limit for comprehensive responses
            reasoning=Reasoning(effort="low", summary="detailed")  # Default to lightweight reasoning, escalate via delegates when needed
        )
    )
    
    logger.info("Comparable Companies Agent created with FMP MCP server")
    
    return agent
