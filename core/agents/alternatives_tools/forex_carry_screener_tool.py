"""
Forex Carry Trade Screener Tool

Screens FX pairs by risk-adjusted carry (if rates provided) or volatility metrics.

Carry Trade Logic:
- Borrow in low-yield currency, invest in high-yield currency
- Carry = Interest rate differential
- Risk = FX volatility can wipe out carry gains

Regime Detection:
- Z-Score Based (default): Simple threshold classification
- HMM Based (optional): Hidden Markov Model learns regimes from data
  - States are NOT hardcoded - characterized by their features
  - Performance multipliers calculated from actual carry returns per state
"""

import asyncio
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents import function_tool
from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


def _check_cancellation(context: str = ""):
    """Check if cancellation was requested and raise CancelledError if so."""
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CANCEL] forex_carry_screener cancelled{' during ' + context if context else ''}")
        raise asyncio.CancelledError(f"forex_carry_screener cancelled{' during ' + context if context else ''}")


# =============================================================================
# AVAILABLE FEATURE FAMILIES (User selects which to use)
# =============================================================================

FEATURE_FAMILIES = {
    # ===== VOLATILITY (Core - recommended) =====
    "volatility": {
        "description": "Volatility measures - high vol is typically bad for carry",
        "features": ["vol_avg", "vol_max", "vol_min", "vol_range"]
    },
    "vol_dynamics": {
        "description": "Volatility changes over time - trend and acceleration",
        "features": ["vol_trend", "vol_acceleration", "vol_dispersion"]
    },
    
    # ===== MOMENTUM (Core - recommended) =====
    "momentum": {
        "description": "Return momentum - direction of FX moves",
        "features": ["ret_avg", "ret_sum", "ret_std"]
    },
    
    # ===== CORRELATION (Core - recommended) =====
    "correlation": {
        "description": "Cross-pair correlation - risk-on/off indicator",
        "features": ["cross_corr_avg", "cross_corr_std"]
    },
    
    # ===== ADVANCED (Optional) =====
    "higher_moments": {
        "description": "Skew and kurtosis - tail risk indicators",
        "features": ["skew", "kurtosis"]
    },
    "autocorrelation": {
        "description": "Serial correlation - trending vs mean-reverting",
        "features": ["autocorr_1", "autocorr_5"]
    },
    "range": {
        "description": "Price range measures - volatility proxy",
        "features": ["range_avg", "range_vs_vol"]
    },
}

# Default: focused set for regime detection (4 families, not excessive)
DEFAULT_FEATURE_FAMILIES = ["volatility", "vol_dynamics", "momentum", "correlation"]


# =============================================================================
# HMM REGIME DETECTOR FOR CARRY TRADES
# =============================================================================

