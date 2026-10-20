"""
Flow anomaly detector using Isolation Forest.

Flags unusual flow patterns that may indicate informed trading.
All thresholds configurable.
"""

from typing import Dict, List, Optional, Any
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_ANOMALY_CONFIG = {
    "contamination": 0.05,  # Expected proportion of anomalies
    "n_estimators": 100,
    "max_samples": "auto",
    "random_state": 42,
    "min_samples_fit": 20,
}


# =============================================================================
# ANOMALY DETECTOR
# =============================================================================

class AnomalyDetector:
    """
    Detects unusual flow patterns using Isolation Forest.
    
    High anomaly score + strong directional flow = potential informed activity.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_ANOMALY_CONFIG, **(config or {})}
        self.model = None
        self._fitted = False
        self._feature_names = []
    
    def fit(self, historical_flow: pd.DataFrame) -> Dict[str, Any]:
        """
        Fit anomaly detector on historical flow data.
        
        Args:
            historical_flow: DataFrame with flow features
        
        Returns:
            Dict with training info
        """
        min_samples = self.config.get("min_samples_fit", 20)
        
        if len(historical_flow) < min_samples:
            return {
                "status": "insufficient_data",
                "n_samples": len(historical_flow),
                "min_required": min_samples
            }
        
        try:
            from sklearn.ensemble import IsolationForest
            
            self.model = IsolationForest(
                contamination=self.config.get("contamination", 0.05),
                n_estimators=self.config.get("n_estimators", 100),
                max_samples=self.config.get("max_samples", "auto"),
                random_state=self.config.get("random_state", 42)
            )
            
            X = historical_flow.values
            self._feature_names = list(historical_flow.columns)
            
            self.model.fit(X)
            self._fitted = True
            
            # Get baseline anomaly distribution
            scores = self.model.score_samples(X)
            
            return {
                "status": "success",
                "n_samples": len(historical_flow),
                "n_features": len(self._feature_names),
                "score_mean": float(np.mean(scores)),
                "score_std": float(np.std(scores))
            }
            
        except ImportError:
            logger.warning("sklearn not installed, using z-score fallback")
            return {"status": "fallback", "reason": "sklearn not installed"}
        except Exception as e:
            logger.warning(f"Anomaly detector training failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def detect(self, current_flow: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect anomalies in current flow data.
        
        Args:
            current_flow: DataFrame with current flow features
        
        Returns:
            Dict with anomaly scores and flags
        """
        if not self._fitted or self.model is None:
            return self._detect_zscore_fallback(current_flow)
        
        try:
            X = current_flow.values
            
            # Get anomaly predictions (-1 = anomaly, 1 = normal)
            predictions = self.model.predict(X)
            
            # Get anomaly scores (more negative = more anomalous)
            scores = self.model.score_samples(X)
            
            results = []
            for i, (pred, score) in enumerate(zip(predictions, scores)):
                is_anomaly = pred == -1
                
                # Convert score to 0-1 scale (higher = more anomalous)
                anomaly_score = 1 - (score + 0.5)  # Rough normalization
                anomaly_score = max(0, min(1, anomaly_score))
                
                result = {
                    "index": i,
                    "is_anomaly": is_anomaly,
                    "anomaly_score": round(anomaly_score, 4),
                    "raw_score": round(score, 4),
                }
                
                if is_anomaly:
                    result["interpretation"] = "Unusual flow pattern - potential informed activity"
                else:
                    result["interpretation"] = "Normal flow pattern"
                
                results.append(result)
            
            # Summary
            n_anomalies = sum(1 for r in results if r["is_anomaly"])
            
            return {
                "status": "success",
                "method": "isolation_forest",
                "results": results,
                "n_anomalies": n_anomalies,
                "anomaly_rate": round(n_anomalies / len(results), 4) if results else 0
            }
            
        except Exception as e:
            logger.warning(f"Anomaly detection failed: {e}")
            return self._detect_zscore_fallback(current_flow)
    
    def _detect_zscore_fallback(self, current_flow: pd.DataFrame) -> Dict[str, Any]:
        """Z-score based anomaly detection fallback."""
        results = []
        
        for i, row in current_flow.iterrows():
            # Compute z-score for each feature
            zscores = []
            for col in current_flow.columns:
                val = row[col]
                col_mean = current_flow[col].mean()
                col_std = current_flow[col].std()
                
                if col_std > 1e-9:
                    zscore = abs((val - col_mean) / col_std)
                    zscores.append(zscore)
            
            # Average z-score
            avg_zscore = np.mean(zscores) if zscores else 0
            
            # Flag as anomaly if avg z-score > 2.5
            is_anomaly = avg_zscore > 2.5
            
            results.append({
                "index": i,
                "is_anomaly": is_anomaly,
                "anomaly_score": round(min(avg_zscore / 4, 1.0), 4),
                "avg_zscore": round(avg_zscore, 4),
                "interpretation": "Unusual flow pattern" if is_anomaly else "Normal flow pattern"
            })
        
        n_anomalies = sum(1 for r in results if r["is_anomaly"])
        
        return {
            "status": "fallback",
            "method": "zscore",
            "results": results,
            "n_anomalies": n_anomalies,
            "anomaly_rate": round(n_anomalies / len(results), 4) if results else 0
        }
    
    def score_single(self, flow_vector: np.ndarray) -> Dict[str, Any]:
        """
        Score a single flow observation.
        
        Args:
            flow_vector: 1D array of flow features
        
        Returns:
            Dict with anomaly score and flag
        """
        if not self._fitted or self.model is None:
            return {"is_anomaly": False, "anomaly_score": 0, "method": "not_fitted"}
        
        try:
            X = flow_vector.reshape(1, -1)
            
            prediction = self.model.predict(X)[0]
            score = self.model.score_samples(X)[0]
            
            is_anomaly = prediction == -1
            anomaly_score = 1 - (score + 0.5)
            anomaly_score = max(0, min(1, anomaly_score))
            
            return {
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_score, 4),
                "raw_score": round(score, 4),
                "method": "isolation_forest"
            }
            
        except Exception as e:
            logger.warning(f"Single score failed: {e}")
            return {"is_anomaly": False, "anomaly_score": 0, "error": str(e)}
