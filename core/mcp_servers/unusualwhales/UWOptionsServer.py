"""
Unusual Whales Options MCP Server.

Provides options flow, Greeks, volatility, and screening tools.
Under 500 lines following CODING_RULES.md - delegates to helpers for data fetching.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

from .uw_ddc_loader import UWDDCLoader
from .uw_data_fetcher import UWDataFetcher
from .uw_models import UWDatasetEntry

logger = logging.getLogger(__name__)


class UWOptionsServer(MCPServer):
    """
    MCP Server for Unusual Whales options data.
    Provides 14 tools covering flow alerts, Greeks, volatility, and screening.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize UW Options Server."""
        super().__init__()
        self._name = "UWOptionsServer"
        self.use_structured_content = False
        
        if api_key is None:
            api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        
        if not api_key:
            raise ValueError("UW_API_KEY or UNUSUAL_WHALES_API_KEY not provided")
        
        self.api_key = api_key
        self.base_url = "https://api.unusualwhales.com"
        
        self.ddc_loader = UWDDCLoader()
        self.data_fetcher = UWDataFetcher(api_key, self.base_url)
        
        logger.info("UWOptionsServer initialized")
    
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
        logger.info("UWOptionsServer connected")
    
    async def cleanup(self):
        await self.data_fetcher.cleanup()
        logger.info("UWOptionsServer cleaned up")
    
    def _get_tools(self) -> List[MCPTool]:
        """Return all available tools."""
        return [
            self._tool_flow_alerts(),
            self._tool_greek_flow(),
            self._tool_gex(),
            self._tool_flow_summary(),
            self._tool_volatility(),
            self._tool_option_chain(),
            self._tool_contract_data(),
            self._tool_oi_change(),
            self._tool_net_flow_expiry(),
            self._tool_sentiment(),
            self._tool_hottest_contracts(),
            self._tool_options_volume(),
            self._tool_greeks(),
            self._tool_option_price_levels(),
        ]
    
    def _tool_flow_alerts(self) -> MCPTool:
        return MCPTool(
            name="uw_flow_alerts",
            description="""Detects unusual options activity and institutional flow patterns in real-time.

USE THIS FOR: Real-time monitoring of unusual trades, sweep orders, floor trades, and institutional patterns as they happen.

IMPORTANT - ORDERING: Results are returned in CHRONOLOGICAL ORDER (newest first). This endpoint CANNOT sort by premium, volume, or size. For "top contracts by premium/volume" queries, use uw_hottest_contracts instead.

RETURNS: Trade details including premium, size, side (ask/bid), Greeks, underlying price, option symbol, timestamps, and pattern classification (sweep, floor, repeated hits, etc.).

KEY FILTERS:
- is_sweep=true: Intermarket sweeps indicate urgency (aggressive buying/selling across exchanges)
- is_floor=true: Floor trades suggest institutional block orders
- all_opening=true: New positions being opened (vs closing existing)
- is_otm=true: Out-of-the-money bets (more speculative/leveraged)
- min_premium: Filter by minimum dollar amount (e.g., 100000 for $100K+ trades)

