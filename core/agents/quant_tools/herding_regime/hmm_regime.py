"""
Hidden Markov Model for Herding Regime Detection.

3-state HMM trained on Ising statistics to classify market regimes:
- State 0: Dispersed (low herding, idiosyncratic)
- State 1: Normal (moderate herding)
- State 2: Critical (high herding, contagion risk)

Transition matrix and emission parameters are LEARNED from data,
not specified as priors.

Note: Uses diagonal covariance and holdout validation to prevent
overfitting and produce calibrated probability estimates.
"""

from typing import Dict, List, Optional, Any, Tuple
import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Try to import hmmlearn
try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logger.warning("hmmlearn not available. HMM regime detection will use fallback.")


# =============================================================================
# REGIME DEFINITIONS
# =============================================================================

REGIME_STATES = {
    0: {
        "name": "dispersed",
        "description": "Low herding, idiosyncratic sector moves",
        "color": "#22c55e",  # Green
    },
    1: {
        "name": "normal",
        "description": "Moderate herding, typical market conditions",
        "color": "#3b82f6",  # Blue
    },
    2: {
        "name": "critical",
        "description": "High herding, contagion risk elevated",
        "color": "#ef4444",  # Red
    },
}


# =============================================================================
# HMM REGIME DETECTOR
# =============================================================================

