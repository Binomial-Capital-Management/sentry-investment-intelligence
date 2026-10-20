"""
Comparable Companies Analysis Tool

Production-grade trading multiples analysis with football field visualization.
Compares a target company against peers across valuation metrics to derive PRICE TARGETS.
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import asyncio
import pandas as pd
import numpy as np

from core.valuation_modules.comparable_analysis import ComparableAnalysis
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# Formatting configuration
DECIMAL_PLACES_RATIO = 2
DECIMAL_PLACES_PERCENT = 1
MAX_CONCURRENT_FETCHES = 10


async def analyze_comparable_companies_internal(
    target_ticker: str,
    peer_tickers: List[str],
    fields: List[str],
    include_football_field: bool = True,
    percentiles: Optional[List[float]] = None,
) -> dict:
    """Internal callable for Canvas - same logic as analyze_comparable_companies."""
    fmp_server = None
    
    try:
        # Validate inputs
        if not target_ticker or not target_ticker.strip():
            raise ValueError("target_ticker is required")
        
        target_ticker = target_ticker.strip().upper()
        
        if not peer_tickers or len(peer_tickers) == 0:
            raise ValueError("At least one peer_ticker is required")
        
        peer_tickers = [p.strip().upper() for p in peer_tickers if p and p.strip()]
        
        # Remove duplicates and exclude target from peers
        peer_tickers = list(dict.fromkeys(peer_tickers))  # Preserve order, remove dupes
        peer_tickers = [p for p in peer_tickers if p != target_ticker]
        
        if not peer_tickers:
            raise ValueError("No valid peer tickers after removing duplicates and target")
        
        if not fields or len(fields) == 0:
            raise ValueError(
                "fields parameter is required. Use discover_valuation_fields to find "
                "available fields. Common fields: peRatio, evToEbitda, priceToBookRatio, "
                "priceToSalesRatio. MUST include 'price' for fair value calculations."
            )
        
        # Ensure price is included for fair value calculations
        if "price" not in fields:
            fields = ["price"] + list(fields)
            logger.info("Added 'price' field for fair value calculations")
        
        all_tickers = [target_ticker] + peer_tickers
        logger.info(f"Starting comps analysis: {target_ticker} vs {len(peer_tickers)} peers, {len(fields)} fields")
        
        # Initialize FMP server
        fmp_server = FMPMarketDataServer()
        await fmp_server.connect()
        
        # Fetch data for all tickers with bounded concurrency
        ticker_data, fetch_errors = await _fetch_all_ticker_data(
            fmp_server, all_tickers, fields
        )
        
        # Log any fetch issues
        if fetch_errors:
            for ticker, error in fetch_errors.items():
                logger.warning(f"Fetch issue for {ticker}: {error}")
        
        # Validate we have target data
        if target_ticker not in ticker_data or "error" in ticker_data.get(target_ticker, {}):
            error_msg = ticker_data.get(target_ticker, {}).get("error", "No data returned")
            raise ValueError(f"Failed to fetch target {target_ticker}: {error_msg}")
        
        # Count successful peers
        successful_peers = [
            p for p in peer_tickers 
            if p in ticker_data and "error" not in ticker_data.get(p, {})
        ]
        
        if len(successful_peers) == 0:
            raise ValueError(f"No peer data available. All peers failed: {fetch_errors}")
        
        if len(successful_peers) < len(peer_tickers):
            failed = set(peer_tickers) - set(successful_peers)
            logger.warning(f"Proceeding with {len(successful_peers)} peers. Failed: {failed}")
        
        # Initialize analyzer
        if percentiles is None:
            percentiles = [10, 25, 50, 75, 90]
        
        comp_analyzer = ComparableAnalysis(percentiles=percentiles)
        
        # Run analysis
        valuation_data = {"ticker_data": ticker_data}
        results = comp_analyzer.analyze_comparables(
            target=target_ticker,
            peers=successful_peers,
            data=valuation_data,
            method="all"
        )
        
        # Format comparison table for output
        results = _format_results_for_output(results)
        
        # Calculate fair value (PRICE TARGETS)
        if "field_statistics" in results:
            fair_value = comp_analyzer.calculate_simple_fair_value(
                target_data=ticker_data.get(target_ticker, {}),
                field_stats=results["field_statistics"]
            )
            if fair_value:
                results["fair_value"] = fair_value
        
        # Ensure football_field is present and populated
        if include_football_field:
            if "football_field" not in results or not results.get("football_field", {}).get("methods"):
                # Regenerate football field if missing
                football_field = comp_analyzer._generate_football_field(
                    target_ticker,
                    ticker_data.get(target_ticker, {}),
                    results.get("field_statistics", {})
                )
                results["football_field"] = football_field
        else:
            # Remove if not requested
            results.pop("football_field", None)
        
        # Generate football field chart
        charts = []
        if include_football_field and results.get("football_field", {}).get("methods"):
            chart = _build_football_field_chart(results["football_field"], target_ticker)
            if chart:
                # wrap_plotly_charts automatically handles caching via register_chart_handle
                charts = wrap_plotly_charts([chart], default_type="football_field")

        # Build response
        response = {
            "status": "success",
            "comp_results": results,
            "target": target_ticker,
            "peers": successful_peers,
            "peers_requested": len(peer_tickers),
            "peers_successful": len(successful_peers),
            "fields_requested": fields,
            "charts": charts,
        }
        
        # Include failed peers info if any
        failed_peers = list(set(peer_tickers) - set(successful_peers))
        if failed_peers:
            response["failed_peers"] = failed_peers
            response["fetch_errors"] = {p: fetch_errors.get(p, "Unknown error") for p in failed_peers}
        
        logger.info(f"Comps analysis complete: {target_ticker} vs {len(successful_peers)} peers")
        
        return response
        
    except ValueError as e:
        # User/input errors - return structured error
        logger.warning(f"Comps validation error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": "validation_error",
            "target": target_ticker if target_ticker else None,
        }
        
    except Exception as e:
        # Unexpected errors
        logger.error(f"Comps analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": "analysis_error",
            "target": target_ticker if target_ticker else None,
        }
        
    finally:
        if fmp_server is not None:
            try:
                await fmp_server.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up FMP server: {e}")


@function_tool
async def analyze_comparable_companies(
    target_ticker: str,
    peer_tickers: List[str],
    fields: List[str],
    include_football_field: bool = True,
    percentiles: Optional[List[float]] = None,
) -> dict:
    """
    Comparable companies valuation analysis - derives PRICE TARGETS from peer multiples.
    
    Args:
        target_ticker: Target company ticker (e.g., "CRM")
        peer_tickers: Peer companies (e.g., ["NOW", "WDAY", "ADBE"])
        fields: FMP fields to fetch. MUST include "price" + multiples like peRatio, evToEbitda
        include_football_field: Include football field visualization data (default: True)
        percentiles: Percentile levels for ranges (default: [10, 25, 50, 75, 90])
    
    Returns comparison_table_formatted, fair_value with price targets, and football_field data.
    
    AGENT INSTRUCTIONS:
    - Present a markdown comparison table from comparison_table_formatted
    - Present a price target table (bear/base/bull) from fair_value.valuations_by_multiple
    - Present a football field showing valuation ranges from football_field.methods
    - Show current price vs fair value with upside/downside %
    """
    return await analyze_comparable_companies_internal(
        target_ticker=target_ticker,
        peer_tickers=peer_tickers,
        fields=fields,
        include_football_field=include_football_field,
        percentiles=percentiles,
    )


async def _fetch_all_ticker_data(
    fmp_server: FMPMarketDataServer,
    tickers: List[str],
    fields: List[str]
) -> tuple[Dict[str, Dict], Dict[str, str]]:
    """
    Fetch data for all tickers with bounded concurrency.
    
    Returns:
        Tuple of (ticker_data dict, errors dict)
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
    errors = {}
    
    async def fetch_single(ticker: str) -> tuple[str, Dict]:
        async with semaphore:
            try:
                # FMP requires period and limit in nested "params" for ratios/key-metrics endpoints
                result = await fmp_server.call_tool("get_fields", {
                    "symbol": ticker,
                    "fields": fields,
                    "params": {"period": "annual", "limit": 1}
                })
                
                if result is None:
                    errors[ticker] = "Null response from server"
                    return ticker, {"error": "Null response"}
                
                if result.isError:
                    error_text = "API error"
                    if hasattr(result, 'content') and result.content:
                        error_text = str(result.content[0].get("text", "API error"))
                    errors[ticker] = error_text
                    return ticker, {"error": error_text}
                
                if not hasattr(result, 'content'):
                    errors[ticker] = "No content in response"
                    return ticker, {"error": "No content"}
                
                data = safe_parse_json(result)
                
                # Log metadata if present
                if "metadata" in data:
                    meta = data["metadata"]
                    logger.debug(
                        f"{ticker}: {meta.get('api_calls', 0)} API calls, "
                        f"cache={meta.get('cache_used', False)}"
                    )
                
                # Extract data payload
                payload = data.get("data", data)
                
                # Check if payload has any actual values
                if not payload:
                    errors[ticker] = "No field values returned"
                    return ticker, {"error": "Empty data"}
                
                return ticker, payload
                
            except asyncio.TimeoutError:
                errors[ticker] = "Request timeout"
                return ticker, {"error": "Timeout"}
                
            except Exception as e:
                errors[ticker] = str(e)
                logger.error(f"Error fetching {ticker}: {e}")
                return ticker, {"error": str(e)}
    
    # Fetch all in parallel with semaphore limiting
    results = await asyncio.gather(*[fetch_single(t) for t in tickers])
    ticker_data = dict(results)
    
    return ticker_data, errors


