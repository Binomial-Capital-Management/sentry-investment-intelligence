/**
 * Shared types for the Sentry Excel Add-in.
 * Matches the backend Pydantic models in api/models.py.
 */

// -- Cell Formatting --

export type BorderStyle = "thin" | "medium" | "thick" | "double" | "dotted" | "dashed" | "none";
export type HAlign = "left" | "center" | "right" | "fill" | "justify" | "distributed";
export type VAlign = "top" | "center" | "bottom" | "justify" | "distributed";

export interface BorderEdge {
  style: BorderStyle;
  color?: string;
}

export interface CellBorders {
  top?: BorderEdge;
  bottom?: BorderEdge;
  left?: BorderEdge;
  right?: BorderEdge;
  outline?: BorderEdge; // shortcut: apply to all four sides
}

export interface CellFormat {
  // Font
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strikethrough?: boolean;
  font_color?: string;
  font_size?: number;
  font_name?: string;

  // Fill
  fill?: string;

  // Number format
  number_format?: string;

  // Alignment
  horizontal_alignment?: HAlign;
  vertical_alignment?: VAlign;
  wrap_text?: boolean;
  indent?: number;
  text_rotation?: number; // -90 to 90

  // Borders
  borders?: CellBorders;
}

export interface CellOperation {
  range: string;
  values?: (string | number | null)[][] | null;
  formulas?: (string | null)[][] | null;
  format?: CellFormat | null;
  /** Merge cells in this range into one (writes value to top-left cell) */
  merge?: boolean;
}

// -- Conditional Formatting --

export interface ConditionalFormatRule {
  range: string;
  /** "colorScale" | "dataBar" | "iconSet" | "cellValue" | "top" */
  type: string;
  // For cellValue rules
  operator?: string; // "greaterThan" | "lessThan" | "between" | "equalTo" etc.
  value?: number | string;
  value2?: number | string; // for "between"
  format_fill?: string;
  format_font_color?: string;
  // For colorScale (2 or 3 stops)
  color_scale?: string[]; // e.g. ["#FF0000", "#FFFF00", "#00B050"]
}

// -- Named Range --

export interface NamedRangeSpec {
  name: string;
  range: string;
  sheet: string;
  comment?: string;
}

// -- Data Validation --

export interface DataValidationSpec {
  range: string;
  type: "list" | "decimal" | "whole" | "date" | "textLength" | "custom";
  /** For list: comma-separated values or range reference. For decimal/whole: formula */
  formula1?: string;
  formula2?: string;
  operator?: string; // "between", "greaterThan", "lessThan", etc.
  show_error?: boolean;
  error_title?: string;
  error_message?: string;
}

// -- Table --

export interface TableSpec {
  range: string;
  name: string;
  has_headers?: boolean;
  style?: string; // e.g. "TableStyleMedium2"
}

// -- Sort --

export interface SortSpec {
  range: string;
  /** Column index (0-based from range start) */
  key_column: number;
  ascending?: boolean;
}

// -- Agent Plan --

export interface DataRequest {
  reason: string;
  range: string;
  sheet: string;
}

export interface AgentStep {
  step_number: number;
  description: string;
  sheet: string;
  operations: CellOperation[];
  target_range: string;
  create_sheet?: boolean;
  rename_sheet?: string;
  validation?: string;

  // ─── Post-write actions ───

  /** Create a native Excel chart */
  chart?: {
    data_range: string;
    chart_type?: string;
    title?: string;
    target_sheet?: string;
    left?: number;
    top?: number;
    width?: number;
    height?: number;
  };
  /** Auto-fit column widths for these columns (e.g. ["A", "B:G"]) */
  autofit_columns?: string[];
  /** Set explicit column widths: { "A": 15, "B:D": 20 } (character units) */
  column_widths?: Record<string, number>;
  /** Set explicit row heights: { "1": 30, "2:5": 18 } (points) */
  row_heights?: Record<string, number>;
  /** Freeze panes at this cell (e.g. "B3" freezes rows 1-2 and column A) */
  freeze_panes?: string;
  /** Conditional formatting rules */
  conditional_formats?: ConditionalFormatRule[];
  /** Named ranges to create */
  named_ranges?: NamedRangeSpec[];
  /** Data validation rules */
  data_validations?: DataValidationSpec[];
  /** Create a structured table */
  table?: TableSpec;
  /** Sort a range */
  sort?: SortSpec;
  /** Protect the sheet (optional password) */
  protect?: { password?: string } | boolean;
}

export interface AgentPlan {
  summary: string;
  steps: AgentStep[];
  data_requests: DataRequest[];
  workbook_id: string;
  context_chunks_used?: number;
}

// -- Workbook Index --

export interface IndexLookupResult {
  indexed: boolean;
  workbook_id?: string;
  content_hash?: string;
  total_chunks?: number;
  workbook_name?: string;
  last_indexed_at?: string;
}

export interface DiffResult {
  stale: boolean;
  stored_hash?: string;
  reason?: string;
}

export interface WorkbookChunk {
  id: string;
  sheet_name: string;
  chunk_type: string;
  cell_range: string | null;
  content: string;
  metadata: Record<string, unknown>;
  similarity: number;
}

// -- Validation --

export interface ValidationResult {
  passed: boolean;
  reason: string;
  corrected_operations?: CellOperation[] | null;
}

