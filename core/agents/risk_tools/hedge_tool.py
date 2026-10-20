"""
Stress Test and Hedge Portfolio Tool
"""

from agents import function_tool
from typing import List, Optional
import numpy as np
import logging
import json

from core.risk_modules.barra_factor import BarraFactorModel
from core.risk_modules.hedge_portfolio import HedgePortfolioOptimizer
from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns, jsonify_results
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.constants import DEFAULT_PERIOD, HEDGE_RISK_MULTIPLIERS
from .shared import fetch_market_data_batch, sanitize_tool_output, register_chart_handle
from core.charts.builders.portfolio import build_correlation_matrix
from core.charts.models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


async def create_hedge_portfolio_internal(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_betas: Optional[str] = None,
    hedge_strategy: str = "market_neutral"
) -> dict:
    """Internal callable for Canvas - same logic as create_hedge_portfolio."""
    market_server = None
    try:
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        if weights is None:
            weights = np.array([1.0 / len(tickers)] * len(tickers))
        else:
            weights = np.array(weights)
        
        # Parse target betas
        target_beta_dict = None
        if target_betas:
            target_beta_dict = json.loads(target_betas)
        elif hedge_strategy == "market_neutral":
            target_beta_dict = {"Market": 0.0}
        elif hedge_strategy == "sector_neutral":
            target_beta_dict = {"Market": 1.0, "Financials": 0.0, "Technology": 0.0}
        
        # Create Barra model
        barra_model = BarraFactorModel()
        
        # Get factor ETFs
        factor_etf_tickers = list(barra_model.FACTOR_ETFS.keys())
        all_tickers = tickers + factor_etf_tickers
        
        # Fetch data for all tickers including factor ETFs
        combined_data = await fetch_market_data_batch(market_server, all_tickers, period, start_date, end_date)
        prices = adapt_mcp_to_prices(combined_data, all_tickers)
        
        # Filter to only tickers that exist in the data
        available_portfolio_tickers = [t for t in tickers if t in prices.columns]
        available_factor_tickers = [t for t in factor_etf_tickers if t in prices.columns]
        
        if len(available_portfolio_tickers) < 1:
            return {'status': 'error', 'error': 'No valid portfolio tickers found in market data'}
        
        if len(available_factor_tickers) < 1:
            return {'status': 'error', 'error': 'No factor ETF data available (SPY, XLF, XLK)'}
        
        # Log skipped tickers
        skipped = [t for t in tickers if t not in prices.columns]
        if skipped:
            logger.warning(f"Skipped tickers not found in data: {skipped}")
        
        # Split into portfolio prices and factor prices
        portfolio_prices = prices[available_portfolio_tickers]
        factor_prices = prices[available_factor_tickers]
        
        # Rename factor columns to factor names
        factor_prices.columns = [barra_model.FACTOR_ETFS.get(t, t) for t in factor_prices.columns]
        
        # Recalculate weights for available tickers only
        if weights is not None:
            # Filter weights to match available tickers
            ticker_weight_map = dict(zip(tickers, weights))
            filtered_weights = np.array([ticker_weight_map.get(t, 0) for t in available_portfolio_tickers])
            # Renormalize
            if filtered_weights.sum() > 0:
                weights = filtered_weights / filtered_weights.sum()
            else:
                weights = np.array([1.0 / len(available_portfolio_tickers)] * len(available_portfolio_tickers))
        else:
            weights = np.array([1.0 / len(available_portfolio_tickers)] * len(available_portfolio_tickers))
        
        # Update tickers to available only
        tickers = available_portfolio_tickers
        
        # Calculate returns
        portfolio_returns = portfolio_prices.pct_change().dropna()
        
        # Fit model with factor prices
        barra_model.estimate_factor_model(portfolio_returns, portfolio_prices, factor_prices=factor_prices)
        
        portfolio_weights_dict = dict(zip(tickers, weights))
        
        # Create hedge optimizer
        hedge_optimizer = HedgePortfolioOptimizer(barra_model)
        hedge_weights = hedge_optimizer.calculate_hedge_weights(
            portfolio_weights=portfolio_weights_dict,
            target_betas=target_beta_dict,
            hedge_universe=factor_etf_tickers,
            constraints='long_short',
            max_position_size=0.5
        )
        
        # Calculate risk metrics using barra model
        risk_before = barra_model.calculate_portfolio_risk(weights)
        combined_weights = portfolio_weights_dict.copy()
        combined_weights.update(hedge_weights)
        
        risk_after_estimate = {
            'total_volatility': risk_before.get('total_volatility', 0) * HEDGE_RISK_MULTIPLIERS['total'],
            'factor_risk': risk_before.get('factor_risk', 0) * HEDGE_RISK_MULTIPLIERS['factor'],
            'specific_risk': risk_before.get('specific_risk', 0) * HEDGE_RISK_MULTIPLIERS['specific']
        }
        
        # Extract exposures
        exposures_before = {}
        exposures_after = {}
        
        # Factor ETFs have exposure of 1.0 to their corresponding factor
        # SPY -> Market, XLF -> Financials, XLK -> Technology
        factor_etf_exposures = {
            'SPY': {'Market': 1.0, 'Financials': 0.0, 'Technology': 0.0},
            'XLF': {'Market': 0.0, 'Financials': 1.0, 'Technology': 0.0},
            'XLK': {'Market': 0.0, 'Financials': 0.0, 'Technology': 1.0},
        }
        
        if barra_model.factor_exposures is not None:
            for factor in barra_model.factor_exposures.columns:
                # Calculate before exposure from portfolio
                exp_before = sum(portfolio_weights_dict.get(t, 0) * barra_model.factor_exposures.loc[t, factor] 
                               for t in tickers if t in barra_model.factor_exposures.index)
                exposures_before[factor] = float(exp_before)
                
                # Calculate after exposure: portfolio + hedge ETF contributions
                hedge_contribution = 0.0
                for hedge_ticker, hedge_weight in hedge_weights.items():
                    if hedge_ticker in factor_etf_exposures:
                        hedge_contribution += hedge_weight * factor_etf_exposures[hedge_ticker].get(factor, 0)
                
                exp_after = exp_before + hedge_contribution
                exposures_after[factor] = float(exp_after)
        
        # Build hedge positions list
        hedge_positions = [
            {"ticker": t, "notional_weight": w}
            for t, w in hedge_weights.items()
        ]
        
        return {
            'status': 'success',
            'hedge_positions': hedge_positions,
            'exposures_before': exposures_before,
            'exposures_after': exposures_after,
            'expected_risk_reduction': {
                'volatility_reduction_pct': (1 - HEDGE_RISK_MULTIPLIERS['total']) * 100,
            },
            'hedge_strategy': hedge_strategy,
        }
        
    except Exception as e:
        logger.error(f"Hedge portfolio failed: {e}")
        return {'status': 'error', 'error': str(e)}
    finally:
        if market_server:
            try:
                await market_server.cleanup()
            except Exception:
                pass