def _format_results_for_output(results: Dict[str, Any]) -> Dict[str, Any]:
    """Format results for clean JSON output."""
    
    # Format comparison table
    if "comparison_table" in results and hasattr(results["comparison_table"], 'to_dict'):
        df = results["comparison_table"]
        
        table_data = []
        for company in df.index:
            row = {"Company": str(company)}
            for col in df.columns:
                value = df.loc[company, col]
                # Handle scalar values only - reject Series/arrays
                if isinstance(value, (list, tuple)) or (hasattr(value, '__iter__') and not isinstance(value, (str, bytes))):
                    row[col] = "N/A"
                elif pd.isna(value):
                    row[col] = "N/A"
                elif isinstance(value, (int, float, np.number)):
                    try:
                        row[col] = round(float(value), DECIMAL_PLACES_RATIO)
                    except (TypeError, ValueError):
                        row[col] = "N/A"
                else:
                    row[col] = value
            table_data.append(row)
        
        results["comparison_table_formatted"] = table_data
        results["comparison_table_columns"] = ["Company"] + list(df.columns)
        # Use 'records' instead of 'index' to avoid duplicate index errors
        results["comparison_table"] = df.reset_index().to_dict("records")
    
    # Format key metrics table
    if "field_statistics" in results:
        key_metrics_table = []
        for field, stats in results["field_statistics"].items():
            if stats.get("target_value") is not None:
                metric_row = {
                    "Metric": field,
                    "Target": _format_number(stats.get("target_value")),
                    "Peer Median": _format_number(stats.get("median")),
                    "Peer Mean": _format_number(stats.get("mean")),
                    "Peer Min": _format_number(stats.get("min")),
                    "Peer Max": _format_number(stats.get("max")),
                    "Target Percentile": f"{stats.get('target_percentile', 'N/A')}%",
                    "vs Median": f"{stats.get('target_vs_median_pct', 'N/A'):+.1f}%" if stats.get('target_vs_median_pct') is not None else "N/A",
                }
                key_metrics_table.append(metric_row)
        
        if key_metrics_table:
            results["key_metrics_table"] = key_metrics_table
    
    return results


