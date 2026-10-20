"""
Earnings Pattern Analyzer - Historical Earnings Intelligence

Analyzes historical earnings patterns to identify vol trading opportunities.
All computation is stateless - fetches data, analyzes on-the-fly, outputs insights.

Data Sources:
-------------
- FMP: EPS actual/estimate data (Non-GAAP, what analysts track)
- UW: Volatility metrics (expected_move, post_earnings_move, short_straddle returns)

Key Questions Answered:
-----------------------
1. How does implied move compare to actual move historically?
2. What's the vol crush rate for this stock?
3. Is current IV rank high/low relative to pre-earnings history?
4. What patterns predict vol crush vs vol expansion?

No persistent storage - everything computed fresh each call.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import os
import aiohttp
import numpy as np
from scipy import stats as scipy_stats
from agents import function_tool

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


# =============================================================================
# FMP EPS DATA FETCHER (Non-GAAP - what analysts estimate against)
# =============================================================================

async def _fetch_fmp_earnings(ticker: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch EPS data from FMP (earnings-surprises endpoint).
    
    FMP provides Non-GAAP EPS which is what analysts estimate against.
    This is more accurate for beat/miss analysis than GAAP EPS.
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        logger.warning("FMP_API_KEY not set - cannot fetch EPS data")
        return []
    
    url = f"https://financialmodelingprep.com/api/v3/earnings-surprises/{ticker}?apikey={api_key}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    logger.warning(f"FMP earnings API returned {resp.status}")
                    return []
                
                data = await resp.json()
                
                if not isinstance(data, list):
                    logger.warning(f"FMP earnings response not a list: {type(data)}")
                    return []
                
                # FMP returns: date, actualEarningResult, estimatedEarning
                logger.info(f"[FMP EPS] Fetched {len(data)} earnings records for {ticker}")
                return data[:limit]
                
    except Exception as e:
        logger.warning(f"Error fetching FMP earnings for {ticker}: {e}")
        return []


# =============================================================================
# DATA FETCHERS
# =============================================================================

async def _fetch_uw_vol_data(
    market_server: UWMarketServer,
    ticker: str
) -> List[Dict[str, Any]]:
    """Fetch volatility metrics around earnings from UW.
    
    UW provides: expected_move_perc, post_earnings_move_1d, short_straddle_1d
    These are the key vol trading metrics.
    """
    try:
        result = await market_server.call_tool(
            "uw_earnings",
            {"ticker": ticker}
        )
        data = safe_parse_json(result)
        
        if data and "data" in data:
            earnings = data["data"]
            if isinstance(earnings, list):
                logger.info(f"[UW VOL] Fetched {len(earnings)} vol records for {ticker}")
                return earnings
        
        return []
    except Exception as e:
        logger.warning(f"Error fetching UW vol data for {ticker}: {e}")
        return []


async def _merge_earnings_data(
    fmp_eps: List[Dict[str, Any]],
    uw_vol: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge FMP EPS data with UW volatility data by date.
    
    FMP: date, actualEarningResult, estimatedEarning (Non-GAAP)
    UW: report_date, expected_move_perc, post_earnings_move_1d, short_straddle_1d
    
    Returns merged records with both EPS and vol data.
    """
    merged = []
    
    # Build lookup for UW data by date
    uw_by_date = {}
    for uw_rec in uw_vol:
        date_str = uw_rec.get("report_date")
        if date_str:
            # Normalize to just date part
            uw_by_date[date_str[:10]] = uw_rec
    
    # Merge with FMP data
    for fmp_rec in fmp_eps:
        fmp_date = fmp_rec.get("date")
        if not fmp_date:
            continue
        
        merged_rec = {
            "date": fmp_date[:10],
            # FMP EPS data (Non-GAAP - accurate)
            "eps_actual": fmp_rec.get("actualEarningResult"),
            "eps_estimate": fmp_rec.get("estimatedEarning"),
        }
        
        # Try to find matching UW vol data
        uw_match = uw_by_date.get(fmp_date[:10])
        if uw_match:
            # UW vol data
            merged_rec["expected_move_perc"] = uw_match.get("expected_move_perc")
            merged_rec["post_earnings_move_1d"] = uw_match.get("post_earnings_move_1d")
            merged_rec["short_straddle_1d"] = uw_match.get("short_straddle_1d")
            merged_rec["report_time"] = uw_match.get("report_time")
        
        merged.append(merged_rec)
    
    # Also add UW-only records (future earnings with expected_move but no actual yet)
    for date_str, uw_rec in uw_by_date.items():
        if not any(m["date"] == date_str for m in merged):
            # UW-only record (probably future or missing from FMP)
            if uw_rec.get("expected_move_perc") and not uw_rec.get("actual_eps"):
                merged.append({
                    "date": date_str,
                    "expected_move_perc": uw_rec.get("expected_move_perc"),
                    "report_time": uw_rec.get("report_time"),
                    "is_future": True
                })
    
    # Sort by date descending
    merged.sort(key=lambda x: x["date"], reverse=True)
    
    logger.info(f"[MERGE] Combined {len(fmp_eps)} FMP + {len(uw_vol)} UW = {len(merged)} merged records")
    
    return merged


