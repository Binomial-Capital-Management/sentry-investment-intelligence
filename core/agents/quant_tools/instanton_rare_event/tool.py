"""
Instanton Rare Event Analyzer - Main Tool Entry Point

Physics-based crash probability analysis using instanton methods from
path integral theory. Finds the "most likely path to a crash" analytically
rather than simulating millions of paths.

Supports:
- Single asset analysis
- Portfolio with weights
- Multi-scenario crash analysis
- Severity distribution
- Portfolio crash decomposition
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

import numpy as np

from agents import function_tool

from .data_fetcher import InstantonDataFetcher
from .distribution_fitter import (
    fit_distribution,
    distribution_to_dict,
    get_crash_thresholds,
    FittedDistribution,
)
from .instanton_solver import (
    compute_instanton,
    compute_fluctuation_band,
    instanton_to_dict,
)
from .probability_calculator import (
    compute_crash_probability,
    compute_severity_distribution,
    compute_scenario_probabilities,
    probability_to_dict,
)
from .portfolio_decomposition import full_portfolio_decomposition
from .charts import generate_all_charts
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


def _build_summary(
    mode: str,
    name: str,
    primary_scenario: Dict[str, Any],
    distribution: Dict[str, Any],
    portfolio_decomp: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build user-friendly summary of the analysis."""
    
    crash_pct = primary_scenario["crash_pct"]
    prob = primary_scenario["probability"]
    prob_pct = prob * 100
    tail_mult = primary_scenario.get("tail_multiplier", 1.0)
    gaussian_pct = primary_scenario.get("gaussian_estimate", prob) * 100
    
    # Headline
    if prob_pct >= 1:
        headline = f"{name} has {prob_pct:.1f}% probability of {crash_pct:.0f}% crash"
    else:
        headline = f"{name} has {prob_pct:.2f}% probability of {crash_pct:.0f}% crash"
    
    # Key finding
    if tail_mult > 1.5:
        key_finding = (
            f"Fat tails increase crash risk {tail_mult:.1f}x vs Gaussian assumption "
            f"({prob_pct:.2f}% vs {gaussian_pct:.2f}%)"
        )
    else:
        key_finding = "Tail behavior close to Gaussian - standard risk models adequate"
    
    # Actionable insight
    if mode == "portfolio" and portfolio_decomp:
        contributions = portfolio_decomp.get("crash_contributions", {})
        dominant = contributions.get("dominant_risk_contributor", "")
        if dominant:
            actionable = f"Consider hedging {dominant} specifically - it dominates crash risk"
        else:
            actionable = "Crash risk roughly proportional to weights"
    else:
        if prob_pct > 5:
            actionable = "Elevated crash risk - consider protective puts or reducing position"
        elif prob_pct > 1:
            actionable = "Moderate crash risk - monitor closely"
        else:
            actionable = "Low crash risk at this threshold/horizon"
    
    return {
        "headline": headline,
        "key_finding": key_finding,
        "actionable_insight": actionable,
    }


