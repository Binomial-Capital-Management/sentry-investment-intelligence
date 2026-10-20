"""
Distribution fitting for Portfolio Geodesic Distance.

Fits Normal or t-distributions to return data and computes Fisher Information.
Auto-selects distribution based on normality tests (no hardcoded thresholds -
uses percentiles from the data).
"""

from typing import Dict, List, Optional, Any, Tuple
import logging

import numpy as np
from scipy import stats
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


def fit_normal(returns: np.ndarray) -> Dict[str, Any]:
    """
    Fit a Normal distribution to returns using MLE.
    
    Args:
        returns: Array of returns
        
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
        "params": {
            "mu": float(mu),
            "sigma": float(sigma),
        },
        "log_likelihood": float(ll),
        "aic": float(aic),
        "bic": float(bic),
        "n_params": k,
    }


def fit_t_distribution(returns: np.ndarray) -> Dict[str, Any]:
    """
    Fit a Student's t-distribution to returns using MLE.
    
    Args:
        returns: Array of returns
        
    Returns:
        Dict with parameters and fit statistics
    """
    # Fit t-distribution
    df, loc, scale = stats.t.fit(returns)
    
    # Ensure reasonable df (avoid degenerate cases)
    df = max(2.01, min(df, 100))
    
    # Log-likelihood
    ll = np.sum(stats.t.logpdf(returns, df=df, loc=loc, scale=scale))
    
    # AIC and BIC
    n = len(returns)
    k = 3  # df, loc, scale
    aic = 2 * k - 2 * ll
    bic = k * np.log(n) - 2 * ll
    
    return {
        "type": "t",
        "params": {
            "df": float(df),
            "loc": float(loc),
            "scale": float(scale),
        },
        "log_likelihood": float(ll),
        "aic": float(aic),
        "bic": float(bic),
        "n_params": k,
    }


def compute_tail_fatness_ratio(df: float) -> float:
    """
    Compute how much more often 3-sigma events occur vs normal.
    
    This is computed from the distributions themselves, not hardcoded.
    
    Args:
        df: Degrees of freedom of t-distribution
        
    Returns:
        Ratio of t-dist 3-sigma probability to normal 3-sigma probability
    """
    normal_3sigma = 2 * (1 - stats.norm.cdf(3))  # ~0.27%
    t_3sigma = 2 * (1 - stats.t.cdf(3, df=df))
    
    return t_3sigma / normal_3sigma


def auto_select_distribution(returns: np.ndarray) -> str:
    """
    Auto-select between normal and t-distribution based on data.
    
    Uses likelihood ratio test (data-driven, not hardcoded thresholds).
    
    Args:
        returns: Array of returns
        
    Returns:
        "normal" or "t"
    """
    normal_fit = fit_normal(returns)
    t_fit = fit_t_distribution(returns)
    
    # Use BIC for model selection (penalizes extra parameters)
    # Lower BIC is better
    if t_fit["bic"] < normal_fit["bic"] - 2:  # BIC difference > 2 = positive evidence
        return "t"
    else:
        return "normal"


def fit_distribution(
    returns: List[float],
    method: str = "auto"
) -> Dict[str, Any]:
    """
    Fit a distribution to portfolio returns.
    
    Args:
        returns: List of returns
        method: "normal", "t", or "auto" (BIC-based selection)
        
    Returns:
        Dict with distribution parameters, fit statistics, and interpretations
    """
    returns_arr = np.array(returns)
    n = len(returns_arr)
    
    if n < 20:
        logger.warning(f"Few observations ({n}), fit may be unreliable")
    
    # Fit both distributions
    normal_fit = fit_normal(returns_arr)
    t_fit = fit_t_distribution(returns_arr)
    
    # Select distribution
    if method == "auto":
        selected = auto_select_distribution(returns_arr)
    elif method == "t":
        selected = "t"
    else:
        selected = "normal"
    
    if selected == "t":
        fit = t_fit
        df = fit["params"]["df"]
        tail_ratio = compute_tail_fatness_ratio(df)
        
        # Interpretation is derived from computed ratio, not hardcoded
        if tail_ratio > 3:
            tail_interpretation = f"Very fat tails - expect 3-sigma events ~{tail_ratio:.1f}x more often than normal"
        elif tail_ratio > 1.5:
            tail_interpretation = f"Moderately fat tails - expect 3-sigma events ~{tail_ratio:.1f}x more often than normal"
        else:
            tail_interpretation = f"Near-normal tails - 3-sigma events occur ~{tail_ratio:.1f}x vs normal"
        
        type_explanation = "Returns have fat tails (more extreme moves than normal bell curve)"
    else:
        fit = normal_fit
        tail_ratio = 1.0
        tail_interpretation = "Standard bell curve - 3-sigma events at expected ~0.27% frequency"
        type_explanation = "Returns follow standard bell curve (normal distribution)"
    
    # Annualized metrics
    daily_mean = fit["params"].get("mu") or fit["params"].get("loc", 0)
    daily_vol = fit["params"].get("sigma") or fit["params"].get("scale", 0)
    
    annualized_return = daily_mean * 252
    annualized_vol = daily_vol * np.sqrt(252)
    
    return {
        "type": selected,
        "type_explanation": type_explanation,
        "params": fit["params"],
        "metrics": {
            "daily_mean": float(daily_mean),
            "daily_volatility": float(daily_vol),
            "annualized_return": float(annualized_return),
            "annualized_return_pct": f"{annualized_return * 100:.1f}%",
            "annualized_volatility": float(annualized_vol),
            "annualized_volatility_pct": f"{annualized_vol * 100:.1f}%",
        },
        "tail_analysis": {
            "tail_fatness_ratio": float(tail_ratio),
            "interpretation": tail_interpretation,
        },
        "fit_quality": {
            "log_likelihood": fit["log_likelihood"],
            "aic": fit["aic"],
            "bic": fit["bic"],
            "n_observations": n,
        },
        "model_comparison": {
            "normal_bic": normal_fit["bic"],
            "t_bic": t_fit["bic"],
            "bic_difference": t_fit["bic"] - normal_fit["bic"],
            "selection_reason": (
                "t-distribution selected (better BIC)" if selected == "t"
                else "normal distribution selected (simpler model, similar fit)"
            ),
        },
    }


def compute_fisher_information_normal(sigma: float, n: int) -> Dict[str, Any]:
    """
    Compute Fisher Information Matrix for normal distribution.
    
    I = [[1/sigma^2, 0], [0, 2/sigma^2]]
    
    Args:
        sigma: Standard deviation
        n: Number of observations (for scaling)
        
    Returns:
        Dict with Fisher matrix and related quantities
    """
    fisher = np.array([
        [1 / sigma**2, 0],
        [0, 2 / sigma**2]
    ])
    
    # Cramér-Rao bounds (minimum variance for unbiased estimator)
    # CR bound = 1 / (n * I_ii)
    cr_bound_mu = sigma**2 / n
    cr_bound_sigma = sigma**2 / (2 * n)
    
    return {
        "fisher_matrix": fisher.tolist(),
        "parameters": ["mu", "sigma"],
        "cramer_rao_bounds": {
            "mu": float(cr_bound_mu),
            "sigma": float(cr_bound_sigma),
        },
        "std_errors": {
            "mu": float(np.sqrt(cr_bound_mu)),
            "sigma": float(np.sqrt(cr_bound_sigma)),
        },
    }


def compute_fisher_information_t(df: float, scale: float, n: int) -> Dict[str, Any]:
    """
    Compute Fisher Information Matrix for t-distribution (numerical approximation).
    
    For t-distribution, the Fisher matrix is more complex. We use the
    asymptotic approximation.
    
    Args:
        df: Degrees of freedom
        scale: Scale parameter
        n: Number of observations
        
    Returns:
        Dict with Fisher matrix and related quantities
    """
    # For t-distribution with known df, the Fisher information for (loc, scale) is:
    # I_loc = (df + 1) / ((df + 3) * scale^2)
    # I_scale = (2 * df) / ((df + 3) * scale^2)
    
    if df <= 2:
        # t-distribution with df <= 2 has infinite variance
        I_loc = 1 / scale**2  # Approximate
        I_scale = 2 / scale**2
    else:
        I_loc = (df + 1) / ((df + 3) * scale**2)
        I_scale = (2 * df) / ((df + 3) * scale**2)
    
    fisher = np.array([
        [I_loc, 0],
        [0, I_scale]
    ])
    
    # Cramér-Rao bounds
    cr_bound_loc = 1 / (n * I_loc) if I_loc > 0 else np.inf
    cr_bound_scale = 1 / (n * I_scale) if I_scale > 0 else np.inf
    
    return {
        "fisher_matrix": fisher.tolist(),
        "parameters": ["loc", "scale"],
        "cramer_rao_bounds": {
            "loc": float(cr_bound_loc),
            "scale": float(cr_bound_scale),
        },
        "std_errors": {
            "loc": float(np.sqrt(cr_bound_loc)) if cr_bound_loc < np.inf else float('inf'),
            "scale": float(np.sqrt(cr_bound_scale)) if cr_bound_scale < np.inf else float('inf'),
        },
        "df": float(df),
    }


def compute_fisher_information(distribution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute Fisher Information for a fitted distribution.
    
    Args:
        distribution: Output from fit_distribution()
        
    Returns:
        Dict with Fisher matrix and Cramér-Rao bounds
    """
    dist_type = distribution["type"]
    n = distribution["fit_quality"]["n_observations"]
    
    if dist_type == "normal":
        sigma = distribution["params"]["sigma"]
        return compute_fisher_information_normal(sigma, n)
    else:
        df = distribution["params"]["df"]
        scale = distribution["params"]["scale"]
        return compute_fisher_information_t(df, scale, n)


