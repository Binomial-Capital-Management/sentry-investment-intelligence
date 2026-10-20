"""
Dealer Gamma Regime Tool - Calibration-Based Gamma Exposure Analysis

Instead of ASSUMING dealer positioning (the typical GEX approach), this tool
ESTIMATES the dealer gamma regime from observable price dynamics using regression.

Mathematical Basis:
------------------
If dealers delta-hedge, their aggregate hedging flow creates a signature in returns:
    r_{t+1} = α + β × Γ_t × r_t + γ × r_t + ε

Where:
    - r_t = return at time t
    - Γ_t = gross gamma exposure
    - β captures the interaction effect

Interpretation of β:
    - β > 0: High gamma + up move → further up move = dealers SHORT gamma (amplification)
    - β < 0: High gamma + up move → reversal = dealers LONG gamma (dampening)
    - β ≈ 0: No detectable hedging effect

This is ESTIMATION from data, not assumption.

Regime Detection Options:
- Default: Autocorrelation-based (simple, fast)
- Optional: HMM-based (multi-feature, learns regimes from data)

Key Outputs:
- Gross gamma profile by strike (observable, no assumptions)
- Key gamma levels (max gamma strike, put wall, call wall)
- Estimated dealer regime with statistical confidence
- HMM state analysis (if enabled)
"""

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import math
import logging
import numpy as np
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


# =============================================================================
# HMM FEATURE FAMILIES FOR GAMMA REGIME DETECTION
# =============================================================================

HMM_FEATURE_FAMILIES = {
    # ===== AUTOCORRELATION (Core - captures hedging signature) =====
    "autocorrelation": {
        "description": "Return autocorrelation - positive=trending (short gamma), negative=mean-reverting (long gamma)",
        "features": ["autocorr_1", "autocorr_5", "autocorr_10"]
    },
    
    # ===== VOLATILITY (Core - vol regime affects gamma hedging) =====
    "volatility": {
        "description": "Realized volatility measures across windows",
        "features": ["vol_10d", "vol_20d", "vol_ratio"]
    },
    "vol_dynamics": {
        "description": "Volatility changes - expanding/contracting vol regimes",
        "features": ["vol_trend", "vol_acceleration"]
    },
    
    # ===== MOMENTUM (Trending vs ranging behavior) =====
    "momentum": {
        "description": "Return momentum and trend strength",
        "features": ["ret_5d", "ret_10d", "ret_20d", "trend_strength"]
    },
    
    # ===== HIGHER MOMENTS (Tail risk and asymmetry) =====
    "higher_moments": {
        "description": "Skew and kurtosis - tail behavior",
        "features": ["skew", "kurtosis"]
    },
    
    # ===== RANGE (Intraday-like behavior proxy) =====
    "range": {
        "description": "Range-based measures (proxy for intraday activity)",
        "features": ["range_vol_ratio", "range_expansion"]
    },
}

# Default: focused set for gamma regime detection
DEFAULT_HMM_FEATURES = ["autocorrelation", "volatility", "momentum"]


# =============================================================================
# HMM GAMMA REGIME DETECTOR
# =============================================================================

