"""
Aggregation methods for combining factor scores.

Supports multiple methods - from simple equal-weighted to ML-based.
All weights and thresholds configurable.
"""

from typing import Dict, List, Optional, Any, Literal
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

AggregationMethod = Literal[
    "equal_weighted",
    "learned_weights",
    "regime_conditional",
    "ml_predictor"
]

DEFAULT_AGGREGATION_CONFIG = {
    # Default factor weights (used by equal_weighted and as fallback)
    # cross_sectional_zscore: today's flow vs all sectors (relative strength)
    # delta_flow: today's flow vs historical baseline (time-series)
    "default_weights": {
        "delta_flow": 0.25,
        "cross_sectional_zscore": 0.25,  # Key signal: relative to other sectors TODAY
        "otm_conviction": 0.20,
        "vega_flow": 0.15,
        "persistence": 0.10,
        "relative_strength": 0.05,
    },
    
    # Regime-conditional weights
    "regime_weights": {
        "risk_on": {
            "delta_flow": 0.25,
            "cross_sectional_zscore": 0.30,  # Follow momentum in risk-on
            "otm_conviction": 0.20,
            "vega_flow": 0.10,
            "persistence": 0.10,
            "relative_strength": 0.05,
        },
        "risk_off": {
            "delta_flow": 0.15,
            "cross_sectional_zscore": 0.20,
            "otm_conviction": 0.15,
            "vega_flow": 0.15,  # Vol more important in risk-off
            "persistence": 0.20,  # Trend persistence matters
            "relative_strength": 0.15,
        },
        "transition": {
            "delta_flow": 0.20,
            "cross_sectional_zscore": 0.25,
            "otm_conviction": 0.20,
            "vega_flow": 0.15,
            "persistence": 0.10,
            "relative_strength": 0.10,
        },
    },
    
    # Learned weights config
    "learned_weights_regularization": 1.0,
    "learned_weights_min_samples": 50,
}


# =============================================================================
# AGGREGATOR CLASS
# =============================================================================

