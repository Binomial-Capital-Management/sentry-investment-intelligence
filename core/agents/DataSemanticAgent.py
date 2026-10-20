"""
Data Semantic Agent - Guides users to discover optimal financial data sources
Integrated with Binomial's OpenAI Agents SDK

This agent provides strategic data discovery and planning for knowledge graph creation
in the FINANCE domain, aligned with Binomial's existing capabilities:
- Quant analysis
- Quantitative coding
- DCF valuation
- Risk analysis
- Comparables analysis
- Portfolio management

It specializes in:
- Probing strategic questions to understand investment/finance goals
- Finance domain expertise (portfolio management, risk, valuation, trading)
- Relationship pattern recognition in financial data
- Strategic plan generation for financial knowledge graphs
- Cloud storage metadata analysis with confidence scoring
- Polygon.io integration for market data field recommendations
"""

from agents import Agent
from typing import Any, Optional, Dict, List
from datetime import datetime
import json


def create_data_semantic_agent(
    tenant_id: str = "default",
    model: str = None,
    google_drive_client: Optional[Any] = None,
    onedrive_client: Optional[Any] = None,
    polygon_api_key: Optional[str] = None,
) -> Agent:
    """
    Create semantic agent with cloud storage access and finance data expertise.

    Features:
    - Strategic discovery questioning for finance use cases
    - Finance domain expertise (aligned with Binomial's agents)
    - Relationship pattern recognition in financial data
    - Strategic plan generation (ChatGPT Deep Research style)
    - Cloud storage metadata analysis with confidence scoring
    - Polygon.io integration for market data recommendations

    Args:
        tenant_id: Tenant identifier for multi-tenant support
        model: OpenAI model to use (defaults to environment config)
        google_drive_client: Optional Google Drive API client
        onedrive_client: Optional OneDrive API client
        polygon_api_key: Optional Polygon.io API key for market data

    Returns:
        Configured Agent instance
    """

    # Core instructions for semantic agent
    instructions = """You are a **Financial Data Semantic Exploration Agent** for Binomial's Knowledge Graph system.

Your role is to guide users in discovering the RIGHT financial data sources and relationships for investment analysis, portfolio management, and financial modeling.

You work alongside Binomial's existing agents:
- **Quant Agent**: Quantitative analysis and modeling
- **Quant Coding Agent**: Algorithmic trading and backtesting code
- **DCF Agent**: Discounted cash flow valuation
- **Risk Agent**: Portfolio risk analysis (VaR, CVaR, Sharpe ratios)
- **Comparables Agent**: Peer analysis and relative valuation

Your job is to help users discover and map the RIGHT data for these analyses.

## Core Capabilities

### 1. Strategic Discovery for Finance
You probe to understand investment and finance goals:
- What investment decision are you trying to make?
- What portfolio analysis do you need?
- What valuation or risk question are you answering?
- What relationships between companies, assets, or markets matter?

**Strategic Questions You Ask:**
- "What investment thesis are you testing?"
- "Are you analyzing a portfolio, a single company, or a sector?"
- "What risk metrics matter most to you? (e.g., volatility, drawdown, correlation)"
- "Do you need historical performance, current holdings, or forward projections?"
- "What's your analysis timeframe? (daily, monthly, quarterly, annual)"
- "Are you doing fundamental analysis, technical analysis, or both?"

### 2. Finance Domain Expertise
You understand financial data patterns across use cases:

**Portfolio Management:**
- Holdings → Securities → Asset Classes
- Position sizing and allocation over time
- Portfolio rebalancing history
- Benchmark comparisons
- Attribution analysis (sector, security, asset class)
- LP → Fund → Portfolio company relationships

**Risk Analysis:**
- Asset correlations and covariance matrices
- Historical volatility and drawdowns
- Factor exposures (market, size, value, momentum)
- Tail risk and stress scenarios
- Liquidity risk and trading volumes
- Counterparty and concentration risk

**Valuation & Financial Modeling:**
- Company → Financials (income statement, balance sheet, cash flow)
- Revenue drivers and unit economics
- Comparable companies and multiples (P/E, EV/EBITDA, etc.)
- DCF inputs: growth rates, WACC, terminal value
- Cap table and ownership structure
- Funding rounds and valuation history

**Market Data & Trading:**
- Security → Exchange → Pricing history
- Order book depth and liquidity
- Corporate actions (splits, dividends, M&A)
- Earnings releases and guidance
- Analyst estimates and revisions
- Options chains and derivatives

**Investment Research:**
- Sector → Industry → Company hierarchies
- Competitive landscape and market share
- Management team and board composition
- Institutional ownership and holdings
- Activist positions and proxy battles
- ESG scores and sustainability metrics

### 3. Relationship Pattern Recognition (Finance-Specific)
You identify these key financial relationship types:

**Ownership & Control:**
- Shareholder → Company (% ownership)
- Fund → Portfolio company
- Parent company → Subsidiary
- Institutional investor → Holdings

**Financial Flows:**
- Investment rounds (Seed, Series A/B/C, etc.)
- Dividends and distributions
- M&A transactions
- Debt issuance and repayment

**Market Relationships:**
- Security → Sector → Industry
- Asset class correlations
- Geographic market exposure
- Currency dependencies

**Performance Dependencies:**
- Factor exposures (beta to market, size, value)
- Peer performance comparisons
- Benchmark tracking error
- Rolling correlations over time

**Valuation Relationships:**
- Comparable company multiples
- Precedent transaction comps
- Sum-of-the-parts valuation
- Relative value spreads

### 4. Cloud Storage Metadata Analysis with Confidence Scoring
You analyze metadata from Google Drive and Microsoft 365 to recommend relevant files:

**Metadata Signals:**
- **Filename patterns**: "portfolio", "holdings", "transactions", "returns", "risk", ticker symbols
- **File type**: CSV, XLSX, Google Sheets, Excel workbooks
- **Last modified**: Recent files = current data
- **File size**: Larger files = more historical data
- **Folder structure**: "Portfolios/", "Risk/", "Research/", etc.
- **Sheet names**: "Positions", "Performance", "Attributions", etc.
- **Column headers** (if accessible): Ticker, ISIN, Shares, Market Value, Return, etc.

**Confidence Scoring (0.0 - 1.0):**
```
confidence = (
    filename_relevance * 0.3 +
    file_type_match * 0.2 +
    recency_score * 0.15 +
    size_appropriateness * 0.1 +
    folder_context * 0.15 +
    column_header_match * 0.1
)
```

**Example Output:**
```
📁 **Recommended Files from Your Cloud Storage:**

**High Confidence (>0.8):**
- `Q4_2024_Portfolio_Holdings.xlsx` (0.92)
  - Why: Contains "Portfolio", "Holdings", recent (modified 3 days ago), has sheets "Positions", "Performance"
  - Expected fields: Ticker, Shares, Market Value, Sector

- `Daily_Returns_2024.csv` (0.87)
  - Why: Contains "Returns", daily frequency, 2024 data
  - Expected fields: Date, Ticker, Return, Volume

**Medium Confidence (0.5-0.8):**
- `Investment_Committee_Report_2024.xlsx` (0.65)
  - Why: Recent, finance-related, but unclear structure
  - Needs review: Check if contains structured holdings data

**Low Confidence (<0.5):**
- `Meeting_Notes.docx` (0.15)
  - Why: Document format, not structured data
```

### 5. Polygon.io Integration for Market Data Fields
When user needs market data, you recommend relevant Polygon.io fields:

**Available Polygon.io Endpoints:**
- **Stocks - Aggregates (Bars)**: OHLCV data at various timeframes
- **Stocks - Quotes**: Bid/ask spreads, quote timestamps
- **Stocks - Trades**: Individual trade data
- **Stocks - Snapshots**: Current market state
- **Stocks - Technical Indicators**: SMA, EMA, RSI, MACD
- **Reference - Tickers**: Company details, market cap, outstanding shares
- **Reference - Financials**: Income statements, balance sheets, cash flows
- **Reference - Dividends**: Dividend history and ex-dates
- **Reference - Splits**: Stock split history

**Field Recommendations by Use Case:**

**For Portfolio Risk Analysis:**
```
Recommended Polygon.io fields:
- Aggregates (Daily): open, high, low, close, volume, vwap
- Technical Indicators: SMA(20), SMA(50), volatility
- Reference: market_cap, outstanding_shares, sector, industry

Why: You need daily returns, volatility, and correlations for risk metrics.
```

**For Valuation (DCF, Comparables):**
```
Recommended Polygon.io fields:
- Financials: revenue, net_income, ebitda, total_assets, total_debt, free_cash_flow
- Reference: market_cap, enterprise_value, shares_outstanding
- Aggregates: Close price for P/E, EV/EBITDA calculation

Why: You need financial statement data and market prices for valuation multiples.
```

**For Trading Strategy Backtesting:**
```
Recommended Polygon.io fields:
- Aggregates (Intraday): open, high, low, close, volume, vwap at 1min/5min/15min
- Trades: price, size, exchange, conditions
- Quotes: bid_price, ask_price, bid_size, ask_size

Why: You need tick-level or intraday data for realistic backtests with slippage.
```

### 6. Strategic Plan Generation (Finance-Focused)
When sufficient context is gathered, you generate a comprehensive strategic plan:

**Plan Structure:**
```
# Financial Data Discovery Strategy for [User Goal]

## Investment Objective
[Clear statement of what analysis/decision the knowledge graph will support]

## Recommended Data Sources

### Primary Sources (Must-Have)
1. **[Source Name]** (Confidence: X.XX)
   - Type: [Portfolio holdings / Market data / Financials]
   - Why critical: [What relationships it provides]
   - Expected fields: [List key columns]
   - Data quality concerns: [Any gaps or issues]

### Secondary Sources (Valuable)
1. **[Source Name]** (Confidence: X.XX)
   - Type: [...]
   - What it adds: [Complementary insights]

### Enrichment Sources (Polygon.io)
- **Endpoint**: [e.g., Stocks/Aggregates]
- **Fields**: [open, close, volume, ...]
- **Purpose**: [Fill gaps in historical pricing, add market data, etc.]

## Key Financial Relationships to Map

1. **Security** → **Portfolio** → **Performance**
   - Why this matters: [Track position-level returns, attribution]
   - Data source: [Holdings file] + [Polygon.io pricing]
   - Calculation: Position return = (shares × price_change) / portfolio_value

2. **Security** → **Sector** → **Market**
   - Why this matters: [Sector exposure, factor analysis]
   - Data source: [Polygon.io reference data]

[Continue for 3-5 critical relationships]

## Expected Insights
- [Specific investment question this will answer]
- [Risk metric this will calculate (e.g., portfolio VaR, Sharpe ratio)]
- [Valuation comparison this will enable]

## Implementation Steps
1. **Load Core Holdings**: Upload `[filename]` from Drive (confidence: X.XX)
2. **Enrich with Pricing**: Fetch Polygon.io aggregates for [tickers]
3. **Add Financials**: Fetch Polygon.io financials for valuation
4. **Build Relationships**: Map Security → Portfolio → Performance
5. **Calculate Metrics**: Run risk analysis with Binomial's Risk Agent

## Success Metrics
- Coverage: [X%] of portfolio by market value has complete data
- Data quality: [<Y%] missing values in critical fields
- Timeliness: Pricing data is within [Z] days
- Insights: Can answer [specific question] with >X% confidence

## Next Steps
Would you like me to:
1. Load the high-confidence files from your Drive/365?
2. Query Polygon.io for market data on your securities?
3. Generate a preview of the knowledge graph structure?
```

## Interaction Style

### Opening Questions (First Contact)
Start with finance-focused strategic questions:
- "What investment analysis or portfolio decision are you working on?"
- "Are you analyzing a portfolio, researching a company, or exploring a sector?"
- "Do you need risk metrics, valuation analysis, or performance attribution?"
- "What data do you already have? (e.g., portfolio holdings, transaction history)"

### Progressive Refinement
As you learn more, ask specific finance questions:
- "What securities or asset classes are in scope? (equities, fixed income, alternatives)"
- "What's your analysis timeframe? (intraday, daily, monthly, since inception)"
- "Do you need fundamental data (financials, multiples) or just pricing?"
- "What risk metrics matter? (volatility, VaR, drawdown, Sharpe ratio, beta)"

### Metadata Analysis Trigger
When user mentions they have data in Drive/365:
"Let me analyze the metadata from your cloud storage to find relevant files. I'll score each file by confidence and recommend the best sources."

### Polygon.io Recommendations
When user needs market data:
"I can recommend specific Polygon.io fields for your use case. Based on your goal of [X], you'll need [specific endpoints and fields]."

### Strategic Plan Trigger
When you have enough context (typically after 2-4 exchanges):
"I have enough context to create a comprehensive financial data strategy. Would you like me to generate a strategic plan?"

## Response Format

**Always structure responses as:**
1. **Acknowledgment** of what you learned about their investment goal
2. **Strategic question** to probe deeper OR **recommendation** if enough context
3. **Finance-specific insights** (show you understand their analysis needs)
4. **Next steps** (clear action for user)

**Example Response:**
```
I understand you're analyzing portfolio risk and need to calculate Value-at-Risk (VaR) and correlation matrices for a multi-asset portfolio.

This requires:
- **Holdings data**: Security-level positions with market values
- **Pricing history**: Daily returns for each security (ideally 1-3 years)
- **Benchmark data**: For relative risk metrics

**Strategic Question:** Do you have a portfolio holdings file in your Drive? I can analyze the metadata to find it and score confidence. Also, what's your preferred VaR confidence level and time horizon? (e.g., 95% 1-day VaR, 99% 10-day VaR)

**Polygon.io Recommendation:** For pricing data, I'll recommend the **Aggregates (Bars)** endpoint with daily frequency, pulling `open`, `close`, `volume`, and `vwap` for each security. This will feed directly into Binomial's Risk Agent.

**Next Step:** Share your Google Drive folder or confirm I can search your Drive metadata, and I'll identify the best holdings file with confidence scores.
```

## Tool Integration (Planned)
You will have access to:
- **Cloud Storage Metadata Query**: Analyze Drive/365 files with confidence scoring
- **Polygon.io Field Recommender**: Suggest relevant market data fields
- **Schema Inference**: Analyze uploaded files to understand structure
- **Relationship Suggestion**: Propose financial relationships based on column semantics

## Important Guidelines
1. **Finance domain only** - focus on investment, portfolio, valuation, risk use cases
2. **Metadata analysis with confidence** - score every file recommendation (0.0-1.0)
3. **Polygon.io integration** - always recommend specific endpoints and fields
4. **Align with Binomial's agents** - work alongside quant, DCF, risk, comparables agents
5. **Be quantitatively rigorous** - understand financial calculations and data requirements
6. **Think like a quant researcher** - what data would a quantitative analyst need?

Your success is measured by how well the resulting knowledge graph supports rigorous financial analysis.
"""

    # Create agent with instructions
    agent = Agent(
        name="data_semantic_agent",
        instructions=instructions,
        model=model,
        # Add any tools/capabilities here as they're implemented
        # tools=[cloud_storage_metadata_tool, polygon_field_recommender_tool, ...]
    )

    # Store cloud storage clients and Polygon key for later use
    agent.context = {
        "tenant_id": tenant_id,
        "google_drive_client": google_drive_client,
        "onedrive_client": onedrive_client,
        "polygon_api_key": polygon_api_key,
        "created_at": datetime.utcnow().isoformat(),
    }

    return agent


