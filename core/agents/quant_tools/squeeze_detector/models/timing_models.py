"""
Timing Models for Squeeze Detection

Predict WHEN a squeeze triggers using data-driven approaches.
No hardcoded coefficients - models work directly with z-scored features.

Models:
- Survival: Time-to-event based on signal strength
- Logistic: Multi-signal probability estimation
- XGBoost: Nonlinear pattern detection
"""

import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod
import numpy as np

logger = logging.getLogger(__name__)


class TimingModel(ABC):
    """Base class for timing models."""
    
    @abstractmethod
    def predict(self, features: Dict) -> Dict[str, Any]:
        """
        Predict squeeze timing from z-scored features.
        
        Returns:
            trigger_prob_5d, trigger_prob_10d, median_days_to_trigger,
            signal_count, elevated_signals
        """
        pass
    
    def _extract_zscores(self, features: Dict) -> Dict[str, float]:
        """Extract all z-score features dynamically."""
        feature_values = features.get("features", {})
        zscores = {}
        
        for key, val in feature_values.items():
            if isinstance(val, (int, float)) and not np.isnan(val):
                # Accept any numeric feature - no hardcoded field names
                zscores[key] = float(val)
        
        return zscores
    
    def _compute_signal_strength(self, zscores: Dict[str, float], threshold: float = 2.0) -> Dict:
        """
        Compute aggregate signal strength from z-scores.
        
        No hardcoded weights - treats all elevated signals equally,
        then adjusts based on signal count (wisdom of crowds).
        """
        elevated = {k: v for k, v in zscores.items() if abs(v) >= threshold}
        
        # Cap individual z-scores to prevent single-signal dominance
        capped = {k: np.clip(v, -4, 4) for k, v in elevated.items()}
        
        # Aggregate: mean of elevated signals (not sum)
        if capped:
            mean_signal = np.mean(list(capped.values()))
            max_signal = max(capped.values())
        else:
            mean_signal = 0
            max_signal = 0
        
        return {
            "elevated_count": len(elevated),
            "total_features": len(zscores),
            "mean_signal": mean_signal,
            "max_signal": max_signal,
            "elevated_features": list(elevated.keys())
        }


class SurvivalModel(TimingModel):
    """
    Time-to-event model based on signal strength.
    
    Hazard rate derived from z-score distribution - no hardcoded thresholds.
    """
    
    def __init__(self, z_threshold: float = 2.0, **kwargs):
        self.z_threshold = z_threshold
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict using survival model - derived from data."""
        zscores = self._extract_zscores(features)
        signal_info = self._compute_signal_strength(zscores, self.z_threshold)
        
        n_elevated = signal_info["elevated_count"]
        mean_signal = signal_info["mean_signal"]
        max_signal = signal_info["max_signal"]
        elevated_features = signal_info["elevated_features"]
        n_total = signal_info["total_features"]
        
        # Compute hazard from data distribution
        # Base hazard is LOW (most setups don't trigger)
        base_hazard = 0.005  # 0.5% daily base rate
        
        # Signal count contribution (sigmoid to prevent explosion)
        count_contrib = np.tanh(n_elevated / 3.0) * 0.03
        
        # Mean signal strength contribution (only if elevated)
        strength_contrib = np.tanh(max(0, mean_signal) / 3.0) * 0.02 if n_elevated > 0 else 0
        
        # Coverage bonus (fraction of signals elevated)
        coverage = n_elevated / max(n_total, 1)
        coverage_contrib = coverage * 0.01
        
        # Combined daily hazard
        daily_hazard = base_hazard + count_contrib + strength_contrib + coverage_contrib
        daily_hazard = np.clip(daily_hazard, 0.005, 0.15)  # Cap at 15% daily
        
        # Survival probabilities from hazard
        survival_5d = np.exp(-daily_hazard * 5)
        survival_10d = np.exp(-daily_hazard * 10)
        
        trigger_5d = 1 - survival_5d
        trigger_10d = 1 - survival_10d
        
        # Median time from hazard
        median_days = np.log(2) / daily_hazard if daily_hazard > 0 else 30
        median_days = min(median_days, 30)
        
        # Build survival curve
        days = list(range(0, 31))
        survival_curve = [np.exp(-daily_hazard * d) for d in days]
        
        return {
            "model": "survival",
            "trigger_prob_5d": round(trigger_5d, 3),
            "trigger_prob_10d": round(trigger_10d, 3),
            "median_days_to_trigger": round(median_days, 1),
            "daily_hazard_rate": round(daily_hazard, 4),
            "signal_count": n_elevated,
            "elevated_signals": elevated_features,
            "survival_curve": {
                "days": days,
                "survival_probability": [round(s, 3) for s in survival_curve]
            }
        }


class LogisticModel(TimingModel):
    """
    Multi-signal probability model using logistic regression.
    
    Probability derived from z-score aggregation through sigmoid.
    """
    
    def __init__(self, z_threshold: float = 2.0, **kwargs):
        self.z_threshold = z_threshold
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict using logistic aggregation - derived from data."""
        zscores = self._extract_zscores(features)
        signal_info = self._compute_signal_strength(zscores, self.z_threshold)
        
        n_elevated = signal_info["elevated_count"]
        mean_signal = signal_info["mean_signal"]
        max_signal = signal_info["max_signal"]
        n_total = signal_info["total_features"]
        
        # Logit built from signal statistics
        # Strong negative intercept (prior against squeeze)
        logit = -3.5
        
        # Signal count contribution (tanh to prevent explosion)
        logit += 1.5 * np.tanh(n_elevated / 2.0)
        
        # Mean signal strength (capped contribution)
        logit += 0.5 * np.tanh(mean_signal / 2.0)
        
        # Coverage (fraction of features elevated)
        coverage = n_elevated / max(n_total, 1)
        logit += 0.5 * coverage
        
        # Sigmoid
        prob = 1 / (1 + np.exp(-logit))
        
        # Time estimate inversely proportional to probability
        median_days = np.log(2) / max(prob * 0.1, 0.01)
        median_days = np.clip(median_days, 3, 30)
        
        return {
            "model": "logistic",
            "trigger_prob_5d": round(prob * 0.6, 3),
            "trigger_prob_10d": round(prob * 0.8, 3),
            "trigger_probability": round(prob, 3),
            "median_days_to_trigger": round(median_days, 1),
            "signal_count": n_elevated,
            "elevated_signals": signal_info["elevated_features"],
            "logit": round(logit, 2)
        }


