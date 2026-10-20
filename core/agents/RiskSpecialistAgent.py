"""
Risk Specialist Agent - Clean Version with Modular Tools
Status: Production
Created: August 2025

PURPOSE: Risk Specialist Agent that uses modular risk tools from risk_tools directory.
         Clean separation of agent creation from tool definitions.
"""

from agents import Agent, CodeInterpreterTool
from typing import Any, Optional
import logging

# Import all risk tools from the modular risk_tools directory
from core.agents.risk_tools import (
    calculate_var,
    run_monte_carlo,
    optimize_portfolio,
    analyze_barra_factors,
    create_hedge_portfolio,
    analyze_fft_trends,
    RISK_TOOLS
)

# Import quant tools for factor decomposition (PCA is used for risk attribution)
from core.agents.quant_tools import analyze_pca_eigen_portfolios, analyze_instanton_crash

# Import memory tools for saving important info to user's memory notebook
from core.agents.memory_tools import MEMORY_TOOLS

logger = logging.getLogger(__name__)


def create_risk_specialist_agent(
    market_server: Optional[Any] = None,
    economic_server: Optional[Any] = None,
    uw_options_server: Optional[Any] = None,
    uw_market_server: Optional[Any] = None,
    model: str = None
) -> Agent:
    """
    Factory function to create the Risk Specialist Agent.
    Uses modular tools from risk_tools directory.
    
    Args:
        market_server: Optional YFinanceServer or FMPMarketDataServer instance for additional market data access
        economic_server: Optional EconomicDataServer instance for economic data access
        uw_options_server: Optional UWOptionsServer instance for GEX, dealer gamma, and flow-based risk signals
        uw_market_server: Optional UWMarketServer instance for short interest and market risk data
        model: Optional model override (defaults to config.agent_model)
    
    Returns:
        Configured Agent instance with risk calculation tools and MCP servers
    """
    # Import ModelSettings for parallel tools
    from agents import ModelSettings
    from openai.types.shared import Reasoning
    
    # Create MCP servers if not provided
    mcp_servers = []
    if market_server is None:
        from core.mcp_servers.YFinanceServer import YFinanceServer
        market_server = YFinanceServer()
    mcp_servers.append(market_server)

    if economic_server is None:
        from core.mcp_servers.EconomicDataServer import EconomicDataServer
        economic_server = EconomicDataServer()
    mcp_servers.append(economic_server)

    # Add FMP TradeFlow server for ETF holdings data (implied correlation)
    from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer
    fmp_tradeflow_server = FMPTradeFlowServer()
    mcp_servers.append(fmp_tradeflow_server)

    # Add Polygon Options server for options IV data (implied correlation)
    from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
    polygon_options_server = PolygonOptionsFuturesServer()
    mcp_servers.append(polygon_options_server)
    
    # Add UW servers for flow-based risk signals (GEX, dealer gamma, short interest)
    if uw_options_server:
        mcp_servers.append(uw_options_server)
        logger.info(f"Risk specialist includes UW Options Server for GEX and flow data")
    if uw_market_server:
        mcp_servers.append(uw_market_server)
        logger.info(f"Risk specialist includes UW Market Server for short interest data")
    
    # Import the enhanced prompt from the prompts module
    from core.agents.prompts.risk_specialist_prompt import get_risk_specialist_prompt
    
    # Use the enhanced GPT-5 optimized prompt without handoff instructions
    instructions = get_risk_specialist_prompt()
    
    # Build tools list with risk tools and portfolio tools (PCA already included in RISK_TOOLS)
    tools = list(RISK_TOOLS)
    tools.append(analyze_instanton_crash)  # Physics-based crash probability (tail risk)
    tools.append(
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        )
    )

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for risk calculations to access user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to risk specialist")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for risk specialist: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model
    
    # Create the agent with modular tools and MCP servers
    agent = Agent(
        name="SentryRiskCore",  # Updated to Sentry branding
        instructions=instructions,
        model=model,  # Dynamic model selection, not hardcoded
        tools=tools,  # Combined risk and portfolio tools
        mcp_servers=mcp_servers,  # Include MCP servers for additional data access
        model_settings=ModelSettings(
            parallel_tool_calls=True,  # Enable parallel tool calling
            max_tokens=15000,  # Increased output limit for comprehensive responses
            # temperature=1 is default for GPT-5, don't set it explicitly
            reasoning=Reasoning(effort="medium", summary="detailed")  # Maintain consistent analytical depth
        )
    )
    
    logger.info("Risk Specialist Agent created with risk tools, quant tools (PCA), and MCP servers (YFinance, Economic, FMP TradeFlow, Polygon Options)")
    
    return agent
