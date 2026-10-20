"""
FMP Document Server - Phase 3 Implementation
Dynamic discovery for all FMP document endpoints except SEC filings
NO HARDCODING - all fields discovered at runtime
"""

import os
import aiohttp
import asyncio
import redis.asyncio as redis
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Import MCP base class from agents SDK
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

# Import DDC loader
from .ddc_loader import DDCLoader, DatasetEntry
from .field_discovery import DEFAULT_PAGE_SIZE
from core.utils import gather_dict

logger = logging.getLogger(__name__)


class FMPDocumentServer(MCPServer):
    """
    MCP Server for FMP document discovery and retrieval.
    Dynamically discovers all document types except SEC filings.
    NO HARDCODING - everything discovered at runtime from DDC and API responses.
    """
    
    def __init__(self, api_key: str = None):
        """Initialize FMP Document Server"""
        super().__init__()
        self._name = "FMPDocumentServer"
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+

        # Load API key from environment if not provided
        if api_key is None:
            import os
            api_key = os.getenv("FMP_API_KEY")
        
        if not api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com"  # No /api suffix - document catalog uses /stable/ endpoints
        
        # Load DDC catalog
        self.ddc_loader = DDCLoader()
        
        # Cache settings
        self.cache_ttl = 3600  # 1 hour for documents
        self.memory_cache: Dict[str, Dict] = {}
        self.redis_client: Optional[redis.Redis] = None
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info("FMPDocumentServer initialized")
    
    @property
    def name(self) -> str:
        """Server name for MCP"""
        return self._name
    
    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        """
        MCP method: List available tools.
        Required by Agents SDK for tool discovery.
        """
        return self.get_available_tools()
    
    async def list_prompts(self, run_context, agent) -> List[str]:
        """List available prompts (none for this server)"""
        return []
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = {}) -> str:
        """Get a prompt by name. Not used by FMPDocumentServer."""
        return ""
    
    async def connect(self):
        """Connect to Redis and create HTTP session"""
        # Create HTTP session with proper connector and timeout configuration
        # 5-minute timeout for document fetching (SEC filings, transcripts can be slow)
        connector = aiohttp.TCPConnector(
            force_close=False,  # Keep connections alive for reuse
            enable_cleanup_closed=True  # Auto-cleanup closed connections
        )
        timeout = aiohttp.ClientTimeout(total=300, connect=10, sock_read=180)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)

        # Try to connect to Redis with enhanced configuration
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            logger.info(f"FMP DocumentServer connecting to Redis: {redis_url}")

            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            await self.redis_client.ping()
            logger.info("FMP DocumentServer: Redis connection successful")
        except redis.ConnectionError as e:
            logger.warning(f"FMP DocumentServer: Redis connection failed: {e}")
            self.redis_client = None
        except redis.TimeoutError as e:
            logger.warning(f"FMP DocumentServer: Redis connection timeout: {e}")
            self.redis_client = None
        except Exception as e:
            logger.warning(f"FMP DocumentServer: Redis not available, using memory cache: {e}")
            self.redis_client = None

        logger.info(f"{self.name} connected")
    
    async def cleanup(self):
        """Cleanup connections"""
        if self.session:
            await self.session.close()
            # CRITICAL: Close connector to prevent resource leak
            if self.session.connector:
                await self.session.connector.close()

        if self.redis_client:
            await self.redis_client.close()

        self.memory_cache.clear()
        logger.info(f"{self.name} cleaned up")
    
    def get_available_tools(self) -> List[MCPTool]:
        """Return the list of available tools"""
        return [
            MCPTool(
                name="list_document_types",
                description="Lists all available FMP document types: earnings transcripts, press releases, stock news, FMP articles, insider trading reports, calendars. Excludes SEC filings (use SECFilingServer for those). Returns document type catalog.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            MCPTool(
                name="discover_documents",
                description="Probes document endpoints for a symbol to discover available fields. depth='quick' (fast: transcripts, press releases), depth='full' (comprehensive: all document types). Returns aggregated document fields.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL')"
                        },
                        "depth": {
                            "type": "string",
                            "enum": ["quick", "full"],
                            "description": "Discovery depth: 'quick' for fast endpoints, 'full' for comprehensive discovery",
                            "default": "quick"
                        }
                    },
                    "required": ["symbol"]
                }
            ),
            MCPTool(
                name="get_document_fields",
                description="Fetches specific field values from discovered documents. Provide symbol and keys array (field names from discover_documents). Returns requested document field values. Use after discover_documents to fetch specific data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL')"
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of field keys to retrieve from discovered documents"
                        }
                    },
                    "required": ["symbol", "keys"]
                }
            ),
            MCPTool(
                name="get_raw_document",
                description="Fetches raw documents from specific dataset. Examples: earning-call-transcript (needs symbol, year, quarter), press-releases (needs symbols), stock-news (needs symbols), fmp-articles (needs page, limit). Enable paginate=true for multi-page fetching.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "description": "Dataset name: 'earning-call-transcript', 'insider-trading', 'press-releases', 'stock-news', 'earning-call-calendar', 'fmp-articles', etc."
                        },
                        "params": {
                            "type": "object",
                            "description": "Required parameters by dataset - earning-call-transcript: {symbol, year, quarter}. insider-trading: {page, limit}. press-releases: {symbols}. stock-news: {symbols}. earning-call-calendar: {} (no params). fmp-articles: {page, limit}."
                        },
                        "paginate": {
                            "type": "boolean",
                            "description": "Enable automatic pagination for datasets that support it",
                            "default": False
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Maximum pages to fetch when pagination is enabled",
                            "default": 5
                        }
                    },
                    "required": ["dataset", "params"]
                }
            ),
            MCPTool(
                name="get_document_dataset",
                description="Alias for get_raw_document with dataset-first approach. Same functionality: fetches documents by dataset name with params. Use either tool interchangeably. Supports pagination for multi-page datasets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string"},
                        "params": {"type": "object"},
                        "paginate": {"type": "boolean", "default": False},
                        "max_pages": {"type": "integer", "default": 5}
                    },
                    "required": ["dataset"],
                    "additionalProperties": True
                }
            )
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Route tool calls to appropriate methods"""
        try:
            if name == "list_document_types":
                result = await self.list_document_types()
            elif name == "discover_documents":
                result = await self.discover_documents(
                    arguments["symbol"],
                    arguments.get("depth", "quick")
                )
            elif name == "get_document_fields":
                result = await self.get_document_fields(
                    arguments["symbol"],
                    arguments["keys"]
                )
            elif name == "get_raw_document":
                # Debug: Log what we received from the agent
                logger.debug(f"get_raw_document called with arguments: {arguments}")

                # Extract dataset and params correctly
                # Agent can call in two ways:
                # 1. Nested: get_raw_document(dataset="X", params={"key": "value"})
                # 2. Flat: get_raw_document(dataset="X", key="value")
                dataset = arguments.get("dataset")
                paginate = arguments.get("paginate", False)
                max_pages = arguments.get("max_pages", 5)

                if not dataset:
                    raise ValueError("dataset is required for get_raw_document")

                # Check if params is already a nested dict
                if "params" in arguments and isinstance(arguments["params"], dict):
                    # Case 1: Agent passed params as nested dict
                    params = arguments["params"]
                else:
                    # Case 2: Agent passed params at top level
                    params = {
                        k: v
                        for k, v in arguments.items()
                        if k not in {"dataset", "apikey", "params", "paginate", "max_pages"}
                    }

                logger.debug(f"  - dataset: {dataset}")
                logger.debug(f"  - extracted params: {params}")
                logger.debug(f"  - paginate: {paginate}, max_pages: {max_pages}")

                result = await self.get_raw_document(dataset, params, paginate, max_pages)
            elif name == "get_document_dataset":
                # Alias mapping to get_raw_document
                mapped = {
                    "dataset": arguments.get("dataset"),
                    "params": arguments.get("params", {}),
                    "paginate": arguments.get("paginate", False),
                    "max_pages": arguments.get("max_pages", 5)
                }
                # Re-dispatch to get_raw_document
                return await self.call_tool("get_raw_document", mapped)
            else:
                return CallToolResult(
                    content=[{"type": "text", "text": f"Unknown tool: {name}"}],
                    isError=True
                )

            from core.agents.binomial_hash import bh_ingest
            raw = json.dumps(result, indent=2)
            text = bh_ingest(raw, name)
            return CallToolResult(
                content=[{"type": "text", "text": text}],
                isError=False
            )

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return CallToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )
    
    async def list_document_types(self) -> Dict[str, Any]:
        """List available document types from DDC catalog (excluding SEC)"""
        # Get all document class datasets from multiple classes
        # FMP documents are in "documents", "insider", and "news" classes
        document_classes = ["documents", "insider", "news"]
        datasets = []
        for doc_class in document_classes:
            datasets.extend(self.ddc_loader.filter_by_class(doc_class))
        
        # Exclude SEC-related datasets
        excluded_keywords = ["sec", "filing", "10-k", "10-q", "8-k", "def", "rss"]
        
        available = []
        for dataset in datasets:
            # Dynamic exclusion based on dataset name and notes
            dataset_lower = dataset.dataset.lower()
            notes_lower = (dataset.notes or "").lower()
            
            # Check if any excluded keyword appears in dataset name or notes
            is_sec_related = any(
                keyword in dataset_lower or keyword in notes_lower 
                for keyword in excluded_keywords
            )
            
            if not is_sec_related:
                available.append({
                    "name": dataset.dataset,
                    "url": dataset.url,
                    "notes": dataset.notes,
                    "cache_ttl": dataset.cache_ttl
                })
        
        return {
            "total_document_types": len(available),
            "document_types": available,
            "note": "SEC filings excluded - will be handled by separate service"
        }
    
    async def discover_documents(self, symbol: str, depth: str = "quick") -> Dict[str, Any]:
        """
        Discover all available document fields by fetching from multiple endpoints.
        Similar to market discovery but for document endpoints.
        """
        # Check cache first
        cache_key = f"fmp:doc_discovery:{symbol}:{depth}"
        cached = await self._get_cache(cache_key)
        if cached:
            logger.info(f"Using cached document discovery for {symbol}")
            return cached
        
        # Get document datasets (excluding SEC) from multiple classes
        # FMP documents are in "documents", "insider", and "news" classes
        document_classes = ["documents", "insider", "news"]
        datasets = []
        for doc_class in document_classes:
            datasets.extend(self.ddc_loader.filter_by_class(doc_class))
        excluded_keywords = ["sec", "filing", "10-k", "10-q", "8-k", "def", "rss"]
        
        # Filter out SEC-related
        available_datasets = []
        for dataset in datasets:
            dataset_lower = dataset.dataset.lower()
            notes_lower = (dataset.notes or "").lower()
            
            is_sec_related = any(
                keyword in dataset_lower or keyword in notes_lower 
                for keyword in excluded_keywords
            )
            
            if not is_sec_related:
                available_datasets.append(dataset)
        
        # Determine which to fetch based on depth
        if depth == "quick":
            # Quick discovery - only fast document endpoints
            quick_names = ["earning-call-transcript", "insider-trading", "press-releases", "stock-news"]
            datasets_to_fetch = [d for d in available_datasets if d.dataset in quick_names]
        else:
            # Full discovery - all non-SEC document datasets
            datasets_to_fetch = available_datasets
        
        # Aggregate data from multiple endpoints
        aggregated_data: Dict[str, Any] = {}
        errors: List[str] = []

        async def fetch_dataset(dataset: DatasetEntry) -> Dict[str, Any]:
            try:
                return await self._fetch_document_dataset(symbol, dataset)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch %s: %s", dataset.dataset, exc)
                return {"error": str(exc)}

        factories = {
            dataset.dataset: (lambda d=dataset: fetch_dataset(d))
            for dataset in datasets_to_fetch
        }

        raw_results = await gather_dict(factories, concurrency_limit=4) if factories else {}

        for dataset_name, payload in raw_results.items():
            if payload.get("error"):
                errors.append(f"{dataset_name}: {payload['error']}")
                continue
            flattened = self._flatten_dict(payload, prefix=dataset_name)
            for key, value in flattened.items():
                aggregated_data[key] = {
                    "value": value,
                    "source": dataset_name,
                    "type": type(value).__name__
                }
        
        # Prepare final result with both fields AND documents list for compatibility
        documents_list = []
        for dataset in datasets_to_fetch:
            # Create a document entry for each dataset queried
            doc_entry = {
                "type": dataset.dataset,
                "source": "FMP",
                "url": f"{self.base_url}{dataset.url}".replace("{symbol}", symbol),
                "available": dataset.dataset not in [e.split(":")[0] for e in errors]
            }
            documents_list.append(doc_entry)
        
        discovery_result = {
            "symbol": symbol,
            "depth": depth,
            "discovered_fields": len(aggregated_data),
            "datasets_queried": len(datasets_to_fetch),
            "timestamp": datetime.now().isoformat(),
            "fields": aggregated_data,
            "documents": documents_list  # Add documents list for compatibility
        }
        
        if errors:
            discovery_result["errors"] = errors
        
        # Cache the result
        await self._set_cache(cache_key, discovery_result, self.cache_ttl)
        
        return discovery_result
    
    async def get_document_fields(self, symbol: str, keys: List[str]) -> Dict[str, Any]:
        """Get specific field values from discovered documents"""
        # First discover all document fields
        discovery = await self.discover_documents(symbol, "quick")
        
        # Extract requested fields
        result = {
            "symbol": symbol,
            "requested_fields": keys,
            "found_fields": {},
            "missing_fields": []
        }
        
        fields_data = discovery.get("fields", {})
        
        for key in keys:
            if key in fields_data:
                result["found_fields"][key] = fields_data[key]
            else:
                result["missing_fields"].append(key)
        
        return result
    
    async def get_raw_document(
        self,
        dataset_name: str,
        params: Dict[str, Any],
        paginate: bool = False,
        max_pages: int = 5,
    ) -> Dict[str, Any]:
        """Get raw data from a specific document dataset with optional pagination."""
        dataset = self.ddc_loader.get_dataset(dataset_name)
        if not dataset:
            return {"error": f"Dataset '{dataset_name}' not found in catalog"}

        params_schema = dataset.params_schema
        required_params = [
            param for param, ptype in params_schema.items()
            if param != "apikey" and not str(ptype).endswith("?")
        ]
        missing = [p for p in required_params if p not in params]
        if missing:
            return {
                "error": f"Missing required parameters for {dataset_name}: {missing}",
                "required_schema": params_schema,
                "provided_params": list(params.keys()),
                "catalog_notes": dataset.notes,
                "dataset_url": dataset.url,
            }

        async def fetch_page(page_idx: Optional[int] = None) -> Dict[str, Any]:
            url = dataset.url
            for key, value in params.items():
                placeholder = f"{{{key}}}"
                if placeholder in url:
                    url = url.replace(placeholder, str(value))

            full_url = f"{self.base_url}{url}"
            query_params = {"apikey": self.api_key}
            query_params.update({k: v for k, v in params.items() if f"{{{k}}}" not in dataset.url})

            if paginate and page_idx is not None:
                query_params["page"] = page_idx
                query_params["limit"] = query_params.get("limit", DEFAULT_PAGE_SIZE)

            async with self.session.get(full_url, params=query_params) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status} for {dataset_name}")
                return await response.json()

        try:
            if not paginate:
                data = await fetch_page()
                pages_fetched = 1
                return {
                    "dataset": dataset_name,
                    "params": params,
                    "data": data,
                    "pages_fetched": pages_fetched,
                    "timestamp": datetime.now().isoformat(),
                }

            # Fetch up to max_pages concurrently
            page_indices = list(range(max_pages))
            factories = {idx: (lambda i=idx: fetch_page(i)) for idx in page_indices}
            results = await gather_dict(factories, concurrency_limit=3)

            all_data: List[Any] = []
            pages_fetched = 0
            for idx in page_indices:
                payload = results.get(idx)
                if isinstance(payload, list) and payload:
                    all_data.extend(payload)
                    pages_fetched += 1
                else:
                    break

            return {
                "dataset": dataset_name,
                "params": params,
                "data": all_data,
                "pages_fetched": pages_fetched,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"error": str(exc), "dataset": dataset_name, "params": params}
    
    async def _fetch_document_dataset(self, symbol: str, dataset: DatasetEntry) -> Dict[str, Any]:
        """Fetch data from a single document endpoint"""
        # Ensure session exists - fail fast if not connected
        if not self.session:
            raise RuntimeError("FMPDocumentServer not connected. Call connect() first.")
        
        try:
            # Build URL - handle different parameter patterns
            url = dataset.url
            
            # Some endpoints have {symbol} in URL
            if "{symbol}" in url:
                url = url.replace("{symbol}", symbol)
            
            full_url = f"{self.base_url}{url}"
            
            # Build params
            params = {"apikey": self.api_key}

            # Add symbol as parameter if not in URL
            if "{symbol}" not in dataset.url:
                params["symbol"] = symbol

            # Auto-fill required parameters for specific datasets during discovery
            if dataset.dataset == "earning-call-transcript":
                # Calculate most recent completed quarter
                now = datetime.now()
                current_year = now.year
                current_month = now.month

                # Determine quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
                # Use previous quarter since current quarter might not be available yet
                if current_month <= 3:
                    quarter = 4
                    year = current_year - 1
                elif current_month <= 6:
                    quarter = 1
                    year = current_year
                elif current_month <= 9:
                    quarter = 2
                    year = current_year
                else:
                    quarter = 3
                    year = current_year

                params["year"] = year
                params["quarter"] = quarter
            
            # Make HTTP request
            async with self.session.get(full_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Handle different response formats
                    if isinstance(data, list) and len(data) > 0:
                        # Return first item for discovery
                        return data[0] if isinstance(data[0], dict) else {"items": data[:5]}
                    elif isinstance(data, dict):
                        return data
                    else:
                        return {"data": data}
                else:
                    raise Exception(f"HTTP {response.status}")
        except asyncio.TimeoutError:
            raise Exception("Request timeout")
        except Exception as e:
            raise Exception(f"Fetch error: {str(e)}")
    

    def _flatten_dict(self, d: Dict, prefix: str = "", sep: str = ".") -> Dict:
        """Flatten nested dictionary to dotted keys"""
        items = []
        for k, v in d.items():
            new_key = f"{prefix}{sep}{k}" if prefix else k
            
            if isinstance(v, dict):
                # Recursively flatten nested dicts
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # For lists, just store length and sample
                items.append((f"{new_key}_count", len(v)))
                if v and isinstance(v[0], dict):
                    # Sample first item if it's a dict
                    items.extend(self._flatten_dict(v[0], f"{new_key}[0]", sep=sep).items())
                elif v:
                    # Store first few items as sample
                    items.append((f"{new_key}_sample", v[:3]))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    async def _get_cache(self, key: str) -> Optional[Dict]:
        """Get value from cache (Redis or memory)"""
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            cached = self.memory_cache[key]
            if cached["expires"] > datetime.now():
                return cached["data"]
            else:
                del self.memory_cache[key]
        
        return None
    
    async def _set_cache(self, key: str, value: Dict, ttl: int):
        """Set value in cache (Redis or memory)"""
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key, 
                    ttl, 
                    json.dumps(value)
                )
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # Fallback to memory cache
        self.memory_cache[key] = {
            "data": value,
            "expires": datetime.now() + timedelta(seconds=ttl)
        }