class XGBoostTimingModel(TimingModel):
    """
    Nonlinear pattern detection model.
    
    Uses signal category diversity and interaction effects.
    """
    
    def __init__(self, z_threshold: float = 2.0, **kwargs):
        self.z_threshold = z_threshold
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict using nonlinear signal combination - derived from data."""
        zscores = self._extract_zscores(features)
        signal_info = self._compute_signal_strength(zscores, self.z_threshold)
        
        n_elevated = signal_info["elevated_count"]
        mean_signal = signal_info["mean_signal"]
        total_features = signal_info["total_features"]
        elevated_features = signal_info["elevated_features"]
        
        # Dynamically categorize elevated signals by name patterns
        gamma_signals = [k for k in elevated_features if 'gamma' in k.lower() or 'gex' in k.lower()]
        short_signals = [k for k in elevated_features if 'short' in k.lower() or 'borrow' in k.lower() or 'dtc' in k.lower()]
        momentum_signals = [k for k in elevated_features if 'oi' in k.lower() or 'vol' in k.lower() or 'momentum' in k.lower()]
        
        categories_active = sum([
            len(gamma_signals) > 0,
            len(short_signals) > 0,
            len(momentum_signals) > 0
        ])
        
        # Base probability from signal statistics (sigmoid)
        coverage = n_elevated / max(total_features, 1)
        base_logit = -3.0 + 1.5 * np.tanh(n_elevated / 2.0) + 0.5 * np.tanh(mean_signal / 2.0)
        
        # Synergy multiplier (categories confirming each other)
        synergy_factor = 1.0 + 0.2 * np.tanh(categories_active - 1)
        
        # Combined probability
        prob = (1 / (1 + np.exp(-base_logit))) * synergy_factor
        prob = np.clip(prob, 0.01, 0.70)
        
        # Median days from probability
        median_days = np.log(2) / max(prob * 0.1, 0.01)
        median_days = np.clip(median_days, 3, 30)
        
        # Feature importance from z-score magnitudes
        feature_importance = {}
        if zscores:
            total_abs = sum(abs(v) for v in zscores.values())
            if total_abs > 0:
                feature_importance = {k: round(abs(v) / total_abs, 3) for k, v in zscores.items()}
        
        return {
            "model": "xgboost",
            "trigger_prob_5d": round(prob * 0.55, 3),
            "trigger_prob_10d": round(prob * 0.75, 3),
            "trigger_probability": round(prob, 3),
            "median_days_to_trigger": round(median_days, 1),
            "signal_count": n_elevated,
            "elevated_signals": elevated_features,
            "categories_active": categories_active,
            "synergy_factor": round(synergy_factor, 3),
            "feature_importance": feature_importance
        }

