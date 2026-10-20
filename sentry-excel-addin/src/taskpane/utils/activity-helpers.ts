import { ActivityGroup } from "../../shared/types";

let activityIdCounter = 0;

/* ── Static display names for every known tool ── */

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  // Excel — sheet ops
  excel_create_sheet: "Create sheet",
  excel_rename_sheet: "Rename sheet",
  excel_delete_sheet: "Delete sheet",
  excel_activate_sheet: "Activate sheet",
  excel_get_workbook_structure: "Get workbook structure",
  get_workbook_structure: "Get workbook structure",
  excel_get_sheet_summary: "Get sheet summary",
  get_sheet_summary: "Get sheet summary",
  excel_find_columns_by_header: "Find columns by header",
  find_columns_by_header: "Find columns by header",
  excel_read_range: "Read range",
  read_range: "Read range",
  excel_write_range: "Write range",
  write_range: "Write range",

  // Excel — cell ops
  excel_write_values: "Write cell values",
  excel_write_formulas: "Write formulas",
  excel_format_range: "Format cells",
  excel_clear_range: "Clear range",
  excel_insert_rows: "Insert rows",
  excel_delete_rows: "Delete rows",
  excel_autofit_columns: "Auto-fit columns",
  excel_set_column_widths: "Set column widths",
  excel_freeze_panes: "Freeze panes",
  excel_copy_range: "Copy range",
  excel_sort_range: "Sort range",

  // Excel — objects & decoration
  excel_create_chart: "Create chart",
  excel_create_table: "Create table",
  excel_add_conditional_format: "Add conditional format",
  excel_add_data_validation: "Add data validation",
  excel_add_named_range: "Add named range",
  excel_auto_filter: "Add auto-filter",
  excel_pivot_table: "Create pivot table",
  excel_scenario_table: "Create scenario table",
  excel_annotations: "Add annotations",
  excel_structure: "Structure sheet",
  excel_sheet_config: "Configure sheet",
  generate_vba_macro: "Generate VBA macro",
  bh_dump_to_excel: "Export data to Excel",
  fill_column_from_bh_lookup: "Fill column via lookup",

  // BinomialHash — data
  bh_retrieve: "Query dataset",
  bh_aggregate: "Aggregate data",
  bh_query: "Filter dataset",
  bh_schema: "Get dataset schema",
  bh_group_by: "Group & aggregate",
  bh_to_excel: "Export to Excel",

  // BinomialHash — manifold
  bh_manifold_state: "Inspect manifold state",
  bh_manifold_insights: "Get manifold insights",
  bh_navigate: "Navigate manifold",
  bh_manifold_slice: "Slice manifold",
  bh_geodesic: "Find geodesic path",
  bh_walk_axis: "Walk axis",
  bh_multiscale_view: "Multiscale view",
  bh_orbit: "Compute orbit",
  bh_frontier: "Find frontier",
  bh_basin: "Analyze basin",
  bh_ridge_trace: "Trace ridge",
  bh_valley_trace: "Trace valley",
  bh_coverage_audit: "Run coverage audit",
  bh_wrap_audit: "Run wrap audit",

  // BinomialHash — analytics
  bh_regress: "Run regression",
  bh_partial_corr: "Partial correlation",
  bh_pca_surface: "PCA surface",
  bh_dependency_screen: "Screen dependencies",
  bh_solver: "Run solver",

  // Valuation
  analyze_comparable_companies: "Run comps analysis",
  gather_dcf_data_sources: "Gather DCF inputs",
  analyze_three_stage_dcf: "Run 3-stage DCF",
  analyze_two_stage_dcf: "Run 2-stage DCF",
  analyze_stable_stage_dcf: "Run stable DCF",
  analyze_reverse_dcf: "Run reverse DCF",
  analyze_epv: "Run EPV valuation",
  analyze_monte_carlo_dcf: "Run Monte Carlo DCF",
  analyze_rim: "Run residual income model",
  dcf_sensitivity_analysis: "DCF sensitivity analysis",

  // Structuring
  price_interest_rate_swap: "Price interest rate swap",
  price_swaption: "Price swaption",
  price_credit_default_swap: "Price CDS",
  price_variance_swap: "Price variance swap",
  price_dispersion_trade: "Price dispersion trade",
  price_exotic_derivatives: "Price exotic derivative",

  // Risk
  calculate_var: "Calculate VaR",
  run_monte_carlo: "Run Monte Carlo",
  optimize_portfolio: "Optimize portfolio",
  analyze_barra_factors: "Analyze Barra factors",
  create_hedge_portfolio: "Create hedge portfolio",
  analyze_fft_trends: "Analyze FFT trends",
  calculate_rolling_correlation: "Rolling correlation",
  calculate_implied_correlation: "Implied correlation",
  stress_test_correlation: "Stress-test correlation",
  analyze_graph_theory_risk: "Graph-theory risk analysis",
  analyze_systemic_risk_score: "Systemic risk score",
  find_optimal_hedge_path: "Find optimal hedge path",

  // Quant — options & greeks
  price_equity_options: "Price options",
  model_volatility_surface: "Model vol surface",
  model_greeks_surface: "Model Greeks surface",
  analyze_dealer_gamma_regime: "Dealer gamma regime",
  analyze_vanna_charm_flow: "Vanna / charm flow",
  analyze_iv_rv_vs_peers: "IV vs RV screener",
  detect_signal_confluence: "Detect signal confluence",
  analyze_earnings_patterns: "Earnings patterns",
  analyze_gex_levels: "Analyze GEX levels",
  scan_nope_divergences: "Scan NOPE divergences",
  detect_squeeze_setup: "Detect squeeze setup",
  analyze_pca_eigen_portfolios: "PCA eigen-portfolios",
  analyze_correlation_matrix: "Correlation matrix",
  calculate_delta_exposure: "Delta exposure",
  calculate_gamma_exposure: "Gamma exposure",
  calculate_vega_exposure: "Vega exposure",
  calculate_theta_decay: "Theta decay",
  calculate_cross_greeks: "Cross Greeks",
  construct_dynamic_hedge: "Dynamic hedge",
  price_correlation_swap: "Price correlation swap",

  // Portfolio
  list_user_portfolios: "List portfolios",
  get_portfolio: "Get portfolio",
  set_active_portfolio: "Set active portfolio",
  get_active_portfolio: "Get active portfolio",

  // Memory
  save_to_memory: "Save to notebook",
  recall_memory: "Recall from notebook",

  // Sentiment
  analyze_news_sentiment: "Analyze news sentiment",

  // Utility
  web_search: "Search the web",
  read_file_content: "Read uploaded file",

  // Bloomberg
  bloomberg_bdp: "Bloomberg data point",
  bloomberg_bdh: "Bloomberg time series",
  bloomberg_bds: "Bloomberg bulk data",
  bloomberg_bql: "Bloomberg BQL query",
  bloomberg_formula: "Bloomberg formula",
  search_bloomberg_fields: "Search Bloomberg fields",

  // FMP — Market Data
  discover_fields: "Discover data fields",
  discover_market_wide_fields: "Discover market fields",
  discover_valuation_fields: "Discover valuation fields",
  discover_technical_fields: "Discover technical fields",
  run_stock_screener: "Run stock screener",
  get_fields: "Get data fields",
  list_datasets: "List available datasets",
  get_historical_data: "Fetch price history",
  list_cached_fields: "List cached fields",
  get_latest_news: "Fetch latest news",
  get_news_by_symbol: "Fetch news",

  // FMP — Valuation
  discover_dcf_fields: "Discover DCF fields",
  discover_forecast_fields: "Discover forecast fields",
  get_dcf_data: "Fetch DCF data",
  get_valuation_dataset: "Fetch valuation data",
  get_forecast_data: "Fetch forecast data",
  calculate_wacc_inputs: "Calculate WACC inputs",
  get_growth_estimates: "Fetch growth estimates",
  list_valuation_datasets: "List valuation datasets",

  // FMP — Documents
  list_document_types: "List document types",
  discover_documents: "Discover documents",
  get_document_fields: "Get document fields",
  get_raw_document: "Fetch raw document",
  get_document_dataset: "Fetch document data",

  // FMP — Alternatives
  discover_alternatives_fields: "Discover alt-data fields",
  get_alternatives_dataset: "Fetch market data",
  get_crypto_quote: "Fetch crypto quote",
  get_crypto_historical: "Fetch crypto history",
  list_crypto: "List crypto assets",
  get_forex_quote: "Fetch FX quote",
  get_forex_historical: "Fetch FX rates",
  list_forex: "List FX pairs",
  get_commodities_data: "Fetch commodities data",
  get_batch_quotes: "Fetch batch quotes",
  get_latest_alternatives_news: "Fetch alt-data news",
  get_alternatives_news_by_symbol: "Fetch alt-data news",
  list_alternatives_datasets: "List alt-data datasets",

  // FMP — Trade Flow
  discover_institutional_fields: "Discover institutional fields",
  get_tradeflow_dataset: "Fetch trade-flow data",
  get_13f_holdings: "Fetch 13F holdings",
  get_insider_trading: "Fetch insider trades",
  get_congressional_trades: "Fetch congressional trades",
  get_etf_holdings: "Fetch ETF holdings",
  get_esg_ratings: "Fetch ESG ratings",
  list_tradeflow_datasets: "List trade-flow datasets",
  get_ma_activity: "Fetch M&A activity",
  get_ipo_data: "Fetch IPO data",
  get_institutional_activity: "Fetch institutional activity",

  // Economic Data
  search_economic_series: "Search economic data",
  get_economic_data: "Fetch economic data",
  get_release_calendar: "Fetch release calendar",
  search_by_country: "Search by country",
  search_by_source: "Search by source",
  get_series_info: "Get series info",
  compare_series: "Compare data series",
  get_release_series: "Fetch release data",

  // YFinance
  discover_market_fields: "Discover market fields",
  list_market_fields: "List market fields",
  get_market_data: "Fetch market data",
  yf_historical_data: "Fetch price history",

  // Polygon Options/Futures
  discover_polygon_options_fields: "Discover options fields",
  discover_polygon_options_technical_fields: "Discover options technicals",
  list_polygon_options_datasets: "List options datasets",
  get_polygon_options_dataset: "Fetch options data",
  get_polygon_options_aggregates: "Fetch options aggregates",
  get_option_chain: "Fetch options chain",
  get_polygon_options_snapshot: "Fetch options snapshot",
  list_polygon_options_cached_fields: "List cached options fields",
  get_polygon_options_market_status: "Options market status",

  // UW — Options
  uw_flow_alerts: "Check flow alerts",
  uw_greek_flow: "Fetch Greek flow",
  uw_gex: "Fetch GEX data",
  uw_flow_summary: "Fetch flow summary",
  uw_volatility: "Fetch volatility data",
  uw_option_chain: "Fetch options chain",
  uw_contract_data: "Fetch contract data",
  uw_oi_change: "Fetch OI changes",
  uw_net_flow_expiry: "Fetch net flow by expiry",
  uw_sentiment: "Fetch sentiment data",
  uw_hottest_contracts: "Fetch hottest contracts",
  uw_options_volume: "Fetch options volume",
  uw_greeks: "Fetch Greeks",
  uw_option_price_levels: "Fetch option price levels",

  // UW — Market
  uw_earnings: "Fetch earnings data",
  uw_correlations: "Fetch correlations",
  uw_market_overview: "Fetch market overview",
  uw_analyst_ratings: "Fetch analyst ratings",
  uw_stock_screener: "Run stock screener",
  uw_seasonality: "Fetch seasonality data",
  uw_short_data: "Fetch short interest",

  // UW — Institutional
  uw_congress: "Fetch congressional trades",
  uw_darkpool: "Fetch dark-pool data",
  uw_insider: "Fetch insider trades",
  uw_institution: "Fetch institutional data",
  uw_ownership: "Fetch ownership data",
  uw_institutions_list: "List institutions",
  uw_etf: "Fetch ETF data",

  // Batch tools
  get_market_data_batch: "Fetch market data batch",
  code_interpreter: "Run calculation",
  get_fields_batch: "Fetch financial metrics",

  // Test tools
  cancer_test_bh: "Synthetic genomics test",
  hotsauce_test_bh: "Synthetic order-book test",
};

