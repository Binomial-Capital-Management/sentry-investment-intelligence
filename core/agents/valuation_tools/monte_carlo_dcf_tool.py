"""
Monte Carlo DCF Tool
Probabilistic DCF valuation with data-driven assumptions.
Status: Production
Created: December 2025

PURPOSE
- Generate intrinsic value distributions from uncertain DCF inputs
- Answer: "What's the probability the stock is undervalued?"
- Quantify valuation uncertainty and sensitivity drivers

THEORY
Traditional DCF implies false precision (one growth rate → one value).
Monte Carlo propagates parameter uncertainty:
- Growth mean/std derived from HISTORICAL DATA (5-year EPS growth)
- Discount rate via CAPM: live DGS10 risk-free rate (FRED) + beta × ERP
- Terminal growth is AGENT'S DISCRETION (based on company's moat, industry)
- Run N DCF calculations (default 1000, configurable)
- Get probability distribution of fair values

DATA FLOW
1. Agent analyzes company → determines terminal_growth based on moat/industry
2. Agent calls this tool with terminal_growth + model config
3. Tool fetches historical data → calculates growth mean/std from EPS history
4. Tool fetches WACC inputs → uses cost of equity
5. Tool runs Monte Carlo → returns statistics
"""

import json
import logging
from typing import List, Optional

import numpy as np
from scipy import stats
import plotly.graph_objects as go

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.risk_tools.shared import register_chart_handle

logger = logging.getLogger(__name__)


