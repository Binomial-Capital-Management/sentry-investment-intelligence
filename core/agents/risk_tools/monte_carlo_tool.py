"""
Monte Carlo Simulation Tool
"""

from agents import function_tool
from typing import List, Optional
import logging
import json
import hashlib

from core.risk_modules.montecarlo import MonteCarloEngine
import numpy as np
from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns, jsonify_results
from core.utils.validation import validate_weights, validate_confidence_level, validate_portfolio_value, validate_simulation_params
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.constants import (
    DEFAULT_PORTFOLIO_VALUE, DEFAULT_MC_SIMULATIONS,
    CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99,
    TRADING_DAYS_PER_YEAR, DEFAULT_PERIOD
)
from .shared import fetch_market_data_batch, register_chart_handle
from core.charts.builders.risk import build_monte_carlo_paths
from core.charts.models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


async def run_monte_carlo_internal(
    tickers: List[str],
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    weights: Optional[List[float]] = None,
    n_simulations: int = DEFAULT_MC_SIMULATIONS,
    time_horizon: int = TRADING_DAYS_PER_YEAR,
    confidence_levels: Optional[List[float]] = None,
    portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
    use_hmm: bool = False,
    n_regimes: int = 3,
    hmm_features: Optional[List[str]] = None,
    hmm_n_iter: int = 200,
    hmm_n_init: int = 10,
    hmm_covariance_type: str = "tied",  # "tied" prevents extreme regimes (was "full")
    hmm_tol: float = 1e-4,
    skip_charts: bool = False,  # Skip chart generation, return raw path data instead
) -> dict:
    """
    Run Monte Carlo simulation for portfolio risk analysis. Automatically fetches required market data.
    
    Args:
        tickers: List of ticker symbols (REQUIRED)
        period: Historical data period. Use '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'. Default: '1y'
        start_date: OPTIONAL - Start date in YYYY-MM-DD format (e.g., '2023-01-01'). 
                    ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        end_date: OPTIONAL - End date in YYYY-MM-DD format (e.g., '2024-01-01').
                  ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        weights: OPTIONAL - Portfolio weights. OMIT for equal weighting.
        n_simulations: Number of simulation paths (default: 1000)
        time_horizon: Forecast horizon in trading days (default: 252 for 1 year)
        confidence_levels: OPTIONAL - List of confidence levels (e.g., [0.95, 0.99]). OMIT for defaults.
        portfolio_value: Total portfolio value in dollars (default: 1000000)
        use_hmm: OPTIONAL - Use Hidden Markov Model regime-switching simulation (default: False).
                 HMM identifies market regimes with different return/volatility characteristics
                 for more realistic tail behavior and volatility clustering.
        
        === HMM CONFIGURATION (only used when use_hmm=True) ===
        
        n_regimes: Number of market regimes (2-5, default: 3)
                   GUIDANCE:
                   - 2: Most robust. Good for bull/bear or low/high volatility.
                   - 3: Balanced. Adds a "transition" or "neutral" regime. RECOMMENDED.
                   - 4-5: Risk of overfitting. Only use with 3+ years of data.
                   Rule: Need ~100+ days per regime for stable estimates.
        
        hmm_features: Features for regime detection (granular selection).
                      
                      INDIVIDUAL FEATURES:
                      Volatility: 'return_squared', 'abs_return', 'rolling_vol_5d', 'rolling_vol_10d',
                                  'rolling_vol_20d', 'rolling_vol_60d', 'vol_ratio_5_20'
                      Momentum: 'return_lag1', 'return_lag2', 'return_lag5', 'cum_return_5d',
                                'cum_return_10d', 'cum_return_20d', 'cum_return_60d', 'ma_crossover_5_20'
                      Mean Reversion: 'zscore_5d', 'zscore_10d', 'zscore_20d', 'distance_from_high_20d'
                      Higher Order: 'skewness_20d', 'kurtosis_20d'
                      
                      PRESETS:
                      - 'minimal': Just return_squared (fast, adds variance info)
                      - 'volatility': All volatility features
                      - 'momentum': All momentum features
                      - 'mean_reversion': All mean reversion features
                      - 'standard': Balanced mix - RECOMMENDED starting point
                      - 'full' or 'all': Everything (slowest, risk of overfitting)
                      
                      Default: None (univariate - returns only, fastest)
        
        hmm_n_iter: Max EM iterations per initialization (default: 200)
                    - 100: Fast, may not fully converge
                    - 200: Good balance (default)
                    - 500: Use if model_diagnostics shows "did not converge"
        
        hmm_n_init: Number of random initializations (default: 10)
                    NOTE: More inits = better global optimum, NOT more overfitting.
                    - 1: Fastest, may find local optimum (unstable)
                    - 10: Good balance (default)
                    - 20-50: More robust, recommended for important analysis
        
        hmm_covariance_type: Covariance structure (default: "tied")
                    THIS IS THE KEY PARAMETER FOR CONTROLLING OVERFITTING:
                    - "tied": DEFAULT. Regimes share covariance. Prevents extreme regimes.
                    - "full": Most flexible, HIGHEST overfitting risk. Each regime has own covariance.
                    - "diag": Diagonal only. Faster, assumes feature independence.
                    - "spherical": Most constrained. Single variance per regime.
                    
                    ⚠️ Only use "full" if you have 3+ years of data and understand the risks.
        
        hmm_tol: Convergence tolerance (default: 1e-4)
                 Lower = stricter convergence, better fit quality.
        
        === MODEL FIT ASSESSMENT (check model_diagnostics in response) ===
        
        WHAT CAUSES OVERFITTING:
        1. Too many regimes for data (need ~100+ samples per regime)
        2. "full" covariance with few samples
        3. Too many features relative to data
        
        SIGNS OF GOOD FIT:
        - quality_score: "good"
        - All regimes have 50+ samples
        - Regime returns are realistic (±30%/yr typical, ±50%/yr max)
        - Model converged
        - AIC/BIC reasonable (compare across configs - lower is better)
        
        SIGNS OF OVERFITTING:
        - quality_score: "poor"
        - Extreme regime returns (>100%/yr or <-50%/yr)
        - Very small regimes (<20 samples)
        - quality_issues list is non-empty
        
        RECOMMENDED SETTINGS FOR STABILITY:
        - n_regimes=2 or 3 (not 4-5 unless you have 3+ years data)
        - hmm_covariance_type="tied" (prevents extreme variance differences)
        - hmm_features=["standard"] or None (don't use "all")
        - period="2y" or longer for more training data
    
    Returns:
        JSON string of Monte Carlo simulation results with risk metrics and charts.
        When use_hmm=True, also returns:
        - regime_params: mean, std, sharpe, frequency per regime
        - current_regime: which regime the market is currently in
        - transition_matrix: probabilities of moving between regimes
        - hmm_features: which features were used for regime detection
        - model_diagnostics: training metrics including:
          * log_likelihood: how well model fits data (higher = better)
          * aic/bic: model selection criteria (lower = better, penalizes complexity)
          * samples_per_regime: how many days in each regime
          * quality_score: 'good', 'fair', or 'poor' based on diagnostics
          * quality_issues: list of any detected problems (overfitting, low samples, etc.)
        
    Examples:
        ✅ Basic: run_monte_carlo(tickers=["AAPL", "MSFT"], period="1y")
        ✅ HMM univariate: run_monte_carlo(tickers=["SPY"], use_hmm=True)
        ✅ HMM with features: run_monte_carlo(tickers=["SPY"], use_hmm=True, hmm_features=["standard"])
        ✅ HMM anti-overfitting: run_monte_carlo(tickers=["SPY"], use_hmm=True, n_regimes=2, 
                                                  hmm_covariance_type="tied")
        ✅ HMM robust: run_monte_carlo(tickers=["SPY"], use_hmm=True, n_regimes=3,
                                        hmm_features=["standard"], hmm_n_init=20, hmm_covariance_type="tied")
        ✅ HMM granular: run_monte_carlo(tickers=["SPY"], use_hmm=True, n_regimes=3, 
                                         hmm_features=["return_squared", "rolling_vol_20d", "zscore_20d"],
                                         hmm_n_iter=300, hmm_n_init=15)
        
        TROUBLESHOOTING:
        - Getting extreme regimes (>100%/yr)? → Try hmm_covariance_type="tied" or reduce n_regimes
        - Model not converging? → Increase hmm_n_iter to 500
        - Want more robust results? → Increase hmm_n_init to 20+
        
        ❌ WRONG: DO NOT pass "null", "undefined", or empty strings for optional parameters
    """
    market_server = None
    try:
        # Create MCP server for data fetching (FMP as primary source)
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Use centralized data fetching
        combined_data = await fetch_market_data_batch(market_server, tickers, period, start_date, end_date)
        
        # Adapt to price DataFrame and calculate returns
        prices = adapt_mcp_to_prices(combined_data, tickers)
        returns = prepare_returns(prices)
        
        # Get the actual tickers that have data (may be subset of requested tickers)
        actual_tickers = list(prices.columns)
        
        # Filter weights to match actual tickers with data
        if weights is not None and len(tickers) != len(actual_tickers):
            # Map original weights to actual tickers
            ticker_to_weight = dict(zip(tickers, weights))
            filtered_weights = [ticker_to_weight[t] for t in actual_tickers if t in ticker_to_weight]
            weights = filtered_weights
            logger.info(f"Filtered weights from {len(tickers)} to {len(actual_tickers)} tickers (matched with available data)")
        
        # Use validation utils
        weights = validate_weights(weights, len(actual_tickers))
        if confidence_levels is None:
            confidence_levels = [CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99]
        else:
            confidence_levels = [validate_confidence_level(cl) for cl in confidence_levels]
        n_simulations, time_horizon = validate_simulation_params(n_simulations, time_horizon)
        portfolio_value = validate_portfolio_value(portfolio_value)
        
        # Create Monte Carlo engine
        mc_engine = MonteCarloEngine(
            n_simulations=n_simulations,
            time_horizon=time_horizon,
            confidence_levels=confidence_levels
        )
        
        # Run simulation (HMM or standard)
        if use_hmm:
            # HMM regime-switching simulation
            n_regimes = min(max(n_regimes, 2), 5)  # Clamp to valid range
            feature_desc = hmm_features if hmm_features else "returns only (univariate)"
            logger.info(f"Running HMM Monte Carlo with {n_regimes} regimes, features: {feature_desc}")
            logger.info(f"HMM params: n_iter={hmm_n_iter}, n_init={hmm_n_init}, cov_type={hmm_covariance_type}")
            results = mc_engine.hmm_simulation(
                returns=returns,
                weights=weights,
                portfolio_value=portfolio_value,
                n_regimes=n_regimes,
                hmm_features=hmm_features,
                hmm_n_iter=hmm_n_iter,
                hmm_n_init=hmm_n_init,
                hmm_covariance_type=hmm_covariance_type,
                hmm_tol=hmm_tol
            )
        else:
            # Standard Monte Carlo with optional t-distribution
            results = mc_engine.monte_carlo_simulation(
                returns=returns,
                weights=weights,
                portfolio_value=portfolio_value
            )
        
        # Generate paths data (always needed for metrics and optional chart)
        chart = None
        raw_paths_data = None
        id_seed = f"{tuple(tickers)}|{time_horizon}|{n_simulations}"
        paths_matrix = None
        
        try:
            n_chart_sims = 512  # sample for paths

            if use_hmm and '_chart_paths' in results:
                paths_matrix = results['_chart_paths']
                n_chart_sims = paths_matrix.shape[0]
                logger.info(f"Using {n_chart_sims} HMM paths from simulation for chart")
            else:
                daily_mean = returns.mean(axis=0) @ weights
                cov_matrix = returns.cov().values
                portfolio_var = weights @ cov_matrix @ weights
                daily_vol = np.sqrt(portfolio_var) if portfolio_var > 0 else returns.std(axis=0).mean()
                daily_mean = float(daily_mean) if np.isfinite(daily_mean) else 0.0
                daily_vol = float(daily_vol) if np.isfinite(daily_vol) and daily_vol > 0 else max(1e-6, float(returns.stack().std()))

                rng = np.random.default_rng()
                increments = rng.normal(loc=daily_mean, scale=daily_vol, size=(n_chart_sims, time_horizon))
                comp = np.cumprod(1.0 + increments, axis=1)
                paths_matrix = np.concatenate([np.ones((n_chart_sims, 1)), comp], axis=1) * float(portfolio_value)

            # Compute percentile bands and representative paths
            percentiles = {
                '5': np.percentile(paths_matrix, 5, axis=0).tolist(),
                '25': np.percentile(paths_matrix, 25, axis=0).tolist(),
                '50': np.percentile(paths_matrix, 50, axis=0).tolist(),
                '75': np.percentile(paths_matrix, 75, axis=0).tolist(),
                '95': np.percentile(paths_matrix, 95, axis=0).tolist(),
            }
            terminal_vals = paths_matrix[:, -1]
            targets = [np.percentile(terminal_vals, p) for p in [5, 25, 50, 75, 95]]
            rep_indices = [int(np.argmin(np.abs(terminal_vals - t))) for t in targets]
            representative_paths = [paths_matrix[idx].tolist() for idx in rep_indices]
            
            # Terminal value distribution for histogram
            terminal_returns = ((terminal_vals / float(portfolio_value)) - 1.0).tolist()

            terminal_stats = {
                'mean': float(np.mean(terminal_vals)),
                'std': float(np.std(terminal_vals)),
                'var_95': float(np.percentile(terminal_vals, 5)),
                'var_99': float(np.percentile(terminal_vals, 1)),
            }

            # Store raw paths data for Canvas to use
            # Include more paths for spaghetti chart (sample from paths_matrix)
            n_spaghetti = min(100, paths_matrix.shape[0])  # Up to 100 paths for visualization
            sampled_indices = np.linspace(0, paths_matrix.shape[0] - 1, n_spaghetti, dtype=int)
            spaghetti_paths = [paths_matrix[i].tolist() for i in sampled_indices]
            
            raw_paths_data = {
                'percentiles': percentiles,
                'representative_paths': spaghetti_paths,  # Many paths for spaghetti chart
                'terminal_returns': terminal_returns,
                'terminal_stats': terminal_stats,
                'n_paths': n_spaghetti,
                'time_horizon': time_horizon,
                'portfolio_value': portfolio_value,
            }

            # Only build chart if not skipping
            if not skip_charts:
                ticker_display = ', '.join(actual_tickers[:5])
                if len(actual_tickers) > 5:
                    ticker_display += f" +{len(actual_tickers) - 5} more"
                chart_title = f"HMM Monte Carlo ({n_regimes} regimes) - {ticker_display}" if use_hmm else f"Monte Carlo Simulation - {ticker_display}"
                chart_id = f"mc_{hashlib.md5(id_seed.encode()).hexdigest()[:8]}"
                
                chart_spec = ChartSpec(
                    id=chart_id,
                    type=ChartType.MONTE_CARLO_PATHS,
                    title=chart_title,
                    inputs={
                        'paths': representative_paths[:3],  # 5th, 50th, 95th only
                        'percentiles': {k: v for k, v in percentiles.items() if k in ['5', '50', '95']},
                        'terminal_stats': terminal_stats
                    },
                    priority=ChartPriority.HIGH,
                    options=None
                )
                chart_figure = await build_monte_carlo_paths(chart_spec, {})
            
                if chart_figure:
                    chart = register_chart_handle(
                        chart_figure.plotly,
                        chart_type=ChartType.MONTE_CARLO_PATHS.value,
                        title=chart_figure.title,
                        alt_text=chart_figure.alt_text,
                        metadata=chart_figure.metadata,
                        chart_id=chart_figure.id
                    )
        except Exception as e:
            logger.warning(f"Paths generation failed: {e}")
            # Fallback for chart if not skipping
            if not skip_charts:
                try:
                    ticker_display = ', '.join(actual_tickers[:5])
                    if paths_matrix is not None:
                        terminal_returns = ((paths_matrix[:, -1] / float(portfolio_value)) - 1.0).tolist()
                    else:
                        terminal_returns = []
                    hist_spec = ChartSpec(
                        id=f"mc_hist_{hashlib.md5(id_seed.encode()).hexdigest()[:8]}",
                        type=ChartType.RETURNS_HISTOGRAM,
                        title=f"Terminal Return Distribution - {ticker_display}",
                        inputs={'returns': terminal_returns[:10000]},
                        priority=ChartPriority.MEDIUM,
                        options=None
                    )
                    from core.charts.builders.risk import build_returns_histogram
                    chart_figure = await build_returns_histogram(hist_spec, {})
                    if chart_figure:
                        chart = register_chart_handle(
                            chart_figure.plotly,
                            chart_type=ChartType.RETURNS_HISTOGRAM.value,
                            title=chart_figure.title,
                            alt_text=chart_figure.alt_text,
                            metadata=chart_figure.metadata,
                            chart_id=chart_figure.id
                        )
                except Exception as e2:
                    logger.warning(f"Histogram fallback failed: {e2}")
        
        # Remove internal chart paths before serialization (large numpy array)
        results_clean = {k: v for k, v in results.items() if not k.startswith('_')}
        
        response = {
            'status': 'success',
            'monte_carlo_results': results_clean,
            'tickers': actual_tickers,
            'tickers_requested': tickers,
            'tickers_excluded': list(set(tickers) - set(actual_tickers)),
            'weights': weights.tolist(),
            'portfolio_value': portfolio_value,
            'n_simulations': n_simulations,
            'time_horizon': time_horizon,
            'confidence_levels': confidence_levels,
            'charts': [chart] if chart else [],
        }
        
        # Include raw paths data when charts are skipped (for Canvas to build its own)
        if skip_charts and raw_paths_data:
            response['raw_paths_data'] = raw_paths_data
        
        # Add HMM-specific info to top level for easier access
        if use_hmm:
            response['hmm_enabled'] = True
            response['n_regimes'] = results_clean.get('n_regimes', n_regimes)
            response['current_regime'] = results_clean.get('current_regime')
            response['regime_params'] = results_clean.get('regime_params')
            response['hmm_features'] = results_clean.get('hmm_features')
            response['model_diagnostics'] = results_clean.get('model_diagnostics')
        
        return jsonify_results(response)
        
    except Exception as e:
        logger.error(f"Monte Carlo simulation with data failed: {e}")
        error_type = 'data_error' if 'no data' in str(e).lower() else 'general_error'
        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'monte_carlo'
        }
    finally:
        # Cleanup FMP server connection
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")


