"""
Field Mappings - Maps endpoints to object types and categories.

Used to populate object_type and category columns in canvas_fields.db.
"""

from typing import Dict, List, Optional

# =============================================================================
# ENDPOINT ALIASES - For cross-asset joins
# =============================================================================
# Maps generic endpoint names to asset-specific endpoints.
# When a generic endpoint is requested for a specific object type,
# it gets translated to the actual endpoint in that asset's catalog.
# This enables cross-asset joins using a common endpoint name.

ENDPOINT_ALIASES: Dict[str, Dict[str, str]] = {
    # historical-price-full is the equity endpoint name
    # For other asset types, translate to their specific endpoint names
    "historical-price-full": {
        "crypto": "crypto-historical-eod-full",
        "forex": "forex-historical-eod-full",
        "commodity": "commodities-historical-eod-full",
    },
}


def resolve_endpoint_alias(endpoint: str, object_type: str) -> str:
    """
    Resolve an endpoint alias to the actual endpoint for the given object type.
    
    Args:
        endpoint: The requested endpoint name (e.g., "historical-price-full")
        object_type: The object type (e.g., "crypto", "forex", "equity")
        
    Returns:
        The actual endpoint name to use (may be the same as input if no alias)
    """
    if endpoint in ENDPOINT_ALIASES:
        aliases = ENDPOINT_ALIASES[endpoint]
        if object_type in aliases:
            return aliases[object_type]
    return endpoint


# =============================================================================
# ENDPOINT TO OBJECT TYPE MAPPING
# =============================================================================
# Which object types can use each endpoint
# Some endpoints support multiple object types (e.g., company-quote works for equity and etf)

ENDPOINT_TO_OBJECT_TYPES: Dict[str, List[str]] = {
    # =========================================================================
    # FMP - EQUITY (stocks)
    # =========================================================================
    "company-quote": ["equity", "etf"],
    "company-profile": ["equity", "etf"],
    "ratios": ["equity"],
    "ratios-ttm": ["equity"],
    "key-metrics": ["equity"],
    "key-metrics-ttm": ["equity"],
    "income-statement": ["equity"],
    "income-statement-growth": ["equity"],
    "balance-sheet-statement": ["equity"],
    "cash-flow-statement": ["equity"],
    "financial-growth": ["equity"],
    "financial-reports-json": ["equity"],
    "financial-statement-full-as-reported": ["equity"],
    "enterprise-values": ["equity"],
    "market-capitalization": ["equity"],
    "historical-price-full": ["equity", "etf", "crypto", "forex"],
    "historical-chart-1min": ["equity", "etf"],
    "historical-chart-5min": ["equity", "etf"],
    "historical-chart-15min": ["equity", "etf"],
    "historical-chart-30min": ["equity", "etf"],
    "historical-chart-1hour": ["equity", "etf"],
    "historical-chart-4hour": ["equity", "etf"],
    "historical-chart-1day": ["equity", "etf"],
    "stock-price-change": ["equity", "etf"],
    "stock-dividend": ["equity"],
    "stock-split": ["equity"],
    "stock-news": ["equity"],
    "stock-news-latest": ["equity"],
    "shares-float": ["equity"],
    "key-executives": ["equity"],
    "institutional-holder": ["equity"],
    "institutional-ownership-dates": ["equity"],
    "institutional-ownership-extract": ["equity"],
    "institutional-ownership-extract-analytics-holder": ["equity"],
    "institutional-ownership-holder-industry-breakdown": ["equity"],
    "institutional-ownership-holder-performance-summary": ["equity"],
    "institutional-ownership-industry-summary": ["equity"],
    "institutional-ownership-symbol-positions-summary": ["equity"],
    "funds-disclosure": ["equity"],
    "funds-disclosure-dates": ["equity"],
    "funds-disclosure-holders-search": ["equity"],
    "insider-trading-reporting-name": ["equity"],
    "mergers-acquisitions-search": ["equity"],
    
    # Technical Indicators
    "technical-indicator-sma": ["equity", "etf"],
    "technical-indicator-ema": ["equity", "etf"],
    "technical-indicator-rsi": ["equity", "etf"],
    "technical-indicator-bbands": ["equity", "etf"],
    "technical-indicator-stoch": ["equity", "etf"],
    
    # Analyst / Ratings
    "analyst-estimates": ["equity"],
    "grade": ["equity"],
    "grades": ["equity"],
    "grades-consensus": ["equity"],
    "grades-historical": ["equity"],
    "grades-latest-news": ["equity"],
    "grades-news": ["equity"],
    "rating": ["equity"],
    "ratings-historical": ["equity"],
    "ratings-snapshot": ["equity"],
    "historical-rating": ["equity"],
    "price-target": ["equity"],
    "price-target-consensus": ["equity"],
    "price-target-summary": ["equity"],
    "price-target-news": ["equity"],
    "price-target-latest-news": ["equity"],
    
    # Valuation / DCF
    "dcf": ["equity"],
    "discounted-cash-flow": ["equity"],
    "levered-dcf": ["equity"],
    "advanced-dcf": ["equity"],
    "custom-discounted-cash-flow": ["equity"],
    "custom-levered-discounted-cash-flow": ["equity"],
    "financial-estimates": ["equity"],
    
    # Ownership / Institutional
    "insider-trading": ["equity"],
    "insider-trading-latest": ["equity"],
    "insider-trading-rss-feed": ["equity"],
    "insider-trading-search": ["equity"],
    "insider-trading-statistics": ["equity"],
    "insider-trading-transaction-type": ["equity"],
    "institutional-ownership-latest": ["equity"],
    "mutual-fund-holder": ["equity"],
    "etf-holder": ["equity"],
    "acquisition-of-beneficial-ownership": ["equity"],
    "funds-disclosure-holders-latest": ["equity"],
    
    # SEC / Filings
    "sec-filings": ["equity"],
    "rss-feed": ["equity"],
    "rss-feed-8k": ["equity"],
    "press-releases": ["equity"],
    "press-releases-latest": ["equity"],
    "fmp-articles": ["equity"],
    
    # Earnings
    "earning-call-calendar": ["equity"],
    "earning-call-transcript": ["equity"],
    "earnings-confirmed": ["equity"],
    
    # ESG
    "esg-scores": ["equity"],
    "esg-ratings": ["equity"],
    "esg-disclosures": ["equity"],
    "esg-benchmark": ["market"],
    
    # IPO / M&A
    "ipos-disclosure": ["equity"],
    "ipos-prospectus": ["equity"],
    "mergers-acquisitions-latest": ["equity"],
    
    # DCF Bulk
    "dcf-bulk": ["equity"],
    
    # Historical PE
    "historical-sector-pe": ["market"],
    "historical-industry-pe": ["market"],
    
    # Congress by name
    "senate-trades-by-name": ["market"],
    "house-trades-by-name": ["market"],
    
    # =========================================================================
    # FMP - ETF
    # =========================================================================
    "etf-asset-exposure": ["etf"],
    "etf-holdings": ["etf"],
    "etf-info": ["etf"],
    "etf-sector-weightings": ["etf"],
    "etf-country-weightings": ["etf"],
    
    # =========================================================================
    # FMP - CRYPTO
    # =========================================================================
    "crypto-quote": ["crypto"],
    "crypto-quote-short": ["crypto"],
    "crypto-batch-quotes": ["crypto"],
    "crypto-list": ["crypto"],
    "crypto-historical-eod-full": ["crypto"],
    "crypto-historical-eod-light": ["crypto"],
    "crypto-historical-1min": ["crypto"],
    "crypto-historical-5min": ["crypto"],
    "crypto-historical-1hour": ["crypto"],
    "crypto-news": ["crypto"],
    "crypto-news-latest": ["crypto"],
    
    # =========================================================================
    # FMP - FOREX
    # =========================================================================
    "forex-quote": ["forex"],
    "forex-quote-short": ["forex"],
    "forex-batch-quotes": ["forex"],
    "forex-list": ["forex"],
    "forex-historical-eod-full": ["forex"],
    "forex-historical-eod-light": ["forex"],
    "forex-historical-1min": ["forex"],
    "forex-historical-5min": ["forex"],
    "forex-historical-1hour": ["forex"],
    "forex-news": ["forex"],
    "forex-news-latest": ["forex"],
    
    # =========================================================================
    # FMP - COMMODITIES
    # =========================================================================
    "commodities-quote": ["commodity"],
    "commodities-quote-short": ["commodity"],
    "commodities-batch-quotes": ["commodity"],
    "commodities-list": ["commodity"],
    "commodities-historical-eod-full": ["commodity"],
    "commodities-historical-eod-light": ["commodity"],
    "commodities-historical-1min": ["commodity"],
    "commodities-historical-5min": ["commodity"],
    "commodities-historical-1hour": ["commodity"],
    
    # =========================================================================
    # FMP - MARKET-WIDE (no symbol required)
    # =========================================================================
    "treasury": ["market"],
    "economic-calendar": ["market"],
    "market-risk-premium": ["market"],
    "sector-performance": ["market"],
    "sector-pe-snapshot": ["market"],
    "industry-performance": ["market"],
    "industry-pe-snapshot": ["market"],
    "biggest-gainers": ["market"],
    "biggest-losers": ["market"],
    "most-actives": ["market"],
    "stock-screener": ["market"],
    "general-news-latest": ["market"],
    
    # Congress / Senate
    "senate-trading": ["market"],
    "senate-latest": ["market"],
    "senate-disclosure": ["market"],
    "house-trades": ["market"],
    "house-latest": ["market"],
    
    # =========================================================================
    # POLYGON - CRYPTO
    # =========================================================================
    "crypto-tickers": ["crypto"],
    "crypto-ticker-detail": ["crypto"],
    "crypto-open-close": ["crypto"],
    
    # =========================================================================
    # POLYGON - FOREX
    # =========================================================================
    "forex-tickers": ["forex"],
    "forex-ticker-detail": ["forex"],
    
    # =========================================================================
    # POLYGON - OPTIONS
    # =========================================================================
    "options-contracts-list": ["options"],
    "options-aggregates-range": ["options"],
    "options-prev-close": ["options"],
    "options-indicator-sma": ["options"],
    "options-indicator-ema": ["options"],
    "options-indicator-rsi": ["options"],
    "options-indicator-macd": ["options"],
    
    # =========================================================================
    # POLYGON - CRYPTO ADDITIONAL
    # =========================================================================
    "crypto-aggregates-grouped": ["crypto"],
    "crypto-aggregates-prev": ["crypto"],
    "crypto-aggregates-range": ["crypto"],
    "crypto-indicator-sma": ["crypto"],
    "crypto-indicator-ema": ["crypto"],
    "crypto-indicator-rsi": ["crypto"],
    "crypto-indicator-macd": ["crypto"],
    "crypto-last-trade": ["crypto"],
    "crypto-snapshot-market": ["crypto"],
    "crypto-snapshot-movers": ["crypto"],
    "crypto-snapshot-single": ["crypto"],
    "crypto-trades": ["crypto"],
    
    # =========================================================================
    # POLYGON - FOREX ADDITIONAL
    # =========================================================================
    "forex-aggregates-grouped": ["forex"],
    "forex-aggregates-prev": ["forex"],
    "forex-aggregates-range": ["forex"],
    "forex-indicator-sma": ["forex"],
    "forex-indicator-ema": ["forex"],
    "forex-indicator-rsi": ["forex"],
    "forex-indicator-macd": ["forex"],
    "forex-quotes": ["forex"],
    "forex-snapshot-market": ["forex"],
    "forex-snapshot-movers": ["forex"],
    "forex-snapshot-single": ["forex"],
    "forex-conversion": ["forex"],
    
    # =========================================================================
    # POLYGON - OPTIONS ADDITIONAL
    # =========================================================================
    "options-contract-detail": ["options"],
    "options-last-trade": ["options"],
    "options-open-close": ["options"],
    "options-quotes": ["options"],
    "options-snapshot-chain": ["options"],
    "options-snapshot-single": ["options"],
    "options-trades": ["options"],
    
    # =========================================================================
    # POLYGON - MARKET REFERENCE
    # =========================================================================
    "reference-exchanges": ["market"],
    "reference-conditions": ["market"],
    "marketstatus-now": ["market"],
    "marketstatus-upcoming": ["market"],
    "snapshot-unified": ["equity", "etf", "crypto", "forex"],
    
    # =========================================================================
    # UNUSUAL WHALES - OPTIONS (equity-based)
    # =========================================================================
    "flow-alerts": ["equity"],
    "stock-flow-recent": ["equity"],
    "stock-flow-per-expiry": ["equity"],
    "stock-flow-per-strike": ["equity"],
    "stock-flow-per-strike-intraday": ["equity"],
    "stock-greek-exposure": ["equity"],
    "stock-greek-exposure-by-expiry": ["equity"],
    "stock-greek-exposure-by-strike": ["equity"],
    "stock-greek-exposure-by-strike-expiry": ["equity"],
    "stock-greek-flow": ["equity"],
    "stock-greeks": ["equity"],
    "stock-oi-change": ["equity"],
    "stock-oi-per-expiry": ["equity"],
    "stock-oi-per-strike": ["equity"],
    "stock-option-contracts": ["equity"],
    "stock-option-price-levels": ["equity"],
    "stock-options-volume": ["equity"],
    "stock-volume-oi-per-expiry": ["equity"],
    "stock-expiry-breakdown": ["equity"],
    "stock-max-pain": ["equity"],
    "stock-nope": ["equity"],
    "stock-iv-rank": ["equity"],
    "stock-interpolated-iv": ["equity"],
    "stock-volatility-realized": ["equity"],
    "stock-volatility-stats": ["equity"],
    "stock-volatility-term-structure": ["equity"],
    "stock-historical-risk-reversal-skew": ["equity"],
    "stock-spot-exposures-expiry-strike": ["equity"],
    "stock-spot-exposures-strike": ["equity"],
    "net-flow-expiry": ["equity"],
    "screener-option-contracts": ["equity"],
    
    # =========================================================================
    # UNUSUAL WHALES - INSTITUTIONAL
    # =========================================================================
    "institution-ownership": ["equity"],
    "institutions-list": ["market"],
    "insider-transactions": ["equity"],
    "market-insider-buy-sells": ["market"],
    "congress-recent-trades": ["market"],
    "congress-late-reports": ["market"],
    "congress-trader-reports": ["market"],
    "darkpool-recent-trades": ["market"],
    "darkpool-ticker-trades": ["equity"],
    
    # =========================================================================
    # UNUSUAL WHALES - MARKET
    # =========================================================================
    "market-sector-etfs": ["market"],
    "market-tide": ["market"],
    "market-top-net-impact": ["market"],
    "market-oi-change": ["market"],
    "market-total-options-volume": ["market"],
    "screener-analysts": ["market"],
    "screener-stocks": ["market"],
    "seasonality-market": ["market"],
    "seasonality-ticker-monthly": ["equity"],
    "seasonality-ticker-year-month": ["equity"],
    "earnings-historical": ["equity"],
    
    # =========================================================================
    # UNUSUAL WHALES - ETF
    # =========================================================================
    "etf-exposure": ["etf"],
    "etf-tide": ["etf"],
    "etf-weights": ["etf"],
    "etf-holdings": ["etf"],
    "etf-inflow-outflow": ["etf"],
    
    # =========================================================================
    # UNUSUAL WHALES - OPTIONS ADDITIONAL
    # =========================================================================
    "option-contract-flow": ["equity"],
    "option-contract-historic": ["equity"],
    "option-contract-intraday": ["equity"],
    "option-contract-volume-profile": ["equity"],
    "stock-option-chains": ["equity"],
    "stock-atm-chains": ["equity"],
    "stock-greek-flow-by-expiry": ["equity"],
    "group-greek-flow": ["market"],
    "group-greek-flow-by-expiry": ["market"],
    
    # =========================================================================
    # UNUSUAL WHALES - MARKET ADDITIONAL
    # =========================================================================
    "market-correlations": ["market"],
    "market-spike": ["market"],
    "sector-tide": ["market"],
    "seasonality-month-performers": ["market"],
    
    # =========================================================================
    # UNUSUAL WHALES - INSTITUTIONAL ADDITIONAL
    # =========================================================================
    "institution-holdings": ["equity"],
    "institution-sectors": ["market"],
    
    # =========================================================================
    # UNUSUAL WHALES - SHORTS
    # =========================================================================
    "shorts-data": ["equity"],
    "shorts-ftds": ["equity"],
    "shorts-interest-float": ["equity"],
    "shorts-volume-ratio": ["equity"],
    "shorts-volume-by-exchange": ["equity"],
}


