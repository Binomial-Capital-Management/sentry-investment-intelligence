"""
Reverse DCF Tool
Back-solve for market-implied growth rate from current stock price.
Status: Production
Created: December 2025

PURPOSE
- Answer: "What growth rate is the market pricing in?"
- Work backwards from current stock price to derive implied growth assumptions
- Essential for sanity-checking DCF assumptions against market expectations

DATA FLOW
1. Agent discovers fields using discover_dcf_fields (FMPAdvancedValuationServer) 
   and optionally discover_fields (FMPMarketDataServer)
2. Tool fetches TTM baseline data and calculates discount_rate from beta
3. Tool runs bisection algorithm to solve for implied growth rate
4. Returns actual implied growth rate (no Code Interpreter needed)

RETURN SHAPE
{
    "status": "success",
    "symbol": "AAPL",
    "implied_growth_rate": 0.0842,
    "implied_growth_rate_pct": "8.42%",
    "current_price": 187.44,
    "calculated_dcf_value": 187.39,
    "discount_rate_used": 0.0985,
    "stages_used": 2,
    "iterations": 23,
    "financial_data": {...},
    "analyst_comparison": {...}
}
"""

import json
import logging
from typing import Dict, Any, List

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


def _normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize reverse DCF parameters with minimal validation.
    
    Following NO-HARDCODING rules: accepts agent-provided parameters flexibly.
    Only validates types, not specific allowed values.
    
    Args:
        params: Raw parameters from agent
        
    Returns:
        Normalized parameters ready for use
        
    Raises:
        ValueError: If parameters have invalid types
    """
    normalized = {}
    
    # Optional: discount_rate (agent should calculate from WACC/CAPM if not provided)
    if "discount_rate" in params:
        discount_rate = params["discount_rate"]
        if not isinstance(discount_rate, (int, float)) or discount_rate <= 0:
            raise ValueError(
                f"Invalid discount_rate: {discount_rate}. Must be a positive number (e.g., 0.10 for 10%)."
            )
        normalized["discount_rate"] = float(discount_rate)
    
    # Pass through string parameters (agent determines valid values)
    for str_key in ["model_type", "solve_for", "terminal_method", "terminal_multiple_type"]:
        if str_key in params and params[str_key] is not None:
            normalized[str_key] = str(params[str_key])
    
    # Pass through integer parameters with basic bounds check
    for int_key in ["stages", "projection_years", "stage1_years", "stage2_years", "max_iterations"]:
        if int_key in params and params[int_key] is not None:
            val = params[int_key]
            if isinstance(val, (int, float)):
                normalized[int_key] = int(val)
    
    # Pass through float parameters
    float_keys = [
        "fixed_terminal_growth", "fixed_stage1_growth", "terminal_multiple",
        "tax_rate", "capex_ratio", "depreciation_ratio", "nwc_intensity", 
        "reinvestment_rate", "tolerance",
        "current_price", "base_eps", "base_fcf", "shares_outstanding"
    ]
    for float_key in float_keys:
        if float_key in params and params[float_key] is not None:
            val = params[float_key]
            if isinstance(val, (int, float)):
                normalized[float_key] = float(val)
    
    # Pass through boolean parameters
    for bool_key in ["include_sensitivity", "compare_to_analyst"]:
        if bool_key in params:
            normalized[bool_key] = bool(params[bool_key])
    
    # Pass through list parameters (growth_bounds, sensitivity_range)
    for list_key in ["growth_bounds", "sensitivity_range"]:
        if list_key in params and params[list_key] is not None:
            val = params[list_key]
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                normalized[list_key] = [float(val[0]), float(val[1])]
    
    return normalized


def _calculate_discount_rate(beta: float, risk_free_rate: float = 0.04, market_risk_premium: float = 0.05) -> float:
    """
    Calculate cost of equity using CAPM.
    
    cost_of_equity = risk_free_rate + beta * market_risk_premium
    """
    if beta is None or beta <= 0:
        beta = 1.0  # Market beta as fallback
    return risk_free_rate + beta * market_risk_premium


def _calculate_dcf_value(
    base_metric: float,
    growth_rate: float,
    discount_rate: float,
    stages: int,
    projection_years: int,
    stage1_years: int,
    terminal_growth: float,
    stage2_years: int = 0,
) -> float:
    """
    Calculate DCF intrinsic value per share given a growth rate.
    
    For 2-stage model:
    - Stage 1: High growth at growth_rate for stage1_years
    - Terminal: Perpetuity growth at terminal_growth
    
    For 3-stage:
    - Stage 1: High growth for stage1_years
    - Stage 2: Linear fade to terminal for stage2_years
    - Terminal: Perpetuity
    """
    if base_metric is None or base_metric <= 0:
        return 0.0
    
    total_pv = 0.0
    current_cf = base_metric
    
    if stages == 1:
        # Gordon Growth Model: P = CF * (1+g) / (r - g)
        if discount_rate <= terminal_growth:
            return float('inf')
        return current_cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    
    elif stages == 2:
        # Stage 1: High growth
        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_rate)
            pv = current_cf / ((1 + discount_rate) ** year)
            total_pv += pv
        
        # Terminal value at end of stage 1
        if discount_rate <= terminal_growth:
            return float('inf')
        terminal_cf = current_cf * (1 + terminal_growth)
        terminal_value = terminal_cf / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / ((1 + discount_rate) ** stage1_years)
        total_pv += terminal_pv
    
    elif stages == 3:
        # Stage 1: High growth
        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_rate)
            pv = current_cf / ((1 + discount_rate) ** year)
            total_pv += pv
        
        # Stage 2: Linear fade from growth_rate to terminal_growth
        if stage2_years > 0:
            growth_decrement = (growth_rate - terminal_growth) / stage2_years
            fade_growth = growth_rate
            for year in range(stage1_years + 1, stage1_years + stage2_years + 1):
                fade_growth -= growth_decrement
                current_cf = current_cf * (1 + fade_growth)
                pv = current_cf / ((1 + discount_rate) ** year)
                total_pv += pv
        
        # Terminal value
        total_years = stage1_years + stage2_years
        if discount_rate <= terminal_growth:
            return float('inf')
        terminal_cf = current_cf * (1 + terminal_growth)
        terminal_value = terminal_cf / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / ((1 + discount_rate) ** total_years)
        total_pv += terminal_pv
    
    return total_pv


def _solve_implied_growth(
    target_price: float,
    base_metric: float,
    discount_rate: float,
    stages: int,
    projection_years: int,
    stage1_years: int,
    terminal_growth: float,
    stage2_years: int,
    growth_bounds: tuple,
    tolerance: float,
    max_iterations: int,
) -> Dict[str, Any]:
    """
    Use bisection to find the implied growth rate that equates DCF value to target price.
    """
    low, high = growth_bounds
    iterations = 0
    
    # Check bounds
    dcf_low = _calculate_dcf_value(base_metric, low, discount_rate, stages, projection_years, stage1_years, terminal_growth, stage2_years)
    dcf_high = _calculate_dcf_value(base_metric, high, discount_rate, stages, projection_years, stage1_years, terminal_growth, stage2_years)
    
    # Check if solution exists in bounds
    if dcf_low > target_price and dcf_high > target_price:
        return {"error": "Target price below DCF at minimum growth - stock appears overvalued vs any reasonable growth"}
    if dcf_low < target_price and dcf_high < target_price:
        return {"error": "Target price above DCF at maximum growth - stock appears undervalued vs any reasonable growth"}
    
    # Bisection
    while iterations < max_iterations:
        mid = (low + high) / 2
        dcf_mid = _calculate_dcf_value(base_metric, mid, discount_rate, stages, projection_years, stage1_years, terminal_growth, stage2_years)
        
        if abs(dcf_mid - target_price) < tolerance:
            return {
                "implied_growth_rate": mid,
                "calculated_dcf_value": dcf_mid,
                "iterations": iterations + 1,
                "converged": True,
            }
        
        if dcf_mid < target_price:
            low = mid
        else:
            high = mid
        
        iterations += 1
    
    # Return best estimate even if not fully converged
    mid = (low + high) / 2
    dcf_mid = _calculate_dcf_value(base_metric, mid, discount_rate, stages, projection_years, stage1_years, terminal_growth, stage2_years)
    return {
        "implied_growth_rate": mid,
        "calculated_dcf_value": dcf_mid,
        "iterations": iterations,
        "converged": False,
        "warning": f"Did not converge within {max_iterations} iterations",
    }


@function_tool
async def analyze_reverse_dcf(
    symbol: str,
    reverse_dcf_params: str,
    fields: List[str]
) -> str:
    """
    Prepare a Reverse DCF calculation envelope to find market-implied growth rate.

    This tool fetches baseline financial data and returns an envelope for Code Interpreter
    to solve for the growth rate that equates the DCF value to the current stock price.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    CRITICAL: DISCOVERY-FIRST WORKFLOW
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    1. FIRST: Call discover_dcf_fields(symbol) from FMPAdvancedValuationServer
       to find DCF-specific fields (FCF, EPS, revenue, etc.)
    2. OPTIONALLY: Call discover_fields(symbol) from FMPMarketDataServer
       for general market data (price, shares outstanding, market cap)
    3. THEN: Select relevant fields from discovery results
    4. FINALLY: Call this tool with the discovered fields
    
    Do NOT assume field names. Discovery determines what's available.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETERS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    symbol : str
        Stock ticker symbol (e.g., "AAPL", "MSFT")

    reverse_dcf_params : str (JSON)
        Configuration for the reverse DCF calculation:

        REQUIRED (have defaults, but agent should provide):
        - discount_rate (float): Cost of equity or WACC. Default: 0.10 (10%)
        - stages (int): Number of DCF stages (1, 2, or 3). Default: 2

        MODEL CONFIGURATION (optional):
        - model_type (str): "eps", "fcfe", "fcff". Default: "eps"
        - projection_years (int): Years to project. Default: 10
        - stage1_years (int): High-growth duration. Default: 5
        - stage2_years (int): Transition duration for 3-stage. Default: 5

        SOLVE TARGET (optional):
        - solve_for (str): What to solve for (agent-defined target)
        - fixed_terminal_growth (float): Fix terminal g, solve for stage1
        - fixed_stage1_growth (float): Fix stage1 g, solve for terminal

        TERMINAL VALUE (optional):
        - terminal_method (str): Method for terminal value calculation
        - terminal_multiple (float): Exit multiple if using multiple method
        - terminal_multiple_type (str): Type of multiple

        REINVESTMENT (optional):
        - tax_rate (float): Effective tax rate
        - capex_ratio (float): CapEx as % of revenue
        - depreciation_ratio (float): D&A as % of revenue
        - nwc_intensity (float): Delta NWC / Delta Revenue
        - reinvestment_rate (float): Reinvestment rate

        SOLVER CONFIG (optional):
        - growth_bounds (list): [min, max] search range
        - tolerance (float): Convergence tolerance in $
        - max_iterations (int): Max iterations

        OUTPUT OPTIONS (optional):
        - include_sensitivity (bool): Include discount rate sensitivity
        - sensitivity_range (list): [min, max] offset from discount_rate
        - compare_to_analyst (bool): Compare to analyst consensus

        DATA OVERRIDES (optional):
        - current_price (float): Override fetched price
        - base_eps (float): Override TTM EPS
        - base_fcf (float): Override TTM FCF per share
        - shares_outstanding (float): Override share count

    fields : List[str]
        REQUIRED. Fields to fetch from FMP - determined by discover_fields().
        Agent must specify which fields to fetch based on discovery results.
        Example: ["price", "eps", "freeCashFlow", "marketCap", "outstandingShares"]

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RETURNS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JSON string with calculation envelope:
    {
        "status": "data_ready_for_calculation",
        "symbol": str,
        "current_price": float,
        "market_cap": float,
        "financial_data": {...},
        "analyst_estimates": {...} or null,
        "reverse_dcf_params": {...},
        "instruction": str  # Solver instructions for Code Interpreter
    }

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EXAMPLE WORKFLOW
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Step 1: Discover available fields
        result = await discover_fields("AAPL")
        # Returns available field names

    Step 2: Call reverse DCF with discovered fields
        params = '{}'  # Empty - agent calculates discount_rate and infers stages
        # OR provide specific config:
        # params = '{"discount_rate": 0.10, "stages": 2}'
        fields = ["price", "eps", "freeCashFlow", "marketCap", "outstandingShares"]
        result = await analyze_reverse_dcf("AAPL", params, fields)
    """

    if not reverse_dcf_params:
        raise ValueError(
            "reverse_dcf_params is required (can be empty JSON {}). "
            "Agent should calculate discount_rate and infer stages from data if not provided."
        )
    
    if not fields or len(fields) == 0:
        raise ValueError(
            "fields parameter is required. Agent must specify which fields to fetch "
            "based on discover_fields() results. No default field list - use discovery first."
        )

    market_server = None
    valuation_server = None

    try:
        # Parse and normalize parameters
        try:
            params_dict = json.loads(reverse_dcf_params)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in reverse_dcf_params: {e}")

        normalized_params = _normalize_params(params_dict)
        logger.info(f"Reverse DCF for {symbol}: params={list(normalized_params.keys())}")

        # Use agent-provided fields (from discovery)
        fmp_fields = list(fields)
        
        # Expand to include TTM variants for reverse DCF (prefer TTM over annual)
        # Common fields that have TTM equivalents in key-metrics-ttm / ratios-ttm
        ttm_expansions = {
            "eps": "netIncomePerShareTTM",
            "pe": "priceToEarningsRatioTTM",
            "peRatio": "priceToEarningsRatioTTM",
            "freeCashFlowPerShare": "freeCashFlowPerShareTTM",
            "revenuePerShare": "revenuePerShareTTM",
            "netIncomePerShare": "netIncomePerShareTTM",
            "operatingCashFlowPerShare": "operatingCashFlowPerShareTTM",
            "bookValuePerShare": "bookValuePerShareTTM",
            "dividendYield": "dividendYieldTTM",
            "roe": "roeTTM",
            "returnOnEquity": "roeTTM",
            "roa": "roaTTM",
            "returnOnAssets": "roaTTM",
            "debtToEquity": "debtToEquityTTM",
            "currentRatio": "currentRatioTTM",
            "enterpriseValue": "enterpriseValueTTM",
            "priceToSales": "priceToSalesRatioTTM",
            "priceToBook": "priceToBookRatioTTM",
        }
        
        # Add TTM variants if base field is requested
        for base_field, ttm_field in ttm_expansions.items():
            if base_field in fmp_fields and ttm_field not in fmp_fields:
                fmp_fields.append(ttm_field)
        
        # Always fetch fields needed for discount_rate and stages calculation
        calc_fields = ["beta", "debtToEquity", "marketCap", "totalDebt"]
        for f in calc_fields:
            if f not in fmp_fields:
                fmp_fields.append(f)

        # =========================================
        # Fetch Data from FMPMarketDataServer
        # Strategy: Get current data + 4 quarters, sum quarters for TTM
        # =========================================
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # Step 1: Fetch current/TTM endpoint data (price, shares, market cap, TTM ratios)
        current_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": fmp_fields,
            "params": {"period": "annual", "limit": 1}
        })

        raw_data = {}
        if current_result and hasattr(current_result, "content"):
            current_data = safe_parse_json(current_result)
            if current_data.get("status") != "missing_required_params":
                if "data" in current_data:
                    raw_data = current_data["data"]
                else:
                    raw_data = current_data

        # Step 2: Fetch last 4 quarters for TTM calculation
        # Flow metrics (revenue, net income, FCF) need to be summed
        quarterly_flow_fields = [
            "revenue", "netIncome", "freeCashFlow", "operatingCashFlow",
            "ebitda", "grossProfit", "operatingIncome", "eps", "epsDiluted",
            "capitalExpenditure", "depreciationAndAmortization"
        ]
        # Only request fields that were in the original request
        quarterly_fields_to_fetch = [f for f in quarterly_flow_fields if f in fmp_fields or f in fields]
        
        if quarterly_fields_to_fetch:
            quarterly_result = await market_server.call_tool("get_fields", {
                "symbol": symbol,
                "fields": quarterly_fields_to_fetch,
                "historical": True,
                "period": "quarter",
                "limit": 4
            })

            if quarterly_result and hasattr(quarterly_result, "content"):
                quarterly_data = safe_parse_json(quarterly_result)
                if quarterly_data.get("status") != "missing_required_params":
                    q_data = quarterly_data.get("data", quarterly_data)
                    
                    # Sum last 4 quarters for flow metrics → TTM
                    if isinstance(q_data, list) and len(q_data) > 0:
                        logger.info(f"Calculating TTM from {len(q_data)} quarters")
                        for field in quarterly_fields_to_fetch:
                            values = [q.get(field) for q in q_data if q.get(field) is not None]
                            if len(values) >= 4:
                                ttm_value = sum(values[:4])  # Sum most recent 4
                                raw_data[f"{field}_ttm_calculated"] = ttm_value
                                # Use calculated TTM if no native TTM value
                                if field not in raw_data or raw_data.get(field) is None:
                                    raw_data[field] = ttm_value
                                logger.info(f"  {field} TTM (4Q sum): {ttm_value:,.0f}")

        if not raw_data:
            return json.dumps({
                "error": f"No financial data found for {symbol}",
                "symbol": symbol,
                "fmp_fields_attempted": fmp_fields
            })

        logger.info(f"Retrieved FMP data for {symbol}: {list(raw_data.keys())[:10]}...")

        # Map to semantic names - PREFER CALCULATED TTM (4Q sum) > TTM endpoint > annual
        shares = raw_data.get("outstandingShares") or raw_data.get("dilutedSharesOutstanding")
        price = raw_data.get("price")
        
        # EPS: prefer calculated TTM (4Q sum) > TTM endpoint > annual
        eps = (
            raw_data.get("eps_ttm_calculated") or 
            raw_data.get("epsDiluted_ttm_calculated") or
            raw_data.get("netIncomePerShareTTM") or 
            raw_data.get("eps") or 
            raw_data.get("epsDiluted")
        )
        
        # FCF: prefer calculated TTM (4Q sum) > TTM endpoint > annual
        fcf = (
            raw_data.get("freeCashFlow_ttm_calculated") or
            raw_data.get("freeCashFlow")
        )
        fcf_per_share_ttm = raw_data.get("freeCashFlowPerShareTTM")
        
        # Net income & Revenue: prefer calculated TTM
        net_income = raw_data.get("netIncome_ttm_calculated") or raw_data.get("netIncome")
        revenue = raw_data.get("revenue_ttm_calculated") or raw_data.get("revenue")
        
        market_cap = raw_data.get("marketCap") or raw_data.get("marketCapTTM")

        # Apply data overrides if provided
        if "current_price" in normalized_params:
            price = normalized_params["current_price"]
            logger.info(f"Using override price: ${price}")
        if "base_eps" in normalized_params:
            eps = normalized_params["base_eps"]
            logger.info(f"Using override EPS: ${eps}")
        if "base_fcf" in normalized_params and shares:
            fcf = normalized_params["base_fcf"] * shares
            logger.info(f"Using override FCF per share: ${normalized_params['base_fcf']}")
        if "shares_outstanding" in normalized_params:
            shares = normalized_params["shares_outstanding"]
            logger.info(f"Using override shares: {shares:,.0f}")

        # Validate required data
        if price is None:
            raise ValueError(
                f"Missing price data for {symbol}. "
                f"Provide 'current_price' override in reverse_dcf_params or check ticker validity."
            )

        # FCF per share: prefer TTM endpoint value, then calculate from total
        fcf_per_share = fcf_per_share_ttm  # From key-metrics-ttm if available
        if fcf_per_share is None and fcf is not None and shares is not None and shares > 0:
            fcf_per_share = fcf / shares

        # Log available metrics for agent reference (no hardcoded validation)
        available_metrics = []
        if eps is not None:
            available_metrics.append("eps")
        if fcf_per_share is not None:
            available_metrics.append("fcf_per_share")
        if net_income is not None:
            available_metrics.append("net_income")
        
        logger.info(f"Available metrics for {symbol}: {available_metrics}")

        # Prefer calculated TTM for other flow metrics
        ebitda = raw_data.get("ebitda_ttm_calculated") or raw_data.get("ebitda")
        operating_cf = raw_data.get("operatingCashFlow_ttm_calculated") or raw_data.get("operatingCashFlow")
        capex = raw_data.get("capitalExpenditure_ttm_calculated") or raw_data.get("capitalExpenditure")
        dna = raw_data.get("depreciationAndAmortization_ttm_calculated") or raw_data.get("depreciationAndAmortization")
        
        # Track TTM source for transparency
        ttm_source = "4Q_sum" if any(k.endswith("_ttm_calculated") for k in raw_data.keys()) else "ttm_endpoint_or_annual"

        # Build financial_data payload
        financial_data = {
            "shares": shares,
            "diluted_shares": raw_data.get("dilutedSharesOutstanding"),
            "price": price,
            "ttm_eps": eps,
            "ttm_eps_diluted": raw_data.get("epsDiluted"),
            "net_income": net_income,
            "revenue": revenue,
            "free_cash_flow": fcf,
            "ttm_fcf_per_share": fcf_per_share,
            "operating_cash_flow": operating_cf,
            "market_cap": market_cap,
            "enterprise_value": raw_data.get("enterpriseValue"),
            "ebitda": ebitda,
            "total_debt": raw_data.get("totalDebt"),
            "total_cash": raw_data.get("cashAndCashEquivalents"),
            "depreciation_and_amortization": dna,
            "capital_expenditure": capex,
            "change_in_working_capital": raw_data.get("changeInWorkingCapital"),
            "ttm_calculation_method": ttm_source,
            # Fields for discount_rate calculation (CAPM)
            "beta": raw_data.get("beta"),
            "debt_to_equity": raw_data.get("debtToEquity"),
        }

        # Calculate net debt
        total_debt = financial_data.get("total_debt")
        total_cash = financial_data.get("total_cash")
        if total_debt is not None and total_cash is not None:
            financial_data["net_debt"] = total_debt - total_cash
        else:
            financial_data["net_debt"] = None

        # Include any extra requested fields
        if fields:
            for f in fields:
                if f in raw_data and f not in financial_data:
                    financial_data[f] = raw_data[f]

        # Remove None values for cleaner output
        financial_data = {k: v for k, v in financial_data.items() if v is not None}

        await market_server.cleanup()
        market_server = None

        # =========================================
        # Fetch Analyst Estimates (optional, graceful degradation)
        # =========================================
        analyst_estimates = None
        if normalized_params.get("compare_to_analyst", True):
            try:
                valuation_server = FMPAdvancedValuationServer()
                await valuation_server.connect()

                growth_result = await valuation_server.call_tool("get_growth_estimates", {
                    "symbol": symbol
                })

                if growth_result and not growth_result.isError:
                    growth_data = safe_parse_json(growth_result)
                    
                    # Extract from growth_estimates key (actual response structure)
                    estimates_raw = growth_data.get("growth_estimates", growth_data.get("data", growth_data))
                    
                    # Handle list response (multiple periods)
                    if isinstance(estimates_raw, list) and len(estimates_raw) > 0:
                        estimates_raw = estimates_raw[0]  # Most recent
                    
                    analyst_estimates = {}
                    if isinstance(estimates_raw, dict):
                        # Copy all estimate fields
                        for key, val in estimates_raw.items():
                            if val is not None and key not in ["symbol", "date", "period"]:
                                analyst_estimates[key] = val
                    
                    if analyst_estimates:
                        logger.info(f"Retrieved {len(analyst_estimates)} analyst estimate fields for {symbol}")
                    else:
                        analyst_estimates = None
                        logger.info(f"No analyst estimates found for {symbol}")

                await valuation_server.cleanup()
                valuation_server = None

            except Exception as e:
                logger.warning(f"Failed to fetch analyst estimates for {symbol}: {e}")
                analyst_estimates = None
                if valuation_server:
                    try:
                        await valuation_server.cleanup()
                    except Exception:
                        pass
                    valuation_server = None

        # =========================================
        # Calculate Discount Rate (if not provided)
        # =========================================
        beta = financial_data.get("beta")
        if "discount_rate" in normalized_params:
            discount_rate = normalized_params["discount_rate"]
            discount_rate_source = "provided"
        else:
            discount_rate = _calculate_discount_rate(beta)
            discount_rate_source = f"calculated from beta={beta}"
        
        # =========================================
        # Determine Stages (if not provided)
        # =========================================
        if "stages" in normalized_params:
            stages = normalized_params["stages"]
        else:
            stages = 2  # Default to 2-stage
        
        # =========================================
        # Get Base Metric for DCF
        # =========================================
        model_type = normalized_params.get("model_type", "eps")
        if model_type == "eps":
            base_metric = eps
        elif model_type in ["fcfe", "fcf"]:
            base_metric = fcf_per_share
        else:
            base_metric = eps  # Fallback to EPS
        
        if base_metric is None or base_metric <= 0:
            return json.dumps({
                "error": f"Invalid base metric for {model_type}: {base_metric}",
                "symbol": symbol,
                "suggestion": "Check that EPS or FCF per share is positive"
            })
        
        # =========================================
        # Run Reverse DCF Calculation
        # =========================================
        projection_years = normalized_params.get("projection_years", 10)
        stage1_years = normalized_params.get("stage1_years", 5)
        stage2_years = normalized_params.get("stage2_years", 5)
        terminal_growth = normalized_params.get("fixed_terminal_growth", 0.025)  # Default 2.5%
        growth_bounds = normalized_params.get("growth_bounds", (-0.05, 0.50))
        tolerance = normalized_params.get("tolerance", 0.01)
        max_iterations = normalized_params.get("max_iterations", 100)
        
        result = _solve_implied_growth(
            target_price=price,
            base_metric=base_metric,
            discount_rate=discount_rate,
            stages=stages,
            projection_years=projection_years,
            stage1_years=stage1_years,
            terminal_growth=terminal_growth,
            stage2_years=stage2_years,
            growth_bounds=growth_bounds,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        
        if "error" in result:
            return json.dumps({
                "status": "calculation_failed",
                "symbol": symbol,
                "error": result["error"],
                "current_price": price,
                "base_metric": base_metric,
                "discount_rate": discount_rate,
            })
        
        implied_growth = result["implied_growth_rate"]
        
        # =========================================
        # Sensitivity Analysis (optional)
        # =========================================
        sensitivity_grid = None
        if normalized_params.get("include_sensitivity", False):
            sens_range = normalized_params.get("sensitivity_range", [-0.02, 0.02])
            sensitivity_grid = {}
            for dr_offset in [sens_range[0], sens_range[0]/2, 0, sens_range[1]/2, sens_range[1]]:
                dr = discount_rate + dr_offset
                sens_result = _solve_implied_growth(
                    target_price=price,
                    base_metric=base_metric,
                    discount_rate=dr,
                    stages=stages,
                    projection_years=projection_years,
                    stage1_years=stage1_years,
                    terminal_growth=terminal_growth,
                    stage2_years=stage2_years,
                    growth_bounds=growth_bounds,
                    tolerance=tolerance,
                    max_iterations=50,
                )
                if "implied_growth_rate" in sens_result:
                    sensitivity_grid[f"{dr:.2%}"] = f"{sens_result['implied_growth_rate']:.2%}"
        
        # =========================================
        # Analyst Comparison
        # =========================================
        analyst_comparison = None
        if analyst_estimates and normalized_params.get("compare_to_analyst", True):
            # Try to find analyst growth estimate
            analyst_growth = None
            for key in ["estimatedEpsAvg", "epsAvg", "estimatedRevenueAvg"]:
                if key in analyst_estimates and analyst_estimates[key]:
                    analyst_growth = analyst_estimates[key]
                    break
            
            if analyst_growth and eps:
                # Calculate implied growth from analyst estimate
                try:
                    analyst_implied_growth = (analyst_growth / eps) - 1
                    analyst_comparison = {
                        "implied_growth": f"{implied_growth:.2%}",
                        "analyst_consensus_growth": f"{analyst_implied_growth:.2%}",
                        "premium_to_consensus": f"{(implied_growth - analyst_implied_growth):.2%}",
                    }
                except Exception:
                    pass
        
        # =========================================
        # Build Response Payload
        # =========================================
        payload = {
            "status": "success",
            "symbol": symbol,
            "implied_growth_rate": implied_growth,
            "implied_growth_rate_pct": f"{implied_growth:.2%}",
            "current_price": price,
            "calculated_dcf_value": result["calculated_dcf_value"],
            "valuation_gap": result["calculated_dcf_value"] - price,
            "model_config": {
                "model_type": model_type,
                "base_metric": base_metric,
                "stages": stages,
                "discount_rate": discount_rate,
                "discount_rate_source": discount_rate_source,
                "terminal_growth": terminal_growth,
                "projection_years": projection_years,
            },
            "solver_info": {
                "iterations": result["iterations"],
                "converged": result.get("converged", True),
            },
            "financial_data": financial_data,
        }
        
        if sensitivity_grid:
            payload["sensitivity_grid"] = sensitivity_grid
        if analyst_comparison:
            payload["analyst_comparison"] = analyst_comparison
        if analyst_estimates:
            payload["analyst_estimates"] = analyst_estimates

        logger.info(f"Reverse DCF for {symbol}: implied growth = {implied_growth:.2%}")
        return json.dumps(payload)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in reverse_dcf_params: {e}")

    except Exception as e:
        logger.error(f"Error in Reverse DCF for {symbol}: {str(e)}")
        return json.dumps({
            "error": f"Reverse DCF failed: {str(e)}",
            "symbol": symbol,
            "reverse_dcf_params": reverse_dcf_params
        })

    finally:
        # Cleanup MCP server connections
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass
        if valuation_server is not None:
            try:
                await valuation_server.cleanup()
            except Exception:
                pass