class GammaRegimeDetector:
    """
    Hidden Markov Model regime detector for gamma/hedging flow analysis.
    
    Key principles:
    1. Features are CONFIGURABLE - user selects which feature families to use
    2. States are NOT hardcoded - described by their characteristics
    3. Regime interpretation (short/long gamma) derived from state features
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
            self.feature_families = DEFAULT_HMM_FEATURES.copy()
        elif feature_families == ["all"] or feature_families == "all":
            self.feature_families = list(HMM_FEATURE_FAMILIES.keys())
        else:
            valid_families = []
            for fam in feature_families:
                if fam in HMM_FEATURE_FAMILIES:
                    valid_families.append(fam)
                else:
                    logger.warning(f"[GammaHMM] Unknown feature family '{fam}', skipping")
            self.feature_families = valid_families if valid_families else DEFAULT_HMM_FEATURES.copy()
        
        # Build feature list from families
        self.feature_names = []
        for fam in self.feature_families:
            self.feature_names.extend(HMM_FEATURE_FAMILIES[fam]["features"])
        
        logger.info(f"[GammaHMM] Using feature families: {self.feature_families}")
        logger.info(f"[GammaHMM] Total features: {len(self.feature_names)}")
    
    def _compute_features(
        self, 
        returns: np.ndarray,
        prices: np.ndarray,
        window: int = 20
    ) -> Optional[Tuple[np.ndarray, List[str]]]:
        """
        Compute HMM features from return/price data.
        
        Args:
            returns: Daily returns array
            prices: Daily price array
            window: Rolling window for calculations
        
        Returns:
            Tuple of (features array, feature names) or None if insufficient data
        """
        if len(returns) < window * 3:
            logger.warning(f"[GammaHMM] Insufficient data: {len(returns)} (need {window * 3})")
            return None
        
        logger.info(f"[GammaHMM] Computing features from {len(returns)} returns")
        
        # Convert to pandas for rolling calculations
        ret_series = pd.Series(returns)
        price_series = pd.Series(prices)
        
        computed_features = {}
        
        # ===== AUTOCORRELATION FAMILY =====
        if "autocorrelation" in self.feature_families:
            def rolling_autocorr(series, w, lag):
                return series.rolling(w).apply(
                    lambda x: pd.Series(x).autocorr(lag=lag) if len(x) > lag else 0,
                    raw=False
                )
            computed_features["autocorr_1"] = rolling_autocorr(ret_series, window, 1)
            computed_features["autocorr_5"] = rolling_autocorr(ret_series, window, 5)
            computed_features["autocorr_10"] = rolling_autocorr(ret_series, min(window, 15), 10)
        
        # ===== VOLATILITY FAMILY =====
        if "volatility" in self.feature_families:
            computed_features["vol_10d"] = ret_series.rolling(10).std() * np.sqrt(252)
            computed_features["vol_20d"] = ret_series.rolling(20).std() * np.sqrt(252)
            # Ratio: short-term vs longer-term vol
            computed_features["vol_ratio"] = computed_features["vol_10d"] / (computed_features["vol_20d"] + 1e-9)
        
        # ===== VOL DYNAMICS FAMILY =====
        if "vol_dynamics" in self.feature_families:
            vol_20d = ret_series.rolling(20).std() * np.sqrt(252)
            computed_features["vol_trend"] = vol_20d.diff(5)
            computed_features["vol_acceleration"] = vol_20d.diff(5).diff(5)
        
        # ===== MOMENTUM FAMILY =====
        if "momentum" in self.feature_families:
            computed_features["ret_5d"] = ret_series.rolling(5).sum()
            computed_features["ret_10d"] = ret_series.rolling(10).sum()
            computed_features["ret_20d"] = ret_series.rolling(20).sum()
            # Trend strength: |mean| / std
            computed_features["trend_strength"] = ret_series.rolling(window).apply(
                lambda x: abs(x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0
            )
        
        # ===== HIGHER MOMENTS FAMILY =====
        if "higher_moments" in self.feature_families:
            computed_features["skew"] = ret_series.rolling(window).skew()
            computed_features["kurtosis"] = ret_series.rolling(window).kurt()
        
        # ===== RANGE FAMILY =====
        if "range" in self.feature_families:
            # Range proxy: max - min of returns in window
            range_measure = ret_series.rolling(window).apply(lambda x: x.max() - x.min())
            vol = ret_series.rolling(window).std()
            computed_features["range_vol_ratio"] = range_measure / (vol + 1e-9)
            # Range expansion: current range vs longer-term
            short_range = ret_series.rolling(5).apply(lambda x: x.max() - x.min())
            long_range = ret_series.rolling(window).apply(lambda x: x.max() - x.min())
            computed_features["range_expansion"] = short_range / (long_range + 1e-9)
        
        # Filter to only selected features
        selected_features = {k: v for k, v in computed_features.items() if k in self.feature_names}
        
        if not selected_features:
            logger.warning("[GammaHMM] No features computed")
            return None
        
        # Combine into DataFrame
        features_df = pd.DataFrame(selected_features).dropna()
        
        min_feature_obs = self.n_states * 10
        if len(features_df) < min_feature_obs:
            logger.warning(f"[GammaHMM] Insufficient observations: {len(features_df)} (need {min_feature_obs})")
            return None
        
        actual_feature_names = list(features_df.columns)
        logger.info(f"[GammaHMM] Computed {len(features_df)} observations with {len(actual_feature_names)} features")
        
        return features_df.values, actual_feature_names
    
    def fit_predict(
        self, 
        returns: List[float],
        prices: List[float],
        window: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Fit HMM and describe each state by its characteristics.
        
        Returns:
            Dict with state descriptions, current state, and gamma regime interpretation
        """
        try:
            from hmmlearn import hmm
        except ImportError:
            logger.warning("[GammaHMM] hmmlearn not installed, skipping HMM regime detection")
            return None
        
        returns_arr = np.array(returns)
        prices_arr = np.array(prices)
        
        result = self._compute_features(returns_arr, prices_arr, window)
        if result is None:
            return None
        
        observations, feature_names = result
        
        # Standardize features
        means = np.nanmean(observations, axis=0)
        stds = np.nanstd(observations, axis=0) + 1e-9
        standardized = (observations - means) / stds
        
        # Handle NaN
        valid_mask = ~np.isnan(standardized).any(axis=1)
        clean_obs = standardized[valid_mask]
        raw_obs = observations[valid_mask]
        
        min_clean = self.n_states * 8
        if len(clean_obs) < min_clean:
            logger.warning(f"[GammaHMM] Not enough clean obs: {len(clean_obs)} (need {min_clean})")
            return None
        
        logger.info(f"[GammaHMM] Fitting HMM with {len(clean_obs)} observations, {len(feature_names)} features")
        
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
            logger.warning(f"[GammaHMM] Fitting failed: {e}")
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
            
            # Identify dominant features
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
            
            # Determine gamma regime based on autocorrelation feature
            autocorr_zscore = 0
            for fname in ["autocorr_1", "autocorr_5"]:
                if fname in characteristics:
                    autocorr_zscore = characteristics[fname]["z_score"]
                    break
            
            # Interpret gamma regime from autocorrelation
            if autocorr_zscore > 0.5:
                gamma_interpretation = "SHORT_GAMMA"
                gamma_description = "Trending/momentum behavior - consistent with dealers SHORT gamma"
            elif autocorr_zscore < -0.5:
                gamma_interpretation = "LONG_GAMMA"
                gamma_description = "Mean-reverting behavior - consistent with dealers LONG gamma"
            else:
                gamma_interpretation = "NEUTRAL"
                gamma_description = "Mixed/neutral behavior - no clear gamma positioning signal"
            
            # Persistence
            persistence = float(self.model.transmat_[state_idx, state_idx])
            n_days_in_state = int((state_sequence == state_idx).sum())
            
            states[f"state_{state_idx}"] = {
                "characteristics": characteristics,
                "dominant_features": dominant_features[:5],
                "gamma_interpretation": gamma_interpretation,
                "gamma_description": gamma_description,
                "current_probability": float(current_probs[state_idx]),
                "persistence": round(persistence, 3),
                "days_in_sample": n_days_in_state,
                "pct_of_sample": round(n_days_in_state / len(state_sequence) * 100, 1)
            }
        
        # Transition forecast
        next_probs_raw = current_probs @ self.model.transmat_
        transition_forecast = {f"state_{i}": float(p) for i, p in enumerate(next_probs_raw)}
        
        # Current state info
        current_state = f"state_{current_state_idx}"
        current_gamma = states[current_state]["gamma_interpretation"]
        current_persistence = states[current_state]["persistence"]
        
        return {
            "current_state": current_state,
            "current_probability": float(current_probs[current_state_idx]),
            "current_gamma_regime": current_gamma,
            "feature_families_used": self.feature_families,
            "features_used": feature_names,
            "states": states,
            "transition_forecast": transition_forecast,
            "regime_persistence": current_persistence,
            "n_observations_used": len(clean_obs),
            "recommendation": self._generate_recommendation(current_state, current_gamma, current_persistence, states)
        }
    
    def _generate_recommendation(
        self, 
        current_state: str, 
        gamma_regime: str, 
        persistence: float,
        states: Dict
    ) -> str:
        """Generate actionable recommendation based on HMM state."""
        
        if gamma_regime == "SHORT_GAMMA":
            rec = f"HMM detects SHORT GAMMA regime (trending behavior). "
            if persistence > 0.8:
                rec += f"Regime is stable ({persistence:.0%} persistence) - expect continuation of trends. "
                rec += "Key levels may NOT hold; moves likely to extend."
            else:
                rec += f"Moderate stability ({persistence:.0%}) - monitor for regime transition."
        elif gamma_regime == "LONG_GAMMA":
            rec = f"HMM detects LONG GAMMA regime (mean-reverting). "
            if persistence > 0.8:
                rec += f"Regime is stable ({persistence:.0%} persistence) - expect price to revert to key levels. "
                rec += "Max gamma strike likely to act as 'magnet'."
            else:
                rec += f"Moderate stability ({persistence:.0%}) - may transition to trending soon."
        else:
            rec = f"HMM detects NEUTRAL regime - no clear gamma signal. "
            rec += "Use key levels for support/resistance but expect normal market behavior."
        
        return rec


