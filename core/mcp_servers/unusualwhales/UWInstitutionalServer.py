"""
Unusual Whales Institutional MCP Server.

Provides congressional trading, dark pool, insider, ETF, and 13F institutional data.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

from .uw_ddc_loader import UWDDCLoader
from .uw_data_fetcher import UWDataFetcher

logger = logging.getLogger(__name__)


class UWInstitutionalServer(MCPServer):
    """
    MCP Server for Unusual Whales institutional and political flow data.
    7 tools covering congressional trades, dark pools, insider transactions, 13F filings, and ETF data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize UW Institutional Server."""
        super().__init__()
        self._name = "UWInstitutionalServer"
        self.use_structured_content = False
        
        if api_key is None:
            api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        
        if not api_key:
            raise ValueError("UW_API_KEY or UNUSUAL_WHALES_API_KEY not provided")
        
        self.api_key = api_key
        self.base_url = "https://api.unusualwhales.com"
        
        self.ddc_loader = UWDDCLoader()
        self.data_fetcher = UWDataFetcher(api_key, self.base_url)
        
        logger.info("UWInstitutionalServer initialized")
    
    @property
    def name(self) -> str:
        return self._name
    
    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        return self._get_tools()
    
    async def list_prompts(self, run_context, agent) -> List[str]:
        return []
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any], run_context, agent) -> str:
        raise NotImplementedError(f"No prompts available for {self.name}")
    
    async def connect(self):
        await self.data_fetcher.connect()
        logger.info("UWInstitutionalServer connected")
    
    async def cleanup(self):
        await self.data_fetcher.cleanup()
        logger.info("UWInstitutionalServer cleaned up")
    
    def _get_tools(self) -> List[MCPTool]:
        """Return all available tools."""
        return [
            self._tool_congress(),
            self._tool_darkpool(),
            self._tool_insider(),
            self._tool_institution(),
            self._tool_ownership(),
            self._tool_institutions_list(),
            self._tool_etf(),
        ]
    
    # ==========================================================================
    # TOOL DEFINITIONS
    # ==========================================================================
    
    def _tool_congress(self) -> MCPTool:
        return MCPTool(
            name="uw_congress",
            description="""Returns US Congress member stock trading data from STOCK Act disclosures.

USE THIS FOR: Tracking political insider trading, identifying trending tickers among politicians, monitoring STOCK Act compliance, and analyzing congressional trading patterns.

VIEWS (choose one):
- recent: Latest trades across ALL congress members. Real-time feed of political trading.
- member: Trading history for a SPECIFIC politician. Requires 'name' parameter.
- late: Late-filed disclosures (STOCK Act violations). Trades disclosed after 45-day deadline.

DATA SOURCE: SEC periodic transaction reports required under the STOCK Act.

RETURNS: Congress member name, party, chamber, ticker, transaction type (purchase/sale), amount range (e.g., $1,001-$15,000), transaction date, disclosure date.

NOTABLE TRADERS: Nancy Pelosi, Dan Crenshaw, Tommy Tuberville, and others.

NAME FORMAT for 'member' view: Full name like "Nancy Pelosi", "Dan Crenshaw"

ANALYSIS TIPS:
- Cluster purchases across multiple members = potential signal
- Compare transaction date vs disclosure date for timing
- Watch committee members trading in their oversight sectors
- Late filers on profitable trades may indicate intentional delay""",
            inputSchema={
                "type": "object",
                "properties": {
                    "view": {"type": "string", "default": "recent", "enum": ["recent", "member", "late"], "description": "Data view: recent (all members), member (specific person), late (violations)"},
                    "name": {"type": "string", "description": "Congress member name for 'member' view (e.g., 'Nancy Pelosi')"},
                    "ticker": {"type": "string", "description": "Filter by stock ticker"},
                    "date": {"type": "string", "description": "Filter by date YYYY-MM-DD"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_darkpool(self) -> MCPTool:
        return MCPTool(
            name="uw_darkpool",
            description="""Returns dark pool (off-exchange) trade prints for institutional block detection.

USE THIS FOR: Detecting large institutional block trades, identifying accumulation/distribution patterns, tracking off-exchange activity, and finding potential support/resistance from large prints.

WHAT ARE DARK POOLS: Alternative trading systems where large orders execute away from public exchanges to minimize market impact. ~40% of US equity volume trades in dark pools.

MODES:
- Without ticker: Market-wide dark pool feed across all stocks
- With ticker: Dark pool prints for that specific stock only

