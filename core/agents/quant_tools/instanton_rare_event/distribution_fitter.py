"""
Distribution fitting for Instanton Rare Event Analyzer.

Fits Normal or Student-t distributions to return data for crash probability
calculations. Auto-selects distribution based on BIC (data-driven, not hardcoded).
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import logging

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class FittedDistribution:
    """Container for fitted distribution parameters."""
    dist_type: str  # "normal" or "student_t"
    mu: float       # Location (mean)
    sigma: float    # Scale (volatility)
    df: float       # Degrees of freedom (inf for normal)
    log_likelihood: float
    aic: float
    bic: float
    n_observations: int
    tail_fatness_ratio: float  # How much fatter than normal


def fit_normal(returns: np.ndarray) -> Dict[str, Any]:
    """
    Fit a Normal distribution to returns using MLE.
    
    Args:
        returns: Array of log returns
        
    Returns:
        Dict with parameters and fit statistics
    """
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)
    
    # Log-likelihood
    ll = np.sum(stats.norm.logpdf(returns, loc=mu, scale=sigma))
    
    # AIC and BIC for model comparison
    n = len(returns)
    k = 2  # number of parameters
    aic = 2 * k - 2 * ll
    bic = k * np.log(n) - 2 * ll
    
    return {
        "type": "normal",
        "mu": float(mu),
        "sigma": float(sigma),
        "df": float('inf'),
        "log_likelihood": float(ll),
        "aic": float(aic),
        "bic": float(bic),
        "n_params": k,
    }


def fit_student_t(returns: np.ndarray) -> Dict[str, Any]:
    """
    Fit a Student's t-distribution to returns using MLE.
    
    Args:
        returns: Array of log returns
        
    Returns:
        Dict with parameters and fit statistics
    """
    # Fit t-distribution
    df, loc, scale = stats.t.fit(returns)
    
    # Ensure reasonable df (avoid degenerate cases)
    df = max(2.1, min(df, 100))
    
    # Log-likelihood
    ll = np.sum(stats.t.logpdf(returns, df=df, loc=loc, scale=scale))
    
    # AIC and BIC
    n = len(returns)
    k = 3  # df, loc, scale
    aic = 2 * k - 2 * ll
    bic = k * np.log(n) - 2 * ll
    
    return {
        "type": "student_t",
        "mu": float(loc),
        "sigma": float(scale),
        "df": float(df),
        "log_likelihood": float(ll),
        "aic": float(aic),
        "bic": float(bic),
        "n_params": k,
    }


def compute_tail_fatness_ratio(df: float) -> float:
    """
    Compute how much more often 3-sigma events occur vs normal.
    
    This ratio is computed from the distributions, not hardcoded.
    
    Args:
        df: Degrees of freedom of t-distribution (inf for normal)
        
    Returns:
        Ratio of t-dist tail probability to normal tail probability
    """
    if not np.isfinite(df):
        return 1.0
    
    # 3-sigma tail probability under normal
    normal_3sigma = 2 * (1 - stats.norm.cdf(3))  # ~0.27%
    
    # 3-sigma equivalent under t-distribution
    t_3sigma = 2 * (1 - stats.t.cdf(3, df=df))
    
    return t_3sigma / normal_3sigma


def fit_distribution(
    returns: List[float],
    method: str = "auto"
) -> FittedDistribution:
    """
    Fit a distribution to returns for instanton analysis.
    
    Args:
        returns: List of log returns
        method: "normal", "student_t", or "auto" (BIC-based selection)
        
    Returns:
        FittedDistribution with parameters for crash probability calculation
    """
    returns_arr = np.array(returns)
    n = len(returns_arr)
    
    if n < 20:
        logger.warning(f"Few observations ({n}), fit may be unreliable")
    
    # Fit both distributions
    normal_fit = fit_normal(returns_arr)
    t_fit = fit_student_t(returns_arr)
    
    # Select distribution based on method
    if method == "auto":
        # Use BIC for model selection (lower is better)
        # Require BIC difference > 2 for positive evidence
        selected = "student_t" if t_fit["bic"] < normal_fit["bic"] - 2 else "normal"
    elif method == "student_t" or method == "t":
        selected = "student_t"
    else:
        selected = "normal"
    
    fit = t_fit if selected == "student_t" else normal_fit
    tail_ratio = compute_tail_fatness_ratio(fit["df"])
    
    return FittedDistribution(
        dist_type=selected,
        mu=fit["mu"],
        sigma=fit["sigma"],
        df=fit["df"],
        log_likelihood=fit["log_likelihood"],
        aic=fit["aic"],
        bic=fit["bic"],
        n_observations=n,
        tail_fatness_ratio=tail_ratio,
    )


def distribution_to_dict(dist: FittedDistribution) -> Dict[str, Any]:
    """Convert FittedDistribution to dict for JSON output."""
    
    # Interpretation based on computed tail ratio
    if dist.tail_fatness_ratio > 3:
        tail_interpretation = (
            f"Very fat tails - 3-sigma events ~{dist.tail_fatness_ratio:.1f}x "
            "more likely than normal. Crash risk significantly underestimated by Gaussian models."
        )
    elif dist.tail_fatness_ratio > 1.5:
        tail_interpretation = (
            f"Moderately fat tails - 3-sigma events ~{dist.tail_fatness_ratio:.1f}x "
            "more likely than normal."
        )
    else:
        tail_interpretation = "Near-normal tails - Gaussian approximation reasonable."
    
    # Type explanation
    if dist.dist_type == "student_t":
        type_explanation = (
            f"Returns have fat tails (df={dist.df:.1f}). "
            "More extreme moves than standard bell curve."
        )
    else:
        type_explanation = "Returns follow standard bell curve (normal distribution)."
    
    return {
        "type": dist.dist_type,
        "type_explanation": type_explanation,
        "params": {
            "mu": dist.mu,
            "sigma": dist.sigma,
            "df": dist.df if np.isfinite(dist.df) else None,
        },
        "annualized": {
            "volatility": dist.sigma * np.sqrt(252),
            "volatility_pct": f"{dist.sigma * np.sqrt(252) * 100:.1f}%",
            "drift": dist.mu * 252,
            "drift_pct": f"{dist.mu * 252 * 100:.1f}%",
        },
        "tail_analysis": {
            "tail_fatness_ratio": dist.tail_fatness_ratio,
            "interpretation": tail_interpretation,
        },
        "fit_quality": {
            "log_likelihood": dist.log_likelihood,
            "aic": dist.aic,
            "bic": dist.bic,
            "n_observations": dist.n_observations,
        },
    }


def compute_var_levels(
    dist: FittedDistribution,
    horizon_days: int,
    confidence_levels: List[float] = None
) -> Dict[str, float]:
    """
    Compute Value-at-Risk levels from fitted distribution.
    
    These can be used as automatic crash thresholds.
    
    Args:
        dist: Fitted distribution
        horizon_days: Time horizon in trading days
        confidence_levels: List of confidence levels (default [0.95, 0.99, 0.995])
        
    Returns:
        Dict mapping confidence level to crash percentage
    """
    if confidence_levels is None:
        confidence_levels = [0.95, 0.99, 0.995]
    
    # Scale parameters to horizon
    horizon_sigma = dist.sigma * np.sqrt(horizon_days)
    horizon_mu = dist.mu * horizon_days
    
    var_levels = {}
    
    for conf in confidence_levels:
        if dist.dist_type == "student_t" and np.isfinite(dist.df):
            # t-distribution quantile
            z = stats.t.ppf(1 - conf, df=dist.df)
            var_log_return = horizon_mu + z * horizon_sigma
        else:
            # Normal quantile
            z = stats.norm.ppf(1 - conf)
            var_log_return = horizon_mu + z * horizon_sigma
        
        # Convert log return to percentage
        var_pct = (np.exp(var_log_return) - 1) * 100
        
        var_levels[f"var_{int(conf*100)}"] = float(var_pct)
    
    return var_levels


def compute_historical_max_drawdown(returns: List[float]) -> Dict[str, Any]:
    """
    Compute historical maximum drawdown from returns.
    
    Args:
        returns: List of simple returns
        
    Returns:
        Dict with max drawdown info
    """
    # Build cumulative wealth
    returns_arr = np.array(returns)
    wealth = np.cumprod(1 + returns_arr)
    
    # Running maximum
    running_max = np.maximum.accumulate(wealth)
    
    # Drawdown series
    drawdown = (wealth - running_max) / running_max
    
    # Max drawdown
    max_dd = np.min(drawdown)
    max_dd_idx = np.argmin(drawdown)
    
    # Find peak before max drawdown
    peak_idx = np.argmax(wealth[:max_dd_idx+1]) if max_dd_idx > 0 else 0
    
    return {
        "max_drawdown_pct": float(max_dd * 100),
        "max_drawdown_start_idx": int(peak_idx),
        "max_drawdown_end_idx": int(max_dd_idx),
        "duration_days": int(max_dd_idx - peak_idx),
    }


def get_crash_thresholds(
    dist: FittedDistribution,
    returns: List[float],
    horizon_days: int,
    user_crash_pct: float = None,
    crash_target: str = None,
) -> List[Dict[str, Any]]:
    """
    Generate crash thresholds for multi-scenario analysis.
    
    Args:
        dist: Fitted distribution
        returns: Historical simple returns (for max drawdown)
        horizon_days: Time horizon
        user_crash_pct: User-specified crash percentage (e.g., -20.0)
        crash_target: Target method ("var_95", "var_99", "max_drawdown", "vol_3")
        
    Returns:
        List of crash scenario dicts with names and thresholds
    """
    scenarios = []
    
    # VaR-based thresholds
    var_levels = compute_var_levels(dist, horizon_days)
    
    # Historical max drawdown
    max_dd_info = compute_historical_max_drawdown(returns)
    
    # Volatility multiples
    annualized_vol = dist.sigma * np.sqrt(252)
    horizon_vol = annualized_vol * np.sqrt(horizon_days / 252)
    
    # Build default scenarios if no specific target
    if crash_target is None and user_crash_pct is None:
        # Default: provide multiple scenarios
        scenarios = [
            {
                "name": "VaR 95%",
                "method": "var_95",
                "crash_pct": var_levels.get("var_95", -5.0),
            },
            {
                "name": "VaR 99%",
                "method": "var_99",
                "crash_pct": var_levels.get("var_99", -10.0),
            },
            {
                "name": "VaR 99.5%",
                "method": "var_99",
                "crash_pct": var_levels.get("var_99", -15.0),
            },
            {
                "name": "Max Historical Drawdown",
                "method": "max_drawdown",
                "crash_pct": max_dd_info["max_drawdown_pct"],
            },
        ]
    elif user_crash_pct is not None:
        # User specified exact percentage
        scenarios = [
            {
                "name": f"Custom ({user_crash_pct:.0f}%)",
                "method": "user_specified",
                "crash_pct": float(user_crash_pct),
            }
        ]
    else:
        # Specific target method
        if crash_target == "var_95":
            scenarios = [{"name": "VaR 95%", "method": "var_95", 
                         "crash_pct": var_levels.get("var_95", -5.0)}]
        elif crash_target == "var_99":
            scenarios = [{"name": "VaR 99%", "method": "var_99",
                         "crash_pct": var_levels.get("var_99", -10.0)}]
        elif crash_target == "max_drawdown":
            scenarios = [{"name": "Max Drawdown", "method": "max_drawdown",
                         "crash_pct": max_dd_info["max_drawdown_pct"]}]
        elif crash_target.startswith("vol_"):
            # vol_2, vol_3, vol_4 etc
            try:
                n_sigma = int(crash_target.split("_")[1])
                crash_pct = -n_sigma * horizon_vol * 100
                scenarios = [{"name": f"{n_sigma}-Sigma Move", "method": crash_target,
                             "crash_pct": crash_pct}]
            except (ValueError, IndexError):
                scenarios = [{"name": "3-Sigma Move", "method": "vol_3",
                             "crash_pct": -3 * horizon_vol * 100}]
    
    return scenarios


















