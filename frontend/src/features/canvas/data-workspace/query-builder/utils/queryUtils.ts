/**
 * Shared utilities for Single and Multi Object forms
 */

import api from '@/services/api';
import type { 
  EndpointInfo, 
  EquivalenceGroup, 
  EndpointEquivalenceResponse, 
  Granularity,
  TimeGroup,
  EndpointTimeInfo,
  TimeGroupEndpoints,
  EndpointsByTimeGroupResponse,
  JoinStrategy,
} from '@/features/canvas/types';

/**
 * Detect object type from symbol and optional exchange
 */
export const detectObjectType = (symbol: string, exchange?: string): string => {
  const sym = symbol.toUpperCase();
  if (sym === '_MARKET_' || sym === 'MARKET' || sym === '') return 'market';
  if (sym.includes('-USD') || sym.includes('USDT') || sym.endsWith('BTC') || sym.endsWith('ETH')) return 'crypto';
  if (sym.match(/^[A-Z]{3}\/[A-Z]{3}$/) || (sym.match(/^[A-Z]{6}$/) && !exchange)) return 'forex';
  if (exchange && ['ARCA', 'BATS'].includes(exchange.toUpperCase())) return 'etf';
  return 'equity';
};

/**
 * Load endpoints for a given object type from the API
 */
export const loadEndpointsForType = async (objectType: string): Promise<EndpointInfo[]> => {
  try {
    const res = await api.get('/api/canvas/data/fields/grouped/' + objectType);
    const endpoints: EndpointInfo[] = [];
    Object.entries(res.data || {}).forEach(([category, endpointMap]: [string, any]) => {
      Object.entries(endpointMap).forEach(([endpoint, fields]: [string, any]) => {
        const fieldList = fields as any[];
        const required_params = fieldList[0]?.required_params || [];
        const source = fieldList[0]?.source || 'fmp';
        const structureType = fieldList[0]?.structure_type;
        const filteredParams = required_params.filter((p: string) =>
          !['apikey', 'apiKey', 'symbol', 'symbols', 'ticker', 'tickers'].includes(p.toLowerCase())
        );
        endpoints.push({
          endpoint,
          category,
          required_params: filteredParams,
          fields: fieldList.map((f: any) => f.field),
          source,
          structureType,
        });
      });
    });
    return endpoints;
  } catch (e) {
    console.error('Failed to load endpoints:', e);
    return [];
  }
};

/**
 * Group endpoints by category with optional source filtering
 */
export const groupEndpointsByCategory = (
  endpoints: EndpointInfo[],
  sourceFilter: string = 'all'
): Record<string, EndpointInfo[]> => {
  const grouped: Record<string, EndpointInfo[]> = {};
  endpoints
    .filter(ep => {
      if (sourceFilter === 'all') return true;
      // Normalize source: "unusualwhales" -> "uw"
      const normalizedSource = ep.source === 'unusualwhales' ? 'uw' : ep.source;
      return normalizedSource === sourceFilter;
    })
    .forEach(ep => {
      const cat = ep.category || 'Other';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(ep);
    });
  return grouped;
};

/**
 * Count endpoints by source for filter badges
 */
export const countEndpointsBySource = (endpoints: EndpointInfo[]): Record<string, number> => {
  const counts: Record<string, number> = { all: endpoints.length, fmp: 0, polygon: 0, uw: 0 };
  endpoints.forEach(ep => {
    // Normalize source: "unusualwhales" -> "uw"
    const normalizedSource = ep.source === 'unusualwhales' ? 'uw' : ep.source;
    if (counts[normalizedSource] !== undefined) counts[normalizedSource]++;
  });
  return counts;
};

/**
 * Get smart default parameter values based on endpoint requirements
 */
