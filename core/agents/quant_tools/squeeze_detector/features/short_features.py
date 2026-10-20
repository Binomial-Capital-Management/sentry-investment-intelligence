"""
Short Feature Extraction

Extracts short selling features:
- Short interest % of float
- Days to cover
- FTD (Failure to Deliver) trends
- Borrow fee / availability
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np

from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


async def extract_short_features(
    uw_market,  # UWMarketServer
    ticker: str,
    lookback_days: int = 60
) -> Optional[Dict[str, Any]]:
    """
    Extract short selling features from Unusual Whales.
    
    Fetches:
    1. Short interest - SI%, shares short, days to cover
    2. FTDs - Failure to deliver trends
    3. Borrow data - Fee rate, availability
    
    Returns:
        Dict with short metrics for squeeze analysis
    """
    try:
        import asyncio
        
        # Parallel fetch all views
        results = await asyncio.gather(
            _fetch_short_interest(uw_market, ticker),
            _fetch_ftd_data(uw_market, ticker),
            _fetch_borrow_data(uw_market, ticker),
            return_exceptions=True
        )
        
        si_data = results[0] if not isinstance(results[0], Exception) else None
        ftd_data = results[1] if not isinstance(results[1], Exception) else None
        borrow_data = results[2] if not isinstance(results[2], Exception) else None
        
        if not any([si_data, ftd_data, borrow_data]):
            logger.warning(f"No short data available for {ticker}")
            return None
        
        return {
            "short_interest": si_data,
            "ftd": ftd_data,
            "borrow": borrow_data,
            "summary": _summarize_short(si_data, ftd_data, borrow_data)
        }
    
    except Exception as e:
        logger.error(f"Failed to extract short features for {ticker}: {e}")
        return None


async def _fetch_short_interest(uw_market, ticker: str) -> Optional[Dict]:
    """Fetch short interest data."""
    try:
        result = await uw_market.call_tool("uw_short_data", {
            "ticker": ticker,
            "view": "interest"
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        return _parse_short_interest(data)
    
    except Exception as e:
        logger.warning(f"Failed to fetch short interest: {e}")
        return None


async def _fetch_ftd_data(uw_market, ticker: str) -> Optional[Dict]:
    """Fetch failure to deliver data."""
    try:
        result = await uw_market.call_tool("uw_short_data", {
            "ticker": ticker,
            "view": "ftds"
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        return _parse_ftd_data(data)
    
    except Exception as e:
        logger.warning(f"Failed to fetch FTD data: {e}")
        return None


async def _fetch_borrow_data(uw_market, ticker: str) -> Optional[Dict]:
    """Fetch borrow availability and fee data."""
    try:
        result = await uw_market.call_tool("uw_short_data", {
            "ticker": ticker,
            "view": "data"
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        return _parse_borrow_data(data)
    
    except Exception as e:
        logger.warning(f"Failed to fetch borrow data: {e}")
        return None


def _parse_short_interest(data: Any) -> Dict:
    """Parse short interest data."""
    if isinstance(data, list) and len(data) > 0:
        data = data[0]  # Take most recent
    
    if not isinstance(data, dict):
        return {}
    
    si_pct = _find_numeric(data, [
        "short_interest_pct", "shortInterestPct", "si_pct", 
        "short_percent_of_float", "shortPercentOfFloat"
    ])
    
    shares_short = _find_numeric(data, [
        "shares_short", "sharesShort", "short_shares"
    ])
    
    days_to_cover = _find_numeric(data, [
        "days_to_cover", "daysToCover", "dtc"
    ])
    
    return {
        "short_interest_pct": round(si_pct, 2) if si_pct else None,
        "shares_short": int(shares_short) if shares_short else None,
        "days_to_cover": round(days_to_cover, 2) if days_to_cover else None
    }


def _parse_ftd_data(data: Any) -> Dict:
    """Parse FTD data and calculate trend."""
    ftd_list = []
    
    if isinstance(data, list):
        ftd_list = data
    elif isinstance(data, dict):
        ftd_list = data.get("data", data.get("ftds", []))
    
    if not ftd_list:
        return {"ftd_trend": "unknown", "recent_ftds": 0}
    
    # Extract FTD values (most recent first)
    ftd_values = []
    for item in ftd_list[:20]:  # Last 20 data points
        if isinstance(item, dict):
            val = _find_numeric(item, ["ftd", "ftds", "quantity", "failsToDeliver"])
            if val is not None:
                ftd_values.append(val)
    
    if not ftd_values:
        return {"ftd_trend": "unknown", "recent_ftds": 0}
    
    # Calculate trend
    recent_avg = np.mean(ftd_values[:5]) if len(ftd_values) >= 5 else np.mean(ftd_values)
    older_avg = np.mean(ftd_values[5:10]) if len(ftd_values) >= 10 else recent_avg
    
    if recent_avg > older_avg * 1.2:
        trend = "increasing"
    elif recent_avg < older_avg * 0.8:
        trend = "decreasing"
    else:
        trend = "stable"
    
    return {
        "ftd_trend": trend,
        "recent_ftds": int(recent_avg),
        "ftd_change_pct": round((recent_avg / older_avg - 1) * 100, 1) if older_avg > 0 else 0
    }


def _parse_borrow_data(data: Any) -> Dict:
    """Parse borrow availability data."""
    if isinstance(data, list) and len(data) > 0:
        data = data[0]
    
    if not isinstance(data, dict):
        return {}
    
    fee_rate = _find_numeric(data, [
        "fee_rate", "feeRate", "borrow_fee", "borrowFee",
        "rebate_rate", "rebateRate"
    ])
    
    shares_available = _find_numeric(data, [
        "shares_available", "sharesAvailable", "available",
        "short_shares_available"
    ])
    
    # Determine if hard to borrow
    hard_to_borrow = False
    if fee_rate and fee_rate > 10:
        hard_to_borrow = True
    if shares_available and shares_available < 100000:
        hard_to_borrow = True
    
    return {
        "borrow_fee_pct": round(fee_rate, 2) if fee_rate else None,
        "shares_available": int(shares_available) if shares_available else None,
        "hard_to_borrow": hard_to_borrow
    }


def _summarize_short(
    si_data: Optional[Dict],
    ftd_data: Optional[Dict],
    borrow_data: Optional[Dict]
) -> Dict:
    """
    Create summary of short data.
    
    No hardcoded thresholds - just reports the signals present.
    Models use z-scores for probability estimation.
    """
    summary = {
        "signals_present": []
    }
    
    if si_data:
        si_pct = si_data.get("short_interest_pct")
        dtc = si_data.get("days_to_cover")
        
        if si_pct is not None:
            summary["short_interest_pct"] = si_pct
            summary["signals_present"].append("short_interest")
        if dtc is not None:
            summary["days_to_cover"] = dtc
            summary["signals_present"].append("days_to_cover")
    
    if ftd_data:
        ftd_trend = ftd_data.get("ftd_trend")
        if ftd_trend and ftd_trend != "unknown":
            summary["ftd_trend"] = ftd_trend
            summary["signals_present"].append("ftd")
    
    if borrow_data:
        if borrow_data.get("hard_to_borrow"):
            summary["hard_to_borrow"] = True
            summary["signals_present"].append("borrow_difficulty")
        if borrow_data.get("borrow_fee_pct") is not None:
            summary["borrow_fee_pct"] = borrow_data["borrow_fee_pct"]
    
    summary["signal_count"] = len(summary["signals_present"])
    
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

