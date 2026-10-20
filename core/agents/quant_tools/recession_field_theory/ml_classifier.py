"""
Recession Field Theory - ML Classifier (Optional)

Optional machine learning ensemble for recession probability estimation.
Combines:
- Economic field values (φ history)
- Physics statistics (AR1, correlation length, susceptibility, spectral)
- HMM state probabilities

Models:
- Logistic Regression (interpretable baseline)
- Gradient Boosting (if available, better performance)

Target: Binary classification - recession within N months
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Check for sklearn availability
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import precision_score, recall_score, roc_auc_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("[ML] scikit-learn not installed. ML classifier disabled.")

# Check for xgboost (optional)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def build_features(
    field: pd.Series,
    physics_stats: Dict[str, Any],
    hmm_probs: Dict[str, float],
    field_lags: int = 4
) -> Dict[str, float]:
    """
    Build feature vector for ML classifier.
    
    Args:
        field: Economic field series
        physics_stats: Dict from PhysicsStatsAnalyzer
        hmm_probs: Regime probabilities from HMM
        field_lags: Number of lagged field values to include
    
    Returns:
        Dict of feature name -> value
    """
    features = {}
    
    # Field values (current and lagged)
    if field is not None and len(field) > 0:
        clean_field = field.dropna()
        
        if len(clean_field) > 0:
            features["field_current"] = float(clean_field.iloc[-1])
            
            for lag in range(1, min(field_lags + 1, len(clean_field))):
                features[f"field_lag_{lag}"] = float(clean_field.iloc[-1 - lag])
            
            # Field momentum
            if len(clean_field) >= 3:
                features["field_momentum_3m"] = float(clean_field.iloc[-1] - clean_field.iloc[-3])
            
            if len(clean_field) >= 6:
                features["field_momentum_6m"] = float(clean_field.iloc[-1] - clean_field.iloc[-6])
            
            # Field volatility
            if len(clean_field) >= 6:
                features["field_volatility_6m"] = float(clean_field.tail(6).std())
    
    # Physics statistics
    if physics_stats:
        stats = physics_stats.get("statistics", {})
        
        ar1_data = stats.get("critical_slowing_down", {})
        if ar1_data.get("ar1_coefficient") is not None:
            features["ar1_coefficient"] = ar1_data["ar1_coefficient"]
        
        xi_data = stats.get("correlation_length", {})
        if xi_data.get("cross_sector_correlation") is not None:
            features["correlation_length"] = xi_data["cross_sector_correlation"]
        
        chi_data = stats.get("susceptibility", {})
        if chi_data.get("variance_ratio") is not None:
            features["susceptibility"] = chi_data["variance_ratio"]
        
        spec_data = stats.get("spectral_dominance", {})
        if spec_data.get("first_eigenvalue_share") is not None:
            features["spectral_dominance"] = spec_data["first_eigenvalue_share"]
        
        # Signal counts
        signals = physics_stats.get("signals", {})
        features["n_elevated_signals"] = sum(1 for s in signals.values() if s == "ELEVATED")
        features["n_critical_signals"] = sum(1 for s in signals.values() if s == "CRITICAL")
    
    # HMM probabilities
    if hmm_probs:
        features["hmm_prob_expansion"] = hmm_probs.get("expansion", 0.33)
        features["hmm_prob_transition"] = hmm_probs.get("transition", 0.34)
        features["hmm_prob_recession"] = hmm_probs.get("recession", 0.33)
    
    return features


# =============================================================================
# SIMPLE HEURISTIC MODEL (No ML required)
# =============================================================================

def heuristic_recession_probability(
    features: Dict[str, float]
) -> Tuple[float, Dict[str, Any]]:
    """
    Simple heuristic-based recession probability when ML not available.
    
    Uses weighted combination of signals.
    
    Returns:
        Tuple of (probability, details)
    """
    prob = 0.10  # Base probability
    contributions = {}
    
    # Field value contribution
    field_val = features.get("field_current", 0)
    if field_val < -1.0:
        field_contrib = 0.30
    elif field_val < -0.5:
        field_contrib = 0.15
    elif field_val < 0:
        field_contrib = 0.05
    else:
        field_contrib = 0.0
    prob += field_contrib
    contributions["field_value"] = field_contrib
    
    # Physics signals contribution
    n_elevated = features.get("n_elevated_signals", 0)
    n_critical = features.get("n_critical_signals", 0)
    
    signal_contrib = n_elevated * 0.05 + n_critical * 0.15
    prob += signal_contrib
    contributions["physics_signals"] = signal_contrib
    
    # AR1 contribution
    ar1 = features.get("ar1_coefficient", 0.85)
    if ar1 > 0.95:
        ar1_contrib = 0.15
    elif ar1 > 0.90:
        ar1_contrib = 0.08
    else:
        ar1_contrib = 0.0
    prob += ar1_contrib
    contributions["ar1"] = ar1_contrib
    
    # HMM contribution
    hmm_recession = features.get("hmm_prob_recession", 0.1)
    hmm_contrib = hmm_recession * 0.20
    prob += hmm_contrib
    contributions["hmm_recession_prob"] = hmm_contrib
    
    # Cap at reasonable range
    prob = max(0.02, min(0.95, prob))
    
    return prob, {
        "method": "heuristic",
        "contributions": contributions,
        "confidence_interval": [max(0.01, prob - 0.15), min(0.99, prob + 0.15)]
    }


# =============================================================================
# ML CLASSIFIER CLASS
# =============================================================================

class RecessionClassifier:
    """
    ML-based recession probability classifier.
    
    Falls back to heuristic when sklearn not available.
    """
    
    def __init__(
        self,
        forecast_horizon_months: int = 6,
        use_xgboost: bool = True
    ):
        """
        Initialize the classifier.
        
        Args:
            forecast_horizon_months: How far ahead to predict recession
            use_xgboost: Use XGBoost if available (else LogisticRegression)
        """
        self.forecast_horizon = forecast_horizon_months
        self.use_xgboost = use_xgboost and XGBOOST_AVAILABLE
        
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.is_fitted = False
        
        # Performance metrics from training
        self.training_metrics = None
    
    def _create_model(self):
        """Create the underlying model."""
        if not SKLEARN_AVAILABLE:
            return None
        
        if self.use_xgboost and XGBOOST_AVAILABLE:
            return xgb.XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            )
        else:
            return LogisticRegression(
                C=1.0,
                max_iter=1000,
                random_state=42
            )
    
    def fit(
        self,
        features_df: pd.DataFrame,
        recession_labels: pd.Series
    ) -> bool:
        """
        Fit the classifier on historical data.
        
        Args:
            features_df: DataFrame of features over time
            recession_labels: Binary series (1 = recession within horizon)
        
        Returns:
            True if fitting succeeded
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("[ML] sklearn not available, using heuristic")
            self.is_fitted = False
            return False
        
        # Align data
        common_idx = features_df.index.intersection(recession_labels.index)
        X = features_df.loc[common_idx]
        y = recession_labels.loc[common_idx]
        
        # Drop NaN
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X = X.loc[valid_mask]
        y = y.loc[valid_mask]
        
        if len(X) < 30:
            logger.warning(f"[ML] Insufficient training data: {len(X)} samples")
            return False
        
        try:
            # Store feature names
            self.feature_names = X.columns.tolist()
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Create and fit model
            self.model = self._create_model()
            
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=5)
            cv_scores = []
            
            for train_idx, val_idx in tscv.split(X_scaled):
                X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                
                self.model.fit(X_train, y_train)
                
                if hasattr(self.model, 'predict_proba'):
                    y_prob = self.model.predict_proba(X_val)[:, 1]
                    if len(np.unique(y_val)) > 1:
                        cv_scores.append(roc_auc_score(y_val, y_prob))
            
            # Final fit on all data
            self.model.fit(X_scaled, y)
            
            # Store metrics
            y_pred = self.model.predict(X_scaled)
            y_prob = self.model.predict_proba(X_scaled)[:, 1] if hasattr(self.model, 'predict_proba') else y_pred
            
            self.training_metrics = {
                "n_samples": len(X),
                "n_features": len(self.feature_names),
                "cv_auc_mean": float(np.mean(cv_scores)) if cv_scores else None,
                "precision": float(precision_score(y, y_pred, zero_division=0)),
                "recall": float(recall_score(y, y_pred, zero_division=0)),
                "recession_rate": float(y.mean())
            }
            
            self.is_fitted = True
            logger.info(f"[ML] Model fitted: {self.training_metrics}")
            
            return True
            
        except Exception as e:
            logger.error(f"[ML] Fitting failed: {e}")
            return False
    
    def predict_probability(
        self,
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Predict recession probability from features.
        
        Args:
            features: Feature dictionary from build_features()
        
        Returns:
            Dict with probability and details
        """
        # Fallback to heuristic if model not available
        if not self.is_fitted or self.model is None:
            prob, details = heuristic_recession_probability(features)
            return {
                "probability": round(prob, 3),
                "probability_6_month": round(prob, 3),
                "confidence_interval": details["confidence_interval"],
                "method": details["method"],
                "details": details
            }
        
        try:
            # Build feature vector in correct order
            X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
            
            # Scale
            X_scaled = self.scaler.transform(X)
            
            # Predict
            if hasattr(self.model, 'predict_proba'):
                prob = float(self.model.predict_proba(X_scaled)[0, 1])
            else:
                prob = float(self.model.predict(X_scaled)[0])
            
            # Confidence interval (approximate)
            ci_width = 0.10 if prob > 0.3 else 0.05
            ci_lower = max(0.01, prob - ci_width)
            ci_upper = min(0.99, prob + ci_width)
            
            return {
                "probability": round(prob, 3),
                "probability_6_month": round(prob, 3),
                "confidence_interval": [round(ci_lower, 3), round(ci_upper, 3)],
                "method": "xgboost" if self.use_xgboost else "logistic_regression",
                "model_metrics": self.training_metrics,
                "feature_importance": self._get_feature_importance()
            }
            
        except Exception as e:
            logger.error(f"[ML] Prediction failed: {e}")
            prob, details = heuristic_recession_probability(features)
            return {
                "probability": round(prob, 3),
                "probability_6_month": round(prob, 3),
                "confidence_interval": details["confidence_interval"],
                "method": "heuristic_fallback",
                "error": str(e)
            }
    
    def _get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance from model."""
        if self.model is None or self.feature_names is None:
            return None
        
        try:
            if hasattr(self.model, 'feature_importances_'):
                # XGBoost or tree-based
                importances = self.model.feature_importances_
            elif hasattr(self.model, 'coef_'):
                # Logistic regression
                importances = np.abs(self.model.coef_[0])
            else:
                return None
            
            return {
                name: round(float(imp), 4)
                for name, imp in zip(self.feature_names, importances)
            }
        except Exception:
            return None


# =============================================================================
# MAIN INTERFACE
# =============================================================================

def estimate_recession_probability(
    field: pd.Series,
    physics_stats: Dict[str, Any],
    hmm_result: Dict[str, Any],
    classifier: Optional[RecessionClassifier] = None
) -> Dict[str, Any]:
    """
    Estimate recession probability combining all signals.
    
    Args:
        field: Economic field series
        physics_stats: Results from PhysicsStatsAnalyzer
        hmm_result: Results from RegimeAnalyzer
        classifier: Optional pre-trained classifier
    
    Returns:
        Dict with recession probability estimate
    """
    # Build features
    hmm_probs = hmm_result.get("regime_probabilities", {})
    features = build_features(field, physics_stats, hmm_probs)
    
    # Get prediction
    if classifier is not None and classifier.is_fitted:
        result = classifier.predict_probability(features)
    else:
        prob, details = heuristic_recession_probability(features)
        result = {
            "probability": round(prob, 3),
            "probability_6_month": round(prob, 3),
            "confidence_interval": details["confidence_interval"],
            "method": details["method"],
            "details": details
        }
    
    # Add interpretation
    prob = result["probability"]
    if prob >= 0.6:
        result["interpretation"] = "High recession risk"
        result["recommendation"] = "Defensive positioning recommended"
    elif prob >= 0.35:
        result["interpretation"] = "Elevated recession risk"
        result["recommendation"] = "Reduce risk exposure, increase hedges"
    elif prob >= 0.20:
        result["interpretation"] = "Moderate recession risk"
        result["recommendation"] = "Monitor closely, prepare contingency plans"
    else:
        result["interpretation"] = "Low recession risk"
        result["recommendation"] = "Normal positioning appropriate"
    
    return result