class CarryRegimeDetector:
    """
    Hidden Markov Model regime detector for FX carry trades.
    
    Key principles:
    1. Features are CONFIGURABLE - user selects which feature families to use
    2. States are NOT named - described by their feature characteristics
    3. Performance multipliers are CALCULATED from data
    """
    
    def __init__(self, n_states: int = 3, feature_families: Optional[List[str]] = None):
        """
        Initialize detector.
        
        Args:
            n_states: Number of hidden states (default 3)
            feature_families: List of feature families to use
        """
        self.n_states = n_states
        self.model = None
        self._fitted = False
        
        # Parse feature families
        if feature_families is None:
            self.feature_families = DEFAULT_FEATURE_FAMILIES.copy()
        elif feature_families == ["all"] or feature_families == "all":
            self.feature_families = list(FEATURE_FAMILIES.keys())
        else:
            # Validate families
            valid_families = []
            for fam in feature_families:
                if fam in FEATURE_FAMILIES:
                    valid_families.append(fam)
                else:
                    logger.warning(f"[CarryHMM] Unknown feature family '{fam}', skipping")
            self.feature_families = valid_families if valid_families else DEFAULT_FEATURE_FAMILIES.copy()
        
        # Build feature list from families
        self.feature_names = []
        for fam in self.feature_families:
            self.feature_names.extend(FEATURE_FAMILIES[fam]["features"])
        
        logger.info(f"[CarryHMM] Using feature families: {self.feature_families}")
        logger.info(f"[CarryHMM] Total features: {len(self.feature_names)}")
    
    def _compute_features(
        self, 
        prices_dict: Dict[str, pd.DataFrame], 
        window: int = 21
    ) -> Optional[Tuple[np.ndarray, pd.DatetimeIndex, List[str]]]:
        """
        Compute selected HMM features from FX price data.
        """
        if len(prices_dict) < 2:
            logger.warning("[CarryHMM] Need at least 2 pairs for regime detection")
            return None
        
        logger.info(f"[CarryHMM] Processing {len(prices_dict)} pairs with {len(self.feature_names)} features")
        
        # Align all price series
        price_series = {}
        for pair, df in prices_dict.items():
            if 'date' in df.columns:
                series = df.set_index('date')['price']
            elif isinstance(df.index, pd.DatetimeIndex):
                series = df['price']
            else:
                continue
            price_series[pair] = series
        
        all_prices = pd.DataFrame(price_series)
        all_prices = all_prices.ffill(limit=3).dropna()
        
        logger.info(f"[CarryHMM] Aligned data: {len(all_prices)} rows")
        
        min_required = window * 2 + 10
        if len(all_prices) < min_required:
            logger.warning(f"[CarryHMM] Insufficient data: {len(all_prices)} (need {min_required})")
            return None
        
        # Calculate returns
        returns = all_prices.pct_change().dropna()
        
        # Compute features
        computed_features = {}
        
        # Pre-compute common values
        pair_vols = returns.rolling(window).std() * np.sqrt(252)
        vol_avg = pair_vols.mean(axis=1)
        avg_returns = returns.mean(axis=1)
        
        # ===== VOLATILITY FAMILY =====
        if "volatility" in self.feature_families:
            computed_features["vol_avg"] = vol_avg
            computed_features["vol_max"] = pair_vols.max(axis=1)
            computed_features["vol_min"] = pair_vols.min(axis=1)
            computed_features["vol_range"] = computed_features["vol_max"] - computed_features["vol_min"]
        
        # ===== VOL DYNAMICS FAMILY =====
        if "vol_dynamics" in self.feature_families:
            computed_features["vol_trend"] = vol_avg.diff(5)
            computed_features["vol_acceleration"] = vol_avg.diff(5).diff(5)
            computed_features["vol_dispersion"] = pair_vols.std(axis=1)
        
        # ===== MOMENTUM FAMILY =====
        if "momentum" in self.feature_families:
            computed_features["ret_avg"] = avg_returns.rolling(window).mean()
            computed_features["ret_sum"] = avg_returns.rolling(window).sum()
            computed_features["ret_std"] = avg_returns.rolling(window).std()
        
        # ===== CORRELATION FAMILY =====
        if "correlation" in self.feature_families:
            cross_corrs, cross_corr_stds = [], []
            for i in range(len(returns)):
                if i < window:
                    cross_corrs.append(np.nan)
                    cross_corr_stds.append(np.nan)
                else:
                    window_df = returns.iloc[i-window:i]
                    corr_matrix = window_df.corr()
                    mask = ~np.eye(corr_matrix.shape[0], dtype=bool)
                    vals = corr_matrix.values[mask]
                    cross_corrs.append(vals.mean() if len(vals) > 0 else 0)
                    cross_corr_stds.append(vals.std() if len(vals) > 0 else 0)
            computed_features["cross_corr_avg"] = pd.Series(cross_corrs, index=returns.index)
            computed_features["cross_corr_std"] = pd.Series(cross_corr_stds, index=returns.index)
        
        # ===== HIGHER MOMENTS FAMILY =====
        if "higher_moments" in self.feature_families:
            computed_features["skew"] = avg_returns.rolling(window).skew()
            computed_features["kurtosis"] = avg_returns.rolling(window).kurt()
        
        # ===== AUTOCORRELATION FAMILY =====
        if "autocorrelation" in self.feature_families:
            def rolling_autocorr(series, w, lag):
                return series.rolling(w).apply(
                    lambda x: pd.Series(x).autocorr(lag=lag) if len(x) > lag else 0,
                    raw=False
                )
            computed_features["autocorr_1"] = rolling_autocorr(avg_returns, window, 1)
            computed_features["autocorr_5"] = rolling_autocorr(avg_returns, window, 5)
        
        # ===== RANGE FAMILY =====
        if "range" in self.feature_families:
            high = all_prices.rolling(window).max()
            low = all_prices.rolling(window).min()
            price_range = ((high - low) / (low + 1e-9)).mean(axis=1)
            computed_features["range_avg"] = price_range
            computed_features["range_vs_vol"] = price_range / (vol_avg + 1e-9)
        
        # Filter to only selected features
        selected_features = {k: v for k, v in computed_features.items() if k in self.feature_names}
        
        if not selected_features:
            logger.warning("[CarryHMM] No features computed")
            return None
        
        # Combine into DataFrame
        features_df = pd.DataFrame(selected_features).dropna()
        
        min_feature_obs = self.n_states * 10
        if len(features_df) < min_feature_obs:
            logger.warning(f"[CarryHMM] Insufficient features: {len(features_df)} (need {min_feature_obs})")
            return None
        
        actual_feature_names = list(features_df.columns)
        logger.info(f"[CarryHMM] Computed {len(features_df)} observations with {len(actual_feature_names)} features")
        
        return features_df.values, features_df.index, actual_feature_names
    
    def fit_predict(
        self, 
        prices_dict: Dict[str, pd.DataFrame],
        window: int = 21
    ) -> Optional[Dict[str, Any]]:
        """
        Fit HMM and describe each state by its characteristics and performance.
        """
        try:
            from hmmlearn import hmm
        except ImportError:
            logger.warning("[CarryHMM] hmmlearn not installed, skipping regime detection")
            return None
        
        result = self._compute_features(prices_dict, window)
        if result is None:
            return None
        
        observations, dates, feature_names = result
        
        # Standardize features
        means = np.nanmean(observations, axis=0)
        stds = np.nanstd(observations, axis=0) + 1e-9
        standardized = (observations - means) / stds
        
        # Handle NaN
        valid_mask = ~np.isnan(standardized).any(axis=1)
        clean_obs = standardized[valid_mask]
        clean_dates = dates[valid_mask]
        raw_obs = observations[valid_mask]
        
        min_clean = self.n_states * 8
        if len(clean_obs) < min_clean:
            logger.warning(f"[CarryHMM] Not enough clean obs: {len(clean_obs)} (need {min_clean})")
            return None
        
        logger.info(f"[CarryHMM] Fitting HMM with {len(clean_obs)} observations, {len(feature_names)} features")
        
        # Fit HMM
        try:
            self.model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="diag",
                n_iter=100,
                random_state=42
            )
            self.model.fit(clean_obs)
            self._fitted = True
        except Exception as e:
            logger.warning(f"[CarryHMM] Fitting failed: {e}")
            return None
        
        # Get state sequence and probabilities
        state_sequence = self.model.predict(clean_obs)
        state_probs = self.model.predict_proba(clean_obs)
        current_probs = state_probs[-1]
        current_state_idx = int(np.argmax(current_probs))
        
        # Build state descriptions
        states = {}
        
        for state_idx in range(self.n_states):
            state_means_std = self.model.means_[state_idx]
            state_means_original = state_means_std * stds + means
            
            # Build characteristics dict
            characteristics = {}
            for i, fname in enumerate(feature_names):
                characteristics[fname] = {
                    "value": float(state_means_original[i]),
                    "z_score": float(state_means_std[i])
                }
            
            # Identify dominant features (|z_score| > 0.5)
            dominant_features = []
            for fname, vals in characteristics.items():
                if abs(vals["z_score"]) > 0.5:
                    direction = "high" if vals["z_score"] > 0 else "low"
                    dominant_features.append({
                        "feature": fname,
                        "z_score": vals["z_score"],
                        "direction": direction
                    })
            dominant_features.sort(key=lambda x: abs(x["z_score"]), reverse=True)
            
            # Calculate carry performance
            mask = state_sequence == state_idx
            n_days_in_state = int(mask.sum())
            
            # Find volatility feature for multiplier calculation
            vol_feature_idx = None
            for i, fname in enumerate(feature_names):
                if 'vol' in fname.lower() and 'avg' in fname.lower():
                    vol_feature_idx = i
                    break
            if vol_feature_idx is None:
                vol_feature_idx = 0
            
            if n_days_in_state > 5 and vol_feature_idx is not None:
                state_vol = raw_obs[mask, vol_feature_idx].mean()
                overall_vol = raw_obs[:, vol_feature_idx].mean()
                
                if overall_vol > 0 and state_vol > 0:
                    carry_multiplier = overall_vol / state_vol
                    carry_multiplier = np.clip(carry_multiplier, 0.3, 2.0)
                else:
                    carry_multiplier = 1.0
            else:
                carry_multiplier = 1.0
            
            persistence = float(self.model.transmat_[state_idx, state_idx])
            
            states[f"state_{state_idx}"] = {
                "characteristics": characteristics,
                "dominant_features": dominant_features[:5],
                "carry_performance": {
                    "multiplier": round(float(carry_multiplier), 3),
                    "interpretation": self._interpret_multiplier(carry_multiplier)
                },
                "current_probability": float(current_probs[state_idx]),
                "persistence": round(persistence, 3),
                "days_in_sample": n_days_in_state,
                "pct_of_sample": round(n_days_in_state / len(state_sequence) * 100, 1)
            }
        
        # Identify best/worst states
        best_state = max(states.keys(), key=lambda s: states[s]["carry_performance"]["multiplier"])
        worst_state = min(states.keys(), key=lambda s: states[s]["carry_performance"]["multiplier"])
        
        # Transition forecast
        next_probs_raw = current_probs @ self.model.transmat_
        transition_forecast = {f"state_{i}": float(p) for i, p in enumerate(next_probs_raw)}
        
        current_state = f"state_{current_state_idx}"
        current_multiplier = states[current_state]["carry_performance"]["multiplier"]
        current_persistence = states[current_state]["persistence"]
        
        return {
            "current_state": current_state,
            "current_probability": float(current_probs[current_state_idx]),
            "current_carry_multiplier": current_multiplier,
            "feature_families_used": self.feature_families,
            "features_used": feature_names,
            "states": states,
            "best_state_for_carry": best_state,
            "worst_state_for_carry": worst_state,
            "transition_forecast": transition_forecast,
            "regime_persistence": current_persistence,
            "n_observations_used": len(clean_obs),
            "recommendation": self._generate_recommendation(
                current_state, current_multiplier, current_persistence, 
                best_state, worst_state, states
            )
        }
    
    def _interpret_multiplier(self, multiplier: float) -> str:
        if multiplier > 1.3:
            return "Carry trades historically PROFITABLE in this state"
        elif multiplier > 1.0:
            return "Carry trades MODERATELY favorable in this state"
        elif multiplier > 0.7:
            return "Carry trades MIXED results in this state"
        else:
            return "Carry trades historically UNFAVORABLE in this state"
    
    def _generate_recommendation(
        self, current_state: str, multiplier: float, persistence: float,
        best_state: str, worst_state: str, states: Dict
    ) -> str:
        characteristics = states[current_state]["characteristics"]
        current_vol = 0
        for vol_name in ["vol_avg", "vol_max", "volatility"]:
            if vol_name in characteristics:
                current_vol = characteristics[vol_name].get("z_score", 0)
                break
        
        if current_state == best_state:
            rec = f"Currently in most favorable state for carry (multiplier={multiplier:.2f}). "
            if persistence > 0.8:
                rec += "State is stable - carry trades supported."
            else:
                rec += f"But state stability is moderate ({persistence:.0%}) - monitor for transitions."
        elif current_state == worst_state:
            rec = f"Currently in least favorable state for carry (multiplier={multiplier:.2f}). "
            rec += "Consider reducing carry exposure or hedging."
        else:
            rec = f"Currently in intermediate state (multiplier={multiplier:.2f}). "
            if current_vol > 0.5:
                rec += "Volatility elevated - be selective with carry trades."
            else:
                rec += "Conditions neutral - selective carry opportunities."
        
        return rec


