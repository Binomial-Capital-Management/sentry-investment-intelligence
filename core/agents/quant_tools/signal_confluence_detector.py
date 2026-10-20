"""
Signal Confluence Detector - Multi-Factor Anomaly Scanner

The Rentec Approach: Don't look for one signal. Find when MULTIPLE independent 
signals align simultaneously. That's not noise - that's information.

Philosophy:
----------
Single signals = noise. Markets are efficient enough to arbitrage single-factor edges.
But when 5 independent data sources all flash at once? That's statistical anomaly.

This tool:
1. Pulls ALL available signals for a ticker across UW endpoints
2. Converts each to z-score against its OWN historical distribution
3. Identifies confluence - when N+ signals are simultaneously extreme
4. Surfaces anomalies for human investigation (not automated trading)

Signal Categories:
-----------------
- VOLATILITY: IV rank, IV/RV ratio, term structure, skew
- FLOW: Net premium, sweep %, floor %, call/put ratio, vol>OI
- POSITIONING: GEX regime, OI change, charm/vanna exposure
- SMART_MONEY: Dark pool prints, insider trades, congress filings
- SHORT: Short interest, FTDs, borrow rate, days to cover

Mathematical Basis:
------------------
For each metric M:
    z_score(M) = (M_current - μ_historical) / σ_historical

Confluence Score = count of signals where |z_score| > threshold

A confluence score of 5+ with aligned direction is rare (<2% of days)
and historically predictive.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import logging
import numpy as np
from scipy import stats
from agents import function_tool

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWInstitutionalServer import UWInstitutionalServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# =============================================================================
# SIGNAL DEFINITIONS
# =============================================================================

SIGNAL_CATEGORIES = {
    "volatility": [
        {"name": "iv_rank", "description": "IV percentile vs 1Y range", "higher_is": "rich_vol"},
        {"name": "iv_rv_ratio", "description": "Implied vs Realized vol", "higher_is": "rich_vol"},
        {"name": "term_structure_slope", "description": "Front vs back vol", "higher_is": "contango"},
        {"name": "put_skew_25d", "description": "Put richness at 25-delta", "higher_is": "fear"},
    ],
    "flow": [
        {"name": "net_premium_z", "description": "Net premium vs 30d avg", "higher_is": "bullish"},
        {"name": "sweep_ratio", "description": "Sweep volume %", "higher_is": "urgency"},
        {"name": "floor_ratio", "description": "Floor trade %", "higher_is": "institutional"},
        {"name": "call_put_premium_ratio", "description": "Call vs put premium", "higher_is": "bullish"},
        {"name": "vol_gt_oi_count", "description": "Contracts with vol>OI", "higher_is": "new_activity"},
    ],
    "positioning": [
        {"name": "gex_regime", "description": "Net gamma exposure", "higher_is": "vol_suppression"},
        {"name": "oi_change_pct", "description": "OI change vs yesterday", "higher_is": "building"},
        {"name": "net_delta_exposure", "description": "Aggregate delta", "higher_is": "bullish"},
    ],
    "smart_money": [
        {"name": "dark_pool_volume_z", "description": "DP volume vs avg", "higher_is": "accumulation"},
        {"name": "insider_net_30d", "description": "Insider buy-sell balance", "higher_is": "bullish"},
        {"name": "congress_activity", "description": "Recent congressional trades", "higher_is": "attention"},
    ],
    "short": [
        {"name": "short_interest_pct", "description": "SI as % of float", "higher_is": "bearish_pressure"},
        {"name": "ftd_trend", "description": "Fail-to-deliver trend", "higher_is": "settlement_stress"},
        {"name": "borrow_rate", "description": "Cost to borrow", "higher_is": "hard_to_borrow"},
        {"name": "days_to_cover", "description": "SI / Avg volume", "higher_is": "squeeze_potential"},
    ],
}


# =============================================================================
# DATA FETCHERS
# =============================================================================

async def _fetch_volatility_signals(
    options_server: UWOptionsServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch volatility-related signals from UW."""
    signals = {}
    
    try:
        # IV Rank and stats
        vol_stats_result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "stats"}
        )
        vol_stats = safe_parse_json(vol_stats_result)
        
        if vol_stats and "data" in vol_stats:
            data = vol_stats["data"]
            if isinstance(data, dict):
                signals["iv_rank"] = data.get("iv_rank") or data.get("ivRank")
                iv = data.get("iv") or data.get("impliedVolatility")
                rv = data.get("rv") or data.get("realizedVolatility") or data.get("hv")
                try:
                    iv_f = float(iv) if iv else 0
                    rv_f = float(rv) if rv else 0
                    if iv_f > 0 and rv_f > 0:
                        signals["iv_rv_ratio"] = iv_f / rv_f
                except (ValueError, TypeError):
                    pass
        
        # Historical IV for distribution
        vol_hist_result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "realized", "timeframe": "1Y"}
        )
        vol_hist = safe_parse_json(vol_hist_result)
        
        if vol_hist and "data" in vol_hist:
            hist_data = vol_hist["data"]
            if isinstance(hist_data, list) and len(hist_data) > 20:
                ratios = []
                for d in hist_data:
                    iv_val = d.get("iv") or d.get("implied_volatility")
                    rv_val = d.get("rv") or d.get("realized_volatility") or d.get("hv")
                    try:
                        iv_f = float(iv_val) if iv_val else 0
                        rv_f = float(rv_val) if rv_val else 0
                        if iv_f > 0 and rv_f > 0:
                            ratios.append(iv_f / rv_f)
                    except (ValueError, TypeError):
                        continue
                if ratios:
                    signals["iv_rv_history"] = ratios
        
        # Term structure
        term_result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "term_structure"}
        )
        term_data = safe_parse_json(term_result)
        
        if term_data and "data" in term_data:
            ts = term_data["data"]
            if isinstance(ts, list) and len(ts) >= 2:
                # Sort by expiry and compute slope
                sorted_ts = sorted(ts, key=lambda x: x.get("expiry", x.get("expiration", "")))
                front_iv = sorted_ts[0].get("iv") or sorted_ts[0].get("implied_volatility")
                back_iv = sorted_ts[-1].get("iv") or sorted_ts[-1].get("implied_volatility")
                if front_iv and back_iv:
                    signals["term_structure_slope"] = float(back_iv) - float(front_iv)
        
        # Skew
        skew_result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "skew"}
        )
        skew_data = safe_parse_json(skew_result)
        
        if skew_data and "data" in skew_data:
            sd = skew_data["data"]
            if isinstance(sd, dict):
                signals["put_skew_25d"] = sd.get("put_skew_25d") or sd.get("skew_25_delta")
            elif isinstance(sd, list) and len(sd) > 0:
                # Take latest
                signals["put_skew_25d"] = sd[-1].get("skew") or sd[-1].get("risk_reversal")
    
    except Exception as e:
        logger.warning(f"Error fetching volatility signals for {ticker}: {e}")
    
    return signals


