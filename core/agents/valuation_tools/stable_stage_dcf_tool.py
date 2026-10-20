"""
Stable-Stage DCF Execution Tool (EPS/FCFE-first)
Status: Production (lightweight)
Created: October 2025

PURPOSE
- Prepare a single-stage (steady-state) FCFE DCF envelope for companies already operating at
  terminal characteristics (minimal explicit growth runway).
- Assumes the agent has already gathered historical/analyst context and now needs a compact
  payload for Code Interpreter to run the FCFE projection.

EXPECTED INPUT (JSON string):
{
  "stage": {"years": 1, "eps_growth": 0.04},
  "fcfe_margins": {
      "capex_ratio": 0.07,
      "depreciation_ratio": 0.07,
      "nwc_intensity": 0.00,
      "tax_rate": 0.20
  },
  "terminal": {"growth": 0.02},
  "discount": {"cost_of_equity": 0.085, "wacc": 0.08},
  "shares_policy": "allow_dilution"
}

STAGE YEARS INTERPRETATION
- years = 0: Use TTM metrics directly as terminal baseline (no explicit projection phase)
- years = 1: Project 1 year at eps_growth, then jump to terminal (typical for stable-stage)
- years = 2: Project 2 years at eps_growth, then terminal (rare, for borderline cases)

NOTES
- Stage.years can be 0–2 depending on analyst judgement (default to 1 when absent).
- discount may either have top-level `cost_of_equity`/`wacc` keys or a nested `discount` block.
- Returns a payload identical in spirit to three-stage/two-stage tools; Code Interpreter must
  still perform the DCF math and produce the Excel artifact.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


def _normalize_assumptions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy keys into the stable-stage schema."""
    normalized = dict(data)

    # Allow top-level discount keys or nested dict
    if isinstance(normalized.get("wacc"), (int, float)) or isinstance(normalized.get("cost_of_equity"), (int, float)):
        discount_block = normalized.setdefault("discount", {})
        if "cost_of_equity" in normalized:
            discount_block.setdefault("cost_of_equity", float(normalized["cost_of_equity"]))
        if "wacc" in normalized:
            discount_block.setdefault("wacc", float(normalized["wacc"]))

    def _norm_stage(stage: Dict[str, Any]) -> Dict[str, Any]:
        s = dict(stage)
        if "eps_growth" not in s:
            for key in ("growth_rate", "revenue_growth", "ni_growth"):
                if key in s:
                    s["eps_growth"] = s.pop(key)
                    break
        if "years" not in s and "duration" in s:
            s["years"] = s.pop("duration")
        try:
            s["years"] = int(s.get("years", 1))
        except Exception:
            s["years"] = 1
        return s

    def _norm_fcfe_margins(margins: Dict[str, Any]) -> Dict[str, Any]:
        m = dict(margins)
        mapping = {
            "capex_to_revenue": "capex_ratio",
            "depreciation_to_revenue": "depreciation_ratio",
            "nwc_to_revenue": "nwc_intensity",
            "delta_nwc_to_delta_revenue": "nwc_intensity",
            "tax": "tax_rate",
        }
        for old, new in mapping.items():
            if old in m and new not in m:
                m[new] = m.pop(old)
        return m

    if "stage" in normalized:
        normalized["stage"] = _norm_stage(normalized["stage"])
    if "fcfe_margins" in normalized:
        normalized["fcfe_margins"] = _norm_fcfe_margins(normalized["fcfe_margins"])
    if "terminal" in normalized and isinstance(normalized["terminal"], dict):
        term = dict(normalized["terminal"])
        if "growth_rate" in term and "growth" not in term:
            term["growth"] = term.pop("growth_rate")
        normalized["terminal"] = term

    return normalized


def _validate_assumptions(data: Dict[str, Any]) -> None:
    """Ensure minimal schema is present."""
    if "stage" not in data:
        raise ValueError("Stable-stage DCF requires a 'stage' block with eps_growth/years.")
    if "fcfe_margins" not in data:
        raise ValueError("Stable-stage DCF requires 'fcfe_margins' (capex_ratio, depreciation_ratio, nwc_intensity, tax_rate).")
    if "terminal" not in data or "growth" not in data["terminal"]:
        raise ValueError("Stable-stage DCF requires terminal growth (terminal.growth).")

    discount = data.get("discount", {})
    has_ke = "cost_of_equity" in discount
    has_wacc = "wacc" in discount
    if not (has_ke or has_wacc):
        raise ValueError("Stable-stage DCF requires cost_of_equity or wacc inside 'discount'.")

    # fcfe_margins completeness
    margins = data["fcfe_margins"]
    for key in ("capex_ratio", "depreciation_ratio", "nwc_intensity", "tax_rate"):
        if key not in margins:
            raise ValueError(f"Missing '{key}' inside fcfe_margins.")


