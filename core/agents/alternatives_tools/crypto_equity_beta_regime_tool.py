"""
Crypto-Equity Beta Regime Tool

Detects when BTC/ETH correlates with risk-on assets (SPY/QQQ) vs. decoupling.
Provides regime classification and trading signals for crypto-equity correlation.

NO HARDCODING: Uses dynamic field discovery for market data.
"""

import asyncio
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging

# Agent framework
from agents import function_tool

# Internal utilities
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


def _check_cancellation(context: str = ""):
    """Check if cancellation was requested and raise CancelledError if so."""
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CANCEL] crypto_equity_beta cancelled{' during ' + context if context else ''}")
        raise asyncio.CancelledError(f"crypto_equity_beta cancelled{' during ' + context if context else ''}")


def _discover_price_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the price field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing price data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    # Priority order for price-related keys (case-insensitive search)
    price_indicators = ['close', 'price', 'adj_close', 'adjusted']

    available_keys = list(data.keys())

    # Search for price-related keys
    for indicator in price_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key

    return None


def _discover_date_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the date field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing date data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    date_indicators = ['date', 'time', 'timestamp']
    available_keys = list(data.keys())

    for indicator in date_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key

    return None


async def _fetch_equity_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int
) -> pd.DataFrame:
    """
    Fetch historical equity price data from FMP.

    Args:
        fmp_server: Connected FMP market data server
        ticker: Stock symbol (SPY, QQQ, etc.)
        lookback_days: Days of historical data

    Returns:
        DataFrame with date and price columns
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    result = await fmp_server.call_tool("get_historical_data", {
        "symbol": ticker,
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    })

    if not result or not hasattr(result, 'content'):
        raise ValueError(f"No data returned for {ticker}")

    data = safe_parse_json(result)

    if not data or not isinstance(data, dict):
        raise ValueError(f"Invalid data structure for {ticker}")

    date_field = _discover_date_field(data)
    price_field = _discover_price_field(data)

    if not date_field:
        raise ValueError(f"No date field found for {ticker}. Keys: {list(data.keys())}")
    if not price_field:
        raise ValueError(f"No price field found for {ticker}. Keys: {list(data.keys())}")

    dates = data[date_field]
    prices = data[price_field]

    if len(dates) != len(prices):
        raise ValueError(f"Date/price length mismatch for {ticker}")

    df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'price': pd.to_numeric(prices, errors='coerce')
    })

    df = df.sort_values('date').reset_index(drop=True)
    df = df.dropna()

    return df


async def _fetch_crypto_data(
    alternatives_server: FMPAlternativesServer,
    symbol: str,
    lookback_days: int
) -> pd.DataFrame:
    """
    Fetch historical crypto price data from FMP Alternatives.

    Args:
        alternatives_server: Connected FMP alternatives server
        symbol: Crypto symbol (BTCUSD, ETHUSD, etc.)
        lookback_days: Days of historical data

    Returns:
        DataFrame with date and price columns
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    result = await alternatives_server.call_tool("get_crypto_historical", {
        "symbol": symbol,
        "timeframe": "1hour",  # Use hourly for better granularity, will resample to daily
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d")
    })

    if not result or not hasattr(result, 'content'):
        raise ValueError(f"No data returned for {symbol}")

    data = safe_parse_json(result)

    if not data:
        raise ValueError(f"Invalid data structure for {symbol}")

    # Handle nested response structure
    historical_data = data.get('historical_data', data)

    if isinstance(historical_data, list) and len(historical_data) > 0:
        # List of OHLCV bars
        df = pd.DataFrame(historical_data)

        # Discover date and price fields dynamically
        date_col = None
        price_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'date' in col_lower or 'time' in col_lower:
                date_col = col
            if col_lower == 'close' or (price_col is None and 'price' in col_lower):
                price_col = col

        if not date_col or not price_col:
            raise ValueError(f"Could not find date/price columns for {symbol}. Columns: {list(df.columns)}")

        df['date'] = pd.to_datetime(df[date_col])
        df['price'] = pd.to_numeric(df[price_col], errors='coerce')
        df = df[['date', 'price']].dropna()

        # Resample to daily (take last price of each day)
        df = df.set_index('date')
        df = df.resample('D').last().dropna().reset_index()

    elif isinstance(historical_data, dict):
        date_field = _discover_date_field(historical_data)
        price_field = _discover_price_field(historical_data)

        if not date_field or not price_field:
            raise ValueError(f"Could not find date/price fields for {symbol}")

        df = pd.DataFrame({
            'date': pd.to_datetime(historical_data[date_field]),
            'price': pd.to_numeric(historical_data[price_field], errors='coerce')
        })
        df = df.dropna()
    else:
        raise ValueError(f"Unexpected data format for {symbol}")

    df = df.sort_values('date').reset_index(drop=True)

    return df


