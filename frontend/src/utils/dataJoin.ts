/**
 * Data Join Utilities
 *
 * Joins datasets on their common primary key (symbol + time).
 * Intelligently detects which time fields exist in the data.
 *
 * Supports cross-asset joins (e.g., AAPL + BTC on date) via Smart Join.
 */

import { DatasetConfig } from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import { analyzeJoinability, DatasetInfo } from './timeAlignment';
import { mapBackendToTimeStructure } from './compatibilityMatrix';

// Possible time key fields in order of preference
const TIME_KEY_CANDIDATES = [
  ['calendarYear', 'period'],  // Fiscal period data (Q1 2024, etc.)
  ['_normalized_date'],        // Normalized date (we create this)
];

// Date fields that can be normalized to a common date
// Order matters - first found is used
const DATE_FIELD_ALIASES = [
  // Standard date fields
  'date',
  'acceptedDate', 
  'filingDate',
  'reportedDate',
  'priceDate',
  'transactionDate',
  'effectiveDate',
  'publishedDate',  // News endpoints
  // UW/Unusual Whales date fields
  'executed_at',    // darkpool-ticker-trades, stock-flow-recent
  'timestamp',      // stock-greek-flow, stock-nope, shorts-data
  'start_time',     // option-contract-intraday
  'report_date',    // earnings-historical, institution-ownership
  'curr_date',      // stock-oi-change
  'market_date',    // shorts-interest-float
  // Polygon date fields
  't',              // aggregates-range endpoints (Unix timestamp ms - needs conversion)
];

// Fields that should always be part of the primary key
const IDENTITY_FIELDS = ['symbol'];

interface DatasetResult {
  dataset: DatasetConfig;
  columns: string[];
  rows: Record<string, any>[];
  error?: string;
}

// Normalized result after date normalization
interface NormalizedDatasetResult extends DatasetResult {
  normalizedRows: Record<string, any>[];
  dateFieldUsed?: string;  // Which original date field was normalized
}

interface JoinedResult {
  columns: string[];
  rows: Record<string, any>[];
  joinKey: string[];
  joinKeyDisplay: string[];  // Human-readable key names
  datasetsJoined: string[];
  canJoin: boolean;
  reason?: string;
  isSnapshotJoin?: boolean;  // True when joining snapshot data (no time dimension)
}

/**
 * Options for joinDatasets function
 */
export interface JoinOptions {
  /** When true, join only on date (not symbol+date) - for cross-asset joins */
  crossSymbolJoin?: boolean;
}

/**
 * Normalize date fields in a dataset - creates _normalized_date from any date-like field
 */
function normalizeDates(result: DatasetResult): NormalizedDatasetResult {
  // Special handling for Polygon 't' field (Unix timestamp in milliseconds)
  if (result.columns.includes('t')) {
    const normalizedRows = result.rows.map(row => {
      const timestamp = row['t'];
      if (typeof timestamp === 'number') {
        // Convert Unix timestamp (ms) to YYYY-MM-DD
        const dateObj = new Date(timestamp);
        return {
          ...row,
          _normalized_date: dateObj.toISOString().split('T')[0],
        };
      }
      return { ...row, _normalized_date: '' };
    });
    return { ...result, normalizedRows, dateFieldUsed: 't' };
  }
  
  // Find which date field exists in this dataset
  const dateField = DATE_FIELD_ALIASES.find(f => result.columns.includes(f));
  
  if (!dateField) {
    return { ...result, normalizedRows: result.rows };
  }
  
  // Create normalized rows with _normalized_date
  const normalizedRows = result.rows.map(row => {
    const dateValue = row[dateField];
    // Normalize to YYYY-MM-DD format (strip time if present)
    let normalizedDate = '';
    if (dateValue) {
      // Handle numeric timestamps (common in UW data)
      if (typeof dateValue === 'number') {
        // Determine if seconds or milliseconds based on magnitude
        const ts = dateValue > 1e11 ? dateValue : dateValue * 1000;
        const dateObj = new Date(ts);
        normalizedDate = dateObj.toISOString().split('T')[0];
      } else {
        const dateStr = String(dateValue);
        // Handle "2024-01-15 10:30:00" or "2024-01-15T10:30:00"
        normalizedDate = dateStr.split(/[T\s]/)[0];
      }
    }
    return {
      ...row,
      _normalized_date: normalizedDate,
    };
  });
  
  return {
    ...result,
    normalizedRows,
    dateFieldUsed: dateField,
  };
}