export const getSmartParamDefaults = (ep: EndpointInfo): Record<string, string> => {
  const defaults: Record<string, string> = {};
  const params = ep.required_params.map(p => p.toLowerCase());
  
  // Special handling for screener endpoints
  if (ep.endpoint.includes('screener')) {
    defaults['limit'] = '100';
    return defaults;
  }
  
  // ===== PAGINATION =====
  if (params.includes('limit')) {
    defaults['limit'] = '20';
  }
  if (params.includes('page')) {
    defaults['page'] = '0';
  }
  if (params.includes('size')) {
    defaults['size'] = '20';
  }
  
  // ===== PERIOD/TIME =====
  if (params.includes('period')) {
    // For year+period endpoints like financial-reports-json, use 'FY'
    if (params.includes('year') && !params.includes('quarter')) {
      defaults['period'] = 'FY';
    } else {
      defaults['period'] = 'annual';
    }
  }
  if (params.includes('year')) {
    defaults['year'] = String(new Date().getFullYear());
  }
  if (params.includes('quarter')) {
    // Default to previous quarter
    const currentQ = Math.ceil((new Date().getMonth() + 1) / 3);
    defaults['quarter'] = String(currentQ > 1 ? currentQ - 1 : 4);
  }
  if (params.includes('timeframe') || params.includes('timespan')) {
    defaults['timeframe'] = 'day';
    defaults['timespan'] = 'day';
  }
  if (params.includes('multiplier')) {
    defaults['multiplier'] = '1';
  }
  if (params.includes('interval')) {
    defaults['interval'] = '1Y';
  }
  
  // ===== DATE RANGES =====
  const today = new Date();
  const todayStr = today.toISOString().split('T')[0];
  
  // FMP style: from/to
  if (params.includes('from') || params.includes('to')) {
    const yearAgo = new Date();
    yearAgo.setFullYear(yearAgo.getFullYear() - 1);
    defaults['from'] = yearAgo.toISOString().split('T')[0];
    defaults['to'] = todayStr;
  }
  
  // UW style: start_date/end_date
  if (params.includes('start_date') || params.includes('end_date')) {
    const yearAgo = new Date();
    yearAgo.setFullYear(yearAgo.getFullYear() - 1);
    defaults['start_date'] = yearAgo.toISOString().split('T')[0];
    defaults['end_date'] = todayStr;
  }
  
  // Single date param (common in UW endpoints) - default to today
  if (params.includes('date') && !params.includes('start_date') && !params.includes('end_date') && !params.includes('from')) {
    defaults['date'] = todayStr;
  }
  
  // ===== OPTIONS EXPIRY (UW endpoints) =====
  // Use next monthly expiry (3rd Friday of month)
  if (params.includes('expiry') || params.includes('expirations')) {
    const getMonthlyExpiry = (): string => {
      const today = new Date();
      const date = new Date();
      date.setDate(1); // Start at 1st of current month
      
      // Find first Friday
      while (date.getDay() !== 5) {
        date.setDate(date.getDate() + 1);
      }
      // Add 2 weeks to get 3rd Friday
      date.setDate(date.getDate() + 14);
      
      // If this expiry has already passed, use next month
      if (date < today) {
        const nextMonth = new Date();
        nextMonth.setMonth(nextMonth.getMonth() + 1);
        nextMonth.setDate(1);
        while (nextMonth.getDay() !== 5) {
          nextMonth.setDate(nextMonth.getDate() + 1);
        }
        nextMonth.setDate(nextMonth.getDate() + 14);
        return `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}-${String(nextMonth.getDate()).padStart(2, '0')}`;
      }
      
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    };
    
    const expiryDate = getMonthlyExpiry();
    if (params.includes('expiry')) defaults['expiry'] = expiryDate;
    if (params.includes('expirations')) defaults['expirations'] = expiryDate;
  }
  
  // ===== TECHNICAL INDICATORS =====
  if (params.includes('periodlength')) {
    defaults['periodLength'] = '14';
  }
  if (params.includes('window')) {
    defaults['window'] = '14';
  }
  if (params.includes('series_type')) {
    defaults['series_type'] = 'close';
  }
  if (params.includes('fast')) {
    defaults['fast'] = '12';
  }
  if (params.includes('slow')) {
    defaults['slow'] = '26';
  }
  if (params.includes('signal')) {
    defaults['signal'] = '9';
  }
  
  // ===== FLAGS =====
  if (params.includes('adjusted')) {
    defaults['adjusted'] = 'true';
  }
  if (params.includes('direction')) {
    defaults['direction'] = 'gainers';
  }
  
  // Legacy support for other params
  ep.required_params.forEach(p => {
    const pl = p.toLowerCase();
    if (pl.includes('date') && pl.includes('from') && !defaults[p]) {
      const d = new Date();
      d.setFullYear(d.getFullYear() - 1);
      defaults[p] = d.toISOString().split('T')[0];
    }
    if (pl.includes('date') && pl.includes('to')) {
      defaults[p] = new Date().toISOString().split('T')[0];
    }
  });
  
  return defaults;
};