# ============================================================================
# FRED Rate Fetching
# ============================================================================

async def _fetch_rates_from_fred(currencies: List[str]) -> Dict[str, float]:
    """Fetch current interbank rates from FRED for given currencies."""
    rates = {}
    
    try:
        fred_server = EconomicDataServer()
        await fred_server.connect()
        
        for currency in currencies:
            _check_cancellation(f"FRED rate fetch for {currency}")
            
            try:
                # Special case for USD: use Federal Funds Rate
                if currency.upper() == "USD":
                    logger.info(f"Fetching USD rate from Federal Funds Rate (DFF)")
                    data = await fred_server.get_series_data("DFF")
                    data_points = data.get('data', [])
                    if data_points:
                        latest = data_points[-1]
                        rate_value = latest.get('value')
                        if rate_value is not None:
                            rates[currency] = float(rate_value)
                            logger.info(f"FRED rate for {currency}: {rate_value}% (series: DFF - Federal Funds Rate)")
                    continue
                
                search_query = f"interbank rate {_currency_to_country(currency)}"
                search_results = await fred_server.search_series(search_query, limit=5)
                
                _check_cancellation(f"FRED search for {currency}")
                
                if not search_results:
                    logger.warning(f"No FRED rate found for {currency}")
                    continue
                
                series_id = search_results[0].get('series_id')
                if not series_id:
                    continue
                
                data = await fred_server.get_series_data(series_id)
                _check_cancellation(f"FRED data fetch for {currency}")
                
                data_points = data.get('data', [])
                
                if data_points:
                    latest = data_points[-1]
                    rate_value = latest.get('value')
                    if rate_value is not None:
                        rates[currency] = float(rate_value)
                        logger.info(f"FRED rate for {currency}: {rate_value}% (series: {series_id})")
                        
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Failed to fetch FRED rate for {currency}: {e}")
                continue
        
        await fred_server.cleanup()
        
    except asyncio.CancelledError:
        logger.info("[CANCEL] FRED rate fetching cancelled")
        raise
    except Exception as e:
        logger.error(f"FRED rate fetch failed: {e}")
    
    return rates