@function_tool
async def create_hedge_portfolio(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    weights: Optional[List[float]] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_betas: Optional[str] = None,
    hedge_strategy: str = "market_neutral"
) -> dict:
    """
    Create a hedge portfolio to neutralize risk factors using ETFs.
    Constructs positions that offset unwanted factor exposures or create market-neutral strategies.
    
    Args:
        tickers: List of ticker symbols in the portfolio to hedge. OPTIONAL if portfolio_id provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers/weights from.
        weights: OPTIONAL - Portfolio weights. OMIT for equal weighting. Ignored if portfolio_id provided.
        period: Historical data period. Use '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'. Default: '1y'
        start_date: OPTIONAL - Start date in YYYY-MM-DD format (e.g., '2023-01-01').
                    ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        end_date: OPTIONAL - End date in YYYY-MM-DD format (e.g., '2024-01-01').
                  ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        target_betas: OPTIONAL - JSON string of target factor exposures like '{"Market": 0.0}' for market-neutral. OMIT for defaults.
        hedge_strategy: Hedging strategy: 'market_neutral', 'sector_neutral', or 'custom'. Default: 'market_neutral'
    
    Returns:
        JSON string with hedge positions, factor exposures before/after hedging, and expected risk reduction
        
    Examples:
        ✅ CORRECT: create_hedge_portfolio(portfolio_id="my_portfolio", hedge_strategy="market_neutral")
        ✅ CORRECT: create_hedge_portfolio(tickers=["AAPL", "MSFT"], hedge_strategy="market_neutral")
        ❌ WRONG: DO NOT pass "null", "undefined", or empty strings for optional parameters
    """
    from .shared import resolve_portfolio_tickers
    
    market_server = None
    try:
        # Resolve tickers from portfolio if portfolio_id provided
        if portfolio_id:
            try:
                tickers, portfolio_weights = await resolve_portfolio_tickers(portfolio_id)
                weights = list(portfolio_weights.values())
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'error_type': 'portfolio_error',
                    'calculation_type': 'hedge_portfolio'
                }
        
        # Validate we have tickers
        if not tickers:
            return {
                'status': 'error',
                'error': 'Either tickers or portfolio_id must be provided',
                'error_type': 'validation_error',
                'calculation_type': 'hedge_portfolio'
            }
        
        # Create MCP server for data fetching (FMP as primary source)
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Set defaults
        if weights is None:
            weights = np.array([1.0 / len(tickers)] * len(tickers))
        else:
            weights = np.array(weights)
        
        # Parse target betas if provided
        target_beta_dict = None
        if target_betas:
            target_beta_dict = json.loads(target_betas)
        elif hedge_strategy == "market_neutral":
            target_beta_dict = {"Market": 0.0}
        elif hedge_strategy == "sector_neutral":
            target_beta_dict = {"Market": 1.0, "Financials": 0.0, "Technology": 0.0}
        
        # Create Barra model
        barra_model = BarraFactorModel()
        
        # Get the factor ETFs to fetch
        factors_to_fetch = list(barra_model.FACTOR_ETFS.keys())
        all_tickers = tickers + factors_to_fetch
        
        # Sanitize date parameters to handle LLM passing "null" strings
        from .shared import sanitize_date_param, fetch_market_data_batch
        start_date = sanitize_date_param(start_date)
        end_date = sanitize_date_param(end_date)
        
        # Use centralized batch fetching for better performance and format handling
        combined_data = await fetch_market_data_batch(market_server, all_tickers, period, start_date, end_date)
        
        # Adapt to price DataFrame
        prices = adapt_mcp_to_prices(combined_data, all_tickers)
        
        # Get actual tickers that have data (may be subset of requested)
        actual_portfolio_tickers = [t for t in tickers if t in prices.columns]
        actual_factor_tickers = [t for t in factors_to_fetch if t in prices.columns]
        
        if len(actual_portfolio_tickers) == 0:
            raise ValueError(f"No portfolio tickers have sufficient data. Requested: {tickers}")
        if len(actual_factor_tickers) == 0:
            raise ValueError(f"No factor tickers have data. Cannot create hedge portfolio.")
        
        # Separate portfolio and factor prices (only those with data)
        portfolio_prices = prices[actual_portfolio_tickers]
        factor_prices = prices[actual_factor_tickers]
        
        # Filter weights to match actual portfolio tickers
        if weights is not None and len(tickers) != len(actual_portfolio_tickers):
            if isinstance(weights, list):
                ticker_to_weight = dict(zip(tickers, weights))
                filtered_weights = np.array([ticker_to_weight[t] for t in actual_portfolio_tickers if t in ticker_to_weight])
                weights = filtered_weights
            logger.info(f"Filtered portfolio from {len(tickers)} to {len(actual_portfolio_tickers)} tickers")
        
        # Validate/set weights
        if weights is None:
            weights = np.array([1.0 / len(actual_portfolio_tickers)] * len(actual_portfolio_tickers))
        
        # Log if tickers were excluded
        if len(actual_portfolio_tickers) < len(tickers):
            excluded = set(tickers) - set(actual_portfolio_tickers)
            logger.info(f"Excluded portfolio tickers: {', '.join(excluded)}")
        
        # Calculate returns
        returns = prepare_returns(portfolio_prices)
        
        # Estimate factor model
        barra_model.estimate_factor_model(returns, portfolio_prices, factor_prices=factor_prices)
        
        # Create hedge optimizer
        hedge_optimizer = HedgePortfolioOptimizer(barra_model)
        
        # Create portfolio weights dict
        portfolio_weights_dict = {ticker: float(weight) for ticker, weight in zip(tickers, weights)}
        
        # Calculate hedge weights
        hedge_weights = hedge_optimizer.calculate_hedge_weights(
            portfolio_weights=portfolio_weights_dict,
            target_betas=target_beta_dict,
            constraints='long_short' if 'neutral' in hedge_strategy else 'long_only'
        )
        
        # Calculate risk before hedging
        risk_before = barra_model.calculate_portfolio_risk(weights)
        
        # Combine original and hedge weights
        combined_tickers = list(portfolio_weights_dict.keys()) + list(hedge_weights.keys())
        combined_weights = []
        for ticker in combined_tickers:
            w = portfolio_weights_dict.get(ticker, 0.0) + hedge_weights.get(ticker, 0.0)
            combined_weights.append(w)
        
        # Calculate risk after hedging (simplified estimate)
        risk_after_estimate = {
            'total_risk': risk_before.get('total_risk', 0) * HEDGE_RISK_MULTIPLIERS['total'],
            'factor_risk': risk_before.get('factor_risk', 0) * HEDGE_RISK_MULTIPLIERS['factor'],
            'specific_risk': risk_before.get('specific_risk', 0) * HEDGE_RISK_MULTIPLIERS['specific']
        }
        
        # Generate chart directly (no tool calls)
        chart = None
        try:
            # Calculate correlation matrix from returns
            corr_matrix = returns.corr()
            
            # Build chart spec with correlation matrix
            # Truncate ticker list for title if too long
            ticker_display = ', '.join(actual_portfolio_tickers[:5])
            if len(actual_portfolio_tickers) > 5:
                ticker_display += f" +{len(actual_portfolio_tickers) - 5} more"
            
            chart_spec = ChartSpec(
                id=f"hedge_{abs(hash(str(tickers)))&0xFFFFFF:06x}",
                type=ChartType.CORRELATION_MATRIX,
                title=f"Asset Correlation Matrix - {ticker_display}",
                inputs={
                    'symbols': tickers,
                    'matrix': corr_matrix.values.tolist()
                },
                priority=ChartPriority.HIGH,
                options=None
            )
            
            # Call builder directly
            chart_figure = await build_correlation_matrix(chart_spec, {})
            
            if chart_figure:
                chart = register_chart_handle(
                    chart_figure.plotly,
                    chart_type=ChartType.CORRELATION_MATRIX.value,
                    title=chart_figure.title,
                    alt_text=chart_figure.alt_text,
                    metadata=chart_figure.metadata,
                    chart_id=chart_figure.id
                )
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            # Continue without chart
        
        normalized = jsonify_results({
            'status': 'success',
            'hedge_analysis': {
                'original_portfolio': portfolio_weights_dict,
                'hedge_positions': hedge_weights,
                'hedge_strategy': hedge_strategy,
                'target_betas': target_beta_dict
            },
            'risk_metrics': {
                'before_hedging': risk_before,
                'after_hedging_estimate': risk_after_estimate,
                'risk_reduction': {
                    'total': f"{(1 - HEDGE_RISK_MULTIPLIERS['total']) * 100:.0f}%",
                    'factor': f"{(1 - HEDGE_RISK_MULTIPLIERS['factor']) * 100:.0f}%",
                    'specific': f"{(1 - HEDGE_RISK_MULTIPLIERS['specific']) * 100:.0f}%"
                }
            },
            'implementation_notes': [
                f"Hedge strategy: {hedge_strategy}",
                f"Number of hedge positions: {len(hedge_weights)}",
                "Consider transaction costs and market impact"
            ],
            'charts': [chart] if chart else []
        })
        
        # Return directly - sanitizer was causing SDK to hang
        return normalized
        
    except Exception as e:
        logger.error(f"Stress test with hedge failed: {e}")
        error_type = 'model_error' if 'model' in str(e).lower() else 'general_error'
        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'stress_test'
        }
    finally:
        # Cleanup FMP server connection
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")
