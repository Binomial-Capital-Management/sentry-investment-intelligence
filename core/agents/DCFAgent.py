"""
DCF Agent Factory - Creates the DCF analysis agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the DCF agent
that handles discounted cash flow valuation analysis.

This agent:
- Performs DCF valuations and intrinsic value calculations
- Calculates WACC, terminal values, and sensitivity analysis
- Uses OpenAI's hosted CodeInterpreterTool
- Uses FMP Market Data Server for financial statements
- Uses Web Search for qualitative research (products, news, industry, competition)
- Formats output in required DCF table structure
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_dcf_agent(market_server: Any = None, economic_server: Any = None, valuation_server: Any = None, model: str = None) -> Agent:
    """
    Create the DCF analysis agent with Code Interpreter and Web Search.

    Following QuantCodingAgent pattern - uses CodeInterpreterTool
    for DCF calculations and WebSearch for qualitative research.

    Args:
        market_server: FMPMarketDataServer instance for market data
        economic_server: EconomicDataServer instance for economic data
        valuation_server: FMPAdvancedValuationServer instance for valuation data
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance for DCF analysis
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.dcf_agent_prompt import get_dcf_agent_prompt

    # Get the enhanced prompt
    instructions = get_dcf_agent_prompt()

    # Import native Code Interpreter from Agents SDK
    from agents import CodeInterpreterTool

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import DCF tools for specialized calculations
    from core.agents.valuation_tools import DCF_TOOLS

    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with native Code Interpreter + DCF tools
    tools = [
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
        read_file_content,       # For loading financial data files/CSVs
        search_file_chunks_tool,  # For semantic search over uploaded financial models
        *DCF_TOOLS,              # Add specialized DCF tools (gather_dcf_data_sources, analyze_three_stage_dcf, dcf_sensitivity_analysis, analyze_two_stage_dcf)
    ]

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to DCF analyst")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for DCF analyst: {e}")

    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - always include if provided (no conditionals)
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"DCF agent includes Market Server: {market_server}")
    if economic_server:
        mcp_servers.append(economic_server)
        logger.info(f"DCF agent includes Economic Server: {economic_server}")
    if valuation_server:
        mcp_servers.append(valuation_server)
        logger.info(f"DCF agent includes Valuation Server: {valuation_server}")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with CodeInterpreterTool
    agent = Agent(
        name="DCFAnalyst",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Market data server (direct attachment)
        tools=tools,  # CodeInterpreterTool + file tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage for DCF calculations
            parallel_tool_calls=True,  # Can read files while executing code
            max_tokens=50000,  # Maximum for complex DCF models, tables, code, and comprehensive analysis
            reasoning=Reasoning(effort="low", summary="detailed")  # Universal: Works for both OpenAI and Anthropic
        )
    )

    logger.info(f"DCF agent created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"DCFAnalyst has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent