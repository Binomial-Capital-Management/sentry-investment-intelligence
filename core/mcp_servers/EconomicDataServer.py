"""
Economic Data MCP Server - FRED (Federal Reserve Economic Data)

Provides dynamic discovery and retrieval of 800,000+ economic time series
covering US and global macro data from sources including:
- Federal Reserve, BLS, BEA, Census (US)
- OECD, IMF, World Bank, BIS (International)

Tools support:
- Keyword search with country/source filtering
- Release calendar for upcoming economic data
- Category-based browsing
- Multi-series comparison
"""

from fredapi import Fred
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class EconomicDataServer(MCPServer):
    """
    Smart librarian for economic data.
    Discovers what information FRED has dynamically.
    """
    
    def __init__(self, fred_api_key: Optional[str] = None):
        """Initialize with FRED API key"""
        super().__init__()
        self._name = "EconomicDataServer"  # Required by Agents SDK
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+
        
        # Get API key from parameter or environment
        self.api_key = fred_api_key or os.getenv('FRED_API_KEY')
        
        if not self.api_key:
            raise ValueError("FRED API key required. Set FRED_API_KEY environment variable.")
        
        # Base URL for direct FRED API calls (features not in fredapi)
        self.base_url = "https://api.stlouisfed.org/fred"
        
        try:
            self.fred = Fred(api_key=self.api_key)
            logger.info("FRED client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FRED client: {e}")
            raise
        
        # Cache for search results and data
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache
    
    @property
    def name(self) -> str:
        """A readable name for the server."""
        return self._name
    
    async def connect(self):
        """Connect to the server. For EconomicDataServer, FRED client already initialized."""
        logger.info(f"{self.name} connected")
    
    async def cleanup(self):
        """Cleanup the server. Clear cache."""
        self.cache.clear()
        logger.info(f"{self.name} cleaned up")
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = {}) -> str:
        """Get a prompt by name. Not used by EconomicDataServer."""
        return ""
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts. EconomicDataServer doesn't use prompts."""
        return []
        
    def _safe_search(self, query: str, limit: int) -> pd.DataFrame:
        """
        Safely search FRED with error handling for date parsing issues.
        Some FRED series have malformed dates that cause pandas errors.
        """
        try:
            result = self.fred.search(query, limit=limit)
            if result is None:
                return pd.DataFrame(columns=['id', 'title', 'units', 'frequency'])
            return result
        except Exception as e:
            logger.error(f"FRED search failed for '{query}': {str(e)}")
            return pd.DataFrame(columns=['id', 'title', 'units', 'frequency'])
    
    async def search_series(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search FRED for economic data series matching query.
        Like asking: "What data do you have about interest rates?"
        
        Args:
            query: Search terms like "interest rates", "inflation", "GDP"
            limit: Maximum number of results to return
            
        Returns:
            List of series with metadata
        """
        try:
            # Check cache first
            cache_key = f"search_{query}_{limit}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"Using cached search results for '{query}'")
                return self.cache[cache_key]['data']
            
            # Search FRED using safe method
            logger.info(f"Searching FRED for '{query}'")
            results = self._safe_search(query, limit)
            
            # Handle empty results
            if results.empty:
                logger.warning(f"No results found for '{query}'")
                return []
            
            # Transform pandas DataFrame to list of dicts
            series_list = []
            for idx, row in results.iterrows():
                try:
                    # Safely handle date fields that might cause issues
                    obs_start = row.get("observation_start", "")
                    obs_end = row.get("observation_end", "")
                    
                    # Convert dates to strings safely
                    if pd.notna(obs_start):
                        obs_start = str(obs_start)
                    else:
                        obs_start = ""
                        
                    if pd.notna(obs_end):
                        obs_end = str(obs_end)
                    else:
                        obs_end = ""
                    
                    series_list.append({
                        "series_id": idx,  # The index is the series ID
                        "title": row.get("title", ""),
                        "units": row.get("units", ""),
                        "frequency": row.get("frequency", ""),
                        "observation_start": obs_start,
                        "observation_end": obs_end,
                        "popularity": row.get("popularity", 0),
                        "notes": row.get("notes", "")[:200] + "..." if len(str(row.get("notes", ""))) > 200 else row.get("notes", "")
                    })
                except Exception as e:
                    logger.warning(f"Skipping series {idx} due to error: {e}")
                    continue
            
            # Sort by popularity (most popular first)
            series_list.sort(key=lambda x: x.get("popularity", 0), reverse=True)
            
            # Cache the results
            self.cache[cache_key] = {
                'data': series_list,
                'timestamp': datetime.now()
            }
            
            logger.info(f"Found {len(series_list)} series for '{query}'")
            return series_list
            
        except Exception as e:
            logger.error(f"Error searching FRED for '{query}': {e}")
            raise ValueError(f"Failed to search economic series: {str(e)}")
    
    async def get_series_data(self, series_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get actual data for a specific FRED series.
        Like asking: "Show me the 10-year treasury rate data"
        
        Args:
            series_id: FRED series ID like "DGS10", "UNRATE"
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with data and metadata
        """
        try:
            # Default to last 120 days when agent doesn't specify dates
            # (120 days ensures we capture quarterly data which comes every ~90 days)
            if not start_date and not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
                logger.info(f"No dates specified, defaulting to last 120 days: {start_date} to {end_date}")
            
            # Build cache key
            cache_key = f"data_{series_id}_{start_date}_{end_date}"
            
            # Check cache
            if self._is_cache_valid(cache_key):
                logger.debug(f"Using cached data for {series_id}")
                return self.cache[cache_key]['data']
            
            # Fetch series info first
            logger.info(f"Fetching info for series {series_id}")
            info = self.fred.get_series_info(series_id)
            
            # Fetch the actual data
            logger.info(f"Fetching data for series {series_id}")
            data = self.fred.get_series(
                series_id, 
                observation_start=start_date,
                observation_end=end_date
            )
            
            # Convert to list of dicts for JSON serialization
            data_points = []
            for date, value in data.items():
                if pd.notna(value):  # Skip NaN values
                    data_points.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "value": float(value)
                    })
            
            # Build response
            result = {
                "series_id": series_id,
                "title": info.get("title", series_id),
                "units": info.get("units", ""),
                "frequency": info.get("frequency", ""),
                "source": info.get("source", ""),
                "seasonal_adjustment": info.get("seasonal_adjustment", ""),
                "last_updated": str(info.get("last_updated", "")),
                "observation_start": str(info.get("observation_start", "")),
                "observation_end": str(info.get("observation_end", "")),
                "data": data_points,
                "data_count": len(data_points)
            }
            
            # Cache the result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            logger.info(f"Retrieved {len(data_points)} data points for {series_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching data for {series_id}: {e}")
            raise ValueError(f"Failed to get series data: {str(e)}")
    
    
    def _is_cache_valid(self, key: str) -> bool:
        """
        Check if cached data is still fresh.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if cache is valid, False if expired or missing
        """
        if key not in self.cache:
            return False
        
        cached_time = self.cache[key]['timestamp']
        age = datetime.now() - cached_time
        
        is_valid = age < timedelta(seconds=self.cache_ttl)
        
        if not is_valid:
            logger.debug(f"Cache expired for {key} (age: {age.seconds}s)")
        
        return is_valid

    def _fred_api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make direct FRED API request for endpoints not supported by fredapi.
        
        Args:
            endpoint: API endpoint (e.g., 'releases/dates')
            params: Query parameters
            
        Returns:
            JSON response from FRED API
        """
        params['api_key'] = self.api_key
        params['file_type'] = 'json'
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"FRED API request failed: {endpoint} - {e}")
            raise ValueError(f"FRED API request failed: {str(e)}")

    async def get_release_calendar(
        self, 
        days_ahead: int = 14,
        include_past_days: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming (and optionally recent) economic data releases.
        Critical for timing around major announcements like NFP, CPI, FOMC.
        
        Args:
            days_ahead: Number of days to look ahead (default: 14)
            include_past_days: Include releases from past N days (default: 0)
            limit: Max releases to return (default: 100)
            
        Returns:
            List of releases with dates and names
        """
        try:
            cache_key = f"release_calendar_{days_ahead}_{include_past_days}_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            # Calculate date range for release dates (not realtime)
            today = datetime.now()
            start_date = (today - timedelta(days=include_past_days)).strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            # Use FRED API for releases/dates with correct parameters
            # release_date_start/end filter by when data is released (not realtime vintage)
            data = self._fred_api_request('releases/dates', {
                'release_date_start': start_date,
                'release_date_end': end_date,
                'include_release_dates_with_no_data': 'true',
                'limit': limit,
                'sort_order': 'asc'
            })
            
            releases = []
            for item in data.get('release_dates', []):
                releases.append({
                    'release_id': item.get('release_id'),
                    'release_name': item.get('release_name', ''),
                    'date': item.get('date', ''),
                })
            
            # Sort by date
            releases.sort(key=lambda x: x['date'])
            
            self.cache[cache_key] = {'data': releases, 'timestamp': datetime.now()}
            logger.info(f"Found {len(releases)} upcoming releases")
            return releases
            
        except Exception as e:
            logger.error(f"Error fetching release calendar: {e}")
            raise ValueError(f"Failed to get release calendar: {str(e)}")

    async def search_by_country(
        self,
        country: str,
        topic: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for economic series by country name, optionally filtered by topic.
        Dynamically discovers series - no hardcoded country codes.
        
        Args:
            country: Country name (e.g., 'Japan', 'Australia', 'Germany')
            topic: Optional topic filter (e.g., 'inflation', 'interest rate', 'gdp')
            limit: Maximum results
            
        Returns:
            List of series matching country (and topic if specified)
        """
        try:
            # Build search query dynamically
            query = country
            if topic:
                query = f"{topic} {country}"
            
            cache_key = f"country_{country}_{topic}_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            # Use existing search but with country-focused query
            results = await self.search_series(query, limit=limit)
            
            self.cache[cache_key] = {'data': results, 'timestamp': datetime.now()}
            return results
            
        except Exception as e:
            logger.error(f"Error searching by country {country}: {e}")
            raise ValueError(f"Failed to search by country: {str(e)}")

    async def search_by_source(
        self,
        source: str,
        topic: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for series from a specific data source/provider.
        Useful for finding authoritative data from trusted sources.
        
        Args:
            source: Data source (e.g., 'OECD', 'IMF', 'World Bank', 'BLS', 'BEA')
            topic: Optional topic filter
            limit: Maximum results
            
        Returns:
            List of series from the specified source
        """
        try:
            query = source
            if topic:
                query = f"{source} {topic}"
            
            cache_key = f"source_{source}_{topic}_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            results = await self.search_series(query, limit=limit)
            
            self.cache[cache_key] = {'data': results, 'timestamp': datetime.now()}
            return results
            
        except Exception as e:
            logger.error(f"Error searching by source {source}: {e}")
            raise ValueError(f"Failed to search by source: {str(e)}")

    async def get_series_info(self, series_id: str) -> Dict[str, Any]:
        """
        Get detailed metadata for a series without fetching data.
        Useful for understanding units, frequency, source before pulling data.
        
        Args:
            series_id: FRED series ID
            
        Returns:
            Detailed series metadata
        """
        try:
            cache_key = f"info_{series_id}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            info = self.fred.get_series_info(series_id)
            
            result = {
                'series_id': series_id,
                'title': info.get('title', ''),
                'units': info.get('units', ''),
                'units_short': info.get('units_short', ''),
                'frequency': info.get('frequency', ''),
                'frequency_short': info.get('frequency_short', ''),
                'seasonal_adjustment': info.get('seasonal_adjustment', ''),
                'seasonal_adjustment_short': info.get('seasonal_adjustment_short', ''),
                'source': info.get('source', ''),
                'last_updated': str(info.get('last_updated', '')),
                'observation_start': str(info.get('observation_start', '')),
                'observation_end': str(info.get('observation_end', '')),
                'notes': info.get('notes', '')
            }
            
            self.cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
            return result
            
        except Exception as e:
            logger.error(f"Error fetching info for {series_id}: {e}")
            raise ValueError(f"Failed to get series info: {str(e)}")

    async def compare_series(
        self,
        series_ids: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch multiple series and align them for comparison.
        Useful for cross-country or cross-indicator analysis.
        
        Args:
            series_ids: List of FRED series IDs to compare
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dict with aligned data for all series
        """
        try:
            if len(series_ids) > 10:
                raise ValueError("Maximum 10 series for comparison")
            
            # Default date range
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            results = {}
            for series_id in series_ids:
                try:
                    data = await self.get_series_data(series_id, start_date, end_date)
                    results[series_id] = {
                        'title': data.get('title', series_id),
                        'units': data.get('units', ''),
                        'frequency': data.get('frequency', ''),
                        'data': data.get('data', []),
                        'data_count': data.get('data_count', 0)
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch {series_id}: {e}")
                    results[series_id] = {'error': str(e)}
            
            return {
                'series_count': len(series_ids),
                'date_range': {'start': start_date, 'end': end_date},
                'series': results
            }
            
        except Exception as e:
            logger.error(f"Error comparing series: {e}")
            raise ValueError(f"Failed to compare series: {str(e)}")

    async def get_release_series(
        self,
        release_id: int,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get all series associated with a specific economic release.
        Useful after finding releases via get_release_calendar.
        
        Args:
            release_id: FRED release ID (from release calendar)
            limit: Maximum series to return
            
        Returns:
            Release info with list of associated series
        """
        try:
            cache_key = f"release_series_{release_id}_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            # Get release info
            release_data = self._fred_api_request('release', {
                'release_id': release_id
            })
            
            # Get series in release
            series_data = self._fred_api_request('release/series', {
                'release_id': release_id,
                'limit': limit
            })
            
            release_info = release_data.get('releases', [{}])[0]
            series_list = []
            
            for s in series_data.get('seriess', []):
                series_list.append({
                    'series_id': s.get('id', ''),
                    'title': s.get('title', ''),
                    'units': s.get('units', ''),
                    'frequency': s.get('frequency', ''),
                    'seasonal_adjustment': s.get('seasonal_adjustment', ''),
                    'last_updated': s.get('last_updated', '')
                })
            
            result = {
                'release_id': release_id,
                'release_name': release_info.get('name', ''),
                'release_link': release_info.get('link', ''),
                'series_count': len(series_list),
                'series': series_list
            }
            
            self.cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
            return result
            
        except Exception as e:
            logger.error(f"Error fetching release series for {release_id}: {e}")
            raise ValueError(f"Failed to get release series: {str(e)}")

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
            
            if tool_name == "search_economic_series":
                result = await self.search_series(
                    arguments["query"],
                    arguments.get("limit", 10)
                )
            elif tool_name == "get_economic_data":
                result = await self.get_series_data(
                    arguments["series_id"],
                    arguments.get("start_date"),
                    arguments.get("end_date")
                )
            elif tool_name == "get_release_calendar":
                result = await self.get_release_calendar(
                    arguments.get("days_ahead", 14),
                    arguments.get("include_past_days", 0),
                    arguments.get("limit", 100)
                )
            elif tool_name == "search_by_country":
                result = await self.search_by_country(
                    arguments["country"],
                    arguments.get("topic"),
                    arguments.get("limit", 20)
                )
            elif tool_name == "search_by_source":
                result = await self.search_by_source(
                    arguments["source"],
                    arguments.get("topic"),
                    arguments.get("limit", 20)
                )
            elif tool_name == "get_series_info":
                result = await self.get_series_info(
                    arguments["series_id"]
                )
            elif tool_name == "compare_series":
                result = await self.compare_series(
                    arguments["series_ids"],
                    arguments.get("start_date"),
                    arguments.get("end_date")
                )
            elif tool_name == "get_release_series":
                result = await self.get_release_series(
                    arguments["release_id"],
                    arguments.get("limit", 50)
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Return properly serialized JSON — compact large outputs
            from core.agents.binomial_hash import bh_ingest
            raw = json.dumps(result)
            text = bh_ingest(raw, tool_name)
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
        8 tools covering discovery, retrieval, and comparison of economic data.
        """
        return [
            # === DISCOVERY TOOLS (return series IDs, NOT data values) ===
            {
                "type": "function",
                "function": {
                    "name": "search_economic_series",
                    "description": "Search FRED's 800,000+ series by keyword. Returns series IDs and metadata, NOT actual data values. IMPORTANT: After finding series, you MUST call get_economic_data(series_id) to fetch actual values!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search keywords (e.g., 'inflation rate', 'treasury yield', 'unemployment')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results to return (default: 10, max: 100)"
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_country",
                    "description": "Find series for a country. Returns series IDs and metadata, NOT actual data values. IMPORTANT: After finding series, you MUST call get_economic_data(series_id) to fetch actual values!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "country": {
                                "type": "string",
                                "description": "Country name (e.g., 'Japan', 'Australia', 'Germany', 'United Kingdom')"
                            },
                            "topic": {
                                "type": "string",
                                "description": "Optional topic filter (e.g., 'inflation', 'interest rate', 'gdp')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default: 20)"
                            }
                        },
                        "required": ["country"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_source",
                    "description": "Find series from a data provider (OECD, IMF, BLS, etc). Returns series IDs and metadata, NOT actual data values. IMPORTANT: After finding series, you MUST call get_economic_data(series_id) to fetch actual values!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Data source (e.g., 'OECD', 'IMF', 'World Bank', 'BLS', 'BEA')"
                            },
                            "topic": {
                                "type": "string",
                                "description": "Optional topic filter (e.g., 'inflation', 'interest rates', 'gdp')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results (default: 20)"
                            }
                        },
                        "required": ["source"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            # === CALENDAR & RELEASES ===
            {
                "type": "function",
                "function": {
                    "name": "get_release_calendar",
                    "description": "Get upcoming economic data releases. Critical for traders timing around major announcements (NFP, CPI, FOMC, GDP). Returns release names and dates. Use get_release_series to see what data is in each release.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days_ahead": {
                                "type": "integer",
                                "description": "Days to look ahead (default: 14, max: 60)"
                            },
                            "include_past_days": {
                                "type": "integer",
                                "description": "Include releases from past N days (default: 0)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max releases to return (default: 100)"
                            }
                        },
                        "required": [],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_release_series",
                    "description": "Get all data series included in a specific economic release. Use after get_release_calendar to explore what's in releases like 'Employment Situation', 'Consumer Price Index', 'GDP'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "release_id": {
                                "type": "integer",
                                "description": "FRED release ID (from get_release_calendar results)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max series to return (default: 50)"
                            }
                        },
                        "required": ["release_id"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            # === DATA RETRIEVAL (use after discovery to get actual values) ===
            {
                "type": "function",
                "function": {
                    "name": "get_economic_data",
                    "description": "REQUIRED after search tools: Fetch actual data VALUES for a FRED series. Search tools only return series IDs - you MUST call this to get the actual numbers! Returns time series with dates and values.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "series_id": {
                                "type": "string",
                                "description": "FRED series ID from search results (e.g., 'CPIAUCSL', 'DGS10', 'UNRATE')"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date YYYY-MM-DD (optional, defaults to 120 days ago)"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date YYYY-MM-DD (optional, defaults to today)"
                            }
                        },
                        "required": ["series_id"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_series_info",
                    "description": "Get detailed metadata for a series WITHOUT fetching data. Returns units, frequency, source, seasonal adjustment, date range, and notes. Use to understand a series before pulling data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "series_id": {
                                "type": "string",
                                "description": "FRED series ID"
                            }
                        },
                        "required": ["series_id"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            # === COMPARISON ===
            {
                "type": "function",
                "function": {
                    "name": "compare_series",
                    "description": "Fetch multiple series for comparison. Useful for cross-country analysis (US vs Japan CPI) or related indicators (CPI vs PCE). Returns aligned data for up to 10 series.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "series_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of FRED series IDs to compare (max 10)"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date YYYY-MM-DD (default: 1 year ago)"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date YYYY-MM-DD (default: today)"
                            }
                        },
                        "required": ["series_ids"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            }
        ]