/* ── FMP dataset slug → friendly name ── */

const DATASET_DISPLAY_NAMES: Record<string, string> = {
  "forex-historical-eod-light": "FX history",
  "forex-historical-eod": "FX history",
  "forex-intraday": "FX intraday",
  "historical-chart-1day": "daily prices",
  "historical-chart-4hour": "4h prices",
  "historical-chart-1hour": "1h prices",
  "historical-price-full": "price history",
  "historical-price-eod-light": "price history",
  "company-profile": "profile",
  "company-quote": "quote",
  "company-outlook": "outlook",
  "institutional-holders": "institutional holders",
  "institutional-holder-rss-feed": "institutional filings",
  "mutual-fund-holders": "mutual fund holders",
  "etf-holders": "ETF holders",
  "insider-trading": "insider trades",
  "insider-roster": "insider roster",
  "discounted-cash-flow": "DCF",
  "advanced-dcf": "advanced DCF",
  "levered-dcf": "levered DCF",
  "income-statement": "income statement",
  "income-statement-quarterly": "quarterly income statement",
  "balance-sheet": "balance sheet",
  "balance-sheet-quarterly": "quarterly balance sheet",
  "cash-flow-statement": "cash flow statement",
  "cash-flow-statement-quarterly": "quarterly cash flow",
  "key-metrics": "key metrics",
  "key-metrics-quarterly": "quarterly key metrics",
  "financial-ratios": "ratios",
  "financial-ratios-quarterly": "quarterly ratios",
  "financial-growth": "financial growth",
  "enterprise-value": "enterprise value",
  "analyst-estimates": "analyst estimates",
  "analyst-estimates-quarterly": "quarterly estimates",
  "earnings": "earnings",
  "earnings-surprises": "earnings surprises",
  "earnings-calendar": "earnings calendar",
  "sec-filings": "SEC filings",
  "press-releases": "press releases",
  "stock-dividend": "dividends",
  "stock-split": "stock splits",
  "shares-float": "shares float",
  "crypto-historical-eod-light": "crypto history",
  "crypto-intraday": "crypto intraday",
  "commodities-historical-eod-light": "commodities history",
  "congressional-trading": "congressional trades",
  "senate-trading": "Senate trades",
  "house-trading": "House trades",
  "13f-filings": "13F filings",
  "esg-ratings": "ESG ratings",
  "ipo-calendar": "IPO calendar",
  "etf-holdings": "ETF holdings",
  "merger-acquisition": "M&A activity",
};

