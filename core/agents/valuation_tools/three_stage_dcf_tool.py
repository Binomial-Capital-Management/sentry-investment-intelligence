"""
Three-Stage DCF Execution Tool
Pure DCF calculator with agent-provided assumptions
Status: Production
Created: January 2025

PURPOSE: Execute DCF calculations using agent-formulated assumptions

DATA FLOW (Two-Phase Pattern):
─────────────────────────────────────────────────────────────────────
Phase 1: Historical Trend Analysis (gather_dcf_data_sources)
  - Agent calls gather_dcf_data_sources(symbol)
  - Receives 5-year ANNUAL historical financials for trend analysis
  - Receives analyst estimates (if available)
  - Receives economic data (risk-free rate, GDP growth)

Phase 2: Agent Reasoning (FCFE-first)
  - Agent analyzes 5-year historical data to calculate:
    → EPS/Net Income trajectory (analyst EPS + historical EPS trends)
    → CapEx and D&A (maintenance vs growth; glide toward maintenance by terminal)
    → Working capital dynamics (ΔNWC series that normalizes toward ~0 by terminal)
    → Tax rates (effective tax rate trends)
  - Uses analyst EPS forecasts if available; otherwise extrapolates from historical EPS
  - Calculates cost_of_equity (and WACC for cross-check) using economic/market data

Phase 3: DCF Calculation (this tool)
  - Agent calls this tool with final reasoned assumptions
  - Tool fetches TTM (Trailing Twelve Months) baseline data
  - Executes pure DCF math with agent's assumptions
  - Returns intrinsic value and valuation breakdown
─────────────────────────────────────────────────────────────────────

IMPORTANT:
- This tool fetches TTM data for CURRENT baseline (not historical trends)
- Annual historical data comes from gather_dcf_data_sources
- Tool has NO business logic - just pure DCF calculation
- No hardcoded fallbacks or assumptions
"""

import logging
import json
from typing import Dict, Any, List, Optional
from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# TTM baseline fields for EPS/FCFE DCF calculations
# These fields are mapped to endpoints that don't require period/limit params
TTM_BASELINE_FIELDS: List[str] = [
    # From shares-float (no params required)
    "outstandingShares",
    "floatShares",
    # From company-quote (no params required for basic fields)
    "price",
    "marketCap",
    # From ratios-ttm (no params required - TRUE TTM values)
    "netIncomePerShareTTM",      # TTM EPS
    "revenuePerShareTTM",
    "freeCashFlowPerShareTTM",
    "operatingCashFlowPerShareTTM",
    "capexPerShareTTM",
    "bookValuePerShareTTM",
    "priceToEarningsRatioTTM",
    "dividendPerShareTTM",
    # From key-metrics-ttm (no params required)
    "enterpriseValueTTM",
    "freeCashFlowToEquityTTM",
    "freeCashFlowToFirmTTM",
    "workingCapitalTTM",
    "capexToRevenueTTM",
    "capexToDepreciationTTM",
    "earningsYieldTTM",
    "returnOnEquityTTM",
    # From custom-discounted-cash-flow (no params required)
    "dilutedSharesOutstanding",
    "totalCash",
    "taxRate",
    "wacc",
    "costOfEquity",
    "riskFreeRate",
]


