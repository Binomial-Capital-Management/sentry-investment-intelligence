"""
Recession Field Theory - Hidden Markov Model Regime Detection

Uses a 3-state Gaussian HMM aligned with NBER business cycle phases:
- State 0: Expansion (positive field, stable growth)
- State 1: Transition/Peak-Trough (neutral field, high uncertainty)
- State 2: Recession (negative field, contraction)

The HMM learns:
- Transition probabilities between states
- Emission distributions (what φ looks like in each state)
- Most likely state sequence (Viterbi)
- Current state probabilities (forward algorithm)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List, Any
from scipy.special import softmax

logger = logging.getLogger(__name__)

# Try to import hmmlearn
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logger.warning("[HMM] hmmlearn not installed.")


# =============================================================================
# BUSINESS CYCLE PHASES (NBER Standard)
# =============================================================================
#
# The business cycle has 4 distinct phases:
#
#        Peak
#         /\
#        /  \
#   Expansion  Contraction
#      /        \
#     /          \
#  Trough -----> Recovery
#
# =============================================================================

REGIME_STATES = {
    0: {
        "name": "expansion",
        "description": "Economic growth - rising GDP, employment, production",
        "typical_field_range": (0.3, 1.5),
        "color": "#16a34a"  # Green
    },
    1: {
        "name": "peak",
        "description": "Cycle maximum - economy at full capacity, turning point ahead",
        "typical_field_range": (0.8, 1.2),
        "color": "#0ea5e9"  # Blue
    },
    2: {
        "name": "contraction",
        "description": "Economic decline - falling GDP, rising unemployment",
        "typical_field_range": (-1.0, -0.2),
        "color": "#f59e0b"  # Amber
    },
    3: {
        "name": "trough",
        "description": "Cycle minimum - economy bottoming out, recovery ahead",
        "typical_field_range": (-1.5, -0.8),
        "color": "#dc2626"  # Red
    }
}


# =============================================================================
# GAUSSIAN HMM IMPLEMENTATION (BUSINESS CYCLE ALIGNED)
# =============================================================================

class RecessionHMM:
    """
    Hidden Markov Model for business cycle phase detection.
    
    4 States aligned to NBER business cycle:
    - Expansion: Growing economy (φ > 0.3)
    - Peak: Maximum before decline (φ ~ 0.8-1.2)  
    - Contraction: Declining economy (φ < 0)
    - Trough: Minimum before recovery (φ << 0)
    """
    
    def __init__(
        self,
        n_states: int = 4,
        n_iter: int = 200,
        random_state: int = 42
    ):
        """
        Initialize the HMM with 4 business cycle states.
        
        Args:
            n_states: Number of hidden states (default: 4)
            n_iter: Maximum iterations for EM algorithm
            random_state: Random seed for reproducibility
        """
        self.n_states = n_states
        self.n_iter = n_iter
        self.random_state = random_state
        
        self.model = None
        self.is_fitted = False
        
        # Default 1:1 mapping (will be updated after fitting)
        self.state_mapping = {i: i for i in range(n_states)}
        self.reverse_mapping = {i: i for i in range(n_states)}
        
        # Business cycle state priors (field values)
        # State 0: Expansion  (moderate positive)
        # State 1: Peak       (high positive)
        # State 2: Contraction (negative)
        # State 3: Trough     (strongly negative)
        self.prior_means = np.array([[0.5], [1.0], [-0.4], [-1.0]])
        
        # Wider variances to avoid extreme probabilities
        self.prior_vars = np.array([[[0.5]], [[0.4]], [[0.5]], [[0.4]]])
        
        # Business cycle transition matrix
        # Cycle: Expansion → Peak → Contraction → Trough → Expansion
        #                    Expansion  Peak   Contract  Trough
        self.prior_transmat = np.array([
            [0.92, 0.08, 0.00, 0.00],  # Expansion: stays or → Peak
            [0.10, 0.70, 0.20, 0.00],  # Peak: can stay, back to expansion, or → Contraction
            [0.00, 0.00, 0.80, 0.20],  # Contraction: stays or → Trough
            [0.30, 0.00, 0.00, 0.70],  # Trough: stays or → Expansion (recovery)
        ])
    
    def fit(
        self,
        field: pd.Series,
        use_priors: bool = True
    ) -> bool:
        """
        Fit the HMM to historical economic field data.
        
        Args:
            field: Economic field series φ(t)
            use_priors: Initialize with business cycle priors
        
        Returns:
            True if fitting succeeded
        """
        if not HMM_AVAILABLE:
            logger.warning("[HMM] hmmlearn not available")
            return False
        
        # Prepare data
        data = field.dropna().values.reshape(-1, 1)
        
        if len(data) < 30:
            logger.warning(f"[HMM] Insufficient data for training: {len(data)} points")
            return False
        
        try:
            # Initialize model - set init_params='' to use our priors without warning
            self.model = GaussianHMM(
                n_components=self.n_states,
                covariance_type="full",
                n_iter=self.n_iter,
                random_state=self.random_state,
                init_params='',      # Don't auto-init (we provide values)
                params='stmc',       # But still train all parameters
                tol=0.01,            # Convergence tolerance
                verbose=False
            )
            
            # Set business cycle aligned initial parameters
            # State 0=Expansion, 1=Peak, 2=Contraction, 3=Trough
            self.model.startprob_ = np.array([0.60, 0.20, 0.15, 0.05])
            self.model.transmat_ = self.prior_transmat.copy()
            self.model.means_ = self.prior_means.copy()
            self.model.covars_ = self.prior_vars.copy()
            
            # Fit model to data
            self.model.fit(data)
            
            # After fitting, re-map states based on learned means
            # This ensures semantic alignment even if EM swapped states
            self._map_states_to_labels()
            
            self.is_fitted = True
            
            means = self.model.means_.flatten()
            
            # Get means by semantic state
            mean_by_phase = {}
            for hmm_idx, semantic_idx in self.state_mapping.items():
                if semantic_idx < len(REGIME_STATES):
                    phase_name = REGIME_STATES[semantic_idx]["name"]
                    mean_by_phase[phase_name] = means[hmm_idx]
            
            logger.info(
                f"[HMM] Fitted on {len(data)} points. "
                f"Learned means: {', '.join(f'{k}={v:.2f}' for k, v in mean_by_phase.items())}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[HMM] Fitting failed: {e}")
            return False
    
    def _map_states_to_labels(self):
        """
        Map HMM state indices to semantic business cycle phases based on learned means.
        
        Business cycle order by field value (high to low):
        - Peak (highest positive) → semantic 1
        - Expansion (moderate positive) → semantic 0
        - Contraction (negative) → semantic 2
        - Trough (most negative) → semantic 3
        
        Creates BOTH directions:
        - state_mapping: hmm_idx → semantic_idx
        - reverse_mapping: semantic_idx → hmm_idx
        """
        if self.model is None:
            self.state_mapping = {i: i for i in range(self.n_states)}
            self.reverse_mapping = {i: i for i in range(self.n_states)}
            return
        
        means = self.model.means_.flatten()
        sorted_indices = np.argsort(means)  # ascending order (lowest first)
        
        # Map based on mean ordering:
        # sorted_indices[0] = lowest mean → trough (semantic 3)
        # sorted_indices[1] = second lowest → contraction (semantic 2)
        # sorted_indices[2] = second highest → expansion (semantic 0)
        # sorted_indices[3] = highest mean → peak (semantic 1)
        
        if self.n_states == 4:
            self.state_mapping = {
                int(sorted_indices[3]): 1,  # Highest → Peak
                int(sorted_indices[2]): 0,  # Second highest → Expansion
                int(sorted_indices[1]): 2,  # Second lowest → Contraction
                int(sorted_indices[0]): 3,  # Lowest → Trough
            }
        else:
            # Fallback for other state counts
            self.state_mapping = {i: i for i in range(self.n_states)}
        
        # Reverse mapping: semantic → hmm
        self.reverse_mapping = {v: k for k, v in self.state_mapping.items()}
    
    def predict_regime(
        self,
        field: pd.Series
    ) -> Dict[str, Any]:
        """
        Predict current regime and state probabilities.
        
        Uses the forward algorithm to get smooth posterior probabilities
        over the business cycle states.
        
        Args:
            field: Economic field series (uses most recent values)
        
        Returns:
            Dict with regime prediction and probabilities
        """
        if not self.is_fitted or not HMM_AVAILABLE or self.model is None:
            return self._threshold_predict(field)
        
        # Prepare data
        data = field.dropna().values.reshape(-1, 1)
        
        if len(data) < 5:
            return self._threshold_predict(field)
        
        try:
            # Get state probabilities using forward algorithm
            _, posteriors = self.model.score_samples(data)
            
            # Get probabilities for most recent observation
            raw_probs = posteriors[-1]
            
            # Map HMM state probs to semantic business cycle phases
            # These are the RAW posterior probabilities from the forward algorithm
            mapped_probs = {
                "expansion": 0.0,
                "peak": 0.0,
                "contraction": 0.0,
                "trough": 0.0
            }
            
            for hmm_state in range(self.n_states):
                semantic_state = self.state_mapping.get(hmm_state, 0)
                if semantic_state < len(REGIME_STATES):
                    state_name = REGIME_STATES[semantic_state]["name"]
                    mapped_probs[state_name] += float(raw_probs[hmm_state])
            
            # Probabilities come directly from HMM forward algorithm
            
            # Determine most likely regime
            most_likely_name = max(mapped_probs, key=mapped_probs.get)
            
            # Get Viterbi path for duration analysis
            viterbi_path = self.model.predict(data)
            
            # Convert Viterbi path to semantic states
            semantic_path = [self.state_mapping.get(s, 0) for s in viterbi_path]
            
            # Count recent regime history (last 12 months)
            recent_path = semantic_path[-12:] if len(semantic_path) >= 12 else semantic_path
            regime_counts = {"expansion": 0, "peak": 0, "contraction": 0, "trough": 0}
            for semantic_state in recent_path:
                if semantic_state < len(REGIME_STATES):
                    name = REGIME_STATES[semantic_state]["name"]
                    regime_counts[name] += 1
            
            # Estimate current regime duration
            current_semantic = semantic_path[-1] if semantic_path else 1
            duration = 1
            for i in range(len(semantic_path) - 2, -1, -1):
                if semantic_path[i] == current_semantic:
                    duration += 1
                else:
                    break
            
            # Get learned state distributions for reporting
            learned_means = {}
            for hmm_state in range(self.n_states):
                semantic = self.state_mapping.get(hmm_state, 1)
                name = REGIME_STATES[semantic]["name"]
                learned_means[name] = float(self.model.means_[hmm_state, 0])
            
            return {
                "current_regime": most_likely_name,
                "regime_probabilities": mapped_probs,
                "confidence": float(mapped_probs[most_likely_name]),
                "regime_duration_months": duration,
                "recent_regime_distribution": regime_counts,
                "learned_state_means": learned_means,
                "model_info": {
                    "n_states": self.n_states,
                    "method": "gaussian_hmm",
                    "is_fitted": True
                }
            }
            
        except Exception as e:
            logger.error(f"[HMM] Prediction failed: {e}")
            return self._threshold_predict(field)
    
    def _threshold_predict(
        self,
        field: pd.Series
    ) -> Dict[str, Any]:
        """
        Business cycle phase classification using softmax on field distance to state means.
        
        Uses soft boundaries for graduated probabilities aligned with
        the 4-phase business cycle.
        """
        default_probs = {"expansion": 0.25, "peak": 0.25, "contraction": 0.25, "trough": 0.25}
        
        if field is None or field.empty:
            return {
                "current_regime": "expansion",
                "regime_probabilities": default_probs,
                "confidence": 0.25,
                "model_info": {"is_fitted": False, "method": "threshold"}
            }
        
        # Get recent values for smoothing
        recent = field.dropna().tail(6)
        if len(recent) == 0:
            return {
                "current_regime": "expansion",
                "regime_probabilities": default_probs,
                "confidence": 0.25,
                "model_info": {"is_fitted": False, "method": "threshold"}
            }
        
        current_value = float(recent.iloc[-1])
        recent_mean = float(recent.mean())
        
        # Business cycle state centers (same as HMM priors)
        state_means = {
            "expansion": 0.5,
            "peak": 1.0,
            "contraction": -0.4,
            "trough": -1.0
        }
        
        # Calculate negative squared distances (for softmax)
        # Temperature controls sharpness - higher = softer boundaries
        temperature = 0.6  # Higher = more spread out probabilities
        neg_distances = {}
        for state, mean in state_means.items():
            distance = (recent_mean - mean) ** 2
            neg_distances[state] = -distance / temperature
        
        # Softmax to get probabilities (natural soft boundaries)
        values = np.array([neg_distances["expansion"], neg_distances["peak"], 
                          neg_distances["contraction"], neg_distances["trough"]])
        probs_array = softmax(values)
        
        probs = {
            "expansion": float(probs_array[0]),
            "peak": float(probs_array[1]),
            "contraction": float(probs_array[2]),
            "trough": float(probs_array[3])
        }
        
        regime = max(probs, key=probs.get)
        
        return {
            "current_regime": regime,
            "regime_probabilities": probs,
            "confidence": float(probs[regime]),
            "current_field_value": current_value,
            "recent_field_mean": recent_mean,
            "model_info": {"is_fitted": False, "method": "softmax_threshold"}
        }
    
    def get_transition_matrix(self) -> Optional[np.ndarray]:
        """Get the learned transition probability matrix."""
        if self.model is None:
            return None
        
        return self.model.transmat_
    
    def get_state_distributions(self) -> Dict[str, Dict[str, float]]:
        """Get the learned emission distributions for each business cycle phase."""
        if self.model is None:
            return {}
        
        distributions = {}
        for hmm_state, semantic_state in self.state_mapping.items():
            if semantic_state < len(REGIME_STATES):
                state_name = REGIME_STATES[semantic_state]["name"]
                distributions[state_name] = {
                    "mean": float(self.model.means_[hmm_state, 0]),
                    "variance": float(self.model.covars_[hmm_state, 0, 0])
                }
        
        return distributions


# =============================================================================
# REGIME ANALYSIS UTILITIES
# =============================================================================

def estimate_regime_duration(
    regime_probs: Dict[str, float],
    transition_matrix: Optional[np.ndarray] = None
) -> str:
    """
    Estimate expected duration in current business cycle phase.
    
    Based on historical NBER data:
    - Expansions: ~58 months average
    - Peaks: 1-3 months (turning point)
    - Contractions: ~11 months average
    - Troughs: 1-3 months (turning point)
    """
    current_regime = max(regime_probs, key=regime_probs.get)
    prob = regime_probs[current_regime]
    
    durations = {
        "expansion": "6-12+ months (expansions are longest phase)",
        "peak": "1-3 months (turning point, watch for decline)",
        "contraction": "3-6 months (recessions avg 11 months total)",
        "trough": "1-3 months (turning point, watch for recovery)"
    }
    
    if prob > 0.6:
        return durations.get(current_regime, "uncertain")
    else:
        return f"uncertain - {current_regime} most likely but low confidence"


def get_regime_interpretation(
    regime: str,
    probabilities: Dict[str, float],
    physics_signals: Dict[str, str]
) -> str:
    """
    Generate natural language interpretation for business cycle phase.
    """
    # Count elevated physics signals
    n_elevated = sum(1 for s in physics_signals.values() if s in ["ELEVATED", "CRITICAL"])
    n_critical = sum(1 for s in physics_signals.values() if s == "CRITICAL")
    
    if regime == "trough":
        return (
            "Economy at cycle trough - lowest point of contraction. "
            "Watch for signs of recovery and expansion ahead."
        )
    
    elif regime == "contraction":
        if n_critical > 0:
            return (
                "Economy in contraction with critical warning signals. "
                "May be heading toward trough. Historical contractions last ~11 months."
            )
        else:
            return (
                "Economy contracting - declining GDP and rising unemployment. "
                "Monitor for signs of stabilization or further deterioration."
            )
    
    elif regime == "peak":
        if n_elevated >= 2:
            return (
                "Economy at cycle peak with elevated warning signals. "
                "High risk of contraction beginning. Consider defensive positioning."
            )
        else:
            return (
                "Economy at or near cycle peak - maximum expansion reached. "
                "Watch for early signs of slowdown."
            )
    
    else:  # expansion
        if n_elevated >= 2:
            return (
                "Economy expanding but warning signals suggest late-cycle. "
                "May be approaching peak. Monitor for deterioration."
            )
        else:
            return (
                "Economy in expansion phase with healthy indicators. "
                "Continued growth expected in near term."
            )


# =============================================================================
# MAIN ANALYZER CLASS
# =============================================================================

class RegimeAnalyzer:
    """
    Combines HMM business cycle detection with physics-based signals.
    """
    
    def __init__(
        self,
        n_states: int = 4,
        fit_on_init: bool = True
    ):
        """
        Initialize the regime analyzer with 4 business cycle states.
        
        Args:
            n_states: Number of HMM states (default: 4)
            fit_on_init: Whether to fit model when data is provided
        """
        self.hmm = RecessionHMM(n_states=n_states)
        self.fit_on_init = fit_on_init
        self.last_result = None
    
    def analyze(
        self,
        field: pd.Series,
        physics_signals: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Perform business cycle phase analysis.
        
        Args:
            field: Economic field series
            physics_signals: Dict of signal classifications from physics stats
        
        Returns:
            Complete regime analysis result with 4 phases
        """
        # Fit HMM if needed
        if not self.hmm.is_fitted and self.fit_on_init:
            self.hmm.fit(field)
        
        # Get HMM prediction
        hmm_result = self.hmm.predict_regime(field)
        
        # Combine with physics signals
        if physics_signals is None:
            physics_signals = {}
        
        # Generate interpretation
        interpretation = get_regime_interpretation(
            hmm_result["current_regime"],
            hmm_result["regime_probabilities"],
            physics_signals
        )
        
        # Estimate duration
        duration_estimate = estimate_regime_duration(
            hmm_result["regime_probabilities"],
            self.hmm.get_transition_matrix()
        )
        
        # Map regime name to state index for state_info lookup
        regime_to_idx = {"expansion": 0, "peak": 1, "contraction": 2, "trough": 3}
        current_idx = regime_to_idx.get(hmm_result["current_regime"], 0)
        
        result = {
            "method": "hidden_markov_model",
            "n_states": 4,
            "business_cycle_phases": ["expansion", "peak", "contraction", "trough"],
            "current_regime": hmm_result["current_regime"],
            "regime_probabilities": hmm_result["regime_probabilities"],
            "confidence": hmm_result["confidence"],
            "regime_duration_estimate": duration_estimate,
            "interpretation": interpretation,
            "state_info": REGIME_STATES.get(current_idx, REGIME_STATES[0]),
            "model_details": hmm_result.get("model_info", {}),
            "hmm_available": HMM_AVAILABLE
        }
        
        # Add recent regime distribution if available
        if "recent_regime_distribution" in hmm_result:
            result["recent_regime_distribution"] = hmm_result["recent_regime_distribution"]
        
        # Add learned state means if available
        if "learned_state_means" in hmm_result:
            result["learned_state_means"] = hmm_result["learned_state_means"]
        
        # Add state distributions if available
        if self.hmm.is_fitted and HMM_AVAILABLE and self.hmm.model is not None:
            result["state_distributions"] = self.hmm.get_state_distributions()
        
        self.last_result = result
        return result