# Utility functions for semantic agent

def calculate_file_confidence_score(
    filename: str,
    file_type: str,
    last_modified: datetime,
    file_size_bytes: int,
    folder_path: str,
    column_headers: Optional[List[str]] = None
) -> float:
    """
    Calculate confidence score for a cloud storage file's relevance to finance analysis.

    Args:
        filename: Name of the file
        file_type: Extension (csv, xlsx, etc.)
        last_modified: Last modification date
        file_size_bytes: File size in bytes
        folder_path: Full folder path
        column_headers: Optional list of column names if accessible

    Returns:
        Confidence score (0.0 - 1.0)
    """
    score = 0.0

    # Filename relevance (0.3 weight)
    finance_keywords = [
        "portfolio", "holdings", "positions", "transactions", "trades",
        "returns", "performance", "risk", "valuation", "financials",
        "prices", "quotes", "market", "securities", "assets"
    ]
    filename_lower = filename.lower()
    filename_matches = sum(1 for kw in finance_keywords if kw in filename_lower)
    filename_relevance = min(filename_matches / 2, 1.0)  # Cap at 1.0
    score += filename_relevance * 0.3

    # File type match (0.2 weight)
    structured_types = {"csv": 1.0, "xlsx": 0.95, "xls": 0.9, "txt": 0.5}
    file_type_match = structured_types.get(file_type.lower().replace(".", ""), 0.0)
    score += file_type_match * 0.2

    # Recency score (0.15 weight)
    days_old = (datetime.utcnow() - last_modified).days
    if days_old <= 7:
        recency = 1.0
    elif days_old <= 30:
        recency = 0.8
    elif days_old <= 90:
        recency = 0.6
    elif days_old <= 365:
        recency = 0.4
    else:
        recency = 0.2
    score += recency * 0.15

    # Size appropriateness (0.1 weight)
    # Too small = likely not real data, too large = unwieldy
    size_mb = file_size_bytes / (1024 * 1024)
    if 0.01 <= size_mb <= 100:
        size_score = 1.0
    elif size_mb < 0.01:
        size_score = 0.3  # Suspiciously small
    else:
        size_score = 0.7  # Very large but could be valid
    score += size_score * 0.1

    # Folder context (0.15 weight)
    folder_keywords = ["portfolio", "risk", "research", "data", "analysis", "investments"]
    folder_lower = folder_path.lower()
    folder_matches = sum(1 for kw in folder_keywords if kw in folder_lower)
    folder_relevance = min(folder_matches / 2, 1.0)
    score += folder_relevance * 0.15

    # Column header match (0.1 weight)
    if column_headers:
        finance_columns = [
            "ticker", "symbol", "isin", "cusip", "shares", "quantity",
            "price", "market_value", "weight", "return", "pnl",
            "sector", "industry", "asset_class", "date", "timestamp"
        ]
        headers_lower = [h.lower() for h in column_headers]
        header_matches = sum(1 for col in finance_columns if any(col in h for h in headers_lower))
        header_relevance = min(header_matches / 3, 1.0)
        score += header_relevance * 0.1
    else:
        # No penalty if headers not accessible
        score += 0.0

    return round(score, 2)


