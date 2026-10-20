"""
Supervisor Routing Examples - Compact Training Data
Status: Production | Last Updated: November 2025
"""

ROUTING_EXAMPLES_XML = """
<routing_examples>

<!-- EXPLICIT AGENT MENTIONS (Priority 1 - Always wins) -->
<category name="explicit_mentions">
    <example><query>risk-agent analyze my positions</query><route>risk_specialist</route></example>
    <example><query>document-agent get the filing</query><route>document_analyst</route></example>
    <example><query>comp-agent analyze the peer group</query><route>comparable_companies</route></example>
    <example><query>dcf-agent value this company</query><route>dcf_agent</route></example>
    <example><query>chart-analyst analyze this pattern</query><route>chart_analyst</route></example>
    <example><query>quant-agent implement GARCH</query><route>quant_coding</route></example>
    <example><query>options-agent pull the chain</query><route>options_coding</route></example>
    <example><query>derivatives-agent analyze the spread</query><route>options_coding</route></example>
    <example><query>structuring-agent price the swap</query><route>structuring_analyst</route></example>
    <example><query>alternatives-agent get crypto data</query><route>alternatives_coding</route></example>
    <example><query>institutional-agent analyze ownership</query><route>institutional_activity</route></example>
    <example><query>funds-agent analyze the ETF</query><route>funds_products_analyst</route></example>
    <example><query>prediction-markets-agent check the odds</query><route>prediction_markets_analyst</route></example>
    <example><query>pe-agent look at Blackstone deals</query><route>private_markets</route></example>
    <example><query>vc-agent analyze the round</query><route>private_markets</route></example>
</category>

<!-- GENERALIST - Default for market data, financials, technicals, economics -->
<category name="generalist">
    <example><query>What's Apple's stock price?</query><route>generalist</route></example>
    <example><query>Show me TSLA RSI</query><route>generalist</route></example>
    <example><query>Apple's MACD</query><route>generalist</route></example>
    <example><query>50-day moving average for MSFT</query><route>generalist</route></example>
    <example><query>What is Apple's revenue?</query><route>generalist</route></example>
    <example><query>Tesla PE ratio</query><route>generalist</route></example>
    <example><query>Microsoft market cap</query><route>generalist</route></example>
    <example><query>Show me Apple's income statement</query><route>generalist</route></example>
    <example><query>What's the 10-year treasury yield?</query><route>generalist</route></example>
    <example><query>Current Fed funds rate</query><route>generalist</route></example>
    <example><query>Inflation rate CPI</query><route>generalist</route></example>
    <example><query>Explain PE ratio</query><route>generalist</route></example>
    <example><query>What is a moving average?</query><route>generalist</route></example>
    <example><query>Hello</query><route>generalist</route></example>
    <example><query>Help</query><route>generalist</route></example>
    <example><query>Market news today</query><route>generalist</route></example>
    <example><query>Find stocks with PE under 15</query><route>generalist</route></example>
</category>

<!-- RISK SPECIALIST - Portfolio risk (requires "my portfolio/holdings/positions") -->
<category name="risk_specialist">
    <example><query>Calculate VaR for my portfolio</query><route>risk_specialist</route></example>
    <example><query>CVaR analysis for my positions</query><route>risk_specialist</route></example>
    <example><query>Run Monte Carlo on my portfolio</query><route>risk_specialist</route></example>
    <example><query>Optimize my portfolio for max Sharpe</query><route>risk_specialist</route></example>
    <example><query>Minimum variance portfolio from my holdings</query><route>risk_specialist</route></example>
    <example><query>Stress test my portfolio</query><route>risk_specialist</route></example>
    <example><query>What happens to my portfolio if market drops 20%?</query><route>risk_specialist</route></example>
    <example><query>Barra analysis for my portfolio</query><route>risk_specialist</route></example>
    <example><query>Factor decomposition of my holdings</query><route>risk_specialist</route></example>
    <example><query>What's my portfolio beta?</query><route>risk_specialist</route></example>
    <example><query>Correlation matrix for my holdings</query><route>risk_specialist</route></example>
    <example><query>Efficient frontier for my portfolio</query><route>risk_specialist</route></example>
</category>

<!-- DOCUMENT ANALYST - SEC filings, transcripts, insider trading, 13F -->
<category name="document_analyst">
    <example><query>Show me Apple's 10-K</query><route>document_analyst</route></example>
    <example><query>Get Tesla's latest 10-Q</query><route>document_analyst</route></example>
    <example><query>Microsoft's 8-K filing</query><route>document_analyst</route></example>
    <example><query>Amazon's annual report</query><route>document_analyst</route></example>
    <example><query>Get the latest earnings transcript</query><route>document_analyst</route></example>
    <example><query>Apple's earnings call</query><route>document_analyst</route></example>
    <example><query>What's Apple's guidance?</query><route>document_analyst</route></example>
    <example><query>Show me insider Form 4 filings</query><route>document_analyst</route></example>
    <example><query>Insider trading for Apple</query><route>document_analyst</route></example>
    <example><query>Senate trading data</query><route>document_analyst</route></example>
    <example><query>Congressional stock trades</query><route>document_analyst</route></example>
    <example><query>Warren Buffett's 13F holdings</query><route>document_analyst</route></example>
    <example><query>Berkshire's latest 13F</query><route>document_analyst</route></example>
    <example><query>Risk factors from the 10-K</query><route>document_analyst</route></example>
    <example><query>When does Apple report earnings?</query><route>document_analyst</route></example>
</category>

<!-- COMPARABLE COMPANIES - Peer valuation comparisons (PE, EV/EBITDA, P/S vs peers) -->
<category name="comparable_companies">
    <example><query>Compare Apple's PE to its peers</query><route>comparable_companies</route></example>
    <example><query>How does Tesla trade vs other EV makers?</query><route>comparable_companies</route></example>
    <example><query>NVDA's multiple vs semiconductor peers</query><route>comparable_companies</route></example>
    <example><query>Show me peer valuation multiples</query><route>comparable_companies</route></example>
    <example><query>Comp table for Apple</query><route>comparable_companies</route></example>
    <example><query>Apple's premium to tech peers</query><route>comparable_companies</route></example>
    <example><query>Ranking of bank valuations</query><route>comparable_companies</route></example>
    <example><query>Benchmark Apple against its industry peers</query><route>comparable_companies</route></example>
</category>

<!-- DCF AGENT - DCF, intrinsic value, fair value, WACC -->
<category name="dcf_agent">
    <example><query>Calculate DCF for Apple</query><route>dcf_agent</route></example>
    <example><query>DCF analysis of Tesla</query><route>dcf_agent</route></example>
    <example><query>What's Tesla's intrinsic value?</query><route>dcf_agent</route></example>
    <example><query>Fair value for Microsoft</query><route>dcf_agent</route></example>
    <example><query>Terminal value for Apple</query><route>dcf_agent</route></example>
    <example><query>WACC calculation for Apple</query><route>dcf_agent</route></example>
    <example><query>Cost of equity for Tesla</query><route>dcf_agent</route></example>
    <example><query>Free cash flow projections for Apple</query><route>dcf_agent</route></example>
</category>

<!-- OPTIONS CODING - Options chains, Greeks, IV, strategies -->
<category name="options_coding">
    <example><query>Options chain for AAPL</query><route>options_coding</route></example>
    <example><query>Options Greeks for SPY</query><route>options_coding</route></example>
    <example><query>Calculate delta for SPY put</query><route>options_coding</route></example>
    <example><query>What's the IV for Tesla options?</query><route>options_coding</route></example>
    <example><query>Build an iron condor</query><route>options_coding</route></example>
    <example><query>Price a call option on Tesla</query><route>options_coding</route></example>
    <example><query>Black-Scholes for AAPL 200 call</query><route>options_coding</route></example>
    <example><query>IV term structure for SPY</query><route>options_coding</route></example>
</category>

<!-- QUANT CODING - GARCH, backtesting, ML, custom models -->
<category name="quant_coding">
    <example><query>Implement GARCH model</query><route>quant_coding</route></example>
    <example><query>Write Python code for Monte Carlo</query><route>quant_coding</route></example>
    <example><query>Code a backtest strategy</query><route>quant_coding</route></example>
    <example><query>Build a Kalman filter for price tracking</query><route>quant_coding</route></example>
    <example><query>Machine learning model for stock prediction</query><route>quant_coding</route></example>
    <example><query>Statistical arbitrage strategy</query><route>quant_coding</route></example>
    <example><query>PCA on returns</query><route>quant_coding</route></example>
    <example><query>Cointegration analysis</query><route>quant_coding</route></example>
</category>

<!-- ALTERNATIVES CODING - Crypto, forex, commodities -->
<category name="alternatives_coding">
    <example><query>Bitcoin price</query><route>alternatives_coding</route></example>
    <example><query>Ethereum current price</query><route>alternatives_coding</route></example>
    <example><query>BTC/USD</query><route>alternatives_coding</route></example>
    <example><query>EUR/USD exchange rate</query><route>alternatives_coding</route></example>
    <example><query>Dollar to Euro</query><route>alternatives_coding</route></example>
    <example><query>Gold price today</query><route>alternatives_coding</route></example>
    <example><query>Oil price</query><route>alternatives_coding</route></example>
    <example><query>Natural gas price</query><route>alternatives_coding</route></example>
</category>

<!-- PREDICTION MARKETS - Polymarket, Kalshi, event odds -->
<category name="prediction_markets_analyst">
    <example><query>Polymarket odds on Fed rate cut</query><route>prediction_markets_analyst</route></example>
    <example><query>Kalshi recession probability</query><route>prediction_markets_analyst</route></example>
    <example><query>PredictIt election odds</query><route>prediction_markets_analyst</route></example>
    <example><query>What are the betting odds for the election?</query><route>prediction_markets_analyst</route></example>
    <example><query>Probability of Fed rate cut</query><route>prediction_markets_analyst</route></example>
    <example><query>What are prediction markets saying?</query><route>prediction_markets_analyst</route></example>
</category>

<!-- PRIVATE MARKETS - PE, VC, M&A, funding rounds, IPO -->
<category name="private_markets">
    <example><query>Private equity deals this quarter</query><route>private_markets</route></example>
    <example><query>Blackstone's recent acquisitions</query><route>private_markets</route></example>
    <example><query>Latest VC funding rounds</query><route>private_markets</route></example>
    <example><query>Series C funding in fintech</query><route>private_markets</route></example>
    <example><query>Recent M&amp;A activity</query><route>private_markets</route></example>
    <example><query>IPO pipeline for tech</query><route>private_markets</route></example>
    <example><query>Upcoming IPOs</query><route>private_markets</route></example>
    <example><query>Research Stripe's valuation</query><route>private_markets</route></example>
    <example><query>SpaceX latest funding</query><route>private_markets</route></example>
    <example><query>Unicorn companies</query><route>private_markets</route></example>
</category>

<!-- END - Conversation termination -->
<category name="end">
    <example><query>Thanks, that's all!</query><route>end</route></example>
    <example><query>Thank you</query><route>end</route></example>
    <example><query>Goodbye</query><route>end</route></example>
    <example><query>Done</query><route>end</route></example>
    <example><query>That's all</query><route>end</route></example>
    <example><query>Exit</query><route>end</route></example>
</category>

<!-- EDGE CASES - Critical routing decisions -->
<category name="edge_cases">
    <!-- Technical indicators → GENERALIST (chart_analyst requires explicit mention) -->
    <example><query>Show me RSI for AAPL</query><route>generalist</route><reason>No chart-analyst mention</reason></example>
    <example><query>Analyze this chart</query><route>generalist</route><reason>No chart-analyst mention</reason></example>
    <example><query>Technical analysis of Apple</query><route>generalist</route><reason>No chart-analyst mention</reason></example>
    
    <!-- 13F/Insider → DOCUMENT_ANALYST (not institutional_activity) -->
    <example><query>13F holdings for Berkshire</query><route>document_analyst</route><reason>Filing request</reason></example>
    <example><query>Show me 13F filings</query><route>document_analyst</route><reason>Filing request</reason></example>
    <example><query>Insider Form 4 for Apple</query><route>document_analyst</route><reason>Filing request</reason></example>
    
    <!-- Performance comparison → GENERALIST (not comparable_companies) -->
    <example><query>Compare AAPL and MSFT performance</query><route>generalist</route><reason>Performance, not valuation</reason></example>
    <example><query>YTD returns AAPL vs GOOGL</query><route>generalist</route><reason>Returns, not valuation</reason></example>
    
    <!-- Single stock risk → GENERALIST (not risk_specialist) -->
    <example><query>What's Apple's beta?</query><route>generalist</route><reason>Single stock, no portfolio</reason></example>
    <example><query>Calculate VaR for Tesla</query><route>generalist</route><reason>Single stock, no portfolio</reason></example>
    <example><query>How risky is NVDA?</query><route>generalist</route><reason>Single stock</reason></example>
    
    <!-- Funds without agent mention → GENERALIST -->
    <example><query>SPY expense ratio</query><route>generalist</route><reason>No funds-agent mention</reason></example>
    <example><query>ETF holdings for QQQ</query><route>generalist</route><reason>No funds-agent mention</reason></example>
    
    <!-- Custom indicator → GENERALIST (not quant_coding) -->
    <example><query>Build a custom indicator</query><route>generalist</route><reason>Generic request</reason></example>
</category>

</routing_examples>
"""