/* ── FRED series ID → friendly name ── */

const SERIES_DISPLAY_NAMES: Record<string, string> = {
  GDP: "GDP",
  GDPC1: "Real GDP",
  GNPCA: "Real GNP",
  CPIAUCSL: "CPI",
  CPIAUCNS: "CPI (NSA)",
  CPILFESL: "Core CPI",
  CPILFENS: "Core CPI (NSA)",
  PCEPI: "PCE Price Index",
  PCEPILFE: "Core PCE",
  UNRATE: "Unemployment Rate",
  PAYEMS: "Nonfarm Payrolls",
  ICSA: "Initial Jobless Claims",
  DGS10: "10Y Treasury",
  DGS2: "2Y Treasury",
  DGS5: "5Y Treasury",
  DGS30: "30Y Treasury",
  DGS1: "1Y Treasury",
  DTB3: "3M T-Bill",
  FEDFUNDS: "Fed Funds Rate",
  DFEDTARU: "Fed Funds Upper",
  DFEDTARL: "Fed Funds Lower",
  T10Y2Y: "10Y-2Y Spread",
  T10Y3M: "10Y-3M Spread",
  T10YIE: "10Y Breakeven Inflation",
  VIXCLS: "VIX",
  DTWEXBGS: "USD Index",
  DEXUSEU: "USD/EUR",
  DEXJPUS: "JPY/USD",
  DEXUSUK: "USD/GBP",
  M2SL: "M2 Money Supply",
  WALCL: "Fed Balance Sheet",
  UMCSENT: "Consumer Sentiment",
  RSXFS: "Retail Sales",
  INDPRO: "Industrial Production",
  HOUST: "Housing Starts",
  HSN1F: "New Home Sales",
  CSUSHPINSA: "Case-Shiller Home Price",
  BAMLH0A0HYM2: "HY OAS Spread",
  BAMLC0A0CM: "IG OAS Spread",
  SP500: "S&P 500",
  NASDAQCOM: "Nasdaq Composite",
  DJIA: "Dow Jones",
  WILL5000INDFC: "Wilshire 5000",
};