async def _fetch_volatility_history(
    options_server: UWOptionsServer,
    ticker: str,
    timeframe: str = "1Y"
) -> List[Dict[str, Any]]:
    """Fetch historical IV/RV data from UW."""
    try:
        result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "realized", "timeframe": timeframe}
        )
        data = safe_parse_json(result)
        
        if data and "data" in data:
            vol_data = data["data"]
            if isinstance(vol_data, list):
                return vol_data
        
        return []
    except Exception as e:
        logger.warning(f"Error fetching volatility history for {ticker}: {e}")
        return []


async def _fetch_current_vol_stats(
    options_server: UWOptionsServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch current volatility stats from UW."""
    try:
        result = await options_server.call_tool(
            "uw_volatility",
            {"ticker": ticker, "metric": "stats"}
        )
        data = safe_parse_json(result)
        
        if data and "data" in data:
            return data["data"] if isinstance(data["data"], dict) else {}
        
        return {}
    except Exception as e:
        logger.warning(f"Error fetching current vol stats for {ticker}: {e}")
        return {}


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def _parse_earnings_date(earnings_record: Dict[str, Any]) -> Optional[datetime]:
    """Parse earnings date from various possible formats."""
    date_fields = ["date", "reportDate", "report_date", "earningsDate", "earnings_date"]
    
    for field in date_fields:
        date_str = earnings_record.get(field)
        if date_str:
            try:
                # Try various formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(date_str[:10], fmt[:len(date_str[:10])+2])
                    except:
                        continue
                # Try ISO format
                return datetime.fromisoformat(date_str.replace("Z", "+00:00").split("T")[0])
            except:
                continue
    
    return None


def _extract_earnings_features(earnings: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standardized features from a merged earnings record.
    
    Merged format contains:
    - FMP data: eps_actual, eps_estimate (Non-GAAP - accurate)
    - UW data: expected_move_perc, post_earnings_move_1d, short_straddle_1d
    """
    features = {}
    
    # Date (already in YYYY-MM-DD string format from merge)
    date_str = earnings.get("date")
    if date_str:
        try:
            features["date"] = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except:
            features["date"] = None
    
    # Skip future earnings (have expected_move but no actual data)
    if earnings.get("is_future"):
        features["is_future"] = True
        features["expected_move_pct"] = earnings.get("expected_move_perc")
        return features
    
    # EPS from FMP (Non-GAAP - what analysts track)
    eps_actual = earnings.get("eps_actual")
    eps_estimate = earnings.get("eps_estimate")
    
    if eps_actual is not None and eps_estimate is not None:
        try:
            eps_actual = float(eps_actual)
            eps_estimate = float(eps_estimate)
            features["eps_actual"] = eps_actual
            features["eps_estimate"] = eps_estimate
            features["eps_beat"] = eps_actual > eps_estimate
            if eps_estimate != 0:
                features["eps_surprise_pct"] = (eps_actual - eps_estimate) / abs(eps_estimate) * 100
        except (ValueError, TypeError):
            pass
    
    # Vol data from UW - Expected vs Actual Move
    expected_move_pct = earnings.get("expected_move_perc")
    actual_move_1d = earnings.get("post_earnings_move_1d")
    
    if expected_move_pct is not None and actual_move_1d is not None:
        try:
            expected_pct = float(expected_move_pct) * 100  # Convert to percentage
            actual_pct = abs(float(actual_move_1d)) * 100  # Absolute value
            features["expected_move_pct"] = expected_pct
            features["actual_move_pct"] = actual_pct
            features["vol_crush"] = actual_pct < expected_pct  # Vol crush if move < expected
        except (ValueError, TypeError):
            pass
    
    # Report time (pre-market vs after-hours)
    features["report_time"] = earnings.get("report_time")
    
    # Straddle returns from UW (actual performance of vol trades)
    short_straddle_1d = earnings.get("short_straddle_1d")
    if short_straddle_1d is not None:
        try:
            features["short_straddle_return"] = float(short_straddle_1d) * 100
        except (ValueError, TypeError):
            pass
    
    return features


def _find_iv_at_date(
    vol_history: List[Dict[str, Any]],
    target_date: datetime,
    days_before: int = 3
) -> Optional[float]:
    """Find IV at or near a specific date (configurable window)."""
    if not vol_history or not target_date:
        return None
    
    best_match = None
    best_diff = float('inf')
    
    for record in vol_history:
        date_str = record.get("date") or record.get("timestamp")
        if not date_str:
            continue
        
        try:
            record_date = datetime.fromisoformat(date_str.replace("Z", "+00:00").split("T")[0])
            days_diff = (target_date - record_date).days
            
            # Look for data within the configurable window before earnings
            if 0 <= days_diff <= days_before:
                if days_diff < best_diff:
                    best_diff = days_diff
                    # Try to get IV or IV rank
                    iv = record.get("iv") or record.get("implied_volatility")
                    if iv:
                        try:
                            best_match = float(iv)
                        except:
                            pass
        except:
            continue
    
    return best_match


def _compute_historical_stats(
    earnings_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute aggregate statistics from historical earnings.
    
    Handles both EPS beat/miss data and vol crush data from UW.
    """
    if not earnings_data:
        return {}
    
    # EPS stats
    beat_count = 0
    total_with_eps = 0
    surprise_pcts = []
    
    # Vol crush stats (from UW)
    vol_crush_count = 0
    total_with_vol_data = 0
    expected_moves = []
    actual_moves = []
    short_straddle_returns = []
    
    for e in earnings_data:
        # EPS data
        if "eps_beat" in e:
            total_with_eps += 1
            if e["eps_beat"]:
                beat_count += 1
        if "eps_surprise_pct" in e:
            surprise_pcts.append(e["eps_surprise_pct"])
        
        # Vol data (from UW)
        if "vol_crush" in e:
            total_with_vol_data += 1
            if e["vol_crush"]:
                vol_crush_count += 1
        if "expected_move_pct" in e:
            expected_moves.append(e["expected_move_pct"])
        if "actual_move_pct" in e:
            actual_moves.append(e["actual_move_pct"])
        if "short_straddle_return" in e:
            short_straddle_returns.append(e["short_straddle_return"])
    
    stats = {
        "quarters_analyzed": len(earnings_data),
        "quarters_with_eps_data": total_with_eps,
        "quarters_with_vol_data": total_with_vol_data,
    }
    
    # EPS stats
    if total_with_eps > 0:
        stats["eps_beat_count"] = beat_count
        stats["eps_beat_rate"] = beat_count / total_with_eps
    
    if surprise_pcts:
        stats["avg_eps_surprise_pct"] = round(np.mean(surprise_pcts), 2)
        stats["median_eps_surprise_pct"] = round(np.median(surprise_pcts), 2)
    
    # Vol crush stats (KEY for options trading)
    if total_with_vol_data > 0:
        stats["vol_crush_count"] = vol_crush_count
        stats["vol_crush_rate"] = round(vol_crush_count / total_with_vol_data, 2)
    
    if expected_moves and actual_moves:
        stats["avg_expected_move_pct"] = round(np.mean(expected_moves), 2)
        stats["avg_actual_move_pct"] = round(np.mean(actual_moves), 2)
        stats["move_ratio"] = round(np.mean(actual_moves) / np.mean(expected_moves), 2) if np.mean(expected_moves) > 0 else None
    
    # Short straddle returns (actual performance of vol selling)
    if short_straddle_returns:
        stats["avg_short_straddle_return"] = round(np.mean(short_straddle_returns), 2)
        stats["short_straddle_win_rate"] = round(sum(1 for r in short_straddle_returns if r > 0) / len(short_straddle_returns), 2)
    
    return stats


def _compute_vol_crush_analysis(
    pre_earnings_ivs: List[float],
    current_iv: Optional[float]
) -> Dict[str, Any]:
    """Analyze IV patterns around earnings."""
    if not pre_earnings_ivs:
        return {}
    
    analysis = {
        "historical_pre_earnings_ivs": pre_earnings_ivs,
        "avg_pre_earnings_iv": np.mean(pre_earnings_ivs),
        "median_pre_earnings_iv": np.median(pre_earnings_ivs),
        "std_pre_earnings_iv": np.std(pre_earnings_ivs),
        "min_pre_earnings_iv": min(pre_earnings_ivs),
        "max_pre_earnings_iv": max(pre_earnings_ivs),
    }
    
    if current_iv is not None:
        # Where does current IV rank in historical pre-earnings IVs?
        percentile = scipy_stats.percentileofscore(pre_earnings_ivs, current_iv)
        z_score = (current_iv - analysis["avg_pre_earnings_iv"]) / (analysis["std_pre_earnings_iv"] + 1e-9)
        
        analysis["current_iv"] = current_iv
        analysis["current_percentile"] = round(percentile, 1)
        analysis["current_z_score"] = round(z_score, 2)
        analysis["current_vs_avg"] = "ABOVE" if current_iv > analysis["avg_pre_earnings_iv"] else "BELOW"
    
    return analysis


def _generate_strategy(
    vol_analysis: Dict[str, Any],
    earnings_stats: Dict[str, Any],
    current_vol_stats: Dict[str, Any],
    thresholds: Dict[str, float]
) -> Dict[str, Any]:
    """Generate trading strategy based on analysis with configurable thresholds."""
    strategy = {
        "signal": "NEUTRAL",
        "confidence": "LOW",
        "rationale": [],
        "ideas": [],
        "thresholds_used": thresholds
    }
    
    # Extract thresholds
    iv_pct_high = thresholds.get("iv_percentile_high", 75)
    iv_pct_low = thresholds.get("iv_percentile_low", 25)
    iv_rank_high = thresholds.get("iv_rank_high", 70)
    iv_rank_low = thresholds.get("iv_rank_low", 30)
    z_thresh = thresholds.get("z_score_threshold", 1.0)
    beat_strong = thresholds.get("beat_rate_strong", 0.75)
    beat_weak = thresholds.get("beat_rate_weak", 0.50)
    
    # Get current positioning data
    current_percentile = vol_analysis.get("current_percentile")
    current_z = vol_analysis.get("current_z_score")
    beat_rate = earnings_stats.get("eps_beat_rate")  # Updated field name
    
    # Get IV rank from current stats
    iv_rank = None
    if current_vol_stats:
        iv_rank = current_vol_stats.get("iv_rank") or current_vol_stats.get("ivRank")
        if iv_rank:
            try:
                iv_rank = float(iv_rank)
            except:
                iv_rank = None
    
    bullish_factors = 0
    bearish_factors = 0
    
    # Factor 1: Current IV percentile vs historical pre-earnings
    if current_percentile is not None:
        if current_percentile > iv_pct_high:
            strategy["rationale"].append(f"IV in {current_percentile:.0f}th percentile of pre-earnings history (>{iv_pct_high:.0f} threshold)")
            bullish_factors += 1  # High IV = sell vol opportunity
        elif current_percentile < iv_pct_low:
            strategy["rationale"].append(f"IV in {current_percentile:.0f}th percentile of pre-earnings history (<{iv_pct_low:.0f} threshold)")
            bearish_factors += 1  # Low IV = don't sell vol
    
    # Factor 2: IV Rank
    if iv_rank is not None:
        if iv_rank > iv_rank_high:
            strategy["rationale"].append(f"IV Rank at {iv_rank:.0f} (>{iv_rank_high:.0f} threshold)")
            bullish_factors += 1
        elif iv_rank < iv_rank_low:
            strategy["rationale"].append(f"IV Rank at {iv_rank:.0f} (<{iv_rank_low:.0f} threshold)")
            bearish_factors += 1
    
    # Factor 3: Beat rate (EPS)
    if beat_rate is not None:
        if beat_rate > beat_strong:
            strategy["rationale"].append(f"Strong EPS beat rate: {beat_rate:.0%} (>{beat_strong:.0%} threshold)")
            bullish_factors += 0.5  # Consistent beater = less uncertainty
        elif beat_rate < beat_weak:
            strategy["rationale"].append(f"Weak EPS beat rate: {beat_rate:.0%} (<{beat_weak:.0%} threshold)")
            bearish_factors += 0.5
    
    # Factor 3b: Vol crush rate (from UW - MORE IMPORTANT for options)
    vol_crush_rate = earnings_stats.get("vol_crush_rate")
    if vol_crush_rate is not None:
        if vol_crush_rate > 0.65:  # >65% of the time, actual move < expected
            strategy["rationale"].append(f"High vol crush rate: {vol_crush_rate:.0%} (actual < expected move)")
            bullish_factors += 1.5  # Strong signal for selling vol
        elif vol_crush_rate < 0.40:  # <40% - moves often exceed expectations
            strategy["rationale"].append(f"Low vol crush rate: {vol_crush_rate:.0%} (moves often exceed expectations)")
            bearish_factors += 1.5
    
    # Factor 3c: Historical short straddle returns (actual money data!)
    avg_straddle_return = earnings_stats.get("avg_short_straddle_return")
    if avg_straddle_return is not None:
        if avg_straddle_return > 20:  # Average >20% return on short straddles
            strategy["rationale"].append(f"Historical short straddle avg return: +{avg_straddle_return:.0f}%")
            bullish_factors += 1
        elif avg_straddle_return < -10:  # Average <-10% loss
            strategy["rationale"].append(f"Historical short straddle avg return: {avg_straddle_return:.0f}%")
            bearish_factors += 1
    
    # Factor 4: Z-score
    if current_z is not None and abs(current_z) > z_thresh:
        if current_z > z_thresh:
            strategy["rationale"].append(f"Current IV is {current_z:.1f}σ above historical mean (>{z_thresh}σ threshold)")
            bullish_factors += 1
        elif current_z < -z_thresh:
            strategy["rationale"].append(f"Current IV is {abs(current_z):.1f}σ below historical mean (>{z_thresh}σ threshold)")
            bearish_factors += 1
    
    # Determine signal
    net_score = bullish_factors - bearish_factors
    
    if net_score >= 2:
        strategy["signal"] = "SELL_VOL"
        strategy["confidence"] = "HIGH" if net_score >= 3 else "MEDIUM"
        strategy["ideas"] = [
            "Iron Condor - defined risk, benefits from vol crush",
            "Short Straddle - max premium capture if confident in range",
            "Put Credit Spread - bullish bias with vol sell",
            "Jade Lizard - upside call + put spread"
        ]
    elif net_score <= -2:
        strategy["signal"] = "BUY_VOL"
        strategy["confidence"] = "HIGH" if net_score <= -3 else "MEDIUM"
        strategy["ideas"] = [
            "Long Straddle - if expecting big move",
            "Long Strangle - cheaper, needs bigger move",
            "Calendar Spread - if term structure favorable",
            "Back Ratio - leveraged vol play"
        ]
    else:
        strategy["signal"] = "NEUTRAL"
        strategy["confidence"] = "LOW"
        strategy["ideas"] = [
            "Wait for better setup",
            "Small position if trading",
            "Consider post-earnings play instead"
        ]
        if not strategy["rationale"]:
            strategy["rationale"].append("No strong directional vol signal")
    
    strategy["factor_score"] = {
        "bullish": bullish_factors,
        "bearish": bearish_factors,
        "net": net_score
    }
    
    return strategy


def _build_earnings_chart(
    earnings_data: List[Dict[str, Any]],
    ticker: str
) -> Optional[Dict[str, Any]]:
    """Build a comprehensive earnings chart - ALWAYS produces something."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        logger.info(f"[CHART DEBUG] Building earnings chart for {ticker}, input records: {len(earnings_data)}")
        
        if not earnings_data:
            logger.warning(f"[CHART DEBUG] No earnings data provided!")
            return None
        
        # Debug: log what fields each record has
        sample = earnings_data[0]
        logger.info(f"[CHART DEBUG] Sample record keys: {list(sample.keys())}")
        logger.info(f"[CHART DEBUG] Sample record: {sample}")
        
        # Filter to records with vol move data (expected_move_pct and actual_move_pct)
        vol_data = [e for e in earnings_data if e.get("date") and "expected_move_pct" in e and "actual_move_pct" in e]
        
        # Also collect EPS surprise data
        eps_data = [e for e in earnings_data if e.get("date") and "eps_surprise_pct" in e]
        
        # Collect short straddle data
        straddle_data = [e for e in earnings_data if e.get("date") and "short_straddle_return" in e]
        
        # Collect any record with a date (fallback)
        any_data = [e for e in earnings_data if e.get("date")]
        
        logger.info(f"[CHART DEBUG] Records with vol data: {len(vol_data)}, EPS: {len(eps_data)}, Straddle: {len(straddle_data)}, Any: {len(any_data)}")
        
        # Simple color scheme
        GREEN = "#3fb950"
        RED = "#f85149"
        PURPLE = "#a371f7"
        
        # Build comprehensive chart with vol data and straddle returns
        if len(vol_data) >= 2 or len(straddle_data) >= 2:
            # Decide on layout based on available data
            has_vol = len(vol_data) >= 2
            has_straddle = len(straddle_data) >= 2
            
            if has_vol and has_straddle:
                fig = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=True,
                    vertical_spacing=0.15,
                    subplot_titles=(
                        f"<b>{ticker}</b> Expected vs Actual Earnings Move",
                        f"<b>{ticker}</b> Short Straddle Returns"
                    ),
                    row_heights=[0.6, 0.4]
                )
            else:
                fig = make_subplots(rows=1, cols=1)
            
            # === SUBPLOT 1: Expected vs Actual Move ===
            if has_vol:
                valid_vol = sorted(vol_data, key=lambda x: x["date"])
                dates = [e["date"].strftime("%b %Y") for e in valid_vol]
                expected = [e["expected_move_pct"] for e in valid_vol]
                actual = [e["actual_move_pct"] for e in valid_vol]
                
                # Color based on vol crush (green if actual < expected)
                colors = [GREEN if a < e else RED for a, e in zip(actual, expected)]

                # Expected move bars
                fig.add_trace(go.Bar(
                    x=dates,
                    y=expected,
                    name="Expected (IV)",
                    marker_color=PURPLE,
                    opacity=0.7,
                    hovertemplate="Expected: %{y:.1f}%<extra></extra>"
                ), row=1, col=1)

                # Actual move bars
                fig.add_trace(go.Bar(
                    x=dates,
                    y=actual,
                    name="Actual Move",
                    marker_color=colors,
                    hovertemplate="Actual: %{y:.1f}%<extra></extra>"
                ), row=1, col=1)

                # Add vol crush rate annotation
                vol_crush_pct = sum(1 for a, e in zip(actual, expected) if a < e) / len(actual) * 100
                fig.add_annotation(
                    x=0.02, y=0.98, xref="paper", yref="paper",
                    text=f"Vol Crush Rate: {vol_crush_pct:.0f}%",
                    showarrow=False,
                    font=dict(size=12),
                    bgcolor="white",
                    bordercolor=GREEN if vol_crush_pct > 50 else RED,
                    borderwidth=2
                )
            
            # === SUBPLOT 2: Short Straddle Returns ===
            if has_straddle and has_vol:
                valid_straddle = sorted(straddle_data, key=lambda x: x["date"])
                straddle_dates = [e["date"].strftime("%b %Y") for e in valid_straddle]
                returns = [e["short_straddle_return"] for e in valid_straddle]
                
                straddle_colors = [GREEN if r > 0 else RED for r in returns]

                fig.add_trace(go.Bar(
                    x=straddle_dates,
                    y=returns,
                    name="Straddle Return",
                    marker_color=straddle_colors,
                    hovertemplate="Return: %{y:+.1f}%<extra></extra>"
                ), row=2, col=1)

                # Add zero line
                fig.add_hline(y=0, line_dash="solid", line_color="gray", row=2, col=1)

                # Add win rate annotation
                win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
                avg_return = sum(returns) / len(returns)
                fig.add_annotation(
                    x=0.02, y=0.42, xref="paper", yref="paper",
                    text=f"Win Rate: {win_rate:.0f}% | Avg: {avg_return:+.1f}%",
                    showarrow=False,
                    font=dict(size=12),
                    bgcolor="white",
                    bordercolor=GREEN if win_rate > 50 else RED,
                    borderwidth=2
                )

                fig.update_yaxes(title_text="Return %", row=2, col=1)
            
            # Layout
            fig.update_layout(
                height=650 if has_straddle and has_vol else 450,
                barmode='group',
                showlegend=True,
                hovermode="closest",
                template="plotly_white"
            )

            fig.update_yaxes(title_text="Move %", row=1, col=1)
            fig.update_xaxes(tickangle=-45)
            
            return fig.to_dict()
            
        elif len(eps_data) >= 2:
            # Fallback to EPS surprise chart
            valid_data = sorted(eps_data, key=lambda x: x["date"])

            dates = [e["date"].strftime("%b %Y") for e in valid_data]
            surprises = [e["eps_surprise_pct"] for e in valid_data]
            colors = [GREEN if s >= 0 else RED for s in surprises]

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=dates,
                y=surprises,
                marker_color=colors,
                name="EPS Surprise %",
                hovertemplate="Surprise: %{y:+.1f}%<extra></extra>"
            ))

            # Add beat rate annotation
            beat_rate = sum(1 for s in surprises if s >= 0) / len(surprises) * 100
            fig.add_annotation(
                x=0.02, y=0.98, xref="paper", yref="paper",
                text=f"Beat Rate: {beat_rate:.0f}%",
                showarrow=False,
                font=dict(size=12),
                bgcolor="white",
                bordercolor=GREEN if beat_rate > 50 else RED,
                borderwidth=2
            )

            fig.add_hline(y=0, line_dash="solid", line_color="gray")

            fig.update_layout(
                title=f"{ticker} EPS Surprises",
                height=450,
                showlegend=False,
                template="plotly_white"
            )

            fig.update_xaxes(title_text="Earnings Date", tickangle=-45)
            fig.update_yaxes(title_text="EPS Surprise %")
            
            return fig.to_dict()
        
        # FALLBACK: Simple beat/miss chart
        elif len(any_data) >= 1:
            logger.info(f"[CHART DEBUG] Using fallback chart with {len(any_data)} records")
            valid_data = sorted(any_data, key=lambda x: x["date"])

            dates = [e["date"].strftime("%b %Y") for e in valid_data]

            # Get beat/miss
            beats = []
            for e in valid_data:
                if "eps_beat" in e:
                    beats.append(1 if e["eps_beat"] else -1)
                elif "eps_surprise_pct" in e:
                    beats.append(1 if e["eps_surprise_pct"] >= 0 else -1)
                else:
                    beats.append(0)

            colors = [GREEN if b > 0 else RED if b < 0 else "gray" for b in beats]
            labels = ["Beat" if b > 0 else "Miss" if b < 0 else "?" for b in beats]

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=dates,
                y=[abs(b) if b != 0 else 0.5 for b in beats],
                marker_color=colors,
                text=labels,
                textposition="inside",
                hovertemplate="%{text}<extra></extra>"
            ))

            beat_count = sum(1 for b in beats if b > 0)
            beat_rate = beat_count / len([b for b in beats if b != 0]) * 100 if any(b != 0 for b in beats) else 0

            fig.update_layout(
                title=f"{ticker} Earnings (Beat Rate: {beat_rate:.0f}%)",
                height=400,
                showlegend=False,
                yaxis=dict(showticklabels=False, showgrid=False),
                template="plotly_white"
            )

            fig.update_xaxes(title_text="Earnings Date", tickangle=-45)
            
            return fig.to_dict()
        
        logger.warning(f"[CHART DEBUG] No valid data at all for chart")
        return None
        
    except Exception as e:
        logger.error(f"[CHART DEBUG] Error building earnings chart: {e}", exc_info=True)
        return None


