/**
 * Data Workspace Store Types
 * 
 * Extracted from dataWorkspaceStore.ts for better organization.
 * All type definitions for the workspace state management.
 */

import type { EndpointInfo, FormMode } from '@/features/canvas/types';
import type { SavedProcess } from '@/features/canvas/shared/AIChat/types';

// ============================================================================
// CORE TYPES
// ============================================================================

export interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
  exchange?: string;
}

export interface FieldConfig {
  field_name: string;
  endpoint: string;
  params?: Record<string, string>;
}

export interface DatasetConfig {
  id: string;
  symbol: string;
  endpoint: string;
  params: Record<string, any>;
  fields: string[];
  category?: string;
  addedAt: number;
  structureType?: string;
  compatibilityGroup?: string;
  timeKey?: string | null;
  cardinality?: 'single' | 'multi' | 'none';
  /** ID of the DatasetGroup this dataset belongs to */
  groupId?: string;
}

/**
 * DatasetGroup - A collection of datasets that should be merged/joined together.
 * 
 * When users add datasets in multi-object mode, they can choose to:
 * 1. Add to an existing group (extends the merged table)
 * 2. Create a new group (separate merged table)
 */
export interface DatasetGroup {
  id: string;
  name: string;  // e.g., "Price Data", "Analyst Estimates"
  createdAt: number;
}

// ============================================================================
// PIVOT TYPES
// ============================================================================

export interface PivotValueConfig {
  field: string;
  aggregation: 'none' | 'sum' | 'avg' | 'count' | 'min' | 'max' | 'median' | 'stddev' | 'first' | 'last';
  showTotal?: boolean;
  totalAggregation?: 'none' | 'sum' | 'avg' | 'count' | 'min' | 'max' | 'median' | 'stddev' | 'first' | 'last';
  showAs?: 'value' | 'pct_row' | 'pct_col' | 'pct_grand';
}

export interface PivotConfig {
  id: string;
  sourceTabId?: string;
  sourceSheetId?: string;
  rows: string[];
  columns: string[];
  values: PivotValueConfig[];
  filters?: Record<string, { operator: string; value: any }>;
  filterableFields?: string[];
  selectedDatasetIds?: string[];
  mergeMode?: 'union' | 'inner';
  mergeKey?: string;
  showGrandTotalColumn?: boolean;
  showSubtotals?: boolean;
}

// ============================================================================
// CHART TYPES
// ============================================================================

export interface ChartSeriesConfig {
  field: string;
  color?: string;
  label?: string;
}

export interface ChartFilter {
  id: string;
  field: string;
  filterType: 'date_range' | 'numeric_range';
  minValue?: string | number;
  maxValue?: string | number;
}

export interface OHLCFields {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume?: string;
}

export type ChartType = 
  | 'line' 
  | 'area' 
  | 'bar' 
  | 'pie' 
  | 'scatter' 
  | 'bubble' 
  | 'box' 
  | 'violin' 
  | 'radar' 
  | 'histogram' 
  | 'scatter3d' 
  | 'surface3d' 
  | 'candlestick' 
  | 'heatmap' 
  | 'scatterMatrix' 
  | 'dotPlot';

export interface ChartConfig {
  id: string;
  sourceTabId?: string;
  sourceSheetId?: string;
  chartType: ChartType;
  xAxis: string;
  ySeries: ChartSeriesConfig[];
  selectedDatasetIds?: string[];
  title?: string;
  showLegend?: boolean;
  showGrid?: boolean;
  typeOptions?: Record<string, any>;
  filters?: ChartFilter[];
  xAxisLabel?: string;
  yAxisLabel?: string;
  zAxisLabel?: string;
  xAxisRange?: [number | string | null, number | string | null];
  yAxisRange?: [number | null, number | null];
  ohlcFields?: OHLCFields;
}

// ============================================================================
// FORM STATE TYPES
// ============================================================================