function humanizeSlug(slug: string): string {
  return slug.replace(/-/g, " ");
}

function friendlyDataset(raw: string): string {
  return DATASET_DISPLAY_NAMES[raw] ?? humanizeSlug(raw);
}

function friendlySeries(raw: string): string {
  return SERIES_DISPLAY_NAMES[raw] ?? raw;
}

function friendlyBhKey(raw: string): string {
  const base = raw.replace(/_[0-9a-f]{6}$/, "");
  let display = TOOL_DISPLAY_NAMES[base];
  if (display) {
    return display.replace(/^(Fetch|Get|List|Run|Search|Discover|Calculate|Analyze)\s+/i, "");
  }
  // Try stripping a trailing _<ticker> suffix (e.g. get_fields_batch_aap → get_fields_batch)
  const withoutTicker = base.replace(/_[a-z0-9]+$/, "");
  display = TOOL_DISPLAY_NAMES[withoutTicker];
  if (display) {
    return display.replace(/^(Fetch|Get|List|Run|Search|Discover|Calculate|Analyze)\s+/i, "");
  }
  return base.replace(/^(get|fetch|list|discover|search|analyze|calculate)_/, "").replace(/_/g, " ");
}

/* ── Parameter extractors ── */

function sym(params: Record<string, unknown>): string | undefined {
  const v = params.symbol || params.ticker || params.underlying || params.target_ticker;
  if (typeof v === "string" && v.length <= 12) return v.toUpperCase();
  return undefined;
}

function tickerList(params: Record<string, unknown>): string | undefined {
  const v = params.tickers || params.symbols;
  if (Array.isArray(v) && v.length > 0 && v.length <= 5) {
    return v.map((t: unknown) => String(t).toUpperCase()).join(", ");
  }
  if (typeof v === "string" && v.includes(",")) {
    const parts = v.split(",").map(t => t.trim().toUpperCase()).filter(Boolean);
    if (parts.length <= 5) return parts.join(", ");
  }
  return undefined;
}

function tickerPair(params: Record<string, unknown>): string | undefined {
  const x = params.ticker_x;
  const y = params.ticker_y;
  if (typeof x === "string" && typeof y === "string") return `${x.toUpperCase()} / ${y.toUpperCase()}`;
  return undefined;
}

function fxPair(params: Record<string, unknown>): string | undefined {
  if (typeof params.pair === "string") return params.pair.toUpperCase();
  if (params.from && params.to) return `${String(params.from).toUpperCase()}/${String(params.to).toUpperCase()}`;
  return undefined;
}

function sh(params: Record<string, unknown>): string | undefined {
  const v = params.sheet || params.sheetName || params.sheet_name;
  return typeof v === "string" ? v : undefined;
}

function rng(params: Record<string, unknown>): string | undefined {
  const v = params.range || params.data_range || params.source_range;
  return typeof v === "string" ? v : undefined;
}

function ds(params: Record<string, unknown>): string | undefined {
  const v = params.dataset || params.key || params.table;
  return typeof v === "string" ? v : undefined;
}

function seriesId(params: Record<string, unknown>): string | undefined {
  const v = params.series_id;
  return typeof v === "string" ? v : undefined;
}

function loc(sheet?: string, range?: string): string {
  if (sheet && range) return `${range} in ${sheet} sheet`;
  return sheet || range || "";
}

/**
 * Parameter-aware label builder. Returns undefined when no enrichment applies,
 * letting the caller fall back to the static dictionary.
 */
