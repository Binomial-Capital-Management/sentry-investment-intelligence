"""
ARIMAX Macro Forecasting Tool - Multi-Factor Time Series Analysis

A power tool for quantitative macro-driven forecasting that combines:
- FRED economic indicators (800,000+ series: rates, inflation, employment, GDP)
- Unusual Whales options sentiment (IV rank, put/call, Greek flow, market tide)
- FMP market data (prices, volume, correlations)

Supports three modes:
1. STOCK FORECAST: Forecast stock/ETF prices using macro indicators as exogenous regressors
2. MACRO FORECAST: Forecast economic indicators themselves (CPI, rates, unemployment)
3. CORRELATION DISCOVERY: Find which indicators drive asset prices

Key Features:
- Dynamic indicator discovery based on correlation strength
- ARIMAX with configurable exogenous regressors
- Regime-aware analysis (expansion vs contraction)
- IV/sentiment integration from options market
- Comprehensive diagnostics and charts

Data Sources:
- EconomicDataServer: FRED API (interest rates, inflation, employment, GDP, etc.)
- UWMarketServer: Unusual Whales market sentiment and seasonality
- UWOptionsServer: IV rank, realized vol, options flow
- FMPMarketDataServer: Historical prices, fundamentals
"""

from agents import function_tool
from typing import List, Optional, Dict, Any, Tuple
import logging
import warnings
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Suppress sklearn/pmdarima warnings
warnings.filterwarnings("ignore", message=".*force_all_finite.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", message=".*stepwise model cannot be fit in parallel.*")

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# FREQUENCY DETECTION AND MINIMUM DATA REQUIREMENTS
# =============================================================================

def _detect_frequency(df: pd.DataFrame) -> str:
    """
    Detect data frequency from a DataFrame's index.
    Returns: 'daily', 'weekly', 'monthly', 'quarterly', or 'unknown'
    """
    if len(df) < 3:
        return "unknown"
    
    # Calculate median gap between observations
    gaps = df.index.to_series().diff().dropna()
    if len(gaps) == 0:
        return "unknown"
    
    median_gap = gaps.median().days
    
    if median_gap <= 2:
        return "daily"
    elif median_gap <= 10:
        return "weekly"
    elif median_gap <= 45:
        return "monthly"
    elif median_gap <= 120:
        return "quarterly"
    else:
        return "unknown"


def _get_min_data_points(frequency: str) -> int:
    """
    Get minimum data points required based on frequency.
    ARIMA needs enough data for estimation - adjust by frequency.
    """
    return {
        "daily": 100,      # ~4-5 months of trading days
        "weekly": 52,      # 1 year
        "monthly": 24,     # 2 years
        "quarterly": 12,   # 3 years
        "unknown": 30,     # Conservative fallback
    }.get(frequency, 30)


# =============================================================================
# DEFAULT SEARCH TERMS (for dynamic discovery via FRED search)
# =============================================================================

# These are SEARCH KEYWORDS, not hardcoded series IDs
# The tool uses EconomicDataServer.search_series() to find actual series
# More terms allowed since correlation filter picks the best
INDICATOR_SEARCH_TERMS = {
    "rates": ["federal funds rate", "10 year treasury", "2 year treasury", "30 year treasury"],
    "inflation": ["consumer price index", "PCE price index", "breakeven inflation", "producer price index"],
    "employment": ["unemployment rate", "initial claims", "nonfarm payrolls", "labor force participation"],
    "growth": ["real GDP", "industrial production", "retail sales", "capacity utilization"],
    "financial_conditions": ["VIX", "credit spread", "financial conditions index", "high yield spread"],
    "commodities": ["crude oil WTI", "gold price", "commodity index", "copper price"],
    "housing": ["housing starts", "existing home sales", "home price index", "mortgage rates"],
    "trade": ["trade balance", "imports", "exports", "dollar index"],
    "money_supply": ["M2 money supply", "monetary base", "bank credit"],
    "credit": ["consumer credit", "commercial paper", "corporate bonds", "credit card delinquency"],
}


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

async def _discover_indicators(
    econ_server: EconomicDataServer,
    search_terms: List[str],
    max_per_term: int = 3
) -> List[str]:
    """
    Dynamically discover FRED series IDs by searching keywords.
    Uses EconomicDataServer.search_series() - no hardcoded IDs.
    """
    discovered = []
    
    for term in search_terms:
        try:
            results = await econ_server.search_series(term, limit=max_per_term)
            for result in results:
                series_id = result.get("series_id")
                if series_id and series_id not in discovered:
                    discovered.append(series_id)
                    logger.info(f"[DISCOVER] Found '{series_id}' for search '{term}'")
        except Exception as e:
            logger.warning(f"[DISCOVER] Search failed for '{term}': {e}")
    
    return discovered