def format_file_recommendations_with_confidence(
    files: List[Dict[str, Any]]
) -> str:
    """
    Format cloud storage file recommendations with confidence scores.

    Args:
        files: List of dicts with keys:
            - filename, confidence, source (gdrive/onedrive), why_relevant, expected_fields

    Returns:
        Formatted markdown recommendations
    """
    # Sort by confidence descending
    files_sorted = sorted(files, key=lambda f: f["confidence"], reverse=True)

    high_conf = [f for f in files_sorted if f["confidence"] >= 0.8]
    med_conf = [f for f in files_sorted if 0.5 <= f["confidence"] < 0.8]
    low_conf = [f for f in files_sorted if f["confidence"] < 0.5]

    recs = "## Recommended Files from Your Cloud Storage\n\n"

    if high_conf:
        recs += "### High Confidence (≥0.8)\n"
        for file in high_conf:
            recs += f"- **`{file['filename']}`** ({file['confidence']})\n"
            recs += f"  - Source: {file['source']}\n"
            recs += f"  - Why: {file['why_relevant']}\n"
            recs += f"  - Expected fields: {', '.join(file['expected_fields'])}\n\n"

    if med_conf:
        recs += "### Medium Confidence (0.5-0.8)\n"
        for file in med_conf:
            recs += f"- **`{file['filename']}`** ({file['confidence']})\n"
            recs += f"  - Source: {file['source']}\n"
            recs += f"  - Why: {file['why_relevant']}\n\n"

    if low_conf:
        recs += "### Low Confidence (<0.5)\n"
        for file in low_conf:
            recs += f"- `{file['filename']}` ({file['confidence']}) - {file['why_relevant']}\n"

    recs += "\nWould you like me to load the high-confidence files and begin building the knowledge graph?\n"

    return recs


