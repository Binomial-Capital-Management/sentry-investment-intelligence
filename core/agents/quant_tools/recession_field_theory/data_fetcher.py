"""
Recession Field Theory - Data Fetcher

Fetches and aligns economic indicators from FRED and market data from FMP.
Handles different data frequencies (daily, weekly, monthly) and missing values.

Data retrieval patterns consistent with arimax_macro_forecast_tool.py and
correlation_matrix_tool.py.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# =============================================================================
# EXPANDED INDICATOR CONFIGURATION
# =============================================================================

# Core recession-predictive FRED indicators
# Organized by category with search terms and fallback IDs
DEFAULT_INDICATOR_CONFIG = {
    # =========================================================================
    # YIELD CURVE & INTEREST RATES (Most predictive category)
    # =========================================================================
    "yield_curve_10y2y": {
        "search_term": "10 year 2 year treasury spread",
        "fallback_id": "T10Y2Y",
        "weight": 0.12,
        "invert": False,  # Positive = expansion, negative/inverted = recession warning
        "category": "rates",
        "description": "10Y-2Y Treasury spread (inverts 6-18 months before recessions)"
    },
    "yield_curve_10y3m": {
        "search_term": "10 year 3 month treasury spread",
        "fallback_id": "T10Y3M",
        "weight": 0.10,
        "invert": False,
        "category": "rates",
        "description": "10Y-3M Treasury spread (alternative yield curve measure)"
    },
    "fed_funds_rate": {
        "search_term": "federal funds effective rate",
        "fallback_id": "FEDFUNDS",
        "weight": 0.05,
        "invert": True,  # Higher rates = tighter conditions = negative for growth
        "category": "rates",
        "description": "Federal funds effective rate"
    },
    
    # =========================================================================
    # EMPLOYMENT (Lagging but important)
    # =========================================================================
    "unemployment_claims": {
        "search_term": "initial unemployment claims",
        "fallback_id": "ICSA",
        "weight": 0.10,
        "invert": True,  # Higher claims = worse
        "category": "employment",
        "description": "Weekly initial unemployment claims (spikes in recessions)"
    },
    "continued_claims": {
        "search_term": "continued unemployment claims",
        "fallback_id": "CCSA",
        "weight": 0.05,
        "invert": True,
        "category": "employment",
        "description": "Continued unemployment claims"
    },
    "unemployment_rate": {
        "search_term": "unemployment rate",
        "fallback_id": "UNRATE",
        "weight": 0.05,
        "invert": True,
        "category": "employment",
        "description": "Civilian unemployment rate"
    },
    "nonfarm_payrolls": {
        "search_term": "nonfarm payrolls",
        "fallback_id": "PAYEMS",
        "weight": 0.05,
        "invert": False,  # Higher = expansion
        "category": "employment",
        "description": "Total nonfarm payrolls (employment growth)"
    },
    
    # =========================================================================
    # MANUFACTURING & PRODUCTION (Leading indicators)
    # =========================================================================
    "ism_pmi": {
        "search_term": "ISM manufacturing PMI",
        "fallback_id": "NAPM",
        "weight": 0.08,
        "invert": False,  # Above 50 = expansion
        "category": "manufacturing",
        "description": "ISM Manufacturing PMI (50 = neutral)"
    },
    "industrial_production": {
        "search_term": "industrial production index",
        "fallback_id": "INDPRO",
        "weight": 0.06,
        "invert": False,
        "category": "manufacturing",
        "description": "Industrial Production Index"
    },
    "capacity_utilization": {
        "search_term": "capacity utilization total industry",
        "fallback_id": "TCU",
        "weight": 0.04,
        "invert": False,
        "category": "manufacturing",
        "description": "Capacity Utilization: Total Industry"
    },
    "new_orders_durable": {
        "search_term": "manufacturers new orders durable goods",
        "fallback_id": "DGORDER",
        "weight": 0.04,
        "invert": False,
        "category": "manufacturing",
        "description": "Manufacturers' New Orders: Durable Goods"
    },
    
    # =========================================================================
    # CREDIT & FINANCIAL CONDITIONS (Critical for stress detection)
    # =========================================================================
    "credit_spread_hy": {
        "search_term": "high yield corporate bond spread",
        "fallback_id": "BAMLH0A0HYM2",
        "weight": 0.08,
        "invert": True,  # Higher spreads = stress
        "category": "credit",
        "description": "ICE BofA High Yield Option-Adjusted Spread"
    },
    "credit_spread_bbb": {
        "search_term": "BBB corporate bond spread",
        "fallback_id": "BAMLC0A4CBBB",
        "weight": 0.04,
        "invert": True,
        "category": "credit",
        "description": "ICE BofA BBB US Corporate Index Option-Adjusted Spread"
    },
    "baa_10y_spread": {
        "search_term": "BAA corporate bond yield 10 year treasury spread",
        "fallback_id": "BAA10Y",
        "weight": 0.04,
        "invert": True,  # Higher spreads = credit stress
        "category": "credit",
        "description": "BAA Corporate - 10Y Treasury spread (credit risk indicator, long history back to 1986)"
    },
    
    # =========================================================================
    # CONSUMER (Consumption is 70% of GDP)
    # =========================================================================
    "consumer_sentiment": {
        "search_term": "consumer sentiment university michigan",
        "fallback_id": "UMCSENT",
        "weight": 0.05,
        "invert": False,
        "category": "consumer",
        "description": "University of Michigan Consumer Sentiment"
    },
    "retail_sales": {
        "search_term": "retail sales total",
        "fallback_id": "RSAFS",
        "weight": 0.04,
        "invert": False,
        "category": "consumer",
        "description": "Advance Retail Sales: Retail Trade"
    },
    "personal_consumption": {
        "search_term": "personal consumption expenditures",
        "fallback_id": "PCE",
        "weight": 0.03,
        "invert": False,
        "category": "consumer",
        "description": "Personal Consumption Expenditures"
    },
    
    # =========================================================================
    # HOUSING (Leading indicator, amplifies cycles)
    # =========================================================================
    "housing_starts": {
        "search_term": "housing starts total",
        "fallback_id": "HOUST",
        "weight": 0.04,
        "invert": False,
        "category": "housing",
        "description": "Housing Starts: Total New Privately Owned"
    },
    "building_permits": {
        "search_term": "building permits",
        "fallback_id": "PERMIT",
        "weight": 0.03,
        "invert": False,
        "category": "housing",
        "description": "New Private Housing Units Authorized by Building Permits"
    },
    
    # =========================================================================
    # LEADING ECONOMIC INDEX (Composite)
    # =========================================================================
    "lei": {
        "search_term": "leading economic index",
        "fallback_id": "USSLIND",
        "weight": 0.06,
        "invert": False,
        "category": "composite",
        "description": "Leading Index for the United States"
    }
}


# =============================================================================
# CROSS-CORRELATION ASSETS (for correlation length calculation)
# =============================================================================

# Sector ETFs - captures cross-sector correlation (contagion measure)
SECTOR_ETFS = [
    "XLF",   # Financials
    "XLE",   # Energy
    "XLK",   # Technology
    "XLV",   # Healthcare
    "XLI",   # Industrials
    "XLP",   # Consumer Staples
    "XLY",   # Consumer Discretionary
    "XLU",   # Utilities
    "XLB",   # Materials
    "XLRE",  # Real Estate
    "XLC",   # Communication Services
]

# Asset classes - captures cross-asset correlation (risk-off measure)
ASSET_CLASS_ETFS = [
    "SPY",   # US Large Cap Equity
    "QQQ",   # US Tech/Growth
    "IWM",   # US Small Cap
    "EFA",   # International Developed
    "EEM",   # Emerging Markets
    "TLT",   # Long-term Treasuries
    "IEF",   # Intermediate Treasuries
    "LQD",   # Investment Grade Corporate Bonds
    "HYG",   # High Yield Corporate Bonds
    "GLD",   # Gold
    "USO",   # Oil
    "UUP",   # US Dollar
]

# Risk indicators for spectral analysis
RISK_INDICATORS = [
    "VIX",   # Volatility Index (if available via FMP)
]


# =============================================================================
# DYNAMIC FIELD DISCOVERY (consistent with correlation_matrix_tool.py)
# =============================================================================

def _discover_price_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the price field in FMP data without hardcoding.
    Consistent with pattern in correlation_matrix_tool.py.
    """
    if not data or not isinstance(data, dict):
        return None
    
    price_indicators = ['close', 'price', 'adj_close', 'adjusted', 'prices', 'closes']
    available_keys = list(data.keys())
    
    for indicator in price_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key
    return None


