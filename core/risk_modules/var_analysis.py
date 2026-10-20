"""
Value at Risk (VaR) Analysis Module

Calculates VaR using multiple methods:
- Parametric (variance-covariance)
- Historical simulation
- Monte Carlo simulation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from scipy import stats
import logging
from ..constants import DEFAULT_PORTFOLIO_VALUE

logger = logging.getLogger(__name__)


class VaRAnalysis:
    """Value at Risk calculation engine."""
    
    def __init__(self, confidence_levels: List[float] = None):
        """
        Initialize VaR analysis engine.
        
        Args:
            confidence_levels: List of confidence levels (e.g., [0.95, 0.99])
        """
        self.confidence_levels = confidence_levels or [0.95, 0.99]
        
    def calculate_var(self, 
                     prices: pd.DataFrame,
                     weights: np.ndarray,
                     method: str = 'all',
                     portfolio_value: float = DEFAULT_PORTFOLIO_VALUE) -> Dict:
        """
        Calculate VaR using specified method(s).
        
        Args:
            prices: DataFrame of asset prices
            weights: Portfolio weights
            method: 'parametric', 'historical', 'monte_carlo', or 'all'
            portfolio_value: Total portfolio value
            
        Returns:
            Dictionary with VaR calculations and statistics
        """
        # Calculate returns
        returns = prices.pct_change().dropna()
        portfolio_returns = returns @ weights
        
        results = {
            'dates': returns.index.tolist(),
            'returns': portfolio_returns.values,
            'portfolio_value': portfolio_value
        }
        
        # Calculate VaR by method
        if method in ['parametric', 'all']:
            results['parametric_var'] = self._parametric_var(
                portfolio_returns, portfolio_value
            )
            
        if method in ['historical', 'all']:
            results['historical_var'] = self._historical_var(
                portfolio_returns, portfolio_value
            )
            
        if method in ['monte_carlo', 'all']:
            results['monte_carlo_var'] = self._monte_carlo_var(
                returns, weights, portfolio_value
            )
        
        # Run backtesting if we have enough data
        if len(portfolio_returns) > 250:  # At least 1 year
            results['backtest_results'] = self._backtest_var(
                portfolio_returns, 
                results.get('historical_var', {}),
                portfolio_value
            )
        
        return results
    
    def _parametric_var(self, returns: pd.Series, portfolio_value: float) -> Dict:
        """Calculate parametric (variance-covariance) VaR."""
        mean = returns.mean()
        std = returns.std()

        var_dict = {}
        for conf_level in self.confidence_levels:
            # For 95% confidence, we want the 5th percentile (left tail)
            alpha = 1 - conf_level
            z_score = stats.norm.ppf(alpha)  # This gives negative z-score for left tail
            # VaR as positive loss value
            var = -(mean + z_score * std) * portfolio_value
            var_dict[str(conf_level)] = float(var)

            # Calculate CVaR (Expected Shortfall) - expected loss beyond VaR
            # Formula: CVaR = -μ + σ * φ(z) / α where φ is the PDF
            pdf_value = stats.norm.pdf(z_score)
            cvar = -(mean - std * pdf_value / alpha) * portfolio_value
            var_dict[f'cvar_{conf_level}'] = float(cvar)
        
        var_dict['mean_return'] = float(mean)
        var_dict['volatility'] = float(std)
        
        return var_dict
    
    def _historical_var(self, returns: pd.Series, portfolio_value: float) -> Dict:
        """Calculate historical simulation VaR."""
        var_dict = {}
        
        for conf_level in self.confidence_levels:
            var_percentile = (1 - conf_level) * 100
            var = -np.percentile(returns, var_percentile) * portfolio_value
            var_dict[str(conf_level)] = float(var)
            
            # Calculate CVaR (average of returns worse than VaR)
            threshold = np.percentile(returns, var_percentile)
            worse_returns = returns[returns <= threshold]
            cvar = -worse_returns.mean() * portfolio_value if len(worse_returns) > 0 else var
            var_dict[f'cvar_{conf_level}'] = float(cvar)
        
        # Add rolling VaR for time series
        if len(returns) > 60:  # Need at least 60 days
            var_dict['rolling_var'] = self._calculate_rolling_var(returns, portfolio_value)
        
        return var_dict
    
    def _monte_carlo_var(self, returns: pd.DataFrame, weights: np.ndarray,
                        portfolio_value: float, n_simulations: int = 10000) -> Dict:
        """Calculate Monte Carlo VaR."""
        # Calculate portfolio parameters
        portfolio_returns = returns @ weights
        mean = portfolio_returns.mean()
        std = portfolio_returns.std()

        # Generate simulations using same approach as montecarlo.py for consistency
        np.random.seed(42)  # For reproducibility
        simulated_returns = np.random.normal(mean, std, n_simulations)
        
        var_dict = {}
        for conf_level in self.confidence_levels:
            var_percentile = (1 - conf_level) * 100
            var = -np.percentile(simulated_returns, var_percentile) * portfolio_value
            var_dict[str(conf_level)] = float(var)
            
            # Calculate CVaR
            threshold = np.percentile(simulated_returns, var_percentile)
            worse_returns = simulated_returns[simulated_returns <= threshold]
            cvar = -worse_returns.mean() * portfolio_value if len(worse_returns) > 0 else var
            var_dict[f'cvar_{conf_level}'] = float(cvar)
        
        var_dict['n_simulations'] = n_simulations
        
        return var_dict
    
    def _calculate_rolling_var(self, returns: pd.Series, portfolio_value: float,
                             window: int = 60) -> Dict:
        """Calculate rolling VaR over time."""
        rolling_var = {}
        
        for conf_level in self.confidence_levels:
            var_series = []
            dates = []
            
            for i in range(window, len(returns)):
                window_returns = returns.iloc[i-window:i]
                var_percentile = (1 - conf_level) * 100
                var = -np.percentile(window_returns, var_percentile) * portfolio_value
                var_series.append(var)
                dates.append(returns.index[i])
            
            rolling_var[str(conf_level)] = var_series
            
        rolling_var['dates'] = dates
        return rolling_var
    
    def _backtest_var(self, returns: pd.Series, var_estimates: Dict,
                     portfolio_value: float) -> Dict:
        """Backtest VaR model using Kupiec and Christoffersen tests."""
        results = {}
        
        for method in ['historical', 'parametric']:
            if method not in var_estimates:
                continue
                
            method_results = {}
            
            for conf_level in self.confidence_levels:
                if str(conf_level) not in var_estimates.get(method, {}):
                    continue
                    
                var_value = var_estimates[method][str(conf_level)] / portfolio_value
                actual_losses = -returns
                violations = actual_losses > var_value
                
                n_violations = violations.sum()
                n_observations = len(returns)
                expected_violations = n_observations * (1 - conf_level)
                violation_rate = n_violations / n_observations
                
                # Kupiec test (unconditional coverage)
                if n_violations > 0:
                    lr_uc = -2 * np.log((1-conf_level)**n_violations * conf_level**(n_observations-n_violations)) + \
                            2 * np.log(violation_rate**n_violations * (1-violation_rate)**(n_observations-n_violations))
                    kupiec_pvalue = 1 - stats.chi2.cdf(lr_uc, 1)
                else:
                    kupiec_pvalue = 1.0
                
                method_results[str(conf_level)] = {
                    'breach_count': int(n_violations),
                    'expected_breaches': float(expected_violations),
                    'actual_breach_rate': float(violation_rate),
                    'expected_breach_rate': float(1 - conf_level),
                    'kupiec_pvalue': float(kupiec_pvalue),
                    'kupiec_result': 'Accept' if kupiec_pvalue > 0.05 else 'Reject'
                }
            
            results[method] = method_results
        
        return results