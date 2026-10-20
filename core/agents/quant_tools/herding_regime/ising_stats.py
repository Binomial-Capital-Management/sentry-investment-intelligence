"""
Ising Model Statistics for Herding Detection.

Computes 4 physics-inspired statistics from sector returns:
1. Magnetization (M) - Net market sentiment
2. Susceptibility (chi) - Response sensitivity
3. Correlation Length (xi) - Herding spread
4. Critical Slowing Down (tau) - Momentum persistence

Plus 3 Ising model parameters:
- Temperature (T) - From VIX, controls disorder
- External Field (h) - From RSI breadth (discretionary) or macro factors
- Coupling (J) - From options flow correlation, spin-spin interaction strength

All statistics are normalized to percentiles (self-normalizing).
Composite index uses PCA weighting.
"""

from typing import Dict, List, Optional, Tuple, Any
import logging

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


# =============================================================================
# SIGNAL THRESHOLDS (Percentile-Based)
# =============================================================================

def _percentile_to_signal(percentile: float) -> str:
    """Convert percentile to signal label."""
    if percentile > 0.95:
        return "CRITICAL"
    elif percentile > 0.80:
        return "ELEVATED"
    elif percentile > 0.50:
        return "NORMAL"
    else:
        return "LOW"


def _herding_index_to_regime(index: float) -> Tuple[str, str]:
    """
    Convert herding index to regime and risk level.
    
    Returns:
        (regime_name, risk_level)
    """
    if index > 0.80:
        return "CRITICAL", "EXTREME"
    elif index > 0.60:
        return "PRE_CRITICAL", "HIGH"
    elif index > 0.40:
        return "ELEVATED", "MODERATE"
    elif index > 0.20:
        return "NORMAL", "LOW"
    else:
        return "DISPERSED", "MINIMAL"


# =============================================================================
# RSI CALCULATION
# =============================================================================

def compute_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Compute RSI (Relative Strength Index) for a price series.
    
    Args:
        prices: List of prices (oldest to newest)
        period: RSI period (default 14)
        
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    # Compute price changes
    changes = np.diff(prices)
    
    # Separate gains and losses
    gains = np.where(changes > 0, changes, 0)
    losses = np.where(changes < 0, -changes, 0)
    
    # Use exponential moving average for smoothing
    alpha = 1 / period
    
    # Initialize with simple average of first `period` values
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    # Apply EMA for remaining values
    for i in range(period, len(gains)):
        avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
        avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi)


# =============================================================================
# DISCRETIONARY EXTERNAL FIELD (RSI Breadth)
# =============================================================================

def compute_discretionary_field(
    prices_dict: Dict[str, List[float]],
    rsi_period: int = 14
) -> Dict[str, Any]:
    """
    Compute external field from RSI breadth of input universe.
    
    This is physics-correct: measures PARTICIPATION (how many tickers have
    bullish momentum) rather than the weighted aggregate (like SPY).
    
    Args:
        prices_dict: Dict mapping ticker -> price list
        rsi_period: RSI calculation period (default 14)
        
    Returns:
        Dict with h_value, breadth metrics, and interpretation
    """
    logger.info(f"[EXTERNAL FIELD] compute_discretionary_field called with {len(prices_dict) if prices_dict else 0} tickers")
    
    if not prices_dict or len(prices_dict) < 2:
        logger.warning("[EXTERNAL FIELD] Insufficient tickers for discretionary field")
        return {
            "available": False,
            "error": "Need at least 2 tickers for breadth calculation",
        }
    
    # Compute RSI for each ticker
    rsi_values = {}
    for ticker, prices in prices_dict.items():
        rsi = compute_rsi(prices, rsi_period)
        if rsi is not None:
            rsi_values[ticker] = rsi
            logger.debug(f"[RSI] {ticker}: {rsi:.1f} (prices={len(prices)})")
    
    logger.info(f"[EXTERNAL FIELD] Computed RSI for {len(rsi_values)}/{len(prices_dict)} tickers")
    
    if len(rsi_values) < 2:
        return {
            "available": False,
            "error": "Insufficient price history for RSI calculation",
        }
    
    # Breadth = % of tickers with RSI > 50
    bullish_count = sum(1 for rsi in rsi_values.values() if rsi > 50)
    breadth = bullish_count / len(rsi_values)
    
    # External field h: normalize to approximately [-1, 1]
    # breadth=0 -> h=-1 (all bearish), breadth=1 -> h=1 (all bullish)
    h_value = (breadth - 0.5) * 2
    
    logger.info(f"[EXTERNAL FIELD] RSI breadth: {bullish_count}/{len(rsi_values)} bullish ({breadth:.1%}), h={h_value:.3f}")
    
    # Percentile of current breadth against uniform distribution
    # (used for consistency with other percentile-based stats)
    h_percentile = breadth
    
    # Overbought/oversold counts
    overbought_count = sum(1 for rsi in rsi_values.values() if rsi > 70)
    oversold_count = sum(1 for rsi in rsi_values.values() if rsi < 30)
    
    # Interpretation
    if breadth > 0.7:
        bias = "BULLISH"
        interpretation = f"Strong bullish participation: {bullish_count}/{len(rsi_values)} tickers with RSI > 50"
    elif breadth > 0.55:
        bias = "MILDLY_BULLISH"
        interpretation = f"Mild bullish breadth: {bullish_count}/{len(rsi_values)} tickers positive"
    elif breadth < 0.3:
        bias = "BEARISH"
        interpretation = f"Weak breadth: only {bullish_count}/{len(rsi_values)} tickers with RSI > 50"
    elif breadth < 0.45:
        bias = "MILDLY_BEARISH"
        interpretation = f"Slightly negative breadth: {bullish_count}/{len(rsi_values)} tickers positive"
    else:
        bias = "NEUTRAL"
        interpretation = f"Balanced participation: {bullish_count}/{len(rsi_values)} tickers with RSI > 50"
    
    return {
        "available": True,
        "method": "rsi_breadth",
        "h_value": float(h_value),
        "h_percentile": float(h_percentile),
        "breadth": float(breadth),
        "bullish_count": bullish_count,
        "total_count": len(rsi_values),
        "overbought_count": overbought_count,
        "oversold_count": oversold_count,
        "bias": bias,
        "interpretation": interpretation,
        "rsi_values": rsi_values,
        "config": {
            "rsi_period": rsi_period,
            "bullish_threshold": 50,
        }
    }