function dynamicLabel(tool: string, p: Record<string, unknown>): string | undefined {
  const s = sym(p);
  const tl = tickerList(p);
  const sOrList = s || tl;
  const sheet = sh(p);
  const range = rng(p);
  const where = loc(sheet, range);
  const dataset = ds(p);
  const series = seriesId(p);
  const pair = fxPair(p);
  const chartType = typeof p.chart_type === "string" ? p.chart_type : undefined;
  const chartTitle = typeof p.title === "string" ? p.title : undefined;
  const objective = typeof p.objective === "string" ? p.objective : undefined;
  const query = typeof p.query === "string" ? p.query : undefined;
  const country = typeof p.country === "string" ? p.country : undefined;
  const source = typeof p.source === "string" ? p.source : undefined;
  const name = typeof p.name === "string" ? p.name : undefined;

  switch (tool) {
    /* ── Excel — sheet / range context ── */
    case "excel_read_range":
    case "read_range":
      return where ? `Read ${where}` : undefined;
    case "excel_write_range":
    case "write_range":
      return where ? `Write to ${where}` : undefined;
    case "excel_write_values":
      return where ? `Write values to ${where}` : undefined;
    case "excel_write_formulas":
      return where ? `Write formulas to ${where}` : undefined;
    case "excel_get_sheet_summary":
    case "get_sheet_summary":
      return sheet ? `Summarize ${sheet}` : undefined;
    case "excel_find_columns_by_header":
    case "find_columns_by_header":
      return sheet ? `Find columns in ${sheet}` : undefined;
    case "excel_format_range":
      return where ? `Format ${where}` : undefined;
    case "excel_clear_range":
      return where ? `Clear ${where}` : undefined;
    case "excel_copy_range":
      return where ? `Copy ${where}` : undefined;
    case "excel_sort_range":
      return where ? `Sort ${where}` : undefined;
    case "excel_insert_rows":
      return sheet ? `Insert rows in ${sheet}` : undefined;
    case "excel_delete_rows":
      return sheet ? `Delete rows in ${sheet}` : undefined;
    case "excel_autofit_columns":
      return sheet ? `Auto-fit ${sheet} columns` : undefined;
    case "excel_set_column_widths":
      return sheet ? `Set ${sheet} column widths` : undefined;
    case "excel_freeze_panes":
      return sheet ? `Freeze panes in ${sheet}` : undefined;
    case "excel_add_conditional_format":
      return where ? `Conditional format on ${where}` : undefined;
    case "excel_add_data_validation":
      return where ? `Data validation on ${where}` : undefined;
    case "excel_add_named_range":
      return name ? `Name range "${name}"` : (where ? `Name range ${where}` : undefined);
    case "excel_auto_filter":
      return where ? `Auto-filter ${where}` : undefined;
    case "excel_create_chart": {
      const label = chartTitle || chartType;
      if (label && sheet) return `Create ${label} chart in ${sheet}`;
      if (label) return `Create ${label} chart`;
      return sheet ? `Create chart in ${sheet}` : undefined;
    }
    case "excel_create_table":
      return where ? `Create table at ${where}` : undefined;
    case "excel_pivot_table": {
      const src = typeof p.source_sheet === "string" ? p.source_sheet : undefined;
      const dst = typeof p.dest_sheet === "string" ? p.dest_sheet : undefined;
      if (src && dst) return `Pivot ${src} → ${dst}`;
      return src ? `Pivot from ${src}` : undefined;
    }
    case "excel_scenario_table":
      return sheet ? `Scenario table in ${sheet}` : undefined;
    case "excel_annotations":
      return sheet ? `Annotate ${sheet}` : undefined;
    case "excel_activate_sheet":
      return sheet ? `Activate ${sheet}` : undefined;
    case "excel_rename_sheet":
      return sheet ? `Rename ${sheet}` : undefined;
    case "excel_delete_sheet":
      return sheet ? `Delete ${sheet}` : undefined;
    case "excel_create_sheet": {
      const n = name || (typeof p.sheet_name === "string" ? p.sheet_name : undefined);
      return n ? `Create "${n}" sheet` : undefined;
    }
    case "excel_structure":
      return sheet ? `Structure ${sheet}` : undefined;
    case "excel_sheet_config":
      return sheet ? `Configure ${sheet}` : undefined;

    /* ── BH export to Excel ── */
    case "bh_dump_to_excel":
      return sheet ? `Export data to ${sheet}` : undefined;
    case "fill_column_from_bh_lookup": {
      const col = typeof p.column === "string" ? p.column : undefined;
      if (sheet && col) return `Fill ${sheet}!${col} via lookup`;
      return sheet ? `Fill column in ${sheet} via lookup` : undefined;
    }

    /* ── Discovery tools with symbol ── */
    case "discover_fields":
      return s ? `Discover ${s} fields` : undefined;
    case "discover_market_wide_fields":
      return s ? `Discover ${s} market fields` : undefined;
    case "discover_valuation_fields":
      return s ? `Discover ${s} valuation fields` : undefined;
    case "discover_technical_fields":
      return s ? `Discover ${s} technical fields` : undefined;
    case "discover_dcf_fields":
      return s ? `Discover ${s} DCF fields` : undefined;
    case "discover_forecast_fields":
      return s ? `Discover ${s} forecast fields` : undefined;
    case "discover_alternatives_fields":
      return s ? `Discover ${s} alt-data fields` : undefined;
    case "discover_institutional_fields":
      return s ? `Discover ${s} institutional fields` : undefined;
    case "discover_polygon_options_fields":
      return s ? `Discover ${s} options fields` : undefined;
    case "discover_polygon_options_technical_fields":
      return s ? `Discover ${s} options technicals` : undefined;

    /* ── FMP market data ── */
    case "get_fields_batch":
    case "get_market_data_batch": {
      const syms = p.symbols || p.tickers;
      const flds = p.fields;
      if (Array.isArray(syms) && syms.length > 0) {
        const tickerLabel = syms.length <= 4
          ? syms.map((t: unknown) => String(t).toUpperCase()).join(", ")
          : `${syms.length} stocks`;
        if (Array.isArray(flds) && flds.length > 0 && flds.length <= 3) {
          return `Fetch ${flds.join(", ")} for ${tickerLabel}`;
        }
        return `Fetch metrics for ${tickerLabel}`;
      }
      return undefined;
    }
    case "get_historical_data":
      return s ? `Fetch ${s} price history` : undefined;
    case "get_fields":
      return s ? `Fetch ${s} data fields` : undefined;
    case "get_news_by_symbol":
    case "get_alternatives_news_by_symbol":
      return s ? `Fetch ${s} news` : undefined;
    case "run_stock_screener":
      return dataset ? `Screen stocks — ${friendlyDataset(dataset)}` : undefined;

    /* ── FMP alternatives ── */
    case "get_alternatives_dataset":
      return s && dataset ? `Fetch ${s} ${friendlyDataset(dataset)}` : (s ? `Fetch ${s} market data` : (dataset ? `Fetch ${friendlyDataset(dataset)}` : undefined));
    case "get_forex_historical":
      return pair ? `Fetch ${pair} FX history` : undefined;
    case "get_forex_quote":
      return pair ? `Fetch ${pair} FX quote` : undefined;
    case "get_crypto_quote":
      return s ? `Fetch ${s} crypto quote` : undefined;
    case "get_crypto_historical":
      return s ? `Fetch ${s} crypto history` : undefined;
    case "get_commodities_data":
      return s ? `Fetch ${s} commodities data` : undefined;
    case "get_batch_quotes":
      return tl ? `Fetch quotes for ${tl}` : undefined;

    /* ── FMP valuation ── */
    case "get_dcf_data":
      return s ? `Fetch ${s} DCF data` : undefined;
    case "get_valuation_dataset":
      return s && dataset ? `Fetch ${s} ${friendlyDataset(dataset)}` : (s ? `Fetch ${s} valuation` : (dataset ? `Fetch ${friendlyDataset(dataset)}` : undefined));
    case "get_forecast_data":
      return s ? `Fetch ${s} forecasts` : undefined;
    case "calculate_wacc_inputs":
      return s ? `Calculate ${s} WACC` : undefined;
    case "get_growth_estimates":
      return s ? `Fetch ${s} growth estimates` : undefined;

    /* ── FMP documents ── */
    case "get_raw_document":
    case "get_document_dataset":
      return s && dataset ? `Fetch ${s} ${friendlyDataset(dataset)}` : (dataset ? `Fetch ${friendlyDataset(dataset)}` : (s ? `Fetch ${s} filings` : undefined));

    /* ── FMP trade flow ── */
    case "get_tradeflow_dataset":
      return s && dataset ? `Fetch ${s} ${friendlyDataset(dataset)}` : (s ? `Fetch ${s} trade flow` : (dataset ? `Fetch ${friendlyDataset(dataset)}` : undefined));
    case "get_13f_holdings":
      return s ? `Fetch ${s} 13F holdings` : undefined;
    case "get_insider_trading":
      return s ? `Fetch ${s} insider trades` : undefined;
    case "get_congressional_trades":
      return s ? `Fetch ${s} congressional trades` : undefined;
    case "get_etf_holdings":
      return s ? `Fetch ${s} ETF holdings` : undefined;
    case "get_esg_ratings":
      return s ? `Fetch ${s} ESG ratings` : undefined;
    case "get_ma_activity":
      return s ? `Fetch ${s} M&A activity` : undefined;
    case "get_ipo_data":
      return s ? `Fetch ${s} IPO data` : undefined;
    case "get_institutional_activity":
      return s ? `Fetch ${s} institutional activity` : undefined;

    /* ── Economic data ── */
    case "get_economic_data":
      return series ? `Fetch ${friendlySeries(series)} data` : undefined;
    case "search_economic_series":
      return query ? `Search "${query}"` : undefined;
    case "search_by_country":
      return country ? `Search ${country} economic data` : undefined;
    case "search_by_source":
      return source ? `Search ${source} data` : undefined;
    case "get_series_info":
      return series ? `Info for ${friendlySeries(series)}` : undefined;
    case "compare_series": {
      const ids = p.series_ids;
      if (Array.isArray(ids) && ids.length > 0) return `Compare ${ids.map((id: unknown) => friendlySeries(String(id))).join(", ")}`;
      return undefined;
    }

    /* ── YFinance ── */
    case "yf_historical_data":
      return s ? `Fetch ${s} price history` : undefined;
    case "get_market_data": {
      const field = typeof p.field === "string" ? p.field : undefined;
      if (s && field) return `Fetch ${s} ${field}`;
      return s ? `Fetch ${s} market data` : undefined;
    }

    /* ── Polygon options ── */
    case "get_option_chain":
      return s ? `Fetch ${s} options chain` : undefined;
    case "get_polygon_options_dataset":
      return s && dataset ? `Fetch ${s} ${friendlyDataset(dataset)}` : (s ? `Fetch ${s} options data` : undefined);
    case "get_polygon_options_aggregates":
      return s ? `Fetch ${s} options aggregates` : undefined;
    case "get_polygon_options_snapshot":
      return s ? `Fetch ${s} options snapshot` : undefined;

    /* ── UW options ── */
    case "uw_flow_alerts":
      return s ? `Fetch ${s} flow alerts` : undefined;
    case "uw_greek_flow":
      return s ? `Fetch ${s} Greek flow` : undefined;
    case "uw_gex":
      return s ? `Fetch ${s} GEX` : undefined;
    case "uw_flow_summary":
      return s ? `Fetch ${s} flow summary` : undefined;
    case "uw_volatility":
      return s ? `Fetch ${s} volatility` : undefined;
    case "uw_option_chain":
      return s ? `Fetch ${s} options chain` : undefined;
    case "uw_contract_data":
      return s ? `Fetch ${s} contract data` : undefined;
    case "uw_oi_change":
      return s ? `Fetch ${s} OI changes` : undefined;
    case "uw_net_flow_expiry":
      return s ? `Fetch ${s} net flow by expiry` : undefined;
    case "uw_sentiment":
      return s ? `Fetch ${s} sentiment` : undefined;
    case "uw_hottest_contracts":
      return s ? `Fetch ${s} hottest contracts` : undefined;
    case "uw_options_volume":
      return s ? `Fetch ${s} options volume` : undefined;
    case "uw_greeks":
      return s ? `Fetch ${s} Greeks` : undefined;
    case "uw_option_price_levels":
      return s ? `Fetch ${s} price levels` : undefined;

    /* ── UW market ── */
    case "uw_earnings":
      return s ? `Fetch ${s} earnings` : undefined;
    case "uw_correlations":
      return s ? `Fetch ${s} correlations` : undefined;
    case "uw_analyst_ratings":
      return s ? `Fetch ${s} analyst ratings` : undefined;
    case "uw_seasonality":
      return s ? `Fetch ${s} seasonality` : undefined;
    case "uw_short_data":
      return s ? `Fetch ${s} short interest` : undefined;
    case "uw_stock_screener":
      return dataset ? `Screen stocks — ${friendlyDataset(dataset)}` : undefined;

    /* ── UW institutional ── */
    case "uw_congress":
      return s ? `Fetch ${s} congressional trades` : undefined;
    case "uw_darkpool":
      return s ? `Fetch ${s} dark-pool data` : undefined;
    case "uw_insider":
      return s ? `Fetch ${s} insider trades` : undefined;
    case "uw_institution":
      return s ? `Fetch ${s} institutional data` : undefined;
    case "uw_ownership":
      return s ? `Fetch ${s} ownership data` : undefined;
    case "uw_etf":
      return s ? `Fetch ${s} ETF data` : undefined;

    /* ── Valuation ── */
    case "analyze_comparable_companies": {
      const peers = p.peer_tickers;
      if (s && Array.isArray(peers) && peers.length) return `Run ${s} comps vs ${peers.map(String).join(", ")}`;
      return s ? `Run ${s} comps analysis` : undefined;
    }
    case "gather_dcf_data_sources":
      return s ? `Gather ${s} DCF inputs` : undefined;
    case "analyze_three_stage_dcf":
      return s ? `Run ${s} 3-stage DCF` : undefined;
    case "analyze_two_stage_dcf":
      return s ? `Run ${s} 2-stage DCF` : undefined;
    case "analyze_stable_stage_dcf":
      return s ? `Run ${s} stable DCF` : undefined;
    case "analyze_reverse_dcf":
      return s ? `Run ${s} reverse DCF` : undefined;
    case "analyze_epv":
      return s ? `Run ${s} EPV valuation` : undefined;
    case "analyze_monte_carlo_dcf":
      return s ? `Run ${s} Monte Carlo DCF` : undefined;
    case "analyze_rim":
      return s ? `Run ${s} residual income model` : undefined;
    case "dcf_sensitivity_analysis":
      return s ? `Run ${s} DCF sensitivity` : undefined;

    /* ── Risk ── */
    case "calculate_var":
      return sOrList ? `VaR for ${sOrList}` : undefined;
    case "run_monte_carlo":
      return sOrList ? `Monte Carlo for ${sOrList}` : undefined;
    case "optimize_portfolio":
      return objective ? `Optimize portfolio — ${objective}` : (sOrList ? `Optimize ${sOrList}` : undefined);
    case "analyze_barra_factors":
      return sOrList ? `Analyze Barra factors for ${sOrList}` : undefined;
    case "create_hedge_portfolio":
      return sOrList ? `Create hedge portfolio for ${sOrList}` : undefined;
    case "analyze_fft_trends":
      return sOrList ? `Analyze FFT trends for ${sOrList}` : undefined;
    case "calculate_rolling_correlation": {
      const tp = tickerPair(p);
      return tp ? `Calculate rolling correlation for ${tp}` : undefined;
    }
    case "calculate_implied_correlation":
      return s ? `Calculate ${s} implied correlation` : undefined;
    case "stress_test_correlation":
      return sOrList ? `Stress-test correlation for ${sOrList}` : undefined;

    /* ── Quant / options pricing ── */
    case "price_equity_options":
      return s ? `Price ${s} options` : undefined;
    case "model_volatility_surface":
      return s ? `Model ${s} vol surface` : undefined;
    case "model_greeks_surface":
      return s ? `Model ${s} Greeks surface` : undefined;
    case "analyze_dealer_gamma_regime":
      return s ? `Analyze ${s} dealer gamma regime` : undefined;
    case "analyze_vanna_charm_flow":
      return s ? `Analyze ${s} vanna/charm flow` : undefined;
    case "analyze_iv_rv_vs_peers":
      return s ? `Analyze ${s} IV vs RV` : undefined;
    case "detect_signal_confluence":
      return s ? `Detect ${s} signal confluence` : undefined;
    case "analyze_earnings_patterns":
      return s ? `Analyze ${s} earnings patterns` : undefined;
    case "analyze_gex_levels":
      return s ? `Analyze ${s} GEX levels` : undefined;
    case "scan_nope_divergences":
      return s ? `Scan ${s} NOPE divergences` : undefined;
    case "detect_squeeze_setup":
      return s ? `Detect ${s} squeeze setup` : undefined;
    case "analyze_pca_eigen_portfolios":
      return sOrList ? `Analyze PCA eigen-portfolios for ${sOrList}` : undefined;
    case "analyze_correlation_matrix":
      return sOrList ? `Analyze correlation matrix for ${sOrList}` : undefined;
    case "calculate_delta_exposure":
      return s ? `Calculate ${s} delta exposure` : undefined;
    case "calculate_gamma_exposure":
      return s ? `Calculate ${s} gamma exposure` : undefined;
    case "calculate_vega_exposure":
      return s ? `Calculate ${s} vega exposure` : undefined;
    case "calculate_theta_decay":
      return s ? `Calculate ${s} theta decay` : undefined;
    case "calculate_cross_greeks":
      return s ? `Calculate ${s} cross Greeks` : undefined;
    case "construct_dynamic_hedge":
      return s ? `Construct ${s} dynamic hedge` : undefined;
    case "price_correlation_swap":
      return sOrList ? `Price correlation swap for ${sOrList}` : undefined;

    /* ── Structuring — ticker enrichment ── */
    case "price_interest_rate_swap":
    case "price_swaption":
    case "price_credit_default_swap":
    case "price_variance_swap":
    case "price_dispersion_trade":
    case "price_exotic_derivatives":
      return s ? `${TOOL_DISPLAY_NAMES[tool]} — ${s}` : undefined;

    /* ── Sentiment ── */
    case "analyze_news_sentiment":
      return s ? `Analyze ${s} news sentiment` : undefined;

    /* ── BH data tools ── */
    case "bh_retrieve":
      return dataset ? `Query ${friendlyBhKey(dataset)}` : undefined;
    case "bh_query":
      return dataset ? `Filter ${friendlyBhKey(dataset)}` : undefined;
    case "bh_aggregate":
      return dataset ? `Aggregate ${friendlyBhKey(dataset)}` : undefined;
    case "bh_group_by":
      return dataset ? `Group ${friendlyBhKey(dataset)}` : undefined;
    case "bh_schema":
      return dataset ? `Schema of ${friendlyBhKey(dataset)}` : undefined;
    case "bh_to_excel":
      return dataset ? `Export ${friendlyBhKey(dataset)} to Excel` : undefined;

    /* ── BH manifold ── */
    case "bh_manifold_state":
    case "bh_manifold_insights":
    case "bh_navigate":
    case "bh_manifold_slice":
    case "bh_geodesic":
    case "bh_walk_axis":
    case "bh_regress":
    case "bh_partial_corr":
    case "bh_pca_surface":
    case "bh_dependency_screen":
    case "bh_solver":
    case "bh_orbit":
    case "bh_multiscale_view":
    case "bh_frontier":
    case "bh_basin":
    case "bh_ridge_trace":
    case "bh_valley_trace":
    case "bh_coverage_audit":
    case "bh_wrap_audit":
      return dataset ? `${TOOL_DISPLAY_NAMES[tool]} — ${friendlyBhKey(dataset)}` : undefined;

    /* ── Memory ── */
    case "recall_memory":
      return query ? `Recall "${query}"` : undefined;

    /* ── Web search ── */
    case "web_search":
      return query ? `Search "${query}"` : undefined;

    /* ── Portfolio ── */
    case "get_portfolio":
    case "set_active_portfolio": {
      const pid = p.portfolio_id || p.id;
      return typeof pid === "string" ? `${TOOL_DISPLAY_NAMES[tool]} — ${pid}` : undefined;
    }

    /* ── Bloomberg ── */
    case "bloomberg_bdp":
    case "bloomberg_bdh":
    case "bloomberg_bds":
    case "bloomberg_bql":
    case "bloomberg_formula":
      return s ? `${TOOL_DISPLAY_NAMES[tool]} — ${s}` : undefined;

    default:
      return undefined;
  }
}

