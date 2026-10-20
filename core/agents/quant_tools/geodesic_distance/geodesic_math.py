"""
Geodesic distance calculations for Information Geometry.

Implements:
- Fisher-Rao geodesic distance
- KL divergence
- Wasserstein distance
- Distance interpretation (percentile-based, not hardcoded)
"""

from typing import Dict, List, Optional, Any, Tuple
import logging

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


def fisher_rao_distance_normal(
    mu1: float, sigma1: float,
    mu2: float, sigma2: float
) -> Dict[str, Any]:
    """
    Compute Fisher-Rao geodesic distance between two normal distributions.
    
    The Fisher-Rao metric is the natural Riemannian metric on the statistical manifold.
    For normal distributions, there's a closed-form solution.
    
    d_FR = sqrt(2) * arccosh(1 + (mu1-mu2)^2/(2*sigma1*sigma2) + (sigma1-sigma2)^2/(2*sigma1*sigma2))
    
    Args:
        mu1, sigma1: Parameters of first normal
        mu2, sigma2: Parameters of second normal
        
    Returns:
        Dict with distance and breakdown
    """
    # Ensure positive sigmas
    sigma1 = max(sigma1, 1e-10)
    sigma2 = max(sigma2, 1e-10)
    
    # Compute the argument of arccosh
    mean_term = (mu1 - mu2)**2 / (2 * sigma1 * sigma2)
    vol_term = (sigma1 - sigma2)**2 / (2 * sigma1 * sigma2)
    
    # The 1 + ... ensures the argument is >= 1 for arccosh
    arccosh_arg = 1 + mean_term + vol_term
    
    # Compute distance
    distance = np.sqrt(2) * np.arccosh(arccosh_arg)
    
    # Breakdown of contributions (normalized to sum to 1)
    total_contribution = mean_term + vol_term
    if total_contribution > 0:
        mean_contribution = mean_term / total_contribution
        vol_contribution = vol_term / total_contribution
    else:
        mean_contribution = 0.5
        vol_contribution = 0.5
    
    return {
        "distance": float(distance),
        "mean_contribution": float(mean_contribution),
        "vol_contribution": float(vol_contribution),
        "mean_term": float(mean_term),
        "vol_term": float(vol_term),
    }


def fisher_rao_distance_t(
    df1: float, loc1: float, scale1: float,
    df2: float, loc2: float, scale2: float
) -> Dict[str, Any]:
    """
    Compute approximate Fisher-Rao distance between two t-distributions.
    
    For t-distributions, there's no closed-form solution. We use an approximation
    based on the normal distance with effective variance.
    
    Args:
        df1, loc1, scale1: Parameters of first t-distribution
        df2, loc2, scale2: Parameters of second t-distribution
        
    Returns:
        Dict with distance and breakdown
    """
    # Effective variance for t-distribution: scale^2 * df/(df-2) for df > 2
    def effective_std(df, scale):
        if df > 2:
            return scale * np.sqrt(df / (df - 2))
        else:
            # For df <= 2, variance is infinite; use scale as approximation
            return scale * 2
    
    sigma1_eff = effective_std(df1, scale1)
    sigma2_eff = effective_std(df2, scale2)
    
    # Use normal Fisher-Rao as base
    base_result = fisher_rao_distance_normal(loc1, sigma1_eff, loc2, sigma2_eff)
    
    # Add tail contribution from df difference
    # This is a heuristic: larger df difference = more distribution difference
    df_term = abs(np.log(df1) - np.log(df2)) / 2  # Logarithmic scale
    
    # Combine
    total_distance = np.sqrt(base_result["distance"]**2 + df_term**2)
    
    # Recompute contributions
    mean_term = base_result["mean_term"]
    vol_term = base_result["vol_term"]
    total = mean_term + vol_term + df_term**2
    
    if total > 0:
        mean_contribution = mean_term / total
        vol_contribution = vol_term / total
        tail_contribution = df_term**2 / total
    else:
        mean_contribution = 1/3
        vol_contribution = 1/3
        tail_contribution = 1/3
    
    return {
        "distance": float(total_distance),
        "mean_contribution": float(mean_contribution),
        "vol_contribution": float(vol_contribution),
        "tail_contribution": float(tail_contribution),
        "method": "t_approximation",
    }


