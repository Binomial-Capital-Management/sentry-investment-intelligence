"""
EPV (Earnings Power Value) Tool
Graham/Dodd normalized earnings valuation assuming zero growth.
Status: Production
Created: December 2025

PURPOSE
- Conservative floor valuation: If EPV > Price, you're getting growth for free
- Normalize earnings over N years to smooth cyclicality
- Estimate maintenance CapEx from D&A
- Compare to current market multiples for context

FORMULA
    Normalized EBIT = normalize(EBIT over N years)
    Maintenance CapEx ≈ D&A (or user-specified ratio)
    Normalized NOPAT = Normalized EBIT × (1 - Tax Rate)
    EPV (Enterprise) = Normalized NOPAT / WACC
    Equity EPV = EPV - Net Debt
    Per Share = Equity EPV / Shares Outstanding

FEATURES
- Multiple normalization methods: average, median, weighted (recent-biased)
- Sensitivity grid: WACC × tax rate matrix
- Adjustable maintenance CapEx: D&A-based, ratio override, growth-adjusted
- Valuation multiples comparison: implied P/E, EV/EBIT vs current

LIMITATIONS (be honest)
- Maintenance CapEx ≈ D&A is a heuristic, breaks for growth companies
- Normalization doesn't detect one-time items automatically
- Zero growth assumption is conservative, not realistic
"""

import json
import logging
import statistics
from typing import Dict, Any, List, Optional

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


