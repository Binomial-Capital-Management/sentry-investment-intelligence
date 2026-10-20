"""
Excel Data Service

Data feeds for =SENTRY.* custom Excel functions.
Wraps existing MCP servers (FMP, Yahoo, FRED) — no duplicate API calls.

Following CODING_RULES.md: KISS, DRY, reuse existing infrastructure.
"""

import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Simple TTL cache: {key: (value, expiry_timestamp)}
_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 60


def _cache_get(key: str) -> Optional[Any]:
    """Get from cache if not expired."""
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    """Set with TTL."""
    _cache[key] = (value, time.time() + CACHE_TTL_SECONDS)


async def get_price(ticker: str) -> Dict[str, Any]:
    """Get current stock price via existing MCP servers."""
    ticker = ticker.upper().strip()
    cache_key = f"price:{ticker}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = {"ticker": ticker, "price": None, "source": None}

    # Try FMP MCP server (existing infrastructure)
    try:
        from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
        server = FMPMarketDataServer()
        data = await server.call_tool(
            "get_fields",
            {"symbol": ticker, "fields": ["price"], "period": "ttm"},
        )
        if data and isinstance(data, dict):
            price = data.get("price")
            if price is not None:
                result["price"] = float(price)
                result["source"] = "fmp"
                _cache_set(cache_key, result)
                return result
    except Exception as e:
        logger.debug(f"FMP price failed for {ticker}: {e}")

    # Fallback: yfinance MCP server
    try:
        from core.mcp_servers.yfinance.YFinanceServer import YFinanceServer
        server = YFinanceServer()
        data = await server.call_tool(
            "get_stock_price", {"symbol": ticker}
        )
        if data and isinstance(data, dict):
            price = data.get("price") or data.get("regularMarketPrice")
            if price is not None:
                result["price"] = float(price)
                result["source"] = "yfinance"
                _cache_set(cache_key, result)
                return result
    except Exception as e:
        logger.debug(f"YFinance price failed for {ticker}: {e}")

    result["source"] = "unavailable"
    return result


async def get_metric(ticker: str, metric: str) -> Dict[str, Any]:
    """Get a financial metric via FMP MCP server (dynamic field discovery)."""
    ticker = ticker.upper().strip()
    cache_key = f"metric:{ticker}:{metric}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = {"ticker": ticker, "metric": metric, "value": None, "source": None}

    try:
        from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
        server = FMPMarketDataServer()
        data = await server.call_tool(
            "get_fields",
            {"symbol": ticker, "fields": [metric], "period": "ttm"},
        )
        if data and isinstance(data, dict):
            val = data.get(metric)
            if val is not None:
                result["value"] = float(val) if isinstance(val, (int, float)) else val
                result["source"] = "fmp"
                _cache_set(cache_key, result)
                return result
    except Exception as e:
        logger.debug(f"FMP metric failed for {ticker}/{metric}: {e}")

    result["source"] = "unavailable"
    return result


async def get_fred(series: str) -> Dict[str, Any]:
    """Get FRED economic data via existing EconomicDataServer MCP."""
    series = series.upper().strip()
    cache_key = f"fred:{series}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = {"series": series, "value": None, "source": None}

    try:
        from core.mcp_servers.EconomicDataServer import EconomicDataServer
        server = EconomicDataServer()
        data = await server.call_tool(
            "get_economic_data",
            {"series_id": series, "limit": 1, "sort_order": "desc"},
        )
        if data and isinstance(data, dict):
            observations = data.get("observations", [])
            if observations:
                val = observations[0].get("value")
                if val and val != ".":
                    result["value"] = float(val)
                    result["source"] = "fred"
                    _cache_set(cache_key, result)
                    return result
    except Exception as e:
        logger.debug(f"FRED fetch failed for {series}: {e}")

    result["source"] = "unavailable"
    return result
