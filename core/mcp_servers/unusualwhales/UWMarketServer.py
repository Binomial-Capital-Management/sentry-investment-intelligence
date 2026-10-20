"""
Unusual Whales Market MCP Server.

Provides market analytics, seasonality, short interest, earnings, and screening tools.
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


class UWMarketServer(MCPServer):
    """
    MCP Server for Unusual Whales market-wide data.
    7 tools covering earnings, correlations, market overview, analysts, screening, seasonality, and short interest.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize UW Market Server."""
        super().__init__()
        self._name = "UWMarketServer"
        self.use_structured_content = False
        
        if api_key is None:
            api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        
        if not api_key:
            raise ValueError("UW_API_KEY or UNUSUAL_WHALES_API_KEY not provided")
        
        self.api_key = api_key
        self.base_url = "https://api.unusualwhales.com"
        
        self.ddc_loader = UWDDCLoader()
        self.data_fetcher = UWDataFetcher(api_key, self.base_url)
        
        logger.info("UWMarketServer initialized")
    
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
        logger.info("UWMarketServer connected")
    
    async def cleanup(self):
        await self.data_fetcher.cleanup()
        logger.info("UWMarketServer cleaned up")
    
    def _get_tools(self) -> List[MCPTool]:
        """Return all available tools."""
        return [
            self._tool_earnings(),
            self._tool_correlations(),
            self._tool_market_overview(),
            self._tool_analyst_ratings(),
            self._tool_stock_screener(),
            self._tool_seasonality(),
            self._tool_short_data(),
        ]
    
    # ==========================================================================
    # TOOL DEFINITIONS
    # ==========================================================================
    
    def _tool_earnings(self) -> MCPTool:
        return MCPTool(
            name="uw_earnings",
            description="""Returns historical earnings data for a specific ticker.

USE THIS FOR: Analyzing earnings history, tracking estimate accuracy, backtesting earnings-based strategies, and understanding historical volatility around announcements.

RETURNS: Past earnings reports with:
- EPS actual vs estimate (beat/miss)
- Revenue actual vs estimate
- Report date and time (pre-market/after-hours)
- Surprise percentage

