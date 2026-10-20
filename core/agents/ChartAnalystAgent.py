"""
Chart Analyst Agent Factory - Creates the chart analysis agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Chart Analyst agent
that handles technical analysis, chart pattern recognition, and
visual interpretation of financial charts.

This agent:
- Analyzes uploaded chart images using GPT-5 vision
- Fetches technical indicators via FMPMarketDataServer
- Identifies chart patterns and support/resistance levels
- Provides technical trading insights and signals
"""

from agents import Agent, ModelSettings, CodeInterpreterTool
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_chart_analyst_agent(
    market_server: Any = None,
    uw_options_server: Any = None,
    uw_market_server: Any = None,
    quiver_server: Any = None,
    model: str = None
) -> Agent:
    """
    Create the chart analyst agent with market data and vision capabilities.

    Args:
        market_server: FMPMarketDataServer instance for technical data (optional)
        uw_options_server: UWOptionsServer instance for GEX levels as S/R and flow-based key levels
        uw_market_server: UWMarketServer instance for market movers, short interest, and correlations
        quiver_server: QuiverQuantServer instance for off-exchange, sentiment,
            and event/political context overlays (optional)
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with technical analysis tools
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.chart_analyst_prompt import get_chart_analyst_prompt

    # Use the specialized technical analysis prompt
    instructions = get_chart_analyst_prompt()

    # Import vision tools for chart image analysis
    from core.agents.file_tools import read_file_content
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS


    # Collect available MCP servers
    mcp_servers = []

    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Chart analyst includes FMP Market Server: {market_server}")
    else:
        logger.warning("Chart analyst created without market data server - only image analysis available")
    
    if uw_options_server:
        mcp_servers.append(uw_options_server)
        logger.info(f"Chart analyst includes UW Options Server for GEX levels: {uw_options_server}")
    if uw_market_server:
        mcp_servers.append(uw_market_server)
        logger.info(f"Chart analyst includes UW Market Server for market data: {uw_market_server}")
    if quiver_server:
        mcp_servers.append(quiver_server)
        logger.info(f"Chart analyst includes Quiver Server for alternative context: {quiver_server}")

    # Collect tools
    tools = [
        read_file_content,  # For reading uploaded files (works for images too via vision API)
        # analyze_chart_image removed - read_file_content handles images perfectly
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
    ]

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to chart analyst")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for chart analyst: {e}")

    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    agent = Agent(
        name="ChartAnalyst",
        instructions=instructions,
        model=model,  # Dynamic model selection, not hardcoded
        mcp_servers=mcp_servers,  # FMP server provides all technical data tools
        tools=tools,  # Explicit vision and file tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage for analysis
            parallel_tool_calls=True,
            max_tokens=15000,  # Increased for detailed technical analysis
            reasoning=Reasoning(effort="low", summary="detailed")  # Default lightweight reasoning; heavy analysis handled via specialists
        )
    )

    logger.info(f"Chart analyst agent created with {len(mcp_servers)} server(s) and {len(tools)} tools")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"Chart Analyst has {len(agent.tools)} tools registered")
        for tool in agent.tools[:10]:  # Log first 10 to avoid spam
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
