"""
FMP Historical Data - Handles historical data operations
Following KISS principle - focused only on historical data fetching
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime as _dt, timedelta

from .ddc_loader import DDCLoader
from .data_fetcher import FMPDataFetcher
from .field_map_manager import FieldMapManager
from core.utils import gather_dict

logger = logging.getLogger(__name__)


class FMPHistoricalData:
    """
    Handles historical data operations for FMP.
    Fetches time series data for prices and metrics.
    """
    
    def __init__(self, api_key: str, data_fetcher: FMPDataFetcher, 
                 ddc_loader: DDCLoader, field_manager: FieldMapManager):
        """Initialize historical data handler with dependencies"""
        self.api_key = api_key
        self.data_fetcher = data_fetcher
        self.ddc_loader = ddc_loader
        self.field_manager = field_manager
        
    async def get_historical_data(self, symbol: str, period: str = None,
                                 start: str = None, end: str = None) -> Optional[str]:
        """
        Get historical price data for charting.
        
        Args:
            symbol: Stock symbol
            period: Time period (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 2Y, 5Y, max)
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            
        Returns:
            JSON string with chart data or None
        """
        # Convert period to date range if needed
        if period and not start:
            start, end = self._period_to_dates(period)
        
        # Default to last month if nothing specified
        if not start and not end:
            end = _dt.now().strftime("%Y-%m-%d")
            start = (_dt.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Get the FULL historical price dataset (not the light version)
        dataset = self.ddc_loader.get_dataset("historical-price-full")
        if not dataset:
            logger.error("Historical price dataset not found in DDC catalog")
            return None
        
        try:
            # Prepare parameters
            params = {}
            if start:
                params["from"] = start
            if end:
                params["to"] = end
            
            # Fetch data
            data = await self.data_fetcher.fetch_dataset(
                symbol, 
                dataset,
                historical_params=params
            )
            
            if not data:
                return None
            
            # FMP returns newest first, reverse for charting (oldest first)
            if isinstance(data, list):
                data = list(reversed(data))
            
            # Convert to chart format
            chart_data = self._convert_to_chart_format(data)
            
            # Return as JSON string for compatibility
            import json
            return json.dumps(chart_data)
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return None
    
    async def get_historical_metrics(self, symbol: str, fields: List[str],
                                    period: str = None, limit: int = 20) -> Dict[str, Any]:
        """
        Get historical data for specific financial metrics.
        
        This is the key method for fetching historical EPS, FCF, etc for charting.
        
        Args:
            symbol: Stock symbol
            fields: List of field names to fetch (e.g., ['eps', 'fcfPerShare'])
            period: Time period or None for default
            limit: Maximum number of periods to fetch
            
        Returns:
            Dict with field -> time series data
        """
        # Map fields to their endpoints using field manager
        endpoints = self.field_manager.get_endpoints_for_fields(fields)
        
        if not endpoints:
            logger.warning(f"No endpoints found for fields: {fields}")
            return {}
        
        async def fetch_endpoint(endpoint_name: str, endpoint_fields: List[str]) -> Dict[str, List[Dict[str, Any]]]:
            dataset = self.ddc_loader.get_dataset(endpoint_name)
            if not dataset:
                logger.warning("Dataset %s not found in DDC", endpoint_name)
                return {}

            params = {"limit": limit}
            if period:
                params["period"] = period

            try:
                data = await self.data_fetcher.fetch_dataset(
                    symbol,
                    dataset,
                    historical_params=params,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Error fetching from %s: %s", endpoint_name, exc)
                return {}

            return self._extract_field_series(data, endpoint_fields)

        factories = {
            endpoint_name: (lambda name=endpoint_name, fields=endpoint_fields: fetch_endpoint(name, fields))
            for endpoint_name, endpoint_fields in endpoints.items()
        }

        raw_results = await gather_dict(factories, concurrency_limit=4) if factories else {}

        results: Dict[str, List[Dict[str, Any]]] = {}
        for endpoint_map in raw_results.values():
            for field, series in endpoint_map.items():
                results[field] = series

        return results
    
    def _period_to_dates(self, period: str) -> tuple:
        """
        Convert period string to date range.

        Args:
            period: Period string (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 2Y, 5Y, max) - case insensitive

        Returns:
            Tuple of (start_date, end_date) as strings
        """
        end_date = _dt.now()

        # Normalize to uppercase for case-insensitive matching
        period = period.upper() if period else ""

        # Parse period
        if period == "1D":
            start_date = end_date - timedelta(days=1)
        elif period == "5D":
            start_date = end_date - timedelta(days=5)
        elif period == "1M":
            start_date = end_date - timedelta(days=30)
        elif period == "3M":
            start_date = end_date - timedelta(days=90)
        elif period == "6M":
            start_date = end_date - timedelta(days=180)
        elif period == "YTD":
            start_date = _dt(end_date.year, 1, 1)
        elif period == "1Y":
            start_date = end_date - timedelta(days=365)
        elif period == "2Y":
            start_date = end_date - timedelta(days=730)
        elif period == "3Y":
            start_date = end_date - timedelta(days=1095)
        elif period == "5Y":
            start_date = end_date - timedelta(days=1825)
        elif period == "MAX":
            start_date = _dt(2000, 1, 1)  # Far back enough
        else:
            # Default to 1 month
            start_date = end_date - timedelta(days=30)
        
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def _extract_field_series(self, data: Any, endpoint_fields: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        extracted: Dict[str, List[Dict[str, Any]]] = {}
        if not data:
            return extracted

        if isinstance(data, list):
            for field in endpoint_fields:
                series: List[Dict[str, Any]] = []
                for item in data:
                    if isinstance(item, dict) and field in item:
                        series.append({
                            "date": item.get("date") or item.get("calendarYear"),
                            "value": item[field],
                        })
                if series:
                    extracted[field] = series
        elif isinstance(data, dict):
            for field in endpoint_fields:
                if field in data:
                    extracted[field] = [{
                        "date": data.get("date") or _dt.now().strftime("%Y-%m-%d"),
                        "value": data[field],
                    }]

        return extracted
    
    def _convert_to_chart_format(self, data: Any) -> Dict[str, Any]:
        """
        Convert FMP data to chart-friendly format.
        
        Returns data in BOTH formats:
        1. Array format (dates, prices, closes, etc.) for charting
        2. "data" array format with {Date, Close, Open, ...} dicts for risk tools (YFinance-compatible)
        
        Args:
            data: Raw FMP data (list or dict)
            
        Returns:
            Chart-formatted data with dates, prices, volumes, and YFinance-compatible "data" array
        """
        if not data:
            return {}
        
        # Ensure we have a list
        if isinstance(data, dict):
            data = [data]
        
        if not isinstance(data, list) or not data:
            return {}
        
        # Extract arrays for charting
        dates = []
        prices = []
        volumes = []
        opens = []
        highs = []
        lows = []
        closes = []
        
        # Also build YFinance-compatible "data" array for risk tools
        data_array = []
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Get date - handle FMP format "2025-08-21 00:00:00"
            date_str = item.get("date", "")
            if " " in date_str:
                date_str = date_str.split()[0]
            
            if date_str:
                dates.append(date_str)
                
                # Build YFinance-compatible row
                row = {"Date": date_str}
                
                # Price data
                if "close" in item:
                    prices.append(item["close"])
                    closes.append(item["close"])
                    row["Close"] = item["close"]
                elif "price" in item:
                    prices.append(item["price"])
                    row["Close"] = item["price"]
                
                # OHLC data
                if "open" in item:
                    opens.append(item["open"])
                    row["Open"] = item["open"]
                if "high" in item:
                    highs.append(item["high"])
                    row["High"] = item["high"]
                if "low" in item:
                    lows.append(item["low"])
                    row["Low"] = item["low"]
                
                # Volume
                if "volume" in item:
                    volumes.append(item["volume"])
                    row["Volume"] = item["volume"]
                
                data_array.append(row)
        
        # Build result with both formats
        result = {"dates": dates}
        
        if prices:
            result["prices"] = prices
        if opens:
            result["opens"] = opens
        if highs:
            result["highs"] = highs
        if lows:
            result["lows"] = lows
        if closes:
            result["closes"] = closes
        if volumes:
            result["volumes"] = volumes
        
        # Add YFinance-compatible format for risk tools
        result["data"] = data_array
        result["data_count"] = len(data_array)
        
        # Add source attribution for audit trail
        result["source"] = "Financial Modeling Prep (FMP)"
        result["source_type"] = "market_data"
        
        return result
