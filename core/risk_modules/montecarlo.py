# montecarlo.py
"""
Production Monte Carlo engine with correct risk metrics.
Key fixes: proper path generation, correct VaR/CVaR calculation.
"""
import os
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats
from core.visualization.risk_templates.montecarlo_visualizations import MonteCarloVisualizations
import logging

from core.utils.context_utils import get_cancel_event
from ..config import get_config
from ..constants import (
    TRADING_DAYS_PER_YEAR, DEFAULT_MC_SIMULATIONS, DEFAULT_MONTE_CARLO_HORIZON,
    CONFIDENCE_LEVELS, CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99, DEFAULT_RISK_FREE_RATE
)

logger = logging.getLogger(__name__)

class MonteCarloEngine:
    def __init__(self, 
                 n_simulations: int = None,
                 time_horizon: int = None,
                 confidence_levels: List[float] = None):
        config = get_config()
        self.n_sims = n_simulations or config.mc_simulations
        self.horizon = time_horizon or config.mc_time_horizon
        self.time_horizon = self.horizon  # Backward compatibility
        self.confidence_levels = confidence_levels or CONFIDENCE_LEVELS
    
    def _check_cancelled(self, operation: str = "operation") -> None:
        """Check if cancellation was requested and raise if so.
        
        Call this periodically in long-running loops to allow cancellation.
        """
        cancel_event = get_cancel_event()
        if cancel_event and cancel_event.is_set():
            logger.info(f"[CANCEL] Monte Carlo {operation} cancelled by user")
            raise asyncio.CancelledError(f"Monte Carlo {operation} cancelled by user")
        
    def parametric_var(self, 
                      returns: pd.DataFrame, 
                      weights: np.ndarray,
                      portfolio_value: float,
                      method: str = 'normal') -> Dict:
        """
        Analytical VaR calculation - fast and suitable for liquid portfolios.
        """
        # Portfolio returns
        portfolio_returns = returns @ weights
        
        # Calculate moments
        daily_mean = portfolio_returns.mean()
        daily_vol = portfolio_returns.std()
        
        # Scale to horizon
        horizon_mean = daily_mean * self.horizon
        horizon_vol = daily_vol * np.sqrt(self.horizon)
        
        # Get risk-free rate from environment
        risk_free_rate = float(os.getenv('RISK_FREE_RATE', DEFAULT_RISK_FREE_RATE))
        
        # Calculate annualized metrics
        annual_return = daily_mean * TRADING_DAYS_PER_YEAR
        annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
        
        # Calculate Sharpe ratio
        sharpe_ratio = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
        
        results = {
            'daily_vol': daily_vol,
            'annual_vol': annual_vol,
            'expected_return': annual_return,
            'sharpe_ratio': sharpe_ratio
        }
        
        if method == 'normal':
            # Normal VaR
            for conf in self.confidence_levels:
                # For 95% confidence, we want the 5th percentile (left tail)
                alpha = 1 - conf
                z_score = stats.norm.ppf(alpha)
                # VaR as percentage loss over the horizon
                # Since z_score is negative for left tail, this gives us positive VaR for losses
                var_pct = -(horizon_mean + z_score * horizon_vol)
                # Convert VaR to dollar amount
                var_dollars = var_pct * portfolio_value
                # CVaR as percentage (expected loss beyond VaR)
                # CVaR = -E[R|R < -VaR] = -(μ - σ * φ(z) / α)
                # where φ(z) is the PDF and α = 1 - conf
                cvar_pct = -(horizon_mean - horizon_vol * stats.norm.pdf(z_score) / alpha)
                
                results[f'VaR_{conf}'] = var_dollars  # Dollar amount
                results[f'CVaR_{conf}'] = cvar_pct    # Percentage
                
        elif method == 'cornish-fisher':
            # Adjusted for skewness and kurtosis
            skew = portfolio_returns.skew()
            kurt = portfolio_returns.kurtosis()
            
            for conf in self.confidence_levels:
                # For left tail (losses)
                alpha = 1 - conf
                z = stats.norm.ppf(alpha)
                
                # Cornish-Fisher expansion
                z_cf = z + (z**2 - 1) * skew / 6 + \
                       (z**3 - 3*z) * (kurt - 3) / 24 - \
                       (2*z**3 - 5*z) * skew**2 / 36
                
                var_pct = -(horizon_mean + z_cf * horizon_vol)
                var_dollars = var_pct * portfolio_value
                
                # CVaR using Cornish-Fisher expansion
                # For non-normal distributions, approximate CVaR
                # using the conditional expectation beyond VaR threshold
                pdf_z = stats.norm.pdf(z)
                cvar_pct = -(horizon_mean - horizon_vol * pdf_z / alpha * 
                            (1 + skew/6 * (z**2 - 1) + (kurt-3)/24 * (z**3 - 3*z)))
                
                results[f'VaR_{conf}'] = var_dollars  # Dollar amount
                results[f'CVaR_{conf}'] = cvar_pct    # Percentage
        
        return results
    
    def historical_simulation(self, 
                            returns: pd.DataFrame, 
                            weights: np.ndarray,
                            portfolio_value: float) -> Dict:
        """
        Historical simulation with proper bootstrap.
        Best for capturing empirical return distribution.
        """
        # Portfolio returns
        portfolio_returns = returns @ weights
        n_historical = len(portfolio_returns)
        
        # Check if we have enough data
        if n_historical < int(os.getenv('TRADING_DAYS', 252)):
            logger.warning("Less than 1 year of data for historical simulation")
        
        # Generate paths using block bootstrap
        block_size = min(20, n_historical // 10)  # Preserve autocorrelation
        n_blocks = (self.horizon // block_size) + 1
        
        final_returns = np.zeros(self.n_sims)
        
        for sim in range(self.n_sims):
            # ✅ CHECK CANCELLATION periodically (every 100 sims)
            if sim % 100 == 0:
                self._check_cancelled(f"historical simulation {sim}/{self.n_sims}")
            
            path_returns = []
            
            for _ in range(n_blocks):
                # Random block start
                start_idx = np.random.randint(0, n_historical - block_size)
                block = portfolio_returns.iloc[start_idx:start_idx + block_size].values
                path_returns.extend(block)
            
            # Trim to exact horizon
            path_returns = np.array(path_returns[:self.horizon])
            
            # Compound returns for the period
            final_returns[sim] = np.prod(1 + path_returns) - 1
        
        # Calculate risk metrics
        results = self._calculate_var_cvar(final_returns, portfolio_value)
        results['method'] = 'historical'
        results['n_observations'] = n_historical
        
        return results
    
    def monte_carlo_simulation(self, 
                             returns: pd.DataFrame, 
                             weights: np.ndarray,
                             portfolio_value: float,
                             use_t_dist: bool = True) -> Dict:
        """
        Full Monte Carlo simulation with Student-t distribution option.
        """
        # Portfolio parameters
        portfolio_returns = returns @ weights
        daily_mean = portfolio_returns.mean()
        daily_vol = portfolio_returns.std()
        
        # Fit distribution and get parameters for simulation
        df = None
        t_loc = daily_mean
        t_scale = daily_vol
        
        if use_t_dist:
            # Fit Student-t distribution for fat tails
            params = stats.t.fit(portfolio_returns)
            df, t_loc, t_scale = params
            logger.info(f"Fitted t-distribution with df={df:.2f}, loc={t_loc:.6f}, scale={t_scale:.6f}")
        
        # Generate paths
        final_values = np.zeros(self.n_sims)
        
        for sim in range(self.n_sims):
            # ✅ CHECK CANCELLATION periodically (every 100 sims)
            if sim % 100 == 0:
                self._check_cancelled(f"MC simulation {sim}/{self.n_sims}")
            
            path_value = 1.0
            
            for t in range(self.horizon):
                if use_t_dist and df is not None and df < 30:  # Use t-dist only if significantly different from normal
                    # Use the fitted t-distribution parameters
                    daily_return = stats.t.rvs(df, loc=t_loc, scale=t_scale)
                else:
                    daily_return = np.random.normal(daily_mean, daily_vol)
                
                # Cap extreme daily returns to prevent unrealistic compounding

                
                path_value *= (1 + daily_return)
            
            final_values[sim] = path_value
        
        # Convert to returns
        final_returns = final_values - 1
        
        # Calculate metrics
        results = self._calculate_var_cvar(final_returns, portfolio_value)
        results['distribution'] = 't-dist' if use_t_dist else 'normal'
        
        # Add path statistics
        results['paths'] = {
            'min': np.min(final_values),
            'max': np.max(final_values),
            'median': np.median(final_values),
            'mean': np.mean(final_values)
        }
        
        return results
    
    def factor_based_simulation(self,
                              returns: pd.DataFrame,
                              weights: np.ndarray,
                              portfolio_value: float,
                              barra_model,
                              stressed_factors: Optional[Dict[str, float]] = None) -> Dict:
        """
        Factor-based Monte Carlo with optional stress scenarios.
        Most sophisticated approach for factor-driven portfolios.
        """
        if not hasattr(barra_model, 'factor_exposures') or barra_model.factor_exposures is None:
            raise ValueError("Barra model must be fitted first")
        
        # Portfolio factor exposures
        portfolio_betas = barra_model.factor_exposures.T @ weights
        
        # Factor covariance
        factor_cov = barra_model.factor_covariance.values
        n_factors = len(factor_cov)
        
        # Specific risk
        specific_risks = barra_model.specific_risk.values
        portfolio_specific_risk = np.sqrt(np.sum((weights ** 2) * (specific_risks ** 2)))
        
        # Cholesky decomposition for correlated factor draws
        try:
            L = np.linalg.cholesky(factor_cov)
        except np.linalg.LinAlgError:
            # If not positive definite, add small diagonal
            factor_cov += np.eye(n_factors) * 1e-6
            L = np.linalg.cholesky(factor_cov)
        
        # Daily scaling
        trading_days = int(os.getenv('TRADING_DAYS', 252))
        daily_L = L / np.sqrt(trading_days)
        daily_specific_vol = portfolio_specific_risk / np.sqrt(trading_days)
        
        # Simulate
        final_values = np.zeros(self.n_sims)
        
        for sim in range(self.n_sims):
            # ✅ CHECK CANCELLATION periodically (every 100 sims)
            if sim % 100 == 0:
                self._check_cancelled(f"factor simulation {sim}/{self.n_sims}")
            
            path_value = 1.0
            
            for t in range(self.horizon):
                # Generate factor returns
                if t == 0 and stressed_factors:
                    # Apply stress on first day
                    factor_returns = np.array([
                        stressed_factors.get(factor, 0) 
                        for factor in barra_model.factor_covariance.columns
                    ])
                else:
                    # Normal factor returns (correlated)
                    z = np.random.standard_normal(n_factors)
                    factor_returns = daily_L @ z
                
                # Portfolio return = factor return + specific return
                factor_contribution = portfolio_betas @ factor_returns
                specific_return = np.random.normal(0, daily_specific_vol)
                
                daily_return = factor_contribution + specific_return
                path_value *= (1 + daily_return)
            
            final_values[sim] = path_value
        
        # Calculate metrics
        final_returns = final_values - 1
        results = self._calculate_var_cvar(final_returns, portfolio_value)
        
        # Add factor attribution
        results['risk_attribution'] = {
            'systematic': np.sqrt(portfolio_betas @ factor_cov @ portfolio_betas) / np.sqrt(int(os.getenv('TRADING_DAYS', 252))),
            'idiosyncratic': portfolio_specific_risk
        }
        
        if stressed_factors:
            results['stress_scenario'] = stressed_factors
        
        return results
    
    # Individual HMM features - fully granular selection
    HMM_FEATURES = {
        # === VOLATILITY FEATURES ===
        'return_squared': {
            'description': 'Squared daily returns (variance proxy)',
            'category': 'volatility',
            'lookback': 0
        },
        'abs_return': {
            'description': 'Absolute daily returns',
            'category': 'volatility', 
            'lookback': 0
        },
        'rolling_vol_5d': {
            'description': '5-day rolling standard deviation',
            'category': 'volatility',
            'lookback': 5
        },
        'rolling_vol_10d': {
            'description': '10-day rolling standard deviation',
            'category': 'volatility',
            'lookback': 10
        },
        'rolling_vol_20d': {
            'description': '20-day rolling standard deviation',
            'category': 'volatility',
            'lookback': 20
        },
        'rolling_vol_60d': {
            'description': '60-day (quarterly) rolling standard deviation',
            'category': 'volatility',
            'lookback': 60
        },
        'vol_ratio_5_20': {
            'description': 'Ratio of 5d vol to 20d vol (vol regime change detector)',
            'category': 'volatility',
            'lookback': 20
        },
        # === MOMENTUM FEATURES ===
        'return_lag1': {
            'description': '1-day lagged return (autocorrelation)',
            'category': 'momentum',
            'lookback': 1
        },
        'return_lag2': {
            'description': '2-day lagged return',
            'category': 'momentum',
            'lookback': 2
        },
        'return_lag5': {
            'description': '5-day lagged return',
            'category': 'momentum',
            'lookback': 5
        },
        'cum_return_5d': {
            'description': '5-day cumulative return (weekly momentum)',
            'category': 'momentum',
            'lookback': 5
        },
        'cum_return_10d': {
            'description': '10-day cumulative return (bi-weekly momentum)',
            'category': 'momentum',
            'lookback': 10
        },
        'cum_return_20d': {
            'description': '20-day cumulative return (monthly momentum)',
            'category': 'momentum',
            'lookback': 20
        },
        'cum_return_60d': {
            'description': '60-day cumulative return (quarterly momentum)',
            'category': 'momentum',
            'lookback': 60
        },
        'ma_crossover_5_20': {
            'description': '5d MA minus 20d MA (trend signal)',
            'category': 'momentum',
            'lookback': 20
        },
        # === MEAN REVERSION FEATURES ===
        'zscore_5d': {
            'description': 'Z-score from 5-day moving average',
            'category': 'mean_reversion',
            'lookback': 5
        },
        'zscore_10d': {
            'description': 'Z-score from 10-day moving average',
            'category': 'mean_reversion',
            'lookback': 10
        },
        'zscore_20d': {
            'description': 'Z-score from 20-day moving average',
            'category': 'mean_reversion',
            'lookback': 20
        },
        'distance_from_high_20d': {
            'description': 'Distance from 20-day rolling max (drawdown proxy)',
            'category': 'mean_reversion',
            'lookback': 20
        },
        # === HIGHER ORDER FEATURES ===
        'skewness_20d': {
            'description': '20-day rolling skewness',
            'category': 'higher_order',
            'lookback': 20
        },
        'kurtosis_20d': {
            'description': '20-day rolling kurtosis (tail risk)',
            'category': 'higher_order',
            'lookback': 20
        },
    }
    
    # Preset feature combinations
    HMM_FEATURE_PRESETS = {
        'minimal': ['return_squared'],  # Just add variance proxy
        'volatility': ['return_squared', 'abs_return', 'rolling_vol_5d', 'rolling_vol_20d', 'vol_ratio_5_20'],
        'momentum': ['return_lag1', 'cum_return_5d', 'cum_return_20d', 'ma_crossover_5_20'],
        'mean_reversion': ['zscore_5d', 'zscore_20d', 'distance_from_high_20d'],
        'higher_order': ['skewness_20d', 'kurtosis_20d'],
        'standard': ['return_squared', 'rolling_vol_20d', 'cum_return_20d', 'zscore_20d'],  # Balanced default
        'full': list(HMM_FEATURES.keys()),  # Everything
    }
    
    def _build_hmm_features(self, 
                            portfolio_returns: np.ndarray,
                            features: List[str]) -> Tuple[np.ndarray, List[str]]:
        """
        Build feature matrix for HMM based on selected individual features.
        
        Args:
            portfolio_returns: Array of daily portfolio returns
            features: List of feature names from HMM_FEATURES or preset names
            
        Returns:
            features: ndarray of shape (n_obs, n_features)
            feature_names: list of feature names for interpretability
        """
        ret = portfolio_returns.flatten()
        ret_series = pd.Series(ret)
        n_obs = len(ret)
        
        feature_arrays = []
        feature_names = []
        
        # Returns is always included as first feature (needed for simulation)
        feature_arrays.append(ret)
        feature_names.append('return')
        
        # Expand presets to individual features
        expanded_features = []
        for f in features:
            if f in self.HMM_FEATURE_PRESETS:
                expanded_features.extend(self.HMM_FEATURE_PRESETS[f])
            elif f in self.HMM_FEATURES:
                expanded_features.append(f)
            elif f == 'all':
                expanded_features.extend(self.HMM_FEATURES.keys())
        
        # Remove duplicates while preserving order
        seen = set()
        expanded_features = [f for f in expanded_features if not (f in seen or seen.add(f))]
        
        # Build each feature
        for feat_name in expanded_features:
            if feat_name not in self.HMM_FEATURES:
                logger.warning(f"Unknown HMM feature: {feat_name}, skipping")
                continue
                
            feat_info = self.HMM_FEATURES[feat_name]
            
            try:
                # === VOLATILITY FEATURES ===
                if feat_name == 'return_squared':
                    arr = ret ** 2
                elif feat_name == 'abs_return':
                    arr = np.abs(ret)
                elif feat_name == 'rolling_vol_5d':
                    arr = ret_series.rolling(5, min_periods=2).std().bfill().values
                elif feat_name == 'rolling_vol_10d':
                    arr = ret_series.rolling(10, min_periods=3).std().bfill().values
                elif feat_name == 'rolling_vol_20d':
                    arr = ret_series.rolling(20, min_periods=5).std().bfill().values
                elif feat_name == 'rolling_vol_60d':
                    arr = ret_series.rolling(60, min_periods=10).std().bfill().values
                elif feat_name == 'vol_ratio_5_20':
                    vol_5 = ret_series.rolling(5, min_periods=2).std().bfill()
                    vol_20 = ret_series.rolling(20, min_periods=5).std().bfill()
                    arr = (vol_5 / vol_20.replace(0, 1)).fillna(1).values
                    
                # === MOMENTUM FEATURES ===
                elif feat_name == 'return_lag1':
                    arr = np.roll(ret, 1); arr[0] = 0
                elif feat_name == 'return_lag2':
                    arr = np.roll(ret, 2); arr[:2] = 0
                elif feat_name == 'return_lag5':
                    arr = np.roll(ret, 5); arr[:5] = 0
                elif feat_name == 'cum_return_5d':
                    arr = ret_series.rolling(5, min_periods=1).sum().values
                elif feat_name == 'cum_return_10d':
                    arr = ret_series.rolling(10, min_periods=1).sum().values
                elif feat_name == 'cum_return_20d':
                    arr = ret_series.rolling(20, min_periods=1).sum().values
                elif feat_name == 'cum_return_60d':
                    arr = ret_series.rolling(60, min_periods=1).sum().values
                elif feat_name == 'ma_crossover_5_20':
                    ma_5 = ret_series.rolling(5, min_periods=2).mean().bfill()
                    ma_20 = ret_series.rolling(20, min_periods=5).mean().bfill()
                    arr = (ma_5 - ma_20).fillna(0).values
                    
                # === MEAN REVERSION FEATURES ===
                elif feat_name == 'zscore_5d':
                    ma = ret_series.rolling(5, min_periods=2).mean().bfill()
                    std = ret_series.rolling(5, min_periods=2).std().bfill()
                    arr = ((ret_series - ma) / std.replace(0, 1)).fillna(0).values
                elif feat_name == 'zscore_10d':
                    ma = ret_series.rolling(10, min_periods=3).mean().bfill()
                    std = ret_series.rolling(10, min_periods=3).std().bfill()
                    arr = ((ret_series - ma) / std.replace(0, 1)).fillna(0).values
                elif feat_name == 'zscore_20d':
                    ma = ret_series.rolling(20, min_periods=5).mean().bfill()
                    std = ret_series.rolling(20, min_periods=5).std().bfill()
                    arr = ((ret_series - ma) / std.replace(0, 1)).fillna(0).values
                elif feat_name == 'distance_from_high_20d':
                    # Use cumulative return for "price-like" behavior
                    cum_ret = (1 + ret_series).cumprod()
                    rolling_max = cum_ret.rolling(20, min_periods=1).max()
                    arr = ((cum_ret - rolling_max) / rolling_max.replace(0, 1)).fillna(0).values
                    
                # === HIGHER ORDER FEATURES ===
                elif feat_name == 'skewness_20d':
                    arr = ret_series.rolling(20, min_periods=10).skew().bfill().fillna(0).values
                elif feat_name == 'kurtosis_20d':
                    arr = ret_series.rolling(20, min_periods=10).kurt().bfill().fillna(0).values
                else:
                    logger.warning(f"Feature {feat_name} not implemented, skipping")
                    continue
                
                feature_arrays.append(arr)
                feature_names.append(feat_name)
                
            except Exception as e:
                logger.warning(f"Error computing feature {feat_name}: {e}, skipping")
                continue
        
        # Stack features into matrix
        feature_matrix = np.column_stack(feature_arrays)
        
        # Handle any NaN/inf values
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=0.0, neginf=0.0)
        
        return feature_matrix, feature_names
    
    def hmm_simulation(self,
                       returns: pd.DataFrame,
                       weights: np.ndarray,
                       portfolio_value: float,
                       n_regimes: int = 3,
                       hmm_features: Optional[List[str]] = None,
                       hmm_n_iter: int = 200,
                       hmm_n_init: int = 10,
                       hmm_covariance_type: str = "full",
                       hmm_tol: float = 1e-4) -> Dict:
        """
        HMM regime-switching Monte Carlo simulation with granular feature selection.
        
        Fits a Gaussian Hidden Markov Model using selected features to identify
        market regimes, then samples regime transitions during path generation.
        
        INDIVIDUAL FEATURES (pick any combination):
        
        Volatility:
          - return_squared: Squared returns (variance proxy)
          - abs_return: Absolute returns
          - rolling_vol_5d/10d/20d/60d: Rolling standard deviation
          - vol_ratio_5_20: 5d/20d vol ratio (regime change detector)
        
        Momentum:
          - return_lag1/lag2/lag5: Lagged returns
          - cum_return_5d/10d/20d/60d: Cumulative returns
          - ma_crossover_5_20: MA trend signal
        
        Mean Reversion:
          - zscore_5d/10d/20d: Z-score from moving average
          - distance_from_high_20d: Drawdown proxy
        
        Higher Order:
          - skewness_20d: Rolling skewness
          - kurtosis_20d: Rolling kurtosis (tail risk)
        
        PRESETS (for convenience):
          - 'minimal': Just return_squared
          - 'volatility': All volatility features
          - 'momentum': All momentum features  
          - 'mean_reversion': All mean reversion features
          - 'higher_order': Skewness + kurtosis
          - 'standard': Balanced mix (return_squared, rolling_vol_20d, cum_return_20d, zscore_20d)
          - 'full' or 'all': Everything
        
        Args:
            returns: DataFrame of asset returns
            weights: Portfolio weights
            portfolio_value: Total portfolio value in dollars
            n_regimes: Number of regimes (2-5). 
                      GUIDANCE: 
                        - 2 regimes: Most robust, captures bull/bear or low/high vol
                        - 3 regimes: Good balance, adds a "transition" regime
                        - 4-5 regimes: Risk of overfitting unless you have 3+ years of data
                      Rule of thumb: Need ~100+ days per regime for stable estimates
            hmm_features: List of individual feature names or preset names
                         Default: None (univariate - returns only, fastest)
                         Examples:
                           ['return_squared', 'rolling_vol_20d']  # Specific features
                           ['volatility']  # Use volatility preset
                           ['standard']  # Use standard preset
                           ['volatility', 'zscore_20d']  # Mix preset + specific
                           ['all']  # Everything
            hmm_n_iter: Max EM iterations per initialization (default: 200)
                       Higher = more likely to converge, but slower
            hmm_n_init: Number of random initializations (default: 10)
                       Higher = better chance of finding global optimum
                       Set to 1 for speed, 20+ for robustness
            hmm_covariance_type: Covariance matrix structure (default: "full")
                       - "full": Each regime has its own full covariance (most flexible)
                       - "tied": All regimes share same covariance (reduces overfitting)
                       - "diag": Diagonal covariance only (faster, assumes independence)
                       - "spherical": Single variance per regime (most constrained)
            hmm_tol: Convergence tolerance (default: 1e-4)
                    Lower = stricter convergence, higher quality fit
            
        Returns:
            Dict with VaR/CVaR metrics, regime parameters, current regime,
            transition matrix, and feature info
        """
        from hmmlearn.hmm import GaussianHMM
        
        # Clamp n_regimes to valid range
        n_regimes = min(max(n_regimes, 2), 5)
        
        # Calculate portfolio returns
        portfolio_returns = (returns @ weights).values.reshape(-1, 1)
        
        # =====================================================================
        # WINSORIZE EXTREME RETURNS TO PREVENT OUTLIER-DRIVEN REGIMES
        # =====================================================================
        # Clip returns to percentile bounds to prevent extreme days from dominating.
        # Using 1st/99th percentile is more robust than σ-based for fat-tailed returns.
        lower_pct = np.percentile(portfolio_returns, 1)
        upper_pct = np.percentile(portfolio_returns, 99)
        
        n_clipped = int(np.sum((portfolio_returns < lower_pct) | (portfolio_returns > upper_pct)))
        if n_clipped > 0:
            logger.info(f"Winsorizing {n_clipped} extreme returns to 1st-99th percentile "
                       f"[{lower_pct*100:.2f}%, {upper_pct*100:.2f}%]")
            portfolio_returns = np.clip(portfolio_returns, lower_pct, upper_pct)
        
        # Build feature matrix (handles None, presets, individual features)
        if hmm_features is None:
            hmm_features = []  # Empty = just returns (univariate)
        elif isinstance(hmm_features, str):
            hmm_features = [hmm_features]
        
        feature_matrix, feature_names = self._build_hmm_features(portfolio_returns, hmm_features)
        n_features = feature_matrix.shape[1]
        
        logger.info(f"HMM fitting with {n_features} features: {feature_names}")
        if hmm_features:
            logger.info(f"Requested features/presets: {hmm_features}")
        
        # =====================================================================
        # FIT HMM WITH CONFIGURABLE PARAMETERS
        # =====================================================================
        # Use multiple random initializations and pick the best (highest log-likelihood)
        best_model = None
        best_score = float('-inf')
        convergence_info = []
        
        n_samples = feature_matrix.shape[0]
        logger.info(f"Fitting HMM: {n_regimes} regimes, {n_features} features, {n_samples} samples")
        logger.info(f"HMM params: n_init={hmm_n_init}, n_iter={hmm_n_iter}, cov_type={hmm_covariance_type}, tol={hmm_tol}")
        
        for init in range(hmm_n_init):
            # ✅ CHECK CANCELLATION between initializations
            self._check_cancelled(f"HMM init {init + 1}/{hmm_n_init}")
            
            try:
                model = GaussianHMM(
                    n_components=n_regimes,
                    covariance_type=hmm_covariance_type,
                    n_iter=hmm_n_iter,
                    tol=hmm_tol,
                    random_state=42 + init,  # Different seed each init
                    init_params="stmc",      # Initialize all params (startprob, transmat, means, covars)
                    params="stmc",           # Update all params during training
                )
                model.fit(feature_matrix)
                score = model.score(feature_matrix)  # Log-likelihood
                
                convergence_info.append({
                    'init': init,
                    'converged': model.monitor_.converged,
                    'n_iter': model.monitor_.iter,
                    'log_likelihood': float(score)
                })
                
                if score > best_score:
                    best_score = score
                    best_model = model
                    
            except Exception as e:
                logger.debug(f"HMM init {init} failed: {e}")
                continue
        
        if best_model is None:
            raise ValueError("HMM fitting failed on all initializations")
        
        model = best_model
        
        # =====================================================================
        # MODEL DIAGNOSTICS
        # =====================================================================
        log_likelihood = best_score
        n_params = n_regimes * n_features + n_regimes * n_features * (n_features + 1) // 2 + n_regimes * (n_regimes - 1)
        # AIC = -2 * log_likelihood + 2 * n_params
        # BIC = -2 * log_likelihood + n_params * log(n_samples)
        aic = -2 * log_likelihood + 2 * n_params
        bic = -2 * log_likelihood + n_params * np.log(n_samples)
        
        # Per-regime sample sizes (how many days assigned to each regime)
        regime_sequence_full = model.predict(feature_matrix)
        regime_counts = [int(np.sum(regime_sequence_full == i)) for i in range(n_regimes)]
        min_regime_samples = min(regime_counts)
        
        # =====================================================================
        # DEGENERATE FIT CHECK: If any regime has < 20 samples, fall back to single regime
        # =====================================================================
        MIN_REGIME_SAMPLES = 20
        if min_regime_samples < MIN_REGIME_SAMPLES:
            logger.warning(f"HMM fit degenerate: regime with only {min_regime_samples} samples. "
                          f"Falling back to standard Monte Carlo (single regime).")
            # Return standard Monte Carlo results instead
            return self.monte_carlo_simulation(
                returns=returns,
                weights=weights,
                portfolio_value=portfolio_value
            )
        
        # Convergence summary
        n_converged = sum(1 for c in convergence_info if c['converged'])
        
        model_diagnostics = {
            'log_likelihood': float(log_likelihood),
            'aic': float(aic),
            'bic': float(bic),
            'n_params': n_params,
            'n_samples': n_samples,
            'n_features': n_features,
            'n_regimes': n_regimes,
            'samples_per_regime': regime_counts,
            'min_samples_per_regime': min_regime_samples,
            'n_initializations': hmm_n_init,
            'n_converged': n_converged,
            'best_init_log_likelihood': float(best_score),
            'convergence_details': convergence_info,
            'model_converged': model.monitor_.converged,
            'model_iterations': model.monitor_.iter,
            # Record the parameters used
            'hmm_params': {
                'n_iter': hmm_n_iter,
                'n_init': hmm_n_init,
                'covariance_type': hmm_covariance_type,
                'tol': hmm_tol
            }
        }
        
        # Quality assessment
        quality_issues = []
        if min_regime_samples < 20:
            quality_issues.append(f"Low samples in smallest regime ({min_regime_samples}). Risk of overfitting.")
        if not model.monitor_.converged:
            quality_issues.append("Model did not converge. Results may be unstable.")
        if n_samples / n_regimes < 50:
            quality_issues.append(f"Insufficient data ({n_samples} samples for {n_regimes} regimes). Need ~50+ per regime.")
        
        model_diagnostics['quality_issues'] = quality_issues
        model_diagnostics['quality_score'] = 'good' if not quality_issues else ('fair' if len(quality_issues) == 1 else 'poor')
        
        logger.info(f"HMM fit complete: LL={log_likelihood:.1f}, AIC={aic:.1f}, BIC={bic:.1f}, "
                   f"converged={model.monitor_.converged}, regime_counts={regime_counts}")
        
        # =====================================================================
        # EXTRACT REGIME PARAMETERS
        # =====================================================================
        # For multivariate HMM, means_ is (n_regimes, n_features), covars_ is (n_regimes, n_features, n_features)
        if n_features == 1:
            # Univariate case
            means = model.means_.flatten()
            stds = np.sqrt(model.covars_.flatten())
        else:
            # Multivariate case - extract returns dimension (index 0)
            means = model.means_[:, 0]  # Mean return for each regime
            stds = np.sqrt(model.covars_[:, 0, 0])  # Std of returns for each regime
        
        logger.info(f"Regime return distributions (daily):")
        extreme_regime_warning = False
        for i in range(n_regimes):
            daily_mean_pct = means[i] * 100
            daily_std_pct = stds[i] * 100
            samples_in_regime = regime_counts[i]
            # Warn if daily mean exceeds ±0.3% (roughly ±75%/yr) - likely overfitting
            if abs(means[i]) > 0.003:
                logger.warning(f"  Regime {i}: mean={daily_mean_pct:.4f}%/day, std={daily_std_pct:.4f}%, n={samples_in_regime} ⚠️ EXTREME")
                extreme_regime_warning = True
            else:
                logger.info(f"  Regime {i}: mean={daily_mean_pct:.4f}%/day, std={daily_std_pct:.4f}%, n={samples_in_regime}")
        
        if extreme_regime_warning:
            quality_issues.append("Extreme regime means detected (>0.3%/day). Likely overfitting.")
            logger.warning(f"⚠️ Detected extreme regime parameters. With {n_regimes} regimes, the HMM may be "
                          f"overfitting to noise. Consider using fewer regimes (2-3) for more robust results.")
        
        # 2D regime classification using ABSOLUTE thresholds (not relative percentiles)
        # Direction based on sign of mean return, intensity based on volatility level
        
        def classify_regime_2d(mean_daily: float, std_daily: float) -> str:
            """
            Classify regime using absolute economic thresholds.
            
            Direction (based on daily mean):
            - mean > +0.0005 (+0.05%/day ≈ +12.6%/yr): bull
            - mean < -0.0005 (-0.05%/day ≈ -12.6%/yr): bear  
            - otherwise: neutral
            
            Intensity (based on daily volatility):
            - std > 0.025 (2.5%/day ≈ 40%/yr vol): volatile/crisis
            - std < 0.008 (0.8%/day ≈ 12%/yr vol): calm
            - otherwise: normal
            """
            # Direction: absolute sign-based (not relative ranking)
            if mean_daily > 0.0005:  # +0.05%/day ≈ +12.6%/yr
                direction = "bull"
            elif mean_daily < -0.0005:  # -0.05%/day ≈ -12.6%/yr
                direction = "bear"
            else:
                direction = "neutral"
            
            # Intensity: absolute volatility thresholds
            # Typical daily vol: SPY ≈ 1%, high vol regime ≈ 2-3%+
            if std_daily > 0.025:  # 2.5%/day ≈ 40% annual vol = high volatility
                intensity = "volatile"
            elif std_daily < 0.008:  # 0.8%/day ≈ 12% annual vol = calm
                intensity = "calm"
            else:
                intensity = "normal"
            
            # Special case labels for extreme combinations
            if direction == "bear" and intensity == "volatile":
                return "crisis"
            if direction == "bull" and intensity == "volatile":
                return "euphoria"
            
            # Combine direction and intensity
            if intensity == "normal":
                return direction  # Just "bull", "bear", "neutral"
            else:
                return f"{direction}_{intensity}"  # "bull_calm", "neutral_calm", etc.
        
        # Classify each regime using absolute thresholds
        regime_labels_raw = []
        for i in range(n_regimes):
            label = classify_regime_2d(means[i], stds[i])  # Absolute classification
            regime_labels_raw.append((i, label, means[i], stds[i]))
        
        # Sort by Sharpe ratio (economic quality) - best first for intuitive ordering
        sharpes = means / stds
        sorted_idx = np.argsort(sharpes)[::-1]  # Descending by Sharpe
        
        # Build final labels in sorted order
        labels = [regime_labels_raw[idx][1] for idx in sorted_idx]
        
        # Handle duplicate labels by adding suffix
        label_counts = {}
        final_labels = []
        for label in labels:
            if label in label_counts:
                label_counts[label] += 1
                final_labels.append(f"{label}_{label_counts[label]}")
            else:
                label_counts[label] = 1
                final_labels.append(label)
        labels = final_labels
        
        # Use the regime sequence we already computed for diagnostics
        regime_sequence = regime_sequence_full
        
        # Build regime params with full statistics
        regime_params = {}
        idx_to_label = {}
        for rank, idx in enumerate(sorted_idx):
            label = labels[rank]
            idx_to_label[idx] = label
            
            # Calculate regime frequency
            frequency = float(np.mean(regime_sequence == idx))
            
            # Daily Sharpe for regime (annualized would be * sqrt(252))
            daily_sharpe = float(means[idx] / stds[idx]) if stds[idx] > 0 else 0.0
            
            # Determine direction and intensity for clarity
            mean_val = float(means[idx])
            std_val = float(stds[idx])
            direction = "bullish" if mean_val > 0.0001 else "bearish" if mean_val < -0.0001 else "flat"
            
            # PROPER compounding for annualized return: (1 + r_daily)^252 - 1
            # No artificial caps - show the true mathematical result
            annualized_return = (1 + mean_val) ** TRADING_DAYS_PER_YEAR - 1
            
            # Volatility annualization is sqrt(252) * daily_vol (correct)
            annualized_vol = std_val * np.sqrt(TRADING_DAYS_PER_YEAR)
            
            # Annualized Sharpe = annualized_return / annualized_vol (proper ratio)
            sharpe_annual = annualized_return / annualized_vol if annualized_vol > 0 else 0.0
            
            regime_params[label] = {
                'mean_daily': mean_val,
                'mean_daily_pct': mean_val * 100,  # Daily return in %
                'mean_annualized': float(annualized_return),
                'mean_annualized_pct': float(annualized_return * 100),  # Annual return in %
                'std_daily': std_val,
                'std_daily_pct': std_val * 100,  # Daily vol in %
                'vol_annualized': float(annualized_vol),
                'vol_annualized_pct': float(annualized_vol * 100),  # Annual vol in %
                'sharpe_daily': daily_sharpe,
                'sharpe_annualized': float(sharpe_annual),
                'frequency': frequency,
                'frequency_pct': frequency * 100,  # Frequency in %
                'direction': direction,
                'expected_days_per_year': int(frequency * TRADING_DAYS_PER_YEAR)
            }
        
        # Identify current regime (last observation)
        current_regime_idx = regime_sequence[-1]
        current_regime = idx_to_label[current_regime_idx]
        
        # Reorder transition matrix to match vol-sorted labels
        raw_transmat = model.transmat_
        sorted_transmat = np.zeros_like(raw_transmat)
        for i, from_idx in enumerate(sorted_idx):
            for j, to_idx in enumerate(sorted_idx):
                sorted_transmat[i, j] = raw_transmat[from_idx, to_idx]
        
        logger.info(f"Fitted HMM with {n_regimes} regimes. Current regime: {current_regime}")
        for label, params in regime_params.items():
            logger.info(f"  {label} ({params['direction']}): "
                       f"daily={params['mean_daily_pct']:.3f}%/day, "
                       f"annual={params['mean_annualized_pct']:.1f}%/yr (compounded), "
                       f"vol={params['vol_annualized_pct']:.1f}%/yr, "
                       f"sharpe={params['sharpe_annualized']:.2f}, "
                       f"freq={params['frequency_pct']:.1f}% (~{params['expected_days_per_year']}d/yr)")
        
        # Simulate paths using fitted model
        # Each simulation uses a different random state to ensure path diversity
        final_values = np.zeros(self.n_sims)
        
        # Store sample paths for charting (subset to keep memory reasonable)
        n_chart_paths = min(512, self.n_sims)
        chart_paths = np.zeros((n_chart_paths, self.horizon + 1))
        chart_paths[:, 0] = portfolio_value  # Initial value
        
        for sim in range(self.n_sims):
            # ✅ CHECK CANCELLATION periodically (every 100 sims)
            if sim % 100 == 0:
                self._check_cancelled(f"HMM simulation {sim}/{self.n_sims}")
            
            # Pass unique random_state per simulation for diverse paths
            samples, _ = model.sample(self.horizon, random_state=sim)
            
            # Extract only returns column (index 0) for path simulation
            # Other features were only used for regime detection
            if n_features == 1:
                returns_path = samples.flatten()
            else:
                returns_path = samples[:, 0]  # First column is always returns
            
            path_value = np.prod(1 + returns_path)
            final_values[sim] = path_value
            
            # Store full path for charting (first n_chart_paths simulations)
            if sim < n_chart_paths:
                chart_paths[sim, 1:] = portfolio_value * np.cumprod(1 + returns_path)
        
        # Convert to returns and calculate VaR/CVaR
        final_returns = final_values - 1
        results = self._calculate_var_cvar(final_returns, portfolio_value)
        
        # Add HMM-specific results
        results['method'] = 'hmm'
        results['n_regimes'] = n_regimes
        results['regime_params'] = regime_params
        results['current_regime'] = current_regime
        results['transition_matrix'] = sorted_transmat.tolist()
        results['regime_labels'] = labels  # For reference
        results['model_diagnostics'] = model_diagnostics  # Training performance metrics
        
        # Feature info for transparency
        results['hmm_features'] = {
            'requested': hmm_features if hmm_features else ['returns_only'],
            'resolved': feature_names,
            'n_features': n_features,
            'available_features': list(self.HMM_FEATURES.keys()),
            'available_presets': list(self.HMM_FEATURE_PRESETS.keys()),
            'note': 'Features used for regime detection. Only returns dimension used for path simulation.'
        }
        
        # Check for overfitting indicators
        max_daily_mean = max(abs(m) for m in means)
        if max_daily_mean > 0.003:  # >0.3%/day is extreme
            results['hmm_warning'] = {
                'type': 'potential_overfitting',
                'message': f'Detected extreme regime means (max: {max_daily_mean*100:.2f}%/day). '
                          f'With {n_regimes} regimes, the HMM may be overfitting to noise in the data. '
                          f'Recommendations: (1) Use fewer regimes (2-3), (2) Use more historical data, '
                          f'(3) Add regularizing features like rolling_vol_20d.',
                'max_daily_mean_pct': max_daily_mean * 100,
                'n_regimes': n_regimes
            }
        
        # Add path statistics
        results['paths'] = {
            'min': float(np.min(final_values)),
            'max': float(np.max(final_values)),
            'median': float(np.median(final_values)),
            'mean': float(np.mean(final_values))
        }
        
        # Include chart paths matrix for visualization (not serialized to JSON response)
        results['_chart_paths'] = chart_paths
        
        return results
    
    def _calculate_var_cvar(self, returns: np.ndarray, portfolio_value: float = None) -> Dict:
        """
        Calculate VaR and CVaR from return distribution.
        VaR: Value at Risk (percentile)
        CVaR: Conditional Value at Risk (expected loss beyond VaR)
        
        Note: VaR and CVaR are reported as positive numbers representing losses
        """
        results = {
            'mean_return': np.mean(returns),
            'volatility': np.std(returns),
            'skewness': stats.skew(returns),
            'kurtosis': stats.kurtosis(returns),
            'min_return': np.min(returns),
            'max_return': np.max(returns)
        }
        
        # Calculate VaR and CVaR for each confidence level
        for conf in self.confidence_levels:
            # VaR is the loss at the (1-conf) percentile
            # For 95% confidence, we look at the 5th percentile
            var_percentile = (1 - conf) * 100
            var_threshold = np.percentile(returns, var_percentile)
            
            # VaR is the absolute loss value
            # If threshold is negative (a loss), convert to positive
            var_pct = -var_threshold if var_threshold < 0 else 0
            
            # Convert VaR to dollars if portfolio value provided
            if portfolio_value and portfolio_value > 0:
                var = var_pct * portfolio_value  # Dollar amount
            else:
                var = var_pct  # Keep as percentage if no portfolio value
            
            # CVaR is the expected percentage loss in the tail
            tail_returns = returns[returns <= var_threshold]
            if len(tail_returns) > 0:
                # Average of the tail returns (as percentage)
                cvar_pct = -np.mean(tail_returns) if np.mean(tail_returns) < 0 else 0
            else:
                # If no returns in tail, CVaR equals VaR percentage
                cvar_pct = var_pct
            
            # Backward-compatible keys (both in dollars if portfolio_value provided)
            results[f'VaR_{conf}'] = var  # Dollar amount
            if portfolio_value and portfolio_value > 0:
                results[f'CVaR_{conf}'] = cvar_pct * portfolio_value  # Dollar amount
            else:
                results[f'CVaR_{conf}'] = cvar_pct  # Percentage fallback

            # New normalized keys with consistent units
            results[f'VaR_{conf}_pct'] = var_pct
            if portfolio_value and portfolio_value > 0:
                results[f'VaR_{conf}_usd'] = var
                results[f'CVaR_{conf}_usd'] = cvar_pct * portfolio_value
            results[f'CVaR_{conf}_pct'] = cvar_pct
            
            # Add number of VaR breaches for validation
            n_breaches = np.sum(returns <= var_threshold)
            results[f'VaR_breaches_{conf}'] = n_breaches
            results[f'VaR_breach_rate_{conf}'] = n_breaches / len(returns)
            
            # Verify CVaR >= VaR (mathematical requirement)
            # Note: We're comparing percentages for CVaR vs dollars/percentage for VaR
            # So we need to compare apples to apples
            if portfolio_value and (cvar_pct < var_pct):
                logger.warning(f"CVaR ({cvar_pct:.4f}) < VaR ({var_pct:.4f}) - mathematical inconsistency")
                # Don't arbitrarily adjust - this indicates a calculation error
        
        return results
    
    def calculate_marginal_var(self,
                             returns: pd.DataFrame,
                             weights: np.ndarray,
                             confidence: float = 0.95,
                             delta: float = 0.01) -> pd.Series:
        """
        Calculate marginal VaR contribution of each asset.
        Useful for risk budgeting.
        """
        base_var = self.parametric_var(returns, weights)['VaR_' + str(confidence)]
        marginal_vars = pd.Series(index=returns.columns)
        
        for i, asset in enumerate(returns.columns):
            # Increase weight slightly
            weights_up = weights.copy()
            weights_up[i] += delta
            weights_up /= weights_up.sum()  # Renormalize
            
            # Calculate new VaR
            new_var = self.parametric_var(returns, weights_up)['VaR_' + str(confidence)]
            
            # Marginal VaR
            marginal_vars[asset] = (new_var - base_var) / delta
        
        return marginal_vars
    
    def plot_monte_carlo_paths(self, 
                               returns: pd.DataFrame,
                               weights: np.ndarray,
                               n_paths: int = 1000,
                               n_days: int = None,
                               initial_value: float = 100,
                               figsize: Tuple[int, int] = (10, 7),
                               output_path: Optional[str] = None):
        """
        Generate and plot Monte Carlo simulation paths for portfolio value.
        Returns interactive plotly figure.
        """
        if n_days is None:
            n_days = self.time_horizon
        
        # Use the plotly visualization
        fig = MonteCarloVisualizations.plot_monte_carlo_paths(
            returns=returns,
            weights=weights,
            n_simulations=n_paths,
            time_horizon=n_days,
            portfolio_value=initial_value,
            confidence_levels=[0.95, 0.99],
            figsize=figsize
        )
        
        # Save if output path provided
        if output_path:
            if output_path.endswith('.html'):
                MonteCarloVisualizations.save_plotly_figure(fig, output_path, format='html')
            else:
                MonteCarloVisualizations.save_plotly_figure(fig, output_path, format='png')
            logger.info(f"Saved Monte Carlo paths visualization to {output_path}")
        
        return fig