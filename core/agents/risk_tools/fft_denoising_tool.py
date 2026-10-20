"""
FFT Denoising Tool for Signal Processing
Based on StockPredictionAI approach
Following comps_tool.py pattern for FMP integration
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import pandas as pd
from scipy.fft import fft, ifft, fftfreq
from dotenv import load_dotenv

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.risk_tools.shared import register_chart_handle
from core.charts.builders.market import build_price_compare
from core.charts.models import ChartSpec, ChartType, ChartPriority
from core.utils.risk_adapter import jsonify_results

load_dotenv()
logger = logging.getLogger(__name__)


async def analyze_fft_trends_internal(
    tickers: List[str],
    components: List[int] = None,
    period: str = "1Y"
) -> Dict[str, Any]:
    """
    Internal version for Canvas integration.
    Apply FFT denoising to extract trends and identify cycles in price data.

    Args:
        tickers: Stock symbols to analyze
        components: Frequency component counts to keep (default: [3, 6, 9, 100])
        period: Historical period to analyze (default: "1Y"). Use "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"

    Returns:
        Raw dictionary with denoised trends, dominant cycles, and chart data
    """
    try:
        if components is None:
            components = [3, 6, 9, 100]

        fmp_server = FMPMarketDataServer()
        results = {}

        try:
            await fmp_server.connect()

            for ticker in tickers:
                # Fetch via MCP tool
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })

                if not result or not hasattr(result, 'content'):
                    raise ValueError(f"No data for {ticker}")

                data = safe_parse_json(result)

                # FMP returns format: {"dates": [...], "prices": [...], ...}
                # Convert to list of dicts for DataFrame
                if not data or "dates" not in data:
                    raise ValueError(f"No date data for {ticker}")

                dates = data.get("dates", [])
                prices = data.get("prices", []) or data.get("closes", [])

                if not dates or not prices or len(dates) < 50:
                    raise ValueError(f"Insufficient data: {len(dates)} points")

                # Create DataFrame from parallel arrays
                df = pd.DataFrame({
                    "date": dates,
                    "close": prices
                })

                # Find columns dynamically
                date_col = next((c for c in df.columns if any(k in c.lower() for k in ['date', 'time'])), df.columns[0])
                price_col = next((c for c in df.columns if any(k in c.lower() for k in ['close', 'price'])), df.columns[-1])

                df[date_col] = pd.to_datetime(df[date_col])
                df = df.sort_values(date_col)

                close_prices = df[price_col].values
                dates = df[date_col]

                # Handle NaN
                if np.isnan(close_prices).any():
                    close_prices = pd.Series(close_prices).fillna(method='ffill').values

                # FFT decomposition
                close_fft = fft(close_prices)
                amplitudes = np.abs(close_fft)
                frequencies = fftfreq(len(close_prices), d=1.0)

                # Find dominant frequencies
                sorted_indices = np.argsort(amplitudes)[::-1]
                dominant_freq_indices = sorted_indices[1:11]
                dominant_frequencies = frequencies[dominant_freq_indices].tolist()
                dominant_periods = [abs(1/f) if f != 0 else 0 for f in dominant_frequencies]

                # Reconstruct for each component level
                fft_components_result = {}
                denoised_signal = None

                for n_components in components:
                    # Cap at Nyquist limit
                    max_comp = len(close_prices) // 2
                    actual_comp = min(n_components, max_comp)

                    # Filter: keep DC + top N components
                    fft_filtered = np.zeros_like(close_fft)
                    fft_filtered[0] = close_fft[0]  # DC component

                    top_indices = sorted_indices[1:actual_comp+1]
                    fft_filtered[top_indices] = close_fft[top_indices]

                    # Mirror for negative frequencies
                    if actual_comp > 0:
                        fft_filtered[-actual_comp:] = np.conj(
                            fft_filtered[1:actual_comp+1][::-1]
                        )

                    # Reconstruct
                    reconstructed = np.real(ifft(fft_filtered))

                    # Calculate average period captured by this component level
                    avg_period = np.mean([
                        abs(1/frequencies[idx])
                        for idx in top_indices
                        if frequencies[idx] != 0
                    ])

                    fft_components_result[str(n_components)] = {
                        "trend_data": reconstructed.tolist(),
                        "avg_period_days": float(avg_period),
                        "components_used": actual_comp
                    }

                    if n_components == max(components):
                        denoised_signal = reconstructed

                # Noise metrics
                if denoised_signal is None:
                    logger.warning("Denoised signal not set; defaulting to original prices for noise metrics")
                    denoised_signal = close_prices

                original_variance = float(np.var(close_prices))
                noise_variance = float(np.var(close_prices - denoised_signal))

                if original_variance > 0:
                    noise_remaining_ratio = noise_variance / original_variance
                    noise_reduction_pct = (1 - noise_remaining_ratio) * 100
                else:
                    noise_reduction_pct = 0.0

                # Downsample data if too large to avoid ChartSpec validation error
                # Target: ~150 points max to stay well under 100KB limit
                num_points = len(close_prices)
                max_points = 150
                
                if num_points > max_points:
                    # Sample every Nth point
                    step = num_points // max_points
                    indices = list(range(0, num_points, step))[:max_points]
                    sampled_prices = close_prices[indices].tolist()
                    sampled_dates = dates.iloc[indices].dt.strftime('%Y-%m-%d').tolist()
                else:
                    sampled_prices = close_prices.tolist()
                    sampled_dates = dates.dt.strftime('%Y-%m-%d').tolist()
                    indices = list(range(num_points))

                # Build chart with original + all component levels (sampled)
                prices_dict = {
                    f"{ticker} Original": sampled_prices
                }
                symbols_list = [f"{ticker} Original"]

                # Add each component level to the chart (sampled)
                for n_comp in components:
                    comp_data = fft_components_result[str(n_comp)]
                    label = f"{ticker} ({n_comp} comp)"
                    trend_array = np.array(comp_data["trend_data"])
                    sampled_trend = trend_array[indices].tolist() if num_points > max_points else comp_data["trend_data"]
                    prices_dict[label] = sampled_trend
                    symbols_list.append(label)

                # Chart specification
                chart_spec = ChartSpec(
                    id=f"fft_{ticker.lower()}_{abs(hash(str([ticker, components])))&0xFFFF:04x}",
                    type=ChartType.PRICE_OVERLAY_COMPARE,
                    title=f"FFT Denoising - {ticker} (Multi-Timeframe Trends)",
                    inputs={
                        'symbols': symbols_list,
                        'prices_dict': prices_dict,
                        'dates': sampled_dates
                    },
                    priority=ChartPriority.HIGH
                )

                try:
                    chart_figure = await build_price_compare(chart_spec, {})
                    chart = register_chart_handle(
                        chart_figure.plotly,
                        chart_type=ChartType.PRICE_OVERLAY_COMPARE.value,
                        title=chart_figure.title,
                        alt_text=chart_figure.alt_text,
                        metadata=chart_figure.metadata,
                        chart_id=chart_figure.id
                    ) if chart_figure else None
                except Exception as e:
                    logger.warning(f"Chart generation failed for {ticker}: {e}")
                    chart = None

                results[ticker] = {
                    'fft_components': fft_components_result,
                    'denoised_price': denoised_signal.tolist(),
                    'original_prices': close_prices.tolist(),
                    'dominant_frequencies': dominant_frequencies,
                    'dominant_periods_days': dominant_periods,
                    'noise_reduction_pct': round(noise_reduction_pct, 2),
                    'dates': dates.dt.strftime('%Y-%m-%d').tolist(),
                    'chart': chart
                }

            all_charts = [r['chart'] for r in results.values() if r.get('chart')]

            return {
                'status': 'success',
                'results': results,
                'tickers': tickers,
                'components': components,
                'period': period,
                'charts': all_charts
            }

        except Exception as e:
            logger.error(f"FFT failed: {e}")
            error_type = 'data_error' if any(
                kw in str(e).lower() for kw in ['no data', 'insufficient']
            ) else 'general_error'

            return {
                'status': 'error',
                'error': str(e),
                'error_type': error_type,
                'calculation_type': 'fft_denoising'
            }

    except Exception as e:
        logger.error(f"FFT denoising failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'calculation_type': 'fft_denoising'
        }


@function_tool
async def analyze_fft_trends(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    components: List[int] = None,
    period: str = "1Y"
) -> dict:
    """
    Apply FFT denoising to extract trends and identify cycles in price data.

    Args:
        tickers: Stock symbols to analyze. OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers from.
        components: Frequency component counts to keep (default: [3, 6, 9, 100])
        period: Historical period to analyze (default: "1Y"). Use "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"

    Returns:
        Dict with denoised trends, dominant cycles, and charts
        
    Examples:
        ✅ CORRECT: analyze_fft_trends(portfolio_id="my_portfolio")
        ✅ CORRECT: analyze_fft_trends(tickers=["AAPL", "MSFT"], period="2Y")
    """
    from .shared import resolve_portfolio_tickers
    
    # Resolve tickers from portfolio if portfolio_id provided
    if portfolio_id:
        try:
            tickers, _ = await resolve_portfolio_tickers(portfolio_id)
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'error_type': 'portfolio_error',
                'calculation_type': 'fft_denoising'
            }
    
    # Validate we have tickers
    if not tickers:
        return {
            'status': 'error',
            'error': 'Either tickers or portfolio_id must be provided',
            'error_type': 'validation_error',
            'calculation_type': 'fft_denoising'
        }
    
    result = await analyze_fft_trends_internal(tickers, components, period)
    return jsonify_results(result)