def _format_number(value: Any) -> Any:
    """Format a number for display."""
    if value is None:
        return "N/A"
    # Reject arrays/Series - only format scalars
    if isinstance(value, (list, tuple)) or (hasattr(value, '__iter__') and not isinstance(value, (str, bytes))):
        return "N/A"
    if isinstance(value, (int, float, np.number)):
        try:
            if not np.isfinite(value):
                return "N/A"
            return round(float(value), DECIMAL_PLACES_RATIO)
        except (TypeError, ValueError):
            return "N/A"
    return value


def _build_football_field_chart(football_field: Dict[str, Any], target: str) -> Dict[str, Any]:
    """
    Build a football field chart showing valuation ranges from comparable companies.
    
    Args:
        football_field: Football field data with methods, current_price, etc.
        target: Target company ticker
        
    Returns:
        Chart dict with id, title, and plotly figure
    """
    methods = football_field.get('methods', [])
    current_price = football_field.get('current_price')
    composite = football_field.get('composite_fair_value', {})
    
    if not methods:
        return None
    
    # Reverse order to match typical top-to-bottom reading (first method at top)
    methods_rev = list(reversed(methods))

    # Clean up method names for display
    def clean_method_name(raw: str) -> str:
        """Convert technical field names to readable labels."""
        name_map = {
            'Comps: price': 'Market Price',
            'priceToBookRatioTTM': 'P/B Ratio',
            'priceToEarningsRatioTTM': 'P/E Ratio',
            'priceToSalesRatioTTM': 'P/S Ratio',
            'evToEBITDATTM': 'EV/EBITDA',
            'priceToFreeCashFlowsRatioTTM': 'P/FCF Ratio',
            'priceToOperatingCashFlowsRatioTTM': 'P/OCF Ratio',
            'priceCashFlowRatioTTM': 'Price/Cash Flow',
        }
        return name_map.get(raw, raw)

    method_names = [clean_method_name(m.get('method', 'Unknown')) for m in methods_rev]
    low_values = [m.get('low', 0.0) for m in methods_rev]
    high_values = [m.get('high', 0.0) for m in methods_rev]
    
    # Create figure
    fig = go.Figure()

    # 1. The Range Bars (Floating Bars)
    # We use a Bar trace with 'base' set to the low value, and 'x' as the width (high - low)
    fig.add_trace(go.Bar(
        y=method_names,
        x=[h - l for h, l in zip(high_values, low_values)],
        base=low_values,
        orientation='h',
        marker=dict(
            color='#4472c4',  # Standard professional blue
            line=dict(color='#2c5aa0', width=1)  # Border for visibility
        ),
        name='Valuation Range',
        hoverinfo='y+text',
        hovertext=[f"{m}: ${l:.2f} - ${h:.2f}" for m, l, h in zip(method_names, low_values, high_values)]
    ))

    # 2. Labels on the Left (Low Values) - positioned outside bars
    for i, (name, val) in enumerate(zip(method_names, low_values)):
        fig.add_annotation(
            x=val,
            y=name,
            text=f"${val:.2f}",
            showarrow=False,
            xanchor="right",
            xshift=-5,  # Shift left of bar start
            font=dict(size=10, color="#333333")
        )

    # 3. Labels on the Right (High Values) - positioned outside bars
    for i, (name, val) in enumerate(zip(method_names, high_values)):
        fig.add_annotation(
            x=val,
            y=name,
            text=f"${val:.2f}",
            showarrow=False,
            xanchor="left",
            xshift=5,  # Shift right of bar end
            font=dict(size=10, color="#333333")
        )
    
    # 4. Current Price Line
    if current_price is not None and current_price > 0:
        fig.add_vline(
            x=current_price,
            line_dash="dash",
            line_color="#DC2626",  # Red
            line_width=1,
            annotation=dict(
                text=f"Current share price ${current_price:.2f}",
                textangle=0,
                xanchor="left",
                yanchor="bottom",
                yref="paper",
                y=0,
                yshift=-20,
                font=dict(size=10, color="#DC2626", weight="bold")
            )
        )
    
    # 5. Composite Mean Line (Optional)
    if composite and composite.get('mean'):
        composite_mean = composite['mean']
        # Only add if distinguishable from current price (avoid clutter)
        if current_price and abs(composite_mean - current_price) / current_price > 0.02:
            fig.add_vline(
                x=composite_mean,
                line_dash="dot",
                line_color="#7C3AED",  # Purple
                line_width=1,
                opacity=0.7,
                annotation=dict(
                    text=f"Avg: ${composite_mean:.2f}",
                    textangle=0,
                    xanchor="left",
                    yanchor="top",
                    yref="paper",
                    y=1,
                    font=dict(size=9, color="#7C3AED")
                )
            )
    
    # Update layout
    fig.update_layout(
        title=dict(
            text="Football field - stock price range",
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title="",
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            tickprefix="$",
        ),
        yaxis=dict(
            showgrid=False,
            showline=False,
            automargin=True
        ),
        barmode='overlay',
        bargap=0.15,  # Reduce gap between bars to make them thicker
        plot_bgcolor='white',
        margin=dict(l=150, r=80, t=60, b=60),
        height=max(400, len(methods) * 60),
        showlegend=False,
        template="plotly_white"
    )
    
    # Adjust x-axis range to fit labels
    all_values = low_values + high_values
    if current_price:
        all_values.append(current_price)
    
    if all_values:
        min_val = min(all_values)
        max_val = max(all_values)
        padding = (max_val - min_val) * 0.15
        fig.update_xaxes(range=[max(0, min_val - padding), max_val + padding])

    # Return chart dict for wrap_plotly_charts
    return {
        'id': f'football_field_{target.lower()}',
        'title': f'Football Field Valuation - {target}',
        'plotly': fig.to_dict()
    }


