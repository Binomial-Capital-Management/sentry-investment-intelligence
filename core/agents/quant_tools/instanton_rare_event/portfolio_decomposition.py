"""
Portfolio Decomposition for Instanton Rare Event Analyzer

Analyzes which assets drive portfolio crash risk and how correlations
behave differently during crashes vs normal times.

Key insights:
- Crash contributions differ from weights (high-vol assets dominate)
- Correlations SPIKE during crashes (diversification fails when needed most)
- Diversification decay quantifies how much protection you lose in tails
"""

from typing import Dict, List, Any, Optional, Tuple
import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def compute_crash_contributions(
    weights: List[float],
    volatilities: Dict[str, float],
    correlation_matrix: np.ndarray,
    tickers: List[str],
) -> Dict[str, Any]:
    """
    Decompose portfolio crash risk into per-asset contributions.
    
    Crash contribution ≠ weight. A 20% weight in NVDA with 45% vol
    contributes more to crash risk than 20% in KO with 15% vol.
    
    Uses marginal contribution to risk (MCR) methodology.
    
    Args:
        weights: Portfolio weights
        volatilities: Dict of ticker -> annualized volatility
        correlation_matrix: Correlation matrix (same order as tickers)
        tickers: List of ticker symbols
        
    Returns:
        Dict with crash contributions and interpretation
    """
    n = len(tickers)
    weights_arr = np.array(weights)
    
    # Build volatility vector
    vols = np.array([volatilities.get(t, 0.2) for t in tickers])
    
    # Covariance matrix from correlation and volatilities
    # Cov = diag(vol) @ Corr @ diag(vol)
    cov_matrix = np.outer(vols, vols) * correlation_matrix
    
    # Portfolio variance
    portfolio_var = weights_arr @ cov_matrix @ weights_arr
    portfolio_vol = np.sqrt(portfolio_var)
    
    # Marginal contribution to risk: ∂σ_p/∂w_i = (Σ w)_i / σ_p
    marginal_risk = (cov_matrix @ weights_arr) / portfolio_vol
    
    # Total contribution = w_i × MCR_i
    total_contributions = weights_arr * marginal_risk
    
    # Percentage contributions (should sum to portfolio vol)
    pct_contributions = total_contributions / portfolio_vol
    
    # Build result
    contributions = {}
    for i, ticker in enumerate(tickers):
        contributions[ticker] = {
            "weight": float(weights[i]),
            "weight_pct": f"{weights[i]*100:.1f}%",
            "volatility": float(vols[i]),
            "volatility_pct": f"{vols[i]*100:.1f}%",
            "crash_contribution": float(pct_contributions[i]),
            "crash_contribution_pct": f"{pct_contributions[i]*100:.1f}%",
            "contribution_vs_weight_ratio": float(pct_contributions[i] / weights[i]) if weights[i] > 0 else 0,
        }
    
    # Find dominant risk contributor
    max_contrib_idx = np.argmax(pct_contributions)
    max_contrib_ticker = tickers[max_contrib_idx]
    
    # Interpretation
    if pct_contributions[max_contrib_idx] > weights_arr[max_contrib_idx] * 1.5:
        interpretation = (
            f"{max_contrib_ticker} dominates crash risk ({pct_contributions[max_contrib_idx]*100:.0f}%) "
            f"despite {weights_arr[max_contrib_idx]*100:.0f}% weight - consider hedging specifically"
        )
    else:
        interpretation = "Crash risk is roughly proportional to weights"
    
    return {
        "by_asset": contributions,
        "portfolio_volatility": float(portfolio_vol),
        "dominant_risk_contributor": max_contrib_ticker,
        "interpretation": interpretation,
    }


def estimate_crash_correlations(
    returns_df: pd.DataFrame,
    threshold_sigma: float = -2.0,
) -> Dict[str, Any]:
    """
    Estimate correlations conditional on crash (returns below threshold).
    
    Correlations typically SPIKE during crashes. This means diversification
    fails exactly when you need it most.
    
    Args:
        returns_df: DataFrame of asset returns (columns = tickers)
        threshold_sigma: Threshold in standard deviations (e.g., -2.0)
        
    Returns:
        Dict with normal and crash correlation matrices
    """
    tickers = list(returns_df.columns)
    n = len(tickers)
    
    # Compute standardized returns
    means = returns_df.mean()
    stds = returns_df.std()
    standardized = (returns_df - means) / stds
    
    # Normal (unconditional) correlation
    normal_corr = returns_df.corr().values
    
    # Crash regime: at least one asset below threshold
    crash_mask = (standardized < threshold_sigma).any(axis=1)
    n_crash_days = crash_mask.sum()
    
    if n_crash_days < 10:
        # Not enough crash observations
        logger.warning(f"Only {n_crash_days} crash days, using normal correlations")
        crash_corr = normal_corr
    else:
        crash_returns = returns_df[crash_mask]
        crash_corr = crash_returns.corr().values
    
    # Handle NaN in crash correlations
    crash_corr = np.nan_to_num(crash_corr, nan=0.9)  # Default to high correlation
    
    # Average correlations (excluding diagonal)
    mask = ~np.eye(n, dtype=bool)
    avg_normal_corr = normal_corr[mask].mean() if n > 1 else 0
    avg_crash_corr = crash_corr[mask].mean() if n > 1 else 0
    
    # Correlation spike
    corr_spike = avg_crash_corr - avg_normal_corr
    
    # Return summary (omit full correlation matrices to prevent context overflow)
    # Full matrices are embedded in cached charts
    return {
        # Removed: normal_correlation and crash_correlation matrices (n×n can be large)
        "tickers": tickers,
        "n_assets": len(tickers),
        "average_normal_correlation": float(avg_normal_corr),
        "average_crash_correlation": float(avg_crash_corr),
        "correlation_spike": float(corr_spike),
        "n_crash_observations": int(n_crash_days),
        "threshold_sigma": threshold_sigma,
        "interpretation": (
            f"Correlations spike from {avg_normal_corr:.2f} to {avg_crash_corr:.2f} in crashes. "
            f"Diversification benefit reduced during tail events."
            if corr_spike > 0.1 else
            "Correlations relatively stable across regimes"
        ),
    }


def compute_diversification_decay(
    weights: List[float],
    normal_corr: np.ndarray,
    crash_corr: np.ndarray,
    volatilities: Dict[str, float],
    tickers: List[str],
) -> Dict[str, Any]:
    """
    Compute how much diversification benefit is lost during crashes.
    
    Diversification ratio = portfolio vol / weighted avg vol
    < 1 means diversification helps
    = 1 means no diversification benefit
    
    Args:
        weights: Portfolio weights
        normal_corr: Normal regime correlation matrix
        crash_corr: Crash regime correlation matrix
        volatilities: Asset volatilities
        tickers: Ticker symbols
        
    Returns:
        Dict with diversification analysis
    """
    weights_arr = np.array(weights)
    vols = np.array([volatilities.get(t, 0.2) for t in tickers])
    
    # Weighted average volatility (if assets were independent)
    weighted_avg_vol = np.sum(weights_arr * vols)
    
    # Normal regime portfolio volatility
    normal_cov = np.outer(vols, vols) * normal_corr
    normal_port_var = weights_arr @ normal_cov @ weights_arr
    normal_port_vol = np.sqrt(normal_port_var)
    
    # Crash regime portfolio volatility
    crash_cov = np.outer(vols, vols) * crash_corr
    crash_port_var = weights_arr @ crash_cov @ weights_arr
    crash_port_vol = np.sqrt(crash_port_var)
    
    # Diversification ratios
    normal_div_ratio = normal_port_vol / weighted_avg_vol if weighted_avg_vol > 0 else 1
    crash_div_ratio = crash_port_vol / weighted_avg_vol if weighted_avg_vol > 0 else 1
    
    # Diversification benefit (how much vol is reduced)
    normal_benefit = 1 - normal_div_ratio  # e.g., 0.3 = 30% vol reduction
    crash_benefit = 1 - crash_div_ratio
    
    # Benefit decay
    if normal_benefit > 0:
        benefit_decay = (normal_benefit - crash_benefit) / normal_benefit
    else:
        benefit_decay = 0
    
    return {
        "weighted_average_volatility": float(weighted_avg_vol),
        "normal_regime": {
            "portfolio_volatility": float(normal_port_vol),
            "diversification_ratio": float(normal_div_ratio),
            "diversification_benefit": float(normal_benefit),
            "benefit_pct": f"{normal_benefit*100:.0f}%",
        },
        "crash_regime": {
            "portfolio_volatility": float(crash_port_vol),
            "diversification_ratio": float(crash_div_ratio),
            "diversification_benefit": float(crash_benefit),
            "benefit_pct": f"{crash_benefit*100:.0f}%",
        },
        "benefit_decay": float(benefit_decay),
        "benefit_decay_pct": f"{benefit_decay*100:.0f}%",
        "interpretation": (
            f"Diversification benefit drops from {normal_benefit*100:.0f}% to "
            f"{crash_benefit*100:.0f}% during crashes ({benefit_decay*100:.0f}% decay)"
            if benefit_decay > 0.1 else
            "Diversification benefit relatively stable"
        ),
    }


