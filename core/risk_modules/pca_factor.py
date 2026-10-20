"""
PCA Risk Decomposition for Portfolio Analytics

PCA on the correlation matrix of portfolio holdings' daily returns.
Identifies the principal risk directions purely from internal portfolio structure
— no ETFs, no benchmarks.

Outputs:
  - Variance explained per PC + cumulative
  - Top stock loadings per PC
  - Portfolio exposure to each PC (φ_k = w′·e_k)
  - Number of PCs needed to explain 80% of variance
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PCAFactorModel:
    """
    PCA decomposition of portfolio return correlation structure.
    """

    def __init__(self):
        self.eigenvalues: Optional[np.ndarray] = None
        self.eigenvectors: Optional[np.ndarray] = None  # (N, K) columns = PCs
        self.variance_explained: Optional[np.ndarray] = None
        self.tickers: Optional[List[str]] = None

    def fit(self, prices: pd.DataFrame, tickers: List[str]) -> "PCAFactorModel":
        """
        Fit PCA on correlation matrix of holdings returns.

        Args:
            prices: Daily close prices DataFrame
            tickers: Portfolio ticker list

        Returns:
            self (fitted)
        """
        valid = [t for t in tickers if t in prices.columns]
        if len(valid) < 2:
            raise ValueError(f"Need at least 2 tickers for PCA, got {len(valid)}")

        returns = prices[valid].pct_change().dropna()

        # Drop columns with too many NaNs
        valid_cols = returns.columns[returns.isnull().mean() < 0.3]
        returns = returns[valid_cols].dropna()

        if returns.shape[0] < 30:
            raise ValueError("Insufficient return history for PCA")

        self.tickers = list(valid_cols)

        # Correlation matrix (standardize first)
        corr = returns.corr().values
        N = len(self.tickers)

        # Ensure PSD via small ridge
        corr += np.eye(N) * 1e-8

        # Eigendecomposition (ascending order from eigh)
        eigenvalues, eigenvectors = np.linalg.eigh(corr)

        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        self.eigenvalues = eigenvalues[idx]
        self.eigenvectors = eigenvectors[:, idx]  # (N, K), columns = PCs

        total = self.eigenvalues.sum()
        self.variance_explained = self.eigenvalues / total if total > 0 else self.eigenvalues

        return self

    def portfolio_analysis(
        self,
        weights: np.ndarray,
        weight_tickers: List[str],
        n_components: int = 8,
        top_n_loadings: int = 5,
    ) -> Dict:
        """
        Compute portfolio PCA analytics.

        Args:
            weights: Portfolio weights aligned to weight_tickers
            weight_tickers: Tickers corresponding to weights
            n_components: Number of PCs to report
            top_n_loadings: Top loadings per PC

        Returns:
            dict with components, n_components_80pct, portfolio_pc_exposure
        """
        if self.eigenvectors is None:
            raise ValueError("Call fit() first")

        N = len(self.tickers)
        n_components = min(n_components, N)

        # Align weights to fitted tickers
        w = np.zeros(N)
        for i, t in enumerate(self.tickers):
            if t in weight_tickers:
                idx = weight_tickers.index(t)
                if idx < len(weights):
                    w[i] = weights[idx]
        if w.sum() > 0:
            w /= w.sum()

        # Number of PCs to explain 80%
        cumvar = np.cumsum(self.variance_explained)
        n_80 = int(np.searchsorted(cumvar, 0.80)) + 1
        n_80 = min(n_80, N)

        components = []
        for k in range(n_components):
            ev = self.eigenvectors[:, k]  # (N,) loadings

            # Portfolio exposure to this PC: φ_k = w · e_k
            portfolio_exposure = float(w @ ev)

            # Top loadings by absolute value
            abs_ev = np.abs(ev)
            top_idx = np.argsort(abs_ev)[::-1][:top_n_loadings]
            top_loadings = [
                {"ticker": self.tickers[i], "loading": round(float(ev[i]), 4)}
                for i in top_idx
            ]

            components.append({
                "pc": k + 1,
                "variance_explained": round(float(self.variance_explained[k]), 4),
                "cumulative": round(float(cumvar[k]), 4),
                "portfolio_exposure": round(portfolio_exposure, 4),
                "top_loadings": top_loadings,
            })

        return {
            "n_components_80pct": n_80,
            "components": components,
        }
