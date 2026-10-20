"""
Alternative Assets Coding Agent Factory - Creates the alternative assets coding agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Alternative Assets Coding agent
that handles custom cryptocurrency, forex, and commodities implementations with Code Interpreter.

This agent:
- Executes custom Python code for crypto, forex, and commodities analysis
- Uses OpenAI's hosted CodeInterpreterTool
- Implements alternative asset models not available in pre-built tools
- Performs backtesting and custom analysis for digital and alternative assets
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_alternatives_coding_agent(
    polygon_server: Any = None,
    alternatives_server: Any = None,
    model: str = None,
) -> Agent:
    """
    Create the alternative assets coding agent with Code Interpreter.

    Following OpenAI documentation - uses Responses API with code_interpreter
    tool that executes Python code in a sandboxed container environment.

    Args:
        polygon_server: PolygonCryptoFXServer instance for live FX/crypto datasets
        alternatives_server: FMPAlternativesServer instance for additional alternative-asset data
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with execute_python_code tool
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.alternatives_coding_prompt import get_alternatives_coding_prompt

    # Get the enhanced prompt
    instructions = get_alternatives_coding_prompt()

    # Import native Code Interpreter from Agents SDK
    from agents import CodeInterpreterTool

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import alternatives-specific analysis tools
    from core.agents.alternatives_tools import ALTERNATIVES_TOOLS
    
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

    # Add alternatives-specific tools (crypto-equity regime, carry trade, etc.)
    tools.extend(ALTERNATIVES_TOOLS)

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to alternatives coder")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for alternatives coder: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - prefer Polygon crypto/FX as primary, then FMP alternatives
    mcp_servers = []
    if polygon_server:
        mcp_servers.append(polygon_server)
        logger.info("Alternatives coding agent includes Polygon Crypto/FX Server")
    if alternatives_server:
        mcp_servers.append(alternatives_server)
        logger.info("Alternatives coding agent includes FMP Alternatives Server")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with CodeInterpreterTool
    agent = Agent(
        name="AlternativesCoder",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Alternative assets data server (direct attachment)
        tools=tools,  # CodeInterpreterTool + file tools
        model_settings=ModelSettings(
            tool_choice="required",  # Require the agent to choose one of the registered tools
            parallel_tool_calls=True,  # Can read files while executing code
            max_tokens=20000,  # Increased for code + output + visualizations
            reasoning=Reasoning(effort="low", summary="detailed")  # Default lightweight reasoning; escalate via QuantCoder when needed
        )
    )

    logger.info(f"Alternatives coding agent created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"AlternativesCoder has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
