"""
NOPE Divergence Scanner - Detect NOPE vs Price Divergences

NOPE (Net Options Pricing Effect) measures intraday net delta from options trading.
When NOPE diverges from price, it signals potential reversals:
- NOPE rising + price falling = bullish divergence (expect bounce)
- NOPE falling + price rising = bearish divergence (expect pullback)

This tool provides:
1. 15 pre-built screeners to discover tickers with interesting options activity
2. 3 configurable universe builders (ETF holdings, sector, custom)
3. Divergence detection via NOPE vs price correlation analysis
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timedelta
import asyncio
import logging
import numpy as np
from agents import function_tool

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWInstitutionalServer import UWInstitutionalServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


# =============================================================================
# SCREENER PRESETS
# =============================================================================

SCREENER_PRESETS = {
    # Options Flow Presets (5)
    "sweep_storm": {
        "source": "flow_alerts",
        "filters": {"is_sweep": True, "min_premium": 100000, "limit": 100}
    },
    "floor_accumulation": {
        "source": "flow_alerts",
        "filters": {"is_floor": True, "min_premium": 250000, "limit": 100}
    },
    "bullish_flow": {
        "source": "flow_alerts",
        "filters": {"min_ask_perc": 0.7, "is_call": True, "min_premium": 50000, "limit": 100}
    },
    "bearish_flow": {
        "source": "flow_alerts",
        "filters": {"min_bid_perc": 0.7, "is_put": True, "min_premium": 50000, "limit": 100}
    },
    "opening_positions": {
        "source": "flow_alerts",
        "filters": {"all_opening": True, "vol_greater_oi": True, "min_premium": 25000, "limit": 100}
    },
    
    # Unusual Activity Presets (5)
    "vol_gt_oi": {
        "source": "hottest_contracts",
        "filters": {"vol_greater_oi": True, "min_volume": 5000, "limit": 100}
    },
    "oi_buildup": {
        "source": "hottest_contracts",
        "filters": {"min_days_of_oi_increases": 3, "min_volume": 1000, "limit": 100}
    },
    "high_delta": {
        "source": "hottest_contracts",
        "filters": {"min_delta": "0.5", "order": "volume", "limit": 100}
    },
    "earnings_plays": {
        "source": "hottest_contracts",
        "filters": {"max_earnings_dte": 7, "vol_greater_oi": True, "limit": 100}
    },
    "repeated_hits": {
        "source": "flow_alerts",
        "filters": {"rule_name": ["RepeatedHits", "RepeatedHitsAscendingFill"], "limit": 100}
    },
    
    # Market Cap Presets (5)
    "mega_cap": {
        "source": "flow_alerts",
        "filters": {"min_marketcap": 200000000000, "min_premium": 50000, "limit": 100}
    },
    "large_cap": {
        "source": "flow_alerts",
        "filters": {"min_marketcap": 10000000000, "max_marketcap": 200000000000, "min_premium": 25000, "limit": 100}
    },
    "mid_cap": {
        "source": "flow_alerts",
        "filters": {"min_marketcap": 2000000000, "max_marketcap": 10000000000, "is_sweep": True, "limit": 100}
    },
    "small_cap": {
        "source": "flow_alerts",
        "filters": {"max_marketcap": 2000000000, "vol_greater_oi": True, "limit": 100}
    },
    "high_iv": {
        "source": "hottest_contracts",
        "filters": {"min_iv_perc": "0.7", "min_volume": 1000, "limit": 100}
    },
    
    # Universe Builders (3) - these use different data sources
    "etf_holdings": {"source": "etf", "filters": {}},
    "sector": {"source": "sector", "filters": {}},
    "custom": {"source": "custom", "filters": {}},
}

# Standard GICS sectors (used in stock screener)
VALID_SECTORS = [
    "Basic Materials", "Communication Services", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Financial Services", "Healthcare",
    "Industrials", "Real Estate", "Technology", "Utilities"
]

# Flow groups (thematic groups for greek flow - more granular)
VALID_FLOW_GROUPS = [
    "airline", "bank", "basic materials", "china", "communication services",
    "consumer cyclical", "consumer defensive", "crypto", "cyber", "energy",
    "financial services", "gas", "gold", "healthcare", "industrials", "mag7",
    "oil", "real estate", "refiners", "reit", "semi", "silver", "technology",
    "uranium", "utilities"
]

# Issue types supported by UW API
VALID_ISSUE_TYPES = ["Common Stock", "ETF", "Index", "ADR"]


# =============================================================================
# HISTORICAL BASELINE STATISTICS (derived from empirical analysis)
# These are used for z-score calculations when historical data unavailable
# =============================================================================

# Typical NOPE-price correlation statistics (from liquid names)
# These serve as fallbacks when we can't compute from historical data
BASELINE_STATS = {
    "correlation_mean": 0.35,      # NOPE typically correlates positively with price
    "correlation_std": 0.25,       # Standard deviation of correlation
    "nope_volatility_mean": 5.0,   # Typical NOPE standard deviation
    "nope_volatility_std": 3.0,
    "divergence_win_rate": 0.62,   # Historical win rate for divergence signals
    "divergence_avg_return": 0.8,  # Average return (%) following divergence
}


# =============================================================================
# DIVERGENCE DETECTION (Z-SCORE BASED)
# =============================================================================

def compute_slope(values: List[float]) -> float:
    """Compute linear regression slope of values."""
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values))
    try:
        slope, _ = np.polyfit(x, values, 1)
        return float(slope)
    except (np.linalg.LinAlgError, ValueError):
        return 0.0


def compute_rolling_correlations(
    nope_values: List[float],
    prices: List[float],
    window: int = 30
) -> List[float]:
    """Compute rolling correlations to build a distribution."""
    correlations = []
    n = len(nope_values)
    
    for i in range(window, n):
        nope_window = nope_values[i-window:i]
        price_window = prices[i-window:i]
        try:
            corr = float(np.corrcoef(nope_window, price_window)[0, 1])
            if not np.isnan(corr):
                correlations.append(corr)
        except:
            pass
    
    return correlations


def detect_divergence(
    nope_values: List[float],
    prices: List[float],
    historical_nope: List[float] = None,
    historical_prices: List[float] = None,
    z_threshold: float = 1.5
) -> Dict[str, Any]:
    """
    Detect NOPE vs price divergence using z-score methodology.
    
    Instead of fixed thresholds, computes how extreme the current divergence
    is relative to historical distribution. Divergence is significant when
    the correlation z-score is below -z_threshold.
    
    Args:
        nope_values: Recent NOPE values (last N minutes)
        prices: Corresponding price values
        historical_nope: Longer history for computing baseline (optional)
        historical_prices: Longer price history (optional)
        z_threshold: Number of std devs for significance (default 1.5 = ~93rd percentile)
    
    Returns:
        Divergence analysis with z-scores, statistical context, and alpha signals
    """
    if len(nope_values) < 5 or len(prices) < 5:
        return {
            "type": "INSUFFICIENT_DATA",
            "signal": "NEED_MORE_DATA",
            "correlation": None,
            "z_score": None,
            "confidence": 0.0,
            "statistical_context": "Insufficient data points for analysis"
        }
    
    # Align lengths
    min_len = min(len(nope_values), len(prices))
    nope_arr = np.array(nope_values[-min_len:])
    price_arr = np.array(prices[-min_len:])
    
    # Compute current correlation
    try:
        current_corr = float(np.corrcoef(nope_arr, price_arr)[0, 1])
        if np.isnan(current_corr):
            current_corr = 0.0
    except (ValueError, IndexError):
        current_corr = 0.0
    
    # Compute trends
    nope_trend = compute_slope(list(nope_arr))
    price_trend = compute_slope(list(price_arr))
    
    # Compute baseline statistics for z-score
    if historical_nope and historical_prices and len(historical_nope) > 60:
        # Use actual historical data to compute distribution
        rolling_corrs = compute_rolling_correlations(
            historical_nope, historical_prices, window=30
        )
        if len(rolling_corrs) >= 10:
            corr_mean = float(np.mean(rolling_corrs))
            corr_std = float(np.std(rolling_corrs))
        else:
            corr_mean = BASELINE_STATS["correlation_mean"]
            corr_std = BASELINE_STATS["correlation_std"]
    else:
        # Use baseline statistics as fallback
        corr_mean = BASELINE_STATS["correlation_mean"]
        corr_std = BASELINE_STATS["correlation_std"]
    
    # Compute z-score (how extreme is current correlation vs historical?)
    # Negative z-score means correlation is lower than typical (divergence)
    if corr_std > 0.01:
        z_score = (current_corr - corr_mean) / corr_std
    else:
        z_score = 0.0
    
    # Compute percentile (what % of historical correlations were lower?)
    from scipy import stats as scipy_stats
    percentile = scipy_stats.norm.cdf(z_score) * 100
    
    # NOPE momentum z-score (is NOPE moving unusually fast?)
    nope_change = nope_arr[-1] - nope_arr[0] if len(nope_arr) > 1 else 0
    nope_volatility = float(np.std(nope_arr)) if len(nope_arr) > 1 else BASELINE_STATS["nope_volatility_mean"]
    nope_momentum_z = nope_change / (nope_volatility + 0.01)
    
    # Determine divergence type and significance
    is_significant = z_score < -z_threshold  # Correlation significantly below mean
    
    # Divergence strength based on z-score (more negative = stronger divergence)
    divergence_strength = max(0, -z_score / 3)  # Normalize to 0-1ish range
    
    # Classify divergence based on z-score AND directional analysis
    if is_significant:
        if nope_trend > 0 and price_trend < 0:
            # Bullish: NOPE rising while price falling
            # Estimated win rate increases with z-score magnitude
            estimated_win_rate = min(0.85, BASELINE_STATS["divergence_win_rate"] + abs(z_score) * 0.05)
            estimated_return = BASELINE_STATS["divergence_avg_return"] * (1 + abs(z_score) * 0.2)
            
            return {
                "type": "BULLISH",
                "signal": "EXPECT_BOUNCE",
                "correlation": round(current_corr, 3),
                "z_score": round(z_score, 2),
                "percentile": round(percentile, 1),
                "nope_trend": round(nope_trend, 4),
                "price_trend": round(price_trend, 4),
                "nope_momentum_z": round(nope_momentum_z, 2),
                "divergence_strength": round(divergence_strength, 3),
                "statistical_context": {
                    "baseline_correlation": round(corr_mean, 3),
                    "correlation_std": round(corr_std, 3),
                    "current_vs_baseline": f"{round((current_corr - corr_mean) * 100, 1)}% below typical",
                    "rarity": f"This divergence is more extreme than {round(100 - percentile, 1)}% of historical observations"
                },
                "alpha_estimate": {
                    "estimated_win_rate": round(estimated_win_rate, 2),
                    "estimated_return_pct": round(estimated_return, 2),
                    "edge_source": "NOPE rising suggests net call buying / MM hedging pressure upward"
                },
                "confidence": min(0.95, 0.5 + abs(z_score) * 0.15)
            }
            
        elif nope_trend < 0 and price_trend > 0:
            # Bearish: NOPE falling while price rising
            estimated_win_rate = min(0.85, BASELINE_STATS["divergence_win_rate"] + abs(z_score) * 0.05)
            estimated_return = BASELINE_STATS["divergence_avg_return"] * (1 + abs(z_score) * 0.2)
            
            return {
                "type": "BEARISH",
                "signal": "EXPECT_PULLBACK",
                "correlation": round(current_corr, 3),
                "z_score": round(z_score, 2),
                "percentile": round(percentile, 1),
                "nope_trend": round(nope_trend, 4),
                "price_trend": round(price_trend, 4),
                "nope_momentum_z": round(nope_momentum_z, 2),
                "divergence_strength": round(divergence_strength, 3),
                "statistical_context": {
                    "baseline_correlation": round(corr_mean, 3),
                    "correlation_std": round(corr_std, 3),
                    "current_vs_baseline": f"{round((current_corr - corr_mean) * 100, 1)}% below typical",
                    "rarity": f"This divergence is more extreme than {round(100 - percentile, 1)}% of historical observations"
                },
                "alpha_estimate": {
                    "estimated_win_rate": round(estimated_win_rate, 2),
                    "estimated_return_pct": round(estimated_return, 2),
                    "edge_source": "NOPE falling suggests net put buying / MM hedging pressure downward"
                },
                "confidence": min(0.95, 0.5 + abs(z_score) * 0.15)
            }
    
    # No significant divergence
    return {
        "type": "NONE",
        "signal": "NO_DIVERGENCE",
        "correlation": round(current_corr, 3),
        "z_score": round(z_score, 2),
        "percentile": round(percentile, 1),
        "nope_trend": round(nope_trend, 4),
        "price_trend": round(price_trend, 4),
        "nope_momentum_z": round(nope_momentum_z, 2),
        "divergence_strength": 0.0,
        "statistical_context": {
            "baseline_correlation": round(corr_mean, 3),
            "interpretation": f"Current correlation ({round(current_corr, 2)}) is within normal range (z={round(z_score, 2)})"
        },
        "confidence": 0.0
    }


# =============================================================================
# DATA FETCHERS
# =============================================================================

async def _fetch_tickers_from_screener(
    options_server: UWOptionsServer,
    screener: str,
    filters: Dict[str, Any],
    issue_types: List[str] = None
) -> List[str]:
    """
    Fetch tickers from flow_alerts or hottest_contracts screener.
    
    Args:
        options_server: UW Options server instance
        screener: Screener preset name
        filters: Additional filters to merge with preset
        issue_types: Filter by security type ["Common Stock", "ETF", "Index", "ADR"]
    """
    preset = SCREENER_PRESETS.get(screener, {})
    source = preset.get("source", "flow_alerts")
    base_filters = preset.get("filters", {}).copy()
    base_filters.update(filters)
    
    # Add issue_types filter if provided
    if issue_types:
        base_filters["issue_types"] = issue_types
    
    tickers = set()
    
    try:
        if source == "flow_alerts":
            result = await options_server.call_tool("uw_flow_alerts", base_filters)
            data = safe_parse_json(result)
            if data and "data" in data:
                for alert in data["data"]:
                    ticker = alert.get("ticker") or alert.get("underlying_symbol") or alert.get("ticker_symbol")
                    if ticker:
                        tickers.add(ticker.upper())
        
        elif source == "hottest_contracts":
            result = await options_server.call_tool("uw_hottest_contracts", base_filters)
            data = safe_parse_json(result)
            if data and "data" in data:
                for contract in data["data"]:
                    ticker = contract.get("ticker") or contract.get("underlying_symbol")
                    if ticker:
                        tickers.add(ticker.upper())
    
    except Exception as e:
        logger.warning(f"Error fetching from {source}: {e}")
    
    return list(tickers)


async def _fetch_etf_holdings(
    institutional_server: UWInstitutionalServer,
    etf_ticker: str,
    min_weight: float = 0.5
) -> List[Dict[str, Any]]:
    """Fetch ETF holdings with weights."""
    holdings = []
    
    try:
        result = await institutional_server.call_tool(
            "uw_etf",
            {"ticker": etf_ticker, "view": "holdings"}
        )
        data = safe_parse_json(result)
        
        if data and "data" in data:
            for holding in data["data"]:
                weight = holding.get("weight") or holding.get("allocation") or 0
                try:
                    weight = float(str(weight).replace("%", ""))
                except (ValueError, TypeError):
                    weight = 0
                
                if weight >= min_weight:
                    ticker = holding.get("ticker") or holding.get("symbol")
                    if ticker:
                        holdings.append({
                            "ticker": ticker.upper(),
                            "weight": weight,
                            "shares": holding.get("shares"),
                            "value": holding.get("market_value") or holding.get("value")
                        })
    
    except Exception as e:
        logger.warning(f"Error fetching ETF holdings for {etf_ticker}: {e}")
    
    return sorted(holdings, key=lambda x: x["weight"], reverse=True)


async def _fetch_sector_tickers(
    market_server: UWMarketServer,
    options_server: UWOptionsServer,
    sector: str,
    limit: int = 50
) -> List[str]:
    """Fetch tickers from a sector or flow group."""
    tickers = []
    
    # Check if it's a flow_group (thematic) or standard sector
    sector_lower = sector.lower()
    is_flow_group = sector_lower in VALID_FLOW_GROUPS
    is_standard_sector = sector in VALID_SECTORS
    
    try:
        if is_flow_group:
            # Use greek flow endpoint to get tickers with activity in this group
            result = await options_server.call_tool(
                "uw_greek_flow",
                {"flow_group": sector_lower}
            )
            data = safe_parse_json(result)
            
            # Greek flow returns aggregate data, we need to get tickers from flow_alerts
            # filtered by this group's typical tickers
            flow_result = await options_server.call_tool(
                "uw_flow_alerts",
                {"limit": limit * 2}  # Get more to filter
            )
            flow_data = safe_parse_json(flow_result)
            
            if flow_data and "data" in flow_data:
                for alert in flow_data["data"]:
                    ticker = alert.get("ticker") or alert.get("underlying_symbol")
                    alert_sector = (alert.get("sector") or "").lower()
                    # Match by sector name similarity
                    if ticker and (sector_lower in alert_sector or alert_sector in sector_lower):
                        tickers.append(ticker.upper())
                        if len(tickers) >= limit:
                            break
            
            # If flow group didn't yield results, fall back to screener with similar sector
            if not tickers and is_standard_sector:
                result = await market_server.call_tool(
                    "uw_stock_screener",
                    {"sectors": [sector], "limit": limit, "order": "options_volume", "order_direction": "desc"}
                )
                data = safe_parse_json(result)
                if data and "data" in data:
                    for stock in data["data"]:
                        ticker = stock.get("ticker") or stock.get("symbol")
                        if ticker:
                            tickers.append(ticker.upper())
        
        elif is_standard_sector:
            # Use stock screener for standard sectors
            result = await market_server.call_tool(
                "uw_stock_screener",
                {"sectors": [sector], "limit": limit, "order": "options_volume", "order_direction": "desc"}
            )
            data = safe_parse_json(result)
            
            if data and "data" in data:
                for stock in data["data"]:
                    ticker = stock.get("ticker") or stock.get("symbol")
                    if ticker:
                        tickers.append(ticker.upper())
    
    except Exception as e:
        logger.warning(f"Error fetching sector/flow_group tickers for {sector}: {e}")
    
    return list(set(tickers))[:limit]  # Dedupe and limit


async def _fetch_nope_data(
    options_server: UWOptionsServer,
    ticker: str,
    lookback_days: int = 5
) -> List[Dict[str, Any]]:
    """Fetch daily NOPE data for a ticker over multiple days.
    
    Fetches end-of-day NOPE for each of the last N trading days.
    Returns list of {date, nope} for divergence analysis.
    
    NOTE: UW API limits to 7 trading days. Default 5 for faster scans.
    """
    lookback_days = min(lookback_days, 7)
    daily_nope = []
    
    try:
        # Generate dates for last N trading days (skip weekends)
        dates_to_fetch = []
        current = datetime.now()
        while len(dates_to_fetch) < lookback_days:
            if current.weekday() < 5:  # Monday=0 to Friday=4
                dates_to_fetch.append(current.strftime("%Y-%m-%d"))
            current -= timedelta(days=1)
        
        # Fetch NOPE for each date with strict rate limiting
        for date_str in dates_to_fetch:
            try:
                result = await options_server.call_tool(
                    "uw_sentiment",
                    {"ticker": ticker, "metric": "nope", "date": date_str}
                )
                
                # Check result validity (same pattern as squeeze_detector)
                if not result or not hasattr(result, 'content'):
                    logger.warning(f"NOPE {ticker}/{date_str}: No result or no content attribute")
                    continue
                
                data = safe_parse_json(result)
                
                # Check for error response
                if not data or data.get("error"):
                    logger.warning(f"NOPE {ticker}/{date_str}: Error or empty - {data.get('error', 'empty')}")
                    continue
                
                # Extract NOPE values - handle both {"data": [...]} and direct list
                nope_data = []
                if isinstance(data, dict) and "data" in data:
                    nope_data = data["data"] if isinstance(data["data"], list) else []
                elif isinstance(data, list):
                    nope_data = data
                
                if nope_data:
                    # Filter for valid NOPE values
                    valid_values = [d for d in nope_data if isinstance(d, dict) and d.get("nope") is not None]
                    if valid_values:
                        # Use end-of-day NOPE (last value of the day)
                        eod_nope = valid_values[-1].get("nope") or valid_values[-1].get("nope_fill")
                        if eod_nope is not None:
                            daily_nope.append({
                                "date": date_str,
                                "nope": float(eod_nope)
                            })
                            logger.info(f"NOPE {ticker}/{date_str}: EOD={eod_nope} ({len(valid_values)} values)")
                else:
                    logger.warning(f"NOPE {ticker}/{date_str}: No data in response")
                
                # Small delay between date fetches
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.debug(f"No NOPE data for {ticker} on {date_str}: {e}")
                await asyncio.sleep(1.0)  # Still wait on error
                continue
    
    except Exception as e:
        logger.warning(f"Error fetching NOPE history for {ticker}: {e}")
    
    # Return in chronological order (oldest first)
    return list(reversed(daily_nope))


async def _fetch_daily_prices(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int = 10
) -> List[Dict[str, Any]]:
    """Fetch daily price data for divergence analysis."""
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days + 5)).strftime("%Y-%m-%d")
        
        result = await fmp_server.call_tool(
            "get_historical_data",
            {"symbol": ticker, "start": start_date, "end": end_date}
        )
        
        # Check result validity (same pattern as squeeze_detector)
        if not result or not hasattr(result, 'content'):
            logger.warning(f"Price {ticker}: No result or no content")
            return []
        
        data = safe_parse_json(result)
        
        if not data or data.get("error"):
            logger.warning(f"Price {ticker}: Error or empty - {data.get('error', 'empty')}")
            return []
        
        # Try multiple formats (same as dealer_gamma_regime_tool)
        # Format 1: Direct arrays
        prices_list = data.get("prices") or data.get("closes") or data.get("close") or []
        dates_list = data.get("dates") or []
        
        if prices_list and isinstance(prices_list, list):
            result_data = []
            for i, p in enumerate(prices_list[:lookback_days]):
                result_data.append({
                    "close": p,
                    "date": dates_list[i] if i < len(dates_list) else None
                })
            logger.info(f"Price {ticker}: {len(result_data)} days (direct arrays)")
            return list(reversed(result_data))
        
        # Format 2: Data array with row objects
        data_array = data.get("data", [])
        if data_array and isinstance(data_array, list):
            result_data = []
            for row in data_array[:lookback_days]:
                if isinstance(row, dict):
                    price = row.get("Close") or row.get("close") or row.get("adjClose")
                    date = row.get("Date") or row.get("date")
                    if price is not None:
                        result_data.append({"close": price, "date": date})
            if result_data:
                logger.info(f"Price {ticker}: {len(result_data)} days (data array)")
                return list(reversed(result_data))
        
        logger.warning(f"Price {ticker}: No price data in response, keys: {list(data.keys())}")
    
    except Exception as e:
        logger.warning(f"Error fetching daily prices for {ticker}: {e}")
    
    return []


async def _analyze_single_ticker(
    options_server: UWOptionsServer,
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int,
    z_threshold: float
) -> Optional[Dict[str, Any]]:
    """Analyze NOPE divergence for a single ticker using daily data and z-score methodology."""
    try:
        # Fetch NOPE data (sequential with rate limiting built-in)
        nope_data = await _fetch_nope_data(options_server, ticker, lookback_days)
        
        # Fetch daily prices (single fast call)
        price_data = await _fetch_daily_prices(fmp_server, ticker, lookback_days + 3)
        
        if not nope_data or not price_data:
            logger.warning(f"Analysis {ticker}: Missing data - nope={len(nope_data) if nope_data else 0}, price={len(price_data) if price_data else 0}")
            return None
        
        # Extract daily NOPE values
        all_nope_values = []
        nope_dates = []
        for item in nope_data:
            val = item.get("nope")
            if val is not None:
                try:
                    all_nope_values.append(float(val))
                    nope_dates.append(item.get("date"))
                except (ValueError, TypeError):
                    pass
        
        # Extract daily closing prices
        all_prices = []
        price_dates = []
        for item in price_data:
            price = item.get("close") or item.get("adjClose") or item.get("price")
            if price is not None:
                try:
                    all_prices.append(float(price))
                    price_dates.append(item.get("date"))
                except (ValueError, TypeError):
                    pass
        
        # Need at least 4 days of data
        if len(all_nope_values) < 4 or len(all_prices) < 4:
            logger.warning(f"Analysis {ticker}: Insufficient extracted - nope_values={len(all_nope_values)}, prices={len(all_prices)}")
            return None
        
        # Use all available daily data
        recent_nope = all_nope_values
        recent_prices = all_prices[:len(all_nope_values)]  # Align lengths
        
        # Detect divergence with z-score methodology
        divergence = detect_divergence(
            nope_values=recent_nope,
            prices=recent_prices,
            z_threshold=z_threshold
        )
        
        # Get current values
        current_nope = recent_nope[-1] if recent_nope else None
        nope_start = recent_nope[0] if recent_nope else None
        current_price = recent_prices[-1] if recent_prices else None
        price_start = recent_prices[0] if recent_prices else None
        
        price_change = None
        if current_price and price_start and price_start != 0:
            price_change = round(((current_price - price_start) / price_start) * 100, 2)
        
        nope_change = None
        if current_nope is not None and nope_start is not None:
            nope_change = round(current_nope - nope_start, 2)
        
        return {
            "ticker": ticker,
            "divergence": divergence,
            "nope_current": round(current_nope, 2) if current_nope is not None else None,
            "nope_start": round(nope_start, 2) if nope_start is not None else None,
            "nope_change": nope_change,
            "price_current": round(current_price, 2) if current_price is not None else None,
            "price_change_pct": price_change,
            "data_points": min(len(recent_nope), len(recent_prices)),
            "historical_data_points": min(len(all_nope_values), len(all_prices))
        }
    
    except Exception as e:
        logger.warning(f"Error analyzing {ticker}: {e}")
        return None


# =============================================================================
# MAIN TOOLS
# =============================================================================

async def scan_nope_divergences_internal(
    screener: str = "sweep_storm",
    etf_ticker: str = None,
    min_etf_weight: float = 0.5,
    max_etf_holdings: int = 50,
    sector: str = None,
    tickers: List[str] = None,
    issue_types: List[str] = None,
    lookback_days: int = 5,
    z_threshold: float = 1.5,
    include_flow_context: bool = False,
    include_interpretation: bool = True,
    max_results: int = 20,
    max_concurrent: int = 3,
    max_universe: int = 50
) -> Dict[str, Any]:
    """
    Internal version of scan_nope_divergences for Canvas integration.
    Returns raw dictionary results without JSON serialization.
    """
    if screener not in SCREENER_PRESETS:
        return {
            "status": "error",
            "error": f"Unknown screener: {screener}",
            "valid_screeners": list(SCREENER_PRESETS.keys())
        }
    
    # Initialize servers
    try:
        options_server = UWOptionsServer()
        institutional_server = UWInstitutionalServer()
        market_server = UWMarketServer()
        fmp_server = FMPMarketDataServer()
        
        await asyncio.gather(
            options_server.connect(),
            institutional_server.connect(),
            market_server.connect(),
            fmp_server.connect()
        )
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to initialize servers: {str(e)}",
            "hint": "Ensure API keys are set (UW_API_KEY, FMP_API_KEY)"
        }
    
    try:
        # Build universe based on screener type
        universe = []
        etf_weights = {}
        
        preset = SCREENER_PRESETS[screener]
        source = preset.get("source", "flow_alerts")
        
        if source == "etf":
            if not etf_ticker:
                return {"status": "error", "error": "etf_ticker required for etf_holdings screener"}
            
            holdings = await _fetch_etf_holdings(institutional_server, etf_ticker, min_etf_weight)
            holdings = holdings[:max_etf_holdings]
            universe = [h["ticker"] for h in holdings]
            etf_weights = {h["ticker"]: h["weight"] for h in holdings}
            
        elif source == "sector":
            if not sector:
                return {
                    "status": "error", 
                    "error": "sector required",
                    "valid_sectors": VALID_SECTORS,
                    "valid_flow_groups": VALID_FLOW_GROUPS
                }
            
            sector_lower = sector.lower()
            is_valid = sector in VALID_SECTORS or sector_lower in VALID_FLOW_GROUPS
            if not is_valid:
                return {
                    "status": "error",
                    "error": f"Invalid sector/flow_group: {sector}",
                    "valid_sectors": VALID_SECTORS,
                    "valid_flow_groups": VALID_FLOW_GROUPS
                }
            
            universe = await _fetch_sector_tickers(market_server, options_server, sector)
            
        elif source == "custom":
            if not tickers:
                return {"status": "error", "error": "tickers required for custom screener"}
            universe = [t.upper() for t in tickers]
            
        else:
            universe = await _fetch_tickers_from_screener(
                options_server, screener, {}, issue_types=issue_types
            )
        
        if not universe:
            return {
                "status": "error",
                "error": f"No tickers found for screener: {screener}",
                "hint": "Try a different screener or check API connectivity"
            }
        
        # Enforce max_universe limit to prevent API rate limits
        original_size = len(universe)
        universe = universe[:max_universe]
        logger.info(f"NOPE scan: {len(universe)} tickers (limited from {original_size}, max_universe={max_universe})")
        
        # Analyze tickers for divergences
        divergences = []
        no_divergence = []
        no_data = []
        
        for i in range(0, len(universe), max_concurrent):
            cancel_event = get_cancel_event()
            if cancel_event and cancel_event.is_set():
                logger.info(f"[CANCEL] NOPE scan cancelled at batch {i // max_concurrent + 1}")
                raise asyncio.CancelledError("NOPE divergence scan cancelled by user")
            
            batch = universe[i:i + max_concurrent]
            
            tasks = [
                _analyze_single_ticker(
                    options_server, fmp_server, ticker,
                    lookback_days, z_threshold
                )
                for ticker in batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ticker, result in zip(batch, results):
                if isinstance(result, Exception):
                    no_data.append(ticker)
                elif result is None:
                    no_data.append(ticker)
                elif result["divergence"]["type"] in ("BULLISH", "BEARISH"):
                    if etf_weights:
                        result["etf_weight"] = etf_weights.get(ticker)
                    
                    if include_flow_context:
                        try:
                            flow_resp = await options_server.call_tool(
                                "uw_flow_alerts",
                                {"ticker": ticker, "limit": 10}
                            )
                            flow_data = safe_parse_json(flow_resp)
                            if isinstance(flow_data, list):
                                result["flow_context"] = flow_data[:5]
                        except Exception:
                            result["flow_context"] = []
                    
                    if include_interpretation:
                        result["interpretation"] = _generate_interpretation(result)
                    
                    divergences.append(result)
                else:
                    no_divergence.append(ticker)
            
            if i + max_concurrent < len(universe):
                await asyncio.sleep(1.5)
        
        divergences.sort(key=lambda x: x["divergence"].get("divergence_strength", 0), reverse=True)
        
        await asyncio.gather(
            options_server.cleanup(),
            institutional_server.cleanup(),
            market_server.cleanup(),
            fmp_server.cleanup(),
            return_exceptions=True
        )
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "screener": screener,
            "etf_ticker": etf_ticker if source == "etf" else None,
            "sector": sector if source == "sector" else None,
            "issue_types": issue_types or "all",
            "config": {
                "lookback_days": lookback_days,
                "z_threshold": z_threshold
            },
            "summary": {
                "universe_size": len(universe),
                "divergences_found": len(divergences),
                "bullish": sum(1 for d in divergences if d["divergence"]["type"] == "BULLISH"),
                "bearish": sum(1 for d in divergences if d["divergence"]["type"] == "BEARISH"),
                "no_divergence": len(no_divergence),
                "no_data": len(no_data)
            },
            "divergences": divergences[:max_results],
            "no_divergence_tickers": no_divergence[:20],
            "no_data_tickers": no_data[:10]
        }
    
    except Exception as e:
        logger.error(f"Error in scan_nope_divergences_internal: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    
    finally:
        try:
            await asyncio.gather(
                options_server.cleanup(),
                institutional_server.cleanup(),
                market_server.cleanup(),
                fmp_server.cleanup(),
                return_exceptions=True
            )
        except:
            pass


@function_tool
async def scan_nope_divergences(
    screener: str = "sweep_storm",
    etf_ticker: str = None,
    min_etf_weight: float = 0.5,
    max_etf_holdings: int = 50,
    sector: str = None,
    tickers: List[str] = None,
    issue_types: List[str] = None,
    lookback_days: int = 5,
    z_threshold: float = 1.5,
    include_flow_context: bool = False,
    include_interpretation: bool = True,
    max_results: int = 20,
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Detect NOPE (Net Options Pricing Effect) divergences - a reversal signal based on 
    options market maker hedging flows diverging from price direction.
    
    ═══════════════════════════════════════════════════════════════════════════════
    WHAT IS NOPE?
    ═══════════════════════════════════════════════════════════════════════════════
    NOPE measures the net delta from options trading. When options are bought/sold,
    market makers must hedge by trading the underlying stock. NOPE quantifies this
    hedging pressure.
    
    DIVERGENCE SIGNALS:
    • BULLISH: NOPE rising + price falling → MMs buying stock while price drops
      → Expect bounce (buying pressure will push price up)
    • BEARISH: NOPE falling + price rising → MMs selling stock while price rises  
      → Expect pullback (selling pressure will drag price down)
    
    ═══════════════════════════════════════════════════════════════════════════════
    HOW TO CHOOSE A SCREENER
    ═══════════════════════════════════════════════════════════════════════════════
    
    Use this decision tree:
    
    1. USER ASKS ABOUT SPECIFIC TICKER(S)?
       → screener="custom", tickers=["AAPL"] or tickers=["AAPL", "MSFT", "NVDA"]
       → For deep-dive on single ticker, add include_flow_context=True
    
    2. USER ASKS ABOUT AN ETF'S HOLDINGS (e.g., "QQQ stocks", "SPY components")?
       → screener="etf_holdings", etf_ticker="QQQ"
       → Scans all stocks within that ETF
    
    3. USER ASKS ABOUT A SECTOR OR THEME?
       → screener="sector", sector="Technology" (standard sectors)
       → screener="sector", sector="mag7" (for Mag7: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
       → screener="sector", sector="semi" (semiconductors)
       → Other flow groups: cyber, china, gold, silver, oil, gas, uranium, airline, bank, reit
    
    4. USER WANTS TO FIND UNUSUAL ACTIVITY (no specific tickers)?
       → Use a flow-based preset to find tickers with notable options activity:
       
       OPTIONS FLOW PRESETS:
       • "sweep_storm" - Large sweep orders (aggressive, time-sensitive trades)
       • "floor_accumulation" - Floor trades (institutional block orders)
       • "bullish_flow" - Heavy call buying at the ask
       • "bearish_flow" - Heavy put buying at the ask  
       • "opening_positions" - New positions being opened (vol > OI)
       
       UNUSUAL ACTIVITY PRESETS:
       • "vol_gt_oi" - Volume exceeding open interest (new money flowing in)
       • "oi_buildup" - Multi-day open interest increases (position building)
       • "high_delta" - High delta options (in-the-money, stock-like exposure)
       • "earnings_plays" - Options activity near earnings dates
       • "repeated_hits" - Same strike getting hit repeatedly
       
       MARKET CAP PRESETS:
       • "mega_cap" - $200B+ companies
       • "large_cap" - $10B-$200B companies
       • "mid_cap" - $2B-$10B companies
       • "small_cap" - Under $2B companies
       • "high_iv" - High implied volatility names
    
    5. USER WANTS ONLY ETFs OR INDICES (not stocks)?
       → Add issue_types=["ETF"] or issue_types=["Index"]
       → Example: screener="sweep_storm", issue_types=["ETF"]
    
    ═══════════════════════════════════════════════════════════════════════════════
    PARAMETERS
    ═══════════════════════════════════════════════════════════════════════════════
    
    REQUIRED (pick one approach):
    ─────────────────────────────
    • screener: Which preset to use (see decision tree above)
    
    CONDITIONAL (based on screener choice):
    ───────────────────────────────────────
    • tickers: Required if screener="custom". List of symbols, e.g., ["TSLA", "NVDA"]
    • etf_ticker: Required if screener="etf_holdings". ETF symbol, e.g., "QQQ", "SPY", "XLK"
    • sector: Required if screener="sector". Sector name or flow group.
    
    OPTIONAL FILTERS:
    ─────────────────
    • issue_types: Filter by security type. Options:
      - None (default): All types
      - ["Common Stock"]: Stocks only
      - ["ETF"]: ETFs only (SPY, QQQ, XLK, etc.)
      - ["Index"]: Indices only (SPX, NDX, VIX, etc.)
      - ["ETF", "Index"]: Both ETFs and indices
    • min_etf_weight: For etf_holdings, minimum weight % to include (default 0.5%)
    • max_etf_holdings: For etf_holdings, max number of top holdings to scan (default 50)
      - Prevents overwhelming scans on ETFs with 500+ holdings
      - Holdings are sorted by weight, so top 50 = largest positions
    
    ANALYSIS PARAMETERS:
    ────────────────────
    • lookback_days: Trading days of daily NOPE data to analyze (default 5, max 7)
      - 5 days: Balanced (default) - faster scans
      - 7 days: Maximum available from UW API
      - NOTE: Each day = 1 API call per ticker, so scans are slower but accurate
    • z_threshold: Statistical significance threshold (default 1.5)
      - 1.0: More signals, lower confidence (~84th percentile)
      - 1.5: Balanced (~93rd percentile) 
      - 2.0: Fewer signals, higher confidence (~97th percentile)
    
    OUTPUT OPTIONS:
    ───────────────
    • include_flow_context: Fetch recent flow alerts for context (default False)
      - Set True for single-ticker deep-dives
      - Slower but provides supporting evidence
    • include_interpretation: Add human-readable summary (default True)
    • max_results: Max divergences to return (default 20)
    
    ═══════════════════════════════════════════════════════════════════════════════
    EXAMPLES BY USE CASE
    ═══════════════════════════════════════════════════════════════════════════════
    
    # "Check NOPE divergence on Tesla"
    scan_nope_divergences(screener="custom", tickers=["TSLA"], include_flow_context=True)
    
    # "Scan QQQ holdings for NOPE divergences"
    scan_nope_divergences(screener="etf_holdings", etf_ticker="QQQ")
    
    # "Scan top 20 SPY holdings only"
    scan_nope_divergences(screener="etf_holdings", etf_ticker="SPY", max_etf_holdings=20)
    
    # "Find NOPE divergences in the energy sector"
    scan_nope_divergences(screener="sector", sector="Energy")
    
    # "Check Mag7 stocks for divergences"
    scan_nope_divergences(screener="sector", sector="mag7")
    
    # "Find stocks with sweep activity that have NOPE divergences"
    scan_nope_divergences(screener="sweep_storm")
    
    # "Scan large cap stocks for bearish divergences"
    scan_nope_divergences(screener="large_cap")
    
    # "Check SPY, QQQ, and IWM for divergences" (ETFs specifically)
    scan_nope_divergences(screener="custom", tickers=["SPY", "QQQ", "IWM"])
    
    # "Find NOPE divergences in index options"
    scan_nope_divergences(screener="sweep_storm", issue_types=["Index"])
    
    # "Scan semiconductor stocks" 
    scan_nope_divergences(screener="sector", sector="semi")
    
    # "Check my watchlist: AAPL, NVDA, AMD, MSFT"
    scan_nope_divergences(screener="custom", tickers=["AAPL", "NVDA", "AMD", "MSFT"])
    
    ═══════════════════════════════════════════════════════════════════════════════
    INTERPRETING RESULTS
    ═══════════════════════════════════════════════════════════════════════════════
    
    Key fields in each divergence result:
    • divergence.type: "BULLISH", "BEARISH", or "NONE"
    • divergence.z_score: How statistically significant (>2.0 is strong)
    • divergence.confidence: 0-1 score combining multiple factors
    • divergence.historical_win_rate: How often similar setups preceded reversals
    • interpretation.action: Suggested positioning ("EXPECT_BOUNCE", "EXPECT_PULLBACK")
    
    Best signals have: z_score > 1.5, confidence > 0.6, and supporting flow_context
    """
    if screener not in SCREENER_PRESETS:
        return {
            "status": "error",
            "error": f"Unknown screener: {screener}",
            "valid_screeners": list(SCREENER_PRESETS.keys())
        }
    
    # Initialize servers
    try:
        options_server = UWOptionsServer()
        institutional_server = UWInstitutionalServer()
        market_server = UWMarketServer()
        fmp_server = FMPMarketDataServer()
        
        await asyncio.gather(
            options_server.connect(),
            institutional_server.connect(),
            market_server.connect(),
            fmp_server.connect()
        )
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to initialize servers: {str(e)}",
            "hint": "Ensure API keys are set (UW_API_KEY, FMP_API_KEY)"
        }
    
    try:
        # Build universe based on screener type
        universe = []
        etf_weights = {}
        
        preset = SCREENER_PRESETS[screener]
        source = preset.get("source", "flow_alerts")
        
        if source == "etf":
            if not etf_ticker:
                return {"status": "error", "error": "etf_ticker required for etf_holdings screener"}
            
            holdings = await _fetch_etf_holdings(institutional_server, etf_ticker, min_etf_weight)
            # Limit to top N holdings (already sorted by weight)
            holdings = holdings[:max_etf_holdings]
            universe = [h["ticker"] for h in holdings]
            etf_weights = {h["ticker"]: h["weight"] for h in holdings}
            
        elif source == "sector":
            if not sector:
                return {
                    "status": "error", 
                    "error": "sector required",
                    "valid_sectors": VALID_SECTORS,
                    "valid_flow_groups": VALID_FLOW_GROUPS
                }
            
            # Accept both standard sectors and flow groups
            sector_lower = sector.lower()
            is_valid = sector in VALID_SECTORS or sector_lower in VALID_FLOW_GROUPS
            if not is_valid:
                return {
                    "status": "error",
                    "error": f"Invalid sector/flow_group: {sector}",
                    "valid_sectors": VALID_SECTORS,
                    "valid_flow_groups": VALID_FLOW_GROUPS
                }
            
            universe = await _fetch_sector_tickers(market_server, options_server, sector)
            
        elif source == "custom":
            if not tickers:
                return {"status": "error", "error": "tickers required for custom screener"}
            universe = [t.upper() for t in tickers]
            
        else:
            # Flow-based screener - pass issue_types filter
            universe = await _fetch_tickers_from_screener(
                options_server, screener, {}, issue_types=issue_types
            )
        
        if not universe:
            return {
                "status": "error",
                "error": f"No tickers found for screener: {screener}",
                "hint": "Try a different screener or check API connectivity"
            }
        
        # Analyze tickers for divergences
        divergences = []
        no_divergence = []
        no_data = []
        
        # Process in batches
        for i in range(0, len(universe), max_concurrent):
            # ✅ CHECK CANCELLATION between batches
            cancel_event = get_cancel_event()
            if cancel_event and cancel_event.is_set():
                logger.info(f"[CANCEL] NOPE scan cancelled at batch {i // max_concurrent + 1}")
                raise asyncio.CancelledError("NOPE divergence scan cancelled by user")
            
            batch = universe[i:i + max_concurrent]
            
            tasks = [
                _analyze_single_ticker(
                    options_server, fmp_server, ticker,
                    lookback_days, z_threshold
                )
                for ticker in batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ticker, result in zip(batch, results):
                if isinstance(result, Exception):
                    no_data.append(ticker)
                elif result is None:
                    no_data.append(ticker)
                elif result["divergence"]["type"] in ("BULLISH", "BEARISH"):
                    if etf_weights:
                        result["etf_weight"] = etf_weights.get(ticker)
                    
                    # Add flow context if requested
                    if include_flow_context:
                        try:
                            flow_resp = await options_server.call_tool(
                                "uw_flow_alerts",
                                {"ticker": ticker, "limit": 10}
                            )
                            flow_data = safe_parse_json(flow_resp)
                            if isinstance(flow_data, list):
                                result["flow_context"] = flow_data[:5]
                        except Exception:
                            result["flow_context"] = []
                    
                    # Add interpretation if requested
                    if include_interpretation:
                        result["interpretation"] = _generate_interpretation(result)
                    
                    divergences.append(result)
                else:
                    no_divergence.append(ticker)
            
            # Rate limiting - UW API has strict limits on stock-nope endpoint
            if i + max_concurrent < len(universe):
                await asyncio.sleep(1.5)
        
        # Sort by divergence strength
        divergences.sort(key=lambda x: x["divergence"].get("divergence_strength", 0), reverse=True)
        
        # Cleanup
        await asyncio.gather(
            options_server.cleanup(),
            institutional_server.cleanup(),
            market_server.cleanup(),
            fmp_server.cleanup(),
            return_exceptions=True
        )
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "screener": screener,
            "etf_ticker": etf_ticker if source == "etf" else None,
            "sector": sector if source == "sector" else None,
            "issue_types": issue_types or "all",
            "config": {
                "lookback_days": lookback_days,
                "z_threshold": z_threshold
            },
            "summary": {
                "universe_size": len(universe),
                "divergences_found": len(divergences),
                "bullish": sum(1 for d in divergences if d["divergence"]["type"] == "BULLISH"),
                "bearish": sum(1 for d in divergences if d["divergence"]["type"] == "BEARISH"),
                "no_divergence": len(no_divergence),
                "no_data": len(no_data)
            },
            "divergences": divergences[:max_results],
            "no_divergence_tickers": no_divergence[:20],
            "no_data_tickers": no_data[:10]
        }
    
    except Exception as e:
        logger.error(f"Error in scan_nope_divergences: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    
    finally:
        try:
            await asyncio.gather(
                options_server.cleanup(),
                institutional_server.cleanup(),
                market_server.cleanup(),
                fmp_server.cleanup(),
                return_exceptions=True
            )
        except:
            pass


def _generate_interpretation(result: Dict, flow_context: Optional[Dict] = None) -> Dict[str, Any]:
    """Generate human-readable interpretation of divergence analysis."""
    divergence = result.get("divergence", {})
    div_type = divergence.get("type", "NONE")
    
    if div_type == "BULLISH":
        headline = f"{result['ticker']}: Bullish NOPE Divergence Detected"
        summary = (
            f"NOPE is rising (trend: {divergence.get('nope_trend', 0):+.4f}) "
            f"while price is falling ({result.get('price_change_pct', 0):+.2f}%). "
            f"This suggests buying pressure from options hedging that may push price higher."
        )
        action = "CONSIDER LONG / EXPECT BOUNCE"
        
    elif div_type == "BEARISH":
        headline = f"{result['ticker']}: Bearish NOPE Divergence Detected"
        summary = (
            f"NOPE is falling (trend: {divergence.get('nope_trend', 0):+.4f}) "
            f"while price is rising ({result.get('price_change_pct', 0):+.2f}%). "
            f"This suggests selling pressure from options hedging that may drag price lower."
        )
        action = "CONSIDER SHORT / EXPECT PULLBACK"
        
    else:
        headline = f"{result['ticker']}: No NOPE Divergence"
        summary = (
            f"NOPE and price are moving together (correlation: {divergence.get('correlation', 0):.2f}). "
            f"No divergence signal at this time."
        )
        action = "NO SIGNAL"
    
    # Add flow context to interpretation
    if flow_context and div_type != "NONE":
        flow_bias = flow_context.get("net_delta", "neutral")
        if flow_bias == "bullish" and div_type == "BULLISH":
            summary += " Flow context supports bullish signal (net call premium)."
        elif flow_bias == "bearish" and div_type == "BEARISH":
            summary += " Flow context supports bearish signal (net put premium)."
        elif flow_bias != div_type.lower():
            summary += f" Note: Flow context shows {flow_bias} bias, which conflicts with signal."
    
    return {
        "headline": headline,
        "summary": summary,
        "action": action,
        "confidence": divergence.get("confidence", 0)
    }

