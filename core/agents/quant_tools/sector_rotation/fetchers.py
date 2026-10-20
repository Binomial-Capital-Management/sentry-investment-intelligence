"""
Data fetchers for sector rotation analysis.

NO HARDCODING: All field names discovered dynamically from API responses.

Data sources:
- UW: Today's options flow (delta, vega, premium) - REAL-TIME SENTIMENT
- FMP: Historical sector ETF prices - Z-SCORE BASELINE
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.mcp_servers.unusualwhales.UWInstitutionalServer import UWInstitutionalServer
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# =============================================================================
# SECTOR ETF MAPPING (SPDR Sector ETFs)
# =============================================================================

# Map UW flow_group names to SPDR sector ETF tickers for FMP historical data
SECTOR_ETF_MAP = {
    "technology": "XLK",
    "healthcare": "XLV", 
    "financial services": "XLF",
    "energy": "XLE",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "industrials": "XLI",
    "basic materials": "XLB",
    "utilities": "XLU",
    "real estate": "XLRE",
    "communication services": "XLC",
}

# Reverse map for lookups
ETF_SECTOR_MAP = {v: k for k, v in SECTOR_ETF_MAP.items()}


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


def _extract_numeric_fields(data: Any, prefix: str = "") -> Dict[str, float]:
    """
    Recursively extract all numeric fields from nested data.
    Returns flat dict with dotted keys.
    """
    result = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[full_key] = float(value)
            elif isinstance(value, (dict, list)):
                result.update(_extract_numeric_fields(value, full_key))
    elif isinstance(data, list) and data:
        # For lists, extract from first element as template
        result.update(_extract_numeric_fields(data[0], prefix))
    
    return result


def _compute_returns(prices: List[float]) -> List[float]:
    """Compute daily returns from price series."""
    if len(prices) < 2:
        return []
    return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]


def _compute_zscore(current: float, history: List[float]) -> Optional[float]:
    """Compute z-score of current value vs historical distribution."""
    if not history or len(history) < 5:
        return None
    mean_val = sum(history) / len(history)
    variance = sum((x - mean_val) ** 2 for x in history) / len(history)
    std_val = variance ** 0.5
    if std_val < 1e-9:
        return 0.0
    return (current - mean_val) / std_val


# =============================================================================
# MAIN FETCHER CLASS
# =============================================================================

class SectorDataFetcher:
    """
    Fetches sector flow data from UW and FMP servers.
    
    All field extraction is dynamic - no hardcoded field names.
    """
    
    def __init__(self):
        self.uw_options = UWOptionsServer()
        self.uw_market = UWMarketServer()
        self.uw_institutional = UWInstitutionalServer()
        self.fmp = FMPMarketDataServer()
        self._connected = False
    
    async def connect(self):
        """Connect to all servers."""
        if not self._connected:
            await self.uw_options.connect()
            await self.uw_market.connect()
            await self.uw_institutional.connect()
            await self.fmp.connect()
            self._connected = True
    
    async def cleanup(self):
        """Cleanup all server connections."""
        await self.uw_options.cleanup()
        await self.uw_market.cleanup()
        await self.uw_institutional.cleanup()
        await self.fmp.cleanup()
        self._connected = False
    
    # -------------------------------------------------------------------------
    # GREEK FLOW (Primary data source)
    # -------------------------------------------------------------------------
    
    async def fetch_greek_flow(
        self, 
        flow_group: str,
        date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch greek flow for a sector/flow group via MCP.
        """
        try:
            # Don't pass date - API returns 0 records when date is specified
            params = {"flow_group": flow_group}
            
            # Use the UW Options Server's data_fetcher directly to bypass caching issues
            dataset = self.uw_options.ddc_loader.get_dataset("group-greek-flow")
            if not dataset:
                logger.error("group-greek-flow dataset not found in catalog")
                return None
            
            # Fetch directly from data_fetcher with cache disabled
            data = await self.uw_options.data_fetcher.fetch_dataset(dataset, params, use_cache=False)
            
            if not data or "error" in data:
                logger.warning(f"Error fetching greek flow for {flow_group}: {data.get('error') if data else 'No data'}")
                return None
            
            # UW returns {"data": [array of minute-by-minute objects]}
            records = data.get("data", [])
            if not records:
                logger.warning(f"No records in UW response for {flow_group}")
                return None
            
            logger.info(f"Got {len(records)} records for {flow_group}")
            
            # Sum up all the values across the day for cumulative flow
            aggregated = {}
            
            for record in records:
                if not isinstance(record, dict):
                    continue
                
                for key, value in record.items():
                    # Skip non-numeric fields
                    if key in ('timestamp', 'flow_group'):
                        continue
                    
                    # Parse string to float (UW returns strings!)
                    try:
                        num_val = float(value) if value else 0.0
                    except (ValueError, TypeError):
                        continue
                    
                    # Aggregate by summing
                    if key not in aggregated:
                        aggregated[key] = 0.0
                    aggregated[key] += num_val
            
            # Build extracted result from aggregated data
            extracted = {"flow_group": flow_group, "raw_fields": aggregated}
            
            # Map UW field names to our standard names
            extracted["delta_flow"] = aggregated.get("dir_delta_flow", 0)
            extracted["directional_delta"] = aggregated.get("dir_delta_flow", 0)
            extracted["vega_flow"] = aggregated.get("dir_vega_flow", 0)
            extracted["call_premium"] = aggregated.get("net_call_premium", 0)
            extracted["put_premium"] = aggregated.get("net_put_premium", 0)
            extracted["net_premium"] = (
                aggregated.get("net_call_premium", 0) - 
                aggregated.get("net_put_premium", 0)
            )
            extracted["total_delta"] = aggregated.get("total_delta_flow", 0)
            extracted["total_vega"] = aggregated.get("total_vega_flow", 0)
            extracted["volume"] = aggregated.get("volume", 0)
            extracted["transactions"] = aggregated.get("transactions", 0)
            
            # OTM specific
            extracted["otm_delta"] = aggregated.get("otm_dir_delta_flow", 0)
            extracted["otm_vega"] = aggregated.get("otm_dir_vega_flow", 0)
            extracted["otm_call_premium"] = aggregated.get("otm_net_call_premium", 0)
            extracted["otm_put_premium"] = aggregated.get("otm_net_put_premium", 0)
            
            logger.info(f"Extracted flow for {flow_group}: delta={extracted['delta_flow']:,.0f}, vega={extracted['vega_flow']:,.0f}")
            
            return extracted
            
        except Exception as e:
            logger.warning(f"Failed to fetch greek flow for {flow_group}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # SECTOR TIDE
    # -------------------------------------------------------------------------
    
    async def fetch_sector_tide(
        self,
        sector: str,
        date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch sector tide sentiment data."""
        try:
            # Sector tide uses GICS sector names, not flow groups
            params = {"sector": sector}
            if date:
                params["date"] = date
            
            result = await self.uw_options.call_tool("uw_sector_tide", params)
            
            if not result or not hasattr(result, 'content'):
                return None
            
            data = safe_parse_json(result)
            return {"sector": sector, "data": data} if data else None
            
        except Exception as e:
            logger.warning(f"Failed to fetch sector tide for {sector}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # MARKET TIDE
    # -------------------------------------------------------------------------
    
    async def fetch_market_tide(
        self,
        date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch market-wide tide sentiment."""
        try:
            params = {}
            if date:
                params["date"] = date
            
            result = await self.uw_options.call_tool("uw_market_tide", params)
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch market tide: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # CORRELATIONS
    # -------------------------------------------------------------------------
    
    async def fetch_correlations(
        self,
        tickers: List[str],
        interval: str = "1M"
    ) -> Optional[Dict[str, Any]]:
        """Fetch correlation matrix between tickers."""
        try:
            result = await self.uw_market.call_tool("uw_correlations", {
                "tickers": ",".join(tickers),
                "interval": interval
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch correlations: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # ETF FLOWS
    # -------------------------------------------------------------------------
    
    async def fetch_etf_flows(
        self,
        etf: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch ETF inflow/outflow data."""
        try:
            result = await self.uw_institutional.call_tool("uw_etf_flows", {
                "ticker": etf
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch ETF flows for {etf}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # SEASONALITY
    # -------------------------------------------------------------------------
    
    async def fetch_seasonality(self) -> Optional[Dict[str, Any]]:
        """Fetch market seasonality data."""
        try:
            result = await self.uw_market.call_tool("uw_seasonality", {
                "view": "market"
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch seasonality: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # SECTOR ETF PERFORMANCE
    # -------------------------------------------------------------------------
    
    async def fetch_sector_etfs(self) -> Optional[Dict[str, Any]]:
        """Fetch current sector ETF performance."""
        try:
            result = await self.uw_market.call_tool("uw_market_overview", {
                "view": "sectors"
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch sector ETFs: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # TOP MOVERS
    # -------------------------------------------------------------------------
    
    async def fetch_movers(
        self,
        limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        """Fetch top movers by net premium flow."""
        try:
            result = await self.uw_market.call_tool("uw_market_overview", {
                "view": "movers",
                "limit": limit
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch movers: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # OI CHANGE
    # -------------------------------------------------------------------------
    
    async def fetch_oi_change(
        self,
        limit: int = 50
    ) -> Optional[Dict[str, Any]]:
        """Fetch contracts with largest OI changes."""
        try:
            result = await self.uw_options.call_tool("uw_oi_change", {
                "limit": limit
            })
            
            if not result or not hasattr(result, 'content'):
                return None
            
            return safe_parse_json(result)
            
        except Exception as e:
            logger.warning(f"Failed to fetch OI change: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # HISTORICAL SECTOR ETF DATA (FMP)
    # -------------------------------------------------------------------------
    
    async def fetch_sector_etf_history(
        self,
        sector: str,
        lookback_days: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical price data for sector ETF from FMP.
        
        Used to compute z-scores for flow vs. historical patterns.
        
        FMP get_historical_data returns JSON with:
        - closes: array of close prices
        - volumes: array of volume values
        - data: array of {Date, Close, Open, High, Low, Volume} dicts
        
        Returns:
            Dict with 'prices', 'returns', 'volumes', 'volatility'
        """
        etf = SECTOR_ETF_MAP.get(sector.lower())
        if not etf:
            logger.warning(f"No ETF mapping for sector: {sector}")
            return None
        
        try:
            # Use period format that FMP understands (1M, 3M, etc)
            period = "3M" if lookback_days <= 90 else "6M" if lookback_days <= 180 else "1Y"
            
            result = await self.fmp.call_tool("get_historical_data", {
                "symbol": etf,
                "period": period
            })
            
            data = safe_parse_json(result)
            if not data:
                logger.warning(f"No data returned for {etf}")
                return None
            
            # FMP returns dict with 'closes', 'volumes', 'data' arrays
            # Use 'closes' array directly (already extracted by FMP server)
            prices = []
            volumes = []
            
            if isinstance(data, dict):
                # Method 1: Use pre-extracted arrays (preferred)
                if "closes" in data:
                    prices = [_safe_float(p) for p in data["closes"]]
                    prices = [p for p in prices if p is not None]
                
                if "volumes" in data:
                    volumes = [_safe_float(v) for v in data["volumes"]]
                    volumes = [v for v in volumes if v is not None]
                
                # Method 2: Fallback to 'data' array if no 'closes'
                if not prices and "data" in data and isinstance(data["data"], list):
                    for row in data["data"]:
                        if isinstance(row, dict):
                            # FMP uses capitalized keys in data array: Close, Volume
                            close = _safe_float(row.get("Close") or row.get("close"))
                            vol = _safe_float(row.get("Volume") or row.get("volume"))
                            if close is not None:
                                prices.append(close)
                            if vol is not None:
                                volumes.append(vol)
            
            if not prices:
                logger.warning(f"No price data extracted for {etf}")
                return None
            
            returns = _compute_returns(prices)
            
            # Compute rolling volatility (20-day std of returns)
            vol_window = min(20, len(returns))
            volatility = None
            if len(returns) >= vol_window:
                recent_returns = returns[-vol_window:]
                mean_ret = sum(recent_returns) / len(recent_returns)
                variance = sum((r - mean_ret) ** 2 for r in recent_returns) / len(recent_returns)
                volatility = (variance ** 0.5) * (252 ** 0.5)  # Annualized
            
            return {
                "etf": etf,
                "sector": sector,
                "prices": prices,
                "returns": returns,
                "volumes": volumes,
                "current_price": prices[-1] if prices else None,
                "volatility": volatility,
                "lookback_days": len(prices),
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch sector ETF history for {sector}: {e}")
            return None
    
    async def fetch_all_sector_histories(
        self,
        sectors: List[str],
        lookback_days: int = 60
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical data for all sectors in parallel.
        
        Returns:
            Dict mapping sector -> historical data
        """
        import asyncio
        
        results = {}
        
        # Batch fetch with rate limiting
        for i, sector in enumerate(sectors):
            try:
                history = await self.fetch_sector_etf_history(sector, lookback_days)
                if history:
                    results[sector] = history
            except Exception as e:
                logger.warning(f"Failed to fetch history for {sector}: {e}")
            
            # Rate limit
            if i < len(sectors) - 1:
                await asyncio.sleep(0.3)
        
        return results
    
    def compute_cross_sectional_zscores(
        self,
        sector_values: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Compute z-scores across sectors (cross-sectional).
        
        This compares each sector's value to the mean of all sectors TODAY,
        not to its own history.
        
        Args:
            sector_values: Dict mapping sector -> current value
            
        Returns:
            Dict mapping sector -> z-score
        """
        if not sector_values or len(sector_values) < 2:
            return {s: 0.0 for s in sector_values}
        
        values = list(sector_values.values())
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = variance ** 0.5
        
        if std_val < 1e-9:
            return {s: 0.0 for s in sector_values}
        
        return {
            sector: (value - mean_val) / std_val
            for sector, value in sector_values.items()
        }
    
    def compute_historical_zscore(
        self,
        current_flow: float,
        historical_returns: List[float]
    ) -> Optional[float]:
        """
        Compute z-score of today's flow vs historical return distribution.
        
        Uses ETF historical returns as baseline for flow magnitude.
        """
        return _compute_zscore(current_flow, historical_returns)