def _normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize EPV parameters with minimal validation.
    Accepts agent-provided parameters flexibly.
    """
    normalized = {}

    # Integer parameters
    int_keys = ["normalization_years"]
    for key in int_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (int, float)):
                normalized[key] = int(val)

    # Float parameters
    float_keys = [
        "wacc", "tax_rate", "maintenance_capex_ratio",
        "risk_free_rate", "market_risk_premium",
        "current_price", "shares_outstanding"
    ]
    for key in float_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (int, float)):
                normalized[key] = float(val)

    # String parameters
    str_keys = ["normalization_method", "capex_method"]
    for key in str_keys:
        if key in params and params[key] is not None:
            normalized[key] = str(params[key])

    # Boolean parameters
    bool_keys = ["include_sensitivity", "include_multiples_comparison"]
    for key in bool_keys:
        if key in params:
            normalized[key] = bool(params[key])

    # List parameters (sensitivity ranges)
    list_keys = ["wacc_range", "tax_range"]
    for key in list_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                normalized[key] = [float(val[0]), float(val[1])]

    return normalized


def _calculate_wacc(beta: float, risk_free_rate: float = 0.04, market_risk_premium: float = 0.05) -> float:
    """
    Calculate cost of equity using CAPM as WACC proxy.
    For proper WACC, would need debt cost and capital structure - simplified here.
    """
    if beta is None or beta <= 0:
        beta = 1.0  # Market beta fallback
    return risk_free_rate + beta * market_risk_premium


def _safe_numeric(value: Any) -> Optional[float]:
    """Safely extract a numeric value, handling dicts and other edge cases."""
    if value is None:
        return None
    if isinstance(value, dict):
        # Some FMP fields return nested dicts - try to extract a value
        return value.get("value") or value.get("v") or None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_historical_ebit(raw_data: Dict[str, Any], historical_data: List[Dict]) -> List[float]:
    """Extract EBIT values from raw and historical data."""
    ebit_values = []
    
    # Try to get EBIT from historical data first
    for year_data in historical_data:
        ebit = _safe_numeric(year_data.get("operatingIncome")) or _safe_numeric(year_data.get("ebit"))
        if ebit is not None and ebit > 0:
            ebit_values.append(ebit)
    
    # If no historical data, try current data
    if not ebit_values:
        current_ebit = _safe_numeric(raw_data.get("operatingIncome")) or _safe_numeric(raw_data.get("ebit"))
        if current_ebit is not None and current_ebit > 0:
            ebit_values.append(current_ebit)
    
    return ebit_values


def _normalize_ebit(ebit_history: List[float], method: str = "average") -> Dict[str, Any]:
    """
    Normalize EBIT using specified method.

    Methods:
    - average: Simple arithmetic mean
    - median: Middle value (robust to outliers)
    - weighted: Recent years weighted higher (3yr: 50%, 25%, 25%)

    Returns dict with normalized value and metadata.
    """
    if not ebit_history or len(ebit_history) == 0:
        return {"value": None, "error": "No EBIT history provided"}

    # Filter out None/negative values for normalization
    valid_ebit = [e for e in ebit_history if e is not None and e > 0]

    if len(valid_ebit) == 0:
        return {"value": None, "error": "No positive EBIT values in history"}

    result = {
        "method": method,
        "years_used": len(valid_ebit),
        "ebit_history": valid_ebit,
    }

    if method == "median":
        result["value"] = statistics.median(valid_ebit)
    elif method == "weighted":
        # Weight recent years more heavily
        # Weights: most recent gets 50%, then declining
        n = len(valid_ebit)
        if n == 1:
            result["value"] = valid_ebit[0]
        elif n == 2:
            result["value"] = valid_ebit[0] * 0.6 + valid_ebit[1] * 0.4
        else:
            # First 3 years: 50%, 25%, 25%; rest equal
            weights = [0.50, 0.25, 0.25] + [0.25 / max(1, n - 3)] * max(0, n - 3)
            weights = weights[:n]
            # Normalize weights to sum to 1
            weight_sum = sum(weights)
            weights = [w / weight_sum for w in weights]
            result["value"] = sum(e * w for e, w in zip(valid_ebit, weights))
            result["weights"] = weights
    else:  # default: average
        result["value"] = statistics.mean(valid_ebit)
        result["method"] = "average"

    return result


def _estimate_maintenance_capex(
    dna: Optional[float],
    capex: Optional[float],
    revenue: Optional[float],
    method: str = "dna",
    ratio: Optional[float] = None
) -> Dict[str, Any]:
    """
    Estimate maintenance CapEx using specified method.

    Methods:
    - dna: Use D&A as proxy (standard Graham/Dodd)
    - ratio: Use user-specified ratio of revenue
    - growth_adjusted: CapEx minus estimated growth CapEx (CapEx * 0.7)
    """
    result = {"method": method}

    if method == "ratio" and ratio is not None and revenue is not None:
        result["value"] = revenue * ratio
        result["ratio_used"] = ratio
    elif method == "growth_adjusted" and capex is not None:
        # Assume 30% of CapEx is maintenance, 70% is growth
        # This is a rough heuristic
        result["value"] = abs(capex) * 0.3
        result["assumption"] = "30% of CapEx assumed to be maintenance"
    elif dna is not None:
        # Default: D&A as maintenance CapEx proxy
        result["value"] = abs(dna)
        result["method"] = "dna"
    else:
        result["value"] = None
        result["error"] = "Insufficient data for maintenance CapEx estimation"

    return result


def _calculate_epv(
    normalized_ebit: float,
    tax_rate: float,
    wacc: float,
    net_debt: float,
    shares: float
) -> Dict[str, Any]:
    """
    Calculate EPV components.
    """
    if wacc <= 0:
        return {"error": "WACC must be positive"}

    normalized_nopat = normalized_ebit * (1 - tax_rate)
    epv_enterprise = normalized_nopat / wacc
    equity_epv = epv_enterprise - net_debt
    epv_per_share = equity_epv / shares if shares > 0 else None

    return {
        "normalized_nopat": normalized_nopat,
        "epv_enterprise": epv_enterprise,
        "equity_epv": equity_epv,
        "epv_per_share": epv_per_share,
    }


def _build_sensitivity_grid(
    normalized_ebit: float,
    net_debt: float,
    shares: float,
    base_wacc: float,
    base_tax: float,
    wacc_range: List[float],
    tax_range: List[float]
) -> Dict[str, Any]:
    """
    Build WACC × Tax Rate sensitivity grid.
    """
    wacc_steps = [
        base_wacc + wacc_range[0],
        base_wacc + wacc_range[0] / 2,
        base_wacc,
        base_wacc + wacc_range[1] / 2,
        base_wacc + wacc_range[1],
    ]
    tax_steps = [
        base_tax + tax_range[0],
        base_tax,
        base_tax + tax_range[1],
    ]

    # Ensure valid ranges
    wacc_steps = [max(0.01, w) for w in wacc_steps]
    tax_steps = [max(0, min(0.5, t)) for t in tax_steps]

    grid = {}
    for wacc in wacc_steps:
        wacc_key = f"{wacc:.1%}"
        grid[wacc_key] = {}
        for tax in tax_steps:
            tax_key = f"{tax:.0%}"
            result = _calculate_epv(normalized_ebit, tax, wacc, net_debt, shares)
            if "epv_per_share" in result and result["epv_per_share"] is not None:
                grid[wacc_key][tax_key] = round(result["epv_per_share"], 2)
            else:
                grid[wacc_key][tax_key] = None

    return {
        "grid": grid,
        "wacc_values": [f"{w:.1%}" for w in wacc_steps],
        "tax_values": [f"{t:.0%}" for t in tax_steps],
    }


def _calculate_multiples_comparison(
    epv_per_share: float,
    current_price: float,
    normalized_ebit: float,
    net_income: Optional[float],
    shares: float,
    market_cap: Optional[float],
    enterprise_value: Optional[float]
) -> Dict[str, Any]:
    """
    Compare EPV-implied multiples to current market multiples.
    """
    comparison = {}

    # EPV-implied P/E (if we have normalized earnings)
    if normalized_ebit and shares > 0:
        # Approximate normalized EPS from EBIT (rough)
        implied_eps = normalized_ebit * 0.75 / shares  # Assume 25% tax
        if implied_eps > 0:
            comparison["epv_implied_pe"] = round(epv_per_share / implied_eps, 1)

    # Current P/E
    if net_income and shares > 0:
        current_eps = net_income / shares
        if current_eps > 0 and current_price > 0:
            comparison["current_pe"] = round(current_price / current_eps, 1)

    # EV/EBIT comparison
    if enterprise_value and normalized_ebit and normalized_ebit > 0:
        comparison["current_ev_ebit"] = round(enterprise_value / normalized_ebit, 1)

    # EPV-implied EV/EBIT (should be 1/WACC conceptually)
    if normalized_ebit > 0:
        epv_enterprise = epv_per_share * shares + (enterprise_value - market_cap if enterprise_value and market_cap else 0)
        if epv_enterprise > 0:
            comparison["epv_implied_ev_ebit"] = round(epv_enterprise / normalized_ebit, 1)

    # Upside/downside
    if current_price > 0:
        comparison["epv_vs_price"] = round((epv_per_share / current_price - 1) * 100, 1)
        comparison["interpretation"] = (
            "EPV > Price: market may be undervaluing earnings power"
            if epv_per_share > current_price
            else "EPV < Price: market pricing in growth expectations"
        )

    return comparison


async def analyze_epv_internal(
    symbol: str,
    epv_params: str = "{}",
    fields: List[str] = None
) -> dict:
    """Internal callable for Canvas - wraps analyze_epv logic and returns dict."""
    # Import the tool and call it, then parse JSON result
    result_json = await _analyze_epv_impl(symbol, epv_params, fields or [])
    import json
    return json.loads(result_json) if isinstance(result_json, str) else result_json


async def _analyze_epv_impl(
    symbol: str,
    epv_params: str,
    fields: List[str]
) -> str:
    """Implementation of EPV analysis."""
    if not fields or len(fields) == 0:
        fields = ["operatingIncome", "ebit", "price", "marketCap", "beta"]

    market_server = None

    try:
        # Parse parameters
        try:
            params_dict = json.loads(epv_params) if epv_params else {}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in epv_params: {e}")

        normalized_params = _normalize_params(params_dict)
        logger.info(f"EPV for {symbol}: params={list(normalized_params.keys())}")

        # Configuration with defaults
        normalization_years = normalized_params.get("normalization_years", 5)
        normalization_method = normalized_params.get("normalization_method", "average")
        capex_method = normalized_params.get("capex_method", "dna")
        include_sensitivity = normalized_params.get("include_sensitivity", False)
        include_multiples = normalized_params.get("include_multiples_comparison", True)

        # Fetch Data from FMPMarketDataServer
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # Run discover_fields FIRST
        logger.info(f"Running discover_fields for {symbol} before fetching EPV data...")
        discovery_result = await market_server.call_tool("discover_fields", {
            "symbol": symbol,
            "max_datasets": 50,
            "period": "annual"
        })

        if discovery_result and not discovery_result.isError:
            discovery_data = safe_parse_json(discovery_result)
            field_count = discovery_data.get("field_count", 0)
            logger.info(f"Discovery complete: {field_count} fields found and cached")

        # Define fields needed for EPV
        epv_core_fields = [
            "operatingIncome", "ebit", "netIncome", "revenue",
            "depreciationAndAmortization", "capitalExpenditure",
            "incomeTaxExpense", "incomeBeforeTax",
            "totalDebt", "cashAndCashEquivalents", "cashAndShortTermInvestments",
            "outstandingShares", "weightedAverageShsOut",
            "price", "marketCap", "enterpriseValue", "beta"
        ]

        all_fields = list(set(epv_core_fields + list(fields)))
        logger.info(f"EPV fetching {len(all_fields)} fields")

        # Fetch current/snapshot data
        current_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": all_fields,
            "params": {"period": "annual", "limit": 1}
        })

        raw_data = {}
        if current_result and not current_result.isError:
            current_data = safe_parse_json(current_result)
            if current_data.get("status") != "missing_required_params":
                raw_data = current_data.get("data", current_data)

        # Fetch historical data for normalization
        hist_fields = [
            "operatingIncome", "ebit", "netIncome", "revenue",
            "depreciationAndAmortization", "capitalExpenditure",
            "incomeTaxExpense", "incomeBeforeTax"
        ]

        historical_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": hist_fields,
            "historical": True,
            "period": "annual",
            "limit": normalization_years
        })

        historical_data = []
        if historical_result and not historical_result.isError:
            hist_parsed = safe_parse_json(historical_result)
            if hist_parsed.get("status") != "missing_required_params":
                hist_data = hist_parsed.get("data", hist_parsed)
                if isinstance(hist_data, list):
                    historical_data = hist_data
                elif isinstance(hist_data, dict):
                    for key in ["operatingIncome", "ebit", "netIncome"]:
                        if key in hist_data and isinstance(hist_data[key], list):
                            num_years = len(hist_data[key])
                            historical_data = []
                            for i in range(num_years):
                                year_data = {}
                                for field, values in hist_data.items():
                                    if isinstance(values, list) and i < len(values):
                                        year_data[field] = values[i]
                                historical_data.append(year_data)
                            break

        await market_server.cleanup()
        market_server = None

        if not raw_data:
            return json.dumps({
                "error": f"No financial data found for {symbol}",
                "symbol": symbol
            })

        # Extract key metrics - use _safe_numeric for all values that may be dicts
        price = normalized_params.get("current_price") or _safe_numeric(raw_data.get("price"))
        shares = normalized_params.get("shares_outstanding") or _safe_numeric(raw_data.get("outstandingShares")) or _safe_numeric(raw_data.get("weightedAverageShsOut"))
        market_cap = _safe_numeric(raw_data.get("marketCap"))
        enterprise_value = _safe_numeric(raw_data.get("enterpriseValue"))
        beta = _safe_numeric(raw_data.get("beta"))

        total_debt = _safe_numeric(raw_data.get("totalDebt")) or 0
        total_cash = _safe_numeric(raw_data.get("cashAndCashEquivalents")) or _safe_numeric(raw_data.get("cashAndShortTermInvestments")) or 0
        net_debt = total_debt - total_cash

        # Tax rate
        if "tax_rate" in normalized_params:
            tax_rate = normalized_params["tax_rate"]
        else:
            tax_expense = _safe_numeric(raw_data.get("incomeTaxExpense"))
            pretax_income = _safe_numeric(raw_data.get("incomeBeforeTax"))
            if tax_expense and pretax_income and pretax_income > 0:
                tax_rate = max(0, min(0.4, tax_expense / pretax_income))
            else:
                tax_rate = 0.21

        dna = _safe_numeric(raw_data.get("depreciationAndAmortization"))
        capex = _safe_numeric(raw_data.get("capitalExpenditure"))
        revenue = _safe_numeric(raw_data.get("revenue"))

        if price is None:
            return json.dumps({"error": f"Missing price for {symbol}", "symbol": symbol})
        if shares is None or shares <= 0:
            return json.dumps({"error": f"Missing shares for {symbol}", "symbol": symbol})

        # Normalize EBIT
        ebit_values = _extract_historical_ebit(raw_data, historical_data)
        if len(ebit_values) == 0:
            return json.dumps({"error": f"No EBIT history for {symbol}", "symbol": symbol})

        ebit_result = _normalize_ebit(ebit_values, normalization_method)
        normalized_ebit = ebit_result.get("value", 0) if isinstance(ebit_result, dict) else ebit_result
        if not normalized_ebit or normalized_ebit <= 0:
            return json.dumps({"error": f"Could not normalize EBIT for {symbol}", "symbol": symbol})

        # Estimate maintenance CapEx
        if dna and dna > 0:
            maintenance_capex = abs(dna)
        elif capex:
            maintenance_capex = abs(capex) * 0.6
        elif revenue:
            maintenance_capex = revenue * 0.03
        else:
            maintenance_capex = 0

        # Calculate WACC
        if "wacc" in normalized_params:
            wacc = normalized_params["wacc"]
        else:
            risk_free = normalized_params.get("risk_free_rate", 0.04)
            market_premium = normalized_params.get("market_risk_premium", 0.05)
            equity_beta = beta if beta else 1.0
            wacc = risk_free + equity_beta * market_premium

        # EPV calculation
        normalized_nopat = normalized_ebit * (1 - tax_rate) - maintenance_capex
        if normalized_nopat < 0:
            normalized_nopat = normalized_ebit * (1 - tax_rate) * 0.8

        if wacc <= 0.01:
            wacc = 0.08

        epv_enterprise = normalized_nopat / wacc
        equity_epv = epv_enterprise - net_debt
        epv_per_share = equity_epv / shares if shares > 0 else 0

        upside_pct = ((epv_per_share / price) - 1) * 100 if price > 0 else 0
        margin_of_safety = (epv_per_share - price) / epv_per_share * 100 if epv_per_share > 0 else 0

        # Build response
        response = {
            "status": "success",
            "symbol": symbol,
            "epv_valuation": {
                "epv_per_share": round(epv_per_share, 2),
                "current_price": round(price, 2),
                "upside_pct": round(upside_pct, 1),
                "margin_of_safety_pct": round(margin_of_safety, 1),
                "epv_enterprise": round(epv_enterprise, 0),
                "equity_epv": round(equity_epv, 0),
                "normalized_ebit": round(normalized_ebit, 0),
                "normalized_nopat": round(normalized_nopat, 0),
                "maintenance_capex": round(maintenance_capex, 0),
                "wacc_used": round(wacc, 4),
                "tax_rate": round(tax_rate, 3),
                "net_debt": round(net_debt, 0),
                "normalization_years": len(ebit_values),
            },
        }

        return json.dumps(response)

    except Exception as e:
        logger.error(f"EPV calculation failed for {symbol}: {e}")
        return json.dumps({"error": f"EPV calculation failed: {str(e)}", "symbol": symbol})

    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass


@function_tool
async def analyze_epv(
    symbol: str,
    epv_params: str,
    fields: List[str]
) -> str:
    """
    Calculate Earnings Power Value (EPV) - Graham/Dodd conservative floor valuation.

    EPV answers: "What is the company worth assuming zero growth?"
    If EPV > Price, you may be getting growth for free.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    DISCOVERY-FIRST WORKFLOW
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    1. FIRST: Call discover_fields(symbol) from FMPMarketDataServer
    2. SELECT: EBIT-related fields, D&A, tax, debt, cash, shares, price
    3. THEN: Call this tool with discovered fields

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETERS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    symbol : str
        Stock ticker (e.g., "AAPL")

    epv_params : str (JSON)
        Configuration options:

        NORMALIZATION (optional):
        - normalization_years (int): Years to average EBIT. Default: 5
        - normalization_method (str): "average" | "median" | "weighted". Default: "average"

        MAINTENANCE CAPEX (optional):
        - capex_method (str): "dna" | "ratio" | "growth_adjusted". Default: "dna"
        - maintenance_capex_ratio (float): If method="ratio", CapEx as % of revenue

        DISCOUNT RATE (optional):
        - wacc (float): Weighted average cost of capital. Auto-calculated from beta if not provided
        - tax_rate (float): Effective tax rate. Fetched from data if not provided
        - risk_free_rate (float): For WACC calculation. Default: 0.04
        - market_risk_premium (float): For WACC calculation. Default: 0.05

        OUTPUT OPTIONS (optional):
        - include_sensitivity (bool): Include WACC × tax rate grid. Default: false
        - wacc_range (list): [min_offset, max_offset] for sensitivity. Default: [-0.02, 0.02]
        - tax_range (list): [min_offset, max_offset] for sensitivity. Default: [-0.05, 0.05]
        - include_multiples_comparison (bool): Compare to market multiples. Default: true

        OVERRIDES (optional):
        - current_price (float): Override fetched price
        - shares_outstanding (float): Override share count

    fields : List[str]
        Fields to fetch from FMP - from discover_fields() results.
        Typically: ["operatingIncome", "ebit", "depreciationAndAmortization",
                   "incomeTaxExpense", "incomeBeforeTax", "totalDebt",
                   "cashAndCashEquivalents", "price", "marketCap", "beta"]

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RETURNS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    JSON with:
    - status, symbol
    - normalized_ebit, normalization_details
    - maintenance_capex, capex_details
    - epv_enterprise, equity_epv, epv_per_share
    - current_price, upside_pct, margin_of_safety
    - sensitivity_grid (if requested)
    - multiples_comparison (if requested)
    - methodology_notes (limitations and assumptions)
    """

    if not fields or len(fields) == 0:
        raise ValueError(
            "fields parameter is required. Use discover_fields() first to find available fields."
        )

    market_server = None

    try:
        # Parse parameters
        try:
            params_dict = json.loads(epv_params) if epv_params else {}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in epv_params: {e}")

        normalized_params = _normalize_params(params_dict)
        logger.info(f"EPV for {symbol}: params={list(normalized_params.keys())}")

        # Configuration with defaults
        normalization_years = normalized_params.get("normalization_years", 5)
        normalization_method = normalized_params.get("normalization_method", "average")
        capex_method = normalized_params.get("capex_method", "dna")
        include_sensitivity = normalized_params.get("include_sensitivity", False)
        include_multiples = normalized_params.get("include_multiples_comparison", True)

        # =========================================
        # Fetch Data from FMPMarketDataServer
        # =========================================
        market_server = FMPMarketDataServer()
        await market_server.connect()

        # STEP 1: Run discover_fields FIRST to populate field cache (pattern from gather_dcf_data_tool.py)
        logger.info(f"Running discover_fields for {symbol} before fetching EPV data...")
        discovery_result = await market_server.call_tool("discover_fields", {
            "symbol": symbol,
            "max_datasets": 50,  # Comprehensive discovery
            "period": "annual"
        })

        if discovery_result and not discovery_result.isError:
            discovery_data = safe_parse_json(discovery_result)
            field_count = discovery_data.get("field_count", 0)
            logger.info(f"Discovery complete: {field_count} fields found and cached")
        else:
            logger.warning(f"Discovery failed for {symbol}, will try to fetch anyway")

        # STEP 2: Define fields needed for EPV (don't rely on agent-provided fields for core data)
        # EPV requires: EBIT/operating income history, D&A, debt, cash, shares, price, beta
        epv_core_fields = [
            # Income metrics
            "operatingIncome", "ebit", "netIncome", "revenue",
            # CapEx and D&A
            "depreciationAndAmortization", "capitalExpenditure",
            # Tax data
            "incomeTaxExpense", "incomeBeforeTax",
            # Balance sheet
            "totalDebt", "cashAndCashEquivalents", "cashAndShortTermInvestments",
            # Shares and price
            "outstandingShares", "weightedAverageShsOut",
            "price", "marketCap", "enterpriseValue", "beta"
        ]

        # Merge with agent-provided fields
        all_fields = list(set(epv_core_fields + list(fields)))
        logger.info(f"EPV fetching {len(all_fields)} fields: {all_fields[:8]}...")

        # STEP 3: Fetch current/snapshot data
        current_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": all_fields,
            "params": {"period": "annual", "limit": 1}
        })

        raw_data = {}
        if current_result and not current_result.isError:
            current_data = safe_parse_json(current_result)
            if current_data.get("status") != "missing_required_params":
                raw_data = current_data.get("data", current_data)
                logger.info(f"Current data fetched: {len(raw_data)} fields available")

        # STEP 4: Fetch historical data for normalization (use core fields, not agent-provided)
        hist_fields = [
            "operatingIncome", "ebit", "netIncome", "revenue",
            "depreciationAndAmortization", "capitalExpenditure",
            "incomeTaxExpense", "incomeBeforeTax"
        ]

        historical_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": hist_fields,
            "historical": True,
            "period": "annual",
            "limit": normalization_years
        })

        historical_data = []
        if historical_result and not historical_result.isError:
            hist_parsed = safe_parse_json(historical_result)
            if hist_parsed.get("status") != "missing_required_params":
                hist_data = hist_parsed.get("data", hist_parsed)
                # Handle both list format and dict with "data" key
                if isinstance(hist_data, list):
                    historical_data = hist_data
                elif isinstance(hist_data, dict):
                    # If dict, try to extract list from common keys
                    for key in ["operatingIncome", "ebit", "netIncome"]:
                        if key in hist_data and isinstance(hist_data[key], list):
                            # Convert column format to row format
                            num_years = len(hist_data[key])
                            historical_data = []
                            for i in range(num_years):
                                year_data = {}
                                for field, values in hist_data.items():
                                    if isinstance(values, list) and i < len(values):
                                        year_data[field] = values[i]
                                historical_data.append(year_data)
                            break

        await market_server.cleanup()
        market_server = None

        if not raw_data:
            return json.dumps({
                "error": f"No financial data found for {symbol}. Ensure discover_fields() was called first.",
                "symbol": symbol
            })

        logger.info(f"Retrieved {len(historical_data)} years of history for {symbol}")

        # =========================================
        # Extract Key Metrics
        # =========================================
        price = normalized_params.get("current_price") or raw_data.get("price")
        shares = normalized_params.get("shares_outstanding") or raw_data.get("outstandingShares") or raw_data.get("weightedAverageShsOut")
        market_cap = raw_data.get("marketCap")
        enterprise_value = raw_data.get("enterpriseValue")
        beta = raw_data.get("beta")

        # Net debt
        total_debt = raw_data.get("totalDebt") or 0
        total_cash = raw_data.get("cashAndCashEquivalents") or raw_data.get("cashAndShortTermInvestments") or 0
        net_debt = total_debt - total_cash

        # Tax rate: try to calculate from data
        if "tax_rate" in normalized_params:
            tax_rate = normalized_params["tax_rate"]
        else:
            tax_expense = raw_data.get("incomeTaxExpense")
            pretax_income = raw_data.get("incomeBeforeTax")
            if tax_expense and pretax_income and pretax_income > 0:
                tax_rate = tax_expense / pretax_income
                tax_rate = max(0, min(0.4, tax_rate))  # Bound to reasonable range
            else:
                tax_rate = 0.21  # Default US corporate rate

        # D&A and CapEx for maintenance estimation
        dna = raw_data.get("depreciationAndAmortization")
        capex = raw_data.get("capitalExpenditure")
        revenue = raw_data.get("revenue")
        net_income = raw_data.get("netIncome")

        # Validation
        if price is None:
            return json.dumps({
                "error": f"Missing price for {symbol}. Provide current_price override.",
                "symbol": symbol
            })
        if shares is None or shares <= 0:
            return json.dumps({
                "error": f"Missing shares outstanding for {symbol}.",
                "symbol": symbol
            })

        # =========================================
        # Calculate WACC
        # =========================================
        if "wacc" in normalized_params:
            wacc = normalized_params["wacc"]
            wacc_source = "provided"
        else:
            risk_free = normalized_params.get("risk_free_rate", 0.04)
            mrp = normalized_params.get("market_risk_premium", 0.05)
            wacc = _calculate_wacc(beta, risk_free, mrp)
            wacc_source = f"CAPM (beta={beta}, rf={risk_free:.1%}, mrp={mrp:.1%})"

        # =========================================
        # Normalize EBIT
        # =========================================
        # Extract EBIT history from historical data
        ebit_history = []
        for year_data in historical_data:
            ebit = year_data.get("ebit") or year_data.get("operatingIncome")
            if ebit is not None:
                ebit_history.append(ebit)

        # Fallback to current EBIT if no history
        if len(ebit_history) == 0:
            current_ebit = raw_data.get("ebit") or raw_data.get("operatingIncome")
            if current_ebit:
                ebit_history = [current_ebit]

        normalization_result = _normalize_ebit(ebit_history, normalization_method)

        if normalization_result.get("value") is None:
            return json.dumps({
                "error": f"Could not normalize EBIT: {normalization_result.get('error')}",
                "symbol": symbol,
                "ebit_history": ebit_history
            })

        normalized_ebit = normalization_result["value"]

        # =========================================
        # Estimate Maintenance CapEx
        # =========================================
        capex_result = _estimate_maintenance_capex(
            dna=dna,
            capex=capex,
            revenue=revenue,
            method=capex_method,
            ratio=normalized_params.get("maintenance_capex_ratio")
        )

        maintenance_capex = capex_result.get("value", 0) or 0

        # =========================================
        # Calculate EPV
        # =========================================
        epv_result = _calculate_epv(
            normalized_ebit=normalized_ebit,
            tax_rate=tax_rate,
            wacc=wacc,
            net_debt=net_debt,
            shares=shares
        )

        if "error" in epv_result:
            return json.dumps({
                "error": epv_result["error"],
                "symbol": symbol
            })

        epv_per_share = epv_result["epv_per_share"]

        # =========================================
        # Build Response
        # =========================================
        upside_pct = ((epv_per_share / price) - 1) * 100 if price > 0 else None

        response = {
            "status": "success",
            "symbol": symbol,
            "normalized_ebit": round(normalized_ebit, 0),
            "normalization_details": {
                "method": normalization_result["method"],
                "years_used": normalization_result["years_used"],
                "ebit_values": [round(e, 0) for e in normalization_result.get("ebit_history", [])],
            },
            "maintenance_capex": round(maintenance_capex, 0),
            "capex_details": {
                "method": capex_result["method"],
                "note": capex_result.get("assumption", "D&A used as maintenance CapEx proxy"),
            },
            "tax_rate_used": round(tax_rate, 3),
            "wacc_used": round(wacc, 4),
            "wacc_source": wacc_source,
            "normalized_nopat": round(epv_result["normalized_nopat"], 0),
            "epv_enterprise": round(epv_result["epv_enterprise"], 0),
            "net_debt": round(net_debt, 0),
            "equity_epv": round(epv_result["equity_epv"], 0),
            "shares_outstanding": round(shares, 0),
            "epv_per_share": round(epv_per_share, 2),
            "current_price": round(price, 2),
            "upside_pct": round(upside_pct, 1) if upside_pct else None,
            "margin_of_safety": round(upside_pct, 1) if upside_pct else None,
            "interpretation": (
                "EPV > Price: market may be undervaluing current earnings power"
                if epv_per_share > price
                else "EPV < Price: market is pricing in future growth expectations"
            ),
        }

        # =========================================
        # Sensitivity Grid (optional)
        # =========================================
        if include_sensitivity:
            wacc_range = normalized_params.get("wacc_range", [-0.02, 0.02])
            tax_range = normalized_params.get("tax_range", [-0.05, 0.05])

            sensitivity = _build_sensitivity_grid(
                normalized_ebit=normalized_ebit,
                net_debt=net_debt,
                shares=shares,
                base_wacc=wacc,
                base_tax=tax_rate,
                wacc_range=wacc_range,
                tax_range=tax_range
            )
            response["sensitivity_grid"] = sensitivity

        # =========================================
        # Multiples Comparison (optional)
        # =========================================
        if include_multiples:
            multiples = _calculate_multiples_comparison(
                epv_per_share=epv_per_share,
                current_price=price,
                normalized_ebit=normalized_ebit,
                net_income=net_income,
                shares=shares,
                market_cap=market_cap,
                enterprise_value=enterprise_value
            )
            response["multiples_comparison"] = multiples

        # =========================================
        # Methodology Notes
        # =========================================
        response["methodology_notes"] = [
            f"EBIT normalized using {normalization_result['method']} over {normalization_result['years_used']} years",
            f"Maintenance CapEx estimated via {capex_result['method']} method",
            "EPV assumes zero growth - conservative floor valuation",
            "If EPV > Price, market may be undervaluing earnings power",
            "If EPV < Price, market expects future growth to justify premium",
        ]

        # Include raw financial data for transparency
        response["financial_data"] = {
            "beta": beta,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "dna": dna,
            "capex": capex,
            "revenue": revenue,
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
        }

        logger.info(f"EPV for {symbol}: ${epv_per_share:.2f} vs price ${price:.2f} ({upside_pct:+.1f}%)")
        return json.dumps(response)

    except Exception as e:
        logger.error(f"EPV calculation failed for {symbol}: {e}")
        return json.dumps({
            "error": f"EPV calculation failed: {str(e)}",
            "symbol": symbol
        })

    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass
