"""
Simple adapter for risk calculation data transformation.
Converts between MCP server formats and risk module formats.
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Union
import datetime


def _extract_closes_and_dates(ticker_data: dict) -> tuple:
    """
    Extract close prices and dates from ticker data, handling both YFinance and FMP formats.
    
    Args:
        ticker_data: Dict containing historical data in either format
        
    Returns:
        Tuple of (closes list, dates list)
    """
    closes = []
    dates = []
    
    # Format 1: YFinance/FMP unified format with "data" array containing {Date, Close, ...} dicts
    if 'data' in ticker_data and isinstance(ticker_data['data'], list):
        for row in ticker_data['data']:
            if isinstance(row, dict) and 'Close' in row:
                closes.append(row['Close'])
                if 'Date' in row:
                    dates.append(row['Date'])
    
    # Format 2: FMP array format with separate "dates" and "closes"/"prices" arrays
    elif 'dates' in ticker_data and ('closes' in ticker_data or 'prices' in ticker_data):
        dates = ticker_data.get('dates', [])
        closes = ticker_data.get('closes') or ticker_data.get('prices', [])
    
    return closes, dates


def adapt_mcp_to_prices(mcp_response: Union[str, dict], tickers: List[str]) -> pd.DataFrame:
    """
    Convert MCP server response to price DataFrame for risk modules.
    Gracefully handles missing/invalid ticker data by excluding them.
    
    Supports both YFinance format and FMP format:
    - YFinance: {"data": [{"Date": "...", "Close": ...}, ...]}
    - FMP: {"dates": [...], "closes": [...]} or {"data": [{"Date": "...", "Close": ...}, ...]}
    
    Args:
        mcp_response: Raw MCP response (JSON string or dict)
        tickers: List of tickers to extract
        
    Returns:
        DataFrame with ticker columns (only tickers with valid data) and price rows with DatetimeIndex
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Parse if string
    if isinstance(mcp_response, str):
        data = json.loads(mcp_response)
    else:
        data = mcp_response
    
    # Handle multiple ticker format (from composite tools)
    if isinstance(data, dict):
        # Multiple tickers - only process those present in response
        available_tickers = [t for t in tickers if t in data]
        
        if not available_tickers:
            raise ValueError(f"No data available for any requested ticker. Requested: {tickers}")
        
        all_prices = {}
        dates = None
        valid_tickers = []
        
        # Find the minimum length across all tickers and extract dates
        min_length = float('inf')
        for ticker in available_tickers:
            ticker_data = data[ticker]
            if not isinstance(ticker_data, dict):
                continue
            
            # Extract closes and dates using format-agnostic helper
            closes, ticker_dates = _extract_closes_and_dates(ticker_data)
            
            if len(closes) > 10:
                min_length = min(min_length, len(closes))
                valid_tickers.append(ticker)
                # Extract dates from the first valid ticker if not done yet
                if dates is None and ticker_dates:
                    dates = ticker_dates
        
        if not valid_tickers:
            raise ValueError(f"No tickers with sufficient data (>10 points). Requested: {tickers}")
        
        # Extract close prices for each valid ticker
        for ticker in valid_tickers:
            ticker_data = data[ticker]
            closes, _ = _extract_closes_and_dates(ticker_data)
            # Truncate to min length
            all_prices[ticker] = closes[:min_length]
        
        # Log skipped tickers
        skipped = set(tickers) - set(valid_tickers)
        if skipped:
            logger.info(f"Excluded tickers with insufficient data: {', '.join(sorted(skipped))}")
        
        # Create DataFrame with DatetimeIndex
        df = pd.DataFrame(all_prices)
        if dates and len(dates) >= len(df):
            df.index = pd.to_datetime(dates[:len(df)])
        return df
    
    # Handle single ticker MCP format
    elif isinstance(data, dict) and ('data' in data or 'dates' in data):
        # Single ticker from MCP - use format-agnostic extraction
        ticker = data.get('ticker', tickers[0] if tickers else 'UNKNOWN')
        closes, dates = _extract_closes_and_dates(data)
        
        df = pd.DataFrame({ticker: closes})
        if dates and len(dates) == len(df):
            df.index = pd.to_datetime(dates)
        return df
    
    # Already in correct format
    return pd.DataFrame(data)


def prepare_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate returns from prices."""
    return prices.pct_change().dropna()


def jsonify_results(obj: Any) -> Any:
    """
    Convert numpy arrays and other non-JSON types to JSON-serializable format.
    
    Args:
        obj: Any object potentially containing numpy arrays
        
    Returns:
        JSON-serializable version
    """
    # Handle None
    if obj is None:
        return None
    
    # Handle numpy types first (most common case)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    # Handle pandas
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='list')
    if isinstance(obj, pd.Series):
        return obj.tolist()
    
    # Handle collections recursively
    if isinstance(obj, dict):
        return {k: jsonify_results(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify_results(v) for v in obj]
    
    return obj