class FactorAggregator:
    """
    Aggregates multiple factor scores into a composite score.
    
    Methods:
    - equal_weighted: Simple average of all factors
    - learned_weights: Ridge regression on historical data
    - regime_conditional: Different weights per market regime
    - ml_predictor: Use ML model to predict returns directly
    """
    
    def __init__(
        self,
        method: AggregationMethod = "equal_weighted",
        config: Optional[Dict] = None,
        custom_weights: Optional[Dict[str, float]] = None
    ):
        self.method = method
        self.config = {**DEFAULT_AGGREGATION_CONFIG, **(config or {})}
        self.custom_weights = custom_weights
        self._learned_model = None
        self._ml_model = None
    
    def aggregate(
        self,
        factors: Dict[str, float],
        regime: Optional[str] = None,
        historical_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Aggregate factor scores into composite.
        
        Args:
            factors: Dict of factor_name -> score
            regime: Market regime (for regime_conditional method)
            historical_data: For learned_weights/ml_predictor training
        
        Returns:
            Dict with composite_score, method_used, weights_applied
        """
        if self.method == "equal_weighted":
            return self._aggregate_equal(factors)
        elif self.method == "learned_weights":
            return self._aggregate_learned(factors, historical_data)
        elif self.method == "regime_conditional":
            return self._aggregate_regime(factors, regime)
        elif self.method == "ml_predictor":
            return self._aggregate_ml(factors, historical_data)
        else:
            logger.warning(f"Unknown method {self.method}, using equal_weighted")
            return self._aggregate_equal(factors)
    
    def _aggregate_equal(self, factors: Dict[str, float]) -> Dict[str, Any]:
        """Simple equal-weighted average."""
        if self.custom_weights:
            weights = self.custom_weights
        else:
            weights = self.config.get("default_weights", {})
        
        # Filter to factors we have
        available = {k: v for k, v in factors.items() if v is not None}
        
        if not available:
            return {"composite_score": None, "error": "No valid factors"}
        
        # If custom weights provided, use them; otherwise equal weight
        if weights:
            total_weight = sum(weights.get(k, 0) for k in available)
            if total_weight > 0:
                score = sum(v * weights.get(k, 0) for k, v in available.items()) / total_weight
            else:
                score = sum(available.values()) / len(available)
            weights_used = {k: weights.get(k, 0) for k in available}
        else:
            score = sum(available.values()) / len(available)
            weights_used = {k: 1.0 / len(available) for k in available}
        
        return {
            "composite_score": round(score, 4),
            "method": "equal_weighted",
            "weights_applied": weights_used,
            "factors_used": list(available.keys())
        }
    
    def _aggregate_learned(
        self,
        factors: Dict[str, float],
        historical_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Use learned weights from Ridge regression.
        
        Falls back to equal_weighted if no model trained.
        """
        if self._learned_model is None:
            if historical_data:
                self._train_learned_model(historical_data)
            else:
                logger.info("No learned model, falling back to equal_weighted")
                return self._aggregate_equal(factors)
        
        if self._learned_model is None:
            return self._aggregate_equal(factors)
        
        # Apply learned weights
        available = {k: v for k, v in factors.items() if v is not None}
        weights = self._learned_model.get("weights", {})
        
        total_weight = sum(abs(weights.get(k, 0)) for k in available)
        if total_weight > 0:
            score = sum(v * weights.get(k, 0) for k, v in available.items())
        else:
            return self._aggregate_equal(factors)
        
        return {
            "composite_score": round(score, 4),
            "method": "learned_weights",
            "weights_applied": {k: weights.get(k, 0) for k in available},
            "factors_used": list(available.keys()),
            "model_r2": self._learned_model.get("r2_score")
        }
    
    def _train_learned_model(self, historical_data: Dict):
        """Train Ridge regression model on historical factor -> return data."""
        try:
            from sklearn.linear_model import Ridge
            import numpy as np
            
            X = historical_data.get("factors")  # List of factor dicts
            y = historical_data.get("returns")  # List of forward returns
            
            if not X or not y or len(X) < self.config.get("learned_weights_min_samples", 50):
                logger.warning("Insufficient data for learned weights")
                return
            
            # Convert to arrays
            factor_names = list(X[0].keys())
            X_arr = np.array([[row.get(f, 0) for f in factor_names] for row in X])
            y_arr = np.array(y)
            
            # Train
            alpha = self.config.get("learned_weights_regularization", 1.0)
            model = Ridge(alpha=alpha)
            model.fit(X_arr, y_arr)
            
            self._learned_model = {
                "weights": dict(zip(factor_names, model.coef_)),
                "intercept": model.intercept_,
                "r2_score": model.score(X_arr, y_arr)
            }
            
            logger.info(f"Trained learned weights model, R2={self._learned_model['r2_score']:.3f}")
            
        except ImportError:
            logger.warning("sklearn not available for learned weights")
        except Exception as e:
            logger.warning(f"Failed to train learned model: {e}")
    
    def _aggregate_regime(
        self,
        factors: Dict[str, float],
        regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use regime-conditional weights."""
        if not regime:
            regime = "transition"  # Default if unknown
        
        regime_weights = self.config.get("regime_weights", {})
        weights = regime_weights.get(regime, regime_weights.get("transition", {}))
        
        if not weights:
            return self._aggregate_equal(factors)
        
        available = {k: v for k, v in factors.items() if v is not None}
        
        total_weight = sum(weights.get(k, 0) for k in available)
        if total_weight > 0:
            score = sum(v * weights.get(k, 0) for k, v in available.items()) / total_weight
        else:
            return self._aggregate_equal(factors)
        
        return {
            "composite_score": round(score, 4),
            "method": "regime_conditional",
            "regime": regime,
            "weights_applied": {k: weights.get(k, 0) for k in available},
            "factors_used": list(available.keys())
        }
    
    def _aggregate_ml(
        self,
        factors: Dict[str, float],
        historical_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Use ML model to predict returns directly.
        
        This bypasses factor weighting and directly predicts.
        Requires ensemble model to be trained.
        """
        if self._ml_model is None:
            if historical_data:
                self._train_ml_model(historical_data)
            else:
                logger.info("No ML model, falling back to equal_weighted")
                return self._aggregate_equal(factors)
        
        if self._ml_model is None:
            return self._aggregate_equal(factors)
        
        try:
            import numpy as np
            
            available = {k: v for k, v in factors.items() if v is not None}
            feature_order = self._ml_model.get("feature_order", [])
            
            X = np.array([[available.get(f, 0) for f in feature_order]])
            prediction = self._ml_model["model"].predict(X)[0]
            
            return {
                "composite_score": round(float(prediction), 4),
                "method": "ml_predictor",
                "model_type": self._ml_model.get("model_type"),
                "factors_used": list(available.keys())
            }
            
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._aggregate_equal(factors)
    
    def _train_ml_model(self, historical_data: Dict):
        """Train ML model for direct return prediction."""
        try:
            from sklearn.ensemble import GradientBoostingRegressor
            import numpy as np
            
            X = historical_data.get("factors")
            y = historical_data.get("returns")
            
            if not X or not y or len(X) < 50:
                logger.warning("Insufficient data for ML model")
                return
            
            factor_names = list(X[0].keys())
            X_arr = np.array([[row.get(f, 0) for f in factor_names] for row in X])
            y_arr = np.array(y)
            
            model = GradientBoostingRegressor(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                random_state=42
            )
            model.fit(X_arr, y_arr)
            
            self._ml_model = {
                "model": model,
                "model_type": "GradientBoostingRegressor",
                "feature_order": factor_names,
                "r2_score": model.score(X_arr, y_arr)
            }
            
            logger.info(f"Trained ML predictor, R2={self._ml_model['r2_score']:.3f}")
            
        except ImportError:
            logger.warning("sklearn not available for ML predictor")
        except Exception as e:
            logger.warning(f"Failed to train ML model: {e}")