async def _fetch_fred_series(
    econ_server: EconomicDataServer,
    series_ids: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, pd.DataFrame]:
    """Fetch multiple FRED series and return as dict of DataFrames."""
    results = {}
    
    for series_id in series_ids:
        try:
            data = await econ_server.get_series_data(series_id, start_date, end_date)
            if data and "data" in data and len(data["data"]) > 0:
                df = pd.DataFrame(data["data"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                df.columns = [series_id]
                results[series_id] = df
                logger.info(f"[FRED] Fetched {series_id}: {len(df)} points")
        except Exception as e:
            logger.warning(f"[FRED] Failed to fetch {series_id}: {e}")
    
    return results


async def _fetch_uw_sentiment(
    options_server: UWOptionsServer,
    market_server: UWMarketServer,
    ticker: str
) -> Dict[str, Any]:
    """Fetch UW options sentiment data for a ticker."""
    sentiment = {}
    
    try:
        # IV Rank
        iv_result = await options_server.call_tool("uw_iv_rank", {"ticker": ticker})
        iv_data = safe_parse_json(iv_result)
        if iv_data and "data" in iv_data:
            sentiment["iv_rank"] = iv_data["data"]
            logger.info(f"[UW] Fetched IV rank for {ticker}")
    except Exception as e:
        logger.warning(f"[UW] IV rank failed for {ticker}: {e}")
    
    try:
        # Volatility stats (IV vs RV)
        vol_result = await options_server.call_tool("uw_volatility", {
            "ticker": ticker,
            "metric": "stats"
        })
        vol_data = safe_parse_json(vol_result)
        if vol_data and "data" in vol_data:
            sentiment["vol_stats"] = vol_data["data"]
            logger.info(f"[UW] Fetched vol stats for {ticker}")
    except Exception as e:
        logger.warning(f"[UW] Vol stats failed for {ticker}: {e}")
    
    try:
        # Put/Call data
        pc_result = await options_server.call_tool("uw_options_volume", {"ticker": ticker})
        pc_data = safe_parse_json(pc_result)
        if pc_data and "data" in pc_data:
            sentiment["options_volume"] = pc_data["data"]
            logger.info(f"[UW] Fetched options volume for {ticker}")
    except Exception as e:
        logger.warning(f"[UW] Options volume failed for {ticker}: {e}")
    
    return sentiment


async def _fetch_price_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    period: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Fetch price data from FMP."""
    result = await fmp_server.call_tool("get_historical_data", {
        "symbol": ticker,
        "period": period
    })
    
    if not result or not hasattr(result, "content"):
        raise ValueError(f"No data for {ticker}")
    
    data = safe_parse_json(result)
    if not data or "dates" not in data:
        raise ValueError(f"No date data for {ticker}")
    
    dates = data.get("dates", [])
    prices = data.get("prices", []) or data.get("closes", [])
    volumes = data.get("volumes", [])
    
    df = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "price": prices,
        "volume": volumes if volumes else [np.nan] * len(dates)
    })
    df = df.set_index("date").sort_index()
    
    return df, data


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def _align_series(
    target: pd.DataFrame,
    indicators: Dict[str, pd.DataFrame],
    min_overlap: int = 50
) -> Tuple[pd.DataFrame, List[str]]:
    """Align target series with indicator series on common dates."""
    # Start with target
    combined = target.copy()
    valid_indicators = []
    
    for name, df in indicators.items():
        # Merge on date index
        merged = combined.join(df, how="inner")
        
        # Check minimum overlap
        if len(merged) >= min_overlap:
            combined = merged
            valid_indicators.append(name)
        else:
            logger.warning(f"[ALIGN] Dropping {name}: only {len(merged)} overlapping points")
    
    # Forward fill any gaps (for different frequencies)
    combined = combined.ffill().dropna()
    
    logger.info(f"[ALIGN] Final dataset: {len(combined)} rows, {len(valid_indicators)} indicators")
    return combined, valid_indicators


def _compute_correlations(
    combined: pd.DataFrame,
    target_col: str,
    indicator_cols: List[str],
    lags: List[int] = [0, 1, 5, 10, 21]
) -> Dict[str, Dict[int, float]]:
    """Compute correlations between target and indicators at various lags."""
    correlations = {}
    target = combined[target_col]
    
    for col in indicator_cols:
        indicator = combined[col]
        correlations[col] = {}
        
        for lag in lags:
            if lag == 0:
                corr = target.corr(indicator)
            else:
                # Lag indicator (indicator leads target)
                corr = target.corr(indicator.shift(lag))
            
            if pd.notna(corr):
                correlations[col][lag] = round(corr, 4)
    
    return correlations


def _select_best_indicators(
    correlations: Dict[str, Dict[int, float]],
    max_indicators: int = 5,
    min_correlation: float = 0.25  # Match main function default
) -> List[Tuple[str, int, float]]:
    """Select indicators with strongest correlations."""
    all_corrs = []
    
    for indicator, lag_corrs in correlations.items():
        for lag, corr in lag_corrs.items():
            if abs(corr) >= min_correlation:
                all_corrs.append((indicator, lag, corr))
    
    # Sort by absolute correlation
    all_corrs.sort(key=lambda x: abs(x[2]), reverse=True)
    
    # Take top N, avoiding duplicate indicators
    selected = []
    seen_indicators = set()
    
    for indicator, lag, corr in all_corrs:
        if indicator not in seen_indicators and len(selected) < max_indicators:
            selected.append((indicator, lag, corr))
            seen_indicators.add(indicator)
    
    return selected


def _fit_arimax(
    target: np.ndarray,
    exog: Optional[np.ndarray],
    forecast_periods: int,
    exog_forecast: Optional[np.ndarray],
    max_p: int = 10,
    max_q: int = 10,
    max_d: int = 2,
    seasonal: bool = True,
    seasonal_period: int = 5,
    stepwise: bool = True,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """Fit ARIMAX model and generate forecast."""
    from pmdarima import auto_arima
    
    # Use log transform for price data
    use_log = np.all(target > 0)
    if use_log:
        target_transformed = np.log(target)
    else:
        target_transformed = target
    
    # Build auto_arima kwargs
    kwargs = {
        'start_p': 1,
        'start_q': 1,
        'max_p': max_p,
        'max_q': max_q,
        'max_d': max_d,
        'seasonal': seasonal,
        'stepwise': stepwise,
        'suppress_warnings': True,
        'error_action': 'ignore',
        'information_criterion': 'aic',
        'n_jobs': -1
    }
    
    if seasonal:
        kwargs['m'] = seasonal_period
        kwargs['max_P'] = 2
        kwargs['max_Q'] = 2
        kwargs['max_D'] = 1
    
    # Add exogenous variables if provided and valid
    has_exog = exog is not None and exog.shape[1] > 0
    if has_exog:
        kwargs['X'] = exog
        logger.info(f"[ARIMAX] Fitting with {exog.shape[1]} exogenous variables")
    else:
        logger.info("[ARIMA] Fitting pure ARIMA (no valid exogenous variables)")
    
    # Fit model
    model = auto_arima(target_transformed, **kwargs)
    
    # In-sample fit (must pass X if model was fit with X)
    if has_exog:
        fitted_transformed = model.predict_in_sample(X=exog)
    else:
        fitted_transformed = model.predict_in_sample()
    
    # Forecast
    if has_exog and exog_forecast is not None and len(exog_forecast) > 0:
        forecast_transformed, conf_int = model.predict(
            n_periods=forecast_periods,
            X=exog_forecast,
            return_conf_int=True,
            alpha=1 - confidence_level
        )
    else:
        forecast_transformed, conf_int = model.predict(
            n_periods=forecast_periods,
            return_conf_int=True,
            alpha=1 - confidence_level
        )
    
    # Transform back
    if use_log:
        fitted = np.exp(fitted_transformed)
        forecast = np.exp(forecast_transformed)
        conf_lower = np.exp(conf_int[:, 0])
        conf_upper = np.exp(conf_int[:, 1])
    else:
        fitted = fitted_transformed
        forecast = forecast_transformed
        conf_lower = conf_int[:, 0]
        conf_upper = conf_int[:, 1]
    
    # Diagnostics
    residuals = target - fitted
    
    return {
        "fitted": fitted,
        "forecast": forecast,
        "conf_lower": conf_lower,
        "conf_upper": conf_upper,
        "residuals": residuals,
        "order": model.order,
        "seasonal_order": getattr(model, 'seasonal_order', None),
        "aic": model.aic(),
        "bic": model.bic(),
        "use_log": use_log
    }


# =============================================================================
# CHART BUILDING
# =============================================================================

async def _build_forecast_chart(
    ticker: str,
    dates: pd.DatetimeIndex,
    prices: np.ndarray,
    fitted: np.ndarray,
    forecast_dates: List[str],
    forecast: np.ndarray,
    conf_lower: np.ndarray,
    conf_upper: np.ndarray,
    selected_indicators: List[Tuple[str, int, float]],
    confidence_level: float
) -> Dict[str, Any]:
    """Build forecast chart with price history, forecast, and indicator correlations."""
    try:
        # Subsample if too many points
        max_points = 200
        if len(dates) > max_points:
            stride = len(dates) // max_points
            plot_dates = dates[::stride]
            plot_prices = prices[::stride]
            plot_fitted = fitted[::stride]
        else:
            plot_dates = dates
            plot_prices = prices
            plot_fitted = fitted
        
        # Key values
        current_price = float(prices[-1])
        forecast_end = float(forecast[-1])
        pct_change = ((forecast_end / current_price) - 1) * 100
        conf_pct = int(confidence_level * 100)
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=[
                f"<b>{ticker}</b> — ARIMAX Forecast",
                f"<b>Indicator Correlations</b>"
            ],
            vertical_spacing=0.14,
            row_heights=[0.7, 0.3]
        )
        
        # --- TOP PANEL: Price & Forecast ---
        
        # Historical prices
        fig.add_trace(go.Scatter(
            x=plot_dates, y=plot_prices,
            mode='lines', name='Historical',
            line=dict(color='#1E3A5F', width=2),
            hovertemplate='%{x|%b %d}<br>$%{y:,.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Model fit (subtle)
        fig.add_trace(go.Scatter(
            x=plot_dates, y=plot_fitted,
            mode='lines', name='Model Fit',
            line=dict(color='#3D8B7A', width=1.2, dash='dash'),
            opacity=0.6,
            hovertemplate='%{x|%b %d}<br>Fit: $%{y:,.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Confidence band (filled area)
        fig.add_trace(go.Scatter(
            x=forecast_dates + forecast_dates[::-1],
            y=list(conf_upper) + list(conf_lower)[::-1],
            fill='toself',
            fillcolor='rgba(232, 93, 4, 0.15)',
            line=dict(color='rgba(0,0,0,0)'),
            name=f'{conf_pct}% CI',
            hoverinfo='skip'
        ), row=1, col=1)
        
        # Forecast line
        fig.add_trace(go.Scatter(
            x=forecast_dates, y=forecast,
            mode='lines', name='Forecast',
            line=dict(color='#E85D04', width=2.5),
            hovertemplate='%{x|%b %d}<br>Forecast: $%{y:,.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Divider line between historical and forecast
        fig.add_vline(
            x=str(plot_dates[-1]),
            line=dict(color='#94A3B8', width=1, dash='dash'),
            row=1, col=1
        )
        
        # Forecast endpoint annotation
        direction = "▲" if pct_change > 0 else "▼"
        color = "#22763F" if pct_change > 0 else "#B91C1C"
        fig.add_annotation(
            x=forecast_dates[-1], y=forecast_end,
            text=f"<b>{direction} {abs(pct_change):.1f}%</b>",
            showarrow=True, arrowhead=2, arrowcolor=color,
            ax=40, ay=-20,
            font=dict(size=11, color=color),
            bgcolor='white', bordercolor=color, borderwidth=1,
            row=1, col=1
        )
        
        # --- BOTTOM PANEL: Correlations ---
        
        if selected_indicators:
            names = [f"{ind[0][:15]}{'…' if len(ind[0])>15 else ''}" for ind in selected_indicators]
            corrs = [ind[2] for ind in selected_indicators]
            colors = ['#22763F' if c > 0 else '#B91C1C' for c in corrs]
            
            fig.add_trace(go.Bar(
                x=names, y=corrs,
                marker_color=colors,
                text=[f"{c:+.2f}" for c in corrs],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='%{x}<br>ρ = %{y:+.3f}<extra></extra>',
                showlegend=False
            ), row=2, col=1)
            
            fig.add_hline(y=0, line=dict(color='#94A3B8', width=1), row=2, col=1)
        
        # Layout
        fig.update_layout(
            template='plotly_white',
            height=680,
            hovermode='x unified',
            legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center'),
            margin=dict(l=60, r=30, t=80, b=40)
        )
        
        fig.update_yaxes(title_text='Price', tickprefix='$', row=1, col=1)
        fig.update_yaxes(title_text='Correlation', range=[-1.1, 1.1], row=2, col=1)
        fig.update_xaxes(tickangle=-30, row=2, col=1)
        
        return {
            'id': f"arimax_forecast_{ticker.lower()}",
            'title': f"ARIMAX Macro Forecast — {ticker}",
            'plotly': fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        return None


async def _build_macro_dashboard(
    indicator_data: Dict[str, pd.DataFrame],
    correlations: Dict[str, Dict[int, float]],
    ticker: str
) -> Dict[str, Any]:
    """Build dashboard showing macro indicator time series with correlations."""
    try:
        n_indicators = min(6, len(indicator_data))
        if n_indicators == 0:
            return None
        
        # Build titles with correlation values
        indicator_names = list(indicator_data.keys())[:n_indicators]
        subplot_titles = []
        for name in indicator_names:
            best_corr = 0
            if name in correlations:
                best_corr = max(correlations[name].values(), key=abs, default=0)
            short_name = name[:22] + '…' if len(name) > 22 else name
            subplot_titles.append(f"{short_name} (ρ={best_corr:+.2f})")
        
        rows = (n_indicators + 1) // 2
        fig = make_subplots(
            rows=rows, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        colors = ['#1E3A5F', '#E85D04', '#3D8B7A', '#9333EA', '#0891B2', '#B91C1C']
        
        for idx, (name, df) in enumerate(list(indicator_data.items())[:n_indicators]):
            row, col = idx // 2 + 1, idx % 2 + 1
            color = colors[idx % len(colors)]
            
            # Subsample
            plot_df = df.iloc[::max(1, len(df)//100)] if len(df) > 100 else df
            
            fig.add_trace(go.Scatter(
                x=plot_df.index,
                y=plot_df[name],
                mode='lines',
                line=dict(color=color, width=1.5),
                showlegend=False,
                hovertemplate='%{x|%b %Y}<br>%{y:,.2f}<extra></extra>'
            ), row=row, col=col)
        
        fig.update_layout(
            title=f"<b>Macro Indicators</b> — {ticker}",
            template='plotly_white',
            height=250 * rows + 50,
            margin=dict(l=50, r=30, t=70, b=40)
        )
        
        return {
            'id': f"macro_dashboard_{ticker.lower()}",
            'title': f"Macro Indicators — {ticker}",
            'plotly': fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Macro dashboard failed: {e}")
        return None


# =============================================================================
# MAIN TOOL
# =============================================================================

async def forecast_arimax_macro_internal(
    # Target specification
    ticker: Optional[str] = None,
    fred_series: Optional[str] = None,
    
    # Forecast parameters
    forecast_periods: int = 30,
    period: str = "3Y",  # Default 3Y for monthly macro data (36 points minimum)
    confidence_level: float = 0.95,
    
    # Indicator selection (discovery-based)
    indicator_categories: Optional[List[str]] = None,
    custom_search_terms: Optional[List[str]] = None,
    custom_series_ids: Optional[List[str]] = None,
    auto_select_indicators: bool = True,
    max_indicators: int = 5,  # Reasonable limit, correlation filter handles quality
    min_correlation: float = 0.25,  # Higher threshold = quality over quantity
    max_series_per_search: int = 1,  # Just get best match per search
    
    # Model parameters
    max_p: int = 10,
    max_q: int = 10,
    max_d: int = 2,
    seasonal: bool = True,
    seasonal_period: int = 5,
    stepwise: bool = True,
    
    # UW sentiment integration
    include_uw_sentiment: bool = True,
    
    # Output options
    include_macro_dashboard: bool = True,
    include_correlation_analysis: bool = True
) -> dict:
    """
    Multi-factor ARIMAX forecasting with macroeconomic indicators.
    
    A power tool combining FRED economic data, Unusual Whales options sentiment,
    and FMP market data for comprehensive macro-driven forecasting.
    
    MODES:
    ------
    1. STOCK/ETF FORECAST: Set `ticker` to forecast asset prices with macro regressors
       Example: forecast_arimax_macro(ticker="SPY", indicator_presets=["rates", "inflation"])
       
    2. MACRO INDICATOR FORECAST: Set `fred_series` to forecast an economic indicator
       Example: forecast_arimax_macro(fred_series="CPIAUCSL")  # Forecast inflation
       Example: forecast_arimax_macro(fred_series="DGS10")     # Forecast 10Y rate
    
    INDICATOR CATEGORIES (discovery-based):
    ---------------------------------------
    - "rates": Searches for treasury rates, fed funds, yield curve
    - "inflation": Searches for CPI, PCE, breakeven inflation
    - "employment": Searches for unemployment, payrolls, jobless claims
    - "growth": Searches for GDP, industrial production, retail sales
    - "financial_conditions": Searches for VIX, credit spreads, financial stress
    - "commodities": Searches for oil, gold, commodity indices
    
    All indicators are discovered dynamically via FRED search - NO hardcoded series IDs.
    
    Args:
        ticker: Stock/ETF symbol to forecast (e.g., "SPY", "QQQ", "TLT")
        fred_series: FRED series ID to forecast directly (e.g., "CPIAUCSL", "DGS10")
        
        forecast_periods: Days ahead to forecast (default: 30)
        period: Historical data period - "1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y" (default: "3Y")
                Use longer periods (3Y+) for monthly macro data like CPI, unemployment.
        confidence_level: CI level (default: 0.95 for 95%)
        
        indicator_categories: List of category names to search for indicators
                             Options: "rates", "inflation", "employment", "growth",
                                      "financial_conditions", "commodities"
        custom_search_terms: List of custom FRED search terms (e.g., ["housing starts", "consumer confidence"])
        custom_series_ids: List of specific FRED series IDs if you know them (bypasses search)
        auto_select_indicators: Automatically select best indicators by correlation
        max_indicators: Max exogenous variables in model (default: 5)
        min_correlation: Minimum |correlation| to consider indicator (default: 0.25, filters low-quality)
        max_series_per_search: Max series to fetch per search term (default: 1)
        
        max_p, max_q, max_d: ARIMA order limits
        seasonal: Enable seasonal components (default: True)
        seasonal_period: Seasonality period in days (default: 5)
        stepwise: Use stepwise search (default: True, faster)
        
        include_uw_sentiment: Include Unusual Whales IV/sentiment data
        include_macro_dashboard: Generate macro indicators dashboard chart
        include_correlation_analysis: Include detailed correlation analysis
    
    Returns:
        Dict with forecast, model diagnostics, correlations, and charts
    
    Examples:
        # Forecast SPY with rate and inflation indicators (discovered via search)
        await forecast_arimax_macro(
            ticker="SPY",
            indicator_categories=["rates", "inflation"],
            forecast_periods=30
        )
        
        # Forecast 10-Year Treasury rate
        await forecast_arimax_macro(
            fred_series="DGS10",
            indicator_categories=["inflation", "growth"],
            forecast_periods=60
        )
        
        # Custom search terms (finds relevant series dynamically)
        await forecast_arimax_macro(
            ticker="XLF",
            custom_search_terms=["bank lending", "credit card delinquency", "mortgage rates"]
        )
        
        # If you know exact series IDs, bypass search
        await forecast_arimax_macro(
            ticker="TLT",
            custom_series_ids=["DGS10", "CPIAUCSL", "UNRATE"],
            auto_select_indicators=False
        )
    """
    
    # Server instances
    fmp_server = None
    econ_server = None
    uw_options = None
    uw_market = None
    
    try:
        # Validate inputs
        if not ticker and not fred_series:
            raise ValueError("Must specify either `ticker` (stock/ETF) or `fred_series` (FRED indicator)")
        
        if ticker and fred_series:
            raise ValueError("Specify only one of `ticker` or `fred_series`, not both")
        
        # Initialize servers
        logger.info("[ARIMAX] Initializing data servers...")
        
        try:
            econ_server = EconomicDataServer()
            await econ_server.connect()
        except Exception as e:
            logger.warning(f"EconomicDataServer init failed: {e}")
            econ_server = None
        
        if ticker:
            fmp_server = FMPMarketDataServer()
            await fmp_server.connect()
            
            if include_uw_sentiment:
                try:
                    uw_options = UWOptionsServer()
                    uw_market = UWMarketServer()
                    await uw_options.connect()
                    await uw_market.connect()
                except Exception as e:
                    logger.warning(f"UW servers init failed: {e}")
        
        # Calculate date range
        end_date = datetime.now()
        period_days = {
            "1M": 30, "3M": 90, "6M": 180,
            "1Y": 365, "2Y": 730, "3Y": 1095, "5Y": 1825,
            # Lowercase variants for compatibility
            "1m": 30, "3m": 90, "6m": 180,
            "1y": 365, "2y": 730, "3y": 1095, "5y": 1825
        }
        start_date = end_date - timedelta(days=period_days.get(period, 1095))  # Default 3Y
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"[ARIMAX] Period parameter: '{period}', Date range: {start_str} to {end_str}")
        
        # =====================================================================
        # FETCH TARGET DATA
        # =====================================================================
        
        if ticker:
            # Mode 1: Stock/ETF forecast
            logger.info(f"[ARIMAX] Fetching price data for {ticker} with period={period}...")
            # Convert period to lowercase for FMP compatibility (e.g., "3Y" -> "3y")
            fmp_period = period.lower()
            price_df, raw_data = await _fetch_price_data(fmp_server, ticker, fmp_period)
            target_df = price_df[["price"]].rename(columns={"price": "target"})
            target_name = ticker
            
            # Fetch UW sentiment
            uw_sentiment = {}
            if include_uw_sentiment and uw_options:
                uw_sentiment = await _fetch_uw_sentiment(uw_options, uw_market, ticker)
        
        else:
            # Mode 2: FRED series forecast
            logger.info(f"[ARIMAX] Fetching FRED series {fred_series}...")
            series_data = await _fetch_fred_series(econ_server, [fred_series], start_str, end_str)
            
            if fred_series not in series_data:
                raise ValueError(f"Could not fetch FRED series {fred_series}")
            
            target_df = series_data[fred_series].rename(columns={fred_series: "target"})
            target_name = fred_series
            uw_sentiment = {}
        
        # Detect frequency and check minimum data requirements
        frequency = _detect_frequency(target_df)
        min_points = _get_min_data_points(frequency)
        
        if len(target_df) < min_points:
            raise ValueError(
                f"Insufficient data: {len(target_df)} {frequency} points (need {min_points}+). "
                f"Try increasing the 'period' parameter (e.g., '3Y' or '5Y')."
            )
        
        # =====================================================================
        # DISCOVER AND FETCH INDICATOR DATA (Dynamic - no hardcoded IDs)
        # =====================================================================
        
        search_terms = []
        indicator_series = []
        
        # Build search terms from categories
        if indicator_categories:
            for category in indicator_categories:
                if category in INDICATOR_SEARCH_TERMS:
                    search_terms.extend(INDICATOR_SEARCH_TERMS[category])
                else:
                    # Unknown category - use it as a search term directly
                    search_terms.append(category)
        
        # Add custom search terms
        if custom_search_terms:
            search_terms.extend(custom_search_terms)
        
        # Default: just 2 key indicators if nothing specified (quality over quantity)
        if not search_terms and not custom_series_ids and econ_server:
            search_terms = ["federal funds rate", "consumer price index"]
        
        # Discover series via FRED search
        if econ_server and search_terms:
            logger.info(f"[ARIMAX] Discovering indicators via FRED search: {search_terms}")
            indicator_series = await _discover_indicators(
                econ_server, 
                search_terms, 
                max_per_term=max_series_per_search
            )
        
        # Add any directly-specified series IDs (bypass search)
        if custom_series_ids:
            indicator_series.extend(custom_series_ids)
        
        # Remove duplicates and target series
        indicator_series = list(dict.fromkeys(indicator_series))  # Preserve order, remove dupes
        if fred_series and fred_series in indicator_series:
            indicator_series.remove(fred_series)
        
        # Fetch indicator data
        indicator_data = {}
        if econ_server and indicator_series:
            logger.info(f"[ARIMAX] Fetching {len(indicator_series)} discovered FRED indicators...")
            indicator_data = await _fetch_fred_series(econ_server, indicator_series, start_str, end_str)
        
        # =====================================================================
        # ALIGN AND ANALYZE DATA
        # =====================================================================
        
        # Align all series
        combined_df, valid_indicators = _align_series(target_df, indicator_data)
        
        # Check minimum after alignment (more lenient - we've already validated raw data)
        min_aligned = max(min_points // 2, 20)  # At least half of min or 20
        if len(combined_df) < min_aligned:
            raise ValueError(
                f"Insufficient overlapping data: {len(combined_df)} points after alignment (need {min_aligned}+). "
                f"Some indicators may have different frequencies or date ranges."
            )
        
        # Compute correlations
        correlations = {}
        if valid_indicators:
            correlations = _compute_correlations(
                combined_df, 
                "target", 
                valid_indicators,
                lags=[0, 1, 5, 10, 21]
            )
        
        # Select best indicators
        selected_indicators = []
        if auto_select_indicators and correlations:
            selected_indicators = _select_best_indicators(
                correlations,
                max_indicators=max_indicators,
                min_correlation=min_correlation
            )
            logger.info(f"[ARIMAX] Auto-selected {len(selected_indicators)} indicators")
        elif not auto_select_indicators and valid_indicators:
            # Use all valid indicators up to max
            for ind in valid_indicators[:max_indicators]:
                best_corr = max(correlations.get(ind, {0: 0}).values(), key=abs, default=0)
                selected_indicators.append((ind, 0, best_corr))
        
        # =====================================================================
        # BUILD EXOGENOUS MATRIX (graceful fallback to pure ARIMA)
        # =====================================================================
        
        exog = None
        exog_forecast = None
        
        if selected_indicators:
            exog_cols = []
            for ind, lag, _ in selected_indicators:
                if ind in combined_df.columns:
                    if lag > 0:
                        exog_cols.append(combined_df[ind].shift(lag))
                    else:
                        exog_cols.append(combined_df[ind])
            
            if exog_cols:
                try:
                    exog_df = pd.concat(exog_cols, axis=1).dropna()
                    if len(exog_df) >= 20:  # Need enough aligned data
                        exog = exog_df.values
                        
                        # For forecast, assume indicators stay at last value (naive)
                        last_values = exog[-1:, :]
                        exog_forecast = np.repeat(last_values, forecast_periods, axis=0)
                        
                        # Trim target to match exog
                        combined_df = combined_df.loc[exog_df.index]
                    else:
                        logger.warning(f"[ARIMAX] Only {len(exog_df)} aligned points - falling back to pure ARIMA")
                        exog = None
                        exog_forecast = None
                except Exception as e:
                    logger.warning(f"[ARIMAX] Failed to build exog matrix: {e} - falling back to pure ARIMA")
                    exog = None
                    exog_forecast = None
        
        # =====================================================================
        # FIT MODEL (ARIMAX if exog available, else pure ARIMA)
        # =====================================================================
        
        model_type = "ARIMAX" if exog is not None else "ARIMA"
        n_exog = exog.shape[1] if exog is not None else 0
        logger.info(f"[{model_type}] Fitting model with {n_exog} exogenous variables...")
        
        target_values = combined_df["target"].values
        
        model_result = _fit_arimax(
            target=target_values,
            exog=exog,
            forecast_periods=forecast_periods,
            exog_forecast=exog_forecast,
            max_p=max_p,
            max_q=max_q,
            max_d=max_d,
            seasonal=seasonal,
            seasonal_period=seasonal_period,
            stepwise=stepwise,
            confidence_level=confidence_level
        )
        
        # Generate forecast dates
        last_date = combined_df.index[-1]
        forecast_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=forecast_periods,
            freq='D'
        )
        forecast_dates_str = forecast_dates.strftime('%Y-%m-%d').tolist()
        
        # =====================================================================
        # COMPUTE DIAGNOSTICS
        # =====================================================================
        
        residuals = model_result["residuals"]
        fitted = model_result["fitted"]
        
        # R-squared
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((target_values - np.mean(target_values))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # MAPE
        mape = np.mean(np.abs(residuals / target_values)) * 100 if np.all(target_values != 0) else 0
        
        # Forecast change
        forecast_end = model_result["forecast"][-1]
        forecast_change_pct = (forecast_end / target_values[-1] - 1) * 100
        
        diagnostics = {
            "order": model_result["order"],
            "seasonal_order": model_result["seasonal_order"],
            "aic": float(model_result["aic"]),
            "bic": float(model_result["bic"]),
            "r_squared": float(r_squared),
            "mape": float(mape),
            "use_log_transform": model_result["use_log"],
            "exogenous_variables": len(selected_indicators),
            "training_points": len(target_values),
            "selected_indicators": [
                {"series": ind, "lag": lag, "correlation": corr}
                for ind, lag, corr in selected_indicators
            ]
        }
        
        # =====================================================================
        # BUILD CHARTS
        # =====================================================================
        
        all_charts = []
        
        # Main forecast chart
        forecast_chart = await _build_forecast_chart(
            ticker=target_name,
            dates=combined_df.index,
            prices=target_values,
            fitted=fitted,
            forecast_dates=forecast_dates_str,
            forecast=model_result["forecast"],
            conf_lower=model_result["conf_lower"],
            conf_upper=model_result["conf_upper"],
            selected_indicators=selected_indicators,
            confidence_level=confidence_level
        )
        if forecast_chart:
            all_charts.append(forecast_chart)
        
        # Macro dashboard
        if include_macro_dashboard and indicator_data:
            macro_chart = await _build_macro_dashboard(
                indicator_data=indicator_data,
                correlations=correlations,
                ticker=target_name
            )
            if macro_chart:
                all_charts.append(macro_chart)
        
        # =====================================================================
        # BUILD RESPONSE
        # =====================================================================
        
        response = {
            "status": "success",
            "target": target_name,
            "mode": "stock_forecast" if ticker else "macro_forecast",
            "timestamp": datetime.now().isoformat(),
            
            # Omit large time series arrays (embedded in cached charts)
            "forecast": {
                "start_date": forecast_dates_str[0] if forecast_dates_str else None,
                "end_date": forecast_dates_str[-1] if forecast_dates_str else None,
                "periods": len(forecast_dates_str),
                # Removed: dates/values/lower/upper arrays (embedded in charts)
                "confidence_interval_level": confidence_level,
                "final_forecast_range": {
                    "lower": float(model_result["conf_lower"][-1]),
                    "upper": float(model_result["conf_upper"][-1])
                }
            },
            
            "historical": {
                "start_date": combined_df.index[0].strftime('%Y-%m-%d'),
                "end_date": combined_df.index[-1].strftime('%Y-%m-%d'),
                "n_observations": len(target_values),
                # Removed: dates/values/fitted arrays (embedded in charts)
            },
            
            "summary": {
                "last_value": float(target_values[-1]),
                "forecast_end_value": float(forecast_end),
                "forecast_change_pct": float(forecast_change_pct),
                "forecast_direction": "UP" if forecast_change_pct > 0 else "DOWN",
                "r_squared": float(r_squared),
                "mape": float(mape)
            },
            
            "diagnostics": diagnostics,
            
            "data_sources": {
                "target_points": len(target_values),
                "indicators_fetched": len(indicator_data),
                "indicators_used": len(selected_indicators),
                "uw_sentiment_included": bool(uw_sentiment)
            },
            
            "charts": wrap_plotly_charts(all_charts, default_type="arimax_macro_chart")
        }
        
        # Add correlation analysis
        if include_correlation_analysis and correlations:
            response["correlation_analysis"] = {
                "method": "Pearson correlation at multiple lags",
                "lags_tested": [0, 1, 5, 10, 21],
                "results": correlations,
                "interpretation": (
                    "Positive correlation: indicator and target move together. "
                    "Negative correlation: they move opposite. "
                    "Lag > 0 means indicator leads target by N days."
                )
            }
        
        # Add UW sentiment if available
        if uw_sentiment:
            response["uw_sentiment"] = uw_sentiment
        
        # Add available categories and search terms for reference
        response["available_categories"] = {
            category: terms
            for category, terms in INDICATOR_SEARCH_TERMS.items()
        }
        response["discovered_series"] = indicator_series
        
        return response
    
    except Exception as e:
        logger.error(f"ARIMAX macro forecast failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "arimax_macro_forecast"
        }
    
    finally:
        # Cleanup all servers
        for server in [fmp_server, econ_server, uw_options, uw_market]:
            if server:
                try:
                    await server.cleanup()
                except Exception as e:
                    logger.warning(f"Server cleanup failed: {e}")


@function_tool
async def forecast_arimax_macro(
    # Target specification
    ticker: Optional[str] = None,
    fred_series: Optional[str] = None,
    
    # Forecast parameters
    forecast_periods: int = 30,
    period: str = "3Y",
    confidence_level: float = 0.95,
    
    # Indicator selection (discovery-based)
    indicator_categories: Optional[List[str]] = None,
    custom_search_terms: Optional[List[str]] = None,
    custom_series_ids: Optional[List[str]] = None,
    auto_select_indicators: bool = True,
    max_indicators: int = 5,
    min_correlation: float = 0.25,
    max_series_per_search: int = 1,
    
    # Model parameters
    max_p: int = 10,
    max_q: int = 10,
    max_d: int = 2,
    seasonal: bool = True,
    seasonal_period: int = 5,
    stepwise: bool = True,
    
    # UW sentiment integration
    include_uw_sentiment: bool = True,
    
    # Output options
    include_macro_dashboard: bool = True,
    include_correlation_analysis: bool = True
) -> str:
    """
    Multi-factor ARIMAX forecasting with macroeconomic indicators.
    
    See forecast_arimax_macro_internal() for full documentation.
    """
    result = await forecast_arimax_macro_internal(
        ticker=ticker,
        fred_series=fred_series,
        forecast_periods=forecast_periods,
        period=period,
        confidence_level=confidence_level,
        indicator_categories=indicator_categories,
        custom_search_terms=custom_search_terms,
        custom_series_ids=custom_series_ids,
        auto_select_indicators=auto_select_indicators,
        max_indicators=max_indicators,
        min_correlation=min_correlation,
        max_series_per_search=max_series_per_search,
        max_p=max_p,
        max_q=max_q,
        max_d=max_d,
        seasonal=seasonal,
        seasonal_period=seasonal_period,
        stepwise=stepwise,
        include_uw_sentiment=include_uw_sentiment,
        include_macro_dashboard=include_macro_dashboard,
        include_correlation_analysis=include_correlation_analysis
    )
    return jsonify_results(result)

