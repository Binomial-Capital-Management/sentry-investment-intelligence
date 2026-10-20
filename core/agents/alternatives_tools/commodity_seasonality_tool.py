"""
Commodity Seasonality Analyzer Tool

Analyzes historical seasonal patterns in commodities to identify:
- Monthly performance patterns (which months tend to be bullish/bearish)
- Seasonal strength vs current price (is the commodity above/below seasonal norm?)
- Trading opportunities based on seasonal deviations

Uses z-scores to identify when prices deviate significantly from seasonal norms.
NO hardcoded symbol mappings - works with any FMP commodity symbol.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from agents import function_tool

from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


def _check_cancellation(context: str = ""):
    """Check if cancellation was requested and raise CancelledError if so."""
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CANCEL] commodity_seasonality cancelled{' during ' + context if context else ''}")
        raise asyncio.CancelledError(f"commodity_seasonality cancelled{' during ' + context if context else ''}")


async def _fetch_commodity_history(
    server: FMPAlternativesServer,
    symbol: str,
    years: int = 2
) -> pd.DataFrame:
    """Fetch historical commodity data for seasonality analysis using EOD (daily) data."""
    from_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    
    result = await server.call_tool("get_commodities_data", {
        "symbol": symbol,
        "data_type": "historical",
        "timeframe": "eod",  # Daily data - efficient for multi-year analysis
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
        
        # Dynamic column detection
        date_col = next((c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()), df.columns[0])
        price_col = next((c for c in df.columns if c.lower() == 'close'), 
                        next((c for c in df.columns if c.lower() in ['price', 'c']), None))
        if not price_col:
            price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        df['date'] = pd.to_datetime(df[date_col])
        df['close'] = pd.to_numeric(df[price_col], errors='coerce')
        df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)
        
        df['month'] = df['date'].dt.month
        df['year'] = df['date'].dt.year
        df['month_name'] = df['date'].dt.strftime('%b')
        
        return df[['date', 'close', 'month', 'year', 'month_name']]
    
    raise ValueError(f"Unexpected data format for {symbol}")


def _calculate_monthly_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate monthly returns from daily data."""
    monthly = df.groupby(['year', 'month']).agg({
        'close': ['first', 'last'],
        'month_name': 'first'
    }).reset_index()
    
    monthly.columns = ['year', 'month', 'open', 'close', 'month_name']
    monthly['return'] = (monthly['close'] / monthly['open'] - 1) * 100
    return monthly


def _calculate_seasonal_stats(monthly_returns: pd.DataFrame) -> Dict[int, Dict[str, float]]:
    """Calculate seasonal statistics by month."""
    seasonal_stats = {}
    
    for month in range(1, 13):
        month_data = monthly_returns[monthly_returns['month'] == month]['return']
        if len(month_data) >= 2:
            seasonal_stats[month] = {
                'mean_return': month_data.mean(),
                'median_return': month_data.median(),
                'std': month_data.std(),
                'win_rate': (month_data > 0).mean() * 100,
                'sample_size': len(month_data),
                'best_year': month_data.max(),
                'worst_year': month_data.min()
            }
    
    return seasonal_stats


def _get_current_context(df: pd.DataFrame, seasonal_stats: Dict[int, Dict[str, float]]) -> Dict[str, Any]:
    """Calculate where current price sits vs seasonal expectations."""
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    ytd_data = df[df['year'] == current_year]
    if len(ytd_data) < 2:
        return {"error": "Insufficient current year data"}
    
    ytd_return = (ytd_data['close'].iloc[-1] / ytd_data['close'].iloc[0] - 1) * 100
    expected_ytd = sum(seasonal_stats.get(m, {}).get('mean_return', 0) for m in range(1, current_month + 1))
    
    # Historical YTD z-score
    historical_ytd = []
    for year in df['year'].unique():
        if year == current_year:
            continue
        year_data = df[(df['year'] == year) & (df['month'] <= current_month)]
        if len(year_data) >= 2:
            yr_return = (year_data['close'].iloc[-1] / year_data['close'].iloc[0] - 1) * 100
            historical_ytd.append(yr_return)
    
    ytd_z = (ytd_return - np.mean(historical_ytd)) / (np.std(historical_ytd) + 1e-9) if historical_ytd else 0
    current_stats = seasonal_stats.get(current_month, {})
    
    return {
        'current_month': datetime.now().strftime('%B'),
        'ytd_return_pct': round(ytd_return, 2),
        'expected_ytd_pct': round(expected_ytd, 2),
        'ytd_deviation_pct': round(ytd_return - expected_ytd, 2),
        'ytd_z_score': round(ytd_z, 2),
        'current_month_expected': round(current_stats.get('mean_return', 0), 2),
        'current_month_win_rate': round(current_stats.get('win_rate', 50), 1)
    }


