"""
Path Models for Squeeze Simulation

Simulate future price trajectories:
- MonteCarloPathModel: Conditional MC with regime dynamics

These generate full path distributions, not just endpoints.
"""

import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import numpy as np

logger = logging.getLogger(__name__)


class PathModel(ABC):
    """Base class for path simulation models."""
    
    @abstractmethod
    def simulate(self, features: Dict, spot_price: float) -> Dict[str, Any]:
        """
        Simulate price paths.
        
        Args:
            features: Feature vector
            spot_price: Current price
            
        Returns:
            Dict with:
            - paths: Simulated paths array (n_paths, horizon)
            - percentile_paths: Key percentile paths
            - peak_timing: Distribution of peak timing
        """
        pass


class MonteCarloPathModel(PathModel):
    """
    Conditional Monte Carlo with squeeze dynamics.
    
    Simulates paths that capture:
    - Normal regime: low vol, mean-reverting
    - Trigger regime: high vol, momentum
    - Peak regime: extreme vol, reversal risk
    
    Parameters:
        n_paths: Number of paths to simulate (default: 500)
        horizon_days: Simulation horizon (default: 30)
    """
    
    def __init__(
        self,
        n_paths: int = 500,
        horizon_days: int = 30,
        **kwargs
    ):
        self.n_paths = n_paths
        self.horizon_days = horizon_days
        
        # Regime parameters
        self._regimes = {
            "normal": {
                "daily_vol": 0.02,
                "drift": 0.0,
                "mean_reversion": 0.1
            },
            "trigger": {
                "daily_vol": 0.05,
                "drift": 0.03,
                "momentum": 0.3
            },
            "squeeze": {
                "daily_vol": 0.10,
                "drift": 0.05,
                "momentum": 0.5
            },
            "peak": {
                "daily_vol": 0.15,
                "drift": -0.02,
                "reversal_prob": 0.3
            }
        }
    
    def simulate(self, features: Dict, spot_price: float) -> Dict[str, Any]:
        """Simulate paths with conditional dynamics."""
        feature_values = features.get("features", {})
        
        # Determine initial regime probabilities from features
        trigger_prob = self._get_trigger_probability(feature_values)
        squeeze_intensity = self._get_squeeze_intensity(feature_values)
        
        # Initialize paths
        paths = np.zeros((self.n_paths, self.horizon_days + 1))
        paths[:, 0] = spot_price
        
        # Simulate each path
        np.random.seed(42)  # Reproducibility
        
        for i in range(self.n_paths):
            regime = "normal"
            peak_reached = False
            
            for t in range(1, self.horizon_days + 1):
                # Regime transition logic
                if regime == "normal":
                    if np.random.random() < trigger_prob * 0.1:  # Daily trigger chance
                        regime = "trigger"
                
                elif regime == "trigger":
                    if np.random.random() < 0.3 * squeeze_intensity:
                        regime = "squeeze"
                    elif np.random.random() < 0.1:
                        regime = "normal"  # Failed trigger
                
                elif regime == "squeeze":
                    if np.random.random() < 0.1 + 0.02 * t:  # Increasing peak prob
                        regime = "peak"
                        peak_reached = True
                
                elif regime == "peak":
                    if np.random.random() < 0.2:
                        regime = "normal"  # Collapse
                
                # Get regime parameters
                params = self._regimes[regime]
                
                # Generate return
                vol = params["daily_vol"]
                drift = params["drift"]
                
                # Add momentum/mean-reversion effects
                if "momentum" in params and t > 1:
                    prev_return = (paths[i, t-1] - paths[i, t-2]) / paths[i, t-2]
                    drift += params["momentum"] * prev_return
                
                if "mean_reversion" in params:
                    deviation = (paths[i, t-1] - spot_price) / spot_price
                    drift -= params["mean_reversion"] * deviation
                
                # Simulate return
                daily_return = drift + vol * np.random.randn()
                paths[i, t] = paths[i, t-1] * (1 + daily_return)
        
        # Calculate percentiles
        percentile_paths = {}
        for p in [10, 25, 50, 75, 90]:
            percentile_paths[f"p{p}"] = np.percentile(paths, p, axis=0).tolist()
        
        # Peak timing distribution
        peak_days = []
        for i in range(self.n_paths):
            peak_idx = np.argmax(paths[i, :])
            if paths[i, peak_idx] > spot_price * 1.1:  # Only count meaningful peaks
                peak_days.append(peak_idx)
        
        peak_timing = {
            "p25": int(np.percentile(peak_days, 25)) if peak_days else None,
            "p50": int(np.percentile(peak_days, 50)) if peak_days else None,
            "p75": int(np.percentile(peak_days, 75)) if peak_days else None
        }
        
        # Summary stats
        final_prices = paths[:, -1]
        max_prices = np.max(paths, axis=1)
        
        return {
            "model": "monte_carlo",
            "n_paths": self.n_paths,
            "horizon_days": self.horizon_days,
            "percentile_paths": percentile_paths,
            "final_price_distribution": {
                "p10": round(np.percentile(final_prices, 10), 2),
                "p50": round(np.percentile(final_prices, 50), 2),
                "p90": round(np.percentile(final_prices, 90), 2)
            },
            "max_price_distribution": {
                "p10": round(np.percentile(max_prices, 10), 2),
                "p50": round(np.percentile(max_prices, 50), 2),
                "p90": round(np.percentile(max_prices, 90), 2)
            },
            "peak_timing": peak_timing,
            "squeeze_probability": round(
                np.mean(max_prices > spot_price * 1.2), 3
            )
        }
    
    def _get_trigger_probability(self, features: Dict) -> float:
        """Estimate trigger probability from features."""
        prob = 0.1  # Baseline
        
        prox = features.get("gamma_ramp_proximity", 0)
        if isinstance(prox, (int, float)):
            prob += 0.3 * prox
        
        call_z = features.get("call_oi_change_zscore", 0)
        if isinstance(call_z, (int, float)) and call_z > 0:
            prob += 0.1 * min(call_z, 3)
        
        return min(prob, 0.8)
    
    def _get_squeeze_intensity(self, features: Dict) -> float:
        """Estimate squeeze intensity from features."""
        intensity = 0.5  # Baseline
        
        short_z = features.get("short_interest_zscore", 0)
        if isinstance(short_z, (int, float)) and short_z > 0:
            intensity += 0.2 * min(short_z, 3)
        
        vol_oi_z = features.get("vol_greater_oi_zscore", 0)
        if isinstance(vol_oi_z, (int, float)) and vol_oi_z > 0:
            intensity += 0.1 * min(vol_oi_z, 3)
        
        return min(intensity, 1.5)