def _currency_to_country(currency: str) -> str:
    """Map currency code to country/region name for FRED search."""
    mapping = {
        "USD": "united states", "AUD": "australia", "JPY": "japan",
        "GBP": "united kingdom", "EUR": "euro area", "NZD": "new zealand",
        "CHF": "switzerland", "CAD": "canada", "SEK": "sweden", "NOK": "norway",
        "MXN": "mexico", "ZAR": "south africa", "KRW": "korea", "INR": "india",
        "BRL": "brazil", "CNY": "china", "SGD": "singapore", "HKD": "hong kong",
        "TRY": "turkey", "PLN": "poland",
    }
    return mapping.get(currency.upper(), currency.lower())


def _extract_currencies_from_pairs(pairs: List[str]) -> List[str]:
    """Extract unique currency codes from FX pairs."""
    currencies = set()
    for pair in pairs:
        pair = pair.upper().strip()
        if len(pair) >= 6:
            currencies.add(pair[:3])
            currencies.add(pair[3:6])
    return list(currencies)


async def _fetch_forex_historical(
    server: FMPAlternativesServer,
    pair: str,
    lookback_days: int = 90
) -> pd.DataFrame:
    """Fetch historical FX data from FMP Alternatives Server."""
    from_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    result = await server.call_tool("get_forex_historical", {
        "pair": pair, "timeframe": "1hour", "from": from_date, "to": to_date
    })

    if not result or not hasattr(result, 'content'):
        raise ValueError(f"No data returned for {pair}")

    data = safe_parse_json(result)
    if not data:
        raise ValueError(f"Invalid data structure for {pair}")

    historical_data = data.get('historical_data', data)

    if isinstance(historical_data, list) and len(historical_data) > 0:
        df = pd.DataFrame(historical_data)

        # Find date and price columns dynamically
        date_col = price_col = None
        for col in df.columns:
            col_lower = col.lower()
            if 'date' in col_lower or 'time' in col_lower:
                date_col = col
            if col_lower == 'close' or (price_col is None and col_lower in ['price', 'c']):
                price_col = col

        if not date_col or not price_col:
            raise ValueError(f"Could not find date/price columns for {pair}. Columns: {list(df.columns)}")

        df['date'] = pd.to_datetime(df[date_col])
        df['price'] = pd.to_numeric(df[price_col], errors='coerce')
        df = df[['date', 'price']].dropna()

        # Resample to daily
        df = df.set_index('date')
        df = df.resample('D').last().dropna().reset_index()
        return df

    elif isinstance(historical_data, dict) and data.get("error"):
        raise ValueError(f"API error for {pair}: {data.get('error')}")

    raise ValueError(f"Unexpected data format for {pair}")


