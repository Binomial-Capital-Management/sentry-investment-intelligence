"""
DCF Data Gathering Tool
Fetches all required data from 3 MCP servers for DCF analysis

Purpose: Aggregate data from Market, Valuation, and Economic servers
Agent uses this data to formulate reasoned DCF assumptions

Notes (guidance, not hardcoding):
- For EPS/FCFE analysis, discovery should include NI/EPS/Equity and cash flow bridge fields so the agent can compute FCFE and reconcile to FCFF.
- Example fields to include via discovery (names vary by dataset; use discovery to confirm):
  netIncome, eps (basic/diluted), shareholdersEquity or bookValue, operatingCashFlow,
  depreciationAndAmortization, capitalExpenditure, changeInWorkingCapital (or components),
  totalDebt, totalCash, stockBasedCompensation, weightedAverageShsOut.
"""

import logging
import json
import asyncio
from typing import List
from datetime import datetime
from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.mcp_result_parser import safe_parse_json, safe_extract_text

logger = logging.getLogger(__name__)

# Constants (avoid magic numbers/strings)
DISCOVERY_MAX_DATASETS = 50
SERIES_GDP = "GDP"
SERIES_10Y = "DGS10"          # 10-Year Treasury Rate
SERIES_CPI = "CPIAUCSL"       # Consumer Price Index


