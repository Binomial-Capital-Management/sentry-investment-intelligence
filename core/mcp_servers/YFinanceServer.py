"""
V6 MIGRATION - Market Data MCP Server
Status: In Development
DO NOT USE IN PRODUCTION
Part of V6 OpenAI Agents SDK architecture

Market Data Server - Dynamic field discovery for Yahoo Finance
MCP server that discovers and fetches market data without hardcoding fields
"""

import json
import yfinance as yf
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

logger = logging.getLogger(__name__)


class YFinanceServer(MCPServer):
    """
    Smart librarian for stock market data.
    Discovers what information Yahoo Finance has dynamically.
    """
    
    def __init__(self):
        """Initialize with empty cache"""
        super().__init__()
        self._name = "MarketDataServer"  # Required by Agents SDK
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+
        self.cache = {}  # Our memory notebook
        self.cache_ttl = 300  # Remember things for 5 minutes
        logger.info("MarketDataServer initialized")
    
    @property
    def name(self) -> str:
        """A readable name for the server."""
        return self._name
    
    async def connect(self):
        """Connect to the server. For MarketDataServer, no connection needed."""
        logger.info(f"{self.name} connected")
    
    async def cleanup(self):
        """Cleanup the server. For MarketDataServer, just clear cache."""
        self.cache.clear()
        logger.info(f"{self.name} cleaned up")
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = {}) -> str:
        """Get a prompt by name. Not used by MarketDataServer."""
        return ""
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts. MarketDataServer doesn't use prompts."""
        return []
    
    async def discover_fields(self, ticker: str) -> Dict[str, Any]:
        """
        Discover all available fields for a stock ticker.
        Like asking: "What information do you have about Apple?"
        
        Args:
            ticker: Stock symbol like "AAPL"
            
        Returns:
            Dictionary of field names and their current values
        """
        try:
            # Check if we already know this (cached)
            if self._is_cache_valid(ticker):
                logger.debug(f"Using cached data for {ticker}")
                return self.cache[ticker]['data']
            
            # Go ask Yahoo Finance
            logger.info(f"Fetching fresh data for {ticker}")
            stock = yf.Ticker(ticker)
            
            # Get ALL the information Yahoo has
            info = stock.info
            
            # Make sure we got valid data (invalid tickers return minimal info)
            if not info or len(info) < 10 or info.get('symbol', '').upper() != ticker.upper():
                raise ValueError(f"No data found for ticker {ticker}")
            
            # Save in our memory notebook
            self.cache[ticker] = {
                'data': info,
                'timestamp': datetime.now()
            }
            
            logger.info(f"Discovered {len(info)} fields for {ticker}")
            return info
            
        except Exception as e:
            logger.error(f"Error discovering fields for {ticker}: {e}")
            raise ValueError(f"Failed to discover fields for {ticker}: {str(e)}")
    
    async def list_fields(self, ticker: str) -> List[str]:
        """
        Just list the field names available for a ticker.
        Like asking: "What categories of information do you have?"
        
        Args:
            ticker: Stock symbol like "AAPL"
            
        Returns:
            List of field names like ['price', 'volume', 'marketCap']
        """
        # Discover all fields
        fields_data = await self.discover_fields(ticker)
        
        # Return just the names
        field_names = list(fields_data.keys())
        logger.debug(f"Found {len(field_names)} field names for {ticker}")
        
        return field_names
    
    async def get_field_value(self, ticker: str, field: str) -> Any:
        """
        Get a specific piece of information about a stock.
        Like asking: "What's Apple's market cap?"
        
        Args:
            ticker: Stock symbol like "AAPL"
            field: Field name like "marketCap"
            
        Returns:
            The value of that field
        """
        try:
            # Get all fields (uses cache if available)
            fields_data = await self.discover_fields(ticker)
            
            # Check if the field exists
            if field not in fields_data:
                # Be helpful - show what IS available
                available = list(fields_data.keys())[:10]  # First 10 as example
                raise KeyError(
                    f"Field '{field}' not found for {ticker}. "
                    f"Available fields include: {', '.join(available)}..."
                )
            
            # Return the value
            value = fields_data[field]
            logger.debug(f"Retrieved {ticker}.{field} = {value}")
            
            return value
            
        except ValueError as e:
            # Re-raise ValueError (invalid ticker)
            raise e
        except Exception as e:
            logger.error(f"Error getting {field} for {ticker}: {e}")
            raise ValueError(f"Failed to get {field} for {ticker}: {str(e)}")

    async def get_market_data_batch(self, tickers: List[str], fields: List[str]) -> Dict[str, Any]:
        """
        Batch-fetch multiple fields for multiple tickers in one call.
        Much faster than calling get_market_data per ticker × field.
        Uses asyncio.gather with semaphore to fetch concurrently.
        """
        import asyncio

        if not tickers:
            raise ValueError("get_market_data_batch requires 'tickers' (list of symbols)")
        if not fields:
            raise ValueError("get_market_data_batch requires 'fields' (list of field names)")

        sem = asyncio.Semaphore(8)

        async def fetch_one(ticker: str) -> tuple:
            async with sem:
                try:
                    info = await self.discover_fields(ticker)
                    row = {}
                    for f in fields:
                        row[f] = info.get(f)
                    return ticker, row
                except Exception as e:
                    logger.warning(f"get_market_data_batch: {ticker} failed: {e}")
                    return ticker, {"_error": str(e)}

        results = await asyncio.gather(*[fetch_one(t) for t in tickers])
        return {ticker: data for ticker, data in results}

    async def get_historical_data(self, ticker: str, period: str = "1mo", start: str = None, end: str = None):
        """
        Get historical data using yfinance's .history() method.
        Just like discover_fields but for time series data.
        
        Args:
            ticker: Stock symbol like "AAPL"
            period: Time period like "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
            start: Start date in YYYY-MM-DD format (optional)
            end: End date in YYYY-MM-DD format (optional)
            
        Returns:
            Dictionary with historical data
        """
        try:
            # Get the ticker object
            stock = yf.Ticker(ticker)
            
            # Get historical data - let yfinance handle all the parameters
            if start and end:
                hist_data = stock.history(start=start, end=end)
            else:
                hist_data = stock.history(period=period)
            
            # Convert to dictionary format (like we do with info)
            # Include dates in the data
            data_with_dates = []
            for date, row in zip(hist_data.index, hist_data.to_dict('records')):
                row_with_date = {"Date": date.strftime("%Y-%m-%d")}
                row_with_date.update(row)
                data_with_dates.append(row_with_date)
            
            result = {
                "ticker": ticker,
                "period": period,
                "start": start,
                "end": end,
                "data": data_with_dates,  # Now includes dates
                "columns": ["Date"] + list(hist_data.columns),
                "data_count": len(hist_data),
                "source": "Yahoo Finance",
                "source_type": "market_data"
            }

            # ── Coverage gap detection ───────────────────────────────────
            # Yahoo FX data (=X tickers) frequently lags 1-4 weeks.
            # If the returned data doesn't reach the requested end date,
            # attach a warning so the agent knows downstream calculations
            # will have stale/frozen values for the missing period.
            if len(hist_data) > 0:
                actual_end = hist_data.index[-1].to_pydatetime().replace(tzinfo=None)
                expected_end = None
                if end:
                    try:
                        expected_end = datetime.strptime(end, "%Y-%m-%d")
                    except ValueError:
                        pass
                elif period:
                    # No explicit end → expect data roughly up to now
                    expected_end = datetime.now() - timedelta(days=3)

                if expected_end:
                    gap_days = (expected_end - actual_end).days
                    if gap_days > 5:
                        result["_coverage_warning"] = (
                            f"Data ends {actual_end.strftime('%Y-%m-%d')}, "
                            f"{'requested' if end else 'expected'} end "
                            f"~{expected_end.strftime('%Y-%m-%d')} "
                            f"({gap_days} calendar days short)"
                        )
                        logger.warning(
                            f"Coverage gap for {ticker}: {result['_coverage_warning']}"
                        )
            # ── End coverage gap detection ────────────────────────────────

            logger.info(f"Retrieved {len(hist_data)} historical data points for {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting historical data for {ticker}: {e}")
            raise ValueError(f"Failed to get historical data for {ticker}: {str(e)}")
    
    def _is_cache_valid(self, ticker: str) -> bool:
        """
        Check if cached data is still fresh (less than 5 minutes old).
        
        Args:
            ticker: Stock symbol to check
            
        Returns:
            True if cache is valid, False if expired or missing
        """
        if ticker not in self.cache:
            return False
        
        cached_time = self.cache[ticker]['timestamp']
        age = datetime.now() - cached_time
        
        is_valid = age < timedelta(seconds=self.cache_ttl)
        
        if not is_valid:
            logger.debug(f"Cache expired for {ticker} (age: {age.seconds}s)")
        
        return is_valid
    
    # MCP Protocol Methods for Agents SDK
    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        """
        MCP method: List available tools.
        Required for OpenAI Agents SDK integration.
        """
        tools = self.get_tools()
        # Convert our tool format to MCPTool format
        mcp_tools = []
        for tool in tools:
            mcp_tools.append(MCPTool(
                name=tool["function"]["name"],
                description=tool["function"]["description"],
                inputSchema=tool["function"]["parameters"]
            ))
        return mcp_tools
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> CallToolResult:
        """
        MCP method: Execute a tool call.
        Required for OpenAI Agents SDK integration.
        """
        if arguments is None:
            arguments = {}
            
        try:
            result = None
            if tool_name == "discover_market_fields":
                result = await self.discover_fields(arguments["ticker"])
            elif tool_name == "list_market_fields":
                result = await self.list_fields(arguments["ticker"])
            elif tool_name == "get_market_data":
                result = await self.get_field_value(
                    arguments["ticker"],
                    arguments["field"]
                )
            elif tool_name == "get_market_data_batch":
                result = await self.get_market_data_batch(
                    arguments["tickers"],
                    arguments["fields"]
                )
            elif tool_name == "yf_historical_data":
                result = await self.get_historical_data(
                    arguments["ticker"],
                    arguments.get("period", "1mo"),
                    arguments.get("start"),
                    arguments.get("end")
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            from core.agents.binomial_hash import bh_ingest
            raw = json.dumps(result, default=str) if not isinstance(result, str) else result
            _id = arguments.get("ticker") or arguments.get("tickers", "")
            if isinstance(_id, list):
                _id = "_".join(_id[:3])
            text = bh_ingest(raw, f"{tool_name}_{_id}" if _id else tool_name)

            # Surface coverage gap warning before the BH summary
            if isinstance(result, dict) and result.get("_coverage_warning"):
                warning = result["_coverage_warning"]
                text = (
                    f"⚠ COVERAGE GAP: {warning}. "
                    f"Downstream calculations using this data will have "
                    f"stale/frozen values for the missing period. Consider "
                    f"noting this limitation or supplementing from another "
                    f"source.\n{text}"
                )

            return CallToolResult(
                content=[{"type": "text", "text": text}],
                is_error=False
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            return CallToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True
            )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Return tool definitions for OpenAI function calling.
        This tells AI what our server can do.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "discover_market_fields",
                    "description": "Discover all available fields for a stock ticker",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., AAPL, MSFT)"
                            }
                        },
                        "required": ["ticker"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_market_fields",
                    "description": "List just the field names available for a stock",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Stock ticker symbol"
                            }
                        },
                        "required": ["ticker"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_data",
                    "description": "Get a specific data field for a stock ticker",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Stock ticker symbol"
                            },
                            "field": {
                                "type": "string",
                                "description": "Field name to retrieve (e.g., marketCap, price)"
                            }
                        },
                        "required": ["ticker", "field"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_data_batch",
                    "description": "Batch-fetch multiple fields for multiple tickers in ONE call. MUCH faster than calling get_market_data per ticker. Use this whenever you need the same field(s) across 2+ symbols. Example: {\"tickers\": [\"AAPL\",\"MSFT\",\"NVDA\"], \"fields\": [\"returnOnEquity\",\"exDividendDate\",\"earningsTimestamp\"]}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tickers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of stock ticker symbols"
                            },
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of field names to retrieve for each ticker"
                            }
                        },
                        "required": ["tickers", "fields"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "yf_historical_data",
                    "description": "Get historical price data for a stock/forex ticker using Yahoo Finance. Forex pairs use format: ILSTRY=X, USDTRY=X, EURUSD=X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., AAPL, MSFT)"
                            },
                            "period": {
                                "type": "string",
                                "description": "Time period like '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max' (default: '1mo')",
                                "default": "1mo"
                            },
                            "start": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format (optional, use either period or start/end)"
                            },
                            "end": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format (optional, use either period or start/end)"
                            }
                        },
                        "required": ["ticker"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            }
        ]