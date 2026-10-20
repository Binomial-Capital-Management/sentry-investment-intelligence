"""Barra Factor Analysis Executor for Canvas.

Handles execution of Barra-style factor analysis and result formatting.
Graph building is done generically by the Canvas router - NOT here.
"""

from typing import Dict, Any, Optional, List
import logging
import numpy as np

from .charts import build_factor_heatmap, build_risk_decomposition, build_r_squared_bar

logger = logging.getLogger(__name__)


# Predefined factor sets
FACTOR_SETS = {
    "default": {
        'SPY': 'Market',
        'XLF': 'Financials',
        'XLK': 'Technology',
    },
    "sector": {
        'SPY': 'Market',
        'XLF': 'Financials',
        'XLK': 'Technology',
        'XLE': 'Energy',
        'XLV': 'Healthcare',
        'XLI': 'Industrials',
        'XLY': 'Consumer_Disc',
        'XLP': 'Consumer_Staples',
    },
    "style": {
        'SPY': 'Market',
        'MTUM': 'Momentum',
        'VLUE': 'Value',
        'QUAL': 'Quality',
        'USMV': 'Low_Volatility',
    },
    "comprehensive": {
        'SPY': 'Market',
        'XLF': 'Financials',
        'XLK': 'Technology',
        'XLE': 'Energy',
        'XLV': 'Healthcare',
        'MTUM': 'Momentum',
        'VLUE': 'Value',
    },
}


