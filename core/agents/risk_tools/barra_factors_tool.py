"""
Barra Factor Analysis Tool
"""

from agents import function_tool
from typing import List, Optional
import logging
import json

from core.risk_modules.barra_factor import BarraFactorModel
from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns, jsonify_results
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.constants import DEFAULT_PERIOD
from .shared import fetch_market_data_batch, sanitize_tool_output, register_chart_handle, resolve_portfolio_tickers
from core.charts.builders.advanced import build_factor_exposure
from core.charts.models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


@function_tool
async def analyze_barra_factors(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    custom_factors: Optional[str] = None
) -> dict:
    """
    Analyze factor exposures using Barra-style factor model. 
    Decomposes returns into exposures to market, size, value, momentum, quality, and volatility factors.
    
    Args:
        tickers: List of ticker symbols to analyze. OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers from. Use this OR tickers, not both.
        period: Historical data period. Use '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'. Default: '1y'
        start_date: OPTIONAL - Start date in YYYY-MM-DD format (e.g., '2023-01-01').
                    ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        end_date: OPTIONAL - End date in YYYY-MM-DD format (e.g., '2024-01-01').
                  ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        custom_factors: OPTIONAL - JSON string of custom factor ETFs like '{"SPY": "Market", "XLF": "Financials"}'. OMIT for default factors.
    
    Returns:
        JSON string with factor exposures, R-squared values, risk attribution, and factor contribution charts
        
    Examples:
        ✅ CORRECT: analyze_barra_factors(portfolio_id="my_portfolio", period="2y")
        ✅ CORRECT: analyze_barra_factors(tickers=["AAPL", "JPM"], period="2y")
        ✅ CORRECT: analyze_barra_factors(tickers=["TSLA"], start_date="2023-01-01", end_date="2024-01-01")
        ❌ WRONG: DO NOT pass "null", "undefined", or empty strings for optional parameters
    """
    market_server = None
    portfolio_weights = None
    
    try:
        # Resolve tickers from portfolio if portfolio_id provided
        if portfolio_id:
            try:
                tickers, portfolio_weights = await resolve_portfolio_tickers(portfolio_id)
                logger.info(f"Loaded {len(tickers)} tickers from portfolio '{portfolio_id}'")
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'error_type': 'portfolio_error',
                    'calculation_type': 'barra_factors'
                }
        
        # Validate we have tickers
        if not tickers:
            return {
                'status': 'error',
                'error': 'Either tickers or portfolio_id must be provided',
                'error_type': 'validation_error',
                'calculation_type': 'barra_factors'
            }
        
        # Create MCP server for data fetching (FMP as primary source)
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Parse custom factors if provided
        factor_etfs = None
        if custom_factors:
            factor_etfs = json.loads(custom_factors)
        
        # Create Barra model
        barra_model = BarraFactorModel(custom_factors=factor_etfs)
        
        # Get the factor ETFs to fetch
        factors_to_fetch = list(barra_model.FACTOR_ETFS.keys())
        all_tickers = tickers + factors_to_fetch
        
        # Sanitize date parameters to handle LLM passing "null" strings
        from .shared import sanitize_date_param
        start_date = sanitize_date_param(start_date)
        end_date = sanitize_date_param(end_date)

        # Use parallel batch fetching for better performance and cancellation support
        # This replaces the old sequential loop - much faster for 40+ tickers!
        combined_data = await fetch_market_data_batch(market_server, all_tickers, period, start_date, end_date)
        
        # Adapt to price DataFrame
        prices = adapt_mcp_to_prices(combined_data, all_tickers)
        
        # Get actual tickers that have data (may be subset of requested)
        actual_portfolio_tickers = [t for t in tickers if t in prices.columns]
        actual_factor_tickers = [t for t in factors_to_fetch if t in prices.columns]
        
        if len(actual_portfolio_tickers) == 0:
            raise ValueError(f"No portfolio tickers have sufficient data. Requested: {tickers}")
        if len(actual_factor_tickers) == 0:
            raise ValueError(f"No factor tickers have data. Cannot perform factor analysis.")
        
        # Separate portfolio and factor prices (only those with data)
        portfolio_prices = prices[actual_portfolio_tickers]
        factor_prices = prices[actual_factor_tickers]
        
        # Log if tickers were excluded
        if len(actual_portfolio_tickers) < len(tickers):
            excluded = set(tickers) - set(actual_portfolio_tickers)
            logger.info(f"Excluded portfolio tickers: {', '.join(excluded)}")
        
        # Calculate returns
        returns = prepare_returns(portfolio_prices)
        
        # Estimate factor model
        results = barra_model.estimate_factor_model(returns, portfolio_prices, factor_prices=factor_prices)
        
        # Calculate portfolio-level aggregate exposures if we have weights
        portfolio_risk_decomposition = None
        if portfolio_weights:
            import numpy as np
            # Build weights array aligned to actual_portfolio_tickers
            weights_array = np.array([portfolio_weights.get(t, 0) for t in actual_portfolio_tickers])
            # Normalize weights to sum to 1 (in case some tickers were excluded)
            if weights_array.sum() > 0:
                weights_array = weights_array / weights_array.sum()
            try:
                portfolio_risk_decomposition = barra_model.calculate_portfolio_risk(weights_array)
                logger.info(f"Calculated aggregate portfolio exposures: {list(portfolio_risk_decomposition.get('portfolio_betas', {}).keys())}")
            except Exception as e:
                logger.warning(f"Failed to calculate portfolio-level risk: {e}")
        
        # Format results
        factor_exposures = {}
        if results and 'factor_exposures' in results:
            # Convert DataFrame to dict for JSON serialization
            exposures_data = results['factor_exposures']
            if isinstance(exposures_data, dict):
                for ticker in tickers:
                    if ticker in exposures_data:
                        factor_exposures[ticker] = exposures_data[ticker]
            else:
                for ticker in tickers:
                    if ticker in exposures_data.index:
                        factor_exposures[ticker] = exposures_data.loc[ticker].to_dict()
        
        r_squared = {}
        if results and 'r_squared' in results:
            r_squared_series = results['r_squared']
            for ticker in tickers:
                if ticker in r_squared_series.index:
                    r_squared[ticker] = float(r_squared_series[ticker])
        
        # Generate chart directly (no tool calls)
        chart = None
        try:
            # Convert factor exposures to heatmap format
            if factor_exposures and tickers:
                # Get factor names from first ticker
                first_ticker = next(iter(factor_exposures.keys())) if factor_exposures else None
                factor_names = list(factor_exposures[first_ticker].keys()) if first_ticker and first_ticker in factor_exposures else []

                # Create exposure matrix (assets x factors)
                exposures_matrix = []
                for ticker in tickers:
                    if ticker in factor_exposures:
                        row = [factor_exposures[ticker].get(factor, 0.0) for factor in factor_names]
                        exposures_matrix.append(row)
                    else:
                        exposures_matrix.append([0.0] * len(factor_names))
            else:
                factor_names = []
                exposures_matrix = []

            # Build chart spec with correct format
            # Truncate ticker list for title if too long
            ticker_display = ', '.join(actual_portfolio_tickers[:5])
            if len(actual_portfolio_tickers) > 5:
                ticker_display += f" +{len(actual_portfolio_tickers) - 5} more"
            
            chart_spec = ChartSpec(
                id=f"factor_{abs(hash(str(tickers)))&0xFFFFFF:06x}",
                type=ChartType.FACTOR_EXPOSURE,
                title=f"Factor Exposures - {ticker_display}",
                inputs={
                    'factors': factor_names,
                    'tickers': tickers,
                    'exposures': exposures_matrix
                },
                priority=ChartPriority.HIGH,
                options=None
            )
            
            # Call builder directly
            chart_figure = await build_factor_exposure(chart_spec, {})
            
            if chart_figure:
                chart = register_chart_handle(
                    chart_figure.plotly,
                    chart_type=ChartType.FACTOR_EXPOSURE.value,
                    title=chart_figure.title,
                    alt_text=chart_figure.alt_text,
                    metadata=chart_figure.metadata,
                    chart_id=chart_figure.id
                )
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            # Continue without chart
        
        result_data = {
            'status': 'success',
            'factor_analysis': {
                'factor_exposures': factor_exposures,
                'r_squared': r_squared,
                'factors_used': barra_model.FACTOR_ETFS
            },
            'tickers': tickers,
            'period': period if not (start_date and end_date) else f"{start_date} to {end_date}",
            'charts': [chart] if chart else []
        }
        
        # Add portfolio info if loaded from portfolio
        if portfolio_id:
            result_data['portfolio_id'] = portfolio_id
        if portfolio_weights:
            result_data['weights'] = portfolio_weights
        
        # Add aggregate portfolio-level exposures (the main value-add for portfolios)
        if portfolio_risk_decomposition:
            result_data['portfolio_aggregate'] = {
                'portfolio_betas': portfolio_risk_decomposition.get('portfolio_betas', {}),
                'total_risk': portfolio_risk_decomposition.get('total_risk'),
                'factor_risk': portfolio_risk_decomposition.get('factor_risk'),
                'specific_risk': portfolio_risk_decomposition.get('specific_risk'),
                'factor_contributions': portfolio_risk_decomposition.get('factor_contributions', {}),
                'risk_decomposition': portfolio_risk_decomposition.get('risk_decomposition', {})
            }
        
        normalized = jsonify_results(result_data)
        
        # Return directly - sanitizer was causing SDK to hang
        return normalized
        
    except Exception as e:
        logger.error(f"Barra factor analysis with data failed: {e}")
        error_type = 'factor_error' if 'factor' in str(e).lower() else 'general_error'
        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'barra_factors'
        }
    finally:
        # Cleanup FMP server connection
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")