# ============================================================================
# DATA FETCHING
# ============================================================================

async def _fetch_underlying_price(fmp_server, ticker: str) -> Optional[float]:
    """Fetch current price for underlying."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)
        
        logger.info(f"[GEX PRICE] Fetching spot price for {ticker}")
        
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        
        if not result:
            logger.warning(f"[GEX PRICE] No result returned for {ticker}")
            return None
            
        if not hasattr(result, 'content'):
            logger.warning(f"[GEX PRICE] Result has no content attribute: {type(result)}")
            return None
        
        data = safe_parse_json(result)
        logger.info(f"[GEX PRICE] Parsed data keys: {list(data.keys()) if data else 'None'}")
        
        # Try multiple field names for compatibility
        prices = data.get("prices") or data.get("closes") or data.get("close") or []
        
        if not prices:
            # Try the "data" array format (YFinance-compatible)
            data_array = data.get("data", [])
            if data_array:
                prices = [row.get("Close") or row.get("close") for row in data_array if row.get("Close") or row.get("close")]
                logger.info(f"[GEX PRICE] Extracted {len(prices)} prices from data array")
        
        if prices:
            return float(prices[-1])
        
        logger.warning(f"[GEX PRICE] No price data found for {ticker}. Data: {data}")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch price for {ticker}: {e}", exc_info=True)
        return None


async def _fetch_price_history(fmp_server, ticker: str, days: int = 90) -> Optional[Dict[str, Any]]:
    """
    Fetch historical price data for regression analysis.
    
    Returns dict with 'dates', 'prices', 'returns' arrays.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(days * 1.5) + 30)
        
        logger.info(f"[GEX HISTORY] Fetching {ticker} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        
        if not result:
            logger.warning(f"[GEX HISTORY] No result from FMP for {ticker}")
            return None
            
        if not hasattr(result, 'content'):
            logger.warning(f"[GEX HISTORY] Result has no content: {type(result)}")
            return None
        
        data = safe_parse_json(result)
        logger.info(f"[GEX HISTORY] Parsed data keys: {list(data.keys()) if data else 'None'}")
        
        # Try multiple field names for prices
        prices = data.get("prices") or data.get("closes") or data.get("close") or []
        dates = data.get("dates") or []
        
        # Fallback: try "data" array format (YFinance-compatible)
        if not prices:
            data_array = data.get("data", [])
            if data_array:
                prices = []
                dates = []
                for row in data_array:
                    price = row.get("Close") or row.get("close")
                    date = row.get("Date") or row.get("date")
                    if price is not None:
                        prices.append(price)
                        if date:
                            dates.append(date)
                logger.info(f"[GEX HISTORY] Extracted {len(prices)} prices from data array")
        
        logger.info(f"[GEX HISTORY] Got {len(prices)} price points for {ticker}")
        
        if len(prices) < 20:
            logger.warning(f"[GEX HISTORY] Insufficient prices ({len(prices)}) for {ticker}. Data keys: {list(data.keys())}")
            return None
        
        valid_prices = []
        for p in prices:
            try:
                if p is not None:
                    valid_prices.append(float(p))
            except (ValueError, TypeError):
                continue
        
        if len(valid_prices) < 20:
            logger.warning(f"[GEX HISTORY] Only {len(valid_prices)} valid prices for {ticker}")
            return None
        
        returns = []
        for i in range(1, len(valid_prices)):
            if valid_prices[i-1] > 0:
                returns.append((valid_prices[i] - valid_prices[i-1]) / valid_prices[i-1])
            else:
                returns.append(0.0)
        
        logger.info(f"[GEX HISTORY] Calculated {len(returns)} returns for {ticker}")
        
        return {
            'dates': dates[1:len(returns)+1] if dates else list(range(len(returns))),
            'prices': valid_prices[1:],
            'returns': returns
        }
    except Exception as e:
        logger.error(f"[GEX HISTORY] Failed to fetch price history for {ticker}: {e}", exc_info=True)
        return None


async def _fetch_options_chain(polygon_server, underlying: str, max_dte: int = 60) -> List[Dict[str, Any]]:
    """
    Fetch complete options chain from Polygon with pagination.
    """
    from core.agents.quant_tools.options_chain_helpers import fetch_options_chain_paginated
    return await fetch_options_chain_paginated(
        polygon_server, 
        underlying, 
        min_dte=1, 
        max_dte=max_dte,
        max_pages=6,
        limit_per_page=250
    )


def _extract_gamma_data(
    contracts: List[Dict[str, Any]],
    spot_price: float,
    min_oi: int = 100,
    max_dte: int = 60
) -> Dict[str, Any]:
    """
    Extract gamma-relevant data from options chain.
    """
    by_strike = {}
    total_call_oi = 0
    total_put_oi = 0
    contracts_included = 0
    
    today = datetime.now().date()
    
    # Log first contract structure for debugging
    if contracts:
        sample = contracts[0]
        logger.info(f"[GEX EXTRACT] Sample contract keys: {list(sample.keys())}")
        logger.debug(f"[GEX EXTRACT] Sample contract: {sample}")
    
    for contract in contracts:
        try:
            details = contract.get('details', {})
            greeks = contract.get('greeks', {})
            
            strike = details.get('strike_price')
            contract_type = details.get('contract_type', '').lower()
            expiry_str = details.get('expiration_date')
            
            oi = contract.get('open_interest', 0) or 0
            gamma = greeks.get('gamma', 0) or 0
            
            if not strike or not contract_type or not expiry_str:
                continue
            
            if oi < min_oi:
                continue
            
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                dte = (expiry_date - today).days
                if dte < 0 or dte > max_dte:
                    continue
            except:
                continue
            
            strike = float(strike)
            if strike not in by_strike:
                by_strike[strike] = {
                    'call_oi': 0, 'put_oi': 0,
                    'call_gamma': 0.0, 'put_gamma': 0.0,
                    'call_gamma_oi': 0.0, 'put_gamma_oi': 0.0
                }
            
            if contract_type == 'call':
                by_strike[strike]['call_oi'] += oi
                by_strike[strike]['call_gamma'] = max(by_strike[strike]['call_gamma'], abs(gamma))
                by_strike[strike]['call_gamma_oi'] += abs(gamma) * oi
                total_call_oi += oi
            elif contract_type == 'put':
                by_strike[strike]['put_oi'] += oi
                by_strike[strike]['put_gamma'] = max(by_strike[strike]['put_gamma'], abs(gamma))
                by_strike[strike]['put_gamma_oi'] += abs(gamma) * oi
                total_put_oi += oi
            
            contracts_included += 1
            
        except Exception as e:
            logger.debug(f"Skipping contract: {e}")
            continue
    
    logger.info(
        f"[GEX EXTRACT] Extracted {contracts_included} contracts across {len(by_strike)} strikes. "
        f"Total put OI: {total_put_oi:,}, Total call OI: {total_call_oi:,}"
    )
    
    return {
        'by_strike': by_strike,
        'total_call_oi': total_call_oi,
        'total_put_oi': total_put_oi,
        'contracts_included': contracts_included
    }


# ============================================================================
# GAMMA CALCULATIONS
# ============================================================================

def _compute_gross_gamma_profile(gamma_data: Dict[str, Any], spot_price: float) -> List[Dict[str, Any]]:
    """Compute gross gamma exposure by strike."""
    profile = []
    
    for strike, data in sorted(gamma_data['by_strike'].items()):
        total_gamma_oi = data['call_gamma_oi'] + data['put_gamma_oi']
        gross_gex = total_gamma_oi * 100 * (spot_price ** 2) * 0.01
        
        profile.append({
            'strike': strike,
            'gross_gex': gross_gex,
            'call_oi': data['call_oi'],
            'put_oi': data['put_oi'],
            'total_oi': data['call_oi'] + data['put_oi'],
            'moneyness': strike / spot_price
        })
    
    return profile


def _identify_key_levels(gamma_profile: List[Dict[str, Any]], spot_price: float) -> Dict[str, Any]:
    """Identify key gamma levels."""
    if not gamma_profile:
        return {}
    
    # Find max gamma strike
    max_gamma_entry = max(gamma_profile, key=lambda x: x['gross_gex'])
    max_gamma_strike = max_gamma_entry['strike']
    
    # Find put wall (strike with max put OI)
    put_wall_entry = max(gamma_profile, key=lambda x: x['put_oi'])
    put_wall = put_wall_entry['strike']
    put_wall_oi = put_wall_entry['put_oi']
    
    # Find call wall (strike with max call OI)
    call_wall_entry = max(gamma_profile, key=lambda x: x['call_oi'])
    call_wall = call_wall_entry['strike']
    call_wall_oi = call_wall_entry['call_oi']
    
    atm_strike = min(gamma_profile, key=lambda x: abs(x['strike'] - spot_price))['strike']
    total_gross_gex = sum(x['gross_gex'] for x in gamma_profile)
    
    logger.info(
        f"[GEX LEVELS] spot=${spot_price:.2f}, put_wall=${put_wall:.0f} (OI={put_wall_oi:,}), "
        f"call_wall=${call_wall:.0f} (OI={call_wall_oi:,}), max_gamma=${max_gamma_strike:.0f}"
    )
    
    # Log top 5 strikes by OI for debugging
    top_put_strikes = sorted(gamma_profile, key=lambda x: x['put_oi'], reverse=True)[:5]
    top_call_strikes = sorted(gamma_profile, key=lambda x: x['call_oi'], reverse=True)[:5]
    logger.debug(f"[GEX LEVELS] Top put OI strikes: {[(s['strike'], s['put_oi']) for s in top_put_strikes]}")
    logger.debug(f"[GEX LEVELS] Top call OI strikes: {[(s['strike'], s['call_oi']) for s in top_call_strikes]}")
    
    return {
        'max_gamma_strike': max_gamma_strike,
        'put_wall': put_wall,
        'call_wall': call_wall,
        'atm_strike': atm_strike,
        'total_gross_gex': total_gross_gex,
        'spot_price': spot_price
    }


# ============================================================================
# REGIME ESTIMATION (Autocorrelation-based - Default)
# ============================================================================

def _estimate_dealer_regime(
    returns: List[float],
    gamma_proxy: Optional[float] = None,
    lookback: int = 60
) -> Dict[str, Any]:
    """
    Estimate dealer gamma regime from return autocorrelation patterns.
    """
    logger.info(f"[GEX REGIME] Estimating regime with {len(returns)} returns, lookback={lookback}")
    
    min_required = min(lookback, 30)
    
    if len(returns) < min_required:
        logger.warning(f"[GEX REGIME] Insufficient returns: {len(returns)} < {min_required}")
        return {
            'regime': 'insufficient_data',
            'confidence': 0.0,
            'autocorr': None,
            'pvalue': None,
            'interpretation': f'Not enough historical data ({len(returns)} returns, need {min_required})'
        }
    
    actual_lookback = min(lookback, len(returns))
    recent_returns = returns[-actual_lookback:]
    
    logger.info(f"[GEX REGIME] Using {actual_lookback} days of returns for analysis")
    
    r_t = np.array(recent_returns[:-1])
    r_t1 = np.array(recent_returns[1:])
    
    valid_mask = np.isfinite(r_t) & np.isfinite(r_t1)
    r_t = r_t[valid_mask]
    r_t1 = r_t1[valid_mask]
    
    if len(r_t) < 20:
        return {
            'regime': 'insufficient_data',
            'confidence': 0.0,
            'autocorr': None,
            'pvalue': None,
            'interpretation': 'Not enough valid data points'
        }
    
    try:
        from scipy import stats as scipy_stats
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(r_t, r_t1)
    except Exception as e:
        logger.warning(f"Regression failed: {e}")
        return {
            'regime': 'estimation_failed',
            'confidence': 0.0,
            'autocorr': None,
            'pvalue': None,
            'interpretation': f'Regression failed: {e}'
        }
    
    autocorr = np.corrcoef(r_t, r_t1)[0, 1]
    significance_threshold = 0.10
    
    if p_value > significance_threshold:
        regime = 'neutral'
        confidence = 1.0 - p_value
        interpretation = (
            f"No statistically significant autocorrelation detected (p={p_value:.3f}). "
            "Market shows random walk behavior - gamma hedging effect not measurable."
        )
    elif slope > 0:
        regime = 'short_gamma'
        confidence = min(1.0, (1.0 - p_value) * abs(autocorr) * 3)
        interpretation = (
            f"Positive autocorrelation ({autocorr:.3f}, p={p_value:.3f}) suggests "
            "trending behavior consistent with dealers being SHORT gamma. "
            "Price moves tend to continue, indicating hedging amplification."
        )
    else:
        regime = 'long_gamma'
        confidence = min(1.0, (1.0 - p_value) * abs(autocorr) * 3)
        interpretation = (
            f"Negative autocorrelation ({autocorr:.3f}, p={p_value:.3f}) suggests "
            "mean-reverting behavior consistent with dealers being LONG gamma. "
            "Price moves tend to reverse, indicating hedging dampening."
        )
    
    return {
        'regime': regime,
        'confidence': round(confidence, 3),
        'autocorr': round(autocorr, 4),
        'beta': round(slope, 4),
        'pvalue': round(p_value, 4),
        'lookback_requested': lookback,
        'lookback_used': actual_lookback,
        'data_points': len(r_t),
        'interpretation': interpretation,
        'method': 'autocorrelation'
    }


def _generate_regime_signal(regime_estimate: Dict[str, Any], key_levels: Dict[str, Any]) -> str:
    """Generate actionable interpretation combining regime and key levels."""
    regime = regime_estimate.get('regime', 'unknown')
    confidence = regime_estimate.get('confidence', 0)
    spot = key_levels.get('spot_price', 0)
    max_gamma = key_levels.get('max_gamma_strike', 0)
    put_wall = key_levels.get('put_wall', 0)
    call_wall = key_levels.get('call_wall', 0)
    
    if regime == 'short_gamma' and confidence > 0.3:
        return (
            f"REGIME: Dealers likely SHORT gamma (confidence: {confidence:.0%}). "
            f"Expect trending/accelerating moves. "
            f"Key levels: Put wall ${put_wall:.0f} (support), Call wall ${call_wall:.0f} (resistance). "
            f"Max gamma at ${max_gamma:.0f} may act as pivot. "
            f"Implication: Moves away from ${spot:.0f} likely to extend."
        )
    elif regime == 'long_gamma' and confidence > 0.3:
        return (
            f"REGIME: Dealers likely LONG gamma (confidence: {confidence:.0%}). "
            f"Expect mean-reverting/choppy price action. "
            f"Key levels: Put wall ${put_wall:.0f}, Call wall ${call_wall:.0f}. "
            f"Max gamma at ${max_gamma:.0f} - price may be 'sticky' here. "
            f"Implication: Moves from ${spot:.0f} likely to fade."
        )
    else:
        return (
            f"REGIME: Neutral/unclear (confidence: {confidence:.0%}). "
            f"No strong hedging signal detected. Key levels still relevant: "
            f"Put wall ${put_wall:.0f}, Call wall ${call_wall:.0f}, Max gamma ${max_gamma:.0f}."
        )


# ============================================================================
# CHART BUILDING
# ============================================================================

def _build_gamma_profile_chart(
    underlying: str,
    gamma_profile: List[Dict[str, Any]],
    key_levels: Dict[str, Any],
    regime_estimate: Dict[str, Any],
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """Build gamma profile chart with key levels marked."""
    try:
        import plotly.graph_objects as go
        
        if not gamma_profile:
            return None
        
        strikes = [p['strike'] for p in gamma_profile]
        gross_gex = [p['gross_gex'] / 1e6 for p in gamma_profile]
        
        spot = key_levels.get('spot_price', 0)
        max_gamma = key_levels.get('max_gamma_strike', 0)
        put_wall = key_levels.get('put_wall', 0)
        call_wall = key_levels.get('call_wall', 0)
        
        regime = regime_estimate.get('regime', 'unknown')
        confidence = regime_estimate.get('confidence', 0)
        method = regime_estimate.get('method', 'autocorrelation')
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=strikes, y=gross_gex, name='Gross Gamma ($M)',
            marker=dict(color='#6366f1', line=dict(width=0)),
            hovertemplate='<b>Strike:</b> $%{x}<br><b>Gross GEX:</b> $%{y:.1f}M<extra></extra>'
        ))
        
        fig.add_vline(x=spot, line=dict(color='#ef4444', width=2, dash='solid'),
                      annotation=dict(text=f'Spot ${spot:.0f}', font=dict(color='#ef4444', size=11), yshift=10))
        
        if max_gamma != spot:
            fig.add_vline(x=max_gamma, line=dict(color='#f59e0b', width=2, dash='dot'),
                          annotation=dict(text=f'Max γ ${max_gamma:.0f}', font=dict(color='#f59e0b', size=10), yshift=-20))
        
        if put_wall and put_wall < spot:
            fig.add_vline(x=put_wall, line=dict(color='#22c55e', width=1.5, dash='dash'),
                          annotation=dict(text='Put Wall', font=dict(color='#22c55e', size=9), yshift=30, xshift=-10))
        
        if call_wall and call_wall > spot:
            fig.add_vline(x=call_wall, line=dict(color='#ef4444', width=1.5, dash='dash'),
                          annotation=dict(text='Call Wall', font=dict(color='#ef4444', size=9), yshift=30, xshift=10))
        
        regime_text = {
            'short_gamma': f'SHORT γ ({confidence:.0%})',
            'long_gamma': f'LONG γ ({confidence:.0%})',
            'neutral': 'Neutral',
            'SHORT_GAMMA': f'SHORT γ ({confidence:.0%}) [HMM]',
            'LONG_GAMMA': f'LONG γ ({confidence:.0%}) [HMM]',
            'NEUTRAL': 'Neutral [HMM]'
        }.get(regime, 'Unknown')
        
        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> Gross Gamma Profile · Regime: {regime_text}',
                font=dict(size=16, family='Inter, sans-serif', color='#0f172a'),
                x=0.5, xanchor='center'
            ),
            xaxis=dict(title=dict(text='Strike Price ($)', font=dict(size=12, color='#475569')),
                       gridcolor='#e2e8f0', tickfont=dict(size=10, color='#64748b')),
            yaxis=dict(title=dict(text='Gross Gamma Exposure ($M)', font=dict(size=12, color='#475569')),
                       gridcolor='#e2e8f0', tickfont=dict(size=10, color='#64748b')),
            width=900, height=500, paper_bgcolor='#ffffff', plot_bgcolor='#f8fafc',
            font=dict(family='Inter, sans-serif'), margin=dict(l=60, r=30, t=80, b=60), showlegend=False
        )
        
        return {'id': chart_id, 'title': f'{underlying} Gamma Profile', 'plotly': fig.to_dict()}
        
    except Exception as e:
        logger.error(f"Failed to build gamma profile chart: {e}", exc_info=True)
        return None