export interface SingleObjectFormState {
  formMode: 'symbol' | 'market' | 'options' | 'forex' | 'crypto';
  formSelectedSymbol: { symbol: string; name: string; objectType: string } | null;
  formCustomIdentifier: string;
  formSelectedEndpoint: EndpointInfo | null;
  formSelectedFields: string[];
  formParams: Record<string, string>;
  formExpandedCategories: string[];
  formSourceFilter: string;
}

export interface MultiObjectFormState {
  selectedSymbols: Array<{ symbol: string; name: string; objectType: string }>;
  searchMode: 'symbol' | 'forex' | 'crypto';
  endpointSelectionMode: 'homogeneous' | 'heterogeneous';
  selectedEndpoint: EndpointInfo | null;
  selectedFields: string[];
  formParams: Record<string, string>;
  expandedCategories: string[];
  sourceFilter: string;
  endpointByType: Record<string, any>;
  fieldsByType: Record<string, string[]>;
  paramsByType: Record<string, Record<string, string>>;
  expandedCategoriesByType: Record<string, string[]>;
  sourceFilterByType: Record<string, string>;
  targetGranularity?: string;
}

/**
 * AddDatasetPanel state - persisted per tab so switching tabs preserves panel state
 */
export interface AddDatasetPanelState {
  // Mode: same endpoint for all types vs per-type endpoints
  endpointSelectionMode: 'homogeneous' | 'heterogeneous';
  // Source filter
  sourceFilter: string;
  // HOMOGENEOUS MODE state
  selectedEndpoint: EndpointInfo | null;
  selectedFields: string[];
  formParams: Record<string, string>;
  expandedCategories: string[];
  // HETEROGENEOUS MODE state
  selectedEndpointByType: Record<string, EndpointInfo | null>;
  fieldsByType: Record<string, string[]>;
  paramsByType: Record<string, Record<string, string>>;
  expandedCategoriesByType: Record<string, string[]>;
  // Scroll position - persisted to restore after navigating back from field selection
  scrollPosition: number;
  // Symbol selection state (for inline symbol adding in sidebar)
  sidebarFormMode: FormMode;
  sidebarSelectedSymbol: { symbol: string; name: string; objectType: string } | null;
  sidebarCustomIdentifier: string;
}

export interface TabFormState {
  single?: SingleObjectFormState;
  multi?: MultiObjectFormState;
  addDataPanel?: AddDatasetPanelState;
}

// ============================================================================
// TAB TYPES
// ============================================================================

export type TabMode = 'empty' | 'form' | 'data';
export type TabType = 'single' | 'multi' | 'compare' | 'pivot' | 'chart' | 'tool';
export type WorkspaceViewMode = 'explorer' | 'tools' | 'pivot' | 'chart';

/** What the middle content panel shows — independent of sidebar mode */
export type ContentViewType =
  | { type: 'data' }
  | { type: 'tool-result'; toolTabId: string; resultLocalId: string }
  | { type: 'pivot'; pivotLocalId: string }
  | { type: 'chart'; chartLocalId: string };

// ============================================================================
// TOOL TAB STATE
// ============================================================================

/** A single stored tool run result within a tab */
export interface TabToolResult {
  /** Stable client-side ID generated at run time (before DB save) */
  localId: string;
  result: SavedProcess;
  toolId: string;
  processName: string;
  /** DB process ID — null until auto-save completes */
  processId: string | null;
  /** Tickers used in the run (for dropdown display) */
  tickers: string[];
  /** Which chart tab is active for this result */
  activeChart: string;
  /** DatasetGroup this result belongs to (undefined = legacy; renders under first group) */
  groupId?: string;
}

/**
 * Per-tool slice stored on a tab, keyed by toolId. All fields are tool-specific:
 * switching tools within a tab gives each tool its own independent state.
 */
export interface PerToolState {
  toolStep: 1 | 2 | 3 | 4;
  toolParams: Record<string, any>;
  manualTickers: string;
  selectedPortfolioId: string;
  error: string | null;
  isRunning: boolean;
  isSaving: boolean;
  toolResults: TabToolResult[];
  activeResultId: string | null;
}

/**
 * Assembled view of the current tool's state, combining the tab-level toolId
 * pointer with the currently-selected PerToolState slice. Consumers read this
 * shape from useToolTab; it is not stored directly.
 */