export function createActivityGroup(tool: string, parameters?: Record<string, unknown>): ActivityGroup {
  const label = tool.startsWith("excel_")
    ? "Updating spreadsheet..."
    : tool === "code_interpreter"
    ? "Running analysis..."
    : "Fetching data...";
  const now = Date.now();

  return {
    id: `activity-${++activityIdCounter}-${now}`,
    label,
    items: [{
      tool,
      label: generateToolLabel(tool, parameters),
      status: "running",
      startedAt: now,
    }],
    status: "running",
    collapsed: true,
    startedAt: now,
  };
}

export function formatToolLabel(tool: string): string {
  return tool
    .replace(/^(excel_|get_|fetch_)/, "")
    .replace(/_/g, " ");
}

/**
 * Generate a user-friendly label for a tool call.
 * Priority: dynamic (parameter-aware) > static dictionary > generic fallback.
 */
export function generateToolLabel(tool: string, parameters?: Record<string, unknown>): string {
  if (parameters) {
    const dyn = dynamicLabel(tool, parameters);
    if (dyn) return dyn;
  }

  return TOOL_DISPLAY_NAMES[tool] ?? formatToolLabel(tool);
}

export function updateActivityLabel(activity: ActivityGroup): string {
  const count = activity.items.length;
  const hasExcel = activity.items.some(i => i.tool.startsWith("excel_"));
  const hasFetch = activity.items.some(i => !i.tool.startsWith("excel_"));
  
  if (activity.status === "done") {
    if (hasExcel && hasFetch) {
      return `Fetched data and updated ${count} items`;
    } else if (hasExcel) {
      return `Updated ${count} Excel operation${count !== 1 ? "s" : ""}`;
    } else {
      return `Fetched ${count} data source${count !== 1 ? "s" : ""}`;
    }
  } else {
    if (hasExcel) {
      return "Updating spreadsheet...";
    } else {
      return "Fetching data...";
    }
  }
}