@function_tool
async def gather_dcf_data_sources(
    symbol: str,
    fields: List[str],  # REQUIRED - agent must specify which fields needed
    historical_years: int = 5
) -> str:
    """
    Gather DCF-relevant data from 3 servers: Market, Valuation, Economic.

    NO CALCULATIONS. NO FALLBACKS. NO REASONING. NO HARDCODING.
    Pure data fetcher - returns raw data with availability flags.

    Agent analyzes this data and formulates DCF assumptions.

    Data Sources:
    1. FMPMarketDataServer: Historical financials (agent-specified fields)
       → Operating margins, capex ratios, WC ratios, tax rates, growth trends

    2. FMPAdvancedValuationServer: Analyst estimates (if available)
       → Growth forecasts, WACC, margin projections, terminal growth

    3. EconomicDataServer: Macro benchmarks
       → GDP growth, risk-free rate (10Y Treasury), inflation

    Args:
        symbol: Stock ticker symbol
        fields: List of financial fields to fetch (e.g., ["revenue", "freeCashFlow", ...])
               Agent must specify - NO defaults to prevent hardcoding
        historical_years: Number of years of historical financials to fetch (default: 5)

    Returns:
        JSON with all fetched data and availability flags for agent reasoning

    Example:
        fields=["revenue", "freeCashFlow", "operatingCashFlow", "ebitda",
                "netIncome", "capitalExpenditure", "totalDebt", "totalCash"]
    """

    degraded_messages = []
    result = {
        "symbol": symbol,
        "fetch_timestamp": datetime.now().isoformat(),
        "data_sources": {},
        "degraded_messages": degraded_messages,
    }

    # ============================================
    # SOURCE 1: Historical Financials (REQUIRED)
    # ============================================
    try:
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # EXPLICIT DISCOVERY: Ensure comprehensive field coverage before fetching
        logger.info(
            f"Discovering fields for {symbol} (max_datasets={DISCOVERY_MAX_DATASETS} for comprehensive coverage)..."
        )
        discovery_result = await market_server.call_tool("discover_fields", {
            "symbol": symbol,
            "max_datasets": DISCOVERY_MAX_DATASETS,  # Increased to catch additional fields
            "period": "annual"
        })

        if discovery_result and not discovery_result.isError:
            # Use provider-agnostic parser
            discovery_data = safe_parse_json(discovery_result)
            field_count = discovery_data.get("field_count", 0)
            logger.info(f"Discovery complete: {field_count} fields found and cached")
        else:
            logger.warning(f"Discovery failed for {symbol}, relying on cached mappings")

        # Validate fields parameter (agent must provide)
        if not fields or len(fields) == 0:
            raise ValueError(
                "Agent must specify which fields to fetch - no defaults allowed. "
                "Example: fields=['revenue', 'freeCashFlow', 'ebitda', 'netIncome', ...]"
            )

        logger.info(f"Agent requested {len(fields)} fields: {fields[:5]}..." if len(fields) > 5 else f"Agent requested {len(fields)} fields: {fields}")

        # Strong suggestion: ensure critical fields are included (no hardcoding, just guidance)
        # Includes FCFF and FCFE-relevant fields to enable dual-track modeling
        critical = {
            "revenue",
            "operatingCashFlow",
            "capitalExpenditure",
            "depreciationAndAmortization",
            "totalDebt",
            "totalCash",
            "sharesOutstanding",
            "outstandingShares",
            "weightedAverageShsOut",
            "price",
            "marketCap",
            # EPS/FCFE guidance fields
            "netIncome",
            "eps",
            "epsdiluted",
            "shareholdersEquity",
            "bookValuePerShare",
            "changeInWorkingCapital",
            "stockBasedCompensation"
        }
        missing_critical = [f for f in critical if f not in fields]
        if missing_critical:
            logger.warning(
                f"DCF gather: requested fields missing common criticals (FCFF/FCFE): {missing_critical[:6]}..."
            )

        # Fetch historical financial statements with agent-specified fields
        hist_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": fields,  # Use agent-provided fields (NO hardcoding)
            "historical": True,
            "period": "annual",
            "limit": historical_years
        })

        if hist_result and not hist_result.isError:
            hist_data = safe_parse_json(hist_result)

            # METADATA LOGGING: Observability for debugging (pattern from comps_tool.py)
            if "metadata" in hist_data:
                meta = hist_data["metadata"]
                logger.info(f"Historical fetch metadata: {meta.get('api_calls', 0)} API calls, "
                           f"mapping_hits={meta.get('mapping_hits', 0)}, "
                           f"mapping_misses={meta.get('mapping_misses', 0)}, "
                           f"cache_used={meta.get('cache_used', False)}, "
                           f"endpoints={meta.get('endpoints_touched', [])[:3]}")  # Show first 3 endpoints

            # FIELD VALIDATION: Detect missing fields for diagnostics
            actual_data = hist_data.get("data", {})
            missing_fields = [f for f in fields if f not in actual_data]

            if missing_fields:
                logger.warning(f"Missing {len(missing_fields)} fields after discovery: {missing_fields}")
                logger.warning(f"Available fields: {list(actual_data.keys())[:10]}...")  # Show first 10
                degraded_messages.append(
                    f"Historical data missing fields: {missing_fields[:6]}{'...' if len(missing_fields) > 6 else ''}"
                )

            # Determine year count - try revenue first, fallback to any available field
            year_count = 0
            if actual_data:
                for field_name, field_data in actual_data.items():
                    if isinstance(field_data, list):
                        year_count = len(field_data)
                        break

            result["data_sources"]["historical_financials"] = {
                "available": True,
                "years": year_count,
                "data": hist_data,
                "source": "FMPMarketDataServer",
                "usage": "Calculate operating margins, capex/WC ratios, tax rates, historical growth",
                "fields_requested": len(fields),
                "fields_received": len(actual_data),
                "missing_fields": missing_fields if missing_fields else None
            }
        else:
            result["data_sources"]["historical_financials"] = {
                "available": False,
                "error": "Failed to fetch historical financials - REQUIRED for DCF"
            }
            degraded_messages.append("Historical financials unavailable")

        await market_server.cleanup()

    except Exception as e:
        logger.error(f"Error fetching historical financials: {e}")
        result["data_sources"]["historical_financials"] = {
            "available": False,
            "error": str(e)
        }

    # ============================================
    # SOURCE 2: Analyst Estimates (OPTIONAL)
    # ============================================
    try:
        valuation_server = FMPAdvancedValuationServer()
        await valuation_server.connect()

        growth_result, wacc_result, forecast_result = await asyncio.gather(
            valuation_server.call_tool("get_growth_estimates", {"symbol": symbol}),
            valuation_server.call_tool("calculate_wacc_inputs", {"symbol": symbol}),
            valuation_server.call_tool(
                "get_forecast_data",
                {"symbol": symbol, "forecast_types": ["revenue", "earnings", "growth"]},
            ),
        )

        # Compile analyst data
        analyst_data = {}
        if growth_result and not growth_result.isError:
            analyst_data["growth_estimates"] = safe_parse_json(growth_result)

        if wacc_result and not wacc_result.isError:
            analyst_data["wacc_inputs"] = safe_parse_json(wacc_result)

        if forecast_result and not forecast_result.isError:
            analyst_data["forecasts"] = safe_parse_json(forecast_result)

        if analyst_data:
            result["data_sources"]["analyst_estimates"] = {
                "available": True,
                "data": analyst_data,
                "source": "FMPAdvancedValuationServer",
                "usage": "Use analyst growth/WACC if available, otherwise calculate from historical"
            }
        else:
            result["data_sources"]["analyst_estimates"] = {
                "available": False,
                "note": "No analyst coverage - derive assumptions from historical data"
            }
            degraded_messages.append("No analyst estimates available")

        await valuation_server.cleanup()

    except Exception as e:
        logger.error(f"Error fetching analyst estimates: {e}")
        result["data_sources"]["analyst_estimates"] = {
            "available": False,
            "error": str(e),
            "note": "Agent should calculate from historical data"
        }

    # ============================================
    # SOURCE 3: Economic Data (REQUIRED)
    # ============================================
    try:
        economic_server = EconomicDataServer()
        await economic_server.connect()

        gdp_result, treasury_result, inflation_result = await asyncio.gather(
            economic_server.call_tool("get_economic_data", {"series_id": SERIES_GDP}),
            economic_server.call_tool("get_economic_data", {"series_id": SERIES_10Y}),
            economic_server.call_tool("get_economic_data", {"series_id": SERIES_CPI}),
        )

        economic_data = {}
        if gdp_result and not gdp_result.isError:
            economic_data["gdp"] = safe_parse_json(gdp_result)

        if treasury_result and not treasury_result.isError:
            economic_data["risk_free_rate"] = safe_parse_json(treasury_result)

        if inflation_result and not inflation_result.isError:
            economic_data["inflation"] = safe_parse_json(inflation_result)

        if economic_data:
            result["data_sources"]["economic_data"] = {
                "available": True,
                "data": economic_data,
                "source": "EconomicDataServer",
                "usage": "Risk-free rate for WACC calculation, GDP+inflation for terminal growth"
            }
        else:
            result["data_sources"]["economic_data"] = {
                "available": False,
                "error": "Economic data unavailable",
                "note": "Agent must explicitly justify macro assumptions (risk-free and terminal growth) with cited benchmarks or pivot to code_interpreter."
            }
            degraded_messages.append("Economic benchmarks unavailable; agent must justify risk-free/terminal")

        await economic_server.cleanup()

    except Exception as e:
        logger.error(f"Error fetching economic data: {e}")
        result["data_sources"]["economic_data"] = {
            "available": False,
            "error": str(e),
            "note": "Agent should use standard macro assumptions"
        }

    # ============================================
    # Summary
    # ============================================
    available = [k for k, v in result["data_sources"].items() if v.get("available", False)]

    result["summary"] = {
        "sources_available": len(available),
        "sources_list": available,
        "sufficient_for_dcf": result["data_sources"]["historical_financials"].get("available", False),
        "analyst_coverage": result["data_sources"]["analyst_estimates"].get("available", False),
        "agent_instruction": (
            "Analyze historical financials to calculate base assumptions. "
            "Use analyst estimates if available, otherwise derive from historical trends. "
            "Use economic data for WACC risk-free rate and terminal growth context."
        ),
        "degraded_messages": degraded_messages or None,
    }

    return json.dumps(result, default=str, indent=2)


