"""
Chart Data Resolver - Fetches data via FMP MCP servers for chart builders.

Following the risk tools pattern but using FMP servers for better data.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def fetch_chart_data_fmp(
    symbol: str, 
    period: str = "1Y", 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch chart data using FMP MCP server, following risk tools pattern.
    
    Args:
        symbol: Ticker symbol
        period: Time period (1D, 5D, 1M, 3M, 6M, 1Y, 2Y, 5Y, max)
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        
    Returns:
        Dict with price data or None if failed
    """
    try:
        # Try FMP server first
        try:
            from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
            market_server = FMPMarketDataServer()
            logger.info(f"Using FMP server for {symbol}")
        except ImportError:
            # Fallback to YFinance if FMP not available
            from core.mcp_servers.YFinanceServer import YFinanceServer
            market_server = YFinanceServer()
            logger.info(f"Using YFinance fallback for {symbol}")
        
        # Calculate dates if not provided
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            # Convert period to days
            period_days = {
                "1D": 1, "5D": 5, "1M": 30, "3M": 90,
                "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825,
                "max": 7300  # 20 years
            }.get(period, 365)
            start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        
        # For FMP, we need to discover fields first
        if hasattr(market_server, 'discover_fields'):
            # FMP server - use discovery
            fields_response = await market_server.discover_fields(symbol)
            
            if not fields_response or not fields_response.get("available_fields"):
                logger.warning(f"No fields discovered for {symbol}")
                # Try direct historical data as fallback
                data = await market_server.get_historical_data(symbol, period=period, start=start_date, end=end_date)
                if data:
                    return json.loads(data) if isinstance(data, str) else data
                return None
            
            # Get OHLCV fields dynamically (no hardcoding!)
            available = fields_response["available_fields"]
            
            # Build query for all price fields
            result = {}
            for field in available:
                field_lower = field.lower()
                # Get any price-related field
                if any(term in field_lower for term in ["open", "high", "low", "close", "volume", "price"]):
                    data_response = await market_server.get_field_data(
                        symbol=symbol,
                        field=field,
                        start_date=start_date,
                        end_date=end_date
                    )
                    if data_response and "values" in data_response:
                        result[field] = data_response["values"]
            
            return result if result else None
            
        else:
            # YFinance fallback - use direct historical data
            data = await market_server.get_historical_data(symbol, period=period, start=start_date, end=end_date)
            if data:
                return json.loads(data) if isinstance(data, str) else data
            return None
        
    except Exception as e:
        logger.error(f"Error fetching chart data for {symbol}: {e}")
        return None


async def resolve_price_line_data(
    symbol: str,
    period: str = "1Y",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Optional[Dict[str, List]]:
    """
    Resolve price line data for a chart.
    
    Returns:
        Dict with 'prices' and 'dates' arrays
    """
    try:
        # Fetch data using FMP/YFinance server
        data = await fetch_chart_data_fmp(symbol, period, start_date, end_date)
        
        if not data:
            logger.warning(f"No data returned for {symbol}")
            return None
        
        prices = []
        dates = []
        
        # Handle FMP format (field data with values array)
        close_field = None
        for field_name in data.keys():
            if "close" in field_name.lower() or "price" in field_name.lower():
                close_field = field_name
                break
        
        if close_field and isinstance(data[close_field], list):
            # FMP format: [{"date": "2024-01-01", "value": 123.45}, ...]
            for item in data[close_field]:
                dates.append(item.get("date", ""))
                prices.append(item.get("value", 0))
        elif "close" in data:
            # YFinance format
            close_data = data["close"]
            if isinstance(close_data, dict):
                for date_str, price in close_data.items():
                    dates.append(date_str)
                    prices.append(price)
        
        if prices and dates:
            logger.info(f"Resolved {len(prices)} price points for {symbol}")
            return {
                "prices": prices,
                "dates": dates
            }
        
        logger.warning(f"Could not extract price data from response for {symbol}")
        return None
        
    except Exception as e:
        logger.error(f"Error resolving price line for {symbol}: {e}")
        return None


async def resolve_ohlc_data(
    symbol: str,
    period: str = "1Y",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Optional[Dict[str, List]]:
    """
    Resolve OHLC data for a candlestick chart.
    
    Returns:
        Dict with 'open', 'high', 'low', 'close', 'dates' arrays
    """
    try:
        # Fetch data using FMP/YFinance server
        data = await fetch_chart_data_fmp(symbol, period, start_date, end_date)
        
        if not data:
            logger.warning(f"No data returned for {symbol}")
            return None
        
        # Initialize arrays
        open_prices = []
        high_prices = []
        low_prices = []
        close_prices = []
        dates = []
        
        # Find OHLC fields dynamically
        ohlc_fields = {}
        for field_name in data.keys():
            field_lower = field_name.lower()
            if "open" in field_lower and "open" not in ohlc_fields:
                ohlc_fields["open"] = field_name
            elif "high" in field_lower and "high" not in ohlc_fields:
                ohlc_fields["high"] = field_name
            elif "low" in field_lower and "low" not in ohlc_fields:
                ohlc_fields["low"] = field_name
            elif ("close" in field_lower or "price" in field_lower) and "close" not in ohlc_fields:
                ohlc_fields["close"] = field_name
        
        # Extract OHLC data
        if len(ohlc_fields) >= 4:
            # We have all OHLC fields
            # Get dates from first field
            first_field = list(ohlc_fields.values())[0]
            if isinstance(data[first_field], list):
                for item in data[first_field]:
                    dates.append(item.get("date", ""))
                
                # Extract values for each field
                for item in data[ohlc_fields["open"]]:
                    open_prices.append(item.get("value", 0))
                for item in data[ohlc_fields["high"]]:
                    high_prices.append(item.get("value", 0))
                for item in data[ohlc_fields["low"]]:
                    low_prices.append(item.get("value", 0))
                for item in data[ohlc_fields["close"]]:
                    close_prices.append(item.get("value", 0))
            
            if open_prices and dates:
                logger.info(f"Resolved {len(dates)} OHLC points for {symbol}")
                return {
                    "open": open_prices,
                    "high": high_prices,
                    "low": low_prices,
                    "close": close_prices,
                    "dates": dates
                }
        
        # Fallback to price line if OHLC not available
        logger.info(f"OHLC not available for {symbol}, falling back to price line")
        price_data = await resolve_price_line_data(symbol, period, start_date, end_date)
        if price_data:
            prices = price_data["prices"]
            return {
                "open": prices,
                "high": prices,
                "low": prices,
                "close": prices,
                "dates": price_data["dates"]
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error resolving OHLC for {symbol}: {e}")
        return None


async def resolve_portfolio_data(
    tickers: List[str],
    period: str = "1Y",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch data for multiple tickers (portfolio charts).
    
    Returns:
        Dict with ticker data
    """
    try:
        portfolio_data = {}
        
        for ticker in tickers:
            data = await resolve_price_line_data(ticker, period, start_date, end_date)
            if data:
                portfolio_data[ticker] = data
            else:
                logger.warning(f"Failed to get data for {ticker}")
        
        if portfolio_data:
            logger.info(f"Resolved portfolio data for {len(portfolio_data)} tickers")
            return portfolio_data
        
        logger.warning(f"Failed to fetch portfolio data for any tickers: {tickers}")
        return None
        
    except Exception as e:
        logger.error(f"Error resolving portfolio data: {e}")
        return None