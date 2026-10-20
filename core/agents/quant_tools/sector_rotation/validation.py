"""
Validation and statistical testing for sector rotation signals.

Walk-forward validation to prevent overfitting.
All thresholds configurable.
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_VALIDATION_CONFIG = {
    # Walk-forward params - percentage based
    "train_pct": 0.80,       # 80% train, 20% test (derived)
    "min_samples": 30,
    
    # Statistical thresholds
    "significance_level": 0.05,
    "min_sharpe": 0.5,
    "min_hit_rate": 0.52,
    "min_profit_factor": 1.1,
    
    # Bootstrap params
    "n_bootstrap": 1000,
    "confidence_level": 0.95,
}


# =============================================================================
# VALIDATION RESULTS
# =============================================================================

@dataclass
class ValidationResult:
    """Container for validation metrics."""
    sharpe_ratio: float
    hit_rate: float
    profit_factor: float
    total_return: float
    max_drawdown: float
    n_trades: int
    is_significant: bool
    confidence_interval: Tuple[float, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "hit_rate": round(self.hit_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "total_return": round(self.total_return, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "n_trades": self.n_trades,
            "is_significant": self.is_significant,
            "confidence_interval": (
                round(self.confidence_interval[0], 4),
                round(self.confidence_interval[1], 4)
            )
        }


# =============================================================================
# WALK-FORWARD VALIDATOR
# =============================================================================

class WalkForwardValidator:
    """
    Walk-forward validation for signal backtesting.
    
    Trains on rolling window, tests on next period.
    Prevents lookahead bias and overfitting.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_VALIDATION_CONFIG, **(config or {})}
        self._results = []
    
    def validate(
        self,
        signals: pd.Series,
        returns: pd.Series,
        train_func: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run walk-forward validation.
        
        Args:
            signals: Series of trading signals (-1, 0, 1)
            returns: Series of actual returns
            train_func: Optional function to retrain model each window
        
        Returns:
            Dict with validation results
        """
        n_samples = len(signals)
        min_samples = self.config.get("min_samples", 30)
        
        if n_samples < min_samples:
            return {
                "status": "insufficient_data",
                "n_samples": n_samples,
                "min_required": min_samples
            }
        
        # Calculate windows from percentage
        train_pct = self.config.get("train_pct", 0.80)
        test_pct = 1.0 - train_pct  # Derived, always sums to 100%
        
        train_window = max(1, int(n_samples * train_pct))
        test_window = max(1, int(n_samples * test_pct))
        
        # Align signals and returns
        common_idx = signals.index.intersection(returns.index)
        signals = signals.loc[common_idx]
        returns = returns.loc[common_idx]
        
        self._results = []
        fold_results = []
        
        # Walk forward
        start = 0
        fold = 0
        
        while start + train_window + test_window <= len(signals):
            train_end = start + train_window
            test_end = train_end + test_window
            
            # Get windows
            train_signals = signals.iloc[start:train_end]
            test_signals = signals.iloc[train_end:test_end]
            test_returns = returns.iloc[train_end:test_end]
            
            # Optionally retrain
            if train_func is not None:
                try:
                    train_func(train_signals)
                except Exception as e:
                    logger.warning(f"Train function failed on fold {fold}: {e}")
            
            # Calculate fold performance
            strategy_returns = test_signals * test_returns
            
            fold_metrics = self._calculate_metrics(strategy_returns)
            fold_metrics["fold"] = fold
            fold_metrics["train_start"] = start
            fold_metrics["test_start"] = train_end
            fold_results.append(fold_metrics)
            
            self._results.append(strategy_returns)
            
            # Slide window
            start += test_window
            fold += 1
        
        # Aggregate results
        if not self._results:
            return {
                "status": "no_folds",
                "n_samples": n_samples,
                "train_window": train_window,
                "test_window": test_window
            }
        
        all_returns = pd.concat(self._results)
        aggregate = self._calculate_metrics(all_returns)
        
        # Statistical significance
        is_significant = self._test_significance(all_returns)
        
        # Bootstrap confidence interval
        ci = self._bootstrap_ci(all_returns)
        
        # Check against thresholds
        passes_thresholds = self._check_thresholds(aggregate)
        
        return {
            "status": "success",
            "n_folds": len(fold_results),
            "train_window": train_window,
            "test_window": test_window,
            "aggregate": aggregate,
            "fold_results": fold_results,
            "is_significant": is_significant,
            "confidence_interval": ci,
            "passes_thresholds": passes_thresholds
        }
    
    def _calculate_metrics(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate performance metrics for a return series."""
        if len(returns) == 0 or returns.std() == 0:
            return {
                "sharpe_ratio": 0.0,
                "hit_rate": 0.0,
                "profit_factor": 0.0,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "n_trades": 0
            }
        
        # Sharpe (annualized, assuming daily)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        
        # Hit rate
        n_positive = (returns > 0).sum()
        n_trades = (returns != 0).sum()
        hit_rate = n_positive / n_trades if n_trades > 0 else 0
        
        # Profit factor
        gains = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        profit_factor = gains / losses if losses > 0 else float('inf')
        
        # Total return
        total_return = (1 + returns).prod() - 1
        
        # Max drawdown
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdowns = cumulative / rolling_max - 1
        max_drawdown = abs(drawdowns.min())
        
        return {
            "sharpe_ratio": round(float(sharpe), 4),
            "hit_rate": round(float(hit_rate), 4),
            "profit_factor": round(float(min(profit_factor, 99.99)), 4),
            "total_return": round(float(total_return), 4),
            "max_drawdown": round(float(max_drawdown), 4),
            "n_trades": int(n_trades)
        }
    
    def _test_significance(self, returns: pd.Series) -> bool:
        """Test if returns are statistically significant."""
        if len(returns) < 10:
            return False
        
        try:
            from scipy import stats
            t_stat, p_value = stats.ttest_1samp(returns, 0)
            return p_value < self.config.get("significance_level", 0.05)
        except ImportError:
            # Fallback: z-test approximation
            mean = returns.mean()
            std = returns.std()
            n = len(returns)
            if std == 0:
                return False
            z = (mean * np.sqrt(n)) / std
            # Approximate p-value for two-tailed test
            p_approx = 2 * (1 - 0.5 * (1 + np.tanh(0.7 * z)))
            return p_approx < self.config.get("significance_level", 0.05)
    
    def _bootstrap_ci(self, returns: pd.Series) -> Tuple[float, float]:
        """Bootstrap confidence interval for mean return."""
        n_bootstrap = self.config.get("n_bootstrap", 1000)
        confidence = self.config.get("confidence_level", 0.95)
        
        if len(returns) < 5:
            return (0.0, 0.0)
        
        bootstrap_means = []
        for _ in range(n_bootstrap):
            sample = returns.sample(n=len(returns), replace=True)
            bootstrap_means.append(sample.mean())
        
        alpha = (1 - confidence) / 2
        lower = np.percentile(bootstrap_means, alpha * 100)
        upper = np.percentile(bootstrap_means, (1 - alpha) * 100)
        
        return (float(lower), float(upper))
    
    def _check_thresholds(self, metrics: Dict[str, float]) -> Dict[str, bool]:
        """Check if metrics pass minimum thresholds."""
        return {
            "sharpe": metrics.get("sharpe_ratio", 0) >= self.config.get("min_sharpe", 0.5),
            "hit_rate": metrics.get("hit_rate", 0) >= self.config.get("min_hit_rate", 0.52),
            "profit_factor": metrics.get("profit_factor", 0) >= self.config.get("min_profit_factor", 1.1)
        }