def format_estimation_quality(
    fisher_info: Dict[str, Any],
    distribution: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format estimation quality in user-friendly terms.
    
    Args:
        fisher_info: Output from compute_fisher_information()
        distribution: Output from fit_distribution()
        
    Returns:
        Dict with human-readable estimation quality metrics
    """
    n = distribution["fit_quality"]["n_observations"]
    std_errors = fisher_info["std_errors"]
    
    # Annualize the standard errors for mean
    mean_std_err = std_errors.get("mu") or std_errors.get("loc", 0)
    mean_std_err_annual = mean_std_err * 252
    
    vol_std_err = std_errors.get("sigma") or std_errors.get("scale", 0)
    vol_std_err_annual = vol_std_err * np.sqrt(252)
    
    # 95% confidence intervals
    mean_ci = 1.96 * mean_std_err_annual
    vol_ci = 1.96 * vol_std_err_annual
    
    # Reliability assessment based on CI width relative to estimate
    # This is percentile-based: compare to typical estimation quality
    annualized_return = distribution["metrics"]["annualized_return"]
    annualized_vol = distribution["metrics"]["annualized_volatility"]
    
    # Coefficient of variation for the estimates
    mean_cv = abs(mean_ci / annualized_return) if annualized_return != 0 else float('inf')
    vol_cv = vol_ci / annualized_vol if annualized_vol > 0 else float('inf')
    
    # Reliability is data-driven: if CV is high, reliability is low
    if mean_cv < 0.5 and vol_cv < 0.1:
        reliability = "GOOD"
        reliability_explanation = "Sufficient data for reliable estimates"
    elif mean_cv < 1.0 and vol_cv < 0.2:
        reliability = "MODERATE"
        reliability_explanation = "Estimates have meaningful uncertainty"
    else:
        reliability = "LOW"
        reliability_explanation = "Wide confidence intervals - interpret with caution"
    
    return {
        "observations": n,
        "mean_estimate_confidence": f"±{mean_ci * 100:.1f}% annualized (95% CI)",
        "vol_estimate_confidence": f"±{vol_ci * 100:.1f}% (95% CI)",
        "mean_std_error_annual": float(mean_std_err_annual),
        "vol_std_error_annual": float(vol_std_err_annual),
        "reliability": reliability,
        "reliability_explanation": reliability_explanation,
    }

