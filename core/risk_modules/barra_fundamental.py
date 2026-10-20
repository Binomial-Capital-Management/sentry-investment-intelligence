"""
Barra Fundamental Factor Model (USE4-style)

Proper cross-sectional fundamental factor model where factor exposures
are stock characteristics (known inputs), NOT estimated via ETF regression.

Methodology references:
  - Menchero, Orr, Wang (2011) "The Barra US Equity Model (USE4)"
  - UePG-21/Barra-risk-model: EWA + Newey-West + Eigenfactor adjustments
  - johnlovesushi/barra-risk-model: factor covariance adjustment chain

Factor structure:
  - Market: constant = 1.0
  - Sectors (11): GICS one-hot encoding from FMP profile
  - Style (6): Momentum, Size, Value, Quality, Volatility, Beta
    All style factors winsorized at ±3σ then cross-sectionally z-scored
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from sklearn.linear_model import LinearRegression
import logging
import os

logger = logging.getLogger(__name__)

TRADING_DAYS = int(os.getenv("TRADING_DAYS", 252))

STYLE_FACTORS = ["Momentum", "Size", "Value", "Quality", "Volatility", "Beta"]

GICS_SECTORS = [
    "Technology", "Healthcare", "Financials", "Consumer_Disc",
    "Consumer_Staples", "Industrials", "Energy", "Materials",
    "Utilities", "Real_Estate", "Communications",
]

ALL_FACTORS = ["Market"] + GICS_SECTORS + STYLE_FACTORS

# SPDR sector ETF proxies for each GICS sector
SECTOR_ETFS: Dict[str, str] = {
    "Technology":      "XLK",
    "Healthcare":      "XLV",
    "Financials":      "XLF",
    "Consumer_Disc":   "XLY",
    "Consumer_Staples":"XLP",
    "Industrials":     "XLI",
    "Energy":          "XLE",
    "Materials":       "XLB",
    "Utilities":       "XLU",
    "Real_Estate":     "XLRE",
    "Communications":  "XLC",
}

# FMP sector name → our canonical sector label
SECTOR_MAP = {
    "Technology": "Technology",
    "Information Technology": "Technology",
    "Health Care": "Healthcare",
    "Healthcare": "Healthcare",
    "Financials": "Financials",
    "Financial Services": "Financials",
    "Consumer Discretionary": "Consumer_Disc",
    "Consumer Cyclical": "Consumer_Disc",
    "Consumer Staples": "Consumer_Staples",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Materials": "Materials",
    "Basic Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real_Estate",
    "Communication Services": "Communications",
    "Telecommunication Services": "Communications",
}


def _winsorize_zscore(series: pd.Series, n_sigma: float = 3.0) -> pd.Series:
    """Winsorize at ±n_sigma MAD then z-score."""
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0:
        mad = series.std()
    if mad == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    clip_lo = median - n_sigma * mad / 0.6745
    clip_hi = median + n_sigma * mad / 0.6745
    clipped = series.clip(clip_lo, clip_hi)
    std = clipped.std()
    if std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (clipped - clipped.mean()) / std


def _cov_ewa(data: np.ndarray, half_life: Optional[int] = None) -> np.ndarray:
    """Exponential-weighted average covariance. data shape: (K, T)."""
    K, T = data.shape
    if half_life is None:
        weights = np.ones(T)
    else:
        alpha = 0.5 ** (1.0 / half_life)
        weights = alpha ** np.arange(T - 1, -1, -1)
    sum_w = weights.sum()
    f_bar = (data * weights[np.newaxis, :]).sum(axis=1, keepdims=True) / sum_w
    demeaned = data - f_bar
    outer = np.array([np.outer(demeaned[:, t], demeaned[:, t]) for t in range(T)])
    return (outer * weights[:, np.newaxis, np.newaxis]).sum(axis=0) / sum_w


class BarraFundamentalModel:
    """
    Cross-sectional fundamental factor model.

    Factor exposures are stock characteristics — not estimated from ETF regressions.
    Factor returns are estimated via WLS cross-sectional regression at each date.
    Factor covariance uses the full UePG-21 adjustment chain.
    """

    def __init__(self):
        self.B: Optional[pd.DataFrame] = None          # (N, K) exposure matrix
        self.factor_returns: Optional[pd.DataFrame] = None   # (T, K)
        self.F_cov: Optional[np.ndarray] = None        # (K, K) factor covariance
        self.D: Optional[pd.Series] = None             # (N,) specific variances
        self.tickers: Optional[List[str]] = None
        self.factor_names: Optional[List[str]] = None
        self.raw_betas: Optional[Dict[str, float]] = None   # unstandardized OLS betas per stock

    # ------------------------------------------------------------------ #
    # Step 1: Compute factor exposures from stock characteristics          #
    # ------------------------------------------------------------------ #

    def compute_factor_exposures(
        self,
        tickers: List[str],
        prices: pd.DataFrame,
        fundamentals: Dict[str, Dict],
        requested_factors: Optional[set] = None,
        vol_window: int = 60,
        beta_window: int = 252,
        benchmark_ticker: str = "SPY",
    ) -> pd.DataFrame:
        """
        Build the B matrix (N × K) from stock characteristics.

        Args:
            tickers: List of portfolio tickers
            prices: DataFrame of daily close prices, columns = tickers (+ benchmark)
            fundamentals: {ticker: {mktCap, sector, pbRatio, roe, beta}} from FMP
            requested_factors: set of factor names to include, or None for all
            vol_window: lookback days for realized volatility factor
            beta_window: lookback days for OLS beta estimation
            benchmark_ticker: ticker used as the market proxy for beta estimation

        Returns:
            B: DataFrame (tickers × factors)
        """
        # Determine which factors to build — always include Market as it anchors WLS
        if requested_factors is None:
            active_factors = set(ALL_FACTORS)
        else:
            active_factors = {"Market"} | requested_factors

        valid_tickers = [t for t in tickers if t in prices.columns]
        if not valid_tickers:
            raise ValueError("No valid tickers with price data")

        returns = prices[valid_tickers].pct_change().dropna()
        # Look up the benchmark column (case-insensitive fallback)
        spy_col = None
        for candidate in [benchmark_ticker, benchmark_ticker.upper(), benchmark_ticker.lower(), "SPY"]:
            if candidate in prices.columns:
                spy_col = candidate
                break
        spy_returns = prices[spy_col].pct_change().dropna() if spy_col else None

        rows = []
        for ticker in valid_tickers:
            row: Dict[str, float] = {}
            fund = fundamentals.get(ticker, {})
            tk_returns = returns[ticker].dropna()

            # ── Always-on: Market factor ──────────────────────────────────────
            row["Market"] = 1.0

            # ── Sector one-hot (only if any sector in active_factors) ─────────
            sector_raw = fund.get("sector", "")
            sector = SECTOR_MAP.get(sector_raw, None)
            for s in GICS_SECTORS:
                if s in active_factors:
                    row[s] = 1.0 if s == sector else 0.0

            # ── Momentum: risk-adjusted 12-1 month return ─────────────────────
            if "Momentum" in active_factors:
                mom_window = max(vol_window * 4, 252)  # scale with vol_window
                if len(tk_returns) >= mom_window:
                    ret = (1 + tk_returns.iloc[-mom_window:-21]).prod() - 1
                    vol = tk_returns.std() * np.sqrt(TRADING_DAYS)
                    row["Momentum"] = ret / vol if vol > 0 else 0.0
                elif len(tk_returns) >= 60:
                    ret = (1 + tk_returns.iloc[:-21]).prod() - 1
                    vol = tk_returns.std() * np.sqrt(TRADING_DAYS)
                    row["Momentum"] = ret / vol if vol > 0 else 0.0
                else:
                    row["Momentum"] = 0.0

            # ── Size: log(market cap) ─────────────────────────────────────────
            if "Size" in active_factors:
                mkt_cap = fund.get("mktCap", 0) or 0
                row["Size"] = np.log(max(mkt_cap, 1e6))

            # ── Value: book-to-price (1/PB) ───────────────────────────────────
            if "Value" in active_factors:
                pb = fund.get("pbRatio", 0) or 0
                row["Value"] = 1.0 / pb if pb > 0 else 0.0

            # ── Quality: ROE ──────────────────────────────────────────────────
            if "Quality" in active_factors:
                roe = fund.get("roe", 0) or 0
                row["Quality"] = float(roe)

            # ── Volatility: annualized realized vol over vol_window ───────────
            if "Volatility" in active_factors:
                window = min(vol_window, len(tk_returns))
                if window >= 10:
                    row["Volatility"] = tk_returns.iloc[-window:].std() * np.sqrt(TRADING_DAYS)
                else:
                    row["Volatility"] = tk_returns.std() * np.sqrt(TRADING_DAYS) if len(tk_returns) > 5 else 0.0

            # ── Beta: OLS vs SPY over beta_window ─────────────────────────────
            if "Beta" in active_factors:
                if spy_returns is not None and len(tk_returns) >= 30:
                    common = tk_returns.index.intersection(spy_returns.index)
                    win = min(beta_window, len(common))
                    if win >= 30:
                        y = tk_returns.loc[common].iloc[-win:].values
                        x = spy_returns.loc[common].iloc[-win:].values.reshape(-1, 1)
                        reg = LinearRegression().fit(x, y)
                        row["Beta"] = float(reg.coef_[0])
                    else:
                        row["Beta"] = 1.0
                else:
                    row["Beta"] = 1.0

            rows.append(row)

        B_raw = pd.DataFrame(rows, index=valid_tickers)

        # Save raw (unstandardized) betas before z-scoring — used for true ex ante beta
        if "Beta" in B_raw.columns:
            self.raw_betas = B_raw["Beta"].to_dict()
        else:
            self.raw_betas = {t: 1.0 for t in valid_tickers}

        # Cross-sectional standardize + winsorize style factors
        for factor in STYLE_FACTORS:
            if factor in B_raw.columns:
                B_raw[factor] = _winsorize_zscore(B_raw[factor])

        # Preserve canonical factor ordering, only keep what was built
        self.tickers = valid_tickers
        self.factor_names = [c for c in ALL_FACTORS if c in B_raw.columns]
        self.B = B_raw[self.factor_names]
        return self.B

    # ------------------------------------------------------------------ #
    # Step 2: Estimate factor returns via cross-sectional WLS              #
    # ------------------------------------------------------------------ #

    def estimate_factor_returns(
        self,
        prices: pd.DataFrame,
        market_caps: Dict[str, float],
    ) -> pd.DataFrame:
        """
        Cross-sectional WLS at each date t: r_t = B_t · f_t + u_t
        Weights = √mktCap (down-weights small caps, matches Barra convention).

        Returns:
            factor_returns: DataFrame (T × K)
        """
        if self.B is None:
            raise ValueError("Call compute_factor_exposures first")

        valid_tickers = self.tickers
        returns = prices[valid_tickers].pct_change().dropna()

        # WLS weights per stock
        caps = np.array([market_caps.get(t, 1e9) for t in valid_tickers], dtype=float)
        caps = np.where(caps <= 0, 1e9, caps)
        wls_weights = np.sqrt(caps)
        wls_weights /= wls_weights.sum()

        B_vals = self.B.values  # (N, K)
        factor_return_list = []
        residual_list = []
        dates = []

        for date, row in returns.iterrows():
            r_vec = row.values  # (N,)
            if np.isnan(r_vec).all():
                continue
            valid_mask = ~np.isnan(r_vec)
            if valid_mask.sum() < len(self.factor_names):
                continue

            B_t = B_vals[valid_mask]
            r_t = r_vec[valid_mask]
            w_t = wls_weights[valid_mask]
            w_t = w_t / w_t.sum()

            # Weighted least squares: min Σ w_i (r_i - B_i f)²
            W = np.diag(w_t)
            try:
                BtWB = B_t.T @ W @ B_t
                BtWr = B_t.T @ W @ r_t
                f_t = np.linalg.lstsq(BtWB, BtWr, rcond=None)[0]
            except np.linalg.LinAlgError:
                continue

            residuals = r_t - B_t @ f_t
            factor_return_list.append(f_t)
            residual_list.append(
                dict(zip(np.array(valid_tickers)[valid_mask], residuals))
            )
            dates.append(date)

        if not factor_return_list:
            raise ValueError("Cross-sectional regression produced no factor returns")

        self.factor_returns = pd.DataFrame(
            factor_return_list, index=dates, columns=self.factor_names
        )
        self._residuals_by_date = residual_list
        self._residual_dates = dates
        return self.factor_returns

    # ------------------------------------------------------------------ #
    # Step 3: Estimate factor covariance (EWA + NW + Eigenfactor)          #
    # ------------------------------------------------------------------ #

    def estimate_factor_covariance(
        self,
        half_life: int = 90,
        nw_lags: int = 5,
        eigen_mc: int = 100,
    ) -> np.ndarray:
        """
        Full UePG-21 covariance adjustment chain:
          1. EWA covariance (half_life=90)
          2. Newey-West adjustment (max_lags=5)
          3. Eigenfactor risk adjustment (Monte Carlo M=100)

        Returns F_cov: (K, K) annualized factor covariance matrix
        """
        if self.factor_returns is None:
            raise ValueError("Call estimate_factor_returns first")

        F = self.factor_returns.values.T  # (K, T)
        K, T = F.shape

        # Step 1: EWA covariance
        FCM = _cov_ewa(F, half_life=half_life)

        # Step 2: Newey-West adjustment (from UePG-21 FactorCovAdjuster)
        for lag in range(1, nw_lags + 1):
            w = 1.0 - lag / (nw_lags + 1)
            C_lag = _cov_ewa(F, half_life=half_life, lag=lag) if False else _cov_ewa_lag(F, half_life, lag)
            FCM = FCM + w * (C_lag + C_lag.T)

        # Annualize
        FCM = FCM * TRADING_DAYS

        # Ensure PSD
        D, U = np.linalg.eigh(FCM)
        D = np.where(D <= 0, 1e-14, D)
        FCM = U @ np.diag(D) @ U.T

        # Step 3: Eigenfactor risk adjustment (Monte Carlo bias correction)
        if eigen_mc > 0 and T > K:
            D0, U0 = np.linalg.eigh(FCM)
            D0 = np.where(D0 <= 0, 1e-14, D0)
            Lambda = np.zeros(K)
            rng = np.random.default_rng(42)
            for _ in range(eigen_mc):
                b_m = np.array([rng.normal(0, np.sqrt(d), T) for d in D0])
                F_m = b_m @ b_m.T / (T - 1)
                Dm, Um = np.linalg.eigh(F_m)
                Dm = np.where(Dm <= 0, 1e-14, Dm)
                D_tilde = np.diag(Um.T @ FCM @ Um)
                Lambda += D_tilde / Dm
            Lambda = np.where(Lambda <= 0, 1e-14, Lambda)
            Lambda = np.sqrt(Lambda / eigen_mc)
            coef = 1.2  # Barra USE4 default
            Gamma = coef * (Lambda - 1.0) + 1.0
            D0_tilde = Gamma ** 2 * D0
            FCM = U0 @ np.diag(D0_tilde) @ U0.T

        self.F_cov = FCM
        return self.F_cov

    # ------------------------------------------------------------------ #
    # Step 4: Specific risk with Bayesian shrinkage                        #
    # ------------------------------------------------------------------ #

    def estimate_specific_risk(self, shrinkage: float = 0.1) -> pd.Series:
        """
        Bayesian shrinkage of stock-specific variances toward cross-sectional mean.
        σ_final = (1 - ν)·σ_i + ν·σ̄
        """
        if self._residuals_by_date is None:
            raise ValueError("Call estimate_factor_returns first")

        # Collect per-stock residuals
        all_residuals: Dict[str, List[float]] = {t: [] for t in self.tickers}
        for row in self._residuals_by_date:
            for ticker, resid in row.items():
                if ticker in all_residuals:
                    all_residuals[ticker].append(resid)

        specific_vars = {}
        for ticker, resids in all_residuals.items():
            if len(resids) >= 20:
                specific_vars[ticker] = np.var(resids) * TRADING_DAYS
            else:
                specific_vars[ticker] = 0.04  # default 20% annual vol squared

        var_series = pd.Series(specific_vars)
        mean_var = var_series.mean()
        self.D = (1 - shrinkage) * var_series + shrinkage * mean_var
        return self.D

    # ------------------------------------------------------------------ #
    # Step 5: Portfolio risk decomposition                                 #
    # ------------------------------------------------------------------ #

    def portfolio_risk(
        self,
        weights: np.ndarray,
        tickers: List[str],
    ) -> Dict:
        """
        Full portfolio risk decomposition.

        Returns dict with ex_ante_vol, factor_risk, specific_risk,
        factor_contributions, portfolio_exposures, ex_ante_beta.
        """
        if self.B is None or self.F_cov is None or self.D is None:
            raise ValueError("Model not fully estimated")

        # Align weights to fitted tickers
        fitted = self.tickers
        w = np.zeros(len(fitted))
        for i, t in enumerate(fitted):
            if t in tickers:
                idx = tickers.index(t)
                if idx < len(weights):
                    w[i] = weights[idx]
        if w.sum() > 0:
            w /= w.sum()

        B = self.B.values  # (N, K)

        # Portfolio factor exposures: B_p = B'w
        B_p = B.T @ w  # (K,)

        # Factor variance
        factor_var = float(B_p @ self.F_cov @ B_p)

        # Specific variance
        D_vals = np.array([self.D.get(t, 0.04) for t in fitted])
        specific_var = float((w ** 2) @ D_vals)

        total_var = factor_var + specific_var
        total_vol = np.sqrt(max(total_var, 1e-8))
        factor_vol = np.sqrt(max(factor_var, 0))
        specific_vol = np.sqrt(max(specific_var, 0))

        # Per-factor contributions to total variance
        K = len(self.factor_names)
        factor_contributions = {}
        if total_var > 0:
            marginal = self.F_cov @ B_p
            for i, fname in enumerate(self.factor_names):
                contrib = B_p[i] * marginal[i] / total_var
                factor_contributions[fname] = float(max(contrib, 0))

        portfolio_exposures = dict(zip(self.factor_names, B_p.tolist()))

        # Ex ante beta = portfolio-weighted average of raw OLS betas (not the standardized factor)
        if self.raw_betas:
            ex_ante_beta = float(sum(w[i] * self.raw_betas.get(fitted[i], 1.0) for i in range(len(fitted))))
        else:
            ex_ante_beta = portfolio_exposures.get("Market", 1.0)

        # Mean R²: average fraction of variance explained by factors
        per_stock_r2 = []
        for i, t in enumerate(fitted):
            stock_var = float(B[i] @ self.F_cov @ B[i]) + D_vals[i]
            factor_var_i = float(B[i] @ self.F_cov @ B[i])
            r2 = factor_var_i / stock_var if stock_var > 0 else 0.0
            per_stock_r2.append(r2)

        return {
            "ex_ante_beta": round(ex_ante_beta, 4),
            "ex_ante_vol": round(total_vol, 6),
            "factor_risk": round(factor_vol, 6),
            "specific_risk": round(specific_vol, 6),
            "systematic_pct": round(factor_var / total_var, 4) if total_var > 0 else 0.5,
            "idiosyncratic_pct": round(specific_var / total_var, 4) if total_var > 0 else 0.5,
            "mean_r_squared": round(float(np.mean(per_stock_r2)), 4),
            "portfolio_exposures": {k: round(v, 4) for k, v in portfolio_exposures.items()},
            "factor_contributions": {k: round(v, 4) for k, v in factor_contributions.items()},
        }


def _cov_ewa_lag(data: np.ndarray, half_life: int, lag: int) -> np.ndarray:
    """Lagged EWA covariance cov(t, t-lag). data shape: (K, T)."""
    K, T = data.shape
    alpha = 0.5 ** (1.0 / half_life)
    weights = alpha ** np.arange(T - 1, -1, -1)
    sum_w = weights.sum()
    f_bar = (data * weights[np.newaxis, :]).sum(axis=1, keepdims=True) / sum_w
    demeaned = data - f_bar
    t_range = range(lag, T)
    elements = np.array([np.outer(demeaned[:, t - lag], demeaned[:, t]) for t in t_range])
    weights_lagged = weights[lag:]
    return (elements * weights_lagged[:, np.newaxis, np.newaxis]).sum(axis=0) / weights_lagged.sum()


def compute_benchmark_exposures(
    benchmark_prices: Optional[pd.Series],
    benchmark_fundamentals: Dict,
    factor_names: List[str],
    model: "BarraFundamentalModel",
    sector_etf_prices: Optional[pd.DataFrame] = None,
) -> Dict[str, float]:
    """
    Derive benchmark factor exposures from real data.

    Sector exposures — OLS regression of benchmark returns against sector ETF
    returns.  If sector ETF prices are unavailable we fall back to S&P 500
    approximate sector weights so the function never silently fails.

    Style exposures — the benchmark is the "market" so its z-scored style
    exposures are approximately zero by construction, with calibrated
    exceptions for Size and Volatility.
    """
    exposures: Dict[str, float] = {}

    # ── Sector exposures via ETF regression ──────────────────────────────────
    sector_factors = [f for f in factor_names if f in GICS_SECTORS]
    sector_weights_from_etf: Dict[str, float] = {}

    if (
        benchmark_prices is not None
        and sector_etf_prices is not None
        and not sector_etf_prices.empty
        and len(sector_factors) > 0
    ):
        bench_ret = benchmark_prices.pct_change().dropna()

        # Build sector ETF return matrix for sectors that appear in factor_names
        etf_cols: List[str] = []
        sector_order: List[str] = []
        for sector in sector_factors:
            etf_ticker = SECTOR_ETFS.get(sector)
            if etf_ticker and etf_ticker in sector_etf_prices.columns:
                etf_cols.append(etf_ticker)
                sector_order.append(sector)

        if etf_cols and len(etf_cols) >= 2:
            common = bench_ret.index.intersection(sector_etf_prices.index)
            if len(common) >= 60:
                S = sector_etf_prices.loc[common, etf_cols].pct_change().dropna()
                b = bench_ret.loc[S.index]
                common2 = S.index.intersection(b.index)
                S = S.loc[common2].values
                b = b.loc[common2].values

                # Non-negative constrained OLS (sector weights must be ≥ 0)
                try:
                    from scipy.optimize import nnls
                    w_raw, _ = nnls(S, b)
                    # Normalize so weights sum to ~1 (benchmark = full investment)
                    w_sum = w_raw.sum()
                    if w_sum > 0.1:
                        w_norm = w_raw / w_sum
                    else:
                        w_norm = w_raw
                    for sector, w in zip(sector_order, w_norm):
                        sector_weights_from_etf[sector] = float(w)
                    logger.debug(
                        "Benchmark sector weights via ETF OLS: %s",
                        {k: round(v, 3) for k, v in sector_weights_from_etf.items()},
                    )
                except Exception as exc:
                    logger.warning("ETF sector OLS failed, using fallback: %s", exc)

    # Fallback hardcoded SPY weights when ETF data is unavailable
    _spy_fallback: Dict[str, float] = {
        "Technology": 0.30, "Healthcare": 0.13, "Financials": 0.13,
        "Consumer_Disc": 0.10, "Industrials": 0.09, "Consumer_Staples": 0.06,
        "Energy": 0.04, "Materials": 0.03, "Real_Estate": 0.03,
        "Utilities": 0.03, "Communications": 0.09,
    }

    # ── Assemble exposures ────────────────────────────────────────────────────
    for f in factor_names:
        if f == "Market":
            exposures[f] = 1.0
        elif f in GICS_SECTORS:
            if sector_weights_from_etf:
                exposures[f] = sector_weights_from_etf.get(f, 0.0)
            else:
                exposures[f] = _spy_fallback.get(f, 0.0)
        elif f == "Beta":
            exposures[f] = 0.0   # benchmark beta ≈ 1, standardized ≈ 0
        elif f == "Size":
            exposures[f] = 1.5   # broad index is large-cap tilted
        elif f == "Volatility":
            exposures[f] = -0.3  # index less volatile than average stock
        else:
            exposures[f] = 0.0   # Momentum, Value, Quality ≈ market average

    return exposures
