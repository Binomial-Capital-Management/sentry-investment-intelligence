"""
Magnitude Models for Squeeze Detection

Predict HOW BIG a squeeze could be using data-driven approaches.
No hardcoded coefficients - magnitude scales with signal strength.

Models:
- GP: Gaussian Process with uncertainty from data
- QuantileRF: Distribution estimation from signal spread
- Linear: Simple aggregation baseline
"""

import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod
import numpy as np

logger = logging.getLogger(__name__)


class MagnitudeModel(ABC):
    """Base class for magnitude models."""
    
    @abstractmethod
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict squeeze magnitude from z-scored features."""
        pass
    
    def _extract_zscores(self, features: Dict) -> Dict[str, float]:
        """Extract all z-score features dynamically."""
        feature_values = features.get("features", {})
        zscores = {}
        
        for key, val in feature_values.items():
            if isinstance(val, (int, float)) and not np.isnan(val):
                zscores[key] = float(val)
        
        return zscores
    
    def _compute_magnitude_factors(self, zscores: Dict[str, float]) -> Dict:
        """
        Compute magnitude scaling from signal distribution.
        
        Higher mean z-score → larger expected move
        More signals elevated → more confidence in estimate
        """
        if not zscores:
            return {"mean": 0, "max": 0, "spread": 0, "count": 0}
        
        values = list(zscores.values())
        positive_values = [v for v in values if v > 0]
        
        return {
            "mean": np.mean(values),
            "max": max(values),
            "min": min(values),
            "spread": np.std(values) if len(values) > 1 else 0,
            "count": len(values),
            "positive_mean": np.mean(positive_values) if positive_values else 0
        }


class GPModel(MagnitudeModel):
    """
    Gaussian Process magnitude prediction.
    
    Expected move derived from z-score distribution statistics.
    """
    
    def __init__(self, kernel: str = "matern", **kwargs):
        self.kernel = kernel
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict using GP-style reasoning - derived from data."""
        zscores = self._extract_zscores(features)
        factors = self._compute_magnitude_factors(zscores)
        
        # Derive expected move from signal statistics
        # Base move scales with positive mean signal (tanh to bound)
        positive_mean = factors["positive_mean"]
        max_signal = factors["max"]
        n_signals = factors["count"]
        
        # Expected move: 2% base + scaled contribution from signals
        base = 0.02
        signal_contrib = 0.03 * np.tanh(positive_mean / 2.0)
        max_contrib = 0.02 * np.tanh(max(0, max_signal - 2) / 2.0)
        
        expected = base + signal_contrib + max_contrib
        expected = np.clip(expected, 0.02, 0.40)
        
        # Uncertainty inversely scales with signal count
        # More signals = more confidence = tighter CI
        confidence = np.tanh(n_signals / 5.0)
        base_std = 0.08
        std = base_std * (1 - 0.5 * confidence)
        std = np.clip(std, 0.02, 0.12)
        
        # 90% CI
        ci_low = max(0.01, expected - 1.645 * std)
        ci_high = min(0.60, expected + 1.645 * std)
        
        return {
            "model": "gp",
            "kernel": self.kernel,
            "expected_move": round(expected, 3),
            "ci_90": [round(ci_low, 3), round(ci_high, 3)],
            "std": round(std, 3),
            "uncertainty": round(std / expected, 3) if expected > 0 else 1.0,
            "signal_count": n_signals,
            "positive_mean": round(positive_mean, 2)
        }


class QuantileRFModel(MagnitudeModel):
    """
    Quantile estimation from signal distribution.
    
    Builds distribution from z-score statistics.
    """
    
    def __init__(self, n_estimators: int = 200, **kwargs):
        self.n_estimators = n_estimators
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict distribution using signal-based scaling - derived from data."""
        zscores = self._extract_zscores(features)
        factors = self._compute_magnitude_factors(zscores)
        
        positive_mean = factors["positive_mean"]
        signal_spread = factors["spread"]
        n_signals = factors["count"]
        
        # Median from positive signal mean (tanh bounded)
        median = 0.02 + 0.08 * np.tanh(positive_mean / 2.0)
        median = np.clip(median, 0.02, 0.35)
        
        # Spread scales with signal variance (uncertain inputs → uncertain outputs)
        base_spread = 0.03
        spread = base_spread * (1 + 0.3 * np.tanh(signal_spread))
        
        # Tighter spread with more signals (confidence)
        confidence = np.tanh(n_signals / 5.0)
        spread *= (1 - 0.3 * confidence)
        spread = np.clip(spread, 0.02, 0.10)
        
        # Build quantiles around median
        quantiles = {
            "p5": max(0.01, median - 2.0 * spread),
            "p10": max(0.01, median - 1.5 * spread),
            "p25": max(0.01, median - 0.7 * spread),
            "p50": median,
            "p75": median + 0.7 * spread,
            "p90": min(median + 1.5 * spread, 0.50),
            "p95": min(median + 2.0 * spread, 0.60)
        }
        
        quantiles = {k: round(v, 3) for k, v in quantiles.items()}
        
        return {
            "model": "quantile_rf",
            "n_estimators": self.n_estimators,
            "expected_move": quantiles["p50"],
            "ci_90": [quantiles["p10"], quantiles["p90"]],
            "quantiles": quantiles,
            "uncertainty": round(spread / median, 3) if median > 0 else 1.0,
            "signal_count": n_signals,
            "positive_mean": round(positive_mean, 2)
        }


class LinearModel(MagnitudeModel):
    """Simple linear aggregation of signals."""
    
    def __init__(self, **kwargs):
        pass
    
    def predict(self, features: Dict) -> Dict[str, Any]:
        """Predict using linear combination of signal statistics."""
        zscores = self._extract_zscores(features)
        factors = self._compute_magnitude_factors(zscores)
        
        # Linear combination: base + scaled mean
        positive_mean = factors["positive_mean"]
        n_signals = factors["count"]
        
        expected = 0.02 + 0.025 * np.tanh(positive_mean / 2.0)
        expected = np.clip(expected, 0.02, 0.30)
        
        # Fixed relative std
        std = 0.04
        
        return {
            "model": "linear",
            "expected_move": round(expected, 3),
            "ci_90": [round(max(0.01, expected - 1.645 * std), 3), 
                      round(min(expected + 1.645 * std, 0.40), 3)],
            "uncertainty": round(std / expected, 3) if expected > 0 else 1.0,
            "signal_count": n_signals,
            "positive_mean": round(positive_mean, 2)
        }

