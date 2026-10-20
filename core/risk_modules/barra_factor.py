import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.linear_model import LinearRegression
from core.visualization.risk_templates.barra_visualizations import BarraVisualizations
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Opt-in to future pandas behavior to silence FutureWarning on fillna downcasting
pd.set_option('future.no_silent_downcasting', True)

logger = logging.getLogger(__name__)

class BarraFactorModel:
    def __init__(self, custom_factors: Optional[Dict[str, str]] = None):
        self.factor_exposures = None
        self.factor_returns = None
        self.specific_returns = None
        self.factor_covariance = None
        self.specific_risk = None
        self.r_squared = None
        
        # v6: Minimal defaults to prevent crashes
        # Full discovery will come with v6 implementation
        self.DEFAULT_FACTOR_ETFS = {
            'SPY': 'Market',          # S&P 500 market factor
            'XLF': 'Financials',      # Financial sector
            'XLK': 'Technology'       # Technology sector  
        }
        
        # Use custom factors if provided, otherwise use defaults
        if custom_factors:
            self.FACTOR_ETFS = custom_factors
            logger.info(f"Using custom factors: {list(custom_factors.values())}")
        else:
            # v6: Use minimal defaults to prevent crashes until full implementation
            self.FACTOR_ETFS = self.DEFAULT_FACTOR_ETFS.copy()
            logger.info("Using minimal default factors - full v6 discovery coming soon")
            
    def set_custom_factors(self, custom_factors: Dict[str, str]):
        """Update factor ETFs after initialization."""
        self.FACTOR_ETFS = custom_factors
        logger.info(f"Updated factor ETFs: {custom_factors}")
        # Reset any cached results
        self.factor_exposures = None
        self.factor_returns = None
        self.factor_covariance = None
        self.specific_risk = None
        self.r_squared = None
        
    def fetch_factor_etf_returns(self, start_date: str, end_date: str, *, market_data_fetcher=None) -> pd.DataFrame:
        """Fetch factor ETF returns via provided market_data_fetcher (MCP), not direct yfinance."""
        if market_data_fetcher is None:
            raise ValueError("market_data_fetcher is required to fetch factor ETF returns")
        
        etf_tickers = list(self.FACTOR_ETFS.keys())
        logger.info(f"Fetching factor ETF data via MCP: {etf_tickers}")
        
        all_price_data: Dict[str, any] = {}
        for ticker in etf_tickers:
            data = market_data_fetcher(ticker, start_date, end_date)
            all_price_data[ticker] = data
        
        # Expect market_data_fetcher to return JSON-serializable objects similar to MCP server
        import json as _json
        combined = _json.dumps(all_price_data)
        from core.utils.risk_adapter import adapt_mcp_to_prices
        prices = adapt_mcp_to_prices(combined, etf_tickers)
        
        # Calculate log returns
        factor_returns = np.log(prices / prices.shift(1)).iloc[1:]
        factor_returns.columns = [self.FACTOR_ETFS[ticker] for ticker in etf_tickers]
        return factor_returns
    
    def estimate_factor_model(self, 
                            returns: pd.DataFrame, 
                            prices: pd.DataFrame,
                            *,
                            factor_prices: Optional[pd.DataFrame] = None,
                            factor_returns: Optional[pd.DataFrame] = None) -> Dict:
        """
        Estimate factor model using ETF returns:
        1. Fetch factor ETF returns
        2. Run time-series regression of asset returns on factor returns
        """
        # Get date range from returns or prices
        # Check if returns has a DatetimeIndex
        if isinstance(returns.index, pd.DatetimeIndex):
            start_date = returns.index[0] - pd.Timedelta(days=10)
            end_date = returns.index[-1]
        elif isinstance(prices.index, pd.DatetimeIndex):
            # Fall back to prices index if available
            start_date = prices.index[0] - pd.Timedelta(days=10)
            end_date = prices.index[-1]
            logger.warning("Returns DataFrame has no DatetimeIndex, using prices DataFrame index")
        else:
            # Use a default lookback period if no DatetimeIndex found
            logger.warning("No DatetimeIndex found in returns or prices, using 1 year lookback from today")
            end_date = pd.Timestamp.now()
            start_date = end_date - pd.Timedelta(days=365)
        
        # Step 1: Get factor returns
        if factor_returns is not None:
            pass  # already provided
        else:
            if factor_prices is not None:
                factor_returns = np.log(factor_prices / factor_prices.shift(1)).iloc[1:]
            else:
                # As a last resort, caller didn't provide factor data; fetch via provided MCP fetcher API is required
                raise ValueError("factor_prices or factor_returns must be provided to estimate_factor_model in v6")
        
        # Step 2: Align data
        common_dates = returns.index.intersection(factor_returns.index)
        if len(common_dates) < 60:
            raise ValueError(f"Insufficient overlapping data: {len(common_dates)} days")
            
        returns_aligned = returns.loc[common_dates]
        factors_aligned = factor_returns.loc[common_dates]
        
        # Store results
        betas = pd.DataFrame(index=returns.columns, columns=factors_aligned.columns)
        alphas = pd.Series(index=returns.columns)
        specific_vols = pd.Series(index=returns.columns)
        r2_values = pd.Series(index=returns.columns)
        
        # Time-series regression for each asset
        for asset in returns.columns:
            y = returns_aligned[asset].values
            X = factors_aligned.values
            
            # Skip if we have NaN values
            mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
            if mask.sum() < 60:
                logger.warning(f"Insufficient data for {asset}")
                continue
                
            y_clean = y[mask]
            X_clean = X[mask]
            
            # Add intercept
            X_with_const = np.column_stack([np.ones(len(X_clean)), X_clean])
            
            # Run regression
            model = LinearRegression(fit_intercept=False)
            model.fit(X_with_const, y_clean)
            
            # Extract results
            alphas[asset] = model.coef_[0]
            betas.loc[asset] = model.coef_[1:]
            
            # Calculate R-squared
            y_pred = model.predict(X_with_const)
            ss_res = np.sum((y_clean - y_pred) ** 2)
            ss_tot = np.sum((y_clean - y_clean.mean()) ** 2)
            r2_values[asset] = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            # Specific risk (residual volatility)
            residuals = y_clean - y_pred
            trading_days = int(os.getenv('TRADING_DAYS', 252))
            specific_vols[asset] = residuals.std() * np.sqrt(trading_days)
        
        # Factor covariance matrix
        trading_days = int(os.getenv('TRADING_DAYS', 252))
        factor_cov = factors_aligned.cov() * trading_days
        
        # Store results (use infer_objects to avoid FutureWarning on fillna downcasting)
        self.factor_exposures = betas.fillna(0).infer_objects(copy=False)
        self.factor_covariance = factor_cov
        self.specific_risk = specific_vols.fillna(specific_vols.mean()).infer_objects(copy=False)
        self.r_squared = r2_values.fillna(0).infer_objects(copy=False)
        self.factor_returns = factors_aligned
        
        logger.info(f"Factor model fitted. Mean R²: {r2_values.mean():.3f}")
        
        return {
            'betas': betas,
            'alphas': alphas,
            'specific_risk': specific_vols,
            'r_squared': r2_values,
            'factor_covariance': self.factor_covariance,
            'factor_exposures': betas.to_dict('index'),  # Asset -> Factor exposures
            'mean_r_squared': float(r2_values.mean())    # Overall model fit
        }
    
    
    def calculate_portfolio_risk(self, weights: np.ndarray) -> Dict:
        """
        Decompose portfolio risk into factor and specific components.
        """
        if self.factor_exposures is None:
            raise ValueError("Model not fitted yet")
        
        # Portfolio factor exposures
        portfolio_betas = self.factor_exposures.T @ weights
        # Ensure it's a numpy array for consistent indexing
        portfolio_betas = np.array(portfolio_betas).flatten()
        
        # Factor risk contribution
        factor_variance = portfolio_betas @ self.factor_covariance @ portfolio_betas
        factor_risk = np.sqrt(factor_variance)
        
        # Specific risk contribution
        specific_variance = np.sum((weights ** 2) * (self.specific_risk ** 2))
        specific_risk = np.sqrt(specific_variance)
        
        # Total risk
        total_variance = factor_variance + specific_variance
        total_risk = np.sqrt(total_variance)
        
        # Risk attribution by factor
        marginal_contributions = self.factor_covariance @ portfolio_betas
        factor_contributions = {}
        
        for i, factor in enumerate(self.factor_covariance.columns):
            # Contribution to variance
            var_contrib = portfolio_betas[i] * marginal_contributions.iloc[i]
            # Percentage of total variance
            factor_contributions[factor] = var_contrib / total_variance
        
        return {
            'total_risk': total_risk,
            'factor_risk': factor_risk,
            'specific_risk': specific_risk,
            'factor_contributions': factor_contributions,
            'portfolio_betas': dict(zip(self.factor_covariance.columns, portfolio_betas)),
            'risk_decomposition': {
                'systematic': factor_variance / total_variance,
                'idiosyncratic': specific_variance / total_variance
            }
        }
    
    def predict_returns(self, 
                       factor_views: Dict[str, float],
                       horizon: int = 21) -> pd.Series:
        """
        Predict asset returns given factor views.
        Useful for tactical allocation.
        """
        if self.factor_exposures is None:
            raise ValueError("Model not fitted")
        
        # Convert views to array
        factor_predictions = np.array([
            factor_views.get(factor, 0) 
            for factor in self.factor_exposures.columns
        ])
        
        # Scale views to horizon
        trading_days = int(os.getenv('TRADING_DAYS', 252))
        factor_predictions = factor_predictions * horizon / trading_days
        
        # Predict returns: R = Beta * F
        predicted_returns = self.factor_exposures @ factor_predictions
        
        return predicted_returns
    
    def plot_factor_exposures(self, ticker_subset: Optional[List[str]] = None, 
                              figsize: Tuple[int, int] = (14, 7)):
        """
        Visualize factor exposures (betas) as an interactive heatmap.
        Shows how much each asset is exposed to each risk factor.
        """
        if self.factor_exposures is None:
            raise ValueError("Model not fitted. Run estimate_factor_model first.")
        
        return BarraVisualizations.plot_factor_exposures(self.factor_exposures, ticker_subset, figsize)
    
    def plot_risk_decomposition(self, weights: np.ndarray,
                                figsize: Tuple[int, int] = (12, 6)):
        """
        Interactive portfolio risk decomposition visualization.
        """
        if self.factor_exposures is None:
            raise ValueError("Model not fitted. Run estimate_factor_model first.")
        
        # Calculate risk decomposition
        risk_decomp = self.calculate_portfolio_risk(weights)
        
        return BarraVisualizations.plot_risk_decomposition(risk_decomp, figsize)
    def plot_factor_returns(self, lookback_days: int = None, 
                            figsize: Tuple[int, int] = (14, 8)):
        """
        Plot cumulative factor performance interactively.
        """
        if self.factor_returns is None:
            raise ValueError("Model not fitted. Run estimate_factor_model first.")
        
        return BarraVisualizations.plot_factor_returns(self.factor_returns, lookback_days, figsize)
    def plot_r_squared_distribution(self, figsize: Tuple[int, int] = (10, 6)):
        """
        Interactive R-squared distribution visualization.
        """
        if self.r_squared is None:
            raise ValueError("Model not fitted. Run estimate_factor_model first.")
        
        return BarraVisualizations.plot_r_squared_distribution(self.r_squared, figsize)