def compute_joint_crash_analysis(
    weights: List[float],
    volatilities: Dict[str, float],
    correlation_matrix: np.ndarray,
    tickers: List[str],
    crash_pct: float,
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Analyze joint crash probability (all assets crashing together).
    
    Computes:
    - Marginal crash prob for each asset
    - Joint crash prob (all crash simultaneously)
    - Conditional probs (if A crashes, prob B crashes)
    
    Args:
        weights: Portfolio weights
        volatilities: Asset volatilities
        correlation_matrix: Correlation matrix
        tickers: Ticker symbols
        crash_pct: Crash percentage
        horizon_days: Time horizon
        
    Returns:
        Dict with joint crash analysis
    """
    n = len(tickers)
    vols = np.array([volatilities.get(t, 0.2) for t in tickers])
    
    # Convert annual vol to horizon vol
    horizon_vols = vols * np.sqrt(horizon_days / 252)
    
    # Required log return for crash
    log_return = np.log(1 + crash_pct / 100)
    
    # Marginal crash probabilities (assuming normal for simplicity)
    marginal_probs = {}
    for i, ticker in enumerate(tickers):
        z = log_return / horizon_vols[i]
        prob = float(stats.norm.cdf(z))
        marginal_probs[ticker] = {
            "probability": prob,
            "probability_pct": f"{prob*100:.2f}%",
        }
    
    # Joint crash probability (multivariate normal)
    # For high correlations, joint prob ≈ marginal prob of weakest link
    # For low correlations, joint prob ≈ product of marginals
    
    avg_corr = correlation_matrix[~np.eye(n, dtype=bool)].mean() if n > 1 else 0
    
    marginal_array = np.array([marginal_probs[t]["probability"] for t in tickers])
    
    if avg_corr > 0.7:
        # High correlation: joint ≈ max marginal (approximately)
        joint_prob = float(np.max(marginal_array))
        joint_method = "high_correlation_approximation"
    else:
        # Lower correlation: use product as lower bound
        # True joint prob is between product and min marginal
        product_prob = float(np.prod(marginal_array))
        max_marginal = float(np.max(marginal_array))
        joint_prob = (product_prob + max_marginal) / 2  # Rough interpolation
        joint_method = "interpolation"
    
    # Conditional probabilities (using Gaussian copula approximation)
    conditional_probs = {}
    for i, ticker_i in enumerate(tickers):
        for j, ticker_j in enumerate(tickers):
            if i >= j:
                continue
            
            corr = correlation_matrix[i, j]
            # P(j crashes | i crashes) ≈ P(j crashes) adjusted for correlation
            # Using bivariate normal approximation
            if marginal_probs[ticker_i]["probability"] > 0.001:
                # Higher correlation → higher conditional prob
                conditional = marginal_probs[ticker_j]["probability"] * (1 + corr) / 2
                conditional = min(conditional * (1 + corr), 0.99)
            else:
                conditional = marginal_probs[ticker_j]["probability"]
            
            key = f"P({ticker_j}_crash|{ticker_i}_crash)"
            conditional_probs[key] = float(conditional)
    
    return {
        "marginal_crash_probabilities": marginal_probs,
        "joint_crash_probability": joint_prob,
        "joint_crash_pct": f"{joint_prob*100:.3f}%",
        "joint_method": joint_method,
        "conditional_probabilities": conditional_probs,
        "average_correlation": float(avg_corr),
        "interpretation": (
            f"If one asset crashes {crash_pct:.0f}%, others likely follow due to "
            f"high correlation ({avg_corr:.2f})"
            if avg_corr > 0.5 else
            f"Assets have moderate correlation ({avg_corr:.2f}) - some crash diversification"
        ),
    }


def full_portfolio_decomposition(
    returns_df: pd.DataFrame,
    weights: List[float],
    tickers: List[str],
    crash_pct: float,
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Complete portfolio crash decomposition analysis.
    
    Args:
        returns_df: DataFrame of asset returns
        weights: Portfolio weights
        tickers: Ticker symbols
        crash_pct: Crash percentage
        horizon_days: Time horizon
        
    Returns:
        Dict with full decomposition analysis
    """
    # Compute volatilities from data
    volatilities = {
        ticker: float(returns_df[ticker].std() * np.sqrt(252))
        for ticker in tickers
        if ticker in returns_df.columns
    }
    
    # Normal correlation matrix
    normal_corr = returns_df.corr().values
    
    # Crash correlations
    crash_corr_result = estimate_crash_correlations(returns_df)
    crash_corr = np.array(crash_corr_result["crash_correlation"])
    
    # Crash contributions
    contributions = compute_crash_contributions(
        weights, volatilities, normal_corr, tickers
    )
    
    # Diversification decay
    diversification = compute_diversification_decay(
        weights, normal_corr, crash_corr, volatilities, tickers
    )
    
    # Joint crash analysis
    joint_analysis = compute_joint_crash_analysis(
        weights, volatilities, crash_corr, tickers, crash_pct, horizon_days
    )
    
    return {
        "crash_contributions": contributions,
        "correlation_analysis": crash_corr_result,
        "diversification_analysis": diversification,
        "joint_crash_analysis": joint_analysis,
    }
