/**
 * Merge smart defaults with preserved identifier params
 */
export const mergeParamsWithDefaults = (
  defaults: Record<string, string>,
  prevParams: Record<string, string>
): Record<string, string> => {
  return {
    ...defaults,
    ...(prevParams.options_ticker && { options_ticker: prevParams.options_ticker }),
    ...(prevParams.fx_ticker && { fx_ticker: prevParams.fx_ticker }),
    ...(prevParams.crypto_ticker && { crypto_ticker: prevParams.crypto_ticker }),
    ...(prevParams.symbol && !defaults.symbol && { symbol: prevParams.symbol }),
  };
};

/**
 * Get source badge color classes
 */
export const getSourceColor = (source: string, isSelected: boolean): string => {
  // Normalize "unusualwhales" -> "uw"
  const normalizedSource = source === 'unusualwhales' ? 'uw' : source;
  const colors: Record<string, string> = {
    fmp: 'bg-blue-100 text-blue-700',
    polygon: 'bg-purple-100 text-purple-700',
    uw: 'bg-orange-100 text-orange-700',
  };
  return colors[normalizedSource] || 'bg-slate-200 text-slate-600';
};

/**
 * Get source display label
 */
export const getSourceLabel = (source: string): string => {
  // Normalize "unusualwhales" -> "uw"
  const normalizedSource = source === 'unusualwhales' ? 'uw' : source;
  const labels: Record<string, string> = {
    fmp: 'FMP',
    polygon: 'Poly',
    uw: 'UW',
  };
  return labels[normalizedSource] || source;
};

// =============================================================================
// ENDPOINT EQUIVALENCE - For cross-asset joins
// =============================================================================

/**
 * Load endpoints for multiple object types and compute equivalence groups.
 * 
 * This enables cross-asset joins by finding endpoints that serve the same
 * semantic purpose across different asset types (e.g., historical prices
 * for equity vs crypto vs forex).
 */
export const loadEndpointsWithEquivalence = async (
  objectTypes: string[]
): Promise<{
  byType: Record<string, EndpointInfo[]>;
  equivalenceGroups: EquivalenceGroup[];
  granularitiesDetected: Granularity[];
  hasMixedGranularity: boolean;
}> => {
  // Load endpoints for each type in parallel
  const endpointPromises = objectTypes.map(async (ot) => ({
    type: ot,
    endpoints: await loadEndpointsForType(ot),
  }));
  
  const results = await Promise.all(endpointPromises);
  const byType: Record<string, EndpointInfo[]> = {};
  results.forEach(({ type, endpoints }) => {
    byType[type] = endpoints;
  });
  
  // Fetch equivalence groups from backend
  let equivalenceGroups: EquivalenceGroup[] = [];
  let granularitiesDetected: Granularity[] = [];
  let hasMixedGranularity = false;
  
  if (objectTypes.length >= 2) {
    try {
      const res = await api.post<EndpointEquivalenceResponse>(
        '/api/canvas/data/endpoint-equivalence',
        { object_types: objectTypes, threshold: 0.5 }
      );
      equivalenceGroups = res.data.equivalence_groups;
      granularitiesDetected = res.data.granularities_detected;
      hasMixedGranularity = res.data.has_mixed_granularity;
    } catch (e) {
      console.error('Failed to load endpoint equivalence:', e);
      // Fall back to empty - will use strict matching
    }
  }
  
  return {
    byType,
    equivalenceGroups,
    granularitiesDetected,
    hasMixedGranularity,
  };
};

/**
 * Find endpoints that are available across all selected object types.
 * 
 * Uses equivalence groups to match semantically equivalent endpoints
 * (e.g., historical-price-full for equity matches crypto-historical-eod-full).
 */
export const getEquivalentEndpoints = (
  objectTypes: string[],
  endpointsByType: Record<string, EndpointInfo[]>,
  equivalenceGroups: EquivalenceGroup[]
): EndpointInfo[] => {
  if (objectTypes.length === 0) return [];
  
  if (objectTypes.length === 1) {
    // Single type - return all its endpoints
    return endpointsByType[objectTypes[0]] || [];
  }
  
  // Multiple types - use equivalence groups
  const result: EndpointInfo[] = [];
  
  for (const group of equivalenceGroups) {
    // Check if this group covers ALL selected object types
    const coversAll = objectTypes.every((ot) => group.endpoints[ot]);
    if (!coversAll) continue;
    
    // Use the first type's endpoint as the representative
    const primaryType = objectTypes[0];
    const primaryEndpointName = group.endpoints[primaryType];
    const primaryEndpoints = endpointsByType[primaryType] || [];
    const primaryEndpoint = primaryEndpoints.find((ep) => ep.endpoint === primaryEndpointName);
    
    if (primaryEndpoint) {
      result.push({
        ...primaryEndpoint,
        equivalenceGroup: group.canonical,
        granularity: group.granularity,
        structureType: group.structure_type,
      });
    }
  }
  
  return result;
};

/**
 * Get the actual endpoint name for a specific object type from an equivalence group.
 * 
 * Use this when fetching data to get the correct endpoint name for each symbol's type.
 */
export const resolveEndpointForType = (
  equivalenceGroup: string,
  objectType: string,
  equivalenceGroups: EquivalenceGroup[]
): string => {
  const group = equivalenceGroups.find((g) => g.canonical === equivalenceGroup);
  if (group && group.endpoints[objectType]) {
    return group.endpoints[objectType];
  }
  // Fallback to canonical name
  return equivalenceGroup;
};

/**
 * Get human-readable granularity label
 */
export const getGranularityLabel = (granularity: Granularity): string => {
  const labels: Record<Granularity, string> = {
    snapshot: 'Snapshot (Point-in-time)',
    daily: 'Daily',
    weekly: 'Weekly',
    monthly: 'Monthly',
    quarterly: 'Quarterly',
    intraday: 'Intraday',
    event: 'Event-based',
    unknown: 'Unknown',
  };
  return labels[granularity] || granularity;
};

/**
 * Check if aggregation is needed between two granularities
 */
export const needsAggregation = (source: Granularity, target: Granularity): boolean => {
  const granularityOrder: Granularity[] = ['intraday', 'daily', 'weekly', 'monthly', 'quarterly'];
  const sourceIdx = granularityOrder.indexOf(source);
  const targetIdx = granularityOrder.indexOf(target);
  
  // Can only aggregate from finer to coarser granularity
  return sourceIdx >= 0 && targetIdx >= 0 && sourceIdx < targetIdx;
};

// =============================================================================
// TIME-KEY BASED ENDPOINT GROUPING - For heterogeneous joins
// =============================================================================

/**
 * Load endpoints grouped by time-key compatibility for multiple object types.
 * 
 * This enables heterogeneous joins - selecting different endpoints per object type
 * (e.g., income-statement for equity + fx-historical for forex) and joining them
 * on their common time key.
 */
export const loadEndpointsByTimeGroup = async (
  objectTypes: string[]
): Promise<{
  byTypeAndGroup: Record<string, TimeGroupEndpoints>;
  allEndpoints: Record<string, EndpointTimeInfo[]>;
}> => {
  try {
    const res = await api.post<EndpointsByTimeGroupResponse>(
      '/api/canvas/data/endpoints-by-time-group',
      { object_types: objectTypes }
    );
    
    const byTypeAndGroup = res.data.endpoints_by_type;
    
    // Also flatten for easy access
    const allEndpoints: Record<string, EndpointTimeInfo[]> = {};
    for (const [objType, groups] of Object.entries(byTypeAndGroup)) {
      allEndpoints[objType] = [
        ...groups.date,
        ...groups.fiscal_period,
        ...groups.snapshot,
      ];
    }
    
    return { byTypeAndGroup, allEndpoints };
  } catch (e) {
    console.error('Failed to load endpoints by time group:', e);
    return { byTypeAndGroup: {}, allEndpoints: {} };
  }
};

/**
 * Analyze join strategy for selected endpoints across object types.
 */
export const analyzeJoinStrategy = async (
  selectedEndpoints: Record<string, string>
): Promise<JoinStrategy> => {
  try {
    const res = await api.post<JoinStrategy>(
      '/api/canvas/data/join-strategy',
      { selected_endpoints: selectedEndpoints }
    );
    return res.data;
  } catch (e) {
    console.error('Failed to analyze join strategy:', e);
    return {
      strategy: 'incompatible',
      time_groups: [],
      granularities: [],
      common_time_key: null,
      needs_aggregation: false,
      aggregation_target: null,
      error: 'Failed to analyze join strategy',
    };
  }
};

/**
 * Convert EndpointTimeInfo to EndpointInfo for compatibility with existing UI components.
 */
export const timeInfoToEndpointInfo = (info: EndpointTimeInfo): EndpointInfo => ({
  endpoint: info.endpoint,
  category: info.category,
  required_params: info.required_params || [],
  fields: info.fields,
  source: 'fmp', // Default
  structureType: info.structure_type,
  granularity: info.granularity,
});

/**
 * Get endpoints filtered by time group for a specific object type.
 */
export const getEndpointsForTimeGroup = (
  byTypeAndGroup: Record<string, TimeGroupEndpoints>,
  objectType: string,
  timeGroup: TimeGroup
): EndpointTimeInfo[] => {
  const typeGroups = byTypeAndGroup[objectType];
  if (!typeGroups) return [];
  return typeGroups[timeGroup] || [];
};

/**
 * Get all endpoints for an object type (including snapshots).
 * 
 * Previously excluded snapshots, but now includes all endpoint types.
 * The UI warns users when incompatible structures are selected via StructureTypeWarning.
 */
export const getJoinableEndpoints = (
  byTypeAndGroup: Record<string, TimeGroupEndpoints>,
  objectType: string
): EndpointTimeInfo[] => {
  const typeGroups = byTypeAndGroup[objectType];
  if (!typeGroups) return [];
  return [
    ...typeGroups.date,
    ...typeGroups.fiscal_period,
    ...typeGroups.snapshot,  // Now included - UI warns on incompatible combinations
  ];
};

/**
 * Group endpoints by category from EndpointTimeInfo array.
 */
export const groupTimeEndpointsByCategory = (
  endpoints: EndpointTimeInfo[]
): Record<string, EndpointTimeInfo[]> => {
  const grouped: Record<string, EndpointTimeInfo[]> = {};
  for (const ep of endpoints) {
    const cat = ep.category || 'Other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(ep);
  }
  return grouped;
};

/**
 * Find common fields across multiple endpoints (for heterogeneous field selection).
 */
export const findCommonFields = (
  endpoints: EndpointTimeInfo[]
): string[] => {
  if (endpoints.length === 0) return [];
  if (endpoints.length === 1) return endpoints[0].fields;
  
  const fieldSets = endpoints.map(ep => new Set(ep.fields));
  const commonFields: string[] = [];
  
  for (const field of fieldSets[0]) {
    if (fieldSets.every(set => set.has(field))) {
      commonFields.push(field);
    }
  }
  
  return commonFields;
};

/**
 * Get fields grouped by endpoint/type for heterogeneous selection UI.
 */
export const getFieldsByEndpoint = (
  selectedEndpoints: Record<string, EndpointTimeInfo>
): {
  common: string[];
  byType: Record<string, { endpoint: string; fields: string[] }>;
} => {
  const endpoints = Object.values(selectedEndpoints);
  const common = findCommonFields(endpoints);
  const commonSet = new Set(common);
  
  const byType: Record<string, { endpoint: string; fields: string[] }> = {};
  for (const [objType, ep] of Object.entries(selectedEndpoints)) {
    byType[objType] = {
      endpoint: ep.endpoint,
      fields: ep.fields.filter(f => !commonSet.has(f)),
    };
  }
  
  return { common, byType };
};