if __name__ == "__main__":
    """Test and display all Barra visualizations."""
    from core.utils.data_fetch import DataFetcher
    
    print("Testing Barra Factor Model Visualizations")
    print("="*50)
    
    # Initialize components
    data_fetcher = DataFetcher()
    barra_model = BarraFactorModel()
    
    # Portfolio setup (!CHECK FLAG 001!)
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'JPM', 'JNJ']
    weights = np.array([0.25, 0.20, 0.20, 0.20, 0.15])
    
    # Fetch data (!CHECK FLAG 002!)
    print("\nFetching market data...")
    start_date = '2022-06-10'
    end_date = '2025-06-09'
    prices = data_fetcher.fetch_prices(tickers, start_date, end_date)
    returns = data_fetcher.calculate_returns(prices)
    
    # Estimate factor model
    print("Estimating factor model...")
    results = barra_model.estimate_factor_model(returns, prices)
    
    print(f"\nModel Results:")
    print(f"Mean R²: {results['r_squared'].mean():.3f}")
    print(f"Factor Covariance shape: {results['factor_covariance'].shape}")
    
    # Generate all visualizations
    print("\nGenerating visualizations...")
    
    # 1. Factor Exposures Heatmap
    print("1. Factor Exposures Heatmap")
    fig1 = barra_model.plot_factor_exposures()
    BarraVisualizations.save_plotly_figure(fig1, 'barra_factor_exposures.html', format='html')
    
    # 2. Risk Decomposition
    print("\n2. Portfolio Risk Decomposition")
    fig2 = barra_model.plot_risk_decomposition(weights)
    BarraVisualizations.save_plotly_figure(fig2, 'barra_risk_decomposition.html', format='html')
    
    # 3. Factor Returns
    print("\n3. Factor ETF Performance")
    fig3 = barra_model.plot_factor_returns()
    BarraVisualizations.save_plotly_figure(fig3, 'barra_factor_returns.html', format='html')
    
    # 4. R-squared Distribution
    print("\n4. Model Fit (R-squared)")
    fig4 = barra_model.plot_r_squared_distribution()
    BarraVisualizations.save_plotly_figure(fig4, 'barra_r_squared.html', format='html')
    
    # Print risk decomposition details
    risk_decomp = barra_model.calculate_portfolio_risk(weights)
    print("\n" + "="*50)
    print("PORTFOLIO RISK ANALYSIS")
    print("="*50)
    print(f"Total Risk: {risk_decomp['total_risk']:.2%}")
    print(f"Systematic Risk: {risk_decomp['factor_risk']:.2%} ({risk_decomp['risk_decomposition']['systematic']:.1%})")
    print(f"Idiosyncratic Risk: {risk_decomp['specific_risk']:.2%} ({risk_decomp['risk_decomposition']['idiosyncratic']:.1%})")
    
    print("\nFactor Contributions:")
    for factor, contrib in risk_decomp['factor_contributions'].items():
        print(f"  {factor}: {contrib:.1%}")
    
    print("\nPortfolio Factor Exposures:")
    for factor, beta in risk_decomp['portfolio_betas'].items():
        print(f"  {factor}: {beta:.3f}")
    
    print("\n✓ All interactive visualizations generated and saved as HTML files!")


