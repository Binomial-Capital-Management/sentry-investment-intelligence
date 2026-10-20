"""
Instanton Solver - Core Physics for Rare Event Analysis

Computes the instanton (most likely path to a crash) and its action.
The action determines the crash probability via P ≈ exp(-S[instanton]).

Key insight: For a crash to occur, the most likely path is one with
constant daily returns (minimizes action). Not one massive gap.

For Geometric Brownian Motion:
    dS/S = μ dt + σ dW
    
The action for a path is:
    S = ∫ (d ln S - μ dt)² / (2σ² dt)
    
For log returns r_t = ln(S_t/S_{t-1}):
    S = Σ (r_t - μ Δt)² / (2σ² Δt)
    
The instanton minimizes this action subject to boundary conditions.
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import logging

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class InstantonPath:
    """Container for instanton path and its properties."""
    times: np.ndarray           # Time points (0 to T)
    prices: np.ndarray          # Price trajectory
    log_returns: np.ndarray     # Daily log returns along path
    action: float               # Total action (lower = more likely)
    daily_return: float         # Constant daily log return (for GBM instanton)
    total_return: float         # Total log return
    total_return_pct: float     # Total return as percentage


def compute_action(
    log_returns: np.ndarray,
    sigma: float,
    mu: float = 0.0,
    dt: float = 1.0
) -> float:
    """
    Compute the action for a sequence of log returns.
    
    Action = Σ (r_t - μ Δt)² / (2σ² Δt)
    
    This measures how "unlikely" the path is. Lower action = more likely.
    
    Args:
        log_returns: Array of daily log returns
        sigma: Daily volatility (standard deviation)
        mu: Daily drift (mean log return)
        dt: Time step (default 1 day)
        
    Returns:
        Action value (dimensionless)
    """
    if len(log_returns) == 0:
        return 0.0
    
    # Deviation from expected drift
    deviations = log_returns - mu * dt
    
    # Action = sum of squared deviations normalized by variance
    action = np.sum(deviations**2) / (2 * sigma**2 * dt)
    
    return float(action)


def compute_instanton_gbm(
    S0: float,
    S_target: float,
    n_days: int,
    sigma: float,
    mu: float = 0.0,
) -> InstantonPath:
    """
    Compute the instanton path for Geometric Brownian Motion.
    
    For GBM, the instanton (most likely path to target) has CONSTANT
    daily log return. This is the path that minimizes action.
    
    Args:
        S0: Starting price
        S_target: Target price (crash level)
        n_days: Number of trading days
        sigma: Daily volatility
        mu: Daily drift (mean log return)
        
    Returns:
        InstantonPath with trajectory and action
    """
    # Total required log return
    total_log_return = np.log(S_target / S0)
    
    # For instanton: constant daily return minimizes action
    daily_log_return = total_log_return / n_days
    
    # Build price trajectory
    times = np.arange(n_days + 1)
    log_prices = np.log(S0) + daily_log_return * times
    prices = np.exp(log_prices)
    
    # Log returns (constant along instanton)
    log_returns = np.full(n_days, daily_log_return)
    
    # Compute action
    action = compute_action(log_returns, sigma, mu, dt=1.0)
    
    # Total return as percentage
    total_return_pct = (S_target / S0 - 1) * 100
    
    return InstantonPath(
        times=times,
        prices=prices,
        log_returns=log_returns,
        action=action,
        daily_return=daily_log_return,
        total_return=total_log_return,
        total_return_pct=total_return_pct,
    )


def compute_instanton_student_t(
    S0: float,
    S_target: float,
    n_days: int,
    sigma: float,
    df: float,
    mu: float = 0.0,
) -> InstantonPath:
    """
    Compute the instanton path for Student-t distributed returns.
    
    For heavy-tailed distributions, the instanton shape differs from GBM.
    The optimal path has slightly varying returns (not exactly constant).
    
    For practical purposes with moderate df (> 4), the GBM instanton
    is a good approximation. We use it with adjusted action.
    
    Args:
        S0: Starting price
        S_target: Target price (crash level)
        n_days: Number of trading days
        sigma: Daily scale parameter
        df: Degrees of freedom
        mu: Daily location parameter
        
    Returns:
        InstantonPath with trajectory and action
    """
    # For t-distribution, the instanton is still approximately constant returns
    # but the action calculation differs
    
    # Total required log return
    total_log_return = np.log(S_target / S0)
    daily_log_return = total_log_return / n_days
    
    # Build price trajectory (same as GBM)
    times = np.arange(n_days + 1)
    log_prices = np.log(S0) + daily_log_return * times
    prices = np.exp(log_prices)
    log_returns = np.full(n_days, daily_log_return)
    
    # Action for t-distribution
    # For t-dist with pdf ∝ (1 + x²/ν)^(-(ν+1)/2)
    # Action ≈ (ν+1)/2 * Σ log(1 + ((r-μ)/σ)²/ν)
    
    z = (daily_log_return - mu) / sigma
    if df > 2:
        # Proper t-distribution action
        action_per_step = (df + 1) / 2 * np.log(1 + z**2 / df)
        action = float(n_days * action_per_step)
    else:
        # Fall back to Gaussian-like for very low df
        action = compute_action(log_returns, sigma, mu, dt=1.0)
    
    total_return_pct = (S_target / S0 - 1) * 100
    
    return InstantonPath(
        times=times,
        prices=prices,
        log_returns=log_returns,
        action=action,
        daily_return=daily_log_return,
        total_return=total_log_return,
        total_return_pct=total_return_pct,
    )


def compute_instanton(
    S0: float,
    crash_pct: float,
    horizon_days: int,
    sigma: float,
    mu: float = 0.0,
    df: Optional[float] = None,
) -> InstantonPath:
    """
    Compute instanton path for given crash scenario.
    
    Args:
        S0: Starting price
        crash_pct: Crash as percentage (e.g., -20.0 for 20% drop)
        horizon_days: Time horizon in trading days
        sigma: Daily volatility
        mu: Daily drift
        df: Degrees of freedom (None for normal distribution)
        
    Returns:
        InstantonPath with trajectory and action
    """
    # Target price
    S_target = S0 * (1 + crash_pct / 100)
    
    if df is not None and np.isfinite(df):
        return compute_instanton_student_t(S0, S_target, horizon_days, sigma, df, mu)
    else:
        return compute_instanton_gbm(S0, S_target, horizon_days, sigma, mu)


def compute_fluctuation_band(
    instanton: InstantonPath,
    sigma: float,
    confidence: float = 0.68,
    n_samples: int = 100,
) -> Dict[str, np.ndarray]:
    """
    Compute uncertainty band around the instanton path.
    
    The instanton is the central (most likely) path. Actual crash paths
    fluctuate around it. This computes the distribution of paths.
    
    Args:
        instanton: The instanton path
        sigma: Daily volatility
        confidence: Confidence level for band (0.68 = 1σ, 0.95 = 2σ)
        n_samples: Number of sample paths to generate
        
    Returns:
        Dict with upper/lower bands and sample paths
    """
    n_days = len(instanton.log_returns)
    
    # Generate fluctuations around instanton
    # Paths are Gaussian-distributed around the instanton
    
    sample_paths = []
    for _ in range(n_samples):
        # Random fluctuations
        noise = np.random.randn(n_days) * sigma
        
        # Fluctuated returns (centered on instanton)
        fluct_returns = instanton.log_returns + noise
        
        # Build price path
        log_prices = np.log(instanton.prices[0]) + np.cumsum(
            np.concatenate([[0], fluct_returns])
        )
        prices = np.exp(log_prices)
        sample_paths.append(prices)
    
    sample_paths = np.array(sample_paths)
    
    # Compute percentile bands
    alpha = (1 - confidence) / 2
    lower_percentile = alpha * 100
    upper_percentile = (1 - alpha) * 100
    
    lower_band = np.percentile(sample_paths, lower_percentile, axis=0)
    upper_band = np.percentile(sample_paths, upper_percentile, axis=0)
    median_path = np.percentile(sample_paths, 50, axis=0)
    
    return {
        "upper_band": upper_band,
        "lower_band": lower_band,
        "median_path": median_path,
        "sample_paths": sample_paths[:10],  # Return first 10 samples
        "confidence": confidence,
    }


def instanton_to_dict(
    instanton: InstantonPath,
    fluctuation_band: Optional[Dict[str, np.ndarray]] = None,
) -> Dict[str, Any]:
    """
    Convert instanton path to dict for JSON output.
    
    Args:
        instanton: The instanton path
        fluctuation_band: Optional fluctuation band data
        
    Returns:
        Dict suitable for JSON serialization
    """
    result = {
        "times": instanton.times.tolist(),
        "prices": instanton.prices.tolist(),
        "log_returns": instanton.log_returns.tolist(),
        "action": instanton.action,
        "daily_log_return": instanton.daily_return,
        "total_log_return": instanton.total_return,
        "total_return_pct": instanton.total_return_pct,
        "interpretation": (
            f"Most likely crash path: steady {instanton.daily_return*100:.2f}% "
            f"daily decline over {len(instanton.log_returns)} days"
        ),
    }
    
    if fluctuation_band is not None:
        # Only include summary bands, omit sample_paths to prevent context overflow
        # Sample paths are embedded in cached charts
        result["fluctuation_band"] = {
            "upper": fluctuation_band["upper_band"].tolist(),
            "lower": fluctuation_band["lower_band"].tolist(),
            "median": fluctuation_band["median_path"].tolist(),
            # Removed: sample_paths (embedded in charts)
            "confidence": fluctuation_band["confidence"],
        }
    
    return result


def compute_multiasset_instanton(
    S0: np.ndarray,
    crash_pcts: np.ndarray,
    horizon_days: int,
    cov_matrix: np.ndarray,
    mu: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Compute joint instanton for multiple correlated assets.
    
    For a portfolio, the instanton accounts for correlations between assets.
    Each asset follows a path that, together, minimizes the joint action.
    
    Args:
        S0: Array of starting prices
        crash_pcts: Array of crash percentages for each asset
        horizon_days: Time horizon
        cov_matrix: Covariance matrix of daily log returns
        mu: Drift vector (default: zero)
        
    Returns:
        Dict with individual asset paths and joint action
    """
    n_assets = len(S0)
    
    if mu is None:
        mu = np.zeros(n_assets)
    
    # Target prices
    S_targets = S0 * (1 + crash_pcts / 100)
    
    # Required total log returns
    total_log_returns = np.log(S_targets / S0)
    
    # Daily log returns (constant for instanton)
    daily_log_returns = total_log_returns / horizon_days
    
    # Build individual paths
    times = np.arange(horizon_days + 1)
    asset_paths = {}
    
    for i in range(n_assets):
        log_prices = np.log(S0[i]) + daily_log_returns[i] * times
        asset_paths[f"asset_{i}"] = {
            "prices": np.exp(log_prices).tolist(),
            "daily_return": float(daily_log_returns[i]),
            "crash_pct": float(crash_pcts[i]),
        }
    
    # Joint action: uses inverse covariance (precision matrix)
    try:
        precision = np.linalg.inv(cov_matrix)
    except np.linalg.LinAlgError:
        # Regularize if singular
        precision = np.linalg.inv(cov_matrix + 0.001 * np.eye(n_assets))
    
    # Action = (r - μ)' Σ^{-1} (r - μ) * T / 2
    deviation = daily_log_returns - mu
    action = 0.5 * horizon_days * (deviation @ precision @ deviation)
    
    return {
        "times": times.tolist(),
        "asset_paths": asset_paths,
        "joint_action": float(action),
        "horizon_days": horizon_days,
    }
