STANDARD_FIELDS: List[str] = [
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


@function_tool
async def analyze_stable_stage_dcf(
    symbol: str,
    dcf_data: str,
    fields: Optional[List[str]] = None
) -> str:
    """
    Prepare a stable/steady-state FCFE DCF envelope with TTM baseline metrics.
    Agent must still run the projection and produce outputs in Code Interpreter.
    """
    if not dcf_data:
        raise ValueError("Stable-stage DCF requires agent-provided assumptions JSON.")

    market_server = None
    try:
        assumptions = json.loads(dcf_data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in dcf_data: {exc}") from exc

    assumptions = _normalize_assumptions(assumptions)
    _validate_assumptions(assumptions)

    field_list = STANDARD_FIELDS.copy()
    if fields:
        field_list.extend(fields)

    try:
        market_server = FMPMarketDataServer()
        await market_server.connect()

        logger.info("Stable-stage DCF: fetching %d FMP fields for %s", len(field_list), symbol)
        result = await market_server.call_tool("get_fields", {"symbol": symbol, "fields": field_list})
        if not result or not hasattr(result, "content"):
            return json.dumps({
                "error": f"No financial data found for {symbol}",
                "symbol": symbol,
                "fmp_fields_attempted": field_list
            })

        raw_payload = safe_parse_json(result)
        if "metadata" in raw_payload:
            meta = raw_payload["metadata"]
            logger.info(
                "Stable-stage DCF baseline fetch: %s API calls, cache_used=%s",
                meta.get("api_calls", 0),
                meta.get("cache_used", False),
            )

        raw_data = raw_payload.get("data", raw_payload)
        semantic = {
            "shares": raw_data.get("outstandingShares"),
            "diluted_shares": raw_data.get("dilutedSharesOutstanding"),
            "price": raw_data.get("price"),
            "ttm_eps": raw_data.get("eps"),
            "ttm_eps_diluted": raw_data.get("epsDiluted"),
            "net_income": raw_data.get("netIncome"),
            "revenue": raw_data.get("revenue"),
            "market_cap": raw_data.get("marketCap"),
            "total_debt": raw_data.get("totalDebt"),
            "total_cash": raw_data.get("cashAndCashEquivalents"),
            "depreciation_and_amortization": raw_data.get("depreciationAndAmortization"),
            "capital_expenditure": raw_data.get("capitalExpenditure"),
            "change_in_working_capital": raw_data.get("changeInWorkingCapital"),
        }

        if fields:
            for field in fields:
                if field in raw_data:
                    semantic[field] = raw_data[field]

        semantic = {k: v for k, v in semantic.items() if v is not None}

        # Baseline presence checks
        if semantic.get("ttm_eps") is None and semantic.get("net_income") is None:
            raise ValueError(
                f"Missing EPS/Net income anchors for {symbol}. FMP data received: {list(raw_data.keys())}"
            )

        # Calculate net debt if agent didn't specify
        if "net_debt" not in assumptions:
            total_debt = semantic.get("total_debt")
            total_cash = semantic.get("total_cash")
            market_cap = semantic.get("market_cap")
            if isinstance(total_debt, (int, float)) and isinstance(total_cash, (int, float)):
                net_debt = float(total_debt) - float(total_cash)
                if isinstance(market_cap, (int, float)) and abs(net_debt) > 1.5 * float(market_cap):
                    logger.warning(
                        "Stable-stage DCF: net_debt=%s vs market_cap=%s for %s; setting net_debt=0",
                        f"{net_debt:,.0f}",
                        f"{market_cap:,.0f}" if market_cap is not None else "n/a",
                        symbol,
                    )
                    assumptions["net_debt"] = 0.0
                else:
                    assumptions["net_debt"] = net_debt
            else:
                logger.warning("Stable-stage DCF: debt/cash not numeric for %s; defaulting net_debt=0", symbol)
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
                "Stable-stage FCFE: treat Stage 1 as steady-state, discount at cost_of_equity; "
                "run the FCFE projection and Excel build in Code Interpreter."
            ),
        }

        logger.info("Stable-stage DCF envelope prepared for %s", symbol)
        return json.dumps(payload)

    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in dcf_data: {exc}") from exc
    except Exception as exc:
        logger.error("Error in Stable-stage DCF analysis for %s: %s", symbol, exc)
        return json.dumps({
            "error": f"Stable-stage DCF preparation failed: {exc}",
            "symbol": symbol,
            "dcf_data": dcf_data
        })
    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass
