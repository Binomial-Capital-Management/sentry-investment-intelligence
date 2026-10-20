"""
Recession Field Theory - Field Builder

Constructs the composite economic "field" φ(t) from standardized indicators.
The field represents the overall economic state at each point in time.

Methods:
- Weighted z-score average (default)
- PCA-based (first principal component)
- PCA-constrained (require yield curve loading)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List, Any
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# =============================================================================
# Z-SCORE STANDARDIZATION
# =============================================================================

def standardize_indicators(
    indicators: pd.DataFrame,
    inversions: Dict[str, bool],
    reference_period: Optional[int] = None
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, float]]]:
    """
    Standardize indicators to z-scores.
    
    Args:
        indicators: DataFrame with indicators as columns, DatetimeIndex
        inversions: Dict mapping indicator name -> should_invert
                   (True if higher values are bad for economy)
        reference_period: If provided, use first N periods for mean/std
                         Otherwise use full sample
    
    Returns:
        Tuple of (z_scores DataFrame, stats dict)
        Stats dict: {indicator: {"mean": float, "std": float, "inverted": bool}}
    """
    z_scores = pd.DataFrame(index=indicators.index)
    stats = {}
    
    for col in indicators.columns:
        series = indicators[col].dropna()
        
        if len(series) < 10:
            logger.warning(f"[FIELD] Insufficient data for {col}: {len(series)} points")
            continue
        
        # Calculate reference statistics
        if reference_period and len(series) > reference_period:
            ref_series = series.iloc[:reference_period]
        else:
            ref_series = series
        
        mean = ref_series.mean()
        std = ref_series.std()
        
        if std < 1e-10:
            logger.warning(f"[FIELD] Zero variance for {col}, skipping")
            continue
        
        # Standardize
        z = (indicators[col] - mean) / std
        
        # Invert if necessary (so positive z always means expansion)
        should_invert = inversions.get(col, False)
        if should_invert:
            z = -z
        
        z_scores[col] = z
        stats[col] = {
            "mean": float(mean),
            "std": float(std),
            "inverted": should_invert
        }
    
    logger.info(f"[FIELD] Standardized {len(z_scores.columns)} indicators")
    return z_scores, stats


# =============================================================================
# WEIGHTED AVERAGE FIELD
# =============================================================================

def build_weighted_field(
    z_scores: pd.DataFrame,
    weights: Dict[str, float],
    normalize_weights: bool = True
) -> Tuple[pd.Series, Dict[str, float]]:
    """
    Build composite field as weighted average of z-scores.
    
    Args:
        z_scores: DataFrame of standardized indicators
        weights: Dict mapping indicator name -> weight
        normalize_weights: If True, normalize weights to sum to 1
    
    Returns:
        Tuple of (field Series, actual weights used)
    """
    # Get weights for available indicators
    available_weights = {}
    for col in z_scores.columns:
        if col in weights:
            available_weights[col] = weights[col]
        else:
            # Default weight
            available_weights[col] = 1.0 / len(z_scores.columns)
    
    # Normalize weights
    if normalize_weights:
        total = sum(available_weights.values())
        if total > 0:
            available_weights = {k: v/total for k, v in available_weights.items()}
    
    # Compute weighted average
    field = pd.Series(0.0, index=z_scores.index)
    
    for col, weight in available_weights.items():
        if col in z_scores.columns:
            field += weight * z_scores[col].fillna(0)
    
    logger.info(f"[FIELD] Built weighted field with {len(available_weights)} indicators")
    return field, available_weights


# =============================================================================
# PCA-BASED FIELD
# =============================================================================

def build_pca_field(
    z_scores: pd.DataFrame,
    n_components: int = 1,
    constraint_indicator: Optional[str] = None,
    min_constraint_loading: float = 0.2
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Build composite field using PCA (first principal component).
    
    Args:
        z_scores: DataFrame of standardized indicators
        n_components: Number of PCA components (default 1)
        constraint_indicator: If provided, require this indicator has
                             at least min_constraint_loading on PC1
        min_constraint_loading: Minimum absolute loading required
    
    Returns:
        Tuple of (field Series, pca_info dict)
        pca_info: {
            "loadings": {indicator: loading},
            "variance_explained": float,
            "constraint_satisfied": bool
        }
    """
    # Handle missing values for PCA
    z_clean = z_scores.dropna()
    
    if len(z_clean) < 20:
        logger.warning(f"[FIELD] Insufficient clean data for PCA: {len(z_clean)} rows")
        # Fallback to equal-weight average
        return z_scores.mean(axis=1), {
            "loadings": {col: 1.0/len(z_scores.columns) for col in z_scores.columns},
            "variance_explained": 0.0,
            "constraint_satisfied": False,
            "fallback": True
        }
    
    # Fit PCA
    pca = PCA(n_components=n_components)
    pca_result = pca.fit_transform(z_clean.values)
    
    # Get loadings (eigenvector components)
    loadings = dict(zip(z_clean.columns, pca.components_[0]))
    variance_explained = pca.explained_variance_ratio_[0]
    
    # Check constraint
    constraint_satisfied = True
    if constraint_indicator and constraint_indicator in loadings:
        actual_loading = abs(loadings[constraint_indicator])
        constraint_satisfied = actual_loading >= min_constraint_loading
        
        if not constraint_satisfied:
            logger.warning(
                f"[FIELD] Constraint not satisfied: {constraint_indicator} loading = "
                f"{actual_loading:.3f} < {min_constraint_loading}"
            )
    
    # Build field series (PC1 scores)
    field = pd.Series(pca_result[:, 0], index=z_clean.index)
    
    # Ensure field direction: positive loading on yield curve = positive field = expansion
    # If yield curve (or constraint indicator) has negative loading, flip the field
    if constraint_indicator and constraint_indicator in loadings:
        if loadings[constraint_indicator] < 0:
            field = -field
            loadings = {k: -v for k, v in loadings.items()}
    
    # Reindex to original index (NaN for missing)
    field = field.reindex(z_scores.index)
    
    logger.info(f"[FIELD] Built PCA field, variance explained: {variance_explained:.1%}")
    
    return field, {
        "loadings": loadings,
        "variance_explained": float(variance_explained),
        "constraint_satisfied": constraint_satisfied,
        "constraint_indicator": constraint_indicator,
        "n_observations": len(z_clean)
    }