def _classify_signal(context: Dict[str, Any], seasonal_stats: Dict[int, Dict[str, float]]) -> Dict[str, Any]:
    """Generate trading signal based on seasonal analysis."""
    ytd_z = context.get('ytd_z_score', 0)
    current_month = datetime.now().month
    
    # Next 3 months outlook
    upcoming = []
    for i in range(1, 4):
        next_month = (current_month + i - 1) % 12 + 1
        stats = seasonal_stats.get(next_month, {})
        upcoming.append({
            'month': datetime(2000, next_month, 1).strftime('%B'),
            'expected_return': round(stats.get('mean_return', 0), 2),
            'win_rate': round(stats.get('win_rate', 50), 1)
        })
    
    expected_3m = sum(m['expected_return'] for m in upcoming)
    avg_win_rate = np.mean([m['win_rate'] for m in upcoming])
    
    # Signal classification
    if expected_3m > 3 and avg_win_rate > 60:
        bias = "BULLISH"
        strength = "STRONG" if expected_3m > 5 else "MODERATE"
    elif expected_3m < -3 and avg_win_rate < 40:
        bias = "BEARISH"
        strength = "STRONG" if expected_3m < -5 else "MODERATE"
    else:
        bias = "NEUTRAL"
        strength = "WEAK"
    
    # Deviation signal
    if ytd_z > 2:
        deviation = "OVERBOUGHT (mean reversion down)"
    elif ytd_z < -2:
        deviation = "OVERSOLD (mean reversion up)"
    elif ytd_z > 1:
        deviation = "Above seasonal trend"
    elif ytd_z < -1:
        deviation = "Below seasonal trend"
    else:
        deviation = "In line with seasonal"
    
    return {
        'bias': bias,
        'strength': strength,
        '3m_expected_return': round(expected_3m, 2),
        '3m_avg_win_rate': round(avg_win_rate, 1),
        'upcoming_months': upcoming,
        'deviation_signal': deviation
    }


