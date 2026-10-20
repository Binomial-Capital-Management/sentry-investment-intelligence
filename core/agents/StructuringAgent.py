"""
Structuring Agent Factory - Creates the derivatives structuring specialist
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Structuring Agent
that handles exotic options, CDS, swaptions, and structured products pricing.

This agent:
- Prices exotic derivatives (barriers, Asians, lookbacks, variance swaps)
- Models credit derivatives (CDS, CDO, credit spreads)
- Values interest rate derivatives (swaptions, caps, floors)
- Structures complex products (autocallables, ELNs, CLNs)
- Uses web search for comprehensive market research
- Processes uploaded term sheets and pricing documents
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_structuring_agent(
    market_server: Any = None,
    economic_server: Any = None,
    tradeflow_server: Any = None,
    polygon_options_server: Any = None,
    uw_options_server: Any = None,
    model: str = None
) -> Agent:
    """
    Create the structuring agent with structuring tools and MCP servers.

    Args:
        market_server: FMPMarketDataServer instance for underlying asset data
        economic_server: EconomicDataServer instance for risk-free rates
        tradeflow_server: FMPTradeFlowServer instance for credit events
        polygon_options_server: PolygonOptionsFuturesServer for vol surface data
        uw_options_server: UWOptionsServer instance for options flow context and GEX levels
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with structuring tools
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.structuring_prompt import get_structuring_prompt

    # Get the enhanced prompt
    instructions = get_structuring_prompt()

    # Import web search tool
    from core.tools.web_search import web_search

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import Code Interpreter for pricing models
    from agents import CodeInterpreterTool

    # Import structuring tools (IRS, swaptions, CDS, variance swaps, dispersion trades, exotic derivatives)
    from core.agents.structuring_tools import STRUCTURING_TOOLS
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with structuring tools, web search, file tools, and code interpreter
    tools = STRUCTURING_TOOLS + [
        web_search,              # For researching derivatives and market data
        read_file_content,       # For loading term sheets and pricing documents
        search_file_chunks_tool, # For semantic search over uploaded documents
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),                       # For custom pricing models and advanced analytics
    ]

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to structuring desk")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for structuring desk: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - market, economic, tradeflow, polygon options, and UW options
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Structuring agent includes Market Server: {market_server}")
    if economic_server:
        mcp_servers.append(economic_server)
        logger.info(f"Structuring agent includes Economic Server: {economic_server}")
    if tradeflow_server:
        mcp_servers.append(tradeflow_server)
        logger.info(f"Structuring agent includes TradeFlow Server: {tradeflow_server}")
    if polygon_options_server:
        mcp_servers.append(polygon_options_server)
        logger.info(f"Structuring agent includes Polygon Options Server: {polygon_options_server}")
    if uw_options_server:
        mcp_servers.append(uw_options_server)
        logger.info(f"Structuring agent includes UW Options Server: {uw_options_server}")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with tools and MCP servers
    agent = Agent(
        name="StructuringDesk",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Market server for underlying data
        tools=tools,  # Web search + file tools + code interpreter
        model_settings=ModelSettings(
            tool_choice="required",  # Require the agent to select one of its registered tools
            parallel_tool_calls=True,  # Can search while reading files
            max_tokens=50000,  # Maximum for comprehensive derivatives pricing
            reasoning=Reasoning(effort="medium", summary="detailed")  # Maintain deeper analysis for complex derivatives
        )
    )

    logger.info(f"Structuring agent created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"StructuringDesk has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