def _calculate_rolling_beta(
    crypto_returns: pd.Series,
    equity_returns: pd.Series,
    window: int
) -> pd.Series:
    """
    Calculate rolling beta of crypto vs equity.

    Beta = Cov(crypto, equity) / Var(equity)

    Args:
        crypto_returns: Crypto return series
        equity_returns: Equity return series
        window: Rolling window size

    Returns:
        Rolling beta series
    """
    # Align series
    aligned = pd.DataFrame({
        'crypto': crypto_returns,
        'equity': equity_returns
    }).dropna()

    if len(aligned) < window:
        return pd.Series(dtype=float)

    # Rolling covariance and variance
    rolling_cov = aligned['crypto'].rolling(window).cov(aligned['equity'])
    rolling_var = aligned['equity'].rolling(window).var()

    # Beta = Cov / Var
    beta = rolling_cov / rolling_var

    return beta


def _calculate_rolling_correlation(
    series1: pd.Series,
    series2: pd.Series,
    window: int
) -> pd.Series:
    """
    Calculate rolling correlation between two series.

    Args:
        series1: First return series
        series2: Second return series
        window: Rolling window size

    Returns:
        Rolling correlation series
    """
    aligned = pd.DataFrame({
        'a': series1,
        'b': series2
    }).dropna()

    if len(aligned) < window:
        return pd.Series(dtype=float)

    return aligned['a'].rolling(window).corr(aligned['b'])