PATTERNS (rule_name): FloorTradeSmallCap, FloorTradeMidCap, FloorTradeLargeCap, RepeatedHits, RepeatedHitsAscendingFill, RepeatedHitsDescendingFill, OtmEarningsFloor, LowHistoricVolumeFloor, SweepsFollowedByFloor""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Comma-separated tickers (e.g., 'AAPL,TSLA'). Prefix '-' to exclude (e.g., '-SPY,-QQQ')"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200, "description": "Number of alerts to return"},
                    "min_premium": {"type": "integer", "minimum": 0, "description": "Minimum trade premium in dollars (e.g., 50000 for $50K+)"},
                    "max_premium": {"type": "integer", "minimum": 0, "description": "Maximum trade premium in dollars"},
                    "min_size": {"type": "integer", "minimum": 0, "description": "Minimum contract size"},
                    "max_size": {"type": "integer", "minimum": 0, "description": "Maximum contract size"},
                    "is_call": {"type": "boolean", "default": True, "description": "Include call options"},
                    "is_put": {"type": "boolean", "default": True, "description": "Include put options"},
                    "is_sweep": {"type": "boolean", "description": "Filter for intermarket sweep orders (aggressive, multi-exchange)"},
                    "is_floor": {"type": "boolean", "description": "Filter for floor/block trades (institutional)"},
                    "is_otm": {"type": "boolean", "description": "Only out-of-the-money contracts"},
                    "is_ask_side": {"type": "boolean", "default": True, "description": "Include trades at/near ask (bullish for calls)"},
                    "is_bid_side": {"type": "boolean", "default": True, "description": "Include trades at/near bid (bearish for calls)"},
                    "all_opening": {"type": "boolean", "default": True, "description": "Only opening transactions (new positions)"},
                    "min_dte": {"type": "integer", "minimum": 0, "description": "Minimum days to expiration"},
                    "max_dte": {"type": "integer", "minimum": 0, "description": "Maximum days to expiration (0 for 0DTE)"},
                    "issue_types": {"type": "array", "items": {"type": "string", "enum": ["Common Stock", "ETF", "Index", "ADR"]}, "description": "Filter by security type"},
                    "rule_name": {"type": "array", "items": {"type": "string"}, "description": "Filter by alert pattern/rule"},
                    "newer_than": {"type": "string", "description": "Only alerts after this time (Unix ms/s or ISO date)"},
                    "older_than": {"type": "string", "description": "Only alerts before this time (Unix ms/s or ISO date)"},
                    "sectors": {"type": "array", "items": {"type": "string"}, "description": "Filter by sector: Technology, Healthcare, Energy, etc."},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_greek_flow(self) -> MCPTool:
        return MCPTool(
            name="uw_greek_flow",
            description="""Tracks real-time delta and vega flow per minute for a ticker or sector group.

USE THIS FOR: Measuring directional sentiment (delta) and volatility demand (vega) throughout the trading day. Useful for intraday analysis, understanding institutional positioning, and timing entries.

RETURNS: Per-minute data with directional delta/vega flow, total delta/vega flow, OTM-specific flows, net call/put premium, net call/put volume, and transaction counts.

KEY CONCEPTS:
- Delta Flow: Positive = bullish positioning, Negative = bearish positioning
- Vega Flow: High positive = buying volatility, Negative = selling volatility
- Directional vs Total: Directional adjusts for trade side (ask=buy, bid=sell)
- OTM Flow: Out-of-the-money specific, indicates speculative activity

FLOW GROUPS: airline, bank, basic materials, china, communication services, consumer cyclical, consumer defensive, crypto, cyber, energy, financial services, gas, gold, healthcare, industrials, mag7, oil, real estate, refiners, reit, semi, silver, technology, uranium, utilities

Add 'expiry' parameter to break down by expiration date.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Single stock ticker (use this OR flow_group, not both)"},
                    "flow_group": {"type": "string", "description": "Sector/theme group: mag7, semi, bank, oil, gold, etc."},
                    "expiry": {"type": "string", "description": "ISO date (YYYY-MM-DD) to filter and break down by specific expiration"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_gex(self) -> MCPTool:
        return MCPTool(
            name="uw_gex",
            description="""Calculates Gamma Exposure (GEX) and other Greek exposures for market maker hedging analysis.

USE THIS FOR: Understanding how market makers must hedge, identifying potential support/resistance levels, predicting volatility regimes, and finding gamma squeeze setups.

KEY CONCEPTS:
- Positive GEX: Market makers are long gamma → they sell into rallies, buy into dips → SUPPRESSES volatility
- Negative GEX: Market makers are short gamma → they buy into rallies, sell into dips → AMPLIFIES volatility
- GEX Flip: Price level where gamma exposure changes sign (key pivot point)
- Charm/Vanna: Second-order Greeks showing how delta changes with time/volatility

VIEWS:
- summary: Historical time series of total Greek exposure
- by_strike: GEX breakdown per strike price (find walls/magnets)
- by_expiry: GEX breakdown per expiration date
- by_strike_expiry: Combined strike+expiry view (requires expiry param)
- spot_strike: Real-time spot GEX per strike ($ hedging per 1% move)
- spot_expiry_strike: Real-time spot GEX with expiry filter

RETURNS: call_gamma, put_gamma, call_delta, put_delta, call_charm, put_charm, call_vanna, put_vanna multiplied by OI and shares/contract.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "view": {"type": "string", "default": "summary", "enum": ["summary", "by_strike", "by_expiry", "by_strike_expiry", "spot_strike", "spot_expiry_strike"], "description": "Analysis view type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "timeframe": {"type": "string", "default": "1Y", "description": "Historical range for summary view: YTD, 1D, 1W, 1M, 2M, 1Y"},
                    "expiry": {"type": "string", "description": "Expiration date YYYY-MM-DD (required for by_strike_expiry)"},
                    "expirations": {"type": "array", "items": {"type": "string"}, "description": "Array of expiry dates (required for spot_expiry_strike)"},
                    "min_strike": {"type": "number", "minimum": 0, "description": "Filter strikes above this price"},
                    "max_strike": {"type": "number", "minimum": 0, "description": "Filter strikes below this price"},
                    "min_dte": {"type": "integer", "minimum": 0, "description": "Minimum days to expiration"},
                    "max_dte": {"type": "integer", "minimum": 0, "description": "Maximum days to expiration"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 500, "description": "Max results per page"},
                    "page": {"type": "integer", "default": 0, "minimum": 0, "description": "Page number for pagination"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_flow_summary(self) -> MCPTool:
        return MCPTool(
            name="uw_flow_summary",
            description="""Aggregates options flow data by expiration, strike, or time for a single ticker.

USE THIS FOR: Understanding where money is flowing, finding high-conviction expirations/strikes, identifying institutional targets, and building flow-based charts.

VIEWS:
- expiry: Call/put premium and volume aggregated per expiration date. Great for seeing if flow targets near-term or LEAPS.
- strike: Call/put premium and volume per strike price. Shows where institutions are building positions.
- strike_intraday: 1-minute interval flow per strike throughout the day. Reveals intraday accumulation patterns.
- recent: Latest individual trades for the ticker. Good for real-time monitoring.

RETURNS: For each grouping - call_premium, put_premium, call_volume, put_volume, call_trades, put_trades, ask/bid side breakdowns, OTM-specific metrics.

ANALYSIS TIPS:
- Compare call vs put premium to gauge directional bias
- High volume at specific strikes = institutional targets
- Ask-side premium > bid-side = bullish (buyers paying up)
- Check OTM premium for speculative bets""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "view": {"type": "string", "default": "expiry", "enum": ["expiry", "strike", "strike_intraday", "recent"], "description": "Aggregation method"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "filter": {"type": "string", "default": "NetPremium", "enum": ["NetPremium", "Volume", "Trades"], "description": "Sort/rank by (strike_intraday only)"},
                    "min_premium": {"type": "integer", "minimum": 0, "description": "Minimum trade premium filter (recent view only)"},
                    "side": {"type": "string", "default": "ALL", "enum": ["ALL", "ASK", "BID", "MID"], "description": "Filter by trade side (recent view only)"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_volatility(self) -> MCPTool:
        return MCPTool(
            name="uw_volatility",
            description="""Comprehensive implied and realized volatility analysis for options pricing and vol trading.

USE THIS FOR: Assessing if options are cheap/expensive, finding vol trading opportunities, understanding term structure, and analyzing put/call skew.

METRICS:
- stats: Comprehensive vol snapshot including current IV, RV, IV percentile, highs/lows. Best starting point.
- rank: IV Rank over time - where current IV sits vs historical range (0-100%). High rank = expensive options.
- realized: Historical/realized vol vs implied vol over time. IV > RV = options overpriced.
- term_structure: IV per expiration date. Upward slope = normal, inverted = fear/event expected.
- interpolated: Interpolated IV when exact expiry unavailable. Smooths the vol surface.
- historical_skew: Risk reversal skew (put vol - call vol) at specific delta. Shows directional fear.

KEY CONCEPTS:
- IV Rank > 50%: Options relatively expensive historically
- IV > RV: Market pricing more vol than realized (premium seller opportunity)
- Inverted term structure: Near-term fear (earnings, events)
- Negative skew: Puts more expensive (downside protection demand)

TRADING SIGNALS:
- Low IV rank + catalyst coming = buy vol
- High IV rank + no catalyst = sell vol
- IV >> RV persistently = systematic overpricing""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "metric": {"type": "string", "default": "stats", "enum": ["stats", "rank", "realized", "term_structure", "interpolated", "historical_skew"], "description": "Volatility metric type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "timeframe": {"type": "string", "default": "1Y", "description": "Historical range: YTD, 1W, 1M, 2M, 1Y (for rank, realized)"},
                    "timespan": {"type": "string", "description": "Alternative range format: 1y, 6m, 3m, 1m, 1w (for rank)"},
                    "expiry": {"type": "string", "description": "Expiration date YYYY-MM-DD (required for historical_skew)"},
                    "delta": {"type": "string", "description": "Delta level: 0.25 or 0.10 (required for historical_skew)"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_option_chain(self) -> MCPTool:
        return MCPTool(
            name="uw_option_chain",
            description="""Retrieves option chain data including contracts, ATM options, expirations, and volume/OI breakdowns.

USE THIS FOR: Finding available strikes/expirations, getting ATM option prices, analyzing open interest distribution, and identifying volume vs OI anomalies.

VIEWS:
- contracts: Full list of option contracts with prices, volume, OI, Greeks. Use filters to narrow.
- chains: All option symbols for the ticker (for building full option chain view).
- atm: At-the-money contracts for specified expirations. Quick ATM pricing.
- expirations: List of available expiration dates with total OI/volume per expiry.
- volume_oi: Volume and open interest breakdown per expiration.

RETURNS: option_symbol, strike, expiry, last_price, bid, ask, volume, open_interest, implied_volatility, Greeks (when available).

USEFUL FILTERS:
- vol_greater_oi=true: Contracts with unusual activity (volume exceeds open interest)
- exclude_zero_oi_chains=true: Only active contracts with existing positions
- maybe_otm_only=true: Out-of-the-money contracts only
- expiry: Focus on a specific expiration date""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "view": {"type": "string", "default": "contracts", "enum": ["contracts", "chains", "atm", "expirations", "volume_oi"], "description": "Data view type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "expirations": {"type": "array", "items": {"type": "string"}, "description": "Array of expiry dates YYYY-MM-DD (required for atm view)"},
                    "expiry": {"type": "string", "description": "Filter by single expiration date YYYY-MM-DD"},
                    "option_type": {"type": "string", "enum": ["call", "put"], "description": "Filter by call or put"},
                    "exclude_zero_dte": {"type": "boolean", "default": False, "description": "Exclude same-day expiring options"},
                    "exclude_zero_oi_chains": {"type": "boolean", "default": False, "description": "Exclude contracts with no open interest"},
                    "exclude_zero_vol_chains": {"type": "boolean", "default": False, "description": "Exclude contracts with no volume today"},
                    "maybe_otm_only": {"type": "boolean", "default": False, "description": "Only out-of-the-money contracts"},
                    "vol_greater_oi": {"type": "boolean", "default": False, "description": "Only contracts where today's volume > open interest (unusual activity)"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 500, "description": "Max results per page"},
                    "page": {"type": "integer", "default": 0, "minimum": 0, "description": "Page number for pagination"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_contract_data(self) -> MCPTool:
        return MCPTool(
            name="uw_contract_data",
            description="""Deep-dive into a specific option contract's trading activity, history, and volume profile.

USE THIS FOR: Analyzing individual high-interest contracts, tracking institutional accumulation in specific strikes, understanding intraday price action, and building volume-at-price profiles.

CONTRACT ID FORMAT: SYMBOL + YYMMDD + C/P + STRIKE*1000
Example: TSLA230526P00167500 = TSLA May 26 2023 $167.50 Put

VIEWS:
- flow: Recent trades (last 50) with premium, size, side, Greeks, and timestamps. See who's buying/selling.
- historic: Daily OHLCV history for the contract. Track how premium evolved over time.
- intraday: 1-minute candles for the contract on a specific day. Useful for timing analysis.
- volume_profile: Volume breakdown by fill price. Shows where most contracts traded (support/resistance).

RETURNS:
- flow: trade details with delta, gamma, vega, theta at time of trade
- historic: open, high, low, close, volume, OI, IV per day
- intraday: minute bars with bid/ask/mid side volume breakdowns
- volume_profile: volume per price level with sweep/floor/cross breakdowns""",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {"type": "string", "description": "Option contract in ISO format (e.g., AAPL240119C00190000 for AAPL Jan 19 2024 $190 Call)"},
                    "view": {"type": "string", "default": "flow", "enum": ["flow", "historic", "intraday", "volume_profile"], "description": "Data view type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "description": "Number of records to return"},
                    "min_premium": {"type": "integer", "minimum": 0, "description": "Minimum trade premium filter (flow view only)"},
                    "side": {"type": "string", "default": "ALL", "enum": ["ALL", "ASK", "BID", "MID"], "description": "Filter by trade side (flow view only)"},
                },
                "required": ["contract_id"],
                "additionalProperties": False
            }
        )
    
    def _tool_oi_change(self) -> MCPTool:
        return MCPTool(
            name="uw_oi_change",
            description="""Tracks open interest changes to identify new position building or unwinding.

USE THIS FOR: Finding contracts where large positions are being opened/closed, confirming flow signals with OI changes, and spotting institutional accumulation.

KEY CONCEPTS:
- Rising OI + Rising Price = New longs (bullish conviction)
- Rising OI + Falling Price = New shorts (bearish conviction)
- Falling OI + Rising Price = Short covering (less bearish)
- Falling OI + Falling Price = Long liquidation (less bullish)

RETURNS: For each contract - current OI, previous OI, OI change (absolute and %), average price, last fill, volume, and total premium.

MODES:
- Without ticker: Market-wide OI changes (excludes ETFs/Indexes by default). Find the biggest moves across all stocks.
- With ticker: OI changes for all contracts on that ticker. See where positions are building.

ANALYSIS TIPS:
- Large OI increase + large premium = institutional conviction
- OI change >> volume = position rollover or assignment
- Sort desc for biggest absolute changes""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker. Omit for market-wide OI changes (excludes ETF/Index)"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200, "description": "Number of results"},
                    "order": {"type": "string", "default": "desc", "enum": ["desc", "asc"], "description": "Sort by OI change (desc=largest first)"},
                    "page": {"type": "integer", "default": 0, "minimum": 0, "description": "Page number for pagination"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_net_flow_expiry(self) -> MCPTool:
        return MCPTool(
            name="uw_net_flow_expiry",
            description="""Market-wide net premium flow broken down by security type, moneyness, and expiration category.

USE THIS FOR: Understanding broad market positioning, 0DTE vs weekly flow dynamics, equity vs index/ETF sentiment, and ITM vs OTM speculative activity.

FILTERS:
- tide_type: What's driving the flow?
  - equity_only: Single stocks (remove ETF/index noise)
  - etf_only: ETF flows (sector bets, hedging)
  - index_only: SPX/NDX (often hedging/institutional)
  
- moneyness: Where on the chain?
  - itm: In-the-money (higher delta, stock replacement)
  - atm: At-the-money (gamma maximized)
  - otm: Out-of-the-money (leverage/lottery tickets)
  
- expiration: When does it expire?
  - zero_dte: Same-day expiration (gambling/scalping)
  - weekly: This week's expiration

RETURNS: Net call premium, net put premium, call/put volume, grouped by the filter combinations. Positive net premium = buying, negative = selling.

BUILD CHARTS: Use to create Zero-DTE dashboards, equity vs index sentiment gauges, and OTM speculation monitors.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "tide_type": {"type": "array", "items": {"type": "string", "enum": ["all", "equity_only", "etf_only", "index_only"]}, "default": ["all"], "description": "Filter by security type"},
                    "moneyness": {"type": "array", "items": {"type": "string", "enum": ["all", "itm", "otm", "atm"]}, "default": ["all"], "description": "Filter by moneyness"},
                    "expiration": {"type": "array", "items": {"type": "string", "enum": ["weekly", "zero_dte"]}, "default": ["weekly", "zero_dte"], "description": "Filter by expiration category"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_sentiment(self) -> MCPTool:
        return MCPTool(
            name="uw_sentiment",
            description="""Returns options-based sentiment indicators: NOPE (Net Options Pricing Effect) and Max Pain.

USE THIS FOR: Predicting short-term price direction based on options positioning, finding expiration-day price targets, and understanding market maker hedging pressure.

METRICS:

NOPE (Net Options Pricing Effect):
- Measures intraday net delta from options trading
- Assumes market makers take the short side and hedge dynamically
- Positive NOPE = net call buying = expected upward pressure
- Negative NOPE = net put buying = expected downward pressure
- Formula: (Call Delta - Put Delta) / Stock Volume
- Best used on liquid tickers (SPY, QQQ, AAPL, TSLA)
- Per-minute readings show intraday sentiment shifts

MAX PAIN:
- Strike price where option holders lose the most money at expiration
- Theory: Market makers profit by pinning price to max pain
- Works best for:
  - Weekly options on high OI tickers
  - OpEx Fridays (monthly expiration)
  - When no major catalysts expected
- Less reliable during earnings, news events, or strong trends

RETURNS: Per-minute NOPE values or max pain levels per expiration.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "metric": {"type": "string", "default": "nope", "enum": ["nope", "max_pain"], "description": "Sentiment indicator type"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    def _tool_hottest_contracts(self) -> MCPTool:
        return MCPTool(
            name="uw_hottest_contracts",
            description="""THE TOOL FOR "TOP BY PREMIUM/VOLUME" QUERIES. Server-side sorted screener for option contracts.

USE THIS FOR: "Top 20 by premium", "highest volume contracts", "most active options today" — any query requiring sorted results by a metric. This is the ONLY options tool that supports server-side sorting.

NOTE: Contracts with volume < 200 are excluded from results.

SORTING (use order + order_direction):
- order=premium: Top contracts by total premium (DEFAULT for "top by premium" queries)
- order=volume: Most actively traded contracts
- order=trades: Most transaction count
- order=floor_volume: Highest institutional floor trade volume
- order=iv: Highest implied volatility
- order=open_interest: Largest open positions

KEY FILTERS:
- vol_greater_oi=true: Unusual activity - today's volume exceeds total open interest
- is_otm=true: Only out-of-the-money (speculative plays)
- type: Filter for calls or puts only
- min_premium: Minimum premium threshold (e.g., '50000' for $50K+)
- min_dte/max_dte: Expiration range (0 for 0DTE, 30 for monthly)

SECTORS: Basic Materials, Communication Services, Consumer Cyclical, Consumer Defensive, Energy, Financial Services, Healthcare, Industrials, Real Estate, Technology, Utilities

RETURNS: Full contract details including symbol, strike, expiry, prices, volume breakdown, OI, Greeks, premium, multileg volume, sweep volume.

EXAMPLE QUERIES:
- "Top 20 by premium": order=premium, order_direction=desc, limit=20
- "Highest volume 0DTE calls": max_dte=0, type=call, order=volume
- "Most active tech options": sectors=['Technology'], order=volume""",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                    "ticker": {"type": "string", "description": "Comma-separated tickers to filter (e.g., 'AAPL,TSLA,NVDA')"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 250, "description": "Results per page"},
                    "page": {"type": "integer", "default": 0, "minimum": 0, "description": "Page number"},
                    "is_otm": {"type": "boolean", "description": "Only out-of-the-money contracts"},
                    "vol_greater_oi": {"type": "boolean", "description": "Only unusual activity (volume > open interest)"},
                    "type": {"type": "string", "enum": ["call", "put"], "description": "Filter by option type"},
                    "issue_types": {"type": "array", "items": {"type": "string"}, "description": "Security types: Common Stock, ETF, Index, ADR"},
                    "sectors": {"type": "array", "items": {"type": "string"}, "description": "Filter by sector"},
                    "expiry_dates": {"type": "array", "items": {"type": "string"}, "description": "Specific expiration dates YYYY-MM-DD"},
                    "order": {"type": "string", "default": "volume", "description": "Sort field: volume, premium, dte, open_interest, trades, iv, etc."},
                    "order_direction": {"type": "string", "default": "desc", "enum": ["desc", "asc"], "description": "Sort direction"},
                    "min_volume": {"type": "integer", "minimum": 1, "description": "Minimum contract volume"},
                    "max_volume": {"type": "integer", "description": "Maximum contract volume"},
                    "min_premium": {"type": "string", "description": "Minimum total premium (e.g., '50000')"},
                    "max_premium": {"type": "string", "description": "Maximum total premium"},
                    "min_dte": {"type": "integer", "minimum": 0, "description": "Minimum days to expiration"},
                    "max_dte": {"type": "integer", "description": "Maximum days to expiration"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_options_volume(self) -> MCPTool:
        return MCPTool(
            name="uw_options_volume",
            description="""Returns total options volume and premium for a ticker or market-wide overview.

USE THIS FOR: Building market state dashboards, tracking total market activity, comparing call vs put volume/premium ratios, and historical volume analysis.

MODES:
- With ticker: Daily options volume/premium history for that stock
- Without ticker: Market-wide totals (all options traded)

RETURNS:
- call_volume: Total call contracts traded
- put_volume: Total put contracts traded  
- call_premium: Sum of all call trade premiums ($)
- put_premium: Sum of all put trade premiums ($)
- date: Trading date

ANALYSIS:
- Call/Put Volume Ratio > 1: More call activity (often bullish)
- Call/Put Premium Ratio: Better sentiment gauge (weights by $)
- Compare to historical averages for context
- Spikes in put premium often signal hedging/fear

Use limit > 1 to get historical time series for trend analysis.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker. Omit for market-wide totals."},
                    "limit": {"type": "integer", "default": 1, "minimum": 1, "maximum": 500, "description": "Number of days of history (1 = just today)"},
                },
                "additionalProperties": False
            }
        )
    
    def _tool_greeks(self) -> MCPTool:
        return MCPTool(
            name="uw_greeks",
            description="""Returns option Greeks (delta, gamma, theta, vega, rho) for every strike at a specific expiration.

USE THIS FOR: Building volatility surfaces, analyzing Greek profiles across strikes, finding gamma walls, and options pricing analysis.

RETURNS per strike:
- delta: Rate of change vs underlying price (-1 to +1 for puts/calls)
- gamma: Rate of change of delta (acceleration, highest ATM)
- theta: Time decay per day (negative, increases near expiry)
- vega: Sensitivity to IV changes (highest ATM)
- rho: Sensitivity to interest rates
- implied_volatility: Market's expected volatility

ANALYSIS TIPS:
- High gamma strikes = potential pin/magnet points
- Gamma peaks at ATM, falls off at wings
- Theta accelerates in final weeks
- Compare IV across strikes for skew analysis
- Use with uw_gex for full market maker exposure picture

Requires both ticker and expiry parameters. Get available expirations first using uw_option_chain with view='expirations'.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "expiry": {"type": "string", "description": "Expiration date YYYY-MM-DD (required)"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                },
                "required": ["ticker", "expiry"],
                "additionalProperties": False
            }
        )
    
    def _tool_option_price_levels(self) -> MCPTool:
        return MCPTool(
            name="uw_option_price_levels",
            description="""Maps options volume to the underlying stock's price levels to show support/resistance from options activity.

USE THIS FOR: Identifying price levels with heavy options activity, finding potential support/resistance based on hedging flows, and understanding where institutions are positioned relative to stock price.

HOW IT WORKS:
- Groups option trades by the stock's price at time of execution
- Shows call vs put volume at each price level
- Heavy call volume at a price = potential support (buying interest)
- Heavy put volume at a price = potential resistance (selling interest)

RETURNS per price level:
- price: Stock price level
- call_volume: Call contracts traded when stock was at this price
- put_volume: Put contracts traded when stock was at this price
- total_volume: Combined volume

USE WITH CHARTS:
- Overlay on stock price chart as volume profile
- Identify clusters of activity
- Find price levels where sentiment shifted (call to put or vice versa)
- Compare to traditional volume profile for confirmation

Best used on active trading days with significant options volume.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "date": {"type": "string", "description": "Trading date YYYY-MM-DD (defaults to last trading day)"},
                },
                "required": ["ticker"],
                "additionalProperties": False
            }
        )
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute a tool by name."""
        try:
            arguments = arguments or {}
            
            handlers = {
                "uw_flow_alerts": self._handle_flow_alerts,
                "uw_greek_flow": self._handle_greek_flow,
                "uw_gex": self._handle_gex,
                "uw_flow_summary": self._handle_flow_summary,
                "uw_volatility": self._handle_volatility,
                "uw_option_chain": self._handle_option_chain,
                "uw_contract_data": self._handle_contract_data,
                "uw_oi_change": self._handle_oi_change,
                "uw_net_flow_expiry": self._handle_net_flow_expiry,
                "uw_sentiment": self._handle_sentiment,
                "uw_hottest_contracts": self._handle_hottest_contracts,
                "uw_options_volume": self._handle_options_volume,
                "uw_greeks": self._handle_greeks,
                "uw_option_price_levels": self._handle_option_price_levels,
                "get_fields": self._handle_get_fields,  # Generic dataset fetch for data workspace
            }
            
            handler = handlers.get(name)
            if not handler:
                return self._error_result(f"Unknown tool: {name}")
            
            result = await handler(arguments)
            # Canvas/workspace can explicitly request raw dataset JSON.
            if name == "get_fields" and arguments.get("_bh_raw"):
                return self._raw_success_result(result)
            return self._success_result(result, label=name)
            
        except ValueError as e:
            return self._error_result(str(e), "invalid_parameters")
        except Exception as e:
            logger.error(f"Error in {name}: {e}", exc_info=True)
            return self._error_result(str(e), "execution_error")
    
    def _success_result(self, data: Any, label: str = "uw_options") -> CallToolResult:
        from core.agents.binomial_hash import bh_ingest
        raw = json.dumps(data, default=str)
        text = bh_ingest(raw, label)
        return CallToolResult(
            content=[{"type": "text", "text": text}],
            isError=False
        )
    
    def _raw_success_result(self, data: Any) -> CallToolResult:
        """Return raw JSON without BinomialHash compression (for canvas data workspace)."""
        return CallToolResult(
            content=[{"type": "text", "text": json.dumps(data, default=str)}],
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
        Accepts 'datasets' (list) or 'dataset' (string), plus 'params' and optional identifier.
        
        Uses identifier_param from dataset catalog to correctly map the symbol/ticker
        to the appropriate parameter name (ticker, id, flow_group, sector, etc.)
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
            args.get("options_ticker") or
            args.get("id") or
            args.get("flow_group") or
            args.get("sector")
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
        return await self.data_fetcher.fetch_dataset(dataset, params)
    
    # --- Handler implementations ---
    
    async def _handle_flow_alerts(self, args: Dict) -> Dict:
        params = {k: v for k, v in args.items() if v is not None}
        if "ticker" in params:
            params["ticker_symbol"] = params.pop("ticker")
        if "issue_types" in params:
            params["issue_types[]"] = params.pop("issue_types")
        if "rule_name" in params:
            params["rule_name[]"] = params.pop("rule_name")
        if "sectors" in params:
            params["sectors[]"] = params.pop("sectors")
        return await self._fetch("flow-alerts", params)
    
    async def _handle_greek_flow(self, args: Dict) -> Dict:
        ticker = args.get("ticker")
        flow_group = args.get("flow_group")
        expiry = args.get("expiry")
        date = args.get("date")
        
        if not ticker and not flow_group:
            return {"error": "Either 'ticker' or 'flow_group' is required"}
        
        params = {"date": date} if date else {}
        
        if ticker:
            if expiry:
                params["expiry"] = expiry
                params["ticker"] = ticker
                return await self._fetch("stock-greek-flow-by-expiry", params)
            params["ticker"] = ticker
            return await self._fetch("stock-greek-flow", params)
        else:
            if expiry:
                params["expiry"] = expiry
                params["flow_group"] = flow_group
                return await self._fetch("group-greek-flow-by-expiry", params)
            params["flow_group"] = flow_group
            return await self._fetch("group-greek-flow", params)
    
    async def _handle_gex(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        view = args.get("view", "summary")
        params = {"ticker": ticker}
        
        for k in ["date", "timeframe", "expiry", "min_strike", "max_strike", 
                  "min_dte", "max_dte", "limit", "page"]:
            if args.get(k) is not None:
                params[k] = args[k]
        
        if args.get("expirations"):
            params["expirations[]"] = args["expirations"]
        
        dataset_map = {
            "summary": "stock-greek-exposure",
            "by_strike": "stock-greek-exposure-by-strike",
            "by_expiry": "stock-greek-exposure-by-expiry",
            "by_strike_expiry": "stock-greek-exposure-by-strike-expiry",
            "spot_strike": "stock-spot-exposures-strike",
            "spot_expiry_strike": "stock-spot-exposures-expiry-strike",
        }
        return await self._fetch(dataset_map[view], params)
    
    async def _handle_flow_summary(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        view = args.get("view", "expiry")
        params = {"ticker": ticker}
        
        if args.get("date"):
            params["date"] = args["date"]
        if view == "strike_intraday" and args.get("filter"):
            params["filter"] = args["filter"]
        if view == "recent":
            if args.get("min_premium"):
                params["min_premium"] = args["min_premium"]
            if args.get("side"):
                params["side"] = args["side"]
        
        dataset_map = {
            "expiry": "stock-flow-per-expiry",
            "strike": "stock-flow-per-strike",
            "strike_intraday": "stock-flow-per-strike-intraday",
            "recent": "stock-flow-recent",
        }
        return await self._fetch(dataset_map[view], params)
    
    async def _handle_volatility(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        metric = args.get("metric", "stats")
        params = {"ticker": ticker}
        
        for k in ["date", "timeframe", "timespan", "expiry", "delta"]:
            if args.get(k):
                params[k] = args[k]
        
        dataset_map = {
            "stats": "stock-volatility-stats",
            "rank": "stock-iv-rank",
            "realized": "stock-volatility-realized",
            "term_structure": "stock-volatility-term-structure",
            "interpolated": "stock-interpolated-iv",
            "historical_skew": "stock-historical-risk-reversal-skew",
            "skew": "stock-historical-risk-reversal-skew",  # Alias for historical_skew
        }
        
        if metric not in dataset_map:
            return {"error": f"Unknown volatility metric: {metric}. Valid: {list(dataset_map.keys())}"}
        
        return await self._fetch(dataset_map[metric], params)
    
    async def _handle_option_chain(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        view = args.get("view", "contracts")
        params = {"ticker": ticker}
        
        for k in ["date", "expiry", "option_type", "limit", "page"]:
            if args.get(k) is not None:
                params[k] = args[k]
        
        for k in ["exclude_zero_dte", "exclude_zero_oi_chains", "exclude_zero_vol_chains", 
                  "maybe_otm_only", "vol_greater_oi"]:
            if args.get(k):
                params[k] = args[k]
        
        if args.get("expirations"):
            params["expirations[]"] = args["expirations"]
        
        dataset_map = {
            "contracts": "stock-option-contracts",
            "chains": "stock-option-chains",
            "atm": "stock-atm-chains",
            "expirations": "stock-expiry-breakdown",
            "volume_oi": "stock-option-volume-oi-expiry",
        }
        return await self._fetch(dataset_map[view], params)
    
    async def _handle_contract_data(self, args: Dict) -> Dict:
        contract_id = args["contract_id"]
        view = args.get("view", "flow")
        params = {"id": contract_id}
        
        for k in ["date", "limit"]:
            if args.get(k) is not None:
                params[k] = args[k]
        
        if view == "flow":
            if args.get("min_premium"):
                params["min_premium"] = args["min_premium"]
            if args.get("side"):
                params["side"] = args["side"]
        
        dataset_map = {
            "flow": "option-contract-flow",
            "historic": "option-contract-historic",
            "intraday": "option-contract-intraday",
            "volume_profile": "option-contract-volume-profile",
        }
        return await self._fetch(dataset_map[view], params)
    
    async def _handle_oi_change(self, args: Dict) -> Dict:
        ticker = args.get("ticker")
        params = {}
        
        for k in ["date", "limit", "order", "page"]:
            if args.get(k) is not None:
                params[k] = args[k]
        
        if ticker:
            params["ticker"] = ticker
            return await self._fetch("stock-oi-change", params)
        return await self._fetch("market-oi-change", params)
    
    async def _handle_net_flow_expiry(self, args: Dict) -> Dict:
        params = {}
        if args.get("date"):
            params["date"] = args["date"]
        if args.get("tide_type"):
            params["tide_type[]"] = args["tide_type"]
        if args.get("moneyness"):
            params["moneyness[]"] = args["moneyness"]
        if args.get("expiration"):
            params["expiration[]"] = args["expiration"]
        return await self._fetch("net-flow-expiry", params)
    
    async def _handle_sentiment(self, args: Dict) -> Dict:
        ticker = args["ticker"]
        metric = args.get("metric", "nope")
        params = {"ticker": ticker}
        if args.get("date"):
            params["date"] = args["date"]
        
        dataset_map = {"nope": "stock-nope", "max_pain": "stock-max-pain"}
        return await self._fetch(dataset_map[metric], params)
    
    async def _handle_hottest_contracts(self, args: Dict) -> Dict:
        params = {k: v for k, v in args.items() if v is not None}
        if "ticker" in params:
            params["ticker_symbol"] = params.pop("ticker")
        if "issue_types" in params:
            params["issue_types[]"] = params.pop("issue_types")
        if "sectors" in params:
            params["sectors[]"] = params.pop("sectors")
        if "expiry_dates" in params:
            params["expiry_dates[]"] = params.pop("expiry_dates")
        return await self._fetch("screener-option-contracts", params)
    
    async def _handle_options_volume(self, args: Dict) -> Dict:
        ticker = args.get("ticker")
        params = {"limit": args.get("limit", 1)}
        
        if ticker:
            params["ticker"] = ticker
            return await self._fetch("stock-options-volume", params)
        return await self._fetch("market-total-options-volume", params)
    
    async def _handle_greeks(self, args: Dict) -> Dict:
        return await self._fetch("stock-greeks", {
            "ticker": args["ticker"],
            "expiry": args["expiry"],
            "date": args.get("date"),
        })
    
    async def _handle_option_price_levels(self, args: Dict) -> Dict:
        return await self._fetch("stock-option-price-levels", {
            "ticker": args["ticker"],
            "date": args.get("date"),
        })

 