export interface ToolTabState extends PerToolState {
  toolId: string;
}

/**
 * A single saved pivot result on a tab. Mirrors TabToolResult: every call to
 * "Create Pivot Table" appends one of these, and they appear as individual
 * entries under a DatasetGroup in the DatasetsDropdown.
 */
export interface TabPivotResult {
  /** Stable client-side ID generated at create time */
  localId: string;
  /** Display name, e.g. "Pivot 1" */
  name: string;
  /** The full pivot configuration for this entry */
  config: PivotConfig;
  /** DatasetGroup this pivot belongs to (undefined = legacy; renders under first group) */
  groupId?: string;
  createdAt: number;
}

/**
 * A single saved chart result on a tab. Mirrors TabPivotResult: every call to
 * "Create Chart" appends one of these, stored inline on the tab.
 */
export interface TabChartResult {
  localId: string;
  name: string;
  config: ChartConfig;
  groupId?: string;
  createdAt: number;
}

export interface WorkspaceSheet {
  id: string;
  name: string;
  compatibilityGroup: string;
  datasets: DatasetConfig[];
}

export interface WorkspaceTab {
  id: string;
  /** Backend process UUID — set after the tab is persisted to the server */
  backendId?: string;
  name: string;
  type: TabType;
  datasets: DatasetConfig[];
  symbols: SelectedObject[];
  activeView: 'table' | 'ontology';
  createdAt: number;
  mode?: TabMode;
  /** @deprecated legacy single-pivot field. New pivots go into pivotResults[]; this is kept for backward-compat reads. */
  pivotConfig?: PivotConfig;
  /** All saved pivots on this tab, accumulated per Create click. */
  pivotResults?: TabPivotResult[];
  /** @deprecated legacy single-chart field. New charts go into chartResults[]; kept for backward-compat reads. */
  chartConfig?: ChartConfig;
  /** All saved charts on this tab, accumulated per Create click. */
  chartResults?: TabChartResult[];
  /** Active group for Chart-mode "Add to" picker. Falls back to activeGroupId when unset. */
  activeChartGroupId?: string;
  formState?: TabFormState;
  /** @deprecated Legacy field - use datasets directly */
  sheets?: WorkspaceSheet[];
  /** Dataset groups for organizing datasets into separate merged tables */
  datasetGroups?: DatasetGroup[];
  /** Currently active group ID - determines which group's datasets are displayed/joined */
  activeGroupId?: string;
  /** Active group for Analysis-mode "Add to" picker. Falls back to activeGroupId when unset. */
  activeAnalysisGroupId?: string;
  /** Active group for Pivot-mode "Add to" picker. Falls back to activeGroupId when unset. */
  activePivotGroupId?: string;
  /** Currently-selected tool in this tab (drives which perToolState slice is active) */
  currentToolId?: string;
  /** Map of per-tool state, keyed by toolId */
  perToolState?: Record<string, PerToolState>;
  /** Active view mode for unified tabs (controls sidebar) */
  viewMode?: WorkspaceViewMode;
  /** What the middle content panel shows — independent of sidebar mode */
  contentView?: ContentViewType;
  /** Active AI chat thread ID for this tab */
  chatThreadId?: string;
  /** All chat thread IDs created on this tab */
  chatThreadIds?: string[];
  /** Dataset IDs selected for merging with the current dataset view */
  mergedDatasetIds?: string[];
  /** ID of the dataset that anchors the merge (the "primary" in the joined view) */
  mergeAnchorDatasetId?: string;
  /** ID of the dataset currently being viewed in the paginated data view */
  activeDatasetId?: string;
}

// ============================================================================
// STORE TYPES
// ============================================================================

export interface CompatibilityResult {
  compatible: boolean;
  group?: string;
  groups?: string[];
  reason?: string;
}

// ============================================================================
// API TYPES
// ============================================================================

export interface EndpointMetadata {
  endpoint: string;
  structureType: string;
  compatibilityGroup: string;
  timeKey: string | null;
  cardinality: 'single' | 'multi' | 'none';
}