def _extract_scalar(value):
    """
    Extract a scalar value from potentially nested FMP data.
    Handles: direct value, list (take first), dict with 'value' key.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and len(value) > 0:
        # Take most recent (first) value from list
        return _extract_scalar(value[0])
    if isinstance(value, dict):
        # Try common keys
        for key in ['value', 'v', 'amount']:
            if key in value:
                return _extract_scalar(value[key])
        # If it's a single-key dict, extract that value
        if len(value) == 1:
            return _extract_scalar(list(value.values())[0])
    return None


def _calculate_dcf_values_vectorized(
    base_metric: float,
    growth_samples: np.ndarray,
    discount_samples: np.ndarray,
    terminal_growth_samples: np.ndarray,
    stages: int,
    stage1_years: int,
    stage2_years: int = 0,
) -> np.ndarray:
    """
    Calculate DCF intrinsic values for all sample combinations (vectorized).
    """
    n_samples = len(growth_samples)
    values = np.zeros(n_samples)

    if base_metric is None or base_metric <= 0:
        return values

    if stages == 1:
        # Gordon Growth Model: V = CF * (1+g) / (r - g)
        spread = discount_samples - terminal_growth_samples
        spread = np.maximum(spread, 0.001)
        values = base_metric * (1 + terminal_growth_samples) / spread

    elif stages == 2:
        # Stage 1: High growth, Stage 2: Terminal perpetuity
        total_pv = np.zeros(n_samples)
        current_cf = np.full(n_samples, base_metric)

        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_samples)
            discount_factor = (1 + discount_samples) ** year
            total_pv += current_cf / discount_factor

        # Terminal value
        spread = discount_samples - terminal_growth_samples
        spread = np.maximum(spread, 0.001)
        terminal_cf = current_cf * (1 + terminal_growth_samples)
        terminal_value = terminal_cf / spread
        terminal_pv = terminal_value / ((1 + discount_samples) ** stage1_years)

        values = total_pv + terminal_pv

    elif stages == 3:
        # Stage 1: High growth, Stage 2: Linear fade, Stage 3: Terminal
        total_pv = np.zeros(n_samples)
        current_cf = np.full(n_samples, base_metric)

        # Stage 1
        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_samples)
            discount_factor = (1 + discount_samples) ** year
            total_pv += current_cf / discount_factor

        # Stage 2: Linear fade
        if stage2_years > 0:
            growth_decrement = (growth_samples - terminal_growth_samples) / stage2_years
            fade_growth = growth_samples.copy()

            for year_offset in range(stage2_years):
                year = stage1_years + year_offset + 1
                fade_growth = fade_growth - growth_decrement
                current_cf = current_cf * (1 + fade_growth)
                discount_factor = (1 + discount_samples) ** year
                total_pv += current_cf / discount_factor

        # Terminal value
        total_years = stage1_years + stage2_years
        spread = discount_samples - terminal_growth_samples
        spread = np.maximum(spread, 0.001)
        terminal_cf = current_cf * (1 + terminal_growth_samples)
        terminal_value = terminal_cf / spread
        terminal_pv = terminal_value / ((1 + discount_samples) ** total_years)

        values = total_pv + terminal_pv

    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    return values


def _calculate_sensitivity(
    param_samples: dict,
    values: np.ndarray
) -> list:
    """
    Rank input parameters by impact on valuation variance.
    Uses Spearman correlation between inputs and outputs.
    """
    sensitivity = []

    for param_name, samples in param_samples.items():
        corr, p_value = stats.spearmanr(samples, values)

        sensitivity.append({
            "param": param_name,
            "correlation": round(corr, 4) if not np.isnan(corr) else 0.0,
            "abs_correlation": abs(corr) if not np.isnan(corr) else 0.0,
            "p_value": round(p_value, 4) if not np.isnan(p_value) else 1.0,
        })

    sensitivity.sort(key=lambda x: x["abs_correlation"], reverse=True)

    for i, item in enumerate(sensitivity):
        item["impact_rank"] = i + 1
        del item["abs_correlation"]

    return sensitivity


def _build_histogram(values: np.ndarray, n_buckets: int = 20) -> dict:
    """Build histogram data for visualization."""
    valid_values = values[~np.isnan(values) & ~np.isinf(values)]

    if len(valid_values) == 0:
        return {"buckets": [], "bucket_width": 0}

    hist_counts, bin_edges = np.histogram(valid_values, bins=n_buckets)

    buckets = []
    for i in range(len(hist_counts)):
        buckets.append({
            "min": round(bin_edges[i], 2),
            "max": round(bin_edges[i + 1], 2),
            "count": int(hist_counts[i])
        })

    return {
        "buckets": buckets,
        "bucket_width": round(bin_edges[1] - bin_edges[0], 2)
    }


def _build_distribution_chart(
    values: np.ndarray,
    current_price: float,
    symbol: str,
    percentiles: dict,
) -> dict:
    """
    Build Plotly distribution chart for Monte Carlo DCF results.

    Returns dict with plotly figure and metadata for wrap_plotly_charts.
    """
    valid_values = values[~np.isnan(values) & ~np.isinf(values) & (values > 0)]

    if len(valid_values) == 0:
        return None

    # Create histogram
    fig = go.Figure()

    # Add histogram of valuation distribution
    fig.add_trace(go.Histogram(
        x=valid_values,
        nbinsx=50,
        name="Valuation Distribution",
        marker=dict(
            color="rgba(59, 130, 246, 0.7)",  # Blue
            line=dict(color="rgba(59, 130, 246, 1)", width=1)
        ),
        hovertemplate="Value: $%{x:,.0f}<br>Count: %{y}<extra></extra>"
    ))

    # Add vertical line for current price
    fig.add_vline(
        x=current_price,
        line_dash="solid",
        line_color="red",
        line_width=2,
        annotation_text=f"Current: ${current_price:,.0f}",
        annotation_position="top"
    )

    # Add vertical lines for key percentiles
    median = percentiles.get("p50", np.median(valid_values))
    fig.add_vline(
        x=median,
        line_dash="dash",
        line_color="green",
        line_width=2,
        annotation_text=f"Median: ${median:,.0f}",
        annotation_position="top right"
    )

    # Add shaded regions for confidence intervals
    p5 = percentiles.get("p5", np.percentile(valid_values, 5))
    p95 = percentiles.get("p95", np.percentile(valid_values, 95))

    # Calculate probability undervalued
    prob_undervalued = float(np.mean(valid_values > current_price))

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"{symbol} Monte Carlo DCF Distribution<br>"
                 f"<sub>P(Undervalued) = {prob_undervalued:.1%} | "
                 f"90% CI: ${p5:,.0f} - ${p95:,.0f}</sub>",
            font=dict(size=16),
            x=0.5,
            xanchor="center"
        ),
        xaxis=dict(
            title="Intrinsic Value per Share ($)",
            tickformat="$,.0f",
            showgrid=True,
            gridcolor="rgba(128, 128, 128, 0.2)"
        ),
        yaxis=dict(
            title="Frequency",
            showgrid=True,
            gridcolor="rgba(128, 128, 128, 0.2)"
        ),
        bargap=0.05,
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        width=800,
        height=500,
        annotations=[
            dict(
                text=f"<b>Current Price:</b> ${current_price:,.0f}<br>"
                     f"<b>Median Value:</b> ${median:,.0f}<br>"
                     f"<b>P(Undervalued):</b> {prob_undervalued:.1%}",
                xref="paper", yref="paper",
                x=0.98, y=0.98,
                xanchor="right", yanchor="top",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="gray",
                borderwidth=1,
                font=dict(size=11)
            )
        ]
    )

    return {
        "plotly": fig.to_dict(),
        "id": f"mc_dcf_distribution_{symbol.lower()}",
        "title": f"{symbol} Monte Carlo DCF Distribution",
        "alt_text": f"Distribution of {len(valid_values):,} Monte Carlo DCF valuations for {symbol}. "
                    f"Median: ${median:,.0f}, Current: ${current_price:,.0f}, "
                    f"P(Undervalued): {prob_undervalued:.1%}",
        "metadata": {
            "symbol": symbol,
            "iterations": len(valid_values),
            "median": median,
            "current_price": current_price,
            "prob_undervalued": prob_undervalued
        }
    }


# Maps ISO-2 country codes → (FRED series ID, static fallback rate)
# FRED series: 10Y government bond yield where available.
# Fallback rates are approximate long-run averages (used only if FRED is unreachable).
_COUNTRY_RF_MAP: dict[str, tuple[str, float]] = {
    "US":  ("DGS10",            0.043),
    "CA":  ("IRLTLT01CAM156N",  0.036),
    "GB":  ("IRLTLT01GBM156N",  0.042),
    "DE":  ("IRLTLT01DEM156N",  0.028),
    "FR":  ("IRLTLT01FRM156N",  0.031),
    "IT":  ("IRLTLT01ITM156N",  0.038),
    "ES":  ("IRLTLT01ESM156N",  0.036),
    "NL":  ("IRLTLT01NLM156N",  0.028),
    "JP":  ("IRLTLT01JPM156N",  0.010),
    "AU":  ("IRLTLT01AUM156N",  0.043),
    "CH":  ("IRLTLT01CHM156N",  0.010),
    "SE":  ("IRLTLT01SEM156N",  0.025),
    "KR":  ("IRLTLT01KRM156N",  0.032),
    "IN":  ("IRLTLT01INM156N",  0.070),
    "BR":  ("IRLTLT01BRM156N",  0.130),
    "MX":  ("IRLTLT01MXM156N",  0.093),
    "ZA":  ("IRLTLT01ZAM156N",  0.092),
    "CN":  (None,               0.025),  # FRED has no clean 10Y CNY series
    "HK":  (None,               0.040),
    "SG":  (None,               0.032),
}

# Damodaran implied ERP by country (Jan 2025 update).
# Source: pages.stern.nyu.edu/~adamodar/
_COUNTRY_ERP_MAP: dict[str, float] = {
    "US": 0.053, "CA": 0.053, "GB": 0.057, "DE": 0.054, "FR": 0.056,
    "IT": 0.068, "ES": 0.063, "NL": 0.054, "JP": 0.063, "AU": 0.055,
    "CH": 0.054, "SE": 0.055, "KR": 0.058, "IN": 0.079, "BR": 0.103,
    "MX": 0.082, "ZA": 0.099, "CN": 0.072, "HK": 0.059, "SG": 0.053,
}
_DEFAULT_ERP = 0.060  # Global average for unlisted countries


async def _fetch_risk_free_rate(country: str = "US") -> tuple[float, str]:
    """
    Fetch the 10-year government bond yield for the given ISO-2 country code.
    Uses FRED where a series exists; falls back to a static estimate otherwise.
    Returns (rate_as_decimal, source_label).
    """
    country = country.strip().upper()
    fred_series, static_fallback = _COUNTRY_RF_MAP.get(country, ("DGS10", 0.043))

    if fred_series is None:
        logger.info(f"No FRED series for country={country}, using static fallback {static_fallback:.1%}")
        return static_fallback, f"static_{country}"

    eco = None
    try:
        eco = EconomicDataServer()
        await eco.connect()
        result = await eco.get_series_data(fred_series)
        await eco.cleanup()
        eco = None

        data_points = result.get("data", [])
        if data_points:
            latest = data_points[-1]["value"]
            rate = latest / 100.0
            label = f"FRED_{fred_series}_{data_points[-1]['date']}"
            logger.info(f"Risk-free rate ({country}): {fred_series}={latest:.2f}% → {rate:.4f}")
            return rate, label
    except Exception as e:
        logger.warning(f"Failed to fetch {fred_series} from FRED for country={country}: {e}")
        if eco:
            try:
                await eco.cleanup()
            except Exception:
                pass

    logger.warning(f"Using static risk-free rate fallback for {country}: {static_fallback:.1%}")
    return static_fallback, f"static_fallback_{country}"


def _calculate_growth_stats(eps_history: list) -> tuple:
    """
    Calculate growth rate mean and std from historical EPS data.
    Returns (mean, std) tuple.
    """
    if not eps_history or len(eps_history) < 2:
        return 0.08, 0.04  # Conservative defaults

    # Filter to only valid numeric values
    clean_eps = []
    for v in eps_history:
        if isinstance(v, (int, float)) and v is not None and not np.isnan(v):
            clean_eps.append(float(v))

    if len(clean_eps) < 2:
        logger.warning(f"Insufficient clean EPS data ({len(clean_eps)} values)")
        return 0.08, 0.04

    # Calculate year-over-year growth rates
    growth_rates = []
    for i in range(1, len(clean_eps)):
        prev_eps = clean_eps[i]  # Older (list is newest first)
        curr_eps = clean_eps[i - 1]  # Newer

        if prev_eps > 0:
            growth = (curr_eps - prev_eps) / prev_eps
            # Filter extreme outliers (>200% growth or <-80% decline)
            if -0.8 < growth < 2.0:
                growth_rates.append(growth)

    if len(growth_rates) < 2:
        return 0.08, 0.04

    mean = float(np.mean(growth_rates))
    std = float(np.std(growth_rates))

    # Floor std at 2% to avoid overconfidence, cap at 15%
    std = max(min(std, 0.15), 0.02)

    return mean, std


async def analyze_monte_carlo_dcf_internal(
    symbol: str,
    fields: Optional[List[str]] = None,
    # Terminal growth - AGENT'S DISCRETION based on company analysis
    terminal_growth: float = 0.025,
    # DCF model configuration
    stages: int = 2,
    stage1_years: int = 5,
    stage2_years: int = 5,
    model_type: str = "eps",
    # Simulation settings
    iterations: int = 1000,
    seed: Optional[int] = None,
    # Output options
    include_sensitivity: bool = True,
    include_histogram: bool = False,
) -> dict:
    """
    Run Monte Carlo DCF to generate intrinsic value distribution.

    Growth and discount rate are AUTOMATICALLY derived from FMP data:
    - Growth mean/std: calculated from 5-year historical EPS growth
    - Discount rate: from WACC inputs (cost of equity via CAPM)

    Only terminal_growth requires agent judgment (based on moat, industry).

    PARAMETERS
    ----------
    symbol : str
        Stock ticker symbol

    fields : List[str]
        Fields to fetch from FMP (from discover_fields)

    terminal_growth : float
        Agent's estimate of perpetuity growth rate based on:
        - Company's competitive moat (strong → higher)
        - Industry growth (tech → higher, utilities → lower)
        - GDP growth expectations
        Typical range: 0.02-0.04 (2-4%)

    DCF MODEL:
    - stages: 1 (stable), 2 (growth→terminal), 3 (growth→fade→terminal)
    - stage1_years: High-growth duration (default 5)
    - stage2_years: Transition duration for 3-stage (default 5)
    - model_type: "eps" or "fcf"

    SIMULATION:
    - iterations: Number of simulations (default 1000, max 50000)
    - seed: Random seed for reproducibility

    DATA-DRIVEN (auto-fetched from FMP):
    - Growth mean: average of 5-year historical EPS growth rates
    - Growth std: volatility of historical EPS growth rates
    - Discount rate: cost of equity from WACC inputs

    RETURNS
    -------
    JSON with valuation distribution, probability undervalued, sensitivity drivers
    """

    # Default fields if not provided (for Canvas)
    if not fields or len(fields) == 0:
        fields = ["price", "netIncomePerShareTTM", "freeCashFlowPerShareTTM", "outstandingShares", "marketCap"]

    # Cap iterations
    iterations = min(iterations, 50000)

    market_server = None

    try:
        logger.info(
            f"Monte Carlo DCF for {symbol}: "
            f"{iterations} iterations, {stages}-stage, "
            f"terminal_growth={terminal_growth:.1%}"
        )

        # =========================================
        # Fetch Historical Data (5 years)
        # =========================================
        fmp_fields = list(fields)
        essential = ["price", "netIncomePerShareTTM", "freeCashFlowPerShareTTM", "outstandingShares", "marketCap", "beta", "country"]
        for f in essential:
            if f not in fmp_fields:
                fmp_fields.append(f)

        market_server = FMPMarketDataServer()
        await market_server.connect()

        # Fetch current data
        current_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": fmp_fields,
            "params": {"period": "annual", "limit": 1}
        })

        raw_data = {}
        if current_result and hasattr(current_result, "content"):
            current_data = safe_parse_json(current_result)
            if current_data.get("status") != "missing_required_params":
                raw_data = current_data.get("data", current_data)

        if not raw_data:
            return {
                "error": f"No financial data found for {symbol}",
                "symbol": symbol
            }

        price = _extract_scalar(raw_data.get("price"))
        shares = _extract_scalar(raw_data.get("outstandingShares")) or _extract_scalar(raw_data.get("dilutedSharesOutstanding"))
        eps = _extract_scalar(raw_data.get("netIncomePerShareTTM")) or _extract_scalar(raw_data.get("eps"))
        fcf_per_share = _extract_scalar(raw_data.get("freeCashFlowPerShareTTM"))
        market_cap = _extract_scalar(raw_data.get("marketCap"))
        market_beta = _extract_scalar(raw_data.get("beta"))
        company_country = (raw_data.get("country") or "US").strip().upper()

        if price is None:
            raise ValueError(f"Missing price data for {symbol}")

        # Fetch 5-year historical EPS for growth calculation
        hist_result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": ["eps", "epsdiluted", "netIncome"],
            "historical": True,
            "period": "annual",
            "limit": 5
        })

        eps_history = []
        if hist_result and hasattr(hist_result, "content"):
            hist_data = safe_parse_json(hist_result)

            # Unwrap data envelope if present
            if isinstance(hist_data, dict) and "data" in hist_data:
                hist_data = hist_data["data"]

            # Extract EPS values from history - handle multiple formats
            if isinstance(hist_data, list):
                # Format: [{"eps": 5.0, ...}, {"eps": 4.5, ...}]
                for d in hist_data:
                    if isinstance(d, dict):
                        eps_val = _extract_scalar(d.get("eps") or d.get("epsdiluted") or d.get("netIncome"))
                        eps_history.append(eps_val)
                    elif isinstance(d, (int, float)):
                        eps_history.append(float(d))
            elif isinstance(hist_data, dict):
                # Format: {"eps": [5.0, 4.5, ...]} or {"eps": {"2024": 5.0, ...}}
                eps_data = hist_data.get("eps") or hist_data.get("epsdiluted") or hist_data.get("netIncome")
                if isinstance(eps_data, list):
                    eps_history = [_extract_scalar(v) for v in eps_data]
                elif isinstance(eps_data, dict):
                    # Dict keyed by date/year
                    eps_history = [_extract_scalar(v) for v in eps_data.values()]

        logger.debug(f"Historical EPS extraction for {symbol}: {eps_history}")

        await market_server.cleanup()
        market_server = None

        # Calculate growth stats from historical data
        growth_mean, growth_std = _calculate_growth_stats(eps_history)
        logger.info(f"Historical EPS growth for {symbol}: mean={growth_mean:.1%}, std={growth_std:.1%}")

        # =========================================
        # Fetch WACC / Cost of Equity
        # =========================================
        # Strategy:
        # 1. Try FMP key-metrics-ttm for direct beta (already on market server)
        # 2. Fall back to beta fetched alongside market data above
        # 3. Compute CAPM: rf (live DGS10 from FRED) + beta * ERP
        # Note: FMPAdvancedValuationServer.calculate_wacc_inputs is a stub —
        # it only checks the DCF endpoint and returns nothing useful for CAPM.
        # All real WACC inputs live in FMPMarketDataServer.

        discount_rate = None
        discount_source = "none"
        beta_used = None

        # ── Step 1: fetch beta from key-metrics-ttm if not already available ──
        if not market_beta or not (0.0 < market_beta < 5.0):
            try:
                km_server = FMPMarketDataServer()
                await km_server.connect()
                km_result = await km_server.call_tool("get_fields", {
                    "symbol": symbol,
                    "fields": ["beta", "returnOnEquityTTM"],
                    "params": {"period": "annual", "limit": 1}
                })
                await km_server.cleanup()
                if km_result and not km_result.isError:
                    km_data = safe_parse_json(km_result)
                    km_data = km_data.get("data", km_data) if isinstance(km_data, dict) else km_data
                    fetched_beta = _extract_scalar(
                        km_data.get("beta") or km_data.get("betaTTM")
                    )
                    if fetched_beta and 0.0 < fetched_beta < 5.0:
                        market_beta = fetched_beta
                        logger.info(f"Beta from key-metrics for {symbol}: {market_beta:.2f}")
            except Exception as e:
                logger.warning(f"Could not fetch key-metrics beta for {symbol}: {e}")

        # ── Step 2: live risk-free rate from FRED, routed by company country ──
        risk_free, rf_source = await _fetch_risk_free_rate(company_country)

        # Damodaran implied ERP for the company's home country (Jan 2025)
        equity_risk_premium = _COUNTRY_ERP_MAP.get(company_country, _DEFAULT_ERP)
        logger.info(f"Country={company_country}, ERP={equity_risk_premium:.1%}")

        # ── Step 3: CAPM → discount rate ──
        if market_beta and 0.0 < market_beta < 5.0:
            beta_used = market_beta
            discount_rate = risk_free + beta_used * equity_risk_premium
            discount_source = f"capm(rf={rf_source},beta={beta_used:.2f},erp={equity_risk_premium:.1%})"
            logger.info(
                f"CAPM for {symbol}: rf={risk_free:.2%} + {beta_used:.2f}×{equity_risk_premium:.1%} "
                f"= {discount_rate:.2%}"
            )
        else:
            # No beta available at all — use rf + market average beta (1.0) as proxy
            beta_used = 1.0
            discount_rate = risk_free + beta_used * equity_risk_premium
            discount_source = f"capm_avg_beta(rf={rf_source},beta=1.0,erp={equity_risk_premium:.1%})"
            logger.warning(
                f"No beta found for {symbol} — using market-average beta=1.0: "
                f"discount_rate={discount_rate:.2%}"
            )

        logger.info(f"Discount rate for {symbol}: {discount_rate:.2%} ({discount_source})")

        base_metric = eps if model_type == "eps" else fcf_per_share

        # Ensure base_metric is a valid number
        if not isinstance(base_metric, (int, float)) or base_metric is None or base_metric <= 0:
            return json.dumps({
                "error": f"Invalid base metric for {model_type}: {base_metric}",
                "symbol": symbol,
                "suggestion": "Try model_type='fcf' if EPS is negative"
            })

        # =========================================
        # Generate Samples & Run Simulation
        # =========================================
        rng = np.random.default_rng(seed)

        # Sample from distributions (data-derived)
        growth_samples = rng.normal(growth_mean, growth_std, iterations)

        # Terminal growth: triangular around agent's estimate ±0.5%
        terminal_samples = rng.triangular(
            max(0.01, terminal_growth - 0.005),
            terminal_growth,
            min(0.05, terminal_growth + 0.01),
            iterations
        )

        # Discount rate: uniform ±1% around calculated rate
        discount_samples = rng.uniform(
            max(0.05, discount_rate - 0.01),
            discount_rate + 0.01,
            iterations
        )

        # Store for sensitivity analysis
        param_samples = {
            "stage1_growth": growth_samples,
            "terminal_growth": terminal_samples,
            "discount_rate": discount_samples,
        }

        logger.info(f"Running {iterations} DCF simulations for {symbol}")

        values = _calculate_dcf_values_vectorized(
            base_metric=base_metric,
            growth_samples=growth_samples,
            discount_samples=discount_samples,
            terminal_growth_samples=terminal_samples,
            stages=stages,
            stage1_years=stage1_years,
            stage2_years=stage2_years if stages == 3 else 0,
        )

        valid_values = values[~np.isnan(values) & ~np.isinf(values) & (values > 0)]

        if len(valid_values) == 0:
            return {
                "error": "All simulations invalid",
                "symbol": symbol,
                "suggestion": "Check that discount_rate > terminal_growth"
            }

        valid_ratio = len(valid_values) / iterations

        # =========================================
        # Calculate Statistics
        # =========================================
        mean_value = float(np.mean(valid_values))
        median_value = float(np.median(valid_values))
        std_value = float(np.std(valid_values))

        percentiles_to_report = [5, 25, 50, 75, 95]
        percentile_values = {
            f"p{int(p)}": float(np.percentile(valid_values, p))
            for p in percentiles_to_report
        }

        confidence_intervals = {
            "80%": [float(np.percentile(valid_values, 10)), float(np.percentile(valid_values, 90))],
            "95%": [float(np.percentile(valid_values, 2.5)), float(np.percentile(valid_values, 97.5))]
        }

        probability_undervalued = float(np.mean(valid_values > price))
        expected_upside = (mean_value - price) / price if price > 0 else 0

        # Sensitivity
        sensitivity_drivers = None
        if include_sensitivity:
            valid_mask = ~np.isnan(values) & ~np.isinf(values) & (values > 0)
            valid_param_samples = {k: v[valid_mask] for k, v in param_samples.items()}
            sensitivity_drivers = _calculate_sensitivity(valid_param_samples, valid_values)

        # Histogram
        histogram = _build_histogram(valid_values) if include_histogram else None

        # =========================================
        # Build Response
        # =========================================
        payload = {
            "status": "success",
            "symbol": symbol,
            "iterations": iterations,
            "valid_iterations": len(valid_values),

            "valuation_distribution": {
                "mean": round(mean_value, 2),
                "median": round(median_value, 2),
                "std": round(std_value, 2),
                "percentiles": {k: round(v, 2) for k, v in percentile_values.items()},
                "confidence_intervals": {
                    k: [round(v[0], 2), round(v[1], 2)]
                    for k, v in confidence_intervals.items()
                }
            },

            "current_price": price,
            "probability_undervalued": round(probability_undervalued, 4),
            "probability_undervalued_pct": f"{probability_undervalued:.1%}",
            "expected_upside": round(expected_upside, 4),
            "expected_upside_pct": f"{expected_upside:.1%}",

            "model_config": {
                "stages": stages,
                "stage1_years": stage1_years,
                "stage2_years": stage2_years if stages == 3 else 0,
                "model_type": model_type,
                "base_metric": round(base_metric, 2),
            },

            "data_derived_inputs": {
                "growth_mean": round(growth_mean, 4),
                "growth_mean_pct": f"{growth_mean:.1%}",
                "growth_std": round(growth_std, 4),
                "growth_std_pct": f"{growth_std:.1%}",
                "growth_source": f"5-year historical EPS ({len(eps_history)} data points)",
                "discount_rate": round(discount_rate, 4),
                "discount_rate_pct": f"{discount_rate:.1%}",
                "discount_source": discount_source,
                "terminal_growth": round(terminal_growth, 4),
                "terminal_growth_pct": f"{terminal_growth:.1%}",
                "terminal_source": "agent_provided",
            },

            "financial_data": {
                "price": price,
                "shares": shares,
                "market_cap": market_cap,
                "eps": eps,
                "fcf_per_share": fcf_per_share,
                "historical_eps": eps_history[:5] if eps_history else None,
            },

            "methodology_notes": [
                f"{iterations} Monte Carlo simulations ({valid_ratio:.1%} valid)",
                f"{stages}-stage DCF: {stage1_years}yr high-growth" +
                (f" + {stage2_years}yr transition" if stages == 3 else "") +
                " + terminal",
                f"Growth: N({growth_mean:.1%}, {growth_std:.1%}) from historical EPS",
                f"Terminal: agent={terminal_growth:.1%} with ±0.5% uncertainty",
                f"Discount: {discount_rate:.1%} ({discount_source}) with ±1% uncertainty",
            ],
        }

        if sensitivity_drivers:
            payload["sensitivity_drivers"] = sensitivity_drivers
        if histogram:
            payload["histogram"] = histogram

        # Build distribution chart
        chart = _build_distribution_chart(
            values=valid_values,
            current_price=price,
            symbol=symbol,
            percentiles=percentile_values
        )
        if chart:
            wrapped_chart = register_chart_handle(
                chart["plotly"],
                chart_type=chart.get("id", "mc_dcf_distribution"),
                title=chart.get("title", f"{symbol} Monte Carlo DCF"),
                alt_text=chart.get("alt_text", ""),
                metadata=chart.get("metadata"),
                chart_id=chart.get("id"),
            )
            payload["charts"] = [wrapped_chart]

        logger.info(
            f"Monte Carlo DCF {symbol}: median=${median_value:.2f}, "
            f"P(undervalued)={probability_undervalued:.1%}"
        )

        return payload

    except Exception as e:
        logger.error(f"Error in Monte Carlo DCF for {symbol}: {str(e)}")
        return {
            "error": f"Monte Carlo DCF failed: {str(e)}",
            "symbol": symbol
        }

    finally:
        if market_server is not None:
            try:
                await market_server.cleanup()
            except Exception:
                pass


@function_tool
async def analyze_monte_carlo_dcf(
    symbol: str,
    fields: List[str],
    # Terminal growth - AGENT'S DISCRETION based on company analysis
    terminal_growth: float = 0.025,
    # DCF model configuration
    stages: int = 2,
    stage1_years: int = 5,
    stage2_years: int = 5,
    model_type: str = "eps",
    # Simulation settings
    iterations: int = 1000,
    seed: Optional[int] = None,
    # Output options
    include_sensitivity: bool = True,
    include_histogram: bool = False,
) -> str:
    """
    Run Monte Carlo DCF to generate intrinsic value distribution.

    Growth and discount rate are AUTOMATICALLY derived from FMP data:
    - Growth mean/std: calculated from 5-year historical EPS growth
    - Discount rate: from WACC inputs (cost of equity via CAPM)

    Only terminal_growth requires agent judgment (based on moat, industry).

    PARAMETERS
    ----------
    symbol : str
        Stock ticker symbol
    fields : List[str]
        Fields to fetch from FMP (from discover_fields)
    terminal_growth : float
        Agent's estimate of perpetuity growth rate (0.02-0.04 typical)
    stages : int
        1 (stable), 2 (growth→terminal), 3 (growth→fade→terminal)
    stage1_years : int
        High-growth duration (default 5)
    model_type : str
        "eps" or "fcf"
    iterations : int
        Number of simulations (default 1000, max 50000)

    RETURNS
    -------
    JSON with valuation distribution, probability undervalued, sensitivity drivers
    """
    result = await analyze_monte_carlo_dcf_internal(
        symbol=symbol,
        fields=fields,
        terminal_growth=terminal_growth,
        stages=stages,
        stage1_years=stage1_years,
        stage2_years=stage2_years,
        model_type=model_type,
        iterations=iterations,
        seed=seed,
        include_sensitivity=include_sensitivity,
        include_histogram=include_histogram,
    )
    return json.dumps(result)