async def execute_barra_factors(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Barra factor analysis.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including portfolio_id, tickers, weights, period, factor_set
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.risk_modules.barra_factor import BarraFactorModel
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.utils.risk_adapter import adapt_mcp_to_prices, prepare_returns
    from core.agents.risk_tools.shared import fetch_market_data_batch
    
    market_server = None
    
    try:
        # Resolve tickers from portfolio or direct input
        tickers = params.get('tickers')
        weights = params.get('weights')
        
        if params.get('portfolio_id'):
            tickers, weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
        
        if not tickers:
            return {"status": "error", "error": "Provide portfolio_id or tickers"}
        
        # Get factor set
        factor_set_name = params.get('factor_set', 'default')
        
        # Support custom factors
        if factor_set_name == 'custom' and params.get('custom_factors'):
            custom_factors = params['custom_factors']
            logger.info(f"Using custom factors: {custom_factors}")
        else:
            custom_factors = FACTOR_SETS.get(factor_set_name, FACTOR_SETS['default'])
        
        logger.info(f"Running Barra factor analysis for {len(tickers)} tickers with {factor_set_name} factors")
        
        # Create Barra model
        barra_model = BarraFactorModel(custom_factors=custom_factors)
        factor_etf_tickers = list(barra_model.FACTOR_ETFS.keys())
        all_tickers = tickers + factor_etf_tickers
        
        # Fetch market data using shared batch fetcher
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        period = params.get('period', '1y')
        combined_data = await fetch_market_data_batch(market_server, all_tickers, period)
        
        # Adapt to price DataFrame
        prices = adapt_mcp_to_prices(combined_data, all_tickers)
        
        # Filter to tickers with data
        actual_portfolio_tickers = [t for t in tickers if t in prices.columns]
        actual_factor_tickers = [t for t in factor_etf_tickers if t in prices.columns]
        
        if len(actual_portfolio_tickers) == 0:
            return {"status": "error", "error": f"No portfolio tickers have data. Requested: {tickers}"}
        if len(actual_factor_tickers) == 0:
            return {"status": "error", "error": "No factor ETFs have data"}
        
        # Separate portfolio and factor prices
        portfolio_prices = prices[actual_portfolio_tickers]
        factor_prices = prices[actual_factor_tickers]
        
        # Calculate returns
        returns = prepare_returns(portfolio_prices)
        
        # Estimate factor model
        results = barra_model.estimate_factor_model(returns, portfolio_prices, factor_prices=factor_prices)
        
        if not results:
            return {"status": "error", "error": "Factor model estimation failed"}
        
        # Extract factor exposures
        factor_exposures = {}
        if 'factor_exposures' in results:
            exposures_data = results['factor_exposures']
            if isinstance(exposures_data, dict):
                factor_exposures = exposures_data
            else:
                for ticker in actual_portfolio_tickers:
                    if ticker in exposures_data.index:
                        factor_exposures[ticker] = exposures_data.loc[ticker].to_dict()
        
        # Extract R-squared values
        r_squared = {}
        if 'r_squared' in results:
            r2_data = results['r_squared']
            for ticker in actual_portfolio_tickers:
                if ticker in r2_data.index:
                    r_squared[ticker] = float(r2_data[ticker])
        
        # Calculate portfolio risk if weights provided
        risk_data = None
        if weights and len(weights) == len(actual_portfolio_tickers):
            try:
                weights_arr = np.array(weights)
                # Normalize weights
                weights_arr = weights_arr / weights_arr.sum()
                risk_data = barra_model.calculate_portfolio_risk(weights_arr)
            except Exception as e:
                logger.warning(f"Portfolio risk calculation failed: {e}")
        
        # Build charts
        heatmap_chart = build_factor_heatmap(factor_exposures, actual_portfolio_tickers)
        r2_chart = build_r_squared_bar(r_squared, actual_portfolio_tickers)
        risk_chart = build_risk_decomposition(risk_data) if risk_data else None
        
        # Build stats table
        stats_table = _build_stats_table(results, risk_data, actual_portfolio_tickers)
        
        # Build metrics
        metrics = _extract_metrics(results, risk_data)
        
        # Build metric cards
        metric_cards = _build_metric_cards(results, risk_data)
        
        return {
            "status": "success",
            "tool_id": "barra_factors",
            "tickers": actual_portfolio_tickers,
            "weights": weights if weights else [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": {
                "factor_heatmap": heatmap_chart,
                "r_squared": r2_chart,
                "risk_decomposition": risk_chart,
            },
            "factor_set": factor_set_name,
            "factors_used": custom_factors,
        }
        
    except Exception as e:
        logger.error(f"Barra factor analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    
    finally:
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")


async def _resolve_portfolio(
    user_id: str, 
    org_id: Optional[str], 
    portfolio_id: str
) -> tuple[Optional[List[str]], Optional[List[float]]]:
    """Resolve tickers and weights from portfolio ID."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return None, None
        
        actual_portfolio = portfolio.get("portfolio", {})
        tickers = actual_portfolio.get('tickers', [])
        weights = actual_portfolio.get('weights', [])
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers) if tickers else None
        return tickers, weights
    except Exception as e:
        logger.warning(f"Could not fetch portfolio: {e}")
    return None, None


def _extract_metrics(results: Dict[str, Any], risk_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract metrics from factor analysis results."""
    metrics = {
        "mean_r_squared": results.get('mean_r_squared', 0),
    }
    
    if risk_data:
        metrics.update({
            "total_risk": risk_data.get('total_risk', 0),
            "factor_risk": risk_data.get('factor_risk', 0),
            "specific_risk": risk_data.get('specific_risk', 0),
            "systematic_pct": risk_data.get('risk_decomposition', {}).get('systematic', 0),
            "idiosyncratic_pct": risk_data.get('risk_decomposition', {}).get('idiosyncratic', 0),
        })
    
    return metrics


def _build_metric_cards(results: Dict[str, Any], risk_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build displayable metric cards with styling metadata."""
    cards = []
    
    # Mean R-squared
    mean_r2 = results.get('mean_r_squared', 0)
    cards.append({
        "id": "mean_r_squared",
        "label": "Mean R²",
        "value": f"{mean_r2*100:.1f}%",
        "sentiment": "positive" if mean_r2 > 0.7 else ("neutral" if mean_r2 > 0.4 else "negative"),
    })
    
    if risk_data:
        # Total Risk
        total_risk = risk_data.get('total_risk', 0)
        cards.append({
            "id": "total_risk",
            "label": "Total Risk (Ann.)",
            "value": f"{total_risk*100:.1f}%",
            "sentiment": "negative" if total_risk > 0.25 else "neutral",
        })
        
        # Systematic vs Idiosyncratic breakdown
        systematic_pct = risk_data.get('risk_decomposition', {}).get('systematic', 0)
        cards.append({
            "id": "systematic_pct",
            "label": "Systematic Risk",
            "value": f"{systematic_pct*100:.0f}%",
            "sentiment": "neutral",
        })
        
        idio_pct = risk_data.get('risk_decomposition', {}).get('idiosyncratic', 0)
        cards.append({
            "id": "idiosyncratic_pct",
            "label": "Idiosyncratic",
            "value": f"{idio_pct*100:.0f}%",
            "sentiment": "positive" if idio_pct > 0.3 else "neutral",
        })
        
        # Top factor contribution
        factor_contributions = risk_data.get('factor_contributions', {})
        if factor_contributions:
            top_factor = max(factor_contributions.items(), key=lambda x: x[1])
            cards.append({
                "id": "top_factor",
                "label": f"Top Factor: {top_factor[0]}",
                "value": f"{top_factor[1]*100:.1f}%",
                "sentiment": "neutral",
            })
    
    return cards


def _build_stats_table(
    results: Dict[str, Any],
    risk_data: Optional[Dict[str, Any]],
    tickers: List[str],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table for display."""
    stats = []
    
    # Model fit stats
    mean_r2 = results.get('mean_r_squared', 0)
    stats.append({"category": "Model Fit", "metric": "Mean R²", "value": f"{mean_r2*100:.1f}%"})
    stats.append({"category": "Model Fit", "metric": "Assets Analyzed", "value": str(len(tickers))})
    
    # Factor count
    factor_cov = results.get('factor_covariance')
    if factor_cov is not None:
        n_factors = len(factor_cov.columns) if hasattr(factor_cov, 'columns') else 0
        stats.append({"category": "Model Fit", "metric": "Factors Used", "value": str(n_factors)})
    
    # Risk decomposition stats (if available)
    if risk_data:
        total_risk = risk_data.get('total_risk', 0)
        factor_risk = risk_data.get('factor_risk', 0)
        specific_risk = risk_data.get('specific_risk', 0)
        systematic_pct = risk_data.get('risk_decomposition', {}).get('systematic', 0)
        idio_pct = risk_data.get('risk_decomposition', {}).get('idiosyncratic', 0)
        
        stats.append({"category": "Portfolio Risk", "metric": "Total Risk (Ann.)", "value": f"{total_risk*100:.1f}%"})
        stats.append({"category": "Portfolio Risk", "metric": "Systematic Risk", "value": f"{factor_risk*100:.1f}%", "pct": f"{systematic_pct*100:.0f}%"})
        stats.append({"category": "Portfolio Risk", "metric": "Idiosyncratic Risk", "value": f"{specific_risk*100:.1f}%", "pct": f"{idio_pct*100:.0f}%"})
        
        # Factor contributions
        factor_contributions = risk_data.get('factor_contributions', {})
        for factor, contrib in sorted(factor_contributions.items(), key=lambda x: -x[1]):
            if contrib > 0.01:  # Only show > 1%
                stats.append({
                    "category": "Factor Attribution",
                    "metric": factor,
                    "value": f"{contrib*100:.1f}%",
                })
        
        # Portfolio betas
        portfolio_betas = risk_data.get('portfolio_betas', {})
        for factor, beta in portfolio_betas.items():
            stats.append({
                "category": "Portfolio Betas",
                "metric": factor,
                "value": f"{beta:.3f}",
            })
    
    return stats