def _classify_regime(
    current_beta: float,
    current_corr: float,
    beta_history: pd.Series,
    corr_history: pd.Series,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5
) -> Dict[str, Any]:
    """
    Classify the current crypto-equity regime using z-score based thresholds.

    **Z-Score Based Classification (No Hardcoded Values):**
    - RISK_ON: Correlation z-score > high_z_threshold (unusually high correlation)
    - RISK_OFF: Correlation z-score < low_z_threshold (unusually negative correlation)
    - DECOUPLED: |Correlation z-score| < neutral_z_band (near historical mean)
    - MODERATE_RISK_ON/OFF: Between neutral and extreme thresholds

    This approach adapts to the asset pair's historical behavior rather than
    assuming fixed correlation thresholds that may not apply across all periods.

    Args:
        current_beta: Current rolling beta
        current_corr: Current rolling correlation
        beta_history: Historical beta series
        corr_history: Historical correlation series
        high_z_threshold: Z-score threshold for RISK_ON classification (default: 1.5)
        low_z_threshold: Z-score threshold for RISK_OFF classification (default: -1.5)
        neutral_z_band: Z-score band around mean for DECOUPLED (default: 0.5)

    Returns:
        Regime classification with z-score based metrics
    """
    # Calculate z-scores - the PRIMARY classification metric
    beta_mean = beta_history.mean()
    beta_std = beta_history.std()
    corr_mean = corr_history.mean()
    corr_std = corr_history.std()

    # Protect against zero std (constant series)
    beta_z = (current_beta - beta_mean) / beta_std if beta_std > 1e-8 else 0
    corr_z = (current_corr - corr_mean) / corr_std if corr_std > 1e-8 else 0

    # Percentile ranks for additional context
    beta_percentile = (beta_history < current_beta).mean() * 100
    corr_percentile = (corr_history < current_corr).mean() * 100

    # Z-SCORE BASED REGIME CLASSIFICATION
    # Uses historical distribution, not arbitrary fixed thresholds
    if corr_z > high_z_threshold:
        regime = "RISK_ON"
        description = (
            f"Correlation z-score ({corr_z:.2f}) exceeds +{high_z_threshold}σ - "
            f"crypto unusually correlated with equities vs history"
        )
        signal = "Crypto behaving as high-beta risk asset - expect amplified equity moves"
    elif corr_z < low_z_threshold:
        regime = "RISK_OFF"
        description = (
            f"Correlation z-score ({corr_z:.2f}) below {low_z_threshold}σ - "
            f"crypto unusually decoupled/inverse vs history"
        )
        signal = "Potential safe-haven behavior - crypto may hedge equity drawdowns"
    elif abs(corr_z) < neutral_z_band:
        regime = "NEUTRAL"
        description = (
            f"Correlation z-score ({corr_z:.2f}) within ±{neutral_z_band}σ band - "
            f"normal correlation regime relative to history"
        )
        signal = "Typical correlation behavior - no unusual regime detected"
    elif corr_z > neutral_z_band:
        regime = "ELEVATED_CORRELATION"
        description = (
            f"Correlation z-score ({corr_z:.2f}) elevated but not extreme - "
            f"above average correlation with equities"
        )
        signal = "Moderate risk-on tilt - some equity sensitivity present"
    else:  # corr_z < -neutral_z_band but > low_z_threshold
        regime = "REDUCED_CORRELATION"
        description = (
            f"Correlation z-score ({corr_z:.2f}) below average but not extreme - "
            f"reduced correlation with equities"
        )
        signal = "Moderate decoupling - crypto-specific factors may be dominating"

    # Confidence: higher when z-score is clearly in a regime, lower near boundaries
    # Max confidence at extreme z-scores, min at boundary thresholds
    if abs(corr_z) > high_z_threshold:
        confidence = min(1.0, 0.7 + (abs(corr_z) - high_z_threshold) * 0.15)
    elif abs(corr_z) < neutral_z_band:
        confidence = 0.8  # High confidence in neutral regime
    else:
        # Transitional zone - lower confidence
        confidence = 0.5 + (abs(corr_z) - neutral_z_band) / (high_z_threshold - neutral_z_band) * 0.2

    confidence = max(0.3, min(1.0, confidence))

    # Historical context for interpretation
    historical_context = {
        "correlation_mean": float(corr_mean),
        "correlation_std": float(corr_std),
        "beta_mean": float(beta_mean),
        "beta_std": float(beta_std),
        "current_vs_mean": f"{'+' if current_corr > corr_mean else ''}{(current_corr - corr_mean):.3f}",
        "interpretation": (
            f"Current correlation ({current_corr:.3f}) is {abs(corr_z):.1f}σ "
            f"{'above' if corr_z > 0 else 'below'} the historical mean ({corr_mean:.3f})"
        )
    }

    return {
        "regime": regime,
        "description": description,
        "signal": signal,
        "confidence": float(confidence),
        "correlation_z_score": float(corr_z),
        "beta_z_score": float(beta_z),
        "correlation_percentile": float(corr_percentile),
        "beta_percentile": float(beta_percentile),
        "thresholds_used": {
            "high_z": high_z_threshold,
            "low_z": low_z_threshold,
            "neutral_band": neutral_z_band
        },
        "historical_context": historical_context
    }


