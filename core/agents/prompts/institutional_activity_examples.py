"""
Institutional Activity Examples - Concrete tool usage patterns for FMPTradeFlowServer
Status: Production
Created: January 2025

PURPOSE: Provide concrete examples showing when and how to use FMPTradeFlowServer tools
for 13F holdings, insider trading, congressional trades, ETF holdings, and ESG analysis.
These examples teach the agent through patterns rather than rules.
"""

def get_institutional_activity_examples() -> str:
    """
    Return structured examples showing proper tool selection and usage for institutional data.

    Returns:
        String containing XML-structured examples for institutional activity agent
    """

    return """
<examples>
<!-- 13F INSTITUTIONAL HOLDINGS EXAMPLES -->
<example>
<query>Who are the largest institutional holders of Apple?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="AAPL", data_types=["latest", "analytics"], page=0, limit=50)
</tool_sequence>
<reasoning>13F filings show institutional ownership - "latest" gives current positions, "analytics" adds concentration metrics</reasoning>
</example>

<example>
<query>Show me Berkshire Hathaway's 13F holdings</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(cik="0001067983", data_types=["latest", "analytics"], page=0, limit=100)
</tool_sequence>
<reasoning>Search by CIK to get specific institutional investor's entire portfolio</reasoning>
</example>

<example>
<query>What changes did institutions make in Tesla last quarter?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="TSLA", data_types=["latest", "analytics"], page=0, limit=50)
2. Analyze position changes (added/reduced shares) from results
</tool_sequence>
<reasoning>Compare current vs previous quarter positions from 13F data to identify accumulation/distribution</reasoning>
</example>

<example>
<query>Which hedge funds increased their Microsoft positions?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="MSFT", data_types=["latest", "analytics"], page=0, limit=100)
2. Filter for positive ownership changes in response
</tool_sequence>
<reasoning>13F analytics show quarter-over-quarter changes - filter for institutions adding shares</reasoning>
</example>

<!-- INSIDER TRADING EXAMPLES -->
<example>
<query>Show recent insider trades for Apple</query>
<action>IMMEDIATE: Call get_insider_trading(symbol="AAPL", data_types=["transactions"], page=0, limit=50), return results</action>
<reasoning>Direct execution - fetch Form 4 transaction data immediately</reasoning>
</example>

<example>
<query>Did Apple executives buy or sell stock recently?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_insider_trading(symbol="AAPL", data_types=["transactions", "statistics"], page=0, limit=50)
</tool_sequence>
<reasoning>Transactions show individual trades, statistics provide buy/sell ratio and trends</reasoning>
</example>

<example>
<query>Show me insider buying activity for META</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_insider_trading(symbol="META", data_types=["transactions"], page=0, limit=100)
2. Filter for transaction_type="P-Purchase" in results
</tool_sequence>
<reasoning>P-Purchase transactions indicate insider conviction - filter for buys only</reasoning>
</example>

<example>
<query>What's the insider ownership percentage for Tesla?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_insider_trading(symbol="TSLA", data_types=["ownership"], page=0, limit=10)
</tool_sequence>
<reasoning>Beneficial ownership data shows total insider stakes and percentages</reasoning>
</example>

<example>
<query>Show me all trades by Elon Musk</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_insider_trading(name="Musk Elon", data_types=["transactions"], page=0, limit=100)
</tool_sequence>
<reasoning>Search by insider name to track specific executive across all their holdings</reasoning>
</example>

<!-- CONGRESSIONAL TRADING EXAMPLES -->
<example>
<query>What stocks did Congress trade recently?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_congressional_trades(chambers=["senate", "house"], page=0, limit=50)
</tool_sequence>
<reasoning>STOCK Act filings show congressional trades - include both chambers for complete view</reasoning>
</example>

<example>
<query>Did any senators trade Apple stock?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_congressional_trades(symbol="AAPL", chambers=["senate"], page=0, limit=50)
</tool_sequence>
<reasoning>Filter congressional trades by symbol and chamber</reasoning>
</example>

<example>
<query>Show me Nancy Pelosi's recent trades</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_congressional_trades(name="Pelosi", chambers=["house"], page=0, limit=50)
</tool_sequence>
<reasoning>Search by congress member name to track their trading activity</reasoning>
</example>

<example>
<query>What tech stocks did Congress buy this year?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_congressional_trades(chambers=["senate", "house"], page=0, limit=200)
2. Filter for tech symbols (AAPL, MSFT, GOOGL, META, NVDA, etc.) and purchase transactions
</tool_sequence>
<reasoning>Fetch broad congressional data, filter for tech sector and buy transactions in analysis</reasoning>
</example>

<!-- ETF HOLDINGS EXAMPLES -->
<example>
<query>What are the top holdings in SPY?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_etf_holdings(etf_symbol="SPY", data_types=["holdings", "info"], page=0, limit=50)
</tool_sequence>
<reasoning>ETF holdings show constituent stocks with weights - info adds fund metadata</reasoning>
</example>

<example>
<query>Show me QQQ's sector allocation</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_etf_holdings(etf_symbol="QQQ", data_types=["sector", "holdings"], page=0, limit=10)
</tool_sequence>
<reasoning>Sector breakdown shows tech/healthcare/financials weightings in the ETF</reasoning>
</example>

<example>
<query>What's the country exposure in VEA?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_etf_holdings(etf_symbol="VEA", data_types=["country", "info"], page=0, limit=10)
</tool_sequence>
<reasoning>Country allocation for international ETFs shows geographic diversification</reasoning>
</example>

<example>
<query>Compare SPY and IVV holdings</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_etf_holdings(etf_symbol="SPY", data_types=["holdings"], page=0, limit=100)
2. Use get_etf_holdings(etf_symbol="IVV", data_types=["holdings"], page=0, limit=100)
3. Compare top holdings and weights
</tool_sequence>
<reasoning>Fetch both ETFs separately, analyze overlap and differences</reasoning>
</example>

<!-- ESG RATINGS EXAMPLES -->
<example>
<query>What's Apple's ESG rating?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_esg_ratings(symbol="AAPL", data_types=["ratings", "disclosures"])
</tool_sequence>
<reasoning>ESG ratings show environmental/social/governance scores and risk metrics</reasoning>
</example>

<example>
<query>Compare ESG scores for Tesla vs Ford</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_esg_ratings(symbol="TSLA", data_types=["ratings"])
2. Use get_esg_ratings(symbol="F", data_types=["ratings"])
3. Compare overall ESG score and component scores
</tool_sequence>
<reasoning>Fetch ESG data for both companies separately, then compare</reasoning>
</example>

<example>
<query>Show me Microsoft's ESG disclosure quality</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_esg_ratings(symbol="MSFT", data_types=["disclosures", "ratings"])
</tool_sequence>
<reasoning>Disclosures show transparency and reporting quality for ESG metrics</reasoning>
</example>

<!-- MULTI-DATASET ANALYSIS EXAMPLES -->
<example>
<query>Give me a complete smart money analysis for NVDA</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="NVDA", data_types=["latest", "analytics"], page=0, limit=50)
2. Use get_insider_trading(symbol="NVDA", data_types=["transactions", "statistics"], page=0, limit=50)
3. Use get_congressional_trades(symbol="NVDA", chambers=["senate", "house"], page=0, limit=20)
4. Synthesize: institutions accumulating? insiders buying? congressional interest?
</tool_sequence>
<reasoning>Comprehensive smart money view requires 13F, insider, and congressional data combined</reasoning>
</example>

<example>
<query>Are insiders and institutions aligned on Microsoft?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="MSFT", data_types=["latest", "analytics"], page=0, limit=30)
2. Use get_insider_trading(symbol="MSFT", data_types=["transactions", "statistics"], page=0, limit=30)
3. Compare: institutional position changes vs insider buy/sell activity
</tool_sequence>
<reasoning>Alignment check: both buying = strong signal, divergence = caution</reasoning>
</example>

<!-- DISCOVERY AND METADATA EXAMPLES -->
<example>
<query>What institutional data is available for Apple?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use discover_institutional_fields(symbol="AAPL", max_datasets=30)
</tool_sequence>
<reasoning>Discovery shows all available 13F, insider, ETF, ESG datasets and fields for the symbol</reasoning>
</example>

<example>
<query>List all available institutional datasets</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use list_tradeflow_datasets(include_details=true)
</tool_sequence>
<reasoning>Catalog view shows all institutional datasets with descriptions and parameters</reasoning>
</example>

<!-- CODE INTERPRETER INTEGRATION EXAMPLES -->
<example>
<query>Calculate the net institutional flow for AAPL and visualize it</query>
<server>FMPTradeFlow + CodeInterpreter</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="AAPL", data_types=["latest", "analytics"], page=0, limit=100)
2. Use CodeInterpreterTool to analyze:
   - Calculate net shares added/removed by institutions
   - Create bar chart showing top buyers vs sellers
   - Calculate total dollar flow (shares * price)
   - Export results to CSV
</tool_sequence>
<reasoning>MCP fetches raw data, CodeInterpreter performs custom analysis and visualization</reasoning>
</example>

<example>
<query>Find insider trading clusters for tech stocks</query>
<server>FMPTradeFlow + CodeInterpreter</server>
<tool_sequence>
1. Use get_insider_trading(symbol="AAPL", data_types=["transactions"], page=0, limit=100)
2. Repeat for MSFT, GOOGL, META, NVDA
3. Use CodeInterpreterTool to:
   - Identify time-based clustering (multiple insiders trading same week)
   - Calculate conviction scores (size * frequency)
   - Plot heatmap of insider activity by company and time
</tool_sequence>
<reasoning>MCP provides transaction data, CodeInterpreter finds patterns across multiple symbols</reasoning>
</example>

<!-- EDGE CASES AND CLARIFICATIONS -->
<example>
<query>Who are the whale holders in Bitcoin ETFs?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_etf_holdings(etf_symbol="IBIT", data_types=["holdings", "info"], page=0, limit=50)
2. Use get_etf_holdings(etf_symbol="FBTC", data_types=["holdings", "info"], page=0, limit=50)
3. Combine results to identify common large holders
</tool_sequence>
<reasoning>Check multiple Bitcoin ETFs to find institutional concentration</reasoning>
</example>

<example>
<query>Did any insiders buy after the recent earnings miss?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Determine earnings date from context or ask
2. Use get_insider_trading(symbol="SYMBOL", data_types=["transactions"], page=0, limit=100)
3. Filter for purchases after earnings date - strong conviction signal
</tool_sequence>
<reasoning>Insider buying post-bad-news is highest conviction signal - timing matters</reasoning>
</example>

<example>
<query>What's the institutional ownership concentration for TSLA?</query>
<server>FMPTradeFlow</server>
<tool_sequence>
1. Use get_13f_holdings(symbol="TSLA", data_types=["latest", "analytics"], page=0, limit=100)
2. Calculate concentration: % held by top 5, top 10, top 20 holders
</tool_sequence>
<reasoning>Analytics provide concentration metrics - high concentration = few holders control large stake</reasoning>
</example>

<!-- DECISION RULES SUMMARY -->
<!--
FMPTradeFlowServer handles:
- 13F institutional holdings (quarterly filings)
- Insider trading (Form 4 transactions, ownership, statistics)
- Congressional trades (STOCK Act disclosures)
- ETF holdings and composition
- ESG ratings and disclosures

CodeInterpreterTool for:
- Custom clustering analysis
- Multi-stock pattern detection
- Advanced visualizations
- Statistical models
- Export and reporting
-->
</examples>

<tool_selection_rules>
USE get_13f_holdings for:
- "Who owns", "largest holders", "institutional ownership"
- "Which hedge funds", "smart money", "13F"
- Position changes quarter-over-quarter

USE get_insider_trading for:
- "Insider buys", "insider sells", "Form 4"
- "Executive trades", "CEO/CFO transactions"
- Insider ownership percentages

USE get_congressional_trades for:
- "Congress trades", "Senate", "House"
- "Nancy Pelosi", "political trading"
- STOCK Act disclosures

USE get_etf_holdings for:
- "ETF holdings", "what's in SPY"
- "Sector allocation", "country exposure"
- ETF composition analysis

USE get_esg_ratings for:
- "ESG score", "sustainability rating"
- Environmental/social/governance metrics
- ESG disclosure quality

USE CodeInterpreterTool when:
- Custom analysis beyond raw data fetch
- Pattern detection across multiple stocks
- Visualization creation
- Statistical modeling
- Multi-dataset synthesis
</tool_selection_rules>

<parameter_defaults>
## Decisive Defaults (Apply When User Doesn't Specify)

**13F Holdings**:
- data_types: ["latest", "analytics"] - always include both for complete view
- page: 0, limit: 50 - reasonable default for most queries

**Insider Trading**:
- data_types: ["transactions", "statistics"] - both give context
- page: 0, limit: 50 - captures recent activity

**Congressional Trades**:
- chambers: ["senate", "house"] - include both unless specified
- page: 0, limit: 50 - recent trades

**ETF Holdings**:
- data_types: ["holdings", "info"] - holdings + metadata
- page: 0, limit: 50 - top holdings

**ESG Ratings**:
- data_types: ["ratings", "disclosures"] - complete ESG view

**Principle**: Use generous defaults, execute immediately, note alternatives in output
</parameter_defaults>
"""
