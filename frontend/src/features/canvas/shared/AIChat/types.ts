import type { ToolEvent as BaseToolEvent } from '@/types';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  toolEvents?: BaseToolEvent[];  // Tool events persisted with message metadata
  reasoningSegments?: string[];  // Reasoning text segments persisted with message metadata
}

export interface ChatThread {
  id: string;
  process_id: string;
  title: string | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

// Canvas process types (matching Canvas.tsx)
export interface StatsRow {
  category: string;
  metric: string;
  value: string;
  pct?: string;
}

export interface MetricCard {
  id: string;
  label: string;
  value: string;
  type?: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
}

export interface SavedProcess {
  id?: string;  // Optional for unsaved (fresh run) results
  tool_id: string;
  tickers: string[];
  weights?: number[];
  metrics: Record<string, any>;
  metric_cards?: MetricCard[];
  charts: Record<string, any>;
  stats_table?: StatsRow[];
  name?: string;
  hmm_enabled?: boolean;
  current_regime?: string;
  regime_params?: Record<string, any>;  // HMM regime parameters
  created_at?: string;
  updated_at?: string;
  graph_steps?: Array<{ coord: number[]; primitive: string; label: string; value?: any }>;
  graph_edges?: Array<{ source: number[]; target: number[] }>;
  params?: Record<string, any>;
}

// Data context for non-process contexts (e.g., DataWorkspace)
export interface DataContext {
  type: 'workspace' | 'workflow' | 'other';
  datasets?: Array<{
    id: string;           // Dataset ID for remove_dataset tool
    tabId?: string;       // Parent tab ID - helps AI specify correct source for charts/pivots
    symbol: string;
    endpoint: string;
    fields: string[];
    rowCount?: number;
    sampleData?: Record<string, any>[];
    groupId?: string;
  }>;
  charts?: Array<{
    id: string;           // Tab ID for remove_chart tool
    name: string;
    chartType?: string;
  }>;
  pivots?: Array<{
    id: string;
    name: string;
    tabId?: string;
    groupId?: string;
    rows?: string[];
    columns?: string[];
    values?: Array<{ field: string; aggregation: string }>;
  }>;
  /** Tool workflow tab summaries — allows AI to see tool results alongside data */
  tools?: Array<{
    tabId: string;
    tabName: string;
    toolId: string;
    tickers: string[];
    step: number;
    hasResults: boolean;
    processId: string | null;
    processName: string;
    metricCards?: Array<{ label: string; value: string; type?: string }>;
    params?: Record<string, any>;
  }>;
  symbols?: string[];
  /** Which tab the user is currently viewing */
  activeTabId?: string;
  activeTabType?: string;
  description?: string;
  datasetGroups?: Array<{ id: string; name: string; datasetCount: number }>;
  activeGroupId?: string;
  contentView?: {
    type: 'data' | 'tool-result' | 'pivot' | 'chart';
    pivotLocalId?: string;
    chartLocalId?: string;
    toolTabId?: string;
    resultLocalId?: string;
  };
  sidebarViewMode?: 'explorer' | 'tools' | 'pivot' | 'chart';
}

export interface CanvasAIChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  process: SavedProcess | null;
  dataContext?: DataContext | null;
  onResize?: (width: number) => void;
  onResultUpdate?: (result: any) => void;
  tabThreadId?: string | null;
  onTabThreadIdChange?: (threadId: string) => void;
  activeTabId?: string;
  onEnsureTab?: () => string;
}

export interface PendingUpdate {
  processId: string;
  toolId: string;
  tickers: string[];
  weights?: number[];
  params?: Record<string, any>;
  fullResult: Record<string, any>;
}

export interface AttachedFile {
  id: string;
  original_name: string;
  source?: 'local' | 'google_drive' | 'onedrive';
}

// =============================================================================
// Agent Action Types (for agentic architecture)
// =============================================================================

export interface AddDatasetAction {
  type: 'add_dataset';
  dataset_id: string;
  symbol: string;
  endpoint: string;
  fields?: string[];
  row_count: number;
}

export interface RemoveDatasetAction {
  type: 'remove_dataset';
  dataset_id: string;
}

export interface CreateChartAction {
  type: 'create_chart';
  config: {
    chartType: string;
    xAxis: string;
    ySeries: Array<{ field: string; label?: string; color?: string }>;
    title?: string;
    showLegend?: boolean;
    showGrid?: boolean;
    selectedDatasetIds?: string[];
  };
}

export interface CreatePivotAction {
  type: 'create_pivot';
  config: {
    rows: string[];
    columns: string[];
    values: Array<{ field: string; aggregation: string }>;
    selectedDatasetIds?: string[];
  };
}

export interface RemoveChartAction {
  type: 'remove_chart';
  tab_id: string;
}

export interface RemovePivotAction {
  type: 'remove_pivot';
  tab_id: string;
}

export interface StartToolAnalysisAction {
  type: 'start_tool_analysis';
  analysis_id: string;
  tool_id: string;
  tool_name: string;
  tickers: string[];
}

export interface ModifyProcessTickersAction {
  type: 'modify_process_tickers';
  process_id: string;
  tickers: string[];
  weights?: number[];
}

// Union type of all agent actions
export type AgentAction =
  | AddDatasetAction
  | RemoveDatasetAction
  | CreateChartAction
  | CreatePivotAction
  | RemoveChartAction
  | RemovePivotAction
  | StartToolAnalysisAction
  | ModifyProcessTickersAction;

// =============================================================================
// Action Result Types (for feedback loop)
// =============================================================================

export interface ActionResult {
  success: boolean;
  error?: string;
  data?: any;
  cancelled?: boolean;  // User cancelled confirmation dialog
}

export interface ActionResultReport {
  thread_id: string;
  action_id: string;
  action_type: string;
  symbol?: string;
  success: boolean;
  error?: string;
  data?: any;
}

// =============================================================================
// Action Validation Types
// =============================================================================

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

// Re-export ToolEvent from types
export type { BaseToolEvent as ToolEvent };
