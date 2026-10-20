"""
Private Markets Research Agent - Web-based intelligence for private companies
Status: Production
Created: January 2025

PURPOSE: Research specialist for venture/PE markets, private companies, and funding rounds.
         Uses web search as PRIMARY tool with M&A, IPO, and market data support.
"""

from agents import Agent, ModelSettings, CodeInterpreterTool
from openai.types.shared import Reasoning
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def create_private_markets_agent(
    tradeflow_server: Optional[Any] = None,
    economic_server: Optional[Any] = None,
    market_server: Optional[Any] = None,
    model: str = None
) -> Agent:
    """
    Factory function to create the Private Markets Research Agent.

    This agent specializes in:
    - Private company research via web sources
    - M&A activity tracking (acquisitions, mergers, valuations)
    - IPO pipeline monitoring (pre-public companies, disclosures)
    - Funding round analysis (Series A/B/C, venture capital)
    - VC/PE investor research and portfolio tracking
    - Private market trends and competitive landscape

    Args:
        tradeflow_server: FMPTradeFlowServer for M&A, IPO, and institutional data
        economic_server: EconomicDataServer for macro venture market context
        market_server: FMPMarketDataServer for public market comparables
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance for private markets research
    """

    # Import the prompt
    from core.agents.prompts.private_markets_prompt import get_private_markets_prompt

    # Collect MCP servers
    mcp_servers = []

    if tradeflow_server:
        mcp_servers.append(tradeflow_server)
        logger.info("Private Markets agent includes TradeFlow Server (M&A, IPO, Executives)")

    if economic_server:
        mcp_servers.append(economic_server)
        logger.info("Private Markets agent includes Economic Data Server")

    if market_server:
        mcp_servers.append(market_server)
        logger.info("Private Markets agent includes Market Data Server")

    # Get agent instructions
    instructions = get_private_markets_prompt()

    # Define tools - web_search is PRIMARY (first in list)
    from core.tools.web_search import web_search
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    tools = [
        web_search,  # PRIMARY TOOL - web research is core capability
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        )
    ]

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to private markets specialist")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for private markets specialist: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Dynamic model selection
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent
    agent = Agent(
        name="PrivateMarketsResearchSpecialist",
        instructions=instructions,
        model=model,
        tools=tools,
        mcp_servers=mcp_servers,
        model_settings=ModelSettings(
            tool_choice="required",
            parallel_tool_calls=True,  # Search multiple sources simultaneously
            max_tokens=15000,  # Research can be comprehensive
            reasoning=Reasoning(effort="low", summary="detailed")  # Requires synthesis skills
        )
    )

    logger.info(f"Private Markets Research Agent created with model: {model}")
    logger.info(f"  - MCP Servers: {len(mcp_servers)} connected")
    logger.info(f"  - Primary Tool: web_search")
    logger.info(f"  - Supporting Tools: Code Interpreter")

    return agent