def get_xml_examples_for_prompt():
    """Return the XML-structured examples for supervisor prompt."""
    return ROUTING_EXAMPLES_XML


def get_test_cases():
    """Comprehensive test cases for validation."""
    return [
        # Explicit agent mentions
        ("quant-agent implement GARCH", "quant_coding"),
        ("chart-analyst analyze this", "chart_analyst"),
        ("pe-agent research Stripe", "private_markets"),
        ("risk-agent analyze my portfolio", "risk_specialist"),
        ("options-agent pull chain", "options_coding"),
        
        # Generalist
        ("What is Apple's revenue?", "generalist"),
        ("Show me TSLA RSI", "generalist"),
        ("Apple stock price", "generalist"),
        ("Explain PE ratio", "generalist"),
        ("Hello", "generalist"),
        
        # Risk specialist
        ("Calculate VaR for my portfolio", "risk_specialist"),
        ("Optimize my holdings", "risk_specialist"),
        ("Stress test my portfolio", "risk_specialist"),
        
        # Document analyst
        ("Show me Apple's 10-K", "document_analyst"),
        ("Get the earnings transcript", "document_analyst"),
        ("Warren Buffett's 13F", "document_analyst"),
        
        # Comparable companies
        ("Compare Apple's PE to peers", "comparable_companies"),
        ("Peer valuation for Tesla", "comparable_companies"),
        
        # DCF agent
        ("Calculate DCF for Apple", "dcf_agent"),
        ("What's Tesla's intrinsic value?", "dcf_agent"),
        
        # Options coding
        ("Options Greeks for SPY", "options_coding"),
        ("Options chain for AAPL", "options_coding"),
        ("Build an iron condor", "options_coding"),
        
        # Quant coding
        ("Implement GARCH model", "quant_coding"),
        ("Code a backtest strategy", "quant_coding"),
        
        # Alternatives
        ("Bitcoin price", "alternatives_coding"),
        ("EUR/USD exchange rate", "alternatives_coding"),
        ("Gold price", "alternatives_coding"),
        
        # Prediction markets
        ("Polymarket odds on Fed rate cut", "prediction_markets_analyst"),
        ("Kalshi recession probability", "prediction_markets_analyst"),
        
        # Private markets
        ("Latest Series C funding rounds", "private_markets"),
        ("Blackstone's acquisitions", "private_markets"),
        ("IPO pipeline for tech", "private_markets"),
        
        # Edge cases
        ("Show me RSI for AAPL", "generalist"),  # Not chart_analyst
        ("Compare AAPL and MSFT performance", "generalist"),  # Not comparable_companies
        ("What's Apple's beta?", "generalist"),  # Not risk_specialist
        ("13F holdings for Berkshire", "document_analyst"),  # Not institutional
        
        # End
        ("Thanks!", "end"),
        ("Goodbye", "end"),
        ("Done", "end"),
    ]