# =============================================================================
# MACRO EXTERNAL FIELD (Sector Breadth + FRED Factors)
# =============================================================================

def compute_macro_field(
    sector_prices_dict: Dict[str, List[float]],
    fred_data: Optional[Dict[str, Any]] = None,
    rsi_period: int = 14,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Compute external field from macro factors: sector RSI breadth + FRED economic data.
    
    This provides economy-wide external pressure on any analysis universe.
    
    Components:
    1. RSI breadth of all 11 sector ETFs (market-wide participation)
    2. Credit spread (BAMLH0A0HYM2) - risk appetite
    3. Yield curve (T10Y2Y) - recession signal
    4. M2 YoY change - liquidity conditions
    
    Args:
        sector_prices_dict: Dict of sector ticker -> price list (all 11 sectors ideally)
        fred_data: Optional dict with 'credit_spread', 'yield_curve', 'm2_change' from FRED
        rsi_period: RSI calculation period
        weights: Optional custom weights for components
        
    Returns:
        Dict with composite h_value and component breakdown
    """
    components = {}
    available_components = []
    
    # Default weights (equal if not specified)
    default_weights = {
        "sector_breadth": 0.4,  # Primary signal
        "credit_spread": 0.2,
        "yield_curve": 0.2,
        "m2_change": 0.2,
    }
    w = weights or default_weights
    
    # =========================================================================
    # Component 1: Sector RSI Breadth (always available if we have sector data)
    # =========================================================================
    if sector_prices_dict and len(sector_prices_dict) >= 3:
        breadth_result = compute_discretionary_field(sector_prices_dict, rsi_period)
        if breadth_result.get("available"):
            components["sector_breadth"] = {
                "value": breadth_result["h_value"],  # Already in [-1, 1]
                "raw": breadth_result["breadth"],
                "bullish_count": breadth_result["bullish_count"],
                "total_count": breadth_result["total_count"],
            }
            available_components.append("sector_breadth")
    
    # =========================================================================
    # Component 2-4: FRED Factors (optional, enhances when available)
    # =========================================================================
    if fred_data:
        # Credit Spread: Higher spread = bearish (risk-off)
        # Normalize: use percentile, invert (high spread = negative h)
        if "credit_spread" in fred_data and fred_data["credit_spread"].get("available"):
            cs = fred_data["credit_spread"]
            # Percentile inverted: high spread = low h (bearish)
            cs_h = (1 - cs.get("percentile", 0.5)) * 2 - 1  # Map to [-1, 1], inverted
            components["credit_spread"] = {
                "value": cs_h,
                "raw": cs.get("current"),
                "percentile": cs.get("percentile"),
            }
            available_components.append("credit_spread")
        
        # Yield Curve: Inversion (negative) = bearish
        # Normalize: positive spread = bullish, negative = bearish
        if "yield_curve" in fred_data and fred_data["yield_curve"].get("available"):
            yc = fred_data["yield_curve"]
            # Direct: positive curve = positive h, inverted = negative h
            # Clamp to reasonable range and normalize
            yc_raw = yc.get("current", 0)
            yc_h = np.clip(yc_raw / 2.0, -1, 1)  # Assume ±2% is extreme
            components["yield_curve"] = {
                "value": yc_h,
                "raw": yc_raw,
                "percentile": yc.get("percentile"),
            }
            available_components.append("yield_curve")
        
        # M2 Change: Expansion = bullish, contraction = bearish
        if "m2_change" in fred_data and fred_data["m2_change"].get("available"):
            m2 = fred_data["m2_change"]
            # YoY change as percentage, normalize
            m2_raw = m2.get("current", 0)
            m2_h = np.clip(m2_raw / 10.0, -1, 1)  # Assume ±10% YoY is extreme
            components["m2_change"] = {
                "value": m2_h,
                "raw": m2_raw,
                "percentile": m2.get("percentile"),
            }
            available_components.append("m2_change")
    
    # =========================================================================
    # Compute Weighted Composite
    # =========================================================================
    if not available_components:
        return {
            "available": False,
            "error": "No macro field components available",
        }
    
    # Normalize weights to available components
    total_weight = sum(w.get(c, 0) for c in available_components)
    if total_weight == 0:
        total_weight = len(available_components)
        normalized_weights = {c: 1/total_weight for c in available_components}
    else:
        normalized_weights = {c: w.get(c, 0) / total_weight for c in available_components}
    
    # Weighted sum
    h_composite = sum(
        components[c]["value"] * normalized_weights[c]
        for c in available_components
    )
    
    # Interpretation
    if h_composite > 0.3:
        bias = "BULLISH"
        interpretation = "Macro factors support risk-on positioning"
    elif h_composite > 0.1:
        bias = "MILDLY_BULLISH"
        interpretation = "Slight macro tailwind"
    elif h_composite < -0.3:
        bias = "BEARISH"
        interpretation = "Macro headwinds: risk-off pressure"
    elif h_composite < -0.1:
        bias = "MILDLY_BEARISH"
        interpretation = "Slight macro headwind"
    else:
        bias = "NEUTRAL"
        interpretation = "Macro factors balanced"
    
    return {
        "available": True,
        "method": "macro_composite",
        "h_value": float(h_composite),
        "h_percentile": float((h_composite + 1) / 2),  # Map [-1,1] to [0,1]
        "bias": bias,
        "interpretation": interpretation,
        "components": components,
        "available_components": available_components,
        "weights_used": normalized_weights,
        "fred_available": fred_data is not None,
    }


# =============================================================================
# MAGNETIZATION (Order Parameter)
# =============================================================================

def compute_magnetization(
    returns_df: pd.DataFrame,
    window: int = 21
) -> Dict[str, Any]:
    """
    Compute magnetization M = (1/N) * sum(sign(returns)).
    
    Magnetization measures net market sentiment:
    - M > 0: Net bullish (more sectors up than down)
    - M < 0: Net bearish (more sectors down than up)
    - |M| ~ 1: Strong consensus
    - |M| ~ 0: Dispersed (potential critical point)
    
    Args:
        returns_df: DataFrame of daily returns (rows=dates, cols=sectors)
        window: Rolling window for smoothing
        
    Returns:
        Dict with raw values, rolling series, and current stats
    """
    n_sectors = returns_df.shape[1]
    
    # Compute daily magnetization: M(t) = mean(sign(r_i(t)))
    signs = np.sign(returns_df)
    daily_magnetization = signs.mean(axis=1)
    
    # Rolling average magnetization
    rolling_magnetization = daily_magnetization.rolling(window=window).mean()
    
    # Current values
    current_raw = daily_magnetization.iloc[-1] if len(daily_magnetization) > 0 else 0.0
    current_rolling = rolling_magnetization.iloc[-1] if len(rolling_magnetization) > window else current_raw
    
    # Direction
    if current_rolling > 0.1:
        direction = "BULLISH"
    elif current_rolling < -0.1:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    # Percentile of |M| (absolute magnetization)
    abs_magnetization = np.abs(daily_magnetization.dropna())
    current_abs = abs(current_raw)
    percentile = stats.percentileofscore(abs_magnetization, current_abs) / 100.0
    
    return {
        "raw": float(current_raw),
        "rolling": float(current_rolling) if not np.isnan(current_rolling) else float(current_raw),
        "direction": direction,
        "percentile": float(percentile),
        "signal": _percentile_to_signal(percentile),
        "history": daily_magnetization.tolist(),
        "rolling_history": rolling_magnetization.dropna().tolist(),
    }


# =============================================================================
# SUSCEPTIBILITY (Response Function)
# =============================================================================

def compute_susceptibility(
    returns_df: pd.DataFrame,
    window: int = 21
) -> Dict[str, Any]:
    """
    Compute susceptibility chi = Var(M) * N.
    
    Susceptibility measures how violently sentiment responds to perturbations:
    - Low chi: Stable regime, shocks absorbed
    - High chi: Crowded trade warning - small news causes big moves
    
    Args:
        returns_df: DataFrame of daily returns
        window: Rolling window for variance calculation
        
    Returns:
        Dict with raw values, percentile, and signal
    """
    n_sectors = returns_df.shape[1]
    
    # Daily magnetization
    signs = np.sign(returns_df)
    daily_magnetization = signs.mean(axis=1)
    
    # Rolling variance of magnetization, scaled by N
    rolling_variance = daily_magnetization.rolling(window=window).var()
    susceptibility = rolling_variance * n_sectors
    
    # Current value
    current = susceptibility.iloc[-1] if len(susceptibility) > window else 0.0
    if np.isnan(current):
        current = 0.0
    
    # Percentile against history
    valid_history = susceptibility.dropna()
    if len(valid_history) > 0:
        percentile = stats.percentileofscore(valid_history, current) / 100.0
    else:
        percentile = 0.5
    
    return {
        "raw": float(current),
        "percentile": float(percentile),
        "signal": _percentile_to_signal(percentile),
        "history": susceptibility.dropna().tolist(),
    }


# =============================================================================
# CORRELATION LENGTH (Herding Spread)
# =============================================================================

def compute_correlation_length(
    returns_df: pd.DataFrame,
    window: int = 21
) -> Dict[str, Any]:
    """
    Compute correlation length xi = mean(|corr_ij|).
    
    Correlation length measures how far herding spreads:
    - Low xi: Idiosyncratic moves, stock-picking works
    - High xi: Everything moving together -> risk-off herding
    
    Args:
        returns_df: DataFrame of daily returns
        window: Rolling window for correlation calculation
        
    Returns:
        Dict with raw values, percentile, correlation matrix, and signal
    """
    n_sectors = returns_df.shape[1]
    
    # Compute rolling correlation length
    correlation_lengths = []
    dates = []
    
    for i in range(window, len(returns_df)):
        window_data = returns_df.iloc[i-window:i]
        corr_matrix = window_data.corr()
        
        # Average absolute off-diagonal correlation
        # xi = (2 / N(N-1)) * sum_{i<j}[ |rho_ij| ]
        upper_tri = np.triu(corr_matrix.values, k=1)
        abs_corrs = np.abs(upper_tri)
        n_pairs = n_sectors * (n_sectors - 1) / 2
        avg_abs_corr = abs_corrs.sum() / n_pairs if n_pairs > 0 else 0
        
        correlation_lengths.append(avg_abs_corr)
        if hasattr(returns_df.index, '__iter__'):
            dates.append(returns_df.index[i] if i < len(returns_df.index) else i)
    
    correlation_lengths = np.array(correlation_lengths)
    
    # Current value
    current = correlation_lengths[-1] if len(correlation_lengths) > 0 else 0.0
    
    # Percentile
    if len(correlation_lengths) > 0:
        percentile = stats.percentileofscore(correlation_lengths, current) / 100.0
    else:
        percentile = 0.5
    
    # Current correlation matrix
    recent_window = returns_df.iloc[-window:]
    current_corr_matrix = recent_window.corr()
    
    return {
        "raw": float(current),
        "percentile": float(percentile),
        "signal": _percentile_to_signal(percentile),
        "correlation_matrix": current_corr_matrix.to_dict(),
        "history": correlation_lengths.tolist(),
    }


# =============================================================================
# CRITICAL SLOWING DOWN (Relaxation Time)
# =============================================================================

def compute_critical_slowing_down(
    returns_df: pd.DataFrame,
    window: int = 21
) -> Dict[str, Any]:
    """
    Compute critical slowing down tau = AR(1) coefficient of magnetization.
    
    Near phase transitions, the system takes longer to return to equilibrium:
    - Low tau: Random, no momentum
    - Medium tau: Normal trending
    - High tau: Approaching phase transition - momentum persists
    
    Args:
        returns_df: DataFrame of daily returns
        window: Rolling window for AR(1) calculation
        
    Returns:
        Dict with raw values, percentile, and signal
    """
    # Daily magnetization
    signs = np.sign(returns_df)
    daily_magnetization = signs.mean(axis=1)
    
    # Rolling AR(1) coefficient: corr(M_t, M_{t-1})
    ar1_values = []
    
    for i in range(window, len(daily_magnetization)):
        window_data = daily_magnetization.iloc[i-window:i].values
        if len(window_data) >= 2:
            # Correlation between M(t) and M(t-1)
            m_t = window_data[1:]
            m_t_minus_1 = window_data[:-1]
            
            if np.std(m_t) > 1e-9 and np.std(m_t_minus_1) > 1e-9:
                ar1 = np.corrcoef(m_t, m_t_minus_1)[0, 1]
                ar1_values.append(ar1 if not np.isnan(ar1) else 0.0)
            else:
                ar1_values.append(0.0)
    
    ar1_values = np.array(ar1_values)
    
    # Current value
    current = ar1_values[-1] if len(ar1_values) > 0 else 0.0
    
    # Percentile (higher AR1 = more concerning)
    if len(ar1_values) > 0:
        percentile = stats.percentileofscore(ar1_values, current) / 100.0
    else:
        percentile = 0.5
    
    return {
        "raw": float(current),
        "percentile": float(percentile),
        "signal": _percentile_to_signal(percentile),
        "history": ar1_values.tolist(),
    }


# =============================================================================
# TEMPERATURE (T) - From VIX
# =============================================================================

def compute_temperature(
    vix_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute temperature (T) from VIX data.
    
    In the Ising model, temperature controls disorder:
    - High T: Random spins, system in disordered state
    - Low T: Ordered spins, system in coherent state
    - Critical T: Phase transition (herding <-> dispersed)
    
    We use percentile-based normalization against the lookback history.
    
    Args:
        vix_data: Dict with 'values', 'current', 'history' from data_fetcher
        
    Returns:
        Dict with T_percentile, regime, and interpretation
    """
    if not vix_data or not vix_data.get("values"):
        return {
            "available": False,
            "error": "No VIX data available",
        }
    
    values = vix_data["values"]
    current = vix_data.get("current", values[-1] if values else None)
    
    if current is None:
        return {
            "available": False,
            "error": "No current VIX value",
        }
    
    # Percentile of current VIX against its own history (self-normalizing)
    T_percentile = stats.percentileofscore(values, current) / 100.0
    
    # Temperature regime interpretation
    if T_percentile > 0.80:
        T_regime = "HIGH_TEMP"
        interpretation = "High volatility regime - random/disordered market, herding signals less reliable"
    elif T_percentile < 0.20:
        T_regime = "LOW_TEMP"
        interpretation = "Low volatility regime - ordered market, herding signals more persistent"
    else:
        T_regime = "NORMAL_TEMP"
        interpretation = "Normal volatility regime"
    
    return {
        "available": True,
        "vix_current": float(current),
        "T_percentile": float(T_percentile),
        "T_regime": T_regime,
        "interpretation": interpretation,
        "vix_history": values,
    }


# =============================================================================
# EXTERNAL FIELD (h) - DEPRECATED: SPY Momentum
# =============================================================================

def compute_external_field(
    benchmark_data: Optional[Dict[str, Any]],
    long_weight: float = 0.7,
    short_weight: float = 0.3
) -> Dict[str, Any]:
    """
    DEPRECATED: Use compute_discretionary_field() or compute_macro_field() instead.
    
    This function used SPY momentum as the external field, which is incorrect
    physics - SPY is the aggregate of the spins, not an external force.
    
    Kept for backward compatibility only.
    
    Args:
        benchmark_data: Dict with 'momentum', 'momentum_short', 'symbol' from data_fetcher
        long_weight: Weight for long-term momentum (default 0.7)
        short_weight: Weight for short-term momentum (default 0.3)
        
    Returns:
        Dict with h_value, bias direction, and interpretation
    """
    import warnings
    warnings.warn(
        "compute_external_field is deprecated. Use compute_discretionary_field or compute_macro_field instead.",
        DeprecationWarning
    )
    if not benchmark_data:
        return {
            "available": False,
            "error": "No benchmark data available",
        }
    
    symbol = benchmark_data.get("symbol", "SPY")
    momentum = benchmark_data.get("momentum")
    # Support both new and old field names
    momentum_short = benchmark_data.get("momentum_short") or benchmark_data.get("momentum_5d")
    
    if momentum is None:
        return {
            "available": False,
            "error": f"No {symbol} momentum calculated",
        }
    
    # External field = benchmark momentum (percentage above/below MA)
    h_value = momentum
    
    # Also use short-term momentum as short-term field
    h_short = momentum_short if momentum_short is not None else 0.0
    
    # Combined field (weighted average with configurable weights)
    h_combined = long_weight * h_value + short_weight * h_short
    
    # Get MA window from data for interpretation
    ma_window = benchmark_data.get("ma_window", 20)
    short_window = benchmark_data.get("short_window", 5)
    
    # Bias interpretation
    if h_combined > 0.02:  # > 2% above MA
        bias = "BULLISH"
        interpretation = f"Strong bullish external field from {symbol} - sectors biased upward"
    elif h_combined > 0.005:  # > 0.5% above MA
        bias = "MILDLY_BULLISH"
        interpretation = f"Mild bullish bias from {symbol} momentum"
    elif h_combined < -0.02:  # > 2% below MA
        bias = "BEARISH"
        interpretation = f"Strong bearish external field from {symbol} - sectors biased downward"
    elif h_combined < -0.005:  # > 0.5% below MA
        bias = "MILDLY_BEARISH"
        interpretation = f"Mild bearish bias from {symbol} momentum"
    else:
        bias = "NEUTRAL"
        interpretation = "No significant external field - intrinsic herding dynamics dominate"
    
    # Percentile of momentum against returns history
    returns = benchmark_data.get("returns", [])
    if returns and len(returns) > ma_window:
        # Use cumulative returns over MA window as comparison
        rolling_returns = []
        for i in range(ma_window, len(returns)):
            cum_ret = sum(returns[i-ma_window:i])
            rolling_returns.append(cum_ret)
        if rolling_returns:
            h_percentile = stats.percentileofscore(rolling_returns, h_value * ma_window) / 100.0
        else:
            h_percentile = 0.5
    else:
        h_percentile = 0.5
    
    return {
        "available": True,
        "symbol": symbol,
        "h_momentum": float(h_value),
        "h_momentum_short": float(h_short),
        "h_combined": float(h_combined),
        "h_percentile": float(h_percentile),
        "bias": bias,
        "interpretation": interpretation,
        "config": {
            "ma_window": ma_window,
            "short_window": short_window,
            "long_weight": long_weight,
            "short_weight": short_weight,
        }
    }


# =============================================================================
# COUPLING STRENGTH (J) - From Options Flow
# =============================================================================

def compute_coupling_strength(
    returns_df: pd.DataFrame,
    greek_flow_data: Optional[Dict[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Compute coupling strength (J) from options delta flow.
    
    In the Ising model, coupling (J) determines how strongly neighboring spins interact:
    - High J: Strong herding, spins strongly influence each other
    - Low J: Weak herding, spins move independently
    
    We measure this as correlation between:
    - Price-based magnetization (backward-looking)
    - Options delta flow magnetization (forward-looking)
    
    Divergence between them signals regime transition.
    
    Args:
        returns_df: DataFrame of daily returns
        greek_flow_data: Dict mapping sector -> greek flow data
        
    Returns:
        Dict with J_effective, divergence signal, and interpretation
    """
    if not greek_flow_data or len(greek_flow_data) < 3:
        return {
            "available": False,
            "error": "Insufficient greek flow data for coupling calculation",
        }
    
    # Compute price-based magnetization for sectors with greek flow
    sectors_with_flow = set(greek_flow_data.keys()) & set(returns_df.columns)
    
    if len(sectors_with_flow) < 3:
        return {
            "available": False,
            "error": f"Only {len(sectors_with_flow)} sectors have both price and flow data",
        }
    
    # Price magnetization: sign of latest return
    price_signs = {}
    for sector in sectors_with_flow:
        if sector in returns_df.columns:
            latest_return = returns_df[sector].iloc[-1]
            price_signs[sector] = np.sign(latest_return)
    
    # Options magnetization: sign of delta flow
    options_signs = {}
    for sector in sectors_with_flow:
        flow = greek_flow_data.get(sector, {})
        delta_flow = flow.get("delta_flow", 0)
        options_signs[sector] = np.sign(delta_flow) if delta_flow != 0 else 0
    
    # Compute magnetizations
    M_price = np.mean(list(price_signs.values())) if price_signs else 0
    M_options = np.mean(list(options_signs.values())) if options_signs else 0
    
    # Agreement between price and options sentiment
    agreement_count = sum(
        1 for s in sectors_with_flow
        if price_signs.get(s, 0) == options_signs.get(s, 0) and price_signs.get(s, 0) != 0
    )
    agreement_rate = agreement_count / len(sectors_with_flow) if sectors_with_flow else 0
    
    # Coupling strength J = correlation/agreement between the two signals
    # High agreement = strong coupling (options and price aligned)
    J_effective = agreement_rate
    
    # Divergence detection
    # If options are bullish but price is bearish (or vice versa), that's divergence
    divergence = False
    divergence_direction = None
    
    if M_options > 0.3 and M_price < -0.3:
        divergence = True
        divergence_direction = "OPTIONS_BULLISH_PRICE_BEARISH"
    elif M_options < -0.3 and M_price > 0.3:
        divergence = True
        divergence_direction = "OPTIONS_BEARISH_PRICE_BULLISH"
    
    # Interpretation
    if J_effective > 0.7:
        signal = "STRONG_COUPLING"
        interpretation = "Options and price strongly aligned - herding is coherent"
    elif J_effective > 0.4:
        signal = "MODERATE_COUPLING"
        interpretation = "Moderate agreement between options and price signals"
    else:
        signal = "WEAK_COUPLING"
        interpretation = "Weak coupling - options and price diverging, potential regime change"
    
    if divergence:
        interpretation = f"DIVERGENCE DETECTED: {divergence_direction}. Potential reversal signal."
    
    return {
        "available": True,
        "J_effective": float(J_effective),
        "M_price": float(M_price),
        "M_options": float(M_options),
        "agreement_rate": float(agreement_rate),
        "divergence": divergence,
        "divergence_direction": divergence_direction,
        "signal": signal,
        "interpretation": interpretation,
        "sectors_analyzed": list(sectors_with_flow),
    }


# =============================================================================
# PCA-WEIGHTED COMPOSITE INDEX
# =============================================================================

def compute_composite_herding_index(
    magnetization: Dict[str, Any],
    susceptibility: Dict[str, Any],
    correlation_length: Dict[str, Any],
    critical_slowing_down: Dict[str, Any],
    use_pca: bool = True
) -> Dict[str, Any]:
    """
    Compute composite herding index using PCA weighting.
    
    Instead of arbitrary weights, use the first principal component
    to find the dominant "herding factor".
    
    Args:
        magnetization: Output from compute_magnetization
        susceptibility: Output from compute_susceptibility
        correlation_length: Output from compute_correlation_length
        critical_slowing_down: Output from compute_critical_slowing_down
        use_pca: If True, use PCA weights. If False, use equal weights.
        
    Returns:
        Dict with composite index, weights, regime, and risk level
    """
    # Get percentiles (already normalized 0-1)
    p_mag = magnetization["percentile"]
    p_sus = susceptibility["percentile"]
    p_corr = correlation_length["percentile"]
    p_ar1 = critical_slowing_down["percentile"]
    
    current_percentiles = np.array([p_sus, p_corr, p_ar1, p_mag])
    
    # Build historical percentile matrix for PCA
    # Use the shortest history available
    histories = [
        susceptibility.get("history", []),
        correlation_length.get("history", []),
        critical_slowing_down.get("history", []),
        np.abs(magnetization.get("history", [])).tolist() if magnetization.get("history") else []
    ]
    
    min_len = min(len(h) for h in histories) if all(histories) else 0
    
    if use_pca and min_len >= 30:
        # Compute percentiles for each historical point
        percentile_matrix = []
        
        for i in range(min_len):
            row_percentiles = []
            for h in histories:
                # Percentile of this point against full history
                pct = stats.percentileofscore(h, h[i]) / 100.0
                row_percentiles.append(pct)
            percentile_matrix.append(row_percentiles)
        
        X = np.array(percentile_matrix)
        
        try:
            # PCA to find dominant herding factor
            pca = PCA(n_components=1)
            pca.fit(X)
            
            # Weights from first PC loadings (normalized to sum to 1)
            weights = np.abs(pca.components_[0])
            weights = weights / weights.sum()
            
            # Explained variance
            explained_variance = float(pca.explained_variance_ratio_[0])
            
        except Exception as e:
            logger.warning(f"PCA failed, using equal weights: {e}")
            weights = np.array([0.25, 0.25, 0.25, 0.25])
            explained_variance = None
    else:
        # Equal weights if not enough history
        weights = np.array([0.25, 0.25, 0.25, 0.25])
        explained_variance = None
    
    # Compute composite index
    herding_index = float(np.dot(weights, current_percentiles))
    
    # Determine regime and risk level
    regime, risk_level = _herding_index_to_regime(herding_index)
    
    return {
        "value": herding_index,
        "regime": regime,
        "risk_level": risk_level,
        "pca_weights": {
            "susceptibility": float(weights[0]),
            "correlation_length": float(weights[1]),
            "critical_slowing_down": float(weights[2]),
            "magnetization": float(weights[3]),
        },
        "explained_variance": explained_variance,
        "method": "pca" if use_pca and min_len >= 30 else "equal_weights",
    }


# =============================================================================
# MAIN COMPUTATION FUNCTION
# =============================================================================

def compute_all_ising_statistics(
    returns_df: pd.DataFrame,
    window: int = 21,
    use_pca: bool = True,
    vix_data: Optional[Dict[str, Any]] = None,
    prices_dict: Optional[Dict[str, List[float]]] = None,
    greek_flow_data: Optional[Dict[str, Dict[str, Any]]] = None,
    field_mode: str = "discretionary",
    rsi_period: int = 14,
    # Macro mode params
    sector_prices_dict: Optional[Dict[str, List[float]]] = None,
    fred_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute all Ising model statistics, parameters, and composite herding index.
    
    Args:
        returns_df: DataFrame of daily returns (rows=dates, cols=tickers)
        window: Rolling window for calculations
        use_pca: Whether to use PCA for composite index weighting
        vix_data: VIX history for temperature (T) calculation
        prices_dict: Dict of ticker -> prices for discretionary field (RSI breadth of input)
        greek_flow_data: Sector greek flow for coupling (J) calculation
        field_mode: "discretionary" or "macro"
            - discretionary: RSI breadth of input tickers (internal participation)
            - macro: RSI breadth of all sectors + FRED factors (external pressure)
        rsi_period: RSI period for field calculation (default 14)
        sector_prices_dict: Dict of all sector ETF prices (for macro mode)
        fred_data: FRED economic data (for macro mode): credit_spread, yield_curve, m2_change
        
    Returns:
        Dict with all statistics, Ising parameters, composite index, and interpretation
    """
    if returns_df.empty or len(returns_df) < window + 10:
        logger.warning(f"Insufficient data: {len(returns_df)} rows, need {window + 10}")
        return {
            "status": "error",
            "error": f"Insufficient data: need at least {window + 10} observations",
        }
    
    logger.info(f"Computing Ising statistics on {len(returns_df)} observations, {returns_df.shape[1]} tickers")
    
    # =========================================================================
    # COMPUTE BASE STATISTICS
    # =========================================================================
    magnetization = compute_magnetization(returns_df, window)
    susceptibility = compute_susceptibility(returns_df, window)
    correlation_length = compute_correlation_length(returns_df, window)
    critical_slowing_down = compute_critical_slowing_down(returns_df, window)
    
    # =========================================================================
    # COMPUTE ISING PARAMETERS (T, h, J)
    # =========================================================================
    
    # Temperature (T) from VIX
    temperature = compute_temperature(vix_data)
    
    # External Field (h) - choose based on field_mode
    logger.info(f"[EXTERNAL FIELD] Computing external field: mode={field_mode}, prices_dict={len(prices_dict) if prices_dict else 0}, sector_prices={len(sector_prices_dict) if sector_prices_dict else 0}, fred_data={fred_data is not None}")
    
    if field_mode == "macro":
        # Macro: RSI breadth of ALL sectors + FRED factors
        # Use sector_prices_dict if provided, otherwise fall back to prices_dict
        macro_prices = sector_prices_dict or prices_dict
        logger.info(f"[EXTERNAL FIELD] Macro mode: using {len(macro_prices) if macro_prices else 0} tickers for RSI breadth")
        external_field = compute_macro_field(macro_prices, fred_data, rsi_period)
    elif field_mode == "discretionary" and prices_dict:
        # Discretionary: RSI breadth of input tickers only
        logger.info(f"[EXTERNAL FIELD] Discretionary mode: using {len(prices_dict)} input tickers")
        external_field = compute_discretionary_field(prices_dict, rsi_period)
    else:
        # Fallback: try discretionary with whatever prices we have
        logger.warning(f"[EXTERNAL FIELD] Fallback mode: prices_dict={prices_dict is not None}, sector_prices={sector_prices_dict is not None}")
        if prices_dict:
            external_field = compute_discretionary_field(prices_dict, rsi_period)
        elif sector_prices_dict:
            external_field = compute_macro_field(sector_prices_dict, fred_data, rsi_period)
        else:
            external_field = {"available": False, "error": "No price data provided for external field"}
    
    logger.info(f"[EXTERNAL FIELD] Result: available={external_field.get('available')}, h={external_field.get('h_value') or external_field.get('h_combined', 'N/A')}")
    
    # Coupling (J) from options flow
    coupling = compute_coupling_strength(returns_df, greek_flow_data)
    
    # =========================================================================
    # COMPUTE ADJUSTED STATISTICS
    # =========================================================================
    
    # Temperature-adjusted susceptibility
    # High T (high VIX) = dampen susceptibility signal (less meaningful in chaotic regime)
    susceptibility_adjusted = susceptibility.copy()
    if temperature.get("available") and temperature.get("T_percentile") is not None:
        T_percentile = temperature["T_percentile"]
        # Weight DOWN when VIX is high (damping factor)
        T_weight = 1 - (T_percentile * 0.5)  # Range: 0.5 to 1.0
        susceptibility_adjusted["raw_adjusted"] = susceptibility["raw"] * T_weight
        susceptibility_adjusted["percentile_adjusted"] = susceptibility["percentile"] * T_weight
        susceptibility_adjusted["T_adjustment_factor"] = float(T_weight)
    
    # Field-corrected magnetization
    # Subtract external field bias to see "intrinsic" magnetization
    magnetization_adjusted = magnetization.copy()
    if external_field.get("available") and external_field.get("h_combined") is not None:
        h = external_field["h_combined"]
        # Scale h to magnetization range (-1 to 1)
        h_scaled = np.clip(h * 10, -0.5, 0.5)  # Scale and clip
        M_corrected = magnetization["raw"] - h_scaled
        magnetization_adjusted["raw_field_corrected"] = float(M_corrected)
        magnetization_adjusted["field_bias_removed"] = float(h_scaled)
    
    # =========================================================================
    # COMPUTE COMPOSITE INDEX
    # =========================================================================
    herding_index = compute_composite_herding_index(
        magnetization,
        susceptibility,
        correlation_length,
        critical_slowing_down,
        use_pca=use_pca
    )
    
    # =========================================================================
    # SIGNAL SUMMARY AND TRADING IMPLICATIONS
    # =========================================================================
    signals = [
        magnetization["signal"],
        susceptibility["signal"],
        correlation_length["signal"],
        critical_slowing_down["signal"]
    ]
    elevated_count = sum(1 for s in signals if s in ["ELEVATED", "CRITICAL"])
    
    # Trading implications (enhanced with T, h, J)
    if herding_index["value"] > 0.6:
        crowding_risk = "HIGH"
        momentum_regime = "TRENDING"
    elif herding_index["value"] > 0.4:
        crowding_risk = "MODERATE"
        momentum_regime = "MIXED"
    else:
        crowding_risk = "LOW"
        momentum_regime = "DISPERSED"
    
    if correlation_length["percentile"] > 0.8:
        contagion_risk = "HIGH"
    elif correlation_length["percentile"] > 0.6:
        contagion_risk = "MODERATE"
    else:
        contagion_risk = "LOW"
    
    # Enhanced implications from Ising parameters
    regime_confidence = "NORMAL"
    if temperature.get("available"):
        if temperature["T_regime"] == "LOW_TEMP":
            regime_confidence = "HIGH"  # Signals more reliable in low-vol regime
        elif temperature["T_regime"] == "HIGH_TEMP":
            regime_confidence = "LOW"  # Signals less reliable in high-vol regime
    
    reversal_warning = False
    if coupling.get("available") and coupling.get("divergence"):
        reversal_warning = True
    
    return {
        "status": "success",
        "herding_index": herding_index,
        "ising_statistics": {
            "magnetization": magnetization_adjusted,
            "susceptibility": susceptibility_adjusted,
            "correlation_length": correlation_length,
            "critical_slowing_down": critical_slowing_down,
        },
        "ising_parameters": {
            "temperature": temperature,
            "external_field": external_field,
            "coupling": coupling,
        },
        "signal_summary": {
            "elevated_count": elevated_count,
            "total_signals": 4,
            "signals": signals,
        },
        "trading_implications": {
            "crowding_risk": crowding_risk,
            "contagion_risk": contagion_risk,
            "momentum_regime": momentum_regime,
            "regime_confidence": regime_confidence,
            "reversal_warning": reversal_warning,
        },
        "metadata": {
            "window": window,
            "n_observations": len(returns_df),
            "n_sectors": returns_df.shape[1],
            "sectors": list(returns_df.columns),
            "vix_available": temperature.get("available", False),
            "spy_available": external_field.get("available", False),
            "greek_flow_available": coupling.get("available", False),
        },
    }