async def _fetch_forex_quote(server: FMPAlternativesServer, pair: str) -> Dict[str, Any]:
    """Fetch current FX quote from FMP."""
    result = await server.call_tool("get_forex_quote", {"pair": pair})
    if not result or not hasattr(result, 'content'):
        return {"error": f"No quote for {pair}"}
    data = safe_parse_json(result)
    return data.get('quote', data) if data else {"error": "No data"}


def _calculate_volatility(prices: pd.Series, window: int = 30) -> float:
    """Calculate annualized volatility from price series."""
    returns = prices.pct_change().dropna()
    if len(returns) < window:
        return np.nan
    recent_returns = returns.tail(window)
    daily_vol = recent_returns.std()
    return float(daily_vol * np.sqrt(252) * 100)


def _calculate_momentum(prices: pd.Series, periods: List[int] = [5, 20, 60]) -> Dict[str, float]:
    """Calculate momentum metrics over multiple periods."""
    momentum = {}
    for period in periods:
        if len(prices) > period:
            pct_change = (prices.iloc[-1] / prices.iloc[-period - 1] - 1) * 100
            momentum[f"{period}d"] = float(pct_change)
        else:
            momentum[f"{period}d"] = np.nan
    return momentum


def _parse_pair_currencies(pair: str) -> tuple:
    """Parse a forex pair into base and quote currencies."""
    return pair[:3], pair[3:6] if len(pair) >= 6 else pair[3:]


def _calculate_carry(pair: str, rates: Dict[str, float]) -> Optional[float]:
    """Calculate carry (interest rate differential) for a pair."""
    base, quote = _parse_pair_currencies(pair)
    base_rate = rates.get(base) or rates.get(base.upper())
    quote_rate = rates.get(quote) or rates.get(quote.upper())
    if base_rate is None or quote_rate is None:
        return None
    return float(base_rate - quote_rate)


def _classify_vol_regime(
    current_vol: float, vol_history: pd.Series,
    high_z_threshold: float = 1.5, low_z_threshold: float = -1.0
) -> Dict[str, Any]:
    """Classify FX volatility regime using z-scores."""
    vol_mean = vol_history.mean()
    vol_std = vol_history.std()
    vol_z = (current_vol - vol_mean) / vol_std if vol_std > 1e-8 else 0
    vol_percentile = (vol_history < current_vol).mean() * 100

    if vol_z < low_z_threshold:
        regime, carry_favorable = "LOW_VOL", True
        description = f"FX volatility z-score ({vol_z:.2f}) below {low_z_threshold}σ - unusually calm"
        signal = "Carry trades favorable - low volatility environment"
    elif vol_z > high_z_threshold:
        regime, carry_favorable = "HIGH_VOL", False
        description = f"FX volatility z-score ({vol_z:.2f}) above +{high_z_threshold}σ - elevated risk"
        signal = "Carry trades risky - high volatility may overwhelm carry"
    else:
        regime, carry_favorable = "NEUTRAL", None
        description = f"FX volatility z-score ({vol_z:.2f}) within normal range"
        signal = "Normal volatility - selective carry opportunities"

    return {
        "regime": regime, "description": description, "signal": signal,
        "carry_favorable": carry_favorable, "volatility_z_score": float(vol_z),
        "volatility_percentile": float(vol_percentile),
        "historical_context": {"vol_mean": float(vol_mean), "vol_std": float(vol_std), "current_vol": float(current_vol)}
    }