def _discover_date_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the date field in FMP data without hardcoding.
    Consistent with pattern in correlation_matrix_tool.py.
    """
    if not data or not isinstance(data, dict):
        return None
    
    date_indicators = ['date', 'dates', 'time', 'timestamp']
    available_keys = list(data.keys())
    
    for indicator in date_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key
    return None


# =============================================================================
# FRED DATA FETCHING (consistent with arimax_macro_forecast_tool.py)
# =============================================================================

async def _discover_fred_series(
    econ_server: EconomicDataServer,
    search_term: str,
    limit: int = 1
) -> Optional[str]:
    """
    Discover FRED series ID by searching keywords.
    Pattern from arimax_macro_forecast_tool.py.
    """
    try:
        results = await econ_server.search_series(search_term, limit=limit)
        if results and len(results) > 0:
            series_id = results[0].get("series_id")
            if series_id:
                logger.info(f"[FRED] Discovered '{series_id}' for search '{search_term}'")
                return series_id
    except Exception as e:
        logger.warning(f"[FRED] Search failed for '{search_term}': {e}")
    return None


async def _fetch_single_fred_series(
    econ_server: EconomicDataServer,
    series_id: str,
    start_date: str,
    end_date: str
) -> Optional[pd.DataFrame]:
    """
    Fetch a single FRED series and return as DataFrame.
    Pattern from arimax_macro_forecast_tool.py.
    
    Returns:
        DataFrame with DatetimeIndex and single column named series_id,
        or None if fetch failed.
    """
    try:
        data = await econ_server.get_series_data(series_id, start_date, end_date)
        
        # EconomicDataServer returns: {"data": [{"date": "YYYY-MM-DD", "value": float}, ...], ...}
        if data and "data" in data and len(data["data"]) > 0:
            df = pd.DataFrame(data["data"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            
            # Rename 'value' column to series_id
            if "value" in df.columns:
                df = df.rename(columns={"value": series_id})
            else:
                # Handle case where column might be named differently
                df.columns = [series_id]
            
            # Ensure numeric
            df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
            df = df.dropna()
            
            logger.info(f"[FRED] Fetched {series_id}: {len(df)} points")
            return df
    except Exception as e:
        logger.warning(f"[FRED] Failed to fetch {series_id}: {e}")
    
    return None


async def fetch_all_fred_indicators(
    econ_server: EconomicDataServer,
    indicator_configs: Dict[str, Dict[str, Any]],
    start_date: str,
    end_date: str
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict]]:
    """
    Fetch all configured FRED indicators with dynamic discovery.
    
    Args:
        econ_server: Connected EconomicDataServer instance
        indicator_configs: Config dict with search terms, fallbacks, weights
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
    
    Returns:
        Tuple of (data_dict, metadata_dict)
        - data_dict: {indicator_name: DataFrame with DatetimeIndex}
        - metadata_dict: {indicator_name: {series_id, weight, invert, ...}}
    """
    data_dict = {}
    metadata_dict = {}
    
    for name, config in indicator_configs.items():
        series_id = None
        
        # Try dynamic discovery first
        search_term = config.get("search_term", "")
        if search_term:
            series_id = await _discover_fred_series(econ_server, search_term, limit=1)
        
        # Fallback to known ID
        if not series_id:
            series_id = config.get("fallback_id")
            if series_id:
                logger.info(f"[FRED] Using fallback ID '{series_id}' for {name}")
        
        if not series_id:
            logger.warning(f"[FRED] No series ID for indicator: {name}")
            continue
        
        # Fetch data
        df = await _fetch_single_fred_series(econ_server, series_id, start_date, end_date)
        
        if df is not None and len(df) > 0:
            # Rename column from series_id to indicator name
            df = df.rename(columns={series_id: name})
            data_dict[name] = df
            
            metadata_dict[name] = {
                "series_id": series_id,
                "weight": config.get("weight", 0.05),
                "invert": config.get("invert", False),
                "category": config.get("category", "other"),
                "description": config.get("description", ""),
                "n_observations": len(df),
                "date_range": (df.index.min().isoformat(), df.index.max().isoformat())
            }
        else:
            logger.warning(f"[FRED] No data fetched for indicator: {name}")
    
    logger.info(f"[FRED] Fetched {len(data_dict)}/{len(indicator_configs)} indicators")
    return data_dict, metadata_dict


# =============================================================================
# FMP DATA FETCHING (consistent with correlation_matrix_tool.py)
# =============================================================================

async def _fetch_single_ticker_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int
) -> Optional[pd.DataFrame]:
    """
    Fetch historical price data with dynamic field discovery.
    Pattern from correlation_matrix_tool.py.
    
    Returns:
        DataFrame with DatetimeIndex and columns ['price', 'returns'],
        or None if fetch failed.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    try:
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        
        if not result or not hasattr(result, 'content'):
            logger.warning(f"[FMP] No data returned for {ticker}")
            return None
        
        data = safe_parse_json(result)
        
        if not data or not isinstance(data, dict):
            logger.warning(f"[FMP] Invalid data structure for {ticker}")
            return None
        
        # Dynamic field discovery
        date_field = _discover_date_field(data)
        price_field = _discover_price_field(data)
        
        if not date_field:
            logger.warning(f"[FMP] No date field for {ticker}. Keys: {list(data.keys())}")
            return None
        
        if not price_field:
            logger.warning(f"[FMP] No price field for {ticker}. Keys: {list(data.keys())}")
            return None
        
        dates = data[date_field]
        prices = data[price_field]
        
        if not dates or not prices or len(dates) != len(prices):
            logger.warning(f"[FMP] Date/price mismatch for {ticker}")
            return None
        
        df = pd.DataFrame({
            'date': pd.to_datetime(dates),
            'price': pd.to_numeric(prices, errors='coerce')
        })
        
        df = df.set_index('date').sort_index()
        df = df.dropna()
        
        # Calculate returns
        df['returns'] = df['price'].pct_change()
        
        if len(df) < 20:
            logger.warning(f"[FMP] Insufficient data for {ticker}: {len(df)} points")
            return None
        
        logger.info(f"[FMP] Fetched {ticker}: {len(df)} points")
        return df
        
    except Exception as e:
        logger.warning(f"[FMP] Failed to fetch {ticker}: {e}")
        return None