def _build_regime_chart(
    dates: pd.Series,
    crypto_prices: pd.Series,
    equity_prices: pd.Series,
    rolling_corr: pd.Series,
    rolling_beta: pd.Series,
    crypto_symbol: str,
    equity_symbol: str,
    corr_mean: float,
    corr_std: float,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5,
    chart_id: str = "crypto_equity_regime"
) -> Dict[str, Any]:
    """
    Build clean two-panel chart showing crypto-equity regime.

    Panel 1: Normalized prices (crypto vs equity)
    Panel 2: Rolling correlation with z-score regime bands

    Args:
        dates: Date index
        crypto_prices: Normalized crypto prices
        equity_prices: Normalized equity prices
        rolling_corr: Rolling correlation series
        rolling_beta: Rolling beta series
        crypto_symbol: Crypto ticker
        equity_symbol: Equity ticker
        corr_mean: Historical correlation mean
        corr_std: Historical correlation std
        high_z_threshold: Z-score for RISK_ON threshold
        low_z_threshold: Z-score for RISK_OFF threshold
        neutral_z_band: Z-score band for NEUTRAL regime
        chart_id: Chart identifier

    Returns:
        Plotly figure dict
    """
    # Convert dates to string format for clean x-axis
    date_strings = pd.to_datetime(dates).strftime('%Y-%m-%d').tolist()

    # Calculate correlation thresholds from z-scores
    risk_on_threshold = corr_mean + high_z_threshold * corr_std
    risk_off_threshold = corr_mean + low_z_threshold * corr_std

    # Create clean 2-panel layout
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        row_heights=[0.5, 0.5],
        subplot_titles=(
            f'<b>{crypto_symbol} vs {equity_symbol}</b> (Normalized to 100)',
            f'<b>Rolling 30-Day Correlation</b>'
        )
    )

    # ═══════════════════════════════════════════════════════════════
    # PANEL 1: Normalized Prices
    # ═══════════════════════════════════════════════════════════════
    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=crypto_prices.tolist(),
            name=crypto_symbol,
            line=dict(color='#F7931A', width=2.5),
            hovertemplate='%{x}<br><b>' + crypto_symbol + '</b>: %{y:.1f}<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=equity_prices.tolist(),
            name=equity_symbol,
            line=dict(color='#2E86AB', width=2.5),
            hovertemplate='%{x}<br><b>' + equity_symbol + '</b>: %{y:.1f}<extra></extra>'
        ),
        row=1, col=1
    )

    # ═══════════════════════════════════════════════════════════════
    # PANEL 2: Correlation with Regime Zones
    # ═══════════════════════════════════════════════════════════════

    # Shade regime zones FIRST (so they're behind the line)
    # Risk-On zone (green, above +1.5σ)
    fig.add_hrect(
        y0=risk_on_threshold, y1=1.0,
        fillcolor="rgba(46, 204, 113, 0.15)",
        line_width=0,
        row=2, col=1
    )

    # Risk-Off zone (red, below -1.5σ)
    fig.add_hrect(
        y0=-1.0, y1=risk_off_threshold,
        fillcolor="rgba(231, 76, 60, 0.15)",
        line_width=0,
        row=2, col=1
    )

    # Correlation line
    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=rolling_corr.tolist(),
            name='Correlation',
            line=dict(color='#8E44AD', width=2.5),
            hovertemplate='%{x}<br><b>ρ</b>: %{y:.3f}<extra></extra>'
        ),
        row=2, col=1
    )

    # Mean line
    fig.add_hline(
        y=corr_mean,
        line_dash="solid",
        line_color="#555555",
        line_width=1.5,
        row=2, col=1
    )

    # Threshold lines (simple, no annotations cluttering the chart)
    fig.add_hline(
        y=risk_on_threshold,
        line_dash="dash",
        line_color="#27AE60",
        line_width=1,
        row=2, col=1
    )
    fig.add_hline(
        y=risk_off_threshold,
        line_dash="dash",
        line_color="#E74C3C",
        line_width=1,
        row=2, col=1
    )

    # Zero line
    fig.add_hline(
        y=0,
        line_dash="dot",
        line_color="#AAAAAA",
        line_width=1,
        row=2, col=1
    )

    # ═══════════════════════════════════════════════════════════════
    # LAYOUT
    # ═══════════════════════════════════════════════════════════════
    fig.update_layout(
        title=dict(
            text=f'<b>Crypto-Equity Regime Analysis</b>',
            font=dict(size=18, color='#2C3E50'),
            x=0.5,
            xanchor='center'
        ),
        height=600,
        width=900,
        template="plotly_white",
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)"
        ),
        margin=dict(t=80, b=60, l=60, r=40),
        font=dict(family="Arial, sans-serif", size=12)
    )

    # Y-axes
    fig.update_yaxes(
        title_text="Normalized Price",
        row=1, col=1,
        gridcolor='#EEEEEE'
    )
    fig.update_yaxes(
        title_text="Correlation (ρ)",
        row=2, col=1,
        range=[-0.5, 1.0],
        gridcolor='#EEEEEE',
        tickformat='.2f'
    )

    # X-axis
    fig.update_xaxes(
        row=2, col=1,
        tickangle=-45,
        nticks=12,
        gridcolor='#EEEEEE'
    )

    # Add regime legend as annotation
    current_corr = rolling_corr.iloc[-1] if len(rolling_corr) > 0 else 0
    regime_text = (
        f"<b>Regime Thresholds:</b><br>"
        f"🟢 RISK_ON: ρ > {risk_on_threshold:.2f} (+{high_z_threshold}σ)<br>"
        f"⚪ NEUTRAL: {risk_off_threshold:.2f} < ρ < {risk_on_threshold:.2f}<br>"
        f"🔴 RISK_OFF: ρ < {risk_off_threshold:.2f} ({low_z_threshold}σ)<br>"
        f"<b>Current:</b> ρ = {current_corr:.3f}"
    )

    fig.add_annotation(
        text=regime_text,
        xref="paper", yref="paper",
        x=0.02, y=0.48,
        showarrow=False,
        font=dict(size=10, color='#34495E'),
        align='left',
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#BDC3C7',
        borderwidth=1,
        borderpad=6
    )

    return {
        'id': chart_id,
        'title': f'Crypto-Equity Regime: {crypto_symbol} vs {equity_symbol}',
        'plotly': fig.to_dict(),
        'metadata': {
            'correlation_mean': float(corr_mean),
            'correlation_std': float(corr_std),
            'risk_on_threshold': float(risk_on_threshold),
            'risk_off_threshold': float(risk_off_threshold),
            'current_correlation': float(current_corr),
            'thresholds': 'z-score based'
        }
    }