async def analyze_instanton_crash_internal(
    # Single asset mode
    ticker: Optional[str] = None,
    
    # Portfolio mode
    tickers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
    portfolio_name: str = "Portfolio",
    
    # Crash specification
    crash_pct: Optional[float] = None,
    crash_target: Optional[str] = None,
    crash_scenarios: Optional[List[Dict[str, Any]]] = None,
    
    # Time horizon
    horizon_days: int = 30,
    
    # Data settings
    lookback_days: int = 756,
    distribution: str = "auto",
    
    # Output options
    include_path_distribution: bool = True,
    include_portfolio_decomposition: bool = True,
    include_severity_distribution: bool = True,
    generate_charts: bool = True,
) -> Dict[str, Any]:
    """
    Analyze rare event (crash) probability using instanton methods.
    
    Uses physics-based path integral approach to compute crash probabilities
    analytically rather than via Monte Carlo simulation.
    
    Args:
        ticker: Single ticker symbol (for single asset mode)
        tickers: List of ticker symbols (for portfolio mode)
        weights: Portfolio weights (equal-weight if None)
        portfolio_name: Display name for portfolio
        crash_pct: Specific crash percentage (e.g., -20.0 for 20% drop)
        crash_target: Auto-computed target ("var_95", "var_99", "max_drawdown", "vol_3")
        crash_scenarios: List of scenarios [{"name": "...", "crash_pct": ...}]
        horizon_days: Time horizon in trading days (default 30)
        lookback_days: Historical data for fitting (default 756 = 3 years)
        distribution: "normal", "student_t", or "auto" (BIC-based selection)
        include_path_distribution: Include fluctuation band around instanton
        include_portfolio_decomposition: Include crash contribution analysis
        include_severity_distribution: Include full severity PDF
        generate_charts: Generate Plotly visualizations
        
    Returns:
        Dict containing:
        - summary: Headline, key finding, actionable insight
        - crash_probability: Primary scenario probability
        - instanton_path: Most likely crash trajectory
        - severity_distribution: Full probability distribution over crash levels
        - scenarios: All scenario results
        - portfolio_decomposition: Crash contributions (portfolio mode only)
        - fitted_distribution: Distribution parameters
        - charts: Plotly figures
        
    Examples:
        # Single asset
        result = await analyze_instanton_crash(
            ticker="AAPL",
            crash_pct=-20.0,
            horizon_days=30
        )
        
        # Portfolio with auto scenarios
        result = await analyze_instanton_crash(
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA"],
            weights=[0.3, 0.25, 0.25, 0.2],
            portfolio_name="Tech Growth",
            crash_target="var_99",
            horizon_days=30
        )
    """
    start_time = datetime.now()
    
    try:
        # =====================================================================
        # STEP 1: Determine mode and validate inputs
        # =====================================================================
        if ticker:
            mode = "single"
            name = ticker
        elif tickers:
            mode = "portfolio"
            name = portfolio_name
        else:
            return {
                "status": "error",
                "error": "Must provide either 'ticker' or 'tickers'",
            }
        
        logger.info(f"Starting instanton analysis: mode={mode}, name={name}")
        
        # =====================================================================
        # STEP 2: Fetch market data
        # =====================================================================
        fetcher = InstantonDataFetcher()
        await fetcher.connect()
        
        try:
            data = await fetcher.fetch_data(
                ticker=ticker,
                tickers=tickers,
                weights=weights,
                portfolio_name=portfolio_name,
                lookback_days=lookback_days,
            )
            
            if not data:
                return {
                    "status": "error",
                    "error": f"Failed to fetch data for {name}",
                }
        finally:
            await fetcher.cleanup()
        
        # Extract key data
        if mode == "single":
            current_price = data["current_price"]
            log_returns = data["log_returns"]
            simple_returns = data["simple_returns"]
            sigma = data["daily_volatility"]
            mu = data["daily_drift"]
        else:
            current_price = data["current_value"]
            log_returns = data["portfolio_log_returns"]
            simple_returns = data["portfolio_simple_returns"]
            sigma = data["daily_volatility"]
            mu = data["daily_drift"]
        
        # =====================================================================
        # STEP 3: Fit distribution
        # =====================================================================
        logger.info("Fitting distribution to returns")
        
        fitted_dist = fit_distribution(log_returns, method=distribution)
        dist_dict = distribution_to_dict(fitted_dist)
        
        # Get df for Student-t (None if normal)
        df = fitted_dist.df if fitted_dist.dist_type == "student_t" else None
        
        # =====================================================================
        # STEP 4: Determine crash scenarios
        # =====================================================================
        if crash_scenarios:
            # User provided scenarios
            scenarios = crash_scenarios
        else:
            # Auto-generate from crash_pct or crash_target
            scenarios = get_crash_thresholds(
                fitted_dist, simple_returns, horizon_days,
                user_crash_pct=crash_pct,
                crash_target=crash_target,
            )
        
        # =====================================================================
        # STEP 5: Compute instanton and probabilities for each scenario
        # =====================================================================
        logger.info(f"Computing instanton for {len(scenarios)} scenarios")
        
        scenario_results = compute_scenario_probabilities(
            S0=current_price,
            scenarios=scenarios,
            horizon_days=horizon_days,
            sigma=sigma,
            mu=mu,
            df=df,
        )
        
        # Primary scenario (first one)
        primary_scenario = scenario_results[0]
        primary_crash_pct = primary_scenario["crash_pct"]
        
        # Compute full instanton with fluctuations for primary scenario
        instanton = compute_instanton(
            S0=current_price,
            crash_pct=primary_crash_pct,
            horizon_days=horizon_days,
            sigma=sigma,
            mu=mu,
            df=df,
        )
        
        # Fluctuation band
        if include_path_distribution:
            fluctuation_band = compute_fluctuation_band(instanton, sigma)
        else:
            fluctuation_band = None
        
        instanton_dict = instanton_to_dict(instanton, fluctuation_band)
        
        # =====================================================================
        # STEP 6: Severity distribution
        # =====================================================================
        if include_severity_distribution:
            severity_dist = compute_severity_distribution(
                S0=current_price,
                horizon_days=horizon_days,
                sigma=sigma,
                mu=mu,
                df=df,
            )
        else:
            severity_dist = None
        
        # =====================================================================
        # STEP 7: Portfolio decomposition (if applicable)
        # =====================================================================
        portfolio_decomp = None
        if mode == "portfolio" and include_portfolio_decomposition:
            logger.info("Computing portfolio decomposition")
            
            portfolio_decomp = full_portfolio_decomposition(
                returns_df=data["log_returns_df"],
                weights=data["weights"],
                tickers=data["tickers"],
                crash_pct=primary_crash_pct,
                horizon_days=horizon_days,
            )
        
        # =====================================================================
        # STEP 8: Build summary
        # =====================================================================
        summary = _build_summary(
            mode=mode,
            name=name,
            primary_scenario=primary_scenario,
            distribution=dist_dict,
            portfolio_decomp=portfolio_decomp,
        )
        
        # =====================================================================
        # STEP 9: Generate charts
        # =====================================================================
        charts = []
        if generate_charts:
            try:
                charts = generate_all_charts(
                    instanton_data=instanton_dict,
                    severity_distribution=severity_dist or {},
                    scenarios=scenario_results,
                    portfolio_decomposition=portfolio_decomp,
                    current_price=current_price,
                    crash_pct=primary_crash_pct,
                    horizon_days=horizon_days,
                    sigma=sigma,
                )
            except Exception as e:
                logger.warning(f"Chart generation failed: {e}")
        
        # =====================================================================
        # STEP 10: Build final result
        # =====================================================================
        elapsed = (datetime.now() - start_time).total_seconds()
        
        result = {
            "status": "success",
            "mode": mode,
            "name": name,
            
            "summary": summary,
            
            "crash_probability": {
                "scenario": primary_scenario["name"],
                "crash_pct": primary_crash_pct,
                "crash_price": primary_scenario["crash_price"],
                "probability": primary_scenario["probability"],
                "probability_pct": primary_scenario["probability_pct"],
                "gaussian_estimate": primary_scenario["gaussian_estimate"],
                "tail_multiplier": primary_scenario["tail_multiplier"],
                "confidence_interval": primary_scenario["confidence_interval"],
                "action": primary_scenario["action"],
            },
            
            "instanton_path": instanton_dict,
            
            "scenarios": scenario_results,
            
            "fitted_distribution": dist_dict,
            
            "metadata": {
                "horizon_days": horizon_days,
                "lookback_days": lookback_days,
                "current_price": current_price,
                "daily_volatility": sigma,
                "annualized_volatility": sigma * np.sqrt(252),
                "n_observations": len(log_returns),
                "computation_time_seconds": elapsed,
            },
        }
        
        # Add severity distribution
        if severity_dist:
            result["severity_distribution"] = {
                "statistics": severity_dist["statistics"],
                "horizon_days": severity_dist["horizon_days"],
                "distribution_type": severity_dist["distribution_type"],
            }
        
        # Add portfolio-specific data
        if mode == "portfolio":
            result["portfolio"] = {
                "tickers": data["tickers"],
                "weights": data["weights"],
                "skipped_tickers": data.get("skipped_tickers", []),
            }
            
            if portfolio_decomp:
                result["portfolio_decomposition"] = portfolio_decomp
        
        # Add charts
        if charts:
            result["charts"] = wrap_plotly_charts(charts, default_type="instanton_crash")
        
        # Build interpretation string
        result["interpretation"] = (
            f"{summary['headline']}. {summary['key_finding']}. "
            f"{summary['actionable_insight']}."
        )
        
        logger.info(f"Instanton analysis complete in {elapsed:.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Instanton analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "metadata": {
                "ticker": ticker,
                "tickers": tickers,
            }
        }


