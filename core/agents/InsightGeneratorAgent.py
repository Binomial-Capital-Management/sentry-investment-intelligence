"""
Insight Generator Agent - Lightweight batch processing for quick insights.
Generates 6 brief market insights per page type/region.
Optimized for small context window models.
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def create_insight_generator_agent(
    market_server: Any = None,
    economic_server: Any = None,
    page_type: str = "markets",
    region: Optional[str] = None,
    model: str = None
) -> Agent:
    """
    Factory function to create a lightweight Insight Generator Agent.

    Args:
        market_server: FMPMarketDataServer for market data
        economic_server: EconomicDataServer for economic indicators
        page_type: "markets", "crypto", or "macro"
        region: For markets - "us", "eu", "china", "korea", "japan"
        model: Optional model override

    Returns:
        Lightweight Agent optimized for fast insight generation
    """
    from core.agents.prompts.insight_generator_prompt import get_insight_generator_prompt

    instructions = get_insight_generator_prompt(page_type=page_type, region=region)

    # NO tools - keep context small. Use only MCP servers for data.
    tools = []

    # MCP servers for market data only
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
    if economic_server:
        mcp_servers.append(economic_server)

    # Use nano model for fast, lightweight insights
    agent = Agent(
        name="SentryInsightGenerator",
        instructions=instructions,
        model='gpt-5-nano',
        tools=tools,
        mcp_servers=mcp_servers,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            max_tokens=4000,  # Reduced - 6 insights don't need much
            reasoning=Reasoning(effort="low"),
            response_format={"type": "json_object"}
        )
    )

    logger.debug(f"Insight Generator created: {page_type}/{region}")
    return agent