async def fetch_multi_ticker_returns(
    fmp_server: FMPMarketDataServer,
    tickers: List[str],
    lookback_days: int
) -> Optional[pd.DataFrame]:
    """
    Fetch returns for multiple tickers and align to common dates.
    
    Returns:
        DataFrame with DatetimeIndex and returns for each ticker as columns,
        or None if insufficient data.
    """
    all_returns = {}
    
    for ticker in tickers:
        df = await _fetch_single_ticker_data(fmp_server, ticker, lookback_days)
        if df is not None and 'returns' in df.columns:
            all_returns[ticker] = df['returns']
    
    if len(all_returns) < 2:
        logger.warning(f"[FMP] Insufficient tickers fetched: {len(all_returns)}")
        return None
    
    # Combine into single DataFrame
    combined = pd.DataFrame(all_returns)
    
    # Drop rows where all are NaN, then forward-fill small gaps
    combined = combined.dropna(how='all')
    combined = combined.ffill(limit=3)
    combined = combined.dropna()
    
    logger.info(f"[FMP] Combined returns: {len(combined)} rows, {len(combined.columns)} tickers")
    return combined


async def fetch_market_index(
    fmp_server: FMPMarketDataServer,
    ticker: str = "SPY",
    lookback_days: int = 252 * 5
) -> Optional[pd.DataFrame]:
    """
    Fetch market index data (price and returns).
    
    Returns:
        DataFrame with price and returns columns.
    """
    return await _fetch_single_ticker_data(fmp_server, ticker, lookback_days)


