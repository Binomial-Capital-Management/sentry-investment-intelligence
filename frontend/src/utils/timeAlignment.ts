/**
 * Time Alignment Utilities
 *
 * Functions for aligning data across different time granularities.
 * Used by the Smart Join system to aggregate fine-grained data (daily)
 * into coarser periods (weekly, monthly, quarterly).
 */

import { AggMethod, applyAggregation } from './aggregation';

// ============================================================================
// TYPES
// ============================================================================

export interface FieldAggregations {
  [fieldName: string]: AggMethod;
}

export interface AggregatedRow {
  [key: string]: unknown;
}

export type Granularity =
  | 'snapshot'
  | 'annual'
  | 'quarterly'
  | 'monthly'
  | 'weekly'
  | 'daily'
  | 'intraday';

export type CalendarMode = 'trading' | 'calendar';

/**
 * Result of analyzing whether datasets can be joined.
 */
export interface JoinAnalysis {
  /** True if datasets can be joined directly without alignment */
  canJoinDirectly: boolean;
  /** True if datasets need time alignment (aggregation) before joining */
  needsAlignment: boolean;
  /** The granularity of each input dataset */
  granularities: Granularity[];
  /** The recommended target granularity for alignment (coarsest) */
  suggestedTargetGranularity: Granularity | null;
  /** Human-readable explanation */
  reason?: string;
}

/**
 * Minimal dataset info needed for join analysis.
 */
export interface DatasetInfo {
  structureType?: string;
  rows?: Record<string, unknown>[];
}

// ============================================================================
// DATE UTILITIES
// ============================================================================

/**
 * Get the quarter (Q1-Q4) for a given date.
 *
 * Uses calendar year quarters:
 * - Q1: January - March
 * - Q2: April - June
 * - Q3: July - September
 * - Q4: October - December
 *
 * @param date - The date to get the quarter for
 * @returns Quarter string (Q1, Q2, Q3, or Q4)
 *
 * @example
 * getQuarter(new Date('2024-02-15')) // => 'Q1'
 * getQuarter(new Date('2024-07-01')) // => 'Q3'
 */
export function getQuarter(date: Date): string {
  const month = date.getMonth(); // 0-11
  if (month < 3) return 'Q1';
  if (month < 6) return 'Q2';
  if (month < 9) return 'Q3';
  return 'Q4';
}

/**
 * Get the calendar year for a date.
 *
 * @param date - The date to get the year for
 * @returns The 4-digit year
 *
 * @example
 * getCalendarYear(new Date('2024-06-15')) // => 2024
 */
export function getCalendarYear(date: Date): number {
  return date.getFullYear();
}

/**
 * Check if a date falls on a weekend (Saturday or Sunday).
 *
 * @param date - The date to check
 * @returns True if Saturday or Sunday
 *
 * @example
 * isWeekend(new Date('2024-01-06')) // => true (Saturday)
 * isWeekend(new Date('2024-01-08')) // => false (Monday)
 */
export function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === 0 || day === 6; // Sunday or Saturday
}

/**
 * Get the start date of a quarter.
 *
 * @param year - The calendar year
 * @param quarter - The quarter (Q1, Q2, Q3, or Q4)
 * @returns Date object for the first day of the quarter
 *
 * @example
 * getQuarterStartDate(2024, 'Q1') // => Date for Jan 1, 2024
 * getQuarterStartDate(2024, 'Q3') // => Date for Jul 1, 2024
 */
export function getQuarterStartDate(year: number, quarter: string): Date {
  const quarterStarts: Record<string, number> = {
    Q1: 0, // January
    Q2: 3, // April
    Q3: 6, // July
    Q4: 9, // October
  };
  return new Date(year, quarterStarts[quarter], 1);
}

/**
 * Get the end date of a quarter.
 *
 * @param year - The calendar year
 * @param quarter - The quarter (Q1, Q2, Q3, or Q4)
 * @returns Date object for the last day of the quarter
 *
 * @example
 * getQuarterEndDate(2024, 'Q1') // => Date for Mar 31, 2024
 * getQuarterEndDate(2024, 'Q2') // => Date for Jun 30, 2024
 */
export function getQuarterEndDate(year: number, quarter: string): Date {
  const quarterEnds: Record<string, [number, number]> = {
    Q1: [2, 31], // March 31
    Q2: [5, 30], // June 30
    Q3: [8, 30], // September 30
    Q4: [11, 31], // December 31
  };
  const [month, day] = quarterEnds[quarter];
  return new Date(year, month, day);
}

// ============================================================================
// GRANULARITY DETECTION
// ============================================================================

/**
 * Map from backend structureType to Granularity.
 *
 * Based on core/canvas/field_mappings.py STRUCTURE_TO_COMPATIBILITY_GROUP
 */
const STRUCTURE_TYPE_TO_GRANULARITY: Record<string, Granularity> = {
  // Snapshot - no time dimension
  snapshot: 'snapshot',

  // Fiscal period - quarterly/annual
  fiscal_period_series: 'quarterly',

  // Daily trading data
  daily_ohlcv: 'daily',
  crypto_daily: 'daily',
  forex_daily: 'daily',
  commodity_daily: 'daily',

  // Intraday
  intraday: 'intraday',
  crypto_intraday: 'intraday',
  forex_intraday: 'intraday',
  commodity_intraday: 'intraday',

  // Events (irregular, treated as daily for alignment purposes)
  event_list: 'daily',
  year_quarter_indexed: 'quarterly',

  // Market-wide (no symbol, snapshot-like)
  market_wide: 'snapshot',

  // SEC filings (event-like, daily granularity)
  sec_filing_search: 'daily',

  // Options
  options_chain: 'snapshot',
  options_flow: 'daily',
  options_contract: 'daily',
  options_market: 'snapshot',
};

/**
 * Detect the granularity of a dataset.
 *
 * Uses the structureType from backend metadata if available,
 * otherwise attempts to infer from the data columns/values.
 *
 * @param structureType - The structure type from endpoint metadata
 * @param rows - Optional data rows to infer from if structureType unknown
 * @returns The detected granularity
 *
 * @example
 * detectGranularity('fiscal_period_series') // => 'quarterly'
 * detectGranularity('daily_ohlcv')          // => 'daily'
 * detectGranularity('snapshot')              // => 'snapshot'
 */
export function detectGranularity(
  structureType?: string,
  rows?: Record<string, unknown>[]
): Granularity {
  // 1. Try to map from known structure types
  if (structureType && structureType in STRUCTURE_TYPE_TO_GRANULARITY) {
    return STRUCTURE_TYPE_TO_GRANULARITY[structureType];
  }

  // 2. Infer from data if we have rows
  if (rows && rows.length > 0) {
    const firstRow = rows[0];
    const columns = Object.keys(firstRow);

    // Check for fiscal period columns
    if (columns.includes('calendarYear') && columns.includes('period')) {
      return 'quarterly';
    }

    // Check for date column
    if (columns.includes('date')) {
      // Could be daily - check interval if we have multiple rows
      if (rows.length >= 2) {
        const date1 = new Date(rows[0].date as string);
        const date2 = new Date(rows[1].date as string);
        const diffMs = Math.abs(date2.getTime() - date1.getTime());
        const diffDays = diffMs / (1000 * 60 * 60 * 24);

        // If interval is less than 1 day, it's intraday
        if (diffDays < 1) {
          return 'intraday';
        }
        // If interval is around 7 days, it's weekly
        if (diffDays >= 6 && diffDays <= 8) {
          return 'weekly';
        }
        // If interval is around 30 days, it's monthly
        if (diffDays >= 28 && diffDays <= 32) {
          return 'monthly';
        }
      }
      return 'daily';
    }

    // Check for datetime column (intraday)
    if (columns.includes('datetime') || columns.includes('timestamp')) {
      return 'intraday';
    }

    // No time columns - must be snapshot
    return 'snapshot';
  }

  // 3. Default to daily if we can't determine
  return 'daily';
}

// ============================================================================
// JOIN ANALYSIS
// ============================================================================

/**
 * Granularity order from finest to coarsest.
 * Used to determine the target granularity for alignment.
 */
const GRANULARITY_ORDER: Granularity[] = [
  'intraday',
  'daily',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
  'snapshot',
];

/**
 * Get the coarsest granularity from a list.
 * Snapshot is treated specially - it's joinable with anything but doesn't
 * determine the target granularity.
 */
function getCoarsestGranularity(granularities: Granularity[]): Granularity | null {
  // Filter out snapshots for determining coarsest
  const nonSnapshot = granularities.filter((g) => g !== 'snapshot');

  if (nonSnapshot.length === 0) {
    // All snapshots - return snapshot
    return granularities.length > 0 ? 'snapshot' : null;
  }

  // Find the coarsest (highest index in order)
  let coarsestIndex = -1;
  for (const g of nonSnapshot) {
    const idx = GRANULARITY_ORDER.indexOf(g);
    if (idx > coarsestIndex) {
      coarsestIndex = idx;
    }
  }

  return coarsestIndex >= 0 ? GRANULARITY_ORDER[coarsestIndex] : null;
}

/**
 * Analyze whether a set of datasets can be joined.
 *
 * Determines if datasets can be joined directly (same granularity)
 * or if they need time alignment (different granularities).
 *
 * @param datasets - Array of dataset info with structureType and/or rows
 * @returns Analysis result with joinability info
 *
 * @example
 * // Same granularity - direct join
 * analyzeJoinability([
 *   { structureType: 'daily_ohlcv' },
 *   { structureType: 'crypto_daily' },
 * ])
 * // => { canJoinDirectly: true, needsAlignment: false, ... }
 *
 * // Different granularity - needs alignment
 * analyzeJoinability([
 *   { structureType: 'fiscal_period_series' },
 *   { structureType: 'daily_ohlcv' },
 * ])
 * // => { canJoinDirectly: false, needsAlignment: true, suggestedTargetGranularity: 'quarterly', ... }
 */
export function analyzeJoinability(datasets: DatasetInfo[]): JoinAnalysis {
  // Handle edge cases
  if (datasets.length === 0) {
    return {
      canJoinDirectly: false,
      needsAlignment: false,
      granularities: [],
      suggestedTargetGranularity: null,
      reason: 'No datasets to analyze',
    };
  }

  if (datasets.length === 1) {
    const granularity = detectGranularity(datasets[0].structureType, datasets[0].rows);
    return {
      canJoinDirectly: true,
      needsAlignment: false,
      granularities: [granularity],
      suggestedTargetGranularity: null,
      reason: 'Single dataset - no join needed',
    };
  }

  // Detect granularity of each dataset
  const granularities = datasets.map((d) =>
    detectGranularity(d.structureType, d.rows)
  );

  // Check if all granularities are the same (or snapshot)
  const uniqueNonSnapshot = new Set(
    granularities.filter((g) => g !== 'snapshot')
  );

  // All snapshots - can join directly (pivot by symbol)
  if (uniqueNonSnapshot.size === 0) {
    return {
      canJoinDirectly: true,
      needsAlignment: false,
      granularities,
      suggestedTargetGranularity: 'snapshot',
      reason: 'All datasets are snapshots - can pivot by symbol',
    };
  }

  // All same granularity (ignoring snapshots) - can join directly
  if (uniqueNonSnapshot.size === 1) {
    const commonGranularity = [...uniqueNonSnapshot][0];
    return {
      canJoinDirectly: true,
      needsAlignment: false,
      granularities,
      suggestedTargetGranularity: commonGranularity,
      reason: `All datasets are ${commonGranularity} - can join directly`,
    };
  }

  // Mixed granularities - need alignment
  const targetGranularity = getCoarsestGranularity(granularities);
  const finer = [...uniqueNonSnapshot].filter(
    (g) => g !== targetGranularity
  );

  return {
    canJoinDirectly: false,
    needsAlignment: true,
    granularities,
    suggestedTargetGranularity: targetGranularity,
    reason: `Mixed granularities (${[...uniqueNonSnapshot].join(', ')}) - need to aggregate ${finer.join(', ')} to ${targetGranularity}`,
  };
}

// ============================================================================
// AGGREGATION FUNCTIONS
// ============================================================================

/**
 * Aggregate daily data rows into quarterly periods.
 *
 * Groups rows by symbol + year + quarter, then applies the specified
 * aggregation method to each field.
 *
 * @param rows - Array of data rows with a date field
 * @param dateField - Name of the field containing the date
 * @param fieldAggregations - Map of field name to aggregation method
 * @param symbolField - Name of the symbol field (default: 'symbol')
 * @returns Array of aggregated rows with calendarYear and period columns
 *
 * @example
 * const daily = [
 *   { symbol: 'BTC', date: '2024-01-15', close: 42000, volume: 100 },
 *   { symbol: 'BTC', date: '2024-02-15', close: 45000, volume: 150 },
 * ];
 * aggregateToQuarterly(daily, 'date', { close: 'last', volume: 'sum' })
 * // => [{ symbol: 'BTC', calendarYear: 2024, period: 'Q1', close: 45000, volume: 250 }]
 */
export function aggregateToQuarterly(
  rows: Record<string, unknown>[],
  dateField: string,
  fieldAggregations: FieldAggregations,
  symbolField = 'symbol'
): AggregatedRow[] {
  // Group rows by symbol + year + quarter
  const groups = new Map<string, Record<string, unknown>[]>();

  for (const row of rows) {
    const dateValue = row[dateField];
    if (!dateValue) continue;

    const date = new Date(dateValue as string | number | Date);
    const year = getCalendarYear(date);
    const quarter = getQuarter(date);
    const symbol = (row[symbolField] as string) || '_';
    const key = `${symbol}|${year}|${quarter}`;

    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(row);
  }

  // Aggregate each group
  const results: AggregatedRow[] = [];

  for (const [key, groupRows] of groups) {
    const [symbol, yearStr, quarter] = key.split('|');
    const result: AggregatedRow = {
      symbol,
      calendarYear: parseInt(yearStr),
      period: quarter,
    };

    // Apply aggregation for each field
    for (const [field, method] of Object.entries(fieldAggregations)) {
      const values = groupRows
        .map((r) => r[field])
        .filter((v) => v != null) as number[];

      result[field] = applyAggregation(values, method);
    }

    results.push(result);
  }

  // Sort by year desc, then quarter desc (newest first)
  results.sort((a, b) => {
    const yearA = a.calendarYear as number;
    const yearB = b.calendarYear as number;
    if (yearA !== yearB) {
      return yearB - yearA;
    }
    const quarterOrder: Record<string, number> = {
      Q4: 0,
      Q3: 1,
      Q2: 2,
      Q1: 3,
    };
    return (
      quarterOrder[a.period as string] - quarterOrder[b.period as string]
    );
  });

  return results;
}

/**
 * Aggregate data rows into monthly periods.
 *
 * @param rows - Array of data rows with a date field
 * @param dateField - Name of the field containing the date
 * @param fieldAggregations - Map of field name to aggregation method
 * @param symbolField - Name of the symbol field (default: 'symbol')
 * @returns Array of aggregated rows with year and month columns
 */
export function aggregateToMonthly(
  rows: Record<string, unknown>[],
  dateField: string,
  fieldAggregations: FieldAggregations,
  symbolField = 'symbol'
): AggregatedRow[] {
  const groups = new Map<string, Record<string, unknown>[]>();

  for (const row of rows) {
    const dateValue = row[dateField];
    if (!dateValue) continue;

    const date = new Date(dateValue as string | number | Date);
    const year = date.getFullYear();
    const month = date.getMonth() + 1; // 1-12
    const symbol = (row[symbolField] as string) || '_';
    const key = `${symbol}|${year}|${month}`;

    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(row);
  }

  const results: AggregatedRow[] = [];

  for (const [key, groupRows] of groups) {
    const [symbol, yearStr, monthStr] = key.split('|');
    const result: AggregatedRow = {
      symbol,
      year: parseInt(yearStr),
      month: parseInt(monthStr),
      date: `${yearStr}-${monthStr.padStart(2, '0')}-01`, // First of month
    };

    for (const [field, method] of Object.entries(fieldAggregations)) {
      const values = groupRows
        .map((r) => r[field])
        .filter((v) => v != null) as number[];
      result[field] = applyAggregation(values, method);
    }

    results.push(result);
  }

  results.sort((a, b) => {
    const yearDiff = (b.year as number) - (a.year as number);
    if (yearDiff !== 0) return yearDiff;
    return (b.month as number) - (a.month as number);
  });

  return results;
}

/**
 * Aggregate data rows into weekly periods.
 *
 * @param rows - Array of data rows with a date field
 * @param dateField - Name of the field containing the date
 * @param fieldAggregations - Map of field name to aggregation method
 * @param symbolField - Name of the symbol field (default: 'symbol')
 * @returns Array of aggregated rows with week start date
 */
export function aggregateToWeekly(
  rows: Record<string, unknown>[],
  dateField: string,
  fieldAggregations: FieldAggregations,
  symbolField = 'symbol'
): AggregatedRow[] {
  const groups = new Map<string, Record<string, unknown>[]>();

  // Get start of week (Monday)
  const getWeekStart = (date: Date): string => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    return d.toISOString().split('T')[0];
  };

  for (const row of rows) {
    const dateValue = row[dateField];
    if (!dateValue) continue;

    const date = new Date(dateValue as string | number | Date);
    const weekStart = getWeekStart(date);
    const symbol = (row[symbolField] as string) || '_';
    const key = `${symbol}|${weekStart}`;

    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(row);
  }

  const results: AggregatedRow[] = [];

  for (const [key, groupRows] of groups) {
    const [symbol, weekStart] = key.split('|');
    const result: AggregatedRow = {
      symbol,
      date: weekStart,
      weekStart,
    };

    for (const [field, method] of Object.entries(fieldAggregations)) {
      const values = groupRows
        .map((r) => r[field])
        .filter((v) => v != null) as number[];
      result[field] = applyAggregation(values, method);
    }

    results.push(result);
  }

  results.sort((a, b) => {
    return new Date(b.date as string).getTime() - new Date(a.date as string).getTime();
  });

  return results;
}

/**
 * Aggregate data to a target granularity.
 *
 * This is the main entry point for granularity alignment.
 * Routes to the appropriate aggregation function based on target granularity.
 *
 * @param rows - Array of data rows
 * @param sourceGranularity - The current granularity of the data
 * @param targetGranularity - The desired granularity to aggregate to
 * @param dateField - Name of the date field (default: 'date')
 * @param fieldAggregations - Optional custom aggregation methods per field
 * @param symbolField - Name of the symbol field (default: 'symbol')
 * @returns Aggregated data rows
 */
export function aggregateToGranularity(
  rows: Record<string, unknown>[],
  sourceGranularity: Granularity,
  targetGranularity: Granularity,
  dateField = 'date',
  fieldAggregations?: FieldAggregations,
  symbolField = 'symbol'
): AggregatedRow[] {
  // Can't aggregate coarser -> finer
  const orderIndex = (g: Granularity): number => GRANULARITY_ORDER.indexOf(g);
  if (orderIndex(sourceGranularity) >= orderIndex(targetGranularity)) {
    // Already at target or coarser - return as-is
    return rows as AggregatedRow[];
  }

  // Infer field aggregations if not provided
  const aggMethods = fieldAggregations || inferFieldAggregations(rows);

  switch (targetGranularity) {
    case 'weekly':
      return aggregateToWeekly(rows, dateField, aggMethods, symbolField);
    case 'monthly':
      return aggregateToMonthly(rows, dateField, aggMethods, symbolField);
    case 'quarterly':
      return aggregateToQuarterly(rows, dateField, aggMethods, symbolField);
    default:
      // No aggregation for snapshot, annual, or same granularity
      return rows as AggregatedRow[];
  }
}

/**
 * Infer aggregation methods for fields based on their names.
 *
 * Common patterns:
 * - open -> first
 * - close, adjClose -> last
 * - high -> max
 * - low -> min
 * - volume -> sum
 * - *_pct, *_change, *_ratio -> mean
 * - other numeric -> mean
 */
export function inferFieldAggregations(
  rows: Record<string, unknown>[]
): FieldAggregations {
  if (rows.length === 0) return {};

  const firstRow = rows[0];
  const result: FieldAggregations = {};

  for (const field of Object.keys(firstRow)) {
    const value = firstRow[field];
    
    // Skip non-numeric fields
    if (typeof value !== 'number') continue;
    
    // Skip date/key fields
    if (['date', 'symbol', 'calendarYear', 'period', 'year', 'month', 'weekStart'].includes(field)) {
      continue;
    }

    const fieldLower = field.toLowerCase();

    // OHLCV patterns
    if (fieldLower === 'open') {
      result[field] = 'first';
    } else if (fieldLower === 'close' || fieldLower === 'adjclose' || fieldLower === 'adj_close') {
      result[field] = 'last';
    } else if (fieldLower === 'high') {
      result[field] = 'max';
    } else if (fieldLower === 'low') {
      result[field] = 'min';
    } else if (fieldLower === 'volume' || fieldLower.includes('volume')) {
      result[field] = 'sum';
    }
    // Percentage/change fields should be averaged
    else if (
      fieldLower.includes('pct') ||
      fieldLower.includes('percent') ||
      fieldLower.includes('change') ||
      fieldLower.includes('ratio') ||
      fieldLower.includes('yield')
    ) {
      result[field] = 'avg';
    }
    // Default to avg for other numeric fields
    else {
      result[field] = 'avg';
    }
  }

  return result;
}