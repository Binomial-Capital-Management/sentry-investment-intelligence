"""
Portfolio Optimization Tool
"""

from agents import function_tool
from typing import List, Optional
import logging
import json
import numpy as np

from core.risk_modules.efficient_frontier import PortfolioOptimizer
from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns, jsonify_results
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.constants import MIN_WEIGHT, DEFAULT_MAX_WEIGHT, DEFAULT_PERIOD
from .shared import fetch_market_data_batch, register_chart_handle
from core.charts.builders.advanced import build_efficient_frontier
from core.charts.models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


@function_tool
async def optimize_portfolio(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    optimization_method: str = "min_variance",
    constraints_json: Optional[str] = None,
    target_return: Optional[float] = None
) -> dict:
    """
    Optimize portfolio allocation using various optimization methods. Automatically fetches required market data.
    
    Args:
        tickers: List of ticker symbols (minimum 2). OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers from. Use this OR tickers.
        period: Historical data period. Use '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'. Default: '1y'
        start_date: OPTIONAL - Start date in YYYY-MM-DD format (e.g., '2023-01-01').
                    ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        end_date: OPTIONAL - End date in YYYY-MM-DD format (e.g., '2024-01-01').
                  ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        optimization_method: Method to use: 'min_variance', 'max_sharpe', 'risk_parity', 'target_return' (default: 'min_variance')
        constraints_json: OPTIONAL - JSON string with constraints like {"min_weight": 0.0, "max_weight": 0.3}. OMIT for defaults.
        target_return: OPTIONAL - Required for 'target_return' method. Target annual return as decimal (e.g., 0.12 for 12%). OMIT otherwise.
    
    Returns:
        JSON string of optimal weights, expected returns, volatility, and Sharpe ratio with efficient frontier chart
        
    Examples:
        ✅ CORRECT: optimize_portfolio(portfolio_id="my_portfolio", optimization_method="max_sharpe")
        ✅ CORRECT: optimize_portfolio(tickers=["AAPL", "MSFT", "GOOGL"], optimization_method="max_sharpe")
        ❌ WRONG: DO NOT pass "null", "undefined", or empty strings for optional parameters
    """
    from .shared import resolve_portfolio_tickers
    
    market_server = None
    try:
        # Resolve tickers from portfolio if portfolio_id provided
        if portfolio_id:
            try:
                tickers, _ = await resolve_portfolio_tickers(portfolio_id)
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'error_type': 'portfolio_error',
                    'calculation_type': 'optimization'
                }
        
        # Validate we have tickers
        if not tickers:
            return {
                'status': 'error',
                'error': 'Either tickers or portfolio_id must be provided',
                'error_type': 'validation_error',
                'calculation_type': 'optimization'
            }
        # Create MCP server for data fetching (FMP as primary source)
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Use centralized data fetching
        combined_data = await fetch_market_data_batch(market_server, tickers, period, start_date, end_date)
        
        # Adapt to price DataFrame and calculate returns
        prices = adapt_mcp_to_prices(combined_data, tickers)
        returns = prepare_returns(prices)
        
        # Get actual tickers that have data (may be subset of requested)
        actual_tickers = list(prices.columns)
        if len(actual_tickers) < len(tickers):
            excluded = set(tickers) - set(actual_tickers)
            logger.info(f"Excluded tickers from optimization: {', '.join(excluded)}")
        
        # Parse constraints if provided
        min_weight = MIN_WEIGHT
        max_weight = DEFAULT_MAX_WEIGHT
        if constraints_json:
            constraints = json.loads(constraints_json)
            min_weight = constraints.get('min_weight', 0.0)
            max_weight = constraints.get('max_weight', 0.25)
        
        # Create optimizer
        optimizer = PortfolioOptimizer(returns, min_weight=min_weight, max_weight=max_weight)
        
        # Run optimization based on method
        if optimization_method == "min_variance":
            result = optimizer.optimize_portfolio(objective='min_variance')
        elif optimization_method == "max_sharpe":
            result = optimizer.optimize_portfolio(objective='sharpe')
        elif optimization_method == "risk_parity":
            result = optimizer.optimize_portfolio(objective='risk_parity')
        elif optimization_method == "target_return" and target_return is not None:
            result = optimizer.optimize_portfolio(objective='target_return', target_return=target_return)
        else:
            raise ValueError(f"Invalid optimization method: {optimization_method}")
        
        # Extract weights from result
        if result and 'weights' in result:
            optimal_weights = result['weights']
        else:
            raise ValueError("Optimization failed to produce valid weights")
        
        # Generate chart directly (no tool calls)
        chart = None
        try:
            # Use the optimizer's built-in efficient_frontier method
            frontier_df = optimizer.efficient_frontier(n_portfolios=30)

            # Extract returns and risks from the dataframe
            frontier_returns = (frontier_df['return'].values * 252).tolist()  # Annualized
            frontier_risks = (frontier_df['volatility'].values * np.sqrt(252) * 100).tolist()  # Annualized %

            # Format optimal portfolio for display
            optimal_portfolio = {}
            if result and 'expected_return' in result and 'volatility' in result:
                optimal_portfolio[optimization_method.replace('_', ' ')] = {
                    'return': result['expected_return'] * 252,  # Annualized
                    'risk': result['volatility'] * np.sqrt(252) * 100  # Annualized %
                }

            # Build chart spec with corrected format
            chart_spec = ChartSpec(
                id=f"opt_{abs(hash(str(tickers)))&0xFFFFFF:06x}",
                type=ChartType.EFFICIENT_FRONTIER,
                title=f"Efficient Frontier - {optimization_method}",
                inputs={
                    'frontier_returns': frontier_returns,
                    'frontier_risks': frontier_risks,
                    'portfolios': optimal_portfolio,
                    'current': None  # Could add current portfolio if available
                },
                priority=ChartPriority.HIGH,
                options=None
            )
            
            # Call builder directly
            chart_figure = await build_efficient_frontier(chart_spec, {})
            
            if chart_figure:
                chart = register_chart_handle(
                    chart_figure.plotly,
                    chart_type=ChartType.EFFICIENT_FRONTIER.value,
                    title=chart_figure.title,
                    alt_text=chart_figure.alt_text,
                    metadata=chart_figure.metadata,
                    chart_id=chart_figure.id
                )
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            # Continue without chart
        
        return jsonify_results({
            'status': 'success',
            'optimal_weights': {ticker: float(weight) for ticker, weight in zip(tickers, optimal_weights)},
            'portfolio_metrics': result,
            'optimization_method': optimization_method,
            'tickers': tickers,
            'charts': [chart] if chart else []
        })
        
    except Exception as e:
        logger.error(f"Portfolio optimization with data failed: {e}")
        error_type = 'optimization_error' if 'optimization' in str(e).lower() else 'general_error'
        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'optimization'
        }
    finally:
        # Cleanup FMP server connection
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")
