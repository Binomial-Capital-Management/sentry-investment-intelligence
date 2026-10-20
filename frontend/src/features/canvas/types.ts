/**
 * Shared types for Canvas feature components
 */

// Portfolio and Tool types
export interface Portfolio {
  id: string;
  name: string;
  tickers: string[];
  weights: number[];
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  category: string;
  params_schema: Record<string, any>;
}

export interface EditProcess {
  id?: string;
  tool_id: string;
  tickers: string[];
  weights?: number[];
  params?: Record<string, any>;
}

// Data Explorer types
export interface ObjectTypeResult {
  object_type: string;
  symbol: string;
  name: string | null;
  exchange: string | null;
  currency?: string | null;
  is_actively_trading?: boolean;
}

// Mode and Step types
export type Mode = 'select' | 'tool' | 'data';
export type Step = 1 | 2 | 3 | 4;
export type WorkspaceStep = 'objects' | 'configure' | 'table';

// Form types
export type FormMode = 'symbol' | 'market' | 'options' | 'forex' | 'crypto';

// Granularity types for time alignment
export type Granularity = 'snapshot' | 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'intraday' | 'event' | 'unknown';

export interface EndpointInfo {
  endpoint: string;
  category: string;
  required_params: string[];
  fields: string[];
  source: string;
  // Equivalence metadata (for cross-asset joins)
  structureType?: string;
  granularity?: Granularity;
  equivalenceGroup?: string;  // canonical name for grouping across asset types
}

// Endpoint equivalence group (for cross-asset joins)
export interface EquivalenceGroup {
  canonical: string;  // Representative endpoint name
  endpoints: Record<string, string>;  // object_type -> endpoint_name
  structure_type: string;
  category: string;
  granularity: Granularity;
  avg_field_overlap: number;
}

// Response from /endpoint-equivalence API
export interface EndpointEquivalenceResponse {
  equivalence_groups: EquivalenceGroup[];
  granularities_detected: Granularity[];
  has_mixed_granularity: boolean;
}

// Time-key group types (for heterogeneous endpoint selection)
export type TimeGroup = 'date' | 'fiscal_period' | 'snapshot';

export interface EndpointTimeInfo {
  endpoint: string;
  granularity: Granularity;
  category: string;
  fields: string[];
  structure_type: string;
  time_key: string | null;
  time_group: TimeGroup;
  required_params: string[];
  source: string;
}

export interface TimeGroupEndpoints {
  date: EndpointTimeInfo[];
  fiscal_period: EndpointTimeInfo[];
  snapshot: EndpointTimeInfo[];
}

export interface EndpointsByTimeGroupResponse {
  endpoints_by_type: Record<string, TimeGroupEndpoints>;
}

export interface JoinStrategy {
  strategy: 'same_group' | 'cross_group' | 'snapshot_stack' | 'incompatible';
  time_groups: TimeGroup[];
  granularities: Granularity[];
  common_time_key: string | null;
  needs_aggregation: boolean;
  aggregation_target: Granularity | null;
  error?: string;
}

// Toast type
export interface Toast {
  message: string;
  type: 'success' | 'error' | 'info';
}

// UW Enum state for sector/flow_group dropdowns
export interface UwEnumState {
  values: Record<string, string[]>;
  loading: Set<string>;
}

// Tab/Sheet types - WorkspaceTab defined in data-workspace/stores/dataWorkspaceStore.ts (more complete)

// Pivot Table types
export interface PivotField {
  name: string;
  type: 'measure' | 'dimension';
  source?: string;
}

export interface PivotSource {
  tabId: string;
  sheetId: string;
  sheet: any;
}

export interface PivotConfigState {
  rows: string[];
  columns: string[];
  values: { field: string; aggregation: string }[];
  filters: Record<string, any>;
  filterableFields: string[];
  mergeMode?: 'union' | 'inner';
  mergeKey?: string;
}


// Dataset type - DatasetConfig defined in data-workspace/stores/dataWorkspaceStore.ts (more complete)

// Dataset template type (symbol-agnostic, for multi-object mode)
export interface DatasetTemplate {
  id: string;
  endpoint: string;
  fields: string[];
  params: Record<string, any>;
  category?: string;
  addedAt: number;
  // Compatibility metadata (populated from backend)
  structureType?: string;
  compatibilityGroup?: string;
  timeKey?: string | null;
  cardinality?: 'single' | 'multi' | 'none';
}

// Selected object in workspace
export interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
  exchange?: string;
}

// Object type filter
export interface ObjectTypeFilter {
  id: string;
  name: string;
  desc: string;
}

// Constants
export const STEPS = [
  { num: 1, label: 'Tool' },
  { num: 2, label: 'Data' },
  { num: 3, label: 'Config' },
  { num: 4, label: 'Results' },
];

export const OBJECT_TYPES: ObjectTypeFilter[] = [
  { id: 'equity', name: 'Equities', desc: 'Stocks & shares' },
  { id: 'etf', name: 'ETFs', desc: 'Exchange-traded funds' },
  { id: 'crypto', name: 'Crypto', desc: 'Digital assets' },
  { id: 'forex', name: 'Forex', desc: 'Currency pairs' },
  { id: 'commodity', name: 'Commodities', desc: 'Gold, oil, etc.' },
  { id: 'macro_series', name: 'Macro', desc: 'Economic data' },
];

// Helper functions
export function inferInputType(schema: Record<string, any>): 'portfolio' | 'single_ticker' | 'tickers' | 'none' {
  const hasPortfolio = 'portfolio_id' in schema;
  const hasTickers = 'tickers' in schema && schema.tickers?.type === 'array';
  const hasUnderlying = 'underlying' in schema && schema.underlying?.type === 'string';
  const hasTicker = 'ticker' in schema && schema.ticker?.type === 'string';
  if (!hasPortfolio && !hasTickers && !hasUnderlying && !hasTicker) return 'none';
  if ((hasUnderlying || hasTicker) && !hasPortfolio && !hasTickers) return 'single_ticker';
  if (hasTickers && !hasPortfolio) return 'tickers';
  return 'portfolio';
}

/**
 * Extract the minimum ticker count for a tool's params schema. Reads an
 * explicit `min_items` field on the tickers param when present; otherwise
 * falls back to parsing `(min N)` from the description. Returns null when
 * the schema has no ticker array or no minimum is encoded.
 */
export function getMinTickers(schema: Record<string, any>): number | null {
  const tickers = schema?.tickers;
  if (!tickers || tickers.type !== 'array') return null;
  const explicit = typeof tickers.min_items === 'number'
    ? tickers.min_items
    : typeof tickers.minItems === 'number' ? tickers.minItems : null;
  if (explicit != null && explicit > 0) return explicit;
  const desc = typeof tickers.description === 'string' ? tickers.description : '';
  const match = desc.match(/\bmin\s*(\d+)\b/i);
  return match ? parseInt(match[1], 10) : null;
}

// Logo helper
const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;
export const getCompanyLogoUrl = (symbol: string) => {
  if (!logoDevToken) {
    return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
  }
  return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
};