# =============================================================================
# ENDPOINT TO CATEGORY MAPPING
# =============================================================================

ENDPOINT_TO_CATEGORY: Dict[str, str] = {
    # =========================================================================
    # PRICE & VOLUME
    # =========================================================================
    "company-quote": "Price & Volume",
    "company-profile": "Price & Volume",
    "historical-price-full": "Price & Volume",
    "historical-chart-1min": "Price & Volume",
    "historical-chart-5min": "Price & Volume",
    "historical-chart-15min": "Price & Volume",
    "historical-chart-30min": "Price & Volume",
    "historical-chart-1hour": "Price & Volume",
    "historical-chart-4hour": "Price & Volume",
    "historical-chart-1day": "Price & Volume",
    "stock-price-change": "Price & Volume",
    "market-capitalization": "Price & Volume",
    "shares-float": "Price & Volume",
    "crypto-quote": "Price & Volume",
    "crypto-quote-short": "Price & Volume",
    "crypto-batch-quotes": "Price & Volume",
    "crypto-historical-eod-full": "Price & Volume",
    "crypto-historical-eod-light": "Price & Volume",
    "crypto-historical-1min": "Price & Volume",
    "crypto-historical-5min": "Price & Volume",
    "crypto-historical-1hour": "Price & Volume",
    "forex-quote": "Price & Volume",
    "forex-quote-short": "Price & Volume",
    "forex-batch-quotes": "Price & Volume",
    "forex-historical-eod-full": "Price & Volume",
    "forex-historical-eod-light": "Price & Volume",
    "forex-historical-1min": "Price & Volume",
    "forex-historical-5min": "Price & Volume",
    "forex-historical-1hour": "Price & Volume",
    "commodities-quote": "Price & Volume",
    "commodities-quote-short": "Price & Volume",
    "commodities-batch-quotes": "Price & Volume",
    "commodities-historical-eod-full": "Price & Volume",
    "commodities-historical-eod-light": "Price & Volume",
    "commodities-historical-1min": "Price & Volume",
    "commodities-historical-5min": "Price & Volume",
    "commodities-historical-1hour": "Price & Volume",
    "crypto-open-close": "Price & Volume",
    "crypto-aggregates-grouped": "Price & Volume",
    "crypto-aggregates-prev": "Price & Volume",
    "crypto-aggregates-range": "Price & Volume",
    "crypto-last-trade": "Price & Volume",
    "crypto-snapshot-market": "Price & Volume",
    "crypto-snapshot-movers": "Price & Volume",
    "crypto-snapshot-single": "Price & Volume",
    "crypto-trades": "Price & Volume",
    "forex-aggregates-grouped": "Price & Volume",
    "forex-aggregates-prev": "Price & Volume",
    "forex-aggregates-range": "Price & Volume",
    "forex-quotes": "Price & Volume",
    "forex-snapshot-market": "Price & Volume",
    "forex-snapshot-movers": "Price & Volume",
    "forex-snapshot-single": "Price & Volume",
    "forex-conversion": "Price & Volume",
    "snapshot-unified": "Price & Volume",
    "dcf-bulk": "Valuation",
    
    # =========================================================================
    # VALUATION
    # =========================================================================
    "ratios": "Valuation",
    "ratios-ttm": "Valuation",
    "key-metrics": "Valuation",
    "key-metrics-ttm": "Valuation",
    "enterprise-values": "Valuation",
    "dcf": "Valuation",
    "discounted-cash-flow": "Valuation",
    "levered-dcf": "Valuation",
    "advanced-dcf": "Valuation",
    "custom-discounted-cash-flow": "Valuation",
    "custom-levered-discounted-cash-flow": "Valuation",
    
    # =========================================================================
    # FUNDAMENTALS
    # =========================================================================
    "income-statement": "Fundamentals",
    "income-statement-growth": "Fundamentals",
    "balance-sheet-statement": "Fundamentals",
    "cash-flow-statement": "Fundamentals",
    "financial-growth": "Fundamentals",
    "financial-reports-json": "Fundamentals",
    "financial-statement-full-as-reported": "Fundamentals",
    "financial-estimates": "Fundamentals",
    
    # =========================================================================
    # ANALYST RATINGS
    # =========================================================================
    "analyst-estimates": "Analyst Ratings",
    "grade": "Analyst Ratings",
    "grades": "Analyst Ratings",
    "grades-consensus": "Analyst Ratings",
    "grades-historical": "Analyst Ratings",
    "grades-latest-news": "Analyst Ratings",
    "grades-news": "Analyst Ratings",
    "rating": "Analyst Ratings",
    "ratings-historical": "Analyst Ratings",
    "ratings-snapshot": "Analyst Ratings",
    "historical-rating": "Analyst Ratings",
    "price-target": "Analyst Ratings",
    "price-target-consensus": "Analyst Ratings",
    "price-target-summary": "Analyst Ratings",
    "price-target-news": "Analyst Ratings",
    "price-target-latest-news": "Analyst Ratings",
    "screener-analysts": "Analyst Ratings",
    
    # =========================================================================
    # OWNERSHIP & INSTITUTIONAL
    # =========================================================================
    "insider-trading": "Ownership",
    "insider-trading-latest": "Ownership",
    "insider-trading-rss-feed": "Ownership",
    "insider-trading-search": "Ownership",
    "insider-trading-statistics": "Ownership",
    "insider-trading-transaction-type": "Ownership",
    "insider-trading-reporting-name": "Ownership",
    "institutional-ownership-latest": "Ownership",
    "institutional-holder": "Ownership",
    "institutional-ownership-dates": "Ownership",
    "institutional-ownership-extract": "Ownership",
    "institutional-ownership-extract-analytics-holder": "Ownership",
    "institutional-ownership-holder-industry-breakdown": "Ownership",
    "institutional-ownership-holder-performance-summary": "Ownership",
    "institutional-ownership-industry-summary": "Ownership",
    "institutional-ownership-symbol-positions-summary": "Ownership",
    "mutual-fund-holder": "Ownership",
    "etf-holder": "Ownership",
    "acquisition-of-beneficial-ownership": "Ownership",
    "funds-disclosure": "Ownership",
    "funds-disclosure-dates": "Ownership",
    "funds-disclosure-holders-latest": "Ownership",
    "funds-disclosure-holders-search": "Ownership",
    "institution-ownership": "Ownership",
    "institution-holdings": "Ownership",
    "institution-sectors": "Ownership",
    "institutions-list": "Ownership",
    "insider-transactions": "Ownership",
    "market-insider-buy-sells": "Ownership",
    
    # =========================================================================
    # SEC FILINGS & NEWS
    # =========================================================================
    "sec-filings": "Filings & News",
    "rss-feed": "Filings & News",
    "rss-feed-8k": "Filings & News",
    "press-releases": "Filings & News",
    "press-releases-latest": "Filings & News",
    "fmp-articles": "Filings & News",
    "stock-news": "Filings & News",
    "stock-news-latest": "Filings & News",
    "crypto-news": "Filings & News",
    "crypto-news-latest": "Filings & News",
    "forex-news": "Filings & News",
    "forex-news-latest": "Filings & News",
    "general-news-latest": "Filings & News",
    
    # =========================================================================
    # EARNINGS
    # =========================================================================
    "earning-call-calendar": "Earnings",
    "earning-call-transcript": "Earnings",
    "earnings-confirmed": "Earnings",
    "earnings-historical": "Earnings",
    
    # =========================================================================
    # DIVIDENDS & SPLITS
    # =========================================================================
    "stock-dividend": "Dividends & Splits",
    "stock-split": "Dividends & Splits",
    
    # =========================================================================
    # ESG
    # =========================================================================
    "esg-scores": "ESG",
    "esg-ratings": "ESG",
    "esg-disclosures": "ESG",
    "esg-benchmark": "ESG",
    
    # =========================================================================
    # IPO & M&A
    # =========================================================================
    "ipos-disclosure": "IPO & M&A",
    "ipos-prospectus": "IPO & M&A",
    "mergers-acquisitions-latest": "IPO & M&A",
    "mergers-acquisitions-search": "IPO & M&A",
    
    # =========================================================================
    # OPTIONS FLOW (UW)
    # =========================================================================
    "flow-alerts": "Options Flow",
    "stock-flow-recent": "Options Flow",
    "stock-flow-per-expiry": "Options Flow",
    "stock-flow-per-strike": "Options Flow",
    "stock-flow-per-strike-intraday": "Options Flow",
    "net-flow-expiry": "Options Flow",
    "screener-option-contracts": "Options Flow",
    "option-contract-flow": "Options Flow",
    "option-contract-historic": "Options Flow",
    "option-contract-intraday": "Options Flow",
    "option-contract-volume-profile": "Options Flow",
    "group-greek-flow": "Options Flow",
    "group-greek-flow-by-expiry": "Options Flow",
    "stock-greek-flow-by-expiry": "Options Flow",
    
    # =========================================================================
    # OPTIONS GREEKS (UW)
    # =========================================================================
    "stock-greek-exposure": "Options Greeks",
    "stock-greek-exposure-by-expiry": "Options Greeks",
    "stock-greek-exposure-by-strike": "Options Greeks",
    "stock-greek-exposure-by-strike-expiry": "Options Greeks",
    "stock-greek-flow": "Options Greeks",
    "stock-greeks": "Options Greeks",
    "stock-spot-exposures-expiry-strike": "Options Greeks",
    "stock-spot-exposures-strike": "Options Greeks",
    
    # =========================================================================
    # OPTIONS OI & VOLUME (UW)
    # =========================================================================
    "stock-oi-change": "Options OI",
    "stock-oi-per-expiry": "Options OI",
    "stock-oi-per-strike": "Options OI",
    "stock-option-contracts": "Options OI",
    "stock-option-price-levels": "Options OI",
    "stock-options-volume": "Options OI",
    "stock-volume-oi-per-expiry": "Options OI",
    "stock-expiry-breakdown": "Options OI",
    "stock-option-chains": "Options OI",
    "stock-atm-chains": "Options OI",
    "market-oi-change": "Options OI",
    "market-total-options-volume": "Options OI",
    
    # =========================================================================
    # OPTIONS VOLATILITY (UW)
    # =========================================================================
    "stock-max-pain": "Options Volatility",
    "stock-nope": "Options Volatility",
    "stock-iv-rank": "Options Volatility",
    "stock-interpolated-iv": "Options Volatility",
    "stock-volatility-realized": "Options Volatility",
    "stock-volatility-stats": "Options Volatility",
    "stock-volatility-term-structure": "Options Volatility",
    "stock-historical-risk-reversal-skew": "Options Volatility",
    
    # =========================================================================
    # POLYGON OPTIONS
    # =========================================================================
    "options-contracts-list": "Options Data",
    "options-aggregates-range": "Options Data",
    "options-prev-close": "Options Data",
    "options-indicator-sma": "Options Data",
    "options-indicator-ema": "Options Data",
    "options-indicator-rsi": "Options Data",
    "options-indicator-macd": "Options Data",
    "options-contract-detail": "Options Data",
    "options-last-trade": "Options Data",
    "options-open-close": "Options Data",
    "options-quotes": "Options Data",
    "options-snapshot-chain": "Options Data",
    "options-snapshot-single": "Options Data",
    "options-trades": "Options Data",
    
    # =========================================================================
    # TECHNICAL INDICATORS
    # =========================================================================
    "technical-indicator-sma": "Technical Indicators",
    "technical-indicator-ema": "Technical Indicators",
    "technical-indicator-rsi": "Technical Indicators",
    "technical-indicator-bbands": "Technical Indicators",
    "technical-indicator-stoch": "Technical Indicators",
    "crypto-indicator-sma": "Technical Indicators",
    "crypto-indicator-ema": "Technical Indicators",
    "crypto-indicator-rsi": "Technical Indicators",
    "crypto-indicator-macd": "Technical Indicators",
    "forex-indicator-sma": "Technical Indicators",
    "forex-indicator-ema": "Technical Indicators",
    "forex-indicator-rsi": "Technical Indicators",
    "forex-indicator-macd": "Technical Indicators",
    
    # =========================================================================
    # DARK POOL
    # =========================================================================
    "darkpool-recent-trades": "Dark Pool",
    "darkpool-ticker-trades": "Dark Pool",
    
    # =========================================================================
    # SHORTS
    # =========================================================================
    "shorts-data": "Short Interest",
    "shorts-ftds": "Short Interest",
    "shorts-interest-float": "Short Interest",
    "shorts-volume-ratio": "Short Interest",
    "shorts-volume-by-exchange": "Short Interest",
    
    # =========================================================================
    # CONGRESS / SENATE
    # =========================================================================
    "senate-trading": "Congress Trading",
    "senate-latest": "Congress Trading",
    "senate-disclosure": "Congress Trading",
    "senate-trades-by-name": "Congress Trading",
    "house-trades": "Congress Trading",
    "house-latest": "Congress Trading",
    "house-trades-by-name": "Congress Trading",
    "congress-recent-trades": "Congress Trading",
    "congress-late-reports": "Congress Trading",
    "congress-trader-reports": "Congress Trading",
    
    # =========================================================================
    # ETF
    # =========================================================================
    "etf-asset-exposure": "ETF Data",
    "etf-exposure": "ETF Data",
    "etf-tide": "ETF Data",
    "etf-weights": "ETF Data",
    "etf-holdings": "ETF Data",
    "etf-info": "ETF Data",
    "etf-sector-weightings": "ETF Data",
    "etf-country-weightings": "ETF Data",
    "etf-inflow-outflow": "ETF Data",
    
    # =========================================================================
    # MACRO / ECONOMIC
    # =========================================================================
    "treasury": "Economic",
    "economic-calendar": "Economic",
    "market-risk-premium": "Economic",
    
    # =========================================================================
    # MARKET OVERVIEW
    # =========================================================================
    "sector-performance": "Market Overview",
    "sector-pe-snapshot": "Market Overview",
    "sector-tide": "Market Overview",
    "industry-performance": "Market Overview",
    "industry-pe-snapshot": "Market Overview",
    "historical-sector-pe": "Market Overview",
    "historical-industry-pe": "Market Overview",
    "biggest-gainers": "Market Overview",
    "biggest-losers": "Market Overview",
    "most-actives": "Market Overview",
    "stock-screener": "Market Overview",
    "screener-stocks": "Market Overview",
    "market-sector-etfs": "Market Overview",
    "market-tide": "Market Overview",
    "market-top-net-impact": "Market Overview",
    "market-correlations": "Market Overview",
    "market-spike": "Market Overview",
    "seasonality-market": "Market Overview",
    "seasonality-ticker-monthly": "Market Overview",
    "seasonality-ticker-year-month": "Market Overview",
    "seasonality-month-performers": "Market Overview",
    
    # =========================================================================
    # REFERENCE / METADATA
    # =========================================================================
    "crypto-list": "Reference",
    "forex-list": "Reference",
    "commodities-list": "Reference",
    "crypto-tickers": "Reference",
    "crypto-ticker-detail": "Reference",
    "forex-tickers": "Reference",
    "forex-ticker-detail": "Reference",
    "reference-exchanges": "Reference",
    "reference-conditions": "Reference",
    "marketstatus-now": "Reference",
    "marketstatus-upcoming": "Reference",
    "key-executives": "Reference",
}