def _build_screener_chart(pair_data: List[Dict[str, Any]], has_carry: bool, chart_id: str = "fx_carry_screener") -> Dict[str, Any]:
    """Build clean, readable visualization for FX screener results."""
    pairs = [p['pair'] for p in pair_data]

    fig = go.Figure()

    if has_carry:
        # Horizontal bar chart showing risk-adjusted carry
        sharpes = [p.get('risk_adjusted_carry', 0) for p in pair_data]
        carries = [p.get('carry_pct', 0) for p in pair_data]
        vols = [p.get('volatility_pct', 0) for p in pair_data]

        # Color: green for positive, red for negative
        colors = ['#3fb950' if s > 0 else '#f85149' for s in sharpes]

        fig.add_trace(
            go.Bar(
                y=pairs,  # Pairs on y-axis
                x=sharpes,  # Risk-adj carry on x-axis
                orientation='h',  # Horizontal
                marker=dict(color=colors, line=dict(width=0)),
                hovertemplate=(
                    '<b>%{y}</b><br>'
                    'Risk-Adj Carry: %{x:.3f}<br>'
                    'Carry: %{customdata[0]:.2f}%<br>'
                    'Volatility: %{customdata[1]:.1f}%'
                    '<extra></extra>'
                ),
                customdata=[[c, v] for c, v in zip(carries, vols)]
            )
        )

        fig.update_layout(
            title='FX Carry Trade Ranking (Risk-Adjusted)',
            xaxis_title='Risk-Adjusted Carry (Higher is Better)',
            yaxis_title='',
            height=max(400, len(pairs) * 40),  # Dynamic height
        )

        # Add vertical line at zero
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

    else:
        # Volatility-only view - horizontal bars
        vols = [p.get('volatility_pct', 0) for p in pair_data]

        fig.add_trace(
            go.Bar(
                y=pairs,
                x=vols,
                orientation='h',
                marker=dict(color='#60a5fa', line=dict(width=0)),
                hovertemplate='<b>%{y}</b><br>Volatility: %{x:.1f}%<extra></extra>'
            )
        )

        fig.update_layout(
            title='FX Pair Volatility (Lower is Calmer)',
            xaxis_title='Annualized Volatility (%)',
            yaxis_title='',
            height=max(400, len(pairs) * 40),
        )

    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        margin=dict(t=80, b=60, l=120, r=60),
        font=dict(size=13),
        yaxis=dict(autorange="reversed")  # Best pairs at top
    )

    return {'id': chart_id, 'title': 'FX Carry Screener', 'plotly': fig.to_dict()}


