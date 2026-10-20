"""
Quant Coding Agent Factory - Creates the quantitative coding agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Quant Coding agent
that handles custom quantitative implementations with Code Interpreter.

This agent:
- Executes custom Python code for quantitative finance
- Uses OpenAI's hosted CodeInterpreterTool
- Implements models not available in pre-built tools
- Performs backtesting and custom analysis
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_quant_coding_agent(
    market_server: Any = None,
    economic_server: Any = None,
    alternatives_server: Any = None,
    uw_options_server: Any = None,
    uw_market_server: Any = None,
    uw_institutional_server: Any = None,
    quiver_server: Any = None,
    model: str = None
) -> Agent:
    """
    Create the quantitative coding agent with Code Interpreter.

    Following OpenAI documentation - uses Responses API with code_interpreter
    tool that executes Python code in a sandboxed container environment.

    Args:
        market_server: FMPMarketDataServer instance for equity/stock data
        economic_server: EconomicDataServer instance for macro/FRED data
        alternatives_server: FMPAlternativesServer instance for crypto/forex/commodities
        uw_options_server: UWOptionsServer instance for options flow and volatility data
        uw_market_server: UWMarketServer instance for correlations, seasonality, and short interest
        uw_institutional_server: UWInstitutionalServer instance for dark pool, congressional, and institutional flow
        quiver_server: QuiverQuantServer instance for political, social,
            institutional, and alternative-signal datasets (optional)
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with execute_python_code tool
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.quant_coding_prompt import get_quant_coding_prompt

    # Get the enhanced prompt
    instructions = get_quant_coding_prompt()

    # Import native Code Interpreter from Agents SDK
    from agents import CodeInterpreterTool

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import quant tools (ARIMA, etc.)
    from core.agents.quant_tools import QUANT_TOOLS
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with native Code Interpreter
    tools = [
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
        read_file_content,      # For loading data files/CSVs
        search_file_chunks_tool,  # For semantic search over uploaded documents
    ]

    # Add quant tools
    tools.extend(QUANT_TOOLS)

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to quant coder")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for quant coder: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - always include if provided (no conditionals)
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Quant coding agent includes Market Server: {market_server}")
    if economic_server:
        mcp_servers.append(economic_server)
        logger.info(f"Quant coding agent includes Economic Server: {economic_server}")
    if alternatives_server:
        mcp_servers.append(alternatives_server)
        logger.info(f"Quant coding agent includes Alternatives Server: {alternatives_server}")
    if uw_options_server:
        mcp_servers.append(uw_options_server)
        logger.info(f"Quant coding agent includes UW Options Server: {uw_options_server}")
    if uw_market_server:
        mcp_servers.append(uw_market_server)
        logger.info(f"Quant coding agent includes UW Market Server: {uw_market_server}")
    if uw_institutional_server:
        mcp_servers.append(uw_institutional_server)
        logger.info(f"Quant coding agent includes UW Institutional Server: {uw_institutional_server}")
    if quiver_server:
        mcp_servers.append(quiver_server)
        logger.info(f"Quant coding agent includes Quiver Server: {quiver_server}")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with CodeInterpreterTool
    agent = Agent(
        name="QuantCoder",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Market, Economic, Alternatives servers (direct attachment)
        tools=tools,  # CodeInterpreterTool + file tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage for code execution
            parallel_tool_calls=True,  # Can read files while executing code
            max_tokens=50000,  # Maximum for complex algorithms, charts, and comprehensive analysis
            reasoning=Reasoning(effort="medium", summary="detailed")  # Ensure consistent depth across providers
        )
    )

    logger.info(f"Quant coding agent created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"QuantCoder has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
