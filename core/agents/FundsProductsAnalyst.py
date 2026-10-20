"""
Funds & Products Analyst Agent Factory - Creates the funds analysis specialist
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Funds & Products Analyst agent
that handles mutual funds, ETFs, hedge funds, and financial product analysis.

This agent:
- Analyzes mutual funds, ETFs, and hedge funds
- Compares financial products and their characteristics
- Evaluates fund holdings, expense ratios, and performance
- Provides product recommendations and due diligence
- Uses web search for comprehensive fund research
- Processes uploaded fund documents and prospectuses
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_funds_products_analyst(
    market_server: Any = None,
    alternatives_server: Any = None,
    uw_institutional_server: Any = None,
    model: str = None
) -> Agent:
    """
    Create the funds & products analyst agent with web search and file tools.

    Args:
        market_server: FMPMarketDataServer instance for equity fund data
        alternatives_server: FMPAlternativesServer instance for crypto/commodity funds
        uw_institutional_server: UWInstitutionalServer instance for ETF holdings, exposure, and flow data
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with web search and file tools
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.funds_products_analyst_prompt import get_funds_products_analyst_prompt

    # Get the enhanced prompt
    instructions = get_funds_products_analyst_prompt()

    # Import web search tool
    from core.tools.web_search import web_search

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import tearsheet forecast tools (ARIMA & ARIMAX for uploaded fund data)
    from core.agents.fund_tools import (
        forecast_tearsheet_returns,
        forecast_tearsheet_with_macro,
        compare_fund_returns,
    )

    # Import Code Interpreter for data analysis
    from agents import CodeInterpreterTool
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with web search, file tools, forecasting, and code interpreter
    tools = [
        web_search,                   # For researching funds and products
        read_file_content,            # For loading prospectuses and fund documents
        search_file_chunks_tool,      # For semantic search over uploaded documents
        forecast_tearsheet_returns,   # ARIMA forecast from uploaded tearsheet returns
        forecast_tearsheet_with_macro,  # ARIMAX with macro indicators (rates, inflation, etc.)
        compare_fund_returns,         # Compare multiple funds from uploaded data
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),                            # For analyzing fund data and performance
    ]
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - market, alternatives, and UW institutional servers
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Funds products analyst includes Market Server: {market_server}")
    if alternatives_server:
        mcp_servers.append(alternatives_server)
        logger.info(f"Funds products analyst includes Alternatives Server: {alternatives_server}")
    if uw_institutional_server:
        mcp_servers.append(uw_institutional_server)
        logger.info(f"Funds products analyst includes UW Institutional Server: {uw_institutional_server}")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with tools and MCP servers
    agent = Agent(
        name="FundsProductsAnalyst",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Market server for fund data
        tools=tools,  # Web search + file tools + code interpreter
        model_settings=ModelSettings(
            tool_choice="required",  # Require the agent to select one of its registered tools
            parallel_tool_calls=True,  # Can search while reading files
            max_tokens=50000,  # Maximum for comprehensive fund analysis
            reasoning=Reasoning(effort="medium", summary="detailed")  # Maintain deeper diligence for complex fund analysis
        )
    )

    logger.info(f"Funds products analyst created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"FundsProductsAnalyst has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