class FactorETFLibrary:
    """Common factor ETFs organized by category for easy reference."""
    
    STYLE_FACTORS = {
        'MTUM': 'Momentum',
        'VLUE': 'Value',
        'QUAL': 'Quality', 
        'USMV': 'Low_Volatility',
        'SIZE': 'Small_Cap',
        'DGRO': 'Dividend_Growth',
        'DVY': 'High_Dividend',
        'SPLV': 'Low_Volatility_SP500'
    }
    
    SECTOR_FACTORS = {
        'XLF': 'Financials',
        'XLK': 'Technology',
        'XLE': 'Energy',
        'XLV': 'Healthcare',
        'XLI': 'Industrials',
        'XLY': 'Consumer_Discretionary',
        'XLP': 'Consumer_Staples',
        'XLB': 'Materials',
        'XLRE': 'Real_Estate',
        'XLU': 'Utilities',
        'XLC': 'Communications'
    }
    
    ASSET_CLASS_FACTORS = {
        'SPY': 'US_Equity_Market',
        'AGG': 'US_Bonds',
        'TLT': 'Long_Term_Treasuries',
        'IEF': 'Intermediate_Treasuries',
        'SHY': 'Short_Term_Treasuries',
        'HYG': 'High_Yield_Bonds',
        'LQD': 'Investment_Grade_Corporate',
        'GLD': 'Gold',
        'DBC': 'Commodities',
        'VNQ': 'US_Real_Estate'
    }
    
    GEOGRAPHIC_FACTORS = {
        'EFA': 'International_Developed',
        'EEM': 'Emerging_Markets',
        'FXI': 'China',
        'EWJ': 'Japan',
        'EWG': 'Germany',
        'EWU': 'United_Kingdom',
        'VGK': 'Europe',
        'VWO': 'Emerging_Markets_Vanguard',
        'INDA': 'India',
        'EWZ': 'Brazil'
    }
    
    THEMATIC_FACTORS = {
        'ICLN': 'Clean_Energy',
        'ARKK': 'Disruptive_Innovation',
        'FINX': 'FinTech',
        'BOTZ': 'Robotics_AI',
        'SKYY': 'Cloud_Computing',
        'HACK': 'Cybersecurity',
        'TAN': 'Solar_Energy',
        'LIT': 'Lithium_Battery',
        'JETS': 'Airlines',
        'XBI': 'Biotech'
    }
    
    @classmethod
    def get_all_factors(cls) -> Dict[str, str]:
        """Get all available factor ETFs."""
        all_factors = {}
        all_factors.update(cls.STYLE_FACTORS)
        all_factors.update(cls.SECTOR_FACTORS)
        all_factors.update(cls.ASSET_CLASS_FACTORS)
        all_factors.update(cls.GEOGRAPHIC_FACTORS)
        all_factors.update(cls.THEMATIC_FACTORS)
        return all_factors
    
    @classmethod
    def get_factor_suggestions(cls, category: Optional[str] = None) -> Dict[str, str]:
        """Get factor suggestions by category."""
        category_map = {
            'style': cls.STYLE_FACTORS,
            'sector': cls.SECTOR_FACTORS,
            'asset_class': cls.ASSET_CLASS_FACTORS,
            'geographic': cls.GEOGRAPHIC_FACTORS,
            'thematic': cls.THEMATIC_FACTORS
        }
        
        if category and category.lower() in category_map:
            return category_map[category.lower()]
        return cls.get_all_factors()
    
    @classmethod
    def create_custom_factor_set(cls, selections: List[str]) -> Dict[str, str]:
        """Create a custom factor set from selections."""
        all_factors = cls.get_all_factors()
        custom_factors = {}
        
        for selection in selections:
            # Handle format like "SPY:Market" or just "SPY"
            if ':' in selection:
                ticker, name = selection.split(':', 1)
                custom_factors[ticker.upper()] = name
            elif selection.upper() in all_factors:
                ticker = selection.upper()
                custom_factors[ticker] = all_factors[ticker]
            else:
                # If not found, add it anyway with a generic name
                custom_factors[selection.upper()] = selection.upper()
                
        return custom_factors