# =============================================================================
# DATA ALIGNMENT
# =============================================================================

def align_indicators_to_monthly(
    data_dict: Dict[str, pd.DataFrame],
    method: str = "last"
) -> pd.DataFrame:
    """
    Align all indicators to monthly frequency.
    
    Different indicators have different frequencies:
    - Yield curve, Fed funds: Daily
    - Unemployment claims: Weekly
    - PMI, Industrial prod: Monthly
    
    Args:
        data_dict: Dict of DataFrames (name -> DataFrame with single column)
        method: Aggregation method ("last", "mean")
    
    Returns:
        Single DataFrame with all indicators as columns, monthly frequency
    """
    monthly_series = {}
    
    for name, df in data_dict.items():
        if df is None or len(df) == 0:
            continue
        
        # Get the data column (should be named 'name')
        if name in df.columns:
            series = df[name]
        else:
            series = df.iloc[:, 0]
        
        # Resample to month-end
        if method == "last":
            monthly = series.resample("ME").last()
        elif method == "mean":
            monthly = series.resample("ME").mean()
        else:
            monthly = series.resample("ME").last()
        
        monthly_series[name] = monthly
    
    if not monthly_series:
        return pd.DataFrame()
    
    # Combine all series into DataFrame
    combined = pd.DataFrame(monthly_series)
    
    logger.info(f"[ALIGN] Monthly alignment: {len(combined)} months, {len(combined.columns)} indicators")
    return combined