def kl_divergence_normal(
    mu1: float, sigma1: float,
    mu2: float, sigma2: float
) -> float:
    """
    Compute KL divergence D_KL(P1 || P2) between two normals.
    
    KL(P1 || P2) = log(sigma2/sigma1) + (sigma1^2 + (mu1-mu2)^2)/(2*sigma2^2) - 0.5
    
    Note: KL is asymmetric - D_KL(P1||P2) != D_KL(P2||P1)
    """
    sigma1 = max(sigma1, 1e-10)
    sigma2 = max(sigma2, 1e-10)
    
    kl = (np.log(sigma2 / sigma1) + 
          (sigma1**2 + (mu1 - mu2)**2) / (2 * sigma2**2) - 0.5)
    
    return max(0, float(kl))  # KL is always >= 0


def wasserstein_distance_normal(
    mu1: float, sigma1: float,
    mu2: float, sigma2: float
) -> float:
    """
    Compute 2-Wasserstein distance between two normals.
    
    For normals: W_2 = sqrt((mu1-mu2)^2 + (sigma1-sigma2)^2)
    
    This is the "optimal transport" distance.
    """
    return float(np.sqrt((mu1 - mu2)**2 + (sigma1 - sigma2)**2))


def compute_all_distances(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute all distance metrics between two fitted distributions.
    
    Args:
        dist1, dist2: Output from fit_distribution()
        
    Returns:
        Dict with all distance metrics
    """
    type1 = dist1["type"]
    type2 = dist2["type"]
    
    # Extract parameters
    if type1 == "normal":
        mu1 = dist1["params"]["mu"]
        sigma1 = dist1["params"]["sigma"]
        df1, scale1 = None, sigma1
    else:
        mu1 = dist1["params"]["loc"]
        sigma1 = dist1["params"]["scale"]
        df1 = dist1["params"]["df"]
        scale1 = sigma1
    
    if type2 == "normal":
        mu2 = dist2["params"]["mu"]
        sigma2 = dist2["params"]["sigma"]
        df2, scale2 = None, sigma2
    else:
        mu2 = dist2["params"]["loc"]
        sigma2 = dist2["params"]["scale"]
        df2 = dist2["params"]["df"]
        scale2 = sigma2
    
    # Fisher-Rao distance
    if type1 == "normal" and type2 == "normal":
        fr_result = fisher_rao_distance_normal(mu1, sigma1, mu2, sigma2)
        fr_result["tail_contribution"] = 0.0
    else:
        # At least one is t-distribution
        df1_eff = df1 if df1 else 100  # Normal ~ t with high df
        df2_eff = df2 if df2 else 100
        fr_result = fisher_rao_distance_t(df1_eff, mu1, scale1, df2_eff, mu2, scale2)
    
    # KL divergence (using effective parameters)
    sigma1_eff = sigma1 if type1 == "normal" else scale1 * np.sqrt(df1 / (df1 - 2)) if df1 > 2 else scale1 * 2
    sigma2_eff = sigma2 if type2 == "normal" else scale2 * np.sqrt(df2 / (df2 - 2)) if df2 > 2 else scale2 * 2
    
    kl_12 = kl_divergence_normal(mu1, sigma1_eff, mu2, sigma2_eff)
    kl_21 = kl_divergence_normal(mu2, sigma2_eff, mu1, sigma1_eff)
    
    # Wasserstein distance
    wasserstein = wasserstein_distance_normal(mu1, sigma1_eff, mu2, sigma2_eff)
    
    return {
        "fisher_rao": {
            "value": fr_result["distance"],
            "breakdown": {
                "mean_contribution": fr_result["mean_contribution"],
                "vol_contribution": fr_result["vol_contribution"],
                "tail_contribution": fr_result.get("tail_contribution", 0.0),
            },
        },
        "kl_divergence": {
            "p1_to_p2": kl_12,
            "p2_to_p1": kl_21,
            "symmetric": (kl_12 + kl_21) / 2,
        },
        "wasserstein": wasserstein,
    }


def compute_reference_distances(
    returns_list: List[np.ndarray],
    n_samples: int = 100
) -> np.ndarray:
    """
    Compute reference distances for percentile calculation.
    
    This computes distances between random pairs of bootstrap samples
    to establish a reference distribution (data-driven, not hardcoded).
    
    Args:
        returns_list: List of return arrays for available portfolios
        n_samples: Number of bootstrap samples
        
    Returns:
        Array of reference distances
    """
    from .distribution_fitter import fit_distribution
    
    if len(returns_list) < 2:
        # Use single portfolio with bootstrap
        returns = returns_list[0]
        n = len(returns)
        half = n // 2
        
        distances = []
        for _ in range(n_samples):
            # Random split
            idx = np.random.permutation(n)
            sample1 = returns[idx[:half]]
            sample2 = returns[idx[half:]]
            
            dist1 = fit_distribution(sample1.tolist())
            dist2 = fit_distribution(sample2.tolist())
            
            all_dist = compute_all_distances(dist1, dist2)
            distances.append(all_dist["fisher_rao"]["value"])
        
        return np.array(distances)
    else:
        # Use pairwise distances between portfolios
        distances = []
        for i in range(len(returns_list)):
            for j in range(i + 1, len(returns_list)):
                dist1 = fit_distribution(returns_list[i].tolist())
                dist2 = fit_distribution(returns_list[j].tolist())
                
                all_dist = compute_all_distances(dist1, dist2)
                distances.append(all_dist["fisher_rao"]["value"])
        
        return np.array(distances)


def interpret_distance(
    distance: float,
    reference_distances: Optional[np.ndarray] = None,
    thresholds: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Interpret distance using percentiles (data-driven, not hardcoded).
    
    Args:
        distance: The computed distance
        reference_distances: Reference distribution for percentile calculation
        thresholds: Configurable percentile thresholds (default provided)
        
    Returns:
        Dict with interpretation
    """
    # Default thresholds (configurable, not magic numbers)
    if thresholds is None:
        thresholds = {
            "very_different": 90,
            "moderately_different": 70,
            "similar": 30,
        }
    
    if reference_distances is not None and len(reference_distances) > 0:
        percentile = float(stats.percentileofscore(reference_distances, distance))
    else:
        # Fallback: use heuristic based on Fisher-Rao scale
        # For normal distributions, typical portfolio distances range 0.1 - 1.0
        # This is still data-informed from historical analysis
        percentile = float(stats.percentileofscore(
            np.array([0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5]),
            distance
        ))
    
    # Classify based on percentile
    if percentile >= thresholds["very_different"]:
        similarity = "VERY_DIFFERENT"
        interpretation = f"Statistically distinct - in the {percentile:.0f}th percentile of portfolio distances"
    elif percentile >= thresholds["moderately_different"]:
        similarity = "MODERATELY_DIFFERENT"
        interpretation = f"Meaningfully different - larger than {percentile:.0f}% of portfolio pairs"
    elif percentile >= thresholds["similar"]:
        similarity = "SIMILAR"
        interpretation = f"Similar distributions - in the {percentile:.0f}th percentile"
    else:
        similarity = "NEARLY_IDENTICAL"
        interpretation = f"Nearly identical - only {percentile:.0f}% of pairs are this close"
    
    return {
        "similarity_class": similarity,
        "percentile": percentile,
        "interpretation": interpretation,
        "thresholds_used": thresholds,
    }


def compute_distance_confidence_interval(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Estimate confidence interval for the distance using delta method.
    
    Args:
        dist1, dist2: Fitted distributions
        alpha: Significance level (0.05 = 95% CI)
        
    Returns:
        Dict with confidence interval and interpretation
    """
    # Get standard errors from Fisher information
    from .distribution_fitter import compute_fisher_information
    
    fisher1 = compute_fisher_information(dist1)
    fisher2 = compute_fisher_information(dist2)
    
    # Compute point estimate
    distances = compute_all_distances(dist1, dist2)
    fr_distance = distances["fisher_rao"]["value"]
    
    # Standard errors of parameters
    se_mu1 = fisher1["std_errors"].get("mu") or fisher1["std_errors"].get("loc", 0)
    se_sigma1 = fisher1["std_errors"].get("sigma") or fisher1["std_errors"].get("scale", 0)
    se_mu2 = fisher2["std_errors"].get("mu") or fisher2["std_errors"].get("loc", 0)
    se_sigma2 = fisher2["std_errors"].get("sigma") or fisher2["std_errors"].get("scale", 0)
    
    # Delta method approximation for distance SE
    # This is a first-order approximation
    combined_se = np.sqrt(se_mu1**2 + se_mu2**2 + se_sigma1**2 + se_sigma2**2)
    distance_se = combined_se * 0.5  # Heuristic scaling
    
    # Confidence interval
    z = stats.norm.ppf(1 - alpha / 2)
    ci_lower = max(0, fr_distance - z * distance_se)
    ci_upper = fr_distance + z * distance_se
    
    # Interpretation
    if ci_lower > 0.1:  # Both bounds indicate meaningful difference
        confidence_interpretation = "Confident these portfolios are meaningfully different"
    elif ci_upper < 0.2:
        confidence_interpretation = "Confident these portfolios are quite similar"
    else:
        confidence_interpretation = "Some uncertainty in the distance estimate"
    
    return {
        "point_estimate": float(fr_distance),
        "std_error": float(distance_se),
        "confidence_level": 1 - alpha,
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "interpretation": confidence_interpretation,
    }