def get_object_types_for_endpoint(endpoint: str) -> List[str]:
    """Get the object types that can use this endpoint."""
    return ENDPOINT_TO_OBJECT_TYPES.get(endpoint, ["equity"])


def get_category_for_endpoint(endpoint: str) -> str:
    """Get the category for an endpoint."""
    return ENDPOINT_TO_CATEGORY.get(endpoint, "Other")


def get_endpoints_for_object_type(object_type: str) -> List[str]:
    """Get all endpoints that support a given object type."""
    endpoints = []
    for endpoint, types in ENDPOINT_TO_OBJECT_TYPES.items():
        if object_type in types:
            endpoints.append(endpoint)
    return endpoints


# =============================================================================
# ENDPOINT TO STRUCTURE TYPE MAPPING
# =============================================================================
# Defines the data structure pattern for each endpoint.
# Used to determine compatibility for merging datasets.

ENDPOINT_TO_STRUCTURE_TYPE: Dict[str, str] = {
    # =========================================================================
    # SNAPSHOT - Single record, no time dimension (current/latest values)
    # =========================================================================
    "company-quote": "snapshot",
    "company-profile": "snapshot",
    "ratios-ttm": "snapshot",
    "key-metrics-ttm": "snapshot",
    "dcf": "snapshot",
    "discounted-cash-flow": "snapshot",
    "levered-dcf": "snapshot",
    "advanced-dcf": "snapshot",
    "custom-discounted-cash-flow": "snapshot",
    "custom-levered-discounted-cash-flow": "snapshot",
    "price-target-consensus": "snapshot",
    "price-target-summary": "snapshot",
    "ratings-snapshot": "snapshot",
    "grades-consensus": "snapshot",
    "shares-float": "snapshot",
    "market-capitalization": "snapshot",
    "stock-price-change": "snapshot",
    "esg-ratings": "snapshot",
    "esg-scores": "snapshot",
    "esg-disclosures": "snapshot",
    "esg-benchmark": "snapshot",
    "mutual-fund-holder": "snapshot",
    "etf-holder": "snapshot",
    "market-risk-premium": "snapshot",
    "crypto-quote": "snapshot",
    "crypto-quote-short": "snapshot",
    "forex-quote": "snapshot",
    "forex-quote-short": "snapshot",
    "commodities-quote": "snapshot",
    "commodities-quote-short": "snapshot",
    "snapshot-unified": "snapshot",
    "etf-exposure": "snapshot",
    "etf-weights": "snapshot",
    "shorts-interest-float": "snapshot",
    "stock-iv-rank": "snapshot",
    "stock-interpolated-iv": "snapshot",
    "stock-volatility-stats": "snapshot",
    "stock-max-pain": "snapshot",
    "stock-nope": "snapshot",
    "stock-greeks": "snapshot",
    
    # =========================================================================
    # FISCAL_PERIOD_SERIES - Indexed by calendarYear + period (FY/Q1/Q2/Q3/Q4)
    # =========================================================================
    "income-statement": "fiscal_period_series",
    "income-statement-growth": "fiscal_period_series",
    "balance-sheet-statement": "fiscal_period_series",
    "cash-flow-statement": "fiscal_period_series",
    "key-metrics": "fiscal_period_series",
    "ratios": "fiscal_period_series",
    "financial-growth": "fiscal_period_series",
    "enterprise-values": "fiscal_period_series",
    "analyst-estimates": "fiscal_period_series",
    "financial-estimates": "fiscal_period_series",
    "financial-statement-full-as-reported": "fiscal_period_series",
    "seasonality-ticker-monthly": "fiscal_period_series",
    "seasonality-ticker-year-month": "fiscal_period_series",
    
    # =========================================================================
    # DAILY_OHLCV - Daily trading time series (date-indexed)
    # =========================================================================
    "historical-price-full": "daily_ohlcv",
    "historical-chart-1day": "daily_ohlcv",
    "treasury": "daily_ohlcv",
    "shorts-volume-ratio": "daily_ohlcv",
    "shorts-volume-by-exchange": "daily_ohlcv",
    
    # =========================================================================
    # INTRADAY - Sub-daily bars (datetime-indexed)
    # =========================================================================
    "historical-chart-1min": "intraday",
    "historical-chart-5min": "intraday",
    "historical-chart-15min": "intraday",
    "historical-chart-30min": "intraday",
    "historical-chart-1hour": "intraday",
    "historical-chart-4hour": "intraday",
    
    # =========================================================================
    # EVENT_LIST - Irregular event records (date varies by event)
    # =========================================================================
    "grade": "event_list",
    "grades": "event_list",
    "grades-historical": "event_list",
    "grades-news": "event_list",
    "grades-latest-news": "event_list",
    "rating": "event_list",
    "ratings-historical": "event_list",
    "historical-rating": "event_list",
    "price-target": "event_list",
    "price-target-news": "event_list",
    "price-target-latest-news": "event_list",
    "insider-trading": "event_list",
    "insider-trading-latest": "event_list",
    "insider-trading-search": "event_list",
    "insider-trading-statistics": "event_list",
    "insider-trading-transaction-type": "event_list",
    "stock-news": "event_list",
    "stock-dividend": "event_list",
    "stock-split": "event_list",
    "senate-trading": "event_list",
    "house-trades": "event_list",
    "ipos-disclosure": "event_list",
    "ipos-prospectus": "event_list",
    "mergers-acquisitions-latest": "event_list",
    "darkpool-ticker-trades": "event_list",
    "institution-ownership": "event_list",
    "insider-transactions": "event_list",
    "shorts-data": "event_list",
    "shorts-ftds": "event_list",
    "etf-tide": "event_list",
    "earnings-historical": "event_list",
    "stock-volatility-realized": "event_list",
    "stock-volatility-term-structure": "event_list",
    "stock-historical-risk-reversal-skew": "event_list",
    
    # =========================================================================
    # YEAR_QUARTER_INDEXED - Requires year + quarter params
    # =========================================================================
    "institutional-ownership-latest": "year_quarter_indexed",
    "earning-call-transcript": "year_quarter_indexed",
    "financial-reports-json": "year_quarter_indexed",
    "acquisition-of-beneficial-ownership": "year_quarter_indexed",
    "funds-disclosure-holders-latest": "year_quarter_indexed",
    
    # =========================================================================
    # MARKET_WIDE - No symbol, paginated (market-level data)
    # =========================================================================
    "sector-performance": "market_wide",
    "sector-pe-snapshot": "market_wide",
    "industry-performance": "market_wide",
    "industry-pe-snapshot": "market_wide",
    "biggest-gainers": "market_wide",
    "biggest-losers": "market_wide",
    "most-actives": "market_wide",
    "stock-screener": "market_wide",
    "general-news-latest": "market_wide",
    "stock-news-latest": "market_wide",
    "press-releases-latest": "market_wide",
    "fmp-articles": "market_wide",
    "earning-call-calendar": "market_wide",
    "earnings-confirmed": "market_wide",
    "rss-feed": "market_wide",
    "rss-feed-8k": "market_wide",
    "insider-trading-rss-feed": "market_wide",
    "senate-latest": "market_wide",
    "senate-disclosure": "market_wide",
    "house-latest": "market_wide",
    "economic-calendar": "market_wide",
    "crypto-list": "market_wide",
    "forex-list": "market_wide",
    "commodities-list": "market_wide",
    "crypto-news": "market_wide",
    "crypto-news-latest": "market_wide",
    "forex-news": "market_wide",
    "forex-news-latest": "market_wide",
    "crypto-batch-quotes": "market_wide",
    "forex-batch-quotes": "market_wide",
    "commodities-batch-quotes": "market_wide",
    "reference-exchanges": "market_wide",
    "reference-conditions": "market_wide",
    "marketstatus-now": "market_wide",
    "marketstatus-upcoming": "market_wide",
    "institutions-list": "market_wide",
    "market-insider-buy-sells": "market_wide",
    "congress-recent-trades": "market_wide",
    "congress-late-reports": "market_wide",
    "congress-trader-reports": "market_wide",
    "darkpool-recent-trades": "market_wide",
    "market-sector-etfs": "market_wide",
    "market-tide": "market_wide",
    "market-top-net-impact": "market_wide",
    "screener-analysts": "market_wide",
    "screener-stocks": "market_wide",
    "seasonality-market": "market_wide",
    
    # =========================================================================
    # SEC_FILING_SEARCH - Filing metadata lists (date-ranged)
    # =========================================================================
    "sec-filings": "sec_filing_search",
    "press-releases": "sec_filing_search",
    
    # =========================================================================
    # CRYPTO_DAILY - 24/7 crypto daily data
    # =========================================================================
    "crypto-historical-eod-full": "crypto_daily",
    "crypto-historical-eod-light": "crypto_daily",
    "crypto-open-close": "crypto_daily",
    
    # =========================================================================
    # CRYPTO_INTRADAY - Sub-daily crypto bars
    # =========================================================================
    "crypto-historical-1min": "crypto_intraday",
    "crypto-historical-5min": "crypto_intraday",
    "crypto-historical-1hour": "crypto_intraday",
    
    # =========================================================================
    # FOREX_DAILY - Daily forex data
    # =========================================================================
    "forex-historical-eod-full": "forex_daily",
    "forex-historical-eod-light": "forex_daily",
    
    # =========================================================================
    # FOREX_INTRADAY - Sub-daily forex bars
    # =========================================================================
    "forex-historical-1min": "forex_intraday",
    "forex-historical-5min": "forex_intraday",
    "forex-historical-1hour": "forex_intraday",
    
    # =========================================================================
    # COMMODITY_DAILY - Daily commodity data
    # =========================================================================
    "commodities-historical-eod-full": "commodity_daily",
    "commodities-historical-eod-light": "commodity_daily",
    
    # =========================================================================
    # COMMODITY_INTRADAY - Sub-daily commodity bars
    # =========================================================================
    "commodities-historical-1min": "commodity_intraday",
    "commodities-historical-5min": "commodity_intraday",
    "commodities-historical-1hour": "commodity_intraday",
    
    # =========================================================================
    # OPTIONS_CHAIN - Per-underlying options data
    # =========================================================================
    "stock-option-contracts": "options_chain",
    "stock-expiry-breakdown": "options_chain",
    "stock-greek-exposure": "options_chain",
    "stock-greek-exposure-by-expiry": "options_chain",
    "stock-greek-exposure-by-strike": "options_chain",
    "stock-greek-exposure-by-strike-expiry": "options_chain",
    "stock-oi-change": "options_chain",
    "stock-oi-per-expiry": "options_chain",
    "stock-oi-per-strike": "options_chain",
    "stock-option-price-levels": "options_chain",
    "stock-options-volume": "options_chain",
    "stock-volume-oi-per-expiry": "options_chain",
    "stock-spot-exposures-expiry-strike": "options_chain",
    "stock-spot-exposures-strike": "options_chain",
    
    # =========================================================================
    # OPTIONS_FLOW - Options flow/order data
    # =========================================================================
    "flow-alerts": "options_flow",
    "stock-flow-recent": "options_flow",
    "stock-flow-per-expiry": "options_flow",
    "stock-flow-per-strike": "options_flow",
    "stock-flow-per-strike-intraday": "options_flow",
    "stock-greek-flow": "options_flow",
    "net-flow-expiry": "options_flow",
    "screener-option-contracts": "options_flow",
    
    # =========================================================================
    # OPTIONS_MARKET - Market-wide options data
    # =========================================================================
    "market-oi-change": "options_market",
    "market-total-options-volume": "options_market",
    
    # =========================================================================
    # POLYGON OPTIONS
    # =========================================================================
    "options-contracts-list": "options_chain",
    "options-aggregates-range": "options_contract",
    "options-prev-close": "options_contract",
    "options-indicator-sma": "options_contract",
    "options-indicator-ema": "options_contract",
    "options-indicator-rsi": "options_contract",
    "options-indicator-macd": "options_contract",
    
    # =========================================================================
    # POLYGON REFERENCE
    # =========================================================================
    "crypto-tickers": "market_wide",
    "crypto-ticker-detail": "snapshot",
    "forex-tickers": "market_wide",
    "forex-ticker-detail": "snapshot",
    
    # =========================================================================
    # ETF DATA
    # =========================================================================
    "etf-asset-exposure": "snapshot",
    
    # =========================================================================
    # EXECUTIVE DATA
    # =========================================================================
    "key-executives": "snapshot",
    
    # =========================================================================
    # NEW FMP - INSTITUTIONAL/OWNERSHIP
    # =========================================================================
    "institutional-holder": "year_quarter_indexed",
    "institutional-ownership-dates": "event_list",
    "institutional-ownership-extract": "event_list",
    "institutional-ownership-extract-analytics-holder": "event_list",
    "institutional-ownership-holder-industry-breakdown": "snapshot",
    "institutional-ownership-holder-performance-summary": "snapshot",
    "institutional-ownership-industry-summary": "snapshot",
    "institutional-ownership-symbol-positions-summary": "snapshot",
    "funds-disclosure": "event_list",
    "funds-disclosure-dates": "event_list",
    "funds-disclosure-holders-search": "event_list",
    "insider-trading-reporting-name": "event_list",
    "mergers-acquisitions-search": "event_list",
    
    # =========================================================================
    # NEW FMP - TECHNICAL INDICATORS
    # =========================================================================
    "technical-indicator-sma": "daily_ohlcv",
    "technical-indicator-ema": "daily_ohlcv",
    "technical-indicator-rsi": "daily_ohlcv",
    "technical-indicator-bbands": "daily_ohlcv",
    "technical-indicator-stoch": "daily_ohlcv",
    
    # =========================================================================
    # NEW FMP - DCF & HISTORICAL PE
    # =========================================================================
    "dcf-bulk": "snapshot",
    "historical-sector-pe": "daily_ohlcv",
    "historical-industry-pe": "daily_ohlcv",
    
    # =========================================================================
    # NEW FMP - CONGRESS BY NAME
    # =========================================================================
    "senate-trades-by-name": "event_list",
    "house-trades-by-name": "event_list",
    
    # =========================================================================
    # NEW FMP - ETF
    # =========================================================================
    "etf-holdings": "snapshot",
    "etf-info": "snapshot",
    "etf-sector-weightings": "snapshot",
    "etf-country-weightings": "snapshot",
    
    # =========================================================================
    # NEW UW - ETF
    # =========================================================================
    "etf-inflow-outflow": "event_list",
    
    # =========================================================================
    # NEW UW - OPTIONS
    # =========================================================================
    "option-contract-flow": "options_flow",
    "option-contract-historic": "options_contract",
    "option-contract-intraday": "options_contract",
    "option-contract-volume-profile": "options_contract",
    "stock-option-chains": "options_chain",
    "stock-atm-chains": "options_chain",
    "stock-greek-flow-by-expiry": "options_flow",
    "group-greek-flow": "options_flow",
    "group-greek-flow-by-expiry": "options_flow",
    
    # =========================================================================
    # NEW UW - MARKET
    # =========================================================================
    "market-correlations": "market_wide",
    "market-spike": "market_wide",
    "sector-tide": "market_wide",
    "seasonality-month-performers": "market_wide",
    
    # =========================================================================
    # NEW UW - INSTITUTIONAL
    # =========================================================================
    "institution-holdings": "event_list",
    "institution-sectors": "snapshot",
    
    # =========================================================================
    # NEW POLYGON - CRYPTO
    # =========================================================================
    "crypto-aggregates-grouped": "crypto_daily",
    "crypto-aggregates-prev": "snapshot",
    "crypto-aggregates-range": "crypto_daily",
    "crypto-indicator-sma": "crypto_daily",
    "crypto-indicator-ema": "crypto_daily",
    "crypto-indicator-rsi": "crypto_daily",
    "crypto-indicator-macd": "crypto_daily",
    "crypto-last-trade": "snapshot",
    "crypto-snapshot-market": "snapshot",
    "crypto-snapshot-movers": "snapshot",
    "crypto-snapshot-single": "snapshot",
    "crypto-trades": "event_list",
    
    # =========================================================================
    # NEW POLYGON - FOREX
    # =========================================================================
    "forex-aggregates-grouped": "forex_daily",
    "forex-aggregates-prev": "snapshot",
    "forex-aggregates-range": "forex_daily",
    "forex-indicator-sma": "forex_daily",
    "forex-indicator-ema": "forex_daily",
    "forex-indicator-rsi": "forex_daily",
    "forex-indicator-macd": "forex_daily",
    "forex-quotes": "snapshot",
    "forex-snapshot-market": "snapshot",
    "forex-snapshot-movers": "snapshot",
    "forex-snapshot-single": "snapshot",
    "forex-conversion": "snapshot",
    
    # =========================================================================
    # NEW POLYGON - OPTIONS
    # =========================================================================
    "options-contract-detail": "snapshot",
    "options-last-trade": "snapshot",
    "options-open-close": "snapshot",
    "options-quotes": "snapshot",
    "options-snapshot-chain": "options_chain",
    "options-snapshot-single": "snapshot",
    "options-trades": "event_list",
}


