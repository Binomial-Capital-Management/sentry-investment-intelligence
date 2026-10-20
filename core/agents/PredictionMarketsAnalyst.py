"""
Prediction Markets Analyst Agent Factory - Creates the prediction markets specialist
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Prediction Markets Analyst agent
that handles prediction market analysis, probability aggregation, and event forecasting.

This agent:
- Analyzes prediction markets across Kalshi, Polymarket, PredictIt, etc.
- Aggregates consensus probabilities from multiple platforms
- Evaluates market quality, liquidity, and pricing efficiency
- Provides event forecasting and probability-based insights
- Uses web search for supplementary research and context
- Processes uploaded market data and analysis documents
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def create_prediction_markets_analyst(
    market_server: Optional[Any] = None,
    polymarket_server: Optional[Any] = None,
    model: Optional[str] = None
) -> Agent:
    """
    Create the prediction markets analyst agent with web search and file tools.

    Args:
        market_server: Market data MCP server for cross-asset context
        polymarket_server: PolymarketServer instance for prediction market data
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with prediction market tools
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.prediction_markets_analyst_prompt import get_prediction_markets_analyst_prompt

    # Get the enhanced prompt
    instructions = get_prediction_markets_analyst_prompt()

    # Import web search tool
    from core.tools.web_search import web_search

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import Code Interpreter for data analysis
    from agents import CodeInterpreterTool
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with web search, file tools, and code interpreter
    tools = [
        web_search,              # For researching markets and events
        read_file_content,       # For loading market data and analysis documents
        search_file_chunks_tool, # For semantic search over uploaded documents
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),                       # For analyzing probability data and trends
    ]
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - market and prediction servers
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Prediction markets analyst includes Market Server: {market_server}")
    if polymarket_server:
        mcp_servers.append(polymarket_server)
        logger.info("Prediction markets analyst includes PolymarketServer")
    else:
        logger.warning("PolymarketServer unavailable; prediction markets agent will operate degraded.")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with tools and MCP servers
    agent = Agent(
        name="PredictionMarketsAnalyst",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Market and prediction servers
        tools=tools,  # Web search + file tools + code interpreter
        model_settings=ModelSettings(
            tool_choice="required",  # Require the agent to select one of its registered tools
            parallel_tool_calls=True,  # Can search while fetching market data
            max_tokens=50000,  # Maximum for comprehensive market analysis
            reasoning=Reasoning(effort="medium", summary="detailed")  # Medium reasoning for thorough analysis
        )
    )

    logger.info(f"Prediction markets analyst created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"PredictionMarketsAnalyst has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