# Decorated version for agent tools
@function_tool
async def run_monte_carlo(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    weights: Optional[List[float]] = None,
    n_simulations: int = DEFAULT_MC_SIMULATIONS,
    time_horizon: int = TRADING_DAYS_PER_YEAR,
    confidence_levels: Optional[List[float]] = None,
    portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
    use_hmm: bool = False,
    n_regimes: int = 3,
    hmm_features: Optional[List[str]] = None,
    hmm_n_iter: int = 200,
    hmm_n_init: int = 10,
    hmm_covariance_type: str = "tied",  # "tied" prevents extreme regimes (was "full")
    hmm_tol: float = 1e-4
) -> dict:
    """
    Run Monte Carlo simulation for portfolio risk analysis.
    
    Args:
        tickers: List of ticker symbols. OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers/weights from.
        period: Historical data period. Default: '1y'
        weights: OPTIONAL - Portfolio weights. Ignored if portfolio_id provided.
        n_simulations: Number of simulation paths
        time_horizon: Forecast horizon in trading days
        ... (other params)
    
    Examples:
        ✅ CORRECT: run_monte_carlo(portfolio_id="my_portfolio")
        ✅ CORRECT: run_monte_carlo(tickers=["AAPL", "MSFT"], n_simulations=5000)
    """
    from .shared import resolve_portfolio_tickers
    
    # Resolve tickers from portfolio if portfolio_id provided
    if portfolio_id:
        try:
            tickers, portfolio_weights = await resolve_portfolio_tickers(portfolio_id)
            weights = list(portfolio_weights.values())
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'error_type': 'portfolio_error',
                'calculation_type': 'monte_carlo'
            }
    
    # Validate we have tickers
    if not tickers:
        return {
            'status': 'error',
            'error': 'Either tickers or portfolio_id must be provided',
            'error_type': 'validation_error',
            'calculation_type': 'monte_carlo'
        }
    
    return await run_monte_carlo_internal(
        tickers=tickers,
        period=period,
        start_date=start_date,
        end_date=end_date,
        weights=weights,
        n_simulations=n_simulations,
        time_horizon=time_horizon,
        confidence_levels=confidence_levels,
        portfolio_value=portfolio_value,
        use_hmm=use_hmm,
        n_regimes=n_regimes,
        hmm_features=hmm_features,
        hmm_n_iter=hmm_n_iter,
        hmm_n_init=hmm_n_init,
        hmm_covariance_type=hmm_covariance_type,
        hmm_tol=hmm_tol,
    )