/**
 * Detect which time key fields exist in ALL datasets
 */
function detectCommonTimeKey(results: NormalizedDatasetResult[]): { 
  keyFields: string[]; 
  displayFields: string[];
} {
  if (results.length === 0) return { keyFields: [], displayFields: [] };
  
  // Check for calendarYear + period first (fiscal data)
  const allHaveFiscal = results.every(r => 
    r.columns.includes('calendarYear') && r.columns.includes('period')
  );
  if (allHaveFiscal) {
    return { 
      keyFields: ['calendarYear', 'period'], 
      displayFields: ['calendarYear', 'period'] 
    };
  }
  
  // Check if all have a normalized date (any date field)
  const allHaveDate = results.every(r => 
    r.normalizedRows.length === 0 || r.normalizedRows[0]._normalized_date !== undefined
  );
  if (allHaveDate && results.some(r => r.dateFieldUsed)) {
    // Use the most common date field name for display
    const dateFields = results.map(r => r.dateFieldUsed).filter(Boolean);
    const displayField = dateFields[0] || 'date';
    return { 
      keyFields: ['_normalized_date'], 
      displayFields: [displayField as string]
    };
  }
  
  return { keyFields: [], displayFields: [] };
}

/**
 * Create a composite key from a row based on key fields
 */
function createJoinKey(row: Record<string, any>, keyFields: string[]): string {
  return keyFields.map(k => String(row[k] ?? '')).join('|');
}

/**
 * Get the time key fields for a compatibility group (for display purposes)
 */
export function getTimeKeyFields(compatibilityGroup: string): string[] {
  // This is now just for display - actual detection happens in detectCommonTimeKey
  const displayMap: Record<string, string[]> = {
    'fiscal_period': ['calendarYear', 'period'],
    'daily_trading': ['date'],
    'event_list': ['date'],
  };
  return displayMap[compatibilityGroup] || ['date'];
}

/**
 * Merge snapshot datasets (single row, no time dimension) into stacked rows.
 * Each dataset becomes one row, with a symbol column for identification.
 */
function mergeSnapshotDatasets(results: NormalizedDatasetResult[]): {
  columns: string[];
  rows: Record<string, any>[];
  joinKey: string[];
  joinKeyDisplay: string[];
  datasetsJoined: string[];
  canJoin: boolean;
  reason?: string;
  isSnapshotJoin?: boolean;
} {
  const datasetsJoined: string[] = [];
  const rows: Record<string, any>[] = [];
  
  // Collect all unique columns across all datasets
  const allColumnsSet = new Set<string>(['symbol']);
  results.forEach((result) => {
    result.columns.forEach(col => allColumnsSet.add(col));
  });
  
  // Build stacked rows - one row per dataset/symbol
  results.forEach((result) => {
    const symbol = result.dataset.symbol;
    datasetsJoined.push(result.dataset.id);
    
    // Get the single row (or empty object if no rows)
    const sourceRow = result.rows[0] || {};
    
    // Create row with symbol column
    const row: Record<string, any> = { symbol };
    result.columns.forEach(col => {
      if (col !== 'symbol') {
        row[col] = sourceRow[col];
      }
    });
    
    rows.push(row);
  });
  
  // Sort columns: symbol first, then alphabetically
  const columns = Array.from(allColumnsSet);
  columns.sort((a, b) => {
    if (a === 'symbol') return -1;
    if (b === 'symbol') return 1;
    return a.localeCompare(b);
  });
  
  return {
    columns,
    rows,
    joinKey: ['symbol'],
    joinKeyDisplay: ['symbol'],
    datasetsJoined,
    canJoin: true,
    isSnapshotJoin: true,
  };
}

