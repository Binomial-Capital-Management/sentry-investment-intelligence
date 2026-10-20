"""
Lead-lag relationship detector using Granger causality.

Finds which sector flows predict other sectors' returns.
All thresholds configurable.
"""

from typing import Dict, List, Optional, Any
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_LEAD_LAG_CONFIG = {
    "max_lag": 5,
    "p_threshold": 0.05,
    "min_observations": 30,
}


# =============================================================================
# LEAD-LAG DETECTOR
# =============================================================================

class LeadLagDetector:
    """
    Detects lead-lag relationships between sector flows and returns.
    
    Uses Granger causality to test if one sector's flow
    predicts another sector's future returns.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_LEAD_LAG_CONFIG, **(config or {})}
        self._results = None
    
    def detect(
        self,
        flow_data: pd.DataFrame,
        return_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect lead-lag relationships.
        
        Args:
            flow_data: DataFrame with columns for each sector's flow
            return_data: DataFrame with columns for each sector's returns
        
        Returns:
            Dict with detected relationships and statistics
        """
        max_lag = self.config.get("max_lag", 5)
        p_threshold = self.config.get("p_threshold", 0.05)
        min_obs = self.config.get("min_observations", 30)
        
        if len(flow_data) < min_obs or len(return_data) < min_obs:
            return {
                "status": "insufficient_data",
                "relationships": [],
                "n_observations": min(len(flow_data), len(return_data))
            }
        
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
            
            relationships = []
            flow_sectors = list(flow_data.columns)
            return_sectors = list(return_data.columns)
            
            for leader in flow_sectors:
                for follower in return_sectors:
                    result = self._test_granger(
                        flow_data[leader],
                        return_data[follower],
                        max_lag,
                        p_threshold
                    )
                    
                    if result is not None:
                        relationships.append({
                            "leader": leader,
                            "follower": follower,
                            "lag_days": result["lag"],
                            "p_value": result["p_value"],
                            "f_statistic": result["f_stat"],
                            "signal": f"{leader} flow predicts {follower} returns by {result['lag']}d"
                        })
            
            # Sort by p-value (most significant first)
            relationships.sort(key=lambda x: x["p_value"])
            
            self._results = relationships
            
            return {
                "status": "success",
                "relationships": relationships,
                "n_significant": len(relationships),
                "n_tests": len(flow_sectors) * len(return_sectors),
                "config": {
                    "max_lag": max_lag,
                    "p_threshold": p_threshold
                }
            }
            
        except ImportError:
            logger.warning("statsmodels not installed, using correlation fallback")
            return self._correlation_fallback(flow_data, return_data)
        except Exception as e:
            logger.warning(f"Lead-lag detection failed: {e}")
            return {"status": "error", "error": str(e), "relationships": []}
    
    def _test_granger(
        self,
        leader: pd.Series,
        follower: pd.Series,
        max_lag: int,
        p_threshold: float
    ) -> Optional[Dict]:
        """Test Granger causality for a single pair."""
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
            
            # Combine into DataFrame and drop NaN
            combined = pd.concat([follower, leader], axis=1).dropna()
            
            if len(combined) < max_lag + 10:
                return None
            
            # Run Granger test (suppress output)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                results = grangercausalitytests(combined, maxlag=max_lag, verbose=False)
            
            # Find best lag with significant p-value
            for lag in range(1, max_lag + 1):
                f_test = results[lag][0]['ssr_ftest']
                f_stat = f_test[0]
                p_value = f_test[1]
                
                if p_value < p_threshold:
                    return {
                        "lag": lag,
                        "p_value": round(p_value, 4),
                        "f_stat": round(f_stat, 4)
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Granger test failed: {e}")
            return None
    
    def _correlation_fallback(
        self,
        flow_data: pd.DataFrame,
        return_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Simple correlation-based fallback when statsmodels unavailable."""
        relationships = []
        max_lag = self.config.get("max_lag", 5)
        
        for leader in flow_data.columns:
            for follower in return_data.columns:
                for lag in range(1, max_lag + 1):
                    # Shift leader back by lag days
                    leader_shifted = flow_data[leader].shift(lag)
                    
                    # Compute correlation
                    combined = pd.concat([leader_shifted, return_data[follower]], axis=1).dropna()
                    if len(combined) < 20:
                        continue
                    
                    corr = combined.iloc[:, 0].corr(combined.iloc[:, 1])
                    
                    # Simple threshold for significance
                    if abs(corr) > 0.3:
                        relationships.append({
                            "leader": leader,
                            "follower": follower,
                            "lag_days": lag,
                            "correlation": round(corr, 4),
                            "signal": f"{leader} flow correlates with {follower} returns at lag {lag}d"
                        })
                        break  # Take first significant lag
        
        relationships.sort(key=lambda x: abs(x.get("correlation", 0)), reverse=True)
        
        return {
            "status": "fallback",
            "method": "correlation",
            "relationships": relationships,
            "n_significant": len(relationships)
        }
    
    def get_leaders(self) -> List[str]:
        """Get sectors that lead others."""
        if not self._results:
            return []
        
        leaders = {}
        for r in self._results:
            leader = r["leader"]
            leaders[leader] = leaders.get(leader, 0) + 1
        
        # Sort by number of relationships
        return sorted(leaders.keys(), key=lambda x: leaders[x], reverse=True)
    
    def get_laggers(self) -> List[str]:
        """Get sectors that lag others."""
        if not self._results:
            return []
        
        laggers = {}
        for r in self._results:
            follower = r["follower"]
            laggers[follower] = laggers.get(follower, 0) + 1
        
        return sorted(laggers.keys(), key=lambda x: laggers[x], reverse=True)