async def _fetch_flow_signals(
    options_server: UWOptionsServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch options flow signals from UW."""
    signals = {}
    
    try:
        # Flow alerts for the ticker
        flow_result = await options_server.call_tool(
            "uw_flow_alerts",
            {"ticker": ticker, "limit": 100}
        )
        flow_data = safe_parse_json(flow_result)
        
        if flow_data and "data" in flow_data:
            alerts = flow_data["data"]
            if isinstance(alerts, list) and len(alerts) > 0:
                total_premium = 0
                call_premium = 0
                put_premium = 0
                sweep_count = 0
                floor_count = 0
                vol_gt_oi = 0
                
                for alert in alerts:
                    prem = alert.get("premium", 0) or 0
                    total_premium += prem
                    
                    if alert.get("is_call") or alert.get("type", "").lower() == "call":
                        call_premium += prem
                    else:
                        put_premium += prem
                    
                    if alert.get("is_sweep") or alert.get("sweep"):
                        sweep_count += 1
                    if alert.get("is_floor") or alert.get("floor"):
                        floor_count += 1
                    if alert.get("vol_greater_oi") or alert.get("volume_gt_oi"):
                        vol_gt_oi += 1
                
                n = len(alerts)
                signals["sweep_ratio"] = sweep_count / n if n > 0 else 0
                signals["floor_ratio"] = floor_count / n if n > 0 else 0
                signals["vol_gt_oi_count"] = vol_gt_oi
                
                if put_premium > 0:
                    signals["call_put_premium_ratio"] = call_premium / put_premium
                
                signals["total_flow_premium"] = total_premium
        
        # Options volume history for z-score
        vol_hist_result = await options_server.call_tool(
            "uw_options_volume",
            {"ticker": ticker, "limit": 60}
        )
        vol_hist = safe_parse_json(vol_hist_result)
        
        if vol_hist and "data" in vol_hist:
            hist = vol_hist["data"]
            if isinstance(hist, list) and len(hist) > 5:
                premiums = [d.get("total_premium") or d.get("premium") or 0 for d in hist]
                premiums = [p for p in premiums if p > 0]
                if premiums:
                    signals["premium_history"] = premiums
                    if len(premiums) > 1:
                        signals["net_premium_z"] = (
                            (premiums[0] - np.mean(premiums[1:])) / 
                            (np.std(premiums[1:]) + 1e-9)
                        )
    
    except Exception as e:
        logger.warning(f"Error fetching flow signals for {ticker}: {e}")
    
    return signals


async def _fetch_positioning_signals(
    options_server: UWOptionsServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch positioning/GEX signals from UW."""
    signals = {}
    
    try:
        # GEX data
        gex_result = await options_server.call_tool(
            "uw_gex",
            {"ticker": ticker, "view": "summary"}
        )
        gex_data = safe_parse_json(gex_result)
        
        if gex_data and "data" in gex_data:
            gd = gex_data["data"]
            if isinstance(gd, dict):
                net_gex = gd.get("net_gex") or gd.get("gamma_exposure") or gd.get("total_gamma")
                if net_gex is not None:
                    signals["gex_regime"] = float(net_gex)
                
                net_delta = gd.get("net_delta") or gd.get("delta_exposure")
                if net_delta is not None:
                    signals["net_delta_exposure"] = float(net_delta)
        
        # OI change
        oi_result = await options_server.call_tool(
            "uw_oi_change",
            {"ticker": ticker, "limit": 50}
        )
        oi_data = safe_parse_json(oi_result)
        
        if oi_data and "data" in oi_data:
            oi_changes = oi_data["data"]
            if isinstance(oi_changes, list) and len(oi_changes) > 0:
                total_change_pct = 0
                count = 0
                for oi in oi_changes:
                    pct = oi.get("oi_change_pct") or oi.get("change_pct")
                    if pct is not None:
                        total_change_pct += float(pct)
                        count += 1
                if count > 0:
                    signals["oi_change_pct"] = total_change_pct / count
    
    except Exception as e:
        logger.warning(f"Error fetching positioning signals for {ticker}: {e}")
    
    return signals


async def _fetch_smart_money_signals(
    institutional_server: UWInstitutionalServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch smart money signals (dark pool, insider, congress) from UW."""
    signals = {}
    
    try:
        # Dark pool
        dp_result = await institutional_server.call_tool(
            "uw_darkpool",
            {"ticker": ticker}
        )
        dp_data = safe_parse_json(dp_result)
        
        if dp_data and "data" in dp_data:
            dp = dp_data["data"]
            if isinstance(dp, list) and len(dp) > 0:
                # Recent DP volume vs average
                volumes = [d.get("volume") or d.get("size") or 0 for d in dp[:30]]
                volumes = [v for v in volumes if v > 0]
                if len(volumes) > 5:
                    recent = np.mean(volumes[:5])
                    historical = np.mean(volumes[5:])
                    std = np.std(volumes[5:]) + 1e-9
                    signals["dark_pool_volume_z"] = (recent - historical) / std
            elif isinstance(dp, dict):
                signals["dark_pool_volume"] = dp.get("volume") or dp.get("total_volume")
        
        # Insider trades
        insider_result = await institutional_server.call_tool(
            "uw_insider",
            {"ticker": ticker}
        )
        insider_data = safe_parse_json(insider_result)
        
        if insider_data and "data" in insider_data:
            insiders = insider_data["data"]
            if isinstance(insiders, list):
                buys = 0
                sells = 0
                for ins in insiders[:20]:  # Last 20 transactions
                    tx_type = (ins.get("transaction_type") or ins.get("type") or "").lower()
                    value = ins.get("value") or ins.get("amount") or 0
                    if "buy" in tx_type or "purchase" in tx_type:
                        buys += value
                    elif "sell" in tx_type or "sale" in tx_type:
                        sells += value
                
                if buys + sells > 0:
                    signals["insider_net_30d"] = (buys - sells) / (buys + sells)
        
        # Congress trades
        congress_result = await institutional_server.call_tool(
            "uw_congress",
            {"view": "recent"}
        )
        congress_data = safe_parse_json(congress_result)
        
        if congress_data and "data" in congress_data:
            congress = congress_data["data"]
            if isinstance(congress, list):
                # Check if ticker appears in recent congress trades
                ticker_upper = ticker.upper()
                congress_trades = [
                    c for c in congress 
                    if (c.get("ticker") or c.get("symbol") or "").upper() == ticker_upper
                ]
                signals["congress_activity"] = len(congress_trades)
    
    except Exception as e:
        logger.warning(f"Error fetching smart money signals for {ticker}: {e}")
    
    return signals


async def _fetch_short_signals(
    market_server: UWMarketServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch short interest signals from UW."""
    signals = {}
    
    try:
        short_result = await market_server.call_tool(
            "uw_short_data",
            {"ticker": ticker, "metric": "all"}
        )
        short_data = safe_parse_json(short_result)
        
        if short_data and "data" in short_data:
            sd = short_data["data"]
            if isinstance(sd, dict):
                signals["short_interest_pct"] = sd.get("short_interest_pct") or sd.get("si_pct_float")
                signals["borrow_rate"] = sd.get("borrow_rate") or sd.get("fee_rate")
                signals["days_to_cover"] = sd.get("days_to_cover") or sd.get("dtc")
            elif isinstance(sd, list) and len(sd) > 0:
                latest = sd[0]
                signals["short_interest_pct"] = latest.get("short_interest_pct") or latest.get("si_pct_float")
                signals["borrow_rate"] = latest.get("borrow_rate") or latest.get("fee_rate")
                signals["days_to_cover"] = latest.get("days_to_cover") or latest.get("dtc")
                
                # FTD trend
                if len(sd) > 5:
                    ftds = [d.get("ftd") or d.get("fails_to_deliver") or 0 for d in sd[:10]]
                    ftds = [f for f in ftds if f > 0]
                    if len(ftds) >= 2:
                        # Positive = increasing FTDs
                        signals["ftd_trend"] = (ftds[0] - ftds[-1]) / (ftds[-1] + 1)
    
    except Exception as e:
        logger.warning(f"Error fetching short signals for {ticker}: {e}")
    
    return signals


# =============================================================================
# Z-SCORE COMPUTATION
# =============================================================================

def _compute_z_scores(signals: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Convert raw signals to z-scores.
    For signals with history, use empirical distribution.
    For point-in-time signals, use reasonable heuristics.
    """
    z_scores = {}
    
    # IV Rank is already a percentile (0-100)
    if "iv_rank" in signals and signals["iv_rank"] is not None:
        iv_rank = float(signals["iv_rank"])
        # Convert percentile to z-score approximation
        z = stats.norm.ppf(iv_rank / 100) if 0 < iv_rank < 100 else 0
        z_scores["iv_rank"] = {
            "value": iv_rank,
            "z_score": z,
            "direction": "high" if z > 0 else "low",
            "category": "volatility"
        }
    
    # IV/RV ratio with history
    if "iv_rv_ratio" in signals and signals["iv_rv_ratio"] is not None:
        current = signals["iv_rv_ratio"]
        history = signals.get("iv_rv_history", [])
        
        if len(history) > 10:
            mu = np.mean(history)
            sigma = np.std(history) + 1e-9
            z = (current - mu) / sigma
        else:
            # Heuristic: ratio of 1.0 is "fair", typical range 0.7-1.5
            z = (current - 1.0) / 0.2
        
        z_scores["iv_rv_ratio"] = {
            "value": round(current, 2),
            "z_score": round(z, 2),
            "direction": "rich_vol" if z > 0 else "cheap_vol",
            "category": "volatility"
        }
    
    # Term structure slope
    if "term_structure_slope" in signals and signals["term_structure_slope"] is not None:
        slope = signals["term_structure_slope"]
        # Typical range: -0.10 to +0.10
        z = slope / 0.03
        z_scores["term_structure_slope"] = {
            "value": round(slope, 4),
            "z_score": round(z, 2),
            "direction": "contango" if z > 0 else "backwardation",
            "category": "volatility"
        }
    
    # Skew
    if "put_skew_25d" in signals and signals["put_skew_25d"] is not None:
        skew = float(signals["put_skew_25d"])
        z = skew / 0.02  # Typical range
        z_scores["put_skew_25d"] = {
            "value": round(skew, 4),
            "z_score": round(z, 2),
            "direction": "fear" if z > 0 else "complacent",
            "category": "volatility"
        }
    
    # Flow signals
    if "net_premium_z" in signals and signals["net_premium_z"] is not None:
        z = signals["net_premium_z"]
        z_scores["net_premium"] = {
            "value": signals.get("total_flow_premium", 0),
            "z_score": round(z, 2),
            "direction": "elevated" if z > 0 else "subdued",
            "category": "flow"
        }
    
    if "sweep_ratio" in signals and signals["sweep_ratio"] is not None:
        sweep = signals["sweep_ratio"]
        # Typical sweep ratio: 10-30%
        z = (sweep - 0.2) / 0.1
        z_scores["sweep_ratio"] = {
            "value": round(sweep * 100, 1),
            "z_score": round(z, 2),
            "direction": "urgent" if z > 0 else "normal",
            "category": "flow"
        }
    
    if "floor_ratio" in signals and signals["floor_ratio"] is not None:
        floor = signals["floor_ratio"]
        z = (floor - 0.05) / 0.03
        z_scores["floor_ratio"] = {
            "value": round(floor * 100, 1),
            "z_score": round(z, 2),
            "direction": "institutional" if z > 0 else "retail",
            "category": "flow"
        }
    
    if "call_put_premium_ratio" in signals and signals["call_put_premium_ratio"] is not None:
        ratio = signals["call_put_premium_ratio"]
        # Neutral at 1.0
        z = (ratio - 1.0) / 0.5
        z_scores["call_put_ratio"] = {
            "value": round(ratio, 2),
            "z_score": round(z, 2),
            "direction": "bullish" if z > 0 else "bearish",
            "category": "flow"
        }
    
    if "vol_gt_oi_count" in signals and signals["vol_gt_oi_count"] is not None:
        count = signals["vol_gt_oi_count"]
        z = (count - 5) / 3
        z_scores["vol_gt_oi"] = {
            "value": count,
            "z_score": round(z, 2),
            "direction": "new_activity" if z > 0 else "normal",
            "category": "flow"
        }
    
    # Positioning
    if "gex_regime" in signals and signals["gex_regime"] is not None:
        gex = signals["gex_regime"]
        # Normalize by typical GEX magnitude (varies by ticker)
        z = gex / (abs(gex) + 1e9) * 2 if gex != 0 else 0
        z_scores["gex_regime"] = {
            "value": gex,
            "z_score": round(z, 2),
            "direction": "positive_gamma" if z > 0 else "negative_gamma",
            "category": "positioning"
        }
    
    if "oi_change_pct" in signals and signals["oi_change_pct"] is not None:
        oi_chg = signals["oi_change_pct"]
        z = oi_chg / 0.15
        z_scores["oi_change"] = {
            "value": round(oi_chg * 100, 1),
            "z_score": round(z, 2),
            "direction": "building" if z > 0 else "unwinding",
            "category": "positioning"
        }
    
    if "net_delta_exposure" in signals and signals["net_delta_exposure"] is not None:
        delta = signals["net_delta_exposure"]
        z = delta / (abs(delta) + 1e6) * 2 if delta != 0 else 0
        z_scores["net_delta"] = {
            "value": delta,
            "z_score": round(z, 2),
            "direction": "bullish" if z > 0 else "bearish",
            "category": "positioning"
        }
    
    # Smart money
    if "dark_pool_volume_z" in signals and signals["dark_pool_volume_z"] is not None:
        z = signals["dark_pool_volume_z"]
        z_scores["dark_pool"] = {
            "value": "elevated" if z > 1 else "normal",
            "z_score": round(z, 2),
            "direction": "accumulation" if z > 0 else "distribution",
            "category": "smart_money"
        }
    
    if "insider_net_30d" in signals and signals["insider_net_30d"] is not None:
        net = signals["insider_net_30d"]
        z = net / 0.3  # -1 to 1 range, significant at ±0.3
        z_scores["insider_activity"] = {
            "value": round(net, 2),
            "z_score": round(z, 2),
            "direction": "buying" if z > 0 else "selling",
            "category": "smart_money"
        }
    
    if "congress_activity" in signals and signals["congress_activity"] is not None:
        count = signals["congress_activity"]
        z = count / 0.5 if count > 0 else 0
        z_scores["congress"] = {
            "value": count,
            "z_score": round(z, 2),
            "direction": "active" if count > 0 else "none",
            "category": "smart_money"
        }
    
    # Short signals
    if "short_interest_pct" in signals and signals["short_interest_pct"] is not None:
        si = float(signals["short_interest_pct"])
        z = (si - 5) / 5  # 5% is typical, 10%+ is elevated
        z_scores["short_interest"] = {
            "value": round(si, 1),
            "z_score": round(z, 2),
            "direction": "elevated" if z > 0 else "low",
            "category": "short"
        }
    
    if "borrow_rate" in signals and signals["borrow_rate"] is not None:
        rate = float(signals["borrow_rate"])
        z = (rate - 1) / 3  # 1% is easy, 4%+ is hard to borrow
        z_scores["borrow_rate"] = {
            "value": round(rate, 1),
            "z_score": round(z, 2),
            "direction": "hard_to_borrow" if z > 0 else "easy",
            "category": "short"
        }
    
    if "days_to_cover" in signals and signals["days_to_cover"] is not None:
        dtc = float(signals["days_to_cover"])
        z = (dtc - 2) / 1.5
        z_scores["days_to_cover"] = {
            "value": round(dtc, 1),
            "z_score": round(z, 2),
            "direction": "squeeze_risk" if z > 0 else "low",
            "category": "short"
        }
    
    if "ftd_trend" in signals and signals["ftd_trend"] is not None:
        trend = signals["ftd_trend"]
        z = trend / 0.2
        z_scores["ftd_trend"] = {
            "value": round(trend, 2),
            "z_score": round(z, 2),
            "direction": "increasing" if z > 0 else "decreasing",
            "category": "short"
        }
    
    return z_scores


# =============================================================================
# CONFLUENCE DETECTION
# =============================================================================

def _detect_confluence(
    z_scores: Dict[str, Dict[str, Any]],
    z_threshold: float,
    min_signals: int
) -> Dict[str, Any]:
    """
    Identify when multiple signals are simultaneously extreme.
    """
    extreme_signals = []
    bullish_signals = []
    bearish_signals = []
    
    bullish_directions = {
        "bullish", "buying", "rich_vol", "accumulation", 
        "squeeze_risk", "increasing", "new_activity", "urgent", "institutional"
    }
    bearish_directions = {
        "bearish", "selling", "cheap_vol", "distribution", "low"
    }
    
    for signal_name, data in z_scores.items():
        z = data["z_score"]
        direction = data["direction"]
        
        if abs(z) >= z_threshold:
            signal_info = {
                "signal": signal_name,
                "z_score": z,
                "value": data["value"],
                "direction": direction,
                "category": data["category"]
            }
            extreme_signals.append(signal_info)
            
            if direction in bullish_directions or z > z_threshold:
                bullish_signals.append(signal_info)
            elif direction in bearish_directions or z < -z_threshold:
                bearish_signals.append(signal_info)
    
    confluence_score = len(extreme_signals)
    has_confluence = confluence_score >= min_signals
    
    # Determine overall bias
    if len(bullish_signals) > len(bearish_signals) + 1:
        bias = "BULLISH"
        aligned_signals = bullish_signals
        conflicting_signals = bearish_signals
    elif len(bearish_signals) > len(bullish_signals) + 1:
        bias = "BEARISH"
        aligned_signals = bearish_signals
        conflicting_signals = bullish_signals
    else:
        bias = "MIXED"
        aligned_signals = extreme_signals
        conflicting_signals = []
    
    return {
        "confluence_detected": has_confluence,
        "confluence_score": confluence_score,
        "z_threshold": z_threshold,
        "min_signals_required": min_signals,
        "bias": bias,
        "extreme_signals": extreme_signals,
        "aligned_signals": aligned_signals,
        "conflicting_signals": conflicting_signals,
        "bullish_count": len(bullish_signals),
        "bearish_count": len(bearish_signals)
    }


def _generate_interpretation(
    ticker: str,
    confluence: Dict[str, Any],
    z_scores: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate human-readable interpretation of the confluence."""
    
    if not confluence["confluence_detected"]:
        return {
            "headline": f"{ticker}: No significant confluence detected",
            "summary": f"Only {confluence['confluence_score']} signals above threshold. Markets appear to be pricing normally.",
            "action": "MONITOR",
            "confidence": "LOW"
        }
    
    score = confluence["confluence_score"]
    bias = confluence["bias"]
    
    # Build narrative from extreme signals
    signal_descriptions = []
    for sig in confluence["extreme_signals"][:5]:  # Top 5
        signal_descriptions.append(
            f"{sig['signal'].replace('_', ' ').title()}: {sig['value']} (z={sig['z_score']:+.1f})"
        )
    
    if bias == "BULLISH":
        headline = f"{ticker}: {score}-Signal BULLISH Confluence 🟢"
        summary = (
            f"Multiple independent signals aligning bullish. "
            f"{confluence['bullish_count']} bullish vs {confluence['bearish_count']} bearish signals. "
            f"This level of confluence is statistically rare (<5% of days)."
        )
        action = "INVESTIGATE LONG"
    elif bias == "BEARISH":
        headline = f"{ticker}: {score}-Signal BEARISH Confluence 🔴"
        summary = (
            f"Multiple independent signals aligning bearish. "
            f"{confluence['bearish_count']} bearish vs {confluence['bullish_count']} bullish signals. "
            f"This level of confluence is statistically rare (<5% of days)."
        )
        action = "INVESTIGATE SHORT"
    else:
        headline = f"{ticker}: {score}-Signal MIXED Confluence ⚠️"
        summary = (
            f"Multiple extreme signals but no clear directional alignment. "
            f"This suggests high uncertainty or a transitional regime. "
            f"Elevated activity without clear bias often precedes volatility."
        )
        action = "INVESTIGATE VOL TRADE"
    
    confidence = "HIGH" if score >= 5 else "MEDIUM" if score >= 3 else "LOW"
    
    return {
        "headline": headline,
        "summary": summary,
        "signal_details": signal_descriptions,
        "action": action,
        "confidence": confidence
    }


# =============================================================================
# MAIN TOOL
# =============================================================================

async def detect_signal_confluence_internal(
    ticker: str,
    z_threshold: float = 1.5,
    min_signals: int = 3,
    categories: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Multi-factor anomaly scanner that detects when multiple independent signals 
    align simultaneously - the statistical signature of real information vs noise.
    
    Philosophy: Single signals are noise. Markets arbitrage single-factor edges.
    But when 5+ independent data sources all flash at once? That's not random.
    
    Args:
        ticker: Stock symbol to analyze
        z_threshold: How extreme a signal must be to count (default 1.5 = ~93rd percentile)
        min_signals: Minimum aligned signals to flag confluence (default 3)
        categories: Filter to specific signal types. Options:
                   ["volatility", "flow", "positioning", "smart_money", "short"]
                   Default: all categories
    
    Returns:
        Confluence analysis with:
        - confluence_score: Number of extreme signals
        - bias: BULLISH / BEARISH / MIXED
        - extreme_signals: Details on each signal above threshold
        - interpretation: Human-readable summary and suggested action
        - all_signals: Full z-score breakdown for all metrics
    
    Example:
        # Basic scan
        detect_signal_confluence("NVDA")
        
        # More sensitive detection
        detect_signal_confluence("TSLA", z_threshold=1.2, min_signals=4)
        
        # Focus on smart money only
        detect_signal_confluence("AAPL", categories=["smart_money", "flow"])
    
    Statistical Context:
        - 1 signal at z>1.5: Common (~14% of time)
        - 3 signals at z>1.5: Rare (~1% of time)  
        - 5 signals at z>1.5: Very rare (<0.1% of time)
        
        When 5+ independent signals align, that's not noise. Investigate.
    """
    
    # Initialize servers
    try:
        options_server = UWOptionsServer()
        institutional_server = UWInstitutionalServer()
        market_server = UWMarketServer()
        
        await options_server.connect()
        await institutional_server.connect()
        await market_server.connect()
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to initialize UW servers: {str(e)}",
            "hint": "Ensure UW_API_KEY is set in environment"
        }
    
    try:
        # Determine which categories to fetch
        all_categories = ["volatility", "flow", "positioning", "smart_money", "short"]
        active_categories = categories if categories else all_categories
        
        # Fetch all signals in parallel
        tasks = []
        
        if "volatility" in active_categories:
            tasks.append(("volatility", _fetch_volatility_signals(options_server, ticker)))
        if "flow" in active_categories:
            tasks.append(("flow", _fetch_flow_signals(options_server, ticker)))
        if "positioning" in active_categories:
            tasks.append(("positioning", _fetch_positioning_signals(options_server, ticker)))
        if "smart_money" in active_categories:
            tasks.append(("smart_money", _fetch_smart_money_signals(institutional_server, ticker)))
        if "short" in active_categories:
            tasks.append(("short", _fetch_short_signals(market_server, ticker)))
        
        # Execute all fetches in parallel
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        
        # Combine all signals
        all_signals = {}
        for (category, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Error fetching {category} signals: {result}")
            elif isinstance(result, dict):
                all_signals.update(result)
        
        if not all_signals:
            return {
                "status": "error",
                "error": f"No signals retrieved for {ticker}",
                "hint": "Ticker may be invalid or have no options activity"
            }
        
        # Compute z-scores
        z_scores = _compute_z_scores(all_signals)
        
        # Detect confluence
        confluence = _detect_confluence(z_scores, z_threshold, min_signals)
        
        # Generate interpretation
        interpretation = _generate_interpretation(ticker, confluence, z_scores)
        
        # Cleanup
        await options_server.cleanup()
        await institutional_server.cleanup()
        await market_server.cleanup()
        
        return {
            "status": "success",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "z_threshold": z_threshold,
                "min_signals": min_signals,
                "categories": active_categories
            },
            "confluence": {
                "detected": confluence["confluence_detected"],
                "score": confluence["confluence_score"],
                "bias": confluence["bias"],
                "bullish_signals": confluence["bullish_count"],
                "bearish_signals": confluence["bearish_count"]
            },
            "extreme_signals": confluence["extreme_signals"],
            "interpretation": interpretation,
            "all_signals": z_scores
        }
        
    except Exception as e:
        logger.error(f"Error in signal confluence detection: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        try:
            await options_server.cleanup()
            await institutional_server.cleanup()
            await market_server.cleanup()
        except:
            pass


@function_tool
async def detect_signal_confluence(
    ticker: str,
    z_threshold: float = 1.5,
    min_signals: int = 3,
    categories: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Multi-factor anomaly scanner that detects when multiple independent signals 
    align simultaneously - the statistical signature of real information vs noise.
    
    This is the agent-facing wrapper. For Canvas integration, use the _internal version.
    """
    from core.utils.risk_adapter import jsonify_results
    result = await detect_signal_confluence_internal(ticker, z_threshold, min_signals, categories)
    return jsonify_results(result)


@function_tool
async def scan_universe_confluence(
    tickers: List[str],
    z_threshold: float = 1.5,
    min_signals: int = 3,
    categories: Optional[List[str]] = None,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    Scan a universe of tickers for signal confluence anomalies.
    
    This is the "screener" version - find which stocks in a universe
    currently have unusual multi-signal alignment.
    
    Args:
        tickers: List of stock symbols to scan
        z_threshold: Extremity threshold for signals (default 1.5)
        min_signals: Minimum signals for confluence (default 3)
        categories: Signal categories to check (default: all)
        max_concurrent: Max parallel scans (default 5, be nice to API)
    
    Returns:
        Universe scan results sorted by confluence score
    
    Example:
        # Scan tech names
        scan_universe_confluence(["AAPL", "NVDA", "TSLA", "AMD", "META"])
        
        # Scan with smart money focus
        scan_universe_confluence(
            ["GME", "AMC", "BBBY", "KOSS"],
            categories=["smart_money", "short"]
        )
    """
    
    async def scan_one(ticker: str) -> Dict[str, Any]:
        try:
            result = await detect_signal_confluence(
                ticker=ticker,
                z_threshold=z_threshold,
                min_signals=min_signals,
                categories=categories
            )
            return {"ticker": ticker, "result": result}
        except Exception as e:
            return {"ticker": ticker, "result": {"status": "error", "error": str(e)}}
    
    # Scan in batches to respect rate limits
    all_results = []
    for i in range(0, len(tickers), max_concurrent):
        batch = tickers[i:i + max_concurrent]
        batch_results = await asyncio.gather(*[scan_one(t) for t in batch])
        all_results.extend(batch_results)
        
        # Small delay between batches
        if i + max_concurrent < len(tickers):
            await asyncio.sleep(1)
    
    # Process results
    anomalies = []
    no_confluence = []
    errors = []
    
    for item in all_results:
        ticker = item["ticker"]
        result = item["result"]
        
        if result.get("status") == "error":
            errors.append({"ticker": ticker, "error": result.get("error")})
        elif result.get("confluence", {}).get("detected"):
            anomalies.append({
                "ticker": ticker,
                "confluence_score": result["confluence"]["score"],
                "bias": result["confluence"]["bias"],
                "headline": result["interpretation"]["headline"],
                "action": result["interpretation"]["action"],
                "top_signals": result["extreme_signals"][:3]
            })
        else:
            no_confluence.append(ticker)
    
    # Sort anomalies by score
    anomalies.sort(key=lambda x: x["confluence_score"], reverse=True)
    
    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "z_threshold": z_threshold,
            "min_signals": min_signals,
            "categories": categories or ["all"],
            "universe_size": len(tickers)
        },
        "summary": {
            "anomalies_found": len(anomalies),
            "no_confluence": len(no_confluence),
            "errors": len(errors)
        },
        "anomalies": anomalies,
        "no_confluence_tickers": no_confluence,
        "errors": errors if errors else None
    }