@function_tool
async def discover_fields(
    symbol: str,
    max_datasets: int = DISCOVERY_MAX_DATASETS,
    period: str = "annual"
) -> str:
    """
    Wrapper around the FMP Market Data discover_fields MCP tool.
    Exposed as a direct agent tool so non-OpenAI providers can access discovery.
    """

    market_server = FMPMarketDataServer()
    await market_server.connect()

    try:
        payload = {
            "symbol": symbol,
            "max_datasets": max(1, max_datasets),
            "period": period,
        }
        logger.info("Running discover_fields via FMPMarketDataServer for %s", symbol)

        response = await market_server.call_tool("discover_fields", payload)
        if response is None or response.isError:
            message = ""
            if response:
                message = safe_extract_text(response, "")
            raise RuntimeError(f"discover_fields failed for {symbol}: {message or 'unknown error'}")

        content = safe_extract_text(response)
        if not content:
            return "{}"

        return content
    finally:
        await market_server.cleanup()


@function_tool
async def discover_dcf_fields(
    symbol: str,
    max_datasets: int = 20
) -> str:
    """
    Wrapper around the FMP Advanced Valuation discover_dcf_fields MCP tool.
    Enables discovery of valuation-specific datasets outside OpenAI providers.
    """

    valuation_server = FMPAdvancedValuationServer()
    await valuation_server.connect()

    try:
        payload = {
            "symbol": symbol,
            "max_datasets": max(1, max_datasets),
        }
        logger.info("Running discover_dcf_fields via FMPAdvancedValuationServer for %s", symbol)

        response = await valuation_server.call_tool("discover_dcf_fields", payload)
        if response is None or response.isError:
            message = ""
            if response:
                message = safe_extract_text(response, "")
            raise RuntimeError(f"discover_dcf_fields failed for {symbol}: {message or 'unknown error'}")

        content = safe_extract_text(response)
        if not content:
            return "{}"

        return content
    finally:
        await valuation_server.cleanup()
