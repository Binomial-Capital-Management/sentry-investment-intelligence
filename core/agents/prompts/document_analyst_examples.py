"""
Document Analyst Examples - Concrete tool usage patterns for FMP and SEC servers
Status: Production
Created: January 2025

PURPOSE: Provide concrete examples showing when and how to use FMP vs SEC servers
for different document types. These examples teach the agent through patterns
rather than rules.
"""

def get_document_analyst_examples() -> str:
    """
    Return structured examples showing proper server selection and tool usage.

    Returns:
        String containing XML-structured examples for document analyst agent
    """

    return """
<examples>
<!-- INSIDER TRADING EXAMPLES - Always use FMP -->
<example>
<query>Show me recent insider trading for Apple</query>
<action>IMMEDIATE: Call get_raw_document(dataset="insider-trading", params={"page": 0, "limit": 50}), filter for AAPL, return transactions</action>
<reasoning>Direct execution - fetch insider trading data immediately, return results</reasoning>
</example>

<example>
<query>What insider transactions happened at SBUX last month?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="insider-trading", params={"page": 0, "limit": 50})
2. Filter results for SBUX symbol and date in response processing
</tool_sequence>
<reasoning>FMP provides structured insider trading data with transaction details</reasoning>
</example>

<example>
<query>Show me Form 4 filings for Microsoft executives</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="insider-trading", params={"page": 0, "limit": 50})
2. Filter for MSFT symbol and parse for executive-level transactions
</tool_sequence>
<reasoning>While Form 4 is an SEC form, FMP provides parsed insider trading data</reasoning>
</example>

<!-- SENATE TRADING EXAMPLES - Always use FMP -->
<example>
<query>What stocks did senators trade recently?</query>
<server>FMP</server>
<tool_sequence>
1. Use list_document_types() to confirm senate-trading availability
2. Use get_raw_document(dataset="senate-trading", params={"page": 0, "limit": 50})
</tool_sequence>
<reasoning>Senate trading disclosures are available through FMP's senate-trading dataset</reasoning>
</example>

<example>
<query>Show me Nancy Pelosi's recent trades</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="senate-trading", params={"page": 0, "limit": 50})
2. Filter for specific senator in results
</tool_sequence>
<reasoning>Congressional trading data is provided by FMP, not SEC</reasoning>
</example>

<!-- EARNINGS CALL TRANSCRIPTS - ZERO PREAMBLES -->
<example>
<query>Get Q3 2024 earnings transcript for AAPL</query>
<bad_response>I'll retrieve Apple's Q3 2024 transcript now. Please wait.</bad_response>
<good_response>[Calls get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 3}) and returns transcript content directly]</good_response>
<reasoning>Parse Q3=3, execute immediately, no talking</reasoning>
</example>

<example>
<query>What did management say about AI in the Tesla Q2 2024 earnings call?</query>
<bad_response>Calling the earnings transcript endpoint for Tesla Q2 2024. Proceeding to fetch.</bad_response>
<good_response>[Returns AI-related quotes from transcript]</good_response>
<reasoning>Parse, fetch, extract, return - zero preambles</reasoning>
</example>

<!-- EARNINGS GUIDANCE - Always use FMP -->
<example>
<query>What's Snowflake's guidance for next year?</query>
<action>IMMEDIATE: Call get_raw_document(dataset="earning-call-transcript", params={"symbol": "SNOW", "year": 2024, "quarter": 4}), extract guidance section</action>
<reasoning>Execute directly - infer latest quarter, fetch transcript, return guidance</reasoning>
</example>

<example>
<query>Did Apple raise or lower guidance?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4})
2. Compare with previous quarter's guidance
</tool_sequence>
<reasoning>Guidance updates are in FMP earnings data</reasoning>
</example>

<!-- PRESS RELEASES - Always use FMP -->
<example>
<query>Show me recent press releases from Microsoft</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="press-releases", params={"symbols": "MSFT"})
</tool_sequence>
<reasoning>Press releases are available through FMP's press-releases dataset</reasoning>
</example>

<example>
<query>Any M&A announcements from Google?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="press-releases", params={"symbols": "GOOGL"})
2. Filter for M&A keywords in results
</tool_sequence>
<reasoning>Corporate announcements are in FMP press releases</reasoning>
</example>

<!-- STOCK NEWS - Always use FMP -->
<example>
<query>What's the latest news about Tesla?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="stock-news", params={"symbols": "TSLA"})
</tool_sequence>
<reasoning>Stock news is aggregated by FMP in the stock-news dataset</reasoning>
</example>

<!-- SEC FILINGS - Use SEC Filing Server -->
<example>
<query>Show me Apple's latest 10-K filing</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="AAPL", filing_type="10-K", query="", top_k=10)
</tool_sequence>
<reasoning>get_filing handles fetch, index, and retrieval in one call - no need for separate index and get steps</reasoning>
</example>

<example>
<query>Get Microsoft's 10-Q from last quarter</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="MSFT", filing_type="10-Q", query="", top_k=10)
</tool_sequence>
<reasoning>get_filing automatically retrieves the most recent filing of the specified type</reasoning>
</example>

<example>
<query>Show me the risk factors from Amazon's 10-K</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="AMZN", filing_type="10-K", query="risk factors", top_k=10)
</tool_sequence>
<reasoning>get_filing with query parameter performs semantic search within the filing</reasoning>
</example>

<example>
<query>Find Apple's latest 8-K filing</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="AAPL", filing_type="8-K", query="", top_k=10)
</tool_sequence>
<reasoning>get_filing retrieves the most recent 8-K automatically</reasoning>
</example>

<example>
<query>Get the MD&A section from Google's 10-K</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="GOOGL", filing_type="10-K", query="management discussion and analysis", top_k=10)
</tool_sequence>
<reasoning>Use query parameter to find specific sections via semantic search</reasoning>
</example>

<example>
<query>Show me Tesla's proxy statement</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="TSLA", filing_type="DEF 14A", query="", top_k=10)
</tool_sequence>
<reasoning>get_filing handles all filing types including proxy statements</reasoning>
</example>

<example>
<query>Find Facebook's S-1 registration statement</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="META", filing_type="S-1", query="", top_k=10)
</tool_sequence>
<reasoning>get_filing supports historical filings like S-1 registration statements</reasoning>
</example>

<!-- EDGE CASES AND CLARIFICATIONS -->
<example>
<query>Show me Form 4 insider trading for Apple</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="insider-trading", params={"page": 0, "limit": 50})
2. Filter for AAPL symbol
</tool_sequence>
<reasoning>Even though Form 4 is an SEC form name, use FMP for parsed insider trading data</reasoning>
</example>

<example>
<query>Get Warren Buffett's 13F holdings</query>
<server>SEC</server>
<tool_sequence>
1. Use search_filings(query="Berkshire Hathaway 13F holdings", top_k=10)
</tool_sequence>
<reasoning>13F institutional holdings are SEC regulatory filings - use search_filings for semantic search</reasoning>
</example>

<example>
<query>What's in Apple's latest earnings report?</query>
<action>IMMEDIATE: Call get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4}), extract key points</action>
<reasoning>Direct execution - fetch transcript, extract earnings highlights, return results</reasoning>
</example>

<example>
<query>Show me the legal proceedings from Microsoft's filings</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="MSFT", filing_type="10-K", query="legal proceedings", top_k=10)
</tool_sequence>
<reasoning>Use get_filing with query parameter to find specific sections via semantic search</reasoning>
</example>

<!-- MULTI-DOCUMENT ANALYSIS EXAMPLES -->
<example>
<query>Compare Apple's risk factors from 10-K with their earnings call discussion</query>
<server>SEC + FMP</server>
<tool_sequence>
1. Use get_filing(company="AAPL", filing_type="10-K", query="risk factors", top_k=10)
2. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4})
3. Compare risk disclosure themes vs management's earnings commentary
</tool_sequence>
<reasoning>10-K shows official risks, earnings call shows how management frames challenges - compare for transparency</reasoning>
</example>

<example>
<query>Did management's guidance match what they said in the press release?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="press-releases", params={"symbols": "AAPL"})
2. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4})
3. Compare guidance figures and language consistency
</tool_sequence>
<reasoning>Check consistency between public press release and detailed earnings call</reasoning>
</example>

<!-- DOCUMENT DISCOVERY EXAMPLES -->
<example>
<query>What documents are available for Tesla?</query>
<server>FMP</server>
<tool_sequence>
1. Use discover_documents(symbol="TSLA", depth="quick")
</tool_sequence>
<reasoning>Discovery shows all available document types and fields without fetching full content</reasoning>
</example>

<example>
<query>List all document types I can access</query>
<server>FMP</server>
<tool_sequence>
1. Use list_document_types()
</tool_sequence>
<reasoning>Catalog view of all FMP document datasets (excluding SEC filings)</reasoning>
</example>

<!-- DOCUMENT FIELD EXTRACTION EXAMPLES -->
<example>
<query>Get the CEO name and guidance from Apple's latest transcript</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4})
2. Extract specific fields: CEO quotes and forward guidance section
</tool_sequence>
<reasoning>Fetch full transcript, extract relevant sections via natural language processing</reasoning>
</example>

<!-- PAGINATION EXAMPLES -->
<example>
<query>Get all insider trading for Apple in the last year</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="insider-trading", params={"page": 0, "limit": 100}, paginate=true, max_pages=5)
</tool_sequence>
<reasoning>Enable pagination to fetch multiple pages of insider trades automatically</reasoning>
</example>

<example>
<query>Show me the last 100 press releases from Microsoft</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="press-releases", params={"symbols": "MSFT"}, paginate=true, max_pages=3)
</tool_sequence>
<reasoning>Paginate through press releases to get comprehensive historical coverage</reasoning>
</example>

<!-- HISTORICAL DOCUMENT COMPARISON -->
<example>
<query>Compare Apple's Q4 2024 earnings to Q4 2023</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2024, "quarter": 4})
2. Use get_raw_document(dataset="earning-call-transcript", params={"symbol": "AAPL", "year": 2023, "quarter": 4})
3. Compare YoY revenue, guidance, management tone
</tool_sequence>
<reasoning>Fetch both quarters separately, analyze year-over-year changes</reasoning>
</example>

<!-- SEC FILING SEARCH EXAMPLES -->
<example>
<query>Find all mentions of AI in Microsoft's 10-K</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="MSFT", filing_type="10-K", query="artificial intelligence AI machine learning", top_k=20)
</tool_sequence>
<reasoning>Semantic search finds all AI-related sections across the entire 10-K</reasoning>
</example>

<example>
<query>What did Amazon say about competition in their latest 10-Q?</query>
<server>SEC</server>
<tool_sequence>
1. Use get_filing(company="AMZN", filing_type="10-Q", query="competition competitive landscape", top_k=10)
</tool_sequence>
<reasoning>Query parameter enables semantic search within the filing</reasoning>
</example>

<!-- UPLOADED DOCUMENT EXAMPLES -->
<example>
<query>Analyze this 10-K I uploaded</query>
<action>IMMEDIATE: Call analyze_uploaded_document(file_id="user_file_id"), extract key sections and insights</action>
<reasoning>Process user-uploaded PDF/document with OCR and semantic analysis</reasoning>
</example>

<example>
<query>Search for revenue recognition in the uploaded documents</query>
<server>User Files</server>
<tool_sequence>
1. Use search_document_content(query="revenue recognition accounting policy", file_ids=["file1", "file2"])
</tool_sequence>
<reasoning>Semantic search across user's uploaded financial documents</reasoning>
</example>

<!-- EARNINGS CALENDAR EXAMPLES -->
<example>
<query>When is Apple's next earnings date?</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="earning-call-calendar", params={})
2. Filter for AAPL symbol in results
</tool_sequence>
<reasoning>Earnings calendar shows upcoming earnings dates across all companies</reasoning>
</example>

<!-- STOCK NEWS WITH FILTERS -->
<example>
<query>Show me recent negative news about Tesla</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="stock-news", params={"symbols": "TSLA"})
2. Analyze sentiment and filter for negative coverage
</tool_sequence>
<reasoning>Stock news provides aggregated coverage, analyze sentiment in response</reasoning>
</example>

<!-- FMP ARTICLES EXAMPLES -->
<example>
<query>Get the latest FMP analysis articles</query>
<server>FMP</server>
<tool_sequence>
1. Use get_raw_document(dataset="fmp-articles", params={"page": 0, "limit": 20})
</tool_sequence>
<reasoning>FMP articles provide their proprietary research and market analysis</reasoning>
</example>

<!-- DECISION RULES SUMMARY -->
<!--
FMP Document Server handles:
- Insider trading (including Form 4 data)
- Senate/congressional trading
- Earnings call transcripts
- Earnings guidance and outlook
- Press releases
- Stock news
- Earnings calendar
- FMP articles
- Financial reports in JSON format

SEC Filing Server handles:
- 10-K annual reports
- 10-Q quarterly reports
- 8-K current reports
- S-1 registration statements
- DEF 14A proxy statements
- 13F institutional holdings (use search_filings for historical queries)
- Specific filing sections (risk factors, MD&A, legal proceedings)
- Semantic search within filings

User File Tools handle:
- Uploaded PDF documents
- Custom financial reports
- Proprietary research documents
-->
</examples>

<server_selection_rules>
USE FMP for:
- Any insider trading query (even if "Form 4" is mentioned)
- Senate or congressional trading
- Earnings calls, transcripts, or guidance
- Press releases or company announcements
- Stock news or market commentary
- Earnings dates or calendar
- FMP proprietary articles and analysis
- Document discovery and field extraction

USE SEC for:
- Regulatory filings (10-K, 10-Q, 8-K, S-1, DEF 14A)
- 13F institutional holdings (use search_filings for historical)
- Specific filing sections (risk factors, MD&A, legal proceedings)
- Semantic search within filings
- Historical filing comparisons
- IPO or registration documents

USE User File Tools for:
- Uploaded PDF/Excel documents
- Custom financial reports
- Proprietary research analysis
- Multi-document semantic search

COMBINE SERVERS when:
- Comparing SEC filings with earnings transcripts
- Cross-referencing press releases with 10-Q disclosures
- Validating management commentary against official filings
</server_selection_rules>

<pagination_rules>
## When to Use Pagination

**Enable paginate=true for**:
- "all", "comprehensive", "complete" queries
- Historical data requests (>50 items)
- Time-range queries (last year, all quarters)

**Default single-page for**:
- "recent", "latest", "last few"
- Quick lookups
- Preview requests

**max_pages guidance**:
- 2-3 pages: Quick comprehensive view (~100-150 items)
- 5 pages: Standard deep analysis (~250-300 items)
- 10 pages: Exhaustive historical research (use sparingly)
</pagination_rules>

<tool_parameters>
## FMP Document Server Parameters

**get_raw_document(dataset, params, paginate, max_pages)**
- dataset: "insider-trading", "earning-call-transcript", "press-releases", "stock-news", "senate-trading", "earning-call-calendar", "fmp-articles"
- params: Dataset-specific (check required_params in error messages)
- paginate: false (default) or true for multi-page fetch
- max_pages: 5 (default), max 10

**Common param patterns**:
- insider-trading: {"page": 0, "limit": 50}
- earning-call-transcript: {"symbol": "AAPL", "year": 2024, "quarter": 4}
- press-releases: {"symbols": "AAPL"}
- stock-news: {"symbols": "TSLA"}
- senate-trading: {"page": 0, "limit": 50}
- earning-call-calendar: {} (no params)
- fmp-articles: {"page": 0, "limit": 20}

## SEC Filing Server Parameters

**get_filing(company, filing_type, query, top_k, stream, user_id, session_id)**
- company: Ticker, CIK, or company name
- filing_type: "10-K", "10-Q", "8-K", "S-1", "DEF 14A", or "latest"
- query: Search query for semantic search (empty for full filing)
- top_k: 10 (default), max 30
- stream: true (default) for immediate previews
- user_id, session_id: Auto-provided by system

**search_filings(query, top_k, user_id, session_id)**
- query: Semantic search across all indexed filings
- top_k: 10 (default), max 30
</tool_parameters>
"""