# =============================================================================
# STRUCTURE TYPE TO COMPATIBILITY GROUP
# =============================================================================
# Maps structure types to compatibility groups for merging.
# Datasets in the same compatibility group can be merged together.

STRUCTURE_TO_COMPATIBILITY_GROUP: Dict[str, str] = {
    # SNAPSHOT group - can pivot by symbol, no time dimension
    "snapshot": "snapshot",
    
    # FISCAL group - join on calendarYear + period
    "fiscal_period_series": "fiscal_period",
    
    # DAILY_TRADING group - join on date
    "daily_ohlcv": "daily_trading",
    
    # INTRADAY group - join on datetime
    "intraday": "intraday",
    
    # EVENT group - isolated, no merge (irregular intervals)
    "event_list": "event_isolated",
    "year_quarter_indexed": "event_isolated",
    
    # MARKET_WIDE group - isolated, no symbol filter
    "market_wide": "market_wide_isolated",
    
    # SEC FILINGS group
    "sec_filing_search": "sec_filings",
    
    # CRYPTO groups - join on date (24/7 trading)
    "crypto_daily": "crypto_daily",
    "crypto_intraday": "crypto_intraday",
    
    # FOREX groups
    "forex_daily": "forex_daily",
    "forex_intraday": "forex_intraday",
    
    # COMMODITIES groups
    "commodity_daily": "commodity_daily",
    "commodity_intraday": "commodity_intraday",
    
    # OPTIONS groups - complex, usually isolated
    "options_chain": "options_chain",
    "options_flow": "options_flow",
    "options_contract": "options_contract",
    "options_market": "options_market_isolated",
}


