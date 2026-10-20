/**
 * useSingleObjectForm - Single Object Form Hook
 * 
 * This hook manages the single-object data entry form state.
 * 
 * State is divided into:
 * - PERSISTED state: Stored in Zustand (survives tab switches and page reload)
 * - TRANSIENT state: Local useState (search UI, loading flags)
 * 
 * The persisted state is the single source of truth via formStateSlice.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import api from '@/services/api';
import type { FormMode, EndpointInfo } from '@/features/canvas/types';
import { useDataWorkspaceStore } from '../../stores/dataWorkspaceStore';
import {
  selectFormMode,
  selectFormSelectedSymbol,
  selectFormCustomIdentifier,
  selectFormSelectedEndpoint,
  selectFormSelectedFields,
  selectFormParams,
  selectFormExpandedCategories,
  selectFormSourceFilter,
} from '../../stores/selectors';
import {
  detectObjectType,
  loadEndpointsForType,
  groupEndpointsByCategory,
  countEndpointsBySource,
  getSmartParamDefaults,
  mergeParamsWithDefaults,
} from '../utils/queryUtils';

export function useSingleObjectForm() {
  // ============================================================================
  // PERSISTED STATE - From Zustand store (formStateSlice)
  // ============================================================================
  
  const formMode = useDataWorkspaceStore(selectFormMode);
  const formSelectedSymbol = useDataWorkspaceStore(selectFormSelectedSymbol);
  const formCustomIdentifier = useDataWorkspaceStore(selectFormCustomIdentifier);
  const formSelectedEndpoint = useDataWorkspaceStore(selectFormSelectedEndpoint);
  const formSelectedFields = useDataWorkspaceStore(selectFormSelectedFields);
  const formParams = useDataWorkspaceStore(selectFormParams);
  const formExpandedCategoriesArray = useDataWorkspaceStore(selectFormExpandedCategories);
  const formSourceFilter = useDataWorkspaceStore(selectFormSourceFilter);
  
  // Store actions
  const setFormMode = useDataWorkspaceStore(s => s.setFormMode);
  const setFormSelectedSymbol = useDataWorkspaceStore(s => s.setFormSelectedSymbol);
  const setFormCustomIdentifier = useDataWorkspaceStore(s => s.setFormCustomIdentifier);
  const setFormSelectedEndpoint = useDataWorkspaceStore(s => s.setFormSelectedEndpoint);
  const setFormSelectedFields = useDataWorkspaceStore(s => s.setFormSelectedFields);
  const setFormParams = useDataWorkspaceStore(s => s.setFormParams);
  const setFormExpandedCategoriesAction = useDataWorkspaceStore(s => s.setFormExpandedCategories);
  const setFormSourceFilter = useDataWorkspaceStore(s => s.setFormSourceFilter);
  
  // Convert array to Set for compatibility with existing API
  const formExpandedCategories = useMemo(
    () => new Set(formExpandedCategoriesArray),
    [formExpandedCategoriesArray]
  );
  
  // Wrapper to convert Set to array when updating
  const setFormExpandedCategories = useCallback(
    (categories: Set<string>) => setFormExpandedCategoriesAction(Array.from(categories)),
    [setFormExpandedCategoriesAction]
  );
  
  // ============================================================================
  // TRANSIENT STATE - Local (search UI, loading flags)
  // ============================================================================
  
  const [formSymbolSearch, setFormSymbolSearch] = useState('');
  const [formSymbolResults, setFormSymbolResults] = useState<Array<{ symbol: string; name: string; exchange?: string }>>([]);
  const [formSymbolSearching, setFormSymbolSearching] = useState(false);
  const [formEndpoints, setFormEndpoints] = useState<EndpointInfo[]>([]);
  const [formEndpointsLoading, setFormEndpointsLoading] = useState(false);

  // ============================================================================
  // EFFECTS - Reload transient state when persisted state is restored
  // ============================================================================

  // When switching tabs, formSelectedSymbol is restored from store
  // but formEndpoints is stale/empty - reload if needed
  useEffect(() => {
    if (formSelectedSymbol && formEndpoints.length === 0 && !formEndpointsLoading) {
      loadEndpointsForType(formSelectedSymbol.objectType).then(endpoints => {
        setFormEndpoints(endpoints);
      }).catch(err => {
        console.error('Failed to reload endpoints for restored symbol:', err);
      });
    }
  }, [formSelectedSymbol, formEndpoints.length, formEndpointsLoading]);

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const searchFormSymbol = useCallback(async (query: string) => {
    if (query.length < 1) {
      setFormSymbolResults([]);
      return;
    }
    try {
      const res = await api.get('/api/ticker-search', { params: { q: query, limit: 8 } });
      setFormSymbolResults(res.data || []);
    } catch (e) {
      console.error('Symbol search error:', e);
      setFormSymbolResults([]);
    }
  }, []);

  const loadFormEndpoints = useCallback(async (objectType: string) => {
    setFormEndpointsLoading(true);
    try {
      const endpoints = await loadEndpointsForType(objectType);
      setFormEndpoints(endpoints);
    } catch (e) {
      console.error('Failed to load endpoints:', e);
      setFormEndpoints([]);
    } finally {
      setFormEndpointsLoading(false);
    }
  }, []);

  const handleFormSymbolSelect = useCallback(async (result: { symbol: string; name: string; exchange?: string }) => {
    // Use backend detection for accurate object type (e.g., ETF vs equity)
    let objectType: string;
    try {
      const detectRes = await api.post('/api/canvas/data/objects/detect', { symbol: result.symbol });
      objectType = detectRes.data.object_type || detectObjectType(result.symbol, result.exchange);
    } catch {
      // Fall back to frontend detection if backend fails
      objectType = detectObjectType(result.symbol, result.exchange);
    }
    
    setFormSelectedSymbol({ symbol: result.symbol, name: result.name, objectType });
    setFormSymbolSearch('');
    setFormSymbolResults([]);
    setFormSelectedEndpoint(null);
    setFormSelectedFields([]);
    setFormParams({});
    loadFormEndpoints(objectType);
  }, [loadFormEndpoints, setFormSelectedSymbol, setFormSelectedEndpoint, setFormSelectedFields, setFormParams]);

  const handleEndpointSelect = useCallback((ep: EndpointInfo) => {
    setFormSelectedEndpoint(ep);
    setFormSelectedFields([]);
    const defaults = getSmartParamDefaults(ep);
    setFormParams(mergeParamsWithDefaults(defaults, formParams));
  }, [formParams, setFormSelectedEndpoint, setFormSelectedFields, setFormParams]);

  const handleFormFieldToggle = useCallback((fieldName: string) => {
    if (formSelectedFields.includes(fieldName)) {
      setFormSelectedFields(formSelectedFields.filter(f => f !== fieldName));
    } else {
      setFormSelectedFields([...formSelectedFields, fieldName]);
    }
  }, [formSelectedFields, setFormSelectedFields]);

  const handleSelectAllFields = useCallback(() => {
    if (formSelectedEndpoint) {
      setFormSelectedFields(formSelectedEndpoint.fields);
    }
  }, [formSelectedEndpoint, setFormSelectedFields]);

  // ============================================================================
  // COMPUTED VALUES
  // ============================================================================

  // Group endpoints by category with source filtering
  const formEndpointsByCategory = useMemo(() => {
    return groupEndpointsByCategory(formEndpoints, formSourceFilter);
  }, [formEndpoints, formSourceFilter]);

  // Count endpoints by source for filter badges
  const formEndpointsBySource = useMemo(() => {
    return countEndpointsBySource(formEndpoints);
  }, [formEndpoints]);

  return {
    // Persisted state (from store)
    formMode,
    setFormMode,
    formSelectedSymbol,
    setFormSelectedSymbol,
    formCustomIdentifier,
    setFormCustomIdentifier,
    formSelectedEndpoint,
    setFormSelectedEndpoint,
    formSelectedFields,
    setFormSelectedFields,
    formParams,
    setFormParams,
    formExpandedCategories,
    setFormExpandedCategories,
    formSourceFilter,
    setFormSourceFilter,
    
    // Transient state (local)
    formSymbolSearch,
    setFormSymbolSearch,
    formSymbolResults,
    setFormSymbolResults,
    formSymbolSearching,
    setFormSymbolSearching,
    formEndpoints,
    setFormEndpoints,
    formEndpointsLoading,
    setFormEndpointsLoading,
    
    // Handlers
    searchFormSymbol,
    loadFormEndpoints,
    handleFormSymbolSelect,
    handleEndpointSelect,
    handleFormFieldToggle,
    handleSelectAllFields,
    
    // Computed values
    formEndpointsByCategory,
    formEndpointsBySource,
  };
}