/**
 * Join multiple dataset results on their common primary key (symbol + time).
 * 
 * Normalizes date fields (date, acceptedDate, filingDate, etc.) to enable
 * joining across datasets that use different date field names.
 * 
 * @param results - Array of dataset results to join
 * @param _compatibilityGroup - Unused, kept for API compatibility
 * @param options - Join options (e.g., crossSymbolJoin for multi-asset joins)
 * @returns Joined result with all columns merged
 */
export function joinDatasets(
  results: DatasetResult[],
  _compatibilityGroup: string,
  options?: JoinOptions
): JoinedResult {
  // Filter out empty/error results
  const validResults = results.filter(r => !r.error && r.rows.length > 0);
  
  if (validResults.length === 0) {
    return { 
      columns: [], 
      rows: [], 
      joinKey: [], 
      joinKeyDisplay: [],
      datasetsJoined: [],
      canJoin: false,
      reason: 'No data to join',
    };
  }
  
  // Single dataset - just return it
  if (validResults.length === 1) {
    const r = validResults[0];
    return {
      columns: r.columns,
      rows: r.rows,
      joinKey: [],
      joinKeyDisplay: [],
      datasetsJoined: [r.dataset.id],
      canJoin: true,
    };
  }
  
  // Normalize dates across all datasets
  const normalizedResults = validResults.map(normalizeDates);
  
  // ==========================================================================
  // SNAPSHOT DETECTION: Use backend structureType (primary) or infer (fallback)
  // ==========================================================================
  
  // Helper: Check if a dataset is a snapshot
  const isSnapshot = (r: DatasetResult): boolean => {
    // Primary: use the centralized mapping that handles all snapshot-like types
    // (snapshot, market_wide, options_chain, options_market, etc.)
    const timeStructure = mapBackendToTimeStructure(r.dataset.structureType);
    if (timeStructure === 'snapshot') return true;
    
    // Fallback: infer from data (for legacy datasets without structureType)
    if (!r.dataset.structureType || r.dataset.structureType === 'unknown') {
      const hasNoTimeFields = !r.columns.some(c => 
        DATE_FIELD_ALIASES.includes(c) || 
        c === 'calendarYear' || 
        c === 'period'
      );
      return r.rows.length <= 1 && hasNoTimeFields;
    }
    
    return false;
  };
  
  // Check structure types across all datasets
  const snapshotCount = validResults.filter(isSnapshot).length;
  const allSnapshots = snapshotCount === validResults.length;
  const hasSnapshots = snapshotCount > 0;
  const hasMixedTypes = hasSnapshots && !allSnapshots;
  
  // If ALL datasets are snapshots, merge them by stacking rows by symbol
  if (allSnapshots && validResults.length >= 2) {
    return mergeSnapshotDatasets(normalizedResults);
  }
  
  // If MIXED (some snapshots + some time-series), they're incompatible
  if (hasMixedTypes) {
    return {
      columns: [],
      rows: [],
      joinKey: [],
      joinKeyDisplay: [],
      datasetsJoined: [],
      canJoin: false,
      reason: 'Cannot join snapshot endpoints with time-series endpoints',
    };
  }
  
  // ==========================================================================
  // TIME-SERIES JOIN: Detect common time key and join on it
  // ==========================================================================
  
  // Detect common time key across all datasets
  const { keyFields: timeKeyFields, displayFields: timeDisplayFields } = detectCommonTimeKey(normalizedResults);
  
  if (timeKeyFields.length === 0) {
    // No common time key found - can't join meaningfully
    return {
      columns: [],
      rows: [],
      joinKey: [],
      joinKeyDisplay: [],
      datasetsJoined: [],
      canJoin: false,
      reason: 'Datasets have different time structures (no common date/period fields)',
    };
  }
  
  // Build primary key: symbol + time fields
  const uniqueSymbols = new Set(normalizedResults.map(r => r.dataset.symbol));
  const hasMultipleSymbols = uniqueSymbols.size > 1;
  
  // For cross-symbol joins (e.g., AAPL + BTCUSD), use ONLY time fields as key
  // This merges rows from different symbols on the same date into one row
  // For regular multi-symbol (same symbol, multiple endpoints), include symbol in key
  const includeSymbolInKey = hasMultipleSymbols && !options?.crossSymbolJoin;
  
  // Primary key fields (internal)
  const pkFields = includeSymbolInKey 
    ? ['symbol', ...timeKeyFields]
    : timeKeyFields;
  
  // Display key fields (human-readable)
  const pkDisplayFields = includeSymbolInKey
    ? ['symbol', ...timeDisplayFields]
    : timeDisplayFields;
  
  // Build a map of key -> merged row
  const mergedMap = new Map<string, Record<string, any>>();
  const allColumns = new Set<string>();
  const datasetsJoined: string[] = [];
  
  // Add display PK columns (not internal _normalized_date)
  pkDisplayFields.forEach(k => allColumns.add(k));
  if (includeSymbolInKey) {
    allColumns.add('symbol');
  }
  
  normalizedResults.forEach((result) => {
    datasetsJoined.push(result.dataset.id);
    
    // For multi-symbol joins, prefix columns with symbol to avoid conflicts
    const prefix = hasMultipleSymbols ? `${result.dataset.symbol}_` : '';
    
    // Use normalized rows for joining
    const rowsToJoin = result.normalizedRows || result.rows;
    
    rowsToJoin.forEach(row => {
      // Build the primary key using normalized fields
      const keyParts = pkFields.map(k => {
        if (k === 'symbol') return result.dataset.symbol;
        return String(row[k] ?? '');
      });
      const key = keyParts.join('|');
      
      // Skip rows with empty key (no date/period)
      if (keyParts.some(p => p === '' || p === 'undefined')) {
        return;
      }
      
      if (!mergedMap.has(key)) {
        // Initialize with display PK fields
        const newRow: Record<string, any> = {};
        if (includeSymbolInKey) {
          newRow['symbol'] = result.dataset.symbol;
        }
        // Add display time fields
        timeDisplayFields.forEach(displayField => {
          // Try to get the value from the original field or normalized
          if (displayField in row) {
            newRow[displayField] = row[displayField];
          } else if (row._normalized_date && DATE_FIELD_ALIASES.includes(displayField)) {
            newRow[displayField] = row._normalized_date;
          }
        });
        mergedMap.set(key, newRow);
      }
      
      const mergedRow = mergedMap.get(key)!;
      
      // Add all columns from this row (skip internal fields)
      result.columns.forEach(col => {
        // Skip PK display fields (already added)
        if (pkDisplayFields.includes(col)) return;
        // Skip internal normalized field
        if (col.startsWith('_')) return;
        
        // For multi-symbol, prefix non-PK columns
        const colName = hasMultipleSymbols ? `${prefix}${col}` : col;
        allColumns.add(colName);
        
        // Merge: if column doesn't exist or is null/undefined, add it
        if (!(colName in mergedRow) || mergedRow[colName] === null || mergedRow[colName] === undefined) {
          mergedRow[colName] = row[col];
        }
      });
    });
  });
  
  // Convert map to sorted array
  const rows = Array.from(mergedMap.values());
  
  // Sort by primary key (newest first)
  rows.sort((a, b) => {
    for (const k of pkDisplayFields) {
      const aVal = a[k];
      const bVal = b[k];
      if (aVal === bVal) continue;
      
      // Symbol: alphabetical
      if (k === 'symbol') {
        return String(aVal).localeCompare(String(bVal));
      }
      
      // Year: descending
      if (k === 'calendarYear') {
        return Number(bVal) - Number(aVal);
      }
      
      // Period: Q4 > Q3 > Q2 > Q1
      if (k === 'period') {
        const order: Record<string, number> = { 'FY': 0, 'Q4': 1, 'Q3': 2, 'Q2': 3, 'Q1': 4 };
        return (order[aVal] ?? 99) - (order[bVal] ?? 99);
      }
      
      // Date fields: descending (newest first)
      if (k.toLowerCase().includes('date')) {
        return String(bVal).localeCompare(String(aVal));
      }
      
      // Default: descending string
      return String(bVal).localeCompare(String(aVal));
    }
    return 0;
  });
  
  // Order columns: PK fields first, then alphabetically
  const columns = Array.from(allColumns).filter(c => !c.startsWith('_'));
  columns.sort((a, b) => {
    const aIsPK = pkDisplayFields.includes(a);
    const bIsPK = pkDisplayFields.includes(b);
    if (aIsPK && !bIsPK) return -1;
    if (!aIsPK && bIsPK) return 1;
    if (aIsPK && bIsPK) {
      return pkDisplayFields.indexOf(a) - pkDisplayFields.indexOf(b);
    }
    return a.localeCompare(b);
  });
  
  return {
    columns,
    rows,
    joinKey: pkFields,
    joinKeyDisplay: pkDisplayFields,
    datasetsJoined,
    canJoin: true,
  };
}

