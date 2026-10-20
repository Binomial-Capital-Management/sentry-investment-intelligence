"""
Data fetcher for Instanton Rare Event Analyzer.

Fetches historical prices via FMP and computes returns for crash analysis.
Provides both prices (for path visualization) and returns (for distribution fitting).
No hardcoded field names - extracts data dynamically from API response.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import asyncio

import pandas as pd
import numpy as np

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _compute_returns(prices: List[float]) -> List[float]:
    """Compute daily log returns from price series."""
    if len(prices) < 2:
        return []
    return [np.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]


def _compute_simple_returns(prices: List[float]) -> List[float]:
    """Compute daily simple returns from price series."""
    if len(prices) < 2:
        return []
    return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]


class InstantonDataFetcher:
    """Fetches market data for instanton crash analysis."""
    
    def __init__(self):
        self.fmp_server: Optional[FMPMarketDataServer] = None
    
    async def connect(self):
        """Initialize FMP server connection."""
        self.fmp_server = FMPMarketDataServer()
        await self.fmp_server.connect()
        logger.info("InstantonDataFetcher connected to FMP server")
    
    async def cleanup(self):
        """Cleanup server connections."""
        if self.fmp_server:
            await self.fmp_server.cleanup()
            logger.info("InstantonDataFetcher cleaned up FMP server")
    
    async def fetch_ticker_history(
        self,
        ticker: str,
        lookback_days: int = 756
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical prices for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of trading days to fetch (default 3 years)
            
        Returns:
            Dict with prices, returns, dates, and current price, or None on failure
        """
        if not self.fmp_server:
            logger.error("FMP server not initialized")
            return None
        
        try:
            # Calculate date range (buffer for non-trading days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(lookback_days * 1.5))
            
            # Fetch historical data
            result = await self.fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })
            
            if not result or not hasattr(result, 'content'):
                logger.warning(f"No data returned for {ticker}")
                return None
            
            # Parse the result
            parsed = safe_parse_json(result)
            if not parsed:
                logger.warning(f"Failed to parse result for {ticker}")
                return None
            
            # Handle different response formats dynamically
            if isinstance(parsed, dict):
                if "historical" in parsed:
                    records = parsed["historical"]
                elif "data" in parsed:
                    records = parsed["data"]
                else:
                    records = [parsed]
            elif isinstance(parsed, list):
                records = parsed
            else:
                logger.warning(f"Unexpected response format for {ticker}")
                return None
            
            if not records:
                logger.warning(f"Empty records for {ticker}")
                return None
            
            # Extract prices and dates dynamically (no hardcoded field names)
            prices = []
            dates = []
            
            for record in records:
                if not isinstance(record, dict):
                    continue
                
                # Find price field dynamically
                price = None
                for key in record.keys():
                    key_lower = key.lower()
                    if key_lower in ("close", "adjclose", "adj_close", "adjusted_close", "price"):
                        price = _safe_float(record[key])
                        if price is not None and price > 0:
                            break
                
                # Find date field dynamically
                date = None
                for key in record.keys():
                    key_lower = key.lower()
                    if key_lower in ("date", "datetime", "timestamp", "time"):
                        date = record[key]
                        break
                
                if price is not None and price > 0:
                    prices.append(price)
                    dates.append(date)
            
            if len(prices) < 20:
                logger.warning(f"Insufficient price data for {ticker}: {len(prices)} points")
                return None
            
            # Reverse if newest first (common in API responses)
            if len(dates) >= 2 and dates[0] and dates[1]:
                if str(dates[0]) > str(dates[1]):
                    prices = prices[::-1]
                    dates = dates[::-1]
            
            # Trim to requested lookback
            if len(prices) > lookback_days:
                prices = prices[-lookback_days:]
                dates = dates[-lookback_days:]
            
            # Compute log returns and simple returns
            log_returns = _compute_returns(prices)
            simple_returns = _compute_simple_returns(prices)
            
            # Current price is the last price
            current_price = prices[-1] if prices else None
            
            return {
                "ticker": ticker,
                "prices": prices,
                "log_returns": log_returns,
                "simple_returns": simple_returns,
                "dates": dates,
                "current_price": current_price,
                "n_observations": len(log_returns),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            return None
    
    async def fetch_single_asset(
        self,
        ticker: str,
        lookback_days: int = 756
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data for single asset crash analysis.
        
        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of trading days
            
        Returns:
            Dict with asset data for instanton analysis
        """
        history = await self.fetch_ticker_history(ticker, lookback_days)
        if not history:
            return None
        
        # Compute volatility from log returns
        log_returns = np.array(history["log_returns"])
        daily_vol = np.std(log_returns, ddof=1)
        annualized_vol = daily_vol * np.sqrt(252)
        
        # Compute drift (mean log return)
        daily_drift = np.mean(log_returns)
        annualized_drift = daily_drift * 252
        
        return {
            "mode": "single",
            "ticker": ticker,
            "current_price": history["current_price"],
            "prices": history["prices"],
            "log_returns": history["log_returns"],
            "simple_returns": history["simple_returns"],
            "dates": history["dates"],
            "n_observations": history["n_observations"],
            "daily_volatility": float(daily_vol),
            "annualized_volatility": float(annualized_vol),
            "daily_drift": float(daily_drift),
            "annualized_drift": float(annualized_drift),
        }
    
    async def fetch_portfolio(
        self,
        tickers: List[str],
        weights: Optional[List[float]] = None,
        portfolio_name: str = "Portfolio",
        lookback_days: int = 756
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data for portfolio crash analysis.
        
        Args:
            tickers: List of ticker symbols
            weights: Portfolio weights (equal-weight if None)
            portfolio_name: Display name for portfolio
            lookback_days: Number of trading days
            
        Returns:
            Dict with portfolio data for instanton analysis
        """
        if not tickers:
            logger.error("No tickers provided")
            return None
        
        # Default to equal weights
        if weights is None:
            weights = [1.0 / len(tickers)] * len(tickers)
        
        # Normalize weights
        weight_sum = sum(weights)
        if weight_sum <= 0:
            logger.error("Invalid weights sum")
            return None
        weights = [w / weight_sum for w in weights]
        
        # Fetch all tickers
        ticker_data = {}
        skipped_tickers = []
        
        for ticker in tickers:
            history = await self.fetch_ticker_history(ticker, lookback_days)
            if history and len(history["log_returns"]) >= 20:
                ticker_data[ticker] = history
            else:
                skipped_tickers.append(ticker)
                logger.warning(f"Skipping ticker: {ticker}")
            await asyncio.sleep(0.1)  # Rate limiting
        
        if not ticker_data:
            logger.error(f"No valid ticker data. Failed: {tickers}")
            return None
        
        # Align returns to same length
        min_len = min(len(d["log_returns"]) for d in ticker_data.values())
        if min_len < 20:
            logger.error(f"Insufficient aligned data: {min_len} observations")
            return None
        
        # Build returns DataFrame
        log_returns_dict = {}
        simple_returns_dict = {}
        prices_dict = {}
        
        for ticker, data in ticker_data.items():
            log_returns_dict[ticker] = data["log_returns"][-min_len:]
            simple_returns_dict[ticker] = data["simple_returns"][-min_len:]
            prices_dict[ticker] = data["prices"][-(min_len+1):]  # +1 for initial price
        
        log_returns_df = pd.DataFrame(log_returns_dict)
        simple_returns_df = pd.DataFrame(simple_returns_dict)
        
        # Build weight vector for available tickers
        weight_dict = dict(zip(tickers, weights))
        available_tickers = list(log_returns_df.columns)
        portfolio_weights = [weight_dict.get(t, 0) for t in available_tickers]
        
        # Renormalize for available tickers
        available_weight_sum = sum(portfolio_weights)
        if available_weight_sum <= 0:
            logger.error("No valid weights for available tickers")
            return None
        portfolio_weights = [w / available_weight_sum for w in portfolio_weights]
        
        # Compute portfolio returns
        portfolio_log_returns = (log_returns_df.values @ np.array(portfolio_weights)).tolist()
        portfolio_simple_returns = (simple_returns_df.values @ np.array(portfolio_weights)).tolist()
        
        # Compute portfolio prices (normalized to start at 100)
        initial_value = 100.0
        portfolio_prices = [initial_value]
        for ret in portfolio_simple_returns:
            portfolio_prices.append(portfolio_prices[-1] * (1 + ret))
        
        # Current portfolio value
        current_value = portfolio_prices[-1]
        
        # Compute covariance matrix (for multivariate instanton)
        cov_matrix = np.cov(log_returns_df.values, rowvar=False)
        corr_matrix = np.corrcoef(log_returns_df.values, rowvar=False)
        
        # Portfolio volatility
        weights_arr = np.array(portfolio_weights)
        portfolio_variance = weights_arr @ cov_matrix @ weights_arr
        portfolio_vol = np.sqrt(portfolio_variance)
        annualized_vol = portfolio_vol * np.sqrt(252)
        
        # Portfolio drift
        daily_drift = np.mean(portfolio_log_returns)
        annualized_drift = daily_drift * 252
        
        # Individual asset volatilities
        asset_vols = {
            ticker: float(np.std(log_returns_df[ticker].values, ddof=1) * np.sqrt(252))
            for ticker in available_tickers
        }
        
        # Get current prices for each asset
        current_prices = {
            ticker: ticker_data[ticker]["current_price"]
            for ticker in available_tickers
        }
        
        return {
            "mode": "portfolio",
            "name": portfolio_name,
            "tickers": available_tickers,
            "weights": portfolio_weights,
            "current_value": float(current_value),
            "initial_value": float(initial_value),
            "portfolio_prices": portfolio_prices,
            "portfolio_log_returns": portfolio_log_returns,
            "portfolio_simple_returns": portfolio_simple_returns,
            "n_observations": len(portfolio_log_returns),
            "daily_volatility": float(portfolio_vol),
            "annualized_volatility": float(annualized_vol),
            "daily_drift": float(daily_drift),
            "annualized_drift": float(annualized_drift),
            # For portfolio decomposition
            "log_returns_df": log_returns_df,
            "covariance_matrix": cov_matrix.tolist(),
            "correlation_matrix": corr_matrix.tolist(),
            "asset_volatilities": asset_vols,
            "current_prices": current_prices,
            "ticker_data": ticker_data,
            "skipped_tickers": skipped_tickers,
        }
    
    async def fetch_data(
        self,
        ticker: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
        portfolio_name: str = "Portfolio",
        lookback_days: int = 756
    ) -> Optional[Dict[str, Any]]:
        """
        Unified data fetching for single asset or portfolio.
        
        Args:
            ticker: Single ticker (for single asset mode)
            tickers: List of tickers (for portfolio mode)
            weights: Portfolio weights
            portfolio_name: Display name for portfolio
            lookback_days: Number of trading days
            
        Returns:
            Dict with data for instanton analysis
        """
        if ticker:
            return await self.fetch_single_asset(ticker, lookback_days)
        elif tickers:
            return await self.fetch_portfolio(tickers, weights, portfolio_name, lookback_days)
        else:
            logger.error("Must provide either ticker or tickers")
            return None


















