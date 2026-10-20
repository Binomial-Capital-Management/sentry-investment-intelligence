"""
Probability Calculator for Instanton Rare Event Analyzer

Converts instanton action to crash probability estimates using saddle-point
approximation. Also computes severity distributions and confidence intervals.

Core formula: P(crash) ≈ exp(-S[instanton]) × prefactor

The prefactor comes from Gaussian integration around the saddle point
(fluctuation corrections). For practical purposes, it's often O(1).
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

import numpy as np
from scipy import stats

from .instanton_solver import InstantonPath, compute_instanton

logger = logging.getLogger(__name__)


@dataclass
class CrashProbability:
    """Container for crash probability estimates."""
    probability: float           # Main estimate
    action: float               # Instanton action
    prefactor: float            # Fluctuation correction
    confidence_interval: Tuple[float, float]  # 95% CI
    gaussian_estimate: float    # What Gaussian would predict
    tail_multiplier: float      # How much fatter tails increase risk
    method: str                 # Calculation method


def saddle_point_probability(action: float, prefactor: float = 1.0) -> float:
    """
    Compute probability from instanton action via saddle-point approximation.
    
    P ≈ prefactor × exp(-action)
    
    Args:
        action: Instanton action S[φ]
        prefactor: Fluctuation correction (default 1.0)
        
    Returns:
        Probability estimate
    """
    # Avoid underflow for very large actions
    if action > 700:
        return 0.0
    
    return prefactor * np.exp(-action)


def compute_fluctuation_prefactor(
    sigma: float,
    horizon_days: int,
    crash_pct: float,
) -> float:
    """
    Compute the fluctuation prefactor (Gaussian integration around saddle).
    
    For GBM, this comes from the path integral measure and gives
    a prefactor of order 1/sqrt(2π σ² T).
    
    Args:
        sigma: Daily volatility
        horizon_days: Time horizon
        crash_pct: Crash percentage
        
    Returns:
        Prefactor (typically 0.1 - 10)
    """
    # Approximate prefactor from Gaussian fluctuations
    # This is the "width" of the Gaussian around the instanton
    
    T = horizon_days
    
    # For a one-dimensional integral, prefactor ~ 1/sqrt(2π variance)
    # The variance is σ² × T (total variance over horizon)
    total_variance = sigma**2 * T
    
    # Prefactor
    prefactor = 1.0 / np.sqrt(2 * np.pi * total_variance)
    
    # Clamp to reasonable range
    return float(np.clip(prefactor, 0.01, 100))


def crash_probability_gaussian(
    crash_pct: float,
    horizon_days: int,
    sigma: float,
    mu: float = 0.0,
) -> float:
    """
    Compute crash probability assuming Gaussian (normal) returns.
    
    This is the baseline that underestimates tail risk.
    
    Args:
        crash_pct: Crash as percentage (e.g., -20.0)
        horizon_days: Time horizon in trading days
        sigma: Daily volatility
        mu: Daily drift
        
    Returns:
        Crash probability under Gaussian assumption
    """
    # Required log return
    log_return = np.log(1 + crash_pct / 100)
    
    # Distribution of log return over horizon
    horizon_mu = mu * horizon_days
    horizon_sigma = sigma * np.sqrt(horizon_days)
    
    # P(log return < log_return) = CDF
    probability = stats.norm.cdf(log_return, loc=horizon_mu, scale=horizon_sigma)
    
    return float(probability)


def crash_probability_student_t(
    crash_pct: float,
    horizon_days: int,
    sigma: float,
    df: float,
    mu: float = 0.0,
) -> float:
    """
    Compute crash probability for Student-t distributed returns.
    
    Fat tails increase crash probability compared to Gaussian.
    
    Args:
        crash_pct: Crash as percentage
        horizon_days: Time horizon
        sigma: Daily scale parameter
        df: Degrees of freedom
        mu: Daily location parameter
        
    Returns:
        Crash probability under Student-t assumption
    """
    # Required log return
    log_return = np.log(1 + crash_pct / 100)
    
    # For t-distribution, variance scales differently
    # Var(sum) = T × Var(daily) for independent
    # But for t-dist with df > 2, Var = σ² × df/(df-2)
    
    horizon_mu = mu * horizon_days
    
    if df > 2:
        daily_var = sigma**2 * df / (df - 2)
    else:
        daily_var = sigma**2 * 10  # Approximate for low df
    
    horizon_sigma = np.sqrt(daily_var * horizon_days)
    
    # Approximate with scaled t-distribution
    # The sum of t-distributed RVs isn't exactly t, but this is a good approx
    z = (log_return - horizon_mu) / horizon_sigma
    probability = stats.t.cdf(z, df=df)
    
    return float(probability)


def compute_crash_probability(
    instanton: InstantonPath,
    sigma: float,
    horizon_days: int,
    crash_pct: float,
    df: Optional[float] = None,
    mu: float = 0.0,
    include_prefactor: bool = True,
) -> CrashProbability:
    """
    Compute crash probability from instanton.
    
    Args:
        instanton: The instanton path
        sigma: Daily volatility
        horizon_days: Time horizon
        crash_pct: Crash percentage
        df: Degrees of freedom (None for Gaussian)
        mu: Daily drift
        include_prefactor: Whether to include fluctuation correction
        
    Returns:
        CrashProbability with estimates and comparisons
    """
    action = instanton.action
    
    # Fluctuation prefactor
    if include_prefactor:
        prefactor = compute_fluctuation_prefactor(sigma, horizon_days, crash_pct)
    else:
        prefactor = 1.0
    
    # Instanton probability
    prob_instanton = saddle_point_probability(action, prefactor)
    
    # Gaussian baseline
    prob_gaussian = crash_probability_gaussian(crash_pct, horizon_days, sigma, mu)
    
    # Student-t probability (if applicable)
    if df is not None and np.isfinite(df):
        prob_t = crash_probability_student_t(crash_pct, horizon_days, sigma, df, mu)
        # Use t-distribution probability as it's more accurate for heavy tails
        main_prob = prob_t
        tail_multiplier = prob_t / prob_gaussian if prob_gaussian > 0 else 1.0
    else:
        main_prob = prob_instanton
        tail_multiplier = 1.0
    
    # Confidence interval (approximate via parameter uncertainty)
    # Assume ~20% uncertainty in sigma estimate
    sigma_low = sigma * 0.85
    sigma_high = sigma * 1.15
    
    if df is not None and np.isfinite(df):
        ci_low = crash_probability_student_t(crash_pct, horizon_days, sigma_low, df, mu)
        ci_high = crash_probability_student_t(crash_pct, horizon_days, sigma_high, df, mu)
    else:
        ci_low = crash_probability_gaussian(crash_pct, horizon_days, sigma_low, mu)
        ci_high = crash_probability_gaussian(crash_pct, horizon_days, sigma_high, mu)
    
    return CrashProbability(
        probability=main_prob,
        action=action,
        prefactor=prefactor,
        confidence_interval=(ci_low, ci_high),
        gaussian_estimate=prob_gaussian,
        tail_multiplier=tail_multiplier,
        method="student_t" if df is not None else "gaussian",
    )


def compute_severity_distribution(
    S0: float,
    horizon_days: int,
    sigma: float,
    mu: float = 0.0,
    df: Optional[float] = None,
    n_points: int = 50,
) -> Dict[str, Any]:
    """
    Compute probability distribution over crash severities.
    
    This gives the full picture: P(crash) for various crash levels.
    
    Args:
        S0: Starting price
        horizon_days: Time horizon
        sigma: Daily volatility
        mu: Daily drift
        df: Degrees of freedom (None for Gaussian)
        n_points: Number of points in distribution
        
    Returns:
        Dict with crash levels and probabilities
    """
    # Range of crash percentages to analyze
    crash_levels = np.linspace(-50, 0, n_points)  # -50% to 0%
    
    probabilities = []
    
    for crash_pct in crash_levels:
        if df is not None and np.isfinite(df):
            prob = crash_probability_student_t(crash_pct, horizon_days, sigma, df, mu)
        else:
            prob = crash_probability_gaussian(crash_pct, horizon_days, sigma, mu)
        probabilities.append(prob)
    
    probabilities = np.array(probabilities)
    
    # Compute PDF (derivative of CDF)
    pdf = np.diff(probabilities) / np.diff(crash_levels)
    pdf_levels = (crash_levels[:-1] + crash_levels[1:]) / 2
    
    # Key statistics
    var_95_idx = np.searchsorted(probabilities, 0.05)
    var_99_idx = np.searchsorted(probabilities, 0.01)
    
    var_95 = crash_levels[var_95_idx] if var_95_idx < len(crash_levels) else crash_levels[-1]
    var_99 = crash_levels[var_99_idx] if var_99_idx < len(crash_levels) else crash_levels[-1]
    
    # Expected shortfall (CVaR) at 99%
    # Average loss given loss exceeds VaR
    tail_mask = crash_levels <= var_99
    if np.any(tail_mask) and probabilities[tail_mask].sum() > 0:
        # Approximate ES as weighted average of tail
        weights = np.diff(np.concatenate([[0], probabilities[tail_mask]]))
        if len(weights) > 0 and weights.sum() > 0:
            es_99 = np.average(crash_levels[tail_mask][:len(weights)], weights=np.abs(weights))
        else:
            es_99 = var_99
    else:
        es_99 = var_99
    
    return {
        "crash_levels": crash_levels.tolist(),
        "cumulative_probabilities": probabilities.tolist(),
        "pdf_levels": pdf_levels.tolist(),
        "pdf_values": pdf.tolist(),
        "statistics": {
            "var_95": float(var_95),
            "var_99": float(var_99),
            "expected_shortfall_99": float(es_99),
        },
        "horizon_days": horizon_days,
        "distribution_type": "student_t" if df is not None else "gaussian",
    }


def compute_scenario_probabilities(
    S0: float,
    scenarios: List[Dict[str, Any]],
    horizon_days: int,
    sigma: float,
    mu: float = 0.0,
    df: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Compute crash probabilities for multiple scenarios.
    
    Args:
        S0: Starting price/value
        scenarios: List of scenario dicts with 'name' and 'crash_pct'
        horizon_days: Time horizon
        sigma: Daily volatility
        mu: Daily drift
        df: Degrees of freedom
        
    Returns:
        List of scenario results with probabilities
    """
    results = []
    
    for scenario in scenarios:
        crash_pct = scenario["crash_pct"]
        name = scenario.get("name", f"{crash_pct:.0f}% crash")
        method = scenario.get("method", "user_specified")
        
        # Compute instanton
        instanton = compute_instanton(S0, crash_pct, horizon_days, sigma, mu, df)
        
        # Compute probability
        prob_result = compute_crash_probability(
            instanton, sigma, horizon_days, crash_pct, df, mu
        )
        
        results.append({
            "name": name,
            "method": method,
            "crash_pct": crash_pct,
            "crash_price": S0 * (1 + crash_pct / 100),
            "probability": prob_result.probability,
            "probability_pct": f"{prob_result.probability * 100:.2f}%",
            "action": prob_result.action,
            "gaussian_estimate": prob_result.gaussian_estimate,
            "tail_multiplier": prob_result.tail_multiplier,
            "confidence_interval": {
                "lower": prob_result.confidence_interval[0],
                "upper": prob_result.confidence_interval[1],
            },
            "instanton_path": {
                "daily_return_pct": instanton.daily_return * 100,
                "interpretation": (
                    f"Most likely path: {instanton.daily_return*100:.2f}% daily "
                    f"for {horizon_days} days"
                ),
            },
        })
    
    return results


def probability_to_dict(prob: CrashProbability, crash_pct: float) -> Dict[str, Any]:
    """Convert CrashProbability to dict for JSON output."""
    return {
        "probability": prob.probability,
        "probability_pct": f"{prob.probability * 100:.3f}%",
        "action": prob.action,
        "prefactor": prob.prefactor,
        "confidence_interval": {
            "lower": prob.confidence_interval[0],
            "lower_pct": f"{prob.confidence_interval[0] * 100:.3f}%",
            "upper": prob.confidence_interval[1],
            "upper_pct": f"{prob.confidence_interval[1] * 100:.3f}%",
        },
        "comparison_to_gaussian": {
            "gaussian_estimate": prob.gaussian_estimate,
            "gaussian_pct": f"{prob.gaussian_estimate * 100:.3f}%",
            "tail_multiplier": prob.tail_multiplier,
            "interpretation": (
                f"Fat tails increase {crash_pct:.0f}% crash risk by "
                f"{prob.tail_multiplier:.1f}x vs Gaussian assumption"
                if prob.tail_multiplier > 1.1 else
                "Gaussian approximation is reasonable"
            ),
        },
        "method": prob.method,
    }


















