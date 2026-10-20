// Ontology Type System - Palantir-inspired object model for financial data

// ===== CORE OBJECT TYPES =====

export type ObjectType =
  | 'company'
  | 'portfolio'
  | 'sec_filing'
  | 'position'
  | 'option_contract'
  | 'institutional_holder'
  | 'analysis_report';

export type LinkType =
  | 'peer_of'           // Company → Company (comparable)
  | 'supplier_of'       // Company → Company (supply chain)
  | 'held_by'          // Company → InstitutionalHolder
  | 'contains'         // Portfolio → Position
  | 'references'       // Position → Company
  | 'has_filing'       // Company → SECFiling
  | 'has_options'      // Company → OptionContract
  | 'analyzes'         // AnalysisReport → Company/Portfolio
  | 'competes_with';   // Company → Company

// ===== COMPANY OBJECT =====

export interface CompanyObject {
  id: string;
  type: 'company';

  // Core identifiers
  ticker: string;
  name: string;
  exchange: string;

  // Classification
  sector: string;
  industry: string;

  // Market data
  price: number;
  marketCap: number;
  volume: number;
  change: number;        // % change
  changeAmount: number;  // $ change

  // Fundamentals (from FMP discover_fields)
  fundamentals: {
    pe_ratio?: number;
    eps?: number;
    revenue?: number;
    ebitda?: number;
    profit_margin?: number;
    roe?: number;
    debt_to_equity?: number;
  };

  // Valuation (from FMP discover_valuation_fields)
  valuation: {
    ev_to_ebitda?: number;
    price_to_sales?: number;
    price_to_book?: number;
    peg_ratio?: number;
    dividend_yield?: number;
  };

  // Technical (from FMP discover_technical_fields)
  technical: {
    rsi?: number;
    macd?: number;
    sma_50?: number;
    sma_200?: number;
    beta?: number;
  };

  // Metadata
  description?: string;
  website?: string;
  logo_url?: string;
  created_at: string;
  updated_at: string;
}

// ===== PORTFOLIO OBJECT =====

export interface PortfolioObject {
  id: string;
  type: 'portfolio';

  name: string;
  description?: string;

  // Metrics
  total_value: number;
  cash: number;
  invested: number;

  // Risk metrics (from Risk Specialist Agent)
  risk_metrics?: {
    var_95?: number;      // Value at Risk
    cvar_95?: number;     // Conditional VaR
    sharpe_ratio?: number;
    volatility?: number;
    beta?: number;
  };

  // Performance
  returns?: {
    day?: number;
    week?: number;
    month?: number;
    ytd?: number;
    all_time?: number;
  };

  // Metadata
  created_at: string;
  updated_at: string;
  position_count: number;
}

// ===== POSITION OBJECT =====

export interface PositionObject {
  id: string;
  type: 'position';

  ticker: string;
  shares: number;
  cost_basis: number;
  current_value: number;

  // Performance
  unrealized_gain: number;
  unrealized_gain_percent: number;

  // Portfolio context
  weight: number;  // % of portfolio

  created_at: string;
  updated_at: string;
}

// ===== SEC FILING OBJECT =====

export interface SECFilingObject {
  id: string;
  type: 'sec_filing';

  ticker: string;
  form_type: '10-K' | '10-Q' | '8-K' | 'DEF 14A' | 'S-1';
  filing_date: string;
  accepted_date: string;

  // Document
  accession_number: string;
  document_url: string;

  // Content summary (from Document Analyst Agent)
  summary?: string;
  key_points?: string[];

  created_at: string;
}

// ===== OPTION CONTRACT OBJECT =====

export interface OptionContractObject {
  id: string;
  type: 'option_contract';

  ticker: string;              // O:AAPL250117C00150000
  underlying: string;          // AAPL
  strike: number;
  expiration: string;
  contract_type: 'call' | 'put';

  // Pricing
  bid: number;
  ask: number;
  last: number;
  volume: number;
  open_interest: number;

  // Greeks (from Polygon discover_polygon_options_technical_fields)
  greeks?: {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    rho?: number;
  };

  // Risk metrics
  implied_volatility?: number;

  created_at: string;
  updated_at: string;
}

// ===== INSTITUTIONAL HOLDER OBJECT =====

export interface InstitutionalHolderObject {
  id: string;
  type: 'institutional_holder';

  name: string;
  ticker: string;  // Company being held

  shares: number;
  value: number;
  percent_held: number;

  change?: {
    shares: number;
    percent: number;
  };

  filing_date: string;
  created_at: string;
}

// ===== ANALYSIS REPORT OBJECT =====

export interface AnalysisReportObject {
  id: string;
  type: 'analysis_report';

  title: string;
  report_type: 'risk_analysis' | 'dcf_valuation' | 'comparable_companies' | 'technical_analysis';

  // Target
  target_type: 'company' | 'portfolio';
  target_id: string;
  target_name: string;

  // Content
  summary: string;
  findings: any;  // Structured findings from agent

  // Artifacts
  charts?: string[];
  files?: Array<{
    name: string;
    url: string;
    type: 'pdf' | 'csv' | 'json';
  }>;

  // Agent info
  agent: string;

  created_at: string;
}

// ===== UNION TYPE =====

export type OntologyObject =
  | CompanyObject
  | PortfolioObject
  | PositionObject
  | SECFilingObject
  | OptionContractObject
  | InstitutionalHolderObject
  | AnalysisReportObject;

// ===== RELATIONSHIP/LINK =====

export interface OntologyLink {
  id: string;
  type: LinkType;

  from_id: string;
  from_type: ObjectType;

  to_id: string;
  to_type: ObjectType;

  // Link metadata
  properties?: Record<string, any>;
  weight?: number;  // Relationship strength (0-1)

  created_at: string;
}

// ===== ACTIONS (Workflows as operations on objects) =====

export interface OntologyAction {
  id: string;
  name: string;
  description: string;

  // Which object types can this action be performed on
  applicable_to: ObjectType[];

  // Agent to execute
  agent: string;

  // Input schema
  parameters: Array<{
    name: string;
    type: 'string' | 'number' | 'boolean' | 'date';
    required: boolean;
    default?: any;
  }>;

  // Output
  creates_object?: ObjectType;  // e.g., 'analysis_report'
  creates_link?: LinkType;       // e.g., 'analyzes'
}

// ===== UI STATE =====

export interface OntologyViewState {
  // Current view
  view_mode: 'graph' | 'list' | 'table';

  // Selected object
  selected_object_id: string | null;
  selected_object_type: ObjectType | null;

  // Filters
  object_type_filters: ObjectType[];
  search_query: string;

  // Graph state
  graph_layout: 'force' | 'hierarchical' | 'circular';
  show_links: LinkType[];

  // Panel state
  detail_panel_open: boolean;
  action_panel_open: boolean;
}