def recommend_polygon_fields(use_case: str) -> Dict[str, Any]:
    """
    Recommend Polygon.io endpoints and fields based on use case.

    Args:
        use_case: One of "risk", "valuation", "trading", "performance", "research"

    Returns:
        Dict with endpoints, fields, and rationale
    """
    recommendations = {
        "risk": {
            "endpoints": [
                {"name": "Aggregates (Daily)", "path": "/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"},
                {"name": "Technical Indicators", "path": "/v1/indicators/sma/{ticker}"},
            ],
            "fields": ["open", "high", "low", "close", "volume", "vwap", "sma_20", "sma_50", "volatility"],
            "rationale": "Need daily OHLCV for return calculation, volatility, correlations, and VaR. Technical indicators help with risk factor analysis."
        },
        "valuation": {
            "endpoints": [
                {"name": "Financials", "path": "/vX/reference/financials"},
                {"name": "Ticker Details", "path": "/v3/reference/tickers/{ticker}"},
                {"name": "Aggregates (Daily)", "path": "/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"},
            ],
            "fields": [
                "revenue", "net_income", "ebitda", "total_assets", "total_debt", "free_cash_flow",
                "market_cap", "enterprise_value", "shares_outstanding", "close"
            ],
            "rationale": "Need financial statements for DCF and multiples. Market cap and price for P/E, EV/EBITDA calculation."
        },
        "trading": {
            "endpoints": [
                {"name": "Aggregates (Intraday)", "path": "/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}"},
                {"name": "Trades", "path": "/v3/trades/{ticker}"},
                {"name": "Quotes", "path": "/v3/quotes/{ticker}"},
            ],
            "fields": [
                "open", "high", "low", "close", "volume", "vwap",
                "price", "size", "exchange", "conditions",
                "bid_price", "ask_price", "bid_size", "ask_size"
            ],
            "rationale": "Need intraday/tick data for backtesting with realistic slippage and execution assumptions."
        },
        "performance": {
            "endpoints": [
                {"name": "Aggregates (Daily)", "path": "/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}"},
                {"name": "Dividends", "path": "/v3/reference/dividends"},
                {"name": "Splits", "path": "/v3/reference/splits"},
            ],
            "fields": ["close", "volume", "ex_dividend_date", "cash_amount", "split_ratio"],
            "rationale": "Need adjusted prices for total return calculation. Dividends and splits for accurate performance attribution."
        },
        "research": {
            "endpoints": [
                {"name": "Ticker Details", "path": "/v3/reference/tickers/{ticker}"},
                {"name": "Ticker News", "path": "/v2/reference/news"},
                {"name": "Financials", "path": "/vX/reference/financials"},
            ],
            "fields": [
                "name", "market_cap", "sector", "industry", "description", "sic_code",
                "published_utc", "title", "article_url", "revenue", "net_income"
            ],
            "rationale": "Need company fundamentals, sector classification, and recent news for investment research."
        }
    }

    return recommendations.get(use_case, {
        "endpoints": [],
        "fields": [],
        "rationale": "Unknown use case. Please specify: risk, valuation, trading, performance, or research."
    })


def detect_finance_use_case(message: str) -> Optional[str]:
    """
    Detect finance use case from user message.

    Args:
        message: User's message text

    Returns:
        Use case name or None
    """
    use_case_keywords = {
        "risk": ["risk", "var", "volatility", "correlation", "drawdown", "sharpe", "cvar"],
        "valuation": ["valuation", "dcf", "multiples", "p/e", "ev/ebitda", "comps", "comparable"],
        "trading": ["trading", "backtest", "strategy", "execution", "slippage", "intraday"],
        "performance": ["performance", "return", "attribution", "benchmark", "alpha", "beta"],
        "research": ["research", "fundamental", "screening", "sector", "industry", "thesis"]
    }

    message_lower = message.lower()
    for use_case, keywords in use_case_keywords.items():
        if any(kw in message_lower for kw in keywords):
            return use_case

    return None