RETURNS: Ticker, size (shares), price, premium (size × price), timestamp, execution venue.

KEY SIGNALS:
- Large prints at/above VWAP = institutional accumulation
- Large prints below VWAP = institutional distribution
- Cluster of prints at price level = support/resistance
- Premium spikes = unusual large block activity

FILTERS: Use min_premium for significant trades (e.g., 100000 for $100K+ trades)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker (omit for market-wide feed)"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    "min_premium": {"type": "integer", "minimum": 0, "description": "Minimum trade value in dollars"},
                    "max_premium": {"type": "integer", "description": "Maximum trade value"},
                    "min_size": {"type": "integer", "minimum": 0, "description": "Minimum share size"},
                    "max_size": {"type": "integer", "description": "Maximum share size"},
                    "newer_than": {"type": "string", "description": "Time filter (ticker mode only)"},
                    "older_than": {"type": "string", "description": "Time filter (ticker mode only)"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_insider(self) -> MCPTool:
        return MCPTool(
            name="uw_insider",
            description="""Returns SEC Form 4 insider transactions (executives, directors, 10%+ owners).

USE THIS FOR: Tracking smart money, identifying insider sentiment, screening for cluster buying, finding executives buying their own stock, and detecting insider confidence signals.

VIEWS:
- transactions: Full transaction screener with 20+ filters. Default view.
- summary: Market-wide aggregated insider buying vs selling over time.

DATA SOURCE: SEC Form 4 filings required within 2 business days of transaction.

TRANSACTION CODES (for filtering):
- P = Open market purchase (most bullish signal)
- S = Open market sale
- A = Award/grant
- M = Option exercise
- G = Gift

KEY FILTERS (transactions view):
- is_officer=true: C-suite executives
- is_director=true: Board members
- is_ten_percent_owner=true: Major shareholders
- transaction_codes=['P']: Purchases only
- min_value: Dollar amount filter

CLUSTER BUYING: Multiple insiders buying = strong conviction signal.

RETURNS: Insider name, title, ticker, shares, value, price, transaction type, filing date.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "view": {"type": "string", "default": "transactions", "enum": ["transactions", "summary"], "description": "transactions (screener) or summary (market-wide aggregates)"},
                    "ticker": {"type": "string", "description": "Filter by ticker (transactions view)"},
                    "owner_name": {"type": "string", "description": "Filter by insider name"},
                    "is_officer": {"type": "boolean", "description": "Filter for officers (CEO, CFO, etc.)"},
                    "is_director": {"type": "boolean", "description": "Filter for board directors"},
                    "is_ten_percent_owner": {"type": "boolean", "description": "Filter for 10%+ owners"},
                    "transaction_codes": {"type": "array", "items": {"type": "string"}, "description": "P (purchase), S (sale), M (exercise), A (award)"},
                    "common_stock_only": {"type": "boolean", "description": "Exclude derivatives"},
                    "is_s_p_500": {"type": "boolean", "description": "Only S&P 500 companies"},
                    "min_value": {"type": "string", "description": "Minimum transaction value"},
                    "max_value": {"type": "string", "description": "Maximum transaction value"},
                    "min_marketcap": {"type": "integer", "minimum": 0},
                    "max_marketcap": {"type": "integer"},
                    "market_cap_size": {"type": "string", "description": "small, mid, large"},
                    "sectors": {"type": "string", "description": "Filter by sector"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    "page": {"type": "integer", "default": 0, "minimum": 0},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_institution(self) -> MCPTool:
        return MCPTool(
            name="uw_institution",
            description="""Returns 13F quarterly filings data for a specific institutional investor.

USE THIS FOR: Tracking hedge fund positions, analyzing institutional conviction, following smart money allocation, and understanding sector tilts.

VIEWS:
- holdings: Full portfolio holdings with positions, values, and changes. Default view.
- sectors: Sector allocation breakdown showing tilts and rotation.

DATA SOURCE: SEC Form 13F filed quarterly by institutions managing $100M+. 45-day delay from quarter end.

REQUIRES: Institution name or CIK number.

NOTABLE INSTITUTIONS: Berkshire Hathaway, Bridgewater Associates, Renaissance Technologies, Citadel, Two Sigma, Tiger Global, Coatue, Pershing Square.

RETURNS (holdings): Ticker, shares held, market value, share change, % of portfolio, first buy date, avg price.
RETURNS (sectors): Per-sector value, position counts, positions increased/decreased/closed.

NAME FORMAT: "BERKSHIRE HATHAWAY INC", "BRIDGEWATER ASSOCIATES LP", or CIK like "1067983"

ANALYSIS TIPS:
- Focus on position changes (new buys, additions, trims, exits)
- High conviction = large position relative to AUM
- Compare quarter-over-quarter for trend""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Institution name or CIK (required)"},
                    "view": {"type": "string", "default": "holdings", "enum": ["holdings", "sectors"], "description": "holdings (positions) or sectors (allocation)"},
                    "date": {"type": "string", "description": "Report date YYYY-MM-DD"},
                    "start_date": {"type": "string", "description": "Start of date range"},
                    "end_date": {"type": "string", "description": "End of date range"},
                    "security_types": {"type": "array", "items": {"type": "string"}, "description": "Filter: Share, Call, Put (holdings only)"},
                    "order": {"type": "string", "description": "Sort by: value, units, units_change, ticker"},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"]},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    "page": {"type": "integer", "default": 0, "minimum": 0},
                },
                "required": ["name"],
                "additionalProperties": False
            }
        )
    
    def _tool_ownership(self) -> MCPTool:
        return MCPTool(
            name="uw_ownership",
            description="""Returns which institutions own a specific stock from 13F filings.

USE THIS FOR: Identifying major shareholders, tracking institutional accumulation/distribution, finding activist positions, and understanding the shareholder base.

REQUIRES: Stock ticker.

RETURNS: Institution name, shares held, market value, % of shares outstanding, share change from prior quarter, first buy date, average cost basis.

TAGS: Filter by institution type - 'activist' for activist investors, etc.

ANALYSIS TIPS:
- Rising institutional ownership = accumulation
- Falling institutional ownership = distribution
- New activist position = potential catalyst
- High % outstanding = crowded trade risk""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker (required)"},
                    "date": {"type": "string", "description": "Report date YYYY-MM-DD"},
                    "start_date": {"type": "string", "description": "Start of date range"},
                    "end_date": {"type": "string", "description": "End of date range"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter: activist, value_investor, etc."},
                    "order": {"type": "string", "description": "Sort: name, units, value, perc_outstanding"},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"]},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    "page": {"type": "integer", "default": 0, "minimum": 0},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_institutions_list(self) -> MCPTool:
        return MCPTool(
            name="uw_institutions_list",
            description="""Browse and search institutional investors (13F filers).

USE THIS FOR: Discovering hedge funds, finding largest institutional players, filtering by investment style, ranking by AUM, and researching specific institutions.

RETURNS: Institution name, CIK, total AUM, breakdown by security type (shares, calls, puts, warrants), position count.

ORDER BY: name, total_value, share_value, call_value, put_value, total_holdings

TAGS: 'activist' for activist investors

ANALYSIS TIPS:
- Sort by call_value to find options-heavy funds
- Sort by put_value to find hedged/bearish funds
- Filter by min_total_value for large institutions""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Search by institution name or CIK"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter: activist, etc."},
                    "min_total_value": {"type": "string", "description": "Minimum total AUM"},
                    "max_total_value": {"type": "string", "description": "Maximum total AUM"},
                    "order": {"type": "string", "description": "Sort by: name, total_value, share_value, call_value"},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"]},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                    "page": {"type": "integer", "default": 0, "minimum": 0},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_etf(self) -> MCPTool:
        return MCPTool(
            name="uw_etf",
            description="""Returns ETF data: holdings, exposure, flows, or weights.

USE THIS FOR: ETF composition analysis, finding passive flow exposure, tracking fund flows, and understanding sector/country allocations.

VIEWS (choose one):
- holdings: All constituent stocks within an ETF with weights and values.
- exposure: Find all ETFs that hold a specific stock (reverse lookup).
- flows: ETF inflow/outflow time series (creations/redemptions).
- weights: Sector and country allocation percentages.

REQUIRES: Ticker (ETF symbol for holdings/flows/weights, stock symbol for exposure).

COMMON ETFs: SPY, QQQ, IWM, XLK, XLF, XLE, ARKK, etc.

RETURNS BY VIEW:
- holdings: Ticker, weight %, shares, value, sector
- exposure: List of ETFs holding the stock with weights
- flows: Time series of inflows, outflows, net flow
- weights: Sector % and country % breakdowns

USE CASES:
- holdings: See what's in an ETF, find top holdings
- exposure: Understand passive demand for a stock
- flows: Gauge sector/theme sentiment
- weights: Check diversification and concentration""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "ETF ticker (holdings/flows/weights) or stock ticker (exposure)"},
                    "view": {"type": "string", "default": "holdings", "enum": ["holdings", "exposure", "flows", "weights"], "description": "Data view type"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    # ==========================================================================
    # TOOL EXECUTION
    # ==========================================================================
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute a tool by name."""
        try:
            arguments = arguments or {}
            
            handlers = {
                "uw_congress": self._handle_congress,
                "uw_darkpool": self._handle_darkpool,
                "uw_insider": self._handle_insider,
                "uw_institution": self._handle_institution,
                "uw_ownership": self._handle_ownership,
                "uw_institutions_list": self._handle_institutions_list,
                "uw_etf": self._handle_etf,
                "get_fields": self._handle_get_fields,  # Generic dataset fetch for data workspace
            }
            
            handler = handlers.get(name)
            if not handler:
                return self._error_result(f"Unknown tool: {name}")
            
            result = await handler(arguments)
            if name == "get_fields" and arguments.get("_bh_raw"):
                return CallToolResult(
                    content=[{"type": "text", "text": json.dumps(result, default=str)}],
                    isError=False
                )
            return self._success_result(result, label=name)
            
        except ValueError as e:
            return self._error_result(str(e), "invalid_parameters")
        except Exception as e:
            logger.error(f"Error in {name}: {e}", exc_info=True)
            return self._error_result(str(e), "execution_error")
    
    def _success_result(self, data: Any, label: str = "uw_institutional") -> CallToolResult:
        from core.agents.binomial_hash import bh_ingest
        raw = json.dumps(data, default=str)
        text = bh_ingest(raw, label)
        return CallToolResult(
            content=[{"type": "text", "text": text}],
            isError=False
        )
    
    def _error_result(self, message: str, error_type: str = "error") -> CallToolResult:
        return CallToolResult(
            content=[{"type": "text", "text": json.dumps({"error": error_type, "message": message})}],
            isError=True
        )
    
    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic dataset fetch for data workspace compatibility.
        
        Uses identifier_param from dataset catalog to correctly map the symbol/ticker
        to the appropriate parameter name (ticker, name, cik, etc.)
        """
        datasets = args.get("datasets") or []
        if args.get("dataset"):
            datasets.append(args["dataset"])
        
        base_params = dict(args.get("params", {}))
        
        # Get identifier from various possible keys
        # Exclude placeholder values like _MARKET_
        raw_identifier = (
            args.get("ticker") or 
            args.get("symbol") or 
            args.get("cik") or 
            args.get("name")
        )
        # Don't use placeholder values as identifiers
        identifier = raw_identifier if raw_identifier and raw_identifier not in ('_MARKET_', 'MARKET', '') else None
        
        results = {}
        for ds_name in datasets:
            try:
                # Get dataset to determine correct identifier_param
                dataset = self.ddc_loader.get_dataset(ds_name)
                if not dataset:
                    results[ds_name] = {"error": f"Dataset not found: {ds_name}"}
                    continue
                
                # Build params with correct identifier key from catalog
                ds_params = dict(base_params)
                
                # Only set identifier_param from identifier if:
                # 1. We have a valid identifier
                # 2. The dataset has an identifier_param
                # 3. The param isn't already set in base_params (don't overwrite explicit params)
                if identifier and dataset.identifier_param:
                    if dataset.identifier_param not in ds_params:
                        ds_params[dataset.identifier_param] = identifier
                
                ds_params = {k: v for k, v in ds_params.items() if v is not None}
                data = await self.data_fetcher.fetch_dataset(dataset, ds_params)
                # Deep copy to prevent lazy/consumable dict issues
                import copy
                results[ds_name] = copy.deepcopy(data)
            except Exception as e:
                results[ds_name] = {"error": str(e)}
        
        return {"datasets": results}
    
    async def _fetch(self, dataset_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch from a dataset with error handling."""
        # Auto-connect if not already connected
        if self.data_fetcher.session is None:
            await self.connect()
        
        dataset = self.ddc_loader.get_dataset(dataset_name)
        if not dataset:
            return {"error": f"Dataset not found: {dataset_name}"}
        params = {k: v for k, v in params.items() if v is not None}
        return await self.data_fetcher.fetch_dataset(dataset, params)
    
    # ==========================================================================
    # HANDLER IMPLEMENTATIONS
    # ==========================================================================
    
    async def _handle_congress(self, args: Dict) -> Dict:
        view = args.get("view", "recent")
        params = {
            "ticker": args.get("ticker"),
            "date": args.get("date"),
            "limit": args.get("limit", 50),
        }
        
        if view == "member":
            params["name"] = args.get("name", "Nancy Pelosi")
            return await self._fetch("congress-trader-reports", params)
        elif view == "late":
            return await self._fetch("congress-late-reports", params)
        else:  # recent
            return await self._fetch("congress-recent-trades", params)
    
    async def _handle_darkpool(self, args: Dict) -> Dict:
        ticker = args.get("ticker")
        params = {
            "date": args.get("date"),
            "limit": args.get("limit", 50),
            "min_premium": args.get("min_premium"),
            "max_premium": args.get("max_premium"),
            "min_size": args.get("min_size"),
            "max_size": args.get("max_size"),
        }
        
        if ticker:
            params["ticker"] = ticker
            params["newer_than"] = args.get("newer_than")
            params["older_than"] = args.get("older_than")
            return await self._fetch("darkpool-ticker-trades", params)
        return await self._fetch("darkpool-recent-trades", params)
    
    async def _handle_insider(self, args: Dict) -> Dict:
        view = args.get("view", "transactions")
        
        if view == "summary":
            return await self._fetch("market-insider-buy-sells", {
                "limit": args.get("limit"),
            })
        
        # transactions view
        params = {
            "ticker_symbol": args.get("ticker"),
            "owner_name": args.get("owner_name"),
            "is_director": args.get("is_director"),
            "is_officer": args.get("is_officer"),
            "is_ten_percent_owner": args.get("is_ten_percent_owner"),
            "common_stock_only": args.get("common_stock_only"),
            "is_s_p_500": args.get("is_s_p_500"),
            "min_value": args.get("min_value"),
            "max_value": args.get("max_value"),
            "min_marketcap": args.get("min_marketcap"),
            "max_marketcap": args.get("max_marketcap"),
            "market_cap_size": args.get("market_cap_size"),
            "sectors": args.get("sectors"),
            "limit": args.get("limit", 50),
            "page": args.get("page", 0),
        }
        if args.get("transaction_codes"):
            params["transaction_codes[]"] = args["transaction_codes"]
        return await self._fetch("insider-transactions", params)
    
    async def _handle_institution(self, args: Dict) -> Dict:
        view = args.get("view", "holdings")
        name = args["name"]
        
        if view == "sectors":
            return await self._fetch("institution-sectors", {
                "name": name,
                "date": args.get("date"),
                "limit": args.get("limit", 50),
                "page": args.get("page", 0),
            })
        
        # holdings view
        params = {
            "name": name,
            "date": args.get("date"),
            "start_date": args.get("start_date"),
            "end_date": args.get("end_date"),
            "order": args.get("order"),
            "order_direction": args.get("order_direction", "desc"),
            "limit": args.get("limit", 50),
            "page": args.get("page", 0),
        }
        if args.get("security_types"):
            params["security_types"] = args["security_types"]
        return await self._fetch("institution-holdings", params)
    
    async def _handle_ownership(self, args: Dict) -> Dict:
        params = {
            "ticker": args["ticker"],
            "date": args.get("date"),
            "start_date": args.get("start_date"),
            "end_date": args.get("end_date"),
            "order": args.get("order"),
            "order_direction": args.get("order_direction", "desc"),
            "limit": args.get("limit", 50),
            "page": args.get("page", 0),
        }
        if args.get("tags"):
            params["tags[]"] = args["tags"]
        return await self._fetch("institution-ownership", params)
    
    async def _handle_institutions_list(self, args: Dict) -> Dict:
        params = {
            "name": args.get("name"),
            "min_total_value": args.get("min_total_value"),
            "max_total_value": args.get("max_total_value"),
            "order": args.get("order"),
            "order_direction": args.get("order_direction", "desc"),
            "limit": args.get("limit", 50),
            "page": args.get("page", 0),
        }
        if args.get("tags"):
            params["tags[]"] = args["tags"]
        return await self._fetch("institutions-list", params)
    
    async def _handle_etf(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        view = args.get("view", "holdings")
        
        dataset_map = {
            "holdings": "etf-holdings",
            "exposure": "etf-exposure",
            "flows": "etf-inflow-outflow",
            "weights": "etf-weights",
        }
        return await self._fetch(dataset_map[view], {"ticker": ticker})
