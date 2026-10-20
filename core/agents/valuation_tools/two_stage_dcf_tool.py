"""
Two-Stage FCFE DCF Execution Tool
Status: Production (lightweight)
Created: October 2025

PURPOSE
- Prepares the data envelope for a two-stage EPS→FCFE discounted cash-flow model.
- Stage 1 uses explicit EPS growth + reinvestment assumptions; Stage 2 jumps directly to terminal.
- All projections, discounting, and sensitivities run inside Code Interpreter; this tool only fetches
baseline TTM metrics and validates the agent's assumptions.

BASELINE REQUIREMENTS (TTM FIELDS WE FETCH)
- Shares: outstandingShares (primary) and dilutedSharesOutstanding for share-policy decisions
- Per-share anchors: eps, epsDiluted, netIncome
- Price context: price, marketCap
- Balance sheet: totalDebt, cashAndCashEquivalents (reused for net debt plausibility guard)
- Reinvestment signals: depreciationAndAmortization, capitalExpenditure, changeInWorkingCapital
- Revenue is fetched for context when analysts still cite it; EPS drives FCFE

AGENT RESPONSIBILITIES
1. Discover available fields with `discover_fields` / `discover_dcf_fields`.
2. Gather historical + analyst data via `gather_dcf_data_sources`.
3. Formulate stage 1 EPS growth, CapEx/D&A/NWC ratios, taxes, and terminal growth under the EPS/FCFE
framing.
4. Provide cost_of_equity (and optional WACC) in `dcf_data`.
5. Call this tool with the finalized assumption JSON.

RETURN SHAPE
{
  "status": "data_ready_for_calculation",
  "symbol": "AAPL",
  "data_source": "fmp_ttm",
  "financial_data": {
    "shares": 15772600000,
    "diluted_shares": 15841300000,
    "price": 187.44,
    "ttm_eps": 6.42,
    "ttm_eps_diluted": 6.25,
    "net_income": 15400000000,
    "revenue": 86400000000,
    "market_cap": 450000000000,
    "total_debt": 109000000000,
    "total_cash": 62000000000,
    "depreciation_and_amortization": 11200000000,
    "capital_expenditure": 10800000000,
    "change_in_working_capital": -1600000000,
    "net_debt": 47000000000
  },
  "agent_assumptions": {...},
  "instruction": "Two-stage FCFE: project stage1 EPS→FCFE, drop directly to terminal. Build spreadsheet per <excel-format>, keep sensitivity grid tight."
}

NOTES
- No fallback assumptions; missing anchors raise immediately.
- Revenue forecast is out of scope; EPS is the primary driver.
- Net debt guardrail zeroes implausible values (>1.5× market cap).
- Agents can request extra FMP fields via the optional `fields` parameter.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


@function_tool
async def analyze_two_stage_dcf(
    symbol: str,
    dcf_data: str,                  # Agent-formulated two-stage assumptions (JSON string)
    fields: Optional[List[str]] = None
) -> str:
    """
    Prepare a two-stage DCF calculation envelope (FCFE-first) with TTM baseline.

    Validation:
    - Requires stage1 and terminal blocks
    - Requires a discount rate: either top-level cost_of_equity/wacc or discount.{cost_of_equity|wacc}
    - Tolerates extra fields; passes them through untouched.
    """

    if not dcf_data:
        raise ValueError("Two-stage DCF requires agent-provided assumptions JSON")

    # Normalize inputs to the two-stage FCFE schema
    def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data)
        # Permit older variants by mapping common keys
        if "terminal" in d and isinstance(d["terminal"], dict):
            t = dict(d["terminal"])
            if "growth_rate" in t and "growth" not in t:
                t["growth"] = t.pop("growth_rate")
            if "capex_to_revenue" in t and "capex_ratio" not in t:
                t["capex_ratio"] = t.pop("capex_to_revenue")
            if "nwc_to_revenue" in t and "nwc_intensity" not in t:
                t["nwc_intensity"] = t.pop("nwc_to_revenue")
            d["terminal"] = t
        if "stage1" in d and isinstance(d["stage1"], dict):
            s1 = dict(d["stage1"])
            if "growth_rate" in s1 and "eps_growth" not in s1:
                s1["eps_growth"] = s1.pop("growth_rate")
            if "capex_to_revenue" in s1 and "capex_ratio" not in s1:
                s1["capex_ratio"] = s1.pop("capex_to_revenue")
            if "nwc_to_revenue" in s1 and "nwc_intensity" not in s1:
                s1["nwc_intensity"] = s1.pop("nwc_to_revenue")
            d["stage1"] = s1
        return d

    market_server = None
    try:
        assumptions = json.loads(dcf_data)
        assumptions = _normalize(assumptions)

        # Required blocks
        for blk in ("stage1", "terminal"):
            if blk not in assumptions:
                raise ValueError(f"Missing required block: {blk}")

        # Discount presence: accept top-level or nested under 'discount'
        has_ke = "cost_of_equity" in assumptions
        has_wacc = "wacc" in assumptions
        has_discount = isinstance(assumptions.get("discount"), dict) and (
            "cost_of_equity" in assumptions["discount"] or "wacc" in assumptions["discount"]
        )
        if not (has_ke or has_wacc or has_discount):
            raise ValueError(
                "Missing discount rate: provide 'cost_of_equity' (FCFE) or a 'discount' block"
            )

        # Baseline fields for EPS/FCFE (matches three-stage tool)
        STANDARD_FIELDS = [
            "outstandingShares",
            "dilutedSharesOutstanding",
            "price",
            "eps",
            "epsDiluted",
            "netIncome",
            "revenue",
            "totalDebt",
            "cashAndCashEquivalents",
            "marketCap",
            "depreciationAndAmortization",
            "capitalExpenditure",
            "changeInWorkingCapital",
        ]
        fmp_fields = STANDARD_FIELDS.copy()
        if fields:
            fmp_fields.extend(fields)

        # Fetch TTM baseline via Market server
        market_server = FMPMarketDataServer()
        await market_server.connect()
        result = await market_server.call_tool("get_fields", {"symbol": symbol, "fields": fmp_fields})
        if not result or not hasattr(result, "content"):
            return json.dumps({"error": f"No financial data found for {symbol}", "symbol": symbol})

        raw = safe_parse_json(result)
        if "data" in raw:
            raw = raw["data"]

        # Map to semantic keys
        semantic = {
            "shares": raw.get("outstandingShares"),
            "diluted_shares": raw.get("dilutedSharesOutstanding"),
            "price": raw.get("price"),
            "ttm_eps": raw.get("eps"),
            "ttm_eps_diluted": raw.get("epsDiluted"),
            "net_income": raw.get("netIncome"),
            "revenue": raw.get("revenue"),
            "market_cap": raw.get("marketCap"),
            "total_debt": raw.get("totalDebt"),
            "total_cash": raw.get("cashAndCashEquivalents"),
            "depreciation_and_amortization": raw.get("depreciationAndAmortization"),
            "capital_expenditure": raw.get("capitalExpenditure"),
            "change_in_working_capital": raw.get("changeInWorkingCapital"),
        }
        if fields:
            for f in fields:
                if f in raw:
                    semantic[f] = raw[f]

        # Validate required fields for EPS/FCFE
        if semantic.get("ttm_eps") is None and semantic.get("net_income") is None:
            raise ValueError(f"Missing EPS/Net Income anchors for {symbol}. FMP data: {list(raw.keys())}")

        # Compute net_debt with plausibility guard (same policy as three-stage)
        if semantic.get("total_debt") is not None and semantic.get("total_cash") is not None:
            td = semantic.get("total_debt")
            tc = semantic.get("total_cash")
            mc = semantic.get("market_cap")
            if isinstance(td, (int, float)) and isinstance(tc, (int, float)):
                net_debt = float(td) - float(tc)
                if "net_debt" in assumptions:
                    logger.info("two_stage: agent provided net_debt; keeping agent value")
                else:
                    if isinstance(mc, (int, float)) and abs(net_debt) > 1.5 * float(mc):
                        logger.warning(
                            f"two_stage: implausible net_debt for {symbol}: {net_debt:,.0f} vs MC {mc:,.0f}; setting 0"
                        )
                        assumptions["net_debt"] = 0.0
                    else:
                        assumptions["net_debt"] = net_debt
            else:
                if "net_debt" not in assumptions:
                    assumptions["net_debt"] = 0.0
        else:
            if "net_debt" not in assumptions:
                assumptions["net_debt"] = 0.0

        payload = {
            "status": "data_ready_for_calculation",
            "symbol": symbol,
            "data_source": "fmp_ttm",
            "financial_data": {
                "shares": semantic.get("shares"),
                "diluted_shares": semantic.get("diluted_shares"),
                "price": semantic.get("price"),
                "ttm_eps": semantic.get("ttm_eps"),
                "ttm_eps_diluted": semantic.get("ttm_eps_diluted"),
                "net_income": semantic.get("net_income"),
                "revenue": semantic.get("revenue"),
                "market_cap": semantic.get("market_cap"),
                "total_debt": semantic.get("total_debt"),
                "total_cash": semantic.get("total_cash"),
                "depreciation_and_amortization": semantic.get("depreciation_and_amortization"),
                "capital_expenditure": semantic.get("capital_expenditure"),
                "change_in_working_capital": semantic.get("change_in_working_capital"),
                "net_debt": assumptions.get("net_debt"),
            },
            "agent_assumptions": assumptions,
            "instruction": (
                "Two-stage FCFE: project stage1 (EPS→FCFE), terminal with k_e & g; "
                "style Excel per <excel-format> and keep sensitivity small."
            ),
        }

        logger.info(f"Two-Stage DCF envelope prepared for {symbol}")
        return json.dumps(payload)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dcf_data: {e}")
    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass
