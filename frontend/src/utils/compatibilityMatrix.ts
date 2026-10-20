/**
 * Compatibility Matrix for Dataset Time Structures
 * 
 * Defines which data structure types can be joined together.
 * Used to warn users when selecting incompatible endpoints in Per-Type mode.
 * 
 * Backend has 17+ granular structure types which we consolidate into 4 categories:
 * - date: All date-indexed time series (daily_ohlcv, intraday, event_list, crypto_*, forex_*, etc.)
 * - fiscal: Quarterly/annual data (fiscal_period_series, year_quarter_indexed)
 * - snapshot: Point-in-time data with no time dimension (snapshot, market_wide, options_chain, etc.)
 * - none: Unknown/unrecognized structure type
 */

export type TimeStructure = 'date' | 'fiscal' | 'snapshot' | 'none';

/**
 * Compatibility matrix between time structure types.
 * 
 * - date + date: Compatible (join on date)
 * - date + fiscal: Compatible (can aggregate daily to quarterly)
 * - fiscal + fiscal: Compatible (join on calendarYear + period)
 * - snapshot + snapshot: Compatible (stack by symbol)
 * - snapshot + date/fiscal: INCOMPATIBLE (no time dimension to align)
 * - none + anything: INCOMPATIBLE (unknown structure)
 */
const COMPATIBILITY: Record<TimeStructure, Record<TimeStructure, boolean>> = {
  date:     { date: true,  fiscal: true,  snapshot: false, none: false },
  fiscal:   { date: true,  fiscal: true,  snapshot: false, none: false },
  snapshot: { date: false, fiscal: false, snapshot: true,  none: false },
  none:     { date: false, fiscal: false, snapshot: false, none: false },
};

/**
 * Maps backend structure types to frontend time structure categories.
 * 
 * Backend types come from field_mappings.py ENDPOINT_TO_STRUCTURE_TYPE.
 * Frontend categories are simplified for user-facing compatibility warnings.
 */
export function mapBackendToTimeStructure(backendType: string | undefined): TimeStructure {
  if (!backendType) return 'none';
  
  const mapping: Record<string, TimeStructure> = {
    // =========================================================================
    // SNAPSHOT - Point-in-time data, no time dimension
    // =========================================================================
    'snapshot': 'snapshot',
    'market_wide': 'snapshot',
    'options_chain': 'snapshot',
    'options_market': 'snapshot',
    'options_market_isolated': 'snapshot',
    'reference': 'snapshot',
    
    // =========================================================================
    // DATE - Time series indexed by date/datetime
    // =========================================================================
    'daily_ohlcv': 'date',
    'intraday': 'date',
    'event_list': 'date',
    'event_isolated': 'date',
    
    // Crypto time series
    'crypto_daily': 'date',
    'crypto_intraday': 'date',
    
    // Forex time series
    'forex_daily': 'date',
    'forex_intraday': 'date',
    
    // Commodity time series
    'commodity_daily': 'date',
    'commodity_intraday': 'date',
    
    // Other date-indexed
    'sec_filing_search': 'date',
    'options_flow': 'date',
    'options_contract': 'date',
    
    // =========================================================================
    // FISCAL - Quarterly/annual fiscal period data
    // =========================================================================
    'fiscal_period_series': 'fiscal',
    'year_quarter_indexed': 'fiscal',
  };
  
  return mapping[backendType] || 'none';
}

/**
 * Check if a set of time structures are compatible for joining.
 * 
 * @param structures - Array of time structures to check
 * @returns Object with compatibility result and any incompatible pairs found
 */
export function checkStructureCompatibility(structures: TimeStructure[]): {
  compatible: boolean;
  incompatiblePairs: [TimeStructure, TimeStructure][];
} {
  const incompatiblePairs: [TimeStructure, TimeStructure][] = [];
  const uniqueStructures = [...new Set(structures)];
  
  // Check all pairs for compatibility
  for (let i = 0; i < uniqueStructures.length; i++) {
    for (let j = i + 1; j < uniqueStructures.length; j++) {
      const struct1 = uniqueStructures[i];
      const struct2 = uniqueStructures[j];
      
      if (!COMPATIBILITY[struct1][struct2]) {
        incompatiblePairs.push([struct1, struct2]);
      }
    }
  }
  
  return {
    compatible: incompatiblePairs.length === 0,
    incompatiblePairs,
  };
}

/**
 * Get human-readable label for a time structure.
 */
export function getStructureLabel(structure: TimeStructure): string {
  const labels: Record<TimeStructure, string> = {
    date: 'Time Series',
    fiscal: 'Fiscal Period',
    snapshot: 'Snapshot',
    none: 'Unknown',
  };
  return labels[structure];
}

/**
 * Get detailed description for a time structure.
 */
export function getStructureDescription(structure: TimeStructure): string {
  const descriptions: Record<TimeStructure, string> = {
    date: 'Date-indexed time series data (daily, intraday, events)',
    fiscal: 'Quarterly or annual fiscal period data',
    snapshot: 'Point-in-time data without time dimension',
    none: 'Unknown or unrecognized data structure',
  };
  return descriptions[structure];
}

/**
 * Check if two specific structures are compatible.
 */
export function areStructuresCompatible(struct1: TimeStructure, struct2: TimeStructure): boolean {
  return COMPATIBILITY[struct1][struct2];
}