# =============================================================================
# STRUCTURE TYPE TO TIME KEY
# =============================================================================
# Maps structure types to their primary time key(s) for joining.
# None means no time dimension (snapshot data).

STRUCTURE_TO_TIME_KEY: Dict[str, Optional[str]] = {
    # No time dimension
    "snapshot": None,
    
    # Fiscal period indexed
    "fiscal_period_series": "calendarYear,period",
    
    # Date indexed
    "daily_ohlcv": "date",
    "event_list": "date",
    "market_wide": None,  # Snapshot data - no time dimension for joining
    "sec_filing_search": "filingDate",
    
    # Datetime indexed
    "intraday": "date",
    
    # Year-quarter indexed
    "year_quarter_indexed": "year,quarter",
    
    # Crypto/Forex/Commodity date indexed
    "crypto_daily": "date",
    "crypto_intraday": "date",
    "forex_daily": "date",
    "forex_intraday": "date",
    "commodity_daily": "date",
    "commodity_intraday": "date",
    
    # Options - complex keys
    "options_chain": None,  # Multi-dimensional: strike × expiry
    "options_flow": "date",
    "options_contract": "date",
    "options_market": "date",
}


# =============================================================================
# ENDPOINT TO CARDINALITY MAPPING
# =============================================================================
# Defines whether an endpoint supports single, multiple, or no symbols.
# - "single": One symbol per request (requires N parallel requests for N symbols)
# - "multi": Comma-separated symbols supported (batch in one request)
# - "none": No symbol parameter (market-wide data)