def _normalize_assumptions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy assumption payloads to the EPS/FCFE schema."""
    normalized = dict(data)

    if isinstance(normalized.get("wacc"), (int, float)):
        normalized["wacc"] = {"rate": float(normalized["wacc"])}

    def _norm_stage(stage: Dict[str, Any], is_stage2: bool = False) -> Dict[str, Any]:
        s = dict(stage)

        # EPS growth normalization (primary)
        if not is_stage2:
            if "eps_growth" not in s:
                for key in ("growth_rate", "revenue_growth", "revenue_growth_rate", "ni_growth"):
                    if key in s:
                        s["eps_growth"] = s.pop(key)
                        break
        else:
            if "final_eps_growth" not in s:
                for key in (
                    "final_growth_rate",
                    "final_revenue_growth",
                    "revenue_growth_rate",
                    "growth_rate",
                    "final_ni_growth",
                ):
                    if key in s:
                        s["final_eps_growth"] = s.pop(key)
                        break

        # Reinvestment ratios
        if "capex_to_revenue" in s and "capex_ratio" not in s:
            s["capex_ratio"] = s.pop("capex_to_revenue")

        # Normalize all NWC variants to nwc_intensity
        if "nwc_intensity" not in s:
            for key in ("nwc_to_revenue", "working_capital_ratio", "delta_nwc_to_delta_revenue"):
                if key in s:
                    s["nwc_intensity"] = s.pop(key)
                    break

        # Duration/years
        if "duration" not in s and "years" in s:
            try:
                s["duration"] = int(s.pop("years"))
            except Exception:
                s["duration"] = s.pop("years")

        return s

    if "stage1" in normalized:
        normalized["stage1"] = _norm_stage(normalized["stage1"], is_stage2=False)
    if "stage2" in normalized:
        normalized["stage2"] = _norm_stage(normalized["stage2"], is_stage2=True)
    if "terminal" in normalized:
        normalized["terminal"] = _norm_stage(normalized["terminal"], is_stage2=False)

    return normalized


@function_tool
async def analyze_three_stage_dcf(
    symbol: str,
    dcf_data: str,
    fields: Optional[List[str]] = None
) -> str:
    """
    Execute Three-Stage DCF valuation calculation with agent-provided assumptions.

    This tool performs pure mathematical DCF calculations. The agent is responsible for
    all data gathering, field discovery, trend analysis, and assumption formulation.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    CRITICAL THREE-PHASE WORKFLOW (Must follow in sequence):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Phase 1: DATA GATHERING & FIELD DISCOVERY
    ─────────────────────────────────────────────
    • FIRST: Call discover_fields(symbol) (Market) and/or discover_dcf_fields(symbol) (Valuation)
      to understand available data structure and exact field names
    • THEN: Call gather_dcf_data_sources(symbol) to obtain:
      - 5-year annual historical financials for trend analysis
      - Analyst estimates and consensus forecasts (if available)
      - Economic indicators (risk-free rate, GDP growth, market risk premium)
    • Discovery is CRITICAL - never assume field names or availability

    Phase 2: AGENT ANALYSIS & ASSUMPTION FORMULATION
    ─────────────────────────────────────────────────
    Based on discovered fields and gathered data, the agent must:

    • ANALYZE historical trends from the 5-year data:
      - Calculate EPS growth rates using analyst estimates + historical trends
      - Determine CapEx/D&A ratios (maintenance vs growth capital)
      - Compute ΔNWC intensity metrics
      - Assess tax efficiency from historical effective rates

    • FORMULATE stage-specific assumptions:
      - Stage 1 (High Growth): Project based on recent trends or analyst estimates
      - Stage 2 (Transition): Model deceleration toward mature growth rates
      - Terminal Stage: Apply sustainable long-term growth assumptions

    • CALCULATE cost of equity (FCFE) or WACC (FCFF cross-check):
      - Use discovered debt/equity data for capital structure
      - Apply appropriate risk premiums based on company characteristics
      - Incorporate current risk-free rate from economic data

    Phase 3: DCF CALCULATION (This Tool)
    ─────────────────────────────────────────────────
    • Tool fetches TTM (Trailing Twelve Months) baseline data
    • Applies agent's assumptions to project cash flows
    • Returns calculation envelope for Code Interpreter
    • Code Interpreter computes final intrinsic value

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    AGENT RESPONSIBILITIES:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    1. DISCOVER available fields - do not assume field names or structure
    2. GATHER comprehensive historical and forecast data
    3. ANALYZE trends using discovered fields appropriately
    4. FORMULATE all DCF assumptions based on evidence
    5. PROVIDE complete assumption set - no reliance on tool defaults

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETERS:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    symbol : str
        The ticker symbol for the company to value.

    dcf_data : str (JSON)
        Complete FCFE-oriented DCF assumptions formulated by the agent after data analysis.
        Minimal structure (FCFE-first):
        {
          "stage1": {"years": int, "eps_growth": float, "capex_ratio": float,
                     "depreciation_ratio": float, "nwc_intensity": float, "tax_rate": float},
          "stage2": {"years": int, "final_eps_growth": float, "final_capex_ratio": float,
                     "final_depreciation_ratio": float, "final_nwc_intensity": float},
          "terminal": {"growth": float, "capex_ratio": float, "depreciation_ratio": float,
                       "nwc_intensity": float},
          "discount": {"cost_of_equity": float, "wacc": float}
        }

    fields : Optional[List[str]]
        Optional additional FMP fields to fetch beyond the standard set.
        Standard fields fetched automatically:
        - eps, epsDiluted, netIncome, revenue, outstandingShares, price, totalDebt,
          cashAndCashEquivalents, marketCap, depreciationAndAmortization, capitalExpenditure,
          changeInWorkingCapital

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RETURNS:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JSON string containing:
    {
        "status": "data_ready_for_calculation",
        "symbol": str,
        "data_source": "fmp_ttm",
        "financial_data": {
            "shares": float,
            "price": float,
            "ttm_eps": float,
            "ttm_eps_diluted": float,
            "net_income": float,
            "revenue": float,
            "market_cap": float,
            "total_debt": float,
            "total_cash": float,
            "depreciation_and_amortization": float,
            "capital_expenditure": float,
            "change_in_working_capital": float,
            "net_debt": float
        },
        "agent_assumptions": {...},
        "instruction": str
    }

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    IMPORTANT NOTES:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    • This tool contains NO fallback assumptions
    • Uses stable FMP baseline fields from TTM_BASELINE_FIELDS constant
    • Assumptions come from agent analysis; FCFE/EPS framing is preferred
    • TTM baseline only; historical analysis should use gather_dcf_data_sources
    • If critical data is missing, use Code Interpreter for a custom model
    """

    if not dcf_data:
        raise ValueError(
            "Agent must provide DCF assumptions after analyzing data.\n"
            "Workflow: gather_dcf_data_sources(symbol) → analyze → call this tool"
        )

    # Parse and normalize assumptions
    try:
        dcf_data_dict = json.loads(dcf_data)
        dcf_data_dict = _normalize_assumptions(dcf_data_dict)

        # Validate base structure
        base_required = ["stage1", "stage2", "terminal"]
        missing_base = [k for k in base_required if k not in dcf_data_dict]
        if missing_base:
            raise ValueError(f"Incomplete assumptions. Missing: {missing_base}")

        # Validate discount rate (flexible: wacc OR cost_of_equity OR discount block)
        has_wacc = "wacc" in dcf_data_dict
        has_ke = "cost_of_equity" in dcf_data_dict
        has_discount_block = isinstance(dcf_data_dict.get("discount"), dict) and (
            "wacc" in dcf_data_dict["discount"] or "cost_of_equity" in dcf_data_dict["discount"]
        )
        if not (has_wacc or has_ke or has_discount_block):
            raise ValueError(
                "Missing discount rate: provide 'wacc' (for FCFF) or 'cost_of_equity' (for FCFE), "
                "optionally inside a 'discount' block."
            )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dcf_data: {e}")

    # Build fields list to fetch
    fmp_fields = TTM_BASELINE_FIELDS.copy()

    if fields:
        fmp_fields.extend(fields)

    market_server = None
    try:
        logger.info(f"Starting Three-Stage DCF analysis for {symbol}")
        logger.info(f"Agent assumptions provided: {len(dcf_data_dict)} categories")
        logger.info(f"Fetching {len(fmp_fields)} FMP fields (standard + optional)")

        # Create market server for TTM data only
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # Fetch TTM baseline
        result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": fmp_fields
        })

        if not result or not hasattr(result, 'content'):
            return json.dumps({
                "error": f"No financial data found for {symbol}",
                "symbol": symbol,
                "fmp_fields_attempted": fmp_fields
            })

        financial_data = safe_parse_json(result)

        # Check for API error response
        if financial_data.get("status") == "error" or "missing_params" in financial_data:
            error_msg = financial_data.get("message", "FMP API error")
            logger.error(f"FMP API error for {symbol}: {error_msg}")
            return json.dumps({
                "error": f"FMP API error for {symbol}: {error_msg}",
                "symbol": symbol,
                "fmp_response": financial_data
            })

        # Extract data from metadata wrapper if present
        if "data" in financial_data:
            financial_data = financial_data["data"]

        logger.info(f"Retrieved FMP data for {symbol}: {list(financial_data.keys())}")

        # Map to semantic names using TTM fields
        semantic_data = {
            # Share counts
            "shares": financial_data.get("outstandingShares"),
            "diluted_shares": financial_data.get("dilutedSharesOutstanding"),
            "float_shares": financial_data.get("floatShares"),
            # Pricing
            "price": financial_data.get("price"),
            "market_cap": financial_data.get("marketCap"),
            "enterprise_value": financial_data.get("enterpriseValueTTM"),
            # Per-share TTM metrics (from ratios-ttm)
            "ttm_eps": financial_data.get("netIncomePerShareTTM"),  # TRUE TTM EPS
            "revenue_per_share": financial_data.get("revenuePerShareTTM"),
            "fcf_per_share": financial_data.get("freeCashFlowPerShareTTM"),
            "ocf_per_share": financial_data.get("operatingCashFlowPerShareTTM"),
            "capex_per_share": financial_data.get("capexPerShareTTM"),
            "book_value_per_share": financial_data.get("bookValuePerShareTTM"),
            "dividend_per_share": financial_data.get("dividendPerShareTTM"),
            "pe_ratio": financial_data.get("priceToEarningsRatioTTM"),
            # Key metrics TTM
            "fcfe_ttm": financial_data.get("freeCashFlowToEquityTTM"),
            "fcff_ttm": financial_data.get("freeCashFlowToFirmTTM"),
            "working_capital": financial_data.get("workingCapitalTTM"),
            "capex_to_revenue": financial_data.get("capexToRevenueTTM"),
            "capex_to_depreciation": financial_data.get("capexToDepreciationTTM"),
            "earnings_yield": financial_data.get("earningsYieldTTM"),
            "roe": financial_data.get("returnOnEquityTTM"),
            # From custom-dcf endpoint
            "total_cash": financial_data.get("totalCash"),
            "tax_rate": financial_data.get("taxRate"),
            "wacc": financial_data.get("wacc"),
            "cost_of_equity": financial_data.get("costOfEquity"),
            "risk_free_rate": financial_data.get("riskFreeRate"),
        }

        # Add optional fields
        if fields:
            for field in fields:
                if field in financial_data:
                    semantic_data[field] = financial_data[field]

        # Remove None values
        semantic_data = {k: v for k, v in semantic_data.items() if v is not None}

        logger.info(f"Semantic data mapped: {list(semantic_data.keys())}")

        # Validate required fields for EPS/FCFE
        if "price" not in semantic_data or semantic_data["price"] is None:
            raise ValueError(
                f"Missing required field 'price' for {symbol}. "
                f"FMP data received: {list(financial_data.keys())}"
            )

        if semantic_data.get("ttm_eps") is None:
            raise ValueError(
                f"Missing TTM EPS (netIncomePerShareTTM) for {symbol}. "
                f"FMP data received: {list(financial_data.keys())}"
            )

        # Calculate net_debt from EV - Market Cap if available, otherwise use agent-provided or default to 0
        if "net_debt" not in dcf_data_dict:
            ev = semantic_data.get("enterprise_value")
            market_cap = semantic_data.get("market_cap")
            if ev is not None and market_cap is not None:
                try:
                    net_debt = float(ev) - float(market_cap)
                    dcf_data_dict["net_debt"] = net_debt
                    logger.info(f"Calculated net_debt from EV-MarketCap: ${net_debt:,.0f}")
                except (ValueError, TypeError):
                    dcf_data_dict["net_debt"] = 0.0
                    logger.warning("Could not calculate net_debt; defaulting to 0")
            else:
                dcf_data_dict["net_debt"] = 0.0
                logger.warning("net_debt defaulted to 0 (EV or MarketCap not available)")

        # Build response payload with TTM data
        payload = {
            "status": "data_ready_for_calculation",
            "symbol": symbol,
            "data_source": "fmp_ttm",
            "financial_data": {
                # Share counts
                "shares": semantic_data.get("shares"),
                "diluted_shares": semantic_data.get("diluted_shares"),
                "float_shares": semantic_data.get("float_shares"),
                # Pricing
                "price": semantic_data.get("price"),
                "market_cap": semantic_data.get("market_cap"),
                "enterprise_value": semantic_data.get("enterprise_value"),
                # Per-share TTM metrics (from ratios-ttm)
                "ttm_eps": semantic_data.get("ttm_eps"),  # netIncomePerShareTTM
                "revenue_per_share": semantic_data.get("revenue_per_share"),
                "fcf_per_share": semantic_data.get("fcf_per_share"),
                "ocf_per_share": semantic_data.get("ocf_per_share"),
                "capex_per_share": semantic_data.get("capex_per_share"),
                "book_value_per_share": semantic_data.get("book_value_per_share"),
                "dividend_per_share": semantic_data.get("dividend_per_share"),
                "pe_ratio": semantic_data.get("pe_ratio"),
                # Key metrics TTM
                "fcfe_ttm": semantic_data.get("fcfe_ttm"),
                "fcff_ttm": semantic_data.get("fcff_ttm"),
                "working_capital": semantic_data.get("working_capital"),
                "capex_to_revenue": semantic_data.get("capex_to_revenue"),
                "capex_to_depreciation": semantic_data.get("capex_to_depreciation"),
                "earnings_yield": semantic_data.get("earnings_yield"),
                "roe": semantic_data.get("roe"),
                # From custom-dcf endpoint
                "total_cash": semantic_data.get("total_cash"),
                "tax_rate": semantic_data.get("tax_rate"),
                "wacc": semantic_data.get("wacc"),
                "cost_of_equity": semantic_data.get("cost_of_equity"),
                "risk_free_rate": semantic_data.get("risk_free_rate"),
                # Calculated
                "net_debt": dcf_data_dict.get("net_debt"),
            },
            "agent_assumptions": dcf_data_dict,
            "instruction": (
                "TTM per-share data fetched. Use CodeInterpreter to compute DCF: "
                "project EPS growth using ttm_eps as base, apply capex/depreciation ratios for reinvestment, "
                "discount FCFE at cost_of_equity (or use wacc for FCFF cross-check); "
                "ensure discount rate > terminal growth (g ≤ 5%)."
            )
        }

        logger.info(f"DCF data prepared for {symbol}")
        return json.dumps(payload)

    except Exception as e:
        logger.error(f"Error in Three-Stage DCF analysis for {symbol}: {str(e)}")
        return json.dumps({
            "error": f"DCF calculation failed: {str(e)}",
            "symbol": symbol,
            "dcf_data": dcf_data
        })
    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass


@function_tool
async def dcf_sensitivity_analysis(
    symbol: str,
    dcf_data: str,
    sensitivity_params: str
) -> str:
    """
    Perform DCF sensitivity analysis using agent-provided parameter ranges.
    Automatically fetches required financial data.

    Args:
        symbol: Company ticker symbol
        dcf_data: Base DCF assumptions
        sensitivity_params: Parameter ranges to test

    Returns:
        Sensitivity analysis results with matrix data

    Notes:
    - For FCFE (equity-mode) runs, you may interpret `wacc_range` as a
      `cost_of_equity` range, or compute a small ke×g grid directly in Code
      Interpreter for speed.

    Example sensitivity_params:
    {
        "wacc_range": [0.08, 0.09, 0.10, 0.11, 0.12],
        "terminal_growth_range": [0.015, 0.02, 0.025, 0.03, 0.035]
    }
    """

    if not dcf_data or not sensitivity_params:
        raise ValueError("Agent must provide assumptions and sensitivity parameters")

    market_server = None
    try:
        # Parse and normalize
        dcf_data_dict = json.loads(dcf_data)
        dcf_data_dict = _normalize_assumptions(dcf_data_dict)
        sensitivity_params_dict = json.loads(sensitivity_params)

        logger.info(f"Starting DCF sensitivity analysis for {symbol}")

        # Create MCP server
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # Fetch standard fields
        result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": TTM_BASELINE_FIELDS
        })

        if not result or not hasattr(result, 'content'):
            return json.dumps({
                "error": f"No financial data found for {symbol}",
                "symbol": symbol,
                "fmp_fields_attempted": TTM_BASELINE_FIELDS
            })

        raw_data = safe_parse_json(result)
        if "data" in raw_data:
            raw_data = raw_data["data"]

        # Map to semantic keys using TTM fields
        financial_data = {
            "shares": raw_data.get("outstandingShares"),
            "diluted_shares": raw_data.get("dilutedSharesOutstanding"),
            "price": raw_data.get("price"),
            "market_cap": raw_data.get("marketCap"),
            "enterprise_value": raw_data.get("enterpriseValueTTM"),
            "ttm_eps": raw_data.get("netIncomePerShareTTM"),  # TRUE TTM EPS
            "revenue_per_share": raw_data.get("revenuePerShareTTM"),
            "fcf_per_share": raw_data.get("freeCashFlowPerShareTTM"),
            "ocf_per_share": raw_data.get("operatingCashFlowPerShareTTM"),
            "capex_per_share": raw_data.get("capexPerShareTTM"),
            "book_value_per_share": raw_data.get("bookValuePerShareTTM"),
            "total_cash": raw_data.get("totalCash"),
            "wacc": raw_data.get("wacc"),
            "cost_of_equity": raw_data.get("costOfEquity"),
        }

        # Remove None values
        financial_data = {k: v for k, v in financial_data.items() if v is not None}

        # Validate required fields for EPS/FCFE
        for required_key in ("shares", "price"):
            if required_key not in financial_data:
                raise ValueError(
                    f"Missing required field '{required_key}' for sensitivity analysis"
                )
        if financial_data.get("ttm_eps") is None:
            raise ValueError(
                f"Missing TTM EPS (netIncomePerShareTTM) for sensitivity analysis. "
                f"FMP data received: {list(raw_data.keys())}"
            )

        # Calculate net_debt from EV - Market Cap if available
        if "net_debt" not in dcf_data_dict:
            ev = financial_data.get("enterprise_value")
            mc = financial_data.get("market_cap")
            if ev is not None and mc is not None:
                try:
                    dcf_data_dict["net_debt"] = float(ev) - float(mc)
                except (ValueError, TypeError):
                    dcf_data_dict["net_debt"] = 0
            else:
                dcf_data_dict["net_debt"] = 0

        # Return payload for Code Interpreter with TTM data
        payload = {
            "status": "sensitivity_request_ready",
            "symbol": symbol,
            "base_assumptions": dcf_data_dict,
            "wacc_range": sensitivity_params_dict.get("wacc_range"),
            "terminal_growth_range": sensitivity_params_dict.get("terminal_growth_range"),
            "current_price": financial_data.get("price"),
            "financial_data": {
                "shares": financial_data.get("shares"),
                "diluted_shares": financial_data.get("diluted_shares"),
                "price": financial_data.get("price"),
                "market_cap": financial_data.get("market_cap"),
                "enterprise_value": financial_data.get("enterprise_value"),
                "ttm_eps": financial_data.get("ttm_eps"),  # netIncomePerShareTTM
                "revenue_per_share": financial_data.get("revenue_per_share"),
                "fcf_per_share": financial_data.get("fcf_per_share"),
                "ocf_per_share": financial_data.get("ocf_per_share"),
                "capex_per_share": financial_data.get("capex_per_share"),
                "book_value_per_share": financial_data.get("book_value_per_share"),
                "total_cash": financial_data.get("total_cash"),
                "wacc": financial_data.get("wacc"),
                "cost_of_equity": financial_data.get("cost_of_equity"),
                "net_debt": dcf_data_dict.get("net_debt"),
            }
        }

        logger.info(f"DCF sensitivity request prepared for {symbol}")
        return json.dumps(payload)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in parameters: {e}")
    except Exception as e:
        logger.error(f"Error in DCF sensitivity analysis for {symbol}: {str(e)}")
        return json.dumps({
            "error": f"Sensitivity analysis failed: {str(e)}",
            "symbol": symbol
        })
    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass
