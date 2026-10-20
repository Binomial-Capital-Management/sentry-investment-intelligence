"""
GEX Alpha Signals Tool - Dealer Gamma Exposure Analysis

Extracts actionable signals from dealer gamma exposure:

1. KEY LEVELS (default): Put wall, call wall, zero gamma, max gamma
2. REGIME TRANSITION: Predicts volatility expansion/compression before it happens
3. FORCED FLOW: Quantifies $ dealers must trade per 1% move
4. PIN PROBABILITY: Likelihood price pins to max gamma by expiration
5. HISTORICAL CONTEXT (optional): GEX percentile, regime duration, transition risk

Philosophy:
----------
Dealers are FORCED participants. They must delta-hedge their short options.
This creates predictable, mechanical flows we can exploit:

- Positive GEX → Dealers buy dips, sell rips → Vol suppression
- Negative GEX → Dealers chase momentum → Vol amplification
- The TRANSITION between regimes is the alpha signal

Historical Analysis:
-------------------
When include_historical=True, fetches GEX time series from UW to provide:
- Where current GEX sits vs historical distribution (percentile)
- How long current regime has lasted vs typical duration
- Transition risk based on GEX trend and proximity to zero

Optional ML (use_ml=True):
-------------------------
When enabled with sufficient historical data, uses Random Forest to:
- PREDICT regime flips before they happen (not just classify current state)
- Labels historical flips and learns what features preceded them
- Walk-forward validated to prevent overfitting
- Configurable: ml_max_depth (default 4), ml_min_samples_leaf (default 5)

NO HARDCODING: Uses dynamic field discovery from Unusual Whales data.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import numpy as np
import pandas as pd
from agents import function_tool

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


# =============================================================================
# DATA FETCHING
# =============================================================================

async def _fetch_spot_price(fmp_server: FMPMarketDataServer, ticker: str) -> Optional[float]:
    """Fetch current spot price using dynamic field discovery via get_fields."""
    try:
        # Use get_fields with price field names - FMP maps them to the right dataset
        result = await fmp_server.call_tool("get_fields", {
            "symbol": ticker,
            "fields": ["price", "previousClose"]
        })
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        # Extract from response structure
        if isinstance(data, dict):
            inner = data.get('data', data)
            for field in ['price', 'previousClose']:
                val = inner.get(field)
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch spot price for {ticker}: {e}")
        return None


async def _fetch_gex_by_strike(uw_server: UWOptionsServer, ticker: str) -> Optional[List[Dict]]:
    """Fetch GEX by strike from Unusual Whales."""
    try:
        result = await uw_server.call_tool("uw_gex", {
            "ticker": ticker,
            "view": "by_strike"
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        # Handle nested data structure
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        
        return data if isinstance(data, list) else None
        
    except Exception as e:
        logger.warning(f"Failed to fetch GEX for {ticker}: {e}")
        return None


async def _fetch_gex_historical(
    uw_server: UWOptionsServer, 
    ticker: str, 
    timeframe: str = "6M"
) -> Optional[pd.DataFrame]:
    """
    Fetch historical GEX time series from Unusual Whales.
    
    Args:
        uw_server: Connected UW server instance
        ticker: Stock symbol
        timeframe: Historical range (1M, 2M, 3M, 6M, 1Y, 2Y, YTD)
    
    Returns:
        DataFrame with columns: date, total_gex, call_gex, put_gex
    """
    try:
        result = await uw_server.call_tool("uw_gex", {
            "ticker": ticker,
            "view": "summary",
            "timeframe": timeframe
        })
        
        if not result or not hasattr(result, 'content'):
            logger.warning(f"[GEX-HIST] No data returned for {ticker}")
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        # Handle nested data structure
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        
        if not isinstance(data, list) or len(data) == 0:
            logger.warning(f"[GEX-HIST] Empty data for {ticker}")
            return None
        
        # Parse into DataFrame with dynamic field discovery
        records = []
        for row in data:
            record = {}
            
            # Date field
            for field in ['date', 'timestamp', 'Date', 'time']:
                if field in row and row[field]:
                    record['date'] = pd.to_datetime(row[field])
                    break
            
            if 'date' not in record:
                continue
            
            # GEX fields - try multiple naming conventions
            for gex_field, target in [
                (['call_gamma', 'call_gex', 'callGamma'], 'call_gex'),
                (['put_gamma', 'put_gex', 'putGamma'], 'put_gex'),
                (['net_gamma', 'total_gex', 'netGamma', 'gamma'], 'total_gex')
            ]:
                for field in gex_field:
                    if field in row and row[field] is not None:
                        try:
                            record[target] = float(row[field])
                        except (ValueError, TypeError):
                            pass
                        break
            
            # Calculate total if not provided
            if 'total_gex' not in record and 'call_gex' in record and 'put_gex' in record:
                record['total_gex'] = record['call_gex'] + record['put_gex']
            
            if 'date' in record and 'total_gex' in record:
                records.append(record)
        
        if not records:
            logger.warning(f"[GEX-HIST] Could not parse any records for {ticker}")
            return None
        
        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)
        
        logger.info(f"[GEX-HIST] Loaded {len(df)} days of GEX history for {ticker}")
        return df
        
    except Exception as e:
        logger.warning(f"[GEX-HIST] Failed to fetch historical GEX for {ticker}: {e}")
        return None


async def _fetch_price_history(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    days: int = 180
) -> Optional[pd.DataFrame]:
    """Fetch historical price data for regime validation."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        # Try to extract prices from various formats
        records = []
        
        # Format 1: {prices: [...], dates: [...]}
        if 'prices' in data and 'dates' in data:
            for d, p in zip(data['dates'], data['prices']):
                if p is not None:
                    records.append({'date': pd.to_datetime(d), 'close': float(p)})
        
        # Format 2: {data: [{Date, Close}, ...]}
        elif 'data' in data and isinstance(data['data'], list):
            for row in data['data']:
                date_val = row.get('Date') or row.get('date')
                close_val = row.get('Close') or row.get('close')
                if date_val and close_val:
                    records.append({'date': pd.to_datetime(date_val), 'close': float(close_val)})
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)
        return df
        
    except Exception as e:
        logger.warning(f"[GEX-PRICE] Failed to fetch price history: {e}")
        return None


def _parse_gex_record(record: Dict) -> Optional[Dict[str, float]]:
    """Parse a single GEX record with dynamic field discovery."""
    try:
        # Strike - try multiple field names
        strike = None
        for field in ['strike', 'strike_price', 'strikeprice']:
            if field in record:
                strike = float(record[field])
                break
        
        if not strike or strike <= 0:
            return None
        
        # GEX fields - UW uses call_gex and put_gex
        call_gex = float(record.get('call_gex', 0) or 0)
        put_gex = float(record.get('put_gex', 0) or 0)
        
        # Net GEX: calls are positive contribution, puts are negative
        # Put GEX from UW is already negative, so we add them
        net_gex = call_gex + put_gex
        
        return {
            'strike': strike,
            'call_gex': call_gex,
            'put_gex': put_gex,
            'net_gex': net_gex
        }
    except (ValueError, TypeError):
        return None


def _build_gex_profile(raw_data: List[Dict]) -> List[Dict[str, float]]:
    """Build sorted GEX profile from raw data."""
    profile = []
    for record in raw_data:
        parsed = _parse_gex_record(record)
        if parsed:
            profile.append(parsed)
    
    profile.sort(key=lambda x: x['strike'])
    return profile


# =============================================================================
# ANALYSIS: KEY LEVELS
# =============================================================================

def _find_key_levels(profile: List[Dict], spot: float) -> Dict[str, Any]:
    """
    Find key GEX levels relative to spot.
    
    Returns:
        put_wall: Largest negative GEX below spot (support)
        call_wall: Largest positive GEX above spot (resistance)
        zero_gamma: Strike where GEX flips sign (pivot)
        max_gamma: Strike with highest absolute GEX (pin magnet)
    """
    if not profile:
        return {}
    
    below = [p for p in profile if p['strike'] < spot]
    above = [p for p in profile if p['strike'] > spot]
    
    # Put wall: largest |put_gex| below spot
    put_wall, put_wall_gex = None, 0
    for p in below:
        magnitude = abs(p['put_gex'])
        if magnitude > put_wall_gex:
            put_wall = p['strike']
            put_wall_gex = magnitude
    
    # Call wall: largest call_gex above spot
    call_wall, call_wall_gex = None, 0
    for p in above:
        if p['call_gex'] > call_wall_gex:
            call_wall = p['strike']
            call_wall_gex = p['call_gex']
    
    # Zero gamma: where net_gex crosses zero, closest to spot
    zero_gamma = None
    min_dist = float('inf')
    for i in range(len(profile) - 1):
        g1, g2 = profile[i]['net_gex'], profile[i + 1]['net_gex']
        if (g1 > 0 and g2 < 0) or (g1 < 0 and g2 > 0):
            s1, s2 = profile[i]['strike'], profile[i + 1]['strike']
            # Linear interpolation
            if g1 != g2:
                zero_strike = s1 + (0 - g1) * (s2 - s1) / (g2 - g1)
            else:
                zero_strike = (s1 + s2) / 2
            
            if abs(zero_strike - spot) < min_dist:
                min_dist = abs(zero_strike - spot)
                zero_gamma = round(zero_strike, 2)
    
    # Max gamma: highest absolute net_gex
    max_gamma, max_gex = None, 0
    for p in profile:
        if abs(p['net_gex']) > max_gex:
            max_gex = abs(p['net_gex'])
            max_gamma = p['strike']
    
    return {
        'put_wall': put_wall,
        'put_wall_gex': round(put_wall_gex, 2) if put_wall_gex else None,
        'call_wall': call_wall,
        'call_wall_gex': round(call_wall_gex, 2) if call_wall_gex else None,
        'zero_gamma': zero_gamma,
        'max_gamma': max_gamma,
        'max_gamma_gex': round(max_gex, 2) if max_gex else None
    }


# =============================================================================
# ANALYSIS: REGIME TRANSITION (The Alpha Signal)
# =============================================================================

def _analyze_regime_transition(profile: List[Dict], spot: float) -> Dict[str, Any]:
    """
    Detect GEX regime and transition signals.
    
    THE KEY INSIGHT:
    - Positive total GEX = dealers dampen moves = low volatility
    - Negative total GEX = dealers amplify moves = high volatility
    - The TRANSITION point predicts vol changes before they happen
    
    Returns:
        regime: 'positive' | 'negative' | 'neutral'
        total_gex: aggregate gamma exposure
        regime_strength: z-score of current regime
        transition_signal: 'VOL_EXPANSION_IMMINENT' | 'VOL_COMPRESSION_LIKELY' | None
        distance_to_flip: how close we are to regime change (0-1, lower = closer)
    """
    if not profile:
        return {}
    
    # Calculate total GEX
    total_gex = sum(p['net_gex'] for p in profile)
    
    # Filter to relevant range (within 10% of spot)
    relevant = [p for p in profile if 0.9 * spot <= p['strike'] <= 1.1 * spot]
    near_gex = sum(p['net_gex'] for p in relevant) if relevant else total_gex
    
    # Determine regime
    if total_gex > 0:
        regime = 'positive'
    elif total_gex < 0:
        regime = 'negative'
    else:
        regime = 'neutral'
    
    # Calculate regime strength (z-score)
    gex_values = [p['net_gex'] for p in profile]
    gex_std = np.std(gex_values) if len(gex_values) > 1 else 1
    gex_mean = np.mean(gex_values)
    regime_strength = (total_gex - gex_mean * len(profile)) / (gex_std * len(profile)) if gex_std > 0 else 0
    
    # Transition detection
    # Key: Look at GEX near spot vs total GEX
    # If they diverge, transition may be coming
    transition_signal = None
    distance_to_flip = 1.0
    
    if total_gex != 0:
        # Normalize by comparing near-spot GEX to total
        near_ratio = near_gex / total_gex if total_gex != 0 else 0
        
        # If near-spot GEX is opposite sign or much weaker than total
        if regime == 'positive' and near_gex <= 0:
            transition_signal = 'VOL_EXPANSION_IMMINENT'
            distance_to_flip = 0.2
        elif regime == 'positive' and near_ratio < 0.3:
            transition_signal = 'VOL_EXPANSION_IMMINENT'
            distance_to_flip = 0.4
        elif regime == 'negative' and near_gex >= 0:
            transition_signal = 'VOL_COMPRESSION_LIKELY'
            distance_to_flip = 0.2
        elif regime == 'negative' and near_ratio < 0.3:
            transition_signal = 'VOL_COMPRESSION_LIKELY'
            distance_to_flip = 0.4
        else:
            # Calculate distance based on how close total is to zero
            max_abs_gex = max(abs(p['net_gex']) for p in profile) * len(profile)
            distance_to_flip = min(1.0, abs(total_gex) / max_abs_gex) if max_abs_gex > 0 else 1.0
    
    return {
        'regime': regime,
        'total_gex': round(total_gex, 2),
        'total_gex_billions': round(total_gex / 1e9, 4),
        'near_spot_gex': round(near_gex, 2),
        'regime_strength': round(regime_strength, 2),
        'transition_signal': transition_signal,
        'distance_to_flip': round(distance_to_flip, 2),
        'interpretation': _get_regime_interpretation(regime, transition_signal)
    }


def _get_regime_interpretation(regime: str, transition: Optional[str]) -> str:
    """Generate human-readable interpretation."""
    if transition == 'VOL_EXPANSION_IMMINENT':
        return "⚠️ ALERT: Volatility expansion likely. Dealers shifting from dampening to amplifying. Consider long gamma strategies."
    elif transition == 'VOL_COMPRESSION_LIKELY':
        return "📉 Volatility compression expected. Dealers moving to dampen moves. Consider short gamma/premium selling."
    elif regime == 'positive':
        return "Positive GEX regime: Dealers absorb moves. Expect mean-reversion and range-bound action."
    elif regime == 'negative':
        return "Negative GEX regime: Dealers amplify moves. Expect trending/momentum behavior."
    else:
        return "Neutral regime: No clear dealer bias."


# =============================================================================
# ANALYSIS: FORCED FLOW QUANTIFICATION
# =============================================================================

def _calculate_forced_flow(profile: List[Dict], spot: float) -> Dict[str, Any]:
    """
    Calculate how much dealers MUST trade per 1% move.
    
    This is mechanical - dealers have no choice. When price moves,
    their delta changes, forcing them to buy/sell to re-hedge.
    
    Flow = Price_Change × Aggregate_Gamma × 100 (shares per contract)
    
    Returns:
        flow_per_1pct_up: $ dealers must trade if price rises 1%
        flow_per_1pct_down: $ dealers must trade if price falls 1%
        flow_impact: 'absorbing' | 'amplifying' based on flow direction
    """
    if not profile:
        return {}
    
    # Calculate aggregate gamma weighted by proximity to spot
    total_gamma = sum(p['net_gex'] for p in profile)
    
    # 1% move in dollars
    one_pct_move = spot * 0.01
    
    # Forced flow = gamma × price_change × 100 (contract multiplier)
    # Positive gamma: dealers buy on down move, sell on up move
    # Negative gamma: dealers sell on down move, buy on up move
    
    flow_per_1pct = abs(total_gamma * one_pct_move * 100)
    
    # Direction depends on gamma sign
    if total_gamma > 0:
        # Positive gamma: dealers SELL into rallies, BUY dips
        flow_up = -flow_per_1pct  # Negative = selling
        flow_down = flow_per_1pct  # Positive = buying
        flow_impact = 'absorbing'
    else:
        # Negative gamma: dealers BUY into rallies, SELL dips
        flow_up = flow_per_1pct  # Buying (chasing)
        flow_down = -flow_per_1pct  # Selling (chasing)
        flow_impact = 'amplifying'
    
    return {
        'flow_per_1pct_up_millions': round(flow_up / 1e6, 2),
        'flow_per_1pct_down_millions': round(flow_down / 1e6, 2),
        'absolute_flow_millions': round(flow_per_1pct / 1e6, 2),
        'flow_impact': flow_impact,
        'interpretation': (
            f"Per 1% move, dealers must trade ~${abs(flow_per_1pct/1e6):.1f}M. "
            f"Flow is {flow_impact} - {'dampening' if flow_impact == 'absorbing' else 'accelerating'} price moves."
        )
    }


# =============================================================================
# ANALYSIS: PIN PROBABILITY
# =============================================================================

def _calculate_pin_probability(
    profile: List[Dict], 
    spot: float, 
    max_gamma_strike: Optional[float]
) -> Dict[str, Any]:
    """
    Estimate probability of pinning to max gamma strike.
    
    Logic:
    - Higher gamma concentration at a strike = stronger magnetic pull
    - Closer to expiry = stronger pin effect
    - Pin probability scales with gamma_at_strike / total_gamma
    
    Returns:
        pin_strike: most likely pin target
        pin_probability: estimated probability (0-1)
        gamma_concentration: how concentrated gamma is at pin strike
    """
    if not profile or not max_gamma_strike:
        return {}
    
    # Find gamma at max strike
    max_gamma_gex = 0
    for p in profile:
        if p['strike'] == max_gamma_strike:
            max_gamma_gex = abs(p['net_gex'])
            break
    
    # Total absolute gamma
    total_abs_gamma = sum(abs(p['net_gex']) for p in profile)
    
    if total_abs_gamma == 0:
        return {}
    
    # Gamma concentration ratio
    concentration = max_gamma_gex / total_abs_gamma
    
    # Distance from spot (closer = higher probability)
    distance_pct = abs(max_gamma_strike - spot) / spot
    distance_factor = max(0, 1 - distance_pct * 10)  # Decays with distance
    
    # Base probability from concentration, adjusted by distance
    # This is a heuristic - real pin probability would need more data
    raw_prob = concentration * distance_factor
    pin_probability = min(0.85, raw_prob * 2)  # Cap at 85%
    
    return {
        'pin_strike': max_gamma_strike,
        'pin_probability': round(pin_probability, 2),
        'gamma_concentration': round(concentration, 3),
        'distance_from_spot_pct': round(distance_pct * 100, 1),
        'interpretation': (
            f"Max gamma at ${max_gamma_strike:.0f} ({distance_pct*100:.1f}% from spot). "
            f"{concentration*100:.1f}% of gamma concentrated here. "
            f"{'Strong' if pin_probability > 0.5 else 'Moderate' if pin_probability > 0.3 else 'Weak'} pin potential."
        )
    }


# =============================================================================
# ANALYSIS: HISTORICAL CONTEXT (The Alpha Edge)
# =============================================================================

def _analyze_historical_context(
    gex_history: pd.DataFrame,
    current_gex: float,
    current_regime: str
) -> Dict[str, Any]:
    """
    Analyze current GEX vs historical distribution.
    
    This provides:
    - Percentile: Where is current GEX vs history?
    - Regime duration: How long has current regime lasted?
    - Transition risk: How close are we to a regime flip?
    - GEX trend: Is gamma exposure increasing or decreasing?
    
    Returns actionable context without ML complexity.
    """
    if gex_history is None or len(gex_history) < 20:
        return {'error': 'Insufficient historical data'}
    
    gex_series = gex_history['total_gex']
    
    # 1. Percentile rank
    percentile = (gex_series < current_gex).mean() * 100
    
    # 2. Z-score vs history
    gex_mean = gex_series.mean()
    gex_std = gex_series.std()
    gex_zscore = (current_gex - gex_mean) / gex_std if gex_std > 0 else 0
    
    # 3. GEX trend (5d and 10d)
    gex_5d_ago = gex_series.iloc[-6] if len(gex_series) > 5 else gex_series.iloc[0]
    gex_10d_ago = gex_series.iloc[-11] if len(gex_series) > 10 else gex_series.iloc[0]
    
    trend_5d = current_gex - gex_5d_ago
    trend_10d = current_gex - gex_10d_ago
    
    trend_direction = 'increasing' if trend_5d > 0 else 'decreasing' if trend_5d < 0 else 'flat'
    
    # 4. Distance to zero (regime flip proximity)
    distance_to_zero_pct = abs(current_gex) / (abs(gex_mean) + 1e-9) * 100
    
    # 5. Regime duration analysis
    # Count consecutive days in same regime
    regime_sign = 1 if current_regime == 'positive' else -1
    consecutive_days = 0
    for i in range(len(gex_series) - 1, -1, -1):
        if (gex_series.iloc[i] > 0 and regime_sign > 0) or (gex_series.iloc[i] < 0 and regime_sign < 0):
            consecutive_days += 1
        else:
            break
    
    # Calculate historical average regime duration
    regime_changes = 0
    total_duration = 0
    current_streak = 0
    last_sign = None
    
    for gex_val in gex_series:
        sign = 1 if gex_val > 0 else -1
        if last_sign is None:
            last_sign = sign
            current_streak = 1
        elif sign == last_sign:
            current_streak += 1
        else:
            regime_changes += 1
            total_duration += current_streak
            current_streak = 1
            last_sign = sign
    
    avg_regime_duration = total_duration / regime_changes if regime_changes > 0 else len(gex_series)
    
    # 6. Transition risk assessment
    transition_risk = _assess_transition_risk(
        current_gex, gex_zscore, trend_5d, trend_direction,
        consecutive_days, avg_regime_duration, current_regime
    )
    
    return {
        'percentile': round(percentile, 1),
        'z_score': round(gex_zscore, 2),
        'trend': {
            'direction': trend_direction,
            'change_5d': round(trend_5d / 1e9, 4),
            'change_10d': round(trend_10d / 1e9, 4),
            'change_5d_pct': round(trend_5d / abs(gex_5d_ago) * 100, 1) if gex_5d_ago != 0 else 0
        },
        'regime_duration': {
            'current_streak_days': consecutive_days,
            'avg_regime_duration_days': round(avg_regime_duration, 1),
            'streak_vs_avg_pct': round(consecutive_days / avg_regime_duration * 100, 1) if avg_regime_duration > 0 else 0
        },
        'transition_risk': transition_risk,
        'historical_stats': {
            'mean_gex_billions': round(gex_mean / 1e9, 4),
            'std_gex_billions': round(gex_std / 1e9, 4),
            'min_gex_billions': round(gex_series.min() / 1e9, 4),
            'max_gex_billions': round(gex_series.max() / 1e9, 4),
            'data_days': len(gex_series)
        }
    }


def _assess_transition_risk(
    current_gex: float,
    z_score: float,
    trend_5d: float,
    trend_direction: str,
    streak_days: int,
    avg_duration: float,
    current_regime: str
) -> Dict[str, Any]:
    """
    Assess probability of regime transition based on multiple factors.
    
    Risk factors:
    - Approaching zero GEX (sign flip imminent)
    - Regime duration exceeds historical average
    - GEX trending toward zero
    - Z-score near zero (unusual positioning)
    """
    risk_score = 0
    risk_factors = []
    
    # Factor 1: Proximity to zero
    if abs(z_score) < 0.5:
        risk_score += 30
        risk_factors.append("GEX near historical average (z < 0.5)")
    
    # Factor 2: Trend toward zero
    if current_regime == 'positive' and trend_direction == 'decreasing':
        risk_score += 25
        risk_factors.append("GEX decreasing in positive regime")
    elif current_regime == 'negative' and trend_direction == 'increasing':
        risk_score += 25
        risk_factors.append("GEX increasing in negative regime")
    
    # Factor 3: Regime duration
    if avg_duration > 0 and streak_days > avg_duration:
        overshoot = (streak_days - avg_duration) / avg_duration
        risk_score += min(30, int(overshoot * 20))
        risk_factors.append(f"Regime duration {streak_days}d exceeds avg {avg_duration:.0f}d")
    
    # Factor 4: Absolute GEX approaching zero
    # If current GEX is small relative to typical swings
    if abs(current_gex) < abs(trend_5d) * 2:
        risk_score += 15
        risk_factors.append("Current GEX < 2x recent daily change")
    
    # Classify risk level
    if risk_score >= 60:
        risk_level = 'HIGH'
        signal = '⚠️ TRANSITION LIKELY'
    elif risk_score >= 35:
        risk_level = 'ELEVATED'
        signal = '⚡ TRANSITION POSSIBLE'
    else:
        risk_level = 'LOW'
        signal = '✓ REGIME STABLE'
    
    return {
        'level': risk_level,
        'score': risk_score,
        'signal': signal,
        'factors': risk_factors,
        'interpretation': _get_transition_interpretation(risk_level, current_regime, risk_factors)
    }


def _get_transition_interpretation(risk_level: str, regime: str, factors: List[str]) -> str:
    """Generate human-readable transition risk interpretation."""
    if risk_level == 'HIGH':
        if regime == 'positive':
            return (
                "High transition risk: Positive gamma regime may be ending. "
                "Prepare for potential volatility expansion. "
                f"Key factors: {', '.join(factors[:2])}"
            )
        else:
            return (
                "High transition risk: Negative gamma regime may be ending. "
                "Potential for volatility compression ahead. "
                f"Key factors: {', '.join(factors[:2])}"
            )
    elif risk_level == 'ELEVATED':
        return (
            f"Elevated transition risk in {regime} gamma regime. "
            "Monitor GEX levels closely for regime change signals."
        )
    else:
        return f"Current {regime} gamma regime appears stable. Key levels should hold."


# =============================================================================
# ANALYSIS: PREDICTIVE REGIME FLIP MODEL (Optional)
# =============================================================================
# Unlike the standard HMM which classifies "what state are we in", this model
# actually PREDICTS upcoming regime FLIPS by:
# 1. Labeling historical regime flips (when GEX crossed thresholds)
# 2. Extracting pre-flip features (what happened BEFORE flips)
# 3. Training a classifier to predict "flip in next N days"
# 4. Walk-forward validation to combat overfitting
# =============================================================================

def _label_regime_flips(
    gex_series: pd.Series,
    threshold_pct: float = 0.0,
    lookahead: int = 5
) -> pd.Series:
    """
    Label each day with whether a regime flip occurs in next `lookahead` days.
    
    Regime flip = GEX crosses from positive to negative or vice versa.
    Returns: Series of 1 (flip coming) or 0 (no flip coming)
    """
    # Determine regime: 1 = positive, -1 = negative
    regimes = np.sign(gex_series - threshold_pct)
    
    # Find flip points (where regime changes)
    flip_points = regimes.diff().abs() > 1  # diff of 2 means -1 to +1 or vice versa
    flip_points = flip_points.astype(int)
    
    # Create target: 1 if any flip in next `lookahead` days
    labels = flip_points.rolling(window=lookahead, min_periods=1).max().shift(-lookahead)
    labels = labels.fillna(0).astype(int)
    
    return labels


def _extract_predictive_features(
    gex_series: pd.Series,
    price_series: pd.Series,
    windows: List[int] = [5, 10, 20]
) -> pd.DataFrame:
    """
    Extract features that might predict upcoming regime flips.
    
    Key insight: Before flips, we often see:
    - GEX trend reversal or acceleration
    - Volatility changes
    - GEX approaching zero (threshold)
    - Price behavior diverging from expected
    """
    returns = price_series.pct_change().fillna(0)
    
    features = {}
    
    for w in windows:
        prefix = f"w{w}_"
        
        # GEX features - distance to flip threshold
        features[f'{prefix}gex_zscore'] = (
            (gex_series - gex_series.rolling(w*2).mean()) / 
            (gex_series.rolling(w*2).std() + 1e-9)
        )
        features[f'{prefix}gex_distance_to_zero'] = np.abs(gex_series) / (np.abs(gex_series).rolling(w*2).mean() + 1e-9)
        features[f'{prefix}gex_trend'] = gex_series.diff(w) / (np.abs(gex_series).rolling(w).mean() + 1e-9)
        features[f'{prefix}gex_acceleration'] = gex_series.diff(w).diff(w // 2)
        
        # Price dynamics
        features[f'{prefix}volatility'] = returns.rolling(w).std() * np.sqrt(252)
        features[f'{prefix}vol_change'] = features[f'{prefix}volatility'].pct_change(w // 2)
        features[f'{prefix}autocorr'] = returns.rolling(w).apply(
            lambda x: pd.Series(x).autocorr(lag=1) if len(x) > 1 else 0, raw=False
        )
        features[f'{prefix}momentum'] = returns.rolling(w).sum()
        
        # Regime behavior match (is price acting as GEX predicts?)
        expected_sign = -np.sign(gex_series)  # positive GEX -> expect negative autocorr
        actual_autocorr = features[f'{prefix}autocorr']
        features[f'{prefix}behavior_divergence'] = expected_sign * np.sign(actual_autocorr)
    
    # Cross-window features
    features['vol_ratio_5_20'] = features['w5_volatility'] / (features['w20_volatility'] + 1e-9)
    features['gex_trend_acceleration'] = features['w5_gex_trend'] - features['w20_gex_trend']
    
    return pd.DataFrame(features)


def _walk_forward_validate(
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    max_depth: int = 4,
    min_samples_leaf: int = 5
) -> Dict[str, Any]:
    """
    Walk-forward validation to get honest out-of-sample metrics.
    
    This is critical to avoid overfitting - we only report performance
    on data the model hasn't seen.
    
    Args:
        max_depth: Max tree depth (lower = less overfit, default 4)
        min_samples_leaf: Min samples per leaf (higher = less overfit, default 5)
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_score, recall_score, roc_auc_score
    
    n = len(X)
    fold_size = n // n_splits
    
    oos_predictions = []
    oos_actuals = []
    oos_probabilities = []
    
    for i in range(n_splits - 1):
        # Walk-forward: train on past, test on future
        train_end = (i + 1) * fold_size
        test_start = train_end
        test_end = min(test_start + fold_size, n)
        
        if test_end <= test_start:
            continue
            
        X_train, y_train = X[:train_end], y[:train_end]
        X_test, y_test = X[test_start:test_end], y[test_start:test_end]
        
        # Skip if no positive class in training
        if y_train.sum() < 3:
            continue
        
        # Simple model with regularization to prevent overfitting
        model = RandomForestClassifier(
            n_estimators=50,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            class_weight='balanced',
            random_state=42
        )
        model.fit(X_train, y_train)
        
        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)[:, 1] if len(model.classes_) > 1 else np.zeros(len(X_test))
        
        oos_predictions.extend(preds)
        oos_actuals.extend(y_test)
        oos_probabilities.extend(probs)
    
    if len(oos_predictions) < 10:
        return {'status': 'insufficient_data', 'n_samples': len(oos_predictions)}
    
    oos_predictions = np.array(oos_predictions)
    oos_actuals = np.array(oos_actuals)
    oos_probabilities = np.array(oos_probabilities)
    
    # Only calculate metrics if we have both classes
    precision = precision_score(oos_actuals, oos_predictions, zero_division=0)
    recall = recall_score(oos_actuals, oos_predictions, zero_division=0)
    
    try:
        auc = roc_auc_score(oos_actuals, oos_probabilities)
    except:
        auc = 0.5
    
    return {
        'status': 'success',
        'n_samples': len(oos_predictions),
        'precision': round(precision, 3),
        'recall': round(recall, 3),
        'auc': round(auc, 3),
        'n_flips_actual': int(oos_actuals.sum()),
        'n_flips_predicted': int(oos_predictions.sum())
    }


def _run_ml_regime_analysis(
    gex_history: pd.DataFrame,
    price_history: pd.DataFrame,
    current_regime: str,
    lookahead: int = 5,
    max_depth: int = 4,
    min_samples_leaf: int = 5
) -> Optional[Dict[str, Any]]:
    """
    PREDICTIVE regime flip model.
    
    Unlike standard HMM that classifies current state, this model:
    1. Labels historical regime flips
    2. Learns what features preceded flips
    3. Predicts probability of flip in next `lookahead` days
    4. Validates via walk-forward to prevent overfitting
    
    Args:
        lookahead: Days ahead to predict flip (default 5)
        max_depth: Max tree depth for RF (lower = less overfit, default 4)
        min_samples_leaf: Min samples per leaf (higher = less overfit, default 5)
    
    Returns actual prediction with confidence + validation metrics.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        logger.info("[GEX-PREDICT] sklearn not installed, skipping ML analysis")
        return None
    
    min_history = 120  # Need enough data for walk-forward validation
    
    if gex_history is None or len(gex_history) < min_history:
        logger.info(f"[GEX-PREDICT] Insufficient GEX history ({len(gex_history) if gex_history is not None else 0} < {min_history})")
        return None
    
    if price_history is None or len(price_history) < min_history:
        logger.info(f"[GEX-PREDICT] Insufficient price history ({len(price_history) if price_history is not None else 0} < {min_history})")
        return None
    
    try:
        # Align data on common dates
        gex_df = gex_history.set_index('date') if 'date' in gex_history.columns else gex_history
        price_df = price_history.set_index('date') if 'date' in price_history.columns else price_history
        
        common_idx = gex_df.index.intersection(price_df.index)
        if len(common_idx) < min_history:
            return None
        
        common_idx = common_idx.sort_values()
        gex_aligned = gex_df.loc[common_idx]['total_gex']
        prices_aligned = price_df.loc[common_idx]['close']
        
        # Step 1: Label historical flips
        labels = _label_regime_flips(gex_aligned, threshold_pct=0.0, lookahead=lookahead)
        
        # Step 2: Extract features
        features = _extract_predictive_features(gex_aligned, prices_aligned)
        
        # Align and clean
        combined = pd.concat([features, labels.rename('target')], axis=1).dropna()
        
        if len(combined) < 80:
            return {'status': 'insufficient_aligned_data', 'n_samples': len(combined)}
        
        X = combined.drop('target', axis=1).values
        y = combined['target'].values
        feature_names = list(combined.drop('target', axis=1).columns)
        
        # Step 3: Walk-forward validation (honest OOS metrics)
        validation = _walk_forward_validate(
            X, y, 
            max_depth=max_depth, 
            min_samples_leaf=min_samples_leaf
        )
        
        if validation['status'] != 'success':
            return validation
        
        # Step 4: Train final model on all data for current prediction
        model = RandomForestClassifier(
            n_estimators=50,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            class_weight='balanced',
            random_state=42
        )
        model.fit(X, y)
        
        # Current prediction
        current_features = X[-1:, :]
        flip_probability = model.predict_proba(current_features)[0, 1] if len(model.classes_) > 1 else 0.0
        flip_predicted = flip_probability > 0.5
        
        # Feature importance
        importance = dict(zip(feature_names, model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Current feature values (for interpretability)
        current_values = dict(zip(feature_names, current_features[0]))
        key_signals = {}
        for feat, imp in top_features:
            val = current_values[feat]
            if 'distance_to_zero' in feat:
                key_signals[feat] = f"{val:.2f} (closer to 0 = higher flip risk)"
            elif 'gex_trend' in feat:
                key_signals[feat] = f"{val:.2f} ({'accelerating toward flip' if val < 0 else 'stable'})"
            elif 'behavior_divergence' in feat:
                key_signals[feat] = f"{val:.1f} (-1 = diverging = flip risk)"
            else:
                key_signals[feat] = f"{val:.3f}"
        
        # Confidence calibration based on validation metrics
        if validation['auc'] < 0.55:
            confidence_note = "⚠️ Model has weak predictive power (AUC < 0.55)"
            adjusted_confidence = 'LOW'
        elif validation['precision'] < 0.3:
            confidence_note = "⚠️ Many false alarms historically (precision < 30%)"
            adjusted_confidence = 'LOW'
        elif validation['auc'] > 0.65 and validation['precision'] > 0.4:
            confidence_note = "✓ Model shows reasonable predictive power"
            adjusted_confidence = 'MODERATE' if flip_probability < 0.7 else 'HIGH'
        else:
            confidence_note = "Model has marginal predictive power"
            adjusted_confidence = 'LOW_MODERATE'
        
        return {
            'status': 'success',
            'model_type': 'PREDICTIVE_REGIME_FLIP',
            'prediction': {
                'flip_in_next_n_days': lookahead,
                'flip_probability': round(float(flip_probability), 3),
                'flip_predicted': flip_predicted,
                'current_regime': current_regime,
                'predicted_action': (
                    f"⚠️ REGIME FLIP LIKELY ({flip_probability:.0%} prob) - prepare for volatility regime change"
                    if flip_predicted else
                    f"✓ Regime appears stable ({1-flip_probability:.0%} confidence for next {lookahead} days)"
                )
            },
            'confidence': {
                'level': adjusted_confidence,
                'note': confidence_note,
                'validation_auc': validation['auc'],
                'validation_precision': validation['precision'],
                'validation_recall': validation['recall']
            },
            'key_signals': key_signals,
            'top_features': [{'feature': f, 'importance': round(i, 3)} for f, i in top_features],
            'validation_metrics': {
                'method': 'walk_forward',
                'n_splits': 5,
                'n_out_of_sample': validation['n_samples'],
                'historical_flips_detected': validation['n_flips_actual'],
                'historical_flips_predicted': validation['n_flips_predicted']
            },
            'model_config': {
                'model': 'RandomForestClassifier',
                'n_estimators': 50,
                'max_depth': max_depth,
                'min_samples_leaf': min_samples_leaf,
                'class_weight': 'balanced'
            },
            'interpretation': (
                f"Based on {len(combined)} days of history with {int(y.sum())} regime flips observed. "
                f"Model achieves {validation['auc']:.0%} AUC on walk-forward validation. "
                f"Key drivers: {', '.join([f[0].split('_')[-1] for f, _ in top_features[:3]])}."
            )
        }
        
    except Exception as e:
        logger.warning(f"[GEX-PREDICT] Predictive analysis failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {'status': 'error', 'error': str(e)}


# =============================================================================
# VISUALIZATION
# =============================================================================

def _build_gex_chart(
    ticker: str,
    profile: List[Dict],
    spot: float,
    key_levels: Dict,
    regime: Dict,
    chart_id: str
) -> Optional[Dict]:
    """Build GEX visualization with key levels marked."""
    try:
        import plotly.graph_objects as go
        
        if not profile:
            return None
        
        strikes = [p['strike'] for p in profile]
        net_gex = [p['net_gex'] / 1e9 for p in profile]  # Billions
        
        colors = ['#3B82F6' if g >= 0 else '#EF4444' for g in net_gex]
        
        fig = go.Figure()
        
        # GEX bars
        fig.add_trace(go.Bar(
            x=strikes,
            y=net_gex,
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate='<b>$%{x:.0f}</b><br>GEX: %{y:.2f}B<extra></extra>',
            showlegend=False
        ))
        
        # Spot price
        fig.add_vline(x=spot, line=dict(color='#0F172A', width=2.5),
                      annotation=dict(text=f'Spot ${spot:.0f}', font=dict(size=11)))
        
        # Key levels
        if key_levels.get('put_wall'):
            fig.add_vline(x=key_levels['put_wall'], 
                         line=dict(color='#22C55E', width=2, dash='dot'),
                         annotation=dict(text='Put Wall', font=dict(color='#22C55E', size=9), yshift=-20))
        
        if key_levels.get('call_wall'):
            fig.add_vline(x=key_levels['call_wall'],
                         line=dict(color='#EF4444', width=2, dash='dot'),
                         annotation=dict(text='Call Wall', font=dict(color='#EF4444', size=9), yshift=-20))
        
        if key_levels.get('zero_gamma'):
            fig.add_vline(x=key_levels['zero_gamma'],
                         line=dict(color='#F59E0B', width=1.5, dash='dash'),
                         annotation=dict(text='Zero γ', font=dict(color='#F59E0B', size=9), yshift=30))
        
        # Title with regime
        regime_text = regime.get('regime', 'unknown').upper()
        transition = regime.get('transition_signal')
        title_suffix = f" | ⚠️ {transition}" if transition else ""
        
        fig.update_layout(
            title=dict(
                text=f'<b>{ticker}</b> GEX Profile | {regime_text} REGIME{title_suffix}',
                font=dict(size=16, family='Inter'),
                x=0.5, xanchor='center'
            ),
            xaxis=dict(title='Strike Price ($)', gridcolor='#E2E8F0'),
            yaxis=dict(title='Net GEX ($B)', gridcolor='#E2E8F0', zeroline=True, zerolinecolor='#94A3B8'),
            width=900, height=450,
            paper_bgcolor='#FFFFFF', plot_bgcolor='#F8FAFC',
            margin=dict(l=60, r=30, t=80, b=60)
        )
        
        return {
            'id': chart_id,
            'title': f'{ticker} GEX Analysis',
            'plotly': fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Chart build failed: {e}")
        return None


# =============================================================================
# MAIN TOOL
# =============================================================================

@function_tool
async def analyze_gex_levels(
    ticker: str,
    include_regime_analysis: bool = True,
    include_forced_flow: bool = False,
    include_pin_probability: bool = False,
    include_historical: bool = False,
    historical_timeframe: str = "6M",
    use_ml: bool = False,
    ml_max_depth: int = 4,
    ml_min_samples_leaf: int = 5
) -> Dict[str, Any]:
    """
    Analyze dealer gamma exposure (GEX) for actionable trading signals.
    
    GEX reveals where dealers MUST trade due to delta-hedging. This creates
    predictable support/resistance and volatility regimes.
    
    **Core Output (always included):**
    - key_levels: Put wall (support), call wall (resistance), zero gamma (pivot), max gamma (pin)
    - spot_price: Current underlying price
    - chart: Visual GEX profile with levels marked
    
    **Optional Analysis:**
    
    1. include_regime_analysis (default: True)
       - Detects current regime: positive (vol suppression) vs negative (vol amplification)
       - **ALPHA SIGNAL**: Identifies regime TRANSITIONS before vol changes
       - transition_signal: 'VOL_EXPANSION_IMMINENT' or 'VOL_COMPRESSION_LIKELY'
    
    2. include_forced_flow (default: False)
       - Quantifies $ dealers must trade per 1% price move
       - Reveals if flows will absorb or amplify moves
    
    3. include_pin_probability (default: False)
       - Estimates probability of pinning to max gamma strike by expiry
       - Useful for expiration week trades
    
    4. include_historical (default: False)
       - Fetches GEX time series from Unusual Whales
       - Provides: percentile rank, z-score, regime duration, transition risk
       - **THE ALPHA EDGE**: Know when regime change is likely
    
    5. use_ml (default: False)
       - Requires include_historical=True
       - Uses Random Forest to PREDICT regime flips before they happen
       - Walk-forward validated to prevent overfitting
       - Outputs flip probability + confidence + key signals
    
    Args:
        ticker: Stock/ETF symbol (e.g., "SPY", "QQQ", "AAPL")
        include_regime_analysis: Analyze regime and detect transitions
        include_forced_flow: Calculate dealer hedging flow per 1% move
        include_pin_probability: Estimate pin probability for max gamma strike
        include_historical: Fetch historical GEX for context and transition risk
        historical_timeframe: Timeframe for historical data (1M, 2M, 3M, 6M, 1Y, 2Y, YTD)
        use_ml: Enable predictive regime flip model (requires include_historical)
        ml_max_depth: Max tree depth for ML model (lower = less overfit, default 4)
        ml_min_samples_leaf: Min samples per leaf (higher = less overfit, default 5)
    
    Returns:
        Dictionary with requested analysis sections and visualization
    
    Example:
        # Basic levels + regime (most common use)
        result = await analyze_gex_levels(ticker="SPY")
        
        # Full analysis with historical context
        result = await analyze_gex_levels(
            ticker="SPY",
            include_historical=True,
            include_forced_flow=True
        )
        
        # Advanced ML analysis
        result = await analyze_gex_levels(
            ticker="SPY",
            include_historical=True,
            use_ml=True
        )
        
        # Check for vol expansion signal
        if result.get('regime', {}).get('transition_signal') == 'VOL_EXPANSION_IMMINENT':
            print("Consider long gamma strategies")
        
        # Check transition risk from historical
        if result.get('historical', {}).get('transition_risk', {}).get('level') == 'HIGH':
            print("Regime change likely - reduce position size")
    """
    ticker = ticker.upper().strip()
    
    # ML requires historical data
    if use_ml and not include_historical:
        include_historical = True
        logger.info("[GEX] use_ml=True implies include_historical=True")
    
    uw_server = UWOptionsServer()
    fmp_server = FMPMarketDataServer()
    
    try:
        await uw_server.connect()
        await fmp_server.connect()
        
        # Fetch current data
        spot = await _fetch_spot_price(fmp_server, ticker)
        if not spot:
            return {'error': f'Could not fetch spot price for {ticker}', 'ticker': ticker}
        
        raw_gex = await _fetch_gex_by_strike(uw_server, ticker)
        if not raw_gex:
            return {'error': f'No GEX data available for {ticker}', 'ticker': ticker, 'spot_price': spot}
        
        # Build profile
        profile = _build_gex_profile(raw_gex)
        if not profile:
            return {'error': 'Could not parse GEX data', 'ticker': ticker, 'spot_price': spot}
        
        logger.info(f"[GEX] {ticker}: {len(profile)} strikes, spot=${spot:.2f}")
        
        # Core analysis: key levels
        key_levels = _find_key_levels(profile, spot)
        
        # Build output
        output = {
            'status': 'success',
            'ticker': ticker,
            'spot_price': round(spot, 2),
            'timestamp': datetime.now().isoformat(),
            'key_levels': key_levels,
            'data_quality': {
                'strikes_analyzed': len(profile),
                'strike_range': f"${profile[0]['strike']:.0f} - ${profile[-1]['strike']:.0f}"
            }
        }
        
        # Calculate current total GEX for historical comparison
        current_total_gex = sum(p['net_gex'] for p in profile)
        
        # Optional: Regime analysis (THE ALPHA SIGNAL)
        regime = {}
        if include_regime_analysis:
            regime = _analyze_regime_transition(profile, spot)
            output['regime'] = regime
        
        # Optional: Forced flow
        if include_forced_flow:
            output['forced_flow'] = _calculate_forced_flow(profile, spot)
        
        # Optional: Pin probability
        if include_pin_probability:
            output['pin_analysis'] = _calculate_pin_probability(
                profile, spot, key_levels.get('max_gamma')
            )
        
        # Optional: Historical context (THE ALPHA EDGE)
        gex_history = None
        price_history = None
        
        if include_historical:
            logger.info(f"[GEX] Fetching historical GEX for {ticker} ({historical_timeframe})")
            gex_history = await _fetch_gex_historical(uw_server, ticker, historical_timeframe)
            
            if gex_history is not None and len(gex_history) > 0:
                current_regime = regime.get('regime', 'neutral')
                historical_analysis = _analyze_historical_context(
                    gex_history, current_total_gex, current_regime
                )
                output['historical'] = historical_analysis
                
                # Update summary with transition risk
                if 'transition_risk' in historical_analysis:
                    risk_level = historical_analysis['transition_risk'].get('level', 'UNKNOWN')
                    output['transition_risk_summary'] = historical_analysis['transition_risk'].get('signal', '')
            else:
                output['historical'] = {'error': 'Could not fetch historical GEX data'}
        
        # Optional: ML regime detection
        if use_ml and gex_history is not None:
            logger.info(f"[GEX] Running ML regime analysis for {ticker}")
            
            # Fetch price history for ML
            days_map = {'1M': 30, '2M': 60, '3M': 90, '6M': 180, '1Y': 365, '2Y': 730, 'YTD': 365}
            price_days = days_map.get(historical_timeframe, 180)
            price_history = await _fetch_price_history(fmp_server, ticker, price_days)
            
            current_regime = regime.get('regime', 'neutral')
            ml_result = _run_ml_regime_analysis(
                gex_history, 
                price_history, 
                current_regime,
                max_depth=ml_max_depth,
                min_samples_leaf=ml_min_samples_leaf
            )
            
            if ml_result and ml_result.get('status') == 'success':
                output['ml_analysis'] = ml_result
                
                # Surface key prediction to top level
                prediction = ml_result.get('prediction', {})
                if prediction.get('flip_predicted'):
                    output['regime_flip_warning'] = prediction.get('predicted_action')
                    output['flip_probability'] = prediction.get('flip_probability')
                    
                # Add confidence note
                confidence = ml_result.get('confidence', {})
                output['ml_confidence'] = confidence.get('level', 'UNKNOWN')
            else:
                reason = ml_result.get('error') if ml_result else 'Insufficient data or sklearn not installed'
                output['ml_analysis'] = {'status': 'skipped', 'reason': reason}
        
        # Build chart
        chart_id = f"gex_{ticker.lower()}_{datetime.now().strftime('%H%M%S')}"
        chart = _build_gex_chart(ticker, profile, spot, key_levels, regime, chart_id)
        output['charts'] = wrap_plotly_charts([chart] if chart else [], default_type="gex_analysis")
        
        # Summary for quick reading
        output['summary'] = _build_summary(ticker, spot, key_levels, regime)
        
        # Add historical context to summary if available
        if 'historical' in output and 'transition_risk' in output.get('historical', {}):
            risk = output['historical']['transition_risk']
            output['summary'] += f" | Transition Risk: {risk.get('level', 'UNKNOWN')}"
        
        return output
        
    except Exception as e:
        logger.error(f"GEX analysis failed for {ticker}: {e}", exc_info=True)
        return {'error': str(e), 'ticker': ticker}
    
    finally:
        await uw_server.cleanup()
        await fmp_server.cleanup()


def _build_summary(ticker: str, spot: float, levels: Dict, regime: Dict) -> str:
    """Build one-line summary for quick reading."""
    parts = [f"{ticker} @ ${spot:.0f}"]
    
    if levels.get('put_wall') and levels.get('call_wall'):
        parts.append(f"Range: ${levels['put_wall']:.0f}-${levels['call_wall']:.0f}")
    
    if regime.get('regime'):
        parts.append(f"Regime: {regime['regime'].upper()}")
    
    if regime.get('transition_signal'):
        parts.append(f"⚠️ {regime['transition_signal']}")
    
    return " | ".join(parts)


# =============================================================================
# LEGACY ALIAS (backward compatibility)
# =============================================================================

# Keep old function name working
map_gex_support_resistance = analyze_gex_levels
