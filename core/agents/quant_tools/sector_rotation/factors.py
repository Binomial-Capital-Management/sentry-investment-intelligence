"""
Factor computation for sector rotation analysis.

Each factor is computed independently and returns a z-score.
NO HARDCODED THRESHOLDS - all configurable via config dict.
"""

from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION (All thresholds here, not scattered in code)
# =============================================================================

DEFAULT_FACTOR_CONFIG = {
    # Data requirements
    "zscore_min_history": 5,
    "persistence_window": 10,
    "vega_momentum_window": 5,
    
    # Z-score thresholds for signals
    "zscore_strong_threshold": 2.0,
    "zscore_moderate_threshold": 1.0,
    
    # Momentum thresholds
    "momentum_threshold": 0.5,
    
    # OTM conviction thresholds
    "otm_bullish_threshold": 0.65,
    "otm_bearish_threshold": 0.35,
    
    # Persistence thresholds
    "persistence_strong_days": 5,
    
    # Relative strength thresholds
    "relative_strength_threshold": 0.5,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_zscore(
    current: float,
    history: List[float],
    min_history: int = 5
) -> Optional[float]:
    """
    Compute z-score of current value vs history.
    
    Returns None if insufficient history.
    """
    if not history or len(history) < min_history:
        return None
    
    mean_val = sum(history) / len(history)
    variance = sum((x - mean_val) ** 2 for x in history) / len(history)
    std_val = variance ** 0.5
    
    if std_val < 1e-9:
        return 0.0
    
    return (current - mean_val) / std_val


def compute_momentum(
    values: List[float],
    window: int = 5
) -> Optional[float]:
    """
    Compute momentum as change over window normalized by average.
    """
    if not values or len(values) < window + 1:
        return None
    
    current = values[-1]
    past = values[-(window + 1)]
    avg = sum(abs(v) for v in values) / len(values)
    
    if avg < 1e-9:
        return 0.0
    
    return (current - past) / avg


def interpret_zscore(zscore: float, config: Dict) -> str:
    """
    Interpret z-score as signal using config thresholds.
    """
    strong = config.get("zscore_strong_threshold", 2.0)
    moderate = config.get("zscore_moderate_threshold", 1.0)
    
    if zscore > strong:
        return "STRONG_BULLISH"
    elif zscore > moderate:
        return "BULLISH"
    elif zscore < -strong:
        return "STRONG_BEARISH"
    elif zscore < -moderate:
        return "BEARISH"
    return "NEUTRAL"


# =============================================================================
# FACTOR CLASSES
# =============================================================================

class DeltaFlowFactor:
    """
    Primary factor: Net delta flow z-score.
    
    Positive delta = bullish positioning.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_FACTOR_CONFIG, **(config or {})}
    
    def compute(
        self,
        current_flow: float,
        historical_flows: List[float]
    ) -> Dict[str, Any]:
        """
        Compute delta flow z-score.
        """
        zscore = compute_zscore(
            current_flow,
            historical_flows,
            self.config.get("zscore_min_history", 5)
        )
        
        if zscore is None:
            return {"value": None, "error": "Insufficient history"}
        
        return {
            "value": round(zscore, 4),
            "current": current_flow,
            "historical_mean": sum(historical_flows) / len(historical_flows),
            "signal": interpret_zscore(zscore, self.config)
        }


class VegaFlowFactor:
    """
    Vega flow momentum - are traders adding/reducing vol exposure?
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_FACTOR_CONFIG, **(config or {})}
    
    def compute(
        self,
        vega_history: List[float]
    ) -> Dict[str, Any]:
        """
        Compute vega momentum.
        """
        window = self.config.get("vega_momentum_window", 5)
        momentum = compute_momentum(vega_history, window)
        
        if momentum is None:
            return {"value": None, "error": "Insufficient history"}
        
        threshold = self.config.get("momentum_threshold", 0.5)
        
        if momentum > threshold:
            signal = "ADDING_VOL"
        elif momentum < -threshold:
            signal = "REDUCING_VOL"
        else:
            signal = "STABLE"
        
        return {
            "value": round(momentum, 4),
            "window": window,
            "signal": signal
        }


