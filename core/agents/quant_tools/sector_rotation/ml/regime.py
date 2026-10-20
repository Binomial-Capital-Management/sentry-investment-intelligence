"""
Market regime classifier using HMM or Random Forest.

Classifies market into: risk_on, risk_off, transition
All thresholds configurable.
"""

from typing import Dict, List, Optional, Any, Literal
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_REGIME_CONFIG = {
    # Model selection
    "model_type": "rf",  # "hmm" or "rf"
    "n_states": 3,
    
    # RF parameters
    "rf_n_estimators": 100,
    "rf_max_depth": 4,
    "rf_min_samples_leaf": 5,
    
    # HMM parameters
    "hmm_covariance_type": "diag",
    "hmm_n_iter": 100,
    
    # Feature thresholds for rule-based fallback
    "vix_high_threshold": 25.0,
    "vix_low_threshold": 18.0,
    "correlation_high_threshold": 0.70,
    "correlation_low_threshold": 0.40,
}

# Regime labels
REGIME_LABELS = ["risk_on", "transition", "risk_off"]


# =============================================================================
# REGIME CLASSIFIER
# =============================================================================

class RegimeClassifier:
    """
    Classifies market regime from observable features.
    
    Features used:
    - VIX level
    - VIX term structure (contango/backwardation)
    - Average sector correlation
    - Realized volatility
    
    Can use HMM (unsupervised) or RF (supervised with labels).
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_REGIME_CONFIG, **(config or {})}
        self.model = None
        self._fitted = False
        self._feature_names = []
    
    def fit(
        self,
        features: pd.DataFrame,
        labels: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Fit regime classifier.
        
        Args:
            features: DataFrame with columns for each feature
            labels: Optional regime labels (required for RF)
        
        Returns:
            Dict with training info
        """
        model_type = self.config.get("model_type", "rf")
        self._feature_names = list(features.columns)
        
        if model_type == "hmm":
            return self._fit_hmm(features)
        else:
            return self._fit_rf(features, labels)
    
    def _fit_hmm(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Fit Hidden Markov Model (unsupervised)."""
        try:
            from hmmlearn import hmm
            
            n_states = self.config.get("n_states", 3)
            
            self.model = hmm.GaussianHMM(
                n_components=n_states,
                covariance_type=self.config.get("hmm_covariance_type", "diag"),
                n_iter=self.config.get("hmm_n_iter", 100),
                random_state=42
            )
            
            X = features.values
            self.model.fit(X)
            self._fitted = True
            
            return {
                "status": "success",
                "model_type": "hmm",
                "n_states": n_states,
                "n_samples": len(features)
            }
            
        except ImportError:
            logger.warning("hmmlearn not installed, falling back to rule-based")
            return {"status": "fallback", "reason": "hmmlearn not installed"}
        except Exception as e:
            logger.warning(f"HMM training failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def _fit_rf(
        self,
        features: pd.DataFrame,
        labels: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """Fit Random Forest classifier (supervised)."""
        try:
            from sklearn.ensemble import RandomForestClassifier
            
            if labels is None:
                # Generate labels using rule-based approach
                labels = self._generate_labels(features)
            
            self.model = RandomForestClassifier(
                n_estimators=self.config.get("rf_n_estimators", 100),
                max_depth=self.config.get("rf_max_depth", 4),
                min_samples_leaf=self.config.get("rf_min_samples_leaf", 5),
                random_state=42
            )
            
            X = features.values
            y = labels.values if hasattr(labels, 'values') else labels
            
            self.model.fit(X, y)
            self._fitted = True
            
            return {
                "status": "success",
                "model_type": "rf",
                "n_samples": len(features),
                "classes": list(self.model.classes_)
            }
            
        except ImportError:
            logger.warning("sklearn not installed, falling back to rule-based")
            return {"status": "fallback", "reason": "sklearn not installed"}
        except Exception as e:
            logger.warning(f"RF training failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def _generate_labels(self, features: pd.DataFrame) -> np.ndarray:
        """Generate regime labels using rule-based approach."""
        labels = []
        
        vix_high = self.config.get("vix_high_threshold", 25.0)
        vix_low = self.config.get("vix_low_threshold", 18.0)
        
        for _, row in features.iterrows():
            # Try to find VIX-like column
            vix_val = None
            for col in features.columns:
                if 'vix' in col.lower():
                    vix_val = row[col]
                    break
            
            if vix_val is not None:
                if vix_val > vix_high:
                    labels.append("risk_off")
                elif vix_val < vix_low:
                    labels.append("risk_on")
                else:
                    labels.append("transition")
            else:
                labels.append("transition")
        
        return np.array(labels)
    
    def predict(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict regime for given features.
        
        Returns:
            Dict with regime, confidence, probabilities
        """
        if not self._fitted or self.model is None:
            return self._predict_rule_based(features)
        
        try:
            X = features.values
            model_type = self.config.get("model_type", "rf")
            
            if model_type == "hmm":
                states = self.model.predict(X)
                # Map states to regime labels based on characteristics
                regime_idx = states[-1] if len(states) > 0 else 1
                regime = REGIME_LABELS[min(regime_idx, len(REGIME_LABELS) - 1)]
                
                return {
                    "regime": regime,
                    "confidence": 0.7,  # HMM doesn't give probabilities easily
                    "method": "hmm"
                }
            else:
                prediction = self.model.predict(X[-1:])
                proba = self.model.predict_proba(X[-1:])[0]
                
                return {
                    "regime": prediction[0],
                    "confidence": float(max(proba)),
                    "probabilities": dict(zip(self.model.classes_, proba)),
                    "method": "rf"
                }
                
        except Exception as e:
            logger.warning(f"Prediction failed, using rule-based: {e}")
            return self._predict_rule_based(features)
    
    def _predict_rule_based(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Rule-based regime classification as fallback."""
        if features.empty:
            return {"regime": "transition", "confidence": 0.5, "method": "rule_based"}
        
        row = features.iloc[-1]
        
        vix_high = self.config.get("vix_high_threshold", 25.0)
        vix_low = self.config.get("vix_low_threshold", 18.0)
        
        # Try to find VIX-like column
        vix_val = None
        for col in features.columns:
            if 'vix' in col.lower():
                vix_val = row[col]
                break
        
        if vix_val is not None:
            if vix_val > vix_high:
                return {"regime": "risk_off", "confidence": 0.8, "method": "rule_based"}
            elif vix_val < vix_low:
                return {"regime": "risk_on", "confidence": 0.8, "method": "rule_based"}
        
        return {"regime": "transition", "confidence": 0.5, "method": "rule_based"}
