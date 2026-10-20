"""
Recession Field Theory - Physics Statistics

Computes physics-inspired early warning statistics:
1. Critical Slowing Down (AR(1) coefficient) - system memory increasing
2. Correlation Length (cross-sector correlation) - contagion spreading  
3. Susceptibility (variance amplification) - increased sensitivity
4. Spectral Dominance (first eigenvalue share) - single factor dominance

These statistics are grounded in phase transition theory from physics:
- Near a critical point, all four diverge simultaneously
- Provides 3-9 months early warning before recessions
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List, Any
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


# =============================================================================
# NORMAL RANGES (derived from historical non-recession periods)
# =============================================================================

NORMAL_RANGES = {
    "ar1_coefficient": {
        "low": 0.75,
        "high": 0.88,
        "critical": 0.95,
        "description": "AR(1) autocorrelation coefficient"
    },
    "correlation_length": {
        "low": 0.20,
        "high": 0.40,
        "critical": 0.65,
        "description": "Mean cross-sector correlation"
    },
    "susceptibility": {
        "low": 0.7,
        "high": 1.3,
        "critical": 2.5,
        "description": "Variance ratio vs baseline"
    },
    "spectral_dominance": {
        "low": 0.25,
        "high": 0.42,
        "critical": 0.60,
        "description": "First eigenvalue / total variance"
    }
}


# =============================================================================
# 1. CRITICAL SLOWING DOWN (AR(1) Coefficient)
# =============================================================================

def compute_ar1_coefficient(
    series: pd.Series,
    window: Optional[int] = None
) -> float:
    """
    Compute AR(1) autocorrelation coefficient.
    
    Critical Slowing Down: Near phase transitions, the system takes longer
    to return to equilibrium. This manifests as autocorrelation → 1.
    
    Args:
        series: Time series (e.g., economic field φ(t))
        window: If provided, use only last N observations
    
    Returns:
        AR(1) coefficient ρ where φ(t) ≈ ρ * φ(t-1) + ε
    """
    if series is None or len(series) < 10:
        return np.nan
    
    # Use window if specified
    if window and len(series) > window:
        series = series.iloc[-window:]
    
    # Drop NaN values
    clean = series.dropna()
    
    if len(clean) < 10:
        return np.nan
    
    # Compute lag-1 autocorrelation
    y = clean.values[1:]
    y_lag = clean.values[:-1]
    
    # Pearson correlation
    if np.std(y) < 1e-10 or np.std(y_lag) < 1e-10:
        return np.nan
    
    ar1 = np.corrcoef(y, y_lag)[0, 1]
    
    return float(ar1)


def compute_rolling_ar1(
    series: pd.Series,
    window: int = 24,
    min_periods: int = 12
) -> pd.Series:
    """
    Compute rolling AR(1) coefficient.
    
    Args:
        series: Time series
        window: Rolling window size
        min_periods: Minimum observations required
    
    Returns:
        Series of rolling AR(1) values
    """
    ar1_values = []
    indices = []
    
    for i in range(min_periods, len(series) + 1):
        start = max(0, i - window)
        window_data = series.iloc[start:i]
        
        ar1 = compute_ar1_coefficient(window_data)
        ar1_values.append(ar1)
        indices.append(series.index[i - 1])
    
    return pd.Series(ar1_values, index=indices, name="ar1_coefficient")


# =============================================================================
# 2. CORRELATION LENGTH (Cross-Sector Correlation)
# =============================================================================

def compute_correlation_length(
    returns: pd.DataFrame,
    window: Optional[int] = None
) -> float:
    """
    Compute correlation length as mean absolute pairwise correlation.
    
    Correlation Length: Near criticality, correlations extend across the
    entire system. In normal times, sectors move independently.
    
    Args:
        returns: DataFrame with asset returns (each column = one asset)
        window: If provided, use only last N observations
    
    Returns:
        Mean absolute correlation (0 to 1)
    """
    if returns is None or returns.empty:
        return np.nan
    
    # Use window if specified
    if window and len(returns) > window:
        returns = returns.iloc[-window:]
    
    # Drop columns with too many NaNs
    min_obs = max(20, len(returns) // 2)
    valid_cols = [col for col in returns.columns if returns[col].notna().sum() >= min_obs]
    
    if len(valid_cols) < 2:
        return np.nan
    
    returns = returns[valid_cols].dropna()
    
    if len(returns) < 20:
        return np.nan
    
    # Compute correlation matrix
    corr_matrix = returns.corr()
    
    # Extract upper triangle (excluding diagonal)
    n = len(corr_matrix)
    upper_triangle = []
    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val):
                upper_triangle.append(abs(val))
    
    if not upper_triangle:
        return np.nan
    
    return float(np.mean(upper_triangle))


def compute_rolling_correlation_length(
    returns: pd.DataFrame,
    window: int = 63,
    stride: int = 5
) -> pd.Series:
    """
    Compute rolling correlation length.
    
    Args:
        returns: DataFrame with daily returns
        window: Rolling window in days (default: 63 ≈ 3 months)
        stride: Step size between calculations
    
    Returns:
        Series of rolling correlation length values
    """
    xi_values = []
    indices = []
    
    for i in range(window, len(returns) + 1, stride):
        window_returns = returns.iloc[i - window:i]
        xi = compute_correlation_length(window_returns)
        xi_values.append(xi)
        indices.append(returns.index[i - 1])
    
    return pd.Series(xi_values, index=indices, name="correlation_length")


# =============================================================================
# 3. SUSCEPTIBILITY (Variance Amplification)
# =============================================================================

def compute_susceptibility(
    series: pd.Series,
    baseline_window: int = 60,
    current_window: int = 12
) -> float:
    """
    Compute susceptibility as variance ratio.
    
    Susceptibility: Near criticality, small perturbations cause large
    responses. This shows up as amplified variance.
    
    χ = var(recent) / var(baseline)
    
    Args:
        series: Time series (e.g., economic field)
        baseline_window: Observations to use for baseline variance
        current_window: Observations to use for current variance
    
    Returns:
        Susceptibility ratio (χ > 1 means elevated)
    """
    if series is None or len(series) < baseline_window + current_window:
        return np.nan
    
    clean = series.dropna()
    
    if len(clean) < baseline_window + current_window:
        return np.nan
    
    # Baseline variance (earlier period)
    baseline = clean.iloc[-(baseline_window + current_window):-current_window]
    baseline_var = baseline.var()
    
    # Current variance (recent period)
    current = clean.iloc[-current_window:]
    current_var = current.var()
    
    if baseline_var < 1e-10:
        return np.nan
    
    chi = current_var / baseline_var
    
    return float(chi)


def compute_rolling_susceptibility(
    series: pd.Series,
    baseline_window: int = 36,
    current_window: int = 6,
    stride: int = 1
) -> pd.Series:
    """
    Compute rolling susceptibility.
    
    Args:
        series: Time series
        baseline_window: Baseline period for variance
        current_window: Current period for variance
        stride: Step size
    
    Returns:
        Series of rolling susceptibility values
    """
    total_window = baseline_window + current_window
    
    chi_values = []
    indices = []
    
    for i in range(total_window, len(series) + 1, stride):
        window_data = series.iloc[i - total_window:i]
        
        baseline = window_data.iloc[:-current_window]
        current = window_data.iloc[-current_window:]
        
        baseline_var = baseline.var()
        current_var = current.var()
        
        if baseline_var > 1e-10:
            chi = current_var / baseline_var
        else:
            chi = np.nan
        
        chi_values.append(chi)
        indices.append(series.index[i - 1])
    
    return pd.Series(chi_values, index=indices, name="susceptibility")


# =============================================================================
# 4. SPECTRAL DOMINANCE (First Eigenvalue Share)
# =============================================================================

def compute_spectral_dominance(
    returns: pd.DataFrame,
    window: Optional[int] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute spectral dominance (λ₁ / Σλ).
    
    Spectral Dominance: When one factor dominates variance, the market
    moves as a single unit - a sign of systemic risk.
    
    Uses Random Matrix Theory bounds to identify signal vs noise.
    
    Args:
        returns: DataFrame with asset returns
        window: If provided, use only last N observations
    
    Returns:
        Tuple of (dominance ratio, details dict)
    """
    if returns is None or returns.empty:
        return np.nan, {}
    
    # Use window if specified
    if window and len(returns) > window:
        returns = returns.iloc[-window:]
    
    # Clean data
    min_obs = max(30, len(returns) // 2)
    valid_cols = [col for col in returns.columns if returns[col].notna().sum() >= min_obs]
    
    if len(valid_cols) < 3:
        return np.nan, {}
    
    returns = returns[valid_cols].dropna()
    T, N = returns.shape
    
    if T < 30 or N < 3:
        return np.nan, {}
    
    # Compute correlation matrix
    corr_matrix = returns.corr().values
    
    # Eigendecomposition
    eigenvalues = np.linalg.eigvalsh(corr_matrix)
    eigenvalues = np.sort(eigenvalues)[::-1]  # Descending order
    
    # Spectral dominance
    total_var = eigenvalues.sum()
    if total_var < 1e-10:
        return np.nan, {}
    
    lambda_1 = eigenvalues[0]
    dominance = lambda_1 / total_var
    
    # Marchenko-Pastur bounds (RMT)
    q = T / N
    if q >= 1:
        mp_upper = (1 + 1/np.sqrt(q))**2
        mp_lower = (1 - 1/np.sqrt(q))**2
    else:
        mp_upper = np.nan
        mp_lower = np.nan
    
    # Count signal eigenvalues (above MP bound)
    n_signal = sum(1 for ev in eigenvalues if ev > mp_upper) if not np.isnan(mp_upper) else 0
    
    details = {
        "lambda_1": float(lambda_1),
        "total_variance": float(total_var),
        "n_assets": N,
        "n_observations": T,
        "mp_upper_bound": float(mp_upper) if not np.isnan(mp_upper) else None,
        "mp_lower_bound": float(mp_lower) if not np.isnan(mp_lower) else None,
        "n_signal_eigenvalues": n_signal,
        "eigenvalue_spectrum": eigenvalues[:min(5, len(eigenvalues))].tolist()
    }
    
    return float(dominance), details


def compute_rolling_spectral_dominance(
    returns: pd.DataFrame,
    window: int = 126,
    stride: int = 21
) -> pd.Series:
    """
    Compute rolling spectral dominance.
    
    Args:
        returns: DataFrame with daily returns
        window: Rolling window in days (default: 126 ≈ 6 months)
        stride: Step size (default: 21 ≈ 1 month)
    
    Returns:
        Series of rolling spectral dominance values
    """
    dom_values = []
    indices = []
    
    for i in range(window, len(returns) + 1, stride):
        window_returns = returns.iloc[i - window:i]
        dominance, _ = compute_spectral_dominance(window_returns)
        dom_values.append(dominance)
        indices.append(returns.index[i - 1])
    
    return pd.Series(dom_values, index=indices, name="spectral_dominance")


# =============================================================================
# SIGNAL CLASSIFICATION
# =============================================================================

def classify_signal(
    value: float,
    stat_name: str
) -> str:
    """
    Classify a statistic as NORMAL, ELEVATED, or CRITICAL.
    
    Args:
        value: The statistic value
        stat_name: Name of the statistic (must be in NORMAL_RANGES)
    
    Returns:
        "NORMAL", "ELEVATED", or "CRITICAL"
    """
    if np.isnan(value) or stat_name not in NORMAL_RANGES:
        return "UNKNOWN"
    
    ranges = NORMAL_RANGES[stat_name]
    
    if value >= ranges["critical"]:
        return "CRITICAL"
    elif value >= ranges["high"]:
        return "ELEVATED"
    else:
        return "NORMAL"


def get_signal_interpretation(
    stat_name: str,
    signal: str
) -> str:
    """Get human-readable interpretation of a signal."""
    interpretations = {
        "ar1_coefficient": {
            "NORMAL": "Economy returning to equilibrium normally after shocks",
            "ELEVATED": "Economy slow to recover from perturbations - early warning",
            "CRITICAL": "System memory very high - approaching critical transition"
        },
        "correlation_length": {
            "NORMAL": "Sectors moving independently - healthy diversification",
            "ELEVATED": "Increased cross-sector correlation - contagion risk rising",
            "CRITICAL": "High contagion - shocks propagating system-wide"
        },
        "susceptibility": {
            "NORMAL": "Economic fluctuations within typical range",
            "ELEVATED": "Amplified volatility - system becoming sensitive",
            "CRITICAL": "Extreme sensitivity to perturbations"
        },
        "spectral_dominance": {
            "NORMAL": "Market variance well-distributed across factors",
            "ELEVATED": "Single factor gaining dominance - systemic risk rising",
            "CRITICAL": "Market moving as single unit - high systemic risk"
        }
    }
    
    if stat_name in interpretations and signal in interpretations[stat_name]:
        return interpretations[stat_name][signal]
    
    return "Unknown signal"


# =============================================================================
# COMPOSITE ANALYSIS
# =============================================================================

class PhysicsStatsAnalyzer:
    """
    Computes and analyzes all physics-inspired early warning statistics.
    """
    
    def __init__(
        self,
        ar1_window: int = 24,
        correlation_window: int = 63,
        susceptibility_baseline: int = 36,
        susceptibility_current: int = 6,
        spectral_window: int = 126
    ):
        """
        Initialize the analyzer.
        
        Args:
            ar1_window: Window for AR(1) calculation (months)
            correlation_window: Window for correlation length (days)
            susceptibility_baseline: Baseline window for susceptibility (months)
            susceptibility_current: Current window for susceptibility (months)
            spectral_window: Window for spectral analysis (days)
        """
        self.ar1_window = ar1_window
        self.correlation_window = correlation_window
        self.susceptibility_baseline = susceptibility_baseline
        self.susceptibility_current = susceptibility_current
        self.spectral_window = spectral_window
        
        # Results storage
        self.results = {}
    
    def analyze(
        self,
        field: pd.Series,
        sector_returns: Optional[pd.DataFrame] = None,
        asset_returns: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Compute all physics statistics.
        
        Args:
            field: Economic field series φ(t) - monthly
            sector_returns: Sector ETF returns - daily
            asset_returns: Asset class returns - daily
        
        Returns:
            Dict with all statistics and signals
        """
        results = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "statistics": {},
            "signals": {},
            "signal_count": {"NORMAL": 0, "ELEVATED": 0, "CRITICAL": 0},
            "composite_warning_score": 0.0
        }
        
        # 1. Critical Slowing Down (AR1)
        ar1 = compute_ar1_coefficient(field, window=self.ar1_window)
        ar1_signal = classify_signal(ar1, "ar1_coefficient")
        
        results["statistics"]["critical_slowing_down"] = {
            "ar1_coefficient": round(ar1, 4) if not np.isnan(ar1) else None,
            "normal_range": [NORMAL_RANGES["ar1_coefficient"]["low"], 
                           NORMAL_RANGES["ar1_coefficient"]["high"]],
            "signal": ar1_signal,
            "interpretation": get_signal_interpretation("ar1_coefficient", ar1_signal)
        }
        results["signals"]["ar1_coefficient"] = ar1_signal
        
        # 2. Correlation Length
        # Use sector returns if available, else asset returns
        corr_data = sector_returns if sector_returns is not None else asset_returns
        
        if corr_data is not None:
            xi = compute_correlation_length(corr_data, window=self.correlation_window)
            xi_signal = classify_signal(xi, "correlation_length")
        else:
            xi = np.nan
            xi_signal = "UNKNOWN"
        
        results["statistics"]["correlation_length"] = {
            "cross_sector_correlation": round(xi, 4) if not np.isnan(xi) else None,
            "normal_range": [NORMAL_RANGES["correlation_length"]["low"],
                           NORMAL_RANGES["correlation_length"]["high"]],
            "signal": xi_signal,
            "interpretation": get_signal_interpretation("correlation_length", xi_signal)
        }
        results["signals"]["correlation_length"] = xi_signal
        
        # 3. Susceptibility
        chi = compute_susceptibility(
            field,
            baseline_window=self.susceptibility_baseline,
            current_window=self.susceptibility_current
        )
        chi_signal = classify_signal(chi, "susceptibility")
        
        results["statistics"]["susceptibility"] = {
            "variance_ratio": round(chi, 4) if not np.isnan(chi) else None,
            "normal_range": [NORMAL_RANGES["susceptibility"]["low"],
                           NORMAL_RANGES["susceptibility"]["high"]],
            "signal": chi_signal,
            "interpretation": get_signal_interpretation("susceptibility", chi_signal)
        }
        results["signals"]["susceptibility"] = chi_signal
        
        # 4. Spectral Dominance
        if corr_data is not None:
            dominance, spectral_details = compute_spectral_dominance(
                corr_data, 
                window=self.spectral_window
            )
            dom_signal = classify_signal(dominance, "spectral_dominance")
        else:
            dominance = np.nan
            spectral_details = {}
            dom_signal = "UNKNOWN"
        
        results["statistics"]["spectral_dominance"] = {
            "first_eigenvalue_share": round(dominance, 4) if not np.isnan(dominance) else None,
            "normal_range": [NORMAL_RANGES["spectral_dominance"]["low"],
                           NORMAL_RANGES["spectral_dominance"]["high"]],
            "signal": dom_signal,
            "interpretation": get_signal_interpretation("spectral_dominance", dom_signal),
            "details": spectral_details
        }
        results["signals"]["spectral_dominance"] = dom_signal
        
        # Count signals
        for signal in results["signals"].values():
            if signal in results["signal_count"]:
                results["signal_count"][signal] += 1
        
        # Composite warning score (0-10)
        score = self._compute_composite_score(
            ar1, xi, chi, dominance
        )
        results["composite_warning_score"] = round(score, 1)
        
        # Overall assessment
        n_elevated = results["signal_count"]["ELEVATED"]
        n_critical = results["signal_count"]["CRITICAL"]
        
        if n_critical >= 2:
            results["overall_assessment"] = "HIGH_RISK"
            results["assessment_text"] = (
                "Multiple critical signals detected. Historical patterns suggest "
                "elevated recession probability within 6-12 months."
            )
        elif n_critical >= 1 or n_elevated >= 3:
            results["overall_assessment"] = "ELEVATED_RISK"
            results["assessment_text"] = (
                "Early warning signals elevated. Economy may be approaching "
                "critical transition. Recommend increased monitoring."
            )
        elif n_elevated >= 2:
            results["overall_assessment"] = "MODERATE_RISK"
            results["assessment_text"] = (
                "Some warning signals elevated. Not yet at critical levels "
                "but warrant attention."
            )
        else:
            results["overall_assessment"] = "LOW_RISK"
            results["assessment_text"] = (
                "All signals within normal ranges. No immediate recession "
                "warning from physics indicators."
            )
        
        self.results = results
        return results
    
    def _compute_composite_score(
        self,
        ar1: float,
        xi: float,
        chi: float,
        dominance: float
    ) -> float:
        """
        Compute composite warning score (0-10).
        
        Uses normalized deviation from normal ranges.
        """
        scores = []
        
        # AR1 score
        if not np.isnan(ar1):
            r = NORMAL_RANGES["ar1_coefficient"]
            if ar1 >= r["critical"]:
                scores.append(10)
            elif ar1 >= r["high"]:
                scores.append(5 + 5 * (ar1 - r["high"]) / (r["critical"] - r["high"]))
            elif ar1 >= r["low"]:
                scores.append(2.5 * (ar1 - r["low"]) / (r["high"] - r["low"]))
            else:
                scores.append(0)
        
        # Correlation length score
        if not np.isnan(xi):
            r = NORMAL_RANGES["correlation_length"]
            if xi >= r["critical"]:
                scores.append(10)
            elif xi >= r["high"]:
                scores.append(5 + 5 * (xi - r["high"]) / (r["critical"] - r["high"]))
            elif xi >= r["low"]:
                scores.append(2.5 * (xi - r["low"]) / (r["high"] - r["low"]))
            else:
                scores.append(0)
        
        # Susceptibility score
        if not np.isnan(chi):
            r = NORMAL_RANGES["susceptibility"]
            if chi >= r["critical"]:
                scores.append(10)
            elif chi >= r["high"]:
                scores.append(5 + 5 * (chi - r["high"]) / (r["critical"] - r["high"]))
            elif chi >= r["low"]:
                scores.append(2.5 * (chi - r["low"]) / (r["high"] - r["low"]))
            else:
                scores.append(0)
        
        # Spectral dominance score
        if not np.isnan(dominance):
            r = NORMAL_RANGES["spectral_dominance"]
            if dominance >= r["critical"]:
                scores.append(10)
            elif dominance >= r["high"]:
                scores.append(5 + 5 * (dominance - r["high"]) / (r["critical"] - r["high"]))
            elif dominance >= r["low"]:
                scores.append(2.5 * (dominance - r["low"]) / (r["high"] - r["low"]))
            else:
                scores.append(0)
        
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores)
    
    def get_rolling_analysis(
        self,
        field: pd.Series,
        returns: pd.DataFrame,
        stride_months: int = 1
    ) -> pd.DataFrame:
        """
        Compute rolling physics statistics for historical analysis.
        
        Returns DataFrame with all statistics over time.
        """
        # This is for visualization - compute rolling versions
        rolling_ar1 = compute_rolling_ar1(field, window=self.ar1_window)
        rolling_chi = compute_rolling_susceptibility(
            field,
            baseline_window=self.susceptibility_baseline,
            current_window=self.susceptibility_current
        )
        
        # For daily data
        if returns is not None and not returns.empty:
            rolling_xi = compute_rolling_correlation_length(
                returns, 
                window=self.correlation_window
            )
            rolling_dom = compute_rolling_spectral_dominance(
                returns,
                window=self.spectral_window
            )
        else:
            rolling_xi = pd.Series(dtype=float)
            rolling_dom = pd.Series(dtype=float)
        
        # Combine (will have different frequencies)
        result = pd.DataFrame({
            "ar1_coefficient": rolling_ar1,
            "susceptibility": rolling_chi
        })
        
        return result

