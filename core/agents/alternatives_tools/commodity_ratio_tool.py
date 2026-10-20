"""
Commodity Ratio Mean Reversion Tool

Generalized commodity ratio analysis using z-score based signals.
Supports preset pairs (Gold/Silver, Gold/Oil, etc.) or custom symbol pairs.

Z-Score Based Signals (not hardcoded thresholds):
- High z-score (ratio elevated): Denominator undervalued → Long denom / Short num
- Low z-score (ratio depressed): Numerator undervalued → Long num / Short denom
- Neutral z-score: No clear mean reversion opportunity
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents import function_tool
from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


# =============================================================================
# PRESET COMMODITY PAIRS
# =============================================================================

PRESET_PAIRS = {
    "gold_silver": {
        "num": "GCUSD",
        "denom": "SIUSD",
        "name": "Gold/Silver",
        "num_name": "Gold",
        "denom_name": "Silver",
        "description": "Classic precious metals ratio. High ratio = silver cheap.",
    },
    "gold_oil": {
        "num": "GCUSD",
        "denom": "CLUSD",
        "name": "Gold/Oil",
        "num_name": "Gold",
        "denom_name": "Oil",
        "description": "Risk/growth indicator. High ratio = oil cheap (growth pessimism).",
    },
    "oil_gas": {
        "num": "CLUSD",
        "denom": "NGUSD",
        "name": "Oil/NatGas",
        "num_name": "Oil",
        "denom_name": "NatGas",
        "description": "Energy substitution ratio. High ratio = nat gas cheap.",
    },
    "copper_gold": {
        "num": "HGUSD",
        "denom": "GCUSD",
        "name": "Copper/Gold",
        "num_name": "Copper",
        "denom_name": "Gold",
        "description": "Risk-on indicator. High ratio = growth optimism.",
    },
    "silver_copper": {
        "num": "SIUSD",
        "denom": "HGUSD",
        "name": "Silver/Copper",
        "num_name": "Silver",
        "denom_name": "Copper",
        "description": "Precious vs industrial metals.",
    },
}


def _check_cancellation(context: str = ""):
    """Check if cancellation was requested and raise CancelledError if so."""
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CANCEL] commodity_ratio cancelled{' during ' + context if context else ''}")
        raise asyncio.CancelledError(f"commodity_ratio cancelled{' during ' + context if context else ''}")


async def _fetch_commodity_historical(
    server: FMPAlternativesServer,
    symbol: str,
    lookback_days: int = 365
) -> pd.DataFrame:
    """
    Fetch historical commodity data from FMP Alternatives Server.

    Args:
        server: Connected FMP Alternatives server instance
        symbol: Commodity symbol (e.g., GCUSD, SIUSD, CLUSD)
        lookback_days: Days of history to fetch

    Returns:
        DataFrame with date and price columns
    """
    from_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    result = await server.call_tool("get_commodities_data", {
        "symbol": symbol,
        "data_type": "historical",
        "timeframe": "1hour",
        "from": from_date,
        "to": to_date
    })

    if not result or not hasattr(result, 'content'):
        raise ValueError(f"No data returned for {symbol}")

    data = safe_parse_json(result)

    if not data:
        raise ValueError(f"Invalid data structure for {symbol}")

    historical_data = data.get('historical_data', data)

    if isinstance(historical_data, list) and len(historical_data) > 0:
        df = pd.DataFrame(historical_data)

        # Find date and price columns dynamically
        date_col = None
        price_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'date' in col_lower or 'time' in col_lower:
                date_col = col
            if col_lower == 'close' or (price_col is None and col_lower in ['price', 'c']):
                price_col = col

        if not date_col:
            date_col = df.columns[0]
        if not price_col:
            for col in ['close', 'Close', 'price', 'Price', 'c']:
                if col in df.columns:
                    price_col = col
                    break
            if not price_col:
                price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

        df['date'] = pd.to_datetime(df[date_col])
        df['price'] = pd.to_numeric(df[price_col], errors='coerce')

        # Resample to daily
        df = df.set_index('date')
        df = df.resample('D').last().dropna().reset_index()

        return df[['date', 'price']]

    elif isinstance(historical_data, dict) and data.get("error"):
        raise ValueError(f"API error for {symbol}: {data.get('error')}")

    raise ValueError(f"Unexpected data format for {symbol}")


def _classify_ratio_regime(
    current_ratio: float,
    ratio_history: pd.Series,
    num_name: str,
    denom_name: str,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5
) -> Dict[str, Any]:
    """
    Classify commodity ratio regime using z-scores.

    Args:
        current_ratio: Current ratio value
        ratio_history: Historical ratio series
        num_name: Name of numerator commodity (e.g., "Gold")
        denom_name: Name of denominator commodity (e.g., "Silver")
        high_z_threshold: Z-score for DENOM_CHEAP signal
        low_z_threshold: Z-score for NUM_CHEAP signal
        neutral_z_band: Z-score band for neutral

    Returns:
        Regime classification with trading signal
    """
    ratio_mean = ratio_history.mean()
    ratio_std = ratio_history.std()

    # Z-score calculation
    ratio_z = (current_ratio - ratio_mean) / ratio_std if ratio_std > 1e-8 else 0

    # Percentile
    ratio_percentile = (ratio_history < current_ratio).mean() * 100

    # Z-score based classification with dynamic names
    if ratio_z > high_z_threshold:
        regime = f"{denom_name.upper()}_CHEAP"
        description = (
            f"Ratio z-score ({ratio_z:.2f}) exceeds +{high_z_threshold}σ - "
            f"{denom_name} historically cheap relative to {num_name}"
        )
        signal = f"LONG {denom_name.upper()} / SHORT {num_name.upper()}"
        trade_idea = (
            f"Consider: Long {denom_name}/Short {num_name} spread, or outright long {denom_name}. "
            f"Ratio mean reversion favors {denom_name} outperformance."
        )
    elif ratio_z < low_z_threshold:
        regime = f"{num_name.upper()}_CHEAP"
        description = (
            f"Ratio z-score ({ratio_z:.2f}) below {low_z_threshold}σ - "
            f"{num_name} historically cheap relative to {denom_name}"
        )
        signal = f"LONG {num_name.upper()} / SHORT {denom_name.upper()}"
        trade_idea = (
            f"Consider: Long {num_name}/Short {denom_name} spread, or outright long {num_name}. "
            f"Ratio mean reversion favors {num_name} outperformance."
        )
    elif abs(ratio_z) < neutral_z_band:
        regime = "NEUTRAL"
        description = (
            f"Ratio z-score ({ratio_z:.2f}) within ±{neutral_z_band}σ - "
            f"no clear mean reversion opportunity"
        )
        signal = "NO TRADE"
        trade_idea = "Ratio near historical mean. Wait for extreme readings."
    elif ratio_z > neutral_z_band:
        regime = f"{denom_name.upper()}_SLIGHTLY_CHEAP"
        description = (
            f"Ratio z-score ({ratio_z:.2f}) elevated but not extreme - "
            f"{denom_name} moderately cheap"
        )
        signal = f"LEAN {denom_name.upper()}"
        trade_idea = f"Mild {denom_name} preference. Consider smaller position or wait for confirmation."
    else:
        regime = f"{num_name.upper()}_SLIGHTLY_CHEAP"
        description = (
            f"Ratio z-score ({ratio_z:.2f}) depressed but not extreme - "
            f"{num_name} moderately cheap"
        )
        signal = f"LEAN {num_name.upper()}"
        trade_idea = f"Mild {num_name} preference. Consider smaller position or wait for confirmation."

    # Confidence based on z-score extremity
    if abs(ratio_z) > high_z_threshold:
        confidence = min(1.0, 0.7 + (abs(ratio_z) - high_z_threshold) * 0.15)
    elif abs(ratio_z) < neutral_z_band:
        confidence = 0.3  # Low confidence in neutral
    else:
        confidence = 0.5

    return {
        "regime": regime,
        "description": description,
        "signal": signal,
        "trade_idea": trade_idea,
        "confidence": float(confidence),
        "ratio_z_score": float(ratio_z),
        "ratio_percentile": float(ratio_percentile),
        "historical_context": {
            "ratio_mean": float(ratio_mean),
            "ratio_std": float(ratio_std),
            "ratio_min": float(ratio_history.min()),
            "ratio_max": float(ratio_history.max()),
            "current_vs_mean": f"{'+' if current_ratio > ratio_mean else ''}{current_ratio - ratio_mean:.2f}"
        }
    }


def _build_ratio_chart(
    dates: pd.Series,
    num_prices: pd.Series,
    denom_prices: pd.Series,
    ratio: pd.Series,
    num_name: str,
    denom_name: str,
    ratio_mean: float,
    ratio_std: float,
    high_z_threshold: float,
    low_z_threshold: float,
    chart_id: str = "commodity_ratio"
) -> Dict[str, Any]:
    """
    Build clean two-panel chart for commodity ratio analysis.

    Panel 1: Numerator and Denominator prices (normalized)
    Panel 2: Ratio with z-score bands
    """
    # Convert dates to strings
    date_strings = pd.to_datetime(dates).dt.strftime('%Y-%m-%d').tolist()

    # Calculate thresholds
    upper_threshold = ratio_mean + high_z_threshold * ratio_std
    lower_threshold = ratio_mean + low_z_threshold * ratio_std

    # Normalize prices to 100
    norm_num = (num_prices / num_prices.iloc[0] * 100).tolist()
    norm_denom = (denom_prices / denom_prices.iloc[0] * 100).tolist()

    ratio_name = f"{num_name}/{denom_name}"

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        row_heights=[0.45, 0.55],
        subplot_titles=(
            f'<b>{num_name} vs {denom_name}</b> (Normalized to 100)',
            f'<b>{ratio_name} Ratio</b>'
        )
    )

    # ═══════════════════════════════════════════════════════════════
    # PANEL 1: Normalized Prices
    # ═══════════════════════════════════════════════════════════════
    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=norm_num,
            name=num_name,
            line=dict(color='#0891b2', width=2.5),
            hovertemplate=f'%{{x}}<br><b>{num_name}</b>: %{{y:.1f}}<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=norm_denom,
            name=denom_name,
            line=dict(color='#d97706', width=2.5),
            hovertemplate=f'%{{x}}<br><b>{denom_name}</b>: %{{y:.1f}}<extra></extra>'
        ),
        row=1, col=1
    )

    # ═══════════════════════════════════════════════════════════════
    # PANEL 2: Ratio with Regime Zones
    # ═══════════════════════════════════════════════════════════════

    # Denom cheap zone (ratio high)
    fig.add_hrect(
        y0=upper_threshold, y1=ratio.max() * 1.05,
        fillcolor="rgba(217, 119, 6, 0.2)",  # Amber tint for denom
        line_width=0,
        row=2, col=1
    )

    # Num cheap zone (ratio low)
    fig.add_hrect(
        y0=ratio.min() * 0.95, y1=lower_threshold,
        fillcolor="rgba(8, 145, 178, 0.2)",  # Teal tint for num
        line_width=0,
        row=2, col=1
    )

    # Ratio line
    fig.add_trace(
        go.Scatter(
            x=date_strings,
            y=ratio.tolist(),
            name=ratio_name,
            line=dict(color='#6b7280', width=2.5),
            hovertemplate='%{x}<br><b>Ratio</b>: %{y:.2f}<extra></extra>'
        ),
        row=2, col=1
    )

    # Mean line
    fig.add_hline(
        y=ratio_mean,
        line_dash="solid",
        line_color="#555555",
        line_width=1.5,
        row=2, col=1
    )

    # Threshold lines
    fig.add_hline(
        y=upper_threshold,
        line_dash="dash",
        line_color="#d97706",
        line_width=1,
        row=2, col=1
    )
    fig.add_hline(
        y=lower_threshold,
        line_dash="dash",
        line_color="#0891b2",
        line_width=1,
        row=2, col=1
    )

    # ═══════════════════════════════════════════════════════════════
    # LAYOUT
    # ═══════════════════════════════════════════════════════════════
    current_ratio = ratio.iloc[-1]

    fig.update_layout(
        title=dict(
            text=f'<b>{ratio_name} Ratio Mean Reversion</b>',
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
        title_text="Ratio",
        row=2, col=1,
        gridcolor='#EEEEEE'
    )

    # X-axis
    fig.update_xaxes(
        row=2, col=1,
        tickangle=-45,
        nticks=12,
        gridcolor='#EEEEEE'
    )

    # Legend annotation
    legend_text = (
        f"<b>Regime Zones:</b><br>"
        f"🟧 {denom_name.upper()} CHEAP: Ratio > {upper_threshold:.2f} (+{high_z_threshold}σ)<br>"
        f"🟦 {num_name.upper()} CHEAP: Ratio < {lower_threshold:.2f} ({low_z_threshold}σ)<br>"
        f"<b>Current:</b> {current_ratio:.2f} (Mean: {ratio_mean:.2f})"
    )

    fig.add_annotation(
        text=legend_text,
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
        'title': f'{ratio_name} Ratio Analysis',
        'plotly': fig.to_dict(),
        'metadata': {
            'current_ratio': float(current_ratio),
            'ratio_mean': float(ratio_mean),
            'upper_threshold': float(upper_threshold),
            'lower_threshold': float(lower_threshold)
        }
    }


async def analyze_commodity_ratio_internal(
    preset: str = "gold_silver",
    numerator: Optional[str] = None,
    denominator: Optional[str] = None,
    lookback_days: int = 365,
    rolling_window: int = 20,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5,
    generate_chart: bool = True
) -> dict:
    """
    Internal function for commodity ratio analysis. Used by Canvas executor.

    Args:
        preset: Preset pair name ("gold_silver", "gold_oil", "oil_gas", "copper_gold", "silver_copper", "custom")
        numerator: Custom numerator symbol (only if preset="custom")
        denominator: Custom denominator symbol (only if preset="custom")
        lookback_days: Historical period for analysis (default: 365)
        rolling_window: Window for smoothing (default: 20)
        high_z_threshold: Z-score for DENOM_CHEAP signal (default: 1.5)
        low_z_threshold: Z-score for NUM_CHEAP signal (default: -1.5)
        neutral_z_band: Z-score band for neutral regime (default: 0.5)
        generate_chart: Generate visualization (default: True)

    Returns:
        Dict with current_ratio, regime, signal, metrics, and optional charts.
    """
    # Resolve symbols from preset or custom
    if preset == "custom":
        if not numerator or not denominator:
            return {
                "error": "Custom preset requires both 'numerator' and 'denominator' symbols",
                "available_presets": list(PRESET_PAIRS.keys())
            }
        num_symbol = numerator.upper()
        denom_symbol = denominator.upper()
        num_name = num_symbol.replace("USD", "")
        denom_name = denom_symbol.replace("USD", "")
        pair_name = f"{num_name}/{denom_name}"
        pair_description = f"Custom ratio: {num_symbol}/{denom_symbol}"
    elif preset in PRESET_PAIRS:
        pair_config = PRESET_PAIRS[preset]
        num_symbol = pair_config["num"]
        denom_symbol = pair_config["denom"]
        num_name = pair_config["num_name"]
        denom_name = pair_config["denom_name"]
        pair_name = pair_config["name"]
        pair_description = pair_config["description"]
    else:
        return {
            "error": f"Unknown preset: {preset}",
            "available_presets": list(PRESET_PAIRS.keys())
        }

    server = FMPAlternativesServer()

    try:
        logger.info(f"Analyzing {pair_name} ratio with {lookback_days} day lookback")

        await server.connect()

        # Fetch numerator data
        num_data = await _fetch_commodity_historical(server, num_symbol, lookback_days)
        _check_cancellation(f"after fetching {num_name} data")

        # Fetch denominator data
        denom_data = await _fetch_commodity_historical(server, denom_symbol, lookback_days)
        _check_cancellation(f"after fetching {denom_name} data")

        if num_data.empty or denom_data.empty:
            return {
                "error": "Failed to fetch commodity data",
                f"{num_name}_records": len(num_data) if not num_data.empty else 0,
                f"{denom_name}_records": len(denom_data) if not denom_data.empty else 0
            }

        # Merge on date
        merged = pd.merge(
            num_data.rename(columns={'price': 'num_price'}),
            denom_data.rename(columns={'price': 'denom_price'}),
            on='date',
            how='inner'
        ).sort_values('date').reset_index(drop=True)

        if len(merged) < rolling_window + 10:
            return {
                "error": f"Insufficient overlapping data: {len(merged)} days",
                "min_required": rolling_window + 10
            }

        # Calculate ratio
        merged['ratio'] = merged['num_price'] / merged['denom_price']

        # Rolling smoothed ratio
        merged['ratio_smooth'] = merged['ratio'].rolling(rolling_window).mean()

        # Get valid data
        valid_data = merged.dropna()

        if len(valid_data) < 30:
            return {"error": "Insufficient data after smoothing"}

        # Current values
        current_ratio = valid_data['ratio'].iloc[-1]
        current_num_price = valid_data['num_price'].iloc[-1]
        current_denom_price = valid_data['denom_price'].iloc[-1]

        # Classify regime with dynamic names
        regime_classification = _classify_ratio_regime(
            current_ratio,
            valid_data['ratio'],
            num_name=num_name,
            denom_name=denom_name,
            high_z_threshold=high_z_threshold,
            low_z_threshold=low_z_threshold,
            neutral_z_band=neutral_z_band
        )

        # Build response
        response = {
            "pair_name": pair_name,
            "pair_description": pair_description,
            "numerator": {"symbol": num_symbol, "name": num_name, "price": float(current_num_price)},
            "denominator": {"symbol": denom_symbol, "name": denom_name, "price": float(current_denom_price)},
            "current_ratio": float(current_ratio),
            "regime": regime_classification,
            "analysis_period": {
                "start_date": valid_data['date'].iloc[0].strftime("%Y-%m-%d"),
                "end_date": valid_data['date'].iloc[-1].strftime("%Y-%m-%d"),
                "trading_days": len(valid_data)
            },
            "parameters": {
                "preset": preset,
                "lookback_days": lookback_days,
                "rolling_window": rolling_window,
                "high_z_threshold": high_z_threshold,
                "low_z_threshold": low_z_threshold
            },
            # Historical series for Canvas chart building
            "historical_series": {
                "dates": valid_data['date'].dt.strftime('%Y-%m-%d').tolist(),
                "num_prices": valid_data['num_price'].tolist(),
                "denom_prices": valid_data['denom_price'].tolist(),
                "ratio": valid_data['ratio'].tolist(),
                "ratio_mean": float(valid_data['ratio'].mean()),
                "ratio_std": float(valid_data['ratio'].std()),
            }
        }

        # Generate chart
        charts = []
        if generate_chart:
            ratio_chart = _build_ratio_chart(
                valid_data['date'],
                valid_data['num_price'],
                valid_data['denom_price'],
                valid_data['ratio'],
                num_name=num_name,
                denom_name=denom_name,
                ratio_mean=float(valid_data['ratio'].mean()),
                ratio_std=float(valid_data['ratio'].std()),
                high_z_threshold=high_z_threshold,
                low_z_threshold=low_z_threshold
            )
            charts.append(ratio_chart)

        if charts:
            response["charts"] = wrap_plotly_charts(charts, "line")

        logger.info(f"{pair_name} analysis complete: {regime_classification['regime']}")
        return response

    except asyncio.CancelledError:
        logger.info(f"[CANCEL] {pair_name} ratio analysis cancelled by user")
        raise
    except Exception as e:
        logger.error(f"Commodity ratio analysis failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }
    finally:
        await server.cleanup()


@function_tool
async def analyze_commodity_ratio(
    preset: str = "gold_silver",
    numerator: Optional[str] = None,
    denominator: Optional[str] = None,
    lookback_days: int = 365,
    rolling_window: int = 20,
    high_z_threshold: float = 1.5,
    low_z_threshold: float = -1.5,
    neutral_z_band: float = 0.5,
    generate_chart: bool = True
) -> dict:
    """
    Analyze any commodity ratio for mean reversion opportunities.

    **What This Tool Does:**
    - Fetches historical prices for two commodities
    - Calculates the ratio (numerator / denominator)
    - Classifies current regime using Z-SCORE based thresholds
    - Provides actionable trading signals for relative value

    **Preset Pairs Available:**
    - gold_silver: Classic precious metals ratio (default)
    - gold_oil: Risk/growth indicator
    - oil_gas: Energy substitution ratio
    - copper_gold: Risk-on indicator
    - silver_copper: Precious vs industrial metals
    - custom: Provide your own numerator and denominator symbols

    **Z-Score Based Signals (No Hardcoded Thresholds):**
    - High z-score: Ratio elevated → Denominator undervalued
    - Low z-score: Ratio depressed → Numerator undervalued
    - Neutral: Ratio near historical mean → No clear trade

    Args:
        preset: Preset pair name or "custom" for manual symbols
        numerator: Custom numerator symbol (e.g., GCUSD) - only used if preset="custom"
        denominator: Custom denominator symbol (e.g., SIUSD) - only used if preset="custom"
        lookback_days: Historical period for analysis (default: 365)
        rolling_window: Window for smoothing (default: 20)
        high_z_threshold: Z-score for DENOM_CHEAP signal (default: 1.5)
        low_z_threshold: Z-score for NUM_CHEAP signal (default: -1.5)
        neutral_z_band: Z-score band for neutral regime (default: 0.5)
        generate_chart: Generate visualization (default: True)

    Returns:
        Dict containing:
        - pair_name: Name of the ratio pair
        - current_ratio: Current ratio value
        - regime: Classification with signal
        - numerator/denominator: Symbol info and current prices
        - charts: Plotly visualization (if enabled)

    Examples:
        # Use preset gold/silver ratio
        >>> result = await analyze_commodity_ratio(preset="gold_silver")
        
        # Use gold/oil ratio
        >>> result = await analyze_commodity_ratio(preset="gold_oil")
        
        # Custom ratio (e.g., Platinum/Palladium)
        >>> result = await analyze_commodity_ratio(
        ...     preset="custom",
        ...     numerator="PLUSD",
        ...     denominator="PAUSD"
        ... )
    """
    return await analyze_commodity_ratio_internal(
        preset=preset,
        numerator=numerator,
        denominator=denominator,
        lookback_days=lookback_days,
        rolling_window=rolling_window,
        high_z_threshold=high_z_threshold,
        low_z_threshold=low_z_threshold,
        neutral_z_band=neutral_z_band,
        generate_chart=generate_chart
    )
