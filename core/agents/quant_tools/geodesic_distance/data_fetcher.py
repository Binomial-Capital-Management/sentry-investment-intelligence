"""
Data fetcher for Portfolio Geodesic Distance tool.

Fetches historical prices via FMP and computes portfolio returns.
No hardcoded field names - extracts price field dynamically from API response.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

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
    """Compute daily returns from price series."""
    if len(prices) < 2:
        return []
    return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]


class GeodesicDataFetcher:
    """Fetches portfolio data for geodesic distance calculations."""
    
    def __init__(self):
        self.fmp_server: Optional[FMPMarketDataServer] = None
    
    async def connect(self):
        """Initialize FMP server connection."""
        self.fmp_server = FMPMarketDataServer()
        await self.fmp_server.connect()
        logger.info("Connected to FMP server")
    
    async def cleanup(self):
        """Cleanup server connections."""
        if self.fmp_server:
            await self.fmp_server.cleanup()
            logger.info("Cleaned up FMP server")
    
    async def fetch_ticker_history(
        self,
        ticker: str,
        lookback_days: int = 252
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical prices for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of trading days to fetch
            
        Returns:
            Dict with prices, returns, dates, or None on failure
        """
        if not self.fmp_server:
            logger.error("FMP server not initialized")
            return None
        
        try:
            # Calculate date range
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
            
            # Handle different response formats
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
            
            # Extract prices dynamically (no hardcoded field names)
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
            
            if len(prices) < 2:
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
            
            # Compute returns
            returns = _compute_returns(prices)
            
            return {
                "ticker": ticker,
                "prices": prices,
                "returns": returns,
                "dates": dates[1:] if dates else [],
                "n_observations": len(returns),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            return None
    
    async def fetch_portfolio_returns(
        self,
        tickers: List[str],
        weights: Optional[List[float]] = None,
        lookback_days: int = 252,
        name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and compute weighted portfolio returns.
        
        Args:
            tickers: List of ticker symbols
            weights: Portfolio weights (equal-weight if None)
            lookback_days: Number of trading days
            name: Optional portfolio name
            
        Returns:
            Dict with portfolio returns and metadata
        """
        import asyncio
        
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
        
        # Fetch all tickers (skip unrecognized ones)
        ticker_data = {}
        skipped_tickers = []
        for ticker in tickers:
            history = await self.fetch_ticker_history(ticker, lookback_days)
            if history and history["returns"]:
                ticker_data[ticker] = history
            else:
                skipped_tickers.append(ticker)
                logger.warning(f"Skipping unrecognized/failed ticker: {ticker}")
            await asyncio.sleep(0.1)  # Rate limiting
        
        if skipped_tickers:
            logger.info(f"Skipped {len(skipped_tickers)} tickers: {skipped_tickers}")
        
        if not ticker_data:
            logger.error(f"No ticker data fetched successfully. All tickers failed: {tickers}")
            return None
        
        # Align returns to same length
        min_len = min(len(d["returns"]) for d in ticker_data.values())
        if min_len < 20:
            logger.error(f"Insufficient aligned data: {min_len} observations")
            return None
        
        # Build returns DataFrame
        returns_dict = {}
        for ticker, data in ticker_data.items():
            returns_dict[ticker] = data["returns"][-min_len:]
        
        returns_df = pd.DataFrame(returns_dict)
        
        # Compute weighted portfolio returns
        weight_dict = dict(zip(tickers, weights))
        portfolio_weights = [weight_dict.get(t, 0) for t in returns_df.columns]
        
        # Renormalize for available tickers
        available_weight_sum = sum(portfolio_weights)
        if available_weight_sum <= 0:
            logger.error("No valid weights for available tickers")
            return None
        portfolio_weights = [w / available_weight_sum for w in portfolio_weights]
        
        portfolio_returns = (returns_df.values @ np.array(portfolio_weights)).tolist()
        
        # Store individual ticker returns for manifold computations
        ticker_returns = {
            ticker: returns_df[ticker].tolist() 
            for ticker in returns_df.columns
        }
        
        return {
            "name": name or f"Portfolio({','.join(tickers[:3])}{'...' if len(tickers) > 3 else ''})",
            "tickers": list(returns_df.columns),
            "weights": portfolio_weights,
            "returns": portfolio_returns,
            "returns_df": returns_df,
            "ticker_returns": ticker_returns,  # For manifold physics
            "n_observations": len(portfolio_returns),
            "start_date": ticker_data[list(ticker_data.keys())[0]].get("dates", [None])[-min_len] if ticker_data else None,
            "end_date": ticker_data[list(ticker_data.keys())[0]].get("dates", [None])[-1] if ticker_data else None,
            "skipped_tickers": skipped_tickers,  # Tickers that failed to fetch
        }
    
    async def fetch_multiple_portfolios(
        self,
        portfolio_specs: List[Dict[str, Any]],
        lookback_days: int = 252
    ) -> List[Dict[str, Any]]:
        """
        Fetch returns for multiple portfolios.
        
        Args:
            portfolio_specs: List of dicts with 'tickers', 'weights', 'name'
            lookback_days: Number of trading days
            
        Returns:
            List of portfolio return dicts
        """
        portfolios = []
        
        for spec in portfolio_specs:
            portfolio = await self.fetch_portfolio_returns(
                tickers=spec.get("tickers", []),
                weights=spec.get("weights"),
                lookback_days=lookback_days,
                name=spec.get("name")
            )
            if portfolio:
                portfolios.append(portfolio)
        
        return portfolios

