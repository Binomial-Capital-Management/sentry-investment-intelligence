"""
Momentum Feature Extraction

Extracts options flow momentum features:
- Call OI changes (5d momentum)
- Vol > OI contracts (unusual activity)
- Hottest strikes
- Flow imbalance
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np

from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


async def extract_momentum_features(
    uw_options,  # UWOptionsServer
    ticker: str,
    lookback_days: int = 60
) -> Optional[Dict[str, Any]]:
    """
    Extract options momentum features from Unusual Whales.
    
    Fetches:
    1. OI changes - Call OI momentum
    2. Vol > OI contracts - Unusual activity
    3. Hottest contracts - Where the action is
    
    Returns:
        Dict with momentum metrics and z-scores
    """
    try:
        import asyncio
        
        # Parallel fetch
        results = await asyncio.gather(
            _fetch_oi_changes(uw_options, ticker),
            _fetch_unusual_activity(uw_options, ticker),
            _fetch_hottest_contracts(uw_options, ticker),
            return_exceptions=True
        )
        
        oi_data = results[0] if not isinstance(results[0], Exception) else None
        unusual_data = results[1] if not isinstance(results[1], Exception) else None
        hottest_data = results[2] if not isinstance(results[2], Exception) else None
        
        if not any([oi_data, unusual_data, hottest_data]):
            logger.warning(f"No momentum data available for {ticker}")
            return None
        
        return {
            "oi_changes": oi_data,
            "unusual_activity": unusual_data,
            "hottest_contracts": hottest_data,
            "summary": _summarize_momentum(oi_data, unusual_data, hottest_data)
        }
    
    except Exception as e:
        logger.error(f"Failed to extract momentum features for {ticker}: {e}")
        return None


async def _fetch_oi_changes(uw_options, ticker: str) -> Optional[Dict]:
    """Fetch open interest changes and flow data."""
    try:
        import asyncio
        
        # Fetch both OI change and flow data in parallel
        oi_task = uw_options.call_tool("uw_oi_change", {"ticker": ticker})
        flow_task = uw_options.call_tool("uw_flow_summary", {"ticker": ticker, "view": "expiry"})
        
        results = await asyncio.gather(oi_task, flow_task, return_exceptions=True)
        
        oi_result = results[0] if not isinstance(results[0], Exception) else None
        flow_result = results[1] if not isinstance(results[1], Exception) else None
        
        oi_data = None
        flow_data = None
        
        if oi_result and hasattr(oi_result, 'content'):
            oi_data = safe_parse_json(oi_result)
        
        if flow_result and hasattr(flow_result, 'content'):
            flow_data = safe_parse_json(flow_result)
        
        # Parse OI change data
        parsed = _parse_oi_changes(oi_data) if oi_data else {}
        
        # Supplement with flow data (more reliable for call/put volume)
        if flow_data:
            flow_parsed = _parse_flow_per_expiry(flow_data)
            if flow_parsed:
                # Use flow data as primary if OI change is 0
                if parsed.get("call_oi_change", 0) == 0:
                    parsed["call_volume"] = flow_parsed.get("call_volume", 0)
                    parsed["put_volume"] = flow_parsed.get("put_volume", 0)
                    parsed["call_premium"] = flow_parsed.get("call_premium", 0)
                    parsed["put_premium"] = flow_parsed.get("put_premium", 0)
                    # Use volume as proxy for positioning momentum
                    parsed["call_oi_change"] = flow_parsed.get("call_volume", 0)
                    parsed["put_oi_change"] = flow_parsed.get("put_volume", 0)
                    parsed["net_oi_change"] = parsed["call_oi_change"] - parsed["put_oi_change"]
                    logger.info(f"[OI_CHANGE] Using flow data: call_vol={parsed['call_oi_change']}, put_vol={parsed['put_oi_change']}")
        
        return parsed if parsed else {"call_oi_change": 0, "put_oi_change": 0, "net_oi_change": 0}
    
    except Exception as e:
        logger.warning(f"Failed to fetch OI changes: {e}")
        return None


def _parse_flow_per_expiry(data: Any) -> Optional[Dict]:
    """Parse flow-per-expiry data for call/put totals."""
    try:
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("data", [])
        
        if not records:
            return None
        
        call_volume = 0
        put_volume = 0
        call_premium = 0
        put_premium = 0
        
        for rec in records:
            if not isinstance(rec, dict):
                continue
            call_volume += _find_numeric(rec, ["call_volume", "callVolume", "calls_volume"]) or 0
            put_volume += _find_numeric(rec, ["put_volume", "putVolume", "puts_volume"]) or 0
            call_premium += _find_numeric(rec, ["call_premium", "callPremium", "calls_premium"]) or 0
            put_premium += _find_numeric(rec, ["put_premium", "putPremium", "puts_premium"]) or 0
        
        return {
            "call_volume": call_volume,
            "put_volume": put_volume,
            "call_premium": call_premium,
            "put_premium": put_premium
        }
    except Exception as e:
        logger.warning(f"Failed to parse flow data: {e}")
        return None


async def _fetch_unusual_activity(uw_options, ticker: str) -> Optional[Dict]:
    """Fetch contracts where volume > open interest."""
    try:
        result = await uw_options.call_tool("uw_option_chain", {
            "ticker": ticker,
            "view": "contracts",
            "vol_greater_oi": True
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        return _parse_unusual_activity(data)
    
    except Exception as e:
        logger.warning(f"Failed to fetch unusual activity: {e}")
        return None


async def _fetch_hottest_contracts(uw_options, ticker: str) -> Optional[Dict]:
    """Fetch hottest contracts by volume."""
    try:
        result = await uw_options.call_tool("uw_hottest_contracts", {
            "ticker": ticker,
            "limit": 20
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        return _parse_hottest_contracts(data)
    
    except Exception as e:
        logger.warning(f"Failed to fetch hottest contracts: {e}")
        return None


def _parse_oi_changes(data: Any) -> Dict:
    """Parse OI change data into structured format."""
    contracts = []
    
    if isinstance(data, list):
        contracts = data
    elif isinstance(data, dict):
        contracts = data.get("data", data.get("contracts", []))
    
    if not contracts:
        logger.warning(f"[OI_CHANGE] No contracts in data: {type(data)}")
        return {"call_oi_change": 0, "put_oi_change": 0, "net_oi_change": 0}
    
    call_oi_change = 0
    put_oi_change = 0
    
    oi_change_fields = ["oi_change", "oiChange", "open_interest_change", "oi_diff", "oi_diff_plain"]
    option_type_fields = ["option_type", "type", "optionType", "side", "contract_type"]
    symbol_fields = ["option_symbol", "symbol", "contract", "contractSymbol"]
    
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        
        oi_change = _find_numeric(contract, oi_change_fields)
        if oi_change is None:
            continue
        
        # Try direct option_type field first
        option_type = _find_string(contract, option_type_fields)
        
        # If no option_type, extract from option_symbol (e.g., "AAPL241220C00250000")
        if not option_type:
            symbol = _find_string(contract, symbol_fields)
            if symbol:
                option_type = _extract_option_type_from_symbol(symbol)
        
        if option_type and option_type.lower() in ["call", "c"]:
            call_oi_change += oi_change
        elif option_type and option_type.lower() in ["put", "p"]:
            put_oi_change += oi_change
    
    logger.info(f"[OI_CHANGE] Parsed: call={call_oi_change}, put={put_oi_change}")
    
    return {
        "call_oi_change": call_oi_change,
        "put_oi_change": put_oi_change,
        "net_oi_change": call_oi_change + put_oi_change,
        "call_put_oi_ratio": call_oi_change / abs(put_oi_change) if put_oi_change != 0 else float('inf')
    }


def _extract_option_type_from_symbol(symbol: str) -> Optional[str]:
    """Extract call/put type from OCC option symbol format.
    
    OCC format: AAPL241220C00250000
    - Ticker (variable length)
    - Date YYMMDD (6 chars)  
    - Type C/P (1 char)
    - Strike (8 chars, price * 1000)
    """
    if not symbol or len(symbol) < 15:
        return None
    
    # Find C or P in the symbol (typically after date, before strike)
    # Look for C or P followed by digits (the strike)
    import re
    match = re.search(r'(\d{6})([CP])(\d{8})', symbol.upper())
    if match:
        return "call" if match.group(2) == "C" else "put"
    
    # Fallback: just look for C or P anywhere
    if "C" in symbol.upper() and "P" not in symbol.upper():
        return "call"
    elif "P" in symbol.upper() and "C" not in symbol.upper():
        return "put"
    
    return None


def _parse_unusual_activity(data: Any) -> Dict:
    """Parse vol>OI contracts."""
    contracts = []
    
    if isinstance(data, list):
        contracts = data
    elif isinstance(data, dict):
        contracts = data.get("data", data.get("contracts", []))
    
    vol_greater_oi_count = len(contracts)
    
    call_count = 0
    put_count = 0
    strikes = []
    
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        
        option_type = _find_string(contract, ["option_type", "type", "optionType"])
        strike = _find_numeric(contract, ["strike", "strike_price"])
        
        if option_type and option_type.lower() in ["call", "c"]:
            call_count += 1
        elif option_type and option_type.lower() in ["put", "p"]:
            put_count += 1
        
        if strike:
            strikes.append(strike)
    
    return {
        "vol_greater_oi_count": vol_greater_oi_count,
        "vol_greater_oi_calls": call_count,
        "vol_greater_oi_puts": put_count,
        "unusual_strikes": sorted(set(strikes)) if strikes else []
    }


def _parse_hottest_contracts(data: Any) -> Dict:
    """Parse hottest contracts data."""
    contracts = []
    
    if isinstance(data, list):
        contracts = data
    elif isinstance(data, dict):
        contracts = data.get("data", data.get("contracts", []))
    
    if not contracts:
        return {"hottest_strikes": [], "hottest_call_strike": None}
    
    strikes = []
    call_volumes = {}
    
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        
        strike = _find_numeric(contract, ["strike", "strike_price"])
        volume = _find_numeric(contract, ["volume", "vol", "total_volume"])
        option_type = _find_string(contract, ["option_type", "type", "optionType"])
        
        if strike:
            strikes.append(strike)
            if option_type and option_type.lower() in ["call", "c"] and volume:
                call_volumes[strike] = call_volumes.get(strike, 0) + volume
    
    # Find hottest call strike
    hottest_call_strike = max(call_volumes.items(), key=lambda x: x[1])[0] if call_volumes else None
    
    return {
        "hottest_strikes": sorted(set(strikes))[:10],
        "hottest_call_strike": hottest_call_strike,
        "contract_count": len(contracts)
    }


def _summarize_momentum(
    oi_data: Optional[Dict],
    unusual_data: Optional[Dict],
    hottest_data: Optional[Dict]
) -> Dict:
    """Create summary metrics from momentum data."""
    summary = {}
    
    if oi_data:
        summary["call_oi_momentum"] = oi_data.get("call_oi_change", 0)
        summary["oi_bullish"] = oi_data.get("call_oi_change", 0) > abs(oi_data.get("put_oi_change", 0))
    
    if unusual_data:
        summary["unusual_activity_count"] = unusual_data.get("vol_greater_oi_count", 0)
        summary["unusual_call_bias"] = (
            unusual_data.get("vol_greater_oi_calls", 0) > 
            unusual_data.get("vol_greater_oi_puts", 0)
        )
    
    if hottest_data:
        summary["hottest_strike"] = hottest_data.get("hottest_call_strike")
    
    return summary


def _find_numeric(item: Dict, candidates: List[str]) -> Optional[float]:
    """Find first matching numeric field."""
    for field in candidates:
        if field in item and item[field] is not None:
            try:
                return float(item[field])
            except (ValueError, TypeError):
                continue
    return None


def _find_string(item: Dict, candidates: List[str]) -> Optional[str]:
    """Find first matching string field."""
    for field in candidates:
        if field in item and item[field] is not None:
            return str(item[field])
    return None

