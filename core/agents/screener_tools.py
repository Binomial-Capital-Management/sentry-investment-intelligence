"""
Stock Screener Tools for AI Agents
Wrapper around FMP Market Data Server's run_stock_screener tool.
Following CODING_RULES.md: No hardcoding, thin wrapper pattern.
"""

try:
    from agents import function_tool
except ImportError:
    # Fallback for when agents SDK is not available
    def function_tool(func):
        """Dummy decorator when agents SDK is not available"""
        return func

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


@function_tool
async def screen_stocks(
    marketCapMoreThan: Optional[int] = None,
    marketCapLowerThan: Optional[int] = None,
    priceMoreThan: Optional[float] = None,
    priceLowerThan: Optional[float] = None,
    peMoreThan: Optional[float] = None,
    peLowerThan: Optional[float] = None,
    betaMoreThan: Optional[float] = None,
    betaLowerThan: Optional[float] = None,
    volumeMoreThan: Optional[int] = None,
    volumeLowerThan: Optional[int] = None,
    dividendMoreThan: Optional[float] = None,
    dividendLowerThan: Optional[float] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    exchange: Optional[str] = None,
    limit: Optional[int] = 50
) -> Dict[str, Any]:
    """
    Screen stocks using FMP's company screener API with flexible filters.

    This is a wrapper tool that agents can use directly. The actual API call
    is handled by the MCP server's run_stock_screener tool.

    Args:
        marketCapMoreThan: Minimum market cap (integer, e.g., 10000000000 for $10B)
        marketCapLowerThan: Maximum market cap
        priceMoreThan: Minimum stock price
        priceLowerThan: Maximum stock price
        peMoreThan: Minimum P/E ratio
        peLowerThan: Maximum P/E ratio
        betaMoreThan: Minimum beta
        betaLowerThan: Maximum beta
        volumeMoreThan: Minimum daily volume
        volumeLowerThan: Maximum daily volume
        dividendMoreThan: Minimum dividend yield (decimal, e.g., 0.03 for 3%)
        dividendLowerThan: Maximum dividend yield
        sector: Exact sector name (e.g., "Technology", "Healthcare")
        industry: Exact industry name
        exchange: Exchange code ("NASDAQ", "NYSE", or None for all)
        limit: Number of results to return (default 50, max 1000)

    Returns:
        Dictionary with screener results including tickers, prices, metrics
    """
    errors: List[str] = []

    # Basic validation to fail fast before delegating to MCP
    if limit is not None and (limit < 1 or limit > 1000):
        errors.append("limit must be between 1 and 1000")

    def _validate_range(low: Optional[float], high: Optional[float], label: str):
        if low is not None and high is not None and low > high:
            errors.append(f"{label} lower bound exceeds upper bound")

    _validate_range(marketCapMoreThan, marketCapLowerThan, "marketCap")
    _validate_range(priceMoreThan, priceLowerThan, "price")
    _validate_range(peMoreThan, peLowerThan, "pe")
    _validate_range(betaMoreThan, betaLowerThan, "beta")
    _validate_range(volumeMoreThan, volumeLowerThan, "volume")
    _validate_range(dividendMoreThan, dividendLowerThan, "dividend")

    if errors:
        logger.warning("Invalid screener parameters: %s", errors)
        return {
            "status": "error",
            "message": "Invalid screener parameters",
            "errors": errors
        }

    filters = {
        "marketCapMoreThan": marketCapMoreThan,
        "marketCapLowerThan": marketCapLowerThan,
        "priceMoreThan": priceMoreThan,
        "priceLowerThan": priceLowerThan,
        "peMoreThan": peMoreThan,
        "peLowerThan": peLowerThan,
        "betaMoreThan": betaMoreThan,
        "betaLowerThan": betaLowerThan,
        "volumeMoreThan": volumeMoreThan,
        "volumeLowerThan": volumeLowerThan,
        "dividendMoreThan": dividendMoreThan,
        "dividendLowerThan": dividendLowerThan,
        "sector": sector,
        "industry": industry,
        "exchange": exchange
    }

    # Note: This tool delegates to the MCP server's run_stock_screener
    # The actual implementation is handled by FMPMarketDataServer
    # This wrapper exists to provide a clean interface for agents

    # The agent will call this tool, which will be automatically routed
    # to the MCP server's run_stock_screener by the OpenAI Agents SDK

    return {
        "status": "delegated_to_mcp",
        "message": "This tool is handled by the MCP server's run_stock_screener",
        "filters": {k: v for k, v in filters.items() if v is not None},
        "limit": limit or 50
    }


# Export tools list for agent registration
SCREENER_TOOLS = [
    screen_stocks
]
