"""
Portfolio Factor Analytics Endpoint

GET /api/portfolios/{portfolio_id}/factor-analysis

Returns comprehensive portfolio risk analytics:
  - Historical VaR / CVaR / vol / Sharpe / skewness / kurtosis
  - Barra fundamental factor model (cross-sectional, USE4-style)
  - PCA risk decomposition (internal correlation structure)
  - Ex ante factor tilts vs. SPY benchmark

Router uses prefix="/api/portfolios" and tags=["portfolios"] to be
grouped with all other portfolio endpoints in Swagger.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from scipy import stats as sp_stats

from core.database.postgres_client import get_postgres_rls_client
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.agents.risk_tools.shared import fetch_market_data_batch
from core.utils.risk_adapter import adapt_mcp_to_prices
from core.risk_modules.barra_fundamental import (
    BarraFundamentalModel,
    compute_benchmark_exposures,
    STYLE_FACTORS,
    GICS_SECTORS,
    ALL_FACTORS,
    SECTOR_ETFS,
)
from core.risk_modules.pca_factor import PCAFactorModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])

# ─── Server-side in-process cache ─────────────────────────────────────────────
# Keyed by (portfolio_id, user_id, period). Stores result + expiry timestamp.
# Prevents redundant recomputes when multiple tiles fire simultaneously.
_RESULT_CACHE: Dict[str, Tuple[Dict, float]] = {}
_CACHE_TTL_S = 600  # 10 minutes
_inflight: Dict[str, asyncio.Future] = {}  # deduplicates concurrent requests

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/api/v3"


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers (same pattern as portfolios.py)
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_ids(request: Request) -> Tuple[str, Optional[str]]:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    org_id = getattr(request.state, "org_id", None)
    return user_id, org_id


# ─────────────────────────────────────────────────────────────────────────────
# FMP fundamentals fetcher
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_profiles(session: aiohttp.ClientSession, tickers: List[str]) -> Dict[str, Dict]:
    """Batch fetch company profiles (mktCap, sector, beta) — 50 per call."""
    results: Dict[str, Dict] = {}
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        symbols = ",".join(batch)
        url = f"{FMP_BASE}/profile/{symbols}?apikey={FMP_API_KEY}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in (data if isinstance(data, list) else []):
                        sym = item.get("symbol", "")
                        if sym:
                            results[sym] = {
                                "mktCap": item.get("mktCap", 0),
                                "sector": item.get("sector", ""),
                                "beta": item.get("beta", 1.0),
                            }
        except Exception as e:
            logger.warning("Profile fetch failed for batch %s: %s", batch[:3], e)
    return results


async def _fetch_key_metrics(session: aiohttp.ClientSession, tickers: List[str]) -> Dict[str, Dict]:
    """Parallel fetch of TTM key metrics (pbRatio, roe) for each ticker."""

    async def _one(ticker: str) -> Tuple[str, Dict]:
        url = f"{FMP_BASE}/key-metrics-ttm/{ticker}?apikey={FMP_API_KEY}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    row = data[0] if isinstance(data, list) and data else {}
                    return ticker, {
                        "pbRatio": row.get("pbRatioTTM", row.get("pbRatio", 0)),
                        "roe": row.get("roeTTM", row.get("roe", 0)),
                    }
        except Exception:
            pass
        return ticker, {}

    results_list = await asyncio.gather(*[_one(t) for t in tickers])
    return dict(results_list)


async def _fetch_fundamentals(tickers: List[str]) -> Dict[str, Dict]:
    """Merge profile + key metrics into one dict per ticker."""
    connector = aiohttp.TCPConnector(limit=20)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        profiles, metrics = await asyncio.gather(
            _fetch_profiles(session, tickers),
            _fetch_key_metrics(session, tickers),
        )
    merged: Dict[str, Dict] = {}
    for t in tickers:
        merged[t] = {**profiles.get(t, {}), **metrics.get(t, {})}
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio DB loader
# ─────────────────────────────────────────────────────────────────────────────

async def _load_portfolio(user_id: str, org_id: Optional[str], portfolio_id: str) -> Tuple[List[str], List[float]]:
    """Load tickers + weights from PostgreSQL under RLS."""
    pg = await get_postgres_rls_client()
    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                "SELECT tickers, weights, holdings FROM portfolios WHERE id = $1",
                portfolio_id,
            )
    except Exception:
        # Fallback without org context
        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT tickers, weights, holdings FROM portfolios WHERE id = $1",
                portfolio_id,
            )

    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    tickers: List[str] = row["tickers"] or []
    weights: List[float] = row["weights"] or []

    # Try to derive from holdings if parallel arrays are empty / mismatched
    if not tickers or len(tickers) != len(weights):
        import json
        holdings_raw = row.get("holdings")
        if holdings_raw:
            holdings = holdings_raw if isinstance(holdings_raw, list) else json.loads(holdings_raw)
            tickers_h, weights_h = [], []
            total_val = sum(
                float(h.get("totalValue") or h.get("total_value") or 0) for h in holdings
            )
            for h in holdings:
                t = h.get("ticker") or h.get("symbol", "")
                if not t:
                    continue
                val = float(h.get("totalValue") or h.get("total_value") or 0)
                tickers_h.append(t)
                weights_h.append(val / total_val if total_val > 0 else 1.0 / len(holdings))
            if tickers_h:
                tickers, weights = tickers_h, weights_h

    if not tickers:
        raise HTTPException(status_code=422, detail="Portfolio has no holdings")

    if len(weights) != len(tickers):
        weights = [1.0 / len(tickers)] * len(tickers)

    # Normalize
    s = sum(weights)
    weights = [w / s for w in weights] if s > 0 else weights

    return tickers, weights


# ─────────────────────────────────────────────────────────────────────────────
# VaR helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_var(portfolio_returns: pd.Series, portfolio_value: float) -> Dict:
    r = portfolio_returns.dropna()
    if len(r) < 20:
        return {}

    ann_vol = float(r.std() * np.sqrt(252))
    daily_vol = float(r.std())
    ann_ret = float(r.mean() * 252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    skew = float(sp_stats.skew(r))
    kurt = float(sp_stats.kurtosis(r))

    var95 = float(np.percentile(r, 5))
    var99 = float(np.percentile(r, 1))
    cvar95 = float(r[r <= var95].mean()) if (r <= var95).any() else var95
    cvar99 = float(r[r <= var99].mean()) if (r <= var99).any() else var99

    return {
        "historical_95": {"pct": round(-var95, 6), "dollar": round(-var95 * portfolio_value, 2)},
        "historical_99": {"pct": round(-var99, 6), "dollar": round(-var99 * portfolio_value, 2)},
        "cvar_95": {"pct": round(-cvar95, 6), "dollar": round(-cvar95 * portfolio_value, 2)},
        "annual_vol": round(ann_vol, 6),
        "daily_vol": round(daily_vol, 6),
        "annual_return_est": round(ann_ret, 6),
        "sharpe_est": round(sharpe, 4),
        "skewness": round(skew, 4),
        "kurtosis": round(kurt, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{portfolio_id}/factor-analysis")
async def get_portfolio_factor_analysis(
    portfolio_id: str,
    request: Request,
    # ── Data window ──────────────────────────────────────────────────────────
    period: str = Query("1y", regex="^(6mo|1y|2y)$", description="Return history window"),
    benchmark: str = Query("SPY", description="Benchmark ticker for tilts / beta"),
    # ── Barra factor controls ─────────────────────────────────────────────────
    ewa_half_life: int = Query(90, ge=10, le=504, description="EWA covariance half-life (trading days)"),
    nw_lags: int = Query(5, ge=0, le=20, description="Newey-West autocorrelation lags"),
    vol_window: int = Query(60, ge=20, le=252, description="Realized volatility lookback (trading days)"),
    beta_window: int = Query(252, ge=60, le=756, description="OLS beta estimation window (trading days)"),
    shrinkage: float = Query(0.1, ge=0.0, le=0.5, description="Bayesian shrinkage for specific risk"),
    factors: str = Query(
        "Market,Momentum,Size,Value,Quality,Volatility,Beta,Sectors",
        description="Comma-separated factor groups to include. "
                    "Use 'Sectors' as shorthand for all 11 GICS sector factors.",
    ),
    # ── PCA controls ─────────────────────────────────────────────────────────
    pca_n: int = Query(8, ge=2, le=20, description="Number of principal components to return"),
    # ── Cache control ─────────────────────────────────────────────────────────
    force: bool = Query(False, description="Bypass server-side cache and recompute"),
) -> Dict[str, Any]:
    """
    Comprehensive portfolio factor analytics with fully configurable model parameters.

    All Barra model inputs (factor set, covariance horizon, volatility window, beta window,
    shrinkage), PCA depth, and benchmark are exposed as query parameters so the frontend
    can run the model with any combination without a redeploy.
    """
    user_id, org_id = _get_user_ids(request)

    # Parse factor list — 'Sectors' expands to all 11 GICS sector dummies
    requested_factors = {f.strip() for f in factors.split(",")}
    if "Sectors" in requested_factors:
        requested_factors.discard("Sectors")
        requested_factors.update(GICS_SECTORS)

    # Cache key includes all user-controllable params
    cache_key = (
        f"{user_id}:{portfolio_id}:{period}:{benchmark}:"
        f"{ewa_half_life}:{nw_lags}:{vol_window}:{beta_window}:{shrinkage}:"
        f"{','.join(sorted(requested_factors))}:{pca_n}"
    )

    # Return cached result if still fresh (unless caller forced a refresh)
    if not force:
        cached = _RESULT_CACHE.get(cache_key)
        if cached:
            result, expiry = cached
            if time.monotonic() < expiry:
                logger.debug("factor-analysis cache hit for %s", portfolio_id)
                return result

    # On force-refresh, drop any stale entry so the new result is stored fresh
    if force:
        _RESULT_CACHE.pop(cache_key, None)

    # Deduplicate: if a compute is already in-flight for this key, await it
    if cache_key in _inflight:
        logger.debug("factor-analysis awaiting in-flight compute for %s", portfolio_id)
        return await _inflight[cache_key]

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _inflight[cache_key] = fut

    try:
        result = await _compute_factor_analysis(
            portfolio_id, user_id, org_id, period, benchmark,
            requested_factors, ewa_half_life, nw_lags,
            vol_window, beta_window, shrinkage, pca_n,
        )
        _RESULT_CACHE[cache_key] = (result, time.monotonic() + _CACHE_TTL_S)
        fut.set_result(result)
        return result
    except Exception as exc:
        fut.set_exception(exc)
        raise
    finally:
        _inflight.pop(cache_key, None)


async def _compute_factor_analysis(
    portfolio_id: str,
    user_id: str,
    org_id: Optional[str],
    period: str,
    benchmark: str,
    requested_factors: set,
    ewa_half_life: int,
    nw_lags: int,
    vol_window: int,
    beta_window: int,
    shrinkage: float,
    pca_n: int,
) -> Dict[str, Any]:
    # 1. Load portfolio
    tickers, weights = await _load_portfolio(user_id, org_id, portfolio_id)
    portfolio_value = sum(weights)  # weights are already fractions; use 1M as proxy
    portfolio_value_dollars = 1_000_000.0  # nominal for VaR dollar display

    # Cap at 100 tickers for performance
    if len(tickers) > 100:
        tickers = tickers[:100]
        weights = weights[:100]
        s = sum(weights)
        weights = [w / s for w in weights]

    # Always fetch sector ETF proxies so benchmark sector decomposition uses real data
    sector_etf_tickers = list(SECTOR_ETFS.values())
    all_fetch_tickers = list(set(tickers + [benchmark] + sector_etf_tickers))

    # 2. Fetch price history + fundamentals in parallel
    market_server = FMPMarketDataServer()
    try:
        await market_server.connect()
        price_data_raw, fundamentals = await asyncio.gather(
            fetch_market_data_batch(market_server, all_fetch_tickers, period=period),
            _fetch_fundamentals(tickers),
        )
    finally:
        try:
            await market_server.cleanup()
        except Exception:
            pass

    prices: pd.DataFrame = adapt_mcp_to_prices(price_data_raw, all_fetch_tickers)
    if prices.empty or len(prices.columns) < 2:
        raise HTTPException(status_code=422, detail="Insufficient price data for analysis")

    # Separate sector ETF price columns for benchmark sector decomposition
    etf_cols_present = [t for t in sector_etf_tickers if t in prices.columns]
    sector_etf_prices_df = prices[etf_cols_present] if etf_cols_present else pd.DataFrame()

    valid_tickers = [t for t in tickers if t in prices.columns]
    valid_weights = []
    for t in valid_tickers:
        idx = tickers.index(t)
        valid_weights.append(weights[idx])
    if sum(valid_weights) > 0:
        s = sum(valid_weights)
        valid_weights = [w / s for w in valid_weights]

    weights_arr = np.array(valid_weights)

    # 3. Portfolio return series for VaR
    returns_df = prices[valid_tickers].pct_change().dropna()
    portfolio_returns = returns_df @ weights_arr

    var_result = _compute_var(portfolio_returns, portfolio_value_dollars)

    # 4. Barra fundamental model
    barra_result = {}
    try:
        model = BarraFundamentalModel()
        B = model.compute_factor_exposures(
            valid_tickers, prices, fundamentals,
            requested_factors=requested_factors,
            vol_window=vol_window,
            beta_window=beta_window,
            benchmark_ticker=benchmark,
        )
        market_caps = {t: fundamentals.get(t, {}).get("mktCap", 1e9) for t in valid_tickers}
        model.estimate_factor_returns(prices, market_caps)
        model.estimate_factor_covariance(half_life=ewa_half_life, nw_lags=nw_lags, eigen_mc=50)
        model.estimate_specific_risk(shrinkage=shrinkage)
        barra_result = model.portfolio_risk(weights_arr, valid_tickers)
        factor_names = model.factor_names or []
    except Exception as e:
        logger.warning("Barra model failed: %s", e)
        model = None
        factor_names = []

    # 5. PCA
    pca_result = {}
    try:
        pca = PCAFactorModel()
        pca.fit(prices, valid_tickers)
        pca_result = pca.portfolio_analysis(weights_arr, valid_tickers, n_components=pca_n, top_n_loadings=5)
    except Exception as e:
        logger.warning("PCA failed: %s", e)

    # 6. Ex ante factor tilts vs benchmark
    tilts_result = {}
    try:
        if model is not None and factor_names:
            spy_fund = fundamentals.get(benchmark, {})
            benchmark_prices_series = prices[benchmark] if benchmark in prices.columns else None
            benchmark_exposures = compute_benchmark_exposures(
                benchmark_prices_series,
                spy_fund,
                factor_names,
                model,
                sector_etf_prices=sector_etf_prices_df if not sector_etf_prices_df.empty else None,
            )
            port_exposures = barra_result.get("portfolio_exposures", {})
            active_tilts = {}
            for f in STYLE_FACTORS:
                if f in port_exposures and f in benchmark_exposures:
                    p_val = port_exposures[f]
                    b_val = benchmark_exposures[f]
                    active_tilts[f] = {
                        "portfolio": round(p_val, 4),
                        "benchmark": round(b_val, 4),
                        "active": round(p_val - b_val, 4),
                    }

            # Sector tilts
            for s in GICS_SECTORS:
                if s in port_exposures and s in benchmark_exposures:
                    p_val = port_exposures[s]
                    b_val = benchmark_exposures[s]
                    if abs(p_val - b_val) > 0.01:
                        active_tilts[s] = {
                            "portfolio": round(p_val, 4),
                            "benchmark": round(b_val, 4),
                            "active": round(p_val - b_val, 4),
                        }

            # Active factor risk
            if model.F_cov is not None:
                port_exp_arr = np.array([port_exposures.get(f, 0.0) for f in factor_names])
                bench_exp_arr = np.array([benchmark_exposures.get(f, 0.0) for f in factor_names])
                active_arr = port_exp_arr - bench_exp_arr
                active_var = float(active_arr @ model.F_cov @ active_arr)
                active_factor_risk = round(np.sqrt(max(active_var, 0)), 6)
                te_est = round(np.sqrt(max(active_var + barra_result.get("specific_risk", 0) ** 2 * 0.1, 0)), 6)
            else:
                active_factor_risk = 0.0
                te_est = 0.0

            tilts_result = {
                "benchmark": benchmark,
                "active_factor_risk": active_factor_risk,
                "tracking_error_est": te_est,
                "active_tilts": active_tilts,
            }
    except Exception as e:
        logger.warning("Tilts calculation failed: %s", e)

    return {
        "portfolio_id": portfolio_id,
        "as_of": date.today().isoformat(),
        "period": period,
        "n_assets": len(valid_tickers),
        "n_factors": len(factor_names),
        "var": var_result,
        "barra": barra_result,
        "pca": pca_result,
        "tilts": tilts_result,
    }