ENDPOINT_TO_CARDINALITY: Dict[str, str] = {
    # =========================================================================
    # MULTI - Batch-capable (comma-separated symbols)
    # =========================================================================
    "company-quote": "multi",
    "company-profile": "multi",
    "ratios-ttm": "multi",
    "key-metrics-ttm": "multi",
    "dcf": "multi",
    "discounted-cash-flow": "multi",
    "stock-price-change": "multi",
    "crypto-quote": "multi",
    "crypto-quote-short": "multi",
    "forex-quote": "multi",
    "forex-quote-short": "multi",
    "commodities-quote": "multi",
    "commodities-quote-short": "multi",
    "snapshot-unified": "multi",
    
    # =========================================================================
    # SINGLE - One symbol per request
    # =========================================================================
    "income-statement": "single",
    "income-statement-growth": "single",
    "balance-sheet-statement": "single",
    "cash-flow-statement": "single",
    "key-metrics": "single",
    "ratios": "single",
    "financial-growth": "single",
    "enterprise-values": "single",
    "analyst-estimates": "single",
    "financial-estimates": "single",
    "financial-statement-full-as-reported": "single",
    "financial-reports-json": "single",
    "historical-price-full": "single",
    "historical-chart-1day": "single",
    "historical-chart-1min": "single",
    "historical-chart-5min": "single",
    "historical-chart-15min": "single",
    "historical-chart-30min": "single",
    "historical-chart-1hour": "single",
    "historical-chart-4hour": "single",
    "sec-filings": "single",
    "press-releases": "single",
    "stock-news": "single",
    "stock-dividend": "single",
    "stock-split": "single",
    "shares-float": "single",
    "market-capitalization": "single",
    "grade": "single",
    "grades": "single",
    "grades-consensus": "single",
    "grades-historical": "single",
    "grades-news": "single",
    "grades-latest-news": "single",
    "rating": "single",
    "ratings-historical": "single",
    "ratings-snapshot": "single",
    "historical-rating": "single",
    "price-target": "single",
    "price-target-consensus": "single",
    "price-target-summary": "single",
    "price-target-news": "single",
    "price-target-latest-news": "single",
    "levered-dcf": "single",
    "advanced-dcf": "single",
    "custom-discounted-cash-flow": "single",
    "custom-levered-discounted-cash-flow": "single",
    "insider-trading": "single",
    "insider-trading-latest": "single",
    "insider-trading-statistics": "single",
    "insider-trading-transaction-type": "single",
    "institutional-ownership-latest": "single",
    "mutual-fund-holder": "single",
    "etf-holder": "single",
    "acquisition-of-beneficial-ownership": "single",
    "funds-disclosure-holders-latest": "single",
    "earning-call-transcript": "single",
    "esg-scores": "single",
    "esg-ratings": "single",
    "esg-disclosures": "single",
    "esg-benchmark": "none",  # Market-wide benchmark, no symbol needed
    "key-executives": "single",
    "crypto-historical-eod-full": "single",
    "crypto-historical-eod-light": "single",
    "crypto-historical-1min": "single",
    "crypto-historical-5min": "single",
    "crypto-historical-1hour": "single",
    "forex-historical-eod-full": "single",
    "forex-historical-eod-light": "single",
    "forex-historical-1min": "single",
    "forex-historical-5min": "single",
    "forex-historical-1hour": "single",
    "commodities-historical-eod-full": "single",
    "commodities-historical-eod-light": "single",
    "commodities-historical-1min": "single",
    "commodities-historical-5min": "single",
    "commodities-historical-1hour": "single",
    "etf-asset-exposure": "single",
    "treasury": "single",
    "senate-trading": "single",
    "house-trades": "single",
    "crypto-open-close": "single",
    "crypto-ticker-detail": "single",
    "forex-ticker-detail": "single",
    # UW Options per-ticker
    "stock-option-contracts": "single",
    "stock-expiry-breakdown": "single",
    "stock-greek-exposure": "single",
    "stock-greek-exposure-by-expiry": "single",
    "stock-greek-exposure-by-strike": "single",
    "stock-greek-exposure-by-strike-expiry": "single",
    "stock-oi-change": "single",
    "stock-oi-per-expiry": "single",
    "stock-oi-per-strike": "single",
    "stock-option-price-levels": "single",
    "stock-options-volume": "single",
    "stock-volume-oi-per-expiry": "single",
    "stock-flow-recent": "single",
    "stock-flow-per-expiry": "single",
    "stock-flow-per-strike": "single",
    "stock-flow-per-strike-intraday": "single",
    "stock-greek-flow": "single",
    "stock-greeks": "single",
    "stock-max-pain": "single",
    "stock-nope": "single",
    "stock-iv-rank": "single",
    "stock-interpolated-iv": "single",
    "stock-volatility-realized": "single",
    "stock-volatility-stats": "single",
    "stock-volatility-term-structure": "single",
    "stock-historical-risk-reversal-skew": "single",
    "stock-spot-exposures-expiry-strike": "single",
    "stock-spot-exposures-strike": "single",
    "net-flow-expiry": "single",
    "institution-ownership": "single",
    "insider-transactions": "single",
    "darkpool-ticker-trades": "single",
    "etf-exposure": "single",
    "etf-tide": "single",
    "etf-weights": "single",
    "shorts-data": "single",
    "shorts-ftds": "single",
    "shorts-interest-float": "single",
    "shorts-volume-ratio": "single",
    "shorts-volume-by-exchange": "single",
    "seasonality-ticker-monthly": "single",
    "seasonality-ticker-year-month": "single",
    "earnings-historical": "single",
    # Polygon per-ticker
    "options-contracts-list": "single",
    "options-aggregates-range": "single",
    "options-prev-close": "single",
    "options-indicator-sma": "single",
    "options-indicator-ema": "single",
    "options-indicator-rsi": "single",
    "options-indicator-macd": "single",
    
    # =========================================================================
    # NONE - Market-wide (no symbol parameter)
    # =========================================================================
    "sector-performance": "none",
    "sector-pe-snapshot": "none",
    "industry-performance": "none",
    "industry-pe-snapshot": "none",
    "biggest-gainers": "none",
    "biggest-losers": "none",
    "most-actives": "none",
    "stock-screener": "none",
    "general-news-latest": "none",
    "stock-news-latest": "none",
    "press-releases-latest": "none",
    "fmp-articles": "none",
    "earning-call-calendar": "none",
    "earnings-confirmed": "none",
    "rss-feed": "none",
    "rss-feed-8k": "none",
    "insider-trading-rss-feed": "none",
    "insider-trading-search": "none",
    "senate-latest": "none",
    "senate-disclosure": "none",
    "house-latest": "none",
    "economic-calendar": "none",
    "market-risk-premium": "none",
    "crypto-list": "none",
    "forex-list": "none",
    "commodities-list": "none",
    "crypto-news": "single",  # Requires 'symbols' param
    "crypto-news-latest": "none",
    "forex-news": "single",   # Requires 'symbols' param
    "forex-news-latest": "none",
    "crypto-batch-quotes": "none",
    "forex-batch-quotes": "none",
    "commodities-batch-quotes": "none",
    "reference-exchanges": "none",
    "reference-conditions": "none",
    "marketstatus-now": "none",
    "marketstatus-upcoming": "none",
    "crypto-tickers": "none",
    "forex-tickers": "none",
    "ipos-disclosure": "none",
    "ipos-prospectus": "none",
    "mergers-acquisitions-latest": "none",
    "institutions-list": "none",
    "market-insider-buy-sells": "none",
    "congress-recent-trades": "none",
    "congress-late-reports": "none",
    "congress-trader-reports": "single",  # Requires 'name' param
    "darkpool-recent-trades": "none",
    "market-sector-etfs": "none",
    "market-tide": "none",
    "market-top-net-impact": "none",
    "market-oi-change": "none",
    "market-total-options-volume": "none",
    "screener-analysts": "none",
    "screener-stocks": "none",
    "screener-option-contracts": "none",
    "seasonality-market": "none",
    "flow-alerts": "none",
    
    # =========================================================================
    # NEW FMP - INSTITUTIONAL/OWNERSHIP
    # =========================================================================
    "institutional-holder": "single",
    "institutional-ownership-dates": "single",
    "institutional-ownership-extract": "single",
    "institutional-ownership-extract-analytics-holder": "single",
    "institutional-ownership-holder-industry-breakdown": "single",
    "institutional-ownership-holder-performance-summary": "single",
    "institutional-ownership-industry-summary": "single",
    "institutional-ownership-symbol-positions-summary": "single",
    "funds-disclosure": "single",
    "funds-disclosure-dates": "single",
    "funds-disclosure-holders-search": "single",  # Requires 'name' param
    "insider-trading-reporting-name": "single",   # Requires 'name' param
    "mergers-acquisitions-search": "single",      # Requires 'name' param
    
    # =========================================================================
    # NEW FMP - TECHNICAL INDICATORS
    # =========================================================================
    "technical-indicator-sma": "single",
    "technical-indicator-ema": "single",
    "technical-indicator-rsi": "single",
    "technical-indicator-bbands": "single",
    "technical-indicator-stoch": "single",
    
    # =========================================================================
    # NEW FMP - DCF & HISTORICAL PE
    # =========================================================================
    "dcf-bulk": "none",
    "historical-sector-pe": "none",
    "historical-industry-pe": "none",
    
    # =========================================================================
    # NEW FMP - CONGRESS BY NAME
    # =========================================================================
    "senate-trades-by-name": "single",  # Requires 'name' param
    "house-trades-by-name": "single",   # Requires 'name' param
    
    # =========================================================================
    # NEW FMP - ETF
    # =========================================================================
    "etf-holdings": "single",
    "etf-info": "single",
    "etf-sector-weightings": "single",
    "etf-country-weightings": "single",
    
    # =========================================================================
    # NEW UW - ETF
    # =========================================================================
    "etf-inflow-outflow": "single",
    
    # =========================================================================
    # NEW UW - OPTIONS
    # =========================================================================
    "option-contract-flow": "single",
    "option-contract-historic": "single",
    "option-contract-intraday": "single",
    "option-contract-volume-profile": "single",
    "stock-option-chains": "single",
    "stock-atm-chains": "single",
    "stock-greek-flow-by-expiry": "single",
    "group-greek-flow": "none",
    "group-greek-flow-by-expiry": "none",
    
    # =========================================================================
    # NEW UW - MARKET
    # =========================================================================
    "market-correlations": "none",
    "market-spike": "none",
    "sector-tide": "none",
    "seasonality-month-performers": "none",
    
    # =========================================================================
    # NEW UW - INSTITUTIONAL
    # =========================================================================
    "institution-holdings": "single",
    "institution-sectors": "single",  # Requires 'name' param
    
    # =========================================================================
    # NEW POLYGON - CRYPTO
    # =========================================================================
    "crypto-aggregates-grouped": "none",
    "crypto-aggregates-prev": "single",
    "crypto-aggregates-range": "single",
    "crypto-indicator-sma": "single",
    "crypto-indicator-ema": "single",
    "crypto-indicator-rsi": "single",
    "crypto-indicator-macd": "single",
    "crypto-last-trade": "single",
    "crypto-snapshot-market": "none",
    "crypto-snapshot-movers": "none",
    "crypto-snapshot-single": "single",
    "crypto-trades": "single",
    
    # =========================================================================
    # NEW POLYGON - FOREX
    # =========================================================================
    "forex-aggregates-grouped": "none",
    "forex-aggregates-prev": "single",
    "forex-aggregates-range": "single",
    "forex-indicator-sma": "single",
    "forex-indicator-ema": "single",
    "forex-indicator-rsi": "single",
    "forex-indicator-macd": "single",
    "forex-quotes": "single",
    "forex-snapshot-market": "none",
    "forex-snapshot-movers": "none",
    "forex-snapshot-single": "single",
    "forex-conversion": "single",
    
    # =========================================================================
    # NEW POLYGON - OPTIONS
    # =========================================================================
    "options-contract-detail": "single",
    "options-last-trade": "single",
    "options-open-close": "single",
    "options-quotes": "single",
    "options-snapshot-chain": "single",
    "options-snapshot-single": "single",
    "options-trades": "single",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_structure_type_for_endpoint(endpoint: str) -> str:
    """Get the structure type for an endpoint."""
    return ENDPOINT_TO_STRUCTURE_TYPE.get(endpoint, "unknown")


def get_compatibility_group_for_endpoint(endpoint: str) -> str:
    """Get the compatibility group for an endpoint."""
    structure_type = get_structure_type_for_endpoint(endpoint)
    return STRUCTURE_TO_COMPATIBILITY_GROUP.get(structure_type, "unknown")


def get_time_key_for_endpoint(endpoint: str) -> Optional[str]:
    """Get the time key for an endpoint."""
    structure_type = get_structure_type_for_endpoint(endpoint)
    return STRUCTURE_TO_TIME_KEY.get(structure_type)


def get_cardinality_for_endpoint(endpoint: str) -> str:
    """Get the cardinality for an endpoint (single/multi/none)."""
    return ENDPOINT_TO_CARDINALITY.get(endpoint, "single")


# =============================================================================
# ENDPOINT EQUIVALENCE - Dynamic cross-asset join matching
# =============================================================================

def compute_field_overlap(fields1: List[str], fields2: List[str]) -> float:
    """
    Compute Jaccard similarity between two field sets.
    
    Returns value between 0.0 and 1.0.
    """
    if not fields1 or not fields2:
        return 0.0
    
    # Normalize field names for comparison (lowercase, strip prefixes)
    def normalize(f: str) -> str:
        f = f.lower()
        # Strip common prefixes that differ between asset types
        for prefix in ['adj', 'adjusted']:
            if f.startswith(prefix):
                f = f[len(prefix):].lstrip('_')
        return f
    
    set1 = {normalize(f) for f in fields1}
    set2 = {normalize(f) for f in fields2}
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def compute_endpoint_similarity(
    ep1: str,
    ep2: str,
    ep1_fields: List[str],
    ep2_fields: List[str],
) -> float:
    """
    Compute similarity score between two endpoints.
    
    Criteria:
    - Same granularity is REQUIRED (returns 0.0 if different)
      This allows crypto_daily ≈ daily_ohlcv (both are 'daily' granularity)
    - Same category adds 0.3 to score
    - Field overlap (Jaccard) contributes up to 0.7
    
    Returns value between 0.0 and 1.0.
    """
    # Hard requirement: same granularity (not structure type)
    # This allows crypto_daily and daily_ohlcv to be equivalent
    st1 = get_structure_type_for_endpoint(ep1)
    st2 = get_structure_type_for_endpoint(ep2)
    
    gran1 = _structure_to_granularity(st1)
    gran2 = _structure_to_granularity(st2)
    
    if gran1 != gran2 or gran1 == "unknown" or gran2 == "unknown":
        return 0.0
    
    score = 0.0
    
    # Category match bonus
    cat1 = get_category_for_endpoint(ep1)
    cat2 = get_category_for_endpoint(ep2)
    if cat1 == cat2:
        score += 0.3
    
    # Field overlap (weighted up to 0.7)
    field_overlap = compute_field_overlap(ep1_fields, ep2_fields)
    score += field_overlap * 0.7
    
    return score


def get_endpoint_fields_from_registry(endpoint: str) -> List[str]:
    """
    Get field names for an endpoint from the canvas field registry.
    
    Falls back to empty list if registry not available.
    """
    try:
        from core.canvas.canvas_field_registry import CanvasFieldRegistry
        registry = CanvasFieldRegistry()
        return registry.get_fields_for_endpoint(endpoint)
    except Exception:
        return []


def compute_endpoint_equivalence(
    object_types: List[str],
    threshold: float = 0.5,
) -> List[Dict[str, any]]:
    """
    Compute equivalence groups for endpoints across multiple object types.
    
    Finds endpoints that serve the same semantic purpose across different
    asset types (e.g., historical-price-full for equity = crypto-historical-eod-full
    for crypto).
    
    Args:
        object_types: List of object types to find equivalences for (e.g., ["equity", "crypto", "forex"])
        threshold: Minimum similarity score to consider endpoints equivalent (0.0-1.0)
    
    Returns:
        List of equivalence groups, each containing:
        {
            "canonical": str,  # Representative endpoint name
            "endpoints": {object_type: endpoint_name},  # Mapping per object type
            "structure_type": str,
            "category": str,
            "granularity": str,  # "daily", "quarterly", "snapshot", etc.
            "avg_field_overlap": float,
        }
    """
    if len(object_types) < 2:
        # Single object type - return all endpoints as individual groups
        endpoints = get_endpoints_for_object_type(object_types[0]) if object_types else []
        return [
            {
                "canonical": ep,
                "endpoints": {object_types[0]: ep},
                "structure_type": get_structure_type_for_endpoint(ep),
                "category": get_category_for_endpoint(ep),
                "granularity": _structure_to_granularity(get_structure_type_for_endpoint(ep)),
                "avg_field_overlap": 1.0,
            }
            for ep in endpoints
        ]
    
    # Get endpoints for each object type
    endpoints_by_type: Dict[str, List[str]] = {}
    for ot in object_types:
        endpoints_by_type[ot] = get_endpoints_for_object_type(ot)
    
    # Cache field lookups
    fields_cache: Dict[str, List[str]] = {}
    def get_fields(ep: str) -> List[str]:
        if ep not in fields_cache:
            fields_cache[ep] = get_endpoint_fields_from_registry(ep)
        return fields_cache[ep]
    
    # Find equivalence groups by comparing endpoints across types
    equivalence_groups: List[Dict[str, any]] = []
    used_endpoints: Dict[str, set] = {ot: set() for ot in object_types}
    
    # Start with the first object type as the anchor
    anchor_type = object_types[0]
    other_types = object_types[1:]
    
    for anchor_ep in endpoints_by_type[anchor_type]:
        if anchor_ep in used_endpoints[anchor_type]:
            continue
        
        anchor_fields = get_fields(anchor_ep)
        anchor_structure = get_structure_type_for_endpoint(anchor_ep)
        anchor_category = get_category_for_endpoint(anchor_ep)
        
        # Find best matching endpoint in each other type
        group_endpoints: Dict[str, str] = {anchor_type: anchor_ep}
        field_overlaps: List[float] = []
        all_matched = True
        
        for other_type in other_types:
            best_match = None
            best_score = 0.0
            best_overlap = 0.0
            
            for candidate_ep in endpoints_by_type[other_type]:
                if candidate_ep in used_endpoints[other_type]:
                    continue
                
                candidate_fields = get_fields(candidate_ep)
                similarity = compute_endpoint_similarity(
                    anchor_ep, candidate_ep, anchor_fields, candidate_fields
                )
                
                if similarity >= threshold and similarity > best_score:
                    best_score = similarity
                    best_match = candidate_ep
                    best_overlap = compute_field_overlap(anchor_fields, candidate_fields)
            
            if best_match:
                group_endpoints[other_type] = best_match
                field_overlaps.append(best_overlap)
            else:
                all_matched = False
                break
        
        # Only add group if ALL object types have a matching endpoint
        if all_matched and len(group_endpoints) == len(object_types):
            # Mark endpoints as used
            for ot, ep in group_endpoints.items():
                used_endpoints[ot].add(ep)
            
            equivalence_groups.append({
                "canonical": anchor_ep,  # Use anchor as canonical name
                "endpoints": group_endpoints,
                "structure_type": anchor_structure,
                "category": anchor_category,
                "granularity": _structure_to_granularity(anchor_structure),
                "avg_field_overlap": sum(field_overlaps) / len(field_overlaps) if field_overlaps else 1.0,
            })
    
    return equivalence_groups


def _structure_to_granularity(structure_type: str) -> str:
    """Map structure type to user-friendly granularity name."""
    mapping = {
        "snapshot": "snapshot",
        "daily_ohlcv": "daily",
        "intraday": "intraday",
        "fiscal_period_series": "quarterly",
        "event_list": "event",
        "crypto_daily": "daily",
        "crypto_intraday": "intraday",
        "forex_daily": "daily",
        "forex_intraday": "intraday",
        "commodity_daily": "daily",
        "market_wide": "snapshot",
    }
    return mapping.get(structure_type, "unknown")


def get_joinable_granularities(object_types: List[str]) -> Dict[str, List[str]]:
    """
    Get all available granularities across endpoints for the given object types.
    
    Returns dict mapping granularity -> list of endpoint names that have that granularity.
    Useful for detecting mixed granularity situations.
    """
    granularities: Dict[str, List[str]] = {}
    
    for ot in object_types:
        for ep in get_endpoints_for_object_type(ot):
            st = get_structure_type_for_endpoint(ep)
            gran = _structure_to_granularity(st)
            if gran not in granularities:
                granularities[gran] = []
            granularities[gran].append(ep)
    
    return granularities


# =============================================================================
# TIME-KEY GROUP FUNCTIONS
# =============================================================================

def get_time_key_group(structure_type: str) -> str:
    """
    Map structure type to joinable time-key group.
    
    Groups:
    - "date": Daily/intraday endpoints joinable on date field
    - "fiscal_period": Quarterly/annual endpoints joinable on period
    - "snapshot": Point-in-time data, NOT joinable on time
    
    Returns group name.
    """
    time_key = STRUCTURE_TO_TIME_KEY.get(structure_type)
    
    if time_key is None:
        return "snapshot"
    
    # Fiscal period group: contains period, quarter, or Year in time key
    if any(k in time_key for k in ["period", "quarter", "Year"]):
        return "fiscal_period"
    
    # Everything else with a time key is date-based
    return "date"


def get_endpoint_time_info(endpoint: str) -> Dict[str, str]:
    """
    Get time-related metadata for an endpoint.
    
    Returns dict with:
    - structure_type: raw structure type
    - time_key: the field(s) used for time indexing
    - time_group: joinable group (date, fiscal_period, snapshot)
    - granularity: user-friendly granularity name
    """
    structure_type = get_structure_type_for_endpoint(endpoint)
    time_key = STRUCTURE_TO_TIME_KEY.get(structure_type)
    time_group = get_time_key_group(structure_type)
    granularity = _structure_to_granularity(structure_type)
    
    return {
        "structure_type": structure_type,
        "time_key": time_key,
        "time_group": time_group,
        "granularity": granularity,
    }


def get_endpoints_by_time_group(object_type: str) -> Dict[str, List[Dict[str, any]]]:
    """
    Get all endpoints for an object type, grouped by time-key compatibility.
    
    Returns dict mapping time_group -> list of endpoint info dicts:
    {
        "date": [
            {"endpoint": "historical-price-full", "granularity": "daily", "category": "...", "fields": [...], "required_params": [...]},
            ...
        ],
        "fiscal_period": [
            {"endpoint": "income-statement", "granularity": "quarterly", ...},
            ...
        ],
        "snapshot": [
            {"endpoint": "company-quote", "granularity": "snapshot", ...},
            ...
        ]
    }
    """
    from core.canvas.canvas_field_registry import get_field_registry
    
    endpoints = get_endpoints_for_object_type(object_type)
    registry = get_field_registry()
    
    grouped: Dict[str, List[Dict[str, any]]] = {
        "date": [],
        "fiscal_period": [],
        "snapshot": [],
    }
    
    for ep in endpoints:
        structure_type = get_structure_type_for_endpoint(ep)
        time_group = get_time_key_group(structure_type)
        granularity = _structure_to_granularity(structure_type)
        category = get_category_for_endpoint(ep)
        fields = get_endpoint_fields_from_registry(ep)
        time_key = STRUCTURE_TO_TIME_KEY.get(structure_type)
        
        # Get required_params and source from registry
        ep_meta = registry.get_endpoint_metadata(ep)
        required_params = ep_meta.get("required_params", [])
        # Filter out apikey and symbol-like params
        required_params = [p for p in required_params if p.lower() not in ('apikey', 'symbol', 'ticker')]
        source = ep_meta.get("source", "fmp")
        
        endpoint_info = {
            "endpoint": ep,
            "granularity": granularity,
            "category": category,
            "fields": fields,
            "structure_type": structure_type,
            "time_key": time_key,
            "time_group": time_group,
            "required_params": required_params,
            "source": source,
        }
        
        grouped[time_group].append(endpoint_info)
    
    return grouped


def get_endpoints_by_time_group_multi(object_types: List[str]) -> Dict[str, Dict[str, List[Dict[str, any]]]]:
    """
    Get endpoints grouped by time-key for multiple object types.
    
    Returns:
    {
        "equity": {
            "date": [...],
            "fiscal_period": [...],
            "snapshot": [...]
        },
        "forex": {
            "date": [...],
            ...
        }
    }
    """
    result = {}
    for ot in object_types:
        result[ot] = get_endpoints_by_time_group(ot)
    return result


def detect_join_strategy(
    selected_endpoints: Dict[str, str]
) -> Dict[str, any]:
    """
    Analyze selected endpoints across object types and determine join strategy.
    
    Args:
        selected_endpoints: Dict mapping object_type -> endpoint name
        
    Returns dict with:
    - strategy: "same_group" | "cross_group" | "incompatible"
    - time_groups: set of time groups involved
    - granularities: set of granularities involved
    - common_time_key: the time key to join on (if compatible)
    - needs_aggregation: bool
    - aggregation_target: suggested target granularity if needs_aggregation
    """
    if not selected_endpoints:
        return {"strategy": "incompatible", "error": "No endpoints selected"}
    
    time_groups = set()
    granularities = set()
    time_keys = set()
    
    for obj_type, endpoint in selected_endpoints.items():
        info = get_endpoint_time_info(endpoint)
        time_groups.add(info["time_group"])
        granularities.add(info["granularity"])
        if info["time_key"]:
            time_keys.add(info["time_key"])
    
    # Check for snapshot endpoints
    if "snapshot" in time_groups:
        if len(time_groups) == 1:
            # All snapshot - can stack by symbol (no time join, but valid combination)
            return {
                "strategy": "snapshot_stack",
                "time_groups": list(time_groups),
                "granularities": list(granularities),
                "common_time_key": None,
                "needs_aggregation": False,
                "aggregation_target": None,
            }
        else:
            # Mix of snapshot and time-indexed - truly incompatible
            return {
                "strategy": "incompatible",
                "time_groups": list(time_groups),
                "granularities": list(granularities),
                "error": "Cannot join snapshot endpoints with time-series endpoints",
            }
    
    # All endpoints have time keys
    if len(time_groups) == 1:
        # Same time group
        group = list(time_groups)[0]
        needs_aggregation = len(granularities) > 1
        
        # Determine common time key
        common_key = "date" if group == "date" else "period"
        
        # Determine aggregation target (coarsest granularity)
        granularity_order = ["intraday", "daily", "weekly", "monthly", "quarterly", "annual"]
        sorted_grans = sorted(granularities, key=lambda g: granularity_order.index(g) if g in granularity_order else 99)
        target = sorted_grans[-1] if needs_aggregation else sorted_grans[0]
        
        return {
            "strategy": "same_group",
            "time_groups": list(time_groups),
            "granularities": list(granularities),
            "common_time_key": common_key,
            "needs_aggregation": needs_aggregation,
            "aggregation_target": target if needs_aggregation else None,
        }
    else:
        # Cross-group (date + fiscal_period)
        # Aggregation required: daily -> quarterly or quarterly -> daily expansion
        granularity_order = ["intraday", "daily", "weekly", "monthly", "quarterly", "annual"]
        sorted_grans = sorted(granularities, key=lambda g: granularity_order.index(g) if g in granularity_order else 99)
        
        return {
            "strategy": "cross_group",
            "time_groups": list(time_groups),
            "granularities": list(granularities),
            "common_time_key": "date",  # Will need to map fiscal periods to dates
            "needs_aggregation": True,
            "aggregation_target": sorted_grans[-1],  # Coarsest wins
        }