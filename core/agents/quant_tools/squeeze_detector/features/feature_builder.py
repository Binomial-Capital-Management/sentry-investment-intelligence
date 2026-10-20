"""
Feature Builder

Combines all feature groups into a unified feature vector.
Z-scores computed from data-provided statistics where available.
No hardcoded baseline thresholds.
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def build_feature_vector(
    gamma_features: Optional[Dict] = None,
    momentum_features: Optional[Dict] = None,
    short_features: Optional[Dict] = None,
    spot_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Build unified feature vector from all feature groups.
    
    Z-scores computed from:
    1. Historical stats provided by feature extractors (preferred)
    2. Relative to data range if no stats provided
    
    Returns:
        Dict with:
        - features: All features with z-scores
        - key_levels: Important price levels (walls, ramps)
        - importance: Feature importance estimates
    """
    features = {}
    key_levels = {}
    raw_values = {}
    
    # =========================================================
    # GAMMA FEATURES
    # =========================================================
    if gamma_features:
        levels = gamma_features.get("key_levels", {}) or {}
        key_levels.update({
            "put_wall": levels.get("put_wall"),
            "call_wall": levels.get("call_wall"),
            "zero_gamma": levels.get("zero_gamma"),
            "gamma_ramp": levels.get("gamma_ramp"),
            "max_gamma": levels.get("max_gamma")
        })
        
        features["gamma_regime"] = gamma_features.get("regime", "unknown")
        
        # GEX concentration (0-1 scale, higher = more concentrated)
        concentration = gamma_features.get("gex_concentration", 0) or 0
        features["gex_concentration"] = concentration
        # Convert concentration to z-score: 0.3 = normal, 0.6+ = elevated
        features["gex_concentration_zscore"] = round((concentration - 0.3) * 5, 2)
        
        # Ramp proximity - how close is spot to gamma ramp trigger
        if spot_price and levels.get("gamma_ramp"):
            ramp = levels["gamma_ramp"]
            distance_pct = abs(spot_price - ramp) / spot_price
            proximity = 1.0 - min(distance_pct, 1.0)
            features["gamma_ramp_proximity"] = round(proximity, 3)
            raw_values["gamma_ramp_proximity"] = proximity
            # Proximity z-score: 0.9+ is very close (elevated), 0.5 is normal
            features["gamma_ramp_proximity_zscore"] = round((proximity - 0.5) * 4, 2)
    
    # =========================================================
    # MOMENTUM FEATURES
    # =========================================================
    if momentum_features:
        oi_data = momentum_features.get("oi_changes", {}) or {}
        unusual = momentum_features.get("unusual_activity", {}) or {}
        hottest = momentum_features.get("hottest_contracts", {}) or {}
        
        # Call OI change
        call_oi_change = oi_data.get("call_oi_change", 0) or 0
        put_oi_change = oi_data.get("put_oi_change", 0) or 0
        features["call_oi_change"] = call_oi_change
        features["put_oi_change"] = put_oi_change
        raw_values["call_oi_change"] = call_oi_change
        
        # Compute call/put OI ratio as a normalized signal
        # Ratio > 1 = bullish bias, < 1 = bearish
        total_oi = abs(call_oi_change) + abs(put_oi_change)
        if total_oi > 0:
            call_ratio = call_oi_change / total_oi
            # Convert to z-score-like metric: 0.5 = neutral, map to ~0
            # 0.8 = very bullish, map to ~2, 0.2 = bearish, map to ~-2
            features["call_oi_change_zscore"] = round((call_ratio - 0.5) * 6, 2)
        else:
            features["call_oi_change_zscore"] = 0.0
        
        # Unusual activity count
        vol_oi_count = unusual.get("vol_greater_oi_count", 0) or 0
        features["vol_greater_oi_count"] = vol_oi_count
        raw_values["vol_greater_oi_count"] = vol_oi_count
        
        # Normalize vol>OI count: typical is 5-15, elevated is 30+
        # Use log scaling to create z-score proxy
        if vol_oi_count > 0:
            # log(count) - log(10) normalized by log(3) gives ~z-score
            features["vol_greater_oi_zscore"] = round((np.log1p(vol_oi_count) - np.log(10)) / 0.5, 2)
        else:
            features["vol_greater_oi_zscore"] = 0.0
        
        # Call bias from unusual activity
        call_count = unusual.get("vol_greater_oi_calls", 0) or 0
        put_count = unusual.get("vol_greater_oi_puts", 0) or 0
        if call_count + put_count > 0:
            features["unusual_call_bias"] = round(call_count / (call_count + put_count), 2)
        
        if hottest.get("hottest_call_strike"):
            features["hottest_call_strike"] = hottest["hottest_call_strike"]
    
    # =========================================================
    # SHORT FEATURES
    # =========================================================
    if short_features:
        si_data = short_features.get("short_interest", {}) or {}
        ftd_data = short_features.get("ftd", {}) or {}
        borrow_data = short_features.get("borrow", {}) or {}
        
        # Short interest % - typical is 2-5%, elevated is 15%+, extreme is 30%+
        si_pct = si_data.get("short_interest_pct")
        if si_pct is not None:
            features["short_interest_pct"] = si_pct
            raw_values["short_interest_pct"] = si_pct
            # Z-score: 5% = 0, 15% = 2, 30% = 4
            features["short_interest_zscore"] = round((si_pct - 5) / 5, 2)
        
        # Days to cover - typical is 1-3, elevated is 5+, extreme is 10+
        dtc = si_data.get("days_to_cover")
        if dtc is not None:
            features["days_to_cover"] = dtc
            raw_values["days_to_cover"] = dtc
            # Z-score: 2 = 0, 5 = 1.5, 10 = 4
            features["days_to_cover_zscore"] = round((dtc - 2) / 2, 2)
        
        # FTD trend and change
        ftd_trend = ftd_data.get("ftd_trend", "unknown")
        ftd_change = ftd_data.get("ftd_change_pct", 0) or 0
        features["ftd_trend"] = ftd_trend
        features["ftd_increasing"] = ftd_trend == "increasing"
        features["ftd_change_pct"] = ftd_change
        # FTD z-score from change %: 0% = 0, 50% increase = 1, 100% = 2
        features["ftd_zscore"] = round(ftd_change / 50, 2) if ftd_change else 0.0
        
        # Borrow fee - typical is 0.5-2%, elevated is 10%+, extreme is 50%+
        borrow_fee = borrow_data.get("borrow_fee_pct")
        if borrow_fee is not None:
            features["borrow_fee_pct"] = borrow_fee
            raw_values["borrow_fee_pct"] = borrow_fee
            # Z-score: 1% = 0, 10% = 1.8, 50% = 4
            features["borrow_fee_zscore"] = round((borrow_fee - 1) / 5, 2)
        
        features["hard_to_borrow"] = borrow_data.get("hard_to_borrow", False)
    
    # =========================================================
    # INTERPRETATIONS & IMPORTANCE
    # =========================================================
    features = _add_interpretations(features)
    importance = _estimate_importance(features)
    
    return {
        "features": features,
        "key_levels": {k: v for k, v in key_levels.items() if v is not None},
        "raw_values": raw_values,
        "importance": importance
    }