class OTMConvictionFactor:
    """
    OTM call/put ratio - speculative conviction.
    
    High OTM call ratio = speculative bullishness.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_FACTOR_CONFIG, **(config or {})}
    
    def compute(
        self,
        otm_call_premium: float,
        otm_put_premium: float
    ) -> Dict[str, Any]:
        """
        Compute OTM conviction ratio.
        """
        total = abs(otm_call_premium) + abs(otm_put_premium)
        
        if total < 1e-9:
            return {"value": 0.5, "error": "No OTM premium"}
        
        ratio = abs(otm_call_premium) / total
        
        bullish_thresh = self.config.get("otm_bullish_threshold", 0.65)
        bearish_thresh = self.config.get("otm_bearish_threshold", 0.35)
        
        if ratio > bullish_thresh:
            signal = "SPECULATIVE_BULLISH"
        elif ratio < bearish_thresh:
            signal = "SPECULATIVE_BEARISH"
        else:
            signal = "BALANCED"
        
        return {
            "value": round(ratio, 4),
            "call_premium": otm_call_premium,
            "put_premium": otm_put_premium,
            "signal": signal
        }


class PersistenceFactor:
    """
    Flow persistence - consistent direction is stronger signal.
    
    Counts consecutive days of same-direction flow.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_FACTOR_CONFIG, **(config or {})}
    
    def compute(
        self,
        flow_history: List[float]
    ) -> Dict[str, Any]:
        """
        Compute persistence score.
        """
        window = self.config.get("persistence_window", 10)
        
        if not flow_history or len(flow_history) < 2:
            return {"value": None, "error": "Insufficient history"}
        
        recent = flow_history[-window:] if len(flow_history) >= window else flow_history
        
        if not recent:
            return {"value": 0, "consecutive_days": 0}
        
        current_sign = 1 if recent[-1] > 0 else -1
        consecutive = 0
        
        for val in reversed(recent):
            val_sign = 1 if val > 0 else -1
            if val_sign == current_sign:
                consecutive += 1
            else:
                break
        
        normalized = min(consecutive / window, 1.0)
        
        strong_days = self.config.get("persistence_strong_days", 5)
        signal = "PERSISTENT" if consecutive >= strong_days else "CHOPPY"
        
        return {
            "value": round(normalized, 4),
            "consecutive_days": consecutive,
            "direction": "BULLISH" if current_sign > 0 else "BEARISH",
            "signal": signal
        }


class RelativeStrengthFactor:
    """
    Cross-sector relative strength.
    
    Compares sector's flow vs market aggregate.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_FACTOR_CONFIG, **(config or {})}
    
    def compute(
        self,
        sector_zscore: float,
        market_zscore: float
    ) -> Dict[str, Any]:
        """
        Compute relative strength.
        """
        relative = sector_zscore - market_zscore
        
        threshold = self.config.get("relative_strength_threshold", 0.5)
        
        if relative > threshold:
            signal = "OUTPERFORMING"
        elif relative < -threshold:
            signal = "UNDERPERFORMING"
        else:
            signal = "INLINE"
        
        return {
            "value": round(relative, 4),
            "sector_zscore": sector_zscore,
            "market_zscore": market_zscore,
            "signal": signal
        }


# =============================================================================
# FACTOR REGISTRY
# =============================================================================

FACTOR_REGISTRY = {
    "delta_flow": DeltaFlowFactor,
    "vega_flow": VegaFlowFactor,
    "otm_conviction": OTMConvictionFactor,
    "persistence": PersistenceFactor,
    "relative_strength": RelativeStrengthFactor,
}


def get_factor(name: str, config: Optional[Dict] = None):
    """Get factor instance by name."""
    if name not in FACTOR_REGISTRY:
        raise ValueError(f"Unknown factor: {name}")
    return FACTOR_REGISTRY[name](config)