// -- Agent Loop State --

/** "agent" = auto-execute. "plan" = show plan card, wait for approval. "ask" = just answer, no execution. */
export type InteractionMode = "agent" | "plan" | "ask";

/** "ask" = show permission dialog before edits. "accept" = auto-approve all edits. */
export type EditApprovalMode = "ask" | "accept";

/** Pending operation awaiting user approval */
export interface PendingOperation {
  id: string;
  description: string;
  toolName?: string;
  toolLabel?: string;
  execute: () => Promise<void>;
}

export type AgentStatus =
  | "idle"
  | "preparing"
  | "indexing"
  | "planning"
  | "thinking"
  | "awaiting_approval"
  | "executing"
  | "responding"
  | "writing_excel"
  | "validating"
  | "re_indexing"
  | "done"
  | "error";

export interface VbaCodePayload {
  title: string;
  code: string;
  purpose: string;
  instructions: string;
  sheets_involved: string[];
}

// -- Activity Sections (Claude-style collapsible tool groups) --

export interface ActivityItem {
  tool: string;
  label: string;
  status: "running" | "done" | "error";
  /** Correlation ID from backend tool_call/tool_done events */
  callId?: string;
  preview?: string;
  /** Accumulated Python code streamed live from code_interpreter tool calls */
  code?: string;
  /** Structured parameters passed to the tool */
  parameters?: Record<string, unknown>;
  /** Structured result returned from the tool */
  result?: Record<string, unknown>;
  /** User's permission decision if this tool call required approval */
  permission?: "allow_once" | "always_allow" | "deny" | "auto_approved";
  /** Timing data for dev performance analysis */
  startedAt?: number;
  completedAt?: number;
  durationMs?: number;
}

export interface ActivityGroup {
  id: string;
  label: string;
  items: ActivityItem[];
  status: "running" | "done";
  collapsed: boolean;
  /** Timing data for dev performance analysis */
  startedAt?: number;
  completedAt?: number;
  durationMs?: number;
}

// -- Thinking Sections (collapsible reasoning blocks) --

export interface ThinkingSection {
  id: string;
  title: string;
  content: string;
  collapsed: boolean;
}

let _msgSeq = 0;
export function nextMessageId(): string {
  return `msg-${Date.now()}-${_msgSeq++}`;
}

export interface AgentMessage {
  id: string;
  role: "user" | "agent" | "system" | "plan" | "vba_code" | "activity" | "thinking";
  content: string;
  timestamp: number;
  /** If true, message won't be filtered out when agent completes */
  persist?: boolean;
  plan?: AgentPlan;
  error?: string;
  /** For plan messages: current state */
  planStatus?: "pending" | "building" | "built" | "undone" | "rejected";
  /** For VBA code messages */
  vbaCode?: VbaCodePayload;
  /** For activity messages: grouped tool calls */
  activity?: ActivityGroup;
  /** For thinking messages: collapsible reasoning sections */
  thinkingSections?: ThinkingSection[];
  /** For thinking messages: final duration in seconds (set when thinking ends, stable across refreshes) */
  thinkingDurationSecs?: number;
  /** If set, this user message has a workbook checkpoint that can be restored */
  checkpointId?: string;
}

// -- Workbook Checkpoint (per-message snapshot for restore) --

/** Serialized conditional format for checkpoint storage */
export interface SerializedConditionalFormat {
  type: string;
  rangeAddress: string;
  priority: number;
  stopIfTrue: boolean;
  cellValueRule?: { operator: string; formula1: string; formula2?: string; fillColor?: string; fontColor?: string };
  colorScaleCriteria?: unknown;
  topBottomRule?: { type: string; rank: number; fillColor?: string };
  customFormula?: string;
  customFillColor?: string;
  customFontColor?: string;
}

/** Serialized table for checkpoint storage */
export interface SerializedTable {
  name: string;
  address: string;
  hasHeaders: boolean;
  style: string;
  showBandedRows: boolean;
  showBandedColumns: boolean;
  showFilterButton: boolean;
}

/** Serialized chart for checkpoint storage */
export interface SerializedChart {
  name: string;
  chartType: string;
  title: string;
  left: number;
  top: number;
  width: number;
  height: number;
  sourceDataAddress: string | null;
}

/** Serialized named range for checkpoint storage */
export interface SerializedNamedRange {
  name: string;
  formula: string;
  comment: string;
  visible: boolean;
}

/** Per-sheet snapshot */
export interface SheetSnapshot {
  values: unknown[][];
  formulas: unknown[][];
  numberFormats: string[][];
  rows: number;
  cols: number;
  usedRangeAddress: string;

  /** Sparse cell formatting — key: "row,col" (0-based within used range) */
  cellFormats: Record<string, Record<string, unknown>>;

  columnWidths: number[];
  rowHeights: number[];

  frozenRange: string | null;
  isProtected: boolean;
  visibility: string;
  mergedAreas: string[];

  conditionalFormats: SerializedConditionalFormat[];
  tables: SerializedTable[];
  charts: SerializedChart[];
}

/** Full workbook checkpoint tied to a user message */
export interface WorkbookCheckpoint {
  messageId: string;
  timestamp: number;
  sheetNames: string[];
  sheets: Record<string, SheetSnapshot>;
  namedRanges: SerializedNamedRange[];
}
