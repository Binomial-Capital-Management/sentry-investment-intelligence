"""
Options Coding Agent Factory - Creates the listed options coding agent
Status: Production
Created: January 2025

PURPOSE: Factory function for creating the Options Coding agent
that executes custom options analytics with Code Interpreter.

This agent:
- Executes custom Python code for listed options analysis
- Uses OpenAI's hosted CodeInterpreterTool
- Leverages Polygon options datasets with catalog-driven discovery
- Performs scenario analysis, Greeks, and payoff modelling for options strategies
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any, List
import logging

logger = logging.getLogger(__name__)


def _collect_mcp_servers(*servers: Any) -> List[Any]:
    """Collect non-null MCP servers while logging inclusion."""
    collected: List[Any] = []
    for server in servers:
        if server:
            collected.append(server)
            logger.info("Options coding agent includes MCP server: %s", server.__class__.__name__)
    return collected


def create_options_coding_agent(
    polygon_options_server: Any = None,
    market_data_server: Any = None,
    uw_options_server: Any = None,
    model: str = None,
) -> Agent:
    """
    Create the listed options coding agent with Code Interpreter.

    Args:
        polygon_options_server: PolygonOptionsFuturesServer instance for options datasets
        market_data_server: Secondary MCP server (e.g., FMPMarketDataServer) for underlying data
        uw_options_server: UWOptionsServer instance for options flow, GEX, and volatility data
        model: Optional model override (defaults to config.agent_model)

    Returns:
        Configured Agent instance with execute_python_code tool
    """

    # Import the specialized prompt from the prompts module
    from core.agents.prompts.options_coding_prompt import get_options_coding_prompt

    # Get the options-centric prompt
    instructions = get_options_coding_prompt()

    # Import native Code Interpreter from Agents SDK
    from agents import CodeInterpreterTool

    # Import file tools for reading uploaded files
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool

    # Import Greeks exposure tools for options portfolio analysis
    from core.agents.quant_tools.delta_exposure_tool import calculate_delta_exposure
    from core.agents.quant_tools.gamma_exposure_tool import calculate_gamma_exposure
    from core.agents.quant_tools.vega_exposure_tool import calculate_vega_exposure
    from core.agents.quant_tools.theta_decay_tool import calculate_theta_decay
    from core.agents.quant_tools.cross_greeks_tool import calculate_cross_greeks
    from core.agents.quant_tools.dynamic_hedge_tool import construct_dynamic_hedge
    from core.agents.quant_tools.equity_option_pricing_tool import price_equity_options
    from core.agents.quant_tools.volatility_surface_tool import model_volatility_surface
    from core.agents.quant_tools.greeks_surface_tool import model_greeks_surface
    from core.agents.quant_tools.dealer_gamma_regime_tool import analyze_dealer_gamma_regime
    from core.agents.quant_tools.vanna_charm_flow_tool import analyze_vanna_charm_flow
    from core.agents.quant_tools.iv_rv_screener_tool import analyze_iv_rv_vs_peers
    from core.agents.quant_tools.gex_support_resistance_tool import analyze_gex_levels
    from core.agents.quant_tools.signal_confluence_detector import detect_signal_confluence, scan_universe_confluence
    from core.agents.quant_tools.earnings_pattern_analyzer import analyze_earnings_patterns
    from core.agents.quant_tools.squeeze_detector import detect_squeeze_setup
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Build tools list with native Code Interpreter
    tools = [
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
        read_file_content,       # Load user-provided datasets
        search_file_chunks_tool, # Semantic retrieval over uploaded research
        calculate_delta_exposure, # Options portfolio delta exposure
        calculate_gamma_exposure, # Options portfolio gamma exposure
        calculate_vega_exposure,  # Options portfolio vega exposure
        calculate_theta_decay,    # Options portfolio theta decay (time value erosion)
        calculate_cross_greeks,   # Second-order Greeks (vanna, volga, charm, veta)
        construct_dynamic_hedge,  # Multi-Greek dynamic hedging algorithm generator
        price_equity_options,     # Black-Scholes/Binomial/Monte Carlo option pricing
        model_volatility_surface, # 3D implied volatility surface modeling and visualization
        model_greeks_surface,     # 3D Greeks surfaces (delta, gamma, theta, vega) modeling
        analyze_dealer_gamma_regime, # Dealer gamma regime estimation from price dynamics
        analyze_vanna_charm_flow,    # Vanna/charm flow analysis with scenarios
        analyze_iv_rv_vs_peers,      # IV/RV peer comparison with z-scores
        analyze_gex_levels,          # GEX alpha signals with regime transition detection
        detect_squeeze_setup,        # Gamma/short squeeze early warning with configurable ML models
        detect_signal_confluence,    # Multi-factor anomaly scanner (Rentec-style)
        scan_universe_confluence,    # Batch universe confluence scanner
        analyze_earnings_patterns,   # Historical earnings pattern analysis with configurable thresholds
    ]

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)

    # Add portfolio tools for reading user portfolios
    try:
        from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
        tools.extend(PORTFOLIO_TOOLS)
        logger.debug(f"Added {len(PORTFOLIO_TOOLS)} portfolio tools to options coder")
    except ImportError as e:
        logger.warning(f"Portfolio tools not available for options coder: {e}")
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Collect MCP servers - prioritise Polygon options datasets, add UW for flow intelligence
    mcp_servers = _collect_mcp_servers(polygon_options_server, market_data_server, uw_options_server)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Create agent with CodeInterpreterTool
    agent = Agent(
        name="OptionsCoder",
        instructions=instructions,
        model=model,
        mcp_servers=mcp_servers,
        tools=tools,
        model_settings=ModelSettings(
            tool_choice="required",
            parallel_tool_calls=True,
            max_tokens=20000,
            reasoning=Reasoning(effort="low", summary="detailed"),
        ),
    )

    logger.info(
        "Options coding agent created with %d tools and %d server(s)",
        len(tools),
        len(mcp_servers),
    )

    # Verify tool registration for early warning if tool wiring changes
    if hasattr(agent, "tools"):
        logger.info("OptionsCoder has %d tools registered", len(agent.tools))
        for tool in agent.tools[:5]:
            tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")
            logger.info("  - Registered tool: %s", tool_name)

    return agent