def _build_chart(symbol: str, seasonal_stats: Dict[int, Dict[str, float]], context: Dict[str, Any], chart_id: str = "commodity_seasonality") -> Dict[str, Any]:
    """Build seasonality visualization."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    months = list(range(1, 13))
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    returns = [seasonal_stats.get(m, {}).get('mean_return', 0) for m in months]
    win_rates = [seasonal_stats.get(m, {}).get('win_rate', 50) for m in months]
    colors = ['#22c55e' if r > 0 else '#ef4444' for r in returns]
    
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        subplot_titles=(f'{symbol} Average Monthly Returns (%)', 'Historical Win Rate (%)'),
        vertical_spacing=0.12
    )
    
    # Returns bar chart
    fig.add_trace(go.Bar(
        x=month_names, y=returns, marker_color=colors,
        text=[f'{r:+.1f}%' for r in returns], textposition='outside',
        name='Return', showlegend=False
    ), row=1, col=1)
    
    # Current month marker
    current_month = datetime.now().month
    fig.add_vline(x=current_month - 1, line_dash="dash", line_color="#3b82f6", 
                  annotation_text="NOW", row=1, col=1)
    
    # Win rate line
    fig.add_trace(go.Scatter(
        x=month_names, y=win_rates, mode='lines+markers',
        line=dict(color='#8b5cf6', width=2), marker=dict(size=8),
        name='Win Rate', showlegend=False
    ), row=2, col=1)
    
    fig.add_hline(y=50, line_dash="dot", line_color="#9ca3af", row=2, col=1)
    
    ytd_z = context.get('ytd_z_score', 0)
    ytd_ret = context.get('ytd_return_pct', 0)
    
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol} Seasonality</b> | YTD: {ytd_ret:+.1f}% | Z-Score: {ytd_z:.2f}",
            font=dict(size=14)
        ),
        height=450, template='plotly_white',
        margin=dict(t=60, b=40, l=50, r=30)
    )
    
    fig.update_yaxes(title_text="Return %", row=1, col=1)
    fig.update_yaxes(title_text="Win Rate %", range=[0, 100], row=2, col=1)
    
    # Return proper chart dict format for wrap_plotly_charts
    return {
        'id': chart_id,
        'title': f'{symbol} Seasonality Analysis',
        'plotly': fig.to_dict()
    }


def _format_monthly_table(seasonal_stats: Dict[int, Dict[str, float]]) -> str:
    """Format monthly patterns as markdown table."""
    rows = ["| Month | Avg Return | Win Rate | Best | Worst | N |",
            "|-------|-----------|----------|------|-------|---|"]
    
    for month in range(1, 13):
        stats = seasonal_stats.get(month, {})
        name = datetime(2000, month, 1).strftime('%b')
        avg = stats.get('mean_return', 0)
        wr = stats.get('win_rate', 50)
        best = stats.get('best_year', 0)
        worst = stats.get('worst_year', 0)
        n = stats.get('sample_size', 0)
        rows.append(f"| {name} | {avg:+.1f}% | {wr:.0f}% | {best:+.1f}% | {worst:+.1f}% | {n} |")
    
    return "\n".join(rows)


async def analyze_commodity_seasonality_internal(
    symbol: str,
    years_history: int = 2,
    generate_chart: bool = True
) -> dict:
    """
    Analyze historical seasonal patterns for any FMP commodity symbol.
    
    Args:
        symbol: FMP commodity symbol (e.g., GCUSD, SIUSD, CLUSD, NGUSD, HGUSD)
        years_history: Years of history (default 2, max 5)
        generate_chart: Generate visualization
    
    Returns:
        - monthly_table: Markdown table of monthly patterns
        - current_context: YTD vs seasonal expectations
        - signal: Forward-looking bias based on upcoming months
        - chart: Seasonality visualization
    """
    server = FMPAlternativesServer()
    
    try:
        await server.connect()
        
        # Clamp years
        years_history = min(max(years_history, 1), 5)
        
        logger.info(f"[SEASONALITY] Fetching {years_history}Y history for {symbol}")
        df = await _fetch_commodity_history(server, symbol, years_history)
        
        # ✅ CHECK CANCELLATION after data fetch
        _check_cancellation("after fetching commodity data")
        
        if len(df) < 60:
            return {"error": f"Insufficient data for {symbol}. Got {len(df)} days, need at least 60."}
        
        monthly_returns = _calculate_monthly_returns(df)
        seasonal_stats = _calculate_seasonal_stats(monthly_returns)
        context = _get_current_context(df, seasonal_stats)
        signal = _classify_signal(context, seasonal_stats)
        
        # Sorted best/worst months
        sorted_months = sorted(seasonal_stats.items(), key=lambda x: x[1].get('mean_return', 0), reverse=True)
        best_3 = [{'month': datetime(2000, m, 1).strftime('%B'), 'return': round(s['mean_return'], 2)} 
                  for m, s in sorted_months[:3]]
        worst_3 = [{'month': datetime(2000, m, 1).strftime('%B'), 'return': round(s['mean_return'], 2)} 
                   for m, s in sorted_months[-3:]]
        
        response = {
            "symbol": symbol,
            "analysis_period": f"{years_history} years",
            "data_points": len(df),
            "monthly_table": _format_monthly_table(seasonal_stats),
            "best_months": best_3,
            "worst_months": worst_3,
            "current_context": context,
            "signal": signal
        }
        
        if generate_chart:
            chart = _build_chart(symbol, seasonal_stats, context, chart_id=f"seasonality_{symbol.lower()}")
            response["charts"] = wrap_plotly_charts([chart], default_type="seasonality")
        
        return response
    
    except asyncio.CancelledError:
        logger.info("[CANCEL] Commodity seasonality analysis cancelled by user")
        raise  # Re-raise to propagate cancellation
    except Exception as e:
        logger.error(f"Seasonality analysis failed: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}
    finally:
        await server.cleanup()


@function_tool
async def analyze_commodity_seasonality(
    symbol: str,
    years_history: int = 2,
    generate_chart: bool = True
) -> dict:
    """
    Analyze historical seasonal patterns for any FMP commodity symbol.
    
    Args:
        symbol: FMP commodity symbol (e.g., GCUSD, SIUSD, CLUSD, NGUSD, HGUSD)
        years_history: Years of history (default 2, max 5)
        generate_chart: Generate visualization
    
    Returns:
        - monthly_table: Markdown table of monthly patterns
        - current_context: YTD vs seasonal expectations
        - signal: Forward-looking bias based on upcoming months
        - chart: Seasonality visualization
    """
    from core.utils.risk_adapter import jsonify_results
    result = await analyze_commodity_seasonality_internal(
        symbol=symbol,
        years_history=years_history,
        generate_chart=generate_chart
    )
    return jsonify_results(result)
