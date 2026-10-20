"""
Main Agent Factory - Creates the primary conversational agent
Status: Production
Created: August 2025

PURPOSE: Factory function for creating the main Binomial Risk Analyst agent
that handles conversation, market data queries, and economic data retrieval.

This agent:
- Manages user conversation
- Fetches market data via MCP servers
- Retrieves economic indicators
- Routes to Risk Specialist for calculations
"""

from agents import Agent, ModelSettings, CodeInterpreterTool
from openai.types.shared import Reasoning
from datetime import datetime
from typing import Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def create_main_agent(
    market_server: Any,
    economic_server: Any,
    alternatives_server: Any = None,
    tradeflow_server: Any = None,
    model: str = None,
    additional_servers: Optional[List[Any]] = None,
) -> Agent:
    """
    Create the main conversational agent with MCP servers.

    Args:
        market_server: YFinanceServer or FMPMarketDataServer instance for market data
        economic_server: EconomicDataServer instance for economic data
        alternatives_server: FMPAlternativesServer for crypto, forex, commodities
        tradeflow_server: FMPTradeFlowServer for institutional activity, insider trades
        model: Optional model override (defaults to config.agent_model)
        additional_servers: Additional MCP servers (Polygon, etc.)

    Returns:
        Configured Agent instance with MCP servers
    """
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Import the enhanced prompt from the prompts module
    from core.agents.prompts.main_agent_prompt import get_main_agent_prompt
    
    # Use the enhanced GPT-5 optimized prompt
    instructions = get_main_agent_prompt({"current_date": current_date})
    
    # Import web search tool with structured responses
    from core.tools.web_search import web_search

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool
    from core.agents.drive_tools import drive_list_files, drive_get_file_preview

    # Import sentiment analysis tool
    from core.agents.sentiment_tools import analyze_news_sentiment
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Import market-specific chart tools for visualization
    # Keep toolset minimal to reduce token overhead
    tools = [
        web_search,
        read_file_content,
        search_file_chunks_tool,
        drive_list_files,
        drive_get_file_preview,
        analyze_news_sentiment,
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
    ]
    try:
        from core.charts.tools import market_chart_build_tool
        tools.extend([market_chart_build_tool])
        logger.info("Chart build tool added to main agent (catalog omitted for token safety)")
    except ImportError:
        logger.warning("Chart build tool not available for main agent")
    
    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to main agent")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for main agent: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model
    
    mcp_servers = [market_server, economic_server]
    if alternatives_server:
        mcp_servers.append(alternatives_server)
    if tradeflow_server:
        mcp_servers.append(tradeflow_server)
    if additional_servers:
        mcp_servers.extend(additional_servers)

    agent = Agent(
        name="SentryAnalyst",  # Updated to Sentry branding
        instructions=instructions,
        model=model,  # Dynamic model selection, not hardcoded
        mcp_servers=mcp_servers,
        tools=tools,  # Web search and chart tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage to prevent looping
            parallel_tool_calls=True,  # Enable parallel tool execution
            max_tokens=15000,  # Increased output limit for comprehensive responses
            # temperature=1 is default for GPT-5, don't set it explicitly
            reasoning=Reasoning(effort="low", summary="detailed")  # Lightweight reasoning with summaries exposed
        )
    )
    
    logger.info("Main agent created with MCP servers")
    
    return agent