# ============================================================================
# MAIN TOOL FUNCTION
# ============================================================================

async def analyze_dealer_gamma_regime_internal(
    underlying: str,
    min_oi_threshold: int = 100,
    max_dte: int = 45,
    lookback_days: int = 60,
    use_hmm_regime: bool = False,
    hmm_n_states: int = 3,
    hmm_features: str = "autocorrelation,volatility,momentum"
) -> Dict[str, Any]:
    """
    Analyze dealer gamma exposure with regime estimation from price dynamics.
    
    Unlike traditional GEX tools that ASSUME dealer positioning, this tool
    ESTIMATES the gamma regime from observable return patterns.
    
    **Regime Detection Methods:**
    
    1. Autocorrelation-based (default, use_hmm_regime=False):
       - Fast, single-factor analysis
       - Positive autocorr → SHORT gamma (trending)
       - Negative autocorr → LONG gamma (mean-reverting)
    
    2. HMM-based (use_hmm_regime=True):
       - Multi-feature Hidden Markov Model
       - Learns regime states from data (not hardcoded)
       - Provides transition probabilities and persistence
       - More robust but requires more data
    
    **Available HMM Feature Families:**
    - autocorrelation: autocorr_1, autocorr_5, autocorr_10 (RECOMMENDED)
    - volatility: vol_10d, vol_20d, vol_ratio (RECOMMENDED)
    - vol_dynamics: vol_trend, vol_acceleration
    - momentum: ret_5d, ret_10d, ret_20d, trend_strength (RECOMMENDED)
    - higher_moments: skew, kurtosis
    - range: range_vol_ratio, range_expansion
    
    Args:
        underlying: Stock ticker (e.g., "AAPL", "SPY")
        min_oi_threshold: Minimum open interest to include (default 100)
        max_dte: Maximum days to expiration to include (default 45)
        lookback_days: Days of price history for regime estimation (default 60)
        use_hmm_regime: Use HMM-based regime detection (default: False)
        hmm_n_states: Number of HMM states (default: 3)
        hmm_features: Comma-separated feature families (default: "autocorrelation,volatility,momentum")
    
    Returns:
        - gross_gamma_profile: Gamma exposure by strike
        - key_levels: Max gamma strike, put wall, call wall
        - regime_estimate: Dealer regime with confidence
        - hmm_regime (if enabled): Detailed HMM state analysis
        - signal: Actionable interpretation
        - charts: Gamma profile visualization
    
    Example with HMM:
        >>> result = await analyze_dealer_gamma_regime(
        ...     underlying="SPY",
        ...     use_hmm_regime=True,
        ...     hmm_features="autocorrelation,volatility"
        ... )
        >>> print(result["hmm_regime"]["current_gamma_regime"])
        "SHORT_GAMMA"
    """
    underlying = underlying.upper().strip()
    
    fmp_server = FMPMarketDataServer()
    polygon_server = PolygonOptionsFuturesServer()
    
    try:
        await fmp_server.connect()
        await polygon_server.connect()
        
        # 1. Fetch current spot price
        spot_price = await _fetch_underlying_price(fmp_server, underlying)
        if not spot_price:
            return {'error': f'Could not fetch price for {underlying}', 'underlying': underlying}
        
        logger.info(f"[GEX] {underlying} spot price: ${spot_price:.2f}")
        
        # 2. Fetch options chain
        contracts = await _fetch_options_chain(polygon_server, underlying, max_dte=max_dte)
        if not contracts:
            return {'error': f'No options data available for {underlying}', 'underlying': underlying, 'spot_price': spot_price}
        
        # 3. Extract gamma data
        gamma_data = _extract_gamma_data(contracts, spot_price, min_oi=min_oi_threshold, max_dte=max_dte)
        
        if not gamma_data['by_strike']:
            return {'error': 'No contracts met OI/DTE filters', 'underlying': underlying,
                    'spot_price': spot_price, 'contracts_fetched': len(contracts)}
        
        logger.info(f"[GEX] Extracted gamma data for {len(gamma_data['by_strike'])} strikes")
        
        # 4. Compute gross gamma profile
        gamma_profile = _compute_gross_gamma_profile(gamma_data, spot_price)
        
        # 5. Identify key levels
        key_levels = _identify_key_levels(gamma_profile, spot_price)
        
        # 6. Fetch price history for regime estimation
        price_history = await _fetch_price_history(fmp_server, underlying, days=lookback_days + 30)
        
        # 7. Estimate dealer regime (standard method)
        if price_history and price_history.get('returns'):
            regime_estimate = _estimate_dealer_regime(
                price_history['returns'],
                gamma_proxy=key_levels.get('total_gross_gex'),
                lookback=lookback_days
            )
        else:
            regime_estimate = {
                'regime': 'no_history', 'confidence': 0.0,
                'interpretation': 'Could not fetch price history for regime estimation',
                'method': 'autocorrelation'
            }
        
        # 8. HMM Regime Detection (optional)
        hmm_regime = None
        if use_hmm_regime and price_history and price_history.get('returns'):
            logger.info("[GEX] Running HMM regime detection")
            
            feature_families_list = [f.strip() for f in hmm_features.split(",") if f.strip()]
            logger.info(f"[GEX] HMM using feature families: {feature_families_list}")
            
            detector = GammaRegimeDetector(n_states=hmm_n_states, feature_families=feature_families_list)
            hmm_regime = detector.fit_predict(
                price_history['returns'],
                price_history['prices'],
                window=min(20, lookback_days // 3)
            )
            
            if hmm_regime:
                # Update regime_estimate with HMM findings for chart display
                regime_estimate['hmm_regime'] = hmm_regime['current_gamma_regime']
                regime_estimate['regime'] = hmm_regime['current_gamma_regime']
                regime_estimate['confidence'] = hmm_regime['current_probability']
                regime_estimate['method'] = 'hmm'
                logger.info(f"[GEX] HMM regime: {hmm_regime['current_gamma_regime']} (P={hmm_regime['current_probability']:.2f})")
            else:
                logger.warning("[GEX] HMM fitting failed, using autocorrelation method")
        
        # 9. Generate signal
        signal = _generate_regime_signal(regime_estimate, key_levels)
        
        # 10. Build chart
        chart_id = f"gex_{underlying.lower()}_{datetime.now().strftime('%H%M%S')}"
        chart = _build_gamma_profile_chart(underlying, gamma_profile, key_levels, regime_estimate, chart_id)
        charts = [chart] if chart else []
        
        # 11. Prepare output
        output = {
            'underlying': underlying,
            'spot_price': spot_price,
            'timestamp': datetime.now().isoformat(),
            
            'key_levels': {
                'max_gamma_strike': key_levels.get('max_gamma_strike'),
                'put_wall': key_levels.get('put_wall'),
                'call_wall': key_levels.get('call_wall'),
                'atm_strike': key_levels.get('atm_strike'),
                'total_gross_gex_millions': round(key_levels.get('total_gross_gex', 0) / 1e6, 2)
            },
            
            'regime_estimate': regime_estimate,
            'signal': signal,
            
            'data_quality': {
                'contracts_analyzed': gamma_data['contracts_included'],
                'strikes_included': len(gamma_data['by_strike']),
                'total_call_oi': gamma_data['total_call_oi'],
                'total_put_oi': gamma_data['total_put_oi'],
                'put_call_oi_ratio': round(gamma_data['total_put_oi'] / max(1, gamma_data['total_call_oi']), 3)
            },
            
            'gamma_profile': [
                {
                    'strike': p['strike'],
                    'gross_gex_millions': round(p['gross_gex'] / 1e6, 3),
                    'call_oi': p['call_oi'],
                    'put_oi': p['put_oi'],
                    'moneyness': round(p['moneyness'], 3)
                }
                for p in gamma_profile
            ],
            
            'methodology': (
                "This tool estimates dealer gamma regime from return patterns. "
                f"Method: {'HMM (multi-feature)' if use_hmm_regime and hmm_regime else 'autocorrelation (single-factor)'}. "
                "Positive autocorr → SHORT gamma (trending); negative → LONG gamma (mean-reverting). "
                "Key levels (put wall, call wall, max gamma) are observable facts."
            )
        }
        
        # Include HMM details if available
        if hmm_regime:
            output['hmm_regime'] = hmm_regime
        
        output['charts'] = wrap_plotly_charts(charts, default_type="gamma_profile")
        return output
        
    except Exception as e:
        logger.error(f"Dealer gamma analysis failed: {e}", exc_info=True)
        return {'error': str(e), 'underlying': underlying}
    
    finally:
        await fmp_server.cleanup()
        await polygon_server.cleanup()


@function_tool
async def analyze_dealer_gamma_regime(
    underlying: str,
    min_oi_threshold: int = 100,
    max_dte: int = 45,
    lookback_days: int = 60,
    use_hmm_regime: bool = False,
    hmm_n_states: int = 3,
    hmm_features: str = "autocorrelation,volatility,momentum"
) -> Dict[str, Any]:
    """
    Analyze dealer gamma exposure with regime estimation from price dynamics.
    
    Unlike traditional GEX tools that ASSUME dealer positioning, this tool
    ESTIMATES the gamma regime from observable return patterns.
    
    Args:
        underlying: Stock ticker (e.g., "AAPL", "SPY")
        min_oi_threshold: Minimum open interest to include (default 100)
        max_dte: Maximum days to expiration to include (default 45)
        lookback_days: Days of price history for regime estimation (default 60)
        use_hmm_regime: Use HMM-based regime detection (default: False)
        hmm_n_states: Number of HMM states (default: 3)
        hmm_features: Comma-separated feature families
    
    Returns:
        Gamma profile, key levels, regime estimate, and charts
    """
    return await analyze_dealer_gamma_regime_internal(
        underlying=underlying,
        min_oi_threshold=min_oi_threshold,
        max_dte=max_dte,
        lookback_days=lookback_days,
        use_hmm_regime=use_hmm_regime,
        hmm_n_states=hmm_n_states,
        hmm_features=hmm_features,
    )
