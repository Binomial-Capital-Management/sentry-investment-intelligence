/**
 * Chat Guide Panel - Slide-in documentation panel from the right
 * Professional institutional finance design with logos and subtle color accents
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  X, Brain, Zap, FileText, BarChart3, LineChart, Code, Calculator,
  Bitcoin, Scale, Sparkles, TrendingDown, Target, Briefcase, Layers,
  TrendingUp, Paperclip, Folder, Compass, Database, AlertTriangle,
  Columns, RefreshCw, Terminal, Globe, Wrench, Server, Activity,
  ChevronRight, ChevronDown, Cpu, Library, Copy, Presentation, Sheet, Pencil,
} from 'lucide-react';
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import perplexityLogo from '@/assets/model-logos/perplexity-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';

interface ChatGuidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabId = 'toc' | 'overview' | 'agents' | 'complications' | 'tools' | 'models' | 'features' | 'context' | 'exports';

// Complete tool reference
const toolCategories = {
  codeExecution: {
    name: 'Code Interpreter',
    icon: Terminal,
    color: '#8b5cf6',
    availability: 'OpenAI models only',
    description: 'Sandboxed Python environment with pre-installed financial libraries (pandas, numpy, scipy, statsmodels, matplotlib, seaborn)',
    tools: [
      { name: 'CodeInterpreterTool', desc: 'Execute Python code, generate visualizations, process data files, run statistical calculations in isolated sandbox' },
    ],
  },
  webSearch: {
    name: 'Web Search',
    icon: Globe,
    color: '#3b82f6',
    availability: 'All models except DeepSeek',
    description: 'Real-time internet search with source attribution and ranked results',
    tools: [
      { name: 'web_search', desc: 'Query the web for current information, news, research. Returns ranked results with URLs, snippets, and relevance scores' },
      { name: 'analyze_news_sentiment', desc: 'FinBERT-based sentiment analysis of news articles for a ticker. Returns sentiment score, key phrases, and summaries' },
    ],
  },
  fileAccess: {
    name: 'File Operations',
    icon: FileText,
    color: '#f59e0b',
    availability: 'All models',
    description: 'Read, search, and analyze uploaded documents and cloud storage files',
    tools: [
      { name: 'read_file_content', desc: 'Read contents of uploaded files (PDF, CSV, Excel, JSON, TXT, images). Extracts text, tables, and structured data' },
      { name: 'search_file_chunks_tool', desc: 'Semantic search across file contents using vector embeddings. Find relevant sections without reading entire documents' },
      { name: 'drive_list_files', desc: 'List files from connected Google Drive. Filter by folder, type, or name pattern' },
      { name: 'drive_get_file_preview', desc: 'Preview and read Google Drive files. Supports Docs, Sheets, PDFs' },
    ],
  },
  marketData: {
    name: 'Market Data (MCP Servers)',
    icon: Database,
    color: '#10b981',
    availability: 'All models',
    description: 'Real-time and historical financial data via Model Context Protocol servers',
    tools: [
      { name: 'FMPMarketDataServer', desc: 'Stock quotes, company profiles, financial statements (income, balance sheet, cash flow), key ratios, historical prices, dividends, splits, technical indicators' },
      { name: 'EconomicDataServer', desc: 'FRED economic indicators (800k+ series): GDP, CPI, unemployment, interest rates, yield curves, international data via OECD/IMF/World Bank' },
      { name: 'FMPDocumentServer', desc: 'Earnings call transcripts, press releases, SEC filing metadata, insider trading summaries, institutional holdings' },
      { name: 'SECFilingServer', desc: 'Direct SEC EDGAR access: 10-K, 10-Q, 8-K, DEF 14A, 13F filings. Full text search, indexing, and extraction' },
      { name: 'PolygonOptionsFuturesServer', desc: 'Options chains, Greeks (delta, gamma, vega, theta), open interest, volume, implied volatility, futures contracts and expiration data' },
      { name: 'PolygonCryptoFXServer', desc: 'Cryptocurrency prices, FX rates, historical OHLCV data, market depth, 24h changes' },
      { name: 'FMPAlternativesServer', desc: 'Commodities (oil, gold, natural gas, agriculture), crypto market overview, commodity futures' },
      { name: 'FMPTradeFlowServer', desc: '13F institutional holdings, insider transactions (Form 4), congressional trades, ETF flows, sector rotation data' },
      { name: 'FMPAdvancedValuationServer', desc: 'DCF inputs, enterprise value calculations, WACC components, comparable company metrics, growth rates' },
      { name: 'PolymarketServer', desc: 'Prediction market events, odds, volume, liquidity, market resolution data from Polymarket' },
      { name: 'YFinanceServer', desc: 'Fallback market data source: quotes, historical prices, options chains, analyst recommendations, company info' },
      { name: 'UWOptionsServer', desc: 'Unusual Whales options flow: flow alerts, Greek flow by sector, GEX levels, IV rank/term structure, NOPE, max pain, hottest contracts, OI changes' },
      { name: 'UWInstitutionalServer', desc: 'Unusual Whales institutional: dark pool prints, congressional trades (STOCK Act), insider transactions, 13F holdings, ETF flows/exposure' },
      { name: 'UWMarketServer', desc: 'Unusual Whales market: correlations, seasonality, short interest/FTDs, analyst ratings, stock screener with flow metrics, market overview' },
    ],
  },
  riskTools: {
    name: 'Risk Analytics',
    icon: Zap,
    color: '#ef4444',
    availability: 'All models (Risk Specialist agent)',
    description: 'Institutional-grade portfolio risk calculations and quantitative analysis',
    tools: [
      { name: 'calculate_var', desc: 'Value at Risk using Historical Simulation, Parametric (variance-covariance), or Monte Carlo methods. Configurable confidence levels (95%, 99%). Returns VaR and CVaR/ES' },
      { name: 'run_monte_carlo', desc: 'Monte Carlo simulation with configurable paths (1000-100000), time horizon, drift/volatility assumptions. Returns distribution statistics, percentiles, and scenario paths' },
      { name: 'optimize_portfolio', desc: 'Mean-variance optimization, minimum variance, maximum Sharpe, risk parity, Black-Litterman with views. Returns optimal weights, efficient frontier, risk/return stats' },
      { name: 'analyze_barra_factors', desc: 'Factor exposure analysis: market, size, value, momentum, volatility, quality, growth. Returns factor loadings, contribution to risk, and residual' },
      { name: 'create_hedge_portfolio', desc: 'Construct hedging positions: beta-neutral, factor-neutral, or tail hedges. Recommends hedge instruments and quantities' },
      { name: 'analyze_fft_trends', desc: 'Fast Fourier Transform for cyclical pattern detection. Identifies dominant frequencies, denoises price series, extracts trend components' },
      { name: 'calculate_rolling_correlation', desc: 'Rolling window correlation between assets with Fisher z-transform. Configurable window size and exponential decay factor' },
      { name: 'calculate_implied_correlation', desc: 'Derive implied correlation from options prices using the variance-decomposition method' },
      { name: 'stress_test_correlation', desc: 'Stress test portfolio under correlation regime changes (crisis scenarios, correlation breakdown, contagion)' },
      { name: 'analyze_pca_eigen_portfolios', desc: 'Principal Component Analysis for return drivers. Identifies systematic vs idiosyncratic risk, constructs eigen portfolios' },
      { name: 'price_correlation_swap', desc: 'Price correlation swaps given strike vol, realized vol estimates, notional, and term' },
      { name: 'analyze_correlation_matrix', desc: 'Full correlation matrix analysis with clustering, heatmaps, stability metrics, and tail dependence' },
      { name: 'calculate_delta_exposure', desc: 'Portfolio delta (first-order price sensitivity). Aggregates across options and linear positions' },
      { name: 'calculate_gamma_exposure', desc: 'Portfolio gamma (second-order sensitivity). Critical for large moves and dealer positioning' },
      { name: 'calculate_vega_exposure', desc: 'Portfolio vega (volatility sensitivity). Measures exposure to implied vol changes' },
      { name: 'calculate_theta_decay', desc: 'Portfolio theta (time decay). Daily P&L from passage of time' },
      { name: 'calculate_cross_greeks', desc: 'Cross-gamma, vanna (dDelta/dVol), volga (dVega/dVol), charm, veta for complex positions' },
      { name: 'construct_dynamic_hedge', desc: 'Build delta-neutral, gamma-neutral, vega-neutral, or multi-Greek hedges. Recommends instruments and rebalancing frequency' },
    ],
  },
  valuationTools: {
    name: 'Valuation',
    icon: Calculator,
    color: '#059669',
    availability: 'All models (DCF/Comps agents)',
    description: 'Discounted cash flow modeling and comparable company analysis',
    tools: [
      { name: 'gather_dcf_data_sources', desc: 'Collect all inputs for DCF: historical financials, growth rates, margins, capex, working capital, beta, risk-free rate, ERP' },
      { name: 'three_stage_dcf', desc: 'Three-stage DCF: high growth → transition → terminal. Projects FCF for each phase with distinct assumptions. Returns equity value per share' },
      { name: 'two_stage_dcf', desc: 'Two-stage DCF: growth phase → terminal value. Standard model for mature growth companies' },
      { name: 'stable_stage_dcf', desc: 'Single-stage DCF for stable, mature businesses. Gordon Growth Model applied to current FCF' },
      { name: 'sensitivity_analysis', desc: 'Build sensitivity tables varying WACC, growth rate, margins, exit multiples. Returns matrix of fair values with color coding' },
      { name: 'analyze_comparable_companies', desc: 'Peer selection, trading multiples (P/E, EV/EBITDA, P/B, P/S, EV/Revenue), premium/discount analysis, regression-based valuation' },
    ],
  },
  structuringTools: {
    name: 'Derivatives Structuring',
    icon: Layers,
    color: '#6366f1',
    availability: 'All models (Structuring Desk agent)',
    description: 'Exotic options, swaps, and structured products pricing',
    tools: [
      { name: 'price_equity_options', desc: 'Black-Scholes, binomial tree, Monte Carlo pricing. Supports American/European exercise, discrete dividends, early exercise premium' },
      { name: 'model_volatility_surface', desc: 'Build implied vol surface from market quotes. SABR, SVI, or local vol calibration. Returns surface, smile parameters, and interpolated vols' },
      { name: 'price_variance_swap', desc: 'Variance swap pricing given strike vol, realized vol estimates, and term. Uses replication via log contract' },
      { name: 'price_volatility_swap', desc: 'Volatility swap pricing with convexity adjustment for vol-of-vol' },
      { name: 'price_dispersion_trade', desc: 'Dispersion trade analysis: index vol vs weighted average constituent vol. Calculates breakeven correlation' },
      { name: 'price_irs', desc: 'Interest rate swap pricing: fixed vs floating leg valuation, DV01, convexity, key rate durations' },
      { name: 'price_swaption', desc: 'Swaption pricing using Black or Bachelier model. Normal vs lognormal vols, receiver vs payer' },
      { name: 'price_cds', desc: 'Credit default swap pricing: spread, upfront, hazard rates, recovery assumptions, risky annuity' },
      { name: 'price_exotic_derivative', desc: 'Barrier options (knock-in/out, up/down), Asian options (arithmetic/geometric), lookback options, autocallables with coupons' },
    ],
  },
  quantTools: {
    name: 'Quantitative Coding',
    icon: Code,
    color: '#ec4899',
    availability: 'All models (Quant Coder agent)',
    description: 'Custom implementations for backtesting, ML, and statistical analysis',
    tools: [
      { name: 'forecast_arima', desc: 'Fit ARIMA(p,d,q) or ARIMAX models. Auto-selects parameters via AIC/BIC. Returns forecasts with confidence intervals' },
      { name: 'analyze_pca_eigen_portfolios', desc: 'Principal Component Analysis on return matrix. Identifies principal portfolios and variance explained by each factor' },
      { name: 'analyze_feature_importance', desc: 'Feature importance using random forest, gradient boosting, or permutation importance. For factor selection and alpha research' },
      { name: 'identify_cointegrated_pairs', desc: 'Engle-Granger and Johansen cointegration tests. Returns cointegrated pairs with test statistics for pairs trading' },
      { name: 'calculate_hedge_ratio', desc: 'Optimal hedge ratio via OLS regression, minimum variance, or cointegration-based methods' },
      { name: 'generate_mean_reversion_signals', desc: 'Half-life of mean reversion, Hurst exponent, ADF test. Generates z-score based trading signals' },
    ],
  },
};

// Agent data with colors for visual distinction
const agentDetails = {
  auto: {
    name: 'Supervisor',
    backendName: 'supervisor',
    icon: Brain,
    color: '#374151',
    description: 'LangGraph-based orchestrator using gpt-5-nano for intent classification. Routes queries to specialized agents via structured RouterDecision output.',
    capabilities: [
      'Intent classification via structured LLM output (RouterDecision schema)',
      'Multi-hop collaboration (up to 6 agent handoffs in Multi-Agent mode)',
      'Context preservation across agent transitions',
      'Portfolio and file context injection into ConversationState',
      'Graceful fallback to Generalist for ambiguous queries',
      'Real-time status message streaming during routing',
    ],
    routing: [
      { condition: 'VaR, CVaR, Monte Carlo, portfolio optimization, Greeks', target: 'risk_specialist' },
      { condition: '10-K, 10-Q, 8-K, earnings transcripts, SEC filings', target: 'document_analyst' },
      { condition: 'P/E, EV/EBITDA, trading multiples, peer comparison', target: 'comparable_companies' },
      { condition: 'DCF, intrinsic value, WACC, terminal value, FCFE', target: 'dcf_agent' },
      { condition: 'Options chains, Greeks, IV surface, payoff diagrams', target: 'options_coding' },
      { condition: 'Crypto, forex, commodities, FX pairs', target: 'alternatives_coding' },
      { condition: 'Chart patterns, technicals, support/resistance', target: 'chart_analyst' },
      { condition: 'IRS, swaptions, CDS, variance swaps, exotics', target: 'structuring_analyst' },
      { condition: '13F filings, Form 4, congressional trades, ETF flows', target: 'institutional_activity' },
      { condition: 'Polymarket, Kalshi, prediction probabilities', target: 'prediction_markets_analyst' },
      { condition: 'ETF, mutual fund, hedge fund analysis', target: 'funds_products_analyst' },
      { condition: 'PE, M&A, VC, private company intelligence', target: 'private_markets' },
      { condition: 'GARCH, backtest, ML models, custom code', target: 'quant_coding' },
      { condition: 'General market questions, news, quotes', target: 'generalist' },
    ],
    mcpServers: [],
    tools: [],
    modelSettings: 'Model: gpt-5-nano | Output: RouterDecision | Reasoning: minimal',
  },
  generalist: {
    name: 'Agentic Search',
    backendName: 'generalist',
    icon: Sparkles,
    color: '#3b82f6',
    description: 'Primary conversational agent with access to all 7 MCP servers. Handles market data queries, economic data, news sentiment, web search, and general research with dynamic field discovery.',
    capabilities: [
      'Real-time quotes, historical prices, company profiles via FMP',
      'Financial statements (income, balance sheet, cash flow)',
      'Economic indicators via FRED (GDP, CPI, rates)',
      'FinBERT-based news sentiment analysis',
      'Web search with source attribution and citations',
      'File reading and semantic search across documents',
      'Dynamic Plotly chart generation',
      'Code execution for custom analysis (OpenAI only)',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Quotes, financials, profiles, historical data, technicals' },
      { name: 'EconomicDataServer', purpose: 'FRED economic indicators, rates, yields' },
      { name: 'FMPAlternativesServer', purpose: 'Commodities, crypto overview' },
      { name: 'FMPTradeFlowServer', purpose: 'Institutional flows, insider trades' },
      { name: 'PolygonOptionsFuturesServer', purpose: 'Options chains, futures' },
      { name: 'PolygonCryptoFXServer', purpose: 'Crypto and forex data' },
      { name: 'YFinanceServer', purpose: 'Fallback market data' },
      { name: 'UWOptionsServer', purpose: 'Options flow, GEX, Greek flow' },
      { name: 'UWInstitutionalServer', purpose: 'Dark pool, congress, insider' },
      { name: 'UWMarketServer', purpose: 'Correlations, short interest' },
    ],
    tools: [
      { name: 'web_search', desc: 'Real-time internet search with source URLs' },
      { name: 'read_file_content', desc: 'Read uploaded files (PDF, CSV, Excel, JSON, images)' },
      { name: 'search_file_chunks_tool', desc: 'Semantic search across file contents' },
      { name: 'drive_list_files', desc: 'List Google Drive files/folders' },
      { name: 'drive_get_file_preview', desc: 'Preview/read Google Drive files' },
      { name: 'analyze_news_sentiment', desc: 'FinBERT sentiment analysis for tickers' },
      { name: 'CodeInterpreterTool', desc: 'Python execution (OpenAI only)' },
      { name: 'market_chart_build_tool', desc: 'Generate interactive Plotly visualizations' },
    ],
    modelSettings: 'tool_choice: auto | parallel_tool_calls: true | max_tokens: 15,000 | reasoning: low',
  },
  risk: {
    name: 'Risk Quant',
    backendName: 'risk_specialist',
    icon: Zap,
    color: '#ef4444',
    description: 'Institutional-grade portfolio risk analytics. Single source of truth for VaR/CVaR, Monte Carlo, optimization, factor models, correlation analysis, Greeks exposure, GEX-based regime detection, and dynamic hedging.',
    capabilities: [
      'Value at Risk (Historical, Parametric, Monte Carlo)',
      'Conditional VaR / Expected Shortfall',
      'Monte Carlo simulation with custom scenarios and horizons',
      'Portfolio optimization (Mean-Variance, Max Sharpe, Black-Litterman, Risk Parity)',
      'Barra-style factor model decomposition and exposure analysis',
      'Correlation matrix analysis with tail dependence metrics',
      'GEX-based market regime detection (positive/negative gamma)',
      'Greeks exposure (Delta, Gamma, Vega, Theta, Cross-Greeks)',
      'Short squeeze risk analysis (short interest, FTDs)',
      'Dynamic hedging strategy construction (multi-Greek)',
      'FFT denoising, trend extraction, and cyclical pattern detection',
      'PCA / Eigen portfolio analysis for factor construction',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Equity prices, fundamentals, technicals' },
      { name: 'EconomicDataServer', purpose: 'FRED macro series for scenario design' },
      { name: 'FMPTradeFlowServer', purpose: 'ETF holdings for implied correlation' },
      { name: 'PolygonOptionsFuturesServer', purpose: 'Options IV data for correlation analysis' },
      { name: 'UWOptionsServer', purpose: 'GEX levels, Greek flow, volatility regime' },
      { name: 'UWMarketServer', purpose: 'Short interest, correlations, market stress' },
    ],
    tools: [
      { name: 'calculate_var', desc: 'Historical/Parametric/Monte Carlo VaR & CVaR' },
      { name: 'run_monte_carlo', desc: 'Monte Carlo shock engine with configurable paths' },
      { name: 'optimize_portfolio', desc: 'Mean-variance, Black-Litterman, risk-parity' },
      { name: 'analyze_barra_factors', desc: 'Factor decomposition (Barra/PCA style)' },
      { name: 'create_hedge_portfolio', desc: 'Beta-neutral, factor-neutral, tail hedges' },
      { name: 'analyze_fft_trends', desc: 'FFT denoising and cycle identification' },
      { name: 'calculate_rolling_correlation', desc: 'Rolling correlation with Fisher z' },
      { name: 'calculate_implied_correlation', desc: 'GS variance decomposition method' },
      { name: 'stress_test_correlation', desc: 'Correlation shock scenarios' },
      { name: 'analyze_pca_eigen_portfolios', desc: 'PCA factor decomposition' },
      { name: 'price_correlation_swap', desc: 'Correlation swap pricing' },
      { name: 'analyze_correlation_matrix', desc: 'Full correlation analysis with tail dependence' },
      { name: 'calculate_delta_exposure', desc: 'Options portfolio delta' },
      { name: 'calculate_gamma_exposure', desc: 'Options portfolio gamma' },
      { name: 'calculate_vega_exposure', desc: 'Options portfolio vega' },
      { name: 'calculate_theta_decay', desc: 'Options portfolio theta' },
      { name: 'calculate_cross_greeks', desc: 'Vanna, volga, charm, veta' },
      { name: 'construct_dynamic_hedge', desc: 'Multi-Greek dynamic hedging' },
      { name: 'PORTFOLIO_TOOLS', desc: 'Portfolio list, get, set active' },
    ],
    modelSettings: 'parallel_tool_calls: true | max_tokens: 15,000 | reasoning: medium',
  },
  filings: {
    name: 'Document Analyst',
    backendName: 'document_analyst',
    icon: FileText,
    color: '#f59e0b',
    description: 'SEC filings, earnings transcripts, and corporate document analysis. Indexes, chunks, and semantically searches complex financial documents with cross-reference capabilities.',
    capabilities: [
      'SEC filing indexing (10-K, 10-Q, 8-K, DEF 14A, proxy statements)',
      'Earnings transcript extraction and semantic search',
      'Form 4 insider trading data retrieval and analysis',
      '10-K analysis: MD&A, Risk Factors, Business Description',
      '10-Q quarterly trend detection',
      '8-K material event extraction',
      'Document chunking with embedding-based search',
      'Cross-reference between filings and time periods',
      'Uploaded document analysis (PDF, Word, Excel)',
    ],
    mcpServers: [
      { name: 'FMPDocumentServer', purpose: 'Earnings transcripts, press releases, insider trades' },
      { name: 'SECFilingServer', purpose: 'SEC EDGAR 10-K, 10-Q, 8-K, proxy, Form 4' },
    ],
    tools: [
      { name: 'sec_index_filing', desc: 'Index SEC filing for semantic search' },
      { name: 'sec_search_filings', desc: 'Search across indexed filings' },
      { name: 'sec_get_filing', desc: 'Retrieve specific filing content' },
      { name: 'read_file_content', desc: 'Read uploaded documents' },
      { name: 'search_file_chunks_tool', desc: 'Semantic search over documents' },
      { name: 'drive_list_files', desc: 'Google Drive file listing' },
      { name: 'drive_get_file_preview', desc: 'Preview Drive files' },
      { name: 'web_search', desc: 'Emergency fallback search' },
      { name: 'CodeInterpreterTool', desc: 'Document processing (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 15,000 | reasoning: medium',
  },
  multiples: {
    name: 'Comps Analyst',
    backendName: 'comparable_companies',
    icon: BarChart3,
    color: '#8b5cf6',
    description: 'Relative valuation and peer comparison analysis. Constructs comprehensive comp tables, analyzes trading multiples, and calculates premium/discount to peers.',
    capabilities: [
      'Peer group selection by sector, size, geography',
      'Trading multiples (P/E, EV/EBITDA, P/B, P/S, EV/Revenue)',
      'Premium/discount to peers calculation',
      'Historical multiples trends and z-score analysis',
      'Regression-based relative valuation',
      'Football field chart generation',
      'Sector and industry benchmarking',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Financials, valuations, ratios, profiles' },
    ],
    tools: [
      { name: 'analyze_comparable_companies', desc: 'Build peer valuation tables' },
      { name: 'web_search', desc: 'Industry research' },
      { name: 'CodeInterpreterTool', desc: 'Custom calculations (OpenAI)' },
    ],
    modelSettings: 'parallel_tool_calls: true | max_tokens: 15,000 | reasoning: low',
  },
  charts: {
    name: 'Chart Analyst',
    backendName: 'chart_analyst',
    icon: LineChart,
    color: '#06b6d4',
    description: 'Technical analysis and chart pattern recognition using GPT-5 Vision capabilities. Analyzes uploaded chart images for patterns, support/resistance, GEX levels, and indicators.',
    capabilities: [
      'Chart image analysis with Vision API',
      'Support and resistance level identification',
      'GEX-based support/resistance (dealer hedging levels)',
      'Max pain price targets for expiration',
      'Trend line and channel analysis',
      'Candlestick pattern recognition (doji, engulfing, etc.)',
      'Technical indicator interpretation (RSI, MACD, Bollinger)',
      'Short squeeze setup identification',
      'Price action analysis and momentum',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Technical indicators and historical prices' },
      { name: 'UWOptionsServer', purpose: 'GEX levels, max pain, flow-based key levels' },
      { name: 'UWMarketServer', purpose: 'Short interest, market movers, correlations' },
    ],
    tools: [
      { name: 'read_file_content', desc: 'Read chart images via Vision API' },
      { name: 'web_search', desc: 'Technical analysis research' },
      { name: 'CodeInterpreterTool', desc: 'Generate custom charts (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 15,000 | reasoning: low',
  },
  quant: {
    name: 'Quant Researcher',
    backendName: 'quant_coding',
    icon: Code,
    color: '#ec4899',
    description: 'Custom quantitative implementations with Code Interpreter. Builds GARCH models, runs backtests, implements ML models, and performs statistical arbitrage analysis with options flow data.',
    capabilities: [
      'Custom Python code execution in sandbox',
      'GARCH volatility modeling and forecasting',
      'ARIMA/ARIMAX time series analysis',
      'Machine learning model implementation (RF, XGBoost)',
      'Backtesting trading strategies',
      'Statistical arbitrage and pairs trading',
      'Cointegration testing (Engle-Granger, Johansen)',
      'Options flow factor signals (Greek flow, GEX)',
      'Seasonality and calendar effects analysis',
      'Factor model construction and testing',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Equity and stock market data' },
      { name: 'EconomicDataServer', purpose: 'Macro/FRED data for factor analysis' },
      { name: 'FMPAlternativesServer', purpose: 'Crypto, forex, commodities data' },
      { name: 'UWOptionsServer', purpose: 'Greek flow, volatility, OI changes for quant signals' },
      { name: 'UWMarketServer', purpose: 'Correlations, seasonality, short interest' },
      { name: 'UWInstitutionalServer', purpose: 'Dark pool, insider flow for alternative factors' },
    ],
    tools: [
      { name: 'CodeInterpreterTool', desc: 'Python sandbox (PRIMARY)' },
      { name: 'read_file_content', desc: 'Load data files and CSVs' },
      { name: 'search_file_chunks_tool', desc: 'Semantic document search' },
      { name: 'forecast_arima', desc: 'ARIMA time series forecasting' },
      { name: 'analyze_pca_eigen_portfolios', desc: 'PCA factor decomposition' },
      { name: 'analyze_feature_importance', desc: 'ML feature importance (RF)' },
      { name: 'identify_cointegrated_pairs', desc: 'Cointegration testing' },
      { name: 'calculate_hedge_ratio', desc: 'Optimal hedge ratios' },
      { name: 'generate_mean_reversion_signals', desc: 'Z-score trading signals' },
      { name: 'price_equity_options', desc: 'Option pricing models' },
      { name: 'model_volatility_surface', desc: '3D vol surface modeling' },
      { name: 'web_search', desc: 'Research fallback' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 50,000 | reasoning: medium',
  },
  structuring: {
    name: 'Structuring Analyst',
    backendName: 'structuring_analyst',
    icon: Layers,
    color: '#6366f1',
    description: 'Derivatives structuring and exotic options pricing. Prices IRS, swaptions, CDS, variance swaps, and structured products with full Greeks.',
    capabilities: [
      'Interest Rate Swaps (IRS) pricing',
      'Swaptions valuation (Black/Bachelier)',
      'Credit Default Swaps (CDS)',
      'Variance and volatility swaps',
      'Dispersion trade analysis',
      'Exotic options (barriers, Asian, lookback, autocallables)',
      'Vol surface modeling (SABR, SVI)',
      'Greeks calculation for complex positions',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Underlying prices' },
      { name: 'EconomicDataServer', purpose: 'Rate curves, yield data' },
      { name: 'FMPTradeFlowServer', purpose: 'Market flows' },
      { name: 'PolygonOptionsFuturesServer', purpose: 'Options/futures data' },
      { name: 'UWOptionsServer', purpose: 'Flow context, GEX levels for barrier placement' },
    ],
    tools: [
      { name: 'price_irs', desc: 'Interest rate swap pricing' },
      { name: 'price_swaption', desc: 'Swaption valuation' },
      { name: 'price_cds', desc: 'CDS pricing' },
      { name: 'price_variance_swap', desc: 'Variance swap pricing' },
      { name: 'price_volatility_swap', desc: 'Volatility swap pricing' },
      { name: 'price_dispersion_trade', desc: 'Dispersion analysis' },
      { name: 'price_exotic_derivative', desc: 'Exotic options pricing' },
      { name: 'price_equity_options', desc: 'Vanilla options (BS, binomial)' },
      { name: 'model_volatility_surface', desc: 'Vol surface calibration' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 50,000 | reasoning: medium',
  },
  dcf: {
    name: 'DCF Analyst',
    backendName: 'dcf_agent',
    icon: Calculator,
    color: '#059669',
    description: 'Discounted cash flow and intrinsic value analysis. Builds multi-stage DCF models with comprehensive sensitivity analysis.',
    capabilities: [
      'Free Cash Flow projections',
      'WACC calculation (CAPM, build-up method)',
      'Terminal value (Gordon Growth, Exit Multiple)',
      'Three-stage DCF (high growth → transition → terminal)',
      'Two-stage DCF for mature companies',
      'Sensitivity analysis on key assumptions',
      'Scenario modeling',
      'Financial statement analysis',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Financial statements' },
      { name: 'EconomicDataServer', purpose: 'Risk-free rates' },
      { name: 'FMPAdvancedValuationServer', purpose: 'Valuation inputs, beta, WACC components' },
    ],
    tools: [
      { name: 'gather_dcf_data_sources', desc: 'Collect all DCF inputs' },
      { name: 'three_stage_dcf', desc: 'Three-stage growth model' },
      { name: 'two_stage_dcf', desc: 'Two-stage growth model' },
      { name: 'stable_stage_dcf', desc: 'Stable/Gordon Growth model' },
      { name: 'sensitivity_analysis', desc: 'Build sensitivity tables' },
      { name: 'CodeInterpreterTool', desc: 'Custom modeling (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 50,000',
  },
  options: {
    name: 'Options Analyst',
    backendName: 'options_coding',
    icon: TrendingDown,
    color: '#f97316',
    description: 'Listed options analysis with Polygon and Unusual Whales data. Analyzes chains, Greeks, implied volatility surfaces, flow alerts, and constructs trading strategies.',
    capabilities: [
      'Options chain analysis',
      'Greeks calculation (Delta, Gamma, Vega, Theta, Rho)',
      'Implied volatility surface modeling',
      'Options flow alerts and unusual activity',
      'GEX (gamma exposure) levels',
      'Options strategy construction',
      'Payoff diagram generation',
      'Dynamic hedging',
      'Vol surface and term structure analysis',
    ],
    mcpServers: [
      { name: 'PolygonOptionsFuturesServer', purpose: 'Options chains, Greeks, IV, OI' },
      { name: 'FMPMarketDataServer', purpose: 'Underlying prices' },
      { name: 'UWOptionsServer', purpose: 'Flow alerts, GEX, Greek flow, IV rank, max pain' },
    ],
    tools: [
      { name: 'uw_flow_alerts', desc: 'Unusual options activity detection' },
      { name: 'uw_greek_flow', desc: 'Delta/vega flow by sector group' },
      { name: 'uw_gex', desc: 'Gamma exposure by strike' },
      { name: 'uw_volatility', desc: 'IV rank, term structure, skew' },
      { name: 'uw_sentiment', desc: 'NOPE and max pain indicators' },
      { name: 'calculate_delta_exposure', desc: 'Delta exposure calculation' },
      { name: 'calculate_gamma_exposure', desc: 'Gamma exposure calculation' },
      { name: 'price_equity_options', desc: 'Option pricing' },
      { name: 'model_volatility_surface', desc: 'Vol surface modeling' },
      { name: 'CodeInterpreterTool', desc: 'Custom analysis (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 20,000',
  },
  alternatives: {
    name: 'Alternatives Researcher',
    backendName: 'alternatives_coding',
    icon: Bitcoin,
    color: '#f59e0b',
    description: 'Cryptocurrency, forex, and commodities analysis with specialized Polygon and FMP data sources.',
    capabilities: [
      'Cryptocurrency market data',
      'Forex pairs analysis',
      'Commodity price tracking',
      'Cross-asset correlation',
      'Technical analysis for crypto/FX',
    ],
    mcpServers: [
      { name: 'PolygonCryptoFXServer', purpose: 'Crypto and FX data' },
      { name: 'FMPAlternativesServer', purpose: 'Commodities, crypto overview' },
    ],
    tools: [
      { name: 'CodeInterpreterTool', desc: 'Custom analysis (OpenAI)' },
      { name: 'read_file_content', desc: 'File access' },
      { name: 'search_file_chunks_tool', desc: 'File search' },
      { name: 'web_search', desc: 'Market research' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 20,000',
  },
  institutional: {
    name: 'Institutional Flow Analyst',
    backendName: 'institutional_activity',
    icon: Scale,
    color: '#8b5cf6',
    description: 'Institutional ownership, insider trading, and smart money tracking. Analyzes 13F filings, Form 4, congressional trades, dark pool activity, and ETF flows.',
    capabilities: [
      '13F institutional holdings analysis',
      'Form 4 insider trading tracking',
      'Congressional trading alerts (STOCK Act)',
      'Dark pool print detection (UW exclusive)',
      'ETF flow and exposure analysis',
      'Ownership concentration analysis',
      'Sector rotation tracking',
      'Smart money flow patterns',
    ],
    mcpServers: [
      { name: 'FMPTradeFlowServer', purpose: '13F filings, insider trades, congressional trades, ETF flows' },
      { name: 'UWInstitutionalServer', purpose: 'Dark pool prints, granular congress trades, real-time insider flow, ETF in-outflow' },
    ],
    tools: [
      { name: 'uw_congress', desc: 'Congressional trades by member, recent, or late filers' },
      { name: 'uw_darkpool', desc: 'Dark pool block trades (unique to UW)' },
      { name: 'uw_insider', desc: 'SEC Form 4 with clustering analysis' },
      { name: 'uw_institution', desc: '13F holdings by institution name' },
      { name: 'uw_ownership', desc: 'Institutional ownership of a stock' },
      { name: 'uw_etf', desc: 'ETF holdings, exposure, flows, weights' },
      { name: 'CodeInterpreterTool', desc: 'Data analysis (OpenAI)' },
      { name: 'web_search', desc: 'Research' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 20,000 | reasoning: medium',
  },
  prediction_markets: {
    name: 'Prediction Markets Analyst',
    backendName: 'prediction_markets_analyst',
    icon: Target,
    color: '#06b6d4',
    description: 'Prediction market analysis and probability forecasting from Polymarket, Kalshi, and other platforms.',
    capabilities: [
      'Polymarket event tracking',
      'Kalshi market analysis',
      'Event probability aggregation',
      'Market sentiment extraction',
      'Political/economic event forecasting',
      'Arbitrage opportunity identification',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Related market data' },
      { name: 'PolymarketServer', purpose: 'Polymarket events and odds' },
    ],
    tools: [
      { name: 'web_search', desc: 'Event research' },
      { name: 'read_file_content', desc: 'File access' },
      { name: 'search_file_chunks_tool', desc: 'File search' },
      { name: 'CodeInterpreterTool', desc: 'Probability analysis (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 50,000 | reasoning: medium',
  },
  funds_products: {
    name: 'Funds Products Analyst',
    backendName: 'funds_products_analyst',
    icon: TrendingUp,
    color: '#10b981',
    description: 'ETF, mutual fund, and hedge fund analysis. Evaluates holdings, performance, fees, and factor exposures.',
    capabilities: [
      'ETF holdings and factor exposure',
      'Mutual fund screening',
      'Hedge fund strategy analysis',
      'Expense ratio comparison',
      'Performance attribution',
      'Fund flow tracking',
      'Due diligence research',
    ],
    mcpServers: [
      { name: 'FMPMarketDataServer', purpose: 'Fund data, holdings' },
      { name: 'FMPAlternativesServer', purpose: 'Alternative fund data' },
      { name: 'UWInstitutionalServer', purpose: 'ETF flows, exposure, holdings, in-outflow' },
    ],
    tools: [
      { name: 'uw_etf', desc: 'ETF holdings, exposure, flows, weights' },
      { name: 'uw_institution', desc: '13F holdings for fund analysis' },
      { name: 'web_search', desc: 'Fund research' },
      { name: 'read_file_content', desc: 'File access' },
      { name: 'search_file_chunks_tool', desc: 'File search' },
      { name: 'CodeInterpreterTool', desc: 'Performance analysis (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 50,000 | reasoning: medium',
  },
  private_markets: {
    name: 'Private Markets Researcher',
    backendName: 'private_markets',
    icon: Briefcase,
    color: '#7c3aed',
    description: 'Private equity, M&A, venture capital, and private company research. Primarily web-search based for deal intelligence.',
    capabilities: [
      'Private equity deal research',
      'M&A transaction analysis',
      'Venture capital funding tracking',
      'IPO pipeline monitoring',
      'Private company intelligence',
      'LBO modeling concepts',
      'GP/LP dynamics',
    ],
    mcpServers: [
      { name: 'FMPTradeFlowServer', purpose: 'Deal flow data' },
      { name: 'EconomicDataServer', purpose: 'Macro context' },
      { name: 'FMPMarketDataServer', purpose: 'Public comparables' },
    ],
    tools: [
      { name: 'web_search', desc: 'Primary tool - deal research' },
      { name: 'CodeInterpreterTool', desc: 'LBO modeling (OpenAI)' },
    ],
    modelSettings: 'tool_choice: required | parallel_tool_calls: true | max_tokens: 15,000',
  },
};

// Model data with logos
const modelCategories = [
  {
    name: 'Reasoning',
    description: 'Extended thinking for complex multi-step analysis',
    models: [
      { name: 'GPT-6 Astra', logo: gptLogo, provider: 'OpenAI', context: '1M', codeExec: true, streaming: true, webSearch: true },
      { name: 'Claude Fable 5.1', logo: claudeLogo, provider: 'Anthropic', context: '1M', codeExec: false, streaming: false, webSearch: true },
      { name: 'Claude Opus 5.5', logo: claudeLogo, provider: 'Anthropic', context: '1M', codeExec: false, streaming: false, webSearch: true },
      { name: 'Gemini 4 Argon', logo: geminiLogo, provider: 'Google', context: '1M', codeExec: false, streaming: false, webSearch: true },
      { name: 'Grok 4.7', logo: grokLogo, provider: 'xAI', context: '500K', codeExec: false, streaming: false, webSearch: true },
    ],
  },
  {
    name: 'Standard',
    description: 'Balanced speed and capability for most tasks',
    models: [
      { name: 'GPT-6.1 Sol', logo: gptLogo, provider: 'OpenAI', context: '1M', codeExec: true, streaming: true, webSearch: true },
      { name: 'Claude Sonnet 5.5', logo: claudeLogo, provider: 'Anthropic', context: '1M', codeExec: false, streaming: false, webSearch: true },
      { name: 'Gemini 3.8 Flash', logo: geminiLogo, provider: 'Google', context: '1M', codeExec: false, streaming: false, webSearch: true },
    ],
  },
  {
    name: 'Fast',
    description: 'Low latency for quick queries',
    models: [
      { name: 'GPT-6 Luna', logo: gptLogo, provider: 'OpenAI', context: '1M', codeExec: true, streaming: true, webSearch: true },
      { name: 'Claude Haiku 4.5', logo: claudeLogo, provider: 'Anthropic', context: '200K', codeExec: false, streaming: false, webSearch: true },
      { name: 'Grok 4.20 Fast', logo: grokLogo, provider: 'xAI', context: '1M', codeExec: false, streaming: false, webSearch: true },
    ],
  },
  {
    name: 'Search',
    description: 'Real-time web search with citations',
    models: [
      { name: 'Perplexity Sonar', logo: perplexityLogo, provider: 'Perplexity', context: 'N/A', codeExec: false, streaming: true, webSearch: true },
      { name: 'Perplexity Sonar Pro', logo: perplexityLogo, provider: 'Perplexity', context: 'N/A', codeExec: false, streaming: true, webSearch: true },
    ],
  },
];

export const ChatGuidePanel: React.FC<ChatGuidePanelProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<string>('toc');
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [serverPage, setServerPage] = useState(1);
  const [toolsPage, setToolsPage] = useState(1);
  const [routingPage, setRoutingPage] = useState(1);
  const [complicationSection, setComplicationSection] = useState<
    'attachments' | 'cloud' | 'portfolio' | 'agent-mode' | 'search-mode' | 'model-selector' | 'deep-analysis' | 'analyst-mode' | 'prompt-library' | 'export-buttons' | 'compaction' | 'data-types'
  >('agent-mode');
  const ITEMS_PER_PAGE = 5;
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [agentModePage, setAgentModePage] = useState(1);
  const [modelsPage, setModelsPage] = useState(1);
  const MODELS_PER_PAGE = 6;
  const [toolCategoriesPage, setToolCategoriesPage] = useState(1);
  const TOOL_CATEGORIES_PER_PAGE = 5;
  const [contextPage, setContextPage] = useState(1);
  const CONTEXT_SECTIONS_PER_PAGE = 1;
  const tabsRef = useRef<HTMLDivElement>(null);

  // Handle horizontal scroll with mouse wheel
  const handleTabsWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (tabsRef.current) {
      e.preventDefault();
      tabsRef.current.scrollLeft += e.deltaY;
    }
  };

  // Convert token counts to user-friendly format with token count
  const formatContext = (context: string): string => {
    if (context === 'N/A') return 'N/A';
    const num = parseInt(context.replace(/[KM]/g, ''));
    let friendly = '';
    if (context.includes('M')) {
      // 1M tokens ≈ 750K words ≈ 1,500 pages
      friendly = `${num * 1.5}K pages`;
    } else if (num >= 300) {
      // 300K+ tokens ≈ 225K words ≈ 450 pages
      friendly = `${Math.round(num * 0.75)}K words`;
    } else if (num >= 150) {
      // 150K tokens ≈ 112K words ≈ 225 pages
      friendly = `${Math.round(num * 0.75)}K words`;
    } else {
      // 75K tokens ≈ 56K words ≈ 112 pages
      friendly = `${Math.round(num * 0.75)}K words`;
    }
    return `${friendly} (${context})`;
  };

  // Animate in
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => setVisible(true), 10);
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  // Reset pagination when switching agents
  useEffect(() => {
    setServerPage(1);
    setToolsPage(1);
    setRoutingPage(1);
  }, [selectedAgent]);

  if (!isOpen) return null;

  const toggleToolCategory = (key: string) => {
    setExpandedTools(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const tabs: { id: TabId; label: string; icon?: React.ReactNode }[] = [
    { id: 'toc', label: 'Contents' },
    { id: 'overview', label: 'Overview' },
    { id: 'agents', label: 'Agents' },
    { id: 'complications', label: 'Chat Complications' },
    { id: 'models', label: 'Models' },
    { id: 'tools', label: 'Tools' },
    { id: 'context', label: 'Adding Context' },
  ];

  return (
    <>
      {/* Non-blocking side panel - chat remains interactive */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl flex flex-col z-40 transition-transform duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-full'}`}
        style={{ borderLeft: '1px solid #e5e7eb' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Chat Documentation</h2>
              <p className="text-sm text-gray-500 mt-0.5">Agent capabilities, tools, and model reference</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200 mt-4">
            <div
              ref={tabsRef}
              onWheel={handleTabsWheel}
              className="flex gap-0 overflow-x-auto no-scrollbar">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2.5 text-xs font-medium transition-all whitespace-nowrap border-b-2 ${
                    activeTab === tab.id
                      ? 'border-gray-900 text-gray-900'
                      : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* TOC Tab */}
          {activeTab === 'toc' && (
            <div className="p-8">
              <h1 className="text-2xl font-bold text-gray-900 mb-6">Table of Contents</h1>

              <div className="space-y-1">
                <button
                  onClick={() => setActiveTab('overview')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  1. Overview
                </button>
                <button
                  onClick={() => setActiveTab('agents')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  2. Agents
                </button>
                <button
                  onClick={() => setActiveTab('complications')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  3. Chat Complications
                </button>
                <button
                  onClick={() => setActiveTab('models')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  4. Models
                </button>
                <button
                  onClick={() => setActiveTab('tools')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  5. Tools
                </button>
                <button
                  onClick={() => setActiveTab('context')}
                  className="w-full text-left px-2 py-2 text-blue-600 hover:underline hover:text-blue-800 transition-colors"
                >
                  6. Adding Context
                </button>
              </div>
            </div>
          )}
          {/* Adding Context Tab */}
          {activeTab === 'context' && (
            <div className="p-6 space-y-5">
              <div className="pb-3 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-900 mb-1">Adding Context</h3>
                <p className="text-sm text-gray-600">
                  Enhance analysis by providing your own data. Context sources appear as pills above the input area.
                </p>
              </div>

              {/* Portfolio Context */}
              {contextPage === 1 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 pb-2 border-b border-gray-200">
                    <Folder size={16} className="text-gray-700" />
                    <h4 className="font-semibold text-sm text-gray-900">Portfolio Context</h4>
                  </div>
                  <p className="text-sm text-gray-700">
                    Select a saved portfolio to inject holdings data into risk calculations, optimization, and analysis.
                  </p>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700">PROCEDURE</div>
                    <ol className="space-y-1 text-sm text-gray-700 list-decimal list-inside">
                      <li>Click the portfolio button in the bottom row of the input area</li>
                      <li>Select a portfolio from the dropdown list (or create new in Portfolio page)</li>
                      <li>Portfolio appears as a pill above input with folder icon and name</li>
                      <li>Click × on the pill to remove portfolio context</li>
                    </ol>
                  </div>

                  <div className="bg-gray-50 border-l-4 border-gray-400 p-3 text-xs text-gray-700">
                    <strong>Included Data:</strong> Tickers, weights, quantities, cost basis, and portfolio metadata are automatically passed to risk agents (VaR, Monte Carlo, optimization, Barra factors).
                  </div>
                </div>
              )}

              {/* File Uploads */}
              {contextPage === 2 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 pb-2 border-b border-gray-200">
                    <Paperclip size={16} className="text-gray-700" />
                    <h4 className="font-semibold text-sm text-gray-900">File Uploads</h4>
                  </div>
                  <p className="text-sm text-gray-700">
                    Upload documents for analysis, data extraction, or custom calculations.
                  </p>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700">SUPPORTED FORMATS</div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 bg-white rounded border border-gray-300">
                        <div className="font-semibold text-gray-900">Documents</div>
                        <div className="text-gray-600">PDF, DOCX, TXT, MD</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-300">
                        <div className="font-semibold text-gray-900">Spreadsheets</div>
                        <div className="text-gray-600">CSV, XLSX, XLS</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-300">
                        <div className="font-semibold text-gray-900">Data</div>
                        <div className="text-gray-600">JSON, XML</div>
                      </div>
                      <div className="p-2 bg-white rounded border border-gray-300">
                        <div className="font-semibold text-gray-900">Images</div>
                        <div className="text-gray-600">PNG, JPG (charts)</div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700">PROCEDURE</div>
                    <ol className="space-y-1 text-sm text-gray-700 list-decimal list-inside">
                      <li>Click the attachment button in the bottom row</li>
                      <li>Select "Upload from Computer" and choose file(s)</li>
                      <li>Files appear as pills with paperclip icon and filename</li>
                      <li>Send message to analyze - agents can read, extract data, or process files</li>
                    </ol>
                  </div>

                  <div className="bg-gray-50 border-l-4 border-gray-400 p-3 text-xs text-gray-700">
                    <strong>Processing:</strong> Document Analyst agent extracts text, tables, and structured data. Quant Coding agent can run custom analysis on uploaded datasets.
                  </div>
                </div>
              )}

              {/* Cloud Storage */}
              {contextPage === 3 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 pb-2 border-b border-gray-200">
                    <Database size={16} className="text-gray-700" />
                    <h4 className="font-semibold text-sm text-gray-900">Cloud Storage Integration</h4>
                  </div>
                  <p className="text-sm text-gray-700">
                    Connect cloud storage to access enterprise documents without manual uploads.
                  </p>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700">SUPPORTED PROVIDERS</div>
                    <div className="space-y-2">
                      <div className="p-2.5 bg-white rounded border border-gray-300 flex items-center gap-3">
                        <img src="/connector-logos/google-drive.png" alt="Google Drive" className="w-8 h-8 object-contain" />
                        <div className="flex-1">
                          <div className="font-semibold text-xs text-gray-900">Google Drive</div>
                          <div className="text-xs text-gray-600">Personal and Workspace accounts</div>
                        </div>
                      </div>
                      <div className="p-2.5 bg-white rounded border border-gray-300 flex items-center gap-3">
                        <img src="/connector-logos/one-drive.png" alt="OneDrive" className="w-8 h-8 object-contain" />
                        <div className="flex-1">
                          <div className="font-semibold text-xs text-gray-900">OneDrive Business</div>
                          <div className="text-xs text-gray-600">Microsoft 365 work/school accounts</div>
                        </div>
                      </div>
                      <div className="p-2.5 bg-white rounded border border-gray-300 flex items-center gap-3">
                        <img src="/connector-logos/one-drive.png" alt="SharePoint" className="w-8 h-8 object-contain" />
                        <div className="flex-1">
                          <div className="font-semibold text-xs text-gray-900">SharePoint</div>
                          <div className="text-xs text-gray-600">Team sites and shared libraries</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700">PROCEDURE</div>
                    <ol className="space-y-1 text-sm text-gray-700 list-decimal list-inside">
                      <li>Click attachment button → select cloud provider</li>
                      <li>Authenticate with provider (OAuth popup window)</li>
                      <li>Browse and select file(s) from cloud storage browser</li>
                      <li>Files appear as pills with provider logo</li>
                    </ol>
                  </div>

                  <div className="bg-gray-50 border-l-4 border-gray-400 p-3 text-xs text-gray-700">
                    <strong>Visual Indicator:</strong> Cloud files show provider logo (Google Drive or OneDrive icon) instead of paperclip to distinguish from local uploads.
                  </div>
                </div>
              )}

              {/* Combined Context - Always visible at bottom */}
              <div className="border border-gray-300 bg-white rounded p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle size={14} className="text-gray-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-gray-700">
                    <div className="font-semibold mb-1">Combining Context</div>
                    <div>
                      You can attach multiple files + portfolio + cloud documents simultaneously. All context is passed to agents for comprehensive analysis.
                    </div>
                  </div>
                </div>
              </div>

              {/* Pagination Controls */}
              <div className="flex items-center justify-center gap-2 pt-2">
                <button
                  onClick={() => setContextPage(Math.max(1, contextPage - 1))}
                  disabled={contextPage === 1}
                  className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  Previous
                </button>
                <span className="text-xs text-gray-600">
                  {contextPage} of 3
                </span>
                <button
                  onClick={() => setContextPage(Math.min(3, contextPage + 1))}
                  disabled={contextPage === 3}
                  className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="h-full bg-white overflow-y-auto">
              <div className="max-w-3xl mx-auto px-8 py-8">

                {/* Header */}
                <div className="mb-8 pb-4 border-b border-gray-200">
                  <h1 className="text-xl font-bold text-gray-900 mb-2">Platform Documentation</h1>
                  <p className="text-sm text-gray-600">
                    Technical overview of the Sentry Investment Intelligence Platform architecture and capabilities.
                  </p>
                </div>

                {/* Core Capabilities */}
                <section className="mb-10">
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Core Capabilities</h2>
                  <ul className="space-y-4 text-sm text-gray-700">
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Intelligent Routing</div>
                      <div className="text-gray-600 leading-relaxed">
                        The system analyzes your question and routes it to the right specialist agent (Risk, Valuation, Options Pricing, DCF, etc.) ensuring expert-level responses for each domain.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Secure Code Execution</div>
                      <div className="text-gray-600 leading-relaxed">
                        Runs calculations and custom code securely for accurate quantitative results including risk metrics, portfolio optimization, and financial modeling.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Real-Time Data Access</div>
                      <div className="text-gray-600 leading-relaxed">
                        Pulls live market data, economic indicators, SEC filings, and company financials as needed. Accepts context from your portfolios, cloud storage, and uploaded files.
                      </div>
                    </li>
                    <li className="flex flex-col gap-1">
                      <div className="font-semibold text-gray-900">Web Search & Attribution</div>
                      <div className="text-gray-600 leading-relaxed">
                        Integrated real-time web search provides up-to-date information for queries outside the training cutoff. All assertions are cited with source URLs.
                      </div>
                    </li>
                  </ul>
                </section>

                {/* Operational Modes */}
                <section className="mb-10">
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Operational Modes</h2>
                  <div className="border rounded-md border-gray-200 divide-y divide-gray-200">
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-gray-100 px-2 py-1 rounded">Auto</span>
                        <span className="text-sm font-semibold text-gray-900">Supervisor Routing</span>
                      </div>
                      <p className="text-sm text-gray-600">
                        System automatically selects the best agent for your question.
                      </p>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-purple-50 text-purple-700 px-2 py-1 rounded">Multi-Agent</span>
                        <span className="text-sm font-semibold text-gray-900">Collaborative Analysis</span>
                      </div>
                      <p className="text-sm text-gray-600">
                        Multiple agents collaborate on complex tasks requiring different areas of expertise (up to 6 agent handoffs).
                      </p>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-semibold bg-blue-50 text-blue-700 px-2 py-1 rounded">Direct Routing</span>
                        <span className="text-sm font-semibold text-gray-900">Manual Agent Selection</span>
                      </div>
                      <p className="text-sm text-gray-600">
                        Manually select a specific agent for your task (Risk, DCF, Options Pricing, Comparable Companies, etc.).
                      </p>
                    </div>
                  </div>
                </section>

                {/* Infrastructure Reference */}
                <section>
                  <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-4">Infrastructure Reference</h2>

                  <div className="mb-6">
                    <h3 className="font-semibold text-gray-900 mb-2 text-sm">Supported Models</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full border border-gray-200 text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Provider</th>
                            <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Models</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">OpenAI</td>
                            <td className="px-4 py-2 text-gray-600">GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Anthropic</td>
                            <td className="px-4 py-2 text-gray-600">Claude Fable 5.1, Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 4.5</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Google</td>
                            <td className="px-4 py-2 text-gray-600">Gemini 4 Argon, Gemini 3.8 Flash, Gemini 3.5 Flash Lite</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">xAI</td>
                            <td className="px-4 py-2 text-gray-600">Grok 4.7, Grok 4.20 Fast</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Perplexity</td>
                            <td className="px-4 py-2 text-gray-600">Perplexity Sonar, Perplexity Sonar Pro</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-gray-900 mb-2 text-sm">Capabilities</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full border border-gray-200 text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Category</th>
                            <th className="px-4 py-2 text-left font-semibold text-gray-900 border-b border-gray-200">Details</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Specialized Agents</td>
                            <td className="px-4 py-2 text-gray-600">Risk, DCF, Options, Comparable Companies</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Custom Tooling</td>
                            <td className="px-4 py-2 text-gray-600">Proprietary financial analysis and quantitative tools</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Market Data</td>
                            <td className="px-4 py-2 text-gray-600">FMP, Refinitiv, Polygon, Yahoo Finance</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Documents & Economic Data</td>
                            <td className="px-4 py-2 text-gray-600">SEC Filings (FRED, SEC Edgar)</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-2 font-medium text-gray-900">Integration</td>
                            <td className="px-4 py-2 text-gray-600">Portfolio, Cloud Storage, File Uploads</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </section>

              </div>
            </div>
          )}

          {/* Agents Tab */}
          {activeTab === 'agents' && (
            <div className="p-6">
              {selectedAgent ? (
                // Agent Detail View
                <div>
                  <button
                    onClick={() => setSelectedAgent(null)}
                    className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 mb-3"
                  >
                    <ChevronRight size={12} className="rotate-180" />
                    Back to agents
                  </button>

                  {(() => {
                    const agent = agentDetails[selectedAgent as keyof typeof agentDetails];
                    if (!agent) return null;
                    const Icon = agent.icon;

                    return (
                      <div className="space-y-5">
                        {/* Header */}
                        <div className="flex items-center gap-3 pb-4 border-b-2 border-gray-200">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                            style={{ backgroundColor: `${agent.color}20` }}
                          >
                            <Icon size={20} style={{ color: agent.color }} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="text-base font-bold text-gray-900">{agent.name}</h3>
                            <p className="text-xs text-gray-500 font-mono">{agent.backendName}</p>
                          </div>
                        </div>

                        <p className="text-sm text-gray-700 leading-relaxed">{agent.description}</p>

                        {/* Capabilities */}
                        <div className="bg-gray-50 rounded-lg p-4">
                          <h4 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">Capabilities</h4>
                          <ul className="space-y-2">
                            {agent.capabilities.map((cap, idx) => (
                              <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                <span className="text-blue-500 mt-1">•</span>
                                <span>{cap}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Routing (for supervisor) */}
                        {'routing' in agent && agent.routing && agent.routing.length > 0 && (() => {
                          const totalPages = Math.ceil(agent.routing.length / ITEMS_PER_PAGE);
                          const startIdx = (routingPage - 1) * ITEMS_PER_PAGE;
                          const endIdx = startIdx + ITEMS_PER_PAGE;
                          const paginatedRouting = agent.routing.slice(startIdx, endIdx);

                          return (
                            <div className="bg-white rounded-lg border border-gray-200 p-4">
                              <h4 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">
                                Routing Logic ({agent.routing.length})
                              </h4>
                              <div className="space-y-3">
                                {paginatedRouting.map((route, idx) => (
                                  <div key={idx} className="flex items-start gap-2 text-sm">
                                    <span className="text-blue-500 mt-0.5 flex-shrink-0">→</span>
                                    <div className="flex-1">
                                      <div className="text-gray-700 mb-1">{route.condition}</div>
                                      <code className="text-xs font-mono bg-gray-50 px-2 py-0.5 rounded text-gray-900">{route.target}</code>
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {/* Pagination Controls */}
                              {totalPages > 1 && (
                                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                                  <button
                                    onClick={() => setRoutingPage(p => Math.max(1, p - 1))}
                                    disabled={routingPage === 1}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Previous
                                  </button>
                                  <span className="text-xs text-gray-500">
                                    Page {routingPage} of {totalPages}
                                  </span>
                                  <button
                                    onClick={() => setRoutingPage(p => Math.min(totalPages, p + 1))}
                                    disabled={routingPage === totalPages}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Next
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {/* MCP Servers */}
                        {agent.mcpServers && agent.mcpServers.length > 0 && (() => {
                          const totalPages = Math.ceil(agent.mcpServers.length / ITEMS_PER_PAGE);
                          const startIdx = (serverPage - 1) * ITEMS_PER_PAGE;
                          const endIdx = startIdx + ITEMS_PER_PAGE;
                          const paginatedServers = agent.mcpServers.slice(startIdx, endIdx);

                          return (
                            <div className="bg-white rounded-lg border border-gray-200 p-4">
                              <h4 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">
                                Data Sources ({agent.mcpServers.length})
                              </h4>
                              <div className="space-y-2">
                                {paginatedServers.map((server, idx) => (
                                  <div key={idx} className="flex items-start gap-2 text-sm">
                                    <Server size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <div className="font-medium text-gray-900">{server.name}</div>
                                      <div className="text-gray-600 text-xs">{server.purpose}</div>
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {/* Pagination Controls */}
                              {totalPages > 1 && (
                                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                                  <button
                                    onClick={() => setServerPage(p => Math.max(1, p - 1))}
                                    disabled={serverPage === 1}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Previous
                                  </button>
                                  <span className="text-xs text-gray-500">
                                    Page {serverPage} of {totalPages}
                                  </span>
                                  <button
                                    onClick={() => setServerPage(p => Math.min(totalPages, p + 1))}
                                    disabled={serverPage === totalPages}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Next
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {/* Tools */}
                        {agent.tools && agent.tools.length > 0 && (() => {
                          const totalPages = Math.ceil(agent.tools.length / ITEMS_PER_PAGE);
                          const startIdx = (toolsPage - 1) * ITEMS_PER_PAGE;
                          const endIdx = startIdx + ITEMS_PER_PAGE;
                          const paginatedTools = agent.tools.slice(startIdx, endIdx);

                          return (
                            <div className="bg-white rounded-lg border border-gray-200 p-4">
                              <h4 className="text-xs font-bold text-gray-900 mb-3 uppercase tracking-wide">
                                Tools ({agent.tools.length})
                              </h4>
                              <div className="space-y-2">
                                {paginatedTools.map((tool, idx) => (
                                  <div key={idx} className="flex items-start gap-2 text-sm">
                                    <Wrench size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <code className="font-medium text-gray-900 text-xs">{tool.name}</code>
                                      <div className="text-gray-600 text-xs">{tool.desc}</div>
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {/* Pagination Controls */}
                              {totalPages > 1 && (
                                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
                                  <button
                                    onClick={() => setToolsPage(p => Math.max(1, p - 1))}
                                    disabled={toolsPage === 1}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Previous
                                  </button>
                                  <span className="text-xs text-gray-500">
                                    Page {toolsPage} of {totalPages}
                                  </span>
                                  <button
                                    onClick={() => setToolsPage(p => Math.min(totalPages, p + 1))}
                                    disabled={toolsPage === totalPages}
                                    className="text-xs text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed"
                                  >
                                    Next
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    );
                  })()}
                </div>
              ) : (
                // Agent List View
                <div className="space-y-3">
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 mb-2">Specialized Agents</h3>
                    <p className="text-sm text-gray-600">
                      The Sentry Investment Intelligence Platform supports 15 agents designed to handle specific domains of investment intelligence. These agents are equipped with a range of tools and data sources to perform a wide range of tasks. Click an agent to view its full capabilities, data sources, and available tools.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Object.entries(agentDetails).map(([id, agent]) => {
                      const Icon = agent.icon;
                      return (
                        <button
                          key={id}
                          onClick={() => setSelectedAgent(id)}
                          className="flex items-start gap-2.5 px-3 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors text-left group"
                        >
                          <Icon size={18} style={{ color: agent.color }} className="flex-shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="mb-0.5">
                              <span className="font-medium text-gray-900 text-sm block">{agent.name}</span>
                              <span className="text-xs font-mono text-gray-400 block">{agent.backendName}</span>
                            </div>
                            <p className="text-xs text-gray-500">
                              {agent.mcpServers?.length || 0} data sources • {agent.tools?.length || 0} tools
                            </p>
                          </div>
                          <ChevronRight size={14} className="text-gray-400 group-hover:text-gray-600 flex-shrink-0 mt-0.5" />
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Chat Complications Tab */}
          {activeTab === 'complications' && (
            <div className="p-6">
              {/* Sub-navigation */}
              <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200">
                <button
                  onClick={() => setComplicationSection('attachments')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'attachments'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Attach Files
                </button>
                <button
                  onClick={() => setComplicationSection('cloud')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'cloud'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Cloud Storage
                </button>
                <button
                  onClick={() => setComplicationSection('portfolio')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'portfolio'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Portfolio
                </button>
                <button
                  onClick={() => setComplicationSection('agent-mode')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'agent-mode'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Agent Mode
                </button>
                <button
                  onClick={() => setComplicationSection('search-mode')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'search-mode'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Search Mode
                </button>
                <button
                  onClick={() => setComplicationSection('model-selector')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'model-selector'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Model Selector
                </button>
                <button
                  onClick={() => setComplicationSection('deep-analysis')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'deep-analysis'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Deep Analysis
                </button>
                <button
                  onClick={() => setComplicationSection('analyst-mode')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'analyst-mode'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Analyst Mode
                </button>
                <button
                  onClick={() => setComplicationSection('prompt-library')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'prompt-library'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Prompt Library
                </button>
                <button
                  onClick={() => setComplicationSection('export-buttons')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'export-buttons'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Export Buttons
                </button>
                <button
                  onClick={() => setComplicationSection('compaction')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'compaction'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Compaction
                </button>
                <button
                  onClick={() => setComplicationSection('data-types')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    complicationSection === 'data-types'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Data Types
                </button>
              </div>

              {/* Content for each section */}
              <div className="space-y-4">
                {complicationSection === 'attachments' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Attach Files Button</h2>
                      <button
                        type="button"
                        style={{
                          padding: '8px',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          borderRadius: '50%',
                        }}
                      >
                        <Paperclip size={20} style={{ color: '#6b7280' }} />
                      </button>
                    </div>

                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-3 text-sm text-gray-700">
                      <div><strong>Maximum:</strong> 5 files per message</div>
                      <div><strong>Accepted formats:</strong> .pdf, .doc, .docx, .csv, .xlsx, .xls, .txt, .json, .png, .jpg, .jpeg</div>
                      <div><strong>Drag & drop:</strong> Files can be dragged anywhere on the input area</div>
                      <div><strong>Visual feedback:</strong> Blue overlay with "Drop files here" message appears when dragging</div>
                    </div>
                  </div>
                )}

                {complicationSection === 'portfolio' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Add Saved Portfolio Context</h2>
                      <button
                        type="button"
                        style={{
                          padding: '8px',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '50%',
                        }}
                      >
                        <Folder size={18} style={{ color: '#6b7280' }} />
                      </button>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Add your saved portfolio context to the chat. This provides agents with your current holdings, weights, and portfolio composition for more personalized analysis.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Purpose:</strong> Adds saved portfolio holdings as context to your chat conversation</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>How to Use:</strong> Click the folder icon to select from your saved portfolios</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Visual Indicator:</strong> Selected portfolio appears as a gray pill above the input area with portfolio name and × to remove</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Agent Integration:</strong> Agents automatically access portfolio tickers and weights for general querying, risk analysis, option pricing, and quantitative calculations</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Portfolio Management:</strong> Create and edit portfolios in the Portfolio page with custom tickers and allocation weights</span>
                        </div>
                      </div>

                      <div className="bg-gray-50 border border-gray-300 rounded p-3 text-xs text-gray-700">
                        <strong>Note:</strong> Portfolio context persists throughout the chat session until removed. Weights must sum to 1.0 for risk calculations.
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'agent-mode' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Agent Mode Selector</h2>
                      <button
                        type="button"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          padding: '0.375rem 0.75rem',
                          fontSize: '0.875rem',
                          fontWeight: 500,
                          background: '#FFFFFF',
                          border: '0.0625rem solid #d1d5db',
                          borderRadius: '1.25rem',
                          cursor: 'pointer',
                          color: '#374151',
                        }}
                      >
                        <Brain size={14} style={{ color: '#111827' }} />
                        <span>Auto</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ opacity: 0.5 }}>
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </button>
                    </div>

                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Select which specialized agent handles your request. Click the pill button to choose from 15 available modes.
                      </p>

                      {(() => {
                        const agentModes = [
                          { mode: 'Auto (Default)', description: 'System intelligently routes your query to the best agent' },
                          { mode: 'Agentic Search', description: 'Real-time web search combined with market data access' },
                          { mode: 'Risk Analysis', description: 'VaR, Monte Carlo, portfolio optimization, and Greeks calculations' },
                          { mode: 'Filing Search', description: 'SEC filings, earnings transcripts, and insider trading data' },
                          { mode: 'Comparable Companies', description: 'Peer analysis using trading multiples and valuation ratios' },
                          { mode: 'Chart Analysis', description: 'Technical analysis with chart pattern recognition' },
                          { mode: 'Quant Coding', description: 'Custom quantitative implementations with code interpreter' },
                          { mode: 'DCF Valuation', description: 'Discounted cash flow models and intrinsic value analysis' },
                          { mode: 'Options Analytics', description: 'Options chains, implied volatility, Greeks, and payoff modeling' },
                          { mode: 'Derivatives Structuring', description: 'Complex derivatives pricing (IRS, swaptions, CDS, exotic options)' },
                          { mode: 'Institutional Activity', description: '13F filings, insider trades, and congressional trading data' },
                          { mode: 'Alternatives Data', description: 'Cryptocurrency, forex, and commodities market data' },
                          { mode: 'Prediction Markets', description: 'Kalshi, Polymarket, and event probability analysis' },
                          { mode: 'Funds & Products', description: 'Mutual funds, ETFs, and hedge fund analysis' },
                          { mode: 'Private Markets', description: 'Private equity, M&A deals, LBOs, and infrastructure investments' },
                        ];

                        const startIdx = (agentModePage - 1) * ITEMS_PER_PAGE;
                        const endIdx = startIdx + ITEMS_PER_PAGE;
                        const paginatedModes = agentModes.slice(startIdx, endIdx);
                        const totalPages = Math.ceil(agentModes.length / ITEMS_PER_PAGE);

                        return (
                          <>
                            <table className="w-full border-collapse">
                              <thead>
                                <tr className="border-b border-gray-300">
                                  <th className="text-left py-2 px-3 text-sm font-semibold text-gray-900">Mode</th>
                                  <th className="text-left py-2 px-3 text-sm font-semibold text-gray-900">Description</th>
                                </tr>
                              </thead>
                              <tbody>
                                {paginatedModes.map((item, idx) => (
                                  <tr key={idx} className="border-b border-gray-200">
                                    <td className="py-2.5 px-3 text-sm text-gray-900 font-medium align-top">{item.mode}</td>
                                    <td className="py-2.5 px-3 text-sm text-gray-600 align-top">{item.description}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>

                            <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                              <button
                                onClick={() => setAgentModePage((p) => Math.max(1, p - 1))}
                                disabled={agentModePage === 1}
                                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Previous
                              </button>
                              <span className="text-xs text-gray-600">
                                Page {agentModePage} of {totalPages}
                              </span>
                              <button
                                onClick={() => setAgentModePage((p) => Math.min(totalPages, p + 1))}
                                disabled={agentModePage === totalPages}
                                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Next
                              </button>
                            </div>
                          </>
                        );
                      })()}

                      <div className="bg-gray-50 border border-gray-300 rounded p-3 text-xs text-gray-700">
                        <strong>Note:</strong> Selecting a specific mode bypasses automatic routing and gives you direct access to specialized agents and their tools.
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'model-selector' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Model Selector</h2>
                      <button
                        type="button"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 12px',
                          fontSize: '14px',
                          background: 'transparent',
                          border: '1px solid #E5E5E5',
                          cursor: 'pointer',
                          color: '#323130',
                          borderRadius: '6px',
                          fontWeight: '500',
                        }}
                      >
                        <img
                          src="/src/assets/model-logos/gpt-logo.png"
                          alt="GPT-6.1 Sol"
                          style={{ width: '20px', height: '20px', borderRadius: '4px' }}
                        />
                        <span>GPT-6.1 Sol</span>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ opacity: 0.5 }}>
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </button>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Choose from multiple AI models organized into 4 categories. Each model has different capabilities, pricing, and context limits. Click the dropdown to switch models.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <div>
                            <strong>Fast and Cost-Efficient:</strong> GPT-6 Luna, Claude Haiku 4.5, Gemini 3.5 Flash Lite, Grok 4.20 Fast
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <div>
                            <strong>Versatile and Highly Intelligent:</strong> GPT-6.1 Sol, Claude Sonnet 5.5, Gemini 3.8 Flash
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <div>
                            <strong>Most Powerful at Complex Tasks:</strong> GPT-6 Astra, Claude Fable 5.1, Claude Opus 5.5, Gemini 4 Argon, Grok 4.7, Kimi K3, Qwen 3.8 Max, GLM-5.3
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <div>
                            <strong>Search Models:</strong> Perplexity Sonar (search mode always active)
                          </div>
                        </div>
                      </div>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Per-Thread Selection:</strong> Each conversation can use a different model</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Context Limits:</strong> Displayed in model descriptions (e.g., "300K tokens")</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Beta Models:</strong> Some models show "Beta" badges for experimental features</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Coming Soon:</strong> Llama 4 Scout on AWS Bedrock</span>
                        </div>
                      </div>

                      <div className="bg-gray-50 border border-gray-300 rounded p-3 text-xs text-gray-700">
                        <strong>See more:</strong> <a href="#models" className="text-blue-600 hover:underline">Complete model list and specifications</a>
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'search-mode' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Search Mode</h2>
                      <Compass size={20} style={{ color: '#6b7280' }} />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Toggle web search integration to enhance your queries with real-time information from the internet.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Activation:</strong> Click the compass icon to toggle search mode on/off</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Behavior:</strong> Automatically prepends <code className="bg-gray-100 px-1 rounded text-xs">/search</code> to your message</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Auto-enable:</strong> Always active when using Perplexity Sonar models</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Disabled:</strong> Not available for DeepSeek models</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Visual Indicator:</strong> Compass icon turns blue when search mode is active</span>
                        </div>
                      </div>

                      <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-gray-700">
                        <strong className="text-blue-900">Dynamic Placeholder:</strong> The input placeholder changes based on the selected model:
                        <ul className="mt-1 ml-4 space-y-0.5">
                          <li>• "Search the web with Perplexity..." (Perplexity models)</li>
                          <li>• "Search portfolios, calculations, market data..." (Search mode on)</li>
                          <li>• "How can I help you?" (Default)</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'analyst-mode' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Analyst Mode</h2>
                      <Columns size={20} style={{ color: '#6b7280' }} />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Enable split-screen Results Panel to view charts, reasoning, execution logs, sources, data tables, and raw JSON alongside the chat. Access by clicking the + icon in the input area, then toggle the Analyst Mode switch.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Activation:</strong> Click the + icon first, then toggle the Analyst Mode switch</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Charts Tab:</strong> View Plotly interactive charts and visualizations</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Reasoning Tab:</strong> Inspect the model's internal reasoning process</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Execution Tab:</strong> Review tool calls, inputs, outputs, and execution time</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Sources Tab:</strong> Access web sources and citations with external links</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Data Tab:</strong> View structured data tables with key-value pairs</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>JSON Tab:</strong> Copy or inspect the raw response JSON</span>
                        </div>
                      </div>

                      <div className="bg-gray-50 border border-gray-300 rounded p-3 text-xs text-gray-700">
                        <strong>Use Cases:</strong> Debugging agent responses, auditing data sources, reviewing calculation steps, examining tool execution logs, inspecting chart data, copying structured output
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'prompt-library' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Prompt Library</h2>
                      <button
                        type="button"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '6px 12px',
                          background: 'transparent',
                          border: '1px solid #E5E5E5',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          color: '#323130',
                          fontSize: '14px',
                          fontWeight: '500',
                        }}
                      >
                        <Library size={16} strokeWidth={2} />
                        <span>Prompt Library</span>
                      </button>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Access pre-written templates for 11 specialized agents. Located in the top bar next to the model selector.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Usage:</strong> Click button → hover over agent category → select template</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Categories:</strong> Agentic Search, Risk Analysis, Filing Search, Comparable Companies, Chart Analysis, Quant Coding, DCF Valuation, Options Analytics, Alternatives Data, Institutional Activity, Prediction Markets</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Templates:</strong> 5-6 pre-written prompts per agent, editable before sending</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'export-buttons' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Export Buttons</h2>
                      <div className="flex items-center gap-2">
                        {/* Copy button */}
                        <button
                          type="button"
                          title="Copy message"
                          style={{
                            padding: '5px',
                            background: 'transparent',
                            border: '1px solid #0051cc',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '4px',
                          }}
                        >
                          <Copy size={14} color="#0051cc" strokeWidth={2} />
                        </button>
                        {/* PDF button */}
                        <button
                          type="button"
                          title="Export as PDF"
                          style={{
                            padding: '5px',
                            background: 'transparent',
                            border: '1px solid #0051cc',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '4px',
                          }}
                        >
                          <FileText size={14} color="#0051cc" strokeWidth={2} />
                        </button>
                        {/* PowerPoint button */}
                        <button
                          type="button"
                          title="Export as PowerPoint"
                          style={{
                            padding: '5px',
                            background: 'transparent',
                            border: '1px solid #0051cc',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '4px',
                          }}
                        >
                          <Presentation size={14} color="#0051cc" strokeWidth={2} />
                        </button>
                        {/* Excel button */}
                        <button
                          type="button"
                          title="Export as Excel"
                          style={{
                            padding: '5px',
                            background: 'transparent',
                            border: '1px solid #0051cc',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '4px',
                          }}
                        >
                          <Sheet size={14} color="#0051cc" strokeWidth={2} />
                        </button>
                        {/* Style selector button */}
                        <button
                          type="button"
                          title="Select export style"
                          style={{
                            padding: '5px',
                            background: 'transparent',
                            border: '1px solid #0051cc',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '4px',
                          }}
                        >
                          <Pencil size={14} color="#0051cc" strokeWidth={2} />
                        </button>
                      </div>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Export AI responses in multiple formats. Five export options appear below each intelligence card.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Options:</strong> Copy message, PDF export (Gamma), PowerPoint (PPTX), Excel/CSV (ZIP), Style selector</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Processing:</strong> Loading spinners show estimated generation times (30s-3min depending on format)</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Customization:</strong> Configure export styles (logo, theme, language, tone) in Settings page</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'compaction' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Compaction</h2>
                      <RefreshCw size={20} style={{ color: '#f59e0b' }} />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Automatic conversation optimization when switching between models with different context windows. Ensures conversation history fits within the new model's token limits while preserving critical information.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Trigger:</strong> Automatically activates when switching model providers (e.g., OpenAI → Claude, Gemini → GPT) with different context limits</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Process:</strong> Intelligently summarizes older messages while preserving recent exchanges, user intent, portfolio data, and key analysis results</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Indicator:</strong> Shows "Compacting [MODEL] → [MODEL]" notification in chat header with spinner during optimization</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Context Priority:</strong> Maintains complete recent messages (last 5-10), current portfolio context, active analysis, and critical data points from earlier conversation</span>
                        </div>
                      </div>

                      <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-gray-700">
                        <strong>Note:</strong> Compaction is seamless and requires no user action. Conversation continuity is maintained across model switches.
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'data-types' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Response Types</h2>
                      <BarChart3 size={20} style={{ color: '#6b7280' }} />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Different formats the AI uses to present analysis results and information.
                      </p>

                      <div className="space-y-3">
                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">REGULAR CHAT</div>
                          <p className="text-sm text-gray-700">Standard conversational responses with formatted text, explanations, and analysis. Supports markdown formatting including bold, italics, lists, and code blocks.</p>
                        </div>

                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">TABLES</div>
                          <p className="text-sm text-gray-700">Structured data displayed in markdown tables with sortable columns. Common for financial metrics, comparison analysis, portfolio holdings, and statistical summaries.</p>
                        </div>

                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">CHARTS</div>
                          <p className="text-sm text-gray-700">Interactive Plotly visualizations including line charts, bar charts, candlestick charts, scatter plots, and heatmaps. Supports zoom, pan, and hover tooltips.</p>
                        </div>

                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">ARTIFACTS</div>
                          <p className="text-sm text-gray-700">Generated files and downloadable content including PDF reports, Excel workbooks, CSV exports, and Python code. Appears with download buttons below the message.</p>
                        </div>

                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">CODE EXECUTION</div>
                          <p className="text-sm text-gray-700">Python code blocks with execution output shown in expandable panels. Used for quantitative analysis, custom calculations, and data processing tasks.</p>
                        </div>

                        <div className="border-l-4 border-gray-400 pl-3">
                          <div className="text-xs font-semibold text-gray-700 mb-1">MIXED RESPONSES</div>
                          <p className="text-sm text-gray-700">Combinations of text, tables, charts, and artifacts in a single response. Common for comprehensive analysis that includes explanation, data, and visualizations.</p>
                        </div>
                      </div>

                      <div className="bg-gray-50 border-l-4 border-gray-400 p-3 text-xs text-gray-700">
                        <strong>Note:</strong> Response type is automatically selected based on your query. You can request specific formats (e.g., "show as a table" or "create a chart").
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'deep-analysis' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Deep Analysis Mode</h2>
                      <Brain size={20} style={{ color: '#6b7280' }} />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Enable multi-agent collaboration for more thorough analysis. Access this feature by clicking the + icon in the input area, then toggle the Brain icon. Multiple specialized agents work together without requiring manual approvals.
                      </p>

                      <div className="space-y-2.5 text-sm text-gray-700">
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Activation:</strong> Click the + icon first, then toggle the Brain icon for Deep Analysis mode</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Multi-Agent Collaboration:</strong> Supervisor can route to multiple specialized agents sequentially</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>No Interruptions:</strong> Agents collaborate automatically without stopping for approvals</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span><strong>Use Cases:</strong> Comprehensive research, cross-domain analysis, complex valuations</span>
                        </div>
                      </div>

                      <div className="bg-purple-50 border border-purple-200 rounded p-3 text-xs text-gray-700">
                        <strong className="text-purple-900">Example:</strong> A query about "AAPL valuation and risks" might route to:
                        <ul className="mt-1 ml-4 space-y-0.5">
                          <li>1. Generalist Agent (fetch financial data)</li>
                          <li>2. DCF Agent (build valuation model)</li>
                          <li>3. Risk Specialist (calculate portfolio risks)</li>
                          <li>4. Comparable Companies (peer analysis)</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {complicationSection === 'cloud' && (
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <h2 className="text-lg font-bold text-gray-900">Cloud Storage Integration</h2>
                      <button
                        type="button"
                        style={{
                          padding: '8px',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          borderRadius: '50%',
                        }}
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                          <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
                        </svg>
                      </button>
                    </div>

                    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                      <p className="text-sm text-gray-700">
                        Attach files directly from your cloud storage providers. OAuth integration provides secure access to your files.
                      </p>

                      <div className="space-y-3">
                        <div className="border-l-4 border-blue-500 pl-3 flex items-center gap-2">
                          <img src="/connector-logos/google-drive.png" alt="Google Drive" style={{ width: '24px', height: 'auto' }} />
                          <div>
                            <div className="font-semibold text-sm text-gray-900">Google Drive</div>
                            <div className="text-xs text-gray-600 mt-1">Native picker with OAuth integration for seamless file selection</div>
                          </div>
                        </div>
                        <div className="border-l-4 border-blue-400 pl-3 flex items-center gap-2">
                          <img src="/connector-logos/one-drive.png" alt="OneDrive" style={{ width: '24px', height: 'auto' }} />
                          <div>
                            <div className="font-semibold text-sm text-gray-900">OneDrive Personal</div>
                            <div className="text-xs text-gray-600 mt-1">Microsoft Graph API integration for personal accounts</div>
                          </div>
                        </div>
                        <div className="border-l-4 border-blue-600 pl-3 flex items-center gap-2">
                          <img src="/connector-logos/one-drive.png" alt="OneDrive Business" style={{ width: '24px', height: 'auto' }} />
                          <div>
                            <div className="font-semibold text-sm text-gray-900">OneDrive Business</div>
                            <div className="text-xs text-gray-600 mt-1">Enterprise account support with work/school credentials</div>
                          </div>
                        </div>
                        <div className="border-l-4 border-blue-700 pl-3 flex items-center gap-2">
                          <img src="/connector-logos/one-drive.png" alt="SharePoint" style={{ width: '24px', height: 'auto' }} />
                          <div>
                            <div className="font-semibold text-sm text-gray-900">SharePoint</div>
                            <div className="text-xs text-gray-600 mt-1">Team site file access for collaborative documents</div>
                          </div>
                        </div>
                      </div>

                      <div className="bg-green-50 border border-green-200 rounded p-3 text-xs text-gray-700">
                        <strong className="text-green-900">Visual Indicators:</strong> Files attached from cloud storage display provider icons (Google Drive or OneDrive logo) instead of the standard paperclip icon.
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tools Tab */}
          {activeTab === 'tools' && (() => {
            const allCategories = Object.entries(toolCategories);
            const totalPages = Math.ceil(allCategories.length / TOOL_CATEGORIES_PER_PAGE);
            const startIdx = (toolCategoriesPage - 1) * TOOL_CATEGORIES_PER_PAGE;
            const displayCategories = allCategories.slice(startIdx, startIdx + TOOL_CATEGORIES_PER_PAGE);

            return (
              <div className="p-6 space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900 mb-2">Tools & MCP Servers</h3>
                  <p className="text-sm text-gray-600">
                    Data sources and capabilities. Click to expand.
                  </p>
                </div>

                <div className="space-y-2">
                  {displayCategories.map(([key, category]) => {
                    const Icon = category.icon;
                    const isExpanded = expandedTools.has(key);

                    return (
                      <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleToolCategory(key)}
                          className="w-full flex items-center justify-between p-2.5 bg-white hover:bg-gray-50 transition-colors text-left"
                        >
                          <div className="flex items-center gap-2.5">
                            <Icon size={16} style={{ color: category.color }} />
                            <div>
                              <span className="font-medium text-sm text-gray-900">{category.name}</span>
                              <span className="text-xs text-gray-500 ml-1.5">({category.tools.length})</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">{category.availability}</span>
                            {isExpanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="px-3 py-2.5 border-t border-gray-200 bg-gradient-to-b from-gray-50 to-white">
                            <p className="text-xs text-gray-600 mb-2.5 italic">{category.description}</p>
                            <div className="space-y-1.5">
                              {category.tools.map((tool, idx) => (
                                <div key={idx} className="p-2 bg-white rounded border border-gray-100 hover:border-gray-200 hover:shadow-sm transition-all">
                                  <code className="text-xs font-mono font-semibold text-gray-900">{tool.name}</code>
                                  <p className="text-xs text-gray-600 mt-0.5 leading-snug">{tool.desc}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                    <button
                      onClick={() => setToolCategoriesPage(p => Math.max(1, p - 1))}
                      disabled={toolCategoriesPage === 1}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ← Previous
                    </button>
                    <span className="text-xs text-gray-500">
                      Page {toolCategoriesPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setToolCategoriesPage(p => Math.min(totalPages, p + 1))}
                      disabled={toolCategoriesPage === totalPages}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      Next →
                    </button>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Models Tab */}
          {activeTab === 'models' && (() => {
            // Flatten all models into a single array
            const allModels = modelCategories.flatMap(cat =>
              cat.models.map(model => ({ ...model, category: cat.name })),
            );
            const totalPages = Math.ceil(allModels.length / MODELS_PER_PAGE);
            const startIdx = (modelsPage - 1) * MODELS_PER_PAGE;
            const displayModels = allModels.slice(startIdx, startIdx + MODELS_PER_PAGE);

            return (
              <div className="p-6 space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900 mb-2">Available Models</h3>
                  <p className="text-sm text-gray-600">
                    <Terminal size={12} className="inline" /> Code • <Activity size={12} className="inline" /> Stream • <Globe size={12} className="inline" /> Search
                  </p>
                </div>

                {/* Paginated Models */}
                <div className="space-y-3">
                  {(() => {
                    let lastCategory = '';
                    return displayModels.map((model, idx) => {
                      const showCategoryHeader = model.category !== lastCategory;
                      lastCategory = model.category;

                      return (
                        <div key={idx}>
                          {showCategoryHeader && (
                            <div className="text-xs font-semibold text-gray-700 mb-1.5 uppercase tracking-wide">
                              {model.category}
                            </div>
                          )}
                          <div className="flex items-center gap-3 p-2.5 bg-white rounded border border-gray-200">
                            <img src={model.logo} alt="" className="w-6 h-6 object-contain" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="font-medium text-sm text-gray-900 truncate">{model.name}</span>
                                <span className="text-xs text-gray-400">·</span>
                                <span className="text-xs text-gray-500">{formatContext(model.context)}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              {model.codeExec && <Terminal size={12} className="text-purple-600" />}
                              {model.streaming && <Activity size={12} className="text-green-600" />}
                              {model.webSearch && <Globe size={12} className="text-blue-600" />}
                            </div>
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                    <button
                      onClick={() => setModelsPage(p => Math.max(1, p - 1))}
                      disabled={modelsPage === 1}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ← Previous
                    </button>
                    <span className="text-xs text-gray-500">
                      Page {modelsPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setModelsPage(p => Math.min(totalPages, p + 1))}
                      disabled={modelsPage === totalPages}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      Next →
                    </button>
                  </div>
                )}

                {/* Compact Note */}
                <div className="p-3 bg-amber-50 rounded border border-amber-200 text-xs text-gray-700">
                  <strong className="text-amber-900">Note:</strong> Only OpenAI models support Code Interpreter.
                </div>
              </div>
            );
          })()}

        </div>
      </div>
    </>
  );
};

// Also export a simple trigger hook
export const useChatGuide = () => {
  const [isOpen, setIsOpen] = useState(false);
  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen(prev => !prev),
  };
};

export default ChatGuidePanel;