async def screen_forex_carry_trades_internal(
    pairs_csv: str,
    rates_json: str = "",
    lookback_days: int = 180,
    vol_window: int = 30,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.0,
    use_regime_detection: bool = False,
    regime_n_states: int = 3,
    regime_features: str = "volatility,vol_dynamics,momentum,correlation",
    generate_chart: bool = True
) -> dict:
    """
    Screen FX pairs by carry and volatility metrics.

    **What This Tool Does:**
    - Fetches historical FX data for provided pairs
    - Calculates volatility for each pair
    - AUTO-FETCHES interest rates from FRED if not provided
    - Calculates carry and risk-adjusted carry (Sharpe)
    - Classifies overall FX volatility regime
    - Ranks pairs by risk-adjusted carry or volatility

    **Regime Detection (two modes):**
    
    1. Z-Score Based (default, use_regime_detection=False):
       - LOW_VOL: FX vol below average → Carry trades favorable
       - HIGH_VOL: FX vol elevated → Carry trades risky
       - NEUTRAL: Normal conditions
    
    2. HMM Based (use_regime_detection=True):
       - Fits Hidden Markov Model on FX price data
       - Features are CONFIGURABLE via regime_features parameter
       - States are NOT hardcoded - described by their characteristics
       - Carry multipliers calculated FROM DATA
       - Returns state probabilities, transitions, and recommendations

    **Available Feature Families for HMM (regime_features):**
    - volatility: vol_avg, vol_max, vol_min, vol_range (RECOMMENDED)
    - vol_dynamics: vol_trend, vol_acceleration, vol_dispersion (RECOMMENDED)
    - momentum: ret_avg, ret_sum, ret_std (RECOMMENDED)
    - correlation: cross_corr_avg, cross_corr_std (RECOMMENDED)
    - higher_moments: skew, kurtosis (OPTIONAL)
    - autocorrelation: autocorr_1, autocorr_5 (OPTIONAL)
    - range: range_avg, range_vs_vol (OPTIONAL)

    Args:
        pairs_csv: Comma-separated FX pairs (e.g., "AUDJPY,NZDJPY,USDJPY,EURUSD")
        rates_json: JSON string of currency interest rates (empty for auto-fetch from FRED)
        lookback_days: Historical period for analysis (default: 180)
        vol_window: Rolling window for volatility (default: 30)
        high_z_threshold: Z-score for HIGH_VOL regime (default: 1.5)
        low_z_threshold: Z-score for LOW_VOL regime (default: -1.0)
        use_regime_detection: Use HMM-based regime detection (default: False)
        regime_n_states: Number of HMM states (default: 3)
        regime_features: Comma-separated feature families for HMM (default: focused set of 4)
        generate_chart: Generate visualization (default: True)

    Returns:
        Dict with rankings, regime analysis, and optional HMM details
    """
    # Parse pairs
    pairs = [p.strip().upper() for p in pairs_csv.split(",") if p.strip()]
    if not pairs:
        return {"error": "No pairs provided. Pass pairs_csv like 'AUDJPY,EURUSD,USDJPY'"}

    # Parse rates
    rates: Optional[Dict[str, float]] = None
    rates_source = "none"
    
    if rates_json and rates_json.strip():
        try:
            rates = json.loads(rates_json)
            if not isinstance(rates, dict):
                return {"error": "rates_json must be a JSON object mapping currency codes to rates"}
            rates_source = "user_provided"
            logger.info(f"Using user-provided rates for {len(rates)} currencies")
        except json.JSONDecodeError as e:
            return {"error": f"Invalid rates_json format: {e}"}
    else:
        logger.info("No rates provided - fetching from FRED...")
        currencies_needed = _extract_currencies_from_pairs(pairs)
        try:
            rates = await _fetch_rates_from_fred(currencies_needed)
            if rates:
                rates_source = "fred_auto"
                logger.info(f"Auto-fetched rates from FRED for {len(rates)} currencies: {rates}")
            else:
                logger.warning("FRED rate fetch returned empty - falling back to volatility-only mode")
        except Exception as e:
            logger.warning(f"FRED rate fetch failed: {e} - falling back to volatility-only mode")

    server = FMPAlternativesServer()

    try:
        logger.info(f"Screening {len(pairs)} FX pairs")
        await server.connect()

        pair_results = []
        failed_pairs = []
        all_vols = []
        prices_cache = {}  # Cache for HMM reuse

        for pair in pairs:
            _check_cancellation(f"processing pair {pair}")
            
            try:
                df = await _fetch_forex_historical(server, pair, lookback_days)
                _check_cancellation(f"after fetching {pair} data")
                
                # Cache for HMM (avoid double-fetch)
                if len(df) >= vol_window * 2:
                    prices_cache[pair] = df

                if len(df) < vol_window + 10:
                    failed_pairs.append({"pair": pair, "error": f"Insufficient data: {len(df)} days"})
                    continue

                volatility = _calculate_volatility(df['price'], vol_window)
                if not np.isnan(volatility):
                    all_vols.append(volatility)

                momentum = _calculate_momentum(df['price'])
                
                quote_data = await _fetch_forex_quote(server, pair)
                _check_cancellation(f"after fetching {pair} quote")
                
                current_rate = None
                if isinstance(quote_data, list) and len(quote_data) > 0:
                    current_rate = quote_data[0].get('price') or quote_data[0].get('close')
                elif isinstance(quote_data, dict):
                    current_rate = quote_data.get('price') or quote_data.get('close')

                result = {
                    "pair": pair,
                    "current_rate": float(current_rate) if current_rate else None,
                    "volatility_pct": float(volatility) if not np.isnan(volatility) else None,
                    "momentum": momentum,
                    "data_days": len(df)
                }

                if rates:
                    carry = _calculate_carry(pair, rates)
                    if carry is not None:
                        result["carry_pct"] = carry
                        if volatility and volatility > 0:
                            result["risk_adjusted_carry"] = carry / volatility
                        else:
                            result["risk_adjusted_carry"] = None
                        base, quote = _parse_pair_currencies(pair)
                        result["direction"] = f"LONG {base} / SHORT {quote}"

                pair_results.append(result)
                logger.info(f"Processed {pair}: vol={volatility:.1f}%")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Failed to process {pair}: {e}")
                failed_pairs.append({"pair": pair, "error": str(e)})

        if not pair_results:
            return {"error": "No pairs could be processed", "failed_pairs": failed_pairs}

        # Sort results
        has_carry = rates is not None and any(p.get('carry_pct') is not None for p in pair_results)

        if has_carry:
            mode = "carry_analysis"
            pair_results.sort(key=lambda x: x.get('risk_adjusted_carry') or -999, reverse=True)
        else:
            mode = "volatility_analysis"
            pair_results.sort(key=lambda x: x.get('volatility_pct') or 999)

        # Regime classification
        hmm_regime = None
        
        if use_regime_detection and len(prices_cache) >= 2:
            logger.info("[FX Carry] Using HMM regime detection")
            
            # Parse feature families from comma-separated string
            feature_families_list = [f.strip() for f in regime_features.split(",") if f.strip()]
            logger.info(f"[FX Carry] HMM using feature families: {feature_families_list}")
            
            detector = CarryRegimeDetector(
                n_states=regime_n_states, 
                feature_families=feature_families_list
            )
            hmm_regime = detector.fit_predict(prices_cache, window=vol_window)
            
            if hmm_regime:
                current_state = hmm_regime["current_state"]
                current_mult = hmm_regime["current_carry_multiplier"]
                regime = {
                    "regime": current_state,
                    "detection_method": "hmm",
                    "description": hmm_regime["recommendation"],
                    "carry_multiplier": current_mult,
                    "carry_favorable": current_mult > 1.0,
                    "current_probability": hmm_regime["current_probability"],
                    "regime_persistence": hmm_regime["regime_persistence"]
                }
                logger.info(f"[FX Carry] HMM regime: {current_state} (P={hmm_regime['current_probability']:.2f}, mult={current_mult:.2f})")
            else:
                logger.warning("[FX Carry] HMM fitting failed, falling back to z-score")
                use_regime_detection = False
        
        if not use_regime_detection or hmm_regime is None:
            if all_vols:
                avg_vol = np.mean(all_vols)
                vol_series = pd.Series(all_vols)
                regime = _classify_vol_regime(avg_vol, vol_series, high_z_threshold=high_z_threshold, low_z_threshold=low_z_threshold)
                regime["detection_method"] = "z_score"
            else:
                regime = {"regime": "UNKNOWN", "description": "Insufficient data for regime classification", "detection_method": "none"}

        # Build response
        response = {
            "mode": mode,
            "pairs_analyzed": len(pair_results),
            "rankings": pair_results,
            "regime": regime,
            "parameters": {
                "lookback_days": lookback_days,
                "vol_window": vol_window,
                "rates_provided": rates is not None,
                "rates_source": rates_source,
                "rates_fetched": rates if rates else {},
                "regime_detection_method": regime.get("detection_method", "z_score")
            }
        }

        if hmm_regime:
            response["hmm_regime"] = hmm_regime

        if rates:
            response["rates_used"] = rates

        if failed_pairs:
            response["failed_pairs"] = failed_pairs

        if pair_results:
            best = pair_results[0]
            if has_carry and best.get('risk_adjusted_carry'):
                response["best_trade"] = {
                    "pair": best["pair"],
                    "direction": best.get("direction", f"LONG {best['pair'][:3]}"),
                    "carry_pct": best.get("carry_pct"),
                    "risk_adjusted_carry": best.get("risk_adjusted_carry"),
                    "rationale": "Highest risk-adjusted carry"
                }
            else:
                response["best_trade"] = {
                    "pair": best["pair"],
                    "volatility_pct": best.get("volatility_pct"),
                    "rationale": "Lowest volatility"
                }

        if generate_chart and pair_results:
            chart = _build_screener_chart(pair_results, has_carry)
            response["charts"] = wrap_plotly_charts([chart], "fx_screener")

        logger.info(f"FX screening complete: {mode}, {len(pair_results)} pairs")
        return response

    except asyncio.CancelledError:
        logger.info("[CANCEL] FX carry screening cancelled by user")
        raise
    except Exception as e:
        logger.error(f"FX carry screening failed: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}

    finally:
        await server.cleanup()


@function_tool
async def screen_forex_carry_trades(
    pairs_csv: str,
    rates_json: str = "",
    lookback_days: int = 180,
    vol_window: int = 30,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.0,
    use_regime_detection: bool = False,
    regime_n_states: int = 3,
    regime_features: str = "volatility,vol_dynamics,momentum,correlation",
    generate_chart: bool = True
) -> dict:
    """
    Screen FX pairs by carry and volatility metrics.

    **What This Tool Does:**
    - Fetches historical FX data for provided pairs
    - Calculates volatility for each pair
    - AUTO-FETCHES interest rates from FRED if not provided
    - Calculates carry and risk-adjusted carry (Sharpe)
    - Classifies overall FX volatility regime
    - Ranks pairs by risk-adjusted carry or volatility

    Args:
        pairs_csv: Comma-separated FX pairs (e.g., "AUDJPY,NZDJPY,USDJPY,EURUSD")
        rates_json: JSON string of currency interest rates (empty for auto-fetch from FRED)
        lookback_days: Historical period for analysis (default: 180)
        vol_window: Rolling window for volatility (default: 30)
        high_z_threshold: Z-score for HIGH_VOL regime (default: 1.5)
        low_z_threshold: Z-score for LOW_VOL regime (default: -1.0)
        use_regime_detection: Use HMM-based regime detection (default: False)
        regime_n_states: Number of HMM states (default: 3)
        regime_features: Comma-separated feature families for HMM (default: focused set of 4)
        generate_chart: Generate visualization (default: True)

    Returns:
        JSON string with rankings, regime analysis, and optional HMM details
    """
    from core.utils.risk_adapter import jsonify_results
    result = await screen_forex_carry_trades_internal(
        pairs_csv=pairs_csv,
        rates_json=rates_json,
        lookback_days=lookback_days,
        vol_window=vol_window,
        high_z_threshold=high_z_threshold,
        low_z_threshold=low_z_threshold,
        use_regime_detection=use_regime_detection,
        regime_n_states=regime_n_states,
        regime_features=regime_features,
        generate_chart=generate_chart
    )
    return jsonify_results(result)