ANALYSIS TIPS:
- Track beat/miss consistency over quarters
- Note magnitude of surprises
- Correlate with post-earnings price moves
- Identify estimate revision trends""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker (required)"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_correlations(self) -> MCPTool:
        return MCPTool(
            name="uw_correlations",
            description="""Returns correlation matrix between multiple tickers.

USE THIS FOR: Portfolio diversification analysis, finding correlated pairs for pairs trading, risk management, and understanding sector/asset relationships.

RETURNS: Pairwise correlation coefficients between all provided tickers. Values range from -1 (perfect negative) to +1 (perfect positive).

INTERVALS: 1D, 1W, 1M, 1Y, YTD (default: 1Y)

ANALYSIS TIPS:
- Correlations > 0.7 = highly correlated (limited diversification)
- Correlations < 0.3 = good diversification
- Negative correlations = potential hedge
- Compare across timeframes for stability""",
            inputSchema={
                "type": "object",
                "properties": {
                    "tickers": {"type": "string", "description": "Comma-separated tickers (e.g., 'AAPL,MSFT,GOOGL,AMZN')"},
                    "interval": {"type": "string", "default": "1Y", "description": "Time interval: 1D, 1W, 1M, 1Y, YTD"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (alternative to interval)"},
                    "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                },
                "required": ["tickers"],
                "additionalProperties": False
            }
        )
    
    def _tool_market_overview(self) -> MCPTool:
        return MCPTool(
            name="uw_market_overview",
            description="""Returns market-wide overview data: sector ETF performance, SPIKE indicator, or top movers by flow.

USE THIS FOR: Quick market health check, sector rotation analysis, identifying market stress, and finding where smart money is flowing.

VIEWS:
- sectors: Current day stats for SPDR sector ETFs (XLK, XLF, XLE, XLV, etc.). Great for sector heatmaps.
- spike: Unusual Whales proprietary SPIKE indicator values throughout the day. UW-specific volatility/stress measure.
- movers: Top tickers by net premium flow - split into most bullish and most bearish. Smart money direction.

RETURNS BY VIEW:
- sectors: Price, change %, volume for each sector ETF
- spike: Time series of SPIKE values with timestamps
- movers: Tickers ranked by net premium (bullish and bearish halves)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "view": {"type": "string", "default": "sectors", "enum": ["sectors", "spike", "movers"], "description": "Data view type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (spike/movers views)"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100, "description": "Number of movers (movers view only)"},
                    "issue_types": {"type": "array", "items": {"type": "string"}, "description": "Filter: Common Stock, ETF, Index, ADR (movers view)"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_analyst_ratings(self) -> MCPTool:
        return MCPTool(
            name="uw_analyst_ratings",
            description="""Returns latest analyst ratings and price target changes.

USE THIS FOR: Tracking Wall Street sentiment, identifying upgrade/downgrade catalysts, screening for consensus changes, and monitoring price target revisions.

RETURNS: Analyst firm name, action type, recommendation, price target (current and prior), ticker, and date.

FILTERS:
- ticker: Focus on specific stock
- action: initiated, reiterated, downgraded, upgraded, maintained
- recommendation: buy, hold, sell

ANALYSIS TIPS:
- Multiple upgrades in short period = momentum building
- Price target raises above current price = upside potential
- Downgrades on good news = potential exhaustion
- Initiations often move stocks""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Filter by stock ticker"},
                    "action": {"type": "string", "description": "Filter: initiated, reiterated, downgraded, upgraded, maintained"},
                    "recommendation": {"type": "string", "description": "Filter: buy, hold, sell"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_stock_screener(self) -> MCPTool:
        return MCPTool(
            name="uw_stock_screener",
            description="""Comprehensive stock screener with 50+ options flow filters.

USE THIS FOR: Finding unusual activity, screening for specific options setups, identifying stocks with elevated flow, and building watchlists based on options data.

KEY FILTER CATEGORIES:
- Basic: ticker, sectors, S&P 500, dividends, price, marketcap
- Options Volume: call/put volume, total premium, net premium
- IV/Volatility: IV rank, implied move, volatility
- OI Analysis: open interest, OI change %, put-call ratio
- Historical: 3-day and 30-day volume percentiles

ORDER BY: Most fields can be used for sorting (premium, volume, iv_rank, put_call_ratio, etc.)

RETURNS: Stocks matching criteria with full options flow metrics including volumes, premiums, IV, OI, and historical comparisons.

EXAMPLE SCREENS:
- High IV rank + high premium: min_iv_rank=80, min_premium=1000000
- Unusual call activity: min_call_volume=10000, min_perc_30_day_call=90
- S&P 500 high net premium: is_s_p_500=true, order=net_premium""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Filter by ticker"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD"},
                    "sectors": {"type": "array", "items": {"type": "string"}, "description": "Sectors: Technology, Healthcare, Energy, etc."},
                    "issue_types": {"type": "array", "items": {"type": "string"}, "description": "Common Stock, ETF, Index, ADR"},
                    "is_s_p_500": {"type": "boolean", "description": "Only S&P 500 stocks"},
                    "has_dividends": {"type": "boolean", "description": "Only dividend payers"},
                    "min_underlying_price": {"type": "string"},
                    "max_underlying_price": {"type": "string"},
                    "min_marketcap": {"type": "string"},
                    "max_marketcap": {"type": "string"},
                    "min_change": {"type": "string", "description": "Min price change %"},
                    "max_change": {"type": "string"},
                    "min_volume": {"type": "integer", "description": "Min options volume"},
                    "max_volume": {"type": "integer"},
                    "min_premium": {"type": "string", "description": "Min total premium"},
                    "max_premium": {"type": "string"},
                    "min_net_premium": {"type": "string", "description": "Min net premium (calls - puts)"},
                    "max_net_premium": {"type": "string"},
                    "min_put_call_ratio": {"type": "string"},
                    "max_put_call_ratio": {"type": "string"},
                    "min_iv_rank": {"type": "string", "description": "Min IV percentile (0-100)"},
                    "max_iv_rank": {"type": "string"},
                    "min_oi": {"type": "integer", "description": "Min open interest"},
                    "max_oi": {"type": "integer"},
                    "order": {"type": "string", "description": "Sort field"},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"]},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_seasonality(self) -> MCPTool:
        return MCPTool(
            name="uw_seasonality",
            description="""Returns historical seasonality data for calendar-based analysis.

USE THIS FOR: Seasonal trading strategies, identifying historically strong/weak months, timing entries/exits, and calendar-based allocation.

VIEWS:
- market: Average monthly returns for SPY, QQQ, IWM, and sector ETFs. No parameters needed.
- performers: Top performing stocks for a specific month historically. Requires 'month' (1-12).
- ticker: Average return by month for a specific stock. Requires 'ticker'.
- ticker_yearly: Year x Month return matrix for detailed breakdown. Requires 'ticker'.

RETURNS BY VIEW:
- market: Monthly avg returns for major ETFs
- performers: Tickers ranked by historical month performance with win rate, median/avg change
- ticker: 12 months of average historical returns
- ticker_yearly: Multi-year matrix of monthly returns

EXAMPLE: Find best January stocks: view='performers', month=1""",
            inputSchema={
                "type": "object",
                "properties": {
                    "view": {"type": "string", "default": "market", "enum": ["market", "performers", "ticker", "ticker_yearly"], "description": "Data view type"},
                    "ticker": {"type": "string", "description": "Stock ticker (required for ticker/ticker_yearly views)"},
                    "month": {"type": "integer", "minimum": 1, "maximum": 12, "description": "Calendar month 1-12 (required for performers view)"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "description": "Results limit (performers view)"},
                    "min_years": {"type": "integer", "default": 10, "minimum": 1, "description": "Min years of history (performers)"},
                    "s_p_500_nasdaq_only": {"type": "boolean", "description": "Only S&P 500/Nasdaq stocks (performers)"},
                    "order": {"type": "string", "description": "Sort: positive_months_perc, median_change, avg_change (performers)"},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"]},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_short_data(self) -> MCPTool:
        return MCPTool(
            name="uw_short_data",
            description="""Returns comprehensive short selling data for a ticker.

USE THIS FOR: Identifying short squeeze candidates, tracking short interest, understanding borrow costs, monitoring FTDs, and analyzing short seller behavior.

VIEWS:
- data: Current borrow data - rebate rate, fee rate, shares available. Hard-to-borrow indicator.
- interest: Short interest as % of float, shares shorted, days to cover. Classic short squeeze metrics.
- volume: Daily short volume and short ratio over time. Short activity trends.
- ftds: Failures to Deliver history. Potential naked shorting indicator.
- exchange: Short volume breakdown by exchange. Market structure analysis.

KEY METRICS:
- High fee rate + low availability = hard to borrow (squeeze potential)
- High short % of float + high days to cover = squeeze setup
- Rising short ratio = increasing short pressure
- Persistent FTDs = settlement issues, regulatory risk

All views require ticker parameter.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker (required)"},
                    "view": {"type": "string", "default": "data", "enum": ["data", "interest", "volume", "ftds", "exchange"], "description": "Data view type"},
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
                "uw_earnings": self._handle_earnings,
                "uw_correlations": self._handle_correlations,
                "uw_market_overview": self._handle_market_overview,
                "uw_analyst_ratings": self._handle_analyst_ratings,
                "uw_stock_screener": self._handle_stock_screener,
                "uw_seasonality": self._handle_seasonality,
                "uw_short_data": self._handle_short_data,
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
    
    def _success_result(self, data: Any, label: str = "uw_market") -> CallToolResult:
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
        to the appropriate parameter name (ticker, tickers, month, etc.)
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
            args.get("tickers") or
            args.get("month")
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
    
    async def _handle_earnings(self, args: Dict) -> Dict:
        return await self._fetch("earnings-historical", {"ticker": args["ticker"]})
    
    async def _handle_correlations(self, args: Dict) -> Dict:
        return await self._fetch("market-correlations", {
            "tickers": args["tickers"],
            "interval": args.get("interval", "1Y"),
            "start_date": args.get("start_date"),
            "end_date": args.get("end_date"),
        })
    
    async def _handle_market_overview(self, args: Dict) -> Dict:
        view = args.get("view", "sectors")
        
        if view == "sectors":
            return await self._fetch("market-sector-etfs", {})
        elif view == "spike":
            return await self._fetch("market-spike", {"date": args.get("date")})
        else:  # movers
            params = {
                "date": args.get("date"),
                "limit": args.get("limit", 20),
            }
            if args.get("issue_types"):
                params["issue_types[]"] = args["issue_types"]
            return await self._fetch("market-top-net-impact", params)
    
    async def _handle_analyst_ratings(self, args: Dict) -> Dict:
        return await self._fetch("screener-analysts", {
            "ticker": args.get("ticker"),
            "action": args.get("action"),
            "recommendation": args.get("recommendation"),
            "limit": args.get("limit", 50),
        })
    
    async def _handle_stock_screener(self, args: Dict) -> Dict:
        params = {
            "ticker": args.get("ticker"),
            "date": args.get("date"),
            "is_s_p_500": args.get("is_s_p_500"),
            "has_dividends": args.get("has_dividends"),
            "min_underlying_price": args.get("min_underlying_price"),
            "max_underlying_price": args.get("max_underlying_price"),
            "min_marketcap": args.get("min_marketcap"),
            "max_marketcap": args.get("max_marketcap"),
            "min_change": args.get("min_change"),
            "max_change": args.get("max_change"),
            "min_volume": args.get("min_volume"),
            "max_volume": args.get("max_volume"),
            "min_premium": args.get("min_premium"),
            "max_premium": args.get("max_premium"),
            "min_net_premium": args.get("min_net_premium"),
            "max_net_premium": args.get("max_net_premium"),
            "min_put_call_ratio": args.get("min_put_call_ratio"),
            "max_put_call_ratio": args.get("max_put_call_ratio"),
            "min_iv_rank": args.get("min_iv_rank"),
            "max_iv_rank": args.get("max_iv_rank"),
            "min_oi": args.get("min_oi"),
            "max_oi": args.get("max_oi"),
            "order": args.get("order"),
            "order_direction": args.get("order_direction", "desc"),
        }
        if args.get("sectors"):
            params["sectors[]"] = args["sectors"]
        if args.get("issue_types"):
            params["issue_types[]"] = args["issue_types"]
        return await self._fetch("screener-stocks", params)
    
    async def _handle_seasonality(self, args: Dict) -> Dict:
        view = args.get("view", "market")
        
        if view == "market":
            return await self._fetch("seasonality-market", {})
        elif view == "performers":
            if not args.get("month"):
                return {"error": "month parameter required for performers view"}
            params = {
                "month": str(args["month"]),
                "limit": args.get("limit", 50),
                "min_years": args.get("min_years", 10),
                "s_p_500_nasdaq_only": args.get("s_p_500_nasdaq_only"),
                "order": args.get("order"),
                "order_direction": args.get("order_direction", "desc"),
            }
            return await self._fetch("seasonality-month-performers", params)
        elif view == "ticker":
            if not args.get("ticker"):
                return {"error": "ticker parameter required for ticker view"}
            return await self._fetch("seasonality-ticker-monthly", {"ticker": args["ticker"]})
        else:  # ticker_yearly
            if not args.get("ticker"):
                return {"error": "ticker parameter required for ticker_yearly view"}
            return await self._fetch("seasonality-ticker-year-month", {"ticker": args["ticker"]})
    
    async def _handle_short_data(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        view = args.get("view", "data")
        
        dataset_map = {
            "data": "shorts-data",
            "interest": "shorts-interest-float",
            "volume": "shorts-volume-ratio",
            "ftds": "shorts-ftds",
            "exchange": "shorts-volume-by-exchange",
        }
        return await self._fetch(dataset_map[view], {"ticker": ticker})
