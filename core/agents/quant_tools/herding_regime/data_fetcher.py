"""
Data fetcher for Herding Regime Detector.

Fetches sector ETF historical prices via FMP and computes daily returns.
Also fetches VIX (temperature), SPY (external field), and sector greek flow (coupling).
No hardcoded field names - extracts price field dynamically from API response.

Data sources:
- FMP: Historical sector ETF prices, VIX, SPY for computing returns
- UW: Sector greek flow for options-based coupling measurement
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

import pandas as pd
import numpy as np

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# =============================================================================
# SECTOR ETF DEFINITIONS (SPDR Sector ETFs)
# =============================================================================

SECTOR_ETFS = {
    "technology": "XLK",
    "healthcare": "XLV",
    "financials": "XLF",
    "energy": "XLE",
    "consumer_discretionary": "XLY",
    "consumer_staples": "XLP",
    "industrials": "XLI",
    "materials": "XLB",
    "utilities": "XLU",
    "real_estate": "XLRE",
    "communication_services": "XLC",
}

# All ETF tickers for quick access
ALL_SECTOR_TICKERS = list(SECTOR_ETFS.values())

# FRED series for macro external field
FRED_SERIES = {
    "credit_spread": {
        "series_id": "BAMLH0A0HYM2",  # ICE BofA US High Yield Index Option-Adjusted Spread
        "description": "High Yield Credit Spread (risk appetite)",
        "invert": True,  # Higher spread = bearish
    },
    "yield_curve": {
        "series_id": "T10Y2Y",  # 10-Year Treasury Constant Maturity Minus 2-Year
        "description": "Yield Curve (recession signal)",
        "invert": False,  # Positive = bullish, inverted = bearish
    },
    "m2_change": {
        "series_id": "M2SL",  # M2 Money Stock
        "description": "M2 Money Supply (liquidity)",
        "yoy": True,  # Calculate YoY change
        "invert": False,  # Higher = bullish
    },
}

# UW flow_group names for greek flow (maps to sector ETFs)
# Values must match UW API enum: technology, healthcare, financial services,
# energy, consumer cyclical, consumer defensive, industrials, basic materials,
# utilities, real estate, communication services
SECTOR_FLOW_GROUPS = {
    "technology": "technology",
    "healthcare": "healthcare",
    "financials": "financial services",
    "energy": "energy",
    "consumer_discretionary": "consumer cyclical",
    "consumer_staples": "consumer defensive",
    "industrials": "industrials",
    "materials": "basic materials",
    "utilities": "utilities",
    "real_estate": "real estate",
    "communication_services": "communication services",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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


# =============================================================================
# MAIN FETCHER CLASS
# =============================================================================

class HerdingDataFetcher:
    """
    Fetches sector ETF data for herding analysis.
    
    All field extraction is dynamic - no hardcoded field names.
    
    Enhanced data sources:
    - Sector ETF prices (magnetization)
    - VIX (temperature)
    - SPY (external field)
    - Sector greek flow (coupling)
    """
    
    def __init__(self):
        self.fmp = FMPMarketDataServer()
        self.uw_options = UWOptionsServer()
        self._connected = False
    
    async def connect(self):
        """Connect to FMP and UW servers."""
        if not self._connected:
            await self.fmp.connect()
            await self.uw_options.connect()
            self._connected = True
    
    async def cleanup(self):
        """Cleanup server connections."""
        await self.fmp.cleanup()
        await self.uw_options.cleanup()
        self._connected = False
    
    # =========================================================================
    # VIX DATA (Temperature)
    # =========================================================================
    
    async def fetch_vix_data(
        self,
        lookback_days: int = 252
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch VIX historical data for temperature calculation.
        
        VIX serves as the "temperature" in the Ising model:
        - High VIX = high temperature = disorder/randomness
        - Low VIX = low temperature = ordered states persist
        
        Args:
            lookback_days: Number of trading days to fetch
            
        Returns:
            Dict with 'values', 'dates', 'current', 'history'
        """
        try:
            # Map lookback to FMP period format
            if lookback_days <= 30:
                period = "1M"
            elif lookback_days <= 90:
                period = "3M"
            elif lookback_days <= 180:
                period = "6M"
            else:
                period = "1Y"
            
            # VIX ticker on FMP
            result = await self.fmp.call_tool("get_historical_data", {
                "symbol": "^VIX",
                "period": period
            })
            
            data = safe_parse_json(result)
            if not data:
                logger.warning("No VIX data returned")
                return None
            
            # Extract closes
            values = []
            dates = []
            
            if isinstance(data, dict):
                if "closes" in data:
                    values = [_safe_float(p) for p in data["closes"]]
                    values = [v for v in values if v is not None]
                if "dates" in data:
                    dates = data["dates"]
                
                # Fallback to data array
                if not values and "data" in data and isinstance(data["data"], list):
                    for row in data["data"]:
                        if isinstance(row, dict):
                            close = _safe_float(row.get("Close") or row.get("close"))
                            date = row.get("Date") or row.get("date")
                            if close is not None:
                                values.append(close)
                            if date:
                                dates.append(date)
            
            if not values:
                logger.warning("No VIX values extracted")
                return None
            
            logger.info(f"Fetched VIX: {len(values)} observations, current={values[-1]:.2f}")
            
            return {
                "values": values,
                "dates": dates,
                "current": values[-1] if values else None,
                "history": values,
                "n_observations": len(values),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch VIX data: {e}")
            return None
    
    # =========================================================================
    # SPY DATA (External Field)
    # =========================================================================
    
    async def fetch_benchmark_data(
        self,
        symbol: str = "SPY",
        lookback_days: int = 252,
        momentum_window: int = 20,
        short_momentum_window: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch benchmark historical data for external field calculation.
        
        Benchmark momentum serves as the "external field" in the Ising model:
        - Positive momentum = bullish bias on all sectors
        - Negative momentum = bearish bias on all sectors
        
        Args:
            symbol: Benchmark ticker (SPY, QQQ, IWM, DIA, etc.)
            lookback_days: Number of trading days to fetch
            momentum_window: Window for moving average (default 20)
            short_momentum_window: Window for short-term momentum (default 5)
            
        Returns:
            Dict with 'prices', 'returns', 'dates', 'momentum'
        """
        try:
            history = await self.fetch_etf_history(symbol, lookback_days)
            if not history:
                return None
            
            prices = history["prices"]
            returns = history["returns"]
            
            # Compute momentum indicators with configurable window
            ma_long = None
            if len(prices) >= momentum_window:
                ma_long = sum(prices[-momentum_window:]) / momentum_window
            
            # Current momentum = price / MA - 1
            current_price = prices[-1] if prices else None
            momentum = None
            if current_price and ma_long:
                momentum = (current_price / ma_long) - 1
            
            # Short-term momentum (configurable window)
            momentum_short = None
            if len(prices) >= short_momentum_window + 1:
                momentum_short = (prices[-1] / prices[-(short_momentum_window + 1)]) - 1
            
            logger.info(f"Fetched {symbol}: {len(returns)} returns, momentum={f'{momentum:.4f}' if momentum else 'N/A'}")
            
            return {
                "symbol": symbol,
                "prices": prices,
                "returns": returns,
                "dates": history.get("dates", []),
                "current_price": current_price,
                "ma_window": momentum_window,
                "ma_value": ma_long,
                "momentum": momentum,  # Price vs MA
                "short_window": short_momentum_window,
                "momentum_short": momentum_short,  # Short-term return
                "n_observations": len(returns),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol} data: {e}")
            return None
    
    # Backward compatibility alias
    async def fetch_spy_data(
        self,
        lookback_days: int = 252
    ) -> Optional[Dict[str, Any]]:
        """Backward compatible wrapper for fetch_benchmark_data with SPY."""
        return await self.fetch_benchmark_data("SPY", lookback_days)
    
    # =========================================================================
    # SECTOR GREEK FLOW (Coupling)
    # =========================================================================
    
    async def fetch_sector_greek_flow(
        self,
        sector: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch greek flow for a single sector via UW.
        
        Delta flow indicates options-based sentiment (forward-looking).
        Used to compute "coupling" - correlation between price and options sentiment.
        
        Args:
            sector: Sector name (e.g., "technology")
            
        Returns:
            Dict with delta_flow, vega_flow, net_premium, etc.
        """
        flow_group = SECTOR_FLOW_GROUPS.get(sector.lower())
        if not flow_group:
            logger.warning(f"No flow group mapping for sector: {sector}")
            return None
        
        try:
            # Get the dataset from UW catalog
            dataset = self.uw_options.ddc_loader.get_dataset("group-greek-flow")
            if not dataset:
                logger.warning("group-greek-flow dataset not found in UW catalog")
                return None
            
            # Fetch data
            params = {"flow_group": flow_group}
            data = await self.uw_options.data_fetcher.fetch_dataset(dataset, params, use_cache=False)
            
            if not data or "error" in data:
                logger.warning(f"Error fetching greek flow for {sector}: {data.get('error') if data else 'No data'}")
                return None
            
            # Aggregate records
            records = data.get("data", [])
            if not records:
                logger.warning(f"No greek flow records for {sector}")
                return None
            
            aggregated = {}
            for record in records:
                if not isinstance(record, dict):
                    continue
                for key, value in record.items():
                    if key in ('timestamp', 'flow_group'):
                        continue
                    try:
                        num_val = float(value) if value else 0.0
                    except (ValueError, TypeError):
                        continue
                    if key not in aggregated:
                        aggregated[key] = 0.0
                    aggregated[key] += num_val
            
            result = {
                "sector": sector,
                "flow_group": flow_group,
                "delta_flow": aggregated.get("dir_delta_flow", 0),
                "vega_flow": aggregated.get("dir_vega_flow", 0),
                "net_call_premium": aggregated.get("net_call_premium", 0),
                "net_put_premium": aggregated.get("net_put_premium", 0),
                "net_premium": aggregated.get("net_call_premium", 0) - aggregated.get("net_put_premium", 0),
                "volume": aggregated.get("volume", 0),
            }
            
            logger.info(f"Fetched greek flow for {sector}: delta={result['delta_flow']:,.0f}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to fetch greek flow for {sector}: {e}")
            return None
    
    async def fetch_all_sector_greek_flows(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch greek flow for all available sectors.
        
        Returns:
            Dict mapping sector -> greek flow data
        """
        import asyncio
        
        results = {}
        
        for sector in SECTOR_FLOW_GROUPS.keys():
            try:
                flow = await self.fetch_sector_greek_flow(sector)
                if flow:
                    results[sector] = flow
            except Exception as e:
                logger.warning(f"Failed to fetch greek flow for {sector}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.2)
        
        logger.info(f"Fetched greek flow for {len(results)} sectors")
        return results
    
    async def fetch_etf_history(
        self,
        ticker: str,
        lookback_days: int = 252
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical price data for a single ETF.
        
        Args:
            ticker: ETF ticker symbol
            lookback_days: Number of trading days to fetch
            
        Returns:
            Dict with 'prices', 'returns', 'dates', 'ticker'
        """
        try:
            # Map lookback to FMP period format
            if lookback_days <= 30:
                period = "1M"
            elif lookback_days <= 90:
                period = "3M"
            elif lookback_days <= 180:
                period = "6M"
            else:
                period = "1Y"
            
            result = await self.fmp.call_tool("get_historical_data", {
                "symbol": ticker,
                "period": period
            })
            
            data = safe_parse_json(result)
            if not data:
                logger.warning(f"No data returned for {ticker}")
                return None
            
            # FMP returns dict with 'closes', 'volumes', 'data' arrays
            prices = []
            dates = []
            
            if isinstance(data, dict):
                # Method 1: Use pre-extracted arrays (preferred)
                if "closes" in data:
                    prices = [_safe_float(p) for p in data["closes"]]
                    prices = [p for p in prices if p is not None]
                
                if "dates" in data:
                    dates = data["dates"]
                
                # Method 2: Fallback to 'data' array
                if not prices and "data" in data and isinstance(data["data"], list):
                    for row in data["data"]:
                        if isinstance(row, dict):
                            close = _safe_float(row.get("Close") or row.get("close"))
                            date = row.get("Date") or row.get("date")
                            if close is not None:
                                prices.append(close)
                            if date:
                                dates.append(date)
            
            if not prices:
                logger.warning(f"No price data extracted for {ticker}")
                return None
            
            # Compute returns
            returns = _compute_returns(prices)
            
            return {
                "ticker": ticker,
                "prices": prices,
                "returns": returns,
                "dates": dates[1:] if dates else [],  # Align with returns
                "n_observations": len(returns),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch history for {ticker}: {e}")
            return None
    
    async def fetch_ticker_data(
        self,
        tickers: List[str],
        lookback_days: int = 252,
        include_vix: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch historical data for arbitrary tickers (stocks, ETFs, etc.).
        
        Args:
            tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
            lookback_days: Number of trading days to fetch
            include_vix: Fetch VIX for temperature (T)
            
        Returns:
            Dict with:
                - 'returns_df': DataFrame of daily returns
                - 'prices_dict': Dict of ticker -> prices for RSI breadth
                - 'tickers': List of tickers successfully fetched
                - 'n_observations': Number of valid observations
                - 'vix_data': VIX history (if include_vix)
        """
        import asyncio
        
        ticker_data = {}
        all_returns = {}
        prices_dict = {}
        
        # Fetch each ticker with rate limiting
        for i, ticker in enumerate(tickers):
            try:
                history = await self.fetch_etf_history(ticker, lookback_days)
                if history and history["returns"]:
                    ticker_data[ticker] = history
                    all_returns[ticker] = history["returns"]
                    prices_dict[ticker] = history["prices"]
                    logger.info(f"Fetched {ticker}: {len(history['returns'])} returns")
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
            
            # Rate limiting
            if i < len(tickers) - 1:
                await asyncio.sleep(0.2)
        
        if not all_returns:
            logger.error("No ticker data fetched successfully")
            return {
                "returns_df": pd.DataFrame(),
                "prices_dict": {},
                "ticker_data": {},
                "tickers": [],
                "n_observations": 0,
            }
        
        # Align all returns to same length (use shortest)
        min_len = min(len(r) for r in all_returns.values())
        
        # Create aligned DataFrame (most recent observations)
        aligned_returns = {
            ticker: returns[-min_len:]
            for ticker, returns in all_returns.items()
        }
        
        # Align prices too
        aligned_prices = {
            ticker: prices[-min_len-1:]  # +1 because returns has one less
            for ticker, prices in prices_dict.items()
        }
        
        returns_df = pd.DataFrame(aligned_returns)
        
        result = {
            "returns_df": returns_df,
            "prices_dict": aligned_prices,
            "ticker_data": ticker_data,
            "tickers": list(aligned_returns.keys()),
            "n_observations": min_len,
        }
        
        # Fetch VIX for temperature (T)
        if include_vix:
            vix_data = await self.fetch_vix_data(lookback_days)
            result["vix_data"] = vix_data
        
        return result

    async def fetch_all_sector_data(
        self,
        sectors: Optional[List[str]] = None,
        lookback_days: int = 252,
        include_vix: bool = True,
        include_greek_flow: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch historical data for all sector ETFs plus Ising model parameters.
        
        Args:
            sectors: List of sector names (e.g., ["technology", "healthcare"])
                     If None, fetches all 11 SPDR sectors.
            lookback_days: Number of trading days to fetch
            include_vix: Fetch VIX for temperature (T)
            include_greek_flow: Fetch sector greek flow for coupling (J)
            
        Returns:
            Dict with:
                - 'returns_df': DataFrame of daily returns (rows=dates, cols=sectors)
                - 'sector_data': Raw data per sector
                - 'prices_dict': Dict of sector -> prices for RSI breadth
                - 'tickers': List of tickers fetched
                - 'n_observations': Number of valid observations
                - 'vix_data': VIX history (if include_vix)
                - 'greek_flow_data': Sector greek flows (if include_greek_flow)
        """
        import asyncio
        
        # Determine which ETFs to fetch
        if sectors:
            tickers_to_fetch = {
                s: SECTOR_ETFS.get(s.lower().replace(" ", "_"), s)
                for s in sectors
            }
        else:
            tickers_to_fetch = SECTOR_ETFS.copy()
        
        sector_data = {}
        all_returns = {}
        
        # Fetch each ETF with rate limiting
        for i, (sector, ticker) in enumerate(tickers_to_fetch.items()):
            try:
                history = await self.fetch_etf_history(ticker, lookback_days)
                if history and history["returns"]:
                    sector_data[sector] = history
                    all_returns[sector] = history["returns"]
                    logger.info(f"Fetched {ticker}: {len(history['returns'])} returns")
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
            
            # Rate limiting
            if i < len(tickers_to_fetch) - 1:
                await asyncio.sleep(0.2)
        
        if not all_returns:
            logger.error("No sector data fetched successfully")
            return {
                "returns_df": pd.DataFrame(),
                "sector_data": {},
                "tickers": [],
                "n_observations": 0,
            }
        
        # Align all returns to same length (use shortest)
        min_len = min(len(r) for r in all_returns.values())
        
        # Create aligned DataFrame (most recent observations)
        aligned_returns = {
            sector: returns[-min_len:]
            for sector, returns in all_returns.items()
        }
        
        returns_df = pd.DataFrame(aligned_returns)
        
        # Build prices_dict for external field computation (RSI breadth)
        prices_dict = {}
        for sector, data in sector_data.items():
            if data and "prices" in data and data["prices"]:
                prices_dict[sector] = data["prices"]
        
        result = {
            "returns_df": returns_df,
            "sector_data": sector_data,
            "prices_dict": prices_dict,  # For discretionary/macro field RSI breadth
            "tickers": [SECTOR_ETFS.get(s, s) for s in aligned_returns.keys()],
            "n_observations": min_len,
        }
        
        # Fetch VIX for temperature (T)
        if include_vix:
            vix_data = await self.fetch_vix_data(lookback_days)
            result["vix_data"] = vix_data
        
        # Fetch sector greek flows for coupling (J)
        if include_greek_flow:
            greek_flow_data = await self.fetch_all_sector_greek_flows()
            result["greek_flow_data"] = greek_flow_data
        
        return result

    async def fetch_fred_data(self) -> Dict[str, Any]:
        """
        Fetch FRED macro indicators for external field calculation.
        
        Fetches:
        - Credit Spread (BAMLH0A0HYM2) - risk appetite
        - Yield Curve (T10Y2Y) - recession signal  
        - M2 Money Supply (M2SL) - liquidity conditions
        
        Returns:
            Dict with 'credit_spread', 'yield_curve', 'm2_change' keys,
            each containing 'available', 'current', 'percentile' etc.
        """
        result = {}
        
        try:
            econ_server = EconomicDataServer()
            await econ_server.connect()
            logger.info("[FRED] Connected to EconomicDataServer")
        except Exception as e:
            logger.warning(f"[FRED] EconomicDataServer connection failed: {e}")
            return {"error": str(e), "available": False}
        
        try:
            # Calculate date range (1 year for percentile calculation)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            for name, config in FRED_SERIES.items():
                series_id = config["series_id"]
                try:
                    data = await econ_server.get_series_data(series_id, start_str, end_str)
                    
                    if data and "data" in data and len(data["data"]) > 0:
                        values = [d.get("value") for d in data["data"] if d.get("value") is not None]
                        
                        if values:
                            # For M2, calculate YoY change
                            if config.get("yoy") and len(values) >= 13:
                                # Monthly data: compare to 12 months ago
                                current = values[-1]
                                year_ago = values[-13] if len(values) >= 13 else values[0]
                                yoy_change = (current - year_ago) / year_ago if year_ago else 0
                                current_val = yoy_change * 100  # Convert to percentage
                            else:
                                current_val = values[-1]
                            
                            # Calculate percentile
                            if config.get("yoy") and len(values) >= 13:
                                # Calculate YoY for all available periods
                                yoy_series = []
                                for i in range(13, len(values)):
                                    yoy = (values[i] - values[i-12]) / values[i-12] if values[i-12] else 0
                                    yoy_series.append(yoy * 100)
                                percentile = sum(1 for v in yoy_series if v <= current_val) / len(yoy_series) if yoy_series else 0.5
                            else:
                                percentile = sum(1 for v in values if v <= current_val) / len(values)
                            
                            result[name] = {
                                "available": True,
                                "series_id": series_id,
                                "current": float(current_val),
                                "percentile": float(percentile),
                                "description": config["description"],
                                "invert": config.get("invert", False),
                            }
                            logger.info(f"[FRED] {name}: {current_val:.2f} (percentile: {percentile:.0%})")
                        else:
                            result[name] = {"available": False, "error": "No values in response"}
                    else:
                        result[name] = {"available": False, "error": "No data returned"}
                        
                except Exception as e:
                    logger.warning(f"[FRED] Failed to fetch {name} ({series_id}): {e}")
                    result[name] = {"available": False, "error": str(e)}
                    
        finally:
            await econ_server.cleanup()
        
        return result