# =============================================================================
# MAIN TOOL
# =============================================================================

async def analyze_earnings_patterns_internal(
    ticker: str,
    lookback_quarters: int = 8,
    vol_history_timeframe: str = "1Y",
    days_before_earnings: int = 3,
    iv_percentile_high: float = 75.0,
    iv_percentile_low: float = 25.0,
    iv_rank_high: float = 70.0,
    iv_rank_low: float = 30.0,
    z_score_threshold: float = 1.0,
    beat_rate_strong: float = 0.75,
    beat_rate_weak: float = 0.50,
    include_chart: bool = True,
    include_historical_detail: bool = True
) -> Dict[str, Any]:
    """
    Analyze historical earnings patterns to identify vol trading opportunities.
    
    Fetches historical earnings data, analyzes IV patterns around each event,
    and generates strategy recommendations based on where current IV sits
    relative to historical pre-earnings levels.
    
    All computation is stateless - data fetched and analyzed fresh each call.
    All thresholds are configurable - no hardcoded rules.
    
    Args:
        ticker: Stock symbol to analyze
        lookback_quarters: Number of historical quarters to analyze (default 8)
        vol_history_timeframe: Timeframe for vol history fetch - "1M", "3M", "6M", "1Y", "2Y" (default "1Y")
        days_before_earnings: How many days before earnings to look for IV data (default 3)
        iv_percentile_high: Percentile threshold for "high" IV vs history (default 75)
        iv_percentile_low: Percentile threshold for "low" IV vs history (default 25)
        iv_rank_high: IV Rank threshold considered elevated (default 70)
        iv_rank_low: IV Rank threshold considered depressed (default 30)
        z_score_threshold: Z-score magnitude to consider significant (default 1.0)
        beat_rate_strong: Beat rate considered "strong" for confidence (default 0.75)
        beat_rate_weak: Beat rate considered "weak" (default 0.50)
        include_chart: Whether to generate visualization (default True)
        include_historical_detail: Whether to include per-quarter breakdown (default True)
    
    Returns:
        Comprehensive earnings analysis with:
        - historical_stats: Beat rate, surprise stats
        - vol_analysis: Historical pre-earnings IV vs current
        - strategy: Signal (SELL_VOL/BUY_VOL/NEUTRAL), confidence, trade ideas
        - charts: Optional visualization
    
    Example:
        # Basic analysis
        analyze_earnings_patterns("AAPL")
        
        # More historical data, tighter thresholds
        analyze_earnings_patterns("NVDA", lookback_quarters=12, iv_percentile_high=80, iv_rank_high=75)
        
        # Looser thresholds for volatile names
        analyze_earnings_patterns("TSLA", iv_percentile_high=60, z_score_threshold=0.75)
    
    Strategy Logic (all thresholds configurable):
        - Current IV percentile > iv_percentile_high → SELL_VOL signal
        - Current IV percentile < iv_percentile_low → BUY_VOL signal
        - IV Rank > iv_rank_high → adds to sell conviction
        - Beat rate > beat_rate_strong → adds to sell conviction
        - Z-score > z_score_threshold → confirms signal
    """
    
    # Initialize UW servers for vol data
    options_server = None
    market_server = None
    
    try:
        options_server = UWOptionsServer()
        market_server = UWMarketServer()
        
        await options_server.connect()
        await market_server.connect()
    except Exception as e:
        logger.warning(f"UW server init failed: {e} - will use FMP only")
    
    try:
        # Build thresholds dict for strategy generation
        thresholds = {
            "iv_percentile_high": iv_percentile_high,
            "iv_percentile_low": iv_percentile_low,
            "iv_rank_high": iv_rank_high,
            "iv_rank_low": iv_rank_low,
            "z_score_threshold": z_score_threshold,
            "beat_rate_strong": beat_rate_strong,
            "beat_rate_weak": beat_rate_weak,
        }
        
        # Fetch EPS from FMP (Non-GAAP - accurate for beat/miss)
        fmp_eps = await _fetch_fmp_earnings(ticker, limit=lookback_quarters + 4)
        
        # Fetch vol metrics from UW (expected move, actual move, straddle returns)
        uw_vol = []
        if market_server:
            uw_vol = await _fetch_uw_vol_data(market_server, ticker)
        
        # Fetch vol history and current stats from UW
        vol_history = []
        current_vol_stats = {}
        if options_server:
            vol_history = await _fetch_volatility_history(options_server, ticker, vol_history_timeframe)
            current_vol_stats = await _fetch_current_vol_stats(options_server, ticker)
        
        # Merge FMP EPS + UW vol data
        merged_earnings = await _merge_earnings_data(fmp_eps, uw_vol)
        
        if not merged_earnings and not fmp_eps:
            return {
                "status": "error",
                "error": f"No earnings data found for {ticker}",
                "hint": "Check FMP_API_KEY and ticker symbol"
            }
        
        # Process merged earnings data
        earnings_processed = []
        for e in merged_earnings[:lookback_quarters]:
            features = _extract_earnings_features(e)
            
            # Skip future earnings in historical analysis
            if features.get("is_future"):
                continue
                
            if features.get("date"):
                # Try to find IV at that date (using configurable window)
                iv_at_earnings = _find_iv_at_date(vol_history, features["date"], days_before_earnings)
                if iv_at_earnings:
                    features["pre_earnings_iv"] = iv_at_earnings
                earnings_processed.append(features)
        
        if not earnings_processed:
            return {
                "status": "error",
                "error": f"Could not process earnings data for {ticker}",
                "hint": "EPS data from FMP may be empty or format unexpected"
            }
        
        # Compute statistics
        earnings_stats = _compute_historical_stats(earnings_processed)
        
        # Vol analysis
        pre_earnings_ivs = [e["pre_earnings_iv"] for e in earnings_processed if "pre_earnings_iv" in e]
        current_iv = None
        if current_vol_stats:
            current_iv = current_vol_stats.get("iv") or current_vol_stats.get("implied_volatility")
            if current_iv:
                try:
                    current_iv = float(current_iv)
                except:
                    current_iv = None
        
        vol_analysis = _compute_vol_crush_analysis(pre_earnings_ivs, current_iv)
        
        # Generate strategy with configurable thresholds
        strategy = _generate_strategy(vol_analysis, earnings_stats, current_vol_stats, thresholds)
        
        # Check for upcoming earnings
        next_earnings = None
        for e in merged_earnings:
            if e.get("is_future") or (e.get("expected_move_perc") and not e.get("eps_actual")):
                next_earnings = {
                    "date": e.get("date"),
                    "expected_move_pct": round(float(e.get("expected_move_perc", 0)) * 100, 2) if e.get("expected_move_perc") else None,
                    "report_time": e.get("report_time")
                }
                break
        
        # Build response
        response = {
            "status": "success",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "data_sources": {
                "eps_data": "FMP (Non-GAAP - what analysts estimate against)",
                "vol_data": "Unusual Whales (expected move, actual move, straddle returns)",
                "fmp_records": len(fmp_eps),
                "uw_vol_records": len(uw_vol),
                "merged_records": len(merged_earnings)
            },
            "next_earnings": next_earnings,
            "config": {
                "lookback_quarters": lookback_quarters,
                "quarters_found": len(earnings_processed),
                "vol_history_timeframe": vol_history_timeframe,
                "days_before_earnings": days_before_earnings,
                "thresholds": thresholds
            },
            "historical_stats": earnings_stats,
            "vol_analysis": {
                "pre_earnings_iv_count": len(pre_earnings_ivs),
                "avg_pre_earnings_iv": vol_analysis.get("avg_pre_earnings_iv"),
                "current_iv": vol_analysis.get("current_iv"),
                "current_percentile": vol_analysis.get("current_percentile"),
                "current_z_score": vol_analysis.get("current_z_score"),
                "current_vs_avg": vol_analysis.get("current_vs_avg"),
            },
            "current_vol_snapshot": {
                "iv_rank": current_vol_stats.get("iv_rank") or current_vol_stats.get("ivRank"),
                "iv": current_vol_stats.get("iv"),
                "rv": current_vol_stats.get("rv") or current_vol_stats.get("hv"),
            },
            "strategy": strategy,
        }
        
        # Add historical detail if requested
        if include_historical_detail:
            response["historical_detail"] = [
                {
                    "date": e["date"].strftime("%Y-%m-%d") if e.get("date") else None,
                    "eps_beat": e.get("eps_beat"),
                    "eps_surprise_pct": round(e["eps_surprise_pct"], 2) if "eps_surprise_pct" in e else None,
                    "pre_earnings_iv": round(e["pre_earnings_iv"], 4) if "pre_earnings_iv" in e else None,
                    "expected_move_pct": round(e["expected_move_pct"], 2) if "expected_move_pct" in e else None,
                    "actual_move_pct": round(e["actual_move_pct"], 2) if "actual_move_pct" in e else None,
                    "vol_crush": e.get("vol_crush"),
                    "short_straddle_return": round(e["short_straddle_return"], 2) if "short_straddle_return" in e else None,
                }
                for e in earnings_processed
            ]
        
        # Add chart - ALWAYS try to build one
        if include_chart:
            logger.info(f"[CHART DEBUG] ===== CHART BUILDING START =====")
            logger.info(f"[CHART DEBUG] Processed records: {len(earnings_processed)}")
            
            # Log what data we have for charting
            for i, e in enumerate(earnings_processed[:3]):
                logger.info(f"[CHART DEBUG] Record {i}: date={e.get('date')}, eps_beat={e.get('eps_beat')}, eps_surprise={e.get('eps_surprise_pct')}, exp_move={e.get('expected_move_pct')}, act_move={e.get('actual_move_pct')}")
            
            chart = _build_earnings_chart(earnings_processed, ticker)
            
            if chart:
                logger.info(f"[CHART DEBUG] Chart built successfully! Type: {type(chart)}")
                try:
                    charts_wrapped = wrap_plotly_charts(
                        [chart],
                        f"earnings_{ticker.lower()}"
                    )
                    response["charts"] = charts_wrapped
                    logger.info(f"[CHART DEBUG] Chart wrapped and added to response: {len(charts_wrapped)} chart(s)")
                except Exception as wrap_err:
                    logger.error(f"[CHART DEBUG] Error wrapping chart: {wrap_err}", exc_info=True)
            else:
                logger.warning(f"[CHART DEBUG] Chart was None - _build_earnings_chart returned None")
            
            logger.info(f"[CHART DEBUG] ===== CHART BUILDING END =====")
        
        # Cleanup
        if options_server:
            await options_server.cleanup()
        if market_server:
            await market_server.cleanup()
        
        return response
        
    except Exception as e:
        logger.error(f"Error in earnings pattern analysis: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        try:
            if options_server:
                await options_server.cleanup()
            if market_server:
                await market_server.cleanup()
        except:
            pass


@function_tool
async def analyze_earnings_patterns(
    ticker: str,
    lookback_quarters: int = 8,
    vol_history_timeframe: str = "1Y",
    days_before_earnings: int = 3,
    iv_percentile_high: float = 75.0,
    iv_percentile_low: float = 25.0,
    iv_rank_high: float = 70.0,
    iv_rank_low: float = 30.0,
    z_score_threshold: float = 1.0,
    beat_rate_strong: float = 0.75,
    beat_rate_weak: float = 0.50,
    include_chart: bool = True,
    include_historical_detail: bool = True
) -> Dict[str, Any]:
    """
    Analyze historical earnings patterns to identify vol trading opportunities.
    
    Fetches historical earnings data, analyzes IV patterns around each event,
    and generates strategy recommendations.
    """
    return await analyze_earnings_patterns_internal(
        ticker=ticker,
        lookback_quarters=lookback_quarters,
        vol_history_timeframe=vol_history_timeframe,
        days_before_earnings=days_before_earnings,
        iv_percentile_high=iv_percentile_high,
        iv_percentile_low=iv_percentile_low,
        iv_rank_high=iv_rank_high,
        iv_rank_low=iv_rank_low,
        z_score_threshold=z_score_threshold,
        beat_rate_strong=beat_rate_strong,
        beat_rate_weak=beat_rate_weak,
        include_chart=include_chart,
        include_historical_detail=include_historical_detail,
    )
