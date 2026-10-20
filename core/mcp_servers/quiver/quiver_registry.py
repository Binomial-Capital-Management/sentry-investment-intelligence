"""
Registry of Quiver Quant datasets exposed through the MCP server.

This keeps the endpoint catalog separate from routing logic so coverage can be
tested directly against the OpenAPI export.
"""

from __future__ import annotations

from typing import Any, Dict, Set


DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {
    "congresstrading": {
        "tier": "tier1",
        "summary": "Congressional trading feed across both chambers.",
        "paths": {"live": "/beta/live/congresstrading", "historical": "/beta/historical/congresstrading/{ticker}", "bulk": "/beta/bulk/congresstrading"},
        "query_params": ["bioguide_id", "date", "nonstock", "normalized", "page", "page_size", "representative", "ticker", "version", "analyst"],
    },
    "senatetrading": {
        "tier": "tier1",
        "summary": "Senate-only trading feed and ticker history.",
        "paths": {"live": "/beta/live/senatetrading", "historical": "/beta/historical/senatetrading/{ticker}"},
        "query_params": ["name", "options", "page", "page_size", "ticker"],
    },
    "housetrading": {
        "tier": "tier1",
        "summary": "House-only trading feed and ticker history.",
        "paths": {"live": "/beta/live/housetrading", "historical": "/beta/historical/housetrading/{ticker}"},
        "query_params": ["name", "options", "page", "page_size", "ticker"],
    },
    "congress_politicians": {
        "tier": "tier1",
        "summary": "Congress politician directory and trading stats.",
        "paths": {"live": "/beta/live/congress/politicians", "bulk": "/beta/bulk/congress/politicians"},
        "query_params": ["chamber", "include_candidates", "is_active", "page", "page_size", "party", "sort_by", "state", "volume_method"],
    },
    "congressholdings": {
        "tier": "enterprise",
        "summary": "Live portfolio holdings for Congress members.",
        "paths": {"live": "/beta/live/congressholdings"},
        "query_params": ["representative", "bioguide_id", "page", "page_size"],
    },
    "lobbying": {
        "tier": "tier1",
        "summary": "Corporate lobbying activity and ticker-specific history.",
        "paths": {"live": "/beta/live/lobbying", "historical": "/beta/historical/lobbying/{ticker}"},
        "query_params": ["all", "date_from", "date_to", "page", "page_size", "query", "queryTicker"],
    },
    "corporatedonors": {
        "tier": "tier1",
        "summary": "Corporate political donor records.",
        "paths": {"historical": "/beta/historical/corporatedonors/{ticker}", "bulk": "/beta/bulk/corporatedonors"},
        "query_params": ["bioguide_id", "cycle", "page", "page_size", "ticker", "transaction_tp"],
    },
    "legislation": {
        "tier": "enterprise",
        "summary": "Recent legislation mentioning companies or themes.",
        "paths": {"live": "/beta/live/legislation"},
        "query_params": ["page", "page_size", "query"],
    },
    "bill_summaries": {
        "tier": "enterprise",
        "summary": "Bill summaries with search and summary truncation.",
        "paths": {"live": "/beta/live/bill_summaries"},
        "query_params": ["page", "page_size", "query", "summary_limit"],
    },
    "politicalbeta": {
        "tier": "tier2",
        "summary": "Political beta scores for companies.",
        "paths": {"live": "/beta/live/politicalbeta", "historical": "/beta/historical/politicalbeta/{ticker}", "bulk": "/beta/bulk/politicalbeta"},
        "query_params": [],
    },
    "govcontracts": {
        "tier": "tier1",
        "summary": "Government contract awards without modifications.",
        "paths": {"live": "/beta/live/govcontracts", "historical": "/beta/historical/govcontracts/{ticker}"},
        "query_params": [],
    },
    "govcontractsall": {
        "tier": "tier1",
        "summary": "Government contracts including modifications and updates.",
        "paths": {"live": "/beta/live/govcontractsall", "historical": "/beta/historical/govcontractsall/{ticker}"},
        "query_params": ["date", "page", "page_size"],
    },
    "insiders": {
        "tier": "tier2",
        "summary": "Recent SEC Form 4 insider trading feed.",
        "paths": {"live": "/beta/live/insiders"},
        "query_params": ["date", "limit_codes", "page", "page_size", "ticker", "uploaded"],
    },
    "sec13f": {
        "tier": "tier2",
        "summary": "Live 13F holdings snapshots.",
        "paths": {"live": "/beta/live/sec13f"},
        "query_params": ["date", "owner", "page", "page_size", "period", "ticker", "today"],
    },
    "sec13fchanges": {
        "tier": "tier2",
        "summary": "13F position changes between filing periods.",
        "paths": {"live": "/beta/live/sec13fchanges"},
        "query_params": ["date", "mobile", "most_recent", "owner", "page", "page_size", "period", "show_new_funds", "ticker", "today"],
    },
    "etfholdings": {
        "tier": "tier2",
        "summary": "ETF holdings lookup by ETF or constituent ticker.",
        "paths": {"live": "/beta/live/etfholdings"},
        "query_params": ["etf", "ticker"],
    },
    "wallstreetbets": {
        "tier": "tier2",
        "summary": "WallStreetBets mention counts and ticker history.",
        "paths": {"live": "/beta/live/wallstreetbets", "historical": "/beta/historical/wallstreetbets/{ticker}", "bulk": "/beta/historical/wallstreetbets"},
        "query_params": ["count_all", "extra_words", "ignore_common", "today", "ticker"],
    },
    "spacs": {
        "tier": "tier2",
        "summary": "SPAC subreddit mention datasets.",
        "paths": {"live": "/beta/live/spacs", "historical": "/beta/historical/spacs/{ticker}"},
        "query_params": ["date_from", "date_to", "ticker"],
    },
    "twitter": {
        "tier": "tier2",
        "summary": "Corporate Twitter following changes.",
        "paths": {"live": "/beta/live/twitter", "historical": "/beta/historical/twitter/{ticker}"},
        "query_params": ["date"],
    },
    "wsbcomments": {
        "tier": "tier3",
        "summary": "Raw WallStreetBets comments feed.",
        "paths": {"live": "/beta/live/wsbcomments"},
        "query_params": ["date_from", "date_to", "extra_words", "figi", "freq", "ignore_common", "ticker", "utc"],
    },
    "wsbcommentsfull": {
        "tier": "enterprise",
        "summary": "Full WSB comments feed with timestamps and richer payloads.",
        "paths": {"live": "/beta/live/wsbcommentsfull"},
        "query_params": ["date_from", "date_to", "freq", "ignore_common", "ticker"],
    },
    "cryptocomments": {
        "tier": "tier3",
        "summary": "Crypto subreddit comments feed.",
        "paths": {"live": "/beta/live/cryptocomments"},
        "query_params": ["date_from", "date_to", "freq", "ignore_common", "ticker"],
    },
    "cryptocommentsfull": {
        "tier": "enterprise",
        "summary": "Full crypto comments feed.",
        "paths": {"live": "/beta/live/cryptocommentsfull"},
        "query_params": ["date_from", "date_to", "freq", "ignore_common", "ticker"],
    },
    "spaccomments": {
        "tier": "tier3",
        "summary": "SPAC-focused raw comments feed.",
        "paths": {"live": "/beta/live/spaccomments"},
        "query_params": ["date_from", "date_to", "freq", "ignore_common", "ticker"],
    },
    "redditcomments": {
        "tier": "tier3",
        "summary": "General Reddit comments feed.",
        "paths": {"live": "/beta/live/redditcomments"},
        "query_params": ["date_from", "date_to", "extra_words", "figi", "freq", "ignore_common", "ticker", "utc"],
    },
    "wsbgreed": {
        "tier": "tier1",
        "summary": "WallStreetBets greed index bulk dataset.",
        "paths": {"bulk": "/beta/bulk/wsbgreed"},
        "query_params": [],
    },
    "allpatents": {
        "tier": "tier2",
        "summary": "Patent grants by ticker and recent patent feed.",
        "paths": {"live": "/beta/live/allpatents", "historical": "/beta/historical/allpatents/{ticker}"},
        "query_params": ["date_from", "date_to", "latest", "ticker"],
    },
    "patentdrift": {
        "tier": "tier2",
        "summary": "Patent drift scores.",
        "paths": {"live": "/beta/live/patentdrift"},
        "query_params": ["date_from", "date_to", "latest", "ticker"],
    },
    "patentmomentum": {
        "tier": "tier2",
        "summary": "Patent momentum scores.",
        "paths": {"live": "/beta/live/patentmomentum"},
        "query_params": ["date_from", "date_to", "latest", "ticker"],
    },
    "appratings": {
        "tier": "tier2",
        "summary": "App store rating signals.",
        "paths": {"live": "/beta/live/appratings"},
        "query_params": [],
    },
    "offexchange": {
        "tier": "tier1",
        "summary": "Off-exchange or dark-pool short volume datasets.",
        "paths": {"live": "/beta/live/offexchange", "historical": "/beta/historical/offexchange/{ticker}"},
        "query_params": ["date", "page", "page_size"],
    },
    "flights": {
        "tier": "tier2",
        "summary": "Corporate private-jet flights.",
        "paths": {"live": "/beta/live/flights", "historical": "/beta/historical/flights/{ticker}"},
        "query_params": [],
    },
    "cnbc": {
        "tier": "tier2",
        "summary": "Recent CNBC trades and analyst picks.",
        "paths": {"live": "/beta/live/cnbc"},
        "query_params": ["analyst", "bulk", "date", "ticker"],
    },
    "eventsbeta": {
        "tier": "tier2",
        "summary": "Event-driven beta scores for today and ticker history.",
        "paths": {"today": "/beta/today/eventsbeta", "historical": "/beta/historical/eventsbeta/{ticker}"},
        "query_params": [],
    },
    "strategies_holdings": {
        "tier": "enterprise",
        "summary": "Current holdings for Quiver strategies.",
        "paths": {"live": "/beta/strategies/holdings"},
        "query_params": ["strategy"],
    },
    "strategies_holdings_infrequent": {
        "tier": "enterprise",
        "summary": "Current holdings for infrequently rebalancing strategies.",
        "paths": {"live": "/beta/strategies/holdings_infrequent"},
        "query_params": ["strategy"],
    },
    "companies": {"tier": "internal", "summary": "Company lookup table.", "paths": {"live": "/beta/companies"}, "query_params": []},
    "coins": {"tier": "internal", "summary": "Coin lookup table.", "paths": {"live": "/beta/coins"}, "query_params": []},
    "funds": {"tier": "internal", "summary": "Fund and ETF lookup table.", "paths": {"live": "/beta/funds"}, "query_params": []},
    "tickerdata": {"tier": "internal", "summary": "Ticker metadata.", "paths": {"live": "/beta/tickerdata"}, "query_params": []},
    "personalities": {"tier": "internal", "summary": "CNBC personalities reference.", "paths": {"live": "/beta/personalities"}, "query_params": []},
    "ignoredtickers": {"tier": "internal", "summary": "Ignored/excluded ticker reference list.", "paths": {"live": "/beta/ignoredtickers"}, "query_params": []},
    "rss": {"tier": "enterprise", "summary": "RSS news feed.", "paths": {"live": "/beta/live/rss"}, "query_params": []},
    "mobile_13frecentfilings": {"tier": "mobile", "summary": "Recent 13F filings for mobile clients.", "paths": {"live": "/beta/mobile/13frecentfilings"}, "query_params": []},
    "mobile_24hcryptocounts": {"tier": "mobile", "summary": "24h crypto comment counts.", "paths": {"live": "/beta/mobile/24hcryptocounts"}, "query_params": ["ticker"]},
    "mobile_24hcryptohottest": {"tier": "mobile", "summary": "24h hottest crypto comments.", "paths": {"live": "/beta/mobile/24hcryptohottest"}, "query_params": ["ticker"]},
    "mobile_24hwsbcounts": {"tier": "mobile", "summary": "24h WSB mention counts.", "paths": {"live": "/beta/mobile/24hwsbcounts"}, "query_params": ["ticker"]},
    "mobile_24hwsbhottest": {"tier": "mobile", "summary": "24h hottest WSB comments.", "paths": {"live": "/beta/mobile/24hwsbhottest"}, "query_params": ["ticker"]},
    "mobile_cnbcbyperson": {"tier": "mobile", "summary": "CNBC trader info by personality.", "paths": {"live": "/beta/mobile/cnbcbyperson"}, "query_params": ["analyst"]},
    "mobile_cnbcgraphs": {"tier": "mobile", "summary": "CNBC mobile chart payloads.", "paths": {"live": "/beta/mobile/cnbcgraphs"}, "query_params": []},
    "mobile_congress_net_worth_rankings": {"tier": "mobile", "summary": "Congress net-worth rankings.", "paths": {"live": "/beta/mobile/congress/net-worth/rankings"}, "query_params": ["active_only", "chamber", "page", "page_size", "party", "state"]},
    "mobile_congress_politicians": {"tier": "mobile", "summary": "Mobile Congress politician list.", "paths": {"live": "/beta/mobile/congress/politicians"}, "query_params": ["active_only", "chamber", "party"]},
    "mobile_congress_politician_profile": {"tier": "mobile", "summary": "Mobile Congress politician profile.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}"}, "query_params": ["bioguide_id"]},
    "mobile_congress_politician_donors": {"tier": "mobile", "summary": "Mobile Congress donor details.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/donors"}, "query_params": ["bioguide_id", "cycle", "donor_type", "page", "page_size"]},
    "mobile_congress_politician_legislation": {"tier": "mobile", "summary": "Mobile Congress legislation details.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/legislation"}, "query_params": ["bioguide_id", "bill_type", "congress", "page", "page_size"]},
    "mobile_congress_politician_opponents": {"tier": "mobile", "summary": "Mobile Congress opponent list.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/opponents"}, "query_params": ["bioguide_id"]},
    "mobile_congress_politician_portfolio": {"tier": "mobile", "summary": "Mobile Congress portfolio view.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/portfolio"}, "query_params": ["bioguide_id", "include_history", "min_allocation"]},
    "mobile_congress_politician_supporters": {"tier": "mobile", "summary": "Mobile Congress supporter list.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/supporters"}, "query_params": ["bioguide_id"]},
    "mobile_congress_politician_trades": {"tier": "mobile", "summary": "Mobile Congress trade history.", "paths": {"live": "/beta/mobile/congress/politicians/{bioguide_id}/trades"}, "query_params": ["bioguide_id", "end_date", "page", "page_size", "sort_by", "start_date", "transaction_type"]},
    "mobile_congress_traders_active": {"tier": "mobile", "summary": "Most active Congress traders.", "paths": {"live": "/beta/mobile/congress/traders/active"}, "query_params": ["page_size"]},
    "mobile_currentmostpopulartickers": {"tier": "mobile", "summary": "Current most popular tickers.", "paths": {"live": "/beta/mobile/currentmostpopulartickers"}, "query_params": []},
    "mobile_govcontracts": {"tier": "mobile", "summary": "Mobile government contracts summary.", "paths": {"live": "/beta/mobile/govcontracts"}, "query_params": ["ticker", "type"]},
    "mobile_insidertrading": {"tier": "mobile", "summary": "Mobile insider trading by type.", "paths": {"live": "/beta/mobile/insidertrading/{type}"}, "query_params": ["ticker", "type"]},
    "mobile_notifications": {"tier": "mobile", "summary": "Mobile alert/notification feed.", "paths": {"live": "/beta/mobile/notifications"}, "query_params": ["category", "date_from", "date_to"]},
    "mobile_repreturns": {"tier": "mobile", "summary": "Representative returns view.", "paths": {"live": "/beta/mobile/repreturns"}, "query_params": []},
    "mobile_repsentiment": {"tier": "mobile", "summary": "Representative sentiment view.", "paths": {"live": "/beta/mobile/repsentiment"}, "query_params": []},
    "mobile_senatereturns": {"tier": "mobile", "summary": "Senate returns view.", "paths": {"live": "/beta/mobile/senatereturns"}, "query_params": []},
    "mobile_senatesentiment": {"tier": "mobile", "summary": "Senate sentiment view.", "paths": {"live": "/beta/mobile/senatesentiment"}, "query_params": []},
    "mobile_strategy_performance": {"tier": "mobile", "summary": "Mobile strategy performance data.", "paths": {"live": "/beta/mobile/strategies/{strategy_name}"}, "query_params": ["strategy_name"]},
    "mobile_ticker": {"tier": "mobile", "summary": "Mobile ticker page payload.", "paths": {"live": "/beta/mobile/ticker/{ticker}"}, "query_params": ["ticker", "version"]},
    "mobile_toplobbying": {"tier": "mobile", "summary": "Mobile top lobbying view.", "paths": {"live": "/beta/mobile/toplobbying"}, "query_params": []},
    "mobile_trendingtickers": {"tier": "mobile", "summary": "Mobile trending tickers feed.", "paths": {"live": "/beta/mobile/trendingtickers"}, "query_params": ["lookback_hours", "page_size"]},
}


def implemented_quiver_paths() -> Set[str]:
    paths: Set[str] = set()
    for entry in DATASET_REGISTRY.values():
        paths.update(entry["paths"].values())
    return paths