def _build_correlation_heatmap(
    correlation_matrix: pd.DataFrame,
    chart_id: str = "crypto_equity_corr_matrix"
) -> Dict[str, Any]:
    """
    Build correlation heatmap for multiple assets.

    Args:
        correlation_matrix: Correlation matrix DataFrame
        chart_id: Chart identifier

    Returns:
        Plotly figure dict
    """
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix.values,
        x=correlation_matrix.columns.tolist(),
        y=correlation_matrix.index.tolist(),
        colorscale='RdBu_r',
        zmin=-1,
        zmax=1,
        colorbar=dict(title="Correlation"),
        hovertemplate='%{y} vs %{x}<br>Correlation: %{z:.3f}<extra></extra>',
        text=np.round(correlation_matrix.values, 2),
        texttemplate='%{text}',
        textfont={"size": 12}
    ))

    fig.update_layout(
        title='Cross-Asset Correlation Matrix',
        height=500,
        width=600,
        template="plotly_white"
    )

    return {
        'id': chart_id,
        'title': 'Cross-Asset Correlation Matrix',
        'plotly': fig.to_dict()
    }


async def analyze_crypto_equity_beta_regime_internal(
    crypto_symbol: str = "BTCUSD",
    equity_symbol: str = "SPY",
    lookback_days: int = 365,
    rolling_window: int = 30,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5,
    additional_cryptos: Optional[List[str]] = None,
    additional_equities: Optional[List[str]] = None,
    generate_chart: bool = True,
    generate_correlation_matrix: bool = True,
    include_regime_history: bool = True
) -> dict:
    """
    Internal function for crypto-equity beta regime analysis. Used by Canvas executor.

    Args:
        crypto_symbol: Primary crypto pair (default: BTCUSD)
        equity_symbol: Primary equity benchmark (default: SPY)
        lookback_days: Historical period in days (default: 365)
        rolling_window: Rolling window in days (default: 30)
        high_z_threshold: Z-score for RISK_ON regime (default: 1.5)
        low_z_threshold: Z-score for RISK_OFF regime (default: -1.5)
        neutral_z_band: Z-score band for NEUTRAL (default: 0.5)
        additional_cryptos: Extra crypto pairs for matrix
        additional_equities: Extra equity tickers for matrix
        generate_chart: Generate visualization (default: True)
        generate_correlation_matrix: Generate heatmap (default: True)
        include_regime_history: Include regime transitions (default: True)

    Returns:
        Dict with current_regime, metrics, historical_series, and optional charts.
    """
    try:
        # Initialize servers
        fmp_server = FMPMarketDataServer()
        alternatives_server = FMPAlternativesServer()

        try:
            await fmp_server.connect()
            await alternatives_server.connect()

            # Build asset lists
            crypto_symbols = [crypto_symbol]
            if additional_cryptos:
                crypto_symbols.extend(additional_cryptos)

            equity_symbols = [equity_symbol]
            if additional_equities:
                equity_symbols.extend(additional_equities)

            # Fetch all data
            price_data = {}
            failed_assets = []

            # Fetch crypto data
            for symbol in crypto_symbols:
                # ✅ CHECK CANCELLATION at each crypto symbol iteration
                _check_cancellation(f"fetching crypto {symbol}")
                
                try:
                    df = await _fetch_crypto_data(alternatives_server, symbol, lookback_days)
                    
                    # ✅ CHECK CANCELLATION after data fetch
                    _check_cancellation(f"after fetching crypto {symbol}")
                    
                    if len(df) > rolling_window:
                        price_data[symbol] = df
                        logger.info(f"Fetched {len(df)} days for {symbol}")
                    else:
                        failed_assets.append({
                            "symbol": symbol,
                            "error": f"Insufficient data: {len(df)} days"
                        })
                except asyncio.CancelledError:
                    raise  # Re-raise cancellation
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")
                    failed_assets.append({"symbol": symbol, "error": str(e)})

            # Fetch equity data
            for symbol in equity_symbols:
                # ✅ CHECK CANCELLATION at each equity symbol iteration
                _check_cancellation(f"fetching equity {symbol}")
                
                try:
                    df = await _fetch_equity_data(fmp_server, symbol, lookback_days)
                    
                    # ✅ CHECK CANCELLATION after data fetch
                    _check_cancellation(f"after fetching equity {symbol}")
                    
                    if len(df) > rolling_window:
                        price_data[symbol] = df
                        logger.info(f"Fetched {len(df)} days for {symbol}")
                    else:
                        failed_assets.append({
                            "symbol": symbol,
                            "error": f"Insufficient data: {len(df)} days"
                        })
                except asyncio.CancelledError:
                    raise  # Re-raise cancellation
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")
                    failed_assets.append({"symbol": symbol, "error": str(e)})

            # Validate we have primary assets
            if crypto_symbol not in price_data:
                return jsonify_results({
                    "error": f"Failed to fetch primary crypto: {crypto_symbol}",
                    "failed_assets": failed_assets
                })

            if equity_symbol not in price_data:
                return jsonify_results({
                    "error": f"Failed to fetch primary equity: {equity_symbol}",
                    "failed_assets": failed_assets
                })

            # Merge primary assets on date
            crypto_df = price_data[crypto_symbol].rename(columns={'price': 'crypto_price'})
            equity_df = price_data[equity_symbol].rename(columns={'price': 'equity_price'})

            merged = pd.merge(crypto_df, equity_df, on='date', how='inner')
            merged = merged.sort_values('date').reset_index(drop=True)

            if len(merged) < rolling_window + 10:
                return jsonify_results({
                    "error": f"Insufficient overlapping data: {len(merged)} days",
                    "crypto_days": len(crypto_df),
                    "equity_days": len(equity_df)
                })

            # Calculate returns
            merged['crypto_return'] = merged['crypto_price'].pct_change()
            merged['equity_return'] = merged['equity_price'].pct_change()
            merged = merged.dropna()

            # Calculate rolling metrics
            rolling_corr = _calculate_rolling_correlation(
                merged['crypto_return'],
                merged['equity_return'],
                rolling_window
            )

            rolling_beta = _calculate_rolling_beta(
                merged['crypto_return'],
                merged['equity_return'],
                rolling_window
            )

            # Get current values
            current_corr = rolling_corr.iloc[-1] if len(rolling_corr) > 0 else 0
            current_beta = rolling_beta.iloc[-1] if len(rolling_beta) > 0 else 0

            # Historical stats
            valid_corr = rolling_corr.dropna()
            valid_beta = rolling_beta.dropna()

            # Classify regime using z-score based thresholds
            regime_classification = _classify_regime(
                current_beta,
                current_corr,
                valid_beta,
                valid_corr,
                high_z_threshold=high_z_threshold,
                low_z_threshold=low_z_threshold,
                neutral_z_band=neutral_z_band
            )

            # Normalize prices for historical series
            norm_crypto = merged['crypto_price'] / merged['crypto_price'].iloc[0] * 100
            norm_equity = merged['equity_price'] / merged['equity_price'].iloc[0] * 100

            # Build response
            response = {
                "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                "crypto_symbol": crypto_symbol,
                "equity_symbol": equity_symbol,
                "lookback_days": lookback_days,
                "rolling_window": rolling_window,
                "data_points": len(merged),
                "current_regime": regime_classification,
                "metrics": {
                    "current_beta": float(current_beta),
                    "current_correlation": float(current_corr),
                    "beta_mean": float(valid_beta.mean()),
                    "beta_std": float(valid_beta.std()),
                    "correlation_mean": float(valid_corr.mean()),
                    "correlation_std": float(valid_corr.std()),
                    "beta_min": float(valid_beta.min()),
                    "beta_max": float(valid_beta.max()),
                    "correlation_min": float(valid_corr.min()),
                    "correlation_max": float(valid_corr.max())
                },
                # Historical series for Canvas chart building
                "historical_series": {
                    "dates": merged['date'].dt.strftime('%Y-%m-%d').tolist(),
                    "crypto_prices": norm_crypto.tolist(),
                    "equity_prices": norm_equity.tolist(),
                    "rolling_corr": rolling_corr.tolist(),
                    "rolling_beta": rolling_beta.tolist(),
                }
            }

            # Regime history using z-score based classification
            if include_regime_history:
                # Sample regime at weekly intervals
                regime_history = []
                sample_indices = range(rolling_window, len(valid_corr), 7)

                # Use same z-score thresholds as main classification
                high_z = high_z_threshold
                low_z = low_z_threshold
                neutral_band = neutral_z_band

                for idx in list(sample_indices)[-12:]:  # Last 12 weeks
                    if idx < len(valid_corr):
                        hist_corr = valid_corr.iloc[idx]
                        hist_beta = valid_beta.iloc[idx]

                        # Calculate z-score at this point using lookback mean/std
                        lookback_corr = valid_corr.iloc[:idx]
                        if len(lookback_corr) > 10:
                            corr_mean_at_point = lookback_corr.mean()
                            corr_std_at_point = lookback_corr.std()
                            corr_z_at_point = (
                                (hist_corr - corr_mean_at_point) / corr_std_at_point
                                if corr_std_at_point > 1e-8 else 0
                            )
                        else:
                            corr_z_at_point = 0

                        # Z-score based regime classification
                        if corr_z_at_point > high_z:
                            regime = "RISK_ON"
                        elif corr_z_at_point < low_z:
                            regime = "RISK_OFF"
                        elif abs(corr_z_at_point) < neutral_band:
                            regime = "NEUTRAL"
                        elif corr_z_at_point > neutral_band:
                            regime = "ELEVATED_CORRELATION"
                        else:
                            regime = "REDUCED_CORRELATION"

                        regime_history.append({
                            "date": merged['date'].iloc[idx].strftime("%Y-%m-%d"),
                            "regime": regime,
                            "correlation": float(hist_corr),
                            "correlation_z_score": float(corr_z_at_point),
                            "beta": float(hist_beta)
                        })

                response["regime_history"] = regime_history

            # Cross-asset correlation matrix
            if generate_correlation_matrix and len(price_data) > 2:
                # Build return DataFrame for all assets
                all_returns = {}

                for symbol, df in price_data.items():
                    df_aligned = df.set_index('date')['price'].pct_change().dropna()
                    all_returns[symbol] = df_aligned

                returns_df = pd.DataFrame(all_returns).dropna()

                if len(returns_df) > rolling_window:
                    corr_matrix = returns_df.corr()
                    response["cross_asset_correlations"] = corr_matrix.to_dict()

            # Generate charts
            charts = []

            if generate_chart:
                regime_chart = _build_regime_chart(
                    merged['date'],
                    norm_crypto,
                    norm_equity,
                    rolling_corr,
                    rolling_beta,
                    crypto_symbol,
                    equity_symbol,
                    corr_mean=float(valid_corr.mean()),
                    corr_std=float(valid_corr.std()),
                    high_z_threshold=high_z_threshold,
                    low_z_threshold=low_z_threshold,
                    neutral_z_band=neutral_z_band
                )
                charts.append(regime_chart)

            if generate_correlation_matrix and len(price_data) > 2:
                # Build correlation matrix for chart
                all_returns = {}
                for symbol, df in price_data.items():
                    df_aligned = df.set_index('date')['price'].pct_change().dropna()
                    all_returns[symbol] = df_aligned

                returns_df = pd.DataFrame(all_returns).dropna()
                if len(returns_df) > rolling_window:
                    corr_matrix = returns_df.corr()
                    corr_chart = _build_correlation_heatmap(corr_matrix)
                    charts.append(corr_chart)

            if charts:
                response["charts"] = wrap_plotly_charts(charts, default_type="regime_chart")

            if failed_assets:
                response["failed_assets"] = failed_assets

            return response

        finally:
            await fmp_server.cleanup()
            await alternatives_server.cleanup()

    except asyncio.CancelledError:
        logger.info("[CANCEL] Crypto-equity beta regime analysis cancelled by user")
        raise  # Re-raise to propagate cancellation
    except Exception as e:
        logger.error(f"Crypto-equity beta regime analysis failed: {e}", exc_info=True)
        return {
            "error": "Analysis failed",
            "details": str(e)
        }


