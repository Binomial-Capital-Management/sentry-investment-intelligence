"""
Gamma Feature Extraction

Extracts dealer gamma positioning features:
- GEX by strike structure
- Put wall, call wall levels
- Zero gamma point
- Gamma ramp start (trigger level)
- Proximity to trigger
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np

from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


async def extract_gamma_features(
    uw_options,  # UWOptionsServer
    ticker: str
) -> Optional[Dict[str, Any]]:
    """
    Extract gamma structure features from Unusual Whales GEX data.
    
    Returns:
        Dict with:
        - gex_by_strike: Raw GEX data per strike
        - put_wall: Highest negative GEX strike (support)
        - call_wall: Highest positive GEX strike (resistance)
        - zero_gamma: Strike where GEX flips sign
        - max_gamma: Strike with maximum absolute GEX
        - gamma_ramp: Strike where gamma acceleration begins
        - total_gex: Net gamma exposure
        - regime: "positive" | "negative" | "neutral"
    """
    try:
        # Fetch GEX by strike
        result = await uw_options.call_tool("uw_gex", {
            "ticker": ticker,
            "view": "by_strike"
        })
        
        if not result or not hasattr(result, 'content'):
            logger.warning(f"No GEX data for {ticker}")
            return None
        
        data = safe_parse_json(result)
        if not data:
            logger.warning(f"[GAMMA] Failed to parse GEX response for {ticker}")
            return None
        
        # Log raw data structure for debugging
        if isinstance(data, dict):
            logger.debug(f"[GAMMA] GEX data keys for {ticker}: {list(data.keys())[:10]}")
            if "data" in data and isinstance(data["data"], list) and data["data"]:
                logger.debug(f"[GAMMA] Sample row keys: {list(data['data'][0].keys()) if data['data'] else 'empty'}")
        elif isinstance(data, list) and data:
            logger.debug(f"[GAMMA] GEX list with {len(data)} items, sample keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
        
        # Handle different data structures
        gex_data = _extract_gex_list(data)
        if not gex_data or len(gex_data) < 3:
            logger.warning(f"[GAMMA] Insufficient GEX data for {ticker}: extracted {len(gex_data) if gex_data else 0} strikes")
            return None
        
        logger.info(f"[GAMMA] Extracted {len(gex_data)} strikes for {ticker}")
        
        # Calculate key levels
        key_levels = _calculate_key_levels(gex_data)
        
        # Calculate total GEX and regime
        total_gex = sum(item.get("gex", 0) for item in gex_data)
        
        if total_gex > 0:
            regime = "positive"  # Dealers short gamma → buy dips, sell rips
        elif total_gex < 0:
            regime = "negative"  # Dealers long gamma → chase momentum
        else:
            regime = "neutral"
        
        return {
            "gex_by_strike": gex_data,
            "key_levels": key_levels,
            "total_gex": total_gex,
            "regime": regime,
            "gex_concentration": _calculate_gex_concentration(gex_data),
            "strike_count": len(gex_data)
        }
    
    except Exception as e:
        logger.error(f"Failed to extract gamma features for {ticker}: {e}")
        return None


def _extract_gex_list(data: Any) -> List[Dict]:
    """
    Extract GEX data as list of {strike, gex, call_gex, put_gex} dicts.
    
    UW API returns call_gamma and put_gamma separately.
    Net GEX = call_gamma - put_gamma (dealer perspective):
    - Positive call_gamma: dealers short calls → buy stock as price rises
    - Negative put_gamma: dealers short puts → buy stock as price falls
    """
    if isinstance(data, list):
        result = []
        for item in data:
            if isinstance(item, dict):
                strike = _find_field(item, ["strike", "strike_price", "Strike"])
                if strike is None:
                    continue
                
                # Try to get net GEX directly
                gex = _find_field(item, ["gex", "gamma_exposure", "GEX", "gammaExposure", "net_gamma", "total_gex"])
                
                # If not available, compute from call_gamma and put_gamma
                if gex is None:
                    call_gamma = _find_field(item, ["call_gamma", "call_gex", "callGamma"])
                    put_gamma = _find_field(item, ["put_gamma", "put_gex", "putGamma"])
                    
                    if call_gamma is not None or put_gamma is not None:
                        call_gamma = call_gamma or 0.0
                        put_gamma = put_gamma or 0.0
                        # Net GEX: dealer hedging flow
                        # call_gamma is positive (dealers short calls → buy shares when price rises)
                        # put_gamma is typically negative (dealers short puts → buy shares when price falls)
                        gex = call_gamma + put_gamma  # Both contribute to directional flow
                
                if gex is not None:
                    record = {
                        "strike": float(strike),
                        "gex": float(gex)
                    }
                    # Store components if available for analysis
                    call_g = _find_field(item, ["call_gamma", "call_gex", "callGamma"])
                    put_g = _find_field(item, ["put_gamma", "put_gex", "putGamma"])
                    if call_g is not None:
                        record["call_gex"] = float(call_g)
                    if put_g is not None:
                        record["put_gex"] = float(put_g)
                    result.append(record)
        
        return result
    
    elif isinstance(data, dict):
        # Check for nested data
        if "data" in data:
            return _extract_gex_list(data["data"])
        if "gex" in data and isinstance(data["gex"], list):
            return _extract_gex_list(data["gex"])
        if "strikes" in data and isinstance(data["strikes"], list):
            return _extract_gex_list(data["strikes"])
        
        # Maybe it's strike -> gex mapping
        result = []
        for key, val in data.items():
            try:
                strike = float(key)
                if isinstance(val, (int, float)):
                    gex = float(val)
                elif isinstance(val, dict):
                    gex = _find_field(val, ["gex", "gamma", "call_gamma", "net_gamma"])
                    if gex is None:
                        call_g = _find_field(val, ["call_gamma", "call_gex"])
                        put_g = _find_field(val, ["put_gamma", "put_gex"])
                        if call_g is not None or put_g is not None:
                            gex = (call_g or 0.0) + (put_g or 0.0)
                else:
                    continue
                if gex is not None:
                    result.append({"strike": strike, "gex": gex})
            except (ValueError, TypeError, AttributeError):
                continue
        return result
    
    return []


def _find_field(item: Dict, candidates: List[str]) -> Optional[float]:
    """Find first matching field from candidates (case-insensitive)."""
    # Try exact match first
    for field in candidates:
        if field in item and item[field] is not None:
            try:
                return float(item[field])
            except (ValueError, TypeError):
                continue
    
    # Try case-insensitive match
    lower_item = {k.lower(): v for k, v in item.items()}
    for field in candidates:
        if field.lower() in lower_item and lower_item[field.lower()] is not None:
            try:
                return float(lower_item[field.lower()])
            except (ValueError, TypeError):
                continue
    
    return None


def _calculate_key_levels(gex_data: List[Dict]) -> Dict[str, Optional[float]]:
    """
    Calculate key gamma levels from GEX by strike data.
    
    - put_wall: Largest negative GEX (dealer put selling = support)
    - call_wall: Largest positive GEX (dealer call selling = resistance)
    - zero_gamma: Where GEX crosses zero
    - max_gamma: Strike with maximum absolute GEX
    - gamma_ramp: First strike above spot with significant positive GEX
    """
    if not gex_data:
        return {}
    
    # Sort by strike
    sorted_gex = sorted(gex_data, key=lambda x: x["strike"])
    
    # Find put wall (max negative GEX)
    negative_gex = [g for g in sorted_gex if g["gex"] < 0]
    put_wall = min(negative_gex, key=lambda x: x["gex"])["strike"] if negative_gex else None
    
    # Find call wall (max positive GEX)
    positive_gex = [g for g in sorted_gex if g["gex"] > 0]
    call_wall = max(positive_gex, key=lambda x: x["gex"])["strike"] if positive_gex else None
    
    # Find zero gamma (where sign flips)
    zero_gamma = None
    for i in range(len(sorted_gex) - 1):
        curr_gex = sorted_gex[i]["gex"]
        next_gex = sorted_gex[i + 1]["gex"]
        if curr_gex * next_gex < 0:  # Sign change
            # Linear interpolation
            curr_strike = sorted_gex[i]["strike"]
            next_strike = sorted_gex[i + 1]["strike"]
            ratio = abs(curr_gex) / (abs(curr_gex) + abs(next_gex))
            zero_gamma = curr_strike + ratio * (next_strike - curr_strike)
            break
    
    # Find max gamma (highest absolute)
    max_gamma_item = max(sorted_gex, key=lambda x: abs(x["gex"]))
    max_gamma = max_gamma_item["strike"]
    
    # Find gamma ramp start (first significant positive GEX cluster)
    gamma_ramp = _find_gamma_ramp(sorted_gex)
    
    return {
        "put_wall": round(put_wall, 2) if put_wall else None,
        "call_wall": round(call_wall, 2) if call_wall else None,
        "zero_gamma": round(zero_gamma, 2) if zero_gamma else None,
        "max_gamma": round(max_gamma, 2) if max_gamma else None,
        "gamma_ramp": round(gamma_ramp, 2) if gamma_ramp else None
    }


def _find_gamma_ramp(sorted_gex: List[Dict]) -> Optional[float]:
    """
    Find where gamma ramp starts - first cluster of high positive GEX.
    
    A gamma ramp is where dealers have sold many calls and will need to
    aggressively buy stock as price approaches these strikes.
    """
    if not sorted_gex:
        return None
    
    # Calculate threshold (top 25% of positive GEX)
    positive_values = [g["gex"] for g in sorted_gex if g["gex"] > 0]
    if not positive_values:
        return None
    
    threshold = np.percentile(positive_values, 75)
    
    # Find first strike with GEX above threshold
    for item in sorted_gex:
        if item["gex"] >= threshold:
            return item["strike"]
    
    return None


def _calculate_gex_concentration(gex_data: List[Dict]) -> float:
    """
    Calculate how concentrated GEX is at specific strikes.
    
    Returns Herfindahl-style concentration index (0-1).
    Higher = more concentrated at few strikes.
    """
    if not gex_data:
        return 0.0
    
    total = sum(abs(g["gex"]) for g in gex_data)
    if total == 0:
        return 0.0
    
    # Normalized squared shares
    concentration = sum((abs(g["gex"]) / total) ** 2 for g in gex_data)
    
    return round(concentration, 4)

