"""
Quiver Quant MCP server.

Grouped, UW-style tools backed by a small endpoint registry.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from agents.mcp import MCPServer
from agents.mcp.server import CallToolResult, MCPTool

from .quiver_fetcher import QuiverDataFetcher, QuiverTierError, normalize_quiver_payload
from .quiver_registry import DATASET_REGISTRY

logger = logging.getLogger(__name__)


class QuiverQuantServer(MCPServer):
    """Grouped MCP interface for Quiver Quant datasets."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._name = "QuiverQuantServer"
        self.use_structured_content = False

        api_key = api_key or os.getenv("QUIVER_API_KEY")
        if not api_key:
            raise ValueError("QUIVER_API_KEY not provided")

        self.data_fetcher = QuiverDataFetcher(api_key)

    @property
    def name(self) -> str:
        return self._name

    async def connect(self):
        await self.data_fetcher.connect()
        logger.info("QuiverQuantServer connected")

    async def cleanup(self):
        await self.data_fetcher.cleanup()
        logger.info("QuiverQuantServer cleaned up")

    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        return self._get_tools()

    async def list_prompts(self, run_context, agent) -> List[str]:
        return []

    async def get_prompt(self, name: str, arguments: Dict[str, Any], run_context, agent) -> str:
        raise NotImplementedError(f"No prompts available for {self.name}")

    def _get_tools(self) -> List[MCPTool]:
        return [
            MCPTool(
                name="get_congress_trading",
                description="""Primary Quiver tool for congressional trading and politician data.

Use this for:
- recent House/Senate/Congress trades
- per-ticker congressional trade history
- bulk Congress trade dumps
- politician directory and profile-like datasets
- Congress holdings if your Quiver tier includes it

Routing behavior:
- dataset=trades uses congresstrading/senatetrading/housetrading
- dataset=politicians uses the Congress politicians endpoints
- dataset=holdings uses congressholdings
- if ticker is provided and no mode is given, the server automatically prefers historical mode when supported

Key filters:
- chamber narrows to senate or house
- politician or bioguide_id filters specific members
- normalized and nonstock mirror Quiver's raw Congress filters
- page/page_size are passed through when the endpoint supports them

Use this instead of the mobile-specific Congress tool unless you explicitly need Quiver mobile endpoints.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "chamber": {"type": "string", "enum": ["all", "senate", "house"], "default": "all"},
                        "dataset": {"type": "string", "enum": ["trades", "politicians", "holdings"], "default": "trades"},
                        "mode": {"type": "string", "enum": ["live", "historical", "bulk"]},
                        "politician": {"type": "string"},
                        "bioguide_id": {"type": "string"},
                        "date": {"type": "string"},
                        "nonstock": {"type": "boolean"},
                        "normalized": {"type": "boolean"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_political_activity",
                description="""Quiver political-activity tool for lobbying, donor, legislation, bill-summary, and political-beta datasets.

Use this for:
- lobbying spend by ticker or recent feed
- corporate donor records
- recent legislation and bill summaries
- political beta time series

Routing behavior:
- dataset=lobbying selects live or ticker-specific lobbying
- dataset=donors selects corporate donors bulk or ticker history
- dataset=legislation and dataset=bills use enterprise-tier live feeds
- dataset=political_beta uses the political beta live/historical/bulk family

Important notes:
- politician is mapped to bioguide_id where Quiver expects it
- election_cycle is mapped to cycle
- ticker with no explicit mode defaults to historical when the dataset supports ticker history""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "dataset": {"type": "string", "enum": ["lobbying", "donors", "legislation", "bills", "political_beta"], "default": "lobbying"},
                        "mode": {"type": "string", "enum": ["live", "historical", "bulk"]},
                        "query": {"type": "string"},
                        "queryTicker": {"type": "string"},
                        "politician": {"type": "string"},
                        "election_cycle": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_government_contracts",
                description="""Quiver government-contracts tool.

Use this for:
- recent federal contract awards
- contract modification-inclusive feeds
- per-ticker historical government contract history

Routing behavior:
- include_modifications=false uses govcontracts
- include_modifications=true uses govcontractsall
- ticker with no mode defaults to historical

Prefer this tool over mobile gov-contract views unless you explicitly need mobile-formatted data.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "mode": {"type": "string", "enum": ["live", "historical"]},
                        "include_modifications": {"type": "boolean", "default": False},
                        "date": {"type": "string"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_quiver_insider_trading",
                description="""Quiver insider-trading feed.

Use this for:
- recent insider transaction screening
- filtering insider trades by ticker, date, or uploaded date
- quickly checking whether Quiver has recent Form 4 activity for a name

Notes:
- Quiver exposes insiders only as a live feed, not a dedicated historical ticker endpoint in the main beta catalog
- page and page_size are forwarded directly
- limit_codes mirrors Quiver's own filter flag""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "date": {"type": "string"},
                        "uploaded": {"type": "string"},
                        "limit_codes": {"type": "boolean"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_institutional_holdings",
                description="""Quiver institutional-holdings tool for SEC 13F and ETF ownership data.

Use this for:
- 13F holdings lookups
- quarter-over-quarter 13F position changes
- ETF holdings by ETF ticker or constituent ticker

Routing behavior:
- dataset=holdings uses sec13f
- dataset=changes uses sec13fchanges
- dataset=etf uses etfholdings

Important filters:
- owner, period, date, today for 13F views
- most_recent and show_new_funds for sec13fchanges
- etf for ETF holdings lookups""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string", "enum": ["holdings", "changes", "etf"], "default": "holdings"},
                        "ticker": {"type": "string"},
                        "owner": {"type": "string"},
                        "date": {"type": "string"},
                        "period": {"type": "string"},
                        "today": {"type": "boolean"},
                        "most_recent": {"type": "boolean"},
                        "show_new_funds": {"type": "boolean"},
                        "etf": {"type": "string"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_social_sentiment",
                description="""Quiver social and community-sentiment tool.

Use this for:
- WallStreetBets mention counts and ticker history
- SPAC and Twitter signal series
- raw comments feeds across WSB, crypto, SPACs, and Reddit
- the WSB greed index bulk dataset

Routing behavior:
- source + detail_level choose between summary datasets and raw comments feeds
- ticker with no explicit mode defaults to historical when the selected dataset has ticker history
- source=wsb with detail_level=summary supports live, ticker-history, and the all-tickers historical feed

Important notes:
- comments_full variants usually require higher-tier access
- Quiver's social endpoints do not expose a perfectly uniform query surface, so unsupported filters are dropped rather than forced
- use get_quiver_mobile_data for 24h hottest/count mobile endpoints rather than this tool""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "enum": ["wsb", "spacs", "twitter", "crypto", "reddit"], "default": "wsb"},
                        "mode": {"type": "string", "enum": ["live", "historical", "bulk"]},
                        "detail_level": {"type": "string", "enum": ["summary", "comments", "comments_full"], "default": "summary"},
                        "ticker": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "freq": {"type": "string"},
                        "ignore_common": {"type": "boolean"},
                        "extra_words": {"type": "boolean"},
                        "figi": {"type": "boolean"},
                        "utc": {"type": "boolean"},
                        "count_all": {"type": "boolean"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_alternative_signals",
                description="""Quiver alternative-signals and market-anomaly tool.

Use this for:
- patents and patent-derived scores
- off-exchange / dark-pool short volume
- app ratings, flights, CNBC analyst/pick feeds
- event beta datasets

Routing behavior:
- signal selects the Quiver dataset family
- mode defaults to historical when ticker history exists and ticker is present
- signal=events_beta supports today and historical, not generic live

Important notes:
- off_exchange is one of the most useful low-noise live endpoints
- patents and flights can have sparse data by ticker, so empty results are not necessarily errors""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "signal": {
                            "type": "string",
                            "enum": ["patents", "patent_drift", "patent_momentum", "app_ratings", "off_exchange", "flights", "cnbc", "events_beta"],
                            "default": "patents",
                        },
                        "mode": {"type": "string", "enum": ["live", "historical", "today"]},
                        "ticker": {"type": "string"},
                        "date": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "latest": {"type": "boolean"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_quiver_strategies",
                description="""Quiver strategy holdings tool.

Use this for:
- current holdings for Quiver's frequent-rebalancing strategy set
- holdings for infrequently rebalancing strategies

Notes:
- this is usually enterprise-tier data
- rebalance_frequency switches between the two documented strategy holdings endpoints
- pass strategy if you want a specific strategy where Quiver supports that query parameter""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rebalance_frequency": {"type": "string", "enum": ["frequent", "infrequent"], "default": "frequent"},
                        "strategy": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_quiver_reference_data",
                description="""Quiver reference and lookup tool.

Use this for:
- company, coin, and fund lookup tables
- ticker metadata
- CNBC personalities
- ignored ticker lists
- RSS feed access

Use this when you need Quiver-native identifiers or reference tables before calling a more specific Quiver dataset.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string", "enum": ["companies", "coins", "funds", "tickerdata", "personalities", "ignoredtickers", "rss"], "default": "companies"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_quiver_mobile_data",
                description="""Direct access to Quiver's documented mobile GET endpoints.

Use this only when the standard grouped tools do not expose a mobile-only dataset you need, such as:
- 24h hottest/count feeds
- mobile Congress profile, trades, donors, portfolio, supporters, opponents
- mobile trending tickers, notifications, gov contracts, insider views
- mobile strategy performance and ticker payloads

Important notes:
- this tool is intentionally generic because Quiver's mobile surface is broad and heterogeneous
- choose the dataset explicitly; the server handles path parameters such as bioguide_id, strategy_name, ticker, and type
- prefer the higher-level grouped Quiver tools first when both surfaces expose similar data""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "enum": [
                                "13frecentfilings", "24hcryptocounts", "24hcryptohottest", "24hwsbcounts", "24hwsbhottest",
                                "cnbcbyperson", "cnbcgraphs", "congress_net_worth_rankings", "congress_politicians",
                                "congress_politician_profile", "congress_politician_donors", "congress_politician_legislation",
                                "congress_politician_opponents", "congress_politician_portfolio", "congress_politician_supporters",
                                "congress_politician_trades", "congress_traders_active", "currentmostpopulartickers",
                                "govcontracts", "insidertrading", "notifications", "repreturns", "repsentiment",
                                "senatereturns", "senatesentiment", "strategy_performance", "ticker", "toplobbying", "trendingtickers"
                            ]
                        },
                        "bioguide_id": {"type": "string"},
                        "strategy_name": {"type": "string"},
                        "ticker": {"type": "string"},
                        "type": {"type": "string"},
                        "analyst": {"type": "string"},
                        "active_only": {"type": "boolean"},
                        "bill_type": {"type": "string"},
                        "category": {"type": "string"},
                        "chamber": {"type": "string"},
                        "congress": {"type": "string"},
                        "cycle": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "donor_type": {"type": "string"},
                        "end_date": {"type": "string"},
                        "include_history": {"type": "boolean"},
                        "lookback_hours": {"type": "integer"},
                        "min_allocation": {"type": "number"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "party": {"type": "string"},
                        "sort_by": {"type": "string"},
                        "start_date": {"type": "string"},
                        "state": {"type": "string"},
                        "transaction_type": {"type": "string"},
                        "version": {"type": "string"},
                    },
                    "required": ["dataset"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="list_quiver_datasets",
                description="""Return the Quiver MCP dataset catalog.

Use this to inspect:
- every dataset known to the server
- supported modes and raw paths
- tier labels
- short summaries for discovery and debugging

This is the best tool to call when you want to confirm Quiver coverage before picking a more specific domain tool.""",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        try:
            handlers = {
                "get_congress_trading": self._handle_congress_trading,
                "get_political_activity": self._handle_political_activity,
                "get_government_contracts": self._handle_government_contracts,
                "get_quiver_insider_trading": self._handle_insider_trading,
                "get_institutional_holdings": self._handle_institutional_holdings,
                "get_social_sentiment": self._handle_social_sentiment,
                "get_alternative_signals": self._handle_alternative_signals,
                "get_quiver_strategies": self._handle_quiver_strategies,
                "get_quiver_reference_data": self._handle_quiver_reference_data,
                "get_quiver_mobile_data": self._handle_quiver_mobile_data,
                "list_quiver_datasets": self._handle_list_datasets,
            }
            handler = handlers.get(name)
            if not handler:
                return self._error_result(f"Unknown tool: {name}", "unknown_tool")

            result = await handler(arguments or {})
            return self._success_result(result, label=name)
        except QuiverTierError as exc:
            return self._error_result(str(exc), "tier_error")
        except ValueError as exc:
            return self._error_result(str(exc), "invalid_parameters")
        except Exception as exc:
            logger.error("Error in %s: %s", name, exc, exc_info=True)
            return self._error_result(str(exc), "execution_error")

    def _success_result(self, data: Any, label: str = "quiver") -> CallToolResult:
        from core.agents.binomial_hash import bh_ingest

        raw = json.dumps(data, default=str)
        text = bh_ingest(raw, label)
        return CallToolResult(content=[{"type": "text", "text": text}], isError=False)

    def _error_result(self, message: str, error_type: str = "error") -> CallToolResult:
        return CallToolResult(
            content=[{"type": "text", "text": json.dumps({"error": error_type, "message": message})}],
            isError=True,
        )

    async def _fetch(self, dataset_key: str, mode: str, args: Dict[str, Any]) -> Dict[str, Any]:
        entry = DATASET_REGISTRY[dataset_key]
        if mode not in entry["paths"]:
            raise ValueError(f"Dataset '{dataset_key}' does not support mode '{mode}'")

        path = entry["paths"][mode]
        path_param_names = re.findall(r"{([^}]+)}", path)
        path_values: Dict[str, Any] = {}
        for param_name in path_param_names:
            value = args.get(param_name)
            if value is None:
                raise ValueError(f"Dataset '{dataset_key}' requires path parameter '{param_name}' for mode '{mode}'")
            path_values[param_name] = value
        if path_values:
            path = path.format(**path_values)

        params = self._filter_params(args, entry.get("query_params", []), exclude=set(path_param_names))
        data = await self.data_fetcher.fetch(path, params=params)
        normalized_data = normalize_quiver_payload(dataset_key, data)
        if normalized_data is not data:
            logger.info(
                "Quiver normalization applied: dataset=%s rows=%s",
                dataset_key,
                len(normalized_data) if isinstance(normalized_data, list) else "n/a",
            )
        return {
            "dataset": dataset_key,
            "mode": mode,
            "path": path,
            "params": params,
            "data": normalized_data,
        }

    def _filter_params(self, args: Dict[str, Any], allowed: List[str], exclude: Optional[set[str]] = None) -> Dict[str, Any]:
        exclude = exclude or set()
        return {key: args.get(key) for key in allowed if key not in exclude and args.get(key) is not None}

    async def _handle_congress_trading(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = args.get("dataset", "trades")
        chamber = args.get("chamber", "all")

        if dataset == "politicians":
            dataset_key = "congress_politicians"
            mode = args.get("mode", "live")
        elif dataset == "holdings":
            dataset_key = "congressholdings"
            mode = "live"
        else:
            dataset_key = {
                "all": "congresstrading",
                "senate": "senatetrading",
                "house": "housetrading",
            }[chamber]
            mode = args.get("mode") or ("historical" if args.get("ticker") else "live")

        return await self._fetch(dataset_key, mode, args)

    async def _handle_political_activity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_map = {
            "lobbying": "lobbying",
            "donors": "corporatedonors",
            "legislation": "legislation",
            "bills": "bill_summaries",
            "political_beta": "politicalbeta",
        }
        dataset_key = dataset_map[args.get("dataset", "lobbying")]
        mode = args.get("mode") or ("historical" if args.get("ticker") and "historical" in DATASET_REGISTRY[dataset_key]["paths"] else "live")

        params = dict(args)
        politician = params.pop("politician", None)
        election_cycle = params.pop("election_cycle", None)
        if politician:
            params["bioguide_id"] = politician
        if election_cycle:
            params["cycle"] = election_cycle

        return await self._fetch(dataset_key, mode, params)

    async def _handle_government_contracts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = "govcontractsall" if args.get("include_modifications") else "govcontracts"
        mode = args.get("mode") or ("historical" if args.get("ticker") else "live")
        return await self._fetch(dataset_key, mode, args)

    async def _handle_insider_trading(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return await self._fetch("insiders", "live", args)

    async def _handle_institutional_holdings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = {
            "holdings": "sec13f",
            "changes": "sec13fchanges",
            "etf": "etfholdings",
        }[args.get("dataset", "holdings")]
        return await self._fetch(dataset_key, "live", args)

    async def _handle_social_sentiment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        source = args.get("source", "wsb")
        detail = args.get("detail_level", "summary")

        if source == "wsb" and detail == "summary":
            dataset_key = "wallstreetbets"
        elif source == "wsb" and detail == "comments":
            dataset_key = "wsbcomments"
        elif source == "wsb" and detail == "comments_full":
            dataset_key = "wsbcommentsfull"
        elif source == "spacs" and detail == "summary":
            dataset_key = "spacs"
        elif source == "twitter":
            dataset_key = "twitter"
        elif source == "crypto":
            dataset_key = "cryptocommentsfull" if detail == "comments_full" else "cryptocomments"
        elif source == "spacs" and detail == "comments":
            dataset_key = "spaccomments"
        elif source == "reddit":
            dataset_key = "redditcomments"
        elif source == "wsb" and args.get("mode") == "bulk":
            dataset_key = "wsbgreed"
        else:
            raise ValueError(f"Unsupported source/detail_level combination: {source}/{detail}")

        mode = args.get("mode") or ("historical" if args.get("ticker") and "historical" in DATASET_REGISTRY[dataset_key]["paths"] else "live")
        return await self._fetch(dataset_key, mode, args)

    async def _handle_alternative_signals(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = {
            "patents": "allpatents",
            "patent_drift": "patentdrift",
            "patent_momentum": "patentmomentum",
            "app_ratings": "appratings",
            "off_exchange": "offexchange",
            "flights": "flights",
            "cnbc": "cnbc",
            "events_beta": "eventsbeta",
        }[args.get("signal", "patents")]
        mode = args.get("mode") or ("historical" if args.get("ticker") and "historical" in DATASET_REGISTRY[dataset_key]["paths"] else "live")
        return await self._fetch(dataset_key, mode, args)

    async def _handle_quiver_strategies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = "strategies_holdings_infrequent" if args.get("rebalance_frequency") == "infrequent" else "strategies_holdings"
        return await self._fetch(dataset_key, "live", args)

    async def _handle_quiver_reference_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = args.get("dataset", "companies")
        return await self._fetch(dataset_key, "live", args)

    async def _handle_quiver_mobile_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset_key = {
            "13frecentfilings": "mobile_13frecentfilings",
            "24hcryptocounts": "mobile_24hcryptocounts",
            "24hcryptohottest": "mobile_24hcryptohottest",
            "24hwsbcounts": "mobile_24hwsbcounts",
            "24hwsbhottest": "mobile_24hwsbhottest",
            "cnbcbyperson": "mobile_cnbcbyperson",
            "cnbcgraphs": "mobile_cnbcgraphs",
            "congress_net_worth_rankings": "mobile_congress_net_worth_rankings",
            "congress_politicians": "mobile_congress_politicians",
            "congress_politician_profile": "mobile_congress_politician_profile",
            "congress_politician_donors": "mobile_congress_politician_donors",
            "congress_politician_legislation": "mobile_congress_politician_legislation",
            "congress_politician_opponents": "mobile_congress_politician_opponents",
            "congress_politician_portfolio": "mobile_congress_politician_portfolio",
            "congress_politician_supporters": "mobile_congress_politician_supporters",
            "congress_politician_trades": "mobile_congress_politician_trades",
            "congress_traders_active": "mobile_congress_traders_active",
            "currentmostpopulartickers": "mobile_currentmostpopulartickers",
            "govcontracts": "mobile_govcontracts",
            "insidertrading": "mobile_insidertrading",
            "notifications": "mobile_notifications",
            "repreturns": "mobile_repreturns",
            "repsentiment": "mobile_repsentiment",
            "senatereturns": "mobile_senatereturns",
            "senatesentiment": "mobile_senatesentiment",
            "strategy_performance": "mobile_strategy_performance",
            "ticker": "mobile_ticker",
            "toplobbying": "mobile_toplobbying",
            "trendingtickers": "mobile_trendingtickers",
        }[args["dataset"]]
        return await self._fetch(dataset_key, "live", args)

    async def _handle_list_datasets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "datasets": [
                {
                    "dataset": key,
                    "tier": value["tier"],
                    "summary": value.get("summary", ""),
                    "paths": sorted(value["paths"].keys()),
                }
                for key, value in sorted(DATASET_REGISTRY.items())
            ]
        }