class HerdingHMM:
    """
    Hidden Markov Model for herding regime detection.
    
    Trains on 4 Ising statistics (as percentiles) and classifies
    current market state into one of 3 regimes.
    """
    
    def __init__(self, n_states: int = 3):
        """
        Initialize HMM.
        
        Args:
            n_states: Number of hidden states (default 3)
        """
        self.n_states = n_states
        self.model = None
        self.is_fitted = False
        self.state_mapping = {}  # Maps HMM states to semantic labels
    
    def _prepare_features(
        self,
        ising_stats: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """
        Extract feature matrix from Ising statistics.
        
        Uses percentile histories for training, current percentiles for prediction.
        
        Returns:
            Feature matrix of shape (T, 4) or None if insufficient data
        """
        try:
            # Extract histories
            sus_hist = ising_stats["ising_statistics"]["susceptibility"].get("history", [])
            corr_hist = ising_stats["ising_statistics"]["correlation_length"].get("history", [])
            ar1_hist = ising_stats["ising_statistics"]["critical_slowing_down"].get("history", [])
            mag_hist = ising_stats["ising_statistics"]["magnetization"].get("history", [])
            
            # Get minimum length
            min_len = min(len(sus_hist), len(corr_hist), len(ar1_hist), len(mag_hist))
            
            if min_len < 30:
                logger.warning(f"Insufficient history for HMM: {min_len} points")
                return None
            
            # Align to same length
            sus_hist = sus_hist[-min_len:]
            corr_hist = corr_hist[-min_len:]
            ar1_hist = ar1_hist[-min_len:]
            mag_hist = np.abs(mag_hist[-min_len:])
            
            # Convert to percentiles within their own distributions
            sus_pct = [stats.percentileofscore(sus_hist, v) / 100.0 for v in sus_hist]
            corr_pct = [stats.percentileofscore(corr_hist, v) / 100.0 for v in corr_hist]
            ar1_pct = [stats.percentileofscore(ar1_hist, v) / 100.0 for v in ar1_hist]
            mag_pct = [stats.percentileofscore(mag_hist, v) / 100.0 for v in mag_hist]
            
            # Stack into feature matrix
            X = np.column_stack([sus_pct, corr_pct, ar1_pct, mag_pct])
            
            return X
            
        except Exception as e:
            logger.error(f"Failed to prepare HMM features: {e}")
            return None
    
    def _map_states_to_labels(self) -> Dict[int, str]:
        """
        Map HMM states to semantic labels based on learned means.
        
        States are labeled by sorting their mean observation values:
        - Lowest mean -> dispersed
        - Middle mean -> normal
        - Highest mean -> critical
        """
        if self.model is None or not hasattr(self.model, 'means_'):
            return {i: REGIME_STATES[i]["name"] for i in range(self.n_states)}
        
        # Compute mean of each state's feature means
        # (average across all 4 features)
        state_means = self.model.means_.mean(axis=1)
        
        # Sort states by mean (ascending)
        sorted_indices = np.argsort(state_means)
        
        # Map to labels
        labels = ["dispersed", "normal", "critical"]
        mapping = {}
        for rank, state_idx in enumerate(sorted_indices):
            if rank < len(labels):
                mapping[state_idx] = labels[rank]
            else:
                mapping[state_idx] = f"state_{state_idx}"
        
        return mapping
    
    def fit(self, ising_stats: Dict[str, Any]) -> bool:
        """
        Fit HMM to historical Ising statistics.
        
        Args:
            ising_stats: Output from compute_all_ising_statistics
            
        Returns:
            True if fitting succeeded, False otherwise
        """
        if not HMM_AVAILABLE:
            logger.warning("hmmlearn not available, cannot fit HMM")
            return False
        
        X = self._prepare_features(ising_stats)
        if X is None or len(X) < 50:
            logger.warning("Insufficient data for HMM fitting")
            return False
        
        try:
            # Hold out last observation for unbiased prediction
            X_train = X[:-1]
            
            # Initialize and fit HMM
            # Using spherical covariance (1 variance per state) to reduce overfitting
            # Parameters: 3*4=12 means + 3 variances + 6 transitions = 21 total
            self.model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="spherical",  # Simplest: single variance per state
                n_iter=100,  # Reduced from 200
                random_state=42,
                tol=0.01,
                init_params="stmc",  # Initialize all params
                params="stmc",
            )
            # Add minimum covariance floor to prevent numerical issues
            self.model.min_covar = 1e-2
            
            self.model.fit(X_train)
            self.is_fitted = True
            
            # Map states to semantic labels
            self.state_mapping = self._map_states_to_labels()
            
            logger.info(f"HMM fitted on {len(X_train)} obs (holdout=1 for unbiased prediction)")
            logger.info(f"State mapping: {self.state_mapping}")
            
            return True
            
        except Exception as e:
            logger.error(f"HMM fitting failed: {e}")
            self.is_fitted = False
            return False
    
    def predict(self, ising_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict current regime and state probabilities.
        
        Args:
            ising_stats: Output from compute_all_ising_statistics
            
        Returns:
            Dict with current state, probabilities, and interpretation
        """
        # Fallback if HMM not fitted or unavailable
        if not self.is_fitted or self.model is None:
            return self._fallback_predict(ising_stats)
        
        try:
            X = self._prepare_features(ising_stats)
            if X is None:
                return self._fallback_predict(ising_stats)
            
            # Get state for ONLY the last (held-out) observation
            # This prevents predicting on training data
            X_last = X[-1:].reshape(1, -1)
            
            # Get state sequence for last observation
            states = self.model.predict(X_last)
            current_state = int(states[0])
            
            # Get state probabilities for the last observation only
            log_prob, posteriors = self.model.score_samples(X_last)
            current_probs = posteriors[0]
            
            # Map to semantic labels
            current_label = self.state_mapping.get(current_state, f"state_{current_state}")
            
            prob_dict = {}
            for state_idx, label in self.state_mapping.items():
                prob_dict[label] = float(current_probs[state_idx])
            
            # Get regime info
            regime_info = REGIME_STATES.get(current_state, REGIME_STATES[1])
            
            return {
                "status": "success",
                "method": "hmm",
                "current_state": current_label,
                "current_state_index": current_state,
                "state_probabilities": prob_dict,
                "description": regime_info["description"],
                "color": regime_info["color"],
                "model_info": {
                    "n_states": self.n_states,
                    "n_observations": len(X),
                    "log_likelihood": float(log_prob),
                },
            }
            
        except Exception as e:
            logger.error(f"HMM prediction failed: {e}")
            return self._fallback_predict(ising_stats)
    
    def _fallback_predict(self, ising_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback prediction using herding index thresholds.
        
        Used when HMM is not available or failed.
        """
        try:
            herding_index = ising_stats.get("herding_index", {}).get("value", 0.5)
            
            # Simple threshold-based classification
            if herding_index > 0.65:
                current_state = "critical"
                probs = {"dispersed": 0.1, "normal": 0.25, "critical": 0.65}
            elif herding_index > 0.35:
                current_state = "normal"
                probs = {"dispersed": 0.2, "normal": 0.55, "critical": 0.25}
            else:
                current_state = "dispersed"
                probs = {"dispersed": 0.6, "normal": 0.3, "critical": 0.1}
            
            # Find state index
            state_idx = {"dispersed": 0, "normal": 1, "critical": 2}.get(current_state, 1)
            regime_info = REGIME_STATES.get(state_idx, REGIME_STATES[1])
            
            return {
                "status": "success",
                "method": "fallback_threshold",
                "current_state": current_state,
                "current_state_index": state_idx,
                "state_probabilities": probs,
                "description": regime_info["description"],
                "color": regime_info["color"],
                "model_info": {
                    "n_states": 3,
                    "note": "Using threshold-based fallback (hmmlearn not available or insufficient data)",
                },
            }
            
        except Exception as e:
            logger.error(f"Fallback prediction failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "current_state": "unknown",
                "state_probabilities": {},
            }


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def detect_hmm_regime(
    ising_stats: Dict[str, Any],
    n_states: int = 3
) -> Dict[str, Any]:
    """
    Detect current herding regime using Hidden Markov Model.
    
    Args:
        ising_stats: Output from compute_all_ising_statistics
        n_states: Number of hidden states
        
    Returns:
        Dict with regime classification and probabilities
    """
    if ising_stats.get("status") != "success":
        return {
            "status": "error",
            "error": "Invalid Ising statistics input",
        }
    
    # Initialize and fit HMM
    hmm_model = HerdingHMM(n_states=n_states)
    
    fit_success = hmm_model.fit(ising_stats)
    if not fit_success:
        logger.warning("HMM fit failed, using fallback")
    
    # Predict current regime
    result = hmm_model.predict(ising_stats)
    
    return result

