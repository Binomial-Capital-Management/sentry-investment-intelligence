"""
Screener Agent - Stock Filtering via Natural Language
Status: Production
Created: January 2025

PURPOSE: Standalone agent for AI stock screening.
         LLM interprets natural language → builds filters → calls MCP tool → returns table.
         Runs OUTSIDE LangGraph orchestrator - direct Runner execution.
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_screener_agent(
    uw_market_server: Any = None,
    uw_options_server: Any = None,
    market_server: Any = None,
    model: str = None,
    mode: str = "stocks"
) -> Agent:
    """
    Factory function to create a mode-specific Screener Agent.
    
    The LLM uses its judgment to interpret queries and map to filters.
    Prompt enforces decisive execution - no questions, just results.

    Args:
        uw_market_server: UWMarketServer instance (for flow/analysts modes)
        uw_options_server: UWOptionsServer instance (for options mode)
        market_server: FMPMarketDataServer (for stocks mode)
        model: Optional model override (defaults to config.agent_model)
        mode: stocks, flow, options, or analysts

    Returns:
        Configured Agent instance for the specified screening mode
    """
    from core.agents.prompts.screener_prompt import get_screener_prompt
    from core.config import get_config

    # Get mode-specific prompt (enforces deterministic behavior)
    instructions = get_screener_prompt(mode)

    # Use provided model or default from config
    if not model:
        model = get_config().agent_model

    # MCP servers based on mode
    mcp_servers = []
    
    if uw_market_server:
        mcp_servers.append(uw_market_server)
        logger.info("Screener agent: UW Market Server")
    
    if uw_options_server:
        mcp_servers.append(uw_options_server)
        logger.info("Screener agent: UW Options Server")
    
    if market_server:
        mcp_servers.append(market_server)
        logger.info("Screener agent: FMP Market Server")
    
    if not mcp_servers:
        raise ValueError("At least one MCP server required for screener agent")

    agent = Agent(
        name="SentryScreener",
        instructions=instructions,
        model=model,
        mcp_servers=mcp_servers,
        model_settings=ModelSettings(
            parallel_tool_calls=False,
            max_tokens=8000,
            reasoning=Reasoning(effort="low", summary="detailed")
        )
    )

    logger.info(f"Screener Agent created: mode={mode}, servers={len(mcp_servers)}")

    return agent