@function_tool(strict_mode=False)  # Uses List[Dict[str, Any]] for crash_scenarios
async def analyze_instanton_crash(
    ticker: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    weights: Optional[List[float]] = None,
    portfolio_name: str = "Portfolio",
    crash_pct: Optional[float] = None,
    crash_target: Optional[str] = None,
    crash_scenarios: Optional[List[Dict[str, Any]]] = None,
    horizon_days: int = 30,
    lookback_days: int = 756,
    distribution: str = "auto",
    include_path_distribution: bool = True,
    include_portfolio_decomposition: bool = True,
    include_severity_distribution: bool = True,
    generate_charts: bool = True,
) -> Dict[str, Any]:
    """
    Analyze rare event (crash) probability using instanton methods.
    
    Uses physics-based path integral approach to compute crash probabilities
    analytically rather than via Monte Carlo simulation.
    """
    return await analyze_instanton_crash_internal(
        ticker=ticker,
        tickers=tickers,
        weights=weights,
        portfolio_name=portfolio_name,
        crash_pct=crash_pct,
        crash_target=crash_target,
        crash_scenarios=crash_scenarios,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        distribution=distribution,
        include_path_distribution=include_path_distribution,
        include_portfolio_decomposition=include_portfolio_decomposition,
        include_severity_distribution=include_severity_distribution,
        generate_charts=generate_charts,
    )
