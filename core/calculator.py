"""
Risk calculation engine extracted from main.py.
Handles portfolio risk analysis without visualization concerns.
"""

import os
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .config import get_config
from .constants import TRADING_DAYS_PER_YEAR, DEFAULT_PORTFOLIO_VALUE
from .utils.validation import validate_tickers, validate_weights, validate_date_range
from .utils import DataFetcher
from .risk_modules import BarraFactorModel, MonteCarloEngine, PortfolioOptimizer

logger = logging.getLogger(__name__)


class RiskCalculator:
    """
    Core risk calculation engine without visualization.
    Focused on portfolio analysis and risk metrics computation.
    """
    
    def __init__(self, portfolio_value: Optional[float] = None, custom_factors: Optional[Dict[str, str]] = None):
        # Load configuration
        self.config = get_config()
        self.portfolio_value = portfolio_value or self.config.portfolio_value
        
        self.data_fetcher = None
        self.risk_free_rate = self.config.risk_free_rate  # Default from config
        
        # Direct module instantiation (KISS principle - simpler than RiskAgent)
        if custom_factors:
            self.barra_model = BarraFactorModel(custom_factors=custom_factors)
        else:
            self.barra_model = BarraFactorModel()
        
        self.mc_engine = MonteCarloEngine()
        
        # Load risk limits from config
        self.risk_limits = self.config.get_risk_limits()
        
        logger.info(f"Risk Calculator initialized for ${self.portfolio_value:,.0f} portfolio")
    
    def initialize(self, fred_api_key: Optional[str] = None):
        """Initialize data connections."""
        # Use provided key or load from config
        fred_key = fred_api_key or self.config.fred_api_key
        
        if not fred_key:
            logger.warning("No FRED API key provided. Macro factors will use synthetic data.")
        
        self.data_fetcher = DataFetcher(fred_api_key=fred_key)
        
        # Try to fetch current risk-free rate from FRED
        if fred_key:
            try:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                rf_series = self.data_fetcher.get_risk_free_rate(start_date, end_date)
                if not rf_series.empty:
                    # Convert daily rate to annual rate
                    self.risk_free_rate = rf_series.iloc[-1] * TRADING_DAYS_PER_YEAR
                    logger.info(f"Fetched risk-free rate from FRED: {self.risk_free_rate:.2%}")
                else:
                    logger.info(f"Using default risk-free rate: {self.risk_free_rate:.2%}")
            except Exception as e:
                logger.warning(f"Failed to fetch risk-free rate from FRED: {e}")
                logger.info(f"Using default risk-free rate: {self.risk_free_rate:.2%}")
        else:
            logger.info(f"Using default risk-free rate: {self.risk_free_rate:.2%}")
        
        logger.info("Data connections initialized")
    
    def analyze_portfolio(self,
                         tickers: List[str],
                         weights: Optional[np.ndarray] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         **kwargs) -> Dict:
        """
        Complete portfolio risk analysis pipeline.
        Returns analysis results without generating visualizations.
        """
        # Validate inputs using common validation utilities
        tickers = validate_tickers(tickers)
        start_date, end_date = validate_date_range(start_date, end_date)
        weights = validate_weights(weights, len(tickers))
        
        logger.info(f"Analyzing portfolio: {dict(zip(tickers, weights))}")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Extract optional parameters
        benchmark = kwargs.get('benchmark')
        if benchmark:
            logger.info(f"Benchmark comparison requested: {benchmark}")
        
        # 1. Fetch and prepare data
        logger.info("Fetching market data...")
        prices = self.data_fetcher.fetch_prices(tickers, start_date, end_date)
        returns = self.data_fetcher.calculate_returns(prices)
        
        # Validate data
        if len(returns) < TRADING_DAYS_PER_YEAR:
            logger.warning("Less than 1 year of data available")
        
        # 2. Factor model analysis
        logger.info("Building factor model...")
        try:
            # Estimate complete factor model
            factor_results = self.barra_model.estimate_factor_model(returns, prices)
            
            # Portfolio risk decomposition
            risk_decomp = self.barra_model.calculate_portfolio_risk(weights)
        except Exception as e:
            logger.error(f"Factor model failed: {e}")
            factor_results = None
            risk_decomp = None
        
        # 3. VaR/CVaR calculations
        logger.info("Running risk simulations...")
        risk_metrics = {}
        
        # Ensure portfolio_value is valid to prevent crashes
        portfolio_value = self.portfolio_value if self.portfolio_value and self.portfolio_value > 0 else DEFAULT_PORTFOLIO_VALUE
        
        # Parametric VaR
        risk_metrics['parametric'] = self.mc_engine.parametric_var(returns, weights, portfolio_value)
        
        # Historical simulation
        risk_metrics['historical'] = self.mc_engine.historical_simulation(returns, weights, portfolio_value)
        
        # Full Monte Carlo
        risk_metrics['monte_carlo'] = self.mc_engine.monte_carlo_simulation(returns, weights, portfolio_value)
        
        # Factor-based (if model available)
        if risk_decomp:
            risk_metrics['factor_based'] = self.mc_engine.factor_based_simulation(
                returns, weights, portfolio_value, self.barra_model
            )
        
        # 4. Calculate performance metrics
        portfolio_returns = returns @ weights
        annual_return = portfolio_returns.mean() * TRADING_DAYS_PER_YEAR
        annual_vol = portfolio_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        sharpe_ratio = (annual_return - self.risk_free_rate) / annual_vol if annual_vol > 0 else 0
        
        performance_metrics = {
            'expected_return': annual_return,
            'annual_vol': annual_vol,
            'sharpe_ratio': sharpe_ratio
        }
        
        # 5. Check risk limits
        limit_breaches = self.check_risk_limits(risk_metrics, weights)
        
        # 6. Compile results
        results = {
            'portfolio_value': portfolio_value,
            'weights': dict(zip(tickers, weights)),
            'returns_data': {
                'prices': prices,
                'returns': returns,
                'start_date': start_date,
                'end_date': end_date
            },
            'risk_metrics': risk_metrics,
            'performance_metrics': performance_metrics,
            'risk_decomposition': risk_decomp,
            'factor_results': factor_results,
            'risk_limits_check': limit_breaches,
            'tickers': tickers
        }
        
        return results
    
    def optimize_portfolio(self,
                          tickers: List[str],
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          method: str = 'sharpe',
                          constraints: Optional[Dict] = None,
                          **kwargs) -> Dict:
        """
        Optimize portfolio allocation.
        """
        # Validate inputs
        tickers = validate_tickers(tickers)
        start_date, end_date = validate_date_range(start_date, end_date)
        
        prices = self.data_fetcher.fetch_prices(tickers, start_date, end_date)
        returns = self.data_fetcher.calculate_returns(prices)
        
        # Direct optimizer creation (KISS - no need for indirection)
        optimizer = PortfolioOptimizer(returns)
        
        # Run optimization
        if method == 'min_variance':
            result = optimizer.optimize_portfolio(objective='min_variance')
            weights = result['weights']
            metrics = result
        elif method == 'sharpe':
            result = optimizer.optimize_portfolio(objective='sharpe')
            weights = result['weights']
            metrics = result
        elif method == 'risk_parity':
            result = optimizer.optimize_portfolio(objective='risk_parity')
            weights = result['weights']
            metrics = result
        elif method == 'target_return':
            target_ret = constraints.get('target_return', 0.10) if constraints else 0.10
            result = optimizer.optimize_portfolio(objective='target_return', target_return=target_ret)
            weights = result['weights']
            metrics = result
        else:
            raise ValueError(f"Unknown optimization method: {method}")
        
        # Run risk analysis on optimal portfolio
        analysis = self.analyze_portfolio(tickers, weights, start_date, end_date)
        analysis['optimization'] = {
            'method': method,
            'weights': dict(zip(tickers, weights)),
            'metrics': metrics
        }
        
        return analysis
    
    def check_risk_limits(self, risk_metrics: Dict, weights: np.ndarray) -> Dict:
        """
        Check if portfolio breaches risk limits.
        """
        violations = []
        
        # Check VaR limit
        var_95 = risk_metrics['parametric']['VaR_0.95'] / self.portfolio_value
        if var_95 > self.risk_limits['max_var_95']:
            violations.append({
                'limit': 'VaR 95%',
                'current': var_95,
                'limit_value': self.risk_limits['max_var_95'],
                'breach': 'EXCEEDED'
            })
        
        # Check concentration
        max_weight = np.max(weights)
        if max_weight > self.risk_limits['max_concentration']:
            violations.append({
                'limit': 'Concentration',
                'current': max_weight,
                'limit_value': self.risk_limits['max_concentration'],
                'breach': 'EXCEEDED'
            })
        
        # Check minimum Sharpe (if available)
        if 'parametric' in risk_metrics:
            annual_return = risk_metrics['parametric'].get('expected_return', 0)
            annual_vol = risk_metrics['parametric'].get('annual_vol', 1)
            
            if annual_vol > 0:
                sharpe = (annual_return - self.risk_free_rate) / annual_vol
                if sharpe < self.risk_limits['min_sharpe_ratio']:
                    violations.append({
                        'limit': 'Sharpe Ratio',
                        'current': sharpe,
                        'limit_value': self.risk_limits['min_sharpe_ratio'],
                        'breach': 'BELOW_MINIMUM'
                    })
        
        return {
            'violations': violations,
            'compliant': len(violations) == 0,
            'total_violations': len(violations)
        }