"""
Institutional Activity Coding Agent Factory - Creates the institutional activity coding agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Institutional Activity Coding agent
that handles custom institutional ownership, insider trading, congressional trades,
ETF flows, and ESG analysis with Code Interpreter.

This agent:
- Executes custom Python code for institutional activity analysis
- Uses OpenAI's hosted CodeInterpreterTool
- Implements smart money flow analysis (13F filings, insider trades, congressional trades)
- Performs ETF holdings and flows analysis
- Analyzes ESG ratings and benchmarking
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_institutional_activity_agent(
    tradeflow_server: Any = None,
    uw_institutional_server: Any = None,
    quiver_server: Any = None,
    model: str = None
) -> Agent:
    """
    Create the institutional activity coding agent with Code Interpreter.

    Following OpenAI documentation - uses Responses API with code_interpreter
    tool that executes Python code in a sandboxed container environment.

    Args:
        tradeflow_server: FMPTradeFlowServer instance for institutional, insider, congressional, ETF, and ESG data
        uw_institutional_server: UWInstitutionalServer instance for dark pool, congressional, insider, and ETF flow data
        quiver_server: QuiverQuantServer instance for congressional, lobbying, insider feed,
            government contracts, 13F/ETF holdings, and alternative datasets (optional)
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with execute_python_code tool
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.institutional_activity_prompt import get_institutional_activity_prompt

    # Get the enhanced prompt
    instructions = get_institutional_activity_prompt()

    # Import native Code Interpreter from Agents SDK
    from agents import CodeInterpreterTool

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool
    
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

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to institutional coder")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for institutional coder: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - always include if provided (no conditionals)
    mcp_servers = []
    if tradeflow_server:
        mcp_servers.append(tradeflow_server)
        logger.info(f"Institutional activity coding agent includes FMP TradeFlow Server: {tradeflow_server}")
    if uw_institutional_server:
        mcp_servers.append(uw_institutional_server)
        logger.info(f"Institutional activity coding agent includes UW Institutional Server: {uw_institutional_server}")
    if quiver_server:
        mcp_servers.append(quiver_server)
        logger.info(f"Institutional activity coding agent includes Quiver Server: {quiver_server}")

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with CodeInterpreterTool
    agent = Agent(
        name="InstitutionalCoder",  # Clear, distinctive name
        instructions=instructions,
        model=model,  # Dynamic model selection
        mcp_servers=mcp_servers,  # Institutional/tradeflow data server (direct attachment)
        tools=tools,  # CodeInterpreterTool + file tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage for code execution
            parallel_tool_calls=True,  # Can read files while executing code
            max_tokens=20000,  # Increased for code + output + visualizations
            reasoning=Reasoning(effort="medium", summary="detailed")  # Maintain consistent diligence across providers
        )
    )

    logger.info(f"Institutional activity coding agent created with {len(tools)} tools and {len(mcp_servers)} server(s)")

    # Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"InstitutionalCoder has {len(agent.tools)} tools registered")
        for tool in agent.tools[:5]:  # Log first 5 tools
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")

    return agent