@function_tool
async def analyze_crypto_equity_beta_regime(
    crypto_symbol: str = "BTCUSD",
    equity_symbol: str = "SPY",
    lookback_days: int = 365,
    rolling_window: int = 30,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5,
    additional_cryptos: Optional[List[str]] = None,
    additional_equities: Optional[List[str]] = None,
    generate_regime_chart: bool = True,
    generate_correlation_matrix: bool = True,
    include_regime_history: bool = True
) -> dict:
    """
    Analyze crypto-equity correlation regime to detect risk-on/risk-off behavior.

    **What This Tool Does:**
    - Fetches historical prices for crypto (BTC/ETH) and equity (SPY/QQQ)
    - Calculates rolling beta and correlation between crypto and equity
    - Classifies current regime using Z-SCORE based thresholds
    - Provides trading signals based on regime

    **Z-Score Based Regime Classification:**
    - RISK_ON: Correlation z-score > +1.5σ (unusually high correlation)
    - RISK_OFF: Correlation z-score < -1.5σ (unusually decoupled)
    - NEUTRAL: |Correlation z-score| < 0.5σ (within normal range)

    Args:
        crypto_symbol: Primary crypto pair (default: BTCUSD)
        equity_symbol: Primary equity benchmark (default: SPY)
        lookback_days: Historical period in days (default: 365)
        rolling_window: Rolling window in days (default: 30)
        high_z_threshold: Z-score for RISK_ON regime (default: 1.5)
        low_z_threshold: Z-score for RISK_OFF regime (default: -1.5)
        neutral_z_band: Z-score band for NEUTRAL (default: 0.5)
        additional_cryptos: Extra crypto pairs for correlation matrix
        additional_equities: Extra equity tickers for correlation matrix
        generate_regime_chart: Generate regime chart (default: True)
        generate_correlation_matrix: Generate correlation heatmap (default: True)
        include_regime_history: Include regime transitions (default: True)

    Returns:
        Dict with current_regime, metrics, regime_history, charts.
    """
    result = await analyze_crypto_equity_beta_regime_internal(
        crypto_symbol=crypto_symbol,
        equity_symbol=equity_symbol,
        lookback_days=lookback_days,
        rolling_window=rolling_window,
        high_z_threshold=high_z_threshold,
        low_z_threshold=low_z_threshold,
        neutral_z_band=neutral_z_band,
        additional_cryptos=additional_cryptos,
        additional_equities=additional_equities,
        generate_chart=generate_regime_chart,
        generate_correlation_matrix=generate_correlation_matrix,
        include_regime_history=include_regime_history,
    )
    return jsonify_results(result)