# =============================================================================
# FIELD DECOMPOSITION
# =============================================================================

def decompose_field(
    field: pd.Series,
    z_scores: pd.DataFrame,
    weights: Dict[str, float]
) -> pd.DataFrame:
    """
    Decompose field value into contributions from each indicator.
    
    Args:
        field: The composite field series
        z_scores: Standardized indicators
        weights: Weights used for each indicator
    
    Returns:
        DataFrame with columns for each indicator's contribution
    """
    contributions = pd.DataFrame(index=z_scores.index)
    
    for col in z_scores.columns:
        if col in weights:
            contributions[f"{col}_contrib"] = weights[col] * z_scores[col]
    
    return contributions


def get_current_field_breakdown(
    z_scores: pd.DataFrame,
    weights: Dict[str, float],
    inversions: Dict[str, bool],
    stats: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """
    Get detailed breakdown of current field value.
    
    Returns dict with current z-scores, contributions, and interpretations.
    """
    if z_scores.empty:
        return {"error": "No data available"}
    
    # Get most recent values
    latest_idx = z_scores.index[-1]
    latest_z = z_scores.loc[latest_idx]
    
    breakdown = {
        "timestamp": latest_idx.isoformat() if hasattr(latest_idx, 'isoformat') else str(latest_idx),
        "components": {}
    }
    
    total_field = 0.0
    
    for col in z_scores.columns:
        z_val = latest_z[col]
        weight = weights.get(col, 0.0)
        inverted = inversions.get(col, False)
        
        if pd.isna(z_val):
            continue
        
        contribution = weight * z_val
        total_field += contribution
        
        # Interpret z-score
        if z_val > 1.5:
            interpretation = "strongly positive" if not inverted else "strongly negative (inverted)"
        elif z_val > 0.5:
            interpretation = "moderately positive" if not inverted else "moderately negative (inverted)"
        elif z_val > -0.5:
            interpretation = "neutral"
        elif z_val > -1.5:
            interpretation = "moderately negative" if not inverted else "moderately positive (inverted)"
        else:
            interpretation = "strongly negative" if not inverted else "strongly positive (inverted)"
        
        breakdown["components"][col] = {
            "z_score": round(float(z_val), 3),
            "weight": round(float(weight), 4),
            "contribution": round(float(contribution), 4),
            "interpretation": interpretation,
            "inverted": inverted
        }
    
    breakdown["total_field_value"] = round(total_field, 4)
    
    # Overall interpretation
    if total_field > 1.0:
        breakdown["field_interpretation"] = "strongly_expanding"
    elif total_field > 0.3:
        breakdown["field_interpretation"] = "moderately_expanding"
    elif total_field > -0.3:
        breakdown["field_interpretation"] = "neutral"
    elif total_field > -1.0:
        breakdown["field_interpretation"] = "moderately_contracting"
    else:
        breakdown["field_interpretation"] = "strongly_contracting"
    
    return breakdown


# =============================================================================
# MAIN FIELD BUILDER CLASS
# =============================================================================

class EconomicFieldBuilder:
    """
    Builds and manages the composite economic field φ(t).
    """
    
    def __init__(
        self,
        method: str = "weighted",
        constraint_indicator: str = "yield_curve_10y2y",
        min_constraint_loading: float = 0.15,
        reference_period: Optional[int] = None
    ):
        """
        Initialize the field builder.
        
        Args:
            method: "weighted" or "pca"
            constraint_indicator: For PCA, require this indicator has significant loading
            min_constraint_loading: Minimum loading for constraint
            reference_period: Months to use for standardization baseline
        """
        self.method = method
        self.constraint_indicator = constraint_indicator
        self.min_constraint_loading = min_constraint_loading
        self.reference_period = reference_period
        
        # State
        self.z_scores = None
        self.standardization_stats = None
        self.field = None
        self.weights = None
        self.pca_info = None
    
    def build(
        self,
        indicators: pd.DataFrame,
        weights: Dict[str, float],
        inversions: Dict[str, bool]
    ) -> pd.Series:
        """
        Build the composite economic field.
        
        Args:
            indicators: DataFrame with indicators as columns
            weights: Dict of indicator weights
            inversions: Dict of inversion flags
        
        Returns:
            Series with the composite field φ(t)
        """
        if indicators.empty:
            raise ValueError("No indicator data provided")
        
        # Step 1: Standardize
        self.z_scores, self.standardization_stats = standardize_indicators(
            indicators,
            inversions,
            self.reference_period
        )
        
        if self.z_scores.empty:
            raise ValueError("Standardization failed - no valid indicators")
        
        # Step 2: Build field based on method
        if self.method == "pca":
            self.field, self.pca_info = build_pca_field(
                self.z_scores,
                n_components=1,
                constraint_indicator=self.constraint_indicator,
                min_constraint_loading=self.min_constraint_loading
            )
            # For PCA, weights are the loadings
            self.weights = self.pca_info.get("loadings", {})
        
        else:  # weighted (default)
            self.field, self.weights = build_weighted_field(
                self.z_scores,
                weights,
                normalize_weights=True
            )
            self.pca_info = None
        
        # Name the series
        self.field.name = "economic_field"
        
        logger.info(f"[FIELD] Built {self.method} field: {len(self.field)} observations")
        return self.field
    
    def get_current_value(self) -> Optional[float]:
        """Get the most recent field value."""
        if self.field is None or self.field.empty:
            return None
        
        # Get last non-NaN value
        valid = self.field.dropna()
        if valid.empty:
            return None
        
        return float(valid.iloc[-1])
    
    def get_breakdown(self, inversions: Dict[str, bool]) -> Dict[str, Any]:
        """Get detailed breakdown of current field value."""
        if self.z_scores is None or self.weights is None:
            return {"error": "Field not built yet"}
        
        return get_current_field_breakdown(
            self.z_scores,
            self.weights,
            inversions,
            self.standardization_stats or {}
        )
    
    def get_field_history(self, periods: Optional[int] = None) -> pd.DataFrame:
        """
        Get historical field values with contributions.
        
        Args:
            periods: Number of recent periods to return (default: all)
        
        Returns:
            DataFrame with field and component contributions
        """
        if self.field is None or self.z_scores is None:
            return pd.DataFrame()
        
        # Get contributions
        contributions = decompose_field(self.field, self.z_scores, self.weights)
        
        # Combine with field
        result = pd.DataFrame({
            "field": self.field
        })
        result = result.join(contributions)
        
        if periods:
            result = result.tail(periods)
        
        return result
    
    def get_build_info(self) -> Dict[str, Any]:
        """Get information about how the field was built."""
        info = {
            "method": self.method,
            "n_indicators": len(self.weights) if self.weights else 0,
            "weights": self.weights,
            "standardization_stats": self.standardization_stats
        }
        
        if self.pca_info:
            info["pca_info"] = self.pca_info
        
        if self.field is not None:
            valid = self.field.dropna()
            info["field_stats"] = {
                "n_observations": len(valid),
                "mean": float(valid.mean()),
                "std": float(valid.std()),
                "min": float(valid.min()),
                "max": float(valid.max()),
                "current": float(valid.iloc[-1]) if len(valid) > 0 else None
            }
        
        return info