/**
 * Check if datasets can be joined (strict mode - same compatibility group only)
 *
 * Used by SingleObjectForm to enforce strict compatibility within a sheet.
 * For cross-asset joins, use canJoinDatasetsMultiObject instead.
 *
 * @param datasets - Array of dataset configs
 * @returns True if all datasets have the same compatibility group
 */
export function canJoinDatasets(datasets: DatasetConfig[]): boolean {
  if (datasets.length <= 1) return true;

  // Strict mode: require same compatibility group
  const groups = new Set(datasets.map((d) => d.compatibilityGroup).filter(Boolean));
  return groups.size <= 1;
}

/**
 * Check if datasets can be joined using Smart Join (cross-asset enabled)
 *
 * Used by MultiObjectForm to allow cross-asset joins like AAPL + BTC.
 * Uses granularity analysis instead of compatibility groups.
 *
 * @param datasets - Array of dataset configs
 * @returns True if datasets can be joined (directly or with alignment)
 */
export function canJoinDatasetsMultiObject(datasets: DatasetConfig[]): boolean {
  if (datasets.length <= 1) return true;

  // Convert to DatasetInfo for analysis
  const datasetInfos: DatasetInfo[] = datasets.map((d) => ({
    structureType: d.structureType,
  }));

  const analysis = analyzeJoinability(datasetInfos);

  // Can join if either:
  // 1. Direct join is possible (same granularity)
  // 2. Alignment is possible (different but compatible granularities)
  return analysis.canJoinDirectly || analysis.needsAlignment;
}

/**
 * Get a human-readable description of the join
 */
export function getJoinDescription(keyFields: string[], displayFields?: string[]): string {
  const fields = displayFields || keyFields;
  if (fields.length === 0) return 'Cannot join - different structures';
  
  const hasSymbol = fields.includes('symbol');
  const timeFields = fields.filter(k => k !== 'symbol' && !k.startsWith('_'));
  
  let timeDesc = '';
  if (timeFields.includes('calendarYear') && timeFields.includes('period')) {
    timeDesc = 'Year + Quarter';
  } else if (timeFields.some(f => f.toLowerCase().includes('date'))) {
    const dateField = timeFields.find(f => f.toLowerCase().includes('date'));
    timeDesc = dateField === 'date' ? 'Date' : dateField || 'Date';
  } else if (timeFields.length > 0) {
    timeDesc = timeFields.join(' + ');
  }
  
  return 'Joined';
}