def fill_missing_values(
    df: pd.DataFrame,
    method: str = "ffill",
    limit: int = 3
) -> pd.DataFrame:
    """
    Fill missing values in aligned data.
    
    Args:
        df: DataFrame with potential missing values
        method: "ffill" (forward fill) or "interpolate"
        limit: Maximum consecutive fills
    
    Returns:
        DataFrame with filled values
    """
    if df.empty:
        return df
    
    if method == "ffill":
        df = df.ffill(limit=limit)
    elif method == "interpolate":
        df = df.interpolate(method="linear", limit=limit)
    
    return df


# =============================================================================
# MAIN DATA FETCHER CLASS
# =============================================================================

class RecessionDataFetcher:
    """
    Orchestrates fetching and alignment of all data needed for recession detection.
    """
    
    def __init__(
        self,
        indicator_configs: Optional[Dict[str, Dict]] = None,
        sector_tickers: Optional[List[str]] = None,
        asset_class_tickers: Optional[List[str]] = None,
        lookback_years: int = 5
    ):
        """
        Initialize the data fetcher.
        
        Args:
            indicator_configs: Custom indicator configuration (or use defaults)
            sector_tickers: List of sector ETFs for cross-sector correlation
            asset_class_tickers: List of asset class ETFs for cross-asset correlation
            lookback_years: Years of historical data to fetch
        """
        self.indicator_configs = indicator_configs or DEFAULT_INDICATOR_CONFIG
        self.sector_tickers = sector_tickers or SECTOR_ETFS
        self.asset_class_tickers = asset_class_tickers or ASSET_CLASS_ETFS
        self.lookback_years = lookback_years
        
        self.econ_server = None
        self.fmp_server = None
        self._connected = False
    
    async def connect(self):
        """Connect to data servers."""
        if self._connected:
            return
        
        # Connect to EconomicDataServer
        try:
            self.econ_server = EconomicDataServer()
            await self.econ_server.connect()
            logger.info("[DataFetcher] Connected to EconomicDataServer")
        except Exception as e:
            logger.warning(f"[DataFetcher] EconomicDataServer connection failed: {e}")
            self.econ_server = None
        
        # Connect to FMPMarketDataServer
        try:
            self.fmp_server = FMPMarketDataServer()
            await self.fmp_server.connect()
            logger.info("[DataFetcher] Connected to FMPMarketDataServer")
        except Exception as e:
            logger.warning(f"[DataFetcher] FMPMarketDataServer connection failed: {e}")
            self.fmp_server = None
        
        self._connected = True
    
    async def cleanup(self):
        """Cleanup server connections."""
        if self.econ_server:
            try:
                await self.econ_server.cleanup()
            except Exception:
                pass
            self.econ_server = None
        
        if self.fmp_server:
            try:
                await self.fmp_server.cleanup()
            except Exception:
                pass
            self.fmp_server = None
        
        self._connected = False
    
    async def fetch_all(self) -> Dict[str, Any]:
        """
        Fetch all data needed for recession field theory analysis.
        
        Returns:
            Dict with:
            - "indicators": Monthly-aligned economic indicators DataFrame
            - "indicator_metadata": Config and stats for each indicator
            - "sector_returns": Daily sector ETF returns for correlation length
            - "asset_class_returns": Daily asset class returns for cross-asset analysis
            - "market_index": Daily SPY price and returns
            - "fetch_summary": Summary of what was fetched
        """
        # Ensure connected
        await self.connect()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_years * 365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        lookback_days = self.lookback_years * 365
        
        result = {
            "indicators": None,
            "indicator_metadata": {},
            "sector_returns": None,
            "asset_class_returns": None,
            "market_index": None,
            "fetch_summary": {
                "start_date": start_str,
                "end_date": end_str,
                "lookback_years": self.lookback_years,
                "indicators_requested": len(self.indicator_configs),
                "indicators_fetched": 0,
                "sectors_fetched": 0,
                "asset_classes_fetched": 0,
                "errors": []
            }
        }
        
        # =====================================================================
        # Fetch FRED indicators
        # =====================================================================
        if self.econ_server:
            try:
                data_dict, metadata = await fetch_all_fred_indicators(
                    self.econ_server,
                    self.indicator_configs,
                    start_str,
                    end_str
                )
                
                if data_dict:
                    # Align to monthly frequency
                    aligned = align_indicators_to_monthly(data_dict)
                    aligned = fill_missing_values(aligned)
                    
                    result["indicators"] = aligned
                    result["indicator_metadata"] = metadata
                    result["fetch_summary"]["indicators_fetched"] = len(data_dict)
                    
                    logger.info(f"[DataFetcher] Aligned {len(aligned)} months of indicator data")
            
            except Exception as e:
                logger.error(f"[DataFetcher] FRED fetch failed: {e}")
                result["fetch_summary"]["errors"].append(f"FRED: {str(e)}")
        else:
            result["fetch_summary"]["errors"].append("FRED: EconomicDataServer not connected")
        
        # =====================================================================
        # Fetch sector ETF returns (for correlation length)
        # =====================================================================
        if self.fmp_server:
            try:
                sector_returns = await fetch_multi_ticker_returns(
                    self.fmp_server,
                    self.sector_tickers,
                    lookback_days
                )
                
                if sector_returns is not None:
                    result["sector_returns"] = sector_returns
                    result["fetch_summary"]["sectors_fetched"] = len(sector_returns.columns)
            
            except Exception as e:
                logger.error(f"[DataFetcher] Sector returns fetch failed: {e}")
                result["fetch_summary"]["errors"].append(f"Sectors: {str(e)}")
            
            # =================================================================
            # Fetch asset class ETF returns (for cross-asset correlation)
            # =================================================================
            try:
                asset_returns = await fetch_multi_ticker_returns(
                    self.fmp_server,
                    self.asset_class_tickers,
                    lookback_days
                )
                
                if asset_returns is not None:
                    result["asset_class_returns"] = asset_returns
                    result["fetch_summary"]["asset_classes_fetched"] = len(asset_returns.columns)
            
            except Exception as e:
                logger.error(f"[DataFetcher] Asset class returns fetch failed: {e}")
                result["fetch_summary"]["errors"].append(f"Asset classes: {str(e)}")
            
            # =================================================================
            # Fetch market index
            # =================================================================
            try:
                market_index = await fetch_market_index(self.fmp_server, "SPY", lookback_days)
                result["market_index"] = market_index
            
            except Exception as e:
                logger.error(f"[DataFetcher] Market index fetch failed: {e}")
                result["fetch_summary"]["errors"].append(f"Market index: {str(e)}")
        else:
            result["fetch_summary"]["errors"].append("FMP: FMPMarketDataServer not connected")
        
        return result
    
    def get_indicator_weights(self) -> Dict[str, float]:
        """Get the configured weights for each indicator."""
        return {
            name: config.get("weight", 0.05)
            for name, config in self.indicator_configs.items()
        }
    
    def get_indicator_inversions(self) -> Dict[str, bool]:
        """Get the inversion flags for each indicator."""
        return {
            name: config.get("invert", False)
            for name, config in self.indicator_configs.items()
        }
