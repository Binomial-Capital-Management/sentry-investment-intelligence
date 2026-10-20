"""
Ensemble stacking model for sector rotation signals.

Combines RF + GBM + LogReg with a meta-learner.
All parameters configurable.
"""

from typing import Dict, List, Optional, Any
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_ENSEMBLE_CONFIG = {
    # Base models - RandomForest
    "rf_n_estimators": 50,
    "rf_max_depth": 4,
    
    # Base models - GradientBoosting
    "gbm_n_estimators": 50,
    "gbm_max_depth": 3,
    "gbm_learning_rate": 0.1,
    
    # Base models - LogisticRegression
    "lr_C": 0.1,
    "lr_max_iter": 500,
    
    # Meta-learner selection
    "meta_learner": "logistic",  # "logistic" or "rf"
    
    # Meta-learner - RandomForest params
    "meta_rf_n_estimators": 20,
    "meta_rf_max_depth": 3,
    
    # Meta-learner - LogisticRegression params
    "meta_lr_C": 1.0,
    "meta_lr_max_iter": 500,
    
    # Cross-validation
    "cv_splits": 5,
    "passthrough": True,  # Include raw features in meta-learner
    
    # Training
    "min_samples": 50,
    "random_state": 42,
}


# =============================================================================
# ENSEMBLE MODEL
# =============================================================================

class EnsembleModel:
    """
    Stacking ensemble for sector outperformance prediction.
    
    Base models: RandomForest, GradientBoosting, LogisticRegression
    Meta-learner: LogisticRegression (default) or RandomForest
    
    Target: Binary (1 = sector outperforms, 0 = underperforms)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_ENSEMBLE_CONFIG, **(config or {})}
        self.model = None
        self._fitted = False
        self._feature_names = []
        self._classes = []
    
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> Dict[str, Any]:
        """
        Fit ensemble model.
        
        Args:
            X: Feature DataFrame
            y: Binary target (1 = outperform, 0 = underperform)
        
        Returns:
            Dict with training info
        """
        min_samples = self.config.get("min_samples", 50)
        
        if len(X) < min_samples:
            return {
                "status": "insufficient_data",
                "n_samples": len(X),
                "min_required": min_samples
            }
        
        try:
            from sklearn.ensemble import (
                RandomForestClassifier, 
                GradientBoostingClassifier,
                StackingClassifier
            )
            from sklearn.linear_model import LogisticRegression
            
            self._feature_names = list(X.columns)
            random_state = self.config.get("random_state", 42)
            
            # Build base estimators - all params from config
            estimators = [
                ('rf', RandomForestClassifier(
                    n_estimators=self.config.get("rf_n_estimators", 50),
                    max_depth=self.config.get("rf_max_depth", 4),
                    random_state=random_state
                )),
                ('gbm', GradientBoostingClassifier(
                    n_estimators=self.config.get("gbm_n_estimators", 50),
                    max_depth=self.config.get("gbm_max_depth", 3),
                    learning_rate=self.config.get("gbm_learning_rate", 0.1),
                    random_state=random_state
                )),
                ('lr', LogisticRegression(
                    C=self.config.get("lr_C", 0.1),
                    random_state=random_state,
                    max_iter=self.config.get("lr_max_iter", 500)
                ))
            ]
            
            # Build meta-learner - all params from config
            meta_type = self.config.get("meta_learner", "logistic")
            if meta_type == "rf":
                final_estimator = RandomForestClassifier(
                    n_estimators=self.config.get("meta_rf_n_estimators", 20),
                    max_depth=self.config.get("meta_rf_max_depth", 3),
                    random_state=random_state
                )
            else:
                final_estimator = LogisticRegression(
                    C=self.config.get("meta_lr_C", 1.0),
                    random_state=random_state,
                    max_iter=self.config.get("meta_lr_max_iter", 500)
                )
            
            # Build stacking classifier
            self.model = StackingClassifier(
                estimators=estimators,
                final_estimator=final_estimator,
                cv=self.config.get("cv_splits", 5),
                passthrough=self.config.get("passthrough", True)
            )
            
            X_arr = X.values
            y_arr = y.values if hasattr(y, 'values') else np.array(y)
            
            self.model.fit(X_arr, y_arr)
            self._fitted = True
            self._classes = list(self.model.classes_)
            
            # Get training accuracy
            train_score = self.model.score(X_arr, y_arr)
            
            return {
                "status": "success",
                "n_samples": len(X),
                "n_features": len(self._feature_names),
                "classes": self._classes,
                "train_accuracy": round(train_score, 4),
                "base_models": ["rf", "gbm", "lr"],
                "meta_learner": meta_type
            }
            
        except ImportError:
            logger.warning("sklearn not installed, ensemble not available")
            return {"status": "error", "reason": "sklearn not installed"}
        except Exception as e:
            logger.warning(f"Ensemble training failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def predict(self, X: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict sector outperformance.
        
        Args:
            X: Feature DataFrame
        
        Returns:
            Dict with predictions and probabilities
        """
        if not self._fitted or self.model is None:
            return {
                "status": "not_fitted",
                "predictions": [],
                "probabilities": []
            }
        
        try:
            X_arr = X.values
            
            predictions = self.model.predict(X_arr)
            probabilities = self.model.predict_proba(X_arr)
            
            results = []
            for i, (pred, proba) in enumerate(zip(predictions, probabilities)):
                results.append({
                    "index": i,
                    "prediction": int(pred) if isinstance(pred, (np.integer, int)) else pred,
                    "probability": round(float(max(proba)), 4),
                    "class_probabilities": {
                        str(c): round(float(p), 4) 
                        for c, p in zip(self._classes, proba)
                    }
                })
            
            return {
                "status": "success",
                "results": results,
                "n_predictions": len(results)
            }
            
        except Exception as e:
            logger.warning(f"Ensemble prediction failed: {e}")
            return {"status": "error", "error": str(e), "results": []}
    
    def predict_proba(self, X: pd.DataFrame) -> Dict[str, float]:
        """
        Get outperformance probability for each row.
        
        Returns:
            Dict mapping index to probability of outperformance
        """
        if not self._fitted or self.model is None:
            return {}
        
        try:
            X_arr = X.values
            probabilities = self.model.predict_proba(X_arr)
            
            # Assume class 1 is "outperform"
            outperform_idx = list(self._classes).index(1) if 1 in self._classes else -1
            
            if outperform_idx >= 0:
                return {
                    i: round(float(proba[outperform_idx]), 4)
                    for i, proba in enumerate(probabilities)
                }
            else:
                return {
                    i: round(float(max(proba)), 4)
                    for i, proba in enumerate(probabilities)
                }
                
        except Exception as e:
            logger.warning(f"Probability prediction failed: {e}")
            return {}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from base models.
        
        Returns:
            Dict mapping feature name to importance score
        """
        if not self._fitted or self.model is None:
            return {}
        
        try:
            # Get RF feature importance (most interpretable)
            rf_model = self.model.named_estimators_.get('rf')
            if rf_model is not None and hasattr(rf_model, 'feature_importances_'):
                importances = rf_model.feature_importances_
                return {
                    name: round(float(imp), 4)
                    for name, imp in zip(self._feature_names, importances)
                }
            
            return {}
            
        except Exception as e:
            logger.warning(f"Feature importance extraction failed: {e}")
            return {}