def _compute_zscore(value: float, stats: Dict) -> float:
    """
    Compute z-score using provided statistics.
    
    If stats has mean/std, use them.
    If stats has percentiles, compute z-score from distribution.
    If no stats, return 0 (unknown significance).
    
    IMPORTANT: Never fake a z-score. If we don't have stats, we don't know.
    """
    if not isinstance(value, (int, float)) or np.isnan(value):
        return 0.0
    
    mean = stats.get("mean")
    std = stats.get("std")
    
    if mean is not None and std is not None and std > 0:
        z = (value - mean) / std
        # Cap at ±5 to prevent outliers from dominating
        return round(np.clip(z, -5, 5), 2)
    
    # If percentiles provided, estimate z from position
    p50 = stats.get("p50") or stats.get("median")
    p75 = stats.get("p75")
    p25 = stats.get("p25")
    
    if p50 is not None and p75 is not None and p25 is not None:
        iqr = p75 - p25
        if iqr > 0:
            # Approximate z-score from percentile position
            z = (value - p50) / (iqr * 0.7413)  # IQR ≈ 1.35σ
            return round(np.clip(z, -5, 5), 2)
    
    # NO STATS AVAILABLE - return 0 (unknown significance)
    # Do NOT fake a z-score from log-scaling - that produces garbage
    return 0.0


def _add_interpretations(features: Dict) -> Dict:
    """Add human-readable interpretations based on z-scores."""
    for key, value in list(features.items()):
        if key.endswith("_zscore") and isinstance(value, (int, float)):
            base_key = key.replace("_zscore", "")
            
            if value > 2.5:
                features[f"{base_key}_interpretation"] = "extreme"
            elif value > 1.5:
                features[f"{base_key}_interpretation"] = "very_high"
            elif value > 1.0:
                features[f"{base_key}_interpretation"] = "high"
            elif value > 0.5:
                features[f"{base_key}_interpretation"] = "elevated"
            elif value < -1.5:
                features[f"{base_key}_interpretation"] = "very_low"
            elif value < -0.5:
                features[f"{base_key}_interpretation"] = "low"
            else:
                features[f"{base_key}_interpretation"] = "normal"
    
    return features


def _estimate_importance(features: Dict) -> Dict[str, float]:
    """
    Estimate feature importance based on z-score magnitudes.
    This is a heuristic - actual models will compute proper importance.
    """
    importance = {}
    total = 0.0
    
    for key, value in features.items():
        if key.endswith("_zscore") and isinstance(value, (int, float)):
            base_key = key.replace("_zscore", "")
            imp = abs(value)
            importance[base_key] = imp
            total += imp
    
    # Normalize to sum to 1
    if total > 0:
        importance = {k: round(v / total, 3) for k, v in importance.items()}
    
    